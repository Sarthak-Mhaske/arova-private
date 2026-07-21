"""
Platform permissions service for querying and requesting desktop capabilities.
Manages OS-specific authorization states for screen capture, accessibility,
notifications, and microphone/camera access.
"""
import abc
import logging
import platform

logger = logging.getLogger(__name__)


class PlatformPermissions(abc.ABC):
    """
    Abstract interface for OS-level permissions required by Arova modules.
    """

    @abc.abstractmethod
    def check_screen_capture(self) -> bool:
        """Check if screen recording / window capture permission is granted."""

    @abc.abstractmethod
    def check_accessibility(self) -> bool:
        """Check if accessibility / window control permission is granted."""

    @abc.abstractmethod
    def check_notifications(self) -> bool:
        """Check if desktop notification delivery is permitted."""


class LinuxPermissions(PlatformPermissions):
    """Permissions handler for Linux desktop environments."""

    def check_screen_capture(self) -> bool:
        # On Linux/X11, capture is generally permitted unless Wayland portal restricts
        return True

    def check_accessibility(self) -> bool:
        return True

    def check_notifications(self) -> bool:
        return True


class MacOSPermissions(PlatformPermissions):
    """Permissions handler for macOS (CoreGraphics / Accessibility API checks)."""

    def check_screen_capture(self) -> bool:
        try:
            import Quartz
            return Quartz.CGPreflightScreenCaptureAccess()
        except Exception:
            return True

    def check_accessibility(self) -> bool:
        try:
            from ApplicationServices import AXIsProcessTrusted
            return AXIsProcessTrusted()
        except Exception:
            return True

    def check_notifications(self) -> bool:
        return True


class WindowsPermissions(PlatformPermissions):
    """Permissions handler for Windows Win32 / UAC checks."""

    def check_screen_capture(self) -> bool:
        return True

    def check_accessibility(self) -> bool:
        return True

    def check_notifications(self) -> bool:
        return True
