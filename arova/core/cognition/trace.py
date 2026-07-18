import time
import json
import logging
from typing import Dict, Any, List
from dataclasses import dataclass, field
from arova.core.events import RuntimeEventBus, EventPayload

@dataclass
class CognitiveTrace:
    trace_id: str
    turn_id: str
    intent_category: str = "unknown"
    reasoning_depth: str = "unknown"
    retrieved_memories: List[str] = field(default_factory=list)
    generated_plan_id: str = "none"
    latency_ms: float = 0.0
    timestamp: float = field(default_factory=time.time)

class CognitiveTraceEngine:
    """
    Observability layer for intelligence. Records *why* decisions were made.
    """
    def __init__(self, event_bus: RuntimeEventBus):
        self.event_bus = event_bus
        self.active_traces: Dict[str, CognitiveTrace] = {}
        
    def begin_trace(self, trace_id: str, turn_id: str):
        self.active_traces[trace_id] = CognitiveTrace(trace_id=trace_id, turn_id=turn_id)
        
    def log_intent(self, trace_id: str, category: str, depth: str):
        if trace_id in self.active_traces:
            self.active_traces[trace_id].intent_category = category
            self.active_traces[trace_id].reasoning_depth = depth
            
    def log_memory_retrieval(self, trace_id: str, reasons: List[str]):
        if trace_id in self.active_traces:
            self.active_traces[trace_id].retrieved_memories.extend(reasons)
            
    def finish_trace(self, trace_id: str, plan_id: str = "none"):
        if trace_id in self.active_traces:
            trace = self.active_traces[trace_id]
            trace.generated_plan_id = plan_id
            trace.latency_ms = (time.time() - trace.timestamp) * 1000
            
            logging.info(f"[COGNITIVE TRACE] {trace_id}: Intent={trace.intent_category}, Depth={trace.reasoning_depth}, Mems={len(trace.retrieved_memories)}, Latency={trace.latency_ms:.1f}ms")
            
            self.event_bus.emit("cognition", "COGNITIVE_TRACE_COMPLETED", {
                "trace_id": trace.trace_id,
                "details": trace.__dict__
            })
            
            self.active_traces.pop(trace_id, None)
