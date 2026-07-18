from dataclasses import dataclass, field
from typing import Any, Dict, Optional
import time

@dataclass
class EventEnvelope:
    """
    Versioned event schema for cross-boundary IPC and core messaging.
    """
    schema_version: str
    event_type: str
    timestamp: float = field(default_factory=time.time)
    payload: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "event_type": self.event_type,
            "timestamp": self.timestamp,
            "payload": self.payload
        }
        
    @classmethod
    def from_dict(cls, data: dict) -> 'EventEnvelope':
        return cls(
            schema_version=data.get("schema_version", "1.0"),
            event_type=data.get("event_type", "UNKNOWN"),
            timestamp=data.get("timestamp", time.time()),
            payload=data.get("payload", {})
        )
