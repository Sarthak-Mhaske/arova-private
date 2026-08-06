import os
import time
import pytest
from unittest.mock import patch, MagicMock
from arova.core.events import RuntimeEventBus as EventBus
from arova.core.cognition.resource_registry import ResourceRegistry, ResourceItem
from arova.core.cognition.restoration_engine import EnvironmentRestorationEngine, RestoreOutcomeSummary, RestoreOutcomeItem
from arova.core.cognition.workspace_manager import WorkspaceManager, CognitiveWorkspace

def test_resource_registry_normalization_and_lookup():
    reg = ResourceRegistry()
    
    # 1. File registration
    f_item = reg.register_file("/home/sarthak/arova/runtime.py", repository="/home/sarthak/arova", line=112, col=15)
    assert f_item.resource_id == f"file://{os.path.abspath('/home/sarthak/arova/runtime.py')}"
    assert f_item.type == "file"
    assert f_item.metadata["line"] == 112
    assert "-g" in f_item.launch_command and ":112:15" in f_item.launch_command

    # 2. URL registration
    u_item = reg.register_url("https://sqlite.org/docs", title="SQLite Documentation")
    assert u_item.resource_id == "url://https://sqlite.org/docs"
    assert u_item.type == "url"
    assert u_item.display_name == "SQLite Documentation"

    # 3. Terminal registration
    t_item = reg.register_terminal("/home/sarthak/arova", recent_command="pytest tests/test_magic_resume.py")
    assert t_item.resource_id == f"terminal://{os.path.abspath('/home/sarthak/arova')}"
    assert t_item.type == "terminal"
    assert t_item.terminal == "pytest tests/test_magic_resume.py"

    # 4. Lookup and filter
    assert reg.get_resource(f_item.resource_id) == f_item
    assert len(reg.get_resources_by_type("file")) == 1
    assert len(reg.get_resources_by_type("url")) == 1

@patch("os.path.isdir")
@patch("os.path.exists")
@patch("subprocess.Popen")
@patch("shutil.which")
def test_environment_restoration_engine_vscode_and_terminal(mock_which, mock_popen, mock_exists, mock_isdir):
    mock_which.return_value = "/usr/bin/code"
    mock_exists.return_value = True
    mock_isdir.return_value = True
    
    reg = ResourceRegistry()
    reg.register_repository("/home/sarthak/arova", display_name="Arova Repo", exists=True)
    reg.register_file("/home/sarthak/arova/arova/runtime.py", line=45, col=10, exists=True)
    reg.register_terminal("/home/sarthak/arova", recent_command="npm run test", exists=True)

    engine = EnvironmentRestorationEngine(resource_registry=reg)
    
    # Dummy workspace
    ws = MagicMock()
    ws.workspace_id = "ws_test_magic"
    ws.title = "Arova Magic Resume"
    ws.reality.resources = {}

    # Restore with vscode and terminal enabled, chrome disabled
    outcome = engine.restore(ws, {
        "restore_vscode": True,
        "restore_terminal": True,
        "restore_chrome": False
    })

    assert isinstance(outcome, RestoreOutcomeSummary)
    assert outcome.workspace_id == "ws_test_magic"
    assert len(outcome.items) >= 2

    # Verify VS Code item status
    vscode_item = next((it for it in outcome.items if it.name == "VS Code"), None)
    if vscode_item is None:
        raise AssertionError(f"vscode_item not found in items: {[(it.name, it.status, it.detail) for it in outcome.items]}")
    assert vscode_item is not None
    assert vscode_item.status == "restored"
    assert "Restored window" in vscode_item.detail
    mock_popen.assert_called()

    # Verify Terminal item status
    term_item = next((it for it in outcome.items if it.name == "Terminal"), None)
    assert term_item is not None
    assert term_item.status == "restored"
    assert "Prepared working directory" in term_item.detail
    assert "npm run test" in term_item.detail

@patch("webbrowser.open")
def test_environment_restoration_engine_browser_opt_in(mock_open):
    reg = ResourceRegistry()
    reg.register_url("https://sqlite.org/docs", title="SQLite docs")
    reg.register_url("https://fastapi.tiangolo.com/", title="FastAPI docs")

    engine = EnvironmentRestorationEngine(resource_registry=reg)
    ws = MagicMock()
    ws.workspace_id = "ws_test_browser"
    ws.title = "Browser Test"
    ws.reality.resources = {}

    # Restore with only SQLite docs selected
    outcome = engine.restore(ws, {
        "restore_vscode": False,
        "restore_terminal": False,
        "selected_urls": ["https://sqlite.org/docs"]
    })

    sqlite_item = next((it for it in outcome.items if "SQLite" in it.name or "sqlite.org" in str(it.resource_id)), None)
    fastapi_item = next((it for it in outcome.items if "FastAPI" in it.name or "fastapi" in str(it.resource_id)), None)

    assert sqlite_item is not None and sqlite_item.status == "restored"
    assert fastapi_item is not None and fastapi_item.status == "skipped"
    mock_open.assert_called_once_with("https://sqlite.org/docs")

def test_workspace_manager_continue_context_evidence_breakdown_and_outcomes():
    bus = EventBus()
    wm = WorkspaceManager(event_bus=bus)
    
    # Create workspace with evidence
    ws = CognitiveWorkspace(workspace_id="ws_magic_1", title="Building runtime engine", domain_type="engineering")
    ws.reality.resources = {
        "/home/sarthak/arova/runtime.py": {"type": "file", "line": 10},
        "/home/sarthak/arova/events.py": {"type": "file", "line": 25},
        "https://sqlite.org/docs": {"type": "url", "summary": "SQLite docs"}
    }
    ws.understanding.momentum.goal = "Implement reliable state persistence"
    ws.understanding.momentum.current_blocker = "Lock contention during write"
    ws.interpretation.repo_paths.append("/home/sarthak/arova")

    wm._workspaces[ws.workspace_id] = ws
    wm._active_workspace_id = ws.workspace_id

    # Mock FS for honest but hermetic test — we still assert 95 only when dir exists
    # Wrap both context calls and restore in same patch so terminal dir check passes
    with patch("os.path.isdir", return_value=True), patch("os.path.exists", return_value=True), patch("shutil.which", return_value="/usr/bin/gnome-terminal"), patch("subprocess.Popen"):
        context = wm.get_continue_context(ws.workspace_id)
        assert "confidence_breakdown" in context
        breakdown = context["confidence_breakdown"]
        
        # Verify evidence scores — honest grounded values
        assert breakdown["Repository"] == 100
        assert breakdown["Open files"] >= 50
        assert breakdown["Goal"] == 94
        assert breakdown["Blocker"] == 89
        assert breakdown["Browser docs"] >= 61
        assert breakdown["Terminal"] == 95

        # Simulate restoration attempt and verify last_restore_outcomes
        wm.restore_environment(ws, {"restore_vscode": False, "restore_terminal": True})
        time.sleep(0.05)

        context_after = wm.get_continue_context(ws.workspace_id)
    assert context_after["last_restore_outcomes"] is not None
    outcomes_dict = context_after["last_restore_outcomes"]
    assert "items" in outcomes_dict
    assert any(it["name"] == "Terminal" and it["status"] == "restored" for it in outcomes_dict["items"])
