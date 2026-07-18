import logging
from arova.core.events import RuntimeEventBus
from arova.core.environment.attention import AttentionState

logger = logging.getLogger(__name__)

class AmbientIntentDetector:
    """
    Fuses semantic window data and attention state to predict the user's high-level goal.
    Emits intent events to the Cognition Runtime.
    """
    def __init__(self, workspace_engine, attention_engine, session_manager, event_bus: RuntimeEventBus):
        self.workspace_engine = workspace_engine
        self.attention_engine = attention_engine
        self.session_manager = session_manager
        self.event_bus = event_bus
        
        self.workspace_engine.add_listener(self._on_semantic_event)
        self.attention_engine.add_listener(self._on_attention_event)
        
        self.current_attention = None

    async def _on_attention_event(self, event):
        from arova.core.environment.events import EnvironmentalEvent
        if not isinstance(event, EnvironmentalEvent):
            return
            
        self.current_attention = event.payload
        
        # Route EnvironmentalEvent to the EventBus directly, but we might want to unwrap payload for existing UI
        # Or just pass the entire EnvironmentalEvent. The user said: "The runtime should interpret BEFORE surfacing"
        # So we pass the event.payload (which has probable_mode etc) to the UI, or just pass the semantic event.
        # Actually, let's just pass the payload for now to match UI expectations, or pass the full semantic mode.
        self.event_bus.emit("environment", "ATTENTION_STATE_CHANGED", event.payload)

    async def _on_semantic_event(self, event):
        from arova.core.environment.events import EnvironmentalEvent
        if not isinstance(event, EnvironmentalEvent) or event.semantic_type != "WORKSPACE_SEMANTICS_CHANGED":
            return
            
        role = event.payload.get("role", "idle") if isinstance(event.payload, dict) else "idle"
        
        # Predict intent based on role
        intent_msg = ""
        if role == "research_assisted_development":
            intent_msg = "Observing research-assisted development workflow."
        elif role == "development":
            intent_msg = "Observing development session."
        elif role == "knowledge_synthesis":
            intent_msg = "Observing knowledge synthesis."
            
        if intent_msg:
            # We emit an ambient narrative event so the UI Narrative Feed can proactively display it
            self.event_bus.emit("environment", "AMBIENT_INTENT_DETECTED", {"intent": intent_msg, "role": role})
