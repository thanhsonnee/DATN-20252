"""
Initial feasible solution for PDPTW: greedy and regret-k insertion by request.
"""
from __future__ import annotations

import random
from typing import List, Optional, Tuple

from solver.constraints import check_route_feasible
from solver.models import Instance, Request, Route, Solution

# Hierarchical objective: minimize number of routes first, then total travel time.
# So "cost" for choosing an option = (1 if new route else 0) * ROUTE_PENALTY + incremental_travel_time.
ROUTE_PENALTY = 1e9  # prefer any feasible insert over opening a new route


def _cost_after_insert(
    instance: Instance,
    route: Route,
    req: Request,
    pickup_idx: int,
    delivery_idx: int,
) -> Optional[float]:
    """
    Insert pickup at position pickup_idx and delivery at delivery_idx (0-based in new sequence).
    pickup_idx < delivery_idx. Returns new total travel time if feasible, else None.
    """
    stops = route.stops
    n = len(stops)
    # New stops: ... pickup_idx positions from original, then pickup, then (delivery_idx - pickup_idx - 1) from original, then delivery, then rest
    new_stops = (
        stops[:pickup_idx]
        + [req.pickup_node, req.delivery_node]
        + stops[pickup_idx:delivery_idx - 1]
        + stops[delivery_idx - 1:]
    )
    # Correct: insert pickup so it is at index pickup_idx in new list, delivery at index delivery_idx.
    # new_stops = [original[0..pickup_idx), pickup, original[pickup_idx..delivery_idx-1), delivery, original[delivery_idx-1..)]
    # So new_stops has length: pickup_idx + 1 + (delivery_idx-1-pickup_idx) + 1 + (n - (delivery_idx-1)) = n+2. And delivery_idx runs from pickup_idx+1 to n+1.
    new_stops = (
        list(stops[:pickup_idx])
        + [req.pickup_node]
        + list(stops[pickup_idx : delivery_idx - 1])
        + [req.delivery_node]
        + list(stops[delivery_idx - 1 :])
    )
    if len(new_stops) != n + 2:
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
    Uses ROUTE_PENALTY so that inserting into an existing route is preferred over opening a new one.
    Returns (route_index, pickup_idx, delivery_idx, score). route_index -1 = new route.
    """
    best_route: Optional[int] = None
    best_pi: Optional[int] = None
    best_di: Optional[int] = None
    best_score: float = 1e30

    # New route: score = ROUTE_PENALTY + travel time (so we prefer insert when feasible)
    new_stops = [req.pickup_node, req.delivery_node]
    single_route = Route(stops=new_stops)
    if check_route_feasible(instance, single_route):
        score = ROUTE_PENALTY + float(single_route.total_travel_time)
        if score < best_score:
            best_route = -1
            best_pi = 0
            best_di = 1
            best_score = score

    for ri, route in enumerate(routes):
        if not route.stops:
            continue
        n = len(route.stops)
        base_cost = float(route.total_travel_time)
        for pi in range(0, n + 1):
            for di in range(pi + 1, n + 2):
                new_total = _cost_after_insert(instance, route, req, pi, di)
                if new_total is not None:
                    incr = new_total - base_cost
                    score = incr  # no penalty: same number of routes
                    if score < best_score:
                        best_score = score
                        best_route = ri
                        best_pi = pi
                        best_di = di

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
    Apply a chosen insertion: add req to routes at (route_index, pickup_idx, delivery_idx).
    route_index < 0: append new route with only this request.
    Modifies routes in place and runs check_route_feasible to fill schedule.
    """
    if route_index < 0:
        new_route = Route(stops=[req.pickup_node, req.delivery_node])
        check_route_feasible(instance, new_route)
        routes.append(new_route)
        return
    route = routes[route_index]
    stops = route.stops
    new_stops = (
        list(stops[:pickup_idx])
        + [req.pickup_node]
        + list(stops[pickup_idx : delivery_idx - 1])
        + [req.delivery_node]
        + list(stops[delivery_idx - 1 :])
    )
    route.stops = new_stops
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
        best_route, best_pi, best_di, best_cost = _best_insertion(instance, routes, req)
        if best_route is None:
            new_route = Route(stops=[req.pickup_node, req.delivery_node])
            if check_route_feasible(instance, new_route):
                routes.append(new_route)
            continue
        if best_route < 0:
            new_route = Route(stops=[req.pickup_node, req.delivery_node])
            check_route_feasible(instance, new_route)
            routes.append(new_route)
        else:
            route = routes[best_route]
            stops = route.stops
            new_stops = (
                list(stops[:best_pi])
                + [req.pickup_node]
                + list(stops[best_pi : best_di - 1])
                + [req.delivery_node]
                + list(stops[best_di - 1 :])
            )
            route.stops = new_stops
            check_route_feasible(instance, route)

    total_cost = sum(r.total_travel_time for r in routes)
    return Solution(routes=routes, total_cost=total_cost)


def build_initial_solution_regret(
    instance: Instance,
    k: int = 3,
    rng: Optional[random.Random] = None,
) -> Solution:
    """
    Regret-k insertion: at each step, choose the request with largest regret
    (difference between k-th best and best insertion cost), insert it at best position.
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
            ri, pi, di, cost = _best_insertion(instance, routes, req)
            if ri is None:
                continue
            costs: List[float] = []
            single = Route(stops=[req.pickup_node, req.delivery_node])
            if check_route_feasible(instance, single):
                costs.append(ROUTE_PENALTY + float(single.total_travel_time))
            for route_idx, route in enumerate(routes):
                n = len(route.stops)
                base = float(route.total_travel_time)
                for pii in range(0, n + 1):
                    for dii in range(pii + 1, n + 2):
                        new_total = _cost_after_insert(instance, route, req, pii, dii)
                        if new_total is not None:
                            costs.append(new_total - base)
            costs.sort()
            if not costs:
                continue
            c_best = costs[0]
            c_k = costs[min(k - 1, len(costs) - 1)] if k else c_best
            regret = c_k - c_best
            if regret > best_regret:
                best_regret = regret
                best_req = req
                best_route_idx, best_pi, best_di = ri, pi, di

        if best_req is None or best_route_idx is None:
            break
        unassigned.remove(best_req)
        if best_route_idx < 0:
            new_route = Route(stops=[best_req.pickup_node, best_req.delivery_node])
            check_route_feasible(instance, new_route)
            routes.append(new_route)
        else:
            route = routes[best_route_idx]
            stops = route.stops
            new_stops = (
                list(stops[:best_pi])
                + [best_req.pickup_node]
                + list(stops[best_pi : best_di - 1])
                + [best_req.delivery_node]
                + list(stops[best_di - 1 :])
            )
            route.stops = new_stops
            check_route_feasible(instance, route)

    total_cost = sum(r.total_travel_time for r in routes)
    return Solution(routes=routes, total_cost=total_cost)


def build_initial_solution(
    instance: Instance,
    rng: Optional[random.Random] = None,
    method: str = "greedy",
) -> Solution:
    """Build initial feasible solution; method in ('greedy', 'regret', 'best')."""
    if rng is None:
        rng = random.Random()
    if method == "regret":
        sol = build_initial_solution_regret(instance, k=3, rng=rng)
    else:
        sol = build_initial_solution_greedy(instance, rng=rng)
    if method == "best":
        sol2 = build_initial_solution_regret(instance, k=3, rng=rng)
        if sol2.total_cost < sol.total_cost:
            sol = sol2
    return sol
