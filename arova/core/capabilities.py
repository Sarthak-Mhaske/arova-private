import shutil

def check_python_capabilities() -> dict[str, bool]:
    res = {
        "yaml": False,
        "requests": False,
        "gtk": False,
        "openwakeword": False,
        "pyaudio": False,
        "numpy": False,
    }
    
    try:
        import yaml
        res["yaml"] = True
    except ImportError:
        pass
        
    try:
        import requests
        res["requests"] = True
    except ImportError:
        pass
        
    try:
        import gi
        gi.require_version("Gtk", "4.0")
        from gi.repository import Gtk
        res["gtk"] = True
    except (ImportError, ValueError):
        pass
        
    try:
        import openwakeword
        res["openwakeword"] = True
    except ImportError:
        pass
        
    try:
        import pyaudio
        res["pyaudio"] = True
    except ImportError:
        pass
        
    try:
        import numpy
        res["numpy"] = True
    except ImportError:
        pass
        
    return res

def check_command_capabilities() -> dict[str, bool]:
    cmds = [
        "parecord", "arecord", "ffmpeg",
        "notify-send", "xdg-open", "mpv", "paplay",
        "edge-tts", "piper"
    ]
    return {cmd: shutil.which(cmd) is not None for cmd in cmds}

def build_capability_report() -> dict:
    py_caps = check_python_capabilities()
    cmd_caps = check_command_capabilities()
    
    features = {}
    
    # Core LLM
    missing_core = []
    if not py_caps["requests"]: missing_core.append("requests")
    features["core_llm"] = {
        "ready": len(missing_core) == 0,
        "missing": missing_core
    }
    
    # Typed Chat
    features["typed_chat"] = {
        "ready": features["core_llm"]["ready"],
        "missing": list(missing_core)
    }
    
    # UI
    missing_ui = []
    if not py_caps["gtk"]: missing_ui.append("gtk")
    features["ui"] = {
        "ready": len(missing_ui) == 0,
        "missing": missing_ui
    }
    
    # Manual Voice
    missing_voice = list(missing_core)
    has_recorder = cmd_caps["parecord"] or cmd_caps["arecord"] or cmd_caps["ffmpeg"]
    if not has_recorder:
        missing_voice.append("parecord OR arecord OR ffmpeg")
    features["manual_voice"] = {
        "ready": len(missing_voice) == 0,
        "missing": missing_voice
    }
    
    # TTS
    missing_tts = []
    if not (cmd_caps["edge-tts"] or cmd_caps["piper"]):
        missing_tts.append("edge-tts OR piper")
    if not (cmd_caps["mpv"] or cmd_caps["paplay"]):
        missing_tts.append("mpv OR paplay")
    features["tts"] = {
        "ready": len(missing_tts) == 0,
        "missing": missing_tts
    }
    
    # Wake Word
    missing_wake = []
    if not py_caps["openwakeword"]: missing_wake.append("openwakeword")
    if not py_caps["pyaudio"]: missing_wake.append("pyaudio")
    if not py_caps["numpy"]: missing_wake.append("numpy")
    features["wake_word"] = {
        "ready": len(missing_wake) == 0,
        "missing": missing_wake
    }
    
    # UI Assistant
    missing_assistant = []
    if not features["ui"]["ready"]: missing_assistant.extend(features["ui"]["missing"])
    if not features["manual_voice"]["ready"]: missing_assistant.extend(features["manual_voice"]["missing"])
    if not features["wake_word"]["ready"]: missing_assistant.extend(features["wake_word"]["missing"])
    if not features["tts"]["ready"]: missing_assistant.extend(features["tts"]["missing"])
    
    # deduplicate missing_assistant
    missing_assistant = list(dict.fromkeys(missing_assistant))
    
    features["ui_assistant"] = {
        "ready": len(missing_assistant) == 0,
        "missing": missing_assistant
    }
    
    return {
        "python": py_caps,
        "commands": cmd_caps,
        "features": features
    }

def format_capability_report(report: dict) -> str:
    lines = ["HyprVoice V2 Capability Report\n"]
    
    lines.append("Feature readiness:")
    for feature, details in report["features"].items():
        status = "READY" if details["ready"] else "MISSING"
        if details["missing"]:
            status += f" ({', '.join(details['missing'])})"
        lines.append(f"- {feature}: {status}")
        
    lines.append("\nPython Capabilities:")
    for k, v in report["python"].items():
        lines.append(f"- {k}: {'OK' if v else 'MISSING'}")
        
    lines.append("\nCommand Capabilities:")
    for k, v in report["commands"].items():
        lines.append(f"- {k}: {'OK' if v else 'MISSING'}")
        
    return "\n".join(lines)
