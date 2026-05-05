"""
Solver config: time limit, seed, ALNS stage ratios, destroy size.
"""
from __future__ import annotations

# Time limit for ALNS (seconds). Construction runs first, then ALNS until time_limit.
TIME_LIMIT_SEC = 60.0

# Random seed for reproducibility.
SEED = 0

# ALNS stages (fractions of time_limit): diversify (0-30%), balance (30-70%), intensify (70-100%).
STAGE_DIVERSIFY_END = 0.30
STAGE_BALANCE_END = 0.70
# Stage 3 = intensify from 0.70 to 1.0

# Destroy size: number of requests to remove per iteration (or min/max for random draw).
# Can be a fraction of num_requests; solver will use at least 1, at most num_requests.
DESTROY_MIN_FRAC = 0.05
DESTROY_MAX_FRAC = 0.25

# Stage-specific destroy fractions (match README)
DESTROY_STAGE1_MIN_FRAC = 0.15
DESTROY_STAGE1_MAX_FRAC = 0.30
DESTROY_STAGE2_MIN_FRAC = 0.10
DESTROY_STAGE2_MAX_FRAC = 0.25
DESTROY_STAGE3_MIN_FRAC = 0.05
DESTROY_STAGE3_MAX_FRAC = 0.15

# Simulated annealing – dynamic, time-based schedule.
# T_initial = initial_solution_cost * SA_TEMP_FACTOR
# T(t)      = T_initial * exp(log(SA_TEMP_MIN_RATIO) * t/time_limit)
# → T goes from T_initial down to T_initial * SA_TEMP_MIN_RATIO over the run.
SA_TEMP_FACTOR    = 0.05    # P(accept +5% worse move) ≈ 0.5 at t=0
SA_TEMP_MIN_RATIO = 0.001   # T at end = 0.1% of T_initial

# Local search (Stage 2/3 intensification)
LS_STAGE2_MAX_MOVES = 20
LS_STAGE3_MAX_MOVES = 60
LS_ROUTE_SAMPLES = 8
LS_POS_TRIALS_PER_ROUTE = 24
LS_FIRST_IMPROVEMENT = True

# Destroy operator mix (probabilities per stage). Must sum to 1.0 per stage.
DESTROY_STAGE1_P_RANDOM = 0.60
DESTROY_STAGE1_P_SHAW = 0.25
DESTROY_STAGE1_P_WORST = 0.15

DESTROY_STAGE2_P_RANDOM = 0.25
DESTROY_STAGE2_P_SHAW = 0.45
DESTROY_STAGE2_P_WORST = 0.20
DESTROY_STAGE2_P_CLUSTER = 0.10

DESTROY_STAGE3_P_WORST = 0.55
DESTROY_STAGE3_P_ROUTE = 0.35
DESTROY_STAGE3_P_SHAW = 0.10

# Repair config
REPAIR_REGRET_K = 3
REPAIR_ROUTE_SAMPLES = 10
REPAIR_POS_TRIALS_PER_ROUTE = 28
REPAIR_EJECTION_MAX = 2
REPAIR_EJECTION_TRIES = 20

# Local search move probabilities (must sum to 1.0)
LS_P_RELOCATE = 0.50
LS_P_SWAP = 0.30
LS_P_OR_OPT = 0.20

# Adaptive penalty (Phase 6)
PENALTY_LAMBDA_INIT = 1.0
PENALTY_LAMBDA_TW_INIT = 0.5    # initial λ for TW violations
PENALTY_LAMBDA_CAP_INIT = 0.5   # initial λ for capacity violations
PENALTY_TARGET_FEASIBLE = 0.50
PENALTY_WINDOW_SIZE = 50
PENALTY_UPDATE_FREQ = 50
PENALTY_LAMBDA_MIN = 0.1
PENALTY_LAMBDA_MAX = 20.0
PENALTY_ADJUST_FACTOR = 1.2

# Set Partitioning (Phase 7)
SP_POOL_MAX_SIZE = 800          # max routes kept in RoutePool
SP_TIME_LIMIT_SEC = 10.0        # MILP time limit per SP call
SP_CALL_FREQ_ITER = 150         # call SP every N iterations (Stage 2+)

# Fix-and-Optimize (Phase 8)
FO_FIX_RATIO = 0.60             # fraction of routes to fix
FO_LS_MAX_MOVES = 40            # local-search budget after re-insertion
FO_CALL_FREQ_ITER = 300         # call F&O every N iterations (Stage 3 only)
FO_NO_IMPROVE_THRESHOLD = 150   # also trigger F&O if no improvement for N iters
