import asyncio
import logging
import uuid
from typing import List, Optional, Dict, Any
from dataclasses import asdict

from arova.core.timeline.events import TimelineEvent

logger = logging.getLogger(__name__)

class TimelineStore:
    """
    Manages storage and disk persistence of cognitive timeline events.
    Keeps events loaded in memory and persisted to disk for retrieval across sessions.
    Emits events to the event bus for real-time UI updates.
    """
    def __init__(self, event_bus, max_hot_events: int = 500):
        self.event_bus = event_bus
        self.max_hot_events = max_hot_events
        self.events: List[TimelineEvent] = []
        self._lock = asyncio.Lock()
        
        import os
        import json
        from pathlib import Path
        self.events_path = Path(os.path.expanduser("~/.config/arova/timeline_events.json"))
        self.capsules_path = Path(os.path.expanduser("~/.config/arova/momentum_capsules.json"))
        
        self.events_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.capsules_path.exists():
            with open(self.capsules_path, "w") as f:
                json.dump([], f)
                
        # Hydrate historical timeline events from disk
        self._hydrate_from_disk()

        if self.event_bus:
            self.event_bus.subscribe("timeline", "create", self._handle_create_event)

    def _hydrate_from_disk(self):
        import json
        if self.events_path.exists():
            try:
                with open(self.events_path, "r", encoding="utf-8") as f:
                    raw_list = json.load(f)
                loaded = []
                for item in raw_list:
                    if isinstance(item, dict):
                        loaded.append(TimelineEvent(**item))
                # Sort newest first
                loaded.sort(key=lambda e: e.timestamp, reverse=True)
                self.events = loaded[:self.max_hot_events]
                logger.info(f"TimelineStore: Hydrated {len(self.events)} timeline events from disk ({self.events_path})")
            except Exception as e:
                logger.warning(f"TimelineStore hydration failed: {e}")

    def _save_events_to_disk(self):
        import json
        try:
            raw_list = [asdict(e) for e in self.events[:self.max_hot_events]]
            with open(self.events_path, "w", encoding="utf-8") as f:
                json.dump(raw_list, f, indent=2)
        except Exception as e:
            logger.error(f"TimelineStore failed to save events to disk: {e}")
            
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
        try:
            data = payload.data if hasattr(payload, 'data') else payload
            if not isinstance(data, dict):
                data = data.__dict__
                
            if getattr(self, '_loop', None) is not None:
                asyncio.run_coroutine_threadsafe(self.create_and_emit(**data), self._loop)
            else:
                # Sync fallback so timeline events are NEVER lost before loop initialization
                event_id = str(uuid.uuid4())
                event = TimelineEvent(
                    id=event_id,
                    category=data.get("category", "environment"),
                    title=data.get("title", "Event"),
                    description=data.get("description", ""),
                    source=data.get("source", "system"),
                    importance=data.get("importance", 0.5),
                    correlation_id=data.get("correlation_id"),
                    metadata=data.get("metadata") or {}
                )
                self.events.insert(0, event)
                if len(self.events) > self.max_hot_events:
                    self.events.pop()
                self._save_events_to_disk()
        except Exception as e:
            logger.error(f"Error handling timeline create event: {e}")

    async def emit(self, event: TimelineEvent):
        """
        Stores an event in hot storage, persists to disk, and broadcasts it to connected clients.
        """
        async with self._lock:
            # We insert at the beginning so index 0 is newest
            self.events.insert(0, event)
            if len(self.events) > self.max_hot_events:
                self.events.pop()
            self._save_events_to_disk()
                
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

    def append_event(self, event: TimelineEvent):
        """Synchronously appends and saves a canonical event to timeline."""
        self.events.insert(0, event)
        if len(self.events) > self.max_hot_events:
            self.events.pop()
        self._save_events_to_disk()
        if self.event_bus:
            payload = asdict(event)
            self.event_bus.emit("timeline", "TIMELINE_EVENT", {"event": payload})

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
