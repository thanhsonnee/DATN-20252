"""
Phase 7 – Exact layer: Set Partitioning (SP).

RoutePool accumulates feasible routes discovered during ALNS.
solve_set_partitioning() periodically selects the best subset of pooled
routes such that every request is covered exactly once, using a MILP solved
by PuLP (optional dependency).  If PuLP is unavailable the call is a no-op.

MILP formulation
----------------
Variables : x_r ∈ {0,1}  for each route r in pool
Objective : min  Σ_r  cost_r · x_r   (cost = num_routes_penalty + travel_time)
Subject to:
  Σ_{r : covers request i}  x_r  = 1   ∀ request i   (partition)

The penalty-weighted cost is used so the MILP also minimises vehicle count.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from solver.construction import ROUTE_PENALTY
from solver.constraints import check_route_feasible
from solver.models import Instance, Route, Solution

logger = logging.getLogger(__name__)

# Maximum pool size – oldest routes are evicted when exceeded
_MAX_POOL_SIZE = 500
# Minimum pool size before SP is attempted
_MIN_POOL_FOR_SP = 10


@dataclass
class _PoolEntry:
    route: Route
    req_ids: frozenset  # request IDs fully served by this route
    cost: float         # scalar cost (ROUTE_PENALTY + travel_time)


class RoutePool:
    """
    Stores a bounded collection of distinct feasible routes.

    Deduplication is by frozenset of (request_id) covered.  If a new route
    covers the same set of requests with lower cost, it replaces the old entry.
    """

    def __init__(self, max_size: int = _MAX_POOL_SIZE) -> None:
        self.max_size = max_size
        self._entries: Dict[frozenset, _PoolEntry] = {}

    def add(self, route: Route, instance: Instance) -> bool:
        """
        Add a feasible route to the pool.

        Returns True if the route was added or improved an existing entry.
        """
        if not route.stops:
            return False

        node_to_req = getattr(instance, "_node_to_req", None)
        if node_to_req is None:
            from solver.constraints import _get_node_to_request_maps
            node_to_req, _ = _get_node_to_request_maps(instance)

        # Identify which requests are fully served by this route
        present = set(route.stops)
        req_ids: set[int] = set()
        for nid in present:
            req = node_to_req.get(nid)
            if req is None:
                continue
            if req.pickup_node in present and req.delivery_node in present:
                req_ids.add(req.id)

        if not req_ids:
            return False

        key = frozenset(req_ids)
        cost = ROUTE_PENALTY + float(route.total_travel_time)

        existing = self._entries.get(key)
        if existing is not None and existing.cost <= cost:
            return False  # existing is at least as good

        self._entries[key] = _PoolEntry(route=route.copy(), req_ids=key, cost=cost)

        # Evict cheapest-cover routes when over capacity
        if len(self._entries) > self.max_size:
            worst_key = max(self._entries, key=lambda k: self._entries[k].cost)
            del self._entries[worst_key]

        return True

    def add_solution(self, solution: Solution, instance: Instance) -> int:
        """Add all routes from a complete solution. Returns count added."""
        added = 0
        for route in solution.routes:
            if route.stops and self.add(route, instance):
                added += 1
        return added

    def __len__(self) -> int:
        return len(self._entries)

    @property
    def entries(self) -> List[_PoolEntry]:
        return list(self._entries.values())


def solve_set_partitioning(
    pool: RoutePool,
    instance: Instance,
    time_limit_sec: float = 10.0,
) -> Optional[Solution]:
    """
    Solve the Set Partitioning MILP over the route pool.

    Returns a Solution if a better partition was found, else None.
    Requires PuLP; returns None silently if not installed.
    """
    try:
        import pulp  # type: ignore
    except ImportError:
        logger.debug("PuLP not installed – Set Partitioning skipped.")
        return None

    entries = pool.entries
    if len(entries) < _MIN_POOL_FOR_SP:
        return None

    n_req = instance.num_requests()
    req_ids = [req.id for req in instance.requests]
    req_index = {rid: i for i, rid in enumerate(req_ids)}

    # Build coverage matrix: entry_idx -> set of request indices it covers
    coverage: List[set[int]] = []
    for e in entries:
        coverage.append({req_index[rid] for rid in e.req_ids if rid in req_index})

    # Only keep entries that cover at least one request
    valid = [(e, cov) for e, cov in zip(entries, coverage) if cov]
    if not valid:
        return None

    prob = pulp.LpProblem("SetPartitioning", pulp.LpMinimize)

    x = [pulp.LpVariable(f"x_{i}", cat="Binary") for i in range(len(valid))]

    # Objective
    prob += pulp.lpSum(e.cost * x[i] for i, (e, _) in enumerate(valid))

    # Partition constraints: each request covered exactly once
    for ri in range(n_req):
        covering = [x[i] for i, (_, cov) in enumerate(valid) if ri in cov]
        if not covering:
            # Request not in pool at all – SP cannot produce a complete solution
            return None
        prob += pulp.lpSum(covering) == 1, f"req_{ri}"

    solver = pulp.PULP_CBC_CMD(msg=0, timeLimit=int(time_limit_sec))
    status = prob.solve(solver)

    if pulp.LpStatus[status] not in ("Optimal", "Feasible"):
        return None

    selected_routes: List[Route] = []
    for i, (e, _) in enumerate(valid):
        if pulp.value(x[i]) is not None and pulp.value(x[i]) > 0.5:
            selected_routes.append(e.route.copy())

    if not selected_routes:
        return None

    # Recompute schedules (routes come from pool, already feasible)
    for r in selected_routes:
        check_route_feasible(instance, r)

    total_cost = int(sum(r.total_travel_time for r in selected_routes))
    return Solution(routes=selected_routes, total_cost=total_cost)
