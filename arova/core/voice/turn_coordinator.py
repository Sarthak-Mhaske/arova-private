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
        
        self._required_silence_s = 3.0
        self._initial_timeout_s = 10.0
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
        """A wake word starts a fresh turn and revokes any existing turn's authority."""
        self._turn_active = True
        self._is_speaking = False
        self._speech_detected_this_turn = False
        self._last_speech_time = 0.0
        self._turn_start_time = RuntimeClock.now()
        
        # Start a new pending turn so a valid turn_id exists for the pipeline.
        # The transcript will be filled in later by STT.
        self._session.start_new_turn("")
        logging.info(f"TurnCoordinator: New turn started. turn_id={self._session.get_authoritative_turn_id()}")
        
    def _on_activity_changed(self, payload):
        """VAD updates our local speech model."""
        if not self._turn_active:
            return
            
        self._is_speaking = payload.is_speaking
        if self._is_speaking:
            if not self._speech_detected_this_turn:
                logging.info("TurnCoordinator: Speech detected! Cancelling initial timeout.")
                self._speech_detected_this_turn = True
            self._last_speech_time = payload.timestamp
            
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
                
            # If we've been silent longer than the required silence duration
            current_time = RuntimeClock.now()
            if not self._is_speaking:
                if self._last_speech_time > 0:
                    if current_time - self._last_speech_time > self._required_silence_s:
                        self._turn_active = False
                        logging.info("TurnCoordinator: Silence threshold reached, finalizing turn.")
                        self._event_bus.emit("voice", "FINALIZE_TURN", {"timestamp": current_time})
                else:
                    if current_time - self._turn_start_time > self._initial_timeout_s:
                        self._turn_active = False
                        logging.info("TurnCoordinator: Initial timeout reached (no speech detected). Finalizing turn.")
                        self._event_bus.emit("voice", "FINALIZE_TURN", {"timestamp": current_time})
            else:
                # BULLETPROOF FALLBACK: Never hang forever
                if current_time - self._turn_start_time > 10.0:
                    self._turn_active = False
                    logging.info("TurnCoordinator: Maximum turn length (10s) reached. Force finalizing turn to prevent hang.")
                    self._event_bus.emit("voice", "FINALIZE_TURN", {"timestamp": current_time})
                    
    def stop(self):
        self._watchdog_active = False
