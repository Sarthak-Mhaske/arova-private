import os
import sys
import logging
import asyncio
from arova.core.platform.windowing.base import WindowingBackend, RawWindowData, FocusedWindowEvent

logger = logging.getLogger(__name__)

class WindowsWindowingBackend(WindowingBackend):
    def __init__(self):
        super().__init__()
        self._running = False
        self._last_title = ""

    async def get_active_window(self):
        try:
            import ctypes
            user32 = ctypes.windll.user32
            hwnd = user32.GetForegroundWindow()
            if not hwnd:
                return None
            length = user32.GetWindowTextLengthW(hwnd)
            buff = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buff, length + 1)
            title = buff.value
            return RawWindowData(
                window_id=str(hwnd),
                app_class="WindowsApp",
                title=title,
                workspace_id="ws_default"
            )
        except Exception:
            return None

    async def subscribe_events(self):
        self._running = True
        while self._running:
            try:
                win = await self.get_active_window()
                if win and win.title != self._last_title:
                    self._last_title = win.title
                    await self._emit(FocusedWindowEvent(window_data=win))
            except Exception as e:
                logger.debug(f"WindowsWindowingBackend error: {e}")
            await asyncio.sleep(0.5)

    def stop(self):
        self._running = False

class MacOSWindowingBackend(WindowingBackend):
    def __init__(self):
        super().__init__()
        self._running = False
        self._last_title = ""

    async def get_active_window(self):
        try:
            cmd = 'osascript -e "tell application \\"System Events\\" to get name of first application process whose frontmost is true"'
            proc = await asyncio.create_subprocess_shell(cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            stdout, _ = await proc.communicate()
            app_name = stdout.decode().strip() if stdout else "MacApp"
            return RawWindowData(
                window_id=app_name,
                app_class=app_name,
                title=app_name,
                workspace_id="ws_default"
            )
        except Exception:
            return None

    async def subscribe_events(self):
        self._running = True
        while self._running:
            try:
                win = await self.get_active_window()
                if win and win.title != self._last_title:
                    self._last_title = win.title
                    await self._emit(FocusedWindowEvent(window_data=win))
            except Exception as e:
                logger.debug(f"MacOSWindowingBackend error: {e}")
            await asyncio.sleep(0.8)

    def stop(self):
        self._running = False

class NoOpBackend(WindowingBackend):
    async def get_active_window(self):
        return None
        
    async def subscribe_events(self):
        pass

class WindowingManager:
    """
    Initializes the correct backend based on the OS and windowing environment.
    """
    @staticmethod
    def get_backend() -> WindowingBackend:
        if sys.platform == "win32":
            logger.info("Initializing native Windows Windowing Backend")
            return WindowsWindowingBackend()
        elif sys.platform == "darwin":
            logger.info("Initializing native macOS Windowing Backend")
            return MacOSWindowingBackend()

        wayland_display = os.environ.get("WAYLAND_DISPLAY")
        if wayland_display:
            if os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"):
                logger.info("Initializing Hyprland Windowing Backend")
                from arova.core.platform.windowing.backends.hyprland.ipc import HyprlandBackend
                return HyprlandBackend()
            else:
                logger.warning("Wayland detected but not Hyprland. Fallback to X11/Polling backend.")
                from arova.core.platform.windowing.backends.x11.ipc import X11Backend
                return X11Backend()
        else:
            logger.info("X11 Linux detected. Initializing X11 Polling Backend.")
            from arova.core.platform.windowing.backends.x11.ipc import X11Backend
            return X11Backend()
