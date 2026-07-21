import asyncio
import logging
from typing import Optional
from arova.core.events import RuntimeEventBus, StateEvent
from arova.core.ambience.schema import AmbientContext
from arova.core.ambience.provider import AmbientProvider

class AmbientObserver:
    """
    Polls the AmbientProvider, implements stability debouncing (Context Stability Windows),
    and emits CONTEXT_CHANGED events to the bus.
    """
    def __init__(self, event_bus: RuntimeEventBus, provider: AmbientProvider, stability_window_seconds: float = 2.0):
        self.event_bus = event_bus
        self.provider = provider
        self.stability_window = stability_window_seconds
        
        self.current_context: Optional[AmbientContext] = None
        
        self._pending_context: Optional[AmbientContext] = None
        self._pending_since: float = 0.0
        
        self._task: Optional[asyncio.Task] = None
        self._running = False
        
    def start(self):
        if not self._running:
            self._running = True
            if getattr(self.provider, "is_event_driven", lambda: False)():
                logging.info("AmbientObserver: Operating system event source detected; operating event-driven without polling loop (P0-4).")
                if hasattr(self.provider, "subscribe"):
                    self.provider.subscribe(self._on_provider_context)
            else:
                logging.info("AmbientObserver: Operating system provides no reliable event source; starting debounced poll loop.")
                self._task = asyncio.create_task(self._poll_loop())
            
    def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()

    def _on_provider_context(self, new_ctx: AmbientContext):
        if new_ctx != self.current_context:
            self.current_context = new_ctx
            self.event_bus.emit("ambience", "CONTEXT_CHANGED", StateEvent(
                state="CONTEXT_CHANGED",
                message="Ambient context stabilized (event-driven)",
                snapshot=new_ctx.__dict__
            ))
            logging.info("AmbientObserver: Context stabilized and updated from OS event stream.")
            
    async def _poll_loop(self):
        while self._running:
            try:
                new_ctx = await self.provider.get_current_context()
                
                # If context is different from current stable context
                if new_ctx != self.current_context:
                    # Check if it matches our pending context (we are in a stability window)
                    if new_ctx == self._pending_context:
                        time_stable = new_ctx.timestamp - self._pending_since
                        if time_stable >= self.stability_window:
                            # It has been stable long enough. Commit it.
                            self.current_context = new_ctx
                            self._pending_context = None
                            
                            self.event_bus.emit("ambience", "CONTEXT_CHANGED", StateEvent(
                                state="CONTEXT_CHANGED",
                                message="Ambient context stabilized",
                                snapshot=new_ctx.__dict__
                            ))
                            logging.info("AmbientObserver: Context stabilized and updated.")
                    else:
                        # New change, reset the stability window
                        self._pending_context = new_ctx
                        self._pending_since = new_ctx.timestamp
                else:
                    # Context matches stable state, clear any pending jitter
                    self._pending_context = None
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logging.error(f"AmbientObserver poll error: {e}")
                
            await asyncio.sleep(1.0)
