import asyncio
import logging
import time
from typing import Dict, List, Optional, Any
from arova.core.capabilities.schema import CapabilityDefinition, CapabilityState, CapabilityHealth

class CapabilityRegistry:
    """
    Central repository for all available system capabilities.
    Manages their definitions and health states.
    """
    def __init__(self):
        self._capabilities: Dict[str, CapabilityDefinition] = {}
        self._states: Dict[str, CapabilityState] = {}
        self._healths: Dict[str, CapabilityHealth] = {}
        self._lock = asyncio.Lock()
        
    async def register(self, capability: CapabilityDefinition):
        async with self._lock:
            if capability.name in self._capabilities:
                logging.warning(f"Capability {capability.name} is already registered. Overwriting.")
            self._capabilities[capability.name] = capability
            self._states[capability.name] = CapabilityState.REGISTERED
            self._healths[capability.name] = CapabilityHealth(is_alive=False, reason="Not yet checked")
            logging.info(f"Registered capability: {capability.name}")
            
    async def get_definition(self, name: str) -> Optional[CapabilityDefinition]:
        async with self._lock:
            return self._capabilities.get(name)
            
    async def get_state(self, name: str) -> Optional[CapabilityState]:
        async with self._lock:
            return self._states.get(name)

    async def get_all_openai_schemas(self, only_ready: bool = True) -> List[Dict[str, Any]]:
        schemas = []
        async with self._lock:
            for name, cap in self._capabilities.items():
                state = self._states.get(name, CapabilityState.DISABLED)
                if only_ready and state != CapabilityState.READY:
                    continue
                schemas.append(cap.to_openai_schema())
        return schemas

    async def run_healthchecks(self):
        """
        Periodically invoked by the Runtime to evaluate if capabilities are still healthy.
        Transitions capabilities to READY or UNHEALTHY.
        """
        async with self._lock:
            caps_to_check = list(self._capabilities.values())
            
        for cap in caps_to_check:
            if cap.healthcheck:
                try:
                    # Timeout the healthcheck so one bad plugin doesn't block the registry
                    health = await asyncio.wait_for(cap.healthcheck(), timeout=2.0)
                except Exception as e:
                    health = CapabilityHealth(is_alive=False, reason=f"Healthcheck failed: {e}", last_checked=time.time())
            else:
                # No healthcheck means it is assumed healthy/ready always
                health = CapabilityHealth(is_alive=True, last_checked=time.time())
                
            async with self._lock:
                self._healths[cap.name] = health
                if health.is_alive:
                    if self._states[cap.name] in (CapabilityState.REGISTERED, CapabilityState.UNHEALTHY):
                        self._states[cap.name] = CapabilityState.READY
                else:
                    self._states[cap.name] = CapabilityState.UNHEALTHY
                    logging.warning(f"Capability {cap.name} is UNHEALTHY: {health.reason}")
