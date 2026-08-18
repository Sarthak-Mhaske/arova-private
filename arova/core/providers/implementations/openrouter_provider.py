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


class OpenRouterProvider(CognitiveProvider):
    """
    Unified multi-model inference via OpenRouter API.
    One API key grants access to hundreds of models across Groq, Anthropic, OpenAI, DeepSeek, and Qwen.
    Treats OpenRouter as a first-class plugin.
    """

    def __init__(self, api_key: str):
        super().__init__()
        self.api_key = api_key
        self.base_url = "https://openrouter.ai/api/v1"

    @property
    def name(self) -> str:
        return "openrouter"

    @property
    def supported_capabilities(self) -> Set[Capability]:
        return {Capability.CHAT, Capability.REASONING, Capability.SUMMARIZATION}

    async def generate(self, messages: List[Dict[str, Any]], system_prompt: str,
                       model: str = "", max_tokens: int = 1024) -> str:
        models_to_try = [model] if model else [
            "openai/gpt-5.6-sol", "anthropic/claude-sonnet-5", "google/gemini-3.1-pro", "google/gemini-3.7-flash", "deepseek/deepseek-r1", "meta-llama/llama-3.3-70b-instruct"
        ]

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": "https://arova.dev",
            "X-Title": "Arova Cognition Engine",
            "Content-Type": "application/json"
        }
        full_messages = []
        if system_prompt:
            full_messages.append({"role": "system", "content": system_prompt})
        full_messages.extend(messages)

        last_err = None
        for current_model in models_to_try:
            t0 = time.time()
            payload = {
                "model": current_model,
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
                            logger.warning(f"OpenRouterProvider: Model {current_model} returned {resp.status}. Trying next candidate...")
                            last_err = RuntimeError(f"OpenRouter API error {resp.status}: {err_text}")
            except Exception as e:
                logger.warning(f"OpenRouterProvider: Model {current_model} failed ({e}). Trying next candidate...")
                last_err = e

        self.health.record_failure(str(last_err) if last_err else "All OpenRouter models failed")
        raise last_err or Exception("All OpenRouter models failed")

    async def stream(self, messages: List[Dict[str, Any]], system_prompt: str,
                     model: str = "", max_tokens: int = 1024) -> AsyncGenerator[str, None]:
        models_to_try = [model] if model else [
            "openai/gpt-5.6-sol", "anthropic/claude-sonnet-5", "google/gemini-3.1-pro", "google/gemini-3.7-flash", "deepseek/deepseek-r1", "meta-llama/llama-3.3-70b-instruct"
        ]

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": "https://arova.dev",
            "X-Title": "Arova Cognition Engine",
            "Content-Type": "application/json"
        }
        full_messages = []
        if system_prompt:
            full_messages.append({"role": "system", "content": system_prompt})
        full_messages.extend(messages)

        last_err = None
        for current_model in models_to_try:
            t0 = time.time()
            payload = {
                "model": current_model,
                "messages": full_messages,
                "max_tokens": max_tokens,
                "stream": True
            }

            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(f"{self.base_url}/chat/completions", headers=headers, json=payload, timeout=30.0) as resp:
                        if resp.status != 200:
                            err = await resp.text()
                            logger.warning(f"OpenRouter stream {current_model} returned {resp.status}. Trying next model...")
                            last_err = RuntimeError(f"OpenRouter stream error {resp.status}: {err}")
                            continue

                        async for line in resp.content:
                            line_str = line.decode("utf-8").strip()
                            if line_str.startswith("data: ") and line_str != "data: [DONE]":
                                try:
                                    chunk = json.loads(line_str[6:])
                                    choices = chunk.get("choices", [])
                                    if choices:
                                        delta = choices[0].get("delta", {}).get("content", "")
                                        if delta:
                                            yield delta
                                except Exception:
                                    pass
                        latency = (time.time() - t0) * 1000
                        self.health.record_success(latency)
                        return
            except Exception as e:
                last_err = e
                continue

        self.health.record_failure(str(last_err) if last_err else "All OpenRouter stream models failed")
        raise last_err or Exception("All OpenRouter stream models failed")

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
