"""
Local search for PDPTW on request level.

Goal: minimize number of non-empty routes first, then total travel time.

Move types:
- Relocate: move 1 request to a different route/position.
- Swap: exchange 2 requests between 2 different routes.
- Or-opt: move 2 requests from one route to another route together.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from solver.constraints import check_route_feasible
from solver.construction import ROUTE_PENALTY, _best_insertion, _insert_nodes, apply_insertion
from solver.models import Instance, Request, Route, Solution


def _num_routes(sol: Solution) -> int:
    return sum(1 for r in sol.routes if r.stops)


def _scalar_cost(sol: Solution) -> float:
    return _num_routes(sol) * ROUTE_PENALTY + sol.total_cost


def _recompute_solution_cost(sol: Solution) -> None:
    sol.total_cost = int(sum(r.total_travel_time for r in sol.routes))


def _request_to_route_index(instance: Instance, solution: Solution) -> Dict[int, int]:
    """Map request.id -> route index."""
    req_to_ri: Dict[int, int] = {}
    for ri, route in enumerate(solution.routes):
        if not route.stops:
            continue
        stops = route.stops
        present = set(stops)
        for req in instance.requests:
            if req.id in req_to_ri:
                continue
            if req.pickup_node in present and req.delivery_node in present:
                if stops.index(req.pickup_node) < stops.index(req.delivery_node):
                    req_to_ri[req.id] = ri
    return req_to_ri


def _remove_request_from_route(route: Route, req: Request) -> None:
    p, d = req.pickup_node, req.delivery_node
    route.stops = [n for n in route.stops if n != p and n != d]


def _best_insertion_sampled(
    instance: Instance,
    route: Route,
    req: Request,
    rng,
    pos_trials: int,
) -> Tuple[Optional[List[int]], Optional[int]]:
    """
    Sample insertion positions for req into route.
    Returns (best_stops, best_travel_time) or (None, None).
    """
    base = route.stops
    m = len(base)
    pickup, delivery = req.pickup_node, req.delivery_node

    if pickup in base or delivery in base:
        return None, None

    if m == 0:
        temp = Route(stops=[pickup, delivery])
        if check_route_feasible(instance, temp):
            return temp.stops, temp.total_travel_time
        return None, None

    trials: List[Tuple[int, int]] = [(0, 1), (m, m + 1)]
    for _ in range(max(0, pos_trials - len(trials))):
        pi = rng.randint(0, m)
        di = rng.randint(pi + 1, m + 1)
        trials.append((pi, di))

    best_stops: Optional[List[int]] = None
    best_tt: Optional[int] = None
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


# ---------------------------------------------------------------------------
# Move: Relocate (existing)
# ---------------------------------------------------------------------------

def _try_relocate(
    instance: Instance,
    solution: Solution,
    req: Request,
    ri: int,
    before_scalar: float,
    rng,
    route_samples: int,
    pos_trials: int,
    first_improvement: bool,
) -> bool:
    """
    Remove req from route ri, try inserting into sampled routes.
    Returns True if an improving move was applied.
    """
    route_a = solution.routes[ri]
    route_a_before = route_a.copy()

    _remove_request_from_route(route_a, req)
    if not check_route_feasible(instance, route_a):
        solution.routes[ri] = route_a_before
        return False

    all_indices = list(range(len(solution.routes)))
    rng.shuffle(all_indices)
    candidates = [ri] + [idx for idx in all_indices if idx != ri]
    candidates = candidates[:max(1, route_samples)]

    best_move: Optional[Tuple[int, List[int]]] = None

    for rj in candidates:
        route_b = solution.routes[rj]
        stops_b, _ = _best_insertion_sampled(instance, route_b, req, rng, pos_trials)
        if stops_b is None:
            continue

        route_b_before = route_b.copy()
        route_b.stops = stops_b
        if not check_route_feasible(instance, route_b):
            solution.routes[rj] = route_b_before
            continue

        _recompute_solution_cost(solution)
        after_scalar = _scalar_cost(solution)
        solution.routes[rj] = route_b_before
        check_route_feasible(instance, solution.routes[rj])
        _recompute_solution_cost(solution)

        if after_scalar < before_scalar:
            best_move = (rj, stops_b)
            if first_improvement:
                break

    if best_move is None:
        solution.routes[ri] = route_a_before
        check_route_feasible(instance, solution.routes[ri])
        _recompute_solution_cost(solution)
        return False

    rj, stops_b = best_move
    route_b_before = solution.routes[rj].copy()
    solution.routes[rj].stops = stops_b
    if not check_route_feasible(instance, solution.routes[rj]):
        solution.routes[rj] = route_b_before
        solution.routes[ri] = route_a_before
        check_route_feasible(instance, solution.routes[ri])
        _recompute_solution_cost(solution)
        return False

    _recompute_solution_cost(solution)
    return True


# ---------------------------------------------------------------------------
# Move: Swap (exchange 2 requests between 2 different routes)
# ---------------------------------------------------------------------------

def _try_swap(
    instance: Instance,
    solution: Solution,
    req_a: Request,
    ri_a: int,
    req_b: Request,
    ri_b: int,
    before_scalar: float,
    rng,
    pos_trials: int,
) -> bool:
    """
    Swap req_a (in ri_a) with req_b (in ri_b).
    Returns True if an improving swap was applied.
    """
    if ri_a == ri_b:
        return False

    route_a = solution.routes[ri_a]
    route_b = solution.routes[ri_b]
    before_a = route_a.copy()
    before_b = route_b.copy()

    _remove_request_from_route(route_a, req_a)
    _remove_request_from_route(route_b, req_b)

    if not check_route_feasible(instance, route_a) or not check_route_feasible(instance, route_b):
        solution.routes[ri_a] = before_a
        solution.routes[ri_b] = before_b
        check_route_feasible(instance, solution.routes[ri_a])
        check_route_feasible(instance, solution.routes[ri_b])
        return False

    # Insert req_b into route_a, req_a into route_b
    stops_a, _ = _best_insertion_sampled(instance, route_a, req_b, rng, pos_trials)
    stops_b, _ = _best_insertion_sampled(instance, route_b, req_a, rng, pos_trials)

    if stops_a is None or stops_b is None:
        solution.routes[ri_a] = before_a
        solution.routes[ri_b] = before_b
        check_route_feasible(instance, solution.routes[ri_a])
        check_route_feasible(instance, solution.routes[ri_b])
        return False

    route_a.stops = stops_a
    route_b.stops = stops_b

    if not check_route_feasible(instance, route_a) or not check_route_feasible(instance, route_b):
        solution.routes[ri_a] = before_a
        solution.routes[ri_b] = before_b
        check_route_feasible(instance, solution.routes[ri_a])
        check_route_feasible(instance, solution.routes[ri_b])
        return False

    _recompute_solution_cost(solution)
    if _scalar_cost(solution) < before_scalar:
        return True

    # Revert
    solution.routes[ri_a] = before_a
    solution.routes[ri_b] = before_b
    check_route_feasible(instance, solution.routes[ri_a])
    check_route_feasible(instance, solution.routes[ri_b])
    _recompute_solution_cost(solution)
    return False


# ---------------------------------------------------------------------------
# Move: Or-opt (move 2 requests from one route to another together)
# ---------------------------------------------------------------------------

def _try_or_opt(
    instance: Instance,
    solution: Solution,
    req_a: Request,
    req_b: Request,
    ri_src: int,
    ri_dst: int,
    before_scalar: float,
    rng,
    pos_trials: int,
) -> bool:
    """
    Remove req_a and req_b from ri_src, insert both into ri_dst.
    Returns True if an improving move was applied.
    """
    route_src = solution.routes[ri_src]
    route_dst = solution.routes[ri_dst]
    before_src = route_src.copy()
    before_dst = route_dst.copy()

    _remove_request_from_route(route_src, req_a)
    _remove_request_from_route(route_src, req_b)

    if not check_route_feasible(instance, route_src):
        solution.routes[ri_src] = before_src
        check_route_feasible(instance, solution.routes[ri_src])
        return False

    # Insert req_a into dst first, then req_b
    stops_a, _ = _best_insertion_sampled(instance, route_dst, req_a, rng, pos_trials)
    if stops_a is None:
        solution.routes[ri_src] = before_src
        check_route_feasible(instance, solution.routes[ri_src])
        return False

    route_dst.stops = stops_a
    check_route_feasible(instance, route_dst)

    stops_b, _ = _best_insertion_sampled(instance, route_dst, req_b, rng, pos_trials)
    if stops_b is None:
        solution.routes[ri_src] = before_src
        solution.routes[ri_dst] = before_dst
        check_route_feasible(instance, solution.routes[ri_src])
        check_route_feasible(instance, solution.routes[ri_dst])
        return False

    route_dst.stops = stops_b
    if not check_route_feasible(instance, route_dst):
        solution.routes[ri_src] = before_src
        solution.routes[ri_dst] = before_dst
        check_route_feasible(instance, solution.routes[ri_src])
        check_route_feasible(instance, solution.routes[ri_dst])
        return False

    _recompute_solution_cost(solution)
    if _scalar_cost(solution) < before_scalar:
        return True

    # Revert
    solution.routes[ri_src] = before_src
    solution.routes[ri_dst] = before_dst
    check_route_feasible(instance, solution.routes[ri_src])
    check_route_feasible(instance, solution.routes[ri_dst])
    _recompute_solution_cost(solution)
    return False


# ---------------------------------------------------------------------------
# Empty-one-route helper
# ---------------------------------------------------------------------------

def try_empty_one_route(instance: Instance, solution: Solution) -> bool:
    """
    Try to empty one route by relocating all its requests to other routes.
    Returns True if a route was emptied.
    """
    for r in solution.routes:
        check_route_feasible(instance, r)
    _recompute_solution_cost(solution)

    req_to_ri = _request_to_route_index(instance, solution)
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
            other_indices = [j for j in range(len(solution.routes)) if j != ri and solution.routes[j].stops]
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


def _req_time_slack(instance: Instance, req: Request) -> float:
    """
    Estimate how 'flexible' a request is: larger slack → easier to reinsert elsewhere.
    slack = min(pickup_tw_late - tw_early, delivery_tw_late - tw_early)
    Smaller slack → tighter constraints → insert first to give repair more room.
    """
    nodes = instance.nodes
    p = nodes[req.pickup_node]
    d = nodes[req.delivery_node]
    return min(p.tw_late - p.tw_early, d.tw_late - d.tw_early)


# ---------------------------------------------------------------------------
# Pair-wise route merge: try to combine two routes into one
# ---------------------------------------------------------------------------

def _try_insert_request_exhaustive(
    instance: Instance, route: Route, req: Request,
) -> Optional[List[int]]:
    """
    Exhaustive best-insertion of a request into a single route.
    Returns new stops if feasible + improves; else None.
    """
    base = route.stops
    m = len(base)
    pickup, delivery = req.pickup_node, req.delivery_node
    if pickup in base or delivery in base:
        return None

    best_stops: Optional[List[int]] = None
    best_tt: Optional[float] = None
    for pi in range(m + 1):
        for di in range(pi + 1, m + 2):
            new_stops = _insert_nodes(base, pickup, delivery, pi, di)
            temp = Route(stops=new_stops)
            if not check_route_feasible(instance, temp):
                continue
            tt = float(temp.total_travel_time)
            if best_tt is None or tt < best_tt:
                best_tt = tt
                best_stops = new_stops
    return best_stops


def _reinsert_all_exhaustive(
    instance: Instance,
    partial_routes: List[Route],
    requests_to_insert: List[Request],
    allow_new_route: bool = False,
    sequential: bool = False,
) -> Optional[List[Route]]:
    """
    Try to insert every request in `requests_to_insert` into `partial_routes`
    using exhaustive best-insertion.

    sequential=False (default): greedy-best-fit — at each step pick the
      request+slot with smallest insertion cost (input order ignored).
    sequential=True: insert requests in the given order; for each, pick the
      best slot exhaustively. Useful with TW-slack ordering (tight first).

    Returns the updated list of routes if all requests are inserted, else None.
    If allow_new_route=False, fails immediately when a request has no feasible
    fit in any existing route.
    """
    routes = [r.copy() for r in partial_routes]

    if sequential:
        for req in requests_to_insert:
            best_ri: int = -1
            best_stops: Optional[List[int]] = None
            best_score: float = 1e30
            for ri, route in enumerate(routes):
                new_stops = _try_insert_request_exhaustive(instance, route, req)
                if new_stops is None:
                    continue
                base_tt = float(route.total_travel_time)
                temp = Route(stops=new_stops)
                check_route_feasible(instance, temp)
                incr = float(temp.total_travel_time) - base_tt
                if incr < best_score:
                    best_score = incr
                    best_ri = ri
                    best_stops = new_stops
            if best_stops is None:
                if not allow_new_route:
                    return None
                new_r = Route(stops=[req.pickup_node, req.delivery_node])
                if not check_route_feasible(instance, new_r):
                    return None
                routes.append(new_r)
                continue
            routes[best_ri].stops = best_stops
            check_route_feasible(instance, routes[best_ri])
        return routes

    remaining = list(requests_to_insert)

    while remaining:
        best_req_idx: Optional[int] = None
        best_ri = -1
        best_stops = None
        best_score = 1e30

        for i, req in enumerate(remaining):
            for ri, route in enumerate(routes):
                new_stops = _try_insert_request_exhaustive(instance, route, req)
                if new_stops is None:
                    continue
                base_tt = float(route.total_travel_time)
                temp = Route(stops=new_stops)
                check_route_feasible(instance, temp)
                incr = float(temp.total_travel_time) - base_tt
                if incr < best_score:
                    best_score = incr
                    best_req_idx = i
                    best_ri = ri
                    best_stops = new_stops

        if best_req_idx is None:
            if not allow_new_route:
                return None
            req = remaining.pop(0)
            new_r = Route(stops=[req.pickup_node, req.delivery_node])
            if not check_route_feasible(instance, new_r):
                return None
            routes.append(new_r)
            continue

        routes[best_ri].stops = best_stops
        check_route_feasible(instance, routes[best_ri])
        remaining.pop(best_req_idx)

    return routes


def try_route_merge_pair(instance: Instance, solution: Solution) -> bool:
    """
    For each pair of routes (A, B), try to dissolve route A by inserting all
    its requests into other routes (exhaustive, greedy best-fit). If successful,
    one route is eliminated.

    Much more aggressive than try_empty_one_route: tries multiple target routes
    per ejected request, and uses exhaustive insertion.

    Returns True if any route was eliminated.
    """
    for r in solution.routes:
        check_route_feasible(instance, r)
    _recompute_solution_cost(solution)

    active_indices = [i for i, r in enumerate(solution.routes) if r.stops]
    if len(active_indices) < 2:
        return False

    req_to_ri = _request_to_route_index(instance, solution)

    # Route-by-route: try to dissolve each (cheapest/smallest first)
    route_info: List[Tuple[int, List[Request]]] = []
    for ri in active_indices:
        reqs = [req for req in instance.requests if req_to_ri.get(req.id) == ri]
        if reqs:
            route_info.append((ri, reqs))
    # Prefer to dissolve routes with fewer requests first (easier to place)
    route_info.sort(key=lambda x: len(x[1]))

    for target_ri, ejected_reqs in route_info:
        other_routes = [r.copy() for i, r in enumerate(solution.routes)
                        if i != target_ri and r.stops]
        if not other_routes:
            continue
        new_routes = _reinsert_all_exhaustive(
            instance, other_routes, ejected_reqs, allow_new_route=False,
        )
        if new_routes is not None:
            solution.routes = [r for r in new_routes if r.stops]
            _recompute_solution_cost(solution)
            return True

    return False


# ---------------------------------------------------------------------------
# Exhaustive elimination (stronger than force_eliminate_routes)
# ---------------------------------------------------------------------------

def try_eliminate_exhaustive(instance: Instance, solution: Solution, rng, max_rounds: int = 3) -> bool:
    """
    Stronger variant of route elimination using exhaustive per-request insertion
    and multiple ordering strategies (TW-slack, route-cost, random).

    Returns True if at least one route was eliminated.
    """
    any_eliminated = False

    for _ in range(max_rounds):
        for r in solution.routes:
            check_route_feasible(instance, r)
        _recompute_solution_cost(solution)

        active_indices = [i for i, r in enumerate(solution.routes) if r.stops]
        if len(active_indices) < 2:
            break

        req_to_ri = _request_to_route_index(instance, solution)

        # Priority: routes with fewest requests first, then routes with highest cost per request
        route_info: List[Tuple[int, List[Request], float]] = []
        for ri in active_indices:
            reqs = [req for req in instance.requests if req_to_ri.get(req.id) == ri]
            if not reqs:
                continue
            cost_per_req = float(solution.routes[ri].total_travel_time) / len(reqs)
            route_info.append((ri, reqs, cost_per_req))
        route_info.sort(key=lambda x: (len(x[1]), -x[2]))

        eliminated_this_round = False
        for target_ri, ejected_reqs, _cpr in route_info:
            partial_base = [r.copy() for i, r in enumerate(solution.routes)
                            if i != target_ri and r.stops]
            if not partial_base:
                continue

            # Orderings to try
            guided_tw = sorted(ejected_reqs, key=lambda r: _req_time_slack(instance, r))
            guided_tw_desc = list(reversed(guided_tw))
            orderings: List[List[Request]] = [guided_tw, guided_tw_desc]
            for _ in range(3):
                shuffled = ejected_reqs[:]
                rng.shuffle(shuffled)
                orderings.append(shuffled)

            found = False
            # For each ordering, try both sequential (respects order) and
            # greedy-best-fit (ignores order, min-insertion-cost). Sequential
            # with TW-slack-ascending gives tight requests priority.
            for ordering in orderings:
                for seq in (True, False):
                    new_routes = _reinsert_all_exhaustive(
                        instance, partial_base, ordering,
                        allow_new_route=False, sequential=seq,
                    )
                    if new_routes is not None:
                        solution.routes = [r for r in new_routes if r.stops]
                        _recompute_solution_cost(solution)
                        found = True
                        break
                if found:
                    break

            if found:
                any_eliminated = True
                eliminated_this_round = True
                break

        if not eliminated_this_round:
            break

    return any_eliminated


def lns_eliminate_route(
    instance: Instance,
    solution: Solution,
    rng,
    trials: int = 12,
    extra_ratio_schedule: Tuple[float, ...] = (0.0, 0.1, 0.2, 0.3, 0.5, 0.7),
) -> bool:
    """
    Strong LNS-assisted route elimination.

    Strategy: eject all requests from the target (smallest) route + a random
    subset from other routes, then exhaustively re-insert (no new route allowed).
    Because extra requests from other routes participate in the re-pack, the
    remaining routes can restructure to absorb ejected requests that would
    otherwise not fit.

    Returns True if a route was eliminated.
    """
    for r in solution.routes:
        check_route_feasible(instance, r)
    _recompute_solution_cost(solution)

    active_indices = [i for i, r in enumerate(solution.routes) if r.stops]
    if len(active_indices) < 2:
        return False

    req_to_ri = _request_to_route_index(instance, solution)

    # Rank candidate target routes: fewest requests first, then highest cost/req.
    route_info: List[Tuple[int, List[Request], float]] = []
    for ri in active_indices:
        reqs = [req for req in instance.requests if req_to_ri.get(req.id) == ri]
        if not reqs:
            continue
        cpr = float(solution.routes[ri].total_travel_time) / len(reqs)
        route_info.append((ri, reqs, cpr))
    route_info.sort(key=lambda x: (len(x[1]), -x[2]))

    for target_ri, target_reqs, _ in route_info:
        other_idx = [i for i in active_indices if i != target_ri]
        other_reqs_by_ri: Dict[int, List[Request]] = {
            i: [req for req in instance.requests if req_to_ri.get(req.id) == i]
            for i in other_idx
        }
        total_other = sum(len(v) for v in other_reqs_by_ri.values())
        if total_other == 0:
            continue

        for extra_ratio in extra_ratio_schedule:
            n_extra = int(extra_ratio * total_other)
            trials_this = trials if extra_ratio > 0 else max(3, trials // 4)

            for _ in range(trials_this):
                # Build partial routes by removing target + extra ejected reqs.
                partial = [solution.routes[i].copy() for i in other_idx]
                ejected: List[Request] = list(target_reqs)

                if n_extra > 0:
                    # Sample n_extra requests uniformly from other routes.
                    pool: List[Tuple[int, Request]] = []
                    for idx_local, i in enumerate(other_idx):
                        for req in other_reqs_by_ri[i]:
                            pool.append((idx_local, req))
                    k = min(n_extra, len(pool))
                    chosen = rng.sample(pool, k)
                    for idx_local, req in chosen:
                        _remove_request_from_route(partial[idx_local], req)
                        if not check_route_feasible(instance, partial[idx_local]):
                            break
                        ejected.append(req)
                    partial = [r for r in partial if r.stops]
                    if not partial:
                        continue

                # Try 3 orderings × 2 modes:
                # (a) TW-slack ascending (tight first) — sequential
                # (b) random shuffle — sequential
                # (c) random shuffle — greedy-best-fit
                tw_order = sorted(ejected, key=lambda r: _req_time_slack(instance, r))
                rand_order = ejected[:]
                rng.shuffle(rand_order)
                attempts = (
                    (tw_order, True),
                    (rand_order, True),
                    (rand_order, False),
                )
                n_old = sum(1 for r in solution.routes if r.stops)
                for order, seq in attempts:
                    new_routes = _reinsert_all_exhaustive(
                        instance, partial, order,
                        allow_new_route=False, sequential=seq,
                    )
                    if new_routes is not None:
                        n_new = sum(1 for r in new_routes if r.stops)
                        if n_new < n_old:
                            solution.routes = [r for r in new_routes if r.stops]
                            _recompute_solution_cost(solution)
                            return True

    return False


def force_eliminate_routes(instance: Instance, solution: Solution, rng, max_attempts: int = 5, trials_per_route: int = 8) -> Solution:
    """
    Aggressively eliminate routes by ejecting all requests from the smallest
    route and reinserting them with regret repair (no new route allowed).

    Guided ejection: requests sorted by time-slack ascending (tightest first),
    so the repair handles the hardest requests first.
    Also tries random orderings as fallback.
    """
    from solver.alns.operators_repair import regret_repair
    from solver.constraints import check_route_feasible as _crf
    from solver.models import Solution as _Sol

    TRIALS_PER_ROUTE = trials_per_route

    for _ in range(max_attempts):
        for r in solution.routes:
            _crf(instance, r)
        _recompute_solution_cost(solution)

        req_to_ri = _request_to_route_index(instance, solution)

        route_info = []
        for ri, route in enumerate(solution.routes):
            if not route.stops:
                continue
            reqs = [req for req in instance.requests if req_to_ri.get(req.id) == ri]
            route_info.append((ri, reqs))
        route_info.sort(key=lambda x: len(x[1]))  # smallest route first

        eliminated = False
        for ri, ejected_reqs in route_info:
            if not ejected_reqs:
                continue

            old_n_routes = sum(1 for r in solution.routes if r.stops)
            partial_routes_base = [r.copy() for i, r in enumerate(solution.routes) if i != ri and r.stops]
            if not partial_routes_base:
                continue

            # Trial 0: guided order (tightest time-slack first)
            guided_order = sorted(ejected_reqs, key=lambda r: _req_time_slack(instance, r))
            orderings = [guided_order]
            # Trials 1..(TRIALS_PER_ROUTE-1): random shuffles
            for _ in range(TRIALS_PER_ROUTE - 1):
                shuffled = ejected_reqs[:]
                rng.shuffle(shuffled)
                orderings.append(shuffled)

            for ordering in orderings:
                partial_routes = [r.copy() for r in partial_routes_base]
                partial = _Sol(
                    routes=partial_routes,
                    total_cost=int(sum(r.total_travel_time for r in partial_routes)),
                )
                candidate = regret_repair(
                    instance, partial, ordering, rng,
                    k=3,
                    route_samples=len(partial_routes),
                    pos_trials_per_route=50,
                    ejection_max=4,
                    ejection_tries=40,
                )
                new_n_routes = sum(1 for r in candidate.routes if r.stops)
                if new_n_routes < old_n_routes:
                    solution.routes = [r for r in candidate.routes if r.stops]
                    _recompute_solution_cost(solution)
                    eliminated = True
                    break

            if eliminated:
                break

        if not eliminated:
            break

    return solution


# ---------------------------------------------------------------------------
# Move: Intra-route 2-opt (reverse a segment within one route)
# ---------------------------------------------------------------------------

def _try_intra_two_opt(
    instance: Instance,
    solution: Solution,
    ri: int,
    before_scalar: float,
) -> bool:
    """
    Classic 2-opt within a single route: reverse segment [i..j].
    Checks feasibility (TW + capacity + pickup-before-delivery).
    Returns True if an improving move was applied (best-improvement).
    """
    route = solution.routes[ri]
    stops = route.stops
    n = len(stops)
    if n < 4:
        return False

    old_tt = float(route.total_travel_time)
    best_gain = 0.0
    best_stops: Optional[List[int]] = None

    for i in range(n - 1):
        for j in range(i + 2, n):
            new_stops = stops[:i] + stops[i:j + 1][::-1] + stops[j + 1:]
            temp = Route(stops=new_stops)
            if not check_route_feasible(instance, temp):
                continue
            gain = old_tt - float(temp.total_travel_time)
            if gain > best_gain:
                best_gain = gain
                best_stops = new_stops

    if best_stops is None:
        return False

    route.stops = best_stops
    check_route_feasible(instance, route)
    _recompute_solution_cost(solution)
    return True


def intra_route_two_opt(instance: Instance, solution: Solution) -> bool:
    """
    Run intra-route 2-opt over ALL routes. Returns True if any route improved.
    """
    improved = False
    for ri in range(len(solution.routes)):
        if not solution.routes[ri].stops:
            continue
        before = _scalar_cost(solution)
        if _try_intra_two_opt(instance, solution, ri, before):
            improved = True
    return improved


def intra_route_or_opt(instance: Instance, solution: Solution) -> bool:
    """
    Intra-route or-opt: for each route, try moving each pickup-delivery pair
    to a better position within the same route (exhaustive, best-improvement).
    Returns True if any improvement was found.
    """
    improved = False
    for ri, route in enumerate(solution.routes):
        if not route.stops:
            continue
        stops = route.stops
        n = len(stops)
        if n < 4:
            continue

        req_to_ri = _request_to_route_index(instance, solution)
        route_reqs = [req for req in instance.requests if req_to_ri.get(req.id) == ri]

        for req in route_reqs:
            p, d = req.pickup_node, req.delivery_node
            # Remove p and d from stops
            base = [s for s in stops if s != p and s != d]
            m = len(base)
            old_tt = float(route.total_travel_time)
            best_gain = 0.0
            best_stops: Optional[List[int]] = None

            for pi in range(m + 1):
                for di in range(pi + 1, m + 2):
                    new_stops = _insert_nodes(base, p, d, pi, di)
                    temp = Route(stops=new_stops)
                    if not check_route_feasible(instance, temp):
                        continue
                    gain = old_tt - float(temp.total_travel_time)
                    if gain > best_gain:
                        best_gain = gain
                        best_stops = new_stops

            if best_stops is not None:
                route.stops = best_stops
                check_route_feasible(instance, route)
                _recompute_solution_cost(solution)
                stops = route.stops  # update for next req
                improved = True

    return improved


# ---------------------------------------------------------------------------
# Move: 2-opt* (swap route suffixes between two routes)
# ---------------------------------------------------------------------------

def _try_two_opt_star(
    instance: Instance,
    solution: Solution,
    ri_a: int,
    ri_b: int,
    before_scalar: float,
    rng,
    max_splits: int = 0,
) -> bool:
    """
    2-opt* inter-route: try swapping the suffix of route A with the suffix of route B.

    For split points (i, j):
      A' = A[:i] + B[j:]
      B' = B[:j] + A[i:]

    Both new routes must be feasible (TW + capacity + precedence).
    Only accepts strictly improving moves.

    max_splits=0 means exhaustive (all i,j pairs); > 0 means random sample.
    """
    route_a = solution.routes[ri_a]
    route_b = solution.routes[ri_b]
    if not route_a.stops or not route_b.stops:
        return False

    before_a = route_a.copy()
    before_b = route_b.copy()
    stops_a = route_a.stops
    stops_b = route_b.stops
    na, nb = len(stops_a), len(stops_b)

    # Build candidate (i, j) pairs
    if max_splits > 0:
        pairs = [(rng.randint(1, na), rng.randint(1, nb)) for _ in range(max_splits)]
    else:
        pairs = [(i, j) for i in range(1, na + 1) for j in range(1, nb + 1)]

    best_gain = 0.0
    best_move: Optional[Tuple] = None

    old_tt = float(route_a.total_travel_time) + float(route_b.total_travel_time)
    old_routes = sum(1 for r in solution.routes if r.stops)

    for i, j in pairs:
        new_stops_a = stops_a[:i] + stops_b[j:]
        new_stops_b = stops_b[:j] + stops_a[i:]

        temp_a = Route(stops=new_stops_a) if new_stops_a else Route(stops=[])
        temp_b = Route(stops=new_stops_b) if new_stops_b else Route(stops=[])

        ok_a = check_route_feasible(instance, temp_a) if new_stops_a else True
        ok_b = check_route_feasible(instance, temp_b) if new_stops_b else True
        if not (ok_a and ok_b):
            continue

        new_tt = (float(temp_a.total_travel_time) if new_stops_a else 0.0) + \
                 (float(temp_b.total_travel_time) if new_stops_b else 0.0)
        new_routes = old_routes \
            - (1 if not new_stops_a else 0) \
            - (1 if not new_stops_b else 0)

        new_scalar = new_routes * ROUTE_PENALTY + (solution.total_cost - int(old_tt) + int(new_tt))
        gain = before_scalar - new_scalar
        if gain > best_gain:
            best_gain = gain
            best_move = (temp_a, temp_b)

    if best_move is None:
        return False

    new_route_a, new_route_b = best_move
    solution.routes[ri_a] = new_route_a
    solution.routes[ri_b] = new_route_b
    _recompute_solution_cost(solution)
    return True


# ---------------------------------------------------------------------------
# Main local search
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LocalSearchConfig:
    max_moves: int = 30
    route_samples: int = 8
    pos_trials_per_route: int = 24
    first_improvement: bool = True
    p_relocate: float = 0.35    # probability of relocate move
    p_swap: float = 0.20        # probability of swap move
    p_or_opt: float = 0.10      # probability of or_opt move (2-request block)
    p_two_opt_star: float = 0.20  # probability of 2-opt* inter-route
    p_intra_two_opt: float = 0.15  # probability of intra-route 2-opt
    two_opt_star_max_splits: int = 0  # 0 = exhaustive; >0 = sampled


def local_search(
    instance: Instance,
    solution: Solution,
    rng,
    cfg: LocalSearchConfig,
) -> Solution:
    """
    Request-level local search with four move types:
    - Relocate     (40%): move 1 request to a better route/position.
    - Swap         (25%): exchange 2 requests between different routes.
    - Or-opt       (15%): move 2 requests together from one route to another.
    - 2-opt*       (20%): swap suffixes of two routes (inter-route restructuring).
    Only improving moves are accepted (first-improvement or best-improvement).
    """
    if cfg.max_moves <= 0 or not solution.routes:
        return solution

    for r in solution.routes:
        check_route_feasible(instance, r)
    _recompute_solution_cost(solution)

    # Empty-one-route phase first
    while try_empty_one_route(instance, solution):
        pass

    for _ in range(cfg.max_moves):
        active = [r for r in solution.routes if r.stops]
        if not active:
            break

        req_to_ri = _request_to_route_index(instance, solution)
        served = [req for req in instance.requests if req.id in req_to_ri]
        if not served:
            break

        before_scalar = _scalar_cost(solution)
        roll = rng.random()

        # --- Relocate ---
        if roll < cfg.p_relocate:
            req = rng.choice(served)
            ri = req_to_ri[req.id]
            _try_relocate(
                instance, solution, req, ri, before_scalar, rng,
                cfg.route_samples, cfg.pos_trials_per_route, cfg.first_improvement,
            )

        # --- Swap ---
        elif roll < cfg.p_relocate + cfg.p_swap:
            if len(served) < 2:
                continue
            req_a = rng.choice(served)
            ri_a = req_to_ri[req_a.id]
            others = [r for r in served if req_to_ri[r.id] != ri_a]
            if not others:
                continue
            req_b = rng.choice(others)
            ri_b = req_to_ri[req_b.id]
            _try_swap(
                instance, solution, req_a, ri_a, req_b, ri_b,
                before_scalar, rng, cfg.pos_trials_per_route,
            )

        # --- Or-opt (2-request block relocation) ---
        elif roll < cfg.p_relocate + cfg.p_swap + cfg.p_or_opt:
            if len(served) < 2:
                continue
            req_a = rng.choice(served)
            ri_src = req_to_ri[req_a.id]
            same_route = [r for r in served if req_to_ri[r.id] == ri_src and r.id != req_a.id]
            if not same_route:
                continue
            req_b = rng.choice(same_route)
            other_routes = [ri for ri in range(len(solution.routes))
                            if ri != ri_src and solution.routes[ri].stops]
            if not other_routes:
                continue
            ri_dst = rng.choice(other_routes)
            _try_or_opt(
                instance, solution, req_a, req_b, ri_src, ri_dst,
                before_scalar, rng, cfg.pos_trials_per_route,
            )

        # --- 2-opt* (inter-route suffix swap) ---
        elif roll < cfg.p_relocate + cfg.p_swap + cfg.p_or_opt + cfg.p_two_opt_star:
            active_indices = [i for i, r in enumerate(solution.routes) if r.stops]
            if len(active_indices) < 2:
                continue
            ri_a, ri_b = rng.sample(active_indices, 2)
            _try_two_opt_star(
                instance, solution, ri_a, ri_b, before_scalar, rng,
                cfg.two_opt_star_max_splits,
            )

        # --- Intra-route 2-opt (cost reduction within single route) ---
        else:
            active_indices = [i for i, r in enumerate(solution.routes) if r.stops]
            if not active_indices:
                continue
            ri = rng.choice(active_indices)
            _try_intra_two_opt(instance, solution, ri, before_scalar)

    solution.routes = [r for r in solution.routes if r.stops]
    _recompute_solution_cost(solution)
    return solution


# ---------------------------------------------------------------------------
# Exhaustive deterministic improvement pass (post-ALNS)
# ---------------------------------------------------------------------------

def exhaustive_improve(instance: Instance, solution: Solution, rng) -> Solution:
    """
    Systematic best-improvement pass over all moves — deterministic, no random sampling.
    Runs until no further improvement is found.

    Order per pass:
      1. Intra-route 2-opt for all routes
      2. 2-opt* (exhaustive) for all route pairs
      3. Relocate every request to every other route (all positions)
      4. Or-opt-2: move 2 requests together from one route to another
    """
    from solver.models import Solution as _Sol

    for r in solution.routes:
        check_route_feasible(instance, r)
    _recompute_solution_cost(solution)

    improved_overall = True
    outer_pass = 0
    while improved_overall and outer_pass < 5:
        improved_overall = False
        outer_pass += 1

        # ── 1. Intra-route 2-opt ─────────────────────────────────────────────
        for ri in range(len(solution.routes)):
            if not solution.routes[ri].stops:
                continue
            before = _scalar_cost(solution)
            if _try_intra_two_opt(instance, solution, ri, before):
                improved_overall = True

        # ── 2. Exhaustive 2-opt* for all route pairs ─────────────────────────
        active = [i for i, r in enumerate(solution.routes) if r.stops]
        for idx_a in range(len(active)):
            for idx_b in range(idx_a + 1, len(active)):
                ri_a, ri_b = active[idx_a], active[idx_b]
                before = _scalar_cost(solution)
                if _try_two_opt_star(instance, solution, ri_a, ri_b, before, rng, max_splits=0):
                    improved_overall = True
                    active = [i for i, r in enumerate(solution.routes) if r.stops]
                    break
            else:
                continue
            break  # restart outer pair loop after any improvement

        # ── 3. Relocate: each request → every other route, all positions ─────
        req_to_ri = _request_to_route_index(instance, solution)
        served = [req for req in instance.requests if req.id in req_to_ri]
        active = [i for i, r in enumerate(solution.routes) if r.stops]

        for _relocate_pass in range(3):  # max 3 passes to avoid O(n^4) blow-up
            moved = False
            req_to_ri = _request_to_route_index(instance, solution)
            served = [req for req in instance.requests if req.id in req_to_ri]
            n_routes_now = sum(1 for r in solution.routes if r.stops)

            for req in served:
                ri = req_to_ri[req.id]
                pickup, delivery = req.pickup_node, req.delivery_node

                # Cost of route_a without req
                base_a = [s for s in solution.routes[ri].stops if s != pickup and s != delivery]
                temp_a = Route(stops=base_a) if base_a else Route(stops=[])
                ok_a = check_route_feasible(instance, temp_a) if base_a else True
                if not ok_a:
                    continue
                old_tt_a = float(solution.routes[ri].total_travel_time)
                new_tt_a = float(temp_a.total_travel_time) if base_a else 0.0

                best_rj: Optional[int] = None
                best_stops: Optional[List[int]] = None
                best_gain = 0.0

                for rj in range(len(solution.routes)):
                    route_b = solution.routes[rj]
                    if rj == ri:
                        base_b = base_a  # req already removed
                    else:
                        base_b = route_b.stops
                    m = len(base_b)
                    if pickup in base_b or delivery in base_b:
                        continue
                    old_tt_b = float(route_b.total_travel_time) if rj != ri else 0.0

                    for pi in range(m + 1):
                        for di in range(pi + 1, m + 2):
                            new_stops = _insert_nodes(base_b, pickup, delivery, pi, di)
                            temp = Route(stops=new_stops)
                            if not check_route_feasible(instance, temp):
                                continue
                            # Gain = reduction in total travel time
                            delta_tt = (new_tt_a + float(temp.total_travel_time)) - (old_tt_a + old_tt_b)
                            # Route count change
                            new_n = n_routes_now - (1 if not base_a and rj != ri else 0)
                            delta_scalar = (new_n - n_routes_now) * ROUTE_PENALTY + delta_tt
                            gain = -delta_scalar
                            if gain > best_gain:
                                best_gain = gain
                                best_rj = rj
                                best_stops = new_stops

                if best_rj is not None and best_stops is not None:
                    # Apply move
                    solution.routes[ri].stops = base_a
                    if base_a:
                        check_route_feasible(instance, solution.routes[ri])
                    solution.routes[best_rj].stops = best_stops
                    check_route_feasible(instance, solution.routes[best_rj])
                    _recompute_solution_cost(solution)
                    req_to_ri[req.id] = best_rj
                    moved = True
                    improved_overall = True

            if not moved:
                break

    solution.routes = [r for r in solution.routes if r.stops]
    _recompute_solution_cost(solution)
    return solution
