import asyncio
import abc
from typing import Callable, Awaitable, Any

class TransportAdapter(abc.ABC):
    """
    Abstract interface for IPC communication.
    Arova is transport-agnostic (could be UDS, WebSockets, etc.).
    """
    @abc.abstractmethod
    async def start_server(self, on_message: Callable[[str, Any], Awaitable[None]]):
        pass
        
    @abc.abstractmethod
    async def stop_server(self):
        pass
        
    @abc.abstractmethod
    async def send_message(self, client_id: str, message: str):
        pass
        
    @abc.abstractmethod
    async def broadcast(self, message: str):
        pass
