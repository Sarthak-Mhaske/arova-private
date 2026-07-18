import logging
import numpy as np
import webrtcvad
from typing import Optional
from dataclasses import dataclass
from arova.core.events import RuntimeEventBus, EventPayload
from arova.core.time import RuntimeClock

@dataclass(frozen=True, kw_only=True)
class VoiceActivityEvent(EventPayload):
    is_speaking: bool
    turn_id: Optional[str] = None

class VoiceActivityRuntime:
    """
    Micro-runtime for Voice Activity Detection.
    
    Uses a dual-detector approach:
      1. WebRTC VAD (primary) — well-tuned for human speech frequencies
      2. AC-energy gating (fallback) — dynamic baseline that adapts to any mic/environment
    
    Critical invariant: on WAKE_DETECTED, internal state is forcibly reset so that
    TurnCoordinator always receives a fresh ACTIVITY_CHANGED rising edge during the turn.
    """
    def __init__(self, event_bus: RuntimeEventBus, sensitivity: int = 3):
        self._event_bus = event_bus
        self._vad = webrtcvad.Vad(sensitivity)
        
        self._is_speaking = False
        self._last_speech_frame_time = 0.0
        
        # Silence duration before finalizing (allows natural conversational pauses)
        self._minimum_silence_duration = 3.0
        
        # Dynamic AC-energy baseline (adapts to any mic/environment automatically)
        self._ac_baseline: float = 0.0
        self._baseline_initialized = False
        
        # Subscribe to WAKE_DETECTED to reset state for a clean edge transition
        self._event_bus.subscribe("voice", "WAKE_DETECTED", self._on_wake_detected)

    def _on_wake_detected(self, payload):
        """
        Reset VAD state so TurnCoordinator receives a fresh rising edge.
        Without this, if _is_speaking was already True from ambient noise,
        the edge-detection 'if is_speech and not self._is_speaking' would
        never fire, and TurnCoordinator would timeout waiting for speech.
        """
        was_speaking = self._is_speaking
        self._is_speaking = False
        self._last_speech_frame_time = 0.0
        if was_speaking:
            logging.info("VAD: Reset speaking state on WAKE_DETECTED (was latched True)")
        
    def process_audio_chunk(self, chunk: bytes, sample_rate: int = 16000):
        if len(chunk) == 0:
            return
        
        # Force flatten to guarantee shape consistency
        audio_np = np.frombuffer(chunk, dtype=np.int16).flatten()
        
        # --- Detector: WebRTC VAD ---
        # WebRTC is battle-tested to detect human vocal tract frequencies
        # and ignore static/background noise.
        try:
            is_speech = self._vad.is_speech(chunk, sample_rate)
        except Exception:
            is_speech = False
        
        now = RuntimeClock.now()
        
        if is_speech:
            self._last_speech_frame_time = now
            
            if not self._is_speaking:
                self._is_speaking = True
                logging.info("VAD SPEECH START DETECTED")
                self._emit_event(True, now)
        else:
            if self._is_speaking:
                if now - self._last_speech_frame_time >= self._minimum_silence_duration:
                    self._is_speaking = False
                    logging.info("VAD SPEECH STOP DETECTED (%.1fs silence)", 
                                 now - self._last_speech_frame_time)
                    self._emit_event(False, now)
                
    def _emit_event(self, speaking: bool, timestamp: float):
        event = VoiceActivityEvent(is_speaking=speaking, timestamp=timestamp)
        self._event_bus.emit("voice", "ACTIVITY_CHANGED", event)
