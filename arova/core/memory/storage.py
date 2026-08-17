import asyncio
import sqlite3
import time
import json
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict, Any

# We use standard sqlite3 with a thread executor to simulate aiosqlite for now
# if aiosqlite is not installed. For a production deployment, we'd depend on aiosqlite directly.

@dataclass
class MemoryEntry:
    id: str
    type: str # "semantic", "preference", "entity"
    content: str
    source_turn_id: str
    confidence: float = 1.0
    reinforcement_count: int = 1
    decay_score: float = 0.0 # higher means more decayed
    created_at: float = time.time()
    last_reinforced_at: float = time.time()
    
    # Phase 7.5 Metadata
    category: str = "general"
    why_remembered: str = ""
    continuity_value: float = 0.5
    sensitivity_tier: int = 2
    approval_state: str = "pending" # "saved", "pending", "rejected", "session_only"
    
class MemoryStorage:
    """
    Event-first explicit SQL storage for layered memory.
    """
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._conn = None
        self._lock = asyncio.Lock()
        from concurrent.futures import ThreadPoolExecutor
        self._executor = ThreadPoolExecutor(max_workers=1)

    async def initialize(self):
        async with self._lock:
            # We'll run the synchronous connect in a thread
            loop = asyncio.get_running_loop()
            self._conn = await loop.run_in_executor(self._executor, self._connect_and_migrate)

    def _connect_and_migrate(self):
        import os
        if self.db_path != ":memory:":
            os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        conn = sqlite3.connect(self.db_path, timeout=30.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
        except Exception:
            pass
        
        # 1. Episodic Memory: Raw conversations & capability execution logs
        conn.execute('''
            CREATE TABLE IF NOT EXISTS episodic_events (
                id TEXT PRIMARY KEY,
                event_type TEXT NOT NULL,
                turn_id TEXT,
                payload JSON NOT NULL,
                timestamp REAL NOT NULL
            )
        ''')
        
        # 2. Semantic/Entity Memory: The extracted "facts"
        conn.execute('''
            CREATE TABLE IF NOT EXISTS semantic_memory (
                id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                content TEXT NOT NULL,
                source_turn_id TEXT,
                confidence REAL DEFAULT 1.0,
                reinforcement_count INTEGER DEFAULT 1,
                decay_score REAL DEFAULT 0.0,
                created_at REAL NOT NULL,
                last_reinforced_at REAL NOT NULL,
                category TEXT DEFAULT 'general',
                why_remembered TEXT DEFAULT '',
                continuity_value REAL DEFAULT 0.5,
                sensitivity_tier INTEGER DEFAULT 2,
                approval_state TEXT DEFAULT 'saved'
            )
        ''')
        
        # Migrations for existing databases
        columns_to_add = [
            ("category", "TEXT DEFAULT 'general'"),
            ("why_remembered", "TEXT DEFAULT ''"),
            ("continuity_value", "REAL DEFAULT 0.5"),
            ("sensitivity_tier", "INTEGER DEFAULT 2"),
            ("approval_state", "TEXT DEFAULT 'saved'")
        ]
        for col_name, col_def in columns_to_add:
            try:
                conn.execute(f"ALTER TABLE semantic_memory ADD COLUMN {col_name} {col_def}")
            except sqlite3.OperationalError:
                pass # Column already exists
        
        # 3. Memory Event Sourcing: Track *why* a semantic memory changed
        conn.execute('''
            CREATE TABLE IF NOT EXISTS memory_mutations (
                id TEXT PRIMARY KEY,
                memory_id TEXT NOT NULL,
                mutation_type TEXT NOT NULL, -- "created", "reinforced", "decayed", "invalidated"
                delta JSON NOT NULL,
                timestamp REAL NOT NULL
            )
        ''')
        
        conn.commit()
        return conn

    async def append_episodic_event(self, event_id: str, event_type: str, turn_id: Optional[str], payload: Dict[str, Any]):
        query = "INSERT INTO episodic_events (id, event_type, turn_id, payload, timestamp) VALUES (?, ?, ?, ?, ?)"
        params = (event_id, event_type, turn_id, json.dumps(payload), time.time())
        await self._execute(query, params)

    async def store_semantic_memory(self, entry: MemoryEntry, mutation_id: str):
        query_mem = """
            INSERT INTO semantic_memory (id, type, content, source_turn_id, confidence, reinforcement_count, decay_score, created_at, last_reinforced_at, category, why_remembered, continuity_value, sensitivity_tier, approval_state)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                confidence=excluded.confidence,
                reinforcement_count=excluded.reinforcement_count,
                decay_score=excluded.decay_score,
                last_reinforced_at=excluded.last_reinforced_at,
                category=excluded.category,
                why_remembered=excluded.why_remembered,
                continuity_value=excluded.continuity_value,
                sensitivity_tier=excluded.sensitivity_tier,
                approval_state=excluded.approval_state
        """
        params_mem = (
            entry.id, entry.type, entry.content, entry.source_turn_id,
            entry.confidence, entry.reinforcement_count, entry.decay_score,
            entry.created_at, entry.last_reinforced_at,
            entry.category, entry.why_remembered, entry.continuity_value,
            entry.sensitivity_tier, entry.approval_state
        )
        
        query_mut = "INSERT INTO memory_mutations (id, memory_id, mutation_type, delta, timestamp) VALUES (?, ?, ?, ?, ?)"
        params_mut = (mutation_id, entry.id, "created", json.dumps(asdict(entry)), time.time())
        
        await self._execute_transaction([(query_mem, params_mem), (query_mut, params_mut)])

    async def get_all_semantic_memory(self, limit: int = None) -> List[MemoryEntry]:
        query = "SELECT * FROM semantic_memory WHERE decay_score < 10.0 ORDER BY last_reinforced_at DESC"
        if limit is not None:
            query += f" LIMIT {limit}"
        rows = await self._fetch(query)
        results = []
        for r in rows:
            # sqlite3.Row supports bracket access but not .get()
            # Convert to dict for safe access
            d = dict(r)
            results.append(MemoryEntry(
                id=d["id"],
                type=d["type"],
                content=d["content"],
                source_turn_id=d["source_turn_id"],
                confidence=d["confidence"],
                reinforcement_count=d["reinforcement_count"],
                decay_score=d["decay_score"],
                created_at=d["created_at"],
                last_reinforced_at=d["last_reinforced_at"],
                category=d.get("category") or "general",
                why_remembered=d.get("why_remembered") or "",
                continuity_value=d.get("continuity_value") if d.get("continuity_value") is not None else 0.5,
                sensitivity_tier=d.get("sensitivity_tier") if d.get("sensitivity_tier") is not None else 2,
                approval_state=d.get("approval_state") or "saved"
            ))
        return results

    async def pin_semantic_memory(self, memory_id: str, mutation_id: str):
        query_mem = "UPDATE semantic_memory SET decay_score = -1.0 WHERE id = ?"
        params_mem = (memory_id,)
        
        query_mut = "INSERT INTO memory_mutations (id, memory_id, mutation_type, delta, timestamp) VALUES (?, ?, ?, ?, ?)"
        params_mut = (mutation_id, memory_id, "pinned", json.dumps({"decay_score": -1.0}), time.time())
        
        await self._execute_transaction([(query_mem, params_mem), (query_mut, params_mut)])

    async def unpin_semantic_memory(self, memory_id: str, mutation_id: str):
        query_mem = "UPDATE semantic_memory SET decay_score = 0.0 WHERE id = ?"
        params_mem = (memory_id,)
        
        query_mut = "INSERT INTO memory_mutations (id, memory_id, mutation_type, delta, timestamp) VALUES (?, ?, ?, ?, ?)"
        params_mut = (mutation_id, memory_id, "unpinned", json.dumps({"decay_score": 0.0}), time.time())
        
        await self._execute_transaction([(query_mem, params_mem), (query_mut, params_mut)])

    async def delete_semantic_memory(self, memory_id: str, mutation_id: str):
        query_mem = "DELETE FROM semantic_memory WHERE id = ?"
        params_mem = (memory_id,)
        
        query_mut = "INSERT INTO memory_mutations (id, memory_id, mutation_type, delta, timestamp) VALUES (?, ?, ?, ?, ?)"
        params_mut = (mutation_id, memory_id, "deleted", json.dumps({}), time.time())
        
        await self._execute_transaction([(query_mem, params_mem), (query_mut, params_mut)])

    async def _execute(self, query: str, params: tuple):
        async with self._lock:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(self._executor, self._sync_execute, query, params)
            
    async def _execute_transaction(self, queries: List[tuple[str, tuple]]):
        async with self._lock:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(self._executor, self._sync_execute_transaction, queries)
            
    async def _fetch(self, query: str, params: tuple = ()) -> List[sqlite3.Row]:
        async with self._lock:
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(self._executor, self._sync_fetch, query, params)

    def _sync_execute(self, query: str, params: tuple):
        self._conn.execute(query, params)
        self._conn.commit()

    def _sync_execute_transaction(self, queries: List[tuple[str, tuple]]):
        try:
            for q, p in queries:
                self._conn.execute(q, p)
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise

    def _sync_fetch(self, query: str, params: tuple) -> List[sqlite3.Row]:
        cur = self._conn.execute(query, params)
        return cur.fetchall()

    def close(self):
        if self._conn:
            self._conn.close()
