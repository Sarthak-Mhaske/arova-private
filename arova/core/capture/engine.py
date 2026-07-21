import time
import uuid
import hashlib
import json
import logging
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, Optional, List, Callable

logger = logging.getLogger(__name__)

@dataclass
class CanonicalActivityEvent:
    """
    A canonical, immutable activity observation from any plugin or OS provider.
    Includes all necessary metadata (`event_id`, `device_id`, `user_id`, `timestamp`, `sequence`, `signature`)
    to support zero-conflict, event-log-driven cloud/peer synchronization.
    """
    event_id: str
    event_type: str  # e.g., 'os_focus', 'editor_change', 'terminal_exec', 'browser_tab', 'git_commit'
    timestamp: float
    source_plugin: str  # e.g., 'vscode', 'terminal', 'chrome', 'os', 'git'
    normalized_payload: Dict[str, Any]
    raw_payload: Dict[str, Any] = field(default_factory=dict)
    provenance: Dict[str, Any] = field(default_factory=dict)
    
    # Sync & Conflict Resolution Fields (`Phase 8`)
    device_id: str = "local-device"
    user_id: str = "local-user"
    sequence: int = 0
    signature: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CanonicalActivityEvent":
        return cls(**data)


class ActivityCaptureEngine:
    """
    The canonical nervous system (`Phase 6`).
    Ingests raw and plugin observations, normalizes them into `CanonicalActivityEvent`s,
    signs/sequences them for immutable sync, and dispatches to:
    - Timeline (`TimelineEvent`)
    - WorkspaceManager (`ingest_fragment`)
    - EventBus & EventLogSyncStore
    """
    def __init__(self, event_bus: Optional[Any] = None, device_id: str = "local-device", user_id: str = "local-user"):
        self.event_bus = event_bus
        self.device_id = device_id
        self.user_id = user_id
        self._sequence_counter = 0
        self._recent_events: List[CanonicalActivityEvent] = []
        self._subscribers: List[Callable[[CanonicalActivityEvent], None]] = []
        
        # References to downstream engines (injected during runtime initialization)
        self.timeline_engine: Optional[Any] = None
        self.workspace_manager: Optional[Any] = None
        self.memory_runtime: Optional[Any] = None
        self.sync_store: Optional[Any] = None

    def subscribe(self, callback: Callable[[CanonicalActivityEvent], None]) -> None:
        """Subscribe a downstream consumer to the canonical event stream."""
        if callback not in self._subscribers:
            self._subscribers.append(callback)

    def _generate_signature(self, event_id: str, timestamp: float, sequence: int, normalized_payload: Dict[str, Any]) -> str:
        """Generate a deterministic signature hash for immutable sync verification."""
        content = f"{event_id}:{self.device_id}:{self.user_id}:{timestamp}:{sequence}:{json.dumps(normalized_payload, sort_keys=True)}"
        return hashlib.sha256(content.encode('utf-8')).hexdigest()

    def ingest_event(self, event_type: str, source_plugin: str, normalized_payload: Dict[str, Any],
                     raw_payload: Optional[Dict[str, Any]] = None,
                     provenance: Optional[Dict[str, Any]] = None) -> CanonicalActivityEvent:
        """
        Ingest a normalized observation from a CapturePlugin or OS provider.
        Normalizes, sequences, signs, and dispatches the canonical event.
        """
        self._sequence_counter += 1
        event_id = str(uuid.uuid4())
        ts = time.time()
        
        signature = self._generate_signature(event_id, ts, self._sequence_counter, normalized_payload)
        
        event = CanonicalActivityEvent(
            event_id=event_id,
            event_type=event_type,
            timestamp=ts,
            source_plugin=source_plugin,
            normalized_payload=normalized_payload or {},
            raw_payload=raw_payload or {},
            provenance=provenance or {"source": source_plugin},
            device_id=self.device_id,
            user_id=self.user_id,
            sequence=self._sequence_counter,
            signature=signature
        )
        
        self._recent_events.append(event)
        if len(self._recent_events) > 500:
            self._recent_events.pop(0)

        # 1. Notify direct subscribers
        for subscriber in self._subscribers:
            try:
                subscriber(event)
            except Exception as e:
                logger.error(f"ActivityCaptureEngine subscriber error: {e}", exc_info=True)

        # 2. Emit to EventBus (`capture.EVENT_INGESTED`)
        if self.event_bus:
            try:
                self.event_bus.emit("capture", "EVENT_INGESTED", event.to_dict())
            except Exception as e:
                logger.warning(f"Failed to emit capture.EVENT_INGESTED: {e}")

        # 3. Feed into Timeline
        if self.timeline_engine:
            try:
                from arova.core.timeline.events import TimelineEvent, CATEGORY_ENVIRONMENT
                title = normalized_payload.get("title") or normalized_payload.get("resource_path") or f"Activity in {source_plugin}"
                desc = normalized_payload.get("summary") or normalized_payload.get("command") or str(normalized_payload)
                tl_event = TimelineEvent(
                    id=event.event_id,
                    category=CATEGORY_ENVIRONMENT,
                    title=str(title),
                    description=str(desc),
                    source=source_plugin,
                    importance=normalized_payload.get("importance", 0.5),
                    metadata=event.to_dict(),
                    timestamp=event.timestamp
                )
                self.timeline_engine.append_event(tl_event)
            except Exception as e:
                logger.debug(f"Could not forward canonical event to timeline: {e}")

        # 4. Feed into WorkspaceManager for organic emergence (`ingest_fragment`)
        if self.workspace_manager:
            try:
                # Map canonical event to workspace fragment schema
                title = normalized_payload.get("title") or normalized_payload.get("resource_path") or ""
                summary = normalized_payload.get("summary") or normalized_payload.get("command") or ""
                if title or summary:
                    self.workspace_manager.ingest_fragment({
                        "source_identity": str(title),
                        "provider_id": source_plugin,
                        "activity_summary": str(summary)
                    })
            except Exception as e:
                logger.debug(f"Could not forward canonical event to workspace_manager: {e}")

        # 5. Feed into EventLogSyncStore (if attached)
        if self.sync_store:
            try:
                self.sync_store.append_event(event)
            except Exception as e:
                logger.debug(f"Could not append canonical event to sync_store: {e}")

        return event

    def get_recent_events(self, count: int = 50) -> List[CanonicalActivityEvent]:
        return self._recent_events[-count:]
