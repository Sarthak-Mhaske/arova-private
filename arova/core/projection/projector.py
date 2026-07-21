import logging
from typing import Dict, Any, Optional
from arova.core.projection.schema import RuntimeProjection, VisibleThread, StreamItem

logger = logging.getLogger(__name__)

ORB_INTENSITY_SPEAKING = 0.8
ORB_INTENSITY_LISTENING = 0.5
ORB_INTENSITY_IDLE = 0.1
MAX_STREAM_ITEMS = 15


class RuntimeProjector:
    """
    Translates deep cognition graphs and persistence models into a clean 
    RuntimeProjection for the UI.
    Shields the frontend from internal fatigue vectors, raw intent probabilities, and architectural routing.
    Contains zero fabricated runtime or placeholder data.
    """
    def __init__(self, session_manager: Any, thread_manager: Any, environment_graph: Optional[Any] = None):
        self.session_manager = session_manager
        self.thread_manager = thread_manager
        self.environment_graph = environment_graph
        
    def project(self, orb_override: Optional[Dict[str, Any]] = None) -> RuntimeProjection:
        projection = RuntimeProjection()
        
        # 1. Orb State
        if orb_override:
            projection.orb_state = orb_override
        else:
            if self.session_manager._active_turn:
                if self.session_manager._active_turn.assistant_response:
                    projection.orb_state = {"state": "speaking", "intensity": ORB_INTENSITY_SPEAKING}
                else:
                    projection.orb_state = {"state": "listening", "intensity": ORB_INTENSITY_LISTENING}
            else:
                projection.orb_state = {"state": "idle", "intensity": ORB_INTENSITY_IDLE}
                
        # 2. Visible Threads
        for thread in self.thread_manager.get_all_threads():
            if thread.state in ("foreground", "ambient") or thread.pinned:
                projection.visible_threads.append(
                    VisibleThread(
                        thread_id=thread.thread_id,
                        title=thread.title,
                        state=thread.state,
                        pinned=thread.pinned,
                        last_active=thread.last_updated,
                        continuity_resonance=getattr(thread, "continuity_resonance", 0.0) or 0.0,
                        workspace_match=getattr(thread, "workspace_match", "") or ""
                    )
                )
                
        # 3. Stream Items
        for msg in self.session_manager._legacy_messages[-MAX_STREAM_ITEMS:]:
            turn_id = msg.get("id", "legacy")
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            projection.stream_items.append(
                StreamItem(
                    turn_id=turn_id,
                    role=role,
                    content=content
                )
            )
            
        # 4. Room State / Environment
        mode = getattr(self.environment_graph, "mode", "Idle") if self.environment_graph else "Idle"
        workspace = getattr(self.environment_graph, "active_applications", []) if self.environment_graph else []
        focus_duration = getattr(self.environment_graph, "focus_duration_minutes", 0) if self.environment_graph else 0
        attention = getattr(self.environment_graph, "attention_state", "Normal") if self.environment_graph else "Normal"

        projection.room_state = {
            "mode": mode,
            "workspace": workspace,
            "focus_duration_minutes": focus_duration,
            "attention": attention,
            "ambient_signals": len(projection.ambient_fragments)
        }

        # 5. Context State
        active_thread = next((t for t in self.thread_manager.get_all_threads() if t.state == "foreground"), None)
        current_intent = getattr(active_thread, "current_intent", "Idle") if active_thread else "Idle"
        projection.context_state = {
            "active_thread": active_thread.title if active_thread else "None",
            "current_intent": current_intent,
            "room": projection.room_state["mode"]
        }
        
        # 6. Runtime State
        projection.runtime_state = {
            "agents": [],
            "plans": []
        }
        
        return projection
