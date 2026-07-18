from dataclasses import dataclass, field
from typing import Dict, Any
import time

@dataclass
class EnvironmentalEvent:
    source: str           # e.g., "x11_observer", "hyprland_ipc", "audio_activity"
    semantic_type: str    # e.g., "ATTENTION_FRAGMENTED", "DEEP_WORK_ENTERED", "APP_SWITCHED"
    confidence: float     # 0.0 to 1.0
    payload: Dict[str, Any]
    timestamp: float = field(default_factory=time.time)
