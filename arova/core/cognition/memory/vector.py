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
    """
    def __init__(self, storage_path: str = "~/.local/share/arova/qdrant/"):
        self.storage_path = os.path.expanduser(storage_path)
        os.makedirs(self.storage_path, exist_ok=True)
        
        if QdrantClient:
            self.client = QdrantClient(path=self.storage_path)
        else:
            self.client = None
            logging.error("qdrant-client not installed. Vector memory disabled.")
            
        self.collection_name = "arova_cognition"
        self.embedding_engine = EmbeddingEngine()
        
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
        if not self.client: return
        
        vector = self.embedding_engine.encode(memory.content)
        if not vector: return
        
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
        Base semantic search.
        """
        if not self.client: return []
        
        vector = self.embedding_engine.encode(query)
        if not vector: return []
        
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
