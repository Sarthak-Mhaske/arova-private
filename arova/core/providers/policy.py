import logging
from typing import Dict, List
from arova.core.providers.capabilities import Capability

logger = logging.getLogger(__name__)


# Each policy maps a Capability -> ordered list of provider names to try.
# The CapabilityRouter walks this list, skipping unhealthy providers.

ROUTING_POLICIES: Dict[str, Dict[Capability, List[str]]] = {
    "instant": {
        Capability.CHAT:           ["groq", "openai", "ollama"],
        Capability.REASONING:      ["groq", "openai", "ollama"],
        Capability.SUMMARIZATION:  ["groq", "openai", "ollama"],
        Capability.EMBEDDINGS:     ["ollama"],
        Capability.VISION:         ["openai", "ollama"],
    },
    "hybrid": {
        Capability.CHAT:           ["groq", "ollama"],
        Capability.REASONING:      ["openai", "groq", "ollama"],
        Capability.SUMMARIZATION:  ["groq", "ollama"],
        Capability.EMBEDDINGS:     ["ollama"],
        Capability.VISION:         ["openai", "ollama"],
    },
    "local": {
        Capability.CHAT:           ["ollama"],
        Capability.REASONING:      ["ollama"],
        Capability.SUMMARIZATION:  ["ollama"],
        Capability.EMBEDDINGS:     ["ollama"],
        Capability.VISION:         ["ollama"],
    },
}


class RoutingPolicy:
    """
    Translates a Presence Style (instant/hybrid/local/custom) into
    an ordered preference list of providers for each Capability.
    
    Presence Style -> RoutingPolicy -> CapabilityRouter -> Provider
    """

    def __init__(self, presence_style: str = "instant", custom_routing: Dict[str, str] = None):
        self._presence_style = presence_style
        self._custom_routing = custom_routing or {}
        
        self._policy = ROUTING_POLICIES.get(presence_style, ROUTING_POLICIES["instant"]).copy()
        
        if presence_style == "custom":
            self._apply_custom_routing()
            
        logger.info(f"RoutingPolicy: Active policy = '{presence_style}'")

    def _apply_custom_routing(self):
        """Overrides the primary provider for capabilities defined in custom_routing."""
        # Use hybrid as the base fallback strategy for custom
        base_policy = ROUTING_POLICIES["hybrid"]
        
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
            logger.warning(f"RoutingPolicy: Unknown style '{style}', defaulting to 'instant'.")
            style = "instant"
            
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
