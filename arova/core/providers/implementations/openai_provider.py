import time
import json
import logging
import aiohttp
from typing import List, Dict, Any, Set, AsyncGenerator
from arova.core.providers.base import CognitiveProvider
from arova.core.providers.capabilities import Capability
from arova.core.models.registry import get_model_registry, ArovaCapability, QualityTier

logger = logging.getLogger(__name__)


class OpenAIProvider(CognitiveProvider):
    """
    Cloud inference via OpenAI API.
    Provides first-class chat, reasoning (o1/o3), vision, and embeddings support.
    """

    def __init__(self, api_key: str):
        super().__init__()
        self.api_key = api_key
        self.base_url = "https://api.openai.com/v1"

    @property
    def name(self) -> str:
        return "openai"

    @property
    def supported_capabilities(self) -> Set[Capability]:
        return {Capability.CHAT, Capability.REASONING, Capability.SUMMARIZATION, Capability.EMBEDDINGS}

    async def generate(self, messages: List[Dict[str, Any]], system_prompt: str,
                       model: str = "", max_tokens: int = 512) -> str:
        if not model:
            candidate = get_model_registry().resolve(ArovaCapability.AROVA_CAPABILITY_FAST_CHAT, QualityTier.BALANCED, provider_id="openai")
            model = candidate.id
        
        t0 = time.time()
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # Format messages with system prompt
        full_messages = []
        if system_prompt:
            full_messages.append({"role": "system", "content": system_prompt})
        full_messages.extend(messages)
        
        payload = {
            "model": model,
            "messages": full_messages,
            "max_tokens": max_tokens
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{self.base_url}/chat/completions", headers=headers, json=payload, timeout=30.0) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        latency = (time.time() - t0) * 1000
                        self.health.record_success(latency)
                        choices = data.get("choices", [])
                        if choices:
                            return choices[0].get("message", {}).get("content", "")
                        return ""
                    else:
                        err_text = await resp.text()
                        self.health.record_failure()
                        raise RuntimeError(f"OpenAI API error {resp.status}: {err_text}")
        except Exception as e:
            self.health.record_failure()
            raise

    async def stream(self, messages: List[Dict[str, Any]], system_prompt: str,
                     model: str = "", max_tokens: int = 512) -> AsyncGenerator[str, None]:
        if not model:
            candidate = get_model_registry().resolve(ArovaCapability.AROVA_CAPABILITY_FAST_CHAT, QualityTier.BALANCED, provider_id="openai")
            model = candidate.id

        t0 = time.time()
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        full_messages = []
        if system_prompt:
            full_messages.append({"role": "system", "content": system_prompt})
        full_messages.extend(messages)

        payload = {
            "model": model,
            "messages": full_messages,
            "max_tokens": max_tokens,
            "stream": True
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{self.base_url}/chat/completions", headers=headers, json=payload, timeout=30.0) as resp:
                    if resp.status != 200:
                        err = await resp.text()
                        self.health.record_failure()
                        raise RuntimeError(f"OpenAI stream error {resp.status}: {err}")
                    
                    async for line in resp.content:
                        line_str = line.decode("utf-8").strip()
                        if line_str.startswith("data: ") and line_str != "data: [DONE]":
                            try:
                                chunk = json.loads(line_str[6:])
                                delta = chunk.get("choices", [{}])[0].get("delta", {}).get("content", "")
                                if delta:
                                    yield delta
                            except Exception:
                                pass
                    latency = (time.time() - t0) * 1000
                    self.health.record_success(latency)
        except Exception as e:
            self.health.record_failure()
            raise

    async def embed(self, text: str) -> List[float]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "text-embedding-3-small",
            "input": text
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{self.base_url}/embeddings", headers=headers, json=payload, timeout=10.0) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("data", [{}])[0].get("embedding", [])
                raise RuntimeError(f"OpenAI embedding error {resp.status}")

    async def health_check(self):
        t0 = time.time()
        try:
            headers = {"Authorization": f"Bearer {self.api_key}"}
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/models", headers=headers, timeout=5.0) as resp:
                    if resp.status == 200:
                        latency = (time.time() - t0) * 1000
                        self.health.record_success(latency)
                    else:
                        self.health.record_failure()
        except Exception:
            self.health.record_failure()
        return self.health
