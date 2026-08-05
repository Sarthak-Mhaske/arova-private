from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional
import time
import uuid

RUNTIME_SCHEMA_VERSION = 4

@dataclass
class CrashRecoveryCheckpoint:
    """Stores the exact state of an interrupted stream or thought to allow graceful recovery."""
    interrupted_stream: str = ""
    active_thread_id: Optional[str] = None
    orb_state: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    recovered: bool = False

@dataclass
class CompletedWork:
    """Represents a unit of work finished or attempted by Arova with empirical verification."""
    work_id: str = field(default_factory=lambda: f"work_{uuid.uuid4().hex[:8]}")
    workflow: str = "Fix" # "Fix" | "Investigate" | "Summarize"
    headline: str = ""
    status: str = "Completed" # "Completed" | "Pending Review" | "Failed Verification" | "Rejected"
    
    # Verification & Action Metadata
    verified: bool = True
    verification_proof: str = ""
    failure_reason: Optional[str] = None
    
    # Permission & Risk Governance
    confidence: float = 0.95
    reversibility: str = "high" # "high" (reversible) | "medium" | "low" (irreversible)
    blast_radius: str = "local" # "tiny" | "local" | "large"
    
    # Action payload for 1-click execution / review
    action_type: str = "apply_patch"
    payload: Dict[str, Any] = field(default_factory=dict)
    
    # Telemetry
    net_work_removed_minutes: float = 15.0
    timestamp: float = field(default_factory=time.time)

@dataclass
class HotRuntimeState:
    """The active, living cognitive state of the room."""
    active_workspace_id: Optional[str] = None
    workspaces: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    active_threads: List[Dict[str, Any]] = field(default_factory=list)
    active_intents: List[Dict[str, Any]] = field(default_factory=list)
    recent_turns: List[Dict[str, Any]] = field(default_factory=list)
    completed_work: List[Dict[str, Any]] = field(default_factory=list)
    current_room_state: Dict[str, Any] = field(default_factory=dict)
    modulation_state: Dict[str, Any] = field(default_factory=dict)
    continuity_pressure: float = 0.0

@dataclass
class ColdArchiveState:
    """The settled, compressed memory of the system."""
    archived_sessions: List[Dict[str, Any]] = field(default_factory=list)
    resolved_threads: List[Dict[str, Any]] = field(default_factory=list)
    semantic_memories: List[Dict[str, Any]] = field(default_factory=list)

@dataclass
class RuntimeSnapshot:
    """The canonical persistence structure."""
    schema_version: int = RUNTIME_SCHEMA_VERSION
    snapshot_id: str = field(default_factory=lambda: f"snap_{uuid.uuid4().hex[:12]}")
    hot_state: HotRuntimeState = field(default_factory=HotRuntimeState)
    cold_state: ColdArchiveState = field(default_factory=ColdArchiveState)
    recovery_checkpoint: Optional[CrashRecoveryCheckpoint] = None
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        import copy
        return {
            "schema_version": self.schema_version,
            "snapshot_id": self.snapshot_id,
            "hot_state": {
                "active_workspace_id": self.hot_state.active_workspace_id,
                "workspaces": copy.deepcopy(self.hot_state.workspaces),
                "active_threads": copy.deepcopy(self.hot_state.active_threads),
                "active_intents": copy.deepcopy(self.hot_state.active_intents),
                "recent_turns": copy.deepcopy(self.hot_state.recent_turns),
                "completed_work": copy.deepcopy(self.hot_state.completed_work),
                "current_room_state": copy.deepcopy(self.hot_state.current_room_state),
                "modulation_state": copy.deepcopy(self.hot_state.modulation_state),
                "continuity_pressure": self.hot_state.continuity_pressure,
            },
            "cold_state": {
                "archived_sessions": copy.deepcopy(self.cold_state.archived_sessions),
                "resolved_threads": copy.deepcopy(self.cold_state.resolved_threads),
                "semantic_memories": copy.deepcopy(self.cold_state.semantic_memories),
            },
            "recovery_checkpoint": copy.deepcopy(asdict(self.recovery_checkpoint)) if (self.recovery_checkpoint and hasattr(self.recovery_checkpoint, "__dataclass_fields__")) else None,
            "timestamp": self.timestamp
        }
        
    @classmethod
    def from_dict(cls, data: dict) -> 'RuntimeSnapshot':
        if data.get('schema_version', 1) < 4:
            raise ValueError(f"Legacy schema {data.get('schema_version')} not supported in strict v4 hydration.")
            
        hot_data = data.get('hot_state', {})
        cold_data = data.get('cold_state', {})
        recovery_data = data.get('recovery_checkpoint')
        
        hot = HotRuntimeState(**hot_data) if hot_data else HotRuntimeState()
        cold = ColdArchiveState(**cold_data) if cold_data else ColdArchiveState()
        
        recovery = None
        if recovery_data:
            recovery = CrashRecoveryCheckpoint(**recovery_data)
            
        return cls(
            schema_version=data.get('schema_version', RUNTIME_SCHEMA_VERSION),
            snapshot_id=data.get('snapshot_id', f"snap_{uuid.uuid4().hex[:12]}"),
            hot_state=hot,
            cold_state=cold,
            recovery_checkpoint=recovery,
            timestamp=data.get('timestamp', time.time())
        )
