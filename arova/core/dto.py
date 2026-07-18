from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional
import time

@dataclass(kw_only=True)
class BaseDTO:
    """Base class for all JSON-serializable Data Transfer Objects."""
    schema_version: str = "1.0"
    timestamp: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

# --- Runtime States ---

@dataclass(kw_only=True)
class VoiceStateDTO(BaseDTO):
    state: str # e.g., "idle", "listening", "thinking", "speaking", "executing", "audio_device_lost"
    turn_id: Optional[str] = None
    message: Optional[str] = None

@dataclass(kw_only=True)
class ExecutionStateDTO(BaseDTO):
    state: str # "THINKING", "PLANNING", "EXECUTING", "RESPONDING", "COMPLETED", "FAILED", "CANCELLED"
    turn_id: Optional[str] = None
    plan_id: Optional[str] = None

@dataclass(kw_only=True)
class RuntimeHealthDTO(BaseDTO):
    current_voice_state: str
    authoritative_turn_id: Optional[str]
    active_execution: int
    active_playback: int
    active_stt: int
    quiescent: bool

# --- Conversational Turn & Memory ---

@dataclass(kw_only=True)
class ConversationTurnDTO(BaseDTO):
    turn_id: str
    user_transcript: str
    assistant_response: str
    intent_type: Optional[str] = None
    associated_plan_id: Optional[str] = None
    interrupted: bool = False
    timestamp_start: float = 0.0
    timestamp_end: float = 0.0

@dataclass(kw_only=True)
class ConversationSnapshotDTO(BaseDTO):
    """Initial boot snapshot of the conversation state."""
    active_turn: Optional[ConversationTurnDTO]
    warm_context: List[ConversationTurnDTO]
    legacy_history: List[Dict[str, Any]] # For smooth UI migration

# --- Execution & Plans ---

@dataclass(kw_only=True)
class PlanStepDTO(BaseDTO):
    step_id: str
    description: str
    status: str # "pending", "running", "completed", "failed", "cancelled"
    message: Optional[str] = None

@dataclass(kw_only=True)
class PlanDTO(BaseDTO):
    plan_id: str
    goal: str
    status: str
    steps: List[PlanStepDTO]
    
@dataclass(kw_only=True)
class ToolExecutionDTO(BaseDTO):
    tool_name: str
    status: str # "started", "completed", "failed"
    result_message: Optional[str] = None
    turn_id: Optional[str] = None

# --- Events / Transport ---

@dataclass(kw_only=True)
class FacadeEventDTO(BaseDTO):
    """Wrapper for streaming events over the Facade API."""
    event_type: str # e.g., "VOICE_STATE_CHANGED", "TURN_UPDATED", "PLAN_UPDATED"
    payload: Dict[str, Any] # Sub-DTO serialized into dict
