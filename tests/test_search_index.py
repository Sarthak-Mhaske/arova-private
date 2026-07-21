import time
from arova.core.cognition.search_index import SearchIndex, SearchableItem
from arova.core.cognition.workspace_manager import WorkspaceManager
from arova.core.capture.engine import CanonicalActivityEvent

def test_search_index_across_all_six_kinds():
    index = SearchIndex()
    now = time.time()
    
    # 1. Decision
    index.index_item(SearchableItem(
        id="dec_1",
        title="Decision: Rejected Redis because zero-dependency SQLite is required",
        summary="We rejected Redis because we need local SQLite persistence without external workers.",
        keywords=["redis", "sqlite", "persistence", "zero-dependency"],
        timestamp=now - 300,
        kind="Decision"
    ))
    
    # 2. Question
    index.index_item(SearchableItem(
        id="q_1",
        title="Question: How to persist approval queues across daemon restarts?",
        summary="Need to investigate whether local SQLite table structure handles approval queue state during crash.",
        keywords=["approval", "queue", "daemon", "restarts", "sqlite"],
        timestamp=now - 200,
        kind="Question"
    ))
    
    # 3. Workspace
    index.index_item(SearchableItem(
        id="ws_main",
        title="Arova Architecture & Development",
        summary="Active code development on memory_policy.py and supervisor daemon recovery.",
        keywords=["arova", "architecture", "memory_policy.py", "supervisor"],
        timestamp=now - 100,
        kind="Workspace"
    ))
    
    # 4. File
    index.index_item(SearchableItem(
        id="file_1",
        title="supervisor.py - Arova Architecture & Development",
        summary="Editing supervisor daemon loop around line 140",
        keywords=["supervisor.py", "daemon", "loop", "python"],
        timestamp=now - 50,
        kind="File"
    ))
    
    # 5. BrowserTab
    index.index_item(SearchableItem(
        id="tab_1",
        title="asyncio — Asynchronous I/O — Python 3 documentation",
        summary="Viewing Python 3 asyncio event loop docs",
        keywords=["asyncio", "python", "documentation", "docs"],
        timestamp=now - 10,
        kind="BrowserTab"
    ))
    
    # 6. Conversation
    index.index_item(SearchableItem(
        id="chat_1",
        title="Chat: Discussing SQLite vs Redis for local queue",
        summary="User asked why we chose SQLite over Redis for the local message queue.",
        keywords=["chat", "sqlite", "redis", "queue"],
        timestamp=now - 5,
        kind="Conversation"
    ))
    
    assert len(index.get_all_items()) == 6
    
    # Query "SQLite" -> Should match Decision, Question, and Conversation (and score highest on query matches)
    sqlite_results = index.search("SQLite")
    assert len(sqlite_results) >= 3
    kinds_found = {it.kind for it in sqlite_results}
    assert "Decision" in kinds_found
    assert "Question" in kinds_found
    assert "Conversation" in kinds_found
    
    # Query "approval queue" -> Should instantly find Question
    queue_results = index.search("approval queue")
    assert len(queue_results) >= 1
    assert queue_results[0].kind == "Question"
    assert "approval queues" in queue_results[0].title.lower()
    
    # Query with kind_filter="File"
    file_results = index.search("supervisor", kind_filter="File")
    assert len(file_results) == 1
    assert file_results[0].kind == "File"
    assert "supervisor.py" in file_results[0].title


def test_index_canonical_event():
    index = SearchIndex()
    event = CanonicalActivityEvent(
        event_id="evt_123",
        event_type="editor_change",
        timestamp=time.time(),
        source_plugin="vscode",
        normalized_payload={
            "resource_path": "/home/sarthak/arova/arova/runtime.py",
            "title": "runtime.py - Arova",
            "summary": "Editing runtime initialization and search index attachment",
            "kind": "File"
        }
    )
    
    item = index.index_canonical_event(event)
    assert item is not None
    assert item.kind == "File"
    
    results = index.search("runtime initialization")
    assert len(results) == 1
    assert results[0].id == "evt_123"


def test_index_workspace_decisions_and_questions():
    wm = WorkspaceManager()
    ws = wm._auto_emerge_workspace({"source_identity": "supervisor.py", "activity_summary": "arova coding"})
    assert ws is not None
    ws.understanding.decisions = ["Rejected Redis due to zero dependency rules"]
    ws.understanding.open_questions = ["Verify SQLite queue recovery during crash"]
    
    index = SearchIndex()
    index.index_workspace(ws)
    
    # Should have indexed the workspace + 1 decision + 1 question
    items = index.get_all_items()
    assert len(items) >= 3
    
    dec_matches = index.search("Redis", kind_filter="Decision")
    assert len(dec_matches) == 1
    assert dec_matches[0].kind == "Decision"
    
    q_matches = index.search("SQLite queue", kind_filter="Question")
    assert len(q_matches) == 1
    assert q_matches[0].kind == "Question"
