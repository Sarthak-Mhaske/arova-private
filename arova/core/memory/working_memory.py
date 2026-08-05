import time
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)

@dataclass
class WorkingMemoryState:
    """
    Staleness & Expiry Guarantee (`HYP-08`) enforced Working Memory object.
    Owns strictly: 'What is the user working on right now?' (`HYP-06`).
    """
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    source: str = "ActivityCaptureEngine"
    refresh_trigger: str = "capture.EVENT_INGESTED"
    cognitive_trigger_type: str = "INITIAL_BOOT"
    ttl: int = 300  # 5 minutes staleness threshold
    
    active_files: List[Dict[str, Any]] = field(default_factory=list)
    current_repository: Optional[str] = None
    browser_evidence: List[Dict[str, Any]] = field(default_factory=list)
    terminal_evidence: List[Dict[str, Any]] = field(default_factory=list)
    unresolved_errors: List[str] = field(default_factory=list)
    active_objective: Optional[str] = None
    interruption_history: List[Dict[str, Any]] = field(default_factory=list)
    current_reasoning_trajectory: Optional[str] = None
    attention_mode: str = "deep_work"  # "deep_work" | "fragmented" | "idle"

    def get_empirical_evidence(self) -> Dict[str, Any]:
        """Returns empirical evidence counts instead of arbitrary floats."""
        now = time.time()
        return {
            "active_files_count": len(self.active_files),
            "terminal_failures_count": sum(1 for t in self.terminal_evidence if t.get("exit_code") not in (None, 0)),
            "unresolved_errors_count": len(self.unresolved_errors),
            "browser_tabs_count": len(self.browser_evidence),
            "attention_mode": self.attention_mode,
            "last_updated_seconds_ago": round(now - self.updated_at, 1)
        }

    def is_stale(self) -> bool:
        return (time.time() - self.updated_at) > self.ttl

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["is_stale"] = self.is_stale()
        d["empirical_evidence"] = self.get_empirical_evidence()
        return d


class WorkingMemoryRuntime:
    """
    Working Memory Runtime (`HYP-06`).
    Sits between Canonical Capture/Workspace Graph and the heavier Reasoning/Memory runtimes.
    Filters granular keystroke/event noise and triggers incremental reasoning only when the working set shifts meaningfully (`HYP-07`).
    """
    def __init__(self, event_bus: Optional[Any] = None, reasoning_runtime: Optional[Any] = None, memory_runtime: Optional[Any] = None):
        self.event_bus = event_bus
        self.reasoning_runtime = reasoning_runtime
        self.memory_runtime = memory_runtime
        self.state = WorkingMemoryState()
        self._last_reasoning_trigger_ts = 0.0
        self._event_count_since_reasoning = 0

    def ingest_event(self, event_payload: Dict[str, Any]) -> bool:
        """
        Absorbs canonical capture event payload.
        Returns True if the working set shifted meaningfully enough to justify downstream reasoning/memory evolution.
        """
        now = time.time()
        self.state.updated_at = now
        self._event_count_since_reasoning += 1
        
        event_type = event_payload.get("event_type", "")
        source_plugin = event_payload.get("source_plugin", "")
        norm = event_payload.get("normalized_payload") or {}
        
        meaningful_shift = False

        # Track active files (`VSCode / Editor`)
        if source_plugin in ("VSCode", "vscode_extension", "editor") or event_type.startswith("file."):
            file_path = norm.get("resource_path") or norm.get("file") or norm.get("title")
            if file_path:
                # Update or insert active file
                existing = next((f for f in self.state.active_files if f.get("path") == file_path), None)
                if existing:
                    existing["last_seen"] = now
                    existing["line"] = norm.get("line", existing.get("line"))
                else:
                    self.state.active_files.append({
                        "path": str(file_path),
                        "last_seen": now,
                        "line": norm.get("line")
                    })
                    if len(self.state.active_files) > 15:
                        self.state.active_files.pop(0)
                    meaningful_shift = True

            repo = norm.get("repository") or norm.get("project_root")
            if repo and repo != self.state.current_repository:
                self.state.current_repository = str(repo)
                meaningful_shift = True

            # Track unresolved errors (`Tracebacks, compiler output`)
            err = norm.get("error") or norm.get("traceback") or norm.get("diagnostic")
            if err and str(err) not in self.state.unresolved_errors:
                self.state.unresolved_errors.append(str(err))
                if len(self.state.unresolved_errors) > 10:
                    self.state.unresolved_errors.pop(0)
                meaningful_shift = True

        # Track terminal evidence
        elif source_plugin in ("Terminal", "bash", "zsh", "shell") or event_type.startswith("terminal."):
            cmd = norm.get("command") or norm.get("summary")
            cwd = norm.get("cwd") or norm.get("directory")
            exit_code = norm.get("exit_code")
            if cmd:
                if exit_code == 0:
                    # Clear previous terminal failure evidence and errors on successful command execution
                    self.state.terminal_evidence = [t for t in self.state.terminal_evidence if t.get("exit_code") == 0]
                    self.state.unresolved_errors = []
                self.state.terminal_evidence.append({
                    "command": str(cmd),
                    "cwd": str(cwd) if cwd else self.state.current_repository,
                    "exit_code": exit_code,
                    "timestamp": now
                })
                if len(self.state.terminal_evidence) > 10:
                    self.state.terminal_evidence.pop(0)
                if exit_code is not None and int(exit_code) != 0:
                    meaningful_shift = True  # Command failure is a meaningful shift

        # Track browser evidence
        elif source_plugin in ("Chrome", "Browser", "web") or event_type.startswith("browser."):
            url = norm.get("url") or norm.get("identity")
            title = norm.get("title") or norm.get("summary")
            if url:
                existing_url = next((u for u in self.state.browser_evidence if u.get("url") == url), None)
                if existing_url:
                    existing_url["last_seen"] = now
                else:
                    self.state.browser_evidence.append({
                        "url": str(url),
                        "title": str(title) if title else str(url),
                        "last_seen": now
                    })
                    if len(self.state.browser_evidence) > 10:
                        self.state.browser_evidence.pop(0)
                    meaningful_shift = True

        # Classify specific cognitive trigger type
        if len(self.state.unresolved_errors) > 0:
            self.state.cognitive_trigger_type = "STACKTRACE_DETECTED"
        elif self.state.terminal_evidence and self.state.terminal_evidence[-1].get("exit_code") not in (None, 0):
            self.state.cognitive_trigger_type = "REPEATED_TERMINAL_FAILURE"
        elif source_plugin in ("VSCode", "vscode_extension", "editor") and self.state.browser_evidence:
            self.state.cognitive_trigger_type = "DOCS_TO_CODE_PIVOT"
        elif meaningful_shift:
            self.state.cognitive_trigger_type = "WORKING_SET_EXPANSION"

        # Check if we should trigger reasoning / memory evolution (`HYP-07` & `HYP-05`)
        time_since_trigger = now - self._last_reasoning_trigger_ts
        is_critical = self.state.cognitive_trigger_type in ("STACKTRACE_DETECTED", "REPEATED_TERMINAL_FAILURE", "DOCS_TO_CODE_PIVOT")
        should_reason = meaningful_shift and (is_critical or time_since_trigger > 15.0 or self._event_count_since_reasoning >= 10)
        
        if should_reason:
            self._last_reasoning_trigger_ts = now
            self._event_count_since_reasoning = 0
            self._emit_working_memory_changed()
            
            # Incremental continuous memory evolution (`HYP-05`)
            if self.memory_runtime and hasattr(self.memory_runtime, "form_incremental_memory"):
                try:
                    self.memory_runtime.form_incremental_memory(self.state.to_dict())
                except Exception as e:
                    logger.debug(f"Working memory -> continuous memory evolution failed: {e}")

        return meaningful_shift

    def tick_idle_dwell(self, elapsed_seconds: float = 60.0) -> bool:
        """
        Autonomous Time & Dwell Engine:
        Tracks reading, thinking, and documentation dwell time even when no keyboard events fire.
        Triggers continuous reasoning updates during prolonged reading or reflection.
        """
        now = time.time()
        self.state.updated_at = now
        
        # Increment dwell duration on current working set
        for f in self.state.active_files:
            f["dwell_seconds"] = f.get("dwell_seconds", 0.0) + elapsed_seconds

        time_since_trigger = (now - self._last_reasoning_trigger_ts) + elapsed_seconds
        if time_since_trigger >= 60.0 and (self.state.active_files or self.state.current_repository):
            self.state.cognitive_trigger_type = "IDLE_DWELL_SYNTHESIS"
            self._last_reasoning_trigger_ts = now
            self._emit_working_memory_changed()
            return True
        return False

    def _emit_working_memory_changed(self) -> None:
        if self.event_bus:
            try:
                self.event_bus.emit("cognition", "WORKING_MEMORY_CHANGED", self.state.to_dict())
            except Exception as e:
                logger.warning(f"Failed to emit cognition.WORKING_MEMORY_CHANGED: {e}")

    def get_snapshot(self) -> Dict[str, Any]:
        return self.state.to_dict()
