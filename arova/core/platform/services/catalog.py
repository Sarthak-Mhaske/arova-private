"""
ApplicationEntry and ApplicationCatalog (abstract).

The catalog discovers installed applications from the OS and exposes them
through a platform-agnostic interface.  The concrete implementation is
provided by a platform backend (e.g., LinuxApplicationCatalog).
"""
import abc
import logging
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List, Set

from .capabilities import Capability

logger = logging.getLogger(__name__)


@dataclass
class ApplicationEntry:
    """
    A single application discovered from the operating system.

    Capabilities are *inferred* from the application metadata (e.g., Exec
    template, MIME types, categories) — never manually specified as booleans.
    """
    app_id: str
    """Unique identifier. On Linux: 'blender.desktop'. On macOS: 'com.microsoft.VSCode'."""

    name: str
    """Human-readable name: 'Blender', 'Visual Studio Code'."""

    executable: str
    """Resolved command name or path: 'blender', '/usr/bin/code'."""

    exec_template: str
    """Raw Exec line from discovery source: 'blender %f', 'code %F'."""

    icon: str = ""
    """Icon identifier for UI display."""

    mime_types: List[str] = field(default_factory=list)
    """MIME types this application can handle."""

    categories: List[str] = field(default_factory=list)
    """Category tags: ['Graphics', '3DGraphics', 'RasterGraphics']."""

    capabilities: Set[Capability] = field(default_factory=set)
    """Inferred capabilities: {OPEN_FILE, OPEN_PROJECT}."""

    is_terminal: bool = False
    """True if this is a terminal/CLI application."""

    window_class: str = ""
    """Window manager class for focus/raise operations (StartupWMClass on Linux)."""

    installed: bool = True
    """True if the executable was found in PATH at scan time."""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "app_id": self.app_id,
            "name": self.name,
            "executable": self.executable,
            "exec_template": self.exec_template,
            "icon": self.icon,
            "mime_types": self.mime_types,
            "categories": self.categories,
            "capabilities": [c.name for c in self.capabilities],
            "is_terminal": self.is_terminal,
            "window_class": self.window_class,
            "installed": self.installed,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ApplicationEntry":
        caps = set()
        for c_name in data.get("capabilities", []):
            try:
                caps.add(Capability[c_name])
            except KeyError:
                pass
        return cls(
            app_id=data["app_id"],
            name=data.get("name", ""),
            executable=data.get("executable", ""),
            exec_template=data.get("exec_template", ""),
            icon=data.get("icon", ""),
            mime_types=data.get("mime_types", []),
            categories=data.get("categories", []),
            capabilities=caps,
            is_terminal=data.get("is_terminal", False),
            window_class=data.get("window_class", ""),
            installed=data.get("installed", True),
        )


class ApplicationCatalog(abc.ABC):
    """
    Platform-agnostic interface for discovering installed applications.

    Each platform backend provides a concrete implementation:
    - Linux: parses .desktop files, xdg-mime, PATH
    - macOS: Launch Services, /Applications, bundle IDs
    - Windows: Registry, Start Menu, file associations
    """

    @abc.abstractmethod
    def scan(self) -> None:
        """Discover all installed applications from the operating system."""

    @abc.abstractmethod
    def get_application(self, exec_name: str) -> Optional[ApplicationEntry]:
        """Look up an application by executable name (e.g., 'code', 'blender')."""

    @abc.abstractmethod
    def find_by_app_id(self, app_id: str) -> Optional[ApplicationEntry]:
        """Look up by platform-specific ID (e.g., 'blender.desktop')."""

    @abc.abstractmethod
    def find_handler_for_mime(self, mime_type: str) -> Optional[ApplicationEntry]:
        """Find the system default handler for a MIME type."""

    @abc.abstractmethod
    def find_handler_for_file(self, file_path: str) -> Optional[ApplicationEntry]:
        """Find the handler for a specific file (uses MIME detection)."""

    @abc.abstractmethod
    def get_default_browser(self) -> Optional[ApplicationEntry]:
        """Return the system default web browser."""

    @abc.abstractmethod
    def get_default_editor(self) -> Optional[ApplicationEntry]:
        """Return the system default text editor."""

    @abc.abstractmethod
    def get_default_terminal(self) -> Optional[ApplicationEntry]:
        """Return the system default terminal emulator."""

    @abc.abstractmethod
    def list_installed(self) -> List[ApplicationEntry]:
        """Return all discovered, installed applications (NoDisplay filtered out)."""

    def rescan(self) -> None:
        """Re-scan for newly installed or removed applications."""
        self.scan()
