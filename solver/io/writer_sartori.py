from __future__ import annotations

from datetime import date
from pathlib import Path

from solver.models import Instance, Solution


def write_sartori_solution(
    instance: Instance,
    solution: Solution,
    path: str,
    author: str = "Thanh Son",
    reference: str = "Thanh Son PDPTW Solver",
) -> None:
    """
    Write a solution file in the Sartori/Buriol format.

    The format follows sample.txt and existing files in solutions/files:
    - Instance name : <instance name>
    - Authors       : <authors>
    - Date          : YYYY-MM-DD
    - Reference     : <reference text>
    - Solution
    - Route k : n1 n2 ... nm

    Routes list only customer nodes (no depot node).
    """

    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    today_str = date.today().strftime("%Y-%m-%d")

    with out_path.open("w", encoding="utf-8") as f:
        f.write(f"Instance name : {instance.name}\n")
        f.write(f"Authors       : {author}\n")
        f.write(f"Date          : {today_str}\n")
        f.write(f"Reference     : {reference}\n")
        f.write("Solution\n")

        for idx, route in enumerate(solution.routes, start=1):
            if not route.stops:
                continue
            node_str = " ".join(str(n) for n in route.stops)
            f.write(f"Route {idx} : {node_str}\n")

