"""
ALNS state: current solution, best solution, and comparison (routes first, then cost).
"""
from __future__ import annotations

import time
from typing import Optional

from solver.models import Instance, Solution


def _num_routes(sol: Solution) -> int:
    return sum(1 for r in sol.routes if r.stops)


def _is_better(new: Solution, best: Solution) -> bool:
    """True if new is better than best: fewer routes, or same routes and lower cost."""
    nr_new = _num_routes(new)
    nr_best = _num_routes(best)
    if nr_new < nr_best:
        return True
    if nr_new > nr_best:
        return False
    return new.total_cost < best.total_cost


class AlnsState:
    def __init__(self, instance: Instance, initial: Solution):
        self.instance = instance
        self.current = initial.copy()
        self.best = initial.copy()
        self.start_time = time.perf_counter()
        self.iterations = 0

    def elapsed(self) -> float:
        return time.perf_counter() - self.start_time

    def is_better_than_best(self, solution: Solution) -> bool:
        return _is_better(solution, self.best)

    def accept_current_as_new(self, new_solution: Solution) -> None:
        """Update current to new_solution. If new is better than best, update best too."""
        self.current = new_solution.copy()
        if _is_better(new_solution, self.best):
            self.best = new_solution.copy()

    def get_best(self) -> Solution:
        return self.best

    def get_current(self) -> Solution:
        return self.current
