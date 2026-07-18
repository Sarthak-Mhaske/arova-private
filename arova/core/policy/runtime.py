import asyncio
import logging
from typing import Dict
from arova.core.events import RuntimeEventBus, EventPayload
from arova.core.policy.schema import PolicyChain, PolicyVerdict, ApprovalRequest
from arova.core.capabilities.registry import CapabilityRegistry
from arova.core.capabilities.schema import CapabilityPermission
from arova.core.policy.schema import Policy, PolicyEvaluation

class DangerousActionPolicy(Policy):
    """Requires approval for capabilities marked as DANGEROUS."""
    def __init__(self, registry: CapabilityRegistry):
        self.registry = registry
        
    async def evaluate(self, payload: EventPayload) -> PolicyEvaluation:
        cap_name = getattr(payload, "capability_name", None)
        if not cap_name:
            return PolicyEvaluation(PolicyVerdict.ALLOW)
            
        cap = await self.registry.get_definition(cap_name)
        if cap and cap.policy.permission_tier == CapabilityPermission.DANGEROUS:
            return PolicyEvaluation(
                verdict=PolicyVerdict.REQUIRE_APPROVAL,
                reason=f"Capability {cap_name} is marked as DANGEROUS."
            )
        return PolicyEvaluation(PolicyVerdict.ALLOW)


class PolicyRuntime:
    """
    Governance subsystem. Intercepts capability and automation requests.
    If policies allow, it re-emits them to the actual runtimes.
    """
    def __init__(self, event_bus: RuntimeEventBus, registry: CapabilityRegistry):
        self.event_bus = event_bus
        self.registry = registry
        
        self.capability_chain = PolicyChain(
            name="CapabilityGovernance",
            policies=[DangerousActionPolicy(registry)]
        )
        
        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            self._loop = None
        
        # Intercept before it hits CapabilityRuntime.
        # NOTE: In the new architecture, callers emit CAPABILITY_EXECUTION_DISPATCHED
        # The PolicyRuntime listens to that, evaluates it, and if allowed,
        # emits CAPABILITY_EXECUTION_REQUESTED for the CapabilityRuntime to actually execute.
        self.event_bus.subscribe("policy", "CAPABILITY_EXECUTION_DISPATCHED", self._on_capability_dispatched)
        
        self._pending_approvals: Dict[str, ApprovalRequest] = {}
        self._approval_locks: Dict[str, asyncio.Event] = {}
        self._approved_cache: Dict[str, bool] = {} # approval_id -> result

    def _on_capability_dispatched(self, payload: EventPayload):
        if self._loop:
            asyncio.run_coroutine_threadsafe(self._evaluate_and_route(payload), self._loop)
        else:
            logging.error("PolicyRuntime: No event loop captured at initialization!")
        
    async def _evaluate_and_route(self, payload: EventPayload):
        eval_res = await self.capability_chain.evaluate_all(payload)
        
        if eval_res.verdict == PolicyVerdict.ALLOW:
            logging.info(f"Policy ALLOWED capability execution.")
            self.event_bus.emit("policy", "CAPABILITY_EXECUTION_REQUESTED", payload)
            
        elif eval_res.verdict == PolicyVerdict.DENY:
            logging.warning(f"Policy DENIED capability execution: {eval_res.reason}")
            # Emit failure immediately
            exec_id = getattr(payload, "execution_id", "unknown")
            self.event_bus.emit("capabilities", "CAPABILITY_EXECUTION_FAILED", {
                "execution_id": exec_id,
                "error": f"Policy Denied: {eval_res.reason}"
            })
            
        elif eval_res.verdict == PolicyVerdict.REQUIRE_APPROVAL:
            # Human in the loop
            logging.info(f"Policy requires approval: {eval_res.reason}")
            req = ApprovalRequest(action=getattr(payload, "capability_name", "unknown"), details=payload.__dict__)
            self._pending_approvals[req.id] = req
            
            # Emit approval required event to UI/Client
            self.event_bus.emit("policy", "APPROVAL_REQUIRED", {
                "approval_id": req.id,
                "action": req.action,
                "reason": eval_res.reason
            })
            
            # In a full implementation, we'd wait on an asyncio.Event for the UI to respond
            # via a new endpoint in RuntimeFacade (e.g., facade.resolve_approval(req.id, True))
            # For this scaffolding phase, we'll auto-deny after timeout
            self._approval_locks[req.id] = asyncio.Event()
            try:
                await asyncio.wait_for(self._approval_locks[req.id].wait(), timeout=req.timeout_seconds)
                
                if self._approved_cache.get(req.id, False):
                    logging.info(f"Approval granted for {req.id}")
                    self.event_bus.emit("policy", "CAPABILITY_EXECUTION_REQUESTED", payload)
                else:
                    logging.info(f"Approval denied for {req.id}")
                    exec_id = getattr(payload, "execution_id", "unknown")
                    self.event_bus.emit("capabilities", "CAPABILITY_EXECUTION_FAILED", {
                        "execution_id": exec_id,
                        "error": "User denied approval."
                    })
            except asyncio.TimeoutError:
                logging.warning(f"Approval request {req.id} timed out.")
                exec_id = getattr(payload, "execution_id", "unknown")
                self.event_bus.emit("capabilities", "CAPABILITY_EXECUTION_FAILED", {
                    "execution_id": exec_id,
                    "error": "Approval timed out."
                })
            finally:
                self._pending_approvals.pop(req.id, None)
                self._approval_locks.pop(req.id, None)
                self._approved_cache.pop(req.id, None)

    async def resolve_approval(self, approval_id: str, approved: bool):
        """Called by RuntimeFacade when client responds."""
        if approval_id in self._approval_locks:
            self._approved_cache[approval_id] = approved
            self._approval_locks[approval_id].set()
