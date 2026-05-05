"""
Phase 8 – Fix-and-Optimize (F&O).

Strategy (Stage 3 intensification):
  1. Sort routes by cost contribution (cheapest first = "good" routes).
  2. Fix the cheapest ceil(fix_ratio * n_routes) routes – do not touch them.
  3. Eject all requests from the remaining routes.
  4. Re-insert ejected requests using regret repair + local search.
  5. Return the new solution if it is better than the input, else return input.

The function is designed to be called periodically during Stage 3 of ALNS
when the best solution has not improved for a while.
"""
from __future__ import annotations

import math
import random
from typing import List

from solver.alns.local_search import LocalSearchConfig, local_search
from solver.alns.operators_repair import greedy_repair, regret_repair
from solver.constraints import check_route_feasible
from solver.construction import ROUTE_PENALTY
from solver.models import Instance, Request, Route, Solution


def _scalar_cost(solution: Solution) -> float:
    n = sum(1 for r in solution.routes if r.stops)
    return n * ROUTE_PENALTY + solution.total_cost


def _route_cost(route: Route, instance: Instance) -> float:
    """Scalar cost of a single route (re-evaluates if needed)."""
    if not route.stops:
        return 0.0
    check_route_feasible(instance, route)
    return float(route.total_travel_time)


def _requests_on_route(route: Route, instance: Instance) -> List[Request]:
    """Return requests fully served by this route."""
    node_to_req = getattr(instance, "_node_to_req", None)
    if node_to_req is None:
        from solver.constraints import _get_node_to_request_maps
        node_to_req, _ = _get_node_to_request_maps(instance)

    present = set(route.stops)
    seen: set[int] = set()
    result: List[Request] = []
    for nid in present:
        req = node_to_req.get(nid)
        if req is None or req.id in seen:
            continue
        if req.pickup_node in present and req.delivery_node in present:
            seen.add(req.id)
            result.append(req)
    return result


def fix_and_optimize(
    instance: Instance,
    solution: Solution,
    rng: random.Random,
    fix_ratio: float = 0.6,
    ls_max_moves: int = 40,
) -> Solution:
    """
    Run one Fix-and-Optimize pass.

    Parameters
    ----------
    instance    : problem instance
    solution    : current best complete solution
    rng         : random state (for repair operators)
    fix_ratio   : fraction of routes to fix (0 < fix_ratio < 1)
    ls_max_moves: local-search budget after re-insertion

    Returns the improved solution, or the original if no improvement found.
    """
    routes = [r for r in solution.routes if r.stops]
    n = len(routes)
    if n < 2:
        return solution

    # Sort routes: cheapest (most "efficient") first
    routes_sorted = sorted(routes, key=lambda r: _route_cost(r, instance))

    n_fix = max(1, min(n - 1, math.ceil(fix_ratio * n)))
    fixed_routes = [r.copy() for r in routes_sorted[:n_fix]]
    free_routes = routes_sorted[n_fix:]

    # Collect requests to re-insert
    ejected: List[Request] = []
    for r in free_routes:
        ejected.extend(_requests_on_route(r, instance))

    if not ejected:
        return solution

    # Build partial solution from fixed routes only
    partial = Solution(
        routes=fixed_routes,
        total_cost=int(sum(r.total_travel_time for r in fixed_routes)),
    )

    # Re-insert ejected requests
    candidate = regret_repair(
        instance, partial, ejected, rng,
        k=3,
        route_samples=12,
        pos_trials_per_route=30,
        ejection_max=2,
        ejection_tries=20,
    )

    # Local search on result
    if candidate.routes:
        candidate = local_search(
            instance, candidate, rng=rng,
            cfg=LocalSearchConfig(
                max_moves=ls_max_moves,
                route_samples=10,
                pos_trials_per_route=28,
                first_improvement=True,
                p_relocate=0.50,
                p_swap=0.30,
                p_or_opt=0.20,
            ),
        )

    # Check completeness
    served: set[int] = set()
    for r in candidate.routes:
        served.update(r.stops)
    all_served = all(
        req.pickup_node in served and req.delivery_node in served
        for req in instance.requests
    )

    if all_served and _scalar_cost(candidate) < _scalar_cost(solution):
        return candidate

    return solution
