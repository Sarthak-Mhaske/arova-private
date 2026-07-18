from typing import List, Dict, Any, Type
import logging
from arova.core.cognition.providers.base import ContextProvider, ContextFragment, ProviderCapability
from arova.core.config.awareness import AwarenessManager

class ProviderManager:
    """Manages the registration and polling of Context Providers."""
    
    def __init__(self, awareness_manager: AwarenessManager):
        self.awareness_manager = awareness_manager
        self._providers: Dict[str, ContextProvider] = {}
        
    def register(self, provider: ContextProvider):
        self._providers[provider.get_id()] = provider
        logging.info(f"Registered ContextProvider: {provider.get_name()} ({provider.get_id()})")
        
    def unregister(self, provider_id: str):
        if provider_id in self._providers:
            del self._providers[provider_id]
            logging.info(f"Unregistered ContextProvider: {provider_id}")
            
    def _is_provider_allowed(self, provider: ContextProvider) -> bool:
        """Checks if the provider is allowed by the active AwarenessPolicy."""
        policy = self.awareness_manager.policy
        if provider.capability == ProviderCapability.PRESENCE:
            return policy.presence.enabled
        elif provider.capability == ProviderCapability.CONTEXT:
            return policy.context.enabled
        elif provider.capability == ProviderCapability.DEEP_CONTEXT:
            return policy.deep_context.enabled
        elif provider.capability == ProviderCapability.VISION:
            return policy.vision.enabled
        return False
            
    def get_active_providers(self) -> List[ContextProvider]:
        """Returns providers that are both registered and permitted by policy."""
        active = []
        for p in self._providers.values():
            if self._is_provider_allowed(p):
                active.append(p)
        return active
        
    async def poll(self) -> List[ContextFragment]:
        """Polls all active providers for context fragments."""
        fragments = []
        for provider in self.get_active_providers():
            try:
                if await provider.detect():
                    frag = await provider.summarize()
                    if frag:
                        fragments.append(frag)
            except Exception as e:
                logging.error(f"Provider {provider.get_id()} failed during poll: {e}")
        return fragments
        
    async def get_visible_context(self) -> List[Dict[str, Any]]:
        """Returns exactly what Arova can see right now, formatted for the UI."""
        visible = []
        for provider in self.get_active_providers():
            try:
                if await provider.detect():
                    frag = await provider.summarize()
                    if frag:
                        visible.append({
                            "provider": provider.get_name(),
                            "activity": frag.activity_summary,
                            "source": frag.source_identity,
                            "confidence": frag.confidence
                        })
            except Exception as e:
                logging.error(f"Provider {provider.get_id()} failed during get_visible_context: {e}")
        return visible
