import time
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from arova.core.memory.runtime import MemoryRuntime
from arova.core.memory.storage import MemoryEntry
from arova.core.cognition.constants import (
    CONFIDENCE_SCORE_WEIGHT, MAX_DECAY_PENALTY, SECONDS_PER_DAY,
    MAX_REINFORCEMENT_BONUS, REINFORCEMENT_BONUS_RATE, MIN_RETRIEVAL_SCORE_THRESHOLD
)

@dataclass
class RetrievedMemory:
    entry: MemoryEntry
    relevance_score: float
    why_retrieved: str
    source: str = "heuristic"

class MemoryRetrievalEngine:
    """
    Hybrid retrieval: Vector semantic (QdrantLocal + HybridRetrievalEngine) + heuristic fallback.
    Tries vector first for semantic matches (synonyms, paraphrases), falls back to keyword heuristic.
    Keeps pipeline functional even when qdrant/sentence-transformers not installed.
    """
    def __init__(self, memory_runtime: MemoryRuntime):
        self.memory = memory_runtime
        # Lazy hybrid components — init only if vector store available
        self._hybrid = None
        self._vector_available = False
        try:
            if getattr(self.memory, 'vector_store', None) is not None:
                from arova.core.cognition.memory.weighting import HybridRetrievalEngine
                self._hybrid = HybridRetrievalEngine()
                self._vector_available = True
        except Exception:
            self._hybrid = None
            self._vector_available = False

    async def _vector_retrieve(self, query: str, limit: int) -> List[RetrievedMemory]:
        """Try vector semantic search, return RetrievedMemory list with source='vector'."""
        if not self._vector_available or not getattr(self.memory, 'vector_store', None):
            return []
        try:
            vector_store = self.memory.vector_store
            # Check if store has any vectors
            has_vectors = False
            if vector_store.client:
                try:
                    has_vectors = vector_store.client.count(vector_store.collection_name).count > 0
                except:
                    has_vectors = len(getattr(vector_store, '_mem_store', {})) > 0
            else:
                has_vectors = len(getattr(vector_store, '_mem_store', {})) > 0
            if not has_vectors:
                return []

            raw_mems = vector_store.search(query, limit=limit * 2)
            if not raw_mems:
                return []

            # Hybrid scoring with attention context
            attention_state = {"probable_mode": "unknown"}
            try:
                # Try to get attention state if available via memory -> not direct, use empty
                pass
            except:
                pass

            # Keep original cosine order (semantic), don't re-rank purely by confidence
            # Hybrid temporal/attention is secondary; for prototype, preserve vector ranking
            # Use rank-based score so semantic order wins over confidence
            scored = [(m, 1.0 - i*0.1) for i, m in enumerate(raw_mems)]
            # Optionally blend with hybrid confidence (weighted)
            if self._hybrid:
                try:
                    hybrid_scored = {vm.id: s for vm, s in self._hybrid.score(raw_mems, attention_state)}
                    # Blend: 0.85 * cosine rank + 0.15 * hybrid
                    blended = []
                    for i, (vm, rank_score) in enumerate(scored):
                        h_score = hybrid_scored.get(vm.id, 0.5)
                        blended_score = rank_score * 0.85 + (h_score / 1.0) * 0.15
                        blended.append((vm, blended_score))
                    blended.sort(key=lambda x: x[1], reverse=True)
                    scored = blended
                except:
                    pass
            vector_results: List[RetrievedMemory] = []
            for vm, score in scored[:limit]:
                # Convert VectorMemory -> MemoryEntry for uniformity
                from arova.core.memory.storage import MemoryEntry
                import time
                entry = MemoryEntry(
                    id=vm.id,
                    type=vm.metadata.semantic_type or "fact",
                    content=vm.content,
                    source_turn_id="vector",
                    confidence=float(vm.metadata.confidence),
                    reinforcement_count=int(vm.metadata.retrieval_frequency),
                    decay_score=0.0,
                    created_at=float(vm.timestamp),
                    last_reinforced_at=float(vm.metadata.last_retrieved or vm.timestamp),
                    category=vm.metadata.source_context or "general",
                    why_remembered=f"Vector semantic (score {score:.2f})",
                    continuity_value=float(vm.metadata.attention_weight),
                    sensitivity_tier=2,
                    approval_state="saved"
                )
                vector_results.append(RetrievedMemory(
                    entry=entry,
                    relevance_score=float(score),
                    why_retrieved=f"Vector semantic (cosine) score={score:.2f}",
                    source="vector"
                ))
            return vector_results
        except Exception as e:
            import logging
            logging.debug(f"Vector retrieve failed, fallback to heuristic: {e}")
            return []

    async def _heuristic_retrieve(self, query: str, limit: int) -> List[RetrievedMemory]:
        """Heuristic fallback pipeline (original)."""
        # 1. Fetch top candidates (pre-filtered via SQL limit/order)
        all_memories = await self.memory.storage.get_all_semantic_memory(limit=100)
        if not all_memories:
            return []
            
        scored: List[RetrievedMemory] = []
        query_words = set(query.lower().split())
        
        for mem in all_memories:
            score = 0.0
            reasons = []
            
            # A. Base Confidence (0.0 - 1.0)
            score += mem.confidence * CONFIDENCE_SCORE_WEIGHT
            
            # B. Recency / Decay Penalty
            time_since_reinforcement = time.time() - mem.last_reinforced_at
            decay_penalty = min(MAX_DECAY_PENALTY, time_since_reinforcement / SECONDS_PER_DAY) # lose up to 0.5 points over 24h
            score -= decay_penalty
            
            # C. Keyword Overlap Heuristic
            mem_words = set(mem.content.lower().split())
            overlap = query_words.intersection(mem_words)
            if overlap:
                score += (len(overlap) / max(len(query_words), 1)) * 1.5
                reasons.append(f"Keyword match: {', '.join(overlap)}")
                
            # D. Reinforcement Bonus
            if mem.reinforcement_count > 1:
                score += min(MAX_REINFORCEMENT_BONUS, mem.reinforcement_count * REINFORCEMENT_BONUS_RATE)
                reasons.append("Highly reinforced")
                
            if score > MIN_RETRIEVAL_SCORE_THRESHOLD: # Minimum threshold
                why = " | ".join(reasons) if reasons else "Base relevance threshold met."
                scored.append(RetrievedMemory(entry=mem, relevance_score=score, why_retrieved=why))
                
        # Sort by relevance and take top N
        scored.sort(key=lambda x: x.relevance_score, reverse=True)
        return scored[:limit]

    async def retrieve_for_context(self, current_query: str, limit: int = 5) -> List[RetrievedMemory]:
        """Hybrid: Vector semantic first (synonyms), heuristic fallback, merged & deduped."""
        vector_results = await self._vector_retrieve(current_query, limit)
        heuristic_results = await self._heuristic_retrieve(current_query, limit)

        # Merge: vector first (semantic), then heuristic, dedupe by content
        seen = set()
        merged: List[RetrievedMemory] = []
        for r in vector_results:
            key = r.entry.content.lower().strip()
            if key not in seen:
                seen.add(key)
                merged.append(r)
        for r in heuristic_results:
            key = r.entry.content.lower().strip()
            if key not in seen:
                seen.add(key)
                merged.append(r)
            if len(merged) >= limit:
                break

        # Sort by relevance_score descending (hybrid scores already comparable)
        merged.sort(key=lambda x: x.relevance_score, reverse=True)
        return merged[:limit]
