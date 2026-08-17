import logging
from typing import List, Dict, Any, AsyncGenerator, Optional
from arova.core.providers.base import CognitiveProvider
from arova.core.providers.capabilities import Capability
from arova.core.providers.manager import ProviderManager
from arova.core.providers.policy import RoutingPolicy
from arova.core.events import RuntimeEventBus

logger = logging.getLogger(__name__)


MODEL_NAMES = {
    "groq": "GPT OSS 120B / Qwen 3.6 / Llama 3.3 (Groq LPU)",
    "gemini": "Gemini 3.1 Pro / 3.7 Flash (Google AI)",
    "anthropic": "Claude Sonnet 5 / Fable 5 (Anthropic)",
    "openai": "GPT-5.6 Sol / o3 (OpenAI)",
    "openrouter": "Qwen 3 / DeepSeek R1 (OpenRouter)",
    "ollama": "GPT OSS 120B / Qwen 3 (Local Ollama)",
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

    def _resolve(self, capability: Capability, exclude: Optional[List[str]] = None) -> CognitiveProvider:
        """
        Walk the policy's preferred provider order for the requested capability.
        Return the first healthy provider not in exclude. Emit PROVIDER_FALLBACK if we had to skip.
        """
        order = self._policy.get_provider_order(capability)
        primary_name = order[0] if order else None

        provider = self._providers.get_for_capability(capability, order, exclude=exclude)

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
                       model: str = "", max_tokens: int = 4096) -> str:
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
            provider.health.record_failure(str(e))
            if not self._policy._allow_fallback:
                return f"⚠ Request failed on {requested_model} (Strict Mode enabled): {e}"
            fallback = self._resolve(capability, exclude=[provider.name])
            if fallback.name != provider.name and fallback.name != "mock":
                self._emit("PROVIDER_FALLBACK", {
                    "capability": capability.value,
                    "primary": provider.name,
                    "fallback": fallback.name,
                    "reason": f"runtime_failure: {e}"
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
                     model: str = "", max_tokens: int = 4096) -> AsyncGenerator[str, None]:
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

        streamed_text = ""
        logger.info(f"CapabilityRouter: stream {capability.value} -> {provider.name}")
        try:
            async for chunk in provider.stream(messages, system_prompt, model, max_tokens):
                streamed_text += chunk
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
            logger.error(f"CapabilityRouter: stream {provider.name} failed (partial length {len(streamed_text)}): {e}")
            provider.health.record_failure(str(e))
            if not self._policy._allow_fallback:
                yield f"\n\n⚠ Stream failed on {requested_model} (Strict Mode enabled): {e}"
                return
            fallback = self._resolve(capability, exclude=[provider.name])
            if fallback.name != provider.name and fallback.name != "mock":
                self._emit("PROVIDER_FALLBACK", {
                    "capability": capability.value,
                    "primary": provider.name,
                    "fallback": fallback.name,
                    "reason": f"stream_failure: {e}"
                })
                try:
                    fallback_messages = list(messages)
                    fallback_sys_prompt = system_prompt
                    if streamed_text.strip():
                        fallback_messages.append({"role": "assistant", "content": streamed_text})
                        fallback_sys_prompt += "\nIMPORTANT: The assistant response was interrupted mid-stream. CONTINUE generating seamlessly from where the assistant message ends. Do NOT repeat text already generated."

                    async for chunk in fallback.stream(fallback_messages, fallback_sys_prompt, model, max_tokens):
                        yield chunk
                    elapsed_ms = int((time.time() - start_t) * 1000)
                    self.last_execution_metadata = {
                        "model_name": MODEL_NAMES.get(fallback.name, fallback.name),
                        "requested_model": requested_model,
                        "provider_id": fallback.name,
                        "latency_ms": elapsed_ms,
                        "fallback": True,
                        "fallback_reason": f"{requested_model} was interrupted mid-response. {MODEL_NAMES.get(fallback.name, fallback.name)} seamlessly continued the response."
                    }
                except Exception as fb_e:
                    logger.error(f"CapabilityRouter: fallback stream {fallback.name} also failed: {fb_e}")
                    if not streamed_text:
                        yield "\n\nI'm currently unable to connect to my cognitive providers. Please check the network or provider settings."
            else:
                if not streamed_text:
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
