import asyncio
import os
import tempfile
import time
import pytest
from unittest.mock import MagicMock, patch

from arova.core.cognition.context import ContextSynthesizer, CognitiveContext
from arova.core.cognition.memory_retrieval import MemoryRetrievalEngine
from arova.core.cognition.workspace import CognitiveWorkspace
from arova.core.timeline.store import TimelineStore
from arova.core.timeline.events import TimelineEvent
from arova.core.events import RuntimeEventBus
from arova.core.ambience.schema import AmbientContext


@pytest.mark.asyncio
async def test_grounded_context_contains_verbatim_resources():
    """TIER 1.1: Synthesized context must contain verbatim RealityLayer resources"""
    bus = RuntimeEventBus()
    timeline = TimelineStore(event_bus=bus)
    # Create workspace with known resources
    from arova.core.cognition.workspace_manager import WorkspaceManager
    wm = WorkspaceManager(event_bus=bus)
    ws = CognitiveWorkspace(title="Arova Dev: runtime.py", domain_type="engineering")
    ws.reality.resources = {
        "/tmp/demo/runtime.py:112": {"type": "file", "identity": "/tmp/demo/runtime.py", "summary": "Fixing race", "line": 112},
        "https://groq.com/docs": {"type": "url", "identity": "https://groq.com/docs", "summary": "Groq docs"}
    }
    ws.interpretation.repo_paths = ["/tmp/demo"]
    ws.understanding.momentum.goal = "Fix race"
    ws.understanding.momentum.current_blocker = "Stale token"
    ws.understanding.momentum.next_action = "Patch supervisor"
    ws.understanding.confidence.score = 90
    wm._workspaces[ws.workspace_id] = ws
    wm._active_workspace_id = ws.workspace_id

    # Timeline
    ev = TimelineEvent(id="ev1", category="environment", title="Edited runtime.py", description="fix", source="vscode", importance=0.8, timestamp=time.time())
    timeline.events.append(ev)

    # Mock memory
    mock_mem = MagicMock()
    mock_mem.retrieve_for_context = MagicMock(return_value=asyncio.Future())
    mock_mem.retrieve_for_context.return_value.set_result([])

    synth = ContextSynthesizer(
        provider_manager=MagicMock(),
        memory_retrieval=mock_mem,
        ambient_observer=MagicMock(current_context=AmbientContext()),
        policy_runtime=MagicMock(),
        workspace_manager=wm,
        timeline_store=timeline
    )
    # Mock provider_manager.poll
    synth.provider_manager.poll = MagicMock(return_value=asyncio.Future())
    synth.provider_manager.poll.return_value.set_result([])

    ctx = await synth.synthesize("where was I?")
    block = ctx.to_system_prompt_block()
    assert "/tmp/demo/runtime.py" in block
    assert "Fix race" in block
    assert "Stale token" in block
    assert "GROUND TRUTH" in block
    assert "RECENT TIMELINE" in block


@pytest.mark.asyncio
async def test_mention_grounding_injects_verbatim_file():
    """TIER 1.3: @-mention should inject verbatim file excerpt"""
    bus = RuntimeEventBus()
    timeline = TimelineStore(event_bus=bus)
    from arova.core.cognition.workspace_manager import WorkspaceManager
    wm = WorkspaceManager(event_bus=bus)

    # Create temp file
    tmpdir = tempfile.mkdtemp()
    fpath = os.path.join(tmpdir, "demo_mention.py")
    with open(fpath, "w") as f:
        f.write("def hello():\n    return 'world'\n# line 3\n")

    ws = CognitiveWorkspace(title="Test", domain_type="engineering")
    ws.reality.resources = {fpath: {"type": "file", "identity": fpath, "summary": "demo"}}
    ws.interpretation.repo_paths = [tmpdir]
    ws.understanding.confidence.score = 85
    wm._workspaces[ws.workspace_id] = ws
    wm._active_workspace_id = ws.workspace_id

    mock_mem = MagicMock()
    mock_mem.retrieve_for_context = MagicMock(return_value=asyncio.Future())
    mock_mem.retrieve_for_context.return_value.set_result([])

    synth = ContextSynthesizer(
        provider_manager=MagicMock(),
        memory_retrieval=mock_mem,
        ambient_observer=MagicMock(current_context=AmbientContext()),
        policy_runtime=MagicMock(),
        workspace_manager=wm,
        timeline_store=timeline
    )
    synth.provider_manager.poll = MagicMock(return_value=asyncio.Future())
    synth.provider_manager.poll.return_value.set_result([])

    ctx = await synth.synthesize("@demo_mention.py why stuck?", mentions=["demo_mention.py"])
    block = ctx.to_system_prompt_block()
    assert "MENTIONED RESOURCES" in block
    assert "def hello()" in block
    assert fpath in block


@pytest.mark.asyncio
async def test_humility_when_low_confidence():
    """TIER 0.1: Low confidence must hedge"""
    bus = RuntimeEventBus()
    from arova.core.cognition.workspace_manager import WorkspaceManager
    wm = WorkspaceManager(event_bus=bus)
    ws = CognitiveWorkspace(title="Fresh", domain_type="general")
    ws.understanding.confidence.score = 40
    wm._workspaces[ws.workspace_id] = ws
    wm._active_workspace_id = ws.workspace_id

    mock_mem = MagicMock()
    mock_mem.retrieve_for_context = MagicMock(return_value=asyncio.Future())
    mock_mem.retrieve_for_context.return_value.set_result([])

    synth = ContextSynthesizer(
        provider_manager=MagicMock(),
        memory_retrieval=mock_mem,
        ambient_observer=MagicMock(current_context=AmbientContext()),
        policy_runtime=MagicMock(),
        workspace_manager=wm,
        timeline_store=TimelineStore(event_bus=bus)
    )
    synth.provider_manager.poll = MagicMock(return_value=asyncio.Future())
    synth.provider_manager.poll.return_value.set_result([])

    ctx = await synth.synthesize("what's my goal?")
    block = ctx.to_system_prompt_block()
    assert "LOW" in block or "hedge" in block.lower() or "I think" in block
    assert "HUMILITY" in block


def test_mock_provider_grounded_when_no_llm():
    """TIER 1 Mock must cite ground truth when available"""
    from arova.core.providers.implementations.mock_provider import _grounded_mock_from_prompt
    system_prompt = """
    [GROUND TRUTH — VERBATIM]
    - [file] /tmp/demo/runtime.py:112 Fixing race
    Workspace: Arova Dev: runtime.py
    Goal: Fix TokenExpiry race
    """
    messages = [{"role": "user", "content": "where was I?"}]
    out = _grounded_mock_from_prompt(system_prompt, messages)
    assert "runtime.py" in out
    assert "Arova Dev" in out
    assert "Grounded mock" in out or "were working" in out


def test_mock_mention_grounded():
    from arova.core.providers.implementations.mock_provider import _grounded_mock_from_prompt
    system_prompt = """
    [GROUND TRUTH]
    - [file] /tmp/x.py
    [MENTIONED RESOURCES — VERBATIM]
    --- FILE: /tmp/demo_mention.py ---
      1 | def hello():
    --- END FILE ---
    """
    messages = [{"role": "user", "content": "@demo_mention.py why stuck?"}]
    out = _grounded_mock_from_prompt(system_prompt, messages)
    assert "demo_mention.py" in out or "@-mentioned" in out
