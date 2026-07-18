from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from typing import Any

def _command_exists(name: str) -> bool:
    return shutil.which(name) is not None

def _expand_path(path: str) -> str:
    return os.path.expanduser(path)

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
        
    fd, padded_path = tempfile.mkstemp(suffix=ext, prefix="hyprvoice_padded_")
    os.close(fd)
    
    # anullsrc approach: generate silence and concat
    # ffmpeg -y -i input -f lavfi -i anullsrc=d=0.3 -filter_complex "[1:a][0:a]concat=n=2:v=0:a=1[out]" -map "[out]" output
    # or adelay=300:all=1
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

def get_edge_voice(config: dict[str, Any], language: str) -> str | None:
    tts_cfg = config.get("tts", {})
    edge_cfg = tts_cfg.get("edge", {})
    if not edge_cfg.get("enabled", True):
        return None
    voices = edge_cfg.get("voices", {})
    return voices.get(language)

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

def synthesize_with_edge(text: str, config: dict[str, Any], language: str = "english", output_path: str | None = None) -> dict[str, Any]:
    tts_cfg = config.get("tts", {})
    edge_cfg = tts_cfg.get("edge", {})
    binary = edge_cfg.get("binary", "edge-tts")

    if not _command_exists(binary):
        return {
            "ok": False,
            "engine": "edge",
            "audio_path": None,
            "error": f"Binary '{binary}' not found in PATH."
        }
        
    voice = get_edge_voice(config, language)
    if not voice:
        return {
            "ok": False,
            "engine": "edge",
            "audio_path": None,
            "error": f"No Edge voice configured for language '{language}'."
        }
        
    if not output_path:
        fd, output_path = tempfile.mkstemp(suffix=".mp3", prefix="hyprvoice_edge_")
        os.close(fd)
        
    cmd = [binary, "--voice", voice, "--text", text, "--write-media", output_path]
    
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=300.0)
        if res.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            return {
                "ok": True,
                "engine": "edge",
                "audio_path": output_path,
                "error": None
            }
        else:
            if os.path.exists(output_path):
                os.remove(output_path)
            return {
                "ok": False,
                "engine": "edge",
                "audio_path": None,
                "error": res.stderr.strip() or "Unknown error synthesizing with Edge TTS."
            }
    except Exception as e:
        if output_path and os.path.exists(output_path):
            os.remove(output_path)
        return {
            "ok": False,
            "engine": "edge",
            "audio_path": None,
            "error": str(e)
        }

def synthesize_with_piper(text: str, config: dict[str, Any], language: str = "english", output_path: str | None = None) -> dict[str, Any]:
    tts_cfg = config.get("tts", {})
    piper_cfg = tts_cfg.get("piper", {})
    binary = piper_cfg.get("binary", "piper")

    if not _command_exists(binary):
        return {
            "ok": False,
            "engine": "piper",
            "audio_path": None,
            "error": f"Binary '{binary}' not found in PATH."
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
        fd, output_path = tempfile.mkstemp(suffix=".wav", prefix="hyprvoice_piper_")
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
