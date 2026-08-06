import logging
import os
from typing import List, Optional
from arova.core.cognition.memory.schema import VectorMemory, MemoryMetadata
from arova.core.cognition.memory.embeddings import EmbeddingEngine

try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import PointStruct, Distance, VectorParams, Filter, FieldCondition, MatchValue
except ImportError:
    QdrantClient = None

class QdrantLocal:
    """
    Local embedded Vector Database via Qdrant Client.
    Stores and retrieves VectorMemory objects.
    Falls back to in-memory cosine store when qdrant-client not installed — keeps
    vector pipeline functional for tests/minimal envs without external deps.
    """
    def __init__(self, storage_path: str = "~/.local/share/arova/qdrant/"):
        self.storage_path = os.path.expanduser(storage_path)
        os.makedirs(self.storage_path, exist_ok=True)
        
        self.embedding_engine = EmbeddingEngine()
        self._mem_store: dict = {}  # fallback: id -> {vector, memory}

        if QdrantClient:
            try:
                self.client = QdrantClient(path=self.storage_path)
            except Exception as e:
                logging.warning(f"Qdrant init failed ({e}) — using in-memory fallback")
                self.client = None
        else:
            self.client = None
            logging.warning("qdrant-client not installed — using in-memory vector fallback (install qdrant-client for persistent Qdrant)")
            
        self.collection_name = "arova_cognition"
        
        self._ensure_collection()
        
    def _ensure_collection(self):
        if not self.client: return
        
        # Check if collection exists
        try:
            self.client.get_collection(self.collection_name)
        except Exception:
            # Create it
            # all-MiniLM-L6-v2 produces 384-dimensional vectors
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=384, distance=Distance.COSINE)
            )
            logging.info(f"Created Qdrant collection: {self.collection_name}")
            
    def insert(self, memory: VectorMemory):
        vector = self.embedding_engine.encode(memory.content)
        if not vector:
            return
        if not self.client:
            # In-memory fallback
            self._mem_store[memory.id] = {"vector": vector, "memory": memory}
            return
        
        payload = memory.metadata.to_dict()
        payload["content"] = memory.content
        payload["timestamp"] = memory.timestamp
        
        point = PointStruct(
            id=memory.id,
            vector=vector,
            payload=payload
        )
        
        self.client.upsert(
            collection_name=self.collection_name,
            points=[point]
        )
        
    def search(self, query: str, semantic_type: Optional[str] = None, limit: int = 5) -> List[VectorMemory]:
        """
        Base semantic search — Qdrant if available, else in-memory cosine.
        """
        vector = self.embedding_engine.encode(query)
        if not vector:
            return []
        if not self.client:
            # In-memory cosine fallback
            return self._mem_search(vector, semantic_type, limit)
        
        query_filter = None
        if semantic_type:
            query_filter = Filter(
                must=[
                    FieldCondition(
                        key="semantic_type",
                        match=MatchValue(value=semantic_type)
                    )
                ]
            )
            
        results = self.client.query_points(
            collection_name=self.collection_name,
            query=vector,
            query_filter=query_filter,
            limit=limit,
            with_payload=True
        ).points
        
        memories = []
        for res in results:
            payload = res.payload
            content = payload.pop("content", "")
            timestamp = payload.pop("timestamp", 0)
            
            meta = MemoryMetadata.from_dict(payload)
            memories.append(VectorMemory(
                id=res.id,
                content=content,
                metadata=meta,
                timestamp=timestamp
            ))
            
        return memories

    def _mem_search(self, query_vec: List[float], semantic_type: Optional[str], limit: int) -> List[VectorMemory]:
        """In-memory cosine similarity fallback."""
        import math
        scored = []
        for entry in self._mem_store.values():
            mem: VectorMemory = entry["memory"]
            vec: List[float] = entry["vector"]
            if semantic_type and mem.metadata.semantic_type != semantic_type:
                continue
            # Cosine
            dot = sum(a*b for a, b in zip(query_vec, vec))
            norm_q = math.sqrt(sum(x*x for x in query_vec)) or 1.0
            norm_v = math.sqrt(sum(x*x for x in vec)) or 1.0
            cos = dot / (norm_q * norm_v)
            scored.append((cos, mem))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [m for _, m in scored[:limit]]
