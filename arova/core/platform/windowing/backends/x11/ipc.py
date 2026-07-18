import asyncio
import os
import subprocess
import logging
from typing import Optional
from arova.core.platform.windowing.base import WindowingBackend, RawWindowData, FocusedWindowEvent, WorkspaceEvent

logger = logging.getLogger(__name__)

class X11Backend(WindowingBackend):
    def __init__(self):
        super().__init__()
        self._running = False
        self._last_window_id = None
        self._workspace_id = "x11_default_workspace"

    async def get_active_window(self) -> Optional[RawWindowData]:
        try:
            # Get active window ID
            proc_id = await asyncio.create_subprocess_exec(
                "xdotool", "getactivewindow",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL
            )
            stdout_id, _ = await proc_id.communicate()
            if proc_id.returncode != 0:
                return None
                
            win_id = stdout_id.decode().strip()
            
            # Get window title
            proc_name = await asyncio.create_subprocess_exec(
                "xdotool", "getwindowname", win_id,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL
            )
            stdout_name, _ = await proc_name.communicate()
            win_title = stdout_name.decode().strip()
            
            # Get window class (app name)
            proc_class = await asyncio.create_subprocess_exec(
                "xprop", "-id", win_id, "WM_CLASS",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL
            )
            stdout_class, _ = await proc_class.communicate()
            class_str = stdout_class.decode().strip()
            
            app_name = "unknown"
            if "WM_CLASS(STRING) = " in class_str:
                parts = class_str.split("WM_CLASS(STRING) = ")[1].split(",")
                if len(parts) > 0:
                    app_name = parts[-1].strip().strip('"')
            
            return RawWindowData(
                window_id=win_id,
                title=win_title,
                app_name=app_name,
                workspace_id=self._workspace_id
            )
        except Exception as e:
            logger.debug(f"X11 get_active_window error: {e}")
            return None

    async def subscribe_events(self):
        """Polls for active window changes since X11 doesn't have a simple async subscribe for this."""
        self._running = True
        logger.info("X11 Windowing Observer started.")
        
        # Emit initial workspace
        await self._emit_event(WorkspaceEvent(workspace_id=self._workspace_id))
        
        while self._running:
            win_data = await self.get_active_window()
            if win_data and win_data.window_id != self._last_window_id:
                self._last_window_id = win_data.window_id
                logger.info(f"X11 Focus Changed: {win_data.app_name} - {win_data.title}")
                await self._emit_event(FocusedWindowEvent(window_data=win_data))
                
            await asyncio.sleep(1.0) # Poll every 1 second
            
    def stop(self):
        self._running = False
