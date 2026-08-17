import os
import time
import json
import logging
import asyncio
import ssl
from typing import Dict, Any, List, Tuple
from arova.core.config.manager import get_config_manager

logger = logging.getLogger(__name__)

def _http_get_sync(url: str, headers: Dict[str, str] = None, timeout: float = 7.0) -> Tuple[int, str]:
    """
    Ultra-resilient HTTP GET helper across Windows, macOS, and Linux.
    Uses `requests` (with bundled certifi Mozilla CAs) if available,
    with fallback to `urllib.request` using verified and unverified SSL contexts.
    """
    req_headers = {
        "User-Agent": "Arova/0.1.0",
        "Accept": "application/json, text/plain, */*"
    }
    if headers:
        req_headers.update(headers)

    # 1. Primary: Use requests (best SSL cert resolution on Windows / PyInstaller bundles)
    try:
        import requests
        try:
            resp = requests.get(url, headers=req_headers, timeout=timeout)
            return resp.status_code, resp.text
        except requests.exceptions.SSLError:
            # Fallback for corporate Windows SSL interception proxies
            try:
                resp = requests.get(url, headers=req_headers, timeout=timeout, verify=False)
                return resp.status_code, resp.text
            except Exception as e:
                return 0, str(e)
        except requests.exceptions.RequestException as e:
            if hasattr(e, 'response') and e.response is not None:
                return e.response.status_code, e.response.text
            return 0, str(e)
    except ImportError:
        pass

    # 2. Secondary: urllib.request with robust SSL context
    import urllib.request
    import urllib.error

    req = urllib.request.Request(url, headers=req_headers, method="GET")
    
    # Try with default system context
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.status, response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")
    except urllib.error.URLError as e:
        # If SSL certificate error on Windows, fallback to unverified SSL context
        try:
            ctx = ssl._create_unverified_context()
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as response:
                return response.status, response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e_inner:
            return e_inner.code, e_inner.read().decode("utf-8", errors="replace")
        except Exception as e_inner:
            return 0, str(e_inner)
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
        
        # 6. Check Ollama (Only if host is explicitly configured by user)
        ollama_running = False
        ollama_host = saved_providers.get("ollama", {}).get("host", "").strip()
        
        if ollama_host:
            try:
                status, _ = await asyncio.to_thread(_http_get_sync, f"{ollama_host}/api/tags", timeout=1.5)
                if status == 200:
                    ollama_running = True
                elif "localhost" in ollama_host:
                    alt_host = ollama_host.replace("localhost", "127.0.0.1")
                    alt_status, _ = await asyncio.to_thread(_http_get_sync, f"{alt_host}/api/tags", timeout=1.5)
                    if alt_status == 200:
                        ollama_running = True
            except Exception:
                pass
            
        results.append({
            "id": "ollama",
            "name": "Ollama",
            "available": ollama_running,
            "configured": bool(ollama_host and ollama_running),
            "detected_automatically": bool(ollama_host and ollama_running),
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
        api_key = (api_key or "").strip().strip("'").strip('"')
        provider_id = (provider_id or "").lower().strip()
        host = (host or "").strip()
        
        try:
            if provider_id == "gemini":
                if not api_key:
                    return {"success": False, "error": "Please enter a valid Gemini API Key (starts with AIza...)"}
                url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
                status, body = await asyncio.to_thread(_http_get_sync, url, timeout=7.0)
                latency = int((time.time() - t0) * 1000)
                if status == 200:
                    return {"success": True, "latency_ms": latency, "context_limit": "2M", "vision": True, "streaming": True}
                elif status in (400, 401, 403):
                    return {"success": False, "error": "Invalid Gemini API Key. Verify your key in Google AI Studio."}
                elif status == 429:
                    return {"success": True, "latency_ms": latency, "warning": "Rate limited, but key is valid"}
                else:
                    return {"success": False, "error": f"Gemini server error (HTTP {status})"}

            elif provider_id == "anthropic":
                if not api_key:
                    return {"success": False, "error": "Please enter an Anthropic API Key (starts with sk-ant-...)"}
                headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01"}
                status, body = await asyncio.to_thread(_http_get_sync, "https://api.anthropic.com/v1/models", headers=headers, timeout=7.0)
                latency = int((time.time() - t0) * 1000)
                if status == 200:
                    return {"success": True, "latency_ms": latency, "context_limit": "200k", "vision": True, "streaming": True}
                elif status in (401, 403):
                    return {"success": False, "error": "Invalid Anthropic API Key. Verify your key in Anthropic Console."}
                elif status == 429:
                    return {"success": True, "latency_ms": latency, "warning": "Rate limited, but key is valid"}
                else:
                    return {"success": False, "error": f"Anthropic server error (HTTP {status})"}

            elif provider_id == "openrouter":
                if not api_key:
                    return {"success": False, "error": "Please enter an OpenRouter API Key (starts with sk-or-...)"}
                headers = {"Authorization": f"Bearer {api_key}"}
                status, body = await asyncio.to_thread(_http_get_sync, "https://openrouter.ai/api/v1/auth/key", headers=headers, timeout=7.0)
                latency = int((time.time() - t0) * 1000)
                if status == 200:
                    return {"success": True, "latency_ms": latency, "context_limit": "128k", "vision": True, "streaming": True}
                elif status in (401, 403):
                    return {"success": False, "error": "Invalid OpenRouter API Key. Check openrouter.ai/keys."}
                elif status == 429:
                    return {"success": True, "latency_ms": latency, "warning": "Rate limited, but key is valid"}
                else:
                    return {"success": False, "error": f"OpenRouter server error (HTTP {status})"}

            elif provider_id == "groq":
                if not api_key:
                    return {"success": False, "error": "Please enter a Groq API Key (starts with gsk_...)"}
                headers = {"Authorization": f"Bearer {api_key}"}
                status, body = await asyncio.to_thread(_http_get_sync, "https://api.groq.com/openai/v1/models", headers=headers, timeout=7.0)
                latency = int((time.time() - t0) * 1000)
                if status == 200:
                    return {"success": True, "latency_ms": latency, "context_limit": "128k", "vision": False, "streaming": True}
                elif status in (401, 403):
                    return {"success": False, "error": "Invalid Groq API Key. Check console.groq.com/keys."}
                elif status == 429:
                    return {"success": True, "latency_ms": latency, "warning": "Rate limited, but key is valid"}
                else:
                    return {"success": False, "error": f"Groq server error (HTTP {status})"}
                        
            elif provider_id == "openai":
                if not api_key:
                    return {"success": False, "error": "Please enter an OpenAI API Key (starts with sk-...)"}
                headers = {"Authorization": f"Bearer {api_key}"}
                status, body = await asyncio.to_thread(_http_get_sync, "https://api.openai.com/v1/models", headers=headers, timeout=7.0)
                latency = int((time.time() - t0) * 1000)
                if status == 200:
                    return {"success": True, "latency_ms": latency, "context_limit": "128k", "vision": True, "streaming": True}
                elif status in (401, 403):
                    return {"success": False, "error": "Invalid OpenAI API Key. Check platform.openai.com/api-keys."}
                elif status == 429:
                    return {"success": True, "latency_ms": latency, "warning": "Rate limited / quota exceeded, but key is valid"}
                else:
                    return {"success": False, "error": f"OpenAI server error (HTTP {status})"}
                        
            elif provider_id == "ollama":
                if not host:
                    return {"success": False, "error": "Please enter your Ollama endpoint (e.g. http://127.0.0.1:11434)"}
                target_host = host
                status, _ = await asyncio.to_thread(_http_get_sync, f"{target_host}/api/tags", timeout=3.0)
                
                # If localhost failed, attempt 127.0.0.1 (common Windows IPv6 localhost resolution issue)
                if status != 200 and "localhost" in target_host:
                    alt_host = target_host.replace("localhost", "127.0.0.1")
                    status, _ = await asyncio.to_thread(_http_get_sync, f"{alt_host}/api/tags", timeout=3.0)
                
                latency = int((time.time() - t0) * 1000)
                if status == 200:
                    return {"success": True, "latency_ms": latency, "context_limit": "32k", "vision": False, "streaming": True}
                else:
                    return {"success": False, "error": f"Could not reach Ollama at {target_host}. Ensure Ollama is running ('ollama serve')."}

            elif provider_id == "lmstudio":
                if not host:
                    return {"success": False, "error": "Please enter your LM Studio endpoint (e.g. http://127.0.0.1:1234)"}
                target_host = host
                status, _ = await asyncio.to_thread(_http_get_sync, f"{target_host}/v1/models", timeout=3.0)
                if status != 200 and "localhost" in target_host:
                    alt_host = target_host.replace("localhost", "127.0.0.1")
                    status, _ = await asyncio.to_thread(_http_get_sync, f"{alt_host}/v1/models", timeout=3.0)
                    
                latency = int((time.time() - t0) * 1000)
                if status == 200:
                    return {"success": True, "latency_ms": latency, "context_limit": "32k", "vision": False, "streaming": True}
                else:
                    return {"success": False, "error": f"Could not reach LM Studio at {target_host}. Ensure LM Studio local server is started."}
                        
            else:
                return {"success": False, "error": f"Unknown provider '{provider_id}'"}
        except Exception as e:
            err_msg = str(e) or type(e).__name__
            return {"success": False, "error": f"Connection error: {err_msg}"}
