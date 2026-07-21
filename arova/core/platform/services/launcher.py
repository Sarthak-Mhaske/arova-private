"""
PlatformLauncher (abstract).

Executes RestoreIntents against the operating system.  Each platform backend
provides a concrete implementation that knows the right subprocess commands,
environment variables, and fallback mechanisms for its OS.
"""
import abc
import logging
from typing import Optional, List, TYPE_CHECKING

if TYPE_CHECKING:
    from .catalog import ApplicationEntry
    from .intents import RestoreIntent, LaunchResult

logger = logging.getLogger(__name__)


class PlatformLauncher(abc.ABC):
    """
    Platform-agnostic interface for launching applications and resources.

    Concrete implementations:
    - Linux: subprocess.Popen, xdg-open fallback
    - macOS: open -a, NSWorkspace
    - Windows: ShellExecute, start
    """

    @abc.abstractmethod
    def execute_intent(self, intent: "RestoreIntent", app: Optional["ApplicationEntry"] = None) -> "LaunchResult":
        """Execute a single RestoreIntent. Core dispatch method."""

    @abc.abstractmethod
    def open_file(self, path: str, line: Optional[int] = None, col: Optional[int] = None,
                  app: Optional["ApplicationEntry"] = None) -> "LaunchResult":
        """Open a file, optionally at a specific line and column."""

    @abc.abstractmethod
    def open_url(self, url: str, app: Optional["ApplicationEntry"] = None) -> "LaunchResult":
        """Open a URL in a browser."""

    @abc.abstractmethod
    def open_folder(self, path: str, app: Optional["ApplicationEntry"] = None) -> "LaunchResult":
        """Open a folder in a file manager or editor."""

    @abc.abstractmethod
    def create_terminal(self, cwd: str, command_hint: Optional[str] = None) -> "LaunchResult":
        """
        Prepare a terminal with working directory set.
        command_hint is informational only — never auto-executed.
        """

    @abc.abstractmethod
    def focus_window(self, window_class: str) -> "LaunchResult":
        """Bring an existing window to the front by its window class."""

    @abc.abstractmethod
    def reveal_file(self, path: str) -> "LaunchResult":
        """Show a file in its parent folder (file manager)."""
