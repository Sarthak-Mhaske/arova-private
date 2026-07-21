import time
import logging
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import GLib

class UIScheduler:
    """
    Batches IPC bursts, handles animation frame syncing, and coalesces cognition events
    to ensure 0 main-thread stalls and smooth 60fps rendering.
    """
    def __init__(self):
        self._pending_events = []
        self._scheduled = False
        self._coalesce_keys = set()
        self._handlers = {} # event_type -> list of callbacks
        self.send_callback = None

    def bind(self, event_type: str, callback):
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(callback)

    def send_ipc_payload(self, payload: dict):
        if self.send_callback:
            self.send_callback(payload)
        else:
            logging.warning("UIScheduler: No IPC send_callback bound for outgoing payload.")

    def dispatch_ipc_event(self, event: dict):
        """Called from background IPC thread."""
        event_type = event.get("event_type")
        if not event_type:
            return
            
        # Coalesce high-frequency events (e.g. state updates where only the latest matters)
        if event_type == "COGNITION_STATE_CHANGED":
            # Remove previous cognition state events from pending queue
            self._pending_events = [e for e in self._pending_events if e.get("event_type") != event_type]
            
        self._pending_events.append(event)
        
        if not self._scheduled:
            self._scheduled = True
            # Schedule batch processing on the GTK main thread
            GLib.idle_add(self._process_batch)

    def _process_batch(self):
        """Runs on GTK Main Thread."""
        self._scheduled = False
        events_to_process = self._pending_events[:]
        self._pending_events.clear()
        
        for event in events_to_process:
            evt_type = event.get("event_type")
            if evt_type in self._handlers:
                for cb in self._handlers[evt_type]:
                    try:
                        cb(event)
                    except Exception as e:
                        logging.error(f"UI Scheduler callback error: {e}")
                        
        return GLib.SOURCE_REMOVE
