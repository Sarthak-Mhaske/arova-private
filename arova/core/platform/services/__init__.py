"""
Platform Services — Intent-driven, capability-based restoration architecture.
Discovers installed applications from the OS, learns user preferences,
and restores any resource through a stable capability interface.
"""
from .capabilities import Capability, CapabilityRegistry
from .intents import RestoreIntent, LaunchPlan, LaunchResult
from .catalog import ApplicationCatalog, ApplicationEntry
from .launcher import PlatformLauncher
from .backend import PlatformBackend
from .permissions import PlatformPermissions
from .environment import PlatformEnvironment

__all__ = [
    "Capability", "CapabilityRegistry",
    "RestoreIntent", "LaunchPlan", "LaunchResult",
    "ApplicationCatalog", "ApplicationEntry",
    "PlatformLauncher", "PlatformBackend",
    "PlatformPermissions", "PlatformEnvironment",
]
