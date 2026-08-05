import logging
from typing import List, Dict, Any, AsyncGenerator, Optional
from arova.core.providers.base import CognitiveProvider
from arova.core.providers.capabilities import Capability
from arova.core.providers.manager import ProviderManager
from arova.core.providers.policy import RoutingPolicy
from arova.core.events import RuntimeEventBus

logger = logging.getLogger(__name__)


MODEL_NAMES = {
    "gemini": "Gemini 2.5 Pro",
    "anthropic": "Claude Sonnet 4",
    "openai": "GPT-5",
    "groq": "Groq Llama 3.3",
    "ollama": "Ollama (Local)",
    "lmstudio": "LM Studio (Local)",
    "mock": "Mock Model"
}

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
        self.last_execution_metadata: Dict[str, Any] = {}

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
            
            # Track consecutive fallbacks away from the primary
            if not hasattr(self, "_consecutive_fallbacks"):
                self._consecutive_fallbacks = {}
                
            count = self._consecutive_fallbacks.get(primary_name, 0) + 1
            self._consecutive_fallbacks[primary_name] = count
            
            # If the primary provider has failed consecutively 3 times, permanently change the default
            if count >= 3:
                try:
                    from arova.core.config.manager import get_config_manager
                    cfg_mgr = get_config_manager()
                    cfg = cfg_mgr.load_config()
                    cfg["preferred_provider"] = provider.name
                    cfg_mgr.save_config(cfg)
                    self._policy.set_presence_style(
                        self._policy._presence_style, 
                        self._policy._custom_routing, 
                        provider.name, 
                        self._policy._allow_fallback
                    )
                    logger.info(f"CapabilityRouter: Automatically switched preferred_provider to {provider.name} after 3 consecutive failures of {primary_name}")
                    self._consecutive_fallbacks.clear()
                    
                    self._emit("PROVIDER_CHANGED", {
                        "provider": provider.name,
                        "reason": f"{primary_name} failed consecutively, automatically switching default to {provider.name}"
                    })
                except Exception as e:
                    logger.error(f"CapabilityRouter: Failed to update default config: {e}")
            else:
                self._emit("PROVIDER_FALLBACK", {
                    "capability": capability.value,
                    "primary": primary_name,
                    "fallback": provider.name,
                    "reason": "primary_unhealthy"
                })
        elif primary_name and provider.name == primary_name:
            # Reset counter on success
            if hasattr(self, "_consecutive_fallbacks") and primary_name in self._consecutive_fallbacks:
                self._consecutive_fallbacks[primary_name] = 0

        return provider

    # ---- Public API (consumed by ModelOrchestrator) ----

    async def generate(self, messages: List[Dict[str, Any]], system_prompt: str,
                       capability: Capability = Capability.CHAT,
                       model: str = "", max_tokens: int = 512) -> str:
        import time
        start_t = time.time()
        order = self._policy.get_provider_order(capability)
        primary_name = order[0] if order else "gemini"
        requested_model = MODEL_NAMES.get(primary_name, primary_name)

        # Check if strict mode prevented provider resolution
        if not self._policy._allow_fallback:
            provider = self._providers.get(primary_name)
            if not provider or not provider.health.is_available:
                err_msg = f"⚠ Unable to connect using {requested_model} (Strict Mode enabled). Reason: API key missing or provider offline. Change model or enable Fallback in Settings."
                self.last_execution_metadata = {
                    "model_name": requested_model,
                    "requested_model": requested_model,
                    "provider_id": primary_name,
                    "latency_ms": 0,
                    "fallback": True,
                    "fallback_reason": f"Strict Mode prevented failover from unconfigured/unreachable {requested_model}."
                }
                return err_msg

        provider = self._resolve(capability)
        fallback_occ = (provider.name != primary_name)
        fallback_reason = f"{requested_model} was unavailable or key missing." if fallback_occ else None
        
        logger.info(f"CapabilityRouter: {capability.value} -> {provider.name}")
        try:
            result = await provider.generate(messages, system_prompt, model, max_tokens)
            elapsed_ms = int((time.time() - start_t) * 1000)
            self.last_execution_metadata = {
                "model_name": MODEL_NAMES.get(provider.name, provider.name),
                "requested_model": requested_model,
                "provider_id": provider.name,
                "latency_ms": elapsed_ms,
                "fallback": fallback_occ,
                "fallback_reason": fallback_reason
            }
            return result
        except Exception as e:
            logger.error(f"CapabilityRouter: {provider.name} failed for {capability.value}: {e}")
            provider.health.record_failure()
            if not self._policy._allow_fallback:
                return f"⚠ Request failed on {requested_model} (Strict Mode enabled): {e}"
            fallback = self._resolve(capability)
            if fallback.name != provider.name:
                self._emit("PROVIDER_FALLBACK", {
                    "capability": capability.value,
                    "primary": provider.name,
                    "fallback": fallback.name,
                    "reason": "runtime_failure"
                })
                try:
                    result = await fallback.generate(messages, system_prompt, model, max_tokens)
                    elapsed_ms = int((time.time() - start_t) * 1000)
                    self.last_execution_metadata = {
                        "model_name": MODEL_NAMES.get(fallback.name, fallback.name),
                        "requested_model": requested_model,
                        "provider_id": fallback.name,
                        "latency_ms": elapsed_ms,
                        "fallback": True,
                        "fallback_reason": f"{requested_model} returned an error ({e}). Fallback is enabled. {MODEL_NAMES.get(fallback.name, fallback.name)} generated this response."
                    }
                    return result
                except Exception as fb_e:
                    logger.error(f"CapabilityRouter: fallback generate {fallback.name} also failed: {fb_e}")
                    return "I'm currently unable to connect to my cognitive providers. Please check the network or provider settings."
            return "I'm currently unable to connect to my cognitive providers. Please check the network or provider settings."

    async def stream(self, messages: List[Dict[str, Any]], system_prompt: str,
                     capability: Capability = Capability.CHAT,
                     model: str = "", max_tokens: int = 512) -> AsyncGenerator[str, None]:
        import time
        start_t = time.time()
        order = self._policy.get_provider_order(capability)
        primary_name = order[0] if order else "gemini"
        requested_model = MODEL_NAMES.get(primary_name, primary_name)

        if not self._policy._allow_fallback:
            provider = self._providers.get(primary_name)
            if not provider or not provider.health.is_available:
                self.last_execution_metadata = {
                    "model_name": requested_model,
                    "requested_model": requested_model,
                    "provider_id": primary_name,
                    "latency_ms": 0,
                    "fallback": True,
                    "fallback_reason": f"Strict Mode prevented failover from unconfigured/unreachable {requested_model}."
                }
                yield f"⚠ Unable to connect using {requested_model} (Strict Mode enabled). Reason: API key missing or provider offline. Change model or enable Fallback in Settings."
                return

        provider = self._resolve(capability)
        fallback_occ = (provider.name != primary_name)
        fallback_reason = f"{requested_model} was unavailable or key missing. Fallback is enabled." if fallback_occ else None

        logger.info(f"CapabilityRouter: stream {capability.value} -> {provider.name}")
        try:
            async for chunk in provider.stream(messages, system_prompt, model, max_tokens):
                yield chunk
            elapsed_ms = int((time.time() - start_t) * 1000)
            self.last_execution_metadata = {
                "model_name": MODEL_NAMES.get(provider.name, provider.name),
                "requested_model": requested_model,
                "provider_id": provider.name,
                "latency_ms": elapsed_ms,
                "fallback": fallback_occ,
                "fallback_reason": fallback_reason
            }
        except Exception as e:
            logger.error(f"CapabilityRouter: stream {provider.name} failed: {e}")
            provider.health.record_failure()
            if not self._policy._allow_fallback:
                yield f"\n\n⚠ Stream failed on {requested_model} (Strict Mode enabled): {e}"
                return
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
                    elapsed_ms = int((time.time() - start_t) * 1000)
                    self.last_execution_metadata = {
                        "model_name": MODEL_NAMES.get(fallback.name, fallback.name),
                        "requested_model": requested_model,
                        "provider_id": fallback.name,
                        "latency_ms": elapsed_ms,
                        "fallback": True,
                        "fallback_reason": f"{requested_model} returned an error ({e}). Fallback is enabled. {MODEL_NAMES.get(fallback.name, fallback.name)} generated this response."
                    }
                except Exception as fb_e:
                    logger.error(f"CapabilityRouter: fallback stream {fallback.name} also failed: {fb_e}")
                    yield "\n\nI'm currently unable to connect to my cognitive providers. Please check the network or provider settings."
            else:
                yield "\n\nI'm currently unable to connect to my cognitive providers. Please check the network or provider settings."

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
