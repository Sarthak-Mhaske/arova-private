import asyncio
import logging
import json
import os
from typing import Callable, Awaitable, Any, Dict
from arova.core.ipc.transport import TransportAdapter

class UnixSocketTransport(TransportAdapter):
    def __init__(self, socket_path: str):
        self.socket_path = socket_path
        self._server: Optional[asyncio.AbstractServer] = None
        self._clients: Dict[str, asyncio.StreamWriter] = {}
        self._on_message: Optional[Callable[[str, Any], Awaitable[None]]] = None

    async def start_server(self, on_message: Callable[[str, Any], Awaitable[None]]):
        self._on_message = on_message
        
        if os.path.exists(self.socket_path):
            os.remove(self.socket_path)
            
        os.makedirs(os.path.dirname(self.socket_path), exist_ok=True)
        
        self._server = await asyncio.start_unix_server(self._handle_client, path=self.socket_path)
        logging.info(f"UDS Server listening on {self.socket_path}")

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        client_id = str(id(writer))
        self._clients[client_id] = writer
        logging.info(f"Client {client_id} connected via UDS")
        
        try:
            while True:
                line = await reader.readline()
                if not line:
                    break
                try:
                    payload = json.loads(line.decode('utf-8'))
                    if self._on_message:
                        await self._on_message(client_id, payload)
                except json.JSONDecodeError:
                    logging.warning(f"Malformed JSON from client {client_id}")
        except Exception as e:
            logging.error(f"UDS client error: {e}")
        finally:
            writer.close()
            await writer.wait_closed()
            self._clients.pop(client_id, None)
            logging.info(f"Client {client_id} disconnected")

    async def stop_server(self):
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            if os.path.exists(self.socket_path):
                os.remove(self.socket_path)

    async def send_message(self, client_id: str, message: str):
        writer = self._clients.get(client_id)
        if writer:
            writer.write((message + "\n").encode('utf-8'))
            await writer.drain()

    async def broadcast(self, message: str):
        for writer in self._clients.values():
            try:
                writer.write((message + "\n").encode('utf-8'))
                await writer.drain()
            except Exception:
                pass
