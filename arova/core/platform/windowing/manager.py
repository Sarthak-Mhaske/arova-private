import os
import logging
from arova.core.platform.windowing.base import WindowingBackend

logger = logging.getLogger(__name__)

class WindowingManager:
    """
    Initializes the correct backend based on the environment (e.g., Wayland vs X11).
    """
    @staticmethod
    def get_backend() -> WindowingBackend:
        wayland_display = os.environ.get("WAYLAND_DISPLAY")
        
        if wayland_display:
            # We assume Hyprland if Wayland for this phase, but we could check $HYPRLAND_INSTANCE_SIGNATURE
            if os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"):
                logger.info("Initializing Hyprland Windowing Backend")
                from arova.core.platform.windowing.backends.hyprland.ipc import HyprlandBackend
                return HyprlandBackend()
            else:
                logger.warning("Wayland detected but not Hyprland. Fallback to X11/Polling backend.")
                from arova.core.platform.windowing.backends.x11.ipc import X11Backend
                return X11Backend()
        else:
            logger.info("X11/Other detected. Initializing X11 Polling Backend.")
            from arova.core.platform.windowing.backends.x11.ipc import X11Backend
            return X11Backend()

class NoOpBackend(WindowingBackend):
    async def get_active_window(self):
        return None
        
    async def subscribe_events(self):
        # Do nothing gracefully
        pass
