"""
Concrete platform backend implementations for Arova cross-platform contract.
"""
from .linux import LinuxBackend, LinuxApplicationCatalog, LinuxPlatformLauncher
from .macos import MacOSBackend, MacOSApplicationCatalog, MacOSPlatformLauncher
from .windows import WindowsBackend, WindowsApplicationCatalog, WindowsPlatformLauncher

__all__ = [
    "LinuxBackend", "LinuxApplicationCatalog", "LinuxPlatformLauncher",
    "MacOSBackend", "MacOSApplicationCatalog", "MacOSPlatformLauncher",
    "WindowsBackend", "WindowsApplicationCatalog", "WindowsPlatformLauncher",
]
