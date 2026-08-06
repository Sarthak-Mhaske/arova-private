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
        cwd = os.path.abspath(os.path.expanduser("/home/sarthak/arova"))
        ws = self._workspaces.get("ws_default")
        
        # If workspace already exists (e.g. hydrated from hot_state), do NOT overwrite its resources
        if ws:
            if getattr(ws, "interpretation", None) and not ws.interpretation.repo_paths:
                ws.interpretation.repo_paths = [cwd]
            return ws
        
        # Initialize default from scratch only if it does not exist
        ws = CognitiveWorkspace(
            workspace_id="ws_default",
            title="New Workspace",
            domain_type="engineering",
            pinned=True
        )
        ws.reality.resources = {}
        ws.interpretation.repo_paths = []
        if not getattr(ws.understanding, "momentum", None) or not ws.understanding.momentum.goal:
            ws.understanding.momentum = WorkspaceMomentum()
        self._workspaces["ws_default"] = ws
        if not self._active_workspace_id:
            self._active_workspace_id = "ws_default"
        logger.info(f"WorkspaceManager: Initialized default workspace '{ws.title}' ({ws.workspace_id}) with project resources at {cwd}")
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

        for win in open_windows:
            if isinstance(win, str) and win and win != window_title:
                provider = self._classify_app_type(win)
                self.ingest_fragment({
                    "source_identity": win,
                    "provider_id": provider,
                    "activity_summary": f"Open window: {win}"
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

            # Phase B: Legacy event emit compatibility
            restore_all = restore_options.get("restore_all", False)
            if restore_all or restore_options.get("restore_editors", False) or restore_options.get("restore_vscode", False):
                for res_id, res_meta in workspace.reality.resources.items():
                    if isinstance(res_meta, dict) and res_meta.get("type") == "file":
                        self.event_bus.emit("environment", "OPEN_RESOURCE_REQUESTED", {"resource": res_meta})
            if restore_all or restore_options.get("restore_browsers", False) or restore_options.get("restore_chrome", False):
                for domain in workspace.interpretation.browser_domains:
                    url = f"https://{domain}" if not domain.startswith("http") else domain
                    self.event_bus.emit("environment", "OPEN_URL_REQUESTED", {"url": url})

    def perform_ambient_scan(self):
        """
        Performs an immediate, authentic scan of open windows, running terminal CWDs,
        IDE project paths, active media, and recent browser tabs/URLs.
        Populates active_ws.reality.resources with real observed items.
        """
        active = self.get_active_workspace()
        if not active:
            return

        # 1. Scan running process CWDs (Kitty, Alacritty, Antigravity IDE, VS Code, Cursor)
        try:
            from arova.core.ambience.process_tracker import ProcessContextTracker
            proc_ctx = ProcessContextTracker.get_active_process_contexts()
            
            for p_path in proc_ctx.get("editor_projects", []):
                if os.path.isdir(p_path) and p_path not in active.interpretation.repo_paths:
                    active.interpretation.repo_paths.append(p_path)
                active.reality.resources[p_path] = {
                    "identity": p_path,
                    "type": "vscode",
                    "last_seen": time.time(),
                    "summary": f"Active project: {os.path.basename(p_path)}"
                }

            for t_cwd in proc_ctx.get("terminal_cwds", []):
                if os.path.isdir(t_cwd):
                    term_key = f"terminal://{t_cwd}"
                    active.reality.resources[term_key] = {
                        "identity": t_cwd,
                        "type": "terminal",
                        "last_seen": time.time(),
                        "summary": f"Terminal CWD: {t_cwd}"
                    }
                    if not active.interpretation.repo_paths and t_cwd != os.path.expanduser("~"):
                        active.interpretation.repo_paths.append(t_cwd)
        except Exception as e:
            logger.debug(f"WorkspaceManager perform_ambient_scan process error: {e}")

        # 2. Scan recent browser tabs/history
        try:
            from arova.core.ambience.browser_tracker import BrowserTabCapture
            urls = BrowserTabCapture.get_recent_browser_history(limit=10)
            for item in urls:
                u = item["url"]
                t = item["title"]
                cat = item.get("category", "general")
                active.reality.resources[u] = {
                    "identity": u,
                    "type": "browser",
                    "category": cat,
                    "last_seen": time.time(),
                    "summary": t
                }
                if u not in active.interpretation.browser_domains:
                    active.interpretation.browser_domains.append(u)
        except Exception as e:
            logger.debug(f"WorkspaceManager perform_ambient_scan browser error: {e}")

        # 3. Scan live open windows & media
        try:
            from arova.core.ambience.provider import LiveOSAmbientProvider
            provider = LiveOSAmbientProvider()
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(self._async_scan_os(provider, active))
                else:
                    ctx = loop.run_until_complete(provider.get_current_context())
                    self._apply_os_context(ctx, active)
            except Exception:
                pass
        except Exception as e:
            logger.debug(f"WorkspaceManager perform_ambient_scan OS window error: {e}")

    async def _async_scan_os(self, provider: Any, active: CognitiveWorkspace):
        try:
            ctx = await provider.get_current_context()
            self._apply_os_context(ctx, active)
        except Exception as e:
            logger.debug(f"Async OS scan failed: {e}")

    def _apply_os_context(self, ctx: Any, active: CognitiveWorkspace):
        if not ctx or not active:
            return
        if ctx.window_title:
            w_type = self._classify_app_type(f"{ctx.active_app} {ctx.window_title}")
            active.reality.resources[ctx.window_title] = {
                "identity": ctx.window_title,
                "type": w_type,
                "last_seen": time.time(),
                "summary": f"Active window: {ctx.window_title}"
            }
        for win in (ctx.open_windows or []):
            if win:
                w_type = self._classify_app_type(win)
                active.reality.resources[win] = {
                    "identity": win,
                    "type": w_type,
                    "last_seen": time.time(),
                    "summary": f"Open window: {win}"
                }
        for media in (ctx.playing_media or []):
            if media:
                active.reality.resources[media] = {
                    "identity": media,
                    "type": "media",
                    "last_seen": time.time(),
                    "summary": f"Playing media: {media}"
                }

    def get_continue_context(self, workspace_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Generates narrative Story-First continue context, [Why?] explainability reasons,
        evidence-based confidence breakdown, and restoration outcomes (`Phase 6 & 7`).
        """
        ws = self.get_workspace(workspace_id) if workspace_id else self.get_active_workspace()
        if not ws:
            return {}

        # If no resources are stored, run an immediate ambient scan of open windows, browser tabs & media
        if not ws.reality.resources:
            self.perform_ambient_scan()
        
        story = ws.understanding.story_narrative
        if not story:
            empirical_story = []
            if ws.understanding.decisions:
                dec = ws.understanding.decisions[0]
                empirical_story.append(f"Decision established: {dec}")
            if ws.understanding.momentum.current_blocker:
                empirical_story.append(f"Stopped due to blocker: {ws.understanding.momentum.current_blocker}")
            elif ws.understanding.momentum.next_action:
                empirical_story.append(f"Next planned step: {ws.understanding.momentum.next_action}")
            if len(ws.reality.resources) > 0:
                res_names = [os.path.basename(str(k)) for k in list(ws.reality.resources.keys())[:3]]
                empirical_story.append(f"Active focus on working set: {', '.join(res_names)}")
            else:
                empirical_story.append("No active working set items captured yet.")
            story = empirical_story

        reasons = ws.understanding.explainability_reasons
        if not reasons:
            empirical_reasons = []
            if len(ws.reality.resources) > 0:
                empirical_reasons.append(f"Active working resources observed ({len(ws.reality.resources)} items)")
            else:
                empirical_reasons.append("Primary workspace environment initialized")
            if ws.understanding.momentum.current_blocker:
                empirical_reasons.append("Active blocker recorded in workspace state")
            if ws.understanding.momentum.goal:
                empirical_reasons.append(f"Active objective tracked: {ws.understanding.momentum.goal}")
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
            
        goal_score = 100 if ws.understanding.momentum.goal else 0
        blk_score = 100 if ws.understanding.momentum.current_blocker else 0
        
        url_keys = [
            k for k, v in ws.reality.resources.items()
            if str(k).startswith("http") or (isinstance(v, dict) and v.get("type") in ("url", "browser", "media"))
        ]
        docs_score = 100 if url_keys else 0
        
        term_res = [v for k, v in ws.reality.resources.items() if isinstance(v, dict) and v.get("type") == "terminal"]
        term_cwd = term_res[0].get("identity") if term_res else (valid_repos[0] if valid_repos else None)
        if term_cwd and term_cwd.startswith("terminal://"):
            term_cwd = term_cwd.replace("terminal://", "")
        term_score = 100 if (term_cwd and os.path.isdir(term_cwd)) else 0
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

        return {
            "workspace_id": ws.workspace_id,
            "title": ws.title,
            "domain_type": ws.domain_type,
            "story_narrative": ws.understanding.story_narrative,
            "explainability_reasons": ws.understanding.explainability_reasons,
            "confidence_score": ws.understanding.confidence.score,
            "confidence_breakdown": confidence_breakdown,
            "last_restore_outcomes": last_outcomes,
            "current_goal": ws.understanding.momentum.goal,
            "current_blocker": ws.understanding.momentum.current_blocker,
            "next_action": ws.understanding.momentum.next_action,
            "associated_resources": list(ws.reality.resources.keys())[:10],
            "resource_summaries": resource_summaries,
            "terminal_cwd": term_cwd,
            "recent_command": recent_command,
            "options": {
                "restore_vscode": True,
                "restore_terminal": True,
                "restore_chrome": False,
                "restore_editors": True,
                "restore_browsers": False,
                "restore_documentation": False
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

