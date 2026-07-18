import logging
from typing import List, Dict, Any, AsyncGenerator, Optional
from arova.core.providers.base import CognitiveProvider
from arova.core.providers.capabilities import Capability
from arova.core.providers.manager import ProviderManager
from arova.core.providers.policy import RoutingPolicy
from arova.core.events import RuntimeEventBus

logger = logging.getLogger(__name__)


class CapabilityRouter:
    """
    The central routing brain of Arova's inference layer.
    
    Architecture:
        IntentRuntime -> ModelOrchestrator -> CapabilityRouter
            -> RoutingPolicy (determines provider order from Presence Style)
            -> ProviderManager (selects healthy provider)
            -> CognitiveProvider (executes inference)
    
    Fallback is NEVER silent. Every degradation emits PROVIDER_FALLBACK.
    """

    def __init__(self, provider_manager: ProviderManager, routing_policy: RoutingPolicy,
                 event_bus: Optional[RuntimeEventBus] = None):
        self._providers = provider_manager
        self._policy = routing_policy
        self._event_bus = event_bus

    def _emit(self, event_type: str, payload: dict):
        if self._event_bus:
            self._event_bus.emit("providers", event_type, payload)

    def _resolve(self, capability: Capability) -> CognitiveProvider:
        """
        Walk the policy's preferred provider order for the requested capability.
        Return the first healthy provider. Emit PROVIDER_FALLBACK if we had to skip.
        """
        order = self._policy.get_provider_order(capability)
        primary_name = order[0] if order else None

        provider = self._providers.get_for_capability(capability, order)

        if provider.name == "mock":
            logger.warning(f"CapabilityRouter: ALL providers exhausted for {capability.value}. Using MockProvider.")
            self._emit("PROVIDER_FALLBACK", {
                "capability": capability.value,
                "primary": primary_name,
                "fallback": "mock",
                "reason": "all_providers_unavailable"
            })
        elif primary_name and provider.name != primary_name:
            logger.info(f"CapabilityRouter: Fallback for {capability.value}: {primary_name} -> {provider.name}")
            self._emit("PROVIDER_FALLBACK", {
                "capability": capability.value,
                "primary": primary_name,
                "fallback": provider.name,
                "reason": "primary_unhealthy"
            })

        return provider

    # ---- Public API (consumed by ModelOrchestrator) ----

    async def generate(self, messages: List[Dict[str, Any]], system_prompt: str,
                       capability: Capability = Capability.CHAT,
                       model: str = "", max_tokens: int = 512) -> str:
        provider = self._resolve(capability)
        logger.info(f"CapabilityRouter: {capability.value} -> {provider.name}")
        try:
            result = await provider.generate(messages, system_prompt, model, max_tokens)
            return result
        except Exception as e:
            logger.error(f"CapabilityRouter: {provider.name} failed for {capability.value}: {e}")
            provider.health.record_failure()
            # Try fallback on failure
            fallback = self._resolve(capability)
            if fallback.name != provider.name:
                self._emit("PROVIDER_FALLBACK", {
                    "capability": capability.value,
                    "primary": provider.name,
                    "fallback": fallback.name,
                    "reason": "runtime_failure"
                })
                try:
                    return await fallback.generate(messages, system_prompt, model, max_tokens)
                except Exception as fb_e:
                    logger.error(f"CapabilityRouter: fallback generate {fallback.name} also failed: {fb_e}")
                    return "I'm currently unable to connect to my cognitive providers. Please check the network or provider settings."
            return "I'm currently unable to connect to my cognitive providers. Please check the network or provider settings."

    async def stream(self, messages: List[Dict[str, Any]], system_prompt: str,
                     capability: Capability = Capability.CHAT,
                     model: str = "", max_tokens: int = 512) -> AsyncGenerator[str, None]:
        provider = self._resolve(capability)
        logger.info(f"CapabilityRouter: stream {capability.value} -> {provider.name}")
        try:
            async for chunk in provider.stream(messages, system_prompt, model, max_tokens):
                yield chunk
        except Exception as e:
            logger.error(f"CapabilityRouter: stream {provider.name} failed: {e}")
            provider.health.record_failure()
            fallback = self._resolve(capability)
            if fallback.name != provider.name:
                self._emit("PROVIDER_FALLBACK", {
                    "capability": capability.value,
                    "primary": provider.name,
                    "fallback": fallback.name,
                    "reason": "stream_failure"
                })
                try:
                    async for chunk in fallback.stream(messages, system_prompt, model, max_tokens):
                        yield chunk
                except Exception as fb_e:
                    logger.error(f"CapabilityRouter: fallback stream {fallback.name} also failed: {fb_e}")
                    yield "I'm currently unable to connect to my cognitive providers. Please check the network or provider settings."
            else:
                yield "I'm currently unable to connect to my cognitive providers. Please check the network or provider settings."

    async def embed(self, text: str, capability: Capability = Capability.EMBEDDINGS) -> List[float]:
        provider = self._resolve(capability)
        return await provider.embed(text)

    def get_active_routes(self) -> Dict[str, str]:
        """Return a snapshot of which provider is currently active for each capability."""
        routes = {}
        for cap in Capability:
            provider = self._resolve(cap)
            routes[cap.value] = provider.name
        return routes

    def get_health_summary(self) -> Dict[str, dict]:
        return self._providers.get_health_summary()
