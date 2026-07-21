import json
import logging
from typing import Dict, Any

from arova.core.cognition.situation import CognitiveSituation
from arova.core.models.router.schema import CapabilityVector
from arova.core.providers.capabilities import Capability
from arova.core.providers.manager import ProviderManager
from arova.core.models.registry import get_model_registry, ArovaCapability, QualityTier

logger = logging.getLogger(__name__)

class AmbiguityRouterLLM:
    """
    Layer 3: Triggered only when the heuristic CapabilityVector has low confidence.
    Calls an LLM (fallback chain) to output score *boosts* rather than final decisions.
    """
    
    def __init__(self, provider_manager: ProviderManager, event_bus=None):
        self.provider_manager = provider_manager
        self.event_bus = event_bus
        
        # Priority fallback chain
        self.router_fallback_chain = ["openai", "groq", "ollama"]

    async def resolve(self, situation: CognitiveSituation, current_vector: CapabilityVector) -> CapabilityVector:
        if current_vector.confidence >= 0.65:
            return current_vector
            
        logger.info("AmbiguityRouterLLM: Triggered due to low confidence (%.2f)", current_vector.confidence)
        
        system_prompt = f"""You are the Cognitive Action Router for Arova OS.
Analyze the user's situation and determine the necessary cognitive action.
You do NOT execute the action. You output a JSON object containing score boosts (-1.0 to 1.0) for capabilities.

Situation:
- Prompt: {situation.prompt}
- Room: {situation.room}
- Workspace: {situation.workspace}
- Attention: {situation.attention_state}

Return EXACTLY valid JSON mapping capabilities to float boosts. Example:
{{
    "chat": 0.1,
    "reasoning": 0.5
}}"""

        messages = [{"role": "user", "content": "Score boosts for situation."}]

        boosts = {}
        success = False
        attempted_providers = []
        
        for provider_name in self.router_fallback_chain:
            provider = self.provider_manager.get_provider(provider_name)
            if not provider or not provider.is_healthy():
                continue
                
            candidate = get_model_registry().resolve(ArovaCapability.AROVA_CAPABILITY_AMBIGUITY_ROUTING, QualityTier.CHEAP, provider_id=provider_name)
            model_name = candidate.id
            try:
                attempted_providers.append(provider_name)
                logger.info(f"AmbiguityRouterLLM: Attempting resolution via {provider_name} ({model_name} - {candidate.selection_reason})")
                
                # We request generate using the resolved model
                response = await provider.generate(messages, system_prompt=system_prompt, model=model_name, max_tokens=150)
                
                text = response.strip()
                if text.startswith("```json"): text = text[7:]
                if text.startswith("```"): text = text[3:]
                if text.endswith("```"): text = text[:-3]
                
                boosts = json.loads(text.strip())
                success = True
                
                # Emit fallback event if we didn't succeed on the first try
                if len(attempted_providers) > 1 and self.event_bus:
                    self.event_bus.emit("timeline", "create", {
                        "category": "routing",
                        "title": "Provider Fallback",
                        "description": f"Arova switched to {provider_name} because earlier providers failed.",
                        "source": "capability_router",
                        "importance": 0.8,
                        "correlation_id": situation.active_thread_id,
                        "metadata": {
                            "failed_providers": attempted_providers[:-1],
                            "successful_provider": provider_name
                        }
                    })
                break
                
            except Exception as e:
                logger.warning(f"AmbiguityRouterLLM: Failed on {provider_name}: {e}")
                continue
                
        if not success:
            logger.error("AmbiguityRouterLLM: All providers failed. Falling back to raw heuristics.")
            if self.event_bus:
                self.event_bus.emit("timeline", "create", {
                    "category": "routing",
                    "title": "Provider Fallback Failed",
                    "description": "All LLM providers failed. Falling back to pure heuristics.",
                    "source": "capability_router",
                    "importance": 1.0,
                    "correlation_id": situation.active_thread_id,
                    "metadata": {"failed_providers": attempted_providers}
                })
            return current_vector
            
        # Apply boosts
        vector = CapabilityVector(
            chat=max(0.0, current_vector.chat + float(boosts.get("chat", 0))),
            reasoning=max(0.0, current_vector.reasoning + float(boosts.get("reasoning", 0))),
            memory_recall=max(0.0, current_vector.memory_recall + float(boosts.get("memory_recall", 0))),
            memory_write=max(0.0, current_vector.memory_write + float(boosts.get("memory_write", 0))),
            tool_execution=max(0.0, current_vector.tool_execution + float(boosts.get("tool_execution", 0))),
            agent_launch=max(0.0, current_vector.agent_launch + float(boosts.get("agent_launch", 0))),
            vision=max(0.0, current_vector.vision + float(boosts.get("vision", 0))),
            search=max(0.0, current_vector.search + float(boosts.get("search", 0))),
            continuity_resume=max(0.0, current_vector.continuity_resume + float(boosts.get("continuity_resume", 0))),
            no_action=max(0.0, current_vector.no_action + float(boosts.get("no_action", 0)))
        )
        
        vector.recalculate_confidence()
        return vector
