import pytest
from arova.core.cognition.workspace import CognitiveWorkspace

def test_workspace_summary_prompt_sectioning_and_attribution():
    ws = CognitiveWorkspace(title="Arova Persistence Engine", domain_type="engineering")
    ws.understanding.momentum.goal = "Fix SQLite approval queue state persistence"
    ws.understanding.momentum.current_blocker = "Lock contention during background write"
    ws.understanding.what_changed = "Created current.json fallback"
    
    prompt = ws.get_workspace_summary_prompt()
    
    # 1. Must contain explicit OBSERVED USER STATE section header
    assert "OBSERVED USER STATE (Telemetry)" in prompt
    assert "Everything in this block describes the USER's activity" in prompt
    
    # 2. Must refer to the USER's goal and project, avoiding self-attribution
    assert "User's Active Project: Arova Persistence Engine" in prompt
    assert "User's Current Goal: Fix SQLite approval queue state persistence" in prompt
    assert "Current blocker the USER is facing:" in prompt

def test_intent_runtime_prompt_construction():
    from arova.core.voice.intent_runtime import IntentRuntime
    from arova.core.events import RuntimeEventBus
    from unittest.mock import MagicMock
    
    bus = RuntimeEventBus()
    session = MagicMock()
    router = MagicMock()
    context_synth = MagicMock()
    planner = MagicMock()
    
    runtime = IntentRuntime(event_bus=bus, session=session, router=router, context_synthesizer=context_synth, planner=planner)
    
    ws = CognitiveWorkspace(title="Arova Development", domain_type="engineering")
    ws.understanding.momentum.goal = "Implement SQLite persistence"
    
    wm = MagicMock()
    wm.get_active_workspace.return_value = ws
    runtime._workspace_manager = wm
    
    # Verify sectioning structure in constructed prompt
    prompt_summary = ws.get_workspace_summary_prompt()
    assert "OBSERVED USER STATE" in prompt_summary
    assert "User's Current Goal: Implement SQLite persistence" in prompt_summary

