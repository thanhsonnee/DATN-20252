"""
Destroy operators: remove requests from solution (random, shaw, worst, route, cluster).
All work at request level.
"""
from __future__ import annotations

import math
from collections import defaultdict
from typing import List, Tuple

from solver.constraints import check_route_feasible
from solver.models import Instance, Request, Route, Solution


def _request_to_route_index(instance: Instance, solution: Solution) -> dict:
    """Map request.id -> route index that serves it (first route containing both pickup and delivery)."""
    req_to_ri = {}
    for ri, route in enumerate(solution.routes):
        for req in instance.requests:
            if req.id in req_to_ri:
                continue
            if req.pickup_node in route.stops and req.delivery_node in route.stops:
                pi, di = route.stops.index(req.pickup_node), route.stops.index(req.delivery_node)
                if pi < di:
                    req_to_ri[req.id] = ri
                    break
    return req_to_ri


def random_removal(
    instance: Instance,
    solution: Solution,
    num_remove: int,
    rng,
) -> Tuple[Solution, List[Request]]:
    """
    Remove num_remove requests chosen at random from solution.
    Returns (destroyed_solution, list of removed requests).
    Destroyed solution has fewer stops; empty routes are removed; schedules recomputed.
    """
    req_to_ri = _request_to_route_index(instance, solution)
    in_sol = [req for req in instance.requests if req.id in req_to_ri]
    if not in_sol:
        return solution.copy(), []
    n_remove = min(num_remove, len(in_sol))
    to_remove = rng.sample(in_sol, n_remove)

    # Per-route: set of node ids to remove (pickup/delivery of to_remove requests)
    remove_per_route = defaultdict(set)
    for req in to_remove:
        ri = req_to_ri.get(req.id)
        if ri is None:
            continue
        remove_per_route[ri].add(req.pickup_node)
        remove_per_route[ri].add(req.delivery_node)

    new_routes = []
    for ri, route in enumerate(solution.routes):
        to_drop = remove_per_route.get(ri, set())
        new_stops = [n for n in route.stops if n not in to_drop]
        if not new_stops:
            continue
        new_route = Route(stops=new_stops)
        new_routes.append(new_route)
    # Drop empty routes and recompute schedule for remaining
    new_routes = [r for r in new_routes if r.stops]
    for route in new_routes:
        check_route_feasible(instance, route)
    total_cost = sum(r.total_travel_time for r in new_routes)
    destroyed = Solution(routes=new_routes, total_cost=total_cost)
    return destroyed, to_remove


def _apply_removal(
    instance: Instance,
    solution: Solution,
    to_remove: List[Request],
    req_to_ri: dict,
) -> Tuple[Solution, List[Request]]:
    """Build destroyed solution by removing the given requests. req_to_ri = _request_to_route_index(instance, solution)."""
    remove_per_route = defaultdict(set)
    for req in to_remove:
        ri = req_to_ri.get(req.id)
        if ri is None:
            continue
        remove_per_route[ri].add(req.pickup_node)
        remove_per_route[ri].add(req.delivery_node)
    new_routes = []
    for ri, route in enumerate(solution.routes):
        to_drop = remove_per_route.get(ri, set())
        new_stops = [n for n in route.stops if n not in to_drop]
        if not new_stops:
            continue
        new_route = Route(stops=new_stops)
        new_routes.append(new_route)
    for route in new_routes:
        check_route_feasible(instance, route)
    return Solution(routes=new_routes, total_cost=sum(r.total_travel_time for r in new_routes)), to_remove


def _relatedness(instance: Instance, req_i: Request, req_j: Request) -> float:
    """Lower = more related. Distance between pickups + time window overlap."""
    depot = instance.depot_id
    tt = instance.travel_time
    nodes = instance.nodes
    dist = tt[req_i.pickup_node][req_j.pickup_node]
    tw_i_e, tw_i_l = nodes[req_i.pickup_node].tw_early, nodes[req_i.pickup_node].tw_late
    tw_j_e, tw_j_l = nodes[req_j.pickup_node].tw_early, nodes[req_j.pickup_node].tw_late
    tw_gap = max(0, max(tw_i_e - tw_j_l, tw_j_e - tw_i_l))
    return dist + 0.1 * tw_gap


def shaw_removal(
    instance: Instance,
    solution: Solution,
    num_remove: int,
    rng,
) -> Tuple[Solution, List[Request]]:
    """
    Relatedness-based removal: pick a seed request, then remove requests most related to it
    (distance + time window similarity). Works at request level.
    """
    req_to_ri = _request_to_route_index(instance, solution)
    in_sol = [req for req in instance.requests if req.id in req_to_ri]
    if not in_sol or num_remove <= 0:
        return solution.copy(), []
    n_remove = min(num_remove, len(in_sol))
    seed = rng.choice(in_sol)
    to_remove = [seed]
    remaining = [r for r in in_sol if r.id != seed.id]
    while len(to_remove) < n_remove and remaining:
        # Pick request most related to any already in to_remove (e.g. to last added)
        last = to_remove[-1]
        remaining.sort(key=lambda r: _relatedness(instance, last, r))
        # Probabilistic: prefer more related (smaller relatedness)
        idx = min(int(rng.random() * (min(5, len(remaining)))), len(remaining) - 1)
        chosen = remaining.pop(idx)
        to_remove.append(chosen)
    return _apply_removal(instance, solution, to_remove, req_to_ri)


def _marginal_cost(instance: Instance, solution: Solution, req: Request, req_to_ri: dict) -> float:
    """Cost of route with req minus cost without req (removal gain)."""
    ri = req_to_ri.get(req.id)
    if ri is None:
        return 0.0
    route = solution.routes[ri]
    current_cost = float(route.total_travel_time)
    new_stops = [n for n in route.stops if n != req.pickup_node and n != req.delivery_node]
    if not new_stops:
        return current_cost
    temp = Route(stops=new_stops)
    if not check_route_feasible(instance, temp):
        return 0.0
    return current_cost - temp.total_travel_time


def worst_removal(
    instance: Instance,
    solution: Solution,
    num_remove: int,
    rng,
) -> Tuple[Solution, List[Request]]:
    """
    Remove requests with highest marginal cost (contribution to route cost).
    Works at request level.
    """
    req_to_ri = _request_to_route_index(instance, solution)
    in_sol = [req for req in instance.requests if req.id in req_to_ri]
    if not in_sol or num_remove <= 0:
        return solution.copy(), []
    n_remove = min(num_remove, len(in_sol))
    marginal = [(req, _marginal_cost(instance, solution, req, req_to_ri)) for req in in_sol]
    marginal.sort(key=lambda x: -x[1])
    to_remove = [marginal[i][0] for i in range(n_remove)]
    return _apply_removal(instance, solution, to_remove, req_to_ri)


def route_removal(
    instance: Instance,
    solution: Solution,
    num_routes_to_remove: int,
    rng,
) -> Tuple[Solution, List[Request]]:
    """
    Remove one or more entire routes (all requests on those routes).
    num_routes_to_remove: how many routes to drop (e.g. 1 or 2).
    """
    if not solution.routes:
        return solution.copy(), []
    req_to_ri = _request_to_route_index(instance, solution)
    n_remove = min(num_routes_to_remove, len(solution.routes))
    indices = rng.sample(range(len(solution.routes)), n_remove)
    to_remove = [req for req in instance.requests if req.id in req_to_ri and req_to_ri[req.id] in indices]
    return _apply_removal(instance, solution, to_remove, req_to_ri)


def cluster_removal(
    instance: Instance,
    solution: Solution,
    num_remove: int,
    rng,
) -> Tuple[Solution, List[Request]]:
    """
    Optional: remove a contiguous cluster by angle from depot (sweep).
    Sort requests by angle of pickup from depot, take a contiguous segment.
    """
    req_to_ri = _request_to_route_index(instance, solution)
    in_sol = [req for req in instance.requests if req.id in req_to_ri]
    if not in_sol or num_remove <= 0:
        return solution.copy(), []
    n_remove = min(num_remove, len(in_sol))
    depot = instance.depot_id
    nodes = instance.nodes

    def angle(req: Request) -> float:
        px = nodes[req.pickup_node].lat
        py = nodes[req.pickup_node].lon
        dx = nodes[depot].lat
        dy = nodes[depot].lon
        return math.atan2(py - dy, px - dx)

    in_sol_sorted = sorted(in_sol, key=angle)
    start = rng.randint(0, len(in_sol_sorted) - 1)
    to_remove = []
    for i in range(n_remove):
        to_remove.append(in_sol_sorted[(start + i) % len(in_sol_sorted)])
    return _apply_removal(instance, solution, to_remove, req_to_ri)
