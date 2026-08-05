import time
import logging
import asyncio
from typing import Dict, Any, Optional
from arova.core.memory.working_memory import WorkingMemoryState

logger = logging.getLogger(__name__)

class ReasoningRuntime:
    """
    Continuous Reasoning Runtime (`HYP-07`).
    Inverts the old reactive 'User asks -> LLM thinks' model into proactive continuous inference.
    Listens to WorkingMemory shifts and updates Workspace Graph understanding proactively.
    """
    def __init__(self, event_bus: Optional[Any] = None, workspace_manager: Optional[Any] = None, model_runtime: Optional[Any] = None):
        self.event_bus = event_bus
        self.workspace_manager = workspace_manager
        self.model_runtime = model_runtime
        self._is_reasoning = False
        self._last_reasoning_ts = 0.0

        if self.event_bus:
            self.event_bus.subscribe("cognition", "WORKING_MEMORY_CHANGED", self._on_working_memory_changed)

    def _on_working_memory_changed(self, payload: Any) -> None:
        """Triggered when WorkingMemory shifts meaningfully."""
        if isinstance(payload, dict):
            # Run continuous reasoning asynchronously without blocking capture
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self.evaluate_working_memory_shift(payload))
            except RuntimeError:
                # Synchronous fallback if outside running loop
                asyncio.run(self.evaluate_working_memory_shift(payload))

    async def evaluate_working_memory_shift(self, working_memory_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluates the shifted working memory state, derives current blocker and next action,
        and updates the active workspace understanding (`HYP-04` Deep Context & `HYP-07`).
        """
        if self._is_reasoning:
            return {}
            
        self._is_reasoning = True
        try:
            now = time.time()
            self._last_reasoning_ts = now
            
            errors = working_memory_dict.get("unresolved_errors", [])
            active_files = working_memory_dict.get("active_files", [])
            terminal = working_memory_dict.get("terminal_evidence", [])
            repo = working_memory_dict.get("current_repository")
            
            # Derive honest empirical reasoning state & confidence score
            inferred_blocker: Optional[str] = None
            inferred_next: Optional[str] = None
            inferred_goal: Optional[str] = None
            confidence: float = 0.5

            total_events = len(active_files) + len(terminal) + len(errors)
            confidence = min(0.95, max(0.2, 0.4 + (total_events * 0.03)))

            if errors:
                latest_err = errors[-1]
                inferred_blocker = f"Unresolved diagnostic or error: {latest_err[:120]}"
                inferred_next = "Investigate error output and fix failing test or syntax issue."
                inferred_goal = f"Fixing runtime error in {repo.split('/')[-1] if repo else 'project'}"
                confidence = min(0.95, confidence + 0.15)
            elif terminal and terminal[-1].get("exit_code") not in (None, 0):
                cmd = terminal[-1].get("command", "")
                inferred_blocker = f"Command failed (exit code {terminal[-1].get('exit_code')}): {cmd}"
                inferred_next = f"Inspect failure logs for `{cmd}` and correct parameters or code."
                inferred_goal = f"Resolving failing command `{cmd}`"
                confidence = min(0.95, confidence + 0.1)
            elif active_files:
                top_file = active_files[-1].get("path", "").split("/")[-1]
                inferred_next = f"Continue modifying or verifying `{top_file}` in `{repo.split('/')[-1] if repo else 'workspace'}`."
                inferred_goal = f"Developing and verifying `{top_file}`"
                if not inferred_blocker:
                    inferred_blocker = None
            else:
                inferred_next = "Awaiting activity or terminal commands to establish objective."
                inferred_goal = "Observing workspace activity"
            trigger_type = working_memory_dict.get("cognitive_trigger_type", "WORKING_SET_EXPANSION")
            empirical_evidence = working_memory_dict.get("empirical_evidence") or {
                "active_files_count": len(active_files),
                "terminal_failures_count": sum(1 for t in terminal if t.get("exit_code") not in (None, 0)),
                "unresolved_errors_count": len(errors),
                "attention_mode": working_memory_dict.get("attention_mode", "deep_work")
            }

            belief_state = None
            if hasattr(self, 'belief_runtime') and self.belief_runtime:
                bs = self.belief_runtime.update_evidence(working_memory_dict)
                belief_state = bs.to_dict()
                if bs.active_belief:
                    inferred_goal = bs.active_belief.title

            reasoning_outcome = {
                "inferred_goal": inferred_goal,
                "inferred_blocker": inferred_blocker,
                "inferred_next_action": inferred_next,
                "cognitive_trigger_type": trigger_type,
                "empirical_evidence": empirical_evidence,
                "belief_state": belief_state,
                "confidence": round(confidence, 2),
                "timestamp": now
            }
            
            # Update WorkspaceManager (`HYP-04` Deep Context update)
            if self.workspace_manager:
                ws = self.workspace_manager.get_active_workspace()
                if ws:
                    if repo and repo not in ws.interpretation.repo_paths:
                        ws.interpretation.repo_paths.append(repo)
                    if inferred_goal:
                        ws.understanding.momentum.goal = inferred_goal
                    ws.understanding.momentum.current_blocker = inferred_blocker
                    if inferred_next:
                        ws.understanding.momentum.next_action = inferred_next
                    ws.understanding.what_changed = f"Continuous reasoning update across {len(active_files)} observed files (Confidence: {round(confidence, 2)})."
                    
            if self.event_bus:
                try:
                    self.event_bus.emit("reasoning", "REASONING_STEP_COMPLETED", reasoning_outcome)
                except Exception as e:
                    logger.warning(f"Failed to emit REASONING_STEP_COMPLETED: {e}")
                    
            return reasoning_outcome
            
        finally:
            self._is_reasoning = False
