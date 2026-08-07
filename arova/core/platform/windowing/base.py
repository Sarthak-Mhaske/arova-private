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
        import asyncio
        import logging
        tasks = []
        for listener in self._listeners:
            tasks.append(asyncio.create_task(asyncio.wait_for(listener(event), timeout=0.5)))
            
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for r in results:
                if isinstance(r, Exception):
                    logging.error(f"Error in windowing listener: {r}")
    
    @abc.abstractmethod
    async def get_active_window(self) -> Optional[RawWindowData]:
        pass
        
    @abc.abstractmethod
    async def subscribe_events(self):
        """Start listening to compositor events and emit normalized events."""
        pass
