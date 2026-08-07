"""
Regression: "open these resources for me" must NEVER launch snap/random apps.
It must open URLs from the prior assistant message (or named resources).
Also covers known-app fast path and MemoryExtractor truncated-JSON salvage.
"""
import asyncio
import os
import sys
from unittest.mock import MagicMock, patch, AsyncMock

import pytest

# Ensure repo root on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from arova.core.cognition.router import CognitiveRouter, IntentClassification
from arova.core.models.schema import ReasoningDepth
from arova.core.events import RuntimeEventBus
from arova.core.session import ConversationSession, ConversationTurn
from arova.core.memory.extractor import MemoryExtractor


class _FakeModels:
    async def invoke_structured(self, *a, **k):
        return {"category": "chat", "confidence": 0.9, "reasoning": "fallback"}


def _router() -> CognitiveRouter:
    return CognitiveRouter(model_runtime=_FakeModels(), event_bus=RuntimeEventBus())


# ---------------------------------------------------------------------------
# Router fast-path
# ---------------------------------------------------------------------------

def test_open_these_resources_is_not_app_launch():
    r = _router()
    for phrase in [
        "can you open these resources for me'",
        "open these resources for me",
        "open those links",
        "open the resources please",
        "can you open them",
        "Open these resources",
    ]:
        result = r._get_fast_path(phrase)
        assert result is not None, f"expected fast path for: {phrase}"
        assert result.category == "open_prior_resources", (
            f"{phrase!r} got category={result.category}"
        )
        assert result.fast_path_graph is None


def test_open_known_app_still_works():
    r = _router()
    result = r._get_fast_path("open firefox")
    assert result is not None
    assert result.category == "fast_action"
    assert result.fast_path_graph is not None
    node = result.fast_path_graph.nodes[0]
    assert node.capability_name == "open_app"
    assert node.args["app_name"] == "firefox"


def test_open_garbage_phrase_does_not_launch():
    r = _router()
    # Must NOT match open_app with app_name="these resources..."
    result = r._get_fast_path("open my notes about linear algebra")
    # Either None (fall through to chat) or open_prior — never garbage app
    if result and result.category == "fast_action":
        app = result.fast_path_graph.nodes[0].args.get("app_name", "")
        assert app in {"firefox", "kitty", "code", "brave", "spotify"} or False, (
            f"must not launch unknown multi-word as app: {app}"
        )
    else:
        assert result is None or result.category == "open_prior_resources"


def test_extract_app_name_rejects_deictics():
    r = _router()
    assert r._extract_app_name("open these resources for me") is None
    assert r._extract_app_name("open those links") is None
    assert r._extract_app_name("open firefox") == "firefox"
    assert r._extract_app_name("launch code") == "code"


# ---------------------------------------------------------------------------
# IntentRuntime open_prior_resources
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_open_prior_resources_opens_urls_from_last_assistant():
    from arova.core.voice.intent_runtime import IntentRuntime

    bus = RuntimeEventBus()
    session = ConversationSession()
    session.add_user_message("help me learn linear algebra")
    session.add_assistant_message(
        "Start with Strang and 3Blue1Brown:\n"
        "1. https://ocw.mit.edu/courses/18-06-linear-algebra-spring-2010/\n"
        "2. https://www.youtube.com/playlist?list=PLZHQObOWTQDPD3MizzM2xVFitgF8hE_ab\n"
    )

    rt = IntentRuntime(
        event_bus=bus,
        session=session,
        router=_router(),
        context_synthesizer=MagicMock(),
        planner=MagicMock(),
    )
    # Capture loop
    rt._loop = asyncio.get_running_loop()

    opened = []
    with patch.object(rt, "_open_url", side_effect=lambda u: opened.append(u) or True):
        await rt._handle_open_prior_resources(
            "can you open these resources for me",
            turn_id="t1",
            vocalize=False,
        )

    assert len(opened) == 2
    assert any("ocw.mit.edu" in u for u in opened)
    assert any("youtube.com" in u for u in opened)
    # Session should record the ack
    last = session.last_assistant_message()
    assert last and "Opened" in last


@pytest.mark.asyncio
async def test_open_prior_resources_named_fallback_without_urls():
    from arova.core.voice.intent_runtime import IntentRuntime

    bus = RuntimeEventBus()
    session = ConversationSession()
    session.add_user_message("resources?")
    # Name-only recommendations (what the buggy LLM produced)
    session.add_assistant_message(
        "I recommend: 1. Textbook: Introduction to Linear Algebra by Gilbert Strang "
        "2. Online Course: Linear Algebra by MIT OpenCourseWare "
        "3. Video Lectures: Linear Algebra by 3Blue1Brown"
    )

    rt = IntentRuntime(
        event_bus=bus,
        session=session,
        router=_router(),
        context_synthesizer=MagicMock(),
        planner=MagicMock(),
    )
    rt._loop = asyncio.get_running_loop()

    opened = []
    with patch.object(rt, "_open_url", side_effect=lambda u: opened.append(u) or True):
        await rt._handle_open_prior_resources("open these resources", "t2", False)

    assert len(opened) >= 2  # Strang/OCW + 3Blue1Brown at minimum
    assert all(u.startswith("http") for u in opened)


@pytest.mark.asyncio
async def test_route_open_resources_end_to_end_no_app_launch():
    """Full route(): open these resources → open_prior_resources, never fast_action."""
    r = _router()
    msgs = [{"role": "user", "content": "can you open these resources for me'"}]
    result = await r.route(msgs)
    assert result.category == "open_prior_resources"
    assert result.fast_path_graph is None


# ---------------------------------------------------------------------------
# Memory extractor truncated JSON + heuristic
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_memory_extractor_recovers_truncated_json():
    ext = MemoryExtractor({})

    class FakeOrch:
        async def invoke_structured(self, *a, **k):
            # Truncated mid-object — same failure mode as production logs
            return {
                "content": (
                    '[\n  {\n    "type": "entity",\n'
                    '    "content": "User is studying Computational Linear Algebra",\n'
                    '    "category": "education",\n'
                    '    "why_remembered": "User explicitly stated their cou'
                )
            }

    ext.set_orchestrator(FakeOrch())
    turn = ConversationTurn(
        user_transcript=(
            "OK YOU have to help me learn Computational Linear Algebra & Optimization "
            "for CS also tell me resources where to cover this from"
        ),
        assistant_response="Let's start fresh...",
    )
    mems = await ext.extract_from_turn(turn)
    assert len(mems) >= 1
    assert any(
        "Linear Algebra" in m.content or "learning context" in m.content.lower()
        for m in mems
    )


@pytest.mark.asyncio
async def test_memory_extractor_heuristic_when_empty_parse():
    ext = MemoryExtractor({})

    class FakeOrch:
        async def invoke_structured(self, *a, **k):
            return {"content": "NOT JSON AT ALL {{{"}

    ext.set_orchestrator(FakeOrch())
    turn = ConversationTurn(
        user_transcript=(
            "I need to learn computational linear algebra for my CS exam "
            "and score an A- without going too deep"
        ),
        assistant_response="Sure.",
    )
    mems = await ext.extract_from_turn(turn)
    assert len(mems) == 1
    assert mems[0].category == "education"
