import logging
from typing import Dict, List
from arova.core.providers.capabilities import Capability

logger = logging.getLogger(__name__)


# Each policy maps a Capability -> ordered list of provider names to try.
# The CapabilityRouter walks this list, skipping unhealthy providers.

ROUTING_POLICIES: Dict[str, Dict[Capability, List[str]]] = {
    "auto": {
        Capability.CHAT:           ["groq", "gemini", "openai", "anthropic", "openrouter", "ollama", "lmstudio"],
        Capability.REASONING:      ["anthropic", "openai", "gemini", "groq", "openrouter", "ollama", "lmstudio"],
        Capability.CODING:         ["anthropic", "openai", "gemini", "groq", "openrouter", "ollama", "lmstudio"],
        Capability.SUMMARIZATION:  ["gemini", "groq", "anthropic", "openai", "openrouter", "ollama", "lmstudio"],
        Capability.EMBEDDINGS:     ["openai", "gemini", "ollama", "lmstudio"],
        Capability.VISION:         ["gemini", "openai", "anthropic", "openrouter", "ollama", "lmstudio"],
    },
    "coding": {
        Capability.CHAT:           ["anthropic", "openai", "gemini", "groq", "openrouter", "ollama", "lmstudio"],
        Capability.REASONING:      ["anthropic", "openai", "gemini", "groq", "openrouter", "ollama", "lmstudio"],
        Capability.CODING:         ["anthropic", "openai", "gemini", "groq", "openrouter", "ollama", "lmstudio"],
        Capability.SUMMARIZATION:  ["anthropic", "gemini", "openai", "groq", "openrouter", "ollama", "lmstudio"],
        Capability.EMBEDDINGS:     ["openai", "gemini", "ollama", "lmstudio"],
        Capability.VISION:         ["anthropic", "gemini", "openai", "openrouter", "ollama", "lmstudio"],
    },
    "instant": {
        Capability.CHAT:           ["groq", "gemini", "openai", "anthropic", "openrouter", "ollama", "lmstudio"],
        Capability.REASONING:      ["groq", "gemini", "openai", "anthropic", "openrouter", "ollama", "lmstudio"],
        Capability.CODING:         ["groq", "openai", "anthropic", "gemini", "openrouter", "ollama", "lmstudio"],
        Capability.SUMMARIZATION:  ["groq", "gemini", "openai", "anthropic", "openrouter", "ollama", "lmstudio"],
        Capability.EMBEDDINGS:     ["openai", "gemini", "ollama", "lmstudio"],
        Capability.VISION:         ["gemini", "openai", "anthropic", "openrouter", "ollama", "lmstudio"],
    },
    "hybrid": {
        Capability.CHAT:           ["groq", "gemini", "openai", "anthropic", "openrouter", "ollama", "lmstudio"],
        Capability.REASONING:      ["anthropic", "openai", "gemini", "groq", "openrouter", "ollama", "lmstudio"],
        Capability.CODING:         ["anthropic", "openai", "gemini", "groq", "openrouter", "ollama", "lmstudio"],
        Capability.SUMMARIZATION:  ["gemini", "groq", "openai", "anthropic", "openrouter", "ollama", "lmstudio"],
        Capability.EMBEDDINGS:     ["openai", "gemini", "ollama", "lmstudio"],
        Capability.VISION:         ["gemini", "openai", "anthropic", "openrouter", "ollama", "lmstudio"],
    },
    "local": {
        Capability.CHAT:           ["ollama", "lmstudio", "groq", "gemini", "openai", "anthropic", "openrouter"],
        Capability.REASONING:      ["ollama", "lmstudio", "anthropic", "openai", "gemini", "groq", "openrouter"],
        Capability.CODING:         ["ollama", "lmstudio", "anthropic", "openai", "gemini", "groq", "openrouter"],
        Capability.SUMMARIZATION:  ["ollama", "lmstudio", "gemini", "groq", "openai", "anthropic", "openrouter"],
        Capability.EMBEDDINGS:     ["ollama", "lmstudio", "openai", "gemini"],
        Capability.VISION:         ["ollama", "lmstudio", "gemini", "openai", "anthropic", "openrouter"],
    },
}


class RoutingPolicy:
    """
    Translates a Presence Style (auto/coding/instant/hybrid/local/custom) into
    an ordered preference list of providers for each Capability.
    
    If `preferred_provider` is set, it deterministically prioritizes it.
    If `allow_fallback` is False, it strictly returns only the preferred provider.
    """

    def __init__(self, 
                 presence_style: str = "auto", 
                 custom_routing: Dict[str, str] = None,
                 preferred_provider: str = None,
                 allow_fallback: bool = True):
        self._presence_style = presence_style
        self._custom_routing = custom_routing or {}
        self._preferred_provider = preferred_provider
        self._allow_fallback = allow_fallback
        
        self._build_policy()
        logger.info(f"RoutingPolicy initialized: style='{presence_style}', preferred='{preferred_provider}', fallback={allow_fallback}")

    def _build_policy(self):
        base_style = self._presence_style
        if base_style not in ROUTING_POLICIES and base_style != "custom":
            base_style = "auto"
            
        base_policy = ROUTING_POLICIES.get(base_style, ROUTING_POLICIES["auto"])
        self._policy = {}
        
        for cap in Capability:
            candidates = base_policy.get(cap, []).copy()
            
            # 1. Custom routing overrides specific capabilities
            if cap.value in self._custom_routing:
                chosen = self._custom_routing[cap.value]
                if chosen in candidates:
                    candidates.remove(chosen)
                candidates.insert(0, chosen)
                
            # 2. Global preferred provider deterministically takes priority (if supported for capability)
            if self._preferred_provider:
                if self._preferred_provider in candidates:
                    candidates.remove(self._preferred_provider)
                    candidates.insert(0, self._preferred_provider)
                
            # 3. Strict mode (no fallback)
            if not self._allow_fallback:
                primary = candidates[0] if candidates else None
                candidates = [primary] if primary else []
                
            self._policy[cap] = candidates

    @property
    def presence_style(self) -> str:
        return self._presence_style

    def set_presence_style(self, style: str, custom_routing: Dict[str, str] = None, preferred_provider: str = None, allow_fallback: bool = None):
        self._presence_style = style
        if custom_routing is not None:
            self._custom_routing = custom_routing
        if preferred_provider is not None:
            self._preferred_provider = preferred_provider
        if allow_fallback is not None:
            self._allow_fallback = allow_fallback
            
        self._build_policy()
        logger.info(f"RoutingPolicy: Switched to style '{style}' (preferred={self._preferred_provider}, fallback={self._allow_fallback})")

    def get_provider_order(self, capability: Capability) -> List[str]:
        """Return the ordered list of provider names for a given capability under the active policy."""
        return self._policy.get(capability, ["ollama"])
