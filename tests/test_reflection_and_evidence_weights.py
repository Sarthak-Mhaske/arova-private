import pytest
from arova.core.cognition.belief import BeliefRuntime
from arova.core.cognition.reflection import ReflectionRuntime
from arova.core.cognition.workspace import CognitiveWorkspace
from arova.core.cognition.workspace_manager import WorkspaceManager

def test_inspectable_evidence_weights():
    """
    Verifies that BeliefRuntime exposes inspectable evidence weight deltas for each hypothesis.
    """
    belief_rt = BeliefRuntime()
    wm = {
        "current_repository": "/home/sarthak/arova",
        "active_files": [{"path": "/home/sarthak/arova/arova/core/memory/storage.py"}],
        "terminal_evidence": [{"command": "pytest tests/test_sqlite.py", "exit_code": 1}],
        "unresolved_errors": ["TransactionDeadlockError: database is locked"],
        "browser_evidence": []
    }
    state = belief_rt.update_evidence(wm)
    assert state.active_belief is not None
    assert len(state.active_belief.evidence_weights) >= 1
    assert "weight" in state.active_belief.evidence_weights[0]
    assert "evidence" in state.active_belief.evidence_weights[0]

def test_reflection_runtime_and_explain_my_day():
    """
    Verifies that ReflectionRuntime conducts periodic background reflection cycles
    and synthesizes human-grade daily work summaries ('Explain my day').
    """
    wm_mgr = WorkspaceManager()
    ws = CognitiveWorkspace("arova_dev", "Arova Development")
    ws.understanding.momentum.goal = "Eliminating transaction deadlock in storage.py"
    ws.understanding.decisions = ["Reordered lock acquisition sequence"]
    wm_mgr._workspaces["arova_dev"] = ws
    wm_mgr.set_active_workspace("arova_dev")

    reflection_rt = ReflectionRuntime(workspace_manager=wm_mgr)
    summary = reflection_rt.reflect_on_session(force=True)

    assert summary.session_title == "Reflection Summary: Arova Development"
    assert "Eliminating transaction deadlock" in summary.workday_narrative

    day_summary = reflection_rt.synthesize_explain_my_day()
    assert "Arova Development" in day_summary
    assert "Reordered lock acquisition sequence" in day_summary
