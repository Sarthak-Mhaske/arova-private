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


class GeminiProvider(CognitiveProvider):
    """
    Cloud inference via Google Gemini REST API.
    Provides generous free-tier chat, reasoning, vision, and long-context summarization.
    """

    def __init__(self, api_key: str):
        super().__init__()
        self.api_key = api_key
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models"

    @property
    def name(self) -> str:
        return "gemini"

    @property
    def supported_capabilities(self) -> Set[Capability]:
        return {Capability.CHAT, Capability.REASONING, Capability.SUMMARIZATION, Capability.VISION}

    async def generate(self, messages: List[Dict[str, Any]], system_prompt: str,
                       model: str = "", max_tokens: int = 1024) -> str:
        from arova.core.models.registry import get_model_registry
        registry = get_model_registry()
        models_to_try = [model] if model else [
            c.id for c in registry._candidates.get("gemini", [])
        ]
        if not models_to_try:
            models_to_try = ["gemini-3.1-pro", "gemini-3.7-flash", "gemini-3.6-flash", "gemini-2.0-flash", "gemini-1.5-pro"]

        # Gemini expects contents: [{parts: [{text: ...}]}] format
        contents = []
        if system_prompt:
            contents.append({"role": "user", "parts": [{"text": f"System Instructions:\n{system_prompt}"}]})
            contents.append({"role": "model", "parts": [{"text": "Understood."}]})

        for m in messages:
            role = "user" if m.get("role") in ("user", "system") else "model"
            content = m.get("content", "")
            if isinstance(content, str):
                contents.append({"role": role, "parts": [{"text": content}]})
            elif isinstance(content, list):
                parts = []
                for item in content:
                    if item.get("type") == "text":
                        parts.append({"text": item.get("text", "")})
                    elif item.get("type") == "image_url":
                        url = item.get("image_url", {}).get("url", "")
                        if url.startswith("data:image/"):
                            import re
                            match = re.match(r"data:(image/\w+);base64,(.*)", url)
                            if match:
                                parts.append({
                                    "inlineData": {
                                        "mimeType": match.group(1),
                                        "data": match.group(2)
                                    }
                                })
                if parts:
                    contents.append({"role": role, "parts": parts})

        last_err = None
        for current_model in models_to_try:
            t0 = time.time()
            url = f"{self.base_url}/{current_model}:generateContent?key={self.api_key}"
            payload = {
                "contents": contents,
                "generationConfig": {"maxOutputTokens": max_tokens}
            }

            try:
                from arova.core.providers.network_utils import get_aiohttp_connector
                connector = get_aiohttp_connector()
                async with aiohttp.ClientSession(connector=connector) as session:
                    async with session.post(url, json=payload, timeout=30.0) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            latency = (time.time() - t0) * 1000
                            self.health.record_success(latency)
                            candidates = data.get("candidates", [])
                            if candidates:
                                parts = candidates[0].get("content", {}).get("parts", [])
                                if parts:
                                    return parts[0].get("text", "")
                            return ""
                        else:
                            err_text = await resp.text()
                            logger.warning(f"GeminiProvider: Model {current_model} returned HTTP {resp.status}. Trying next candidate...")
                            last_err = RuntimeError(f"Gemini API error {resp.status}: {err_text}")
            except Exception as e:
                logger.warning(f"GeminiProvider: Model {current_model} failed ({e}). Trying next candidate...")
                last_err = e

        self.health.record_failure(str(last_err) if last_err else "All Gemini models failed")
        raise last_err or Exception("All Gemini models failed")

    async def stream(self, messages: List[Dict[str, Any]], system_prompt: str,
                     model: str = "", max_tokens: int = 1024) -> AsyncGenerator[str, None]:
        from arova.core.models.registry import get_model_registry
        registry = get_model_registry()
        models_to_try = [model] if model else [
            c.id for c in registry._candidates.get("gemini", [])
        ]
        if not models_to_try:
            models_to_try = ["gemini-3.1-pro", "gemini-3.7-flash", "gemini-3.6-flash", "gemini-2.0-flash", "gemini-1.5-pro"]

        contents = []
        if system_prompt:
            contents.append({"role": "user", "parts": [{"text": f"System Instructions:\n{system_prompt}"}]})
            contents.append({"role": "model", "parts": [{"text": "Understood."}]})
        for m in messages:
            role = "user" if m.get("role") in ("user", "system") else "model"
            contents.append({"role": role, "parts": [{"text": m.get("content", "")}]})

        last_err = None
        for current_model in models_to_try:
            t0 = time.time()
            url = f"{self.base_url}/{current_model}:streamGenerateContent?alt=sse&key={self.api_key}"
            payload = {"contents": contents, "generationConfig": {"maxOutputTokens": max_tokens}}

            try:
                from arova.core.providers.network_utils import get_aiohttp_connector
                connector = get_aiohttp_connector()
                async with aiohttp.ClientSession(connector=connector) as session:
                    async with session.post(url, json=payload, timeout=30.0) as resp:
                        if resp.status != 200:
                            err = await resp.text()
                            logger.warning(f"Gemini stream {current_model} returned {resp.status}. Trying next model...")
                            last_err = RuntimeError(f"Gemini stream error {resp.status}: {err}")
                            continue

                        chunk_yielded = False
                        async for line in resp.content:
                            line_str = line.decode("utf-8").strip()
                            if line_str.startswith("data: "):
                                try:
                                    chunk = json.loads(line_str[6:])
                                    cands = chunk.get("candidates", [])
                                    if cands:
                                        parts = cands[0].get("content", {}).get("parts", [])
                                        if parts and parts[0].get("text"):
                                            chunk_yielded = True
                                            yield parts[0]["text"]
                                except Exception:
                                    pass
                        latency = (time.time() - t0) * 1000
                        self.health.record_success(latency)
                        return
            except Exception as e:
                last_err = e
                continue

        self.health.record_failure(str(last_err) if last_err else "All Gemini stream models failed")
        raise last_err or Exception("All Gemini stream models failed")

    async def health_check(self):
        t0 = time.time()
        try:
            url = f"{self.base_url}?key={self.api_key}"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=5.0) as resp:
                    if resp.status == 200:
                        latency = (time.time() - t0) * 1000
                        self.health.record_success(latency)
                    else:
                        self.health.record_failure()
        except Exception:
            self.health.record_failure()
        return self.health
