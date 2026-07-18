import logging
from typing import Dict
from arova.core.models.router.schema import CapabilityVector
from arova.core.providers.capabilities import Capability

logger = logging.getLogger(__name__)

class ActionRouter:
    """
    Layer 4: Final Authority on Cognitive Action.
    Takes a CapabilityVector and factors in CognitiveCost to decide the final execution path.
    """
    
    # Cognitive Cost Weights (higher = more expensive/slower)
    COGNITIVE_COSTS: Dict[Capability, float] = {
        Capability.CHAT: 1.0,
        Capability.NO_ACTION: 0.0,
        Capability.CONTINUITY_RESUME: 2.0,
        Capability.MEMORY_RECALL: 3.0,
        Capability.MEMORY_WRITE: 3.0,
        Capability.SEARCH: 5.0,
        Capability.TOOL_EXECUTION: 8.0,
        Capability.REASONING: 10.0,
        Capability.VISION: 25.0,
        Capability.AGENT_LAUNCH: 50.0,
        Capability.EMBEDDINGS: 2.0,
        Capability.SUMMARIZATION: 5.0
    }

    @classmethod
    def route(cls, vector: CapabilityVector) -> Capability:
        """
        Calculates the winning capability by applying a cost-penalty to scores.
        Quality vs Latency vs Cost optimization.
        """
        scores = {
            Capability.CHAT: vector.chat,
            Capability.REASONING: vector.reasoning,
            Capability.MEMORY_RECALL: vector.memory_recall,
            Capability.MEMORY_WRITE: vector.memory_write,
            Capability.TOOL_EXECUTION: vector.tool_execution,
            Capability.AGENT_LAUNCH: vector.agent_launch,
            Capability.VISION: vector.vision,
            Capability.SEARCH: vector.search,
            Capability.CONTINUITY_RESUME: vector.continuity_resume,
            Capability.NO_ACTION: vector.no_action
        }
        
        # Apply cognitive cost penalty (very simple optimization: score / log(1 + cost))
        import math
        optimized_scores = {}
        for cap, score in scores.items():
            if score <= 0:
                optimized_scores[cap] = 0.0
                continue
                
            cost = cls.COGNITIVE_COSTS.get(cap, 10.0)
            # Penalty factor reduces the score slightly for expensive operations
            # This prevents expensive models being triggered for marginal gains
            penalty_factor = math.log10(10 + cost)
            optimized_scores[cap] = score / penalty_factor
            
        winning_capability = max(optimized_scores.items(), key=lambda x: x[1])[0]
        logger.info(f"ActionRouter: Selected {winning_capability.name} (Optimized Score: {optimized_scores[winning_capability]:.2f})")
        
        return winning_capability
