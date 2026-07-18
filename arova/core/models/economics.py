from dataclasses import dataclass
from typing import Optional
from arova.core.models.profiles import CognitiveProfile

@dataclass
class CognitiveCost:
    virtual_cents: float
    latency_ms_estimate: float

class CognitiveBudgetEngine:
    """
    Evaluates the 'cost' of a reasoning cycle and enforces budget limits.
    """
    def __init__(self):
        # Very rough mock economics
        # Local inference costs 0 virtual cents, but has higher latency on low-end hardware.
        # Cloud inference has actual token costs.
        self.pricing_table = {
            "llama3-8b-8192": {"cost_per_1k_tokens": 0.05, "base_latency": 400},
            "llama3-70b-8192": {"cost_per_1k_tokens": 0.59, "base_latency": 800},
            "ollama-llama3-8b": {"cost_per_1k_tokens": 0.0, "base_latency": 1500}
        }
        
    def estimate_cost(self, model_name: str, max_tokens: int) -> CognitiveCost:
        rates = self.pricing_table.get(model_name)
        if not rates:
            # Fallback
            return CognitiveCost(virtual_cents=0.1, latency_ms_estimate=1000)
            
        cost = (max_tokens / 1000) * rates["cost_per_1k_tokens"]
        return CognitiveCost(virtual_cents=cost, latency_ms_estimate=rates["base_latency"])
        
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
