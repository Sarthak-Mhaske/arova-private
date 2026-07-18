import os
import aiohttp
import logging
from typing import Dict, Any, List
from arova.core.config.manager import get_config_manager

logger = logging.getLogger(__name__)

class ProviderDiscovery:
    """
    Automated discovery of available cognitive engines.
    Detects local instances (Ollama) and cloud credentials (ENV or config.json).
    Used primarily during onboarding to create a magical first-run experience.
    """

    @classmethod
    async def run_discovery(cls) -> Dict[str, Any]:
        manager = get_config_manager()
        saved_providers = manager.load_providers()
        
        results = []
        
        # 1. Check Groq
        groq_configured = False
        groq_env = bool(os.environ.get("GROQ_API_KEY", "").strip())
        groq_saved = bool(saved_providers.get("groq", {}).get("api_keys", []))
        if groq_env or groq_saved:
            groq_configured = True
            
        results.append({
            "id": "groq",
            "name": "Groq",
            "available": groq_configured,
            "configured": groq_configured,
            "detected_automatically": groq_env and not groq_saved,
            "recommended": True
        })
        
        # 2. Check OpenAI
        openai_configured = False
        openai_env = bool(os.environ.get("OPENAI_API_KEY", "").strip())
        openai_saved = bool(saved_providers.get("openai", {}).get("api_keys", []))
        if openai_env or openai_saved:
            openai_configured = True
            
        results.append({
            "id": "openai",
            "name": "OpenAI",
            "available": openai_configured,
            "configured": openai_configured,
            "detected_automatically": openai_env and not openai_saved,
            "recommended": False
        })
        
        # 3. Check Ollama (Requires network ping)
        ollama_running = False
        ollama_host = saved_providers.get("ollama", {}).get("host", "http://localhost:11434")
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{ollama_host}/api/tags", timeout=aiohttp.ClientTimeout(total=1.0)) as resp:
                    if resp.status == 200:
                        ollama_running = True
        except Exception:
            pass
            
        results.append({
            "id": "ollama",
            "name": "Ollama",
            "available": ollama_running,
            "configured": ollama_running,
            "detected_automatically": ollama_running,
            "recommended": False
        })
        
        # Determine Recommendation
        has_cloud = groq_configured or openai_configured
        has_local = ollama_running
        
        if has_local and not has_cloud:
            recommended_style = "local"
        elif has_local and has_cloud:
            recommended_style = "hybrid"
        elif has_cloud and not has_local:
            recommended_style = "instant"
        else:
            recommended_style = "hybrid"  # Default fallback if nothing found
            
        return {
            "providers": results,
            "recommended_presence_style": recommended_style
        }

    @classmethod
    async def test_provider_connection(cls, provider_id: str, api_key: str, host: str = "") -> Dict[str, Any]:
        """
        Validate a provider connection before allowing the user to save it.
        """
        import time
        t0 = time.time()
        api_key = api_key.strip()
        
        try:
            async with aiohttp.ClientSession() as session:
                if provider_id == "groq":
                    headers = {"Authorization": f"Bearer {api_key}"}
                    async with session.get("https://api.groq.com/openai/v1/models", headers=headers, timeout=5.0) as resp:
                        latency = int((time.time() - t0) * 1000)
                        if resp.status == 200:
                            return {"success": True, "latency_ms": latency}
                        elif resp.status == 401:
                            return {"success": False, "error": "Invalid API Key"}
                        else:
                            return {"success": False, "error": f"HTTP {resp.status}"}
                            
                elif provider_id == "openai":
                    headers = {"Authorization": f"Bearer {api_key}"}
                    async with session.get("https://api.openai.com/v1/models", headers=headers, timeout=5.0) as resp:
                        latency = int((time.time() - t0) * 1000)
                        if resp.status == 200:
                            return {"success": True, "latency_ms": latency}
                        elif resp.status == 401:
                            return {"success": False, "error": "Invalid API Key"}
                        else:
                            return {"success": False, "error": f"HTTP {resp.status}"}
                            
                elif provider_id == "ollama":
                    target_host = host if host else "http://localhost:11434"
                    async with session.get(f"{target_host}/api/tags", timeout=3.0) as resp:
                        latency = int((time.time() - t0) * 1000)
                        if resp.status == 200:
                            return {"success": True, "latency_ms": latency}
                        else:
                            return {"success": False, "error": f"HTTP {resp.status}"}
                            
                else:
                    return {"success": False, "error": "Unknown provider"}
        except Exception as e:
            import traceback
            err_msg = str(e) or type(e).__name__
            return {"success": False, "error": f"Provider Unreachable: {err_msg}"}
