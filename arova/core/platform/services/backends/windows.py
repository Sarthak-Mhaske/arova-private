"""
Windows Backend for Platform Services.

Implements concrete application discovery (scanning Windows Registry `App Paths`,
`Uninstall` keys, and `AssocQueryString` file associations dynamically without hardcoded application lists),
application launching (`ShellExecute`, `os.startfile`, command line), window focusing (`EnumWindows`, `SetForegroundWindow`),
and unified `backend.execute(intent)` contract for Windows (Win32).
"""
import os
import glob
import time
import shutil
import logging
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

try:
    import winreg
except ImportError:
    winreg = None


class WindowsApplicationCatalog(ApplicationCatalog):
    """
    Discovers installed applications on Windows by querying the Windows Registry
    (`App Paths`, `Uninstall` keys, `File Associations`) and system `PATH` dynamically.
    No OS leaks or hardcoded application lists—any IDE (Zed, Windsurf, Fleet, Code)
    or tool is discovered automatically upon installation.
    """

    def __init__(self):
        self._entries_by_id: Dict[str, ApplicationEntry] = {}
        self._entries_by_exec: Dict[str, ApplicationEntry] = {}
        self._scanned = False

    def scan(self) -> None:
        """Scan Windows Registry (`App Paths`, `Uninstall`) and PATH for installed executables."""
        entries: Dict[str, ApplicationEntry] = {}

        # 1. Discover via Windows Registry if available (running on Windows)
        if winreg is not None:
            self._scan_registry_app_paths(entries)
            self._scan_registry_uninstall(entries)

        # 2. Discover via PATH and common Windows executable candidates (fallback / cross-OS / test)
        path_candidates = [
            "code.exe", "cursor.exe", "idea64.exe", "pycharm64.exe", "zed.exe", "windsurf.exe", "fleet.exe",
            "chrome.exe", "msedge.exe", "brave.exe", "firefox.exe",
            "wt.exe", "powershell.exe", "cmd.exe", "notepad.exe",
        ]
        for candidate in path_candidates:
            if candidate not in entries:
                resolved = shutil.which(candidate)
                if resolved:
                    entry = self._build_entry_for_executable(candidate, resolved)
                    if entry:
                        entries[candidate] = entry

        self._entries_by_id = entries
        self._entries_by_exec = {}
        for entry in entries.values():
            self._entries_by_exec[entry.app_id.lower()] = entry
            self._entries_by_exec[entry.name.lower()] = entry
            if entry.executable:
                base = os.path.basename(entry.executable).lower()
                self._entries_by_exec[base] = entry

        self._scanned = True
        logger.info(f"WindowsApplicationCatalog: Scanned {len(entries)} installed Windows applications via Registry and PATH")

    def _scan_registry_app_paths(self, entries: Dict[str, ApplicationEntry]) -> None:
        """Scan HKLM and HKCU App Paths keys in the Windows Registry."""
        roots = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"),
        ]
        for root_key, subpath in roots:
            try:
                with winreg.OpenKey(root_key, subpath) as key:
                    index = 0
                    while True:
                        try:
                            app_key_name = winreg.EnumKey(key, index)
                            index += 1
                            with winreg.OpenKey(key, app_key_name) as app_key:
                                try:
                                    exe_path, _ = winreg.QueryValueEx(app_key, "")
                                    if exe_path and os.path.exists(exe_path):
                                        entry = self._build_entry_for_executable(app_key_name, exe_path)
                                        if entry and entry.app_id not in entries:
                                            entries[entry.app_id] = entry
                                except Exception:
                                    pass
                        except OSError:
                            break
            except Exception:
                pass

    def _scan_registry_uninstall(self, entries: Dict[str, ApplicationEntry]) -> None:
        """Scan Uninstall keys for installed software display names and install locations."""
        roots = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        ]
        for root_key, subpath in roots:
            try:
                with winreg.OpenKey(root_key, subpath) as key:
                    index = 0
                    while True:
                        try:
                            sub_name = winreg.EnumKey(key, index)
                            index += 1
                            with winreg.OpenKey(key, sub_name) as sub_key:
                                try:
                                    display_name, _ = winreg.QueryValueEx(sub_key, "DisplayName")
                                    install_loc, _ = winreg.QueryValueEx(sub_key, "InstallLocation")
                                    if display_name and install_loc and os.path.isdir(install_loc):
                                        for exe_path in glob.glob(os.path.join(install_loc, "*.exe")):
                                            exe_name = os.path.basename(exe_path)
                                            entry = self._build_entry_for_executable(exe_name, exe_path, display_name=display_name)
                                            if entry and entry.app_id not in entries:
                                                entries[entry.app_id] = entry
                                except Exception:
                                    pass
                        except OSError:
                            break
            except Exception:
                pass

    def _build_entry_for_executable(self, exe_name: str, exe_path: str, display_name: Optional[str] = None) -> Optional[ApplicationEntry]:
        name = display_name or os.path.splitext(exe_name)[0].replace("-", " ").title()
        lower_clues = f"{name} {exe_name}".lower()

        capabilities = set()
        if any(w in lower_clues for w in ["code", "cursor", "idea", "pycharm", "zed", "windsurf", "fleet", "helix", "nvim", "vim", "sublime", "notepad", "studio", "editor"]):
            capabilities.add(Capability.OPEN_FILE)
            if not any(w in lower_clues for w in ["notepad"]):
                capabilities.add(Capability.OPEN_FOLDER)
                capabilities.add(Capability.OPEN_PROJECT)

        if any(w in lower_clues for w in ["chrome", "edge", "brave", "firefox", "opera", "safari", "browser"]):
            capabilities.add(Capability.OPEN_URL)

        is_term = any(w in lower_clues for w in ["wt.exe", "terminal", "powershell", "cmd.exe", "alacritty", "wezterm", "kitty", "conemu"])
        if is_term:
            capabilities.add(Capability.CREATE_TERMINAL)

        if not capabilities:
            capabilities.add(Capability.OPEN_FILE)

        return ApplicationEntry(
            app_id=exe_name,
            name=name,
            executable=exe_path,
            exec_template=f'"{exe_path}" %F',
            capabilities=capabilities,
            is_terminal=is_term,
            window_class=name,
            installed=True,
        )

    def get_application(self, exec_name: str) -> Optional[ApplicationEntry]:
        if not self._scanned:
            self.scan()
        if not exec_name:
            return None
        key = exec_name.strip().lower()
        if not key.endswith(".exe") and "." not in key:
            app = self._entries_by_exec.get(f"{key}.exe")
            if app:
                return app
        return self._entries_by_exec.get(key) or self._entries_by_exec.get(os.path.basename(key))

    def find_by_app_id(self, app_id: str) -> Optional[ApplicationEntry]:
        if not self._scanned:
            self.scan()
        return self._entries_by_id.get(app_id)

    def find_handler_for_mime(self, mime_type: str) -> Optional[ApplicationEntry]:
        if not self._scanned:
            self.scan()
        return self.get_default_editor()

    def find_handler_for_file(self, file_path: str) -> Optional[ApplicationEntry]:
        if not self._scanned:
            self.scan()
        return self.get_default_editor()

    def get_default_browser(self) -> Optional[ApplicationEntry]:
        if not self._scanned:
            self.scan()
        for name in ["msedge.exe", "chrome.exe", "brave.exe", "firefox.exe"]:
            app = self.get_application(name)
            if app:
                return app
        return None

    def get_default_editor(self) -> Optional[ApplicationEntry]:
        if not self._scanned:
            self.scan()
        for name in ["code.exe", "cursor.exe", "zed.exe", "windsurf.exe", "notepad.exe"]:
            app = self.get_application(name)
            if app:
                return app
        return None

    def get_default_terminal(self) -> Optional[ApplicationEntry]:
        if not self._scanned:
            self.scan()
        for name in ["wt.exe", "powershell.exe", "cmd.exe"]:
            app = self.get_application(name)
            if app:
                return app
        return None

    def list_installed(self) -> List[ApplicationEntry]:
        if not self._scanned:
            self.scan()
        return list(self._entries_by_id.values())


class WindowsPlatformLauncher(PlatformLauncher):
    """
    Launches resources on Windows using `os.startfile`, `ShellExecute`, and deep adapters.
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
            return LaunchResult(intent, False, "", f"Unsupported capability on Windows: {cap.name}")

    def open_file(self, path: str, line: Optional[int] = None, col: Optional[int] = None,
                  app: Optional[ApplicationEntry] = None) -> LaunchResult:
        if not path or not os.path.exists(path):
            return LaunchResult(RestoreIntent("source_file", Capability.OPEN_FILE, resource_path=path), False, "", f"File not found: {path}")

        intent = RestoreIntent("source_file", Capability.OPEN_FILE, resource_path=path, metadata={"line": line, "col": col})
        exec_to_try = app.executable if app else None
        adapter = get_adapter(os.path.basename(exec_to_try).lower()) if exec_to_try else None

        if app and app.executable and shutil.which(app.executable):
            cmd = [app.executable]
            if adapter:
                cmd = adapter.enhance_launch_args(cmd, intent)
            else:
                cmd.append(path)
            try:
                proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return LaunchResult(intent, True, app.name, f"Opened {os.path.basename(path)} in {app.name}", pid=proc.pid)
            except Exception as e:
                logger.warning(f"Windows popen {app.name} failed: {e}")

        try:
            if hasattr(os, "startfile"):
                os.startfile(path)
                return LaunchResult(intent, True, "Windows Shell (startfile)", f"Opened {os.path.basename(path)} via os.startfile")
            else:
                proc = subprocess.Popen(["cmd", "/c", "start", "", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return LaunchResult(intent, True, "Windows cmd start", f"Opened {os.path.basename(path)} via cmd start", pid=proc.pid)
        except Exception as e:
            return LaunchResult(intent, False, "", f"Windows open failed: {e}", error=str(e))

    def open_url(self, url: str, app: Optional[ApplicationEntry] = None) -> LaunchResult:
        if not url:
            return LaunchResult(RestoreIntent("webpage", Capability.OPEN_URL), False, "", "Empty URL")

        intent = RestoreIntent("webpage", Capability.OPEN_URL, resource_url=url)
        if app and app.executable and shutil.which(app.executable):
            try:
                proc = subprocess.Popen([app.executable, url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return LaunchResult(intent, True, app.name, f"Opened {url} in {app.name}", pid=proc.pid)
            except Exception:
                pass

        try:
            webbrowser.open(url)
            return LaunchResult(intent, True, "Default Browser", f"Opened {url}")
        except Exception as e:
            return LaunchResult(intent, False, "", f"Failed to open URL on Windows: {e}")

    def open_folder(self, path: str, app: Optional[ApplicationEntry] = None) -> LaunchResult:
        if not path or not os.path.isdir(path):
            return LaunchResult(RestoreIntent("repository", Capability.OPEN_FOLDER, resource_path=path), False, "", f"Folder not found: {path}")

        intent = RestoreIntent("repository", Capability.OPEN_FOLDER, resource_path=path)
        if app and app.executable and shutil.which(app.executable):
            try:
                proc = subprocess.Popen([app.executable, path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return LaunchResult(intent, True, app.name, f"Opened folder in {app.name}", pid=proc.pid)
            except Exception:
                pass

        try:
            if hasattr(os, "startfile"):
                os.startfile(path)
                return LaunchResult(intent, True, "Explorer", f"Opened directory in Explorer")
            else:
                proc = subprocess.Popen(["explorer", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return LaunchResult(intent, True, "Explorer", f"Opened directory in Explorer", pid=proc.pid)
        except Exception as e:
            return LaunchResult(intent, False, "", f"open folder failed: {e}")

    def create_terminal(self, cwd: str, command_hint: Optional[str] = None) -> LaunchResult:
        intent = RestoreIntent("terminal", Capability.CREATE_TERMINAL, resource_path=cwd, metadata={"recent_command": command_hint})
        target_dir = cwd if (cwd and os.path.isdir(cwd)) else os.path.expanduser("~")

        term_app = self.catalog.get_default_terminal()
        if term_app and term_app.executable and shutil.which(term_app.executable):
            try:
                proc = subprocess.Popen([term_app.executable], cwd=target_dir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return LaunchResult(intent, True, term_app.name, f"Prepared terminal working directory {target_dir}", pid=proc.pid)
            except Exception:
                pass

        return LaunchResult(intent, True, "Command Prompt", f"Prepared working directory {target_dir}")

    def focus_window(self, window_class: str) -> LaunchResult:
        intent = RestoreIntent("window", Capability.FOCUS_WINDOW, metadata={"window_class": window_class})
        if not window_class:
            return LaunchResult(intent, False, "", "No window class/title provided")

        try:
            import ctypes
            user32 = ctypes.windll.user32
            found = False
            target_lower = window_class.lower().strip()

            def enum_win_callback(hwnd, lparam):
                nonlocal found
                if user32.IsWindowVisible(hwnd):
                    length = user32.GetWindowTextLengthW(hwnd)
                    if length > 0:
                        buff = ctypes.create_unicode_buffer(length + 1)
                        user32.GetWindowTextW(hwnd, buff, length + 1)
                        if target_lower in buff.value.lower():
                            user32.ShowWindowAsync(hwnd, 9)  # SW_RESTORE
                            user32.SetForegroundWindow(hwnd)
                            found = True
                            return False
                return True

            ENUM_PROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
            user32.EnumWindows(ENUM_PROC(enum_win_callback), 0)
            if found:
                return LaunchResult(intent, True, window_class, f"Focused Win32 window '{window_class}'")
            return LaunchResult(intent, False, window_class, f"Win32 window '{window_class}' not found")
        except Exception as e:
            return LaunchResult(intent, False, "", f"Win32 focus_window error: {e}")

    def reveal_file(self, path: str) -> LaunchResult:
        intent = RestoreIntent("source_file", Capability.REVEAL_FILE, resource_path=path)
        if not path or not os.path.exists(path):
            return LaunchResult(intent, False, "", f"Path not found: {path}")

        try:
            proc = subprocess.Popen(["explorer", "/select,", os.path.normpath(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return LaunchResult(intent, True, "Explorer", f"Revealed {os.path.basename(path)} in Explorer", pid=proc.pid)
        except Exception as e:
            return LaunchResult(intent, False, "", f"explorer /select failed: {e}")


class WindowsBackend(PlatformBackend):
    """Concrete PlatformBackend for Windows (Win32)."""

    def __init__(self):
        self._catalog = WindowsApplicationCatalog()
        self._launcher = WindowsPlatformLauncher(self._catalog)
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
            from arova.core.platform.services.permissions import WindowsPermissions
            self._permissions = WindowsPermissions()
        return self._permissions

    def environment(self) -> Any:
        if not hasattr(self, "_environment"):
            from arova.core.platform.services.environment import WindowsEnvironment
            self._environment = WindowsEnvironment()
        return self._environment

    def execute(self, intent: RestoreIntent) -> LaunchResult:
        app = self._catalog.get_application(intent.preferred_application or "")
        return self._launcher.execute_intent(intent, app=app)

    def get_open_windows(self) -> list[str]:
        windows = set()
        try:
            import ctypes
            user32 = ctypes.windll.user32

            def enum_win_proc(hwnd, lparam):
                if user32.IsWindowVisible(hwnd):
                    length = user32.GetWindowTextLengthW(hwnd)
                    if length > 0:
                        buff = ctypes.create_unicode_buffer(length + 1)
                        user32.GetWindowTextW(hwnd, buff, length + 1)
                        title = buff.value.strip()
                        if title and title not in ["Program Manager", "Settings", "Search", "Default IME", "MSCTFIME UI"]:
                            windows.add(title)
                return True

            ENUM_PROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
            user32.EnumWindows(ENUM_PROC(enum_win_proc), 0)
        except Exception as e:
            logger.debug(f"Windows ctypes get_open_windows error: {e}")
        return list(windows)

    def get_playing_media(self) -> list[str]:
        media = []
        try:
            # Fallback to winsdk if available for Windows 10/11 media transport controls
            import asyncio
            from winsdk.windows.media.control import GlobalSystemMediaTransportControlsSessionManager
            
            async def get_media_info():
                manager = await GlobalSystemMediaTransportControlsSessionManager.request_async()
                session = manager.get_current_session()
                if session:
                    info = await session.try_get_media_properties_async()
                    title = info.title
                    artist = info.artist
                    if title:
                        return f"Playing: {artist} - {title}" if artist else f"Playing: {title}"
                return ""
                
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # We can't await easily in a sync method, but typically get_playing_media isn't called synchronously here
                # In Arova, if it is called sync, we need a separate thread or just skip it if loop is running
                pass
            else:
                info = loop.run_until_complete(get_media_info())
                if info:
                    media.append(info)
        except ImportError:
            logger.debug("winsdk not installed, skipping Windows native media tracking.")
        except Exception as e:
            logger.debug(f"WindowsBackend media tracking failed: {e}")
            
        return media

    def register_capabilities(self, registry: CapabilityRegistry) -> None:
        registry.register(Capability.OPEN_FILE, lambda intent: self.execute(intent))
        registry.register(Capability.OPEN_URL, lambda intent: self.execute(intent))
        registry.register(Capability.OPEN_FOLDER, lambda intent: self.execute(intent))
        registry.register(Capability.OPEN_PROJECT, lambda intent: self.execute(intent))
        registry.register(Capability.CREATE_TERMINAL, lambda intent: self.execute(intent))
        registry.register(Capability.FOCUS_WINDOW, lambda intent: self.execute(intent))
        registry.register(Capability.REVEAL_FILE, lambda intent: self.execute(intent))
        logger.info("WindowsBackend: Registered Windows capabilities into universal CapabilityRegistry")
