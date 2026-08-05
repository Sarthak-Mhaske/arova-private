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
        registry = get_model_registry()
        models_to_try = [model] if model else [
            c.id for c in registry._candidates.get("groq", [])
        ]
        if not models_to_try:
            models_to_try = ["llama-3.3-70b-versatile"]

        last_err = None
        for current_model in models_to_try:
            t0 = time.time()
            try:
                result = await self._adapter.invoke(messages, system_prompt, current_model, max_tokens)
                latency = (time.time() - t0) * 1000
                self.health.record_success(latency)
                return str(result)
            except Exception as e:
                last_err = e
                err_str = str(e).lower()
                if "429" in err_str or "rate limit" in err_str:
                    logger.warning(f"GroqProvider: Model {current_model} rate limited. Trying next model...")
                    continue
                # Not a rate limit, abort immediately
                break
                
        self.health.record_failure(str(last_err) if last_err else "All models failed")
        raise last_err or Exception("All models failed")

    async def stream(self, messages: List[Dict[str, Any]], system_prompt: str,
                     model: str = "", max_tokens: int = 512) -> AsyncGenerator[str, None]:
        registry = get_model_registry()
        models_to_try = [model] if model else [
            c.id for c in registry._candidates.get("groq", [])
        ]
        if not models_to_try:
            models_to_try = ["llama-3.3-70b-versatile"]

        last_err = None
        for current_model in models_to_try:
            t0 = time.time()
            try:
                # We need to yield from the generator, but we MUST wrap the first yield to catch immediate 429 errors
                generator = self._adapter.invoke_stream(messages, system_prompt, current_model, max_tokens)
                first_chunk = None
                try:
                    first_chunk = await generator.__anext__()
                except StopAsyncIteration:
                    pass
                except Exception as stream_err:
                    raise stream_err
                
                # If we get here, connection succeeded and we have a chunk
                latency = (time.time() - t0) * 1000
                self.health.record_success(latency)
                
                if first_chunk is not None:
                    yield first_chunk
                    
                async for chunk in generator:
                    yield chunk
                    
                return # Successfully completed
            except Exception as e:
                last_err = e
                err_str = str(e).lower()
                if "429" in err_str or "rate limit" in err_str:
                    logger.warning(f"GroqProvider: Model {current_model} rate limited during stream. Trying next model...")
                    continue
                break
                
        self.health.record_failure(str(last_err) if last_err else "All models failed")
        raise last_err or Exception("All models failed")
