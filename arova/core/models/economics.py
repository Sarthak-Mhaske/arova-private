from dataclasses import dataclass
from typing import Optional
from arova.core.models.profiles import CognitiveProfile
from arova.core.models.registry import get_model_registry

@dataclass
class CognitiveCost:
    virtual_cents: float
    latency_ms_estimate: float

class CognitiveBudgetEngine:
    """
    Evaluates the 'cost' of a reasoning cycle and enforces budget limits.
    """
    def __init__(self):
        pass
        
    def estimate_cost(self, model_name: str, max_tokens: int) -> CognitiveCost:
        # Check all candidates across registry to find this model's cost and latency
        registry = get_model_registry()
        found_cost = 0.1
        found_latency = 1000.0
        for prov_candidates in registry._candidates.values():
            for c in prov_candidates:
                if c.id == model_name:
                    found_cost = c.cost_per_1k_tokens
                    found_latency = float(c.latency_ms)
                    break
            
        cost = (max_tokens / 1000) * found_cost
        return CognitiveCost(virtual_cents=cost, latency_ms_estimate=found_latency)
        
    def is_within_budget(self, profile: CognitiveProfile, cost: CognitiveCost) -> bool:
        """
        Determines if the estimated cost is permitted under the current CognitiveProfile.
        """
        if profile == CognitiveProfile.MINIMAL:
            return cost.virtual_cents == 0.0 # Only local allowed
            
        if profile == CognitiveProfile.OFFLINE_FIRST:
            return cost.virtual_cents == 0.0 # Strict preference for local
            
        if profile == CognitiveProfile.PRIVATE:
            return cost.virtual_cents == 0.0 # Strict privacy constraint (no external API calls)
            
        if profile == CognitiveProfile.BALANCED:
            return cost.virtual_cents <= 0.5 # Allow small cloud calls, block massive 70B generation
            
        if profile == CognitiveProfile.DEEP_WORK:
            return True # Allow deep reasoning for high focus
            
        if profile == CognitiveProfile.POWER_USER:
            return True # No budget limits
            
        return True
