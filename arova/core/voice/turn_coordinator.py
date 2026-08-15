import logging
from typing import Any
from arova.core.events import RuntimeEventBus
from arova.core.time import RuntimeClock

class TurnCoordinator:
    """
    Manages conversational turn-taking, speech completion, and interruption arbitration.
    Abstracts turn finalization away from raw VAD state.
    """
    def __init__(self, event_bus: RuntimeEventBus, session: Any):
        self._event_bus = event_bus
        self._session = session
        
        self._required_silence_s = 2.8
        self._initial_timeout_s = 15.0
        self._last_speech_time = 0.0
        self._turn_start_time = 0.0
        self._is_speaking = False
        self._speech_detected_this_turn = False
        self._turn_active = False
        
        # Subscribe to VAD activity and Wake Detection
        self._event_bus.subscribe("voice", "ACTIVITY_CHANGED", self._on_activity_changed)
        self._event_bus.subscribe("voice", "WAKE_DETECTED", self._on_wake_detected)
        self._event_bus.subscribe("runtime", "INTERRUPT_REQUESTED", self._on_interrupt)
        
        # Periodic check for turn finalization
        self._watchdog_active = True
        import threading
        threading.Thread(target=self._monitor_turn, daemon=True, name="TurnCoordinatorMonitor").start()

    def _on_wake_detected(self, payload):
        """A wake word or manual mic click starts a fresh turn."""
        self._turn_active = True
        self._is_speaking = False
        self._speech_detected_this_turn = False
        self._last_speech_time = 0.0
        self._turn_start_time = RuntimeClock.now()
        
        # Start a new pending turn so a valid turn_id exists for the pipeline.
        self._session.start_new_turn("")
        logging.info(f"TurnCoordinator: New turn started (listening...). turn_id={self._session.get_authoritative_turn_id()}")
        
    def _on_activity_changed(self, payload):
        """VAD updates our local speech model."""
        if not self._turn_active:
            return
            
        self._is_speaking = payload.is_speaking
        if self._is_speaking:
            now = payload.timestamp if hasattr(payload, 'timestamp') and payload.timestamp else RuntimeClock.now()
            self._last_speech_time = now
            if not self._speech_detected_this_turn:
                logging.info("TurnCoordinator: Speech started! Silence monitoring activated.")
                self._speech_detected_this_turn = True
            
    def _on_interrupt(self, payload):
        """An interruption forcibly ends the turn's listening phase."""
        self._turn_active = False
        self._is_speaking = False
        self._session.invalidate_turn()

    def _monitor_turn(self):
        import time
        while self._watchdog_active:
            time.sleep(0.1)
            if not self._turn_active:
                continue
                
            current_time = RuntimeClock.now()
            
            if self._speech_detected_this_turn:
                # Speech was detected — monitor post-speech silence duration
                if not self._is_speaking and self._last_speech_time > 0:
                    if current_time - self._last_speech_time > self._required_silence_s:
                        self._turn_active = False
                        logging.info(f"TurnCoordinator: Post-speech silence threshold ({self._required_silence_s}s) reached, finalizing turn.")
                        self._event_bus.emit("voice", "FINALIZE_TURN", {"timestamp": current_time})
                elif self._is_speaking:
                    # Extended speech guard: max 30s speaking time
                    if current_time - self._turn_start_time > 30.0:
                        self._turn_active = False
                        logging.info("TurnCoordinator: Maximum turn speech duration (30s) reached, finalizing turn.")
                        self._event_bus.emit("voice", "FINALIZE_TURN", {"timestamp": current_time})
            else:
                # Speech has NOT been detected yet — wait up to initial timeout
                if current_time - self._turn_start_time > self._initial_timeout_s:
                    self._turn_active = False
                    logging.info(f"TurnCoordinator: Initial listening timeout ({self._initial_timeout_s}s) reached with no speech detected. Finalizing turn.")
                    self._event_bus.emit("voice", "FINALIZE_TURN", {"timestamp": current_time})
                    
    def stop(self):
        self._watchdog_active = False
