from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable, Awaitable
from enum import Enum
from arova.core.platform.system.executor import SystemExecutionLayer

class CapabilityPermission(str, Enum):
    SAFE = "safe"           # Read-only or completely reversible (e.g. math, status query)
    SENSITIVE = "sensitive" # Accesses private data (e.g. read emails, get location)
    SYSTEM = "system"       # Mutates system state (e.g. set volume, open app, media control)
    DANGEROUS = "dangerous" # Destructive or high-risk (e.g. delete files, send email, execute shell)

class CapabilityState(str, Enum):
    REGISTERED = "registered"
    INITIALIZING = "initializing"
    READY = "ready"
    EXECUTING = "executing"
    FAILED = "failed"
    DISABLED = "disabled"
    UNHEALTHY = "unhealthy"

class InterruptBehavior(str, Enum):
    HARD_CANCEL = "hard_cancel"             # Safe to brutally cancel the asyncio task
    SOFT_CANCEL = "soft_cancel"             # Will poll ctx.check_cancelled() and return cleanly
    COMPLETE_ATOMIC = "complete_atomic"     # Must not be cancelled, runs to completion
    REQUIRE_CONFIRMATION = "require_confirmation" # Ask user before cancelling

@dataclass
class CapabilityPolicy:
    permission_tier: CapabilityPermission
    timeout_seconds: float = 15.0
    requires_confirmation: bool = False
    concurrency_limit: int = 1 # 1 means sequential execution only
    resource_scope: List[str] = field(default_factory=list) # e.g. ["audio", "network"]
    
    # Interruption Supremacy (Phase 7.5)
    interrupt_behavior: InterruptBehavior = InterruptBehavior.HARD_CANCEL
    safe_cancel: bool = True
    rollback_strategy: Optional[str] = None

@dataclass
class ExecutionContext:
    """The boundary object passed to every executing capability."""
    execution_id: str
    turn_id: Optional[str]
    client_id: Optional[str]
    system: SystemExecutionLayer
    _cancelled: bool = False
    
    def is_cancelled(self) -> bool:
        return self._cancelled
        
    def check_cancelled(self):
        """Raises asyncio.CancelledError if cancelled, allowing cooperative cleanup."""
        import asyncio
        if self._cancelled:
            raise asyncio.CancelledError("Execution was preemptively cancelled via Interruption Supremacy.")
    
    # In the future, this would hold sandboxed references or IPC pipes back to the Runtime
    # We will use an async callback for streaming updates
    _stream_callback: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None
    
    async def stream_update(self, data: Dict[str, Any]):
        """Capabilities call this to stream progress before returning a final result."""
        self.check_cancelled()
        if self._stream_callback and not self._cancelled:
            await self._stream_callback(data)

@dataclass
class CapabilityHealth:
    is_alive: bool
    reason: Optional[str] = None
    last_checked: float = 0.0

@dataclass
class CapabilityDefinition:
    name: str
    description: str
    parameters_schema: Dict[str, Any]
    policy: CapabilityPolicy
    
    # Health check callback. If it returns False, state becomes UNHEALTHY
    healthcheck: Optional[Callable[[], Awaitable[CapabilityHealth]]] = None
    
    # The actual execution callback (in-process for Phase 5)
    # Signature: async def execute(args: dict, ctx: ExecutionContext) -> Any
    execute: Callable[[Dict[str, Any], ExecutionContext], Awaitable[Any]] = field(repr=False, default=None)

    def to_openai_schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters_schema,
            }
        }
