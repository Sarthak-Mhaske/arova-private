import time
from arova.core.cognition.workspace_manager import WorkspaceManager
from arova.core.cognition.workspace import CognitiveWorkspace
from arova.core.events import RuntimeEventBus as EventBus

def test_story_first_resume_and_explainability():
    bus = EventBus()
    wm = WorkspaceManager(event_bus=bus, orchestrator=None)
    
    ws = CognitiveWorkspace(title="Arova Architecture", domain_type="engineering")
    ws.understanding.decisions.append("Adopted SQLite for local state persistence.")
    ws.understanding.momentum.current_blocker = "Daemon restart loses approval queue."
    ws.understanding.confidence.score = 92
    ws.reality.resources["/home/sarthak/arova/runtime.py"] = {"type": "file", "identity": "/home/sarthak/arova/runtime.py"}
    
    wm._workspaces[ws.workspace_id] = ws
    wm._active_workspace_id = ws.workspace_id
    
    ctx = wm.get_continue_context(ws.workspace_id)
    
    # Verify Story-First structure
    assert "story_narrative" in ctx
    assert len(ctx["story_narrative"]) >= 2
    assert "Yesterday you focused on Arova Architecture." in ctx["story_narrative"][0]
    assert any("Adopted SQLite" in line for line in ctx["story_narrative"])
    assert any("Stopped due to blocker: Daemon restart loses approval queue." in line for line in ctx["story_narrative"])
    
    # Verify [Why?] explainability structure
    assert "explainability_reasons" in ctx
    assert len(ctx["explainability_reasons"]) >= 3
    assert any("You spent significant time in Arova Architecture recently" in line for line in ctx["explainability_reasons"])
    assert any("High" in line for line in ctx["explainability_reasons"])
    assert any("You left with one unresolved blocker" in line for line in ctx["explainability_reasons"])
    
    # Verify default options checkmarks (`Phase 6 Rule 5`)
    assert ctx["options"]["restore_editors"] is True
    assert ctx["options"]["restore_terminal"] is True
    assert ctx["options"]["restore_browsers"] is False
    assert ctx["options"]["restore_documentation"] is False
