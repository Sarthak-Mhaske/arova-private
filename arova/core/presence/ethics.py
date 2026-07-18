import time
from dataclasses import dataclass
from typing import Dict

@dataclass
class PredictiveSignal:
    topic: str              # What the prediction is about (e.g. "Git Repository Status")
    confidence: float       # 0.0 to 1.0
    utility_score: float    # 0.0 to 1.0 (How useful is surfacing this right now?)
    psychological_cost: float # 0.0 to 1.0 (Current interruption sensitivity / fatigue)

class FamiliarityTracker:
    """Tracks how often a predictive topic is surfaced to apply a familiarity decay penalty."""
    def __init__(self):
        # Maps topic -> (count, last_surfaced_timestamp)
        self.history: Dict[str, dict] = {}
        
    def get_decay_penalty(self, topic: str) -> float:
        """Calculates familiarity penalty. Repeated behaviors become noise."""
        if topic not in self.history:
            return 0.0
            
        record = self.history[topic]
        count = record["count"]
        last_time = record["last_time"]
        
        # Base penalty grows with count
        penalty = min(0.5, count * 0.1)
        
        # If it was very recently surfaced, huge penalty
        time_since = time.time() - last_time
        if time_since < 300: # 5 minutes
            penalty += 0.4
            
        return min(1.0, penalty)
        
    def record_surfaced(self, topic: str):
        if topic not in self.history:
            self.history[topic] = {"count": 1, "last_time": time.time()}
        else:
            self.history[topic]["count"] += 1
            self.history[topic]["last_time"] = time.time()

class EthicsEngine:
    """
    Evaluates predictive actions. Protects the user from 'surveillance feeling' 
    and predictive narration spam.
    """
    def __init__(self):
        self.familiarity_tracker = FamiliarityTracker()
        
    def should_surface_prediction(self, signal: PredictiveSignal) -> bool:
        """
        Core formula: (utility - familiarity_decay) > psychological_cost
        """
        # 1. Reject instantly if confidence is too low
        if signal.confidence < 0.7:
            return False
            
        # 2. Calculate familiarity penalty
        familiarity_decay = self.familiarity_tracker.get_decay_penalty(signal.topic)
        
        # 3. Apply formula
        adjusted_utility = signal.utility_score - familiarity_decay
        
        if adjusted_utility > signal.psychological_cost:
            # We are choosing to surface it! Record it so it decays next time.
            self.familiarity_tracker.record_surfaced(signal.topic)
            return True
            
        return False
