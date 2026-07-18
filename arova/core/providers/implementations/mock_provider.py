import logging
from typing import List, Dict, Any, Set, AsyncGenerator
from arova.core.providers.base import CognitiveProvider
from arova.core.providers.capabilities import Capability

logger = logging.getLogger(__name__)

MOCK_RESPONSE = "I currently have no inference provider available. My presence is still here — threads, memory, and continuity are intact — but I cannot generate new responses right now."


class MockProvider(CognitiveProvider):
    """
    First-class fallback provider.
    When all real providers are down, the room stays alive.
    Threads persist. Memory persists. Orb persists.
    Only cognition degrades gracefully.
    """

    @property
    def name(self) -> str:
        return "mock"

    @property
    def supported_capabilities(self) -> Set[Capability]:
        # Mock supports everything — it's the last resort
        return {Capability.CHAT, Capability.REASONING, Capability.SUMMARIZATION, Capability.EMBEDDINGS, Capability.VISION}

    async def generate(self, messages: List[Dict[str, Any]], system_prompt: str,
                       model: str = "", max_tokens: int = 512) -> str:
        logger.warning("MockProvider: Returning degraded response (no real provider available).")
        return MOCK_RESPONSE

    async def stream(self, messages: List[Dict[str, Any]], system_prompt: str,
                     model: str = "", max_tokens: int = 512) -> AsyncGenerator[str, None]:
        logger.warning("MockProvider: Streaming degraded response.")
        yield MOCK_RESPONSE

    async def embed(self, text: str) -> List[float]:
        # Return a zero vector so downstream doesn't crash
        return [0.0] * 384
