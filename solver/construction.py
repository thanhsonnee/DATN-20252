"""
Initial feasible solution for PDPTW: greedy and regret-k insertion by request.
"""
from __future__ import annotations

import random
from typing import List, Optional, Tuple

from solver.constraints import check_route_feasible
from solver.models import Instance, Request, Route, Solution

# Hierarchical objective: minimize number of routes first, then total travel time.
ROUTE_PENALTY = 1e9  # prefer any feasible insert over opening a new route


def _insert_nodes(stops: List[int], pickup: int, delivery: int, pi: int, di: int) -> List[int]:
    """
    Insert pickup at position pi (in original stops) and delivery at position di
    (in after-pickup-inserted list). pi in [0..n], di in [pi+1..n+1].
    Returns new stop list of length len(stops)+2.
    """
    after_pick = list(stops[:pi]) + [pickup] + list(stops[pi:])
    return list(after_pick[:di]) + [delivery] + list(after_pick[di:])


def _cost_after_insert(
    instance: Instance,
    route: Route,
    req: Request,
    pickup_idx: int,
    delivery_idx: int,
) -> Optional[float]:
    """
    Try inserting req at (pickup_idx, delivery_idx). Returns new total travel time if feasible, else None.
    """
    stops = route.stops
    new_stops = _insert_nodes(stops, req.pickup_node, req.delivery_node, pickup_idx, delivery_idx)
    if len(new_stops) != len(stops) + 2:
        return None
    temp = Route(stops=new_stops)
    if not check_route_feasible(instance, temp):
        return None
    return float(temp.total_travel_time)


def _best_insertion(
    instance: Instance,
    routes: List[Route],
    req: Request,
) -> Tuple[Optional[int], Optional[int], Optional[int], float]:
    """
    Best insertion: minimize (1) number of new routes, (2) incremental travel time.
    Returns (route_index, pickup_idx, delivery_idx, score). route_index=-1 means new route.
    """
    best_route: Optional[int] = None
    best_pi: Optional[int] = None
    best_di: Optional[int] = None
    best_score: float = 1e30

    # New route option
    single_route = Route(stops=[req.pickup_node, req.delivery_node])
    if check_route_feasible(instance, single_route):
        score = ROUTE_PENALTY + float(single_route.total_travel_time)
        if score < best_score:
            best_route, best_pi, best_di, best_score = -1, 0, 1, score

    for ri, route in enumerate(routes):
        if not route.stops:
            continue
        n = len(route.stops)
        base_cost = float(route.total_travel_time)
        for pi in range(0, n + 1):
            for di in range(pi + 1, n + 2):
                new_total = _cost_after_insert(instance, route, req, pi, di)
                if new_total is not None:
                    score = new_total - base_cost
                    if score < best_score:
                        best_score = score
                        best_route, best_pi, best_di = ri, pi, di

    if best_route is None:
        return (None, None, None, 1e30)
    return (best_route, best_pi, best_di, best_score)


def apply_insertion(
    instance: Instance,
    routes: List[Route],
    req: Request,
    route_index: int,
    pickup_idx: int,
    delivery_idx: int,
) -> None:
    """
    Apply insertion: add req to routes at (route_index, pickup_idx, delivery_idx).
    route_index < 0: append new route with only this request.
    Modifies routes in place and runs check_route_feasible to fill schedule.
    """
    if route_index < 0:
        new_route = Route(stops=[req.pickup_node, req.delivery_node])
        check_route_feasible(instance, new_route)
        routes.append(new_route)
        return
    route = routes[route_index]
    route.stops = _insert_nodes(route.stops, req.pickup_node, req.delivery_node, pickup_idx, delivery_idx)
    check_route_feasible(instance, route)


def build_initial_solution_greedy(
    instance: Instance,
    rng: Optional[random.Random] = None,
) -> Solution:
    """
    Greedy insertion: repeatedly insert the request with minimum cost increase.
    Request order: by tw_early of pickup (then random tie-break).
    """
    if rng is None:
        rng = random.Random()
    requests = list(instance.requests)
    requests.sort(key=lambda r: (instance.nodes[r.pickup_node].tw_early, rng.random()))

    routes: List[Route] = []
    for req in requests:
        best_route, best_pi, best_di, _ = _best_insertion(instance, routes, req)
        if best_route is None:
            # Even a standalone route is infeasible — skip (should be rare).
            new_route = Route(stops=[req.pickup_node, req.delivery_node])
            if check_route_feasible(instance, new_route):
                routes.append(new_route)
            continue
        apply_insertion(instance, routes, req, best_route, best_pi, best_di)

    return Solution(routes=routes, total_cost=int(sum(r.total_travel_time for r in routes)))


def build_initial_solution_regret(
    instance: Instance,
    k: int = 3,
    rng: Optional[random.Random] = None,
) -> Solution:
    """
    Regret-k insertion: at each step, choose the request with largest regret
    (difference between k-th best and best insertion cost), insert at best position.
    """
    if rng is None:
        rng = random.Random()
    unassigned = list(instance.requests)
    routes: List[Route] = []

    while unassigned:
        best_req: Optional[Request] = None
        best_route_idx: Optional[int] = None
        best_pi: Optional[int] = None
        best_di: Optional[int] = None
        best_regret = -1.0

        for req in unassigned:
            ri, pi, di, _ = _best_insertion(instance, routes, req)
            if ri is None:
                continue

            # Collect all feasible insertion costs for regret computation.
            costs: List[float] = []
            single = Route(stops=[req.pickup_node, req.delivery_node])
            if check_route_feasible(instance, single):
                costs.append(ROUTE_PENALTY + float(single.total_travel_time))
            for route in routes:
                if not route.stops:
                    continue
                base = float(route.total_travel_time)
                n = len(route.stops)
                for pii in range(0, n + 1):
                    for dii in range(pii + 1, n + 2):
                        new_total = _cost_after_insert(instance, route, req, pii, dii)
                        if new_total is not None:
                            costs.append(new_total - base)
            costs.sort()
            if not costs:
                continue

            c_best = costs[0]
            c_k = costs[min(k - 1, len(costs) - 1)]
            regret = c_k - c_best
            if regret > best_regret:
                best_regret = regret
                best_req = req
                best_route_idx, best_pi, best_di = ri, pi, di

        if best_req is None or best_route_idx is None:
            break

        unassigned.remove(best_req)
        apply_insertion(instance, routes, best_req, best_route_idx, best_pi, best_di)

    return Solution(routes=routes, total_cost=int(sum(r.total_travel_time for r in routes)))


def build_initial_solution_sweep(
    instance: Instance,
    rng: Optional[random.Random] = None,
) -> Solution:
    """
    Sweep (angle-based nearest-neighbour) construction.

    1. Compute the polar angle of each request's pickup node from the depot.
    2. Sort requests by angle (sweep order), breaking ties by tw_early.
    3. Insert each request greedily into the *last open route* first; if that
       fails, try all existing routes; if all fail, open a new route.

    This tends to produce geographically compact routes and gives a diverse
    starting point compared with pure greedy/regret insertion.
    """
    import math as _math

    if rng is None:
        rng = random.Random()

    depot = instance.depot_id
    dep_node = instance.nodes[depot]
    dx, dy = dep_node.lat, dep_node.lon

    def _angle(req: Request) -> float:
        p = instance.nodes[req.pickup_node]
        return _math.atan2(p.lon - dy, p.lat - dx)

    requests = sorted(
        instance.requests,
        key=lambda r: (_angle(r), instance.nodes[r.pickup_node].tw_early),
    )

    routes: List[Route] = []

    for req in requests:
        inserted = False

        # Try last open route first (keeps routes compact)
        if routes:
            route = routes[-1]
            n = len(route.stops)
            for pi in range(0, n + 1):
                for di in range(pi + 1, n + 2):
                    new_stops = _insert_nodes(route.stops, req.pickup_node, req.delivery_node, pi, di)
                    temp = Route(stops=new_stops)
                    if check_route_feasible(instance, temp):
                        routes[-1] = temp
                        inserted = True
                        break
                if inserted:
                    break

        # Fall back to best insertion across all routes
        if not inserted:
            ri, pi, di, _ = _best_insertion(instance, routes, req)
            if ri is not None:
                apply_insertion(instance, routes, req, ri, pi, di)
                inserted = True

        # Open a new route
        if not inserted:
            new_route = Route(stops=[req.pickup_node, req.delivery_node])
            if check_route_feasible(instance, new_route):
                routes.append(new_route)

    return Solution(routes=routes, total_cost=int(sum(r.total_travel_time for r in routes)))


def build_initial_solution(
    instance: Instance,
    rng: Optional[random.Random] = None,
    method: str = "greedy",
) -> Solution:
    """
    Build initial feasible solution.

    method choices:
      'greedy'  – greedy best-insertion sorted by tw_early
      'regret'  – regret-3 insertion
      'sweep'   – angle-sweep construction (new)
      'best'    – run greedy + regret + sweep, return best
    """
    if rng is None:
        rng = random.Random()
    if method == "regret":
        return build_initial_solution_regret(instance, k=3, rng=rng)
    if method == "sweep":
        return build_initial_solution_sweep(instance, rng=rng)
    if method == "best":
        sols = [
            build_initial_solution_greedy(instance, rng=rng),
            build_initial_solution_regret(instance, k=3, rng=rng),
            build_initial_solution_regret(instance, k=5, rng=rng),
            build_initial_solution_sweep(instance, rng=rng),
        ]
        return min(sols, key=lambda s: (
            sum(1 for r in s.routes if r.stops),
            s.total_cost,
        ))
    return build_initial_solution_greedy(instance, rng=rng)
