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

# Simulated annealing: initial temperature, cooling rate (temperature *= cooling per iteration).
SA_INITIAL_TEMPERATURE = 1e4
SA_COOLING = 0.9995

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
