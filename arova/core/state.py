import threading
from typing import Dict, Any, List, Optional
from arova.core.events import RuntimeEventBus
from arova.core.dto import (
    VoiceStateDTO, 
    ExecutionStateDTO, 
    RuntimeHealthDTO, 
    ConversationTurnDTO,
    ConversationSnapshotDTO
)

class RuntimeProjectionCache:
    """
    Read-only projection cache built entirely from RuntimeEventBus streams.
    Replaces the legacy AssistantStateStore.
    Provides snapshot booting for clients.
    """
    def __init__(self, event_bus: RuntimeEventBus):
        self._event_bus = event_bus
        self._lock = threading.RLock()
        
        # Current projections
        self._voice_state = "idle"
        self._execution_state = "COMPLETED"
        self._authoritative_turn_id: Optional[str] = None
        self._turns: Dict[str, ConversationTurnDTO] = {}
        self._legacy_history: List[Dict[str, Any]] = [] # Temporary compatibility
        
        # Subscribe to runtime facts
        self._event_bus.subscribe("state", "STATE_CHANGED", self._on_voice_state)
        self._event_bus.subscribe("state", "EXECUTION_STATE_CHANGED", self._on_execution_state)
        
        # Conversation Turn Events (To be added to ConversationSession / IntentRuntime later)
        # We simulate updates via legacy events for now until we fully emit Turn events
        self._event_bus.subscribe("voice", "TRANSCRIPT_FINAL", self._on_transcript)
        self._event_bus.subscribe("voice", "TEXT_RESPONSE_GENERATED", self._on_response)
        
    def _on_voice_state(self, payload):
        with self._lock:
            self._voice_state = getattr(payload, "state", "idle")
            
    def _on_execution_state(self, payload):
        with self._lock:
            self._execution_state = getattr(payload, "state", "COMPLETED")
            
    def _on_transcript(self, payload):
        with self._lock:
            turn_id = getattr(payload, "turn_id", "unknown_turn")
            text = getattr(payload, "text", "")
            
            if turn_id not in self._turns:
                self._turns[turn_id] = ConversationTurnDTO(
                    turn_id=turn_id,
                    user_transcript=text,
                    assistant_response=""
                )
            else:
                self._turns[turn_id].user_transcript = text
                
            # Legacy sync
            self._legacy_history.append({"role": "user", "content": text})
                
    def _on_response(self, payload):
        with self._lock:
            turn_id = getattr(payload, "turn_id", "unknown_turn")
            text = getattr(payload, "text", "")
            
            if turn_id in self._turns:
                self._turns[turn_id].assistant_response = text
            else:
                self._turns[turn_id] = ConversationTurnDTO(
                    turn_id=turn_id,
                    user_transcript="",
                    assistant_response=text
                )
                
            # Legacy sync
            self._legacy_history.append({"role": "assistant", "content": text})

    def get_conversation_snapshot(self) -> ConversationSnapshotDTO:
        with self._lock:
            turns = list(self._turns.values())
            active_turn = turns[-1] if turns else None
            return ConversationSnapshotDTO(
                active_turn=active_turn,
                warm_context=turns[-10:] if len(turns) > 10 else turns,
                legacy_history=self._legacy_history[-20:]
            )
            
    def get_voice_snapshot(self) -> VoiceStateDTO:
        with self._lock:
            return VoiceStateDTO(
                state=self._voice_state,
                turn_id=self._authoritative_turn_id
            )
            
    def get_execution_snapshot(self) -> ExecutionStateDTO:
        with self._lock:
            return ExecutionStateDTO(
                state=self._execution_state,
                turn_id=self._authoritative_turn_id
            )
