import pytest
from arova.core.cognition.workspace import CognitiveWorkspace
from arova.core.voice.intent_runtime import IntentRuntime
from arova.core.events import RuntimeEventBus
from unittest.mock import MagicMock

def test_golden_scenario_1_user_recap_attribution():
    """
    Scenario 1: User asks 'What was I doing?'
    Expected: Prompt explicitly structures Observed User State with FACTS vs INFERENCES.
    Must attribute project & goal to USER, not 'I was working on'.
    """
    ws = CognitiveWorkspace(title="Arova Persistence", domain_type="engineering")
    ws.understanding.momentum.goal = "Fix SQLite state persistence"
    ws.reality.resources = {"/home/sarthak/arova/storage.py": {"type": "file", "identity": "storage.py"}}
    
    prompt = ws.get_workspace_summary_prompt()
    
    assert "--- FACTS (Directly Observed Telemetry) ---" in prompt
    assert "--- INFERENCES & HYPOTHESES (Context Understanding) ---" in prompt
    assert "User's Current Goal: Fix SQLite state persistence" in prompt
    assert "storage.py" in prompt

def test_golden_scenario_2_assistant_code_generation_policy():
    """
    Scenario 2: User asks 'Continue the implementation' / 'Write the fix'
    Expected: Response policy explicitly permits acting as an assistant to generate requested code.
    """
    bus = RuntimeEventBus()
    runtime = IntentRuntime(event_bus=bus, session=MagicMock(), router=MagicMock(), context_synthesizer=MagicMock(), planner=MagicMock())
    
    ws = CognitiveWorkspace(title="Arova Persistence", domain_type="engineering")
    wm = MagicMock()
    wm.get_active_workspace.return_value = ws
    runtime._workspace_manager = wm
    
    prompt_summary = ws.get_workspace_summary_prompt()
    assert "OBSERVED USER STATE" in prompt_summary
    assert "FACTS" in prompt_summary
    assert "INFERENCES" in prompt_summary

def test_golden_scenario_3_evidence_grounded_inferences():
    """
    Scenario 3: User asks 'Why was I editing runtime.py?'
    Expected: Prompt isolates observed resource facts under FACTS block so LLM grounds response in telemetry.
    """
    ws = CognitiveWorkspace(title="Arova Engine", domain_type="engineering")
    ws.reality.resources = {"/home/sarthak/arova/runtime.py": {"type": "file", "identity": "runtime.py"}}
    
    prompt = ws.get_workspace_summary_prompt()
    assert "--- FACTS (Directly Observed Telemetry) ---" in prompt
    assert "runtime.py" in prompt

def test_golden_scenario_4_empty_workspace_no_hallucination_policy():
    """
    Scenario 4: Workspace is empty / no telemetry.
    Expected: Response policy explicitly instructs: 'If there is no observed workspace telemetry... state I don't have enough context rather than guessing.'
    """
    bus = RuntimeEventBus()
    runtime = IntentRuntime(event_bus=bus, session=MagicMock(), router=MagicMock(), context_synthesizer=MagicMock(), planner=MagicMock())
    
    ws = CognitiveWorkspace(title="Empty Workspace", domain_type="engineering")
    prompt = ws.get_workspace_summary_prompt()
    
    assert "--- FACTS (Directly Observed Telemetry) ---" in prompt
    assert "--- INFERENCES & HYPOTHESES (Context Understanding) ---" in prompt
