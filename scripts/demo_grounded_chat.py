"""
TIER 1 Chat Moat Prototype — Verbatim Grounded Answer Demo
Run: python scripts/demo_grounded_chat.py
Shows: Arova answers "where was I?" with VERBATIM ground truth vs ChatGPT hallucination.
"""

import asyncio
import os
import tempfile
import time

# Create a temp file to demo @-mention grounding
tmp_dir = tempfile.mkdtemp(prefix="arova_demo_")
demo_file = os.path.join(tmp_dir, "runtime.py")
with open(demo_file, "w") as f:
    f.write('''class ModelRuntime:
    def _select_model(self, depth):
        # BUG: TokenExpiry race here at line 112
        if depth == "deep":
            return "groq-llama3.3"
        return "ollama/phi3"

# TODO: Fix supervisor race condition
''')

async def main():
    from arova.core.runtime import RuntimeContainer
    from arova.core.cognition.workspace import CognitiveWorkspace
    from arova.core.timeline.events import TimelineEvent

    print("\n" + "="*70)
    print(" AROVA TIER 1 CHAT MOAT — VERBATIM GROUNDED ANSWER DEMO")
    print("="*70)
    print(f"\n[Setup] Created temp demo file: {demo_file} (with bug at line 3)")

    rc = RuntimeContainer()
    print(f"[Runtime] Booted in {rc.beta_mode.upper()} mode (voice={rc.enable_voice})")

    # === Create a realistic Developer Workspace ===
    ws = CognitiveWorkspace(title="Arova Development: runtime.py", domain_type="engineering")
    ws.reality.resources = {
        demo_file: {"type": "file", "identity": demo_file, "summary": "Editing runtime.py — fixing TokenExpiry race", "line": 3, "col": 12},
        "/home/user/arova/arova/core/cognition/context.py": {"type": "file", "identity": "/home/user/arova/arova/core/cognition/context.py", "summary": "Grounding synthesis"},
        "https://docs.groq.com/docs/models": {"type": "url", "identity": "https://docs.groq.com/docs/models", "summary": "Groq models docs"},
        "/home/user/arova": {"type": "terminal", "identity": "/home/user/arova", "summary": "pytest failed: TokenExpiry race in ModelRuntime"}
    }
    ws.interpretation.repo_paths = ["/home/user/arova", tmp_dir]
    ws.interpretation.browser_domains = ["docs.groq.com"]
    ws.understanding.momentum.goal = "Fix TokenExpiry race in ModelRuntime._select_model"
    ws.understanding.momentum.progress_percentage = 68
    ws.understanding.momentum.current_blocker = "TokenExpiry race condition at runtime.py:3 — supervisor.py still using stale token"
    ws.understanding.momentum.next_action = "Patch supervisor.py to refresh token before _select_model call and re-run pytest"
    ws.understanding.health.status = "Blocked"
    ws.understanding.confidence.score = 88
    ws.understanding.confidence.reasons = ["VS Code active on runtime.py:3", "Terminal shows pytest failure", "Groq docs open", "2 recent commits on this repo"]
    ws.understanding.what_changed = "Reproduced TokenExpiry race with new test, isolated to _select_model deep path"
    ws.understanding.decisions = ["Use Groq for deep reasoning, Ollama for local fallback (decided yesterday)"]
    ws.understanding.delta_changes = ["Reproduced race with pytest -k test_token_expiry", "Isolated to runtime.py:3"]

    rc.workspace_manager._workspaces[ws.workspace_id] = ws
    rc.workspace_manager._active_workspace_id = ws.workspace_id

    # Add timeline events (lived trajectory)
    for title, desc in [
        ("Edited runtime.py:3", "Fixing TokenExpiry race — added refresh logic"),
        ("Terminal: pytest failed", "AssertionError: TokenExpiry race in ModelRuntime"),
        ("Browser: Groq docs", "Reading Groq model routing for deep reasoning"),
    ]:
        ev = TimelineEvent(id=f"ev_{time.time()}", category="environment", title=title, description=desc, source="vscode", importance=0.8, timestamp=time.time())
        rc.timeline.events.append(ev)

    print(f"\n[Workspace] '{ws.title}'")
    print(f"  Goal: {ws.understanding.momentum.goal}")
    print(f"  Blocker: {ws.understanding.momentum.current_blocker}")
    print(f"  Next: {ws.understanding.momentum.next_action}")
    print(f"  Confidence: {ws.understanding.confidence.score}% ({', '.join(ws.understanding.confidence.reasons[:2])})")
    print(f"  Resources: {list(ws.reality.resources.keys())[:2]}")

    # === Demo 1: "where was I?" — Grounded vs ChatGPT ===
    print("\n" + "-"*70)
    print(" DEMO 1: User asks 'where was I?' (no @mention, no context pasted)")
    print("-"*70)
    print(" ChatGPT (stateless): 'Could you tell me what project you're working on?'")
    print(" Arova (stateful, grounded):")
    
    ctx = await rc.context_synthesizer.synthesize("where was I?")
    block = ctx.to_system_prompt_block()
    print("\n  [GROUND TRUTH BLOCK — first 600 chars]:")
    print("  " + block[:600].replace("\n", "\n  ") + "...")

    # Verify verbatim
    assert demo_file in block, "FAILED: demo file not in grounded block!"
    assert "TokenExpiry race" in block, "FAILED: blocker not in block!"
    assert "Patch supervisor.py" in block, "FAILED: next action not in block!"
    print("\n  ✓ Grounded block contains VERBATIM file:line, blocker, next_action")
    print("  ✓ ChatGPT would hallucinate — Arova cites deterministic RealityLayer")

    # Simulate MockProvider grounded answer (no LLM key needed)
    from arova.core.providers.implementations.mock_provider import _grounded_mock_from_prompt
    mock_answer = _grounded_mock_from_prompt(block, [{"role": "user", "content": "where was I?"}])
    print(f"\n  [AROVA MOCK GROUNDED ANSWER (no LLM key)]:\n  {mock_answer}")

    # === Demo 2: @-mention grounding ===
    print("\n" + "-"*70)
    print(f" DEMO 2: User asks '@runtime.py why is this stuck?'")
    print("-"*70)
    print(f" ChatGPT: 'Please paste the code for runtime.py'")
    print(f" Arova: Already has verbatim file excerpt, no paste needed")

    ctx2 = await rc.context_synthesizer.synthesize("@runtime.py why is this stuck?", mentions=["runtime.py", demo_file])
    block2 = ctx2.to_system_prompt_block()
    print("\n  [MENTIONED RESOURCES — excerpt]:")
    if ctx2.mentioned_resources:
        print("  " + ctx2.mentioned_resources[:800].replace("\n", "\n  "))
        assert "ModelRuntime" in ctx2.mentioned_resources, "FAILED: file content not injected!"
        print("\n  ✓ @-mention resolved to VERBATIM file excerpt (first 80 lines with line numbers)")
    else:
        print("  (No excerpt — file not found, but mention noted)")

    print(f"\n  [GROUND TRUTH still present]: {demo_file in block2}")
    mock_answer2 = _grounded_mock_from_prompt(block2, [{"role": "user", "content": "@runtime.py why is this stuck?"}])
    print(f"\n  [AROVA MOCK @-GROUNDED ANSWER]:\n  {mock_answer2}")

    # === Demo 3: Low confidence humility ===
    print("\n" + "-"*70)
    print(" DEMO 3: Low confidence (45%) — humility test")
    print("-"*70)
    ws_low = CognitiveWorkspace(title="Fresh WS", domain_type="general")
    ws_low.understanding.confidence.score = 45
    ws_low.understanding.confidence.reasons = ["Only 1 file observed"]
    rc.workspace_manager._workspaces[ws_low.workspace_id] = ws_low
    rc.workspace_manager._active_workspace_id = ws_low.workspace_id
    ctx_low = await rc.context_synthesizer.synthesize("what's my goal?")
    block_low = ctx_low.to_system_prompt_block()
    assert "LOW" in block_low or "hedge" in block_low.lower() or "I think" in block_low
    print("  Block contains humility instruction:")
    print("  " + [l for l in block_low.split("\n") if "LOW" in l or "hedge" in l.lower() or "I think" in l][0])
    print("  ✓ Arova hedges with 'I think...' when <70% — no confidence theater")

    # === Demo 4: Timeline continuity ===
    print("\n" + "-"*70)
    print(" DEMO 4: Timeline continuity — trajectory")
    print("-"*70)
    # Create a capsule and store
    from arova.core.timeline.momentum import MomentumCapsule
    import uuid
    cap = MomentumCapsule(
        id=f"cap_demo_{uuid.uuid4().hex[:6]}",
        timestamp=time.time(),
        duration=3600,
        room="Implementation",
        workspace=[demo_file],
        objective="Fix TokenExpiry race",
        progress="Reproduced race, isolated to runtime.py:3",
        blockers=["supervisor.py stale token"],
        next_action="Patch supervisor.py",
        confidence=0.88,
        mental_state="blocked",
        energy_level="medium",
        decision_log=["Use Groq for deep"],
        avoid_list=["Don't retry Redis cache — already ruled out"]
    )
    rc.timeline.store_capsule(cap)
    ctx3 = await rc.context_synthesizer.synthesize("what's next?", mentions=[])
    block3 = ctx3.to_system_prompt_block()
    # Need to re-activate original ws for capsule to be fetched (capsule fetch is global, not per ws)
    rc.workspace_manager._active_workspace_id = ws.workspace_id
    ctx3 = await rc.context_synthesizer.synthesize("what's next?")
    block3 = ctx3.to_system_prompt_block()
    if "Next Action" in block3:
        print("  ✓ Momentum capsule Next Action surfaced in context")
        print("  " + [l for l in block3.split("\n") if "Next Action" in l][0])
    if "Avoid" in block3:
        print("  ✓ Avoid list surfaced (don't retry Redis)")
    
    print("\n" + "="*70)
    print(" VERDICT: Arova answers from VERBATIM ground truth.")
    print(" ChatGPT needs you to re-explain. Arova already knows.")
    print(" Moat = RealityLayer + Timeline + @-mention excerpts + Humility.")
    print("="*70 + "\n")
    print(f"[Cleanup] Demo file kept at {demo_file} for inspection")
    print(f"Run again with real Groq key (GROQ_API_KEY env) for full LLM streaming.\n")

if __name__ == "__main__":
    asyncio.run(main())
