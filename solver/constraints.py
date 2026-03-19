"""
Feasibility checks for PDPTW: time windows, capacity, precedence.
"""
from __future__ import annotations

from typing import Dict, List, Tuple

from solver.models import Instance, Node, Request, Route, Solution


def _get_node_to_request_maps(instance: Instance) -> Tuple[Dict[int, Request], Dict[int, Request]]:
    """
    Lazily build and cache maps on the instance:
    - node_id -> Request (for both pickup and delivery nodes)
    - request_id -> Request
    """
    node_to_req = getattr(instance, "_node_to_req", None)
    reqid_to_req = getattr(instance, "_reqid_to_req", None)
    if node_to_req is not None and reqid_to_req is not None:
        return node_to_req, reqid_to_req

    node_to_req = {}
    reqid_to_req = {}
    for req in instance.requests:
        reqid_to_req[req.id] = req
        node_to_req[req.pickup_node] = req
        node_to_req[req.delivery_node] = req

    setattr(instance, "_node_to_req", node_to_req)
    setattr(instance, "_reqid_to_req", reqid_to_req)
    return node_to_req, reqid_to_req


def _compute_route_schedule(instance: Instance, route: Route) -> bool:
    """
    Fill route.arrival_times, start_service_times, loads from route.stops.
    Returns True if feasible (TW, capacity); False otherwise.
    """
    depot = instance.depot_id
    nodes = instance.nodes
    tt = instance.travel_time
    cap = instance.capacity
    horizon = instance.horizon

    stops = route.stops
    n = len(stops)
    if n == 0:
        route.arrival_times = []
        route.start_service_times = []
        route.loads = []
        route.total_travel_time = 0
        route.total_waiting_time = 0
        return True

    arrival: List[float] = [0.0] * n
    start_service: List[float] = [0.0] * n
    load: List[int] = [0] * n

    # First stop: from depot
    arrival[0] = tt[depot][stops[0]]
    start_service[0] = max(arrival[0], float(nodes[stops[0]].tw_early))
    if start_service[0] > nodes[stops[0]].tw_late:
        return False
    # Load after serving stop 0: pickup adds +demand, delivery adds demand (negative)
    load[0] = nodes[stops[0]].demand
    if load[0] < 0:
        return False  # first stop cannot be delivery (nothing on board yet)
    if load[0] > cap:
        return False

    for i in range(1, n):
        prev = stops[i - 1]
        curr = stops[i]
        arrival[i] = start_service[i - 1] + nodes[prev].service_duration + tt[prev][curr]
        start_service[i] = max(arrival[i], float(nodes[curr].tw_early))
        if start_service[i] > nodes[curr].tw_late:
            return False
        d = nodes[curr].demand
        load[i] = load[i - 1] + (d if d > 0 else d)  # pickup: +demand, delivery: demand is negative
        if load[i] < 0 or load[i] > cap:
            return False

    # Return to depot
    last = stops[-1]
    back_time = start_service[-1] + nodes[last].service_duration + tt[last][depot]
    if back_time > horizon:
        return False

    route.arrival_times = [int(round(t)) for t in arrival]
    route.start_service_times = [int(round(t)) for t in start_service]
    route.loads = list(load)
    total_travel = tt[depot][stops[0]]
    for i in range(1, n):
        total_travel += tt[stops[i - 1]][stops[i]]
    total_travel += tt[last][depot]
    route.total_travel_time = int(round(total_travel))
    route.total_waiting_time = int(round(sum(start_service[i] - arrival[i] for i in range(n))))
    return True


def check_route_feasible(instance: Instance, route: Route) -> bool:
    """
    Check one route: time windows, capacity, and precedence (pickup before delivery).
    Fills route's arrival_times, start_service_times, loads if feasible.
    """
    if not route.stops:
        return _compute_route_schedule(instance, route)

    node_to_req, _ = _get_node_to_request_maps(instance)
    pos = {node_id: i for i, node_id in enumerate(route.stops)}

    # Precedence + paired presence (operate only on requests that appear in this route).
    seen_req_ids = set()
    for node_id in route.stops:
        req = node_to_req.get(node_id)
        if req is None or req.id in seen_req_ids:
            continue
        seen_req_ids.add(req.id)
        pi = pos.get(req.pickup_node)
        di = pos.get(req.delivery_node)
        if pi is None or di is None:
            return False
        if pi >= di:
            return False

    return _compute_route_schedule(instance, route)


def check_solution_feasible(instance: Instance, solution: Solution) -> bool:
    """
    Check solution: every request in exactly one route, pickup before delivery,
    TW and capacity on each route.
    """
    node_to_req, reqid_to_req = _get_node_to_request_maps(instance)
    covered_req_ids = set()

    for route in solution.routes:
        if not route.stops:
            continue
        present = set(route.stops)

        # Validate paired presence and uniqueness across routes.
        route_req_ids = set()
        for node_id in present:
            req = node_to_req.get(node_id)
            if req is None:
                continue
            route_req_ids.add(req.id)

        for rid in route_req_ids:
            if rid in covered_req_ids:
                return False
            covered_req_ids.add(rid)
            req = reqid_to_req.get(rid)
            if req is None:
                return False
            if req.pickup_node not in present or req.delivery_node not in present:
                return False

        if not check_route_feasible(instance, route):
            return False

    return len(covered_req_ids) == len(instance.requests)


def quick_feasibility(instance: Instance) -> bool:
    """
    Fast pre-check: e.g. total demand vs capacity, trivial TW infeasibility.
    Returns False if instance is clearly too tight to be worth solving.
    """
    total_demand = sum(r.demand for r in instance.requests)
    if total_demand <= 0:
        return True
    # One vehicle can carry at most capacity per trip; loose bound
    if instance.capacity <= 0:
        return False
    min_vehicles = (total_demand + instance.capacity - 1) // instance.capacity
    if min_vehicles > 1000:  # arbitrary
        return False
    return True
