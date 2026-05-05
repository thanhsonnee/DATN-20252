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
    ap = argparse.ArgumentParser(description="Run PDPTW solver (Sartori dataset).")
    ap.add_argument("instance", nargs="?", default="bar-n1000-3", help="Instance name (e.g. bar-n1000-3)")
    ap.add_argument("--method", choices=["greedy", "regret", "best"], default="greedy")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--time-limit", type=float, default=60.0, help="ALNS time limit in seconds (0 = construction only)")
    args = ap.parse_args()

    inst_path = Path(args.instance)
    if not inst_path.is_absolute() and not inst_path.exists():
        inst_path = infer_instance_path(args.instance)
    if not inst_path.exists():
        raise SystemExit(f"Instance not found: {inst_path}")

    import random

    from solver.construction import build_initial_solution
    from solver.io import write_sartori_solution
    from solver.parsers import load_instance

    rng = random.Random(args.seed)
    instance = load_instance(str(inst_path), dataset_type="sartori")
    solution = build_initial_solution(instance, rng=rng, method=args.method)
    if args.time_limit > 0:
        from solver.alns import run_alns
        solution = run_alns(instance, solution, time_limit_sec=args.time_limit, seed=args.seed)
    num_routes = sum(1 for r in solution.routes if r.stops)

    out_dir = ROOT / "solutions" / "my_solver"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{instance.name}.{num_routes}_{solution.total_cost}.txt"

    write_sartori_solution(
        instance=instance,
        solution=solution,
        path=str(out_path),
        author="Thanh Son",
        reference="Thanh Son PDPTW Solver",
    )

    print(f"Solved {instance.name}: {num_routes} routes, cost {solution.total_cost}")
    print(f"Output: {out_path.resolve()}")


if __name__ == "__main__":
    main()
