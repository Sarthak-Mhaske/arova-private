import asyncio
import logging
import os
import uuid
import traceback
from typing import Dict, Any, Callable
from arova.core.api import RuntimeFacade
from arova.core.dto import FacadeEventDTO
from arova.core.ipc.protocol import IpcFrame, HandshakeRequest, HandshakeResponse, IpcCommand, IpcResponse

class ClientConnection:
    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, facade: RuntimeFacade):
        self.reader = reader
        self.writer = writer
        self.facade = facade
        
        self.client_id = None
        self.session_token = None
        self.is_authenticated = False
        
        self._running = True
        self._write_lock = asyncio.Lock()
        
    async def send_frame(self, frame: IpcFrame):
        async with self._write_lock:
            try:
                self.writer.write(frame.serialize())
                await self.writer.drain()
            except Exception as e:
                logging.error(f"Failed to send frame to client {self.client_id}: {e}")
                self._running = False
                
    async def handle_loop(self):
        try:
            while self._running:
                line = await self.reader.readline()
                if not line:
                    break # EOF
                    
                frame = IpcFrame.deserialize(line)
                asyncio.create_task(self._process_frame(frame))
                
        except asyncio.IncompleteReadError:
            pass
        except Exception as e:
            logging.error(f"IPC Client connection error: {e}")
            traceback.print_exc()
        finally:
            self._running = False
            self.writer.close()
            await self.writer.wait_closed()
            if self.client_id:
                await self.facade.disconnect_client(self.client_id)
                logging.info(f"IPC Client {self.client_id} disconnected.")

    async def _process_frame(self, frame: IpcFrame):
        if frame.type == "handshake":
            req = HandshakeRequest(**frame.payload)
            self.client_id = await self.facade.connect_client(req.capabilities)
            self.session_token = str(uuid.uuid4())
            self.is_authenticated = True
            
            resp = HandshakeResponse(accepted=True, runtime_version="2.0", session_token=self.session_token)
            await self.send_frame(IpcFrame(type="response", message_id=frame.message_id, payload=resp.__dict__))
            
            # Auto-subscribe this connection to all Facade stream events it requests.
            # In a real implementation, clients would send explicit SUBSCRIBE commands.
            # For Phase 4 simplicity, we auto-subscribe based on capabilities or just subscribe all.
            self.facade.subscribe(self.client_id, "VOICE_STATE", self._stream_event)
            self.facade.subscribe(self.client_id, "EXECUTION_STATE", self._stream_event)
            self.facade.subscribe(self.client_id, "PLAN_UPDATED", self._stream_event)
            
        elif frame.type == "command":
            if not self.is_authenticated:
                err = IpcResponse(ok=False, error="Not authenticated")
                await self.send_frame(IpcFrame(type="response", message_id=frame.message_id, payload=err.__dict__))
                return
                
            cmd = IpcCommand(**frame.payload)
            try:
                result = await self._execute_facade_command(cmd)
                resp = IpcResponse(ok=True, data=result)
                await self.send_frame(IpcFrame(type="response", message_id=frame.message_id, payload=resp.__dict__))
            except Exception as e:
                resp = IpcResponse(ok=False, error=str(e))
                await self.send_frame(IpcFrame(type="response", message_id=frame.message_id, payload=resp.__dict__))

    async def _execute_facade_command(self, cmd: IpcCommand) -> Any:
        method = cmd.method
        
        if method == "start_voice_turn":
            await self.facade.start_voice_turn(self.client_id)
            return {}
        elif method == "interrupt":
            await self.facade.interrupt(self.client_id)
            return {}
        elif method == "execute_text":
            text = cmd.args.get("text", "")
            await self.facade.execute_text(self.client_id, text)
            return {}
        elif method == "get_voice_snapshot":
            dto = await self.facade.get_voice_snapshot(self.client_id)
            return dto.to_dict()
        elif method == "get_conversation_snapshot":
            dto = await self.facade.get_conversation_snapshot(self.client_id)
            return dto.to_dict()
        elif method == "get_execution_snapshot":
            dto = await self.facade.get_execution_snapshot(self.client_id)
            return dto.to_dict()
        else:
            raise ValueError(f"Unknown facade command: {method}")

    def _stream_event(self, event_dto: FacadeEventDTO):
        # Fire-and-forget streaming packet back to client
        if not self._running:
            return
            
        frame = IpcFrame(
            type="stream",
            message_id=str(uuid.uuid4()),
            payload=event_dto.to_dict()
        )
        # Using create_task to avoid blocking the EventBus thread
        asyncio.create_task(self.send_frame(frame))


class IpcServer:
    """
    Unix Domain Socket server mapping IPC requests to the RuntimeFacade.
    """
    def __init__(self, facade: RuntimeFacade):
        self.facade = facade
        self.server: Optional[asyncio.Server] = None
        
        # Resolve socket path
        xdg_runtime = os.environ.get("XDG_RUNTIME_DIR", "/tmp")
        arova_dir = os.path.join(xdg_runtime, "arova")
        os.makedirs(arova_dir, exist_ok=True)
        self.socket_path = os.path.join(arova_dir, "arovad.sock")

    async def start(self):
        # Cleanup old socket if it exists
        if os.path.exists(self.socket_path):
            os.remove(self.socket_path)
            
        self.server = await asyncio.start_unix_server(self._handle_client, path=self.socket_path)
        logging.info(f"IpcServer listening on {self.socket_path}")
        
    async def stop(self):
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            if os.path.exists(self.socket_path):
                os.remove(self.socket_path)
            logging.info("IpcServer stopped.")

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        logging.info("IpcServer: Client connected.")
        conn = ClientConnection(reader, writer, self.facade)
        await conn.handle_loop()
