import json
import logging
import requests
import asyncio
from typing import List, Dict, Any, AsyncGenerator
from arova.core.models.adapters.base import ModelAdapter
from arova.core.models.trust import TrustZone

class OllamaAdapter(ModelAdapter):
    """
    Local edge inference using Ollama HTTP API.
    """
    def __init__(self, host: str = "http://localhost:11434"):
        self.host = host
        
    @property
    def trust_zone(self) -> TrustZone:
        return TrustZone.LOCAL
        
    @property
    def provider_name(self) -> str:
        return "ollama"

    async def invoke_structured(self, messages: List[Dict[str, Any]], system_prompt: str, model_name: str, max_tokens: int) -> Dict[str, Any]:
        loop = asyncio.get_running_loop()
        try:
            result_text = await loop.run_in_executor(None, self._sync_call, messages, system_prompt, model_name, max_tokens, False)
            
            # Parse JSON
            text = result_text.strip()
            if text.startswith("```json"):
                text = text[7:]
            if text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]
                
            return json.loads(text.strip())
        except Exception as e:
            if "Connection refused" in str(e) or "Failed to establish a new connection" in str(e):
                logging.info(f"Ollama local provider on {self.host} is offline.")
                return {"error": f"Ollama provider on {self.host} is offline."}
            logging.error(f"Ollama JSON call failed: {e}")
            if 'result_text' in locals():
                return {"content": result_text}
            return {"error": str(e)}

    async def invoke_stream(self, messages: List[Dict[str, Any]], system_prompt: str, model_name: str, max_tokens: int) -> AsyncGenerator[str, None]:
        loop = asyncio.get_running_loop()
        queue = asyncio.Queue()
        
        def _sync_stream():
            try:
                for chunk in self._sync_call(messages, system_prompt, model_name, max_tokens, True):
                    loop.call_soon_threadsafe(queue.put_nowait, chunk)
                loop.call_soon_threadsafe(queue.put_nowait, None)
            except Exception as e:
                if "Connection refused" in str(e) or "Failed to establish a new connection" in str(e):
                    logging.info(f"Ollama local provider on {self.host} is offline.")
                else:
                    logging.error(f"Ollama stream failed: {e}")
                loop.call_soon_threadsafe(queue.put_nowait, e)


        import threading
        threading.Thread(target=_sync_stream, daemon=True).start()
        
        buffer = ""
        while True:
            chunk = await queue.get()
            if isinstance(chunk, Exception):
                raise chunk
            if chunk is None:
                if buffer.strip():
                    yield buffer.strip()
                break
                
            buffer += chunk
            if any(p in buffer for p in [". ", "? ", "! ", "\n"]):
                for p in [". ", "? ", "! ", "\n"]:
                    if p in buffer:
                        idx = buffer.find(p) + len(p)
                        sentence = buffer[:idx].strip()
                        buffer = buffer[idx:]
                        if sentence:
                            yield sentence
                        break

    def _sync_call(self, messages: List[Dict[str, Any]], system_prompt: str, model_name: str, max_tokens: int, stream: bool) -> Any:
        url = f"{self.host}/api/chat"
        
        payload_messages = [{"role": "system", "content": system_prompt}]
        for m in messages:
            payload_messages.append({"role": m["role"], "content": m["content"]})
            
        payload = {
            "model": model_name,
            "messages": payload_messages,
            "stream": stream,
            "options": {
                "num_predict": max_tokens,
                "temperature": 0.0
            }
        }
        
        response = requests.post(url, json=payload, stream=stream)
        response.raise_for_status()
        
        if stream:
            def _gen():
                for line in response.iter_lines():
                    if line:
                        chunk = json.loads(line)
                        yield chunk["message"]["content"]
            return _gen()
        else:
            return response.json()["message"]["content"]
