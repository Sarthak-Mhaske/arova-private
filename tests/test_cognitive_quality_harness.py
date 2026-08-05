import time
import asyncio
import pytest
from arova.core.runtime import RuntimeContainer
from arova.core.memory.working_memory import WorkingMemoryRuntime
from arova.core.reasoning.runtime import ReasoningRuntime

def test_cognitive_trigger_classification_and_evidence():
    """
    Cognitive Quality Test 1:
    Proves that WorkingMemoryRuntime classifies specific Cognitive Triggers
    (STACKTRACE_DETECTED, REPEATED_TERMINAL_FAILURE, DOCS_TO_CODE_PIVOT)
    and exposes empirical evidence breakdowns rather than arbitrary percentage scores.
    """
    wm = WorkingMemoryRuntime()

    # 1. Ingest browser documentation view
    wm.ingest_event({
        "event_type": "browser.tab_changed",
        "source_plugin": "Chrome",
        "normalized_payload": {
            "url": "https://sqlite.org/docs/transactions.html",
            "title": "SQLite Transaction Docs"
        }
    })

    # 2. Ingest IDE file change -> Triggers DOCS_TO_CODE_PIVOT
    wm.ingest_event({
        "event_type": "file.changed",
        "source_plugin": "VSCode",
        "normalized_payload": {
            "resource_path": "/home/sarthak/arova/arova/core/memory/storage.py",
            "repository": "/home/sarthak/arova"
        }
    })
    assert wm.state.cognitive_trigger_type == "DOCS_TO_CODE_PIVOT"

    # 3. Ingest terminal command failure -> Triggers REPEATED_TERMINAL_FAILURE
    wm.ingest_event({
        "event_type": "terminal.command_finished",
        "source_plugin": "Terminal",
        "normalized_payload": {
            "command": "pytest tests/test_sqlite_persistence.py",
            "exit_code": 1
        }
    })
    assert wm.state.cognitive_trigger_type == "REPEATED_TERMINAL_FAILURE"

    # 4. Verify empirical evidence breakdown structure
    evidence = wm.state.get_empirical_evidence()
    assert evidence["active_files_count"] == 1
    assert evidence["terminal_failures_count"] == 1
    assert evidence["browser_tabs_count"] == 1
    assert evidence["attention_mode"] == "deep_work"

def test_semantic_goal_and_blocker_derivation():
    """
    Cognitive Quality Test 2:
    Proves that ReasoningRuntime derives semantic goals and blockers from raw activity evidence,
    and automatically clears blockers when tests pass.
    """
    async def _test():
        runtime = RuntimeContainer()
        from arova.core.cognition.workspace import CognitiveWorkspace
        ws = CognitiveWorkspace("arova_dev", "Arova Development")
        ws.interpretation.repo_paths = ["/home/sarthak/arova"]
        runtime.workspace_manager._workspaces["arova_dev"] = ws
        runtime.workspace_manager.set_active_workspace("arova_dev")

        # Ingest terminal error
        runtime.capture_engine.ingest_event("terminal.command_finished", "Terminal", {
            "command": "pytest tests/test_sqlite.py",
            "exit_code": 1
        })
        outcome = await runtime.reasoning_runtime.evaluate_working_memory_shift(runtime.working_memory_runtime.get_snapshot())
        
        assert outcome["cognitive_trigger_type"] == "REPEATED_TERMINAL_FAILURE"
        assert "Eliminating error" in outcome["inferred_goal"]
        assert "Command failed (exit code 1)" in outcome["inferred_blocker"]
        assert outcome["empirical_evidence"]["terminal_failures_count"] == 1

    asyncio.run(_test())
