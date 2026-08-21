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
        registry = get_model_registry()
        models_to_try = [model] if model else [
            c.id for c in registry._candidates.get("openai", [])
        ]
        if not models_to_try:
            models_to_try = ["gpt-4o", "gpt-4o-mini", "o3-mini", "o1", "o1-mini", "gpt-4-turbo"]
        
        last_err = None
        for current_model in models_to_try:
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
                "model": current_model,
                "messages": full_messages,
                "max_tokens": max_tokens
            }
            
            try:
                from arova.core.providers.network_utils import get_aiohttp_connector
                connector = get_aiohttp_connector()
                async with aiohttp.ClientSession(connector=connector) as session:
                    async with session.post(f"{self.base_url}/chat/completions", headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=30)) as resp:
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
                            logger.warning(f"OpenAIProvider: Model {current_model} returned HTTP {resp.status}. Trying next candidate...")
                            last_err = RuntimeError(f"OpenAI API error {resp.status}: {err_text}")
                            continue
            except Exception as e:
                logger.warning(f"OpenAIProvider: Model {current_model} failed ({e}). Trying next candidate...")
                last_err = e
                continue
                
        err_msg = str(last_err) if last_err else "All models failed"
        self.health.record_failure(err_msg)
        raise last_err or Exception(err_msg)

    async def stream(self, messages: List[Dict[str, Any]], system_prompt: str,
                     model: str = "", max_tokens: int = 512) -> AsyncGenerator[str, None]:
        registry = get_model_registry()
        models_to_try = [model] if model else [
            c.id for c in registry._candidates.get("openai", [])
        ]
        if not models_to_try:
            models_to_try = ["gpt-4o", "gpt-4o-mini", "o3-mini", "o1", "o1-mini", "gpt-4-turbo"]

        last_err = None
        for current_model in models_to_try:
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
                "model": current_model,
                "messages": full_messages,
                "max_tokens": max_tokens,
                "stream": True
            }
    
            try:
                from arova.core.providers.network_utils import get_aiohttp_connector
                connector = get_aiohttp_connector()
                async with aiohttp.ClientSession(connector=connector) as session:
                    async with session.post(f"{self.base_url}/chat/completions", headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                        if resp.status == 200:
                            # Connection succeeded, we can read chunks
                            first_chunk_received = False
                            async for line in resp.content:
                                line = line.decode('utf-8').strip()
                                if line.startswith("data: ") and line != "data: [DONE]":
                                    try:
                                        data = json.loads(line[6:])
                                        choices = data.get("choices", [])
                                        if choices:
                                            delta = choices[0].get("delta", {}).get("content", "")
                                            if delta:
                                                if not first_chunk_received:
                                                    first_chunk_received = True
                                                    latency = (time.time() - t0) * 1000
                                                    self.health.record_success(latency)
                                                yield delta
                                    except json.JSONDecodeError:
                                        continue
                            if not first_chunk_received:
                                latency = (time.time() - t0) * 1000
                                self.health.record_success(latency)
                            return
                        else:
                            err_text = await resp.text()
                            logger.warning(f"OpenAIProvider: Model {current_model} stream returned HTTP {resp.status}. Trying next candidate...")
                            last_err = RuntimeError(f"OpenAI API error {resp.status}: {err_text}")
                            continue
            except Exception as e:
                logger.warning(f"OpenAIProvider: Model {current_model} stream failed ({e}). Trying next candidate...")
                last_err = e
                continue
                
        err_msg = str(last_err) if last_err else "All models failed"
        self.health.record_failure(err_msg)
        raise last_err or Exception(err_msg)

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
            async with session.post(f"{self.base_url}/embeddings", headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("data", [{}])[0].get("embedding", [])
                raise RuntimeError(f"OpenAI embedding error {resp.status}")

    async def health_check(self):
        t0 = time.time()
        try:
            headers = {"Authorization": f"Bearer {self.api_key}"}
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/models", headers=headers, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status == 200:
                        latency = (time.time() - t0) * 1000
                        self.health.record_success(latency)
                    else:
                        self.health.record_failure()
        except Exception:
            self.health.record_failure()
        return self.health
