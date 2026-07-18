import threading
from typing import Dict, Optional
from arova.core.events import RuntimeEventBus

class CancellationToken:
    """A thread-safe cancellation token used to abort running streams and plans."""
    
    def __init__(self):
        self._cancelled = False
        self._event = threading.Event()
        
    def cancel(self):
        self._cancelled = True
        self._event.set()
        
    @property
    def is_cancelled(self) -> bool:
        return self._cancelled
        
    def wait(self, timeout: Optional[float] = None) -> bool:
        """Waits for cancellation. Returns True if cancelled, False if timed out."""
        return self._event.wait(timeout)

class RuntimeCancellationService:
    """
    Coordinates global INTERRUPT_REQUESTED events and translates them into
    token cancellations for active execution and TTS streams.
    """
    
    def __init__(self, event_bus: RuntimeEventBus):
        self._event_bus = event_bus
        self._tokens: Dict[str, CancellationToken] = {}
        self._lock = threading.Lock()
        
        # Subscribe to global interrupt requests
        self._event_bus.subscribe("runtime", "INTERRUPT_REQUESTED", self._on_interrupt)
        
    def create_token(self, execution_context_id: str) -> CancellationToken:
        """Creates and registers a new cancellation token for a specific context."""
        token = CancellationToken()
        with self._lock:
            self._tokens[execution_context_id] = token
        return token
        
    def remove_token(self, execution_context_id: str):
        """Unregisters a cancellation token when a context completes naturally."""
        with self._lock:
            self._tokens.pop(execution_context_id, None)
            
    def _on_interrupt(self, payload):
        """Handles INTERRUPT_REQUESTED events by cancelling all active tokens."""
        # Optional: Payload could specify a specific context ID to cancel,
        # but typically voice interruptions cancel everything currently active.
        target_context = getattr(payload, "execution_context_id", None)
        
        with self._lock:
            if target_context and target_context in self._tokens:
                self._tokens[target_context].cancel()
                del self._tokens[target_context]
            else:
                for token in self._tokens.values():
                    token.cancel()
                self._tokens.clear()
