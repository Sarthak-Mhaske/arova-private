import time
import json
import logging
try:
    import aiohttp
except ImportError:
    aiohttp = None
from typing import List, Dict, Any, Set, AsyncGenerator
from arova.core.providers.base import CognitiveProvider
from arova.core.providers.capabilities import Capability
from arova.core.models.registry import get_model_registry, ArovaCapability, QualityTier

logger = logging.getLogger(__name__)


class AnthropicProvider(CognitiveProvider):
    """
    Cloud inference via Anthropic Messages API.
    Optimized for developer coding, deep reasoning, and precise structured output.
    """

    def __init__(self, api_key: str):
        super().__init__()
        self.api_key = api_key
        self.base_url = "https://api.anthropic.com/v1/messages"

    @property
    def name(self) -> str:
        return "anthropic"

    @property
    def supported_capabilities(self) -> Set[Capability]:
        return {Capability.CHAT, Capability.REASONING, Capability.SUMMARIZATION}

    async def generate(self, messages: List[Dict[str, Any]], system_prompt: str,
                       model: str = "", max_tokens: int = 1024) -> str:
        if not model:
            candidate = get_model_registry().resolve(ArovaCapability.AROVA_CAPABILITY_CODING, QualityTier.HIGH, provider_id="anthropic")
            model = candidate.id

        t0 = time.time()
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json"
        }

        # Anthropic requires messages in [{role, content}] format and top-level system parameter
        formatted_messages = []
        for m in messages:
            role = m.get("role", "user")
            if role == "system":
                continue
            formatted_messages.append({"role": role, "content": m.get("content", "")})

        payload = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": formatted_messages
        }
        if system_prompt:
            payload["system"] = system_prompt

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.base_url, headers=headers, json=payload, timeout=30.0) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        latency = (time.time() - t0) * 1000
                        self.health.record_success(latency)
                        content_list = data.get("content", [])
                        if content_list and isinstance(content_list, list):
                            return content_list[0].get("text", "")
                        return ""
                    else:
                        err_text = await resp.text()
                        self.health.record_failure()
                        raise RuntimeError(f"Anthropic API error {resp.status}: {err_text}")
        except Exception as e:
            self.health.record_failure()
            raise

    async def stream(self, messages: List[Dict[str, Any]], system_prompt: str,
                     model: str = "", max_tokens: int = 1024) -> AsyncGenerator[str, None]:
        if not model:
            candidate = get_model_registry().resolve(ArovaCapability.AROVA_CAPABILITY_CODING, QualityTier.HIGH, provider_id="anthropic")
            model = candidate.id

        t0 = time.time()
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json"
        }
        formatted_messages = [m for m in messages if m.get("role") != "system"]
        payload = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": formatted_messages,
            "stream": True
        }
        if system_prompt:
            payload["system"] = system_prompt

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.base_url, headers=headers, json=payload, timeout=30.0) as resp:
                    if resp.status != 200:
                        err = await resp.text()
                        self.health.record_failure()
                        raise RuntimeError(f"Anthropic stream error {resp.status}: {err}")

                    async for line in resp.content:
                        line_str = line.decode("utf-8").strip()
                        if line_str.startswith("data: "):
                            try:
                                chunk = json.loads(line_str[6:])
                                if chunk.get("type") == "content_block_delta":
                                    text = chunk.get("delta", {}).get("text", "")
                                    if text:
                                        yield text
                            except Exception:
                                pass
                    latency = (time.time() - t0) * 1000
                    self.health.record_success(latency)
        except Exception as e:
            self.health.record_failure()
            raise

    async def health_check(self):
        t0 = time.time()
        try:
            # Minimal probe
            headers = {"x-api-key": self.api_key, "anthropic-version": "2023-06-01", "Content-Type": "application/json"}
            payload = {"model": "claude-3-haiku-20240307", "max_tokens": 1, "messages": [{"role": "user", "content": "hi"}]}
            async with aiohttp.ClientSession() as session:
                async with session.post(self.base_url, headers=headers, json=payload, timeout=5.0) as resp:
                    if resp.status in (200, 400):  # Even 400 confirms API gateway reachable
                        latency = (time.time() - t0) * 1000
                        self.health.record_success(latency)
                    else:
                        self.health.record_failure()
        except Exception:
            self.health.record_failure()
        return self.health
