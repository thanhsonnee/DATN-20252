"""
ALNS main loop: destroy -> repair -> accept, 3-stage.

Key improvements over baseline:
  - Dynamic SA temperature: T_initial ∝ initial solution cost (not fixed 1e4)
  - Time-based cooling: T decreases smoothly with elapsed time (instance-size-agnostic)
  - Adaptive operator weights: operators that find improvements are selected more
  - 2-opt* integrated into Stage 2/3 local search
  - Instance-size-aware LS budget: more moves for small instances
  - Phase 7 (SP) and Phase 8 (F&O) in Stage 2/3
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import List

from solver.alns.local_search import LocalSearchConfig, local_search
from solver.alns.operators_destroy import (
    cluster_removal,
    random_removal,
    route_removal,
    shaw_removal,
    worst_removal,
)
from solver.alns.operators_repair import greedy_repair, regret_repair
from solver.alns.penalty import AdaptivePenalty
from solver.alns.state import AlnsState
from solver.config import (
    DESTROY_STAGE1_MAX_FRAC,
    DESTROY_STAGE1_MIN_FRAC,
    DESTROY_STAGE2_MAX_FRAC,
    DESTROY_STAGE2_MIN_FRAC,
    DESTROY_STAGE3_MAX_FRAC,
    DESTROY_STAGE3_MIN_FRAC,
    FO_CALL_FREQ_ITER,
    FO_FIX_RATIO,
    FO_LS_MAX_MOVES,
    FO_NO_IMPROVE_THRESHOLD,
    LS_FIRST_IMPROVEMENT,
    LS_POS_TRIALS_PER_ROUTE,
    LS_ROUTE_SAMPLES,
    PENALTY_ADJUST_FACTOR,
    PENALTY_LAMBDA_CAP_INIT,
    PENALTY_LAMBDA_INIT,
    PENALTY_LAMBDA_MAX,
    PENALTY_LAMBDA_MIN,
    PENALTY_LAMBDA_TW_INIT,
    PENALTY_TARGET_FEASIBLE,
    PENALTY_UPDATE_FREQ,
    PENALTY_WINDOW_SIZE,
    REPAIR_EJECTION_MAX,
    REPAIR_EJECTION_TRIES,
    REPAIR_POS_TRIALS_PER_ROUTE,
    REPAIR_REGRET_K,
    REPAIR_ROUTE_SAMPLES,
    SA_TEMP_FACTOR,
    SA_TEMP_MIN_RATIO,
    SP_CALL_FREQ_ITER,
    SP_POOL_MAX_SIZE,
    SP_TIME_LIMIT_SEC,
    STAGE_BALANCE_END,
    STAGE_DIVERSIFY_END,
    TIME_LIMIT_SEC,
)
from solver.models import Instance, Solution


@dataclass
class AlnsResult:
    solution: Solution
    iterations: int
    elapsed_sec: float


# ---------------------------------------------------------------------------
# Adaptive operator weight tracker
# ---------------------------------------------------------------------------

class _OpTracker:
    """
    Roulette-wheel operator selection with score-based weight update.

    Scores per iteration:
      +4  new global best found
      +2  improved current solution
      +1  accepted (but not improving current)
       0  rejected
    Weights updated every `update_freq` iterations:
      w_i ← (1 - decay) * w_i + decay * (avg_score_i)
    """

    def __init__(self, names: List[str], decay: float = 0.15, update_freq: int = 30) -> None:
        self.names = names
        self.decay = decay
        self.update_freq = update_freq
        self.weights = {n: 1.0 for n in names}
        self._scores = {n: 0.0 for n in names}
        self._uses = {n: 0 for n in names}
        self._since_update = 0

    def choose(self, rng, available: List[str] | None = None) -> str:
        pool = available if available else self.names
        total = sum(self.weights[n] for n in pool)
        x = rng.random() * total
        cum = 0.0
        for n in pool:
            cum += self.weights[n]
            if x <= cum:
                return n
        return pool[-1]

    def record(self, name: str, score: float) -> None:
        self._scores[name] += score
        self._uses[name] += 1
        self._since_update += 1
        if self._since_update >= self.update_freq:
            self._update()
            self._since_update = 0

    def _update(self) -> None:
        for n in self.names:
            if self._uses[n] > 0:
                avg = self._scores[n] / self._uses[n]
                self.weights[n] = (1 - self.decay) * self.weights[n] + self.decay * max(avg, 0.01)
            self._scores[n] = 0.0
            self._uses[n] = 0
        # Normalise to avoid drift
        total = sum(self.weights.values())
        for n in self.names:
            self.weights[n] = self.weights[n] / total * len(self.names)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_solution_complete(instance: Instance, solution: Solution) -> bool:
    covered = [False] * len(instance.requests)
    req_by_pickup = {r.pickup_node: i for i, r in enumerate(instance.requests)}
    req_by_delivery = {r.delivery_node: i for i, r in enumerate(instance.requests)}
    for route in solution.routes:
        if not route.stops:
            continue
        present = set(route.stops)
        route_req_ids: set = set()
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


def _scalar_cost(sol: Solution) -> float:
    from solver.construction import ROUTE_PENALTY
    n = sum(1 for r in sol.routes if r.stops)
    return n * ROUTE_PENALTY + sol.total_cost


# ---------------------------------------------------------------------------
# Main ALNS loop
# ---------------------------------------------------------------------------

def run_alns(
    instance: Instance,
    initial: Solution,
    time_limit_sec: float = TIME_LIMIT_SEC,
    seed: int = 0,
) -> AlnsResult:
    """
    Run ALNS from initial solution until time_limit_sec.

    Stages:
      Stage 1 (0–30%): diversify  – large destroy, greedy repair
      Stage 2 (30–70%): balance   – medium destroy, regret repair, LS, SP
      Stage 3 (70–100%): intensify – small destroy, regret repair, LS, SP, F&O
    """
    rng = random.Random(seed)
    state = AlnsState(instance, initial)
    n_req = instance.num_requests()

    # ── Dynamic SA temperature (proportional to initial cost) ─────────────────
    # T_initial: P(accept move that worsens by SA_TEMP_FACTOR * cost) ≈ 0.5
    T_initial = max(1.0, initial.total_cost * SA_TEMP_FACTOR)
    T_min = T_initial * SA_TEMP_MIN_RATIO

    def _temperature() -> float:
        """Time-based cooling — independent of iteration count."""
        t = state.elapsed() / time_limit_sec
        return T_initial * math.exp(math.log(T_min / T_initial) * t)

    # ── Adaptive operator pools ────────────────────────────────────────────────
    destroy_tracker = _OpTracker(
        ["random", "shaw", "worst", "cluster", "route"],
        decay=0.15, update_freq=40,
    )
    repair_tracker = _OpTracker(
        ["greedy", "regret"],
        decay=0.15, update_freq=40,
    )

    # ── Penalty ───────────────────────────────────────────────────────────────
    penalty = AdaptivePenalty(
        lambda_missing=PENALTY_LAMBDA_INIT,
        lambda_tw=PENALTY_LAMBDA_TW_INIT,
        lambda_cap=PENALTY_LAMBDA_CAP_INIT,
        target_feasible=PENALTY_TARGET_FEASIBLE,
        window_size=PENALTY_WINDOW_SIZE,
        update_freq=PENALTY_UPDATE_FREQ,
        lambda_min=PENALTY_LAMBDA_MIN,
        lambda_max=PENALTY_LAMBDA_MAX,
        adjust_factor=PENALTY_ADJUST_FACTOR,
    )

    # ── Instance size tiers ───────────────────────────────────────────────────
    # small: n100 (≤75 req) — optimise for speed
    # large: n400+ (≥150 req) — optimise for quality, accept longer runtime
    is_small = n_req <= 75
    is_large = n_req >= 150

    # ── Phase 7: Route pool ───────────────────────────────────────────────────
    # Disabled for small instances: SP overhead (MILP) outweighs benefit when
    # the ALNS loop already runs fast and the solution space is small.
    route_pool = None
    if not is_small:
        try:
            from solver.exact.set_partitioning import RoutePool, solve_set_partitioning
            route_pool = RoutePool(max_size=SP_POOL_MAX_SIZE)
        except ImportError:
            pass

    # SP call frequency: more aggressive for large instances
    sp_call_freq = max(40, SP_CALL_FREQ_ITER * 60 // max(60, n_req))

    # ── Phase 8: Fix-and-Optimize ─────────────────────────────────────────────
    # Disabled for small instances for the same reason as SP.
    _fo_available = False
    if not is_small:
        try:
            from solver.exact.fix_and_optimize import fix_and_optimize
            _fo_available = True
        except ImportError:
            pass

    # F&O no-improve threshold: trigger sooner on large instances
    fo_no_improve_thresh = max(80, FO_NO_IMPROVE_THRESHOLD * 60 // max(60, n_req))

    # ── Instance-size-aware LS budget ─────────────────────────────────────────
    # small (n50): ls_s2=100, ls_s3=200  — light LS, fast iterations
    # large (n200): ls_s2=30, ls_s3=75   — more iterations compensate for deeper LS
    ls_stage2 = max(15, min(200, 5000 // max(1, n_req)))
    ls_stage3 = max(30, min(400, 10000 // max(1, n_req)))

    # 2-opt* in ALNS loop: NEVER exhaustive (reserve that for post-processing).
    # Sampled, scaled so small instances still get good coverage.
    two_opt_star_splits = max(20, 3000 // max(1, n_req))

    iters_since_best = 0

    # Stagnation-based perturbation: when best hasn't improved for a while,
    # restart current solution from best with a large ruin (to escape local optima).
    # Threshold scales with instance size: smaller → fire sooner.
    stagnation_threshold = max(100, 400 * 50 // max(50, n_req))
    stagnation_counter = 0

    while state.elapsed() < time_limit_sec:
        progress = state.elapsed() / time_limit_sec
        T = _temperature()

        # ── Stagnation perturbation (escape local optima) ─────────────────────
        # Trigger only in Stage 2/3 to avoid disrupting diversification.
        if (progress >= STAGE_DIVERSIFY_END
                and iters_since_best > stagnation_threshold
                and stagnation_counter < 3):
            # Reset current to best, then do a large ruin (40-60% of requests)
            state.current = state.best.copy()
            pert_frac = rng.uniform(0.40, 0.60)
            pert_n = max(5, min(n_req, int(n_req * pert_frac)))
            pert_current = state.current.copy()
            pert_destroyed, pert_removed = shaw_removal(instance, pert_current, pert_n, rng)
            if pert_removed:
                from solver.alns.operators_repair import regret_repair as _regret_repair
                pert_candidate = _regret_repair(
                    instance, pert_destroyed, pert_removed, rng,
                    k=REPAIR_REGRET_K,
                    route_samples=REPAIR_ROUTE_SAMPLES,
                    pos_trials_per_route=REPAIR_POS_TRIALS_PER_ROUTE,
                    ejection_max=REPAIR_EJECTION_MAX,
                    ejection_tries=REPAIR_EJECTION_TRIES,
                )
                if _is_solution_complete(instance, pert_candidate):
                    state.current = pert_candidate
                    if state.is_better_than_best(pert_candidate):
                        state.best = pert_candidate.copy()
                        iters_since_best = 0
            iters_since_best = 0
            stagnation_counter += 1
            state.iterations += 1
            continue

        # ── Stage-specific destroy size ───────────────────────────────────────
        if progress < STAGE_DIVERSIFY_END:
            frac = rng.uniform(DESTROY_STAGE1_MIN_FRAC, DESTROY_STAGE1_MAX_FRAC)
            available_destroy = ["random", "shaw", "worst"]
        elif progress < STAGE_BALANCE_END:
            frac = rng.uniform(DESTROY_STAGE2_MIN_FRAC, DESTROY_STAGE2_MAX_FRAC)
            available_destroy = ["random", "shaw", "worst", "cluster"]
        else:
            frac = rng.uniform(DESTROY_STAGE3_MIN_FRAC, DESTROY_STAGE3_MAX_FRAC)
            available_destroy = ["worst", "route", "shaw"]

        n_remove = max(1, min(n_req, int(n_req * frac)))
        current = state.get_current()

        # ── Destroy ───────────────────────────────────────────────────────────
        d_op = destroy_tracker.choose(rng, available_destroy)
        if d_op == "random":
            destroyed, removed = random_removal(instance, current.copy(), n_remove, rng)
        elif d_op == "shaw":
            destroyed, removed = shaw_removal(instance, current.copy(), n_remove, rng)
        elif d_op == "worst":
            destroyed, removed = worst_removal(instance, current.copy(), n_remove, rng)
        elif d_op == "cluster":
            destroyed, removed = cluster_removal(instance, current.copy(), n_remove, rng)
        elif d_op == "route":
            destroyed, removed = route_removal(instance, current.copy(), num_routes_to_remove=1, rng=rng)
        else:
            destroyed, removed = random_removal(instance, current.copy(), n_remove, rng)

        if not removed:
            state.iterations += 1
            iters_since_best += 1
            continue

        # ── Repair ────────────────────────────────────────────────────────────
        if progress < STAGE_DIVERSIFY_END:
            available_repair = ["greedy"]
        else:
            available_repair = ["greedy", "regret"]

        r_op = repair_tracker.choose(rng, available_repair)
        if r_op == "regret":
            candidate = regret_repair(
                instance, destroyed, removed, rng,
                k=REPAIR_REGRET_K,
                route_samples=REPAIR_ROUTE_SAMPLES,
                pos_trials_per_route=REPAIR_POS_TRIALS_PER_ROUTE,
                ejection_max=REPAIR_EJECTION_MAX,
                ejection_tries=REPAIR_EJECTION_TRIES,
            )
        else:
            candidate = greedy_repair(instance, destroyed, removed, rng)

        is_complete = _is_solution_complete(instance, candidate)
        penalty.record(is_complete, candidate, instance)

        # ── Local search (Stage 2+, complete only) ────────────────────────────
        if is_complete and progress >= STAGE_DIVERSIFY_END:
            ls_moves = ls_stage2 if progress < STAGE_BALANCE_END else ls_stage3
            candidate = local_search(
                instance, candidate, rng=rng,
                cfg=LocalSearchConfig(
                    max_moves=ls_moves,
                    route_samples=LS_ROUTE_SAMPLES,
                    pos_trials_per_route=LS_POS_TRIALS_PER_ROUTE,
                    first_improvement=LS_FIRST_IMPROVEMENT,
                    p_relocate=0.40,
                    p_swap=0.25,
                    p_or_opt=0.15,
                    p_two_opt_star=0.20,
                    two_opt_star_max_splits=two_opt_star_splits,
                ),
            )

        # ── Acceptance (SA) ───────────────────────────────────────────────────
        pen_candidate = penalty.penalized_cost(candidate, instance)
        pen_current   = penalty.penalized_cost(current, instance)
        delta = pen_candidate - pen_current

        accepted = delta <= 0 or (T > 0 and rng.random() < math.exp(-delta / T))

        op_score = 0.0
        if accepted:
            state.current = candidate.copy()
            if delta < 0:
                op_score = 2.0
            else:
                op_score = 1.0
            if is_complete and state.is_better_than_best(candidate):
                state.best = candidate.copy()
                iters_since_best = 0
                stagnation_counter = 0  # allow perturbation to fire again later
                op_score = 4.0

        destroy_tracker.record(d_op, op_score)
        repair_tracker.record(r_op, op_score)

        state.iterations += 1
        iters_since_best += 1

        # ── Phase 7: RoutePool + SP ───────────────────────────────────────────
        if route_pool is not None and progress >= STAGE_DIVERSIFY_END and is_complete:
            route_pool.add_solution(candidate, instance)
            if state.iterations % sp_call_freq == 0 and len(route_pool) >= 10:
                remaining = time_limit_sec - state.elapsed()
                sp_limit = min(SP_TIME_LIMIT_SEC, remaining * 0.25)
                if sp_limit > 1.0:
                    sp_sol = solve_set_partitioning(route_pool, instance, time_limit_sec=sp_limit)
                    if sp_sol is not None and state.is_better_than_best(sp_sol):
                        state.best = sp_sol.copy()
                        state.current = sp_sol.copy()
                        iters_since_best = 0

        # ── Phase 8: Fix-and-Optimize (Stage 3 only) ──────────────────────────
        if _fo_available and progress >= STAGE_BALANCE_END:
            stagnated = iters_since_best >= fo_no_improve_thresh
            periodic  = state.iterations % FO_CALL_FREQ_ITER == 0
            if (stagnated or periodic) and state.elapsed() < time_limit_sec:
                fo_sol = fix_and_optimize(
                    instance, state.get_best(), rng,
                    fix_ratio=FO_FIX_RATIO,
                    ls_max_moves=FO_LS_MAX_MOVES,
                )
                if state.is_better_than_best(fo_sol):
                    state.best = fo_sol.copy()
                    state.current = fo_sol.copy()
                    iters_since_best = 0


    # ── Post-ALNS: quick route elimination + intra-route polish ───────────────
    best = state.get_best()
    from solver.alns.local_search import (
        try_empty_one_route, force_eliminate_routes,
        intra_route_two_opt, intra_route_or_opt,
    )

    # Quick elimination (fast: 3 attempts × 3 trials)
    best = force_eliminate_routes(instance, best, rng, max_attempts=3, trials_per_route=3)
    changed = True
    while changed:
        changed = try_empty_one_route(instance, best)

    # Intra-route cost reduction
    changed = True
    while changed:
        c1 = intra_route_two_opt(instance, best)
        c2 = intra_route_or_opt(instance, best)
        changed = c1 or c2

    return AlnsResult(
        solution=best,
        iterations=state.iterations,
        elapsed_sec=state.elapsed(),
    )
