from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import uuid
from arova.core.models.runtime import ModelRuntime
from arova.core.models.schema import ReasoningDepth, ReasoningBudget
from arova.core.automation.graph import GraphDefinition, ExecutionNode
from arova.core.events import RuntimeEventBus, EventPayload

@dataclass
class IntentClassification:
    category: str # "action", "chat", "search", "ambient_reflex", "fast_action"
    confidence: float
    depth: ReasoningDepth
    fast_path_graph: Optional[GraphDefinition] = None
    reasoning: str = ""

class CognitiveRouter:
    """
    The Executive Function. Determines intent and reasoning depth.
    """
    def __init__(self, model_runtime: ModelRuntime, event_bus: RuntimeEventBus):
        self.models = model_runtime
        self.event_bus = event_bus

    def _build_fast_graph(self, name: str, capability: str, args: dict) -> GraphDefinition:
        node = ExecutionNode(id=str(uuid.uuid4()), capability_name=capability, args=args)
        return GraphDefinition(id=str(uuid.uuid4()), name=name, nodes=[node])

    def _get_fast_path(self, text: str) -> Optional[GraphDefinition]:
        """Deterministic regex/keyword bypass for maximum TTFA."""
        norm = text.lower().strip().strip(".!?")
        
        # Hard Fast-Paths that map directly to standard capabilities
        if "volume to " in norm:
            try:
                # very naive extraction for phase 7.5
                vol = int([word for word in norm.split() if word.isdigit()][0])
                return self._build_fast_graph("Set Volume", "set_volume", {"level": vol})
            except:
                pass
                
        if any(w in norm for w in ["pause", "play", "stop", "next"]):
            cmd = "play_pause" if "play" in norm or "pause" in norm else "next_track"
            return self._build_fast_graph("Media Control", "media_control", {"command": cmd})
            
        if any(w in norm for w in ["screenshot", "capture"]):
            return self._build_fast_graph("Take Screenshot", "screenshot", {})
            
        if "open " in norm or "launch " in norm:
            app = norm.replace("open ", "").replace("launch ", "").strip()
            return self._build_fast_graph("Launch App", "open_app", {"app_name": app})
            
        return None

    def _emit_state(self, state: str, details: str = ""):
        self.event_bus.emit("cognition", "COGNITION_STATE_CHANGED", {
            "state": state,
            "details": details
        })

    async def route(self, messages: List[Dict[str, Any]]) -> IntentClassification:
        self._emit_state("ANALYZING_INTENT", "Checking fast-paths...")
        latest = [m["content"] for m in reversed(messages) if m["role"] == "user"]
        if not latest:
            return IntentClassification("chat", 1.0, ReasoningDepth.FAST)
            
        text = latest[0]
        
        # 1. Attempt Fast Path (Zero-Shot Deterministic Bypass)
        fast_graph = self._get_fast_path(text)
        if fast_graph:
            self._emit_state("EXECUTING_FAST_PATH", f"Matched route: {fast_graph.name}")
            return IntentClassification(
                category="fast_action", 
                confidence=1.0, 
                depth=ReasoningDepth.FAST, 
                fast_path_graph=fast_graph,
                reasoning="Matched fast-path heuristic."
            )

        self._emit_state("CLASSIFYING_INTENT", "Consulting LLM router...")
        # 2. Fast LLM Routing (Determine if we need deep planning)
        sys_prompt = (
            "You are the Cognitive Router for Arova, an ambient operating system.\n"
            "Categorize the user's intent into EXACTLY ONE of the following:\n"
            "- action: Requires tools/capabilities (e.g. settings, sys info, executing tasks)\n"
            "- chat: Casual conversation, greetings, simple knowledge.\n"
            "- deep_planning: Requires multi-step execution, heavy memory recall, or complex orchestration.\n"
            "Return JSON matching: {\"category\": \"...\", \"confidence\": 0.0-1.0, \"reasoning\": \"...\"}"
        )
        
        budget = ReasoningBudget(max_tokens=200)
        res = await self.models.invoke_structured(
            messages=messages, 
            system_prompt=sys_prompt, 
            depth=ReasoningDepth.FAST, 
            budget=budget
        )
        
        cat = res.get("category", "chat")
        conf = float(res.get("confidence", 0.5))
        reason = res.get("reasoning", "Failed to parse reasoning")
        
        if cat == "deep_planning":
            depth = ReasoningDepth.DEEP
            cat = "action" # deep planning resolves to actions eventually
            self._emit_state("DEEP_PLANNING_REQUIRED", "Routing to Context Synthesizer")
        else:
            depth = ReasoningDepth.STANDARD
            self._emit_state("STANDARD_ROUTING", f"Intent classified as: {cat}")

        return IntentClassification(
            category=cat,
            confidence=conf,
            depth=depth,
            reasoning=reason
        )
