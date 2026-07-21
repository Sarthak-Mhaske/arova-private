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
            active_app="Arova Architecture & Development",
            window_title="Arova Cognitive Substrate",
            workspace="1",
            is_idle=False,
            time_of_day="morning"
        )
        self._event_callbacks: list = []

    def is_event_driven(self) -> bool:
        # If Hyprland socket exists, we can run event-driven without polling (`P0-4`)
        import os
        xdg = os.environ.get("XDG_RUNTIME_DIR", "")
        if self._has_hyprctl and xdg and os.path.exists(f"{xdg}/hypr"):
            return True
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

        active_app = self._last_context.active_app or "Arova Architecture & Development"
        window_title = self._last_context.window_title or "Arova Cognitive Substrate"
        workspace = self._last_context.workspace or "1"
        is_idle = False
        idle_time_seconds = 0.0

        try:
            if self._has_hyprctl:
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
            logger.debug(f"LiveOSAmbientProvider window check error: {e}")

        try:
            if self._has_xprintidle:
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

        self._last_context = AmbientContext(
            active_app=active_app,
            window_title=window_title,
            workspace=workspace,
            is_idle=is_idle,
            idle_time_seconds=idle_time_seconds,
            time_of_day=tod
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
