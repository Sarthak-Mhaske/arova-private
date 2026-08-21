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
            models_to_try = [
                "groq/compound-mini", "groq/compound", "openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.6-27b", "deepseek-r1-distill-llama-70b"
            ]

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
                logger.warning(f"GroqProvider: Model {current_model} failed ({e}). Trying next model candidate...")
                continue
                
        self.health.record_failure(str(last_err) if last_err else "All models failed")
        raise last_err or Exception("All models failed")

    async def stream(self, messages: List[Dict[str, Any]], system_prompt: str,
                     model: str = "", max_tokens: int = 512) -> AsyncGenerator[str, None]:
        registry = get_model_registry()
        models_to_try = [model] if model else [
            c.id for c in registry._candidates.get("groq", [])
        ]
        if not models_to_try:
            models_to_try = [
                "groq/compound-mini", "groq/compound", "openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.6-27b", "deepseek-r1-distill-llama-70b"
            ]

        streamed_text = ""
        last_err = None
        for current_model in models_to_try:
            t0 = time.time()
            try:
                current_messages = list(messages)
                current_sys_prompt = system_prompt
                if streamed_text.strip():
                    current_messages.append({"role": "assistant", "content": streamed_text})
                    current_sys_prompt += "\nIMPORTANT: The response was interrupted mid-stream due to model limits. CONTINUE generating seamlessly from where the assistant text ends. Do NOT repeat text already generated."

                # We need to yield from the generator, but we MUST wrap the first yield to catch immediate errors
                generator = self._adapter.invoke_stream(current_messages, current_sys_prompt, current_model, max_tokens)
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
                    streamed_text += first_chunk
                    yield first_chunk
                    
                async for chunk in generator:
                    streamed_text += chunk
                    yield chunk
                    
                return # Successfully completed
            except Exception as e:
                last_err = e
                err_str = str(e)
                delay_sec = 0.0
                if "429" in err_str or "rate limit" in err_str.lower():
                    import re, asyncio
                    match_ms = re.search(r"try again in (\d+(?:\.\d+)?)ms", err_str, re.IGNORECASE)
                    match_s = re.search(r"try again in (\d+(?:\.\d+)?)s", err_str, re.IGNORECASE)
                    if match_ms:
                        delay_sec = float(match_ms.group(1)) / 1000.0
                    elif match_s:
                        delay_sec = float(match_s.group(1))

                if 0.0 < delay_sec <= 2.5:
                    logger.info(f"GroqProvider: Model {current_model} 429 reset in {delay_sec:.2f}s. Sleeping before retry...")
                    await asyncio.sleep(delay_sec + 0.1)
                    try:
                        generator = self._adapter.invoke_stream(current_messages, current_sys_prompt, current_model, max_tokens)
                        first_chunk = None
                        try:
                            first_chunk = await generator.__anext__()
                        except StopAsyncIteration:
                            pass
                        if first_chunk is not None:
                            streamed_text += first_chunk
                            yield first_chunk
                        async for chunk in generator:
                            streamed_text += chunk
                            yield chunk
                        return
                    except Exception as retry_err:
                        logger.warning(f"GroqProvider: Retry on {current_model} failed ({retry_err}). Moving to next model candidate...")

                logger.warning(f"GroqProvider: Model {current_model} failed (partial length {len(streamed_text)}: {e}). Trying next model candidate...")
                continue
                
        self.health.record_failure(str(last_err) if last_err else "All models failed")
        raise last_err or Exception("All models failed")
