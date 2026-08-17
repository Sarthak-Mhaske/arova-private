"""
Linux Backend for Platform Services.

Implements concrete application discovery (parsing .desktop files, xdg-mime, PATH),
application launching (subprocess.Popen, webbrowser/xdg-open fallback), window focusing,
and capability registration for Linux desktop environments (X11 / Wayland).
"""
import os
import glob
import time
import shutil
import logging
import mimetypes
import subprocess
import webbrowser
import configparser
from typing import Dict, Any, Optional, List, Set

from arova.core.platform.services.capabilities import Capability, CapabilityRegistry
from arova.core.platform.services.intents import RestoreIntent, LaunchResult
from arova.core.platform.services.catalog import ApplicationEntry, ApplicationCatalog
from arova.core.platform.services.launcher import PlatformLauncher
from arova.core.platform.services.adapters import get_adapter
from arova.core.platform.services.backend import PlatformBackend

logger = logging.getLogger(__name__)


class LinuxApplicationCatalog(ApplicationCatalog):
    """
    Discovers installed applications on Linux by scanning .desktop files
    and resolving MIME associations via xdg-mime.
    """

    def __init__(self):
        self._entries_by_id: Dict[str, ApplicationEntry] = {}
        self._entries_by_exec: Dict[str, ApplicationEntry] = {}
        self._mime_map: Dict[str, List[str]] = {}  # mime -> list of app_ids
        self._scanned = False

    def scan(self) -> None:
        """Scan standard XDG application directories for .desktop files."""
        search_dirs = [
            os.path.expanduser("~/.local/share/applications"),
            "/usr/share/applications",
            "/usr/local/share/applications",
            "/var/lib/flatpak/exports/share/applications",
            "/var/lib/snapd/desktop/applications",
        ]

        entries: Dict[str, ApplicationEntry] = {}
        mime_map: Dict[str, List[str]] = {}

        for s_dir in search_dirs:
            if not os.path.isdir(s_dir):
                continue
            for fpath in glob.glob(os.path.join(s_dir, "*.desktop")):
                try:
                    entry = self._parse_desktop_file(fpath)
                    if entry and entry.installed:
                        app_id = entry.app_id
                        if app_id not in entries:
                            entries[app_id] = entry
                            for m in entry.mime_types:
                                mime_map.setdefault(m, []).append(app_id)
                except Exception as e:
                    logger.debug(f"Error parsing .desktop file {fpath}: {e}")

        self._entries_by_id = entries
        self._entries_by_exec = {}
        for entry in entries.values():
            if entry.executable:
                base_exec = os.path.basename(entry.executable)
                self._entries_by_exec[base_exec.lower()] = entry
                self._entries_by_exec[entry.name.lower()] = entry
            if entry.exec_template:
                raw_base = os.path.basename(entry.exec_template.split()[0])
                if raw_base and raw_base.lower() not in self._entries_by_exec:
                    self._entries_by_exec[raw_base.lower()] = entry

        self._mime_map = mime_map
        self._scanned = True
        logger.info(f"LinuxApplicationCatalog: Scanned {len(entries)} installed applications from .desktop files")

    def _parse_desktop_file(self, fpath: str) -> Optional[ApplicationEntry]:
        cp = configparser.ConfigParser(interpolation=None)
        cp.read(fpath, encoding="utf-8")

        if not cp.has_section("Desktop Entry"):
            return None

        sec = cp["Desktop Entry"]
        if sec.get("Type", "").lower() != "application":
            return None
        if sec.get("NoDisplay", "false").lower() == "true":
            return None

        exec_line = sec.get("Exec", "").strip()
        if not exec_line:
            return None

        tokens = exec_line.split()
        raw_cmd = tokens[0]
        resolved_exec = shutil.which(raw_cmd)
        installed = resolved_exec is not None

        if installed and resolved_exec and os.path.basename(resolved_exec) != os.path.basename(raw_cmd):
            executable = raw_cmd if os.path.basename(raw_cmd) != "code" else resolved_exec
        else:
            executable = resolved_exec or raw_cmd

        name = sec.get("Name", os.path.basename(fpath))
        icon = sec.get("Icon", "")
        wm_class = sec.get("StartupWMClass", name)
        is_term = sec.get("Terminal", "false").lower() == "true"

        raw_mimes = [m.strip() for m in sec.get("MimeType", "").split(";") if m.strip()]
        raw_cats = [c.strip() for c in sec.get("Categories", "").split(";") if c.strip()]

        capabilities = set()
        if "%f" in exec_line or "%F" in exec_line or raw_mimes or "TextEditor" in raw_cats or "IDE" in raw_cats:
            capabilities.add(Capability.OPEN_FILE)
        if "%u" in exec_line or "%U" in exec_line or any(m.startswith("x-scheme-handler/") for m in raw_mimes) or "WebBrowser" in raw_cats:
            capabilities.add(Capability.OPEN_URL)
        if "FileManager" in raw_cats or "IDE" in raw_cats:
            capabilities.add(Capability.OPEN_FOLDER)
            capabilities.add(Capability.OPEN_PROJECT)
        if is_term or "TerminalEmulator" in raw_cats:
            capabilities.add(Capability.CREATE_TERMINAL)

        return ApplicationEntry(
            app_id=os.path.basename(fpath),
            name=name,
            executable=executable,
            exec_template=exec_line,
            icon=icon,
            mime_types=raw_mimes,
            categories=raw_cats,
            capabilities=capabilities,
            is_terminal=is_term,
            window_class=wm_class,
            installed=installed,
        )

    def get_application(self, exec_name: str) -> Optional[ApplicationEntry]:
        if not self._scanned:
            self.scan()
        if not exec_name:
            return None
        key = exec_name.strip().lower()
        key_base = os.path.basename(key)
        return self._entries_by_exec.get(key) or self._entries_by_exec.get(key_base)

    def find_by_app_id(self, app_id: str) -> Optional[ApplicationEntry]:
        if not self._scanned:
            self.scan()
        return self._entries_by_id.get(app_id)

    def find_handler_for_mime(self, mime_type: str) -> Optional[ApplicationEntry]:
        if not self._scanned:
            self.scan()
        if not mime_type:
            return None

        try:
            res = subprocess.run(["xdg-mime", "query", "default", mime_type], capture_output=True, text=True, timeout=2)
            desktop_file = res.stdout.strip()
            if desktop_file and desktop_file in self._entries_by_id:
                return self._entries_by_id[desktop_file]
        except Exception:
            pass

        app_ids = self._mime_map.get(mime_type, [])
        for aid in app_ids:
            if aid in self._entries_by_id:
                return self._entries_by_id[aid]
        return None

    def find_handler_for_file(self, file_path: str) -> Optional[ApplicationEntry]:
        mime, _ = mimetypes.guess_type(file_path)
        if not mime:
            if file_path.endswith((".py", ".js", ".ts", ".tsx", ".jsx", ".rs", ".go", ".c", ".cpp", ".h", ".md", ".json", ".yaml", ".yml", ".toml")):
                mime = "text/plain"
        return self.find_handler_for_mime(mime or "text/plain")

    def get_default_browser(self) -> Optional[ApplicationEntry]:
        for mime in ["x-scheme-handler/https", "x-scheme-handler/http", "text/html"]:
            handler = self.find_handler_for_mime(mime)
            if handler:
                return handler
        return None

    def get_default_editor(self) -> Optional[ApplicationEntry]:
        return self.find_handler_for_mime("text/plain")

    def get_default_terminal(self) -> Optional[ApplicationEntry]:
        if not self._scanned:
            self.scan()
        for entry in self._entries_by_id.values():
            if "TerminalEmulator" in entry.categories and entry.installed:
                return entry
        return None

    def list_installed(self) -> List[ApplicationEntry]:
        if not self._scanned:
            self.scan()
        return list(self._entries_by_id.values())


class LinuxPlatformLauncher(PlatformLauncher):
    """
    Launches resources on Linux using concrete subprocess commands and webbrowser/xdg-open fallback.
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
            if intent.resource_path:
                return self.open_file(intent.resource_path, app=app)
            elif intent.resource_url:
                return self.open_url(intent.resource_url, app=app)
            return LaunchResult(intent, False, "", f"Unsupported capability: {cap.name}")

    def _is_window_active(self, keyword: str) -> bool:
        if not keyword:
            return False
        kw = keyword.lower()
        if shutil.which("hyprctl"):
            try:
                import json
                proc = subprocess.run(["hyprctl", "clients", "-j"], capture_output=True, text=True, timeout=1.5)
                if proc.returncode == 0:
                    data = json.loads(proc.stdout)
                    for client in data:
                        title = (client.get("title") or "").lower()
                        cls = (client.get("class") or "").lower()
                        if kw in title or kw in cls:
                            return True
            except Exception:
                pass
        if shutil.which("wmctrl"):
            try:
                proc = subprocess.run(["wmctrl", "-l"], capture_output=True, text=True, timeout=1.5)
                if proc.returncode == 0:
                    for line in proc.stdout.splitlines():
                        if kw in line.lower():
                            return True
            except Exception:
                pass
        return False

    def open_file(self, path: str, line: Optional[int] = None, col: Optional[int] = None,
                  app: Optional[ApplicationEntry] = None) -> LaunchResult:
        if not path or not os.path.exists(path):
            return LaunchResult(
                RestoreIntent("source_file", Capability.OPEN_FILE, resource_path=path),
                False, app.name if app else "", f"File does not exist: {path}", error="FileNotFound"
            )

        intent = RestoreIntent("source_file", Capability.OPEN_FILE, resource_path=path, metadata={"line": line, "col": col})
        fname = os.path.basename(path)

        # Prefer native editor binaries on PATH first
        exec_bin = shutil.which("antigravity-ide") or shutil.which("antigravity") or shutil.which("code") or shutil.which("code-oss") or shutil.which("cursor")
        if exec_bin:
            friendly = "Antigravity IDE" if "antigravity" in exec_bin else "VS Code" if "code" in exec_bin else "Editor"
            app = ApplicationEntry(app_id="editor", name=friendly, executable=exec_bin, exec_template=f"{exec_bin} %f", installed=True)

        if app and app.executable and shutil.which(app.executable):
            cmd = [app.executable]
            if line:
                cmd.extend(["-g", f"{path}:{line}"])
            else:
                cmd.append(path)
            try:
                proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
                detail = f"Opened {os.path.basename(path)} in {app.name}" + (f" at line {line}" if line else "")
                return LaunchResult(intent, True, app.name, detail, pid=proc.pid)
            except Exception as e:
                logger.warning(f"Failed to launch {app.name} for {path}: {e}")

        try:
            proc = subprocess.Popen(["xdg-open", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
            return LaunchResult(intent, True, "System Default (xdg-open)", f"Opened {os.path.basename(path)} using system default handler", pid=proc.pid)
        except Exception as e:
            return LaunchResult(intent, False, "", f"Failed to open file via xdg-open: {e}", error=str(e))

    def open_url(self, url: str, app: Optional[ApplicationEntry] = None) -> LaunchResult:
        if not url:
            return LaunchResult(RestoreIntent("webpage", Capability.OPEN_URL), False, "", "Empty URL provided")

        intent = RestoreIntent("webpage", Capability.OPEN_URL, resource_url=url)
        browser_exec = (app.executable if app and app.executable and shutil.which(app.executable) else None) or \
                       shutil.which("brave") or shutil.which("brave-browser") or \
                       shutil.which("google-chrome") or shutil.which("chromium") or \
                       shutil.which("firefox")

        if browser_exec:
            try:
                proc = subprocess.Popen([browser_exec, url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
                b_name = os.path.basename(browser_exec).capitalize()
                return LaunchResult(intent, True, b_name, f"Opened browser tab for {url} in {b_name}", pid=proc.pid)
            except Exception as e:
                logger.warning(f"Failed to launch browser executable {browser_exec}: {e}")

        try:
            proc = subprocess.Popen(["xdg-open", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
            return LaunchResult(intent, True, "System Default (xdg-open)", f"Opened browser tab for {url} via xdg-open", pid=proc.pid)
        except Exception as e:
            logger.warning(f"Failed to launch via xdg-open: {e}")

        try:
            webbrowser.open(url)
            return LaunchResult(intent, True, "System Browser", f"Opened browser tab for {url}")
        except Exception as e:
            return LaunchResult(intent, False, "", f"Failed to open URL: {e}", error=str(e))

    def open_folder(self, path: str, app: Optional[ApplicationEntry] = None) -> LaunchResult:
        if not path or not os.path.isdir(path):
            return LaunchResult(RestoreIntent("repository", Capability.OPEN_FOLDER, resource_path=path), False, "", f"Directory does not exist: {path}", error="DirNotFound")

        intent = RestoreIntent("repository", Capability.OPEN_FOLDER, resource_path=path)
        proj = os.path.basename(path)

        # Prefer native editor binaries on PATH first
        exec_bin = shutil.which("antigravity-ide") or shutil.which("antigravity") or shutil.which("code") or shutil.which("code-oss") or shutil.which("cursor")
        if exec_bin:
            friendly = "Antigravity IDE" if "antigravity" in exec_bin else "VS Code" if "code" in exec_bin else "Editor"
            app = ApplicationEntry(app_id="editor", name=friendly, executable=exec_bin, exec_template=f"{exec_bin} %f", installed=True)

        if app and app.executable and shutil.which(app.executable):
            try:
                proc = subprocess.Popen([app.executable, path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
                return LaunchResult(intent, True, app.name, f"Opened project {os.path.basename(path)} in {app.name}", pid=proc.pid)
            except Exception as e:
                logger.warning(f"Failed to open folder in {app.name}: {e}")

        try:
            proc = subprocess.Popen(["xdg-open", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
            return LaunchResult(intent, True, "File Manager", f"Opened folder {path} in file manager", pid=proc.pid)
        except Exception as e:
            return LaunchResult(intent, False, "", f"Failed to open folder via xdg-open: {e}", error=str(e))

    def create_terminal(self, cwd: str, command_hint: Optional[str] = None) -> LaunchResult:
        intent = RestoreIntent("terminal", Capability.CREATE_TERMINAL, resource_path=cwd, metadata={"recent_command": command_hint})
        target_dir = cwd if (cwd and os.path.isdir(cwd)) else os.path.expanduser("~")

        if not os.path.isdir(target_dir):
            return LaunchResult(intent, False, "Terminal", f"Working directory no longer exists or was renamed: {cwd}")

        exec_to_try = shutil.which("kitty") or shutil.which("xfce4-terminal") or shutil.which("alacritty") or shutil.which("gnome-terminal") or shutil.which("konsole") or shutil.which("x-terminal-emulator") or shutil.which("xterm")

        pid = None
        if exec_to_try:
            try:
                proc = subprocess.Popen([exec_to_try], cwd=target_dir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
                pid = proc.pid
            except Exception as e:
                logger.debug(f"Terminal popen failed: {e}")

        term_name = os.path.basename(exec_to_try).capitalize() if exec_to_try else "Terminal"
        detail = f"Opened {term_name} in {target_dir}" + (f" (Recent command: '{command_hint}')" if command_hint else "")
        return LaunchResult(intent, True, term_name, detail, pid=pid)

    def focus_window(self, window_class: str) -> LaunchResult:
        intent = RestoreIntent("window", Capability.FOCUS_WINDOW, metadata={"window_class": window_class})
        if not window_class:
            return LaunchResult(intent, False, "", "No window class provided for focus")

        if shutil.which("wmctrl"):
            try:
                subprocess.run(["wmctrl", "-xa", window_class], check=True, capture_output=True, timeout=2)
                return LaunchResult(intent, True, "Window Manager (wmctrl)", f"Focused window class '{window_class}'")
            except Exception:
                pass

        if shutil.which("hyprctl") and os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"):
            try:
                subprocess.run(["hyprctl", "dispatch", "focuswindow", window_class], check=True, capture_output=True, timeout=2)
                return LaunchResult(intent, True, "Hyprland", f"Focused window class '{window_class}'")
            except Exception:
                pass

        return LaunchResult(intent, False, "", f"Could not focus window class '{window_class}' with available windowing tools")

    def reveal_file(self, path: str) -> LaunchResult:
        intent = RestoreIntent("source_file", Capability.REVEAL_FILE, resource_path=path)
        if not path or not os.path.exists(path):
            return LaunchResult(intent, False, "", f"Path does not exist: {path}")

        if shutil.which("nautilus"):
            try:
                proc = subprocess.Popen(["nautilus", "--select", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return LaunchResult(intent, True, "Nautilus", f"Revealed {os.path.basename(path)} in file manager", pid=proc.pid)
            except Exception:
                pass
        if shutil.which("dolphin"):
            try:
                proc = subprocess.Popen(["dolphin", "--select", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return LaunchResult(intent, True, "Dolphin", f"Revealed {os.path.basename(path)} in file manager", pid=proc.pid)
            except Exception:
                pass

        parent = os.path.dirname(path)
        return self.open_folder(parent)


class LinuxBackend(PlatformBackend):
    """Concrete PlatformBackend for Linux operating systems."""

    def __init__(self):
        self._catalog = LinuxApplicationCatalog()
        self._launcher = LinuxPlatformLauncher(self._catalog)
        self._window_manager = None
        self._clipboard = None
        self._notifications = None

    def catalog(self) -> ApplicationCatalog:
        return self._catalog

    def launcher(self) -> PlatformLauncher:
        return self._launcher

    def window_manager(self) -> Any:
        if not self._window_manager:
            from arova.core.platform.windowing.manager import WindowingManager
            self._window_manager = WindowingManager.get_backend()
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
            from arova.core.platform.services.permissions import LinuxPermissions
            self._permissions = LinuxPermissions()
        return self._permissions

    def environment(self) -> Any:
        if not hasattr(self, "_environment"):
            from arova.core.platform.services.environment import LinuxEnvironment
            self._environment = LinuxEnvironment()
        return self._environment

    def _resolve_app(self, app_name: str) -> Optional[ApplicationEntry]:
        if not app_name:
            return None
        name_lower = app_name.lower()
        if "antigravity" in name_lower or name_lower in ("editor", "ide", "code", "code-oss", "vscode", "visual studio code"):
            exec_bin = shutil.which("antigravity-ide") or shutil.which("antigravity")
            if exec_bin:
                return ApplicationEntry(
                    app_id="antigravity",
                    name="Antigravity IDE",
                    executable=exec_bin,
                    exec_template=f"{exec_bin} %f",
                    installed=True
                )
        app = self._catalog.get_application(app_name)
        if not app and shutil.which(app_name):
            friendly = "VS Code" if app_name in ("code", "code-oss", "VS Code") else app_name
            return ApplicationEntry(app_id=app_name, name=friendly, executable=app_name, exec_template=f"{app_name} %f", installed=True)
        return app

    def execute(self, intent: RestoreIntent) -> LaunchResult:
        """
        Directly execute a RestoreIntent on Linux using the catalog and launcher.
        """
        app = self._resolve_app(intent.preferred_application) if intent.preferred_application else None
        return self._launcher.execute_intent(intent, app=app)

    def get_open_windows(self) -> list[str]:
        windows = set()
        # 1. Try hyprctl
        if shutil.which("hyprctl"):
            try:
                import json
                proc = subprocess.run(["hyprctl", "clients", "-j"], capture_output=True, text=True, timeout=2)
                if proc.returncode == 0:
                    data = json.loads(proc.stdout)
                    for client in data:
                        title = client.get("title", "")
                        cls = client.get("class", "")
                        if title and title != "v2":  # Ignore weird hyprland defaults
                            windows.add(f"{cls} - {title}" if cls else title)
            except Exception as e:
                logger.debug(f"LinuxBackend hyprctl window tracking failed: {e}")

        # 2. Try wmctrl (X11) if hyprctl wasn't successful or to complement
        if not windows and shutil.which("wmctrl"):
            try:
                proc = subprocess.run(["wmctrl", "-l"], capture_output=True, text=True, timeout=2)
                if proc.returncode == 0:
                    for line in proc.stdout.splitlines():
                        parts = line.split(None, 3)
                        if len(parts) >= 4:
                            title = parts[3]
                            if title and title != "N/A":
                                windows.add(title)
            except Exception as e:
                logger.debug(f"LinuxBackend wmctrl window tracking failed: {e}")
                
        return list(windows)

    def get_playing_media(self) -> list[str]:
        media = []
        if shutil.which("playerctl"):
            try:
                proc = subprocess.run(
                    ["playerctl", "-a", "metadata", "-f", "{{status}}: {{artist}} - {{title}}"], 
                    capture_output=True, text=True, timeout=2
                )
                if proc.returncode == 0:
                    for line in proc.stdout.splitlines():
                        if line.strip():
                            media.append(line.strip())
            except Exception as e:
                logger.debug(f"LinuxBackend playerctl media tracking failed: {e}")
        return media

    def register_capabilities(self, registry: CapabilityRegistry) -> None:
        registry.register(Capability.OPEN_FILE, lambda intent: self._launcher.execute_intent(intent, self._resolve_app(intent.preferred_application or "")))
        registry.register(Capability.OPEN_URL, lambda intent: self._launcher.execute_intent(intent, self._resolve_app(intent.preferred_application or "")))
        registry.register(Capability.OPEN_FOLDER, lambda intent: self._launcher.execute_intent(intent, self._resolve_app(intent.preferred_application or "")))
        registry.register(Capability.OPEN_PROJECT, lambda intent: self._launcher.execute_intent(intent, self._resolve_app(intent.preferred_application or "")))
        registry.register(Capability.CREATE_TERMINAL, lambda intent: self._launcher.execute_intent(intent))
        registry.register(Capability.FOCUS_WINDOW, lambda intent: self._launcher.execute_intent(intent))
        registry.register(Capability.REVEAL_FILE, lambda intent: self._launcher.execute_intent(intent))
        logger.info("LinuxBackend: Registered platform capabilities into universal CapabilityRegistry")
