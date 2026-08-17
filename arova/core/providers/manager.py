import os
import time
import logging
from typing import Dict, Optional, List
from arova.core.providers.base import CognitiveProvider
from arova.core.providers.capabilities import Capability
from arova.core.providers.implementations.mock_provider import MockProvider
from arova.core.config.manager import get_config_manager

logger = logging.getLogger(__name__)


class ProviderManager:
    """
    Instantiates and holds references to all configured CognitiveProviders.
    Reads from providers.json and environment variables.
    MockProvider is always registered as the ultimate fallback.
    """

    def __init__(self):
        self._providers: Dict[str, CognitiveProvider] = {}
        self._mock = MockProvider()
        self._providers["mock"] = self._mock
        self._discover_and_register()

    def _discover_and_register(self):
        """Auto-discover providers from config and environment. Clears stale registrations first."""
        manager = get_config_manager()
        providers_cfg = manager.load_providers()

        # Clear all non-mock providers before re-registering to avoid stale state
        stale = [k for k in list(self._providers.keys()) if k != "mock"]
        for k in stale:
            del self._providers[k]
        logger.info(f"ProviderManager: Cleared {stale} before re-discovery.")

        # 1. Groq
        groq_keys = providers_cfg.get("groq", {}).get("api_keys", [])
        groq_keys = [k for k in groq_keys if k]
        if not groq_keys:
            env_key = os.environ.get("GROQ_API_KEY", "").strip()
            if env_key:
                groq_keys = [env_key]
        if groq_keys:
            from arova.core.providers.implementations.groq_provider import GroqProvider
            self._providers["groq"] = GroqProvider(api_key=groq_keys[0])
            logger.info("ProviderManager: Registered Groq provider.")

        # 2. OpenAI
        oai_keys = providers_cfg.get("openai", {}).get("api_keys", [])
        oai_keys = [k for k in oai_keys if k]
        if not oai_keys:
            env_key = os.environ.get("OPENAI_API_KEY", "").strip()
            if env_key:
                oai_keys = [env_key]
        if oai_keys:
            from arova.core.providers.implementations.openai_provider import OpenAIProvider
            self._providers["openai"] = OpenAIProvider(api_key=oai_keys[0])
            logger.info("ProviderManager: Registered OpenAI provider.")

        # 3. Ollama (Only register if host is explicitly configured and not empty)
        ollama_host = providers_cfg.get("ollama", {}).get("host", "").strip()
        if ollama_host:
            from arova.core.providers.implementations.ollama_provider import OllamaProvider
            self._providers["ollama"] = OllamaProvider(host=ollama_host)
            logger.info(f"ProviderManager: Registered Ollama at {ollama_host}.")

        # 3b. LM Studio (Only register if host is explicitly configured and not empty)
        lmstudio_host = providers_cfg.get("lmstudio", {}).get("host", "").strip()
        if lmstudio_host:
            from arova.core.providers.implementations.lmstudio_provider import LMStudioProvider
            self._providers["lmstudio"] = LMStudioProvider(host=lmstudio_host)
            logger.info(f"ProviderManager: Registered LM Studio at {lmstudio_host}.")

        # 4. Anthropic
        ant_keys = providers_cfg.get("anthropic", {}).get("api_keys", [])
        ant_keys = [k for k in ant_keys if k]
        if not ant_keys:
            env_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
            if env_key:
                ant_keys = [env_key]
        if ant_keys:
            from arova.core.providers.implementations.anthropic_provider import AnthropicProvider
            self._providers["anthropic"] = AnthropicProvider(api_key=ant_keys[0])
            logger.info("ProviderManager: Registered Anthropic provider.")

        # 5. Google Gemini
        gem_keys = providers_cfg.get("gemini", {}).get("api_keys", [])
        gem_keys = [k for k in gem_keys if k]
        if not gem_keys:
            env_key = os.environ.get("GEMINI_API_KEY", "").strip() or os.environ.get("GOOGLE_API_KEY", "").strip()
            if env_key:
                gem_keys = [env_key]
        if gem_keys:
            from arova.core.providers.implementations.gemini_provider import GeminiProvider
            self._providers["gemini"] = GeminiProvider(api_key=gem_keys[0])
            logger.info("ProviderManager: Registered Google Gemini provider.")

        # 6. OpenRouter
        or_keys = providers_cfg.get("openrouter", {}).get("api_keys", [])
        or_keys = [k for k in or_keys if k]
        if not or_keys:
            env_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
            if env_key:
                or_keys = [env_key]
        if or_keys:
            from arova.core.providers.implementations.openrouter_provider import OpenRouterProvider
            self._providers["openrouter"] = OpenRouterProvider(api_key=or_keys[0])
            logger.info("ProviderManager: Registered OpenRouter provider.")

        active = [k for k in self._providers if k != "mock"]
        logger.info(f"ProviderManager: Active providers after reload: {active}")

    def get(self, name: str) -> Optional[CognitiveProvider]:
        return self._providers.get(name)

    def get_for_capability(self, capability: Capability, preferred_order: List[str], exclude: Optional[List[str]] = None) -> CognitiveProvider:
        """
        Return the best healthy provider from the preferred_order list
        that supports the given capability.
        Falls back to MockProvider if nothing is available.
        """
        exclude_set = set(exclude or [])
        for provider_name in preferred_order:
            if provider_name in exclude_set:
                continue
            provider = self._providers.get(provider_name)
            if provider and capability in provider.supported_capabilities and provider.health.is_available:
                return provider

        # All preferred providers failed — try ANY healthy provider
        for provider in self._providers.values():
            if provider.name not in exclude_set and provider.name != "mock" and capability in provider.supported_capabilities and provider.health.is_available:
                return provider

        # Everything is dead
        return self._mock

    @property
    def all_providers(self) -> Dict[str, CognitiveProvider]:
        return dict(self._providers)

    def get_health_summary(self) -> Dict[str, dict]:
        summary = {}
        for name, p in self._providers.items():
            if name == "mock":
                continue
            h_dict = p.health.to_dict()
            h_dict["advertised_capabilities"] = [cap.value for cap in p.advertised_capabilities.to_set()]
            summary[name] = h_dict
        return summary

    async def test_all_providers(self) -> Dict[str, dict]:
        """
        One-click verification probe across all registered non-mock providers.
        Sends a minimal probe/health check to verify live authentication, latency, and advertised capabilities.
        """
        results = {}
        for name, provider in self._providers.items():
            if name == "mock":
                continue
            try:
                import time as _time
                start_ts = _time.time()
                health_res = await provider.health_check()
                latency = round((_time.time() - start_ts) * 1000, 1)
                caps = provider.advertised_capabilities
                caps_dict = {
                    "chat": caps.chat,
                    "reasoning": caps.reasoning,
                    "vision": caps.vision,
                    "embeddings": caps.embeddings,
                    "streaming": caps.streaming,
                    "json_mode": caps.json_mode,
                    "tool_use": caps.tool_use
                }
                if health_res.available:
                    results[name] = {
                        "status": "ok",
                        "authentication": True,
                        "available": True,
                        "availability_pct": health_res.availability_pct,
                        "latency_ms": latency if health_res.latency_ms <= 0 else health_res.latency_ms,
                        "tags": provider.profile.tags,
                        "capabilities": caps_dict,
                        "message": f"✓ {name} (latency: {latency} ms)"
                    }
                else:
                    fail_reason = health_res.status if health_res.status != "ok" else (health_res.last_error or "unreachable / offline")
                    results[name] = {
                        "status": fail_reason,
                        "authentication": "401" not in fail_reason and "Invalid" not in fail_reason,
                        "available": False,
                        "availability_pct": health_res.availability_pct,
                        "latency_ms": 0.0,
                        "tags": provider.profile.tags,
                        "capabilities": caps_dict,
                        "message": f"✗ {name}: {fail_reason}"
                    }
            except Exception as e:
                provider.health.record_failure(str(e))
                caps = provider.advertised_capabilities
                results[name] = {
                    "status": f"error: {str(e)[:40]}",
                    "authentication": False,
                    "available": False,
                    "availability_pct": provider.health.availability_pct,
                    "latency_ms": 0.0,
                    "tags": provider.profile.tags,
                    "capabilities": {
                        "chat": caps.chat,
                        "reasoning": caps.reasoning,
                        "vision": caps.vision,
                        "embeddings": caps.embeddings,
                        "streaming": caps.streaming,
                        "json_mode": caps.json_mode,
                        "tool_use": caps.tool_use
                    },
                    "message": f"✗ {name}: {str(e)[:40]}"
                }
        return results
