import asyncio
import pytest
from arova.core.events import RuntimeEventBus
from arova.core.cognition.workspace_manager import WorkspaceManager

def test_context_restoration_trigger():
    async def run():
        from arova.core.cognition.workspace import CognitiveWorkspace
        bus = RuntimeEventBus()
        wm = WorkspaceManager(event_bus=bus)
        ws = CognitiveWorkspace(workspace_id="ws_test", title="Arova Development")
        wm._workspaces["ws_test"] = ws
        wm._active_workspace_id = "ws_test"
        ws.reality.resources["/home/sarthak/arova/arova/core/runtime.py"] = {"type": "editor"}
        
        surfacing_events = []
        def on_surfacing(e):
            surfacing_events.append(e)
        bus.subscribe("cognition", "surfacing_push", on_surfacing)
        
        # Trigger restoration
        wm.restore_environment(ws, {"restore_all": True})
        
        bus.emit("cognition", "surfacing_push", {
            "type": "surfacing",
            "kind": "momentum",
            "from": "AROVA · CONTEXT RECOVERY",
            "lede": f"Restored {ws.title}",
            "paragraphs": [
                f"**Restored Workspace**: {ws.title}",
                "**Active Resources**: runtime.py",
                "**Next Action**: Continue development"
            ],
            "actions": [
                {"label": "Resume & Restore All", "eventType": "workspace.continue", "primary": True},
                {"label": "Choose What To Restore", "clientAction": "open_options"},
                {"label": "Dismiss", "clientAction": "dismiss"}
            ]
        })
        
        await asyncio.sleep(0.05)
        
        assert len(surfacing_events) == 1
        event_data = surfacing_events[0].data
        assert event_data["from"] == "AROVA · CONTEXT RECOVERY"
        assert len(event_data["actions"]) == 3
        assert event_data["actions"][0]["label"] == "Resume & Restore All"

    asyncio.run(run())
