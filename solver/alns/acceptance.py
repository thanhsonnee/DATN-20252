"""
Acceptance criterion: simulated annealing (accept better or worse with probability).
"""
from __future__ import annotations

import math

from solver.construction import ROUTE_PENALTY
from solver.models import Solution


def _scalar_cost(solution: Solution) -> float:
    """Single scalar: fewer routes preferred, then lower travel time."""
    num_routes = sum(1 for r in solution.routes if r.stops)
    return num_routes * ROUTE_PENALTY + solution.total_cost


def accept_sa(
    current: Solution,
    candidate: Solution,
    temperature: float,
    rng,
) -> bool:
    """
    Accept candidate with probability 1 if better, else exp(-delta / T).
    Better = fewer routes, or same routes and lower total_cost.
    """
    if temperature <= 0:
        return _scalar_cost(candidate) < _scalar_cost(current)
    delta = _scalar_cost(candidate) - _scalar_cost(current)
    if delta <= 0:
        return True
    return rng.random() < math.exp(-delta / temperature)
