import os
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

        # Groq
        groq_keys = providers_cfg.get("groq", {}).get("api_keys", [])
        groq_keys = [k for k in groq_keys if k]  # strip empty strings
        if not groq_keys:
            env_key = os.environ.get("GROQ_API_KEY", "").strip()
            if env_key:
                groq_keys = [env_key]
        if groq_keys:
            from arova.core.providers.implementations.groq_provider import GroqProvider
            self._providers["groq"] = GroqProvider(api_key=groq_keys[0])
            logger.info("ProviderManager: Registered Groq provider.")
        else:
            logger.warning("ProviderManager: No Groq key found. Groq not registered.")

        # OpenAI
        oai_keys = providers_cfg.get("openai", {}).get("api_keys", [])
        oai_keys = [k for k in oai_keys if k]  # strip empty strings
        if not oai_keys:
            env_key = os.environ.get("OPENAI_API_KEY", "").strip()
            if env_key:
                oai_keys = [env_key]
        if oai_keys:
            logger.info("ProviderManager: OpenAI key detected (provider stub registered).")

        # Ollama
        ollama_host = providers_cfg.get("ollama", {}).get("host", "http://localhost:11434")
        from arova.core.providers.implementations.ollama_provider import OllamaProvider
        self._providers["ollama"] = OllamaProvider(host=ollama_host)
        logger.info(f"ProviderManager: Registered Ollama at {ollama_host}.")
        
        active = [k for k in self._providers if k != "mock"]
        logger.info(f"ProviderManager: Active providers after reload: {active}")

    def get(self, name: str) -> Optional[CognitiveProvider]:
        return self._providers.get(name)

    def get_for_capability(self, capability: Capability, preferred_order: List[str]) -> CognitiveProvider:
        """
        Return the best healthy provider from the preferred_order list
        that supports the given capability.
        Falls back to MockProvider if nothing is available.
        """
        for provider_name in preferred_order:
            provider = self._providers.get(provider_name)
            if provider and capability in provider.supported_capabilities and provider.health.available:
                return provider

        # All preferred providers failed — try ANY healthy provider
        for provider in self._providers.values():
            if provider.name != "mock" and capability in provider.supported_capabilities and provider.health.available:
                return provider

        # Everything is dead
        return self._mock

    @property
    def all_providers(self) -> Dict[str, CognitiveProvider]:
        return dict(self._providers)

    def get_health_summary(self) -> Dict[str, dict]:
        return {name: p.health.to_dict() for name, p in self._providers.items() if name != "mock"}
