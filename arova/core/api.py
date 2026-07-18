import asyncio
import uuid
import logging
from typing import Callable, Any, Dict, List, Optional
from arova.core.events import RuntimeEventBus, EventPayload
from arova.core.dto import (
    VoiceStateDTO, 
    ExecutionStateDTO, 
    RuntimeHealthDTO, 
    ConversationSnapshotDTO,
    FacadeEventDTO
)
from arova.core.state import RuntimeProjectionCache

class ClientSession:
    """Represents a connected client (UI, Headless, Remote)."""
    def __init__(self, client_id: str, capabilities: List[str]):
        self.client_id = client_id
        self.capabilities = capabilities
        self.subscriptions: List[str] = []

class RuntimeFacade:
    """
    The strict Async IPC Boundary between the Core Runtime and any connected Client.
    All communication uses typed JSON-serializable DTOs.
    Clients MUST NOT access internal runtime objects.
    """
    def __init__(self, event_bus: RuntimeEventBus, projection_cache: RuntimeProjectionCache):
        self._event_bus = event_bus
        self._projection_cache = projection_cache
        self._clients: Dict[str, ClientSession] = {}
        
    async def connect_client(self, capabilities: List[str] = None) -> str:
        """Handshake. Returns a client_id."""
        client_id = str(uuid.uuid4())
        self._clients[client_id] = ClientSession(client_id, capabilities or [])
        logging.info(f"RuntimeFacade: Client {client_id} connected.")
        return client_id
        
    async def disconnect_client(self, client_id: str):
        if client_id in self._clients:
            del self._clients[client_id]
            logging.info(f"RuntimeFacade: Client {client_id} disconnected.")

    # --- Commands ---
    
    async def start_voice_turn(self, client_id: str):
        """Manually trigger a wake event (e.g. mic button click)."""
        # Internal adaptation: EventBus is sync, we bridge it here
        self._event_bus.emit("voice", "WAKE_DETECTED", EventPayload())
        
    async def interrupt(self, client_id: str):
        """Global interrupt."""
        self._event_bus.emit("runtime", "INTERRUPT_REQUESTED", EventPayload())
        
    async def execute_text(self, client_id: str, text: str):
        """Direct text command."""
        # Synthesize a wake and a transcript final to mimic voice execution
        self._event_bus.emit("voice", "WAKE_DETECTED", EventPayload())
        self._event_bus.emit("voice", "TRANSCRIPT_FINAL", EventPayload()) # Assuming IntentRuntime handles it

    # --- Phase 7A: Thread Actions ---
    async def execute_thread_action(self, client_id: str, action: str, thread_id: str, payload: dict = None):
        """Pass thread UI actions (resume, pause, archive, rename, pin) to the ThreadManager."""
        self._event_bus.emit("intention", "THREAD_ACTION_REQUESTED", {
            "action": action,
            "thread_id": thread_id,
            "payload": payload or {}
        })

    # --- Queries / Snapshots ---
    
    async def get_runtime_projection(self, client_id: str) -> dict:
        """
        Returns the unified perceptual renderer payload for the frontend.
        This replaces the old conversation, voice, and execution snapshots.
        """
        # In a real implementation we'd cache this or pass the projector down
        # For now, we assume the frontend receives it via the PROJECTION_UPDATED stream
        # Or we can fetch it from the runtime container if we have a ref to it
        pass
        
    async def get_voice_snapshot(self, client_id: str) -> VoiceStateDTO:
        return self._projection_cache.get_voice_snapshot()

    async def get_execution_snapshot(self, client_id: str) -> ExecutionStateDTO:
        return self._projection_cache.get_execution_snapshot()

    # --- Phase 6: Settings & Config ---
    
    async def get_os_config(self, client_id: str) -> dict:
        from arova.core.config.manager import get_config_manager
        return get_config_manager().load_config()
        
    async def update_os_config(self, client_id: str, patch: dict):
        from arova.core.config.manager import get_config_manager
        manager = get_config_manager()
        current = manager.load_config()
        # Basic recursive merge for the patch
        for k, v in patch.items():
            if isinstance(v, dict) and k in current and isinstance(current[k], dict):
                current[k] = {**current[k], **v}
            else:
                current[k] = v
        manager.save_config(current)
        
    async def run_provider_discovery(self, client_id: str) -> dict:
        from arova.core.config.discovery import ProviderDiscovery
        return await ProviderDiscovery.run_discovery()
        
    async def export_runtime_snapshot(self, client_id: str, export_path: str):
        from arova.core.persistence.store import RuntimeStore
        import json
        
        store = RuntimeStore()
        snapshot = store.hydrate()
        
        with open(export_path, "w", encoding="utf-8") as f:
            json.dump(snapshot.to_dict(), f, indent=2)

    # --- Subscriptions (Stream) ---
    
    def subscribe(self, client_id: str, event_type: str, callback: Callable[[FacadeEventDTO], None]):
        """
        Subscribe to a logical stream of DTOs.
        In a real IPC implementation, this would yield over a WebSocket/gRPC stream.
        Here we adapt the internal EventBus to the callback.
        """
        if client_id not in self._clients:
            raise ValueError("Unknown client_id")
            
        self._clients[client_id].subscriptions.append(event_type)
        
        # Internal adaptation layer: Map internal events to FacadeEventDTOs
        # Example mapping (in reality, this would be more exhaustive)
        def _wrapper(payload):
            # Attempt to map internal payload to a dict representation
            # For this Phase, we assume payload objects have standard fields or we manually construct DTOs
            dto_payload = {}
            if hasattr(payload, "state"):
                dto_payload["state"] = payload.state
            if hasattr(payload, "message"):
                dto_payload["message"] = payload.message
            if hasattr(payload, "turn_id"):
                dto_payload["turn_id"] = payload.turn_id
                
            facade_event = FacadeEventDTO(
                event_type=event_type,
                payload=dto_payload
            )
            # Call the client callback (simulating push to client)
            callback(facade_event)
            
        # Register the wrapper with the internal bus based on event_type mapping
        # This is simplified. Proper routing would map Facade event_types to specific bus channels
        if event_type == "VOICE_STATE":
            self._event_bus.subscribe("state", "STATE_CHANGED", _wrapper)
        elif event_type == "EXECUTION_STATE":
            self._event_bus.subscribe("state", "EXECUTION_STATE_CHANGED", _wrapper)
        elif event_type == "PLAN_UPDATED":
            self._event_bus.subscribe("plans", "PLAN_UPDATED", _wrapper)
