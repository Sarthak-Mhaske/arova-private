import asyncio
import sys
sys.path.append("/home/sarthak/arova")
from arova.core.config.manager import OSConfigManager
from arova.core.models.adapters.groq import GroqAdapter

async def test():
    cfg = OSConfigManager().load_providers()
    api_key = cfg.get("groq", {}).get("api_keys", [])[0]
    adapter = GroqAdapter(api_key=api_key)
    
    messages = [{"role": "user", "content": "hello"}]
    system = "You are a helpful AI. Return a JSON object with key 'response'."
    
    try:
        res = await adapter.invoke_structured(messages, system, "openai/gpt-oss-120b", 512)
        print("Result:", res)
    except Exception as e:
        print("Error:", e)

asyncio.run(test())
