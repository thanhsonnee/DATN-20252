from __future__ import annotations

from datetime import date
from pathlib import Path

from solver.models import Instance, Solution


def write_lilim_solution(
    instance: Instance,
    solution: Solution,
    path: str,
    author: str = "Thanh Son",
    reference: str = "Thanh Son PDPTW Solver",
) -> None:
    """
    Write a solution file for Li & Lim instances.

    Format:
        Instance name : <name>
        Authors       : <author>
        Date          : YYYY-MM-DD
        Reference     : <reference>
        Vehicles      : <num_routes>
        Distance      : <total_cost>
        Solution
        Route 1 : 0 n1 n2 ... 0
        Route 2 : 0 n3 n4 ... 0
        ...

    Routes include depot node (0) at start and end.
    """
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    non_empty = [r for r in solution.routes if r.stops]
    today_str = date.today().strftime("%Y-%m-%d")

    with out_path.open("w", encoding="utf-8") as f:
        f.write(f"Instance name : {instance.name}\n")
        f.write(f"Authors       : {author}\n")
        f.write(f"Date          : {today_str}\n")
        f.write(f"Reference     : {reference}\n")
        f.write(f"Vehicles      : {len(non_empty)}\n")
        f.write(f"Distance      : {solution.total_cost}\n")
        f.write("Solution\n")

        depot = instance.depot_id
        for idx, route in enumerate(non_empty, start=1):
            node_str = " ".join(str(n) for n in route.stops)
            f.write(f"Route {idx} : {depot} {node_str} {depot}\n")
