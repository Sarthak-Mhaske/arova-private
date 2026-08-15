import json
import logging
import requests
import asyncio
from typing import List, Dict, Any, AsyncGenerator
from arova.core.models.adapters.base import ModelAdapter
from arova.core.models.trust import TrustZone

class GroqAdapter(ModelAdapter):
    """
    Cloud inference via Groq for deep reasoning.
    """
    def __init__(self, api_key: str):
        self.api_key = api_key
        
    @property
    def trust_zone(self) -> TrustZone:
        return TrustZone.CLOUD
        
    @property
    def provider_name(self) -> str:
        return "groq"

    async def invoke(self, messages: List[Dict[str, Any]], system_prompt: str, model_name: str, max_tokens: int) -> str:
        loop = asyncio.get_running_loop()
        try:
            return await loop.run_in_executor(None, self._sync_call, messages, system_prompt, model_name, max_tokens, False, False)
        except Exception as e:
            logging.error(f"Groq API call failed: {e}")
            raise e

    async def invoke_structured(self, messages: List[Dict[str, Any]], system_prompt: str, model_name: str, max_tokens: int) -> Dict[str, Any]:
        loop = asyncio.get_running_loop()
        try:
            result_text = await loop.run_in_executor(None, self._sync_call, messages, system_prompt, model_name, max_tokens, False, True)
            
            # Parse JSON with robust extraction
            text = result_text.strip()
            if "```json" in text:
                text = text.split("```json", 1)[1].split("```", 1)[0].strip()
            elif "```" in text:
                text = text.split("```", 1)[1].split("```", 1)[0].strip()
            
            if "{" in text and "}" in text:
                first_brace = text.find("{")
                last_brace = text.rfind("}")
                text = text[first_brace:last_brace + 1].strip()

            return json.loads(text)
        except Exception as e:
            logging.error(f"Groq JSON call failed: {e}")
            raise e

    async def invoke_stream(self, messages: List[Dict[str, Any]], system_prompt: str, model_name: str, max_tokens: int) -> AsyncGenerator[str, None]:
        loop = asyncio.get_running_loop()
        queue = asyncio.Queue()
        
        def _sync_stream():
            try:
                for chunk in self._sync_call(messages, system_prompt, model_name, max_tokens, True):
                    loop.call_soon_threadsafe(queue.put_nowait, chunk)
                loop.call_soon_threadsafe(queue.put_nowait, None)
            except Exception as e:
                logging.error(f"Groq stream failed: {e}")
                loop.call_soon_threadsafe(queue.put_nowait, e)

        import threading
        threading.Thread(target=_sync_stream, daemon=True).start()
        
        while True:
            chunk = await queue.get()
            if isinstance(chunk, Exception):
                raise chunk
            if chunk is None:
                break
            if chunk:
                yield chunk

    def _sync_call(self, messages: List[Dict[str, Any]], system_prompt: str, model_name: str, max_tokens: int, stream: bool, structured: bool = False) -> Any:
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload_messages = [{"role": "system", "content": system_prompt}]
        for m in messages:
            payload_messages.append({"role": m["role"], "content": m["content"]})
            
        payload = {
            "model": model_name,
            "messages": payload_messages,
            "max_tokens": max_tokens,
            "temperature": 0.0,
            "stream": stream
        }
        
        # Only enable JSON mode when explicitly requested via invoke_structured().
        # NEVER auto-detect from system_prompt content — prompts containing "DO NOT OUTPUT JSON"
        # would falsely trigger this and force the LLM to return JSON on chat responses.
        if structured:
            payload["response_format"] = {"type": "json_object"}
        
        timeout_config = (10.0, 60.0) if stream else 30.0
        response = requests.post(url, headers=headers, json=payload, timeout=timeout_config, stream=stream)
        if response.status_code != 200:
            logging.error(f"Groq API error {response.status_code}: {response.text[:500]}")
        response.raise_for_status()
        
        if stream:
            def _gen():
                for line in response.iter_lines():
                    if line:
                        line = line.decode('utf-8')
                        if line.startswith("data: "):
                            data_str = line[6:]
                            if data_str == "[DONE]":
                                break
                            try:
                                chunk = json.loads(data_str)
                                delta = chunk["choices"][0]["delta"]
                                if "content" in delta:
                                    yield delta["content"]
                            except:
                                pass
            return _gen()
        else:
            return response.json()["choices"][0]["message"]["content"]
