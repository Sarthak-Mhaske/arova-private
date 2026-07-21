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
    Intelligently retrieves and ranks memories from the MemoryRuntime.
    For Phase 7, relies on heuristic scoring (confidence, decay, keyword overlap)
    rather than heavy vector embeddings.
    """
    def __init__(self, memory_runtime: MemoryRuntime):
        self.memory = memory_runtime

    async def retrieve_for_context(self, current_query: str, limit: int = 5) -> List[RetrievedMemory]:
        """Heuristic retrieval pipeline."""
        # 1. Fetch all candidates (in a real system, we'd pre-filter via SQL FTS)
        all_memories = await self.memory.storage.get_all_semantic_memory()
        if not all_memories:
            return []
            
        scored: List[RetrievedMemory] = []
        query_words = set(current_query.lower().split())
        
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
