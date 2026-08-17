import os
import time
import json
import logging
import asyncio
import urllib.request
import urllib.error
from typing import Dict, Any, List, Tuple
from arova.core.config.manager import get_config_manager

logger = logging.getLogger(__name__)

def _http_get_sync(url: str, headers: Dict[str, str] = None, timeout: float = 5.0) -> Tuple[int, str]:
    """Pure standard-library HTTP GET helper without external dependencies."""
    req_headers = {"User-Agent": "Arova/0.1.0"}
    if headers:
        req_headers.update(headers)
    req = urllib.request.Request(url, headers=req_headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.status, response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")
    except Exception as e:
        return 0, str(e)

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

        # 3. Check Gemini
        gemini_configured = False
        gemini_env = bool(os.environ.get("GEMINI_API_KEY", "").strip() or os.environ.get("GOOGLE_API_KEY", "").strip())
        gemini_saved = bool(saved_providers.get("gemini", {}).get("api_keys", []))
        if gemini_env or gemini_saved:
            gemini_configured = True

        results.append({
            "id": "gemini",
            "name": "Google Gemini",
            "available": gemini_configured,
            "configured": gemini_configured,
            "detected_automatically": gemini_env and not gemini_saved,
            "recommended": True
        })

        # 4. Check Anthropic
        anthropic_configured = False
        anthropic_env = bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())
        anthropic_saved = bool(saved_providers.get("anthropic", {}).get("api_keys", []))
        if anthropic_env or anthropic_saved:
            anthropic_configured = True

        results.append({
            "id": "anthropic",
            "name": "Anthropic",
            "available": anthropic_configured,
            "configured": anthropic_configured,
            "detected_automatically": anthropic_env and not anthropic_saved,
            "recommended": False
        })

        # 5. Check OpenRouter
        openrouter_configured = False
        openrouter_env = bool(os.environ.get("OPENROUTER_API_KEY", "").strip())
        openrouter_saved = bool(saved_providers.get("openrouter", {}).get("api_keys", []))
        if openrouter_env or openrouter_saved:
            openrouter_configured = True

        results.append({
            "id": "openrouter",
            "name": "OpenRouter",
            "available": openrouter_configured,
            "configured": openrouter_configured,
            "detected_automatically": openrouter_env and not openrouter_saved,
            "recommended": False
        })
        
        # 6. Check Ollama (Requires network ping)
        ollama_running = False
        ollama_host = saved_providers.get("ollama", {}).get("host", "http://localhost:11434")
        if not ollama_host:
            ollama_host = "http://localhost:11434"
        
        try:
            status, _ = await asyncio.to_thread(_http_get_sync, f"{ollama_host}/api/tags", timeout=1.5)
            if status == 200:
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
        has_cloud = groq_configured or openai_configured or gemini_configured or anthropic_configured or openrouter_configured
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
        t0 = time.time()
        api_key = api_key.strip()
        
        try:
            if provider_id == "gemini":
                url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
                status, _ = await asyncio.to_thread(_http_get_sync, url, timeout=5.0)
                latency = int((time.time() - t0) * 1000)
                if status == 200:
                    return {"success": True, "latency_ms": latency, "context_limit": "1M", "vision": True, "streaming": True}
                elif status in (400, 401, 403):
                    return {"success": False, "error": "Invalid API Key"}
                else:
                    return {"success": False, "error": f"HTTP {status}"}

            elif provider_id == "anthropic":
                headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01"}
                status, _ = await asyncio.to_thread(_http_get_sync, "https://api.anthropic.com/v1/models", headers=headers, timeout=5.0)
                latency = int((time.time() - t0) * 1000)
                if status == 200:
                    return {"success": True, "latency_ms": latency, "context_limit": "200k", "vision": True, "streaming": True}
                elif status in (401, 403):
                    return {"success": False, "error": "Invalid API Key"}
                else:
                    return {"success": False, "error": f"HTTP {status}"}

            elif provider_id == "openrouter":
                headers = {"Authorization": f"Bearer {api_key}"}
                status, _ = await asyncio.to_thread(_http_get_sync, "https://openrouter.ai/api/v1/models", headers=headers, timeout=5.0)
                latency = int((time.time() - t0) * 1000)
                if status == 200:
                    return {"success": True, "latency_ms": latency, "context_limit": "128k", "vision": True, "streaming": True}
                elif status == 401:
                    return {"success": False, "error": "Invalid API Key"}
                else:
                    return {"success": False, "error": f"HTTP {status}"}

            elif provider_id == "groq":
                headers = {"Authorization": f"Bearer {api_key}"}
                status, _ = await asyncio.to_thread(_http_get_sync, "https://api.groq.com/openai/v1/models", headers=headers, timeout=5.0)
                latency = int((time.time() - t0) * 1000)
                if status == 200:
                    return {"success": True, "latency_ms": latency, "context_limit": "128k", "vision": False, "streaming": True}
                elif status == 401:
                    return {"success": False, "error": "Invalid API Key"}
                else:
                    return {"success": False, "error": f"HTTP {status}"}
                        
            elif provider_id == "openai":
                headers = {"Authorization": f"Bearer {api_key}"}
                status, _ = await asyncio.to_thread(_http_get_sync, "https://api.openai.com/v1/models", headers=headers, timeout=5.0)
                latency = int((time.time() - t0) * 1000)
                if status == 200:
                    return {"success": True, "latency_ms": latency, "context_limit": "128k", "vision": True, "streaming": True}
                elif status == 401:
                    return {"success": False, "error": "Invalid API Key"}
                else:
                    return {"success": False, "error": f"HTTP {status}"}
                        
            elif provider_id == "ollama":
                target_host = host if host else "http://localhost:11434"
                status, _ = await asyncio.to_thread(_http_get_sync, f"{target_host}/api/tags", timeout=3.0)
                latency = int((time.time() - t0) * 1000)
                if status == 200:
                    return {"success": True, "latency_ms": latency, "context_limit": "32k", "vision": False, "streaming": True}
                else:
                    return {"success": False, "error": f"Ollama unreachable (HTTP {status})"}

            elif provider_id == "lmstudio":
                target_host = host if host else "http://localhost:1234"
                status, _ = await asyncio.to_thread(_http_get_sync, f"{target_host}/v1/models", timeout=3.0)
                latency = int((time.time() - t0) * 1000)
                if status == 200:
                    return {"success": True, "latency_ms": latency, "context_limit": "32k", "vision": False, "streaming": True}
                else:
                    return {"success": False, "error": f"LM Studio unreachable (HTTP {status})"}
                        
            else:
                return {"success": False, "error": "Unknown provider"}
        except Exception as e:
            err_msg = str(e) or type(e).__name__
            return {"success": False, "error": f"Unreachable: {err_msg}"}
