"""
PlatformBackend (ABC) and PlatformBackend.create() factory.

The single entry point for all platform services across different operating
systems.  Arova code above this layer never checks platform.system() and
never invokes OS-specific commands directly.
"""
import abc
import logging
import platform
from typing import Optional, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .catalog import ApplicationCatalog
    from .launcher import PlatformLauncher
    from .capabilities import CapabilityRegistry
    from .permissions import PlatformPermissions
    from .environment import PlatformEnvironment

logger = logging.getLogger(__name__)


class PlatformBackend(abc.ABC):
    """
    Abstract base interface for operating system services.

    Each operating system implements exactly the same contract:
    - LinuxBackend (.desktop / xdg-mime / Wayland / X11)
    - MacOSBackend (Launch Services / Info.plist / AppleScript)
    - WindowsBackend (Registry / App Paths / ShellExecute / Win32)
    """

    @abc.abstractmethod
    def catalog(self) -> "ApplicationCatalog":
        """Return the application discovery catalog for this OS."""

    @abc.abstractmethod
    def launcher(self) -> "PlatformLauncher":
        """Return the platform launcher for executing RestoreIntents."""

    @abc.abstractmethod
    def window_manager(self) -> Any:
        """Return the windowing manager/backend for this OS."""

    @abc.abstractmethod
    def clipboard(self) -> Any:
        """Return the clipboard service interface."""

    @abc.abstractmethod
    def notifications(self) -> Any:
        """Return the desktop notification service interface."""

    @abc.abstractmethod
    def process_manager(self) -> Any:
        """Return the process management interface for querying running apps and PIDs."""

    @abc.abstractmethod
    def file_associations(self) -> Any:
        """Return the MIME and default handler association manager."""

    @abc.abstractmethod
    def permissions(self) -> "PlatformPermissions":
        """Return the OS permissions manager (screen capture, accessibility, etc.)."""

    @abc.abstractmethod
    def environment(self) -> "PlatformEnvironment":
        """Return the runtime environment detector (WSL, Wayland, sandboxing, RDP)."""

    @abc.abstractmethod
    def execute(self, intent: "RestoreIntent") -> "LaunchResult":
        """
        Execute a RestoreIntent cleanly across this platform.
        The backend decides internally whether to use subprocess, Launch Services,
        ShellExecute, xdg-open, Win32 API, AppleScript, or deep adapters.
        """

    @abc.abstractmethod
    def get_open_windows(self) -> list[str]:
        """Return a list of window titles for all active open applications."""

    @abc.abstractmethod
    def get_playing_media(self) -> list[str]:
        """Return a list of formatted strings representing currently playing media across all players."""

    @abc.abstractmethod
    def register_capabilities(self, registry: "CapabilityRegistry") -> None:
        """
        Populate the universal CapabilityRegistry with handler methods
        backed by this platform's launcher and window manager.
        """

    @staticmethod
    def create() -> "PlatformBackend":
        """
        Factory: detect the operating system and instantiate the correct backend.
        If a backend is not available or fails to initialize, raise a clear NotImplementedError.
        """
        sys_name = platform.system().lower()
        logger.info(f"PlatformBackend.create(): Detected OS '{sys_name}'")

        if sys_name == "linux":
            try:
                from .backends.linux import LinuxBackend
                return LinuxBackend()
            except Exception as e:
                logger.error(f"Failed to initialize LinuxBackend: {e}", exc_info=True)
                raise NotImplementedError("Linux backend is not available or failed to initialize in this build.") from e
        elif sys_name == "darwin":
            try:
                from .backends.macos import MacOSBackend
                return MacOSBackend()
            except Exception as e:
                logger.error(f"Failed to initialize MacOSBackend: {e}", exc_info=True)
                raise NotImplementedError("macOS backend is not available or failed to initialize in this build.") from e
        elif sys_name == "windows":
            try:
                from .backends.windows import WindowsBackend
                return WindowsBackend()
            except Exception as e:
                logger.error(f"Failed to initialize WindowsBackend: {e}", exc_info=True)
                raise NotImplementedError("Windows backend is not available or failed to initialize in this build.") from e
        else:
            raise NotImplementedError(f"Operating system '{sys_name}' is not supported in this build.")
