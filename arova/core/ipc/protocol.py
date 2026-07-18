import json
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional
import time

@dataclass
class IpcFrame:
    """Base frame for all IPC communications over the Unix socket."""
    type: str # "handshake", "command", "response", "stream"
    payload: Dict[str, Any]
    message_id: str
    timestamp: float = field(default_factory=time.time)

    def serialize(self) -> bytes:
        return (json.dumps(asdict(self)) + "\n").encode("utf-8")

    @classmethod
    def deserialize(cls, data: bytes) -> 'IpcFrame':
        raw = json.loads(data.decode("utf-8"))
        return cls(**raw)

@dataclass
class HandshakeRequest:
    protocol_version: str = "1.0"
    client_id: str = ""
    capabilities: List[str] = field(default_factory=list)

@dataclass
class HandshakeResponse:
    accepted: bool
    runtime_version: str
    session_token: str
    error: Optional[str] = None
    
@dataclass
class IpcCommand:
    method: str
    args: Dict[str, Any] = field(default_factory=dict)
    
@dataclass
class IpcResponse:
    ok: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
