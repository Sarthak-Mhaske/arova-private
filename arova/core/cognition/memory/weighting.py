from typing import List, Tuple
from datetime import datetime
import math
from arova.core.cognition.memory.schema import VectorMemory

class HybridRetrievalEngine:
    """
    Combines temporal decay, semantic similarity, and attention weighting
    to sort vector search results.
    """
    def __init__(self, decay_half_life_hours: float = 24.0):
        self.decay_half_life_hours = decay_half_life_hours
        
    def score(self, memories: List[VectorMemory], current_attention_state: dict) -> List[Tuple[VectorMemory, float]]:
        """
        Takes raw semantic results and applies weighting rules.
        """
        now = datetime.now().timestamp()
        scored = []
        
        current_focus = current_attention_state.get("probable_mode", "unknown")
        
        for mem in memories:
            # 1. Base Score (assumed high if Qdrant returned it in top-k)
            base_score = mem.metadata.confidence
            
            # 2. Temporal Decay
            hours_old = (now - mem.timestamp) / 3600.0
            # Standard exponential decay
            temporal_multiplier = math.pow(0.5, hours_old / self.decay_half_life_hours)
            
            # 3. Attention Weighting (Phase 10 integration)
            attention_multiplier = 1.0
            if current_focus != "unknown" and current_focus == mem.metadata.source_context:
                # E.g. we are in VSCode and memory is from VSCode, boost it
                attention_multiplier = 1.5 + mem.metadata.attention_weight
                
            # 4. Retrieval Frequency (Reinforcement)
            freq_multiplier = 1.0 + (min(mem.metadata.retrieval_frequency, 10) * 0.1)
            
            final_score = base_score * temporal_multiplier * attention_multiplier * freq_multiplier
            scored.append((mem, final_score))
            
        # Sort descending by score
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored
