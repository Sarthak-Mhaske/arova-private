"""
Platform environment service for querying desktop runtime characteristics.
Detects sandboxing (Flatpak, Snap, WSL), display servers (Wayland vs X11),
remote desktop sessions, and hardware display topology.
"""
import os
import abc
import logging
import platform

logger = logging.getLogger(__name__)


class PlatformEnvironment(abc.ABC):
    """
    Abstract interface for OS runtime environment inspection.
    """

    @abc.abstractmethod
    def is_wsl(self) -> bool:
        """Return True if running inside Windows Subsystem for Linux."""

    @abc.abstractmethod
    def is_sandboxed(self) -> bool:
        """Return True if running inside a containerized package (Flatpak, Snap, AppImage)."""

    @abc.abstractmethod
    def windowing_system(self) -> str:
        """Return the active display/windowing architecture ('wayland', 'x11', 'launchservices', 'win32')."""

    @abc.abstractmethod
    def is_remote_desktop(self) -> bool:
        """Return True if the current session is accessed over RDP, VNC, or SSH X11 forwarding."""


class LinuxEnvironment(PlatformEnvironment):
    """Environment detector for Linux systems."""

    def is_wsl(self) -> bool:
        return "microsoft" in platform.uname().release.lower()

    def is_sandboxed(self) -> bool:
        return any([
            os.path.exists("/.flatpak-info"),
            "SNAP" in os.environ,
            "APPIMAGE" in os.environ,
        ])

    def windowing_system(self) -> str:
        if os.environ.get("WAYLAND_DISPLAY"):
            return "wayland"
        if os.environ.get("DISPLAY"):
            return "x11"
        return "headless"

    def is_remote_desktop(self) -> bool:
        return any([
            "SSH_CONNECTION" in os.environ,
            "SSH_CLIENT" in os.environ,
            "XRDP_SESSION" in os.environ,
        ])


class MacOSEnvironment(PlatformEnvironment):
    """Environment detector for macOS systems."""

    def is_wsl(self) -> bool:
        return False

    def is_sandboxed(self) -> bool:
        return "APP_SANDBOX_CONTAINER_ID" in os.environ

    def windowing_system(self) -> str:
        return "launchservices"

    def is_remote_desktop(self) -> bool:
        return "SSH_CONNECTION" in os.environ


class WindowsEnvironment(PlatformEnvironment):
    """Environment detector for Windows systems."""

    def is_wsl(self) -> bool:
        return False

    def is_sandboxed(self) -> bool:
        return False

    def windowing_system(self) -> str:
        return "win32"

    def is_remote_desktop(self) -> bool:
        return "SESSIONNAME" in os.environ and "RDP" in os.environ.get("SESSIONNAME", "")
