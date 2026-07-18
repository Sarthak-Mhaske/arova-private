import logging
from typing import Any
from arova.core.events import EventPayload

class TurnAuthorityFilter:
    """
    Ingestion filter for the RuntimeEventBus.
    Ensures that stale execution or TTS events from previous turns are dropped
    before they can contaminate the active state machine.
    """
    def __init__(self, session: Any):
        self._session = session
        
        # Events that MUST be scoped to the authoritative turn
        self._scoped_events = {
            "EXECUTION_STARTED",
            "EXECUTION_COMPLETED",
            "EXECUTION_FAILED",
            "EXECUTION_STATE_CHANGED",
            "TEXT_RESPONSE_GENERATED",
            "TTS_STARTED",
            "TTS_COMPLETED",
            "TTS_INTERRUPTED"
        }
        
    def filter_event(self, channel: str, event_name: str, payload: EventPayload) -> bool:
        if event_name not in self._scoped_events:
            return True # Let generic events pass
            
        turn_id = getattr(payload, "turn_id", None)
        if not turn_id:
            # Events in the scoped list MUST have a turn_id
            logging.warning(f"Event dropped: {event_name} lacks turn_id.")
            return False
            
        if not self._session.is_authoritative(turn_id):
            logging.warning(f"Event dropped: {event_name} from stale turn '{turn_id}'. "
                            f"Authoritative is '{self._session.get_authoritative_turn_id()}'.")
            return False
            
        return True
