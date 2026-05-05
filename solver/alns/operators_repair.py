"""
Repair operators: reinsert removed requests (greedy insertion).
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from solver.constraints import check_route_feasible
from solver.construction import ROUTE_PENALTY, _best_insertion, apply_insertion
from solver.models import Instance, Request, Route, Solution


def _recompute_solution_cost(solution: Solution) -> None:
    solution.total_cost = int(sum(r.total_travel_time for r in solution.routes))


def _build_node_to_request(instance: Instance) -> Dict[int, Request]:
    m: Dict[int, Request] = {}
    for req in instance.requests:
        m[req.pickup_node] = req
        m[req.delivery_node] = req
    return m


def _served_requests_in_route(instance: Instance, route: Route, node_to_req: Dict[int, Request]) -> List[Request]:
    """Return requests that are fully present in this route (both pickup and delivery)."""
    if not route.stops:
        return []
    stops = route.stops
    present = set(stops)
    seen: Dict[int, Request] = {}
    out: List[Request] = []
    for n in present:
        req = node_to_req.get(n)
        if req is None or req.id in seen:
            continue
        if req.pickup_node in present and req.delivery_node in present:
            seen[req.id] = req
            out.append(req)
    return out


def _remove_request(route: Route, req: Request) -> None:
    if not route.stops:
        return
    p, d = req.pickup_node, req.delivery_node
    route.stops = [n for n in route.stops if n != p and n != d]


def _insert_nodes(stops: List[int], pickup: int, delivery: int, pi: int, di: int) -> List[int]:
    after_pick = list(stops[:pi]) + [pickup] + list(stops[pi:])
    return list(after_pick[:di]) + [delivery] + list(after_pick[di:])


def _sample_insertion_options(
    instance: Instance,
    routes: List[Route],
    req: Request,
    rng,
    route_samples: int,
    pos_trials_per_route: int,
) -> List[Tuple[float, int, int, int]]:
    """
    Return a list of sampled feasible insertion options: (score, route_index, pickup_idx, delivery_idx).

    score follows hierarchical objective:
    - existing route: incremental travel time
    - new route: ROUTE_PENALTY + route_travel_time
    """
    options: List[Tuple[float, int, int, int]] = []
    pickup, delivery = req.pickup_node, req.delivery_node

    # New route option (route_index = -1).
    single = Route(stops=[pickup, delivery])
    if check_route_feasible(instance, single):
        options.append((ROUTE_PENALTY + float(single.total_travel_time), -1, 0, 1))

    if not routes:
        return options

    # Sample route indices (prefer non-empty routes).
    indices = list(range(len(routes)))
    rng.shuffle(indices)
    indices = indices[: max(1, route_samples)]

    for ri in indices:
        route = routes[ri]
        if not route.stops:
            continue
        base_tt = float(route.total_travel_time)
        m = len(route.stops)

        # Anchor positions + random positions in "after_pick index space"
        trials: List[Tuple[int, int]] = [(0, 1), (m, m + 1)]
        for _ in range(max(0, pos_trials_per_route - len(trials))):
            pi = rng.randint(0, m)
            di = rng.randint(pi + 1, m + 1)
            trials.append((pi, di))

        seen = set()
        for pi, di in trials:
            if (pi, di) in seen:
                continue
            seen.add((pi, di))
            new_stops = _insert_nodes(route.stops, pickup, delivery, pi, di)
            temp = Route(stops=new_stops)
            if not check_route_feasible(instance, temp):
                continue
            incr = float(temp.total_travel_time) - base_tt
            options.append((incr, ri, pi, di))

    return options


def greedy_repair(
    instance: Instance,
    solution: Solution,
    removed: List[Request],
    rng,
) -> Solution:
    """
    Reinsert removed requests one by one using best insertion (greedy).
    Order: by tw_early of pickup, then random. Modifies solution in place and returns it.
    """
    routes = solution.routes
    order = sorted(removed, key=lambda r: (instance.nodes[r.pickup_node].tw_early, rng.random()))
    for req in order:
        ri, pi, di, _ = _best_insertion(instance, routes, req)
        if ri is None:
            # Force new route
            new_route = Route(stops=[req.pickup_node, req.delivery_node])
            if check_route_feasible(instance, new_route):
                routes.append(new_route)
            continue
        apply_insertion(instance, routes, req, ri, pi, di)
    _recompute_solution_cost(solution)
    return solution


def regret_repair(
    instance: Instance,
    solution: Solution,
    removed: List[Request],
    rng,
    k: int = 3,
    route_samples: int = 10,
    pos_trials_per_route: int = 28,
    ejection_max: int = 2,
    ejection_tries: int = 20,
) -> Solution:
    """
    Regret-k repair (sampled): iteratively choose request with largest regret and insert it.

    If a request has no feasible insertion option, try light ejection (1-2 requests) to make room;
    otherwise fall back to opening a new route if feasible.
    """
    node_to_req = _build_node_to_request(instance)
    unassigned: List[Request] = list(removed)

    # Ensure route schedules are consistent before we start.
    for r in solution.routes:
        check_route_feasible(instance, r)
    _recompute_solution_cost(solution)

    while unassigned:
        best_req: Optional[Request] = None
        best_choice: Optional[Tuple[float, int, int, int]] = None
        best_regret: float = -1.0

        # Evaluate regret for each candidate request.
        for req in unassigned:
            options = _sample_insertion_options(
                instance,
                solution.routes,
                req,
                rng=rng,
                route_samples=route_samples,
                pos_trials_per_route=pos_trials_per_route,
            )
            if not options:
                continue
            options.sort(key=lambda x: x[0])
            c_best = options[0][0]
            c_k = options[min(max(k, 1) - 1, len(options) - 1)][0]
            regret = c_k - c_best
            if regret > best_regret:
                best_regret = regret
                best_req = req
                best_choice = options[0]

        if best_req is None or best_choice is None:
            # Nothing had a feasible insertion option via sampling; try to salvage by greedy exact insertion.
            req = unassigned.pop(0)
            ri, pi, di, _ = _best_insertion(instance, solution.routes, req)
            if ri is not None:
                apply_insertion(instance, solution.routes, req, ri, pi, di)
                _recompute_solution_cost(solution)
                continue
            # Try light ejection to make room.
            if _try_ejection_then_insert(
                instance,
                solution,
                req,
                rng=rng,
                node_to_req=node_to_req,
                ejection_max=ejection_max,
                ejection_tries=ejection_tries,
            ):
                _recompute_solution_cost(solution)
                continue
            # Last resort: new single route if feasible.
            new_route = Route(stops=[req.pickup_node, req.delivery_node])
            if check_route_feasible(instance, new_route):
                solution.routes.append(new_route)
                _recompute_solution_cost(solution)
            continue

        # Apply best insertion for the max-regret request.
        unassigned.remove(best_req)
        _score, ri, pi, di = best_choice
        if ri < 0:
            new_route = Route(stops=[best_req.pickup_node, best_req.delivery_node])
            if check_route_feasible(instance, new_route):
                solution.routes.append(new_route)
                _recompute_solution_cost(solution)
                continue
            # If even single route infeasible, try ejection as salvage.
            if _try_ejection_then_insert(
                instance,
                solution,
                best_req,
                rng=rng,
                node_to_req=node_to_req,
                ejection_max=ejection_max,
                ejection_tries=ejection_tries,
            ):
                _recompute_solution_cost(solution)
            continue

        # Insert into existing route with sampled indices.
        route = solution.routes[ri]
        before = route.copy()
        route.stops = _insert_nodes(route.stops, best_req.pickup_node, best_req.delivery_node, pi, di)
        if not check_route_feasible(instance, route):
            # Fallback to exact best insertion if sampled position failed (should be rare).
            solution.routes[ri] = before
            ri2, pi2, di2, _ = _best_insertion(instance, solution.routes, best_req)
            if ri2 is not None:
                apply_insertion(instance, solution.routes, best_req, ri2, pi2, di2)
        _recompute_solution_cost(solution)

    # Drop empty routes if any.
    solution.routes = [r for r in solution.routes if r.stops]
    _recompute_solution_cost(solution)
    return solution


def _try_ejection_then_insert(
    instance: Instance,
    solution: Solution,
    req: Request,
    rng,
    node_to_req: Dict[int, Request],
    ejection_max: int,
    ejection_tries: int,
) -> bool:
    """
    Try to insert req by ejecting 1..ejection_max requests from a sampled route.
    If successful, ejected requests are reinserted greedily (may open new routes).
    """
    if ejection_max <= 0 or ejection_tries <= 0:
        return False

    routes = solution.routes
    if not routes:
        return False

    for _ in range(ejection_tries):
        ri = rng.randrange(len(routes))
        route = routes[ri]
        if not route.stops:
            continue

        served = _served_requests_in_route(instance, route, node_to_req)
        if not served:
            continue

        # Choose up to ejection_max requests to eject.
        rng.shuffle(served)
        for eject_count in range(1, max(1, ejection_max) + 1):
            eject_list = served[:eject_count]
            before = route.copy()
            for ej in eject_list:
                _remove_request(route, ej)
            if not check_route_feasible(instance, route):
                routes[ri] = before
                continue

            # Try insert target req into this modified route using exact best insertion on a single-route list.
            temp_routes = [route]
            rj, pi, di, _ = _best_insertion(instance, temp_routes, req)
            if rj is None:
                routes[ri] = before
                continue
            apply_insertion(instance, temp_routes, req, rj, pi, di)
            routes[ri] = temp_routes[0]

            # Now reinsert ejected requests greedily into full solution routes.
            for ej in eject_list:
                r2, p2, d2, _ = _best_insertion(instance, routes, ej)
                if r2 is None:
                    new_route = Route(stops=[ej.pickup_node, ej.delivery_node])
                    if check_route_feasible(instance, new_route):
                        routes.append(new_route)
                    continue
                apply_insertion(instance, routes, ej, r2, p2, d2)
            return True

    return False
