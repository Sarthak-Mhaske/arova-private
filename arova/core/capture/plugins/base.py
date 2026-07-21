import abc
import logging
from typing import Dict, Any, Optional, List
from arova.core.capture.engine import ActivityCaptureEngine, CanonicalActivityEvent

logger = logging.getLogger(__name__)

class CapturePlugin(abc.ABC):
    """
    Base class for Activity Capture adapters.
    Following Phase 6 rules, we build Tier 1 plugins (`VS Code`, `Terminal`, `Browser`) incrementally
    and ensure every event flows into `ActivityCaptureEngine` as a `CanonicalActivityEvent`.
    """
    def __init__(self, plugin_name: str, version: str = "1.0.0"):
        self.plugin_name = plugin_name
        self.version = version
        self.engine: Optional[ActivityCaptureEngine] = None
        self._is_running = False

    def attach_engine(self, engine: ActivityCaptureEngine) -> None:
        self.engine = engine

    def emit(self, event_type: str, normalized_payload: Dict[str, Any],
             raw_payload: Optional[Dict[str, Any]] = None,
             provenance: Optional[Dict[str, Any]] = None) -> Optional[CanonicalActivityEvent]:
        """Emit a normalized observation into the Activity Capture Engine."""
        if not self.engine:
            logger.warning(f"CapturePlugin '{self.plugin_name}' emitted event without attached engine.")
            return None
        return self.engine.ingest_event(
            event_type=event_type,
            source_plugin=self.plugin_name,
            normalized_payload=normalized_payload,
            raw_payload=raw_payload,
            provenance=provenance or {"plugin": self.plugin_name, "version": self.version}
        )

    @abc.abstractmethod
    def start(self) -> None:
        """Start capturing events from the target application/environment."""
        pass

    @abc.abstractmethod
    def stop(self) -> None:
        """Stop capturing events."""
        pass


class PluginRegistry:
    """Registry managing active Activity Capture adapters."""
    def __init__(self):
        self._plugins: Dict[str, CapturePlugin] = {}

    def register(self, plugin: CapturePlugin, engine: Optional[ActivityCaptureEngine] = None) -> None:
        if engine:
            plugin.attach_engine(engine)
        self._plugins[plugin.plugin_name] = plugin
        logger.info(f"Registered CapturePlugin: {plugin.plugin_name} (v{plugin.version})")

    def unregister(self, plugin_name: str) -> None:
        if plugin_name in self._plugins:
            plugin = self._plugins.pop(plugin_name)
            plugin.stop()

    def get_plugin(self, plugin_name: str) -> Optional[CapturePlugin]:
        return self._plugins.get(plugin_name)

    def list_plugins(self) -> List[str]:
        return list(self._plugins.keys())

    def start_all(self) -> None:
        for name, plugin in self._plugins.items():
            try:
                plugin.start()
            except Exception as e:
                logger.error(f"Failed to start CapturePlugin '{name}': {e}", exc_info=True)

    def stop_all(self) -> None:
        for name, plugin in self._plugins.items():
            try:
                plugin.stop()
            except Exception as e:
                logger.error(f"Failed to stop CapturePlugin '{name}': {e}", exc_info=True)


# ==============================================================================
# Tier 1 Plugins (Incremental Adapters for Phase 6)
# ==============================================================================

class VSCodePlugin(CapturePlugin):
    """
    Tier 1 Adapter (Week 1): Captures active file edits, line positions, repository path, and git branch.
    Normalizes into `editor_change` events.
    """
    def __init__(self):
        super().__init__(plugin_name="vscode", version="1.0.0")

    def start(self) -> None:
        self._is_running = True
        logger.debug("VSCodePlugin started.")

    def stop(self) -> None:
        self._is_running = False
        logger.debug("VSCodePlugin stopped.")

    def report_editor_event(self, file_path: str, line_number: int = 1, cursor_pos: int = 0,
                            repository: str = "", git_branch: str = "",
                            summary: str = "", raw_data: Optional[Dict[str, Any]] = None) -> Optional[CanonicalActivityEvent]:
        if not self._is_running:
            return None
        payload = {
            "resource_path": file_path,
            "title": file_path.split("/")[-1] if file_path else "Untitled",
            "line_number": line_number,
            "cursor_pos": cursor_pos,
            "repository": repository,
            "git_branch": git_branch,
            "summary": summary or f"Editing {file_path.split('/')[-1]} around line {line_number}",
            "kind": "File"
        }
        return self.emit("editor_change", normalized_payload=payload, raw_payload=raw_data)


class TerminalPlugin(CapturePlugin):
    """
    Tier 1 Adapter (Week 2): Captures terminal command execution, current working directory, and errors/tracebacks.
    Normalizes into `terminal_exec` events.
    """
    def __init__(self):
        super().__init__(plugin_name="terminal", version="1.0.0")

    def start(self) -> None:
        self._is_running = True
        logger.debug("TerminalPlugin started.")

    def stop(self) -> None:
        self._is_running = False
        logger.debug("TerminalPlugin stopped.")

    def report_terminal_event(self, cwd: str, command: str, exit_code: int = 0,
                              output_snippet: str = "", raw_data: Optional[Dict[str, Any]] = None) -> Optional[CanonicalActivityEvent]:
        if not self._is_running:
            return None
        payload = {
            "cwd": cwd,
            "command": command,
            "exit_code": exit_code,
            "title": f"Terminal: {command[:30]}..." if len(command) > 30 else f"Terminal: {command}",
            "summary": output_snippet or f"Ran command `{command}` in {cwd}",
            "is_error": exit_code != 0 or any(err in output_snippet.lower() for err in ["error", "traceback", "exception"]),
            "kind": "Terminal"
        }
        return self.emit("terminal_exec", normalized_payload=payload, raw_payload=raw_data)


class BrowserPlugin(CapturePlugin):
    """
    Tier 1 Adapter (Week 3): Captures active documentation tabs, URLs, and domains.
    Normalizes into `browser_tab` events.
    """
    def __init__(self):
        super().__init__(plugin_name="chrome", version="1.0.0")

    def start(self) -> None:
        self._is_running = True
        logger.debug("BrowserPlugin started.")

    def stop(self) -> None:
        self._is_running = False
        logger.debug("BrowserPlugin stopped.")

    def report_browser_event(self, url: str, title: str = "", domain: str = "",
                             summary: str = "", raw_data: Optional[Dict[str, Any]] = None) -> Optional[CanonicalActivityEvent]:
        if not self._is_running:
            return None
        if not domain and url:
            try:
                from urllib.parse import urlparse
                domain = urlparse(url).netloc
            except Exception:
                domain = url
        payload = {
            "url": url,
            "domain": domain,
            "title": title or url,
            "summary": summary or f"Viewing {title or domain}",
            "kind": "BrowserTab"
        }
        return self.emit("browser_tab", normalized_payload=payload, raw_payload=raw_data)
