import json
import logging
from typing import Dict, Any, List, Optional
import requests
from arova.core.config.loader import pick_groq_api_key
from arova.core.models.schema import ReasoningDepth, ReasoningBudget, ModelCapabilityProfile
from arova.core.models.registry import get_model_registry, ArovaCapability, QualityTier

class ModelRuntime:
    """
    Abstracts LLM calls, routes to appropriate models based on depth, and enforces budgets.
    """
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.api_key = pick_groq_api_key(config)

    def _select_model(self, depth: ReasoningDepth) -> str:
        if depth in (ReasoningDepth.DEEP, ReasoningDepth.REFLECTIVE):
            candidate = get_model_registry().resolve(ArovaCapability.AROVA_CAPABILITY_REASONING, QualityTier.PREMIUM)
        else:
            candidate = get_model_registry().resolve(ArovaCapability.AROVA_CAPABILITY_FAST_CHAT, QualityTier.BALANCED)
        return candidate.id

    async def generate(self,
                       messages: List[Dict[str, Any]],
                       system_prompt: str = "",
                       depth: ReasoningDepth = ReasoningDepth.STANDARD,
                       budget: Optional[ReasoningBudget] = None) -> str:
        """Convenience non-streaming text generation method."""
        import asyncio
        if budget is None:
            budget = ReasoningBudget()
        model_name = self._select_model(depth)
        loop = asyncio.get_running_loop()
        try:
            result_text = await loop.run_in_executor(
                None,
                self._sync_groq_call,
                messages,
                system_prompt,
                model_name,
                budget.max_tokens,
                False
            )
            return str(result_text)
        except Exception as e:
            logging.error(f"ModelRuntime.generate failed: {e}")
            raise e

    async def invoke_structured(self, 
                                messages: List[Dict[str, Any]], 
                                system_prompt: str, 
                                depth: ReasoningDepth = ReasoningDepth.STANDARD,
                                budget: Optional[ReasoningBudget] = None) -> Dict[str, Any]:
        """
        Calls the LLM and enforces JSON output.
        In a real implementation, this would be an async HTTP call.
        """
        if budget is None:
            budget = ReasoningBudget()
            
        model_name = self._select_model(depth)
        
        # Fallback loop (very naive for scaffold)
        retries = 2
        for attempt in range(retries):
            try:
                # We'll use a blocking requests call just for scaffolding the architecture
                # A production version uses aiohttp
                import asyncio
                loop = asyncio.get_running_loop()
                result_text = await loop.run_in_executor(
                    None, 
                    self._sync_groq_call, 
                    messages, 
                    system_prompt, 
                    model_name,
                    budget.max_tokens,
                    False # streaming
                )
                
                # Robust JSON extraction: handles codeblocks and conversational intro/outro text
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
            except json.JSONDecodeError as e:
                logging.warning(f"Failed to parse LLM JSON (Attempt {attempt+1}): {e}. Raw text: {result_text[:200]}")
                if attempt == retries - 1:
                    # Secondary attempt: try finding JSON object in raw un-stripped result_text
                    if "{" in result_text and "}" in result_text:
                        try:
                            sub = result_text[result_text.find("{"):result_text.rfind("}")+1]
                            return json.loads(sub)
                        except Exception:
                            pass
                    return {"content": result_text}
            except Exception as e:
                logging.error(f"ModelRuntime invocation failed: {e}")
                if 'result_text' in locals():
                    return {"content": result_text}
                return {"error": str(e)}

    async def invoke_stream(self, messages: List[Dict[str, Any]], system_prompt: str, depth: ReasoningDepth = ReasoningDepth.STANDARD, budget: Optional[ReasoningBudget] = None):
        """
        Yields sentence chunks as they are generated.
        """
        import asyncio
        if budget is None:
            budget = ReasoningBudget()
            
        model_name = self._select_model(depth)
        loop = asyncio.get_running_loop()
        
        # We will use a queue to pass chunks from the sync blocking generator to the async generator
        queue = asyncio.Queue()
        
        def _sync_stream():
            try:
                for chunk in self._sync_groq_call(messages, system_prompt, model_name, budget.max_tokens, True):
                    loop.call_soon_threadsafe(queue.put_nowait, chunk)
                loop.call_soon_threadsafe(queue.put_nowait, None) # EOF
            except Exception as e:
                logging.error(f"Sync stream failed: {e}")
                loop.call_soon_threadsafe(queue.put_nowait, None)

        import threading
        threading.Thread(target=_sync_stream, daemon=True).start()
        
        buffer = ""
        while True:
            chunk = await queue.get()
            if chunk is None:
                if buffer.strip():
                    yield buffer.strip()
                break
                
            buffer += chunk
            # Sentence chunking heuristic
            if any(p in buffer for p in [". ", "? ", "! ", "\n"]):
                # find the first sentence boundary
                for p in [". ", "? ", "! ", "\n"]:
                    if p in buffer:
                        idx = buffer.find(p) + len(p)
                        sentence = buffer[:idx].strip()
                        buffer = buffer[idx:]
                        if sentence:
                            yield sentence
                        break

    def _sync_groq_call(self, messages: List[Dict[str, Any]], system_prompt: str, model_name: str, max_tokens: int, stream: bool = False) -> Any:
        url = "https://api.groq.com/openai/v1/chat/completions"
        api_key = self.api_key
        if not api_key:
            try:
                from arova.core.config.manager import get_config_manager
                saved = get_config_manager().load_providers()
                keys = saved.get("groq", {}).get("api_keys", [])
                if keys and keys[0]:
                    api_key = keys[0]
            except Exception:
                pass

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        payload_messages = [{"role": "system", "content": system_prompt}]
        for m in messages:
            # Drop purely internal keys before sending to LLM
            clean = {"role": m["role"], "content": m["content"]}
            payload_messages.append(clean)
            
        payload = {
            "model": model_name,
            "messages": payload_messages,
            "max_tokens": max_tokens,
            "temperature": 0.0,
            "stream": stream
        }
        
        verify_arg = True
        try:
            import certifi
            verify_arg = certifi.where()
        except ImportError:
            pass

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=10.0, stream=stream, verify=verify_arg)
        except requests.exceptions.SSLError:
            response = requests.post(url, headers=headers, json=payload, timeout=10.0, stream=stream, verify=False)
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
            data = response.json()
            return data["choices"][0]["message"]["content"]
