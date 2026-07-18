import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

@dataclass
class AttentionTrajectory:
    """Probabilistic trajectory of the user's attention."""
    probabilities: Dict[str, float] = field(default_factory=lambda: {
        "deep_work": 0.0,
        "fragmented": 0.0,
        "recovering": 0.0,
        "idle": 1.0
    })
    narrative: str = "The user is currently idle."
    confidence: float = 1.0
    derived_from: List[str] = field(default_factory=list)
    last_updated: float = field(default_factory=time.time)

class AttentionNarrativeGenerator:
    """
    Synthesizes short-term environmental attention states into a smooth
    probabilistic trajectory and generates an English narrative.
    """
    def __init__(self):
        self._history: List[Dict[str, float]] = []
        self._current_trajectory = AttentionTrajectory()
        
    def update(self, attention_state: dict) -> AttentionTrajectory:
        """
        Takes a new raw attention_state (e.g. from AttentionGraphEngine)
        and updates the probabilistic trajectory.
        """
        now = time.time()
        
        # Extract features
        focus_depth = attention_state.get("focus_depth", 0.0)
        interruption_rate = attention_state.get("interruption_rate", 0.0)
        cognitive_momentum = attention_state.get("cognitive_momentum", 0.0)
        
        # Calculate raw probabilities for this tick
        raw_probs = {
            "deep_work": focus_depth * cognitive_momentum,
            "fragmented": interruption_rate * (1.0 - cognitive_momentum),
            "idle": max(0.0, 1.0 - (focus_depth + interruption_rate)),
        }
        
        # Calculate recovering: high focus depth but high recent interruption
        raw_probs["recovering"] = max(0.0, focus_depth * (0.5 + min(0.5, interruption_rate)))
        
        # Normalize raw probs
        total = sum(raw_probs.values())
        if total > 0:
            raw_probs = {k: v/total for k, v in raw_probs.items()}
        else:
            raw_probs = {"idle": 1.0, "deep_work": 0.0, "fragmented": 0.0, "recovering": 0.0}
            
        self._history.append({"time": now, "probs": raw_probs})
        if len(self._history) > 30: # keep last few mins
            self._history.pop(0)
            
        # Smooth the probabilities over recent history
        smoothed_probs = {"deep_work": 0.0, "fragmented": 0.0, "recovering": 0.0, "idle": 0.0}
        weight_sum = 0.0
        for i, entry in enumerate(self._history):
            weight = (i + 1) / len(self._history) # more recent = higher weight
            for k in smoothed_probs:
                smoothed_probs[k] += entry["probs"].get(k, 0.0) * weight
            weight_sum += weight
            
        for k in smoothed_probs:
            smoothed_probs[k] = round(smoothed_probs[k] / weight_sum, 3)
            
        # Generate narrative based on dominant and rising probabilities
        narrative, confidence, derived = self._generate_narrative(smoothed_probs, raw_probs)
        
        self._current_trajectory = AttentionTrajectory(
            probabilities=smoothed_probs,
            narrative=narrative,
            confidence=confidence,
            derived_from=derived,
            last_updated=now
        )
        
        return self._current_trajectory

    def _generate_narrative(self, smoothed: Dict[str, float], raw: Dict[str, float]):
        # Find dominant state
        dominant = max(smoothed.items(), key=lambda x: x[1])
        dom_state = dominant[0]
        dom_prob = dominant[1]
        
        derived = [f"smoothed_{dom_state}_{dom_prob:.2f}"]
        
        if dom_state == "deep_work":
            narrative = "The user is in a state of deep, sustained focus."
            if smoothed["recovering"] > 0.2:
                narrative = "The user appears to have re-entered focused work after recent context switching."
                derived.append("recovering_high")
        elif dom_state == "fragmented":
            narrative = "The user's attention is currently fragmented across multiple contexts."
            if raw["deep_work"] > smoothed["deep_work"]:
                narrative = "The user's attention is fragmented, but they are beginning to stabilize on a task."
                derived.append("deep_work_rising")
        elif dom_state == "recovering":
            narrative = "The user is attempting to regain concentration after repeated interruptions."
        else:
            narrative = "The user is currently idle or lightly active."
            
        return narrative, round(dom_prob, 2), derived

    def get_current_trajectory(self) -> AttentionTrajectory:
        return self._current_trajectory
