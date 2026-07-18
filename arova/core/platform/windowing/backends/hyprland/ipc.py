import os
import json
import asyncio
import logging
from arova.core.platform.windowing.base import (
    WindowingBackend, 
    RawWindowData, 
    WorkspaceEvent, 
    FocusedWindowEvent
)

logger = logging.getLogger(__name__)

class HyprlandBackend(WindowingBackend):
    def __init__(self):
        super().__init__()
        self.signature = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")
        self.runtime_dir = os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
        
    async def get_active_window(self) -> RawWindowData | None:
        if not self.signature:
            return None
            
        socket_path = f"{self.runtime_dir}/hypr/{self.signature}/.socket.sock"
        if not os.path.exists(socket_path):
            return None
            
        try:
            reader, writer = await asyncio.open_unix_connection(socket_path)
            writer.write(b"j/activewindow")
            await writer.drain()
            
            data = await reader.read()
            writer.close()
            await writer.wait_closed()
            
            if not data:
                return None
                
            payload = json.loads(data.decode("utf-8"))
            if not payload or not isinstance(payload, dict):
                return None
                
            return RawWindowData(
                window_id=payload.get("address", ""),
                app_class=payload.get("class", ""),
                title=payload.get("title", ""),
                workspace_id=str(payload.get("workspace", {}).get("id", "")),
                is_fullscreen=payload.get("fullscreen", False),
                is_floating=payload.get("floating", False)
            )
        except Exception as e:
            logger.error(f"Hyprland IPC get_active_window error: {e}")
            return None

    async def subscribe_events(self):
        if not self.signature:
            logger.warning("No HYPRLAND_INSTANCE_SIGNATURE found. Cannot subscribe to events.")
            return
            
        socket_path = f"{self.runtime_dir}/hypr/{self.signature}/.socket2.sock"
        if not os.path.exists(socket_path):
            logger.warning(f"Hyprland event socket not found at {socket_path}")
            return
            
        while True:
            try:
                reader, writer = await asyncio.open_unix_connection(socket_path)
                logger.info("Connected to Hyprland event socket.")
                
                while True:
                    line = await reader.readline()
                    if not line:
                        break
                    
                    line_str = line.decode('utf-8').strip()
                    if not line_str:
                        continue
                        
                    parts = line_str.split(">>")
                    if len(parts) != 2:
                        continue
                        
                    event_name, event_data = parts
                    
                    if event_name == "workspace":
                        await self._emit(WorkspaceEvent(workspace_id=event_data))
                    elif event_name == "activewindow":
                        # data format: window_class,window_title
                        data_parts = event_data.split(",", 1)
                        if len(data_parts) == 2:
                            app_class, title = data_parts
                            # We emit a lightweight FocusedWindowEvent. 
                            # We might need to fetch full window data if we need workspace ID etc.
                            # For now, we will query get_active_window() to ensure rich data.
                            full_window = await self.get_active_window()
                            if full_window:
                                await self._emit(FocusedWindowEvent(window_data=full_window))
                            else:
                                # Fallback if get_active_window fails or is empty
                                await self._emit(FocusedWindowEvent(
                                    window_data=RawWindowData(
                                        window_id="unknown",
                                        app_class=app_class,
                                        title=title,
                                        workspace_id="unknown"
                                    )
                                ))
                    elif event_name == "activewindowv2":
                        # address
                        full_window = await self.get_active_window()
                        if full_window:
                            await self._emit(FocusedWindowEvent(window_data=full_window))

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Hyprland event socket error: {e}")
                await asyncio.sleep(2) # Reconnect delay
