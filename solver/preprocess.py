"""
Phase 0 – Preprocess & quick feasibility.

Provides:
- quick_feasibility_check(instance) → bool   (fast necessary-condition check)
- precompute(instance)              → dict    (precomputed bounds used by ALNS)

Called before construction so the solver can fail fast on clearly infeasible
instances (e.g. a node's time window is earlier than the travel time from the
depot, or the total demand exceeds every possible vehicle count).
"""
from __future__ import annotations

from solver.constraints import quick_feasibility
from solver.models import Instance


def quick_feasibility_check(instance: Instance) -> bool:
    """
    Necessary-condition checks that are cheap to compute.

    Returns False if the instance is provably infeasible:
      1. Any customer node is unreachable from the depot before its TW closes.
      2. For any request, delivery is unreachable after pickup.
      3. Total demand requires more vehicles than a loose upper bound allows.
      4. Capacity is zero or negative.

    Returns True otherwise (the instance *might* be feasible).
    """
    nodes = instance.nodes
    tt = instance.travel_time
    depot = instance.depot_id
    cap = instance.capacity

    # Basic capacity check (delegate to constraints module as well)
    if not quick_feasibility(instance):
        return False

    # Check every customer node reachable from depot within its TW
    for nid, node in nodes.items():
        if nid == depot:
            continue
        earliest_arrival = tt[depot][nid]
        if earliest_arrival > node.tw_late:
            return False

    # Check each request: pickup reachable, then delivery reachable after pickup
    for req in instance.requests:
        p_node = nodes[req.pickup_node]
        d_node = nodes[req.delivery_node]

        # Earliest service start at pickup
        t_p = max(tt[depot][req.pickup_node], float(p_node.tw_early))
        if t_p > p_node.tw_late:
            return False

        # Earliest service start at delivery
        t_d = t_p + p_node.service_duration + tt[req.pickup_node][req.delivery_node]
        t_d = max(t_d, float(d_node.tw_early))
        if t_d > d_node.tw_late:
            return False

        # Demand must not exceed vehicle capacity on its own
        if req.demand > cap:
            return False

    return True


def precompute(instance: Instance) -> dict:
    """
    Compute and cache auxiliary data on the instance object.

    Returns a dict with:
      - feasible          : bool  – result of quick_feasibility_check
      - tw_slack          : dict[node_id, float]  – TW width per node
      - earliest_arrival  : dict[node_id, float]  – earliest arrival from depot
      - latest_departure  : dict[node_id, float]  – latest departure to depot
      - req_urgency       : dict[req_id, float]   – tightness score per request
        (lower = more urgent; used to prioritise insertion order)

    All computed values are also stored as instance attributes so callers
    can access them without re-running precompute:
      instance._tw_slack, instance._earliest_arrival, etc.
    """
    nodes = instance.nodes
    tt = instance.travel_time
    depot = instance.depot_id

    feasible = quick_feasibility_check(instance)

    # TW slack
    tw_slack: dict[int, float] = {
        nid: float(node.tw_late - node.tw_early)
        for nid, node in nodes.items()
    }

    # Earliest arrival from depot (ignoring TW – pure travel time)
    earliest_arrival: dict[int, float] = {
        nid: tt[depot][nid]
        for nid in nodes
    }

    # Latest departure back to depot to arrive before horizon
    horizon = float(instance.horizon)
    latest_departure: dict[int, float] = {}
    for nid, node in nodes.items():
        # Must leave nid no later than horizon - travel_time(nid→depot)
        latest_departure[nid] = horizon - tt[nid][depot] - node.service_duration

    # Request urgency: tight TW at pickup + tight TW at delivery → high urgency
    req_urgency: dict[int, float] = {}
    for req in instance.requests:
        slack_p = tw_slack.get(req.pickup_node, 1e9)
        slack_d = tw_slack.get(req.delivery_node, 1e9)
        req_urgency[req.id] = (slack_p + slack_d) / 2.0

    # Cache on instance object so operators can reuse without re-computing
    setattr(instance, "_tw_slack", tw_slack)
    setattr(instance, "_earliest_arrival", earliest_arrival)
    setattr(instance, "_latest_departure", latest_departure)
    setattr(instance, "_req_urgency", req_urgency)

    return {
        "feasible": feasible,
        "tw_slack": tw_slack,
        "earliest_arrival": earliest_arrival,
        "latest_departure": latest_departure,
        "req_urgency": req_urgency,
    }
