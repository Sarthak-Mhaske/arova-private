import time
from enum import Enum
import logging

class CognitiveAtmosphere(Enum):
    CALM = "calm"
    INTENSE = "intense"
    FRAGMENTED = "fragmented"
    EXPLORATORY = "exploratory"
    FATIGUED = "fatigued"
    DECISIVE = "decisive"

class AtmosphereEngine:
    """
    Evaluates session telemetry to determine emotional continuity.
    Uses temporal smoothing (hysteresis) to prevent emotional jitter.
    """
    def __init__(self):
        self.current_atmosphere = CognitiveAtmosphere.CALM
        self.confidence = 0.0 # Confidence in the current atmosphere (0.0 to 1.0)
        
        # Hysteresis trackers
        self.candidate_atmosphere = CognitiveAtmosphere.CALM
        self.candidate_score = 0.0
        self.last_shift_time = time.time()
        
    def evaluate(self, focus_depth: float, interruption_rate: float, silence_debt_size: int, active_execution: bool):
        """
        Periodically evaluate raw telemetry to drift towards a new atmosphere.
        """
        # Determine raw instantaneous state
        raw_target = CognitiveAtmosphere.CALM
        
        if focus_depth > 0.8 and not active_execution:
            raw_target = CognitiveAtmosphere.INTENSE
        elif focus_depth > 0.8 and active_execution:
            raw_target = CognitiveAtmosphere.DECISIVE
        elif interruption_rate > 0.6:
            raw_target = CognitiveAtmosphere.FRAGMENTED
        elif silence_debt_size > 5 and focus_depth < 0.3:
            # High debt but low focus means the user might be exhausted
            raw_target = CognitiveAtmosphere.FATIGUED
        elif focus_depth < 0.5 and not active_execution:
            raw_target = CognitiveAtmosphere.EXPLORATORY
            
        self._apply_hysteresis(raw_target)
        
    def _apply_hysteresis(self, target: CognitiveAtmosphere):
        """
        Requires sustained evidence before officially shifting the atmosphere.
        """
        if target == self.current_atmosphere:
            # Reinforce current state
            self.confidence = min(1.0, self.confidence + 0.1)
            self.candidate_score = 0.0
            return
            
        if target == self.candidate_atmosphere:
            # Build confidence in the shift
            self.candidate_score += 0.2
        else:
            # Reset candidate
            self.candidate_atmosphere = target
            self.candidate_score = 0.2
            
        # If candidate threshold crossed, shift!
        if self.candidate_score >= 1.0:
            time_since_last_shift = time.time() - self.last_shift_time
            if time_since_last_shift > 30.0: # Prevent jitter (min 30s per state)
                logging.info(f"[AtmosphereEngine] Atmosphere shifting to {target.name}")
                self.current_atmosphere = target
                self.confidence = 0.5
                self.candidate_score = 0.0
                self.last_shift_time = time.time()
