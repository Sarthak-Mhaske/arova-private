import asyncio
import json
import logging
import time
from typing import Dict, Callable, Any, Optional
import websockets

logger = logging.getLogger("Arova.Bridge")

class WebSocketClient:
    def __init__(self, websocket):
        self.websocket = websocket
        self.queue = asyncio.Queue()
        self.connected = True
        self.id = id(websocket)

class WebSocketManager:
    def __init__(self, host: str = "127.0.0.1", port: int = 8765):
        self.host = host
        self.port = port
        self.clients: Dict[int, WebSocketClient] = {}
        self._message_handlers = []
        self._server = None

    def add_message_handler(self, handler: Callable[[dict], None]):
        """Register a callback for incoming messages from the frontend."""
        self._message_handlers.append(handler)

    async def _client_sender(self, client: WebSocketClient):
        """Dedicated asyncio task to send messages to a specific client from its queue."""
        try:
            while client.connected:
                message = await client.queue.get()
                try:
                    await client.websocket.send(message)
                except websockets.exceptions.ConnectionClosed:
                    client.connected = False
                    break
                except Exception as e:
                    logger.error(f"Error sending message to client {client.id}: {e}")
                    client.connected = False
                    break
        finally:
            await self._cleanup_client(client)

    async def _cleanup_client(self, client: WebSocketClient):
        """Remove the client from the active list."""
        if client.id in self.clients:
            logger.info(f"Client disconnected: {client.id}")
            del self.clients[client.id]
            client.connected = False

    async def _handle_connection(self, websocket, path=None):
        """Main handler for a new websocket connection."""
        client = WebSocketClient(websocket)
        self.clients[client.id] = client
        logger.info(f"New client connected: {client.id}")

        # Start the dedicated sender task for this client
        sender_task = asyncio.create_task(self._client_sender(client))

        # Send an immediate connection status event
        status_event = {
            "v": 1,
            "type": "runtime.status",
            "status": "connected",
            "timestamp": int(time.time() * 1000),
            "source": "bridge",
            "id": f"evt_conn_{client.id}"
        }
        await client.queue.put(json.dumps(status_event))

        try:
            async for message in websocket:
                try:
                    payload = json.loads(message)
                    logger.info(f"WS RECEIVED: {payload.get('type', 'UNKNOWN')} | raw: {message[:100]}...")
                    for handler in self._message_handlers:
                        # Schedule handlers dynamically to not block the receiver
                        asyncio.create_task(self._safe_invoke_handler(handler, payload))
                except json.JSONDecodeError:
                    logger.warning(f"Received invalid JSON from client {client.id}")
                except Exception as e:
                    logger.error(f"Error processing message from client {client.id}: {e}")
        except websockets.exceptions.ConnectionClosed:
            logger.debug(f"Connection closed for client {client.id}")
        finally:
            sender_task.cancel()
            await self._cleanup_client(client)

    async def _safe_invoke_handler(self, handler: Callable, payload: dict):
        try:
            if asyncio.iscoroutinefunction(handler):
                await handler(payload)
            else:
                handler(payload)
        except Exception as e:
            logger.error(f"Error in websocket message handler: {e}", exc_info=True)

    def broadcast(self, event_dict: dict):
        """
        Broadcast an event to all connected clients.
        Uses asyncio.Queue per client so slow clients do not stall the daemon.
        """
        if not self.clients:
            return

        try:
            message = json.dumps(event_dict)
            for client in list(self.clients.values()):
                if client.connected:
                    try:
                        client.queue.put_nowait(message)
                    except asyncio.QueueFull:
                        logger.warning(f"Client {client.id} queue full, dropping message")
        except Exception as e:
            logger.error(f"Error during broadcast: {e}")

    async def start(self):
        """Start the WebSocket server."""
        logger.info(f"Starting WebSocket bridge on ws://{self.host}:{self.port}")
        self._server = await websockets.serve(self._handle_connection, self.host, self.port)

    async def stop(self):
        """Stop the WebSocket server."""
        if self._server:
            self._server.close()
            await self._server.wait_closed()
