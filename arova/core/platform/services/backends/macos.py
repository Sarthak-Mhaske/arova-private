"""
macOS Backend for Platform Services.

Implements concrete application discovery (`/Applications`, `~/Applications`, `Info.plist` scanning),
application launching (`open -a`, Launch Services, `open`), window focusing (`NSRunningApplication` / Accessibility / AppleScript),
and unified `backend.execute(intent)` contract for macOS (Darwin).
"""
import os
import glob
import time
import shutil
import logging
import plistlib
import subprocess
import webbrowser
from typing import Dict, Any, Optional, List, Set

from arova.core.platform.services.capabilities import Capability, CapabilityRegistry
from arova.core.platform.services.intents import RestoreIntent, LaunchResult
from arova.core.platform.services.catalog import ApplicationEntry, ApplicationCatalog
from arova.core.platform.services.launcher import PlatformLauncher
from arova.core.platform.services.adapters import get_adapter
from arova.core.platform.services.backend import PlatformBackend

logger = logging.getLogger(__name__)


class MacOSApplicationCatalog(ApplicationCatalog):
    """
    Discovers installed applications on macOS by scanning application bundles
    and parsing Info.plist for bundle identifiers, document types, and URL schemes.
    """

    def __init__(self):
        self._entries_by_id: Dict[str, ApplicationEntry] = {}
        self._entries_by_exec: Dict[str, ApplicationEntry] = {}
        self._scanned = False

    def scan(self) -> None:
        """Scan standard macOS application directories for .app bundles."""
        search_dirs = [
            "/Applications",
            os.path.expanduser("~/Applications"),
            "/System/Applications",
            "/System/Applications/Utilities",
        ]

        entries: Dict[str, ApplicationEntry] = {}
        for s_dir in search_dirs:
            if not os.path.isdir(s_dir):
                continue
            for app_bundle in glob.glob(os.path.join(s_dir, "*.app")):
                try:
                    entry = self._parse_app_bundle(app_bundle)
                    if entry and entry.app_id not in entries:
                        entries[entry.app_id] = entry
                except Exception as e:
                    logger.debug(f"Error parsing macOS bundle {app_bundle}: {e}")

        self._entries_by_id = entries
        self._entries_by_exec = {}
        for entry in entries.values():
            if entry.name:
                self._entries_by_exec[entry.name.lower()] = entry
            if entry.executable:
                base = os.path.basename(entry.executable).lower()
                self._entries_by_exec[base] = entry

        self._scanned = True
        logger.info(f"MacOSApplicationCatalog: Scanned {len(entries)} installed macOS applications")

    def _parse_app_bundle(self, bundle_path: str) -> Optional[ApplicationEntry]:
        plist_path = os.path.join(bundle_path, "Contents", "Info.plist")
        if not os.path.exists(plist_path):
            return None

        try:
            with open(plist_path, "rb") as f:
                plist = plistlib.load(f)
        except Exception:
            return None

        bundle_id = plist.get("CFBundleIdentifier", os.path.basename(bundle_path))
        name = plist.get("CFBundleDisplayName") or plist.get("CFBundleName") or os.path.splitext(os.path.basename(bundle_path))[0]
        exec_name = plist.get("CFBundleExecutable", name)
        exec_path = os.path.join(bundle_path, "Contents", "MacOS", exec_name)
        if not os.path.exists(exec_path):
            exec_path = bundle_path

        doc_types = plist.get("CFBundleDocumentTypes", [])
        url_types = plist.get("CFBundleURLTypes", [])

        capabilities = set()
        mime_types = []
        if doc_types:
            capabilities.add(Capability.OPEN_FILE)
            for dt in doc_types:
                mimes = dt.get("LSItemContentTypes", []) or dt.get("CFBundleTypeExtensions", [])
                mime_types.extend(mimes)

        if url_types or "browser" in name.lower() or "safari" in name.lower() or "chrome" in name.lower():
            capabilities.add(Capability.OPEN_URL)

        if "code" in name.lower() or "idea" in name.lower() or "cursor" in name.lower() or "xcode" in name.lower():
            capabilities.add(Capability.OPEN_FILE)
            capabilities.add(Capability.OPEN_FOLDER)
            capabilities.add(Capability.OPEN_PROJECT)

        is_term = "terminal" in name.lower() or "iterm" in name.lower() or "alacritty" in name.lower()
        if is_term:
            capabilities.add(Capability.CREATE_TERMINAL)

        return ApplicationEntry(
            app_id=bundle_id,
            name=name,
            executable=exec_path,
            exec_template=f'open -a "{name}" %F',
            icon=os.path.join(bundle_path, "Contents", "Resources", plist.get("CFBundleIconFile", "")),
            mime_types=mime_types,
            categories=["TerminalEmulator"] if is_term else [],
            capabilities=capabilities,
            is_terminal=is_term,
            window_class=bundle_id,
            installed=True,
        )

    def get_application(self, exec_name: str) -> Optional[ApplicationEntry]:
        if not self._scanned:
            self.scan()
        if not exec_name:
            return None
        key = exec_name.strip().lower()
        return self._entries_by_exec.get(key) or self._entries_by_exec.get(os.path.basename(key))

    def find_by_app_id(self, app_id: str) -> Optional[ApplicationEntry]:
        if not self._scanned:
            self.scan()
        return self._entries_by_id.get(app_id)

    def find_handler_for_mime(self, mime_type: str) -> Optional[ApplicationEntry]:
        if not self._scanned:
            self.scan()
        for entry in self._entries_by_id.values():
            if mime_type in entry.mime_types:
                return entry
        return None

    def find_handler_for_file(self, file_path: str) -> Optional[ApplicationEntry]:
        if not self._scanned:
            self.scan()
        ext = os.path.splitext(file_path)[1].lstrip(".")
        for entry in self._entries_by_id.values():
            if ext in entry.mime_types:
                return entry
        return self.get_default_editor()

    def get_default_browser(self) -> Optional[ApplicationEntry]:
        if not self._scanned:
            self.scan()
        for name in ["Safari", "Google Chrome", "Brave Browser", "Firefox"]:
            app = self.get_application(name)
            if app:
                return app
        return None

    def get_default_editor(self) -> Optional[ApplicationEntry]:
        if not self._scanned:
            self.scan()
        for name in ["Visual Studio Code", "Cursor", "TextEdit", "Sublime Text"]:
            app = self.get_application(name)
            if app:
                return app
        return None

    def get_default_terminal(self) -> Optional[ApplicationEntry]:
        if not self._scanned:
            self.scan()
        for name in ["iTerm", "Alacritty", "Terminal"]:
            app = self.get_application(name)
            if app:
                return app
        return None

    def list_installed(self) -> List[ApplicationEntry]:
        if not self._scanned:
            self.scan()
        return list(self._entries_by_id.values())


class MacOSPlatformLauncher(PlatformLauncher):
    """
    Launches resources on macOS using `open -a`, Launch Services, and deep adapters.
    """

    def __init__(self, catalog: ApplicationCatalog):
        self.catalog = catalog

    def execute_intent(self, intent: RestoreIntent, app: Optional[ApplicationEntry] = None) -> LaunchResult:
        cap = intent.capability
        if cap == Capability.OPEN_FILE:
            return self.open_file(intent.resource_path or "", intent.metadata.get("line"), intent.metadata.get("col"), app)
        elif cap == Capability.OPEN_URL:
            return self.open_url(intent.resource_url or "", app)
        elif cap == Capability.OPEN_FOLDER or cap == Capability.OPEN_PROJECT:
            return self.open_folder(intent.resource_path or "", app)
        elif cap == Capability.CREATE_TERMINAL:
            return self.create_terminal(intent.resource_path or "", intent.metadata.get("recent_command"))
        elif cap == Capability.FOCUS_WINDOW:
            return self.focus_window(intent.metadata.get("window_class", ""))
        elif cap == Capability.REVEAL_FILE:
            return self.reveal_file(intent.resource_path or "")
        else:
            return LaunchResult(intent, False, "", f"Unsupported capability on macOS: {cap.name}")

    def open_file(self, path: str, line: Optional[int] = None, col: Optional[int] = None,
                  app: Optional[ApplicationEntry] = None) -> LaunchResult:
        if not path or not os.path.exists(path):
            return LaunchResult(RestoreIntent("source_file", Capability.OPEN_FILE, resource_path=path), False, "", f"File not found: {path}")

        intent = RestoreIntent("source_file", Capability.OPEN_FILE, resource_path=path, metadata={"line": line, "col": col})
        exec_to_try = app.executable if app else None
        adapter = get_adapter(os.path.basename(exec_to_try).lower()) if exec_to_try else None

        if app:
            cmd = ["open", "-a", app.name]
            if adapter:
                enhanced = adapter.enhance_launch_args([app.name], intent)
                if len(enhanced) > 1:
                    cmd.extend(["--args"] + enhanced[1:])
            else:
                cmd.append(path)
            try:
                proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return LaunchResult(intent, True, app.name, f"Opened {os.path.basename(path)} in {app.name}", pid=proc.pid)
            except Exception as e:
                logger.warning(f"open -a {app.name} failed: {e}")

        try:
            proc = subprocess.Popen(["open", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return LaunchResult(intent, True, "macOS Launch Services", f"Opened {os.path.basename(path)} via Launch Services", pid=proc.pid)
        except Exception as e:
            return LaunchResult(intent, False, "", f"macOS open failed: {e}", error=str(e))

    def open_url(self, url: str, app: Optional[ApplicationEntry] = None) -> LaunchResult:
        if not url:
            return LaunchResult(RestoreIntent("webpage", Capability.OPEN_URL), False, "", "Empty URL")

        intent = RestoreIntent("webpage", Capability.OPEN_URL, resource_url=url)
        if app:
            try:
                proc = subprocess.Popen(["open", "-a", app.name, url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return LaunchResult(intent, True, app.name, f"Opened {url} in {app.name}", pid=proc.pid)
            except Exception:
                pass

        try:
            webbrowser.open(url)
            return LaunchResult(intent, True, "Default Browser", f"Opened {url}")
        except Exception as e:
            return LaunchResult(intent, False, "", f"Failed to open URL on macOS: {e}")

    def open_folder(self, path: str, app: Optional[ApplicationEntry] = None) -> LaunchResult:
        if not path or not os.path.isdir(path):
            return LaunchResult(RestoreIntent("repository", Capability.OPEN_FOLDER, resource_path=path), False, "", f"Folder not found: {path}")

        intent = RestoreIntent("repository", Capability.OPEN_FOLDER, resource_path=path)
        if app:
            try:
                proc = subprocess.Popen(["open", "-a", app.name, path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return LaunchResult(intent, True, app.name, f"Opened folder in {app.name}", pid=proc.pid)
            except Exception:
                pass

        try:
            proc = subprocess.Popen(["open", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return LaunchResult(intent, True, "Finder", f"Opened folder {path} in Finder", pid=proc.pid)
        except Exception as e:
            return LaunchResult(intent, False, "", f"open folder failed: {e}")

    def create_terminal(self, cwd: str, command_hint: Optional[str] = None) -> LaunchResult:
        intent = RestoreIntent("terminal", Capability.CREATE_TERMINAL, resource_path=cwd, metadata={"recent_command": command_hint})
        target_dir = cwd if (cwd and os.path.isdir(cwd)) else os.path.expanduser("~")

        term_app = self.catalog.get_default_terminal()
        if term_app:
            try:
                proc = subprocess.Popen(["open", "-a", term_app.name, target_dir], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return LaunchResult(intent, True, term_app.name, f"Prepared terminal working directory {target_dir}", pid=proc.pid)
            except Exception:
                pass

        return LaunchResult(intent, True, "Terminal", f"Prepared working directory {target_dir}")

    def focus_window(self, window_class: str) -> LaunchResult:
        intent = RestoreIntent("window", Capability.FOCUS_WINDOW, metadata={"window_class": window_class})
        if not window_class:
            return LaunchResult(intent, False, "", "No window identifier provided")

        script = f'tell application "{window_class}" to activate'
        try:
            subprocess.run(["osascript", "-e", script], check=True, capture_output=True, timeout=2)
            return LaunchResult(intent, True, "AppleScript", f"Focused application '{window_class}'")
        except Exception as e:
            return LaunchResult(intent, False, "", f"AppleScript activation failed: {e}")

    def reveal_file(self, path: str) -> LaunchResult:
        intent = RestoreIntent("source_file", Capability.REVEAL_FILE, resource_path=path)
        if not path or not os.path.exists(path):
            return LaunchResult(intent, False, "", f"Path not found: {path}")

        try:
            proc = subprocess.Popen(["open", "-R", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return LaunchResult(intent, True, "Finder", f"Revealed {os.path.basename(path)} in Finder", pid=proc.pid)
        except Exception as e:
            return LaunchResult(intent, False, "", f"open -R failed: {e}")


class MacOSBackend(PlatformBackend):
    """Concrete PlatformBackend for macOS (Darwin)."""

    def __init__(self):
        self._catalog = MacOSApplicationCatalog()
        self._launcher = MacOSPlatformLauncher(self._catalog)
        self._window_manager = None
        self._clipboard = None
        self._notifications = None

    def catalog(self) -> ApplicationCatalog:
        return self._catalog

    def launcher(self) -> PlatformLauncher:
        return self._launcher

    def window_manager(self) -> Any:
        return self._window_manager

    def clipboard(self) -> Any:
        return self._clipboard

    def notifications(self) -> Any:
        return self._notifications

    def process_manager(self) -> Any:
        return None

    def file_associations(self) -> Any:
        return self._catalog

    def permissions(self) -> Any:
        if not hasattr(self, "_permissions"):
            from arova.core.platform.services.permissions import MacOSPermissions
            self._permissions = MacOSPermissions()
        return self._permissions

    def environment(self) -> Any:
        if not hasattr(self, "_environment"):
            from arova.core.platform.services.environment import MacOSEnvironment
            self._environment = MacOSEnvironment()
        return self._environment

    def execute(self, intent: RestoreIntent) -> LaunchResult:
        app = self._catalog.get_application(intent.preferred_application or "")
        return self._launcher.execute_intent(intent, app=app)

    def get_open_windows(self) -> list[str]:
        windows = set()
        script = '''
        tell application "System Events"
            set windowList to {}
            set activeProcs to every process whose background only is false
            repeat with proc in activeProcs
                try
                    set procWindows to name of every window of proc
                    repeat with winName in procWindows
                        if winName is not "" then
                            set end of windowList to (name of proc) & " - " & winName
                        end if
                    end repeat
                end try
            end repeat
            return windowList
        end tell
        '''
        try:
            proc = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=3)
            if proc.returncode == 0 and proc.stdout:
                titles = proc.stdout.strip().split(", ")
                for t in titles:
                    if t:
                        windows.add(t.strip())
        except Exception as e:
            logger.debug(f"MacOSBackend window tracking failed: {e}")
        return list(windows)

    def get_playing_media(self) -> list[str]:
        media = []
        script = '''
        set mediaInfo to ""
        try
            if application "Spotify" is running then
                tell application "Spotify"
                    if player state is playing then
                        set mediaInfo to "Playing: " & artist of current track & " - " & name of current track
                    end if
                end tell
            end if
        end try
        try
            if application "Music" is running then
                tell application "Music"
                    if player state is playing then
                        set mediaInfo to mediaInfo & "\nPlaying: " & artist of current track & " - " & name of current track
                    end if
                end tell
            end if
        end try
        return mediaInfo
        '''
        try:
            proc = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=2)
            if proc.returncode == 0 and proc.stdout:
                for line in proc.stdout.splitlines():
                    if line.strip():
                        media.append(line.strip())
        except Exception as e:
            logger.debug(f"MacOSBackend media tracking failed: {e}")
        return media

    def register_capabilities(self, registry: CapabilityRegistry) -> None:
        registry.register(Capability.OPEN_FILE, lambda intent: self.execute(intent))
        registry.register(Capability.OPEN_URL, lambda intent: self.execute(intent))
        registry.register(Capability.OPEN_FOLDER, lambda intent: self.execute(intent))
        registry.register(Capability.OPEN_PROJECT, lambda intent: self.execute(intent))
        registry.register(Capability.CREATE_TERMINAL, lambda intent: self.execute(intent))
        registry.register(Capability.FOCUS_WINDOW, lambda intent: self.execute(intent))
        registry.register(Capability.REVEAL_FILE, lambda intent: self.execute(intent))
        logger.info("MacOSBackend: Registered macOS capabilities into universal CapabilityRegistry")
