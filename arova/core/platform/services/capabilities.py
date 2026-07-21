"""
Capability enum and CapabilityRegistry.

Defines the stable set of platform capabilities that the Resume Engine and
Restore Planner can request. The registry maps each capability to a concrete
handler provided by the active PlatformBackend.

New capabilities can be added to the enum without touching the Resume Engine,
Restore Planner, or any platform backend that doesn't implement them.
"""
import logging
from enum import Enum, auto
from typing import Callable, Dict, Optional, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .intents import RestoreIntent, LaunchResult

logger = logging.getLogger(__name__)


class Capability(Enum):
    """
    Every action the platform can perform on behalf of the cognitive engine.
    These never reference a specific application — only what to do.
    """
    OPEN_FILE = auto()
    OPEN_FOLDER = auto()
    OPEN_URL = auto()
    OPEN_PROJECT = auto()
    CREATE_TERMINAL = auto()
    FOCUS_WINDOW = auto()
    REVEAL_FILE = auto()
    RESTORE_EDITOR_STATE = auto()      # deep adapter only
    RESTORE_BROWSER_SESSION = auto()   # deep adapter only


class CapabilityRegistry:
    """
    Maps capabilities to platform-specific handler functions.

    The registry is populated once at startup by the active PlatformBackend.
    The Resume Engine calls capabilities through this registry and never
    touches OS-specific APIs directly.
    """

    def __init__(self):
        self._handlers: Dict[Capability, Callable] = {}

    def register(self, capability: Capability, handler: Callable) -> None:
        """Register a handler for a capability. Called by PlatformBackend at init."""
        self._handlers[capability] = handler
        logger.debug(f"CapabilityRegistry: Registered handler for {capability.name}")

    def can_handle(self, capability: Capability) -> bool:
        return capability in self._handlers

    def execute(self, capability: Capability, intent: "RestoreIntent") -> "LaunchResult":
        """
        Dispatch a RestoreIntent to the registered handler for its capability.
        Returns a LaunchResult with success/failure details.
        """
        from .intents import LaunchResult

        handler = self._handlers.get(capability)
        if handler is None:
            return LaunchResult(
                intent=intent,
                success=False,
                application_name="",
                detail=f"No handler registered for capability {capability.name}",
                error=f"Unregistered capability: {capability.name}"
            )
        try:
            return handler(intent)
        except Exception as e:
            logger.error(f"CapabilityRegistry: Handler for {capability.name} raised: {e}", exc_info=True)
            return LaunchResult(
                intent=intent,
                success=False,
                application_name="",
                detail=f"Handler exception for {capability.name}",
                error=str(e)
            )

    def registered_capabilities(self) -> list:
        return list(self._handlers.keys())
