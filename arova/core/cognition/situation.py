import time
from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class CognitiveSituation:
    """
    A unified cognitive packet representing the complete state of the user's
    environment and request at an exact point in time.
    """
    prompt: str
    
    room: str
    workspace: List[str]
    attention_state: str
    
    active_thread_id: Optional[str]
    continuity_pressure: float
    
    attachments: List[dict] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)
