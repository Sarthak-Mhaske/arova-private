"""
Cognitive Substrate Tuning Constants (P0-8)

Centralizes numeric tuning parameters, thresholds, and weights used across:
- priority.py (surfacing & cognitive pressure)
- modulation.py (interruption sensitivity & ambient density)
- memory_retrieval.py (reinforcement & decay scoring)
- workspace_manager.py (stuckness analysis & behavioral recovery metrics)
"""

try:
    from arova.core.config.loader import load_config
    _cfg = load_config()
except Exception:
    _cfg = {}

_stuck = _cfg.get("stuckness", {})
_prio = _cfg.get("priority", {})
_mod = _cfg.get("modulation", {})
_mem = _cfg.get("memory", {})

# ==========================================
# Priority Layer (priority.py)
# ==========================================
PRESSURE_COMPOUND_RATE = _prio.get("compound_rate", 0.2)
NOVELTY_DECAY_RATE = _prio.get("novelty_decay_rate", 0.8)
PRESSURE_DISSIPATION_RATE = _prio.get("dissipation_rate", 0.2)
MIN_COGNITIVE_PRESSURE_THRESHOLD = _prio.get("min_pressure_threshold", 0.05)

FOREGROUND_SURFACING_THRESHOLD = _prio.get("foreground_surfacing_threshold", 0.5)
BACKGROUND_SURFACING_THRESHOLD = _prio.get("background_surfacing_threshold", 0.3)

# ==========================================
# Modulation Layer (modulation.py)
# ==========================================
DEFAULT_INTERRUPTION_SENSITIVITY = _mod.get("default_interruption_sensitivity", 0.5)
DEFAULT_AMBIENT_DENSITY = _mod.get("default_ambient_density", 0.5)
LOW_AMBIENT_DENSITY = _mod.get("low_ambient_density", 0.2)
HIGH_AMBIENT_DENSITY = _mod.get("high_ambient_density", 0.8)

# ==========================================
# Memory Retrieval Layer (memory_retrieval.py)
# ==========================================
CONFIDENCE_SCORE_WEIGHT = _mem.get("confidence_score_weight", 0.5)
MAX_DECAY_PENALTY = _mem.get("max_decay_penalty", 0.5)
MAX_REINFORCEMENT_BONUS = _mem.get("max_reinforcement_bonus", 0.3)
REINFORCEMENT_BONUS_RATE = _mem.get("reinforcement_bonus_rate", 0.05)
MIN_RETRIEVAL_SCORE_THRESHOLD = _mem.get("min_retrieval_score_threshold", 0.3)
SECONDS_PER_DAY = 86400.0

# ==========================================
# Workspace Manager & Stuckness (workspace_manager.py)
# ==========================================
MIN_BEHAVIORAL_RECOVERY_SECONDS = _stuck.get("min_behavioral_recovery_seconds", 120.0)
SECONDS_PER_RESOURCE_REOPEN = _stuck.get("seconds_per_resource_reopen", 150.0)
SECONDS_PER_SWITCH_AVOIDED = _stuck.get("seconds_per_switch_avoided", 35.0)

STUCKNESS_ERROR_PENALTY = _stuck.get("error_penalty", 35.0)
STUCKNESS_REPEAT_VISIT_RATE = _stuck.get("repeat_visit_rate", 20.0)
STUCKNESS_MAX_REPEAT_PENALTY = _stuck.get("max_repeat_penalty", 50.0)
STUCKNESS_STAGNANT_FOCUS_PENALTY = _stuck.get("stagnant_focus_penalty", 25.0)
STUCKNESS_STAGNANT_TIME_THRESHOLD_SECONDS = _stuck.get("stagnant_time_threshold_seconds", 1800.0)

