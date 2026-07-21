"""
Cognitive Substrate Tuning Constants (P0-8)

Centralizes numeric tuning parameters, thresholds, and weights used across:
- priority.py (surfacing & cognitive pressure)
- modulation.py (interruption sensitivity & ambient density)
- memory_retrieval.py (reinforcement & decay scoring)
- workspace_manager.py (stuckness analysis & behavioral recovery metrics)
"""

# ==========================================
# Priority Layer (priority.py)
# ==========================================
PRESSURE_COMPOUND_RATE = 0.2
NOVELTY_DECAY_RATE = 0.8
PRESSURE_DISSIPATION_RATE = 0.2
MIN_COGNITIVE_PRESSURE_THRESHOLD = 0.05

FOREGROUND_SURFACING_THRESHOLD = 0.5
BACKGROUND_SURFACING_THRESHOLD = 0.3

# ==========================================
# Modulation Layer (modulation.py)
# ==========================================
DEFAULT_INTERRUPTION_SENSITIVITY = 0.5
DEFAULT_AMBIENT_DENSITY = 0.5
LOW_AMBIENT_DENSITY = 0.2
HIGH_AMBIENT_DENSITY = 0.8

# ==========================================
# Memory Retrieval Layer (memory_retrieval.py)
# ==========================================
CONFIDENCE_SCORE_WEIGHT = 0.5
MAX_DECAY_PENALTY = 0.5
MAX_REINFORCEMENT_BONUS = 0.3
REINFORCEMENT_BONUS_RATE = 0.05
MIN_RETRIEVAL_SCORE_THRESHOLD = 0.3
SECONDS_PER_DAY = 86400.0

# ==========================================
# Workspace Manager & Stuckness (workspace_manager.py)
# ==========================================
MIN_BEHAVIORAL_RECOVERY_SECONDS = 120.0
SECONDS_PER_RESOURCE_REOPEN = 150.0
SECONDS_PER_SWITCH_AVOIDED = 35.0

STUCKNESS_ERROR_PENALTY = 35.0
STUCKNESS_REPEAT_VISIT_RATE = 20.0
STUCKNESS_MAX_REPEAT_PENALTY = 50.0
STUCKNESS_STAGNANT_FOCUS_PENALTY = 25.0
STUCKNESS_STAGNANT_TIME_THRESHOLD_SECONDS = 1800.0
