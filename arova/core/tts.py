from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from typing import Any

def _resolve_binary(name: str) -> str | None:
    path = shutil.which(name)
    if path: return path
    local_bin = os.path.expanduser(f"~/.local/bin/{name}")
    if os.path.exists(local_bin) and os.access(local_bin, os.X_OK):
        return local_bin
    return None

def _command_exists(name: str) -> bool:
    return _resolve_binary(name) is not None

def _expand_path(path: str) -> str:
    return os.path.expanduser(path)

def detect_language_from_text(text: str) -> str:
    """
    Detects whether the text contains Hindi/Marathi (Devanagari script) or English.
    Devanagari Unicode range: \u0900-\u097F.
    """
    if not text:
        return "english"
    if any('\u0900' <= char <= '\u097F' for char in text):
        return "hindi"
    return "english"

def normalize_tts_language(language: str | None) -> str:
    if not language:
        return "english"
    lang = language.lower()
    if lang in ("en", "english"):
        return "english"
    if lang in ("hi", "hindi"):
        return "hindi"
    if lang in ("mr", "marathi"):
        return "marathi"
    return "english"

def add_leading_silence(audio_path: str, silence_ms: int, config: dict | None = None) -> dict[str, Any]:
    if silence_ms <= 0:
        return {"ok": True, "audio_path": audio_path, "error": None}
        
    if not _command_exists("ffmpeg"):
        return {"ok": False, "audio_path": audio_path, "error": "ffmpeg not found"}
        
    if not os.path.exists(audio_path):
        return {"ok": False, "audio_path": audio_path, "error": f"Audio file not found: {audio_path}"}
        
    # clamp silence
    silence_ms = max(0, min(2000, silence_ms))
    if silence_ms == 0:
        return {"ok": True, "audio_path": audio_path, "error": None}
        
    _, ext = os.path.splitext(audio_path)
    if not ext:
        ext = ".wav"
        
    fd, padded_path = tempfile.mkstemp(suffix=ext, prefix="arova_padded_")
    os.close(fd)
    
    delay_str = f"adelay={silence_ms}:all=1"
    cmd = ["ffmpeg", "-y", "-i", audio_path, "-af", delay_str, padded_path]
    
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=300.0)
        if res.returncode == 0 and os.path.exists(padded_path) and os.path.getsize(padded_path) > 0:
            return {
                "ok": True,
                "audio_path": padded_path,
                "error": None
            }
        else:
            if os.path.exists(padded_path):
                os.remove(padded_path)
            return {
                "ok": False,
                "audio_path": audio_path,
                "error": f"ffmpeg padding failed: {res.stderr.strip()}"
            }
    except Exception as e:
        if os.path.exists(padded_path):
            os.remove(padded_path)
        return {
            "ok": False,
            "audio_path": audio_path,
            "error": str(e)
        }

def get_edge_voice(config: dict[str, Any], language: str) -> str:
    tts_cfg = config.get("tts", {})
    edge_cfg = tts_cfg.get("edge", {}) if isinstance(tts_cfg, dict) else {}
    voices = edge_cfg.get("voices", {}) if isinstance(edge_cfg, dict) else {}
    
    default_voices = {
        "english": "en-US-AvaMultilingualNeural",
        "hindi": "hi-IN-SwaraNeural",
        "marathi": "hi-IN-SwaraNeural"
    }
    return voices.get(language) or default_voices.get(language, "en-US-AvaMultilingualNeural")

def get_piper_model(config: dict[str, Any], language: str) -> str | None:
    tts_cfg = config.get("tts", {})
    piper_cfg = tts_cfg.get("piper", {})
    if not piper_cfg.get("enabled", True):
        return None
    models = piper_cfg.get("models", {})
    path = models.get(language)
    if path:
        return _expand_path(path)
    return None

async def _edge_tts_async(text: str, voice: str, output_path: str):
    import edge_tts
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_path)

def synthesize_with_edge(text: str, config: dict[str, Any], language: str | None = None, output_path: str | None = None) -> dict[str, Any]:
    # Auto-detect language if not explicitly provided or if default english was passed for Devanagari text
    if not language or language == "english":
        detected = detect_language_from_text(text)
        if detected != "english":
            language = detected
    lang = normalize_tts_language(language)
    voice = get_edge_voice(config, lang)
        
    if not output_path:
        fd, output_path = tempfile.mkstemp(suffix=".mp3", prefix="arova_edge_")
        os.close(fd)
        
    try:
        import asyncio
        try:
            import edge_tts
        except ImportError:
            # Fallback to CLI binary if Python module not found
            binary_name = tts_cfg.get("edge", {}).get("binary", "edge-tts")
            binary = _resolve_binary(binary_name)
            if not binary:
                return {"ok": False, "engine": "edge", "audio_path": None, "error": "edge-tts not installed"}
            cmd = [binary, "--voice", voice, "--text", text, "--write-media", output_path]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=15.0)
            if res.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                return {"ok": True, "engine": "edge", "audio_path": output_path, "error": None}
            return {"ok": False, "engine": "edge", "audio_path": None, "error": res.stderr.strip()}

        # Native in-process Python async execution (no CLI subprocess overhead)
        new_loop = asyncio.new_event_loop()
        try:
            new_loop.run_until_complete(_edge_tts_async(text, voice, output_path))
        finally:
            new_loop.close()

        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            return {
                "ok": True,
                "engine": "edge",
                "audio_path": output_path,
                "error": None
            }
        else:
            return {
                "ok": False,
                "engine": "edge",
                "audio_path": None,
                "error": "Generated audio file is empty."
            }
    except Exception as e:
        if output_path and os.path.exists(output_path):
            try:
                os.remove(output_path)
            except OSError:
                pass
        return {
            "ok": False,
            "engine": "edge",
            "audio_path": None,
            "error": str(e)
        }

def synthesize_with_piper(text: str, config: dict[str, Any], language: str = "english", output_path: str | None = None) -> dict[str, Any]:
    tts_cfg = config.get("tts", {})
    piper_cfg = tts_cfg.get("piper", {})
    binary_name = piper_cfg.get("binary", "piper")
    binary = _resolve_binary(binary_name)

    if not binary:
        return {
            "ok": False,
            "engine": "piper",
            "audio_path": None,
            "error": f"Binary '{binary_name}' not found in PATH or ~/.local/bin."
        }
        
    model = get_piper_model(config, language)
    if not model:
        return {
            "ok": False,
            "engine": "piper",
            "audio_path": None,
            "error": f"No Piper model configured for language '{language}'."
        }
        
    if not os.path.exists(model):
        return {
            "ok": False,
            "engine": "piper",
            "audio_path": None,
            "error": f"Piper model file not found at '{model}'."
        }

    if not output_path:
        fd, output_path = tempfile.mkstemp(suffix=".wav", prefix="arova_piper_")
        os.close(fd)
        
    cmd = [binary, "--model", model, "--output_file", output_path]
    
    try:
        res = subprocess.run(cmd, input=text, capture_output=True, text=True, timeout=300.0)
        if res.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            return {
                "ok": True,
                "engine": "piper",
                "audio_path": output_path,
                "error": None
            }
        else:
            if os.path.exists(output_path):
                os.remove(output_path)
            return {
                "ok": False,
                "engine": "piper",
                "audio_path": None,
                "error": res.stderr.strip() or "Unknown error synthesizing with Piper."
            }
    except Exception as e:
        if output_path and os.path.exists(output_path):
            os.remove(output_path)
        return {
            "ok": False,
            "engine": "piper",
            "audio_path": None,
            "error": str(e)
        }

def speak_text(text: str, config: dict[str, Any], audio_manager: Any = None, language: str = "english", on_playback_start: Any | None = None) -> dict[str, Any]:
    if not text.strip():
        return {
            "ok": True,
            "engine": None,
            "player": None,
            "audio_path": None,
            "error": None
        }
        
    lang = normalize_tts_language(language)
    tts_cfg = config.get("tts", {})
    order = tts_cfg.get("engine_order", ["edge", "piper"])
    
    result = None
    for engine in order:
        if engine == "edge":
            result = synthesize_with_edge(text, config, lang)
        elif engine == "piper":
            result = synthesize_with_piper(text, config, lang)
            
        if result and result.get("ok"):
            break
            
    if not result or not result.get("ok"):
        return {
            "ok": False,
            "engine": None,
            "player": None,
            "audio_path": None,
            "error": result.get("error", "No engines available or all failed.") if result else "No engines configured."
        }
        
    audio_path = result["audio_path"]
    engine_used = result["engine"]
    
    silence_ms = int(tts_cfg.get("leading_silence_ms", 300))
    pad_res = add_leading_silence(audio_path, silence_ms, config)
    
    play_path = pad_res["audio_path"] if pad_res["ok"] else audio_path
    
    play_path = pad_res["audio_path"] if pad_res["ok"] else audio_path
    
    playback_ok = False
    player_used = "audio_session"
    
    if audio_manager:
        if on_playback_start:
            on_playback_start()
        # TTS gets TTS_RESPONSE priority (30)
        playback_ok = audio_manager.request_playback(play_path, priority=30)
        # Wait for audio to finish if using blocking speak_text for legacy loop
        # A true stream wouldn't block here, but we are doing a staged migration.
        if playback_ok:
            import time
            while audio_manager._active_playback_pid is not None:
                time.sleep(0.1)
    else:
        # Fallback if no manager injected yet
        if on_playback_start:
            on_playback_start()
        import subprocess
        try:
            subprocess.run(["pw-play", play_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            playback_ok = True
        except FileNotFoundError:
            try:
                subprocess.run(["paplay", play_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                playback_ok = True
            except FileNotFoundError:
                pass
                
    # Cleanup temp files
    try:
        if os.path.exists(audio_path):
            os.remove(audio_path)
        if pad_res["ok"] and pad_res["audio_path"] != audio_path and os.path.exists(pad_res["audio_path"]):
            os.remove(pad_res["audio_path"])
    except OSError:
        pass
        
    if playback_ok:
        return {
            "ok": True,
            "engine": engine_used,
            "player": player_used,
            "audio_path": audio_path,
            "error": None
        }
    else:
        return {
            "ok": False,
            "engine": engine_used,
            "player": None,
            "audio_path": audio_path,
            "error": "Playback failed."
        }
