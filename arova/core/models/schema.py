from enum import Enum
from dataclasses import dataclass, field

class ReasoningDepth(str, Enum):
    FAST = "fast"         # Simple heuristics/regex, bypasses deep LLM call
    STANDARD = "standard" # Basic LLM classification & action planning
    DEEP = "deep"         # Memory retrieval, contextual synthesis, graph building
    REFLECTIVE = "reflective" # Post-execution evaluation, error correction

class CognitiveState(str, Enum):
    OBSERVING = "observing"
    RETRIEVING = "retrieving"
    SYNTHESIZING = "synthesizing"
    PLANNING = "planning"
    VALIDATING = "validating"
    EXECUTING = "executing"
    REFLECTING = "reflecting"

@dataclass
class ReasoningBudget:
    """Governs the max cost/latency allowed for a cognitive task."""
    max_tokens: int = 1000
    max_retrieval_ms: float = 200.0
    max_planning_depth: int = 1
    allow_reflection: bool = False
    
@dataclass
class ModelCapabilityProfile:
    """Defines what an underlying LLM is approved to do."""
    model_name: str
    supports_fast_reasoning: bool = True
    supports_deep_planning: bool = False
    supports_reflection: bool = False
    context_window: int = 8192
