import logging
import threading
import time
from typing import Any
from arova.core.events import RuntimeEventBus

class RecoveryCoordinator:
    """
    Listens for RECOVERY_REQUIRED events emitted by watchdogs.
    Gracefully tears down active execution and TTS, forcing a return to Quiescence.
    """
    def __init__(self, event_bus: RuntimeEventBus, cancellation: Any):
        self._event_bus = event_bus
        self._cancellation = cancellation
        
        self._event_bus.subscribe("runtime", "RECOVERY_REQUIRED", self._on_recovery_required)
        
    def _on_recovery_required(self, payload):
        reason = getattr(payload, "reason", "unknown")
        logging.error(f"RecoveryCoordinator invoked due to: {reason}. Forcing quiescence.")
        
        # 1. Trigger a global interrupt to cancel all tokens
        self._event_bus.emit("runtime", "INTERRUPT_REQUESTED", {"source": "watchdog_recovery"})
        
        # Wait a brief moment to allow cascade cancellation to propagate
        time.sleep(0.1)
        
        # 2. Inform the VoiceRuntime that recovery steps have been dispatched
        # VoiceRuntime Quiescence checks will naturally bring the system back to IDLE
        # once the cancel events (e.g. EXECUTION_CANCELLED, TTS_INTERRUPTED) propagate.
        self._event_bus.emit("runtime", "RECOVERY_DISPATCHED", {"reason": reason})

class WatchdogService:
    """
    Monitors VoiceRuntime state. Emits RECOVERY_REQUIRED if a state
    exceeds its expected timeout (e.g. stuck THINKING for > 30s).
    """
    def __init__(self, event_bus: RuntimeEventBus):
        self._event_bus = event_bus
        
        self._state_timeouts = {
            "thinking": 45.0, # max seconds to wait for an execution to complete
            "speaking": 300.0, # max seconds a TTS stream can run unattended
        }
        
        self._current_state = "idle"
        self._state_entered_time = 0.0
        
        self._event_bus.subscribe("state", "STATE_CHANGED", self._on_state_changed)
        
        self._running = True
        threading.Thread(target=self._monitor, daemon=True, name="WatchdogService").start()
        
    def _on_state_changed(self, payload):
        state = payload.state
        self._current_state = state
        self._state_entered_time = time.time()
        
    def _monitor(self):
        while self._running:
            time.sleep(1.0)
            if self._current_state not in self._state_timeouts:
                continue
                
            elapsed = time.time() - self._state_entered_time
            if elapsed > self._state_timeouts[self._current_state]:
                logging.error(f"Watchdog timeout: stuck in {self._current_state} for {elapsed:.1f}s.")
                self._event_bus.emit("runtime", "RECOVERY_REQUIRED", {"reason": f"watchdog_{self._current_state}_timeout"})
                
                # Prevent repeating the same timeout indefinitely
                self._current_state = "idle" 
                
    def stop(self):
        self._running = False
