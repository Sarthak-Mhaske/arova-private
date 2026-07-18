from dataclasses import dataclass
from typing import Optional
from arova.core.events import RuntimeEventBus, EventPayload
from arova.core.time import RuntimeClock
import time
import logging
import numpy as np
from openwakeword.model import Model

@dataclass(frozen=True, kw_only=True)
class WakeEvent(EventPayload):
    confidence: float
    source: str

class WakeRuntimeService:
    """
    Background service for wake word detection.
    Continues running even during TTS or execution to enable interruptions.
    Produces WakeEvents with confidence scores.
    """
    
    def __init__(self, event_bus: RuntimeEventBus, config: dict):
        self._event_bus = event_bus
        self._config = config
        self._running = False
        
        # openwakeword requires ~1280 sample chunks at 16kHz (80ms).
        # We will initialize it lazily to avoid heavy loading on import.
        self._oww_model: Optional[Model] = None
        self._last_wake_time = 0.0
        self._cooldown_seconds = 4.0
        
        self._current_state = "idle"
        self._event_bus.subscribe("state", "STATE_CHANGED", self._on_state_changed)
        
    def _on_state_changed(self, payload):
        if isinstance(payload, dict):
            self._current_state = payload.get("state", "idle")
        else:
            self._current_state = getattr(payload, "state", "idle")
            
        # Reset cooldown when entering idle so any echo tail doesn't immediately trigger it
        if self._current_state == "idle":
            self._last_wake_time = time.time()
        
    def start(self):
        self._running = True
        
    def stop(self):
        self._running = False
        
    def process_audio_chunk(self, chunk: bytes, sample_rate: int = 16000):
        """
        Processes audio to detect wake words using openwakeword.
        """
        if not self._running:
            return
            
        if self._current_state != "idle":
            # Suppress wake word processing when Arova is actively listening, thinking, or speaking.
            # This provides architectural conversational gating and solves both 
            # software echo cancellation (speakers) and self-triggering recursive loops.
            return
            
        if self._oww_model is None:
            logging.info("Initializing openwakeword models...")
            # Loads default models like 'hey mycroft', 'alexa', 'hey jarvis', etc.
            # We can use "hey jarvis" as a placeholder for "hey arova" unless custom trained.
            # Or "alexa". For MVP, let's load the default models and check any.
            self._oww_model = Model()
            
        # Convert bytes to numpy array
        # openwakeword expects 16-bit PCM arrays
        audio_data = np.frombuffer(chunk, dtype=np.int16)
        
        # Openwakeword processes internally, usually feeding whatever size is given
        prediction = self._oww_model.predict(audio_data)
        
        now = time.time()
        if now - self._last_wake_time < self._cooldown_seconds:
            return
            
        # Check scores (prediction is a dict {model_name: score})
        for mdl_name, score in prediction.items():
            if score > 0.5: # 0.5 is a reasonable confidence threshold
                logging.info(f"Wake word '{mdl_name}' detected! Score: {score}")
                self._last_wake_time = now
                self._emit_wake(score, source=mdl_name)
                break

    def _emit_wake(self, confidence: float, source: str = "wakeword"):
        event = WakeEvent(confidence=confidence, source=source, timestamp=RuntimeClock.now())
        self._event_bus.emit("voice", "WAKE_DETECTED", event)
        
        # If confidence is extremely high and we are in a speaking/executing state,
        # we might also directly trigger an INTERRUPT_REQUESTED, but typically
        # the VoiceRuntime state coordinator observes WAKE_DETECTED and issues it.
