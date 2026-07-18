import time
import logging
from typing import List, Dict, Any, Set, AsyncGenerator
from arova.core.providers.base import CognitiveProvider
from arova.core.providers.capabilities import Capability
from arova.core.models.adapters.ollama import OllamaAdapter

logger = logging.getLogger(__name__)


class OllamaProvider(CognitiveProvider):
    """
    Local inference via Ollama HTTP API.
    Maximum privacy — never leaves the machine.
    """

    def __init__(self, host: str = "http://localhost:11434", default_model: str = "llama3"):
        super().__init__()
        self._adapter = OllamaAdapter(host=host)
        self._default_model = default_model

    @property
    def name(self) -> str:
        return "ollama"

    @property
    def supported_capabilities(self) -> Set[Capability]:
        return {Capability.CHAT, Capability.REASONING, Capability.SUMMARIZATION, Capability.EMBEDDINGS}

    async def generate(self, messages: List[Dict[str, Any]], system_prompt: str,
                       model: str = "", max_tokens: int = 512) -> str:
        model = model or self._default_model
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
        model = model or self._default_model
        t0 = time.time()
        try:
            async for chunk in self._adapter.invoke_stream(messages, system_prompt, model, max_tokens):
                yield chunk
            latency = (time.time() - t0) * 1000
            self.health.record_success(latency)
        except Exception as e:
            self.health.record_failure()
            raise

    async def embed(self, text: str) -> List[float]:
        """Use Ollama's embedding endpoint."""
        import requests
        try:
            resp = requests.post(
                f"{self._adapter.host}/api/embeddings",
                json={"model": self._default_model, "prompt": text},
                timeout=10.0
            )
            resp.raise_for_status()
            return resp.json().get("embedding", [])
        except Exception as e:
            logger.error(f"Ollama embedding failed: {e}")
            raise

    async def health_check(self):
        """Actively probe Ollama daemon."""
        import aiohttp
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self._adapter.host}/api/tags", timeout=aiohttp.ClientTimeout(total=2)) as resp:
                    if resp.status == 200:
                        self.health.available = True
                    else:
                        self.health.available = False
        except Exception:
            self.health.available = False
        return self.health
