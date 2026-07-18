import logging
from dataclasses import dataclass
from typing import Dict, Any

from arova.core.environment.trajectory import AttentionTrajectory

logger = logging.getLogger(__name__)

@dataclass
class PresenceProfile:
    """The behavioral configuration that drives Arova's interaction style."""
    verbosity: str                # e.g. "concise", "normal", "elaborate"
    cadence: str                  # e.g. "soft", "calming", "brisk", "normal"
    emotional_temperature: str    # e.g. "warm", "neutral", "clinical", "encouraging"
    interruption_sensitivity: float # 0.0 to 1.0 (how easily Arova yields)
    ambient_density: float        # 0.0 to 1.0 (how often to show UI fragments/ghosts)

class PresenceModulator:
    """
    Translates attention trajectories, environment graphs, and cognitive priority 
    into a behavioral presence profile.
    """
    def __init__(self):
        self._current_profile = PresenceProfile(
            verbosity="normal",
            cadence="normal",
            emotional_temperature="neutral",
            interruption_sensitivity=0.5,
            ambient_density=0.5
        )
        
    def modulate(self, trajectory: AttentionTrajectory, graph_derived: Dict[str, Any]) -> PresenceProfile:
        """
        Calculates a new PresenceProfile based on cognitive state.
        """
        probs = trajectory.probabilities
        
        # Defaults
        verbosity = "normal"
        cadence = "normal"
        emotional = "neutral"
        sensitivity = 0.5
        density = 0.5
        
        # Modulation rules
        if probs.get("deep_work", 0) > 0.6:
            verbosity = "concise"
            cadence = "soft"
            emotional = "clinical"
            sensitivity = 0.9 # Yield easily to not interrupt flow
            density = 0.2     # Reduce visual noise
        elif probs.get("fragmented", 0) > 0.6:
            verbosity = "normal"
            cadence = "calming"
            emotional = "warm"
            sensitivity = 0.6
            density = 0.8     # Show ambient signals to try to anchor attention
        elif probs.get("recovering", 0) > 0.4:
            verbosity = "concise"
            cadence = "encouraging"
            emotional = "warm"
            sensitivity = 0.7
            density = 0.4
            
        # Workspace type influence
        workspace = graph_derived.get("current_workspace_type", "unknown")
        if workspace == "knowledge_synthesis":
            verbosity = "elaborate"
            emotional = "encouraging"
            
        self._current_profile = PresenceProfile(
            verbosity=verbosity,
            cadence=cadence,
            emotional_temperature=emotional,
            interruption_sensitivity=sensitivity,
            ambient_density=density
        )
        
        logger.debug(f"PresenceModulator: updated profile to verbosity={verbosity}, cadence={cadence}")
        return self._current_profile

    def get_current_profile(self) -> PresenceProfile:
        return self._current_profile
