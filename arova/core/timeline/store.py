import asyncio
import logging
import uuid
from typing import List, Optional, Dict, Any
from dataclasses import asdict

from arova.core.timeline.events import TimelineEvent

logger = logging.getLogger(__name__)

class TimelineStore:
    """
    Manages the hot-storage of cognitive timeline events.
    Keeps the last N events in memory for instant retrieval.
    Emits events to the event bus for real-time UI updates.
    """
    def __init__(self, event_bus, max_hot_events: int = 500):
        self.event_bus = event_bus
        self.max_hot_events = max_hot_events
        self.events: List[TimelineEvent] = []
        self._lock = asyncio.Lock()
        
        import os
        from pathlib import Path
        self.capsules_path = Path(os.path.expanduser("~/.config/arova/momentum_capsules.json"))
        self.capsules_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.capsules_path.exists():
            with open(self.capsules_path, "w") as f:
                import json
                json.dump([], f)
                
        if self.event_bus:
            self.event_bus.subscribe("timeline", "create", self._handle_create_event)
            
    def store_capsule(self, capsule: Any):
        import json
        from dataclasses import asdict
        try:
            with open(self.capsules_path, "r") as f:
                capsules = json.load(f)
            capsule_dict = asdict(capsule)
            capsule_dict["resumed"] = False
            capsules.append(capsule_dict)
            with open(self.capsules_path, "w") as f:
                json.dump(capsules, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to store capsule: {e}")
            
    def get_latest_unresumed_capsule(self) -> Optional[Dict[str, Any]]:
        import json
        try:
            with open(self.capsules_path, "r") as f:
                capsules = json.load(f)
            for c in reversed(capsules):
                if not c.get("resumed", False):
                    return c
            return None
        except Exception as e:
            logger.error(f"Failed to load capsules: {e}")
            return None
            
    def mark_capsule_resumed(self, capsule_id: str):
        import json
        try:
            with open(self.capsules_path, "r") as f:
                capsules = json.load(f)
            for c in capsules:
                if c.get("id") == capsule_id:
                    c["resumed"] = True
                    break
            with open(self.capsules_path, "w") as f:
                json.dump(capsules, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to mark capsule resumed: {e}")

    async def initialize(self):
        """Must be called in the main asyncio loop."""
        self._loop = asyncio.get_running_loop()

    def _handle_create_event(self, payload: Any):
        # We need to dispatch to async
        if getattr(self, '_loop', None) is None:
            return  # Store not fully initialized yet
            
        try:
            data = payload.data if hasattr(payload, 'data') else payload
            if not isinstance(data, dict):
                data = data.__dict__
            asyncio.run_coroutine_threadsafe(self.create_and_emit(**data), self._loop)
        except Exception as e:
            logger.error(f"Error handling timeline create event: {e}")

    async def emit(self, event: TimelineEvent):
        """
        Stores an event in hot storage and broadcasts it to connected clients.
        """
        async with self._lock:
            # We insert at the beginning so index 0 is newest
            self.events.insert(0, event)
            if len(self.events) > self.max_hot_events:
                self.events.pop()
                
        # Broadcast immediately
        if self.event_bus:
            payload = asdict(event)
            self.event_bus.emit("timeline", "TIMELINE_EVENT", {"event": payload})
            
    async def get_timeline(self, limit: int = 50, before_timestamp: Optional[float] = None) -> List[Dict[str, Any]]:
        """
        Paginated retrieval of timeline events.
        """
        async with self._lock:
            results = []
            for ev in self.events:
                if before_timestamp and ev.timestamp >= before_timestamp:
                    continue
                results.append(asdict(ev))
                if len(results) >= limit:
                    break
            return results

    async def create_and_emit(self, 
                              category: str, 
                              title: str, 
                              description: str, 
                              source: str, 
                              importance: float = 0.5,
                              correlation_id: Optional[str] = None,
                              metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Convenience method to construct and emit an event.
        """
        event_id = str(uuid.uuid4())
        event = TimelineEvent(
            id=event_id,
            category=category,
            title=title,
            description=description,
            source=source,
            importance=importance,
            correlation_id=correlation_id,
            metadata=metadata or {}
        )
        await self.emit(event)
        return event_id
