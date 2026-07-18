import time
from dataclasses import dataclass, field
from typing import List

@dataclass
class SessionContext:
    session_type: str # e.g. "development", "research_synthesis"
    started_at: float = field(default_factory=time.time)
    stability_score: float = 1.0
    semantic_threads: List[str] = field(default_factory=list)

class SessionManager:
    """
    Models temporal session boundaries (e.g. "debugging for 2 hours").
    Prevents cognition from feeling stateless.
    """
    def __init__(self, workspace_engine):
        self.workspace_engine = workspace_engine
        self.current_session: SessionContext = SessionContext(session_type="idle")
        
        # We listen to semantic events from the workspace engine
        self.workspace_engine.add_listener(self._on_semantic_event)
        
    async def _on_semantic_event(self, event):
        from arova.core.environment.events import EnvironmentalEvent
        if isinstance(event, EnvironmentalEvent):
            if event.semantic_type == "WORKSPACE_SEMANTICS_CHANGED":
                new_role = event.payload.get("role", "idle") if isinstance(event.payload, dict) else "idle"
                
                # If role persists over time, it establishes a session
                if new_role != self.current_session.session_type and new_role != "idle":
                    # We could apply strict temporal thresholds here before declaring a new session.
                    # For this MVP, we instantly switch session contexts if semantic intent shifts radically.
                    self.current_session = SessionContext(
                        session_type=new_role,
                        started_at=time.time(),
                        stability_score=event.confidence
                    )
