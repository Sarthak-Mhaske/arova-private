import time
import logging
from typing import List, Dict, Any, Set, AsyncGenerator
from arova.core.providers.base import CognitiveProvider
from arova.core.providers.capabilities import Capability
from arova.core.models.adapters.groq import GroqAdapter
from arova.core.models.registry import get_model_registry, ArovaCapability, QualityTier

logger = logging.getLogger(__name__)


class GroqProvider(CognitiveProvider):
    """
    Cloud inference via Groq.
    Wraps the existing GroqAdapter with health telemetry and capability declaration.
    """

    def __init__(self, api_key: str):
        super().__init__()
        self._adapter = GroqAdapter(api_key=api_key)

    @property
    def name(self) -> str:
        return "groq"

    @property
    def supported_capabilities(self) -> Set[Capability]:
        return {Capability.CHAT, Capability.REASONING, Capability.SUMMARIZATION}

    async def generate(self, messages: List[Dict[str, Any]], system_prompt: str,
                       model: str = "", max_tokens: int = 512) -> str:
        if not model:
            candidate = get_model_registry().resolve(ArovaCapability.AROVA_CAPABILITY_FAST_CHAT, QualityTier.BALANCED, provider_id="groq")
            model = candidate.id
        t0 = time.time()
        try:
            result = await self._adapter.invoke_structured(messages, system_prompt, model, max_tokens)
            latency = (time.time() - t0) * 1000
            self.health.record_success(latency)
            if isinstance(result, dict):
                return result.get("content", result.get("error", str(result)))
            return str(result)
        except Exception as e:
            self.health.record_failure()
            raise

    async def stream(self, messages: List[Dict[str, Any]], system_prompt: str,
                     model: str = "", max_tokens: int = 512) -> AsyncGenerator[str, None]:
        if not model:
            candidate = get_model_registry().resolve(ArovaCapability.AROVA_CAPABILITY_FAST_CHAT, QualityTier.BALANCED, provider_id="groq")
            model = candidate.id
        t0 = time.time()
        try:
            async for chunk in self._adapter.invoke_stream(messages, system_prompt, model, max_tokens):
                yield chunk
            latency = (time.time() - t0) * 1000
            self.health.record_success(latency)
        except Exception as e:
            self.health.record_failure()
            raise
