import pytest
import time
from arova.core.cognition.workspace_manager import WorkspaceManager
from arova.core.cognition.workspace import CognitiveWorkspace
from arova.core.events import RuntimeEventBus as EventBus


def test_universal_stuckness_developer_error_loop():
    bus = EventBus()
    emitted_surfacing = []
    
    def on_surfacing(event):
        emitted_surfacing.append(event.data if hasattr(event, "data") else event)
        
    bus.subscribe("cognition", "surfacing_push", on_surfacing)
    wm = WorkspaceManager(event_bus=bus)
    
    # Simulate repeated file visits with error signature -> naturally emerges workspace (`P0-2`)
    for i in range(5):
        wm.ingest_fragment({
            "source_identity": "/home/sarthak/arova/arova/core/memory/memory_policy.py",
            "provider_id": "WindowObserverProvider",
            "activity_summary": f"Repeated test failure: AssertionError in memory_policy test run {i}"
        })
        
    time.sleep(0.15)
    active = wm.get_active_workspace()
    assert active is not None
    assert active.interpretation.stuckness_score >= 75.0
    assert len(emitted_surfacing) == 1
    surfacing = emitted_surfacing[0]
    assert "<strong>You're still solving the issue around" in surfacing["paragraphs"][0]
    assert "memory_policy.py" in surfacing["paragraphs"][0]
    assert len(surfacing["actions"]) == 3
    assert surfacing["actions"][0]["label"] == "Trace the current flow"


def test_universal_stuckness_writer_rewrite_loop():
    wm = WorkspaceManager()
    ws = CognitiveWorkspace(title="Novel Chapter 4", domain_type="writing")
    wm._workspaces[ws.workspace_id] = ws
    wm._active_workspace_id = ws.workspace_id
    active = wm.get_active_workspace()
    
    # Simulate repeated visits to same paragraph with rewrite loops
    for i in range(6):
        wm.ingest_fragment({
            "source_identity": "/home/sarthak/Documents/Chapter4.docx",
            "provider_id": "DocumentObserver",
            "activity_summary": "Rewrite attempt on opening paragraph without progress"
        })
        
    assert active.interpretation.stuckness_score >= 75.0
    assert any("Revisited resource" in r for r in active.interpretation.stuckness_reasons)


def test_time_to_productivity_telemetry():
    bus = EventBus()
    kpi_events = []
    saved_events = []
    
    def on_kpi(event):
        kpi_events.append(event.data if hasattr(event, "data") else event)
        
    def on_saved(event):
        saved_events.append(event.data if hasattr(event, "data") else event)
        
    bus.subscribe("telemetry", "time_to_productivity", on_kpi)
    bus.subscribe("telemetry", "context_recovery_saved", on_saved)
    wm = WorkspaceManager(event_bus=bus)
    ws = CognitiveWorkspace(title="KPI Verification WS", domain_type="engineering")
    wm._workspaces[ws.workspace_id] = ws
    wm._active_workspace_id = ws.workspace_id
    active = wm.get_active_workspace()
    
    # 1. User clicks resume
    wm.mark_resumed(active.workspace_id)
    time.sleep(0.05)
    
    # 2. User starts meaningful work (fragment reported)
    wm.ingest_fragment({
        "source_identity": "/home/sarthak/arova/arova/core/runtime.py",
        "provider_id": "WindowObserverProvider",
        "activity_summary": "Editing runtime initialization code"
    })
    
    time.sleep(0.15)
    assert len(kpi_events) == 1
    assert kpi_events[0]["workspace_id"] == active.workspace_id
    assert kpi_events[0]["seconds"] >= 0.05
    assert len(saved_events) == 1
    assert saved_events[0]["saved_seconds"] > 100.0
    assert saved_events[0]["saved_minutes"] >= 1.9
