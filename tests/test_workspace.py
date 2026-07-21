import pytest
import time
from arova.core.cognition.workspace import (
    CognitiveWorkspace, RealityLayer, InterpretationLayer, SignalsLayer, UnderstandingLayer,
    WorkspaceMomentum, WorkspaceHealth, WorkspaceConfidence, ConfidenceLayer, ItemConfidence
)
from arova.core.cognition.workspace_manager import WorkspaceManager
from arova.core.persistence.schema import RuntimeSnapshot
from arova.core.persistence.store import RuntimeStore


def test_workspace_seven_questions_golden_rule():
    ws = CognitiveWorkspace(title="Arova Development", domain_type="engineering")
    ws.understanding.momentum.goal = "Build effortless context restoration across long-lived workspaces"
    ws.understanding.momentum.progress_percentage = 82
    ws.understanding.momentum.current_blocker = "Pending queue persistence"
    ws.understanding.momentum.next_action = "Implement SQLite persistence"
    ws.understanding.health.status = "Focused"
    ws.understanding.confidence.score = 97
    ws.understanding.confidence.reasons = ["VSCode active", "Git repo: arova"]
    ws.understanding.what_changed = "Resolved memory consent popup issues."

    questions = ws.get_seven_questions()
    assert questions["what_am_i_doing"] == "Arova Development"
    assert questions["why_am_i_doing_it"] == "Build effortless context restoration across long-lived workspaces"
    assert "82%" in questions["how_far_am_i"]
    assert questions["whats_blocking_me"] == "Pending queue persistence"
    assert questions["what_should_i_do_next"] == "Implement SQLite persistence"
    assert "Confidence is 97%" in questions["why_do_you_believe_that"]
    assert questions["what_changed"] == "Resolved memory consent popup issues."

    # Verify humble behavior when overall confidence is low (< 85%)
    ws.understanding.confidence.score = 70
    ws.understanding.confidence_layer.goal.score = 75
    humble_q = ws.get_seven_questions()
    assert "I think the goal is:" in humble_q["why_am_i_doing_it"]


def test_workspace_trajectory_story():
    ws = CognitiveWorkspace(title="Tax Filing", domain_type="finance")
    ws.understanding.momentum.goal = "Complete Q4 returns"
    ws.understanding.momentum.progress_percentage = 60
    ws.understanding.what_changed = "Found deduction receipts"
    ws.understanding.trajectory_story = "Progressing from raw docs to draft return."
    
    story = ws.get_trajectory_story()
    assert story["title"] == "Tax Filing"
    assert story["progress_story"] == "60% complete"
    assert story["what_changed"] == "Found deduction receipts"


def test_workspace_serialization():
    ws = CognitiveWorkspace(title="Tax Filing", domain_type="finance", pinned=True)
    ws.reality.resources["Quarterly_Forecast.xlsx"] = {"type": "file", "identity": "/home/user/Quarterly_Forecast.xlsx"}
    ws.interpretation.repeated_terms = ["tax", "deductions", "q4"]
    ws.interpretation.stuckness_score = 15.0
    ws.understanding.momentum.progress_percentage = 45

    data = ws.to_dict()
    assert data["title"] == "Tax Filing"
    assert data["reality"]["resources"]["Quarterly_Forecast.xlsx"]["type"] == "file"
    assert data["interpretation"]["stuckness_score"] == 15.0
    assert data["understanding"]["momentum"]["progress_percentage"] == 45

    rehydrated = CognitiveWorkspace.from_dict(data)
    assert rehydrated.title == "Tax Filing"
    assert rehydrated.reality.resources["Quarterly_Forecast.xlsx"]["type"] == "file"
    assert rehydrated.interpretation.repeated_terms == ["tax", "deductions", "q4"]
    assert rehydrated.interpretation.stuckness_score == 15.0
    assert rehydrated.understanding.momentum.progress_percentage == 45


def test_workspace_manager_initialization_and_emergence():
    wm = WorkspaceManager()
    active = wm.get_active_workspace()
    assert active is None, "Clean boot must start with 0 workspaces (P0-2)"

    # Simulate fragment ingestion -> organic emergence
    wm.ingest_fragment({
        "source_identity": "/home/sarthak/arova/arova/core/cognition/workspace.py",
        "provider_id": "WindowObserverProvider",
        "activity_summary": "Editing workspace classes"
    })
    
    active = wm.get_active_workspace()
    assert active is not None
    assert active.title == "Arova Architecture & Development"
    assert active.domain_type == "engineering"
    assert "/home/sarthak/arova/arova/core/cognition/workspace.py" in active.reality.resources
    assert active.reality.last_accessed_at > 0


def test_store_safe_save_with_dicts_or_snapshots(tmp_path):
    store = RuntimeStore()
    store.storage_dir = tmp_path
    
    snapshot = RuntimeSnapshot()
    snapshot.hot_state.active_workspace_id = "ws_test_123"
    snapshot.hot_state.workspaces = {
        "ws_test_123": CognitiveWorkspace(title="Test WS").to_dict()
    }
    
    # Save should not raise 'dict' object has no attribute 'to_dict'
    store.save(snapshot)
    
    # Also verify saving a dictionary directly doesn't crash
    store.save(snapshot.to_dict())


def test_deterministic_crash_recovery(tmp_path):
    """P0-6 & P0-9: Verify strict v4 hydration and save() -> crash -> hydrate() idempotency."""
    store = RuntimeStore()
    store.storage_dir = tmp_path
    
    wm = WorkspaceManager()
    ws = CognitiveWorkspace(title="Recovery Verification WS", domain_type="engineering")
    ws.understanding.confidence_layer.repository.score = 100
    ws.understanding.confidence_layer.resources.score = 68
    wm._workspaces[ws.workspace_id] = ws
    wm._active_workspace_id = ws.workspace_id
    
    snapshot = RuntimeSnapshot()
    snapshot.hot_state.active_workspace_id = ws.workspace_id
    snapshot.hot_state.workspaces = {ws.workspace_id: ws.to_dict()}
    snapshot.hot_state.recent_turns = [{"role": "user", "content": "hello arova"}]
    
    # Save snapshot transactionally
    store.save(snapshot)
    
    # Simulate process crash & reboot with new store pointed to tmp_path
    rebooted_store = RuntimeStore()
    rebooted_store.storage_dir = tmp_path
    hydrated_snap = rebooted_store.hydrate()
    
    assert hydrated_snap.schema_version == 4
    assert hydrated_snap.hot_state.active_workspace_id == ws.workspace_id
    assert ws.workspace_id in hydrated_snap.hot_state.workspaces
    
    hydrated_ws = CognitiveWorkspace.from_dict(hydrated_snap.hot_state.workspaces[ws.workspace_id])
    assert hydrated_ws.title == "Recovery Verification WS"
    assert hydrated_ws.understanding.confidence_layer.repository.score == 100
    assert hydrated_ws.understanding.confidence_layer.resources.score == 68
    assert hydrated_snap.hot_state.recent_turns == [{"role": "user", "content": "hello arova"}]

def test_workspace_delta_changes_serialization():
    ws = CognitiveWorkspace(workspace_id="ws_delta", title="Delta Test WS")
    ws.understanding.delta_changes = [
        "Tests now pass",
        "Switched from Redis to SQLite",
        "Remaining blocker is daemon restart persistence"
    ]
    data = ws.to_dict()
    assert data["understanding"]["delta_changes"] == [
        "Tests now pass",
        "Switched from Redis to SQLite",
        "Remaining blocker is daemon restart persistence"
    ]
    hydrated = CognitiveWorkspace.from_dict(data)
    assert hydrated.understanding.delta_changes == [
        "Tests now pass",
        "Switched from Redis to SQLite",
        "Remaining blocker is daemon restart persistence"
    ]
