import platform
import shutil
from typing import Any
from arova.core.context import detect_environment

def _has_command(name: str) -> bool:
    return shutil.which(name) is not None

def collect_doctor_report() -> dict[str, Any]:
    env = detect_environment()
    commands = [
        "parecord",
        "paplay",
        "mpv",
        "notify-send",
        "playerctl",
        "brightnessctl",
        "xdg-open",
        "curl"
    ]
    
    cmd_status = {cmd: _has_command(cmd) for cmd in commands}
    
    return {
        "python_version": platform.python_version(),
        "env": env,
        "commands": cmd_status
    }

def format_doctor_report(report: dict[str, Any]) -> str:
    env = report.get("env", {})
    cmds = report.get("commands", {})
    
    lines = [
        "Arova Doctor",
        "",
        f"Python Version: {report.get('python_version', 'unknown')}",
        "",
        "Environment:",
        f"- OS: {env.get('os', 'unknown')}",
        f"- Window Manager: {env.get('wm', 'unknown')}",
        f"- Display Server: {env.get('display', 'unknown')}",
        f"- Audio System: {env.get('audio', 'unknown')}",
        f"- Browser: {env.get('browser', 'unknown')}",
        f"- Terminal: {env.get('terminal', 'unknown')}",
        f"- Screenshot Tool: {env.get('screenshot_tool', 'unknown')}",
        f"- Package Manager: {env.get('package_manager', 'unknown')}",
        "",
        "Commands:"
    ]
    
    for cmd, ok in cmds.items():
        status = "OK" if ok else "MISSING"
        lines.append(f"- {cmd}: {status}")
        
    return "\n".join(lines)
