from dataclasses import dataclass, field
import time
from typing import Optional

@dataclass
class AmbientContext:
    """A snapshot of the ambient environment at a point in time."""
    timestamp: float = field(default_factory=time.time)
    
    # State tracking
    active_app: Optional[str] = None
    window_title: Optional[str] = None
    workspace: Optional[str] = None
    
    is_idle: bool = False
    idle_time_seconds: float = 0.0
    
    # Derived temporal state
    time_of_day: str = "unknown" # e.g. "morning", "afternoon", "night"
    
    def __eq__(self, other):
        if not isinstance(other, AmbientContext):
            return False
        # We ignore timestamp for equality checks
        return (
            self.active_app == other.active_app and
            self.window_title == other.window_title and
            self.workspace == other.workspace and
            self.is_idle == other.is_idle
        )
