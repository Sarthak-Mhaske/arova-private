import asyncio
import logging
import uuid
from typing import Any, Dict
from arova.core.events import RuntimeEventBus, EventPayload
from arova.core.capabilities.schema import ExecutionContext, CapabilityState, InterruptBehavior
from arova.core.capabilities.registry import CapabilityRegistry
from arova.core.platform.system.executor import SystemExecutionLayer

class CapabilityRuntime:
    """
    The formal sandbox/execution boundary for all capabilities.
    Nothing executes a tool, command, or automation outside this runtime.
    """
    def __init__(self, event_bus: RuntimeEventBus, registry: CapabilityRegistry, system_executor: SystemExecutionLayer):
        self.event_bus = event_bus
        self.registry = registry
        self.system_executor = system_executor
        
        # Track active executions: execution_id -> (asyncio.Task, ExecutionContext, InterruptBehavior)
        self.active_executions: Dict[str, tuple[asyncio.Task, ExecutionContext, InterruptBehavior]] = {}
        
        self.event_bus.subscribe("capabilities", "CAPABILITY_EXECUTION_REQUESTED", self._on_execution_requested)
        self.event_bus.subscribe("runtime", "INTERRUPT_REQUESTED", self._on_interrupt)
        
        # Periodic healthcheck loop
        try:
            loop = asyncio.get_running_loop()
            self._healthcheck_task = loop.create_task(self._healthcheck_loop())
        except RuntimeError:
            self._healthcheck_task = None
        
    async def _healthcheck_loop(self):
        while True:
            await asyncio.sleep(30)
            await self.registry.run_healthchecks()

    def _on_execution_requested(self, payload: EventPayload):
        cap_name = getattr(payload, "capability_name", None)
        args = getattr(payload, "args", {})
        turn_id = getattr(payload, "turn_id", None)
        client_id = getattr(payload, "client_id", None)
        execution_id = getattr(payload, "execution_id", str(uuid.uuid4()))
        
        if not cap_name:
            logging.error("Execution requested without capability_name")
            return
            
        try:
            loop = asyncio.get_running_loop()
            task = loop.create_task(self._execute_sandbox(cap_name, args, turn_id, client_id, execution_id))
        except RuntimeError:
            logging.error("Cannot execute capability: no running event loop")
        
    def _on_interrupt(self, payload: EventPayload):
        """Phase 7.5: Interruption Supremacy"""
        for exec_id, (task, ctx, behavior) in list(self.active_executions.items()):
            if behavior == InterruptBehavior.HARD_CANCEL:
                logging.info(f"[INTERRUPT] Hard cancelling {exec_id}")
                task.cancel()
            elif behavior == InterruptBehavior.SOFT_CANCEL:
                logging.info(f"[INTERRUPT] Soft cancelling {exec_id} (Cooperative)")
                ctx._cancelled = True
            elif behavior == InterruptBehavior.REQUIRE_CONFIRMATION:
                logging.info(f"[INTERRUPT] Ignored for {exec_id} (Requires confirmation)")
                # In future: emit a prompt for user confirmation
            elif behavior == InterruptBehavior.COMPLETE_ATOMIC:
                logging.info(f"[INTERRUPT] Ignored for {exec_id} (Atomic execution)")

    async def _execute_sandbox(self, cap_name: str, args: Dict[str, Any], turn_id: str, client_id: str, execution_id: str):
        cap = await self.registry.get_definition(cap_name)
        if not cap:
            self._emit_failed(execution_id, cap_name, turn_id, f"Capability '{cap_name}' not found in registry")
            return
            
        state = await self.registry.get_state(cap_name)
        if state != CapabilityState.READY:
            self._emit_failed(execution_id, cap_name, turn_id, f"Capability '{cap_name}' is not READY (State: {state})")
            return
            
        if not cap.execute:
            self._emit_failed(execution_id, cap_name, turn_id, f"Capability '{cap_name}' has no execute function")
            return

        async def _stream_cb(data: Dict[str, Any]):
            self.event_bus.emit("capabilities", "CAPABILITY_STREAM_UPDATE", {
                "execution_id": execution_id,
                "capability_name": cap_name,
                "turn_id": turn_id,
                "data": data
            })
            
        ctx = ExecutionContext(
            execution_id=execution_id,
            turn_id=turn_id,
            client_id=client_id,
            system=self.system_executor,
            _stream_callback=_stream_cb
        )
        
        self.event_bus.emit("capabilities", "CAPABILITY_EXECUTION_STARTED", {
            "execution_id": execution_id,
            "capability_name": cap_name,
            "turn_id": turn_id
        })

        # Register task for interruption
        current_task = asyncio.current_task()
        if current_task:
            self.active_executions[execution_id] = (current_task, ctx, cap.policy.interrupt_behavior)

        try:
            # Apply Policy Timeouts and Execute
            if cap.policy.timeout_seconds > 0:
                result = await asyncio.wait_for(cap.execute(args, ctx), timeout=cap.policy.timeout_seconds)
            else:
                result = await cap.execute(args, ctx)
                
            self.event_bus.emit("capabilities", "CAPABILITY_EXECUTION_COMPLETED", {
                "execution_id": execution_id,
                "capability_name": cap_name,
                "turn_id": turn_id,
                "result": result
            })
        except asyncio.TimeoutError:
            self._emit_failed(execution_id, cap_name, turn_id, f"Execution timed out after {cap.policy.timeout_seconds}s")
        except asyncio.CancelledError:
            self.event_bus.emit("capabilities", "CAPABILITY_EXECUTION_CANCELLED", {
                "execution_id": execution_id,
                "capability_name": cap_name,
                "turn_id": turn_id
            })
        except Exception as e:
            logging.error(f"Capability {cap_name} failed: {e}")
            self._emit_failed(execution_id, cap_name, turn_id, f"Execution failed: {e}")
        finally:
            self.active_executions.pop(execution_id, None)
            
    def _emit_failed(self, execution_id: str, cap_name: str, turn_id: str, error: str):
        self.event_bus.emit("capabilities", "CAPABILITY_EXECUTION_FAILED", {
            "execution_id": execution_id,
            "capability_name": cap_name,
            "turn_id": turn_id,
            "error": error
        })
