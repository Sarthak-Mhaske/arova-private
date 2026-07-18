import time
import uuid
import logging
from typing import Dict, List, Literal, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

IntentOrigin = Literal["inferred", "planner", "explicit_user"]
IntentStatus = Literal["active", "paused", "abandoned", "recurring", "completed"]

@dataclass
class IntentNode:
    """Represents a specific unresolved goal or intention in the cognitive runtime."""
    goal: str
    origin: IntentOrigin
    status: IntentStatus = "active"
    
    # Semantic value vs Temporal Salience
    importance: float = 0.5    # 0.0 - 1.0 (How valuable/critical this is to the user)
    pressure: float = 0.0      # 0.0 - 1.0 (How urgently this is pressing on cognition right now)
    urgency: float = 0.5       # 0.0 - 1.0 (Time-sensitivity)
    intent_strength: float = 0.5 # 0.0 - 1.0 (Confidence that this is a real goal)
    
    # Temporal state
    intent_id: str = field(default_factory=lambda: f"intent_{uuid.uuid4().hex[:8]}")
    thread_id: Optional[str] = None # Link to the CognitiveThread
    created_at: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)
    
    # Graph linking
    related_intents: List[str] = field(default_factory=list)
    dependency_links: List[str] = field(default_factory=list)
    
    # Dynamics
    decay_rate: float = 0.05 # Pressure decay per minute when idle/abandoned

    def to_dict(self) -> dict:
        from dataclasses import asdict
        return asdict(self)
        
    @classmethod
    def from_dict(cls, data: dict) -> 'IntentNode':
        return cls(**data)

class IntentGraph:
    """
    Manages the lifecycle of IntentNodes. Slowly decays pressure for abandoned items, 
    builds pressure for deferred intents, and emits signals to the CognitivePriorityEngine 
    when an intent becomes highly salient.
    """
    def __init__(self, event_bus=None):
        self._nodes: Dict[str, IntentNode] = {}
        self.event_bus = event_bus

    def add_intent(self, intent: IntentNode) -> IntentNode:
        # Enforce pressure ceilings based on origin
        if intent.origin == "inferred":
            intent.pressure = min(intent.pressure, 0.4)
            intent.decay_rate = max(intent.decay_rate, 0.1) # Decays faster
            
        self._nodes[intent.intent_id] = intent
        logger.info(f"IntentGraph: Added intent '{intent.goal}' [origin={intent.origin}, pressure={intent.pressure:.2f}]")
        return intent
        
    def get_intent(self, intent_id: str) -> Optional[IntentNode]:
        return self._nodes.get(intent_id)
        
    def update_intent_status(self, intent_id: str, new_status: IntentStatus):
        if intent_id in self._nodes:
            self._nodes[intent_id].status = new_status
            self._nodes[intent_id].last_seen = time.time()
            
    def tick_decay(self):
        """
        Applies temporal decay to intent pressure based on their status and origin.
        Should be called periodically (e.g. every minute) by a background task.
        """
        now = time.time()
        for node in self._nodes.values():
            elapsed_mins = (now - node.last_seen) / 60.0
            
            if node.status == "completed":
                continue
                
            if node.status in ("abandoned", "paused"):
                # Pressure drops while abandoned
                node.pressure = max(0.0, node.pressure - (node.decay_rate * elapsed_mins))
            elif node.status == "active":
                # If active but unseen, it might be deferred, pressure could slowly build or decay depending on urgency
                # For now, explicit user intents build pressure if ignored, inferred intents decay
                if node.origin in ("planner", "explicit_user"):
                    node.pressure = min(1.0, node.pressure + (0.01 * node.urgency * elapsed_mins))
                else:
                    node.pressure = max(0.0, node.pressure - (node.decay_rate * elapsed_mins))
                    
            node.last_seen = now
            
            # Emit to Priority Engine if pressure is high
            if node.pressure > 0.6 and self.event_bus:
                # We emit it as a signal for the PriorityEngine to arbitrate
                self.event_bus.emit("intention", "INTENT_PRESSURE_HIGH", {
                    "source": "intent_graph",
                    "semantic_type": "DEFERRED_INTENT",
                    "confidence": node.intent_strength,
                    "payload": {
                        "intent_id": node.intent_id,
                        "goal": node.goal,
                        "pressure": node.pressure,
                        "importance": node.importance
                    }
                })

    def get_active_intents(self) -> List[IntentNode]:
        return [n for n in self._nodes.values() if n.status == "active"]
        
    def get_all_intents(self) -> List[IntentNode]:
        return list(self._nodes.values())
