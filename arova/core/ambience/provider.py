import abc
import asyncio
import shutil
import json
import logging
from datetime import datetime
from typing import Optional, Callable
from arova.core.ambience.schema import AmbientContext

logger = logging.getLogger(__name__)

class AmbientProvider(abc.ABC):
    """
    Abstract base class for environment tracking.
    """
    @abc.abstractmethod
    async def get_current_context(self) -> AmbientContext:
        pass

    def is_event_driven(self) -> bool:
        """Returns True if the provider pushes OS events cleanly without periodic polling loops."""
        return False


class LiveOSAmbientProvider(AmbientProvider):
    """
    Live OS Ambient Provider (`P0-3`) that queries real OS window managers (Hyprland / X11 / Wayland)
    and idle timers without fake hardcoded mocks.
    """
    def __init__(self):
        self._has_hyprctl = shutil.which("hyprctl") is not None
        self._has_xdotool = shutil.which("xdotool") is not None
        self._has_xprintidle = shutil.which("xprintidle") is not None
        self._last_context = AmbientContext(
            active_app=None,
            window_title=None,
            workspace=None,
            is_idle=False,
            time_of_day="unknown"
        )
        self._event_callbacks: list = []

    def is_event_driven(self) -> bool:
        # Polling ensures continuous robust discovery across all Linux WMs (Hyprland / Sway / X11)
        return False

    def subscribe(self, callback: Callable[[AmbientContext], None]):
        self._event_callbacks.append(callback)

    async def get_current_context(self) -> AmbientContext:
        hour = datetime.now().hour
        if 5 <= hour < 12:
            tod = "morning"
        elif 12 <= hour < 17:
            tod = "afternoon"
        elif 17 <= hour < 21:
            tod = "evening"
        else:
            tod = "night"

        active_app = self._last_context.active_app if self._last_context else None
        window_title = self._last_context.window_title if self._last_context else None
        workspace = (self._last_context.workspace if self._last_context else None) or "1"
        is_idle = False
        idle_time_seconds = 0.0

        import sys
        try:
            if sys.platform == "darwin":
                # macOS active application and window tracking via AppleScript
                script = '''
                tell application "System Events"
                    set frontApp to first application process whose frontmost is true
                    set frontAppName to name of frontApp
                    set windowTitle to ""
                    try
                        set windowTitle to name of front window of frontApp
                    end try
                    return frontAppName & "|||" & windowTitle
                end tell
                '''
                proc = await asyncio.create_subprocess_exec(
                    "osascript", "-e", script,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, _ = await proc.communicate()
                if proc.returncode == 0 and stdout:
                    out_str = stdout.decode('utf-8', errors='ignore').strip()
                    if "|||" in out_str:
                        app_part, title_part = out_str.split("|||", 1)
                        active_app = app_part.strip() or active_app
                        window_title = title_part.strip() or window_title

            elif sys.platform == "win32":
                # Native Win32 active window & process tracking via ctypes (0ms overhead, no PowerShell spawn)
                try:
                    import ctypes
                    user32 = ctypes.windll.user32
                    hwnd = user32.GetForegroundWindow()
                    if hwnd:
                        length = user32.GetWindowTextLengthW(hwnd)
                        if length > 0:
                            buff = ctypes.create_unicode_buffer(length + 1)
                            user32.GetWindowTextW(hwnd, buff, length + 1)
                            if buff.value:
                                window_title = buff.value

                        pid = ctypes.c_ulong()
                        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                        if pid.value:
                            import psutil
                            try:
                                proc_info = psutil.Process(pid.value)
                                pname = proc_info.name()
                                if pname.lower().endswith(".exe"):
                                    pname = pname[:-4]
                                active_app = pname or active_app
                            except Exception:
                                pass
                except Exception as e:
                    logger.debug(f"Win32 ctypes active window check error: {e}")

            elif self._has_hyprctl:
                proc = await asyncio.create_subprocess_exec(
                    "hyprctl", "activewindow", "-j",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, _ = await proc.communicate()
                if proc.returncode == 0 and stdout:
                    data = json.loads(stdout.decode('utf-8', errors='ignore'))
                    active_app = data.get("class") or data.get("initialClass") or active_app
                    window_title = data.get("title") or window_title
                    ws_info = data.get("workspace", {})
                    if isinstance(ws_info, dict):
                        workspace = str(ws_info.get("name") or ws_info.get("id", workspace))
            elif self._has_xdotool:
                proc_name = await asyncio.create_subprocess_exec(
                    "xdotool", "getactivewindow", "getwindowname",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout_name, _ = await proc_name.communicate()
                if proc_name.returncode == 0 and stdout_name:
                    title_clean = stdout_name.decode('utf-8', errors='ignore').strip()
                    if title_clean:
                        window_title = title_clean
                        parts = window_title.split(" - ")
                        if len(parts) > 1:
                            active_app = parts[-1]
                        else:
                            active_app = window_title.split()[0]
        except Exception as e:
            logger.debug(f"LiveOSAmbientProvider active window check error: {e}")

        # Check idle time
        try:
            if sys.platform == "win32":
                # Native Win32 GetLastInputInfo idle detection
                try:
                    import ctypes
                    class LASTINPUTINFO(ctypes.Structure):
                        _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]
                    lii = LASTINPUTINFO()
                    lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
                    if ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii)):
                        millis = ctypes.windll.kernel32.GetTickCount() - lii.dwTime
                        idle_time_seconds = max(0.0, float(millis) / 1000.0)
                        is_idle = idle_time_seconds > 300.0
                except Exception as e:
                    logger.debug(f"Win32 idle check error: {e}")
            elif self._has_xprintidle:
                proc_idle = await asyncio.create_subprocess_exec(
                    "xprintidle",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout_idle, _ = await proc_idle.communicate()
                if proc_idle.returncode == 0 and stdout_idle:
                    ms = float(stdout_idle.decode('utf-8', errors='ignore').strip())
                    idle_time_seconds = ms / 1000.0
                    is_idle = idle_time_seconds > 300.0
        except Exception as e:
            logger.debug(f"LiveOSAmbientProvider idle check error: {e}")

        # Fetch cross-platform ambient data
        open_windows = []
        playing_media = []
        try:
            from arova.core.platform.services.backend import PlatformBackend
            backend = PlatformBackend.create()
            open_windows = backend.get_open_windows()
            playing_media = backend.get_playing_media()
        except Exception as e:
            logger.debug(f"LiveOSAmbientProvider cross-platform ambient fetch failed: {e}")

        self._last_context = AmbientContext(
            active_app=active_app,
            window_title=window_title,
            workspace=workspace,
            is_idle=is_idle,
            idle_time_seconds=idle_time_seconds,
            time_of_day=tod,
            open_windows=open_windows,
            playing_media=playing_media
        )
        return self._last_context


class PollingProvider(AmbientProvider):
    """
    A simple deterministic polling provider preserved for unit testing scenarios.
    """
    def __init__(self):
        self._mock_app = "kitty"
        self._mock_idle = False
        
    async def get_current_context(self) -> AmbientContext:
        hour = datetime.now().hour
        if 5 <= hour < 12:
            tod = "morning"
        elif 12 <= hour < 17:
            tod = "afternoon"
        elif 17 <= hour < 21:
            tod = "evening"
        else:
            tod = "night"
            
        return AmbientContext(
            active_app=self._mock_app,
            window_title=f"{self._mock_app} - ~",
            workspace="1",
            is_idle=self._mock_idle,
            time_of_day=tod
        )
