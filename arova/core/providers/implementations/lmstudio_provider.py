import time
import logging
import aiohttp
from typing import List, Dict, Any, Set, AsyncGenerator
from arova.core.providers.base import CognitiveProvider
from arova.core.providers.capabilities import Capability

logger = logging.getLogger(__name__)


class LMStudioProvider(CognitiveProvider):
    """
    Local inference via LM Studio OpenAI-compatible HTTP API (http://localhost:1234/v1).
    Provides developers an alternative local transport alongside Ollama.
    """

    def __init__(self, host: str = "http://localhost:1234", default_model: str = "local-model"):
        super().__init__()
        self.host = host.rstrip("/")
        self.default_model = default_model

    @property
    def name(self) -> str:
        return "lmstudio"

    @property
    def supported_capabilities(self) -> Set[Capability]:
        return {Capability.CHAT, Capability.REASONING, Capability.SUMMARIZATION, Capability.STREAMING, Capability.JSON_MODE}

    async def generate(self, messages: List[Dict[str, Any]], system_prompt: str,
                       model: str = "", max_tokens: int = 512) -> str:
        target_model = model or self.default_model
        formatted = []
        if system_prompt:
            formatted.append({"role": "system", "content": system_prompt})
        formatted.extend(messages)

        payload = {
            "model": target_model,
            "messages": formatted,
            "max_tokens": max_tokens,
            "temperature": 0.3
        }

        t0 = time.time()
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.host}/v1/chat/completions",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=60)
                ) as resp:
                    if resp.status != 200:
                        err = await resp.text()
                        self.health.record_failure(f"HTTP {resp.status}: {err[:100]}")
                        raise RuntimeError(f"LM Studio API returned status {resp.status}: {err}")
                    data = await resp.json()
                    content = data["choices"][0]["message"]["content"]
                    latency = (time.time() - t0) * 1000
                    self.health.record_success(latency)
                    return content
        except Exception as e:
            self.health.record_failure(str(e))
            raise

    async def stream(self, messages: List[Dict[str, Any]], system_prompt: str,
                     model: str = "", max_tokens: int = 512) -> AsyncGenerator[str, None]:
        import json
        target_model = model or self.default_model
        formatted = []
        if system_prompt:
            formatted.append({"role": "system", "content": system_prompt})
        formatted.extend(messages)

        payload = {
            "model": target_model,
            "messages": formatted,
            "max_tokens": max_tokens,
            "temperature": 0.3,
            "stream": True
        }

        t0 = time.time()
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.host}/v1/chat/completions",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=60)
                ) as resp:
                    if resp.status != 200:
                        err = await resp.text()
                        self.health.record_failure(f"HTTP {resp.status}")
                        raise RuntimeError(f"LM Studio stream status {resp.status}: {err}")
                    async for line in resp.content:
                        line_str = line.decode("utf-8").strip()
                        if line_str.startswith("data: "):
                            data_part = line_str[6:].strip()
                            if data_part == "[DONE]":
                                break
                            try:
                                chunk_json = json.loads(data_part)
                                delta = chunk_json["choices"][0].get("delta", {})
                                if "content" in delta and delta["content"]:
                                    yield delta["content"]
                            except Exception:
                                continue
            latency = (time.time() - t0) * 1000
            self.health.record_success(latency)
        except Exception as e:
            self.health.record_failure(str(e))
            raise

    async def embed(self, text: str) -> List[float]:
        """Use LM Studio embeddings endpoint if available."""
        payload = {"model": self.default_model, "input": text}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.host}/v1/embeddings",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=15)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data["data"][0]["embedding"]
                    else:
                        return [0.0] * 1536
        except Exception as e:
            logger.error(f"LM Studio embedding failed: {e}")
            raise

    async def health_check(self):
        """Actively probe LM Studio HTTP server."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.host}/v1/models", timeout=aiohttp.ClientTimeout(total=2)) as resp:
                    if resp.status == 200:
                        self.health.available = True
                        self.health.status = "ok"
                    else:
                        self.health.available = False
                        self.health.status = f"HTTP {resp.status}"
        except Exception:
            self.health.available = False
            self.health.status = "unreachable / offline"
        return self.health
