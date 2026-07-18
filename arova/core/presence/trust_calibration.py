import math
from typing import List
from arova.core.presence.journal import PresenceReflection

class PresenceResilienceMetrics:
    """
    The real KPI layer for Human-AI coexistence.
    Calculates psychological metrics over the journal history.
    """
    def __init__(self, reflections: List[PresenceReflection]):
        self.reflections = reflections

    @property
    def annoyance_half_life(self) -> float:
        """How quickly does user annoyance decay after a mistake?"""
        # In a real system, would calculate time between annoyance peaks and recovery.
        # For MVP, we return a mock inverse to average annoyance.
        avg_annoyance = sum(r.annoyance_score for r in self.reflections) / max(1, len(self.reflections))
        return 1.0 - avg_annoyance

    @property
    def ambient_acceptance_rate(self) -> float:
        """Percentage of proactive actions that were NOT dismissed/annoying."""
        if not self.reflections:
            return 1.0
        accepted = sum(1 for r in self.reflections if r.annoyance_score < 0.3)
        return accepted / len(self.reflections)

class EarnedTrustScaling:
    """
    Relaxes predictive thresholds slowly as trust is earned.
    Trust is hard to earn, easy to lose.
    """
    def __init__(self, base_trust_multiplier: float = 1.0):
        self.trust_multiplier = base_trust_multiplier
        
    def recalibrate(self, metrics: PresenceResilienceMetrics):
        """
        Adjust the trust multiplier based on resilience metrics.
        Multiplier > 1.0 means Arova is trusted to be more proactive.
        Multiplier < 1.0 means Arova is strictly restricted.
        """
        acceptance = metrics.ambient_acceptance_rate
        
        if acceptance > 0.9:
            # Earned trust slowly increases
            self.trust_multiplier = min(1.5, self.trust_multiplier + 0.05)
        elif acceptance < 0.5:
            # Trust collapses quickly
            self.trust_multiplier = max(0.5, self.trust_multiplier - 0.2)
            
    def apply_to_threshold(self, base_threshold: float) -> float:
        """
        Returns the adjusted threshold. Higher trust multiplier LOWERS the threshold
        required to act proactively.
        """
        return base_threshold / self.trust_multiplier
