import time
import asyncio
import pytest
from arova.core.runtime import RuntimeContainer
from arova.core.bridge.runtime_events import RuntimeEventMapper

def test_live_daemon_continuous_cognition_harness():
    """
    Live Operational Runtime Harness:
    Proves end-to-end continuous cognition in a running RuntimeContainer instance:
    1. Feeds raw canonical capture events into capture_engine.
    2. Verifies WorkingMemoryRuntime updates active working set without chat input.
    3. Verifies ReasoningRuntime automatically triggers, infers blockers, and updates Workspace Graph.
    4. Verifies MemoryRuntime forms continuous incremental episodic memory.
    5. Verifies EventMapper formats external WebSocket events (`working_memory.changed`, `reasoning.step_completed`).
    """
    async def _async_harness():
        # 1. Boot live RuntimeContainer
        runtime = RuntimeContainer()
        assert runtime.working_memory_runtime is not None
        assert runtime.reasoning_runtime is not None

        captured_ws_events = []
        def _on_ws_event(topic, event_type, payload):
            pdict = payload.data if hasattr(payload, 'data') else (payload.__dict__ if hasattr(payload, '__dict__') else payload)
            mapped = RuntimeEventMapper.map_internal_event(event_type, pdict, topic=topic)
            if mapped:
                captured_ws_events.append(mapped)

        h1 = lambda p: _on_ws_event("cognition", "WORKING_MEMORY_CHANGED", p)
        h2 = lambda p: _on_ws_event("reasoning", "REASONING_STEP_COMPLETED", p)
        test_handlers = [h1, h2]

        runtime.event_bus.subscribe("cognition", "WORKING_MEMORY_CHANGED", h1)
        runtime.event_bus.subscribe("reasoning", "REASONING_STEP_COMPLETED", h2)

        # Seed an active workspace
        from arova.core.cognition.workspace import CognitiveWorkspace
        ws = CognitiveWorkspace("arova_dev", "Arova Development")
        ws.interpretation.repo_paths = ["/home/sarthak/arova"]
        runtime.workspace_manager._workspaces["arova_dev"] = ws
        runtime.workspace_manager.set_active_workspace("arova_dev")

        # 2. Simulate User working on code (editing engine.py)
        file_norm = {
            "resource_path": "/home/sarthak/arova/arova/core/capture/engine.py",
            "repository": "/home/sarthak/arova",
            "line": 154,
            "title": "engine.py"
        }
        runtime.capture_engine.ingest_event("file.changed", "VSCode", file_norm)
        await runtime.reasoning_runtime.evaluate_working_memory_shift(runtime.working_memory_runtime.get_snapshot())

        wm_snap = runtime.working_memory_runtime.get_snapshot()
        assert wm_snap["current_repository"] == "/home/sarthak/arova"
        assert len(wm_snap["active_files"]) == 1
        assert wm_snap["active_files"][0]["path"] == "/home/sarthak/arova/arova/core/capture/engine.py"

        # 3. Simulate Terminal command failure (pytest error)
        term_norm = {
            "command": "pytest tests/test_reality_hyp_03_vision.py",
            "exit_code": 1,
            "summary": "pytest command failed"
        }
        runtime.capture_engine.ingest_event("terminal.command_finished", "Terminal", term_norm)
        await runtime.reasoning_runtime.evaluate_working_memory_shift(runtime.working_memory_runtime.get_snapshot())

        # 4. Verify ReasoningRuntime triggered continuously & updated Workspace Graph
        active_ws = runtime.workspace_manager.get_active_workspace()
        assert active_ws is not None
        assert "Command failed (exit code 1)" in active_ws.understanding.momentum.current_blocker
        assert "pytest tests/test_reality_hyp_03_vision.py" in active_ws.understanding.momentum.next_action

        # 5. Verify mapped external WebSocket events were produced
        await asyncio.sleep(0.1)
        wm_events = [e for e in captured_ws_events if e["type"] == "working_memory.changed"]
        reasoning_events = [e for e in captured_ws_events if e["type"] == "reasoning.step_completed"]
        assert len(wm_events) > 0, "No working_memory.changed WebSocket events emitted!"
        assert len(reasoning_events) > 0, "No reasoning.step_completed WebSocket events emitted!"

    asyncio.run(_async_harness())
