import abc
from typing import Callable, Any, Dict, Optional, Awaitable
from dataclasses import dataclass, field
import time

@dataclass(kw_only=True)
class RawWindowData:
    window_id: str
    app_class: str
    title: str
    workspace_id: str
    is_fullscreen: bool = False
    is_floating: bool = False
    timestamp: float = field(default_factory=time.time)

@dataclass(kw_only=True)
class WorkspaceEvent:
    workspace_id: str
    timestamp: float = field(default_factory=time.time)

@dataclass(kw_only=True)
class FocusedWindowEvent:
    window_data: Optional[RawWindowData]
    timestamp: float = field(default_factory=time.time)

class WindowingBackend(abc.ABC):
    """
    Platform Abstraction Layer for Window Management.
    """
    def __init__(self):
        self._listeners = []
        
    def add_listener(self, callback: Callable[[Any], Awaitable[None]]):
        self._listeners.append(callback)
        
    async def _emit(self, event: Any):
        for listener in self._listeners:
            try:
                await listener(event)
            except Exception as e:
                import logging
                logging.error(f"Error in windowing listener: {e}")
    
    @abc.abstractmethod
    async def get_active_window(self) -> Optional[RawWindowData]:
        pass
        
    @abc.abstractmethod
    async def subscribe_events(self):
        """Start listening to compositor events and emit normalized events."""
        pass
