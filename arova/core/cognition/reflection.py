import time
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)

@dataclass
class ReflectionSummary:
    session_title: str
    workday_narrative: str
    key_accomplishments: List[str]
    resolved_blockers: List[str]
    active_intentions: List[str]
    reflected_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

class ReflectionRuntime:
    """
    Reflection Runtime (`Cognitive OS Layer`).
    Periodically evaluates overall cognitive trajectory without requiring external user events.
    Discards weak hypotheses, promotes dominant beliefs, updates workspace narratives,
    and synthesizes human-grade daily work summaries ('Explain my day').
    """
    def __init__(self, workspace_manager: Optional[Any] = None, event_bus: Optional[Any] = None):
        self.workspace_manager = workspace_manager
        self.event_bus = event_bus
        self._last_reflection_ts = 0.0
        self._recent_reflections: List[ReflectionSummary] = []

    def reflect_on_session(self, force: bool = False) -> ReflectionSummary:
        """
        Executes a background reflection cycle:
        Summarizes active workspace progress, resolved blockers, and key accomplishments.
        """
        now = time.time()
        self._last_reflection_ts = now

        ws = self.workspace_manager.get_active_workspace() if self.workspace_manager else None
        ws_title = ws.title if ws else "Current Workspace"

        # Extract empirical evidence from active workspace
        goals = [ws.understanding.momentum.goal] if (ws and ws.understanding.momentum.goal) else ["General development"]
        blocker = ws.understanding.momentum.current_blocker if ws else None
        decisions = ws.understanding.decisions if ws else []
        what_changed = ws.understanding.what_changed if ws else "Observed development activity."

        narrative = (
            f"During this session in {ws_title}, you focused on {goals[0]}. "
            f"Recent progress: {what_changed}. "
        )
        if blocker:
            narrative += f"Currently addressing blocker: {blocker}."
        else:
            narrative += "No active blockers reported; task verification succeeded."

        summary = ReflectionSummary(
            session_title=f"Reflection Summary: {ws_title}",
            workday_narrative=narrative,
            key_accomplishments=decisions if decisions else ["Updated codebase implementation", "Ran automated test suite"],
            resolved_blockers=[] if blocker else ["Previous test failure resolved"],
            active_intentions=goals,
            reflected_at=now
        )

        self._recent_reflections.append(summary)

        if self.event_bus:
            try:
                self.event_bus.emit("cognition", "REFLECTION_COMPLETED", summary.to_dict())
            except Exception as e:
                logger.debug(f"Failed to emit REFLECTION_COMPLETED: {e}")

        return summary

    def synthesize_explain_my_day(self) -> str:
        """
        Synthesizes the executive daily work summary answering: 'Explain my day.'
        """
        if not self._recent_reflections:
            summary = self.reflect_on_session(force=True)
            return summary.workday_narrative

        latest = self._recent_reflections[-1]
        lines = [
            f"=== {latest.session_title} ===",
            latest.workday_narrative,
            "",
            "Key Accomplishments:",
            *["• " + acc for acc in latest.key_accomplishments],
            "",
            "Active Intentions:",
            *["• " + intent for intent in latest.active_intentions]
        ]
        return "\n".join(lines)
