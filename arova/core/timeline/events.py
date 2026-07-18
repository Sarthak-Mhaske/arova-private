import time
from dataclasses import dataclass, field
from typing import Optional, Dict, Any

@dataclass
class TimelineEvent:
    id: str
    category: str  # environment, cognition, memory, routing, runtime, state_transition, attention, continuity
    title: str
    description: str
    source: str
    importance: float  # 0.0 to 1.0
    correlation_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

# Common Categories
CATEGORY_ENVIRONMENT = "environment"
CATEGORY_COGNITION = "cognition"
CATEGORY_MEMORY = "memory"
CATEGORY_ROUTING = "routing"
CATEGORY_RUNTIME = "runtime"
CATEGORY_STATE_TRANSITION = "state_transition"
CATEGORY_ATTENTION = "attention"
CATEGORY_CONTINUITY = "continuity"

# Common Sources
SOURCE_MEMORY_RUNTIME = "memory_runtime"
SOURCE_AMBIENT_OBSERVER = "ambient_observer"
SOURCE_CAPABILITY_ROUTER = "capability_router"
SOURCE_ACTION_ROUTER = "action_router"
SOURCE_THREAD_MANAGER = "thread_manager"
SOURCE_RUNTIME_STORE = "runtime_store"
SOURCE_PROVIDER_MANAGER = "provider_manager"
