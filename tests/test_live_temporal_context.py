import time
import pytest
from arova.core.time import get_live_temporal_context_prompt
from arova.core.context import format_context_for_llm

def test_live_temporal_context_prompt_formatting():
    prompt = get_live_temporal_context_prompt()
    assert "LIVE TEMPORAL & TIME CONTEXT" in prompt
    assert "Current Date & Time:" in prompt
    assert "IMPORTANT: You ALWAYS have access to real-time information" in prompt

def test_live_temporal_absence_gap():
    past_timestamp = time.time() - 3720 # ~1 hour and 2 mins ago
    prompt = get_live_temporal_context_prompt(last_active_timestamp=past_timestamp)
    assert "User Absence Gap: User was away for ~1h 2m" in prompt

def test_format_context_includes_time():
    env = {"os": "Arch Linux", "installed_apps": ["brave", "code"]}
    formatted = format_context_for_llm(env)
    assert "LIVE TEMPORAL & TIME CONTEXT" in formatted
    assert "Current Date & Time:" in formatted
