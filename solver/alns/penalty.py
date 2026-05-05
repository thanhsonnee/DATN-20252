"""
Adaptive penalty for ALNS – Phase 6.

Three penalty dimensions:
  - lambda_missing  : penalises requests not served at all (incomplete solution)
  - lambda_tw       : penalises cumulative time-window violation across all routes
  - lambda_cap      : penalises cumulative capacity violation across all routes

All three lambdas are updated adaptively based on recent feasibility ratios:
  - lambda_missing  tracks the fraction of complete solutions in a sliding window
  - lambda_tw / lambda_cap track the fraction of TW/capacity-feasible solutions

Precedence (pickup-before-delivery) is kept HARD – operators never violate it.
"""
from __future__ import annotations

from typing import List

from solver.construction import ROUTE_PENALTY
from solver.models import Instance, Solution


def _compute_violations(solution: Solution, instance: Instance) -> tuple[float, float, int]:
    """
    Compute soft violation amounts for a solution (routes may be infeasible).

    Returns:
      (tw_violation, cap_violation, missing_count)

    tw_violation  – total seconds of time-window lateness across all stops
    cap_violation – total units of capacity excess across all stops
    missing_count – number of requests not fully served
    """
    nodes = instance.nodes
    tt = instance.travel_time
    depot = instance.depot_id
    cap = instance.capacity

    tw_viol = 0.0
    cap_viol = 0.0

    served_nodes: set[int] = set()

    for route in solution.routes:
        if not route.stops:
            continue
        stops = route.stops
        served_nodes.update(stops)

        # Simulate schedule without early-exit (soft check)
        time = tt[depot][stops[0]]
        load = 0
        for i, nid in enumerate(stops):
            node = nodes[nid]
            # Time window
            start = max(time, float(node.tw_early))
            lateness = max(0.0, start - node.tw_late)
            tw_viol += lateness
            # Capacity
            load += node.demand
            excess = max(0, load - cap)
            cap_viol += excess
            if i + 1 < len(stops):
                time = start + node.service_duration + tt[nid][stops[i + 1]]

    # Missing requests
    missing = sum(
        1 for req in instance.requests
        if req.pickup_node not in served_nodes or req.delivery_node not in served_nodes
    )

    return tw_viol, cap_viol, missing


class AdaptivePenalty:
    """
    Tracks solution feasibility and adjusts three lambdas dynamically.

    penalized_cost() returns a scalar comparable across complete, incomplete,
    and soft-infeasible solutions so the SA acceptance criterion can work
    uniformly.
    """

    def __init__(
        self,
        lambda_missing: float = 1.0,
        lambda_tw: float = 0.5,
        lambda_cap: float = 0.5,
        target_feasible: float = 0.50,
        window_size: int = 50,
        update_freq: int = 50,
        lambda_min: float = 0.1,
        lambda_max: float = 20.0,
        adjust_factor: float = 1.2,
    ) -> None:
        self.lambda_missing = lambda_missing
        self.lambda_tw = lambda_tw
        self.lambda_cap = lambda_cap
        self.target_feasible = target_feasible
        self.window_size = window_size
        self.update_freq = update_freq
        self.lambda_min = lambda_min
        self.lambda_max = lambda_max
        self.adjust_factor = adjust_factor

        # Separate windows for each dimension
        self._window_missing: List[bool] = []   # True = complete
        self._window_tw: List[bool] = []        # True = TW feasible
        self._window_cap: List[bool] = []       # True = cap feasible
        self._iters_since_update: int = 0

    def penalized_cost(self, solution: Solution, instance: Instance) -> float:
        """
        Scalar cost with soft penalties.

        For a complete, fully feasible solution this equals:
          num_routes * ROUTE_PENALTY + total_cost
        """
        n_routes = sum(1 for r in solution.routes if r.stops)
        base = n_routes * ROUTE_PENALTY + solution.total_cost

        tw_viol, cap_viol, missing = _compute_violations(solution, instance)

        return (
            base
            + self.lambda_missing * missing * ROUTE_PENALTY
            + self.lambda_tw * tw_viol
            + self.lambda_cap * cap_viol
        )

    def record(self, is_complete: bool, solution: Solution | None = None, instance: Instance | None = None) -> None:
        """
        Record candidate solution feasibility and maybe update lambdas.

        Pass solution + instance to also track TW/capacity feasibility;
        if omitted, TW/cap windows are updated conservatively (same as is_complete).
        """
        tw_ok = True
        cap_ok = True
        if solution is not None and instance is not None:
            tw_viol, cap_viol, _ = _compute_violations(solution, instance)
            tw_ok = tw_viol == 0.0
            cap_ok = cap_viol == 0.0

        self._window_missing.append(is_complete)
        self._window_tw.append(tw_ok)
        self._window_cap.append(cap_ok)

        for w in (self._window_missing, self._window_tw, self._window_cap):
            if len(w) > self.window_size:
                w.pop(0)

        self._iters_since_update += 1
        if self._iters_since_update >= self.update_freq:
            self._update_lambdas()
            self._iters_since_update = 0

    def _update_lambdas(self) -> None:
        def _adjust(lam: float, window: List[bool]) -> float:
            if not window:
                return lam
            frac = sum(window) / len(window)
            if frac < self.target_feasible:
                return min(self.lambda_max, lam * self.adjust_factor)
            return max(self.lambda_min, lam / self.adjust_factor)

        self.lambda_missing = _adjust(self.lambda_missing, self._window_missing)
        self.lambda_tw = _adjust(self.lambda_tw, self._window_tw)
        self.lambda_cap = _adjust(self.lambda_cap, self._window_cap)
