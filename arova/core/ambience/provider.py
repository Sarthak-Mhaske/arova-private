import abc
import asyncio
from datetime import datetime
from arova.core.ambience.schema import AmbientContext

class AmbientProvider(abc.ABC):
    """
    Abstract base class for environment tracking.
    """
    @abc.abstractmethod
    async def get_current_context(self) -> AmbientContext:
        pass


class PollingProvider(AmbientProvider):
    """
    A simple deterministic polling provider.
    In the future, this can be swapped with native Wayland/X11 socket providers.
    """
    def __init__(self):
        # We could use hyprctl or xdotool here, but for now we'll mock the integration
        # to focus on the orchestration semantics.
        self._mock_app = "kitty"
        self._mock_idle = False
        
    async def get_current_context(self) -> AmbientContext:
        # 1. Determine time of day
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
