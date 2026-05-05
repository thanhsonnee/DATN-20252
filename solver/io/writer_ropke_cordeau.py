"""
Phase 9 – Solution writer for Ropke & Cordeau PDPTW format.

Output format mirrors the style used by Ropke & Cordeau benchmark solutions:

  Instance name : <name>
  Authors       : <authors>
  Date          : YYYY-MM-DD
  Reference     : <reference>
  Solution
  Route k : n1 n2 ... nm

Routes list only customer node IDs (no depot); 1-based route index.
This matches the Sartori writer convention so solutions are interchangeable.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

from solver.models import Instance, Solution


def write_ropke_cordeau_solution(
    instance: Instance,
    solution: Solution,
    path: str,
    author: str = "Thanh Son",
    reference: str = "Thanh Son PDPTW Solver",
) -> None:
    """
    Write a solution file compatible with the Ropke & Cordeau format.

    Parameters
    ----------
    instance  : solved Instance (used for name and node metadata)
    solution  : Solution to write
    path      : output file path (created with parents if needed)
    author    : author(s) string written to the header
    reference : reference / algorithm description written to the header
    """
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    num_routes = sum(1 for r in solution.routes if r.stops)
    today = date.today().strftime("%Y-%m-%d")

    with out_path.open("w", encoding="utf-8") as f:
        f.write(f"Instance name : {instance.name}\n")
        f.write(f"Authors       : {author}\n")
        f.write(f"Date          : {today}\n")
        f.write(f"Reference     : {reference}\n")
        f.write(f"Num routes    : {num_routes}\n")
        f.write(f"Total cost    : {solution.total_cost}\n")
        f.write("Solution\n")

        route_idx = 1
        for route in solution.routes:
            if not route.stops:
                continue
            node_str = " ".join(str(n) for n in route.stops)
            f.write(f"Route {route_idx} : {node_str}\n")
            route_idx += 1
