"""
Semantic Environment Graph — Arova's persistent, decaying world-model.

Absorbs EnvironmentalEvents, maintains temporal state with confidence decay,
and exposes a stabilized snapshot for cognition systems to query.
"""
import asyncio
import math
import time
import logging
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, Optional
from arova.core.environment.events import EnvironmentalEvent

logger = logging.getLogger(__name__)

# Decay configuration per semantic_type.
# half_life_s: seconds until confidence drops to 50% of its original value.
# sticky: if True, event persists until explicitly overridden by a newer event of the same type.
DECAY_PROFILES: Dict[str, Dict[str, Any]] = {
    "ATTENTION_STATE_CHANGED":       {"half_life_s": 300,  "sticky": False},  # 5 minutes
    "WORKSPACE_SEMANTICS_CHANGED":   {"half_life_s": None, "sticky": True},   # Persists until overridden
    "AMBIENT_INTENT_DETECTED":       {"half_life_s": 600,  "sticky": False},  # 10 minutes
    "DEEP_WORK_ENTERED":             {"half_life_s": 900,  "sticky": False},  # 15 minutes
    "ATTENTION_FRAGMENTED":          {"half_life_s": 180,  "sticky": False},  # 3 minutes — fades fast
}

DEFAULT_DECAY = {"half_life_s": 300, "sticky": False}


@dataclass
class GraphNode:
    """A single state entry in the graph, tied to a semantic_type."""
    event: EnvironmentalEvent
    original_confidence: float
    decayed_confidence: float
    last_updated: float = field(default_factory=time.time)


class SemanticEnvironmentGraph:
    """
    Stateful, decaying world-model. All environmental cognition systems
    feed into this graph via `apply()`. Cognition systems query `snapshot()`.
    
    Design principles:
    - Raw telemetry never leaves this layer. Only semantic meaning propagates.
    - Older states decay unless explicitly reinforced or marked sticky.
    - The graph is the single source of truth for "what is the room doing?"
    """

    def __init__(self):
        self._nodes: Dict[str, GraphNode] = {}  # keyed by semantic_type
        self._history: list = []                  # append-only trace for observability
        self._running = False
        self._decay_task: Optional[asyncio.Task] = None

    def apply(self, event: EnvironmentalEvent):
        """Absorb an EnvironmentalEvent into the graph, replacing or reinforcing existing state."""
        node = GraphNode(
            event=event,
            original_confidence=event.confidence,
            decayed_confidence=event.confidence,
            last_updated=event.timestamp
        )
        self._nodes[event.semantic_type] = node

        # Append to trace (capped for memory safety)
        self._history.append({
            "semantic_type": event.semantic_type,
            "source": event.source,
            "confidence": event.confidence,
            "timestamp": event.timestamp,
            "payload_keys": list(event.payload.keys())
        })
        if len(self._history) > 500:
            self._history = self._history[-250:]

        logger.debug(f"Graph.apply: {event.semantic_type} conf={event.confidence:.2f} src={event.source}")

    def snapshot(self) -> Dict[str, Any]:
        """
        Returns the current decayed world-state.
        Nodes below a confidence threshold of 0.05 are omitted entirely.
        """
        self._apply_decay()

        result: Dict[str, Any] = {}
        for stype, node in self._nodes.items():
            if node.decayed_confidence < 0.05:
                continue
            result[stype] = {
                "confidence": round(node.decayed_confidence, 3),
                "payload": node.event.payload,
                "source": node.event.source,
                "age_s": round(time.time() - node.last_updated, 1)
            }

        # Synthesize high-level derived fields for easy consumption
        result["_derived"] = self._derive_state()
        return result

    def _derive_state(self) -> Dict[str, Any]:
        """Synthesize high-level cognitive fields from active nodes."""
        attention_node = self._nodes.get("ATTENTION_STATE_CHANGED")
        workspace_node = self._nodes.get("WORKSPACE_SEMANTICS_CHANGED")

        focus_depth = 0.0
        probable_mode = "idle"
        workspace_type = "unknown"

        if attention_node and attention_node.decayed_confidence >= 0.05:
            focus_depth = attention_node.event.payload.get("focus_depth", 0.0)
            probable_mode = attention_node.event.payload.get("probable_mode", "idle")

        if workspace_node and workspace_node.decayed_confidence >= 0.05:
            workspace_type = workspace_node.event.payload.get("role", "unknown")

        return {
            "current_workspace_type": workspace_type,
            "active_focus_depth": round(focus_depth, 3),
            "probable_attention_mode": probable_mode,
            "graph_node_count": len([n for n in self._nodes.values() if n.decayed_confidence >= 0.05])
        }

    def _apply_decay(self):
        """Apply exponential decay to all non-sticky nodes based on elapsed time."""
        now = time.time()
        for stype, node in self._nodes.items():
            profile = DECAY_PROFILES.get(stype, DEFAULT_DECAY)

            if profile["sticky"]:
                # Sticky nodes don't decay, they only get replaced by new events
                continue

            half_life = profile["half_life_s"]
            if half_life is None or half_life <= 0:
                continue

            elapsed = now - node.last_updated
            # Exponential decay: confidence * (0.5 ^ (elapsed / half_life))
            decay_factor = math.pow(0.5, elapsed / half_life)
            node.decayed_confidence = node.original_confidence * decay_factor

    async def start_decay_loop(self, interval_s: float = 5.0):
        """Background loop that periodically applies decay. Call once at startup."""
        self._running = True
        logger.info(f"SemanticEnvironmentGraph decay loop started (interval={interval_s}s)")
        while self._running:
            self._apply_decay()
            await asyncio.sleep(interval_s)

    def stop(self):
        """Stop the background decay loop."""
        self._running = False
        if self._decay_task:
            self._decay_task.cancel()

    def get_trace(self, last_n: int = 20) -> list:
        """Return the last N trace entries for observability."""
        return self._history[-last_n:]
