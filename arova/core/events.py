from dataclasses import dataclass, field
import weakref
import threading
import time
import queue
import logging
from typing import Callable, Any, Dict, List, Optional
from enum import IntEnum
from concurrent.futures import ThreadPoolExecutor

class EventPriority(IntEnum):
    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3
    TELEMETRY = 4

@dataclass(frozen=True, kw_only=True)
class EventPayload:
    """Base immutable payload for all events."""
    timestamp: float = field(default_factory=time.time)
    trace_id: Optional[str] = None
    execution_id: Optional[str] = None
    conversation_id: Optional[str] = None
    turn_id: Optional[str] = None
    request_id: Optional[str] = None
    priority: EventPriority = EventPriority.NORMAL

@dataclass(frozen=True, kw_only=True)
class DictPayload(EventPayload):
    data: dict

    def __getattr__(self, name):
        if name in self.data:
            return self.data[name]
        raise AttributeError(name)

@dataclass(frozen=True, kw_only=True)
class ExecutionEvent(EventPayload):
    plan_id: str
    status: str
    step_id: Optional[str] = None
    message: Optional[str] = None
    data: Optional[Dict[str, Any]] = None

@dataclass(frozen=True, kw_only=True)
class PlanEvent(EventPayload):
    plan_id: str
    status: str
    data: Optional[Dict[str, Any]] = None

@dataclass(frozen=True, kw_only=True)
class VoiceEvent(EventPayload):
    state: str
    message: Optional[str] = None
    data: Optional[Dict[str, Any]] = None

@dataclass(frozen=True, kw_only=True)
class StateEvent(EventPayload):
    state: str
    message: str
    snapshot: Dict[str, Any]

class RuntimeEventBus:
    """
    Asynchronous, thread-safe EventBus with channel-aware serialization.
    Guarantees ordered delivery per-channel, while allowing parallel delivery across channels.
    Supports backpressure (drop/coalesce policies) and priority queues.
    """
    def __init__(self, max_queue_size: int = 1000):
        self._lock = threading.RLock()
        self._subscribers: Dict[str, Dict[str, List[weakref.ref]]] = {}
        self._filters: List[Callable[[str, str, EventPayload], bool]] = []
        
        # Channel state
        # channel -> PriorityQueue of (priority, timestamp, sequence, event_name, payload)
        self._queues: Dict[str, queue.PriorityQueue] = {}
        # Tracks which channels currently have an active consumer task in the thread pool
        self._active_consumers: set[str] = set()
        
        # Coalescing: channel -> event_name -> (priority, sequence, payload)
        # Keeps only the latest payload for coalescable events in the queue
        self._coalesced_events: Dict[str, Dict[str, Any]] = {}
        
        self._sequence = 0
        self._max_queue_size = max_queue_size
        
        # Dispatcher pool
        self._executor = ThreadPoolExecutor(
            max_workers=4, 
            thread_name_prefix="EventBus-Dispatcher"
        )
        self._running = True

    def subscribe(self, channel: str, event_name: str, callback: Callable[[EventPayload], None]):
        with self._lock:
            if channel not in self._subscribers:
                self._subscribers[channel] = {}
            if event_name not in self._subscribers[channel]:
                self._subscribers[channel][event_name] = []
                
            if hasattr(callback, '__self__'):
                ref = weakref.WeakMethod(callback)
            else:
                ref = weakref.ref(callback)
                
            self._subscribers[channel][event_name].append(ref)

    def unsubscribe(self, channel: str, event_name: str, callback: Callable[[EventPayload], None]):
        with self._lock:
            if channel in self._subscribers and event_name in self._subscribers[channel]:
                refs = self._subscribers[channel][event_name]
                for r in refs[:]:
                    cb = r()
                    if cb is None or cb == callback:
                        refs.remove(r)

    def add_filter(self, filter_func: Callable[[str, str, EventPayload], bool]):
        with self._lock:
            self._filters.append(filter_func)

    def emit(self, channel: str, event_name: str, payload: Any, coalesce: bool = False):
        if not self._running:
            return
            
        if isinstance(payload, dict):
            kwargs = {}
            # Extract standard EventPayload fields to prevent dataclass defaults from masking dict values
            for field in ["priority", "timestamp", "trace_id", "execution_id", "conversation_id", "turn_id", "request_id"]:
                if field in payload:
                    kwargs[field] = payload[field]
            payload = DictPayload(data=payload, **kwargs)
            
        # Apply ingestion filters
        for f in self._filters:
            if not f(channel, event_name, payload):
                return
                
        with self._lock:
            if channel not in self._queues:
                self._queues[channel] = queue.PriorityQueue()
                self._coalesced_events[channel] = {}
                
            q = self._queues[channel]
            
            if q.qsize() >= self._max_queue_size:
                logging.warning(f"EventBus queue for channel {channel} is full. Dropping event {event_name}.")
                return
                
            self._sequence += 1
            seq = self._sequence
            pri = payload.priority
            
            item = (pri, payload.timestamp, seq, event_name, payload)
            
            if coalesce:
                # Store reference to the latest coalesced item
                old_item = self._coalesced_events[channel].get(event_name)
                if old_item:
                    # We cannot easily remove from PriorityQueue, so we mark it stale 
                    # by keeping the sequence id and verifying it during consumption.
                    pass
                self._coalesced_events[channel][event_name] = seq
            
            q.put(item)
            
            if channel not in self._active_consumers:
                self._active_consumers.add(channel)
                self._executor.submit(self._consume_channel, channel)

    def _consume_channel(self, channel: str):
        while self._running:
            with self._lock:
                q = self._queues.get(channel)
                if not q or q.empty():
                    self._active_consumers.remove(channel)
                    return
                
                try:
                    pri, ts, seq, event_name, payload = q.get_nowait()
                except queue.Empty:
                    self._active_consumers.remove(channel)
                    return
                    
                # Check if this was coalesced out
                latest_seq = self._coalesced_events.get(channel, {}).get(event_name)
                if latest_seq is not None and latest_seq != seq:
                    # Skip stale coalesced event
                    q.task_done()
                    continue
                    
                if latest_seq is not None and latest_seq == seq:
                    # It's the latest, clear it so next emit gets a fresh sequence
                    del self._coalesced_events[channel][event_name]
                    
                subs = self._subscribers.get(channel, {}).get(event_name, [])[:]
                
            # Dispatch outside lock
            dead_refs = []
            for r in subs:
                cb = r()
                if cb is not None:
                    try:
                        cb(payload)
                    except Exception as e:
                        logging.error(f"Error in EventBus listener ({channel}:{event_name}): {e}")
                else:
                    dead_refs.append(r)
                    
            if dead_refs:
                with self._lock:
                    active_subs = self._subscribers.get(channel, {}).get(event_name, [])
                    for r in dead_refs:
                        if r in active_subs:
                            active_subs.remove(r)
                            
            with self._lock:
                q.task_done()

    def shutdown(self, wait: bool = True):
        self._running = False
        self._executor.shutdown(wait=wait)
