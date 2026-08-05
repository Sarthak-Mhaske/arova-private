import pytest
import asyncio
from arova.core.reasoning.runtime import ReasoningRuntime
from arova.core.cognition.workspace_manager import WorkspaceManager
from arova.core.cognition.workspace import CognitiveWorkspace

def test_continuous_reasoning_proactive_update():
    """
    HYP-07 Regression Test: Proves that when working memory shifts (e.g. command failure),
    ReasoningRuntime proactively derives blockers and next actions and updates Workspace Graph
    without waiting for user chat turns.
    """
    wm = WorkspaceManager()
    ws = CognitiveWorkspace("test_repo", "Test Repo")
    ws.interpretation.repo_paths = ["/home/sarthak/arova"]
    wm._workspaces["test_repo"] = ws
    wm._active_workspace_id = "test_repo"
    
    reasoner = ReasoningRuntime(workspace_manager=wm)
    
    # Simulate a working memory shift where terminal command exited with code 1
    wm_shift = {
        "current_repository": "/home/sarthak/arova",
        "active_files": [{"path": "/home/sarthak/arova/arova/core/capture/engine.py"}],
        "terminal_evidence": [{"command": "pytest tests/test_reality_hyp_03_vision.py", "exit_code": 1}],
        "unresolved_errors": []
    }
    
    outcome = asyncio.run(reasoner.evaluate_working_memory_shift(wm_shift))
    assert "Command failed (exit code 1)" in outcome.get("inferred_blocker", ""), f"HYP-07 REGRESSION: Did not infer blocker from failed command: {outcome}"
    assert "pytest tests/test_reality_hyp_03_vision.py" in outcome.get("inferred_next_action", ""), f"HYP-07 REGRESSION: Did not infer next action: {outcome}"
    
    # Verify that workspace momentum in Workspace Graph was proactively updated
    assert ws.understanding.momentum.current_blocker == outcome["inferred_blocker"]
    assert ws.understanding.momentum.next_action == outcome["inferred_next_action"]
