import time
import asyncio
import pytest
from arova.core.runtime import RuntimeContainer
from arova.core.bridge.runtime_events import RuntimeEventMapper

def test_autonomous_workday_cognition_simulator():
    """
    Autonomous Workday Cognition Audit:
    Simulates a full developer workday timeline (09:00 - 17:00) with ZERO chat inputs:
    - 09:00: Project start & file opening
    - 10:15: Test failure cluster & blocker detection
    - 11:30: Active debugging & error log accumulation
    - 13:00: 40-minute documentation reading dwell (heartbeat synthesis)
    - 15:00: Fix verification & automatic blocker resolution
    - 17:00: Workday memory evolution & state summary
    """
    async def _run_workday():
        runtime = RuntimeContainer()
        assert runtime.working_memory_runtime is not None
        assert runtime.reasoning_runtime is not None

        ws_broadcasts = []
        def _on_ws_event(topic, event_type, payload):
            pdict = payload.data if hasattr(payload, 'data') else (payload.__dict__ if hasattr(payload, '__dict__') else payload)
            mapped = RuntimeEventMapper.map_internal_event(event_type, pdict, topic=topic)
            if mapped:
                ws_broadcasts.append(mapped)

        h1 = lambda p: _on_ws_event("cognition", "WORKING_MEMORY_CHANGED", p)
        h2 = lambda p: _on_ws_event("reasoning", "REASONING_STEP_COMPLETED", p)
        handlers = [h1, h2]

        runtime.event_bus.subscribe("cognition", "WORKING_MEMORY_CHANGED", h1)
        runtime.event_bus.subscribe("reasoning", "REASONING_STEP_COMPLETED", h2)

        # Seed Active Workspace
        from arova.core.cognition.workspace import CognitiveWorkspace
        ws = CognitiveWorkspace("arova_sqlite", "SQLite Persistence Development")
        ws.interpretation.repo_paths = ["/home/sarthak/arova"]
        runtime.workspace_manager._workspaces["arova_sqlite"] = ws
        runtime.workspace_manager.set_active_workspace("arova_sqlite")

        # --- 09:00 Morning Start ---
        runtime.capture_engine.ingest_event("file.changed", "VSCode", {
            "resource_path": "/home/sarthak/arova/arova/core/memory/storage.py",
            "repository": "/home/sarthak/arova",
            "line": 42
        })
        await runtime.reasoning_runtime.evaluate_working_memory_shift(runtime.working_memory_runtime.get_snapshot())

        active_ws = runtime.workspace_manager.get_active_workspace()
        assert active_ws.understanding.momentum.goal == "Implementing feature logic in storage.py"
        assert active_ws.understanding.momentum.current_blocker is None

        # --- 10:15 Test Failure Cluster ---
        runtime.capture_engine.ingest_event("terminal.command_finished", "Terminal", {
            "command": "pytest tests/test_sqlite_persistence.py",
            "exit_code": 1,
            "error": "TransactionDeadlockError: database is locked"
        })
        await runtime.reasoning_runtime.evaluate_working_memory_shift(runtime.working_memory_runtime.get_snapshot())

        active_ws = runtime.workspace_manager.get_active_workspace()
        assert "Command failed (exit code 1)" in active_ws.understanding.momentum.current_blocker
        assert "Eliminating error" in active_ws.understanding.momentum.goal

        # --- 11:30 Active Debugging ---
        runtime.capture_engine.ingest_event("file.changed", "VSCode", {
            "resource_path": "/home/sarthak/arova/arova/core/memory/runtime.py",
            "repository": "/home/sarthak/arova",
            "line": 156
        })
        await runtime.reasoning_runtime.evaluate_working_memory_shift(runtime.working_memory_runtime.get_snapshot())

        wm = runtime.working_memory_runtime.get_snapshot()
        assert len(wm["active_files"]) == 2

        # --- 13:00 Documentation & Reading Dwell (Autonomous Heartbeat) ---
        # Simulate 40 minutes (2400 seconds) of reading documentation without typing
        triggered = runtime.working_memory_runtime.tick_idle_dwell(elapsed_seconds=2400.0)
        assert triggered is True
        wm_after_dwell = runtime.working_memory_runtime.get_snapshot()
        top_file_dwell = next(f for f in wm_after_dwell["active_files"] if f["path"].endswith("runtime.py"))
        assert top_file_dwell["dwell_seconds"] >= 2400.0

        # --- 15:00 Fix Verification & Blocker Resolution ---
        runtime.capture_engine.ingest_event("terminal.command_finished", "Terminal", {
            "command": "pytest tests/test_sqlite_persistence.py",
            "exit_code": 0,
            "summary": "12 passed in 0.4s"
        })
        await runtime.reasoning_runtime.evaluate_working_memory_shift(runtime.working_memory_runtime.get_snapshot())

        active_ws = runtime.workspace_manager.get_active_workspace()
        assert active_ws.understanding.momentum.current_blocker is None
        assert "Implementing feature logic" in active_ws.understanding.momentum.goal

        # --- 17:00 Workday Memory Evolution ---
        await asyncio.sleep(0.1)
        assert len(ws_broadcasts) >= 4, f"Expected WebSocket broadcasts across workday timeline, got {len(ws_broadcasts)}"

    asyncio.run(_run_workday())
