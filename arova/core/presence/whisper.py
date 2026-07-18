import logging
from enum import Enum
from arova.core.presence.silence import SilenceEngine

class WhisperUrgency(Enum):
    AMBIENT = "ambient"       # Tiny fade near orb
    CONTEXTUAL = "contextual" # Contextual hints, easily suppressed
    ADVISORY = "advisory"     # Soft expansion of the orb
    WARNING = "warning"       # Edge glow + whisper
    CRITICAL = "critical"     # Full interruption, bypasses silence rules

class WhisperEngine:
    """
    Ingests whispers, checks the SilenceEngine, and routes to IPC.
    """
    def __init__(self, silence_engine: SilenceEngine, event_bus):
        self.silence_engine = silence_engine
        self.event_bus = event_bus
        
    def emit(self, text: str, urgency: WhisperUrgency, current_focus_depth: float = 0.5):
        """
        Evaluates if the whisper should be shown, deferred, or dropped.
        """
        if self.silence_engine.should_suppress(urgency, current_focus_depth):
            if urgency in (WhisperUrgency.ADVISORY, WhisperUrgency.CONTEXTUAL):
                logging.info(f"[WhisperEngine] Suppressing and deferring whisper: {text}")
                self.silence_engine.defer_whisper(text, urgency)
            else:
                logging.debug(f"[WhisperEngine] Dropping ambient whisper due to silence policy: {text}")
            return
            
        # Emit over IPC
        self.silence_engine.record_whisper()
        logging.info(f"[WhisperEngine] Emitting {urgency.name} whisper: {text}")
        self.event_bus.publish("PRESENCE_WHISPER", {
            "text": text,
            "urgency": urgency.value
        })
        
    def check_debt(self):
        """Called periodically or when focus depth drops to flush deferred insights."""
        debt = self.silence_engine.flush_debt()
        if debt:
            summary = "While you were focused:\n- " + "\n- ".join(debt)
            self.emit(summary, WhisperUrgency.ADVISORY, current_focus_depth=0.0) # Force emit
