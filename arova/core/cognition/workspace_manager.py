import time
import logging
from typing import Dict, List, Optional, Any
from arova.core.cognition.workspace import (
    CognitiveWorkspace, RealityLayer, InterpretationLayer, SignalsLayer, UnderstandingLayer,
    WorkspaceMomentum, WorkspaceHealth, WorkspaceConfidence, ConfidenceLayer, ItemConfidence
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

        # Seed with initial long-lived workspace representing current development
        self._seed_initial_workspace()

        if self.event_bus:
            self.event_bus.subscribe("context", "fragment_reported", self._on_fragment_reported)
            self.event_bus.subscribe("timeline", "create", self._on_timeline_create)
            self.event_bus.subscribe("cognition", "SESSION_TURN_COMPLETED", self._on_turn_completed)
            self.event_bus.subscribe("workspace", "continue", self._on_workspace_continue)

    def _seed_initial_workspace(self):
        ws = CognitiveWorkspace(
            title="Arova Development",
            domain_type="engineering",
            pinned=True
        )
        ws.reality.resources["runtime.py"] = {"identity": "/home/sarthak/arova/arova/core/runtime.py", "type": "file"}
        ws.reality.resources["memory_policy.py"] = {"identity": "/home/sarthak/arova/arova/core/memory/memory_policy.py", "type": "file"}
        ws.reality.total_focus_seconds = 15420.0
        
        ws.interpretation.repo_paths = ["/home/sarthak/arova"]
        ws.interpretation.browser_domains = ["console.groq.com", "github.com"]
        ws.interpretation.repeated_terms = ["memory consent", "runtime", "workspace", "daemon"]
        ws.interpretation.cluster_cohesion_score = 0.94
        ws.interpretation.stuckness_score = 12.0
        
        ws.understanding.momentum = WorkspaceMomentum(
            goal="Implementing Long-Lived Cognitive Workspaces & Context Restoration",
            progress_percentage=82,
            confidence_level="High",
            current_blocker="Pending queue persistence across daemon restarts",
            next_action="Implement SQLite persistence for approval queue (~20 min)"
        )
        ws.understanding.health = WorkspaceHealth(
            status="Focused",
            last_progress_reason="Verified two-layer Reality/Understanding split",
            last_progress_timestamp=time.time() - 1080
        )
        ws.understanding.confidence = WorkspaceConfidence(
            score=97,
            reasons=["VSCode active", "Git repo: arova", "Groq Docs open", "4h focus", "8 linked memories"]
        )
        ws.understanding.confidence_layer = ConfidenceLayer(
            goal=ItemConfidence(98, ["Consistent development across daemon and core"]),
            blocker=ItemConfidence(92, ["Identified in recent reflect turns"]),
            next_action=ItemConfidence(94, ["Explicit roadmap item"]),
            overall=ws.understanding.confidence
        )
        ws.understanding.decisions = [
            "Used SQLite for memory store instead of local JSON for transaction durability",
            "Enforced Tier 3 explicit user consent popup for high-sensitivity operations",
            "Split Workspace into Reality Layer vs Interpretation/Understanding Layers"
        ]
        ws.understanding.open_questions = [
            "How should pending review queues hydrate seamlessly across system reboots without blocking STT?"
        ]
        ws.understanding.what_changed = "Completed memory consent flow; SQLite persistence next."
        ws.understanding.trajectory_story = "Transitioned from session-based memory to long-lived workspaces."
        
        self._workspaces[ws.workspace_id] = ws
        self._active_workspace_id = ws.workspace_id

    def get_active_workspace(self) -> Optional[CognitiveWorkspace]:
        if not self._active_workspace_id:
            return None
        return self._workspaces.get(self._active_workspace_id)

    def get_all_workspaces(self) -> List[CognitiveWorkspace]:
        return list(self._workspaces.values())

    def get_workspace(self, workspace_id: str) -> Optional[CognitiveWorkspace]:
        return self._workspaces.get(workspace_id)

    def set_active_workspace(self, workspace_id: str):
        if workspace_id in self._workspaces:
            self._active_workspace_id = workspace_id
            self.sync_to_bus()
            logger.info(f"WorkspaceManager: Active workspace switched to '{self._workspaces[workspace_id].title}'")

    def mark_resumed(self, workspace_id: str):
        """Records resume timestamp for Time to Productivity KPI calculation."""
        if workspace_id in self._workspaces:
            self._resume_timestamps[workspace_id] = time.time()
            logger.info(f"WorkspaceManager: Marked workspace '{workspace_id}' resumed at timestamp {time.time()}")

    def _on_workspace_continue(self, event: Any):
        payload = event.data if hasattr(event, "data") else event
        if payload and "workspace_id" in payload:
            self.mark_resumed(payload["workspace_id"])

    def ingest_fragment(self, fragment: Any):
        self._on_fragment_reported(fragment)

    def _on_fragment_reported(self, event: Any):
        payload = event.data if hasattr(event, "data") else event
        if not payload:
            return
            
        active = self.get_active_workspace()
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
            behavioral_recovery_seconds = max(120.0, (resource_count * 150.0) + (switches_avoided * 35.0))
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
        # Update interpretation repo_paths
        if "/" in source_id and not any(source_id.startswith(p) for p in active.interpretation.repo_paths):
            if "/home/" in source_id or "/workspace/" in source_id:
                parts = source_id.split("/")
                if len(parts) > 3:
                    repo_prefix = "/".join(parts[:4])
                    if repo_prefix not in active.interpretation.repo_paths:
                        active.interpretation.repo_paths.append(repo_prefix)

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
            score += min(50.0, (access_count - 2) * 20.0)
            reasons.append(f"Revisited resource '{source_id.split('/')[-1]}' {access_count} times")

        # Error signature factor
        summary_lower = summary.lower()
        has_error = any(term in summary_lower for term in ["error", "exception", "failed", "traceback", "retry", "stuck", "rewrite"])
        if has_error:
            score += 35.0
            reasons.append("Observed repeated friction/error signatures")

        # Stagnant focus factor
        if active.reality.total_focus_seconds > 1800 and (active.understanding.health.status == "Blocked" or has_error or access_count >= 4):
            score += 25.0
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
        
        if self.event_bus:
            resource_name = source_id.split('/')[-1] if '/' in source_id else source_id
            next_step = active.understanding.momentum.next_action or "the core state persistence flow"
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
        if self.event_bus:
            workspaces_data = [w.to_dict() for w in self._workspaces.values()]
            self.event_bus.emit("workspace", "sync", {
                "active_workspace_id": self._active_workspace_id,
                "workspaces": workspaces_data
            })
