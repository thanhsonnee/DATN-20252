"""
ALNS main loop: destroy -> repair -> accept, with time limit and optional 3-stage.
"""
from __future__ import annotations

import random

from solver.alns.acceptance import accept_sa
from solver.alns.local_search import LocalSearchConfig, local_search
from solver.alns.operators_destroy import (
    cluster_removal,
    random_removal,
    route_removal,
    shaw_removal,
    worst_removal,
)
from solver.alns.operators_repair import greedy_repair, regret_repair
from solver.alns.state import AlnsState
from solver.config import (
    DESTROY_STAGE1_MAX_FRAC,
    DESTROY_STAGE1_MIN_FRAC,
    DESTROY_STAGE1_P_RANDOM,
    DESTROY_STAGE1_P_SHAW,
    DESTROY_STAGE1_P_WORST,
    DESTROY_STAGE2_MAX_FRAC,
    DESTROY_STAGE2_MIN_FRAC,
    DESTROY_STAGE2_P_CLUSTER,
    DESTROY_STAGE2_P_RANDOM,
    DESTROY_STAGE2_P_SHAW,
    DESTROY_STAGE2_P_WORST,
    DESTROY_STAGE3_MAX_FRAC,
    DESTROY_STAGE3_MIN_FRAC,
    DESTROY_STAGE3_P_ROUTE,
    DESTROY_STAGE3_P_SHAW,
    DESTROY_STAGE3_P_WORST,
    LS_FIRST_IMPROVEMENT,
    LS_POS_TRIALS_PER_ROUTE,
    LS_ROUTE_SAMPLES,
    LS_STAGE2_MAX_MOVES,
    LS_STAGE3_MAX_MOVES,
    REPAIR_EJECTION_MAX,
    REPAIR_EJECTION_TRIES,
    REPAIR_POS_TRIALS_PER_ROUTE,
    REPAIR_REGRET_K,
    REPAIR_ROUTE_SAMPLES,
    SA_COOLING,
    SA_INITIAL_TEMPERATURE,
    STAGE_BALANCE_END,
    STAGE_DIVERSIFY_END,
    TIME_LIMIT_SEC,
)
from solver.models import Instance, Solution


def _is_solution_complete(instance: Instance, solution: Solution) -> bool:
    """
    Fast completeness check: each request appears exactly once (both pickup & delivery in same route).
    Does not fully revalidate time windows/capacity (those are ensured by route feasibility checks).
    """
    covered = [False] * len(instance.requests)
    req_by_pickup = {r.pickup_node: i for i, r in enumerate(instance.requests)}
    req_by_delivery = {r.delivery_node: i for i, r in enumerate(instance.requests)}

    for route in solution.routes:
        if not route.stops:
            continue
        present = set(route.stops)
        # Check paired appearance and uniqueness by scanning requests seen in this route.
        route_req_ids = set()
        for n in present:
            idx = req_by_pickup.get(n)
            if idx is None:
                idx = req_by_delivery.get(n)
            if idx is None:
                continue
            if idx in route_req_ids:
                continue
            req = instance.requests[idx]
            if req.pickup_node in present and req.delivery_node in present:
                route_req_ids.add(idx)

        for idx in route_req_ids:
            if covered[idx]:
                return False
            covered[idx] = True

    return all(covered)


def _choose_by_probs(rng, items):
    """
    items: list of (name, probability) where probabilities sum to 1.
    returns chosen name.
    """
    x = rng.random()
    cum = 0.0
    for name, p in items:
        cum += p
        if x <= cum:
            return name
    return items[-1][0]


def run_alns(
    instance: Instance,
    initial: Solution,
    time_limit_sec: float = TIME_LIMIT_SEC,
    seed: int = 0,
) -> Solution:
    """
    Run ALNS from initial solution until time_limit_sec.
    Returns best solution (fewer routes first, then lower cost).
    """
    rng = random.Random(seed)
    state = AlnsState(instance, initial)
    n_req = instance.num_requests()
    T = SA_INITIAL_TEMPERATURE

    while state.elapsed() < time_limit_sec:
        progress = state.elapsed() / time_limit_sec
        # Destroy size: stage-specific random within README ranges
        if progress < STAGE_DIVERSIFY_END:
            frac = rng.uniform(DESTROY_STAGE1_MIN_FRAC, DESTROY_STAGE1_MAX_FRAC)
            destroy_mix = [
                ("random", DESTROY_STAGE1_P_RANDOM),
                ("shaw", DESTROY_STAGE1_P_SHAW),
                ("worst", DESTROY_STAGE1_P_WORST),
            ]
        elif progress < STAGE_BALANCE_END:
            frac = rng.uniform(DESTROY_STAGE2_MIN_FRAC, DESTROY_STAGE2_MAX_FRAC)
            destroy_mix = [
                ("random", DESTROY_STAGE2_P_RANDOM),
                ("shaw", DESTROY_STAGE2_P_SHAW),
                ("worst", DESTROY_STAGE2_P_WORST),
                ("cluster", DESTROY_STAGE2_P_CLUSTER),
            ]
        else:
            frac = rng.uniform(DESTROY_STAGE3_MIN_FRAC, DESTROY_STAGE3_MAX_FRAC)
            destroy_mix = [
                ("worst", DESTROY_STAGE3_P_WORST),
                ("route", DESTROY_STAGE3_P_ROUTE),
                ("shaw", DESTROY_STAGE3_P_SHAW),
            ]
        n_remove = max(1, min(n_req, int(n_req * frac)))

        current = state.get_current()
        op = _choose_by_probs(rng, destroy_mix)
        if op == "random":
            destroyed, removed = random_removal(instance, current.copy(), n_remove, rng)
        elif op == "shaw":
            destroyed, removed = shaw_removal(instance, current.copy(), n_remove, rng)
        elif op == "worst":
            destroyed, removed = worst_removal(instance, current.copy(), n_remove, rng)
        elif op == "cluster":
            destroyed, removed = cluster_removal(instance, current.copy(), n_remove, rng)
        elif op == "route":
            destroyed, removed = route_removal(instance, current.copy(), num_routes_to_remove=1, rng=rng)
        else:
            destroyed, removed = random_removal(instance, current.copy(), n_remove, rng)

        if not removed:
            state.iterations += 1
            T *= SA_COOLING
            continue

        # Stage-dependent repair
        if progress < STAGE_DIVERSIFY_END:
            candidate = greedy_repair(instance, destroyed, removed, rng)
        else:
            candidate = regret_repair(
                instance,
                destroyed,
                removed,
                rng,
                k=REPAIR_REGRET_K,
                route_samples=REPAIR_ROUTE_SAMPLES,
                pos_trials_per_route=REPAIR_POS_TRIALS_PER_ROUTE,
                ejection_max=REPAIR_EJECTION_MAX,
                ejection_tries=REPAIR_EJECTION_TRIES,
            )
        if not _is_solution_complete(instance, candidate):
            state.iterations += 1
            T *= SA_COOLING
            continue

        # Stage-dependent intensification
        if progress >= STAGE_DIVERSIFY_END:
            ls_moves = LS_STAGE2_MAX_MOVES if progress < STAGE_BALANCE_END else LS_STAGE3_MAX_MOVES
            candidate = local_search(
                instance,
                candidate,
                rng=rng,
                cfg=LocalSearchConfig(
                    max_moves=ls_moves,
                    route_samples=LS_ROUTE_SAMPLES,
                    pos_trials_per_route=LS_POS_TRIALS_PER_ROUTE,
                    first_improvement=LS_FIRST_IMPROVEMENT,
                ),
            )
        if accept_sa(current, candidate, T, rng):
            state.accept_current_as_new(candidate)
        T *= SA_COOLING
        state.iterations += 1

    return state.get_best()
