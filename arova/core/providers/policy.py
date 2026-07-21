import logging
from typing import Dict, List
from arova.core.providers.capabilities import Capability

logger = logging.getLogger(__name__)


# Each policy maps a Capability -> ordered list of provider names to try.
# The CapabilityRouter walks this list, skipping unhealthy providers.

ROUTING_POLICIES: Dict[str, Dict[Capability, List[str]]] = {
    "auto": {
        Capability.CHAT:           ["groq", "openrouter", "gemini", "anthropic", "openai", "ollama", "lmstudio"],
        Capability.REASONING:      ["anthropic", "openrouter", "openai", "gemini", "groq", "ollama", "lmstudio"],
        Capability.CODING:         ["anthropic", "openrouter", "openai", "groq", "gemini", "ollama", "lmstudio"],
        Capability.SUMMARIZATION:  ["gemini", "groq", "anthropic", "openai", "ollama", "lmstudio"],
        Capability.EMBEDDINGS:     ["openai", "ollama", "lmstudio"],
        Capability.VISION:         ["gemini", "openai", "anthropic", "ollama", "lmstudio"],
    },
    "coding": {
        Capability.CHAT:           ["anthropic", "openrouter", "openai", "groq", "ollama", "lmstudio"],
        Capability.REASONING:      ["anthropic", "openrouter", "openai", "groq", "ollama", "lmstudio"],
        Capability.CODING:         ["anthropic", "openrouter", "openai", "groq", "ollama", "lmstudio"],
        Capability.SUMMARIZATION:  ["anthropic", "gemini", "groq", "ollama", "lmstudio"],
        Capability.EMBEDDINGS:     ["openai", "ollama", "lmstudio"],
        Capability.VISION:         ["anthropic", "openai", "gemini", "ollama", "lmstudio"],
    },
    "instant": {
        Capability.CHAT:           ["groq", "gemini", "openrouter", "openai", "ollama", "lmstudio"],
        Capability.REASONING:      ["groq", "openrouter", "openai", "anthropic", "ollama", "lmstudio"],
        Capability.SUMMARIZATION:  ["groq", "gemini", "openai", "ollama", "lmstudio"],
        Capability.EMBEDDINGS:     ["ollama", "lmstudio", "openai"],
        Capability.VISION:         ["gemini", "openai", "ollama", "lmstudio"],
    },
    "hybrid": {
        Capability.CHAT:           ["groq", "ollama", "lmstudio", "openrouter"],
        Capability.REASONING:      ["anthropic", "openai", "groq", "ollama", "lmstudio"],
        Capability.SUMMARIZATION:  ["groq", "ollama", "lmstudio"],
        Capability.EMBEDDINGS:     ["ollama", "lmstudio"],
        Capability.VISION:         ["openai", "gemini", "ollama", "lmstudio"],
    },
    "local": {
        Capability.CHAT:           ["ollama", "lmstudio"],
        Capability.REASONING:      ["ollama", "lmstudio"],
        Capability.SUMMARIZATION:  ["ollama", "lmstudio"],
        Capability.EMBEDDINGS:     ["ollama", "lmstudio"],
        Capability.VISION:         ["ollama", "lmstudio"],
    },
}


class RoutingPolicy:
    """
    Translates a Presence Style (auto/coding/instant/hybrid/local/custom) into
    an ordered preference list of providers for each Capability.
    
    Presence Style -> RoutingPolicy -> CapabilityRouter -> Provider
    """

    def __init__(self, presence_style: str = "auto", custom_routing: Dict[str, str] = None):
        self._presence_style = presence_style
        self._custom_routing = custom_routing or {}
        
        self._policy = ROUTING_POLICIES.get(presence_style, ROUTING_POLICIES["auto"]).copy()
        
        if presence_style == "custom":
            self._apply_custom_routing()
            
        logger.info(f"RoutingPolicy: Active policy = '{presence_style}'")

    def _apply_custom_routing(self):
        """Overrides the primary provider for capabilities defined in custom_routing."""
        # Use auto as the base fallback strategy for custom
        base_policy = ROUTING_POLICIES["auto"]
        
        for cap in Capability:
            if cap.value in self._custom_routing:
                chosen_provider = self._custom_routing[cap.value]
                # Keep the base fallback list, but put the chosen provider first
                fallback = [p for p in base_policy.get(cap, []) if p != chosen_provider]
                self._policy[cap] = [chosen_provider] + fallback
            else:
                self._policy[cap] = base_policy.get(cap, ["ollama"])

    @property
    def presence_style(self) -> str:
        return self._presence_style

    def set_presence_style(self, style: str, custom_routing: Dict[str, str] = None):
        if style not in ROUTING_POLICIES and style != "custom":
            logger.warning(f"RoutingPolicy: Unknown style '{style}', defaulting to 'auto'.")
            style = "auto"
            
        self._presence_style = style
        if custom_routing is not None:
            self._custom_routing = custom_routing
            
        if style == "custom":
            self._apply_custom_routing()
        else:
            self._policy = ROUTING_POLICIES[style].copy()
            
        logger.info(f"RoutingPolicy: Switched to '{style}'")

    def get_provider_order(self, capability: Capability) -> List[str]:
        """Return the ordered list of provider names for a given capability under the active policy."""
        return self._policy.get(capability, ["ollama"])
