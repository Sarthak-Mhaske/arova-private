import logging
from typing import Dict, Any, List, Optional
from arova.core.models.schema import ReasoningDepth, ReasoningBudget, ModelCapabilityProfile
from arova.core.models.profiles import CognitiveProfile

from arova.core.config.manager import get_config_manager
from arova.core.providers.capabilities import Capability
from arova.core.providers.manager import ProviderManager
from arova.core.providers.policy import RoutingPolicy
from arova.core.providers.router import CapabilityRouter

class ModelOrchestrator:
    """
    The main Inference Infrastructure entrypoint.
    Delegates to the CapabilityRouter which uses RoutingPolicy to select Providers.
    """
    def __init__(self, config: Dict[str, Any], active_profile: CognitiveProfile = CognitiveProfile.BALANCED, event_bus=None):
        self.config = config
        self.active_profile = active_profile
        
        # Phase 6C Provider Abstraction
        self.provider_manager = ProviderManager()
        
        os_config = get_config_manager().load_config()
        presence_style = os_config.get("presence_style", "instant")
        custom_routing = os_config.get("custom_routing", {})
        preferred_provider = os_config.get("preferred_provider")
        allow_fallback = os_config.get("allow_fallback", True)
        
        self.routing_policy = RoutingPolicy(
            presence_style=presence_style, 
            custom_routing=custom_routing,
            preferred_provider=preferred_provider,
            allow_fallback=allow_fallback
        )
        self.router = CapabilityRouter(
            provider_manager=self.provider_manager, 
            routing_policy=self.routing_policy,
            event_bus=event_bus
        )
        
        # Phase 8 Cognitive Action Router components
        from arova.core.models.router.ambiguity import AmbiguityRouterLLM
        self.ambiguity_router = AmbiguityRouterLLM(self.provider_manager, event_bus=event_bus)

    async def generate(self,
                       messages: List[Dict[str, Any]],
                       system_prompt: str = "",
                       depth: ReasoningDepth = ReasoningDepth.STANDARD,
                       budget: Optional[ReasoningBudget] = None,
                       capability: Capability = Capability.CHAT,
                       max_tokens: int = 1024) -> str:
        """Convenience method delegating to CapabilityRouter."""
        return await self.router.generate(
            messages=messages,
            system_prompt=system_prompt,
            capability=capability,
            max_tokens=max_tokens
        )

    async def resolve_cognitive_action(self, situation: 'CognitiveSituation') -> Capability:
        """
        Phase 8: Main entrypoint for Cognitive Routing.
        Evaluates the Situation and returns the optimal Cognitive Action (Capability).
        """
        from arova.core.models.router.scoring_engine import CognitiveScorer
        from arova.core.models.router.action_router import ActionRouter
        
        # 1. Base Heuristics & Environment Weighting
        vector = CognitiveScorer.evaluate(situation)
        
        # 2. Ambiguity resolution (LLM) if necessary
        old_conf = vector.confidence
        vector = await self.ambiguity_router.resolve(situation, vector)
        if vector.confidence != old_conf and self.router.event_bus:
            self.router.event_bus.emit("timeline", "create", {
                "category": "routing",
                "title": "Ambiguity Router Invoked",
                "description": f"Confidence improved from {old_conf:.2f} to {vector.confidence:.2f}",
                "source": "capability_router",
                "importance": 0.4,
                "correlation_id": situation.active_thread_id,
                "metadata": {"old_confidence": old_conf, "new_confidence": vector.confidence}
            })
            
        # 3. Final Cost-Optimized Action Selection
        action = ActionRouter.route(vector)
        
        if self.router.event_bus:
            self.router.event_bus.emit("timeline", "create", {
                "category": "routing",
                "title": f"Capability Selected: {action.name}",
                "description": f"Selected {action.name} based on optimized scoring.",
                "source": "action_router",
                "importance": 0.5,
                "correlation_id": situation.active_thread_id,
                "metadata": {
                    "action": action.name,
                    "confidence": vector.confidence,
                    "chat_score": vector.chat,
                    "reasoning_score": vector.reasoning,
                    "prompt": situation.prompt[:50] + "..."
                }
            })
            
        return action

    async def invoke_structured(self, 
                                messages: List[Dict[str, Any]], 
                                system_prompt: str, 
                                depth: ReasoningDepth = ReasoningDepth.STANDARD,
                                budget: Optional[ReasoningBudget] = None,
                                model: str = "") -> Dict[str, Any]:
        # Map ReasoningDepth to Capability
        cap = Capability.REASONING if depth in (ReasoningDepth.DEEP, ReasoningDepth.REFLECTIVE) else Capability.CHAT
        
        max_tokens = budget.max_tokens if budget else 512
        
        # Delegate to router
        import json
        text = await self.router.generate(messages, system_prompt, capability=cap, model=model, max_tokens=max_tokens)
        
        if text.strip() == "I'm currently unable to connect to my cognitive providers. Please check the network or provider settings.":
            raise RuntimeError("Cognitive providers offline")
        
        # Attempt to parse JSON if structured
        try:
            t = text.strip()
            if t.startswith("```json"): t = t[7:]
            if t.startswith("```"): t = t[3:]
            if t.endswith("```"): t = t[:-3]
            t = t.strip()
            return json.loads(t)
        except Exception:
            try:
                import ast
                return ast.literal_eval(t)
            except Exception:
                return {"content": text}

    async def invoke_stream(self, 
                            messages: List[Dict[str, Any]], 
                            system_prompt: str, 
                            depth: ReasoningDepth = ReasoningDepth.STANDARD, 
                            budget: Optional[ReasoningBudget] = None,
                            model: str = ""):
        cap = Capability.REASONING if depth in (ReasoningDepth.DEEP, ReasoningDepth.REFLECTIVE) else Capability.CHAT
        max_tokens = budget.max_tokens if budget else 4096
        
        async for chunk in self.router.stream(messages, system_prompt, capability=cap, model=model, max_tokens=max_tokens):
            yield chunk
