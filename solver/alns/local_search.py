"""
Local search for PDPTW on request level.

Goal (consistent with the rest of this repo):
- Minimize number of non-empty routes first, then total travel time.

This implementation is intentionally lightweight and time-limit friendly:
- Operates on whole requests (pickup+delivery together) to keep precedence safe.
- Uses randomized, sampled insertions (instead of full O(n^2) scans) to stay fast.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from solver.constraints import check_route_feasible
from solver.construction import ROUTE_PENALTY, _best_insertion, apply_insertion
from solver.models import Instance, Request, Route, Solution


def _num_routes(sol: Solution) -> int:
    return sum(1 for r in sol.routes if r.stops)


def _scalar_cost(sol: Solution) -> float:
    return _num_routes(sol) * ROUTE_PENALTY + sol.total_cost


def _recompute_solution_cost(sol: Solution) -> None:
    sol.total_cost = int(sum(r.total_travel_time for r in sol.routes))


def _request_to_route_index(instance: Instance, solution: Solution) -> Dict[int, int]:
    """Map request.id -> route index (route containing both pickup and delivery in correct order)."""
    req_to_ri: Dict[int, int] = {}
    for ri, route in enumerate(solution.routes):
        if not route.stops:
            continue
        stops = route.stops
        for req in instance.requests:
            if req.id in req_to_ri:
                continue
            if req.pickup_node in stops and req.delivery_node in stops:
                pi = stops.index(req.pickup_node)
                di = stops.index(req.delivery_node)
                if pi < di:
                    req_to_ri[req.id] = ri
    return req_to_ri


def _remove_request_from_route(route: Route, req: Request) -> None:
    """Remove pickup+delivery nodes of req from the given route (if present)."""
    if not route.stops:
        return
    p, d = req.pickup_node, req.delivery_node
    route.stops = [n for n in route.stops if n != p and n != d]


def _insert_nodes(stops: List[int], pickup: int, delivery: int, pi: int, di: int) -> List[int]:
    """
    Return new stops with pickup inserted at pi and delivery inserted at di.
    Indices are in the resulting list (0..len(stops)+1), with pi < di.
    """
    # Insert pickup first into original list.
    after_pick = list(stops[:pi]) + [pickup] + list(stops[pi:])
    # Now insert delivery into the list that already has pickup.
    return list(after_pick[:di]) + [delivery] + list(after_pick[di:])


def _best_insertion_sampled(
    instance: Instance,
    route: Route,
    req: Request,
    rng,
    pos_trials: int,
) -> Tuple[Optional[List[int]], Optional[int]]:
    """
    Sample a limited number of insertion positions for req into route.
    Returns (best_stops, best_travel_time) or (None, None) if no feasible insertion found.
    """
    base = route.stops
    m = len(base)
    pickup, delivery = req.pickup_node, req.delivery_node

    # If route already contains either node, skip (should not happen in well-formed solutions).
    if pickup in base or delivery in base:
        return None, None

    best_stops: Optional[List[int]] = None
    best_tt: Optional[int] = None

    # For empty routes, only one meaningful insertion.
    if m == 0:
        temp = Route(stops=[pickup, delivery])
        if check_route_feasible(instance, temp):
            return temp.stops, temp.total_travel_time
        return None, None

    # Always include a couple of deterministic anchor positions.
    anchors = [
        (0, 1),  # at start
        (m, m + 1),  # at end
    ]
    trials: List[Tuple[int, int]] = list(anchors)

    # Random samples.
    for _ in range(max(0, pos_trials - len(trials))):
        pi = rng.randint(0, m)  # 0..m
        di = rng.randint(pi + 1, m + 1)  # delivery position in after_pick list is 0..m+1, must be > pi
        # Convert di from "after_pick index space" to final list index:
        # after_pick length = m+1, inserting delivery at index di yields final length m+2.
        trials.append((pi, di))

    seen = set()
    for pi, di in trials:
        if (pi, di) in seen:
            continue
        seen.add((pi, di))
        new_stops = _insert_nodes(base, pickup, delivery, pi, di)
        temp = Route(stops=new_stops)
        if not check_route_feasible(instance, temp):
            continue
        if best_tt is None or temp.total_travel_time < best_tt:
            best_tt = temp.total_travel_time
            best_stops = temp.stops

    return best_stops, best_tt


def try_empty_one_route(
    instance: Instance,
    solution: Solution,
) -> bool:
    """
    Try to empty one route by relocating all its requests to other routes.
    Prefer routes with fewest requests first (easiest to empty).
    If successful, the route is removed and solution is updated; returns True.
    Otherwise returns False (no route could be emptied).
    """
    for r in solution.routes:
        check_route_feasible(instance, r)
    _recompute_solution_cost(solution)

    req_to_ri = _request_to_route_index(instance, solution)
    # (route_index, request_count), sort by count ascending
    route_counts: List[Tuple[int, int]] = []
    for ri, route in enumerate(solution.routes):
        if not route.stops:
            continue
        count = sum(1 for req in instance.requests if req_to_ri.get(req.id) == ri)
        if count > 0:
            route_counts.append((ri, count))
    route_counts.sort(key=lambda x: x[1])

    for ri, _ in route_counts:
        requests_on_route = [req for req in instance.requests if req_to_ri.get(req.id) == ri]
        if not requests_on_route:
            continue
        saved_routes = [route.copy() for route in solution.routes]
        success = True
        for req in requests_on_route:
            _remove_request_from_route(solution.routes[ri], req)
            if not check_route_feasible(instance, solution.routes[ri]):
                success = False
                break
            other_indices = [
                j for j in range(len(solution.routes))
                if j != ri and solution.routes[j].stops
            ]
            if not other_indices:
                success = False
                break
            other_routes = [solution.routes[j] for j in other_indices]
            best_route_idx, best_pi, best_di, _ = _best_insertion(instance, other_routes, req)
            if best_route_idx is None or best_route_idx < 0:
                success = False
                break
            rj = other_indices[best_route_idx]
            apply_insertion(instance, solution.routes, req, rj, best_pi, best_di)
            req_to_ri[req.id] = rj

        if not success:
            for i, route in enumerate(saved_routes):
                solution.routes[i].stops = list(route.stops)
                solution.routes[i].arrival_times = list(route.arrival_times)
                solution.routes[i].start_service_times = list(route.start_service_times)
                solution.routes[i].loads = list(route.loads)
                solution.routes[i].total_travel_time = route.total_travel_time
                solution.routes[i].total_waiting_time = route.total_waiting_time
            for r in solution.routes:
                check_route_feasible(instance, r)
            _recompute_solution_cost(solution)
            continue

        solution.routes = [r for r in solution.routes if r.stops]
        _recompute_solution_cost(solution)
        return True

    return False


@dataclass(frozen=True)
class LocalSearchConfig:
    max_moves: int = 30
    route_samples: int = 8
    pos_trials_per_route: int = 24
    first_improvement: bool = True


def local_search(
    instance: Instance,
    solution: Solution,
    rng,
    cfg: LocalSearchConfig,
) -> Solution:
    """
    Request-level local search:
    - pick a served request
    - remove it from its route
    - try to reinsert into a sampled subset of routes (including its original route)
    - accept improving moves (first- or best-improvement style)
    """
    if cfg.max_moves <= 0 or not solution.routes:
        return solution

    # Ensure route schedules/cost fields are coherent.
    for r in solution.routes:
        check_route_feasible(instance, r)
    _recompute_solution_cost(solution)

    # "Empty one route" phase: try to empty routes (fewest requests first) by relocating all requests elsewhere.
    while try_empty_one_route(instance, solution):
        pass

    before_scalar = _scalar_cost(solution)

    for _ in range(cfg.max_moves):
        req_to_ri = _request_to_route_index(instance, solution)
        served = [req for req in instance.requests if req.id in req_to_ri]
        if not served:
            break

        req = rng.choice(served)
        ri = req_to_ri.get(req.id)
        if ri is None:
            continue

        route_a = solution.routes[ri]
        route_a_before = route_a.copy()

        # Remove request from its current route.
        _remove_request_from_route(route_a, req)
        if not check_route_feasible(instance, route_a):
            # Should not happen; revert and skip.
            solution.routes[ri] = route_a_before
            continue

        # Sample candidate routes (include original route index).
        all_indices = list(range(len(solution.routes)))
        rng.shuffle(all_indices)
        candidates = []
        if ri not in candidates:
            candidates.append(ri)
        for idx in all_indices:
            if idx == ri:
                continue
            candidates.append(idx)
            if len(candidates) >= max(1, cfg.route_samples):
                break

        best_move: Optional[Tuple[int, List[int], int]] = None  # (rj, new_stops, new_tt)

        for rj in candidates:
            route_b = solution.routes[rj]
            stops_b, tt_b = _best_insertion_sampled(
                instance,
                route_b,
                req,
                rng=rng,
                pos_trials=cfg.pos_trials_per_route,
            )
            if stops_b is None or tt_b is None:
                continue

            # Evaluate move by temporarily applying to route_b (and route_a already modified).
            route_b_before = route_b.copy()
            route_b.stops = stops_b
            if not check_route_feasible(instance, route_b):
                solution.routes[rj] = route_b_before
                continue

            _recompute_solution_cost(solution)
            after_scalar = _scalar_cost(solution)

            # Revert route_b; keep route_a removed until we decide final accept/reject.
            solution.routes[rj] = route_b_before
            check_route_feasible(instance, solution.routes[rj])
            _recompute_solution_cost(solution)

            if after_scalar < before_scalar:
                best_move = (rj, stops_b, tt_b)
                if cfg.first_improvement:
                    break

        if best_move is None:
            # No improving move found; revert route_a fully.
            solution.routes[ri] = route_a_before
            check_route_feasible(instance, solution.routes[ri])
            _recompute_solution_cost(solution)
            continue

        # Apply best improving move: update route_b, keep route_a removed.
        rj, stops_b, _tt_b = best_move
        route_b = solution.routes[rj]
        route_b_before = route_b.copy()
        route_b.stops = stops_b
        if not check_route_feasible(instance, route_b):
            # If somehow infeasible, revert everything.
            solution.routes[rj] = route_b_before
            solution.routes[ri] = route_a_before
            check_route_feasible(instance, solution.routes[ri])
            _recompute_solution_cost(solution)
            continue

        # Move accepted.
        _recompute_solution_cost(solution)
        before_scalar = _scalar_cost(solution)

    # Cleanup: drop empty routes to keep solution compact.
    solution.routes = [r for r in solution.routes if r.stops]
    _recompute_solution_cost(solution)
    return solution

