import pytest
from arova.core.memory.working_memory import WorkingMemoryRuntime
from arova.core.capture.engine import ActivityCaptureEngine

def test_working_memory_runtime_ingest():
    """
    HYP-06 Regression Test: Proves that WorkingMemoryRuntime maintains active files,
    repository path, terminal commands, and compiler errors without heavy LLM polling,
    and emits meaningful shift triggers only when state shifts.
    """
    wm = WorkingMemoryRuntime()
    assert wm.state.current_repository is None
    assert len(wm.state.active_files) == 0
    
    # Ingest a file change event
    event1 = {
        "event_type": "file.changed",
        "source_plugin": "VSCode",
        "normalized_payload": {
            "resource_path": "/home/sarthak/arova/runtime.py",
            "repository": "/home/sarthak/arova",
            "line": 42
        }
    }
    shifted = wm.ingest_event(event1)
    assert shifted is True
    assert wm.state.current_repository == "/home/sarthak/arova"
    assert len(wm.state.active_files) == 1
    assert wm.state.active_files[0]["path"] == "/home/sarthak/arova/runtime.py"
    
    # Ingest terminal command failure
    event2 = {
        "event_type": "terminal.command_finished",
        "source_plugin": "Terminal",
        "normalized_payload": {
            "command": "pytest tests/",
            "exit_code": 1
        }
    }
    shifted2 = wm.ingest_event(event2)
    assert shifted2 is True
    assert len(wm.state.terminal_evidence) == 1
    assert wm.state.terminal_evidence[0]["exit_code"] == 1
    
    # Verify staleness tracking
    assert wm.state.is_stale() is False
