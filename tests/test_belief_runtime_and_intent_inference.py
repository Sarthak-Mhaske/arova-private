import pytest
from arova.core.cognition.belief import BeliefRuntime, BeliefState

def test_belief_runtime_competing_hypotheses_shift():
    """
    Belief Runtime Audit:
    Proves that BeliefRuntime maintains competing hypotheses about user intent,
    normalizes probability distributions, and shifts top beliefs as new evidence arrives.
    """
    belief_rt = BeliefRuntime()

    # Step 1: Ingest feature development evidence
    wm_feature = {
        "current_repository": "/home/sarthak/arova",
        "active_files": [{"path": "/home/sarthak/arova/arova/core/memory/storage.py"}],
        "terminal_evidence": [],
        "unresolved_errors": [],
        "browser_evidence": []
    }
    state1 = belief_rt.update_evidence(wm_feature)
    assert state1.active_belief is not None
    assert "Implementing feature logic in storage.py" in state1.active_belief.title
    assert state1.active_belief.probability > 0.5

    # Step 2: Ingest terminal command failure -> Belief shifts to Error Elimination
    wm_error = {
        "current_repository": "/home/sarthak/arova",
        "active_files": [{"path": "/home/sarthak/arova/arova/core/memory/storage.py"}],
        "terminal_evidence": [{"command": "pytest tests/test_sqlite_persistence.py", "exit_code": 1}],
        "unresolved_errors": ["TransactionDeadlockError: database is locked"],
        "browser_evidence": []
    }
    state2 = belief_rt.update_evidence(wm_error)
    
    assert "Eliminating error" in state2.active_belief.title
    assert len(state2.competing_hypotheses) >= 1
    assert "Implementing feature logic" in state2.competing_hypotheses[0].title
    assert state2.uncertainty_index <= 0.85

    # Step 3: Synthesize human-grade objective explanation
    explanation = belief_rt.synthesize_objective_explanation()
    assert "Primary objective: Eliminating error" in explanation
    assert "Competing hypothesis" in explanation
