import os
import sys
import subprocess
import logging
from typing import Dict, List, Optional, Set

logger = logging.getLogger(__name__)

class ProcessContextTracker:
    """
    Cross-platform process inspector (Linux, macOS, Windows).
    Extracts working directories (CWD) and open project folders from running
    terminals, editors, and IDE processes dynamically.
    """
    TERMINAL_NAMES = {"kitty", "alacritty", "gnome-terminal", "konsole", "xterm", "wezterm", "foot", "tilix", "ghostty", "terminal", "warp", "cmd", "powershell", "bash", "zsh", "fish"}
    EDITOR_NAMES = {"code", "vscode", "antigravity", "cursor", "pycharm", "intellij", "idea", "sublime", "zed", "neovim", "fleet", "emacs", "kate", "gedit"}

    @classmethod
    def get_active_process_contexts(cls) -> Dict[str, Any]:
        """
        Returns authentic working directories for active terminals and editors.
        """
        terminal_cwds: Set[str] = set()
        editor_projects: Set[str] = set()

        if sys.platform == "linux":
            cls._scan_linux_proc(terminal_cwds, editor_projects)
        elif sys.platform == "darwin":
            cls._scan_macos_proc(terminal_cwds, editor_projects)
        elif sys.platform == "win32":
            cls._scan_windows_proc(terminal_cwds, editor_projects)

        home = os.path.abspath(os.path.expanduser("~"))
        def _is_clean(p: str) -> bool:
            if not p or not isinstance(p, str) or not os.path.isdir(p):
                return False
            ap = os.path.abspath(p)
            if (
                ap in [home, "/", "/root"]
                or ap.startswith(("/tmp", "/var/tmp", "/usr", "/opt", "/etc"))
                or any(noisy in ap for noisy in [
                    "/.cache",
                    "/.vscode/extensions",
                    "/.vscode-server",
                    "/.cursor/extensions",
                    "/.antigravity",
                    "/.config",
                    "/.local/share",
                    "/node_modules",
                    "/site-packages",
                    "/__pycache__",
                    "/venv",
                    "/.venv",
                    "/.git",
                    "/arova/frontend",
                    "/arova/release",
                    "/arova/dist",
                    "/arova/src-tauri",
                ])
            ):
                return False
            return True

        clean_terms = [p for p in terminal_cwds if _is_clean(p)]
        clean_editors = [p for p in editor_projects if _is_clean(p)]

        return {
            "terminal_cwds": clean_terms,
            "editor_projects": clean_editors
        }

    @classmethod
    def _scan_linux_proc(cls, terminal_cwds: Set[str], editor_projects: Set[str]):
        try:
            pids = [p for p in os.listdir("/proc") if p.isdigit()]
            for pid in pids:
                try:
                    cmdline_path = f"/proc/{pid}/cmdline"
                    if not os.path.exists(cmdline_path):
                        continue
                    with open(cmdline_path, "rb") as f:
                        cmdline = f.read().decode(errors="ignore").replace("\x00", " ")
                    
                    cmd_lower = cmdline.lower()
                    
                    # Read CWD
                    cwd_link = f"/proc/{pid}/cwd"
                    if os.path.islink(cwd_link):
                        real_cwd = os.readlink(cwd_link)
                        if os.path.isdir(real_cwd) and real_cwd != "/" and not real_cwd.startswith("/proc"):
                            # Check terminal process
                            if any(term in cmd_lower for term in cls.TERMINAL_NAMES):
                                terminal_cwds.add(real_cwd)
                            # Check editor process
                            if any(ed in cmd_lower for ed in cls.EDITOR_NAMES):
                                editor_projects.add(real_cwd)

                            # Parse cmdline for explicit directory arguments (e.g. `code /home/...`)
                            for arg in cmdline.split():
                                exp = os.path.expanduser(arg)
                                if os.path.isabs(exp) and os.path.isdir(exp) and exp != "/":
                                    if any(ed in cmd_lower for ed in cls.EDITOR_NAMES):
                                        editor_projects.add(exp)
                except Exception:
                    continue
        except Exception as e:
            logger.debug(f"ProcessContextTracker linux scan error: {e}")

    @classmethod
    def _scan_macos_proc(cls, terminal_cwds: Set[str], editor_projects: Set[str]):
        try:
            proc = subprocess.run(["lsof", "-a", "-d", "cwd", "-c", "kitty,Terminal,iTerm2,code,Cursor,antigravity"], capture_output=True, text=True, timeout=2)
            if proc.returncode == 0:
                for line in proc.stdout.splitlines():
                    parts = line.split()
                    if len(parts) >= 9:
                        name = parts[0].lower()
                        cwd = parts[8]
                        if os.path.isdir(cwd) and cwd != "/":
                            if any(term in name for term in cls.TERMINAL_NAMES):
                                terminal_cwds.add(cwd)
                            if any(ed in name for ed in cls.EDITOR_NAMES):
                                editor_projects.add(cwd)
        except Exception as e:
            logger.debug(f"ProcessContextTracker macos scan error: {e}")

    @classmethod
    def _scan_windows_proc(cls, terminal_cwds: Set[str], editor_projects: Set[str]):
        try:
            cmd = "Get-CimInstance Win32_Process | Select-Object Name, CommandLine, ProcessId | ConvertTo-Json"
            proc = subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True, timeout=3)
            if proc.returncode == 0:
                import json
                items = json.loads(proc.stdout)
                if isinstance(items, dict):
                    items = [items]
                for item in items:
                    name = str(item.get("Name", "")).lower()
                    cmdline = str(item.get("CommandLine", ""))
                    if any(ed in name for ed in cls.EDITOR_NAMES) or any(term in name for term in cls.TERMINAL_NAMES):
                        for arg in cmdline.split():
                            arg_clean = arg.strip('"\'')
                            if os.path.isabs(arg_clean) and os.path.isdir(arg_clean):
                                if any(term in name for term in cls.TERMINAL_NAMES):
                                    terminal_cwds.add(arg_clean)
                                else:
                                    editor_projects.add(arg_clean)
        except Exception as e:
            logger.debug(f"ProcessContextTracker windows scan error: {e}")
