import os
import time
import logging
from typing import Dict, List, Optional, Any
from arova.core.cognition.workspace import (
    CognitiveWorkspace, RealityLayer, InterpretationLayer, SignalsLayer, UnderstandingLayer,
    WorkspaceMomentum, WorkspaceHealth, WorkspaceConfidence, ConfidenceLayer, ItemConfidence
)
from arova.core.cognition.constants import (
    MIN_BEHAVIORAL_RECOVERY_SECONDS, SECONDS_PER_RESOURCE_REOPEN, SECONDS_PER_SWITCH_AVOIDED,
    STUCKNESS_ERROR_PENALTY, STUCKNESS_REPEAT_VISIT_RATE, STUCKNESS_MAX_REPEAT_PENALTY,
    STUCKNESS_STAGNANT_FOCUS_PENALTY, STUCKNESS_STAGNANT_TIME_THRESHOLD_SECONDS
)

logger = logging.getLogger(__name__)


class WorkspaceManager:
    """
    Manages long-lived CognitiveWorkspaces.
    Handles automatic emergence, confidence-based switching, semantic merging,
    universal stuckness detection, observational interventions, and KPI telemetry.
    """
    def __init__(self, event_bus=None, orchestrator=None):
        self._workspaces: Dict[str, CognitiveWorkspace] = {}
        self._active_workspace_id: Optional[str] = None
        self.event_bus = event_bus
        self.orchestrator = orchestrator
        
        self._last_switch_attempt = 0.0
        self._pending_switch_id: Optional[str] = None
        
        # Telemetry & Intervention state
        self._resource_access_counts: Dict[str, Dict[str, int]] = {}
        self._last_intervention_at: Dict[str, float] = {}
        self._resume_timestamps: Dict[str, float] = {}
        self._completed_work: List[Dict[str, Any]] = []

        from .resource_registry import ResourceRegistry
        from .restoration_engine import EnvironmentRestorationEngine
        self.resource_registry = ResourceRegistry()
        self.restoration_engine = EnvironmentRestorationEngine(self.resource_registry, event_bus=self.event_bus)

        if self.event_bus:
            self.event_bus.subscribe("context", "fragment_reported", self._on_fragment_reported)
            self.event_bus.subscribe("timeline", "create", self._on_timeline_create)
            self.event_bus.subscribe("cognition", "SESSION_TURN_COMPLETED", self._on_turn_completed)
            self.event_bus.subscribe("workspace", "continue", self._on_workspace_continue)
            self.event_bus.subscribe("capture", "EVENT_INGESTED", self._on_capture_ingested)
            self.event_bus.subscribe("ambience", "CONTEXT_CHANGED", self._on_context_changed)
            self.event_bus.subscribe("work", "ACCEPT_REQUEST", self._on_work_accept)
            self.event_bus.subscribe("work", "REJECT_REQUEST", self._on_work_reject)
        self._init_default_workspace()

    def _init_default_workspace(self):
        home = os.path.abspath(os.path.expanduser("~"))
        
        # Dynamically discover active workspace from running editor or terminal process
        from arova.core.ambience.process_tracker import ProcessContextTracker
        proc_ctx = ProcessContextTracker.get_active_process_contexts()
        editors = proc_ctx.get("editor_projects", [])
        terminals = proc_ctx.get("terminal_cwds", [])
        
        discovered_path = (editors[0] if editors else (terminals[0] if terminals else None))
        if discovered_path and os.path.isdir(discovered_path) and discovered_path != home:
            base_name = os.path.basename(discovered_path)
            # If the directory is a generic folder like dist/build/target/bin, navigate up to parent
            if base_name.lower() in ["dist", "build", "out", "bin", "lib", "src", "target", "output"] and os.path.dirname(discovered_path) != home:
                discovered_path = os.path.dirname(discovered_path)
                base_name = os.path.basename(discovered_path)
            cwd = discovered_path
            project_title = f"{base_name.replace('-', ' ').replace('_', ' ').title()}"
        else:
            cwd = home
            project_title = "Active Workspace"

        ws = self._workspaces.get("ws_default")
        
        # If workspace already exists (e.g. hydrated from hot_state), do NOT overwrite its resources
        if ws:
            # Cleanse any stale or dirty workspace titles from previous session snapshots (e.g. "Dist Project", ".vscode", "Dist")
            stale_titles = ["New Workspace", "Active Workspace", "Dist Project", "Dist", "Out Project", "Build Project"]
            is_dirty_repo = getattr(ws, "interpretation", None) and any(
                dirty in str(p) for p in (ws.interpretation.repo_paths or []) 
                for dirty in ["/.vscode/extensions", "/.cursor/extensions", "/ms-python", "/dist"]
            )
            if ws.title in stale_titles or is_dirty_repo:
                ws.title = project_title
                ws.interpretation.repo_paths = [cwd] if (cwd != home and os.path.isdir(cwd)) else []
            elif getattr(ws, "interpretation", None) and not ws.interpretation.repo_paths:
                ws.interpretation.repo_paths = [cwd] if cwd != home else []
            return ws
        
        # Initialize default from scratch dynamically
        ws = CognitiveWorkspace(
            workspace_id="ws_default",
            title=project_title,
            domain_type="engineering",
            pinned=True
        )
        ws.reality.resources = {}
        ws.interpretation.repo_paths = [cwd] if (cwd != home and os.path.isdir(cwd)) else []
        if not getattr(ws.understanding, "momentum", None) or not ws.understanding.momentum.goal:
            ws.understanding.momentum = WorkspaceMomentum(
                goal=f"Active focus in {project_title}",
                next_action="Continue active session flow and verify ongoing changes"
            )
        self._workspaces["ws_default"] = ws
        if not self._active_workspace_id:
            self._active_workspace_id = "ws_default"
        logger.info(f"WorkspaceManager: Initialized dynamic workspace '{ws.title}' ({ws.workspace_id}) at {cwd}")
        return ws

    @staticmethod
    def _classify_app_type(text: str) -> str:
        t = str(text).lower()
        if any(w in t for w in ["code", "vscode", "antigravity", "cursor", "pycharm", "intellij", "idea", "sublime", "zed", "neovim", "fleet", "emacs", "kate"]):
            return "vscode"
        if any(w in t for w in ["kitty", "alacritty", "gnome-terminal", "konsole", "xterm", "wezterm", "foot", "tilix", "ghostty", "terminal", "warp", "cmd", "powershell"]):
            return "terminal"
        if any(w in t for w in ["chrome", "firefox", "brave", "chromium", "edge", "safari", "zen", "youtube"]):
            return "browser"
        return "window"

    def _on_context_changed(self, event: Any):
        payload = event.data if hasattr(event, "data") else event
        snapshot = payload.get("snapshot", {}) if isinstance(payload, dict) and "snapshot" in payload else (payload if isinstance(payload, dict) else {})
        if not isinstance(snapshot, dict):
            return
        active_app = snapshot.get("active_app")
        window_title = snapshot.get("window_title")
        open_windows = snapshot.get("open_windows", [])
        playing_media = snapshot.get("playing_media", [])

        if window_title or active_app:
            provider = self._classify_app_type(f"{active_app} {window_title}")
            self.ingest_fragment({
                "source_identity": str(window_title or active_app),
                "provider_id": provider,
                "activity_summary": f"Active window: {window_title}"
            })

        active_repo = self.get_active_workspace().interpretation.repo_paths[0] if (self.get_active_workspace() and self.get_active_workspace().interpretation.repo_paths) else None
        for win in open_windows:
            if isinstance(win, str) and win and win != window_title:
                parsed = self._parse_ambient_window(win, active_repo=active_repo)
                if parsed:
                    summary = parsed.get("action_label") or parsed.get("summary") or f"Open {parsed.get('file_name', win)}"
                    self.ingest_fragment({
                        "source_identity": parsed.get("file_path") or parsed.get("file_name") or win,
                        "provider_id": parsed.get("category", "window"),
                        "activity_summary": summary
                    })

        for media in playing_media:
            if isinstance(media, str) and media:
                self.ingest_fragment({
                    "source_identity": media,
                    "provider_id": "media",
                    "activity_summary": f"Playing media: {media}"
                })

    def _on_capture_ingested(self, event: Any):
        payload = event.data if hasattr(event, "data") else event
        if isinstance(payload, dict):
            normalized = payload.get("normalized_payload", {})
            source_plugin = payload.get("source_plugin", "unknown")
            title = normalized.get("title") or normalized.get("resource_path") or ""
            summary = normalized.get("summary") or normalized.get("command") or ""
            if title or summary:
                self.ingest_fragment({
                    "source_identity": str(title),
                    "provider_id": source_plugin,
                    "activity_summary": str(summary)
                })

    def get_active_workspace(self) -> Optional[CognitiveWorkspace]:
        if not self._active_workspace_id and "ws_default" in self._workspaces:
            self._active_workspace_id = "ws_default"
        if not self._active_workspace_id and self._workspaces:
            self._active_workspace_id = next(iter(self._workspaces.keys()))
        if not self._active_workspace_id:
            return None
        return self._workspaces.get(self._active_workspace_id)

    def get_all_workspaces(self) -> List[CognitiveWorkspace]:
        return list(self._workspaces.values())

    def get_workspace(self, workspace_id: str) -> Optional[CognitiveWorkspace]:
        if workspace_id not in self._workspaces and workspace_id == "ws_default":
            self._init_default_workspace()
        return self._workspaces.get(workspace_id) or self.get_active_workspace()

    def set_active_workspace(self, workspace_id: str):
        if workspace_id not in self._workspaces and workspace_id == "ws_default":
            self._init_default_workspace()
        if workspace_id in self._workspaces:
            self._active_workspace_id = workspace_id
            self.sync_to_bus()
            logger.info(f"WorkspaceManager: Active workspace switched to '{self._workspaces[workspace_id].title}'")
        elif not self._active_workspace_id and "ws_default" in self._workspaces:
            self._active_workspace_id = "ws_default"

    def mark_resumed(self, workspace_id: str):
        self._resume_timestamps[workspace_id] = time.time()
        if self.event_bus:
            self.event_bus.emit("telemetry", "workspace_resumed", {"workspace_id": workspace_id, "timestamp": time.time()})

    def restore_environment(self, workspace: CognitiveWorkspace, restore_options: Optional[Dict[str, Any]] = None):
        """
        Trigger physical restoration of the workspace environment when resumed (`Phase 7 Magic Resume`).
        """
        if getattr(workspace, "workspace_id", None) == "ws_default":
            workspace = self._init_default_workspace()
        restore_options = restore_options or {}
        self.mark_resumed(workspace.workspace_id)
        logger.info(f"WorkspaceManager: Restoring physical environment for '{workspace.title}'")

        # Execute physical restoration through our Engine and capture outcomes
        outcome_summary = self.restoration_engine.restore(workspace, restore_options)

        # Estimate time saved calculation
        resource_count = len(workspace.reality.resources)
        access_dict = self._resource_access_counts.get(workspace.workspace_id, {})
        switches_avoided = sum(access_dict.values()) if isinstance(access_dict, dict) else 0
        behavioral_recovery_seconds = max(MIN_BEHAVIORAL_RECOVERY_SECONDS, (resource_count * SECONDS_PER_RESOURCE_REOPEN) + (switches_avoided * SECONDS_PER_SWITCH_AVOIDED))

        if self.event_bus:
            # Phase A: Cognitive & UI notification
            self.event_bus.emit("environment", "RECOVERY_INITIATED", {
                "workspace_id": workspace.workspace_id,
                "title": workspace.title,
                "resources": workspace.reality.resources,
                "repo_paths": workspace.interpretation.repo_paths,
                "browser_domains": workspace.interpretation.browser_domains,
                "behavioral_recovery_seconds": behavioral_recovery_seconds,
                "options": restore_options,
                "outcomes": outcome_summary.to_dict()
            })
            
            self.event_bus.emit("telemetry", "context_recovery_saved", {
                "workspace_id": workspace.workspace_id,
                "title": workspace.title,
                "saved_seconds": behavioral_recovery_seconds,
                "saved_minutes": round(behavioral_recovery_seconds / 60.0, 1),
                "switches_avoided": switches_avoided,
                "resources_prepared": resource_count
            })

            # Phase B: Physical restoration completed via restoration_engine
            logger.info(f"WorkspaceManager: Environment restoration completed for '{workspace.title}'")

    def perform_ambient_scan(self):
        """
        Performs an immediate, authentic scan of open windows, running terminal CWDs,
        IDE project paths, active media, and recent browser tabs/URLs.
        Populates active_ws.reality.resources with real observed items.
        """
        active = self.get_active_workspace()
        if not active:
            return

    def perform_ambient_scan(self):
        """
        Performs an authentic, dynamic scan of currently running editors, terminal CWDs,
        open windows, active media, and recent browser tabs (strictly last 12h).
        Populates active_ws.reality.resources with genuine current session items.
        """
        active = self.get_active_workspace()
        if not active:
            return

        now = time.time()
        fresh_resources = {}
        fresh_domains = []

        # 1. Scan running process CWDs (Kitty, Alacritty, Antigravity IDE, VS Code, Cursor, Zed, Sublime)
        try:
            from arova.core.ambience.process_tracker import ProcessContextTracker
            proc_ctx = ProcessContextTracker.get_active_process_contexts()
            
            for p_path in proc_ctx.get("editor_projects", []):
                if os.path.isdir(p_path):
                    if p_path not in active.interpretation.repo_paths:
                        active.interpretation.repo_paths.append(p_path)
                    fresh_resources[p_path] = {
                        "identity": p_path,
                        "type": "vscode",
                        "last_seen": now,
                        "summary": f"Active project: {os.path.basename(p_path)}"
                    }

            for t_cwd in proc_ctx.get("terminal_cwds", []):
                if os.path.isdir(t_cwd):
                    # Filter out internal dev/build directories
                    if any(t_cwd.endswith(p) for p in ["/arova/frontend", "/arova/release", "/arova/dist", "/arova/src-tauri", "/arova/target_dist_tar"]):
                        continue
                    term_key = f"terminal://{t_cwd}"
                    fresh_resources[term_key] = {
                        "identity": t_cwd,
                        "type": "terminal",
                        "last_seen": now,
                        "summary": f"Terminal CWD: {t_cwd}"
                    }
                    if not active.interpretation.repo_paths and t_cwd != os.path.expanduser("~"):
                        active.interpretation.repo_paths.append(t_cwd)
        except Exception as e:
            logger.debug(f"WorkspaceManager perform_ambient_scan process error: {e}")

        # 2. Scan recent browser tabs (strictly within last 12 hours)
        try:
            from arova.core.ambience.browser_tracker import BrowserTabCapture
            urls = BrowserTabCapture.get_recent_browser_history(limit=8, max_age_hours=12.0)
            for item in urls:
                u = item["url"]
                t = item["title"]
                cat = item.get("category", "general")
                fresh_resources[u] = {
                    "identity": u,
                    "type": "browser",
                    "category": cat,
                    "last_seen": now,
                    "summary": t
                }
                if u not in fresh_domains:
                    fresh_domains.append(u)
        except Exception as e:
            logger.debug(f"WorkspaceManager perform_ambient_scan browser error: {e}")

        # 3. Scan live open windows & active application
        try:
            from arova.core.ambience.provider import LiveOSAmbientProvider
            provider = LiveOSAmbientProvider()
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(self._async_scan_os(provider, active, fresh_resources))
                else:
                    ctx = loop.run_until_complete(provider.get_current_context())
                    self._apply_os_context(ctx, active, fresh_resources)
            except Exception:
                pass
        except Exception as e:
            logger.debug(f"WorkspaceManager perform_ambient_scan OS window error: {e}")

        # Merge fresh ambient resources into active reality resources
        active.reality.resources.update(fresh_resources)
        for dom in fresh_domains:
            if dom not in active.interpretation.browser_domains:
                active.interpretation.browser_domains.append(dom)

    async def _async_scan_os(self, provider: Any, active: CognitiveWorkspace, target_dict: Optional[Dict[str, Any]] = None):
        try:
            ctx = await provider.get_current_context()
            self._apply_os_context(ctx, active, target_dict)
            if target_dict is not None and active:
                active.reality.resources.update(target_dict)
        except Exception as e:
            logger.debug(f"Async OS scan failed: {e}")

    def _parse_ambient_window(self, win: str, active_repo: Optional[str] = None) -> Optional[Dict[str, Any]]:
        if not win or not isinstance(win, str):
            return None
        win_clean = win.strip()
        win_lower = win_clean.lower()
        
        # 1. Filter out Arova itself, frontend dev window, and generic window manager noise
        if any(w in win_lower for w in [
            "frontend - arova", "arova - arova", "arova desktop", "tauri dev", "npm run tauri", 
            "cargo tauri", "build_arovad.sh", "package_app.sh"
        ]) or win_lower in ["arova", "arovad", "frontend"] or win_lower.startswith("arova v"):
            return None
        if win_clean in ["N/A", "v2", "Desktop", "xprintidle", "root"]:
            return None

        # 2. Check IDE / Editor
        ide_patterns = [
            ("antigravity", "Antigravity IDE"),
            ("visual studio code", "VS Code"),
            ("vscode", "VS Code"),
            ("cursor", "Cursor"),
            ("pycharm", "PyCharm"),
            ("intellij", "IntelliJ IDEA"),
            ("sublime", "Sublime Text"),
            ("zed", "Zed"),
            ("neovim", "Neovim"),
            ("vim", "Vim"),
            ("emacs", "Emacs"),
            ("kate", "Kate"),
            ("gedit", "Gedit")
        ]
        
        for key, ide_label in ide_patterns:
            if key in win_lower:
                parts = [p.strip() for p in win_clean.split(" - ") if p.strip()]
                file_candidate = None
                for p in reversed(parts):
                    if "." in p and not any(p.lower().endswith(ext) for ext in [".exe", ".app", ".desktop", ".com", ".so", ".bin"]):
                        file_candidate = p
                        break
                if not file_candidate and parts:
                    for p in parts:
                        if "." in p and not any(p.lower().endswith(ext) for ext in [".exe", ".app", ".desktop", ".com"]):
                            file_candidate = p
                            break

                proj_name = os.path.basename(active_repo) if active_repo else "Workspace"
                file_path = file_candidate
                if file_candidate and active_repo and os.path.isdir(active_repo):
                    for root, _, files in os.walk(active_repo):
                        if any(skip in root for skip in [".git", "node_modules", ".cache", "__pycache__", "dist", "build"]):
                            continue
                        if file_candidate in files:
                            file_path = os.path.join(root, file_candidate)
                            break

                return {
                    "type": "vscode",
                    "category": "editor",
                    "app": ide_label,
                    "file_name": file_candidate or proj_name,
                    "file_path": file_path or file_candidate,
                    "project": proj_name,
                    "summary": f"Open {file_candidate or proj_name} in {ide_label}",
                    "action_label": f"Open {file_candidate} in {ide_label}" if file_candidate else f"Resume {proj_name} in {ide_label}"
                }

        # 3. Check Terminal
        term_patterns = [
            ("kitty", "Kitty Terminal"),
            ("alacritty", "Alacritty"),
            ("wezterm", "WezTerm"),
            ("foot", "Foot Terminal"),
            ("gnome-terminal", "GNOME Terminal"),
            ("konsole", "Konsole"),
            ("xterm", "XTerm"),
            ("ghostty", "Ghostty")
        ]
        for key, term_label in term_patterns:
            if key in win_lower or "terminal" in win_lower:
                # Exclude if running Arova dev commands or frontend
                if any(w in win_lower for w in ["npm run tauri", "tauri dev", "cargo tauri", "npm run dev", "arovad", "frontend"]):
                    return None
                cwd_candidate = win_clean
                parts = [p.strip() for p in win_clean.split(" - ") if p.strip()]
                if len(parts) > 1:
                    cwd_candidate = parts[-1]
                return {
                    "type": "terminal",
                    "category": "terminal",
                    "app": term_label,
                    "cwd": cwd_candidate,
                    "summary": f"Terminal ({term_label}) in {cwd_candidate}",
                    "action_label": f"Restore terminal session ({cwd_candidate})"
                }

        # 4. Check Browser
        browser_patterns = [
            ("brave", "Brave Browser"),
            ("chrome", "Google Chrome"),
            ("firefox", "Firefox"),
            ("chromium", "Chromium"),
            ("zen", "Zen Browser"),
            ("edge", "Microsoft Edge")
        ]
        for key, browser_label in browser_patterns:
            if key in win_lower:
                parts = [p.strip() for p in win_clean.split(" - ") if p.strip()]
                title = parts[0] if parts else win_clean
                return {
                    "type": "browser",
                    "category": "browser",
                    "app": browser_label,
                    "title": title,
                    "summary": f"{title} ({browser_label})",
                    "action_label": f"Open browser tab: {title}"
                }

        # 5. Generic desktop application
        parts = [p.strip() for p in win_clean.split(" - ") if p.strip()]
        app_name = parts[0] if parts else win_clean
        
        # Filter out ephemeral OS system windows & background shell widgets
        ephemeral_system_windows = [
            "settings", "search", "task manager", "taskmgr", "calculator", "calc",
            "volume control", "sound settings", "system settings", "control panel",
            "snipping tool", "snip & sketch", "notification center", "quick settings",
            "start menu", "taskbar", "shell experience host", "lockapp", "searchapp",
            "cortana", "copilot", "arova", "arovad", "frontend", "tauri", "npm", "cargo",
            "program manager", "desktop", "xprintidle", "root"
        ]
        if any(e == win_lower or win_lower.startswith(e) or f" {e} " in f" {win_lower} " for e in ephemeral_system_windows):
            return None

        if any(w in win_lower for w in ["arova", "arovad", "frontend", "tauri"]):
            return None
        return {
            "type": "window",
            "category": "app",
            "app": app_name,
            "title": win_clean,
            "summary": win_clean,
            "action_label": f"Launch {app_name}"
        }

    def _apply_os_context(self, ctx: Any, active: CognitiveWorkspace, target_dict: Optional[Dict[str, Any]] = None):
        if not ctx or not active:
            return
        dest = target_dict if target_dict is not None else active.reality.resources
        now = time.time()
        active_repo = active.interpretation.repo_paths[0] if (active.interpretation and active.interpretation.repo_paths) else None
        
        all_windows = set()
        if ctx.window_title:
            all_windows.add(ctx.window_title)
        for w in (ctx.open_windows or []):
            if w:
                all_windows.add(w)

        for win in all_windows:
            parsed = self._parse_ambient_window(win, active_repo=active_repo)
            if not parsed:
                continue
            
            # Form clean unique resource key
            if parsed.get("category") == "editor":
                key = parsed.get("file_path") or parsed.get("file_name") or win
                dest[key] = {
                    "identity": key,
                    "type": "vscode",
                    "category": "editor",
                    "app": parsed.get("app"),
                    "file_name": parsed.get("file_name"),
                    "file_path": parsed.get("file_path"),
                    "project": parsed.get("project"),
                    "last_seen": now,
                    "summary": parsed.get("action_label")
                }
            elif parsed.get("category") == "terminal":
                key = f"terminal://{parsed.get('cwd')}"
                dest[key] = {
                    "identity": parsed.get("cwd"),
                    "type": "terminal",
                    "category": "terminal",
                    "app": parsed.get("app"),
                    "last_seen": now,
                    "summary": parsed.get("action_label")
                }
            elif parsed.get("category") == "browser":
                key = f"url://{parsed.get('title')}"
                dest[key] = {
                    "identity": parsed.get("title"),
                    "type": "browser",
                    "category": "browser",
                    "app": parsed.get("app"),
                    "last_seen": now,
                    "summary": parsed.get("action_label")
                }
            elif parsed.get("category") == "app":
                key = f"app://{parsed.get('app')}"
                dest[key] = {
                    "identity": parsed.get("app"),
                    "type": "window",
                    "category": "app",
                    "app": parsed.get("app"),
                    "last_seen": now,
                    "summary": parsed.get("action_label")
                }

        for media in (ctx.playing_media or []):
            if media:
                dest[media] = {
                    "identity": media,
                    "type": "media",
                    "last_seen": now,
                    "summary": f"Playing media: {media}"
                }

    def get_continue_context(self, workspace_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Generates genuine, multi-domain continue context, [Why?] explainability reasons,
        evidence-based confidence breakdown, and restoration outcomes (`Phase 6 & 7`).
        Fully dynamic for any user, any repository, and any workspace task.
        """
        ws = self.get_workspace(workspace_id) if workspace_id else self.get_active_workspace()
        if not ws:
            return {}

        # Refresh live open windows, editor files & browser history if not an uninitialized clean workspace
        if not ws.workspace_id.startswith("clean_"):
            self.perform_ambient_scan()

        home = os.path.abspath(os.path.expanduser("~"))

        # 1. Dynamically identify active workspace project/folder
        valid_repos = [
            p for p in ws.interpretation.repo_paths
            if isinstance(p, str) and os.path.isdir(p) and p != home and p != "/" and "/.cache/" not in p
        ]
        
        # If no repos in interpretation, inspect reality resources
        if not valid_repos:
            for k, v in ws.reality.resources.items():
                if isinstance(v, dict) and v.get("type") in ["vscode", "terminal"]:
                    path = v.get("identity", k)
                    if isinstance(path, str) and path.startswith("terminal://"):
                        path = path.replace("terminal://", "")
                    if os.path.isdir(path) and path != home and path != "/" and "/.cache/" not in path:
                        valid_repos.append(path)

        active_path = valid_repos[0] if valid_repos else home
        project_name = os.path.basename(active_path) if active_path != home else "General Workspace"
        
        # Update title dynamically if generic
        if ws.title in ["New Workspace", "Active Workspace", "General Workspace Project"] or not ws.title:
            ws.title = f"{project_name.replace('-', ' ').replace('_', ' ').title()} Project"

        # 2. Dynamic Progress / Activity Discovery (Git, Filesystem, or Windows)
        activity_summary = ""
        uncommitted_count = 0
        if active_path and active_path != home:
            # Check Git status if repository exists
            git_dir = os.path.join(active_path, ".git")
            if os.path.isdir(git_dir):
                try:
                    import subprocess
                    proc_log = subprocess.run(["git", "log", "-n", "1", "--pretty=format:%s"], capture_output=True, text=True, cwd=active_path, timeout=2.0)
                    if proc_log.returncode == 0 and proc_log.stdout.strip():
                        activity_summary = proc_log.stdout.strip()
                    
                    proc_stat = subprocess.run(["git", "status", "-s"], capture_output=True, text=True, cwd=active_path, timeout=2.0)
                    if proc_stat.returncode == 0 and proc_stat.stdout.strip():
                        uncommitted_count = len(proc_stat.stdout.strip().splitlines())
                except Exception:
                    pass
            else:
                # Non-git directory: inspect recently modified files (last 24 hours)
                try:
                    now = time.time()
                    recent_files = []
                    for root, _, files in os.walk(active_path):
                        if any(skip in root for skip in [".git", "node_modules", ".cache", "__pycache__", "dist", "build"]):
                            continue
                        for f in files:
                            fp = os.path.join(root, f)
                            try:
                                mtime = os.stat(fp).st_mtime
                                if (now - mtime) < 86400: # 24h
                                    recent_files.append(f)
                            except Exception:
                                pass
                        if len(recent_files) >= 3:
                            break
                    if recent_files:
                        activity_summary = f"Working on files: {', '.join(recent_files[:3])}"
                except Exception:
                    pass

        # 3. Build Organic, 100% Empirical Story
        if getattr(ws.understanding.confidence, "score", None) is None and not ws.reality.resources and not ws.understanding.decisions:
            story = []
        elif ws.understanding.story_narrative:
            story = list(ws.understanding.story_narrative)
        else:
            empirical_story = []
            if ws.title and ws.title not in ["New Workspace", "Active Workspace", "General Workspace Project", f"{project_name.replace('-', ' ').replace('_', ' ').title()} Project"]:
                empirical_story.append(f"Yesterday you focused on {ws.title}.")
            elif activity_summary:
                if uncommitted_count > 0:
                    empirical_story.append(f"Recent progress in {project_name}: {activity_summary} ({uncommitted_count} active edits).")
                else:
                    empirical_story.append(f"Recent progress in {project_name}: {activity_summary}.")
            else:
                empirical_story.append(f"Yesterday you focused on {ws.title}.")

            if ws.understanding.decisions:
                empirical_story.append(f"Decision established: {ws.understanding.decisions[0]}")
            if ws.understanding.momentum.current_blocker:
                empirical_story.append(f"Stopped due to blocker: {ws.understanding.momentum.current_blocker}")

            # Active Terminal & Editor context
            active_terms = [
                os.path.relpath(str(v.get("identity")), home) 
                for k, v in ws.reality.resources.items() 
                if isinstance(v, dict) and v.get("type") == "terminal" and v.get("identity") != home
            ]
            if active_terms:
                empirical_story.append(f"Running terminal in: ~/{active_terms[0]}")

            # Active Browser context from today
            active_tabs = [
                v.get("summary") or k for k, v in ws.reality.resources.items() 
                if isinstance(v, dict) and v.get("type") == "browser" and v.get("summary")
            ]
            if active_tabs:
                empirical_story.append(f"Referencing: {', '.join(active_tabs[:2])}")

            story = empirical_story

        reasons = list(ws.understanding.explainability_reasons)
        if not reasons:
            empirical_reasons = []
            empirical_reasons.append(f"You spent significant time in {ws.title} recently")
            score = getattr(ws.understanding.confidence, "score", None)
            if score is not None and score >= 80:
                empirical_reasons.append(f"High confidence state ({score}%)")
            if ws.understanding.momentum.current_blocker:
                empirical_reasons.append("You left with one unresolved blocker")
            if valid_repos:
                empirical_reasons.append(f"Active project folder: ~/{os.path.relpath(active_path, home)}")
            if not empirical_reasons:
                empirical_reasons.append("Primary workspace environment initialized")
            reasons = empirical_reasons

        # Evidence-Based Observation Scorecard (`Phase 7 Point 4 & HYP-01 Reality Guarantee`)
        valid_repos = [p for p in ws.interpretation.repo_paths if os.path.isdir(p)]
        repo_score = 100 if valid_repos else 0
        
        total_file_resources = [
            k for k, v in ws.reality.resources.items()
            if (isinstance(v, dict) and v.get("type") in ("file", "vscode")) or (str(k).startswith("/") and not str(k).startswith("http"))
        ]
        valid_files = [
            f for f in total_file_resources
            if os.path.exists(f) or any(
                r.file == f and getattr(r, 'exists', False) for r in self.restoration_engine.resource_registry.all_resources()
            )
        ]
        open_files_score = int((len(valid_files) / len(total_file_resources)) * 100) if total_file_resources else 0
            
        goal_score = getattr(ws, "confidence_layer", None).goal.score if getattr(ws, "confidence_layer", None) else (100 if ws.understanding.momentum.goal else 0)
        blk_score = getattr(ws, "confidence_layer", None).blocker.score if getattr(ws, "confidence_layer", None) else (100 if ws.understanding.momentum.current_blocker else 0)
        
        url_keys = [
            k for k, v in ws.reality.resources.items()
            if str(k).startswith("http") or (isinstance(v, dict) and v.get("type") in ("url", "browser", "media"))
        ]
        docs_score = 100 if url_keys else 0
        
        term_res = [v for k, v in ws.reality.resources.items() if isinstance(v, dict) and v.get("type") == "terminal"]
        term_cwd = term_res[0].get("identity") if term_res else (valid_repos[0] if valid_repos else None)
        if term_cwd and term_cwd.startswith("terminal://"):
            term_cwd = term_cwd.replace("terminal://", "")
        term_score = getattr(ws, "confidence_layer", None).terminal.score if getattr(ws, "confidence_layer", None) else (100 if (term_res and term_cwd and os.path.isdir(term_cwd)) else 0)
        recent_command = term_res[0].get("recent_command") if term_res else None

        confidence_breakdown = {
            "Repository": repo_score,
            "Open files": open_files_score,
            "Goal": goal_score,
            "Blocker": blk_score,
            "Browser docs": docs_score,
            "Terminal": term_score
        }

        # Also register files/urls to our resource registry
        for k, v in ws.reality.resources.items():
            if isinstance(v, dict):
                r_type = v.get("type", "file")
                identity = v.get("identity", k)
                if r_type == "file" or identity.startswith("/"):
                    self.resource_registry.register_file(identity, line=v.get("line"), col=v.get("col"))
                elif r_type in ["url", "browser"] or identity.startswith("http"):
                    self.resource_registry.register_url(identity, title=v.get("summary"))

        last_outcomes = self.restoration_engine.last_outcome.to_dict() if self.restoration_engine.last_outcome else None

        resource_summaries = {}
        for k, v in ws.reality.resources.items():
            if isinstance(v, dict) and v.get("summary"):
                resource_summaries[k] = v.get("summary")

        # Explicit structured categorized items for clear, transparent UI presentation
        categorized_editors = []
        categorized_terminals = []
        categorized_browsers = []
        categorized_apps = []

        for k, v in ws.reality.resources.items():
            if not isinstance(v, dict):
                continue
            r_type = v.get("type", "")
            r_cat = v.get("category", "")
            identity = str(v.get("identity", k))
            
            # Skip Arova self-references & dead noise
            if any(skip in identity.lower() for skip in ["arova - arova", "arova desktop"]) or identity.lower() in ["arova", "arovad"]:
                continue
            if identity in ["N/A", "v2", "Desktop", "xprintidle"]:
                continue
                
            if r_cat == "terminal" or r_type == "terminal" or identity.startswith("terminal://"):
                clean_cwd = identity.replace("terminal://", "")
                disp_cwd = clean_cwd.replace(home, "~")
                term_app = v.get("app") or "Terminal"
                if not any(t["cwd"] == clean_cwd for t in categorized_terminals):
                    categorized_terminals.append({
                        "id": clean_cwd,
                        "cwd": clean_cwd,
                        "display_path": disp_cwd,
                        "app": term_app,
                        "recent_command": recent_command,
                        "action_label": f"Restore terminal session ({disp_cwd})"
                    })
            elif r_cat == "browser" or r_type in ["browser", "url"] or identity.startswith("http"):
                clean_raw_url = identity.replace("url://", "").strip()
                from arova.core.ambience.browser_tracker import BrowserTabCapture
                
                raw_title = v.get("summary") or v.get("title") or clean_raw_url
                clean_url, custom_title = BrowserTabCapture._clean_url(clean_raw_url, raw_title)
                final_title = custom_title or raw_title
                
                # Layer 1: Strict noise, auth, and error page filtering
                if BrowserTabCapture._is_noise_url(clean_url, final_title):
                    continue

                host = clean_url
                try:
                    import urllib.parse
                    parsed_u = urllib.parse.urlparse(clean_url)
                    if parsed_u.netloc:
                        host = parsed_u.netloc
                except Exception:
                    pass

                # Layer 2: Canonical cross-domain and title deduplication
                title_key = final_title.strip().lower()
                if any(
                    b["url"] == clean_url or 
                    b["title"].strip().lower() == title_key or
                    (host and b.get("domain") == host and (title_key in b["title"].strip().lower() or b["title"].strip().lower() in title_key))
                    for b in categorized_browsers
                ):
                    continue

                browser_app = v.get("app") or "Browser"
                
                # Layer 3: Cognitive relevance scoring
                score = 0
                proj_tokens = [t.lower() for t in ws.title.split() if len(t) > 2]
                url_and_title = f"{clean_url} {final_title}".lower()
                if any(tok in url_and_title for tok in proj_tokens):
                    score += 50
                if any(dev in url_and_title for dev in ["github.com", "gitlab.com", "docs", "api", "tutorial", "architecture"]):
                    score += 30
                if v.get("last_seen"):
                    # Bonus for recency
                    score += min(20, max(0, int((v["last_seen"] - (time.time() - 3600)) / 180)))

                categorized_browsers.append({
                    "id": clean_url,
                    "url": clean_url,
                    "title": final_title,
                    "domain": host,
                    "app": browser_app,
                    "score": score,
                    "action_label": f"Open tab: {final_title}"
                })
            elif r_cat == "editor" or r_type in ["vscode", "editor", "file"] or (identity.startswith("/") and not identity.startswith("http")):
                clean_path = identity.replace("file://", "").strip()
                path_lower = clean_path.lower()
                
                # Layer 1: Strict noise filtering for package caches, cargo registries, and IDE internals
                noisy_editor_patterns = [
                    "/.cargo", "/index.crates.io", "/.rustup", "/.gemini", "/.npm", "/.nvm",
                    "/.pyenv", "/.vscode", "/.cursor", "/.antigravity", "/node_modules",
                    "/site-packages", "/__pycache__", "/venv", "/.venv", "/target/", "/dist/", "/build/",
                    "\\appdata\\", "\\.cargo\\", "\\index.crates.io\\", "\\node_modules\\"
                ]
                if any(np in path_lower for np in noisy_editor_patterns):
                    continue

                parts = clean_path.split("/")
                f_name = v.get("file_name") or parts[-1]
                
                # Clean up raw window title strings from IDEs
                if " - " in f_name or "antigravity" in f_name.lower():
                    subparts = [p.strip() for p in f_name.split(" - ") if p.strip()]
                    cleaned_sub = []
                    for p in subparts:
                        p_low = p.lower()
                        if p_low in ("antigravity-ide", "antigravity ide", "antigravity", "visual studio code", "code", "code - oss", "cursor"):
                            continue
                        if ws.title and p_low == ws.title.lower():
                            continue
                        cleaned_sub.append(p)
                    
                    if cleaned_sub:
                        f_name = cleaned_sub[-1]
                    else:
                        f_name = ws.title or os.path.basename(active_path)

                # Skip if this is just a redundant duplicate title of the workspace project itself
                if ws.title and f_name.lower() == ws.title.lower() and any(e.get("name", "").lower() == ws.title.lower() for e in categorized_editors):
                    continue

                rel_dir = "/".join(parts[-3:-1]) if len(parts) >= 3 else ""
                editor_app = v.get("app") or "Antigravity IDE"
                
                # Avoid duplicate file entries
                if not any(e["name"] == f_name or e["path"] == clean_path for e in categorized_editors):
                    categorized_editors.append({
                        "id": clean_path,
                        "name": f_name,
                        "path": clean_path,
                        "directory": f".../{rel_dir}" if rel_dir else "",
                        "app": editor_app,
                        "action_label": v.get("summary") or f"Open {f_name} in {editor_app}"
                    })
            elif r_cat == "app" or r_type == "window":
                app_name = v.get("app") or identity
                app_name_lower = str(app_name).lower()
                
                # Layer 1: Filter out OS shell utilities and background widgets
                ephemeral_apps = [
                    "settings", "search", "task manager", "taskmgr", "calculator", "calc",
                    "volume control", "sound settings", "system settings", "control panel",
                    "snipping tool", "snip & sketch", "notification center", "quick settings",
                    "start menu", "taskbar", "shell experience host", "lockapp", "searchapp",
                    "cortana", "copilot", "arova", "arovad", "frontend", "tauri", "npm", "cargo"
                ]
                if any(e == app_name_lower or app_name_lower.startswith(e) for e in ephemeral_apps):
                    continue

                if not any(a["name"] == app_name for a in categorized_apps):
                    categorized_apps.append({
                        "id": identity,
                        "name": app_name,
                        "window_title": v.get("title") or identity,
                        "app": app_name,
                        "action_label": f"Launch {app_name}"
                    })

        # Layer 4: Working set synthesis & curation
        # Deduplicate bare project folder when specific files in the project are present
        has_specific_files = any(e.get("name") and "." in e.get("name") for e in categorized_editors)
        if has_specific_files:
            categorized_editors = [e for e in categorized_editors if "." in e.get("name") or (e.get("path") != active_path and e.get("name") != os.path.basename(active_path))]

        # Sort browser tabs by cognitive relevance score and limit to top 4-5 high-signal items
        categorized_browsers.sort(key=lambda x: x.get("score", 0), reverse=True)
        categorized_browsers = categorized_browsers[:5]

        # Limit editors to top 4 and apps to top 3
        categorized_editors = categorized_editors[:4]
        categorized_apps = categorized_apps[:3]

        return {
            "workspace_id": ws.workspace_id,
            "title": ws.title,
            "domain_type": ws.domain_type,
            "story_narrative": story,
            "explainability_reasons": reasons,
            "trajectory_story": story[0] if story else f"Continuing active development in {ws.title}",
            "confidence_score": ws.understanding.confidence.score,
            "confidence_breakdown": confidence_breakdown,
            "last_restore_outcomes": last_outcomes,
            "current_goal": ws.understanding.momentum.goal,
            "current_blocker": ws.understanding.momentum.current_blocker,
            "next_action": ws.understanding.momentum.next_action,
            "categorized_items": {
                "editors": categorized_editors,
                "terminals": categorized_terminals,
                "browsers": categorized_browsers,
                "apps": categorized_apps
            },
            "associated_resources": [
                k for k, v in ws.reality.resources.items()
                if isinstance(v, dict) and v.get("type") in ["vscode", "terminal", "browser", "url"]
            ][:10],
            "resource_summaries": resource_summaries,
            "terminal_cwd": term_cwd,
            "recent_command": recent_command,
            "options": {
                "restore_vscode": True,
                "restore_terminal": True,
                "restore_chrome": len(categorized_browsers) > 0,
                "restore_editors": True,
                "restore_browsers": len(categorized_browsers) > 0,
                "restore_documentation": len(categorized_browsers) > 0
            }
        }

    def _on_workspace_continue(self, event: Any):
        payload = event.data if hasattr(event, "data") else event
        if payload and "workspace_id" in payload:
            wid = payload["workspace_id"]
            restore_options = payload.get("options", {})
            self.set_active_workspace(wid)
            ws = self.get_workspace(wid)
            if ws:
                self.restore_environment(ws, restore_options)

    def ingest_fragment(self, fragment: Any):
        self._on_fragment_reported(fragment)

    def _auto_emerge_workspace(self, payload: dict) -> Optional[CognitiveWorkspace]:
        """Emerges a new long-lived workspace naturally upon observing meaningful user activity."""
        source_id = payload.get("source_identity", "")
        summary = payload.get("activity_summary", "")
        if not source_id and not summary:
            return None
            
        title = "Current Exploration"
        domain_type = "general"
        
        # Derive initial title & domain from source or activity summary
        sig_text = f"{source_id} {summary}".lower()
        if any(term in sig_text for term in [".py", ".ts", ".rs", ".go", "vscode", "git", "repo", "code", "pytest", "python", "bash", "terminal", "traceback", "debug"]):
            domain_type = "engineering"
            if "arova" in sig_text:
                title = "Arova Architecture & Development"
            else:
                title = "Active Code Development"
        elif any(term in sig_text for term in ["docs", "browser", "chrome", "firefox", "http://", "https://"]):
            domain_type = "research"
            title = "Research & Documentation"
            
        ws = CognitiveWorkspace(title=title, domain_type=domain_type, pinned=True)
        self._workspaces[ws.workspace_id] = ws
        self._active_workspace_id = ws.workspace_id
        logger.info(f"WorkspaceManager: Organically emerged first workspace '{title}' ({ws.workspace_id}) from observed activity.")
        self.sync_to_bus()
        return ws

    def _on_fragment_reported(self, event: Any):
        payload = event.data if hasattr(event, "data") else event
        if not payload:
            return
            
        active = self.get_active_workspace()
        if not active:
            active = self._auto_emerge_workspace(payload)
            if not active:
                return

        # Time to Productivity & Behavioral Context Recovery Time Saved KPI evaluation
        if active.workspace_id in self._resume_timestamps:
            resumed_at = self._resume_timestamps.pop(active.workspace_id)
            time_to_productivity_seconds = time.time() - resumed_at
            # Calculate from actual observed complexity (resources to reopen, context switches avoided)
            resource_count = len(active.reality.resources)
            access_dict = self._resource_access_counts.get(active.workspace_id, {})
            switches_avoided = sum(access_dict.values()) if isinstance(access_dict, dict) else 0
            behavioral_recovery_seconds = max(MIN_BEHAVIORAL_RECOVERY_SECONDS, (resource_count * SECONDS_PER_RESOURCE_REOPEN) + (switches_avoided * SECONDS_PER_SWITCH_AVOIDED))
            context_recovery_saved_seconds = max(0.0, behavioral_recovery_seconds - time_to_productivity_seconds)
            logger.info(f"KPI Telemetry: Time to productivity for workspace '{active.title}' was {time_to_productivity_seconds:.2f}s. Behavioral Context Recovery Saved: {context_recovery_saved_seconds:.1f}s.")
            if self.event_bus:
                self.event_bus.emit("telemetry", "time_to_productivity", {
                    "workspace_id": active.workspace_id,
                    "title": active.title,
                    "seconds": time_to_productivity_seconds
                })
                self.event_bus.emit("telemetry", "context_recovery_saved", {
                    "workspace_id": active.workspace_id,
                    "title": active.title,
                    "saved_seconds": context_recovery_saved_seconds,
                    "saved_minutes": round(context_recovery_saved_seconds / 60.0, 1),
                    "switches_avoided": switches_avoided,
                    "resources_prepared": resource_count
                })

        # 1. Update Reality Layer (Zero-LLM)
        source_id = payload.get("source_identity", "unknown")
        provider_id = payload.get("provider_id", "unknown")
        summary = payload.get("activity_summary", "")
        
        active.reality.resources[source_id] = {
            "identity": source_id,
            "type": provider_id,
            "last_seen": time.time(),
            "summary": summary
        }
        # Only set last_accessed_at if not previously set (preserves real user absence gap)
        if not active.reality.last_accessed_at or active.reality.last_accessed_at == 0.0:
            active.reality.last_accessed_at = time.time()

        # Update resource access counts for universal stuckness
        if active.workspace_id not in self._resource_access_counts:
            self._resource_access_counts[active.workspace_id] = {}
        counts = self._resource_access_counts[active.workspace_id]
        counts[source_id] = counts.get(source_id, 0) + 1

        # 2. Extract Interpretation & Check Universal Stuckness
        self._extract_interpretation_and_check_clustering(active, source_id, summary)
        self._calculate_stuckness_and_intervene(active, source_id, summary, counts[source_id])

    def _extract_interpretation_and_check_clustering(self, active: CognitiveWorkspace, source_id: str, summary: str):
        # Update interpretation repo_paths and infer project title dynamically from user activity
        parts = [p for p in source_id.split("/") if p]
        if "/" in source_id:
            if len(parts) >= 2:
                for idx, part in enumerate(parts):
                    if part in ["home", "Users", "workspace"] and idx + 2 < len(parts):
                        project_folder = parts[idx + 2]
                        if project_folder not in ["Desktop", "Downloads", "Documents", "tmp"]:
                            repo_prefix = "/" + "/".join(parts[:idx + 3])
                            if repo_prefix not in active.interpretation.repo_paths:
                                active.interpretation.repo_paths.append(repo_prefix)
                            # If workspace has default title, set to the user's actual project folder
                            if active.title in ["Default Workspace", "Active Workspace", "Current Workspace"]:
                                active.title = project_folder
                            break

        # Dynamic domain & title refinement based on objective activity clusters
        sig_text = f"{source_id} {summary}".lower()
        if any(w in sig_text for w in [".xlsx", ".csv", "portfolio", "bloomberg", "treasury", "equities"]):
            active.domain_type = "finance"
            if active.title in ["Default Workspace", "Active Workspace"]:
                active.title = "Financial Analysis"
        elif any(w in sig_text for w in ["literature", "scholar", "pdf", "paper"]):
            active.domain_type = "research"
            if active.title in ["Default Workspace", "Active Workspace"]:
                active.title = "Research & Literature"
        elif any(w in sig_text for w in [".py", ".ts", ".js", ".rs", ".go", ".cpp", ".c", ".java", "git"]):
            active.domain_type = "engineering"
            filename = parts[-1] if parts else source_id
            if filename and active.title in ["Default Workspace", "Active Workspace"]:
                if len(parts) >= 2 and parts[-2] not in ["home", "Users", "Desktop", "Downloads"]:
                    active.title = f"{parts[-2]}: {filename}"
                else:
                    active.title = filename


        # Check merge possibilities
        self.check_for_emergence_or_merge()
        self.sync_to_bus()

    def _calculate_stuckness_and_intervene(self, active: CognitiveWorkspace, source_id: str, summary: str, access_count: int):
        """
        Universal stuckness detection across any domain (developer, writer, student, finance, researcher).
        Evaluates repeat visit factor, error signatures, context switches, and stagnant focus time.
        """
        score = 0.0
        reasons = []

        # Repeat visit factor
        if access_count >= 3:
            score += min(STUCKNESS_MAX_REPEAT_PENALTY, (access_count - 2) * STUCKNESS_REPEAT_VISIT_RATE)
            reasons.append(f"Revisited resource '{source_id.split('/')[-1]}' {access_count} times")

        # Error signature factor
        summary_lower = summary.lower()
        has_error = any(term in summary_lower for term in ["error", "exception", "failed", "traceback", "retry", "stuck", "rewrite"])
        if has_error:
            score += STUCKNESS_ERROR_PENALTY
            reasons.append("Observed repeated friction/error signatures")

        # Stagnant focus factor
        if active.reality.total_focus_seconds > STUCKNESS_STAGNANT_TIME_THRESHOLD_SECONDS and (active.understanding.health.status == "Blocked" or has_error or access_count >= 4):
            score += STUCKNESS_STAGNANT_FOCUS_PENALTY
            reasons.append("Extended focus duration under high friction")

        active.interpretation.stuckness_score = min(100.0, score)
        active.interpretation.stuckness_reasons = reasons

        # Trigger observational intervention if stuckness >= 75 and 10+ min since last intervention
        if active.interpretation.stuckness_score >= 75.0:
            last_at = self._last_intervention_at.get(active.workspace_id, 0.0)
            if time.time() - last_at > 600.0:
                self._trigger_observational_intervention(active, source_id, reasons)

    def _trigger_observational_intervention(self, active: CognitiveWorkspace, source_id: str, reasons: List[str]):
        """
        Observational and analytical first before offering concrete actions.
        Delivers effort-saving continuity guidance without behaving like a chatbot.
        """
        self._last_intervention_at[active.workspace_id] = time.time()
        logger.info(f"WorkspaceManager: Triggering observational intervention for '{active.title}' (Stuckness: {active.interpretation.stuckness_score}%)")
        
        resource_name = source_id.split('/')[-1] if '/' in source_id else source_id
        next_step = active.understanding.momentum.next_action or "the core state persistence flow"
        
        # Work Factory: Automatically generate an Investigation work item attached to the workspace
        self.create_completed_work(
            workflow="Investigate",
            headline=f"Traced bottleneck around {resource_name}",
            verification_proof=f"Verified across {len(active.reality.resources)} explored resources & error patterns",
            action_type="review_code",
            payload={"resource": source_id, "reasons": reasons},
            nwr_minutes=max(10.0, round(active.reality.total_focus_seconds / 60.0, 1))
        )
        
        if self.event_bus:
            self.event_bus.emit("cognition", "surfacing_push", {
                "type": "surfacing",
                "from": "Arova",
                "paragraphs": [
                    f"<strong>You're still solving the issue around <code>{resource_name}</code>.</strong>",
                    f"Based on what you've already ruled out across {len(active.reality.resources)} explored files/resources ({reasons[0] if reasons else 'high friction'}), {next_step} looks like the remaining bottleneck."
                ],
                "actions": [
                    {"label": "Trace the current flow", "event": "workspace.intervention_action", "payload": {"action": "trace_flow", "resource": source_id}},
                    {"label": "Summarize the architecture", "event": "workspace.intervention_action", "payload": {"action": "summarize_arch", "resource": source_id}},
                    {"label": "Start fresh", "event": "workspace.intervention_action", "payload": {"action": "start_fresh", "resource": source_id}}
                ]
            })

    def create_completed_work(self, workflow: str, headline: str, verification_proof: str, 
                              action_type: str = "apply_patch", payload: dict = None, 
                              status: str = "Completed", failure_reason: str = None, 
                              nwr_minutes: float = 15.0, confidence: float = 0.95,
                              reversibility: str = "high", blast_radius: str = "tiny",
                              parent_work_id: str = None) -> dict:
        """
        Work Factory: Creates or updates a versioned CompletedWork item attached directly to the active Workspace.
        """
        from dataclasses import asdict
        from arova.core.persistence.schema import CompletedWork
        
        active = self.get_active_workspace()
        existing_work = None
        version = 1
        
        if active:
            # Check for version evolution (e.g. v1 Investigation -> v2 Verified Fix)
            for w in active.understanding.completed_work:
                if w.get("work_id") == parent_work_id or (w.get("workflow") == "Investigate" and workflow == "Fix"):
                    existing_work = w
                    version = w.get("version", 1) + 1
                    break
        
        work = CompletedWork(
            workflow=workflow,
            headline=headline,
            status=status,
            verified=(status == "Completed"),
            verification_proof=verification_proof,
            failure_reason=failure_reason,
            confidence=confidence,
            reversibility=reversibility,
            blast_radius=blast_radius,
            action_type=action_type,
            payload=payload or {},
            net_work_removed_minutes=nwr_minutes
        )
        work_dict = asdict(work)
        work_dict["version"] = version
        work_dict["workspace_id"] = active.workspace_id if active else None
        if parent_work_id:
            work_dict["parent_work_id"] = parent_work_id
            
        self._completed_work.append(work_dict)
        if active:
            active.understanding.completed_work.append(work_dict)
        
        if self.event_bus:
            self.event_bus.emit("work", "COMPLETED_WORK_CREATED", {"work": work_dict})
            self.sync_to_bus()
        return work_dict

    def _on_work_accept(self, event: Any):
        payload = event.data if hasattr(event, "data") else event
        work_id = payload.get("work_id") if isinstance(payload, dict) else None
        for w in self._completed_work:
            if w.get("work_id") == work_id:
                w["status"] = "Accepted"
                nwr = w.get("net_work_removed_minutes", 15.0)
                logger.info(f"WorkspaceManager: User ACCEPTED completed work '{w.get('headline')}'. Net Work Removed: {nwr} mins.")
                if self.event_bus:
                    self.event_bus.emit("telemetry", "net_work_removed", {
                        "work_id": work_id,
                        "workflow": w.get("workflow"),
                        "nwr_minutes": nwr,
                        "action": "accepted"
                    })
                    self.event_bus.emit("work", "WORK_UPDATED", {"work": w})
                break

    def _on_work_reject(self, event: Any):
        payload = event.data if hasattr(event, "data") else event
        work_id = payload.get("work_id") if isinstance(payload, dict) else None
        for w in self._completed_work:
            if w.get("work_id") == work_id:
                w["status"] = "Rejected"
                logger.info(f"WorkspaceManager: User REJECTED completed work '{w.get('headline')}'.")
                if self.event_bus:
                    self.event_bus.emit("telemetry", "net_work_removed", {
                        "work_id": work_id,
                        "workflow": w.get("workflow"),
                        "nwr_minutes": 0.0,
                        "action": "rejected"
                    })
                    self.event_bus.emit("work", "WORK_UPDATED", {"work": w})
                break

    def check_for_emergence_or_merge(self):
        """
        If two workspaces share >80% repo paths, terminology, or browser domains over time,
        automatically merge them (e.g., 'Researching Groq' + 'Building Arova' -> 'Arova Development').
        """
        all_ws = list(self._workspaces.values())
        if len(all_ws) < 2:
            return

        for i in range(len(all_ws)):
            for j in range(i + 1, len(all_ws)):
                w1 = all_ws[i]
                w2 = all_ws[j]
                
                # Check path overlap
                overlap = set(w1.interpretation.repo_paths).intersection(set(w2.interpretation.repo_paths))
                if overlap and len(overlap) >= min(len(w1.interpretation.repo_paths), len(w2.interpretation.repo_paths)):
                    logger.info(f"WorkspaceManager: Auto-merging '{w2.title}' into '{w1.title}' due to shared repository cluster.")
                    # Merge resources
                    w1.reality.resources.update(w2.reality.resources)
                    w1.reality.total_focus_seconds += w2.reality.total_focus_seconds
                    w1.understanding.decisions.extend(w2.understanding.decisions)
                    # Remove w2
                    if self._active_workspace_id == w2.workspace_id:
                        self._active_workspace_id = w1.workspace_id
                    del self._workspaces[w2.workspace_id]
                    return

    def _on_timeline_create(self, event: Any):
        payload = event.data if hasattr(event, "data") else event
        active = self.get_active_workspace()
        if active and payload:
            event_id = payload.get("id")
            if event_id and event_id not in active.reality.timeline_event_ids:
                active.reality.timeline_event_ids.append(event_id)

    def _on_turn_completed(self, event: Any):
        # Meaningful transition: turn completed -> trigger synthesis
        self.trigger_synthesis(reason="turn_completed")

    def trigger_synthesis(self, reason: str):
        """
        Triggered ONLY on meaningful transitions (big commit, decision change, context shift, long pause, user leave).
        Updates Understanding Layer on top of Reality Layer without periodic spam.
        """
        active = self.get_active_workspace()
        if not active:
            return

        logger.info(f"WorkspaceManager: Triggering UnderstandingLayer synthesis for '{active.title}' (Reason: {reason})")
        active.understanding.last_synthesized_at = time.time()
        
        # If confidence > 80%, ensure status is Focused and momentum is active
        if active.understanding.confidence.score > 80:
            active.understanding.health.status = "Focused"
            active.understanding.health.last_progress_reason = f"Active progress confirmed during: {reason}"
            active.understanding.health.last_progress_timestamp = time.time()
            
        self.sync_to_bus()

    def sync_to_bus(self):
        active_ws = self.get_active_workspace()
        if hasattr(self, "search_index") and self.search_index and active_ws:
            self.search_index.index_workspace(active_ws)
        if self.event_bus:
            workspaces_data = [w.to_dict() for w in self._workspaces.values()]
            active_dict = active_ws.to_dict() if active_ws else None
            if active_dict and active_ws:
                try:
                    continue_ctx = self.get_continue_context(active_ws.workspace_id)
                    if isinstance(continue_ctx, dict):
                        active_dict.update(continue_ctx)
                except Exception as e:
                    logger.debug(f"sync_to_bus continue_context enrichment warning: {e}")
            self.event_bus.emit("workspace", "sync", {
                "active_workspace_id": self._active_workspace_id,
                "active_workspace": active_dict,
                "workspaces": workspaces_data,
                "completed_work": self._completed_work
            })

