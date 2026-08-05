import time
import pytest
from arova.core.events import RuntimeEventBus
from arova.core.cognition.workspace_manager import WorkspaceManager

def test_create_and_accept_completed_work():
    bus = RuntimeEventBus()
    wm = WorkspaceManager(event_bus=bus)
    
    events_emitted = []
    def on_event(e):
        events_emitted.append(e)
        
    bus.subscribe("telemetry", "net_work_removed", on_event)
    
    # Create completed work
    work = wm.create_completed_work(
        workflow="Fix",
        headline="Reproduced deadlock & applied patch",
        verification_proof="4/4 pytest assertions passed",
        nwr_minutes=25.0
    )
    
    assert work["verified"] is True
    assert work["headline"] == "Reproduced deadlock & applied patch"
    assert work["status"] == "Completed"
    
    # Accept work
    wm._on_work_accept({"work_id": work["work_id"]})
    time.sleep(0.05)
    
    assert work["status"] == "Accepted"
    assert len(events_emitted) == 1
    assert events_emitted[0].data["nwr_minutes"] == 25.0
    assert events_emitted[0].data["action"] == "accepted"

def test_failed_verification_completed_work():
    bus = RuntimeEventBus()
    wm = WorkspaceManager(event_bus=bus)
    
    work = wm.create_completed_work(
        workflow="Fix",
        headline="Attempted deadlock resolution",
        verification_proof="",
        status="Failed Verification",
        failure_reason="Thread 4 deadlocked during stress loop",
        nwr_minutes=0.0
    )
    
    assert work["verified"] is False
    assert work["status"] == "Failed Verification"
    assert work["failure_reason"] == "Thread 4 deadlocked during stress loop"

def test_reject_completed_work():
    bus = RuntimeEventBus()
    wm = WorkspaceManager(event_bus=bus)
    
    events_emitted = []
    def on_event(e):
        events_emitted.append(e)
        
    bus.subscribe("telemetry", "net_work_removed", on_event)
    
    work = wm.create_completed_work(
        workflow="Summarize",
        headline="Summarized 87-page architecture spec",
        verification_proof="Verified against spec index",
        nwr_minutes=15.0
    )
    
    wm._on_work_reject({"work_id": work["work_id"]})
    time.sleep(0.05)
    
    assert work["status"] == "Rejected"
    assert len(events_emitted) == 1
    assert events_emitted[0].data["nwr_minutes"] == 0.0
    assert events_emitted[0].data["action"] == "rejected"
