"""
Deep Adapters — optional enhancements for richer application restoration.

The application launches fine without any adapter.  Adapters add features like
cursor restoration, workspace file support, or project-specific arguments
for applications that expose deeper integration points.

Only VSCodeAdapter ships initially.  Others are added during dogfooding.
"""
import abc
import logging
from typing import Dict, List, Optional, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .intents import RestoreIntent

logger = logging.getLogger(__name__)


class DeepAdapter(abc.ABC):
    """
    Base class for optional deep integration with a specific application.

    Matched against ``ApplicationEntry.executable`` at launch time.
    If no adapter exists for an application, the generic launch path is used.
    """
    app_exec: str = ""  # e.g., "code", "idea", "blender"

    @abc.abstractmethod
    def enhance_launch_args(self, base_args: List[str], intent: "RestoreIntent") -> List[str]:
        """
        Given the base launch arguments and a RestoreIntent, return enhanced
        arguments that leverage application-specific features.
        """

    @abc.abstractmethod
    def can_restore_state(self) -> bool:
        """Whether this adapter supports restoring internal application state."""


class VSCodeAdapter(DeepAdapter):
    """
    Deep integration for Visual Studio Code / Code - OSS.

    Enhancements:
    - ``--goto file:line:col`` for exact cursor restoration
    - ``--reuse-window`` to avoid spawning new windows
    - Workspace file support
    """
    app_exec = "code"

    def enhance_launch_args(self, base_args: List[str], intent: "RestoreIntent") -> List[str]:
        args = list(base_args)
        if not intent.resource_path:
            return args

        line = intent.metadata.get("line")
        col = intent.metadata.get("col")

        if line is not None:
            target = f"{intent.resource_path}:{line}"
            if col is not None:
                target += f":{col}"
            # Replace plain file path with --goto target
            if intent.resource_path in args:
                idx = args.index(intent.resource_path)
                args[idx:idx + 1] = ["-g", target]
            else:
                args.extend(["-g", target])
        else:
            if intent.resource_path not in args:
                args.append(intent.resource_path)

        # Prefer reusing existing window
        if "--reuse-window" not in args and "-r" not in args:
            args.insert(1, "--reuse-window")

        return args

    def can_restore_state(self) -> bool:
        return True


class JetBrainsAdapter(DeepAdapter):
    """
    Deep integration for JetBrains IDEs (IntelliJ, PyCharm, WebStorm, etc.).

    Enhancements:
    - ``--line <n>`` for cursor position
    - Project directory as first argument
    """
    app_exec = "idea"

    def enhance_launch_args(self, base_args: List[str], intent: "RestoreIntent") -> List[str]:
        args = list(base_args)
        line = intent.metadata.get("line")
        if line is not None and intent.resource_path:
            args.extend(["--line", str(line), intent.resource_path])
        elif intent.resource_path and intent.resource_path not in args:
            args.append(intent.resource_path)
        return args

    def can_restore_state(self) -> bool:
        return True


# Registry of all available adapters, keyed by executable name
ADAPTER_REGISTRY: Dict[str, DeepAdapter] = {}


def register_adapter(adapter: DeepAdapter) -> None:
    """Register a deep adapter. Called at module load or by plugins."""
    ADAPTER_REGISTRY[adapter.app_exec] = adapter
    # Also register common aliases
    if adapter.app_exec == "code":
        ADAPTER_REGISTRY["code-oss"] = adapter
        ADAPTER_REGISTRY["code-insiders"] = adapter


def get_adapter(exec_name: str) -> Optional[DeepAdapter]:
    """Look up a deep adapter by executable name. Returns None if none exists."""
    return ADAPTER_REGISTRY.get(exec_name)


# Auto-register built-in adapters
register_adapter(VSCodeAdapter())
register_adapter(JetBrainsAdapter())
