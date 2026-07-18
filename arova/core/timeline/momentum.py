import time
import asyncio
import logging
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
import uuid
import json

from arova.core.events import RuntimeEventBus
from arova.core.timeline.store import TimelineStore

logger = logging.getLogger(__name__)

@dataclass
class MomentumCapsule:
    id: str
    timestamp: float
    duration: float
    
    room: str
    workspace: List[str]
    
    objective: str
    progress: str
    blockers: List[str]
    
    next_action: str
    confidence: float
    mental_state: str
    energy_level: str
    decision_log: List[str]
    avoid_list: List[str]

class CapsuleGenerator:
    """
    Uses the LLM orchestrator to summarize recent timeline events into a MomentumCapsule.
    """
    def __init__(self, timeline_store: TimelineStore, orchestrator=None):
        self.timeline_store = timeline_store
        self.orchestrator = orchestrator
        
    def set_orchestrator(self, orchestrator):
        self.orchestrator = orchestrator

    async def generate_capsule(self, duration_seconds: float) -> Optional[MomentumCapsule]:
        if not self.orchestrator:
            logger.error("No orchestrator set for CapsuleGenerator.")
            return None
            
        now = time.time()
        # Fetch events from the last duration_seconds
        events = await self.timeline_store.get_timeline(limit=500, before_timestamp=now)
        # Filter to only events within the duration
        recent_events = [e for e in events if e['timestamp'] >= (now - duration_seconds)]
        
        if not recent_events:
            logger.warning("Timeline is empty. Generating a test capsule for demonstration purposes.")
            return MomentumCapsule(
                id=f"cap_test_{uuid.uuid4().hex[:8]}",
                timestamp=now,
                duration=duration_seconds,
                room="Implementation",
                workspace=["frontend/src/App.tsx"],
                objective="Test Continuity OS",
                progress="Successfully started daemon and connected.",
                blockers=["Need to build Future Self Messages"],
                next_action="Start Phase 8.6C",
                confidence=0.9,
                mental_state="exploring",
                energy_level="high",
                decision_log=["Used test fallback because timeline was empty"],
                avoid_list=["Don't overcomplicate the timeline store"]
            )
            
        # Format events into text
        event_lines = []
        for e in recent_events:
            event_lines.append(f"[{time.strftime('%H:%M:%S', time.localtime(e['timestamp']))}] {e['category']} - {e['title']}: {e['description']}")
            
        events_text = "\n".join(event_lines)
        
        system_prompt = """You are Arova's Continuity Engine.
Your job is to analyze a developer's timeline of events and compress it into a Momentum Capsule.
A Momentum Capsule captures the context, progress, and most importantly, the MOMENTUM of the session.
You MUST extract the 'avoid_list' (failed paths or things the user decided not to do) and the 'next_action'.

Return ONLY valid JSON in the following schema:
{
    "room": "primary room/mode, e.g. frontend, backend, implementation, fragmented",
    "workspace": ["file1.py", "file2.tsx"],
    "objective": "What was the user trying to do?",
    "progress": "What did they accomplish?",
    "blockers": ["Any obvious blockers or friction points detected?"],
    "next_action": "The absolute most critical next step they should take when they return.",
    "confidence": 0.0 to 1.0,
    "mental_state": "deep work, fragmented, struggling, exploring",
    "energy_level": "high, medium, low",
    "decision_log": ["Key technical decision made"],
    "avoid_list": ["Dead ends, failed experiments, or things explicitly abandoned"]
}"""

        try:
            from arova.core.models.schema import PromptNode
            response = await self.orchestrator.generate(
                prompt=PromptNode(text=f"Timeline Events:\n{events_text}\n\nGenerate the JSON capsule:"),
                system=PromptNode(text=system_prompt),
                model_class="smart"
            )
            
            # Parse JSON
            raw_text = response.text.strip()
            if raw_text.startswith("```json"):
                raw_text = raw_text[7:-3].strip()
            elif raw_text.startswith("```"):
                raw_text = raw_text[3:-3].strip()
                
            data = json.loads(raw_text)
            
            capsule = MomentumCapsule(
                id=f"cap_{uuid.uuid4().hex[:12]}",
                timestamp=now,
                duration=duration_seconds,
                room=data.get("room", "unknown"),
                workspace=data.get("workspace", []),
                objective=data.get("objective", "Unknown"),
                progress=data.get("progress", ""),
                blockers=data.get("blockers", []),
                next_action=data.get("next_action", "Continue"),
                confidence=float(data.get("confidence", 0.5)),
                mental_state=data.get("mental_state", "unknown"),
                energy_level=data.get("energy_level", "medium"),
                decision_log=data.get("decision_log", []),
                avoid_list=data.get("avoid_list", [])
            )
            return capsule
            
        except Exception as e:
            logger.error(f"Error generating capsule: {e}")
            return None


class MomentumTracker:
    """
    Subscribes to AttentionGraphEngine and evaluates overall session momentum.
    """
    def __init__(self, event_bus: RuntimeEventBus, capsule_generator: CapsuleGenerator):
        self.event_bus = event_bus
        self.capsule_generator = capsule_generator
        self._session_start_time = time.time()
        
        self.event_bus.subscribe("environment", "ATTENTION_STATE_CHANGED", self._on_attention_changed)

    def _on_attention_changed(self, payload: Any):
        # Implementation for Phase 8.6A proactive capsule triggers will go here
        pass
