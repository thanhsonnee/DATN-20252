from __future__ import annotations

import argparse
import random
from pathlib import Path

from solver.construction import build_initial_solution
from solver.io import write_sartori_solution
from solver.parsers import load_instance


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="PDPTW initial solver (construction only).")
    parser.add_argument(
        "--instance",
        required=True,
        help="Path to instance file.",
    )
    parser.add_argument(
        "--dataset-type",
        choices=["sartori", "lilim", "ropke_cordeau"],
        default="sartori",
        help="Type of dataset/format for the instance.",
    )
    parser.add_argument(
        "--method",
        choices=["greedy", "regret", "best"],
        default="greedy",
        help="Construction method for the initial solution.",
    )
    parser.add_argument(
        "--output",
        required=False,
        help="Path to output solution file. "
        "If omitted (recommended), a name like <instance>.<vehicles>_<cost>.txt "
        "will be created automatically under solutions/my_solver/ (for Sartori).",
    )
    parser.add_argument(
        "--author",
        default="Thanh Son",
        help="Authors line for the solution header.",
    )
    parser.add_argument(
        "--reference",
        default="Thanh Son PDPTW Solver",
        help="Reference line for the solution header.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=0,
        help="Random seed for construction heuristics.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    rng = random.Random(args.seed)

    instance = load_instance(args.instance, dataset_type=args.dataset_type)
    solution = build_initial_solution(instance, rng=rng, method=args.method)

    num_routes = sum(1 for r in solution.routes if r.stops)

    if args.dataset_type != "sartori":
        raise SystemExit("Currently automatic writer is implemented only for Sartori dataset.")

    if args.output:
        out_path = Path(args.output)
    else:
        # Auto-generate a Sartori-style filename: <instance>.<vehicles>_<cost>.txt
        out_dir = Path("solutions") / "my_solver"
        out_dir.mkdir(parents=True, exist_ok=True)
        inst_name = instance.name
        out_path = out_dir / f"{inst_name}.{num_routes}_{solution.total_cost}.txt"

    write_sartori_solution(
        instance=instance,
        solution=solution,
        path=str(out_path),
        author=args.author,
        reference=args.reference,
    )

    print(
        f"Solved instance {instance.name} "
        f"with {num_routes} routes, total travel time {solution.total_cost}."
    )
    print(f"Solution written to: {out_path.resolve()}")


if __name__ == "__main__":
    main()

