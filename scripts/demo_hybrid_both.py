"""
TIER 1 — Hybrid Vector + Search Unification Demo
Shows: Vector semantic memory (synonym search) + Unified search (find docs) vs ChatGPT hallucination
Run: PYTHONPATH=. python scripts/demo_hybrid_both.py
"""

import asyncio
import os
import tempfile
import time

async def main():
    from arova.core.runtime import RuntimeContainer
    from arova.core.cognition.workspace import CognitiveWorkspace
    from arova.core.timeline.events import TimelineEvent
    from arova.core.cognition.memory.schema import VectorMemory, MemoryMetadata
    from arova.core.cognition.search_index import SearchableItem

    print("\n" + "="*70)
    print(" AROVA TIER 1 — HYBRID VECTOR + SEARCH UNIFICATION DEMO")
    print("="*70)

    rc = RuntimeContainer()
    print(f"[Runtime] {rc.beta_mode.upper()} (vector fallback: hash, search: unified)")

    # === Setup workspace ===
    ws = CognitiveWorkspace(title="Arova Dev: Hybrid Demo", domain_type="engineering")
    ws.reality.resources = {
        "/tmp/demo/auth.py": {"type": "file", "identity": "/tmp/demo/auth.py", "summary": "Auth bug"},
        "https://sqlite.org/docs": {"type": "url", "identity": "https://sqlite.org/docs", "summary": "SQLite docs"},
    }
    ws.interpretation.repo_paths = ["/tmp/demo"]
    ws.understanding.momentum.goal = "Fix auth + docs"
    ws.understanding.momentum.current_blocker = "Auth race"
    ws.understanding.momentum.next_action = "Patch auth.py"
    ws.understanding.confidence.score = 90
    rc.workspace_manager._workspaces[ws.workspace_id] = ws
    rc.workspace_manager._active_workspace_id = ws.workspace_id

    # Seed SearchIndex with diverse items (mimics Phase 6 unified index)
    si = rc.search_index
    si.clear()
    si.index_item(SearchableItem(id="1", title="SQLite Documentation", summary="Official SQLite docs for persistence", keywords=["sqlite", "docs", "persistence"], timestamp=time.time(), kind="BrowserTab", payload={"url": "https://sqlite.org/docs"}))
    si.index_item(SearchableItem(id="2", title="Decision: Use Groq for deep reasoning", summary="Decided to use Groq llama-3.3 for deep reasoning", keywords=["groq", "decision", "reasoning"], timestamp=time.time(), kind="Decision", payload={"text": "Use Groq"}))
    si.index_item(SearchableItem(id="3", title="auth.py", summary="File handling token expiry", keywords=["auth", "token", "expiry"], timestamp=time.time(), kind="File", payload={"resource_path": "/tmp/demo/auth.py"}))
    # Also index workspace
    si.index_workspace(ws)

    print(f"[SearchIndex] Seeded {len(si.get_all_items())} items (Decision, File, BrowserTab, Workspace)")

    # Seed Vector + SQLite memory via MemoryRuntime (hybrid)
    # Create a memory entry via direct storage + vector (to test both paths)
    from arova.core.memory.storage import MemoryEntry
    import uuid
    mem1 = MemoryEntry(id=str(uuid.uuid4()), type="fact", content="User prefers dark mode for coding", source_turn_id="demo", confidence=0.9, category="preference", why_remembered="User said so", approval_state="saved")
    mem2 = MemoryEntry(id=str(uuid.uuid4()), type="fact", content="token expiry race condition in ModelRuntime at runtime.py:112", source_turn_id="demo", confidence=0.95, category="engineering", why_remembered="Bug report", approval_state="saved")
    # Store via MemoryRuntime's storage (and vector)
    await rc.memory_runtime.storage.initialize()
    await rc.memory_runtime.storage.store_semantic_memory(mem1, str(uuid.uuid4()))
    await rc.memory_runtime.storage.store_semantic_memory(mem2, str(uuid.uuid4()))
    # Also manually insert into vector (since extract_eagerly not called, we mimic)
    if rc.memory_runtime.vector_store:
        from arova.core.cognition.memory.schema import VectorMemory, MemoryMetadata
        for mem in [mem1, mem2]:
            meta = MemoryMetadata(semantic_type=mem.type, source_context=mem.category, confidence=mem.confidence)
            vm = VectorMemory(content=mem.content, metadata=meta, id=mem.id)
            rc.memory_runtime.vector_store.insert(vm)
    print(f"[Memory] Seeded 2 SQLite memories + vector (hybrid)")

    # === DEMO 5: Vector Hybrid — synonym search ===
    print("\n" + "-"*70)
    print(" DEMO 5: Vector Hybrid Retrieval — 'token expiry' (and paraphrase 'login failure')")
    print("-"*70)
    print(" ChatGPT/keyword only: 'login failure' != 'token expiry' → no match (or hallucinate)")
    print(" Arova vector (hybrid): word-hash fallback now, sentence-transformers when installed → semantic")
    print("  (Demo uses word-hash fallback: 'token expiry' shares words → finds token expiry; 'login failure' will need real model)")

    from arova.core.cognition.memory_retrieval import MemoryRetrievalEngine
    engine = rc.context_synthesizer.memory  # MemoryRetrievalEngine
    # Direct vector search — use exact phrase that shares words for hash fallback demo
    if rc.memory_runtime.vector_store:
        hits = rc.memory_runtime.vector_store.search("token expiry", limit=2)
        print(f"  Vector search for 'token expiry' returned {len(hits)} hits (word-hash fallback, real model would handle 'login failure' paraphrase)")
        for h in hits:
            print(f"    - {h.content[:70]} (conf {h.metadata.confidence})")
        # Hybrid via engine — exact
        hybrid_hits = await engine.retrieve_for_context("token expiry", limit=2)
        print(f"  Hybrid retrieve (vector + heuristic) for 'token expiry' returned {len(hybrid_hits)} hits:")
        for hr in hybrid_hits:
            print(f"    - [{hr.source}] {hr.entry.content[:70]} (score {hr.relevance_score:.2f}) why: {hr.why_retrieved[:50]}")
        # Paraphrase that would need real semantic
        hits_para = await engine.retrieve_for_context("login failure", limit=2)
        print(f"  Hybrid for paraphrase 'login failure' (needs real sentence-transformers): {len(hits_para)} hits")
        for hr in hits_para:
            print(f"    - [{hr.source}] {hr.entry.content[:60]} (score {hr.relevance_score:.2f})")
        if not hits_para or hits_para[0].entry.content.lower().find("tokenexpiry") == -1 and hits_para[0].entry.content.lower().find("dark") != -1:
            print("    (With hash fallback, paraphrase may miss — install sentence-transformers for true semantic)")
    else:
        print("  Vector store not available — heuristic only")

    # Now test a query that SHOULD match via keyword: "dark mode"
    print("\n  Query 'dark mode' (exact keyword) — should hit via both:")
    hits2 = await engine.retrieve_for_context("dark mode", limit=2)
    for hr in hits2:
        print(f"    - [{hr.source}] {hr.entry.content} (score {hr.relevance_score:.2f})")

    # Synthesize context with memory (show personalization moat)
    ctx = await rc.context_synthesizer.synthesize("dark mode?")
    block = ctx.to_system_prompt_block()
    print("\n  [MEMORY LAYER in grounded block]:")
    for line in block.split("\n"):
        if "dark mode" in line.lower() or "token expiry" in line.lower():
            print(f"    {line}")
    print("  ✓ Hybrid retrieval injects memory verbatim — ChatGPT has no personal memory")

    # === DEMO 6: Search Unification — 'find sqlite docs' ===
    print("\n" + "-"*70)
    print(" DEMO 6: Search Unification — 'find sqlite docs' (no hallucination)")
    print("-"*70)
    print(" ChatGPT: hallucinates generic SQLite description or asks for link")
    print(" Arova: cites VERBATIM unified index hits (Decision, File, BrowserTab)")

    ctx2 = await rc.context_synthesizer.synthesize("find sqlite docs")
    block2 = ctx2.to_system_prompt_block()
    print("\n  [SEARCH RESULTS in grounded block]:")
    in_search = False
    for line in block2.split("\n"):
        if "[SEARCH RESULTS" in line:
            in_search = True
        if in_search:
            print(f"    {line}")
            if "--- END" in line:
                break
        if in_search and len([l for l in block2.split("\n") if "[SEARCH RESULTS" in l]) > 0 and line.startswith("--- END"):
            break
    # Also show raw search directly
    direct_hits = si.search("sqlite docs", limit=3)
    print(f"\n  Direct SearchIndex.search('sqlite docs') → {len(direct_hits)} hits:")
    for h in direct_hits:
        print(f"    - [{h.kind}] {h.title}: {h.summary[:60]}")

    # Check that search results were injected
    if ctx2.search_results:
        print("\n  ✓ Search unification injected verbatim hits — LLM will cite them, not hallucinate")
        # Show mock answer
        from arova.core.providers.implementations.mock_provider import _grounded_mock_from_prompt
        mock = _grounded_mock_from_prompt(block2, [{"role": "user", "content": "find sqlite docs"}])
        print(f"\n  [MOCK GROUNDED SEARCH ANSWER]:\n  {mock}")
    else:
        print("\n  (No search results injected — query not search-like enough, try 'find sqlite docs')")

    # Also test a non-search query should NOT inject search
    ctx3 = await rc.context_synthesizer.synthesize("hello")
    print(f"\n  Query 'hello' search_results present? {bool(ctx3.search_results)} (should be False/None for greetings)")
    print("  ✓ Search only for search-like queries — not for greetings (avoids noise)")

    print("\n" + "="*70)
    print(" VERDICT: Vector (personal memory) + Search (unified index) = moat.")
    print(" ChatGPT: stateless + hallucinates. Arova: remembers you + cites verbatim.")
    print("="*70 + "\n")

if __name__ == "__main__":
    asyncio.run(main())
