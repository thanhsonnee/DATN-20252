"""
Shortcut to run PDPTW solver. Usage:

  python run.py bar-n1000-3
  python run.py bar-n100-1 --method regret

Instance name is resolved to instances/sartori-dataset/n1000/n1000/<name>.txt
(or n100, n200, ... inferred from the name).
"""
from __future__ import annotations

import argparse
import re
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def infer_instance_path(name: str) -> Path:
    """Infer path for Sartori instance from bare name like bar-n1000-3."""
    m = re.search(r"n(\d+)", name, re.I)
    n = m.group(1) if m else "1000"
    base = ROOT / "instances" / "sartori-dataset" / f"n{n}" / f"n{n}"
    if not base.exists():
        base = ROOT / "instances" / f"n{n}" / f"n{n}"
    p = base / (name if name.endswith(".txt") else f"{name}.txt")
    return p


def main() -> None:
    ap = argparse.ArgumentParser(description="Run PDPTW solver.")
    ap.add_argument("instance", nargs="?", default="bar-n1000-3",
                    help="Instance name (Sartori: bar-n1000-3) or full path to file")
    ap.add_argument("--dataset-type", choices=["sartori", "lilim", "ropke_cordeau"],
                    default=None,
                    help="Dataset format. Auto-detected from path if omitted.")
    ap.add_argument("--method", choices=["greedy", "regret", "sweep", "best"], default="best")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--time-limit", type=float, default=60.0,
                    help="ALNS time limit in seconds (0 = construction only)")
    args = ap.parse_args()

    inst_path = Path(args.instance)
    if not inst_path.is_absolute() and not inst_path.exists():
        inst_path = infer_instance_path(args.instance)
    if not inst_path.exists():
        raise SystemExit(f"Instance not found: {inst_path}")

    # Auto-detect dataset type from path if not specified
    dataset_type = args.dataset_type
    if dataset_type is None:
        p = str(inst_path).lower()
        if "lilim" in p:
            dataset_type = "lilim"
        elif "ropke" in p or inst_path.suffix == ".pdptw":
            dataset_type = "ropke_cordeau"
        else:
            dataset_type = "sartori"

    import random

    from solver.construction import build_initial_solution
    from solver.io import write_sartori_solution, write_lilim_solution, write_ropke_cordeau_solution
    from solver.parsers import load_instance

    from solver.preprocess import precompute, quick_feasibility_check

    rng = random.Random(args.seed)
    instance = load_instance(str(inst_path), dataset_type=dataset_type)

    if not quick_feasibility_check(instance):
        raise SystemExit(f"Instance {instance.name} failed quick feasibility check — skipping.")
    precompute(instance)

    from solver.alns.local_search import try_empty_one_route

    def _n_routes(s):
        return sum(1 for r in s.routes if r.stops)

    def _scalar(s):
        from solver.construction import ROUTE_PENALTY
        return _n_routes(s) * ROUTE_PENALTY + s.total_cost

    t_start = time.perf_counter()

    if args.time_limit > 0:
        from solver.alns import run_alns

        n_req = len(instance.requests)
        # small (n100, ≤75 req): 3 fast starts for diversity
        # medium/large (n200+): 2 deeper starts, more time each
        N_STARTS = 3 if n_req <= 75 else 2
        time_per = args.time_limit / N_STARTS
        best_solution = None

        for start_i in range(N_STARTS):
            t_s = time.perf_counter()
            rng_i = random.Random(args.seed + start_i)
            sol_i = build_initial_solution(instance, rng=rng_i, method=args.method)
            changed = True
            while changed:
                changed = try_empty_one_route(instance, sol_i)
            result_i = run_alns(instance, sol_i, time_limit_sec=time_per, seed=args.seed + start_i)
            candidate = result_i.solution
            n_r = sum(1 for r in candidate.routes if r.stops)
            improved = best_solution is None or _scalar(candidate) < _scalar(best_solution)
            if improved:
                best_solution = candidate
            print(f"  Start {start_i+1}/{N_STARTS}: {n_r} routes, cost {candidate.total_cost:.1f}"
                  f"  ({time.perf_counter()-t_s:.1f}s){'  ← best' if improved else ''}")

        # Post-processing: aggressively match or beat BKS by iterating
        #   elimination → route-merge → exhaustive local search → intra-route
        # until no further improvement (or time budget exhausted).
        from solver.alns.local_search import (
            force_eliminate_routes, exhaustive_improve,
            intra_route_two_opt, intra_route_or_opt,
            try_route_merge_pair, try_eliminate_exhaustive,
            lns_eliminate_route,
        )
        t_post = time.perf_counter()
        rng_post = random.Random(args.seed)
        elim_attempts = max(5, min(25, n_req // 4))
        elim_trials   = max(4, min(15, n_req // 8))

        solution = best_solution
        # Soft time budget for post-process; scales with instance size
        pp_budget = max(15.0, min(120.0, args.time_limit * 0.25))
        pp_start = time.perf_counter()

        prev_scalar = float("inf")
        max_iters = 8 if n_req >= 100 else 4
        for _pp_iter in range(max_iters):
            if time.perf_counter() - pp_start > pp_budget:
                break

            # 1. Aggressive elimination via ejection + regret repair
            solution = force_eliminate_routes(
                instance, solution, rng_post,
                max_attempts=elim_attempts, trials_per_route=elim_trials,
            )
            # 2. Exhaustive per-route elimination (stronger, no sampling)
            try_eliminate_exhaustive(instance, solution, rng_post, max_rounds=3)
            # 2b. LNS-assisted elimination: eject target route + random subset of
            # other routes, then exhaustively re-pack. Loops until no gain.
            while time.perf_counter() - pp_start < pp_budget:
                if not lns_eliminate_route(instance, solution, rng_post, trials=10):
                    break
            # 3. Pair-wise merge (exhaustive, fast for small→medium)
            merged = True
            while merged and time.perf_counter() - pp_start < pp_budget:
                merged = try_route_merge_pair(instance, solution)
            # 4. Simple empty-one-route pass
            changed = True
            while changed:
                changed = try_empty_one_route(instance, solution)
            # 5. Inter-route exhaustive local search (2-opt*, relocate)
            if time.perf_counter() - pp_start < pp_budget:
                solution = exhaustive_improve(instance, solution, rng_post)
            # 6. Intra-route polish (2-opt + or-opt within each route)
            changed = True
            while changed:
                c1 = intra_route_two_opt(instance, solution)
                c2 = intra_route_or_opt(instance, solution)
                changed = c1 or c2

            cur_scalar = _scalar(solution)
            if cur_scalar >= prev_scalar - 1e-6:
                break
            prev_scalar = cur_scalar

        print(f"  Post-process: {time.perf_counter()-t_post:.1f}s"
              f"  ({sum(1 for r in solution.routes if r.stops)} routes, cost {solution.total_cost:.1f})")
    else:
        solution = build_initial_solution(instance, rng=rng, method=args.method)
        changed = True
        while changed:
            changed = try_empty_one_route(instance, solution)

    t_elapsed = time.perf_counter() - t_start
    num_routes = sum(1 for r in solution.routes if r.stops)

    out_dir = ROOT / "solutions" / "my_solver"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{instance.name}.{num_routes}_{solution.total_cost}.txt"

    writer_map = {
        "sartori":       write_sartori_solution,
        "lilim":         write_lilim_solution,
        "ropke_cordeau": write_ropke_cordeau_solution,
    }
    writer = writer_map.get(dataset_type, write_sartori_solution)
    writer(
        instance=instance,
        solution=solution,
        path=str(out_path),
        author="Thanh Son",
        reference="Thanh Son PDPTW Solver",
    )

    print(f"Solved {instance.name}: {num_routes} routes, cost {solution.total_cost:.1f}  [{t_elapsed:.1f}s]")
    print(f"Output: {out_path.resolve()}")


if __name__ == "__main__":
    main()
