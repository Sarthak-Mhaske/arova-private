from enum import Enum

class CognitiveProfile(Enum):
    """
    User cognition policy governing routing, cloud usage, memory depth, and reasoning budgets.
    """
    MINIMAL = "minimal"              # Strictly local, minimal resource usage.
    BALANCED = "balanced"            # Mix of local and cloud based on budget.
    DEEP_WORK = "deep_work"          # Suppresses interruptions, routes complex tasks to cloud, prioritizes flow.
    OFFLINE_FIRST = "offline_first"  # Emphasizes local inference (Ollama), only using cloud if local fails or is insufficient.
    PRIVATE = "private"              # Never uses cloud APIs. Strict data containment.
    POWER_USER = "power_user"        # Max budget, max cloud usage, highest latency tolerance for deepest reasoning.
