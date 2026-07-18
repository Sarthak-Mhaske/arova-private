import logging
from typing import Dict, Any, List
from arova.core.projection.schema import RuntimeProjection, VisibleThread, StreamItem

logger = logging.getLogger(__name__)

class RuntimeProjector:
    """
    Translates deep cognition graphs and persistence models into a clean 
    RuntimeProjection for the UI.
    Shields the frontend from internal fatigue vectors, raw intent probabilities, and architectural routing.
    """
    def __init__(self, session_manager, thread_manager, environment_graph):
        self.session_manager = session_manager
        self.thread_manager = thread_manager
        self.environment_graph = environment_graph
        
    def project(self, orb_override: Dict[str, Any] = None) -> RuntimeProjection:
        projection = RuntimeProjection()
        
        # 1. Orb State
        # If not overridden, derive from current session activity
        if orb_override:
            projection.orb_state = orb_override
        else:
            if self.session_manager._active_turn:
                if self.session_manager._active_turn.assistant_response:
                    projection.orb_state = {"state": "speaking", "intensity": 0.8}
                else:
                    projection.orb_state = {"state": "listening", "intensity": 0.5}
            else:
                projection.orb_state = {"state": "idle", "intensity": 0.1}
                
        # 2. Visible Threads
        # Surface threads that are actively foreground or ambiently relevant, 
        # masking latent/archived threads entirely UNLESS they are pinned.
        for thread in self.thread_manager.get_all_threads():
            if thread.state in ("foreground", "ambient") or thread.pinned:
                projection.visible_threads.append(
                    VisibleThread(
                        thread_id=thread.thread_id,
                        title=thread.title,
                        state=thread.state,
                        pinned=thread.pinned,
                        last_active=thread.last_updated,
                        continuity_resonance=thread.continuity_resonance or 87.0, # default placeholder if 0
                        workspace_match="VSCode + Terminal" # placeholder for now until ambient graph is full
                    )
                )
                
        # 3. Stream Items
        # Translate the legacy messages / warm context into a clean visible stream
        # This prevents the frontend from needing to parse ConversationTurn semantics
        for msg in self.session_manager._legacy_messages[-15:]:
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
        # Extract environment signals from AmbientObserver if available
        # Default placeholders for UI to consume
        projection.room_state = {
            "mode": "Implementation",
            "workspace": ["VSCode", "Terminal", "Firefox"],
            "focus_duration_minutes": 43,
            "attention": "Deep Work",
            "ambient_signals": len(projection.ambient_fragments)
        }

        # 5. Context State
        active_thread = next((t for t in self.thread_manager.get_all_threads() if t.state == "foreground"), None)
        projection.context_state = {
            "active_thread": active_thread.title if active_thread else "None",
            "current_intent": "Frontend Completion Sprint", # Placeholder
            "room": projection.room_state["mode"]
        }
        
        # 6. Runtime State
        projection.runtime_state = {
            "agents": [], # Empty state for Phase 8
            "plans": []   # Empty state for Phase 8
        }
        
        return projection
