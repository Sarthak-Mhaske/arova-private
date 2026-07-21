import pytest
from arova.core.capture.engine import ActivityCaptureEngine, CanonicalActivityEvent
from arova.core.capture.plugins.base import PluginRegistry, VSCodePlugin, TerminalPlugin, BrowserPlugin
from arova.core.cognition.workspace_manager import WorkspaceManager

class MockEventBus:
    def __init__(self):
        self.emitted = []
    def emit(self, channel, event, payload):
        self.emitted.append((channel, event, payload))

def test_canonical_activity_event_serialization():
    event = CanonicalActivityEvent(
        event_id="test-uuid-1",
        event_type="editor_change",
        timestamp=1600000000.0,
        source_plugin="vscode",
        normalized_payload={"resource_path": "/path/to/app.py", "line_number": 42},
        device_id="dev-1",
        user_id="user-1",
        sequence=15,
        signature="hash-sig-123"
    )
    data = event.to_dict()
    assert data["event_id"] == "test-uuid-1"
    assert data["sequence"] == 15
    assert data["signature"] == "hash-sig-123"
    
    recovered = CanonicalActivityEvent.from_dict(data)
    assert recovered.event_id == event.event_id
    assert recovered.normalized_payload["line_number"] == 42


def test_activity_capture_engine_ingest_and_subscribe():
    bus = MockEventBus()
    engine = ActivityCaptureEngine(event_bus=bus, device_id="my-laptop")
    
    received = []
    engine.subscribe(lambda e: received.append(e))
    
    event = engine.ingest_event(
        event_type="os_focus",
        source_plugin="os",
        normalized_payload={"title": "VS Code - main.py", "summary": "Active focus on main.py"}
    )
    
    assert event.sequence == 1
    assert event.device_id == "my-laptop"
    assert len(event.signature) == 64  # SHA-256 hex string
    
    assert len(received) == 1
    assert received[0].event_id == event.event_id
    assert len(bus.emitted) == 1
    assert bus.emitted[0][0] == "capture"
    assert bus.emitted[0][1] == "EVENT_INGESTED"


def test_tier1_plugins_integration():
    bus = MockEventBus()
    engine = ActivityCaptureEngine(event_bus=bus)
    registry = PluginRegistry()
    
    vscode = VSCodePlugin()
    terminal = TerminalPlugin()
    browser = BrowserPlugin()
    
    registry.register(vscode, engine=engine)
    registry.register(terminal, engine=engine)
    registry.register(browser, engine=engine)
    
    registry.start_all()
    
    # Report VS Code event
    e1 = vscode.report_editor_event(
        file_path="/home/sarthak/arova/arova/runtime.py",
        line_number=120,
        repository="/home/sarthak/arova",
        summary="Editing runtime.py line 120"
    )
    assert e1 is not None
    assert e1.event_type == "editor_change"
    assert e1.normalized_payload["resource_path"] == "/home/sarthak/arova/arova/runtime.py"
    assert e1.normalized_payload["kind"] == "File"
    
    # Report Terminal event
    e2 = terminal.report_terminal_event(
        cwd="/home/sarthak/arova",
        command="pytest arova/tests/",
        exit_code=1,
        output_snippet="ModuleNotFoundError: No module named 'aiohttp'"
    )
    assert e2 is not None
    assert e2.event_type == "terminal_exec"
    assert e2.normalized_payload["is_error"] is True
    assert e2.normalized_payload["kind"] == "Terminal"
    
    # Report Browser event
    e3 = browser.report_browser_event(
        url="https://docs.python.org/3/library/asyncio.html",
        title="asyncio — Asynchronous I/O"
    )
    assert e3 is not None
    assert e3.event_type == "browser_tab"
    assert e3.normalized_payload["domain"] == "docs.python.org"
    assert e3.normalized_payload["kind"] == "BrowserTab"
    
    assert len(engine.get_recent_events()) == 3
    registry.stop_all()


def test_capture_engine_forwarding_to_workspace_manager():
    wm = WorkspaceManager()
    engine = ActivityCaptureEngine()
    engine.workspace_manager = wm
    
    engine.ingest_event(
        event_type="editor_change",
        source_plugin="vscode",
        normalized_payload={
            "title": "supervisor.py - Arova Architecture & Development",
            "summary": "Editing supervisor daemon loop"
        }
    )
    
    active = wm.get_active_workspace()
    assert active is not None
    assert "Arova" in active.title
