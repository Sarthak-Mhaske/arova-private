from enum import Enum, auto
from typing import Optional, Dict, Any
from dataclasses import dataclass
from arova.core.events import RuntimeEventBus
from arova.core.time import RuntimeClock
import logging

class VoiceStateGroup(Enum):
    PASSIVE = auto()
    ACTIVE = auto()
    INTERRUPTED = auto()
    RECOVERY = auto()

class VoiceState(Enum):
    IDLE = (VoiceStateGroup.PASSIVE, "idle")
    WAKE_MONITORING = (VoiceStateGroup.PASSIVE, "wake_monitoring")
    LISTENING = (VoiceStateGroup.ACTIVE, "listening")
    THINKING = (VoiceStateGroup.ACTIVE, "thinking")
    SPEAKING = (VoiceStateGroup.ACTIVE, "speaking")
    EXECUTING = (VoiceStateGroup.ACTIVE, "executing")
    INTERRUPTING = (VoiceStateGroup.INTERRUPTED, "interrupting")
    CANCELLING = (VoiceStateGroup.INTERRUPTED, "cancelling")
    STT_FAILURE = (VoiceStateGroup.RECOVERY, "stt_failure")
    TTS_FAILURE = (VoiceStateGroup.RECOVERY, "tts_failure")
    AUDIO_DEVICE_LOST = (VoiceStateGroup.RECOVERY, "audio_device_lost")

    def __init__(self, group: VoiceStateGroup, string_val: str):
        self.group = group
        self.string_val = string_val

class VoiceRuntime:
    """
    Coordinates the conversational state machine as a State Observer.
    Transitions ONLY on hard facts, not optimistic guessing.
    Transitions to IDLE only when true Quiescence is earned.
    """
    
    def __init__(self, event_bus: RuntimeEventBus):
        self._event_bus = event_bus
        self._current_state = VoiceState.IDLE
        
        # Quiescence counters
        self._active_execution = 0
        self._active_playback = 0
        self._active_stt = 0
        
        # Subscribe to lower-level events
        self._event_bus.subscribe("voice", "WAKE_DETECTED", self._on_wake_detected)
        self._event_bus.subscribe("voice", "ACTIVITY_CHANGED", self._on_activity_changed)
        self._event_bus.subscribe("voice", "AUDIO_BACKEND_LOST", self._on_backend_lost)
        
        # Subscribe to state facts
        self._event_bus.subscribe("state", "EXECUTION_STATE_CHANGED", self._on_execution_state)
        self._event_bus.subscribe("voice", "TTS_STARTED", self._on_tts_started)
        self._event_bus.subscribe("voice", "TTS_COMPLETED", self._on_tts_completed)
        self._event_bus.subscribe("voice", "TTS_INTERRUPTED", self._on_tts_completed)
        
        # System-wide interrupt
        self._event_bus.subscribe("runtime", "INTERRUPT_REQUESTED", self._on_interrupt_requested)

    def _transition_to(self, new_state: VoiceState):
        if self._current_state == new_state:
            return
            
        old_state = self._current_state
        self._current_state = new_state
        logging.info(f"VoiceRuntime state transition: {old_state.string_val} -> {new_state.string_val}")
        
        # Emit a generic state change for UI projection
        self._event_bus.emit("state", "STATE_CHANGED", {"state": new_state.string_val})
        
    def _check_quiescence(self):
        """Earned IDLE: Only transitions to IDLE if no active systems remain."""
        if self._active_execution <= 0 and self._active_playback <= 0 and self._active_stt <= 0:
            if self._current_state not in (VoiceState.IDLE, VoiceState.WAKE_MONITORING):
                logging.info("Runtime Quiescence reached. Transitioning to IDLE.")
                self._transition_to(VoiceState.IDLE)
        else:
            logging.debug(f"Quiescence check failed: exec={self._active_execution}, "
                          f"play={self._active_playback}, stt={self._active_stt}")

    def _on_wake_detected(self, payload):
        if self._current_state.group == VoiceStateGroup.ACTIVE:
            self._event_bus.emit("runtime", "INTERRUPT_REQUESTED", {"source": "wake_word"})
            
        self._transition_to(VoiceState.LISTENING)
        self._active_stt += 1

    def _on_activity_changed(self, payload):
        # We handle this via TurnCoordinator now (Step 3), so we can just let it be for now.
        pass
        
    def _on_execution_state(self, payload):
        state_val = getattr(payload, "state", "")
        if state_val in ("THINKING", "PLANNING", "EXECUTING", "RESPONDING"):
            self._active_execution = 1
            if state_val == "THINKING":
                self._transition_to(VoiceState.THINKING)
            elif state_val == "EXECUTING":
                self._transition_to(VoiceState.EXECUTING)
        elif state_val in ("COMPLETED", "FAILED", "CANCELLED"):
            self._active_execution = 0
            self._check_quiescence()

    def _on_tts_started(self, payload):
        self._active_playback += 1
        self._transition_to(VoiceState.SPEAKING)
        
    def _on_tts_completed(self, payload):
        self._active_playback = max(0, self._active_playback - 1)
        self._check_quiescence()

    def _on_interrupt_requested(self, payload):
        self._transition_to(VoiceState.INTERRUPTING)
        # Note: We do NOT force transition to IDLE here.
        # The cascade cancellation will emit TTS_INTERRUPTED and EXECUTION_CANCELLED,
        # which decrement the counters and naturally trigger quiescence.
        
    def _on_backend_lost(self, payload):
        self._transition_to(VoiceState.AUDIO_DEVICE_LOST)
        logging.error("VoiceRuntime entered AUDIO_DEVICE_LOST recovery state.")
        self._event_bus.emit("runtime", "RECOVERY_REQUIRED", {"reason": "AUDIO_DEVICE_LOST"})
        
    def get_health_snapshot(self) -> Dict[str, Any]:
        return {
            "current_state": self._current_state.string_val,
            "active_execution": self._active_execution,
            "active_playback": self._active_playback,
            "active_stt": self._active_stt,
            "quiescent": (self._active_execution == 0 and self._active_playback == 0 and self._active_stt == 0)
        }
