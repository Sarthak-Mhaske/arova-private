from enum import Enum
from dataclasses import dataclass, field
import time

class PresenceMode(Enum):
    SILENT = "silent"                 # Minimal activity
    AMBIENT = "ambient"               # Orb only, no narration
    CONVERSATIONAL = "conversational" # Rich narration, active whispering
    DEEP_WORK = "deep_work"           # Nearly invisible, maximum silence debt buildup
    OBSERVATORY = "observatory"       # Maximum trace visibility for debugging/tracing

@dataclass
class PresenceCooldown:
    """Tracks social restraint to prevent annoyance."""
    whisper_decay_rate: float = 0.1         # Rate at which whisper readiness recovers
    animation_decay_rate: float = 0.05
    interruption_penalty: float = 0.0       # Grows when user dismisses or ignores Arova
    last_interruption_time: float = field(default_factory=time.time)
    
    def apply_penalty(self, severity: float = 1.0):
        self.interruption_penalty += severity
        self.last_interruption_time = time.time()
        
    def recover(self):
        # Gradual recovery of trust/presence bandwidth over time
        elapsed = time.time() - self.last_interruption_time
        if elapsed > 60:  # 1 minute cooldown
            recovery = (elapsed / 60) * self.whisper_decay_rate
            self.interruption_penalty = max(0.0, self.interruption_penalty - recovery)
            self.last_interruption_time = time.time()

@dataclass
class PresencePolicy:
    """Governs the boundaries of Arova's presence."""
    mode: PresenceMode
    max_whispers_per_hour: int
    interruption_sensitivity: float # 0.0 to 1.0 (Higher means Arova gets quiet faster)
    narration_density: float        # 0.0 to 1.0 (How many cognitive states map to UI feed)
    silence_priority: float         # 0.0 to 1.0 (How aggressively to suppress presence)

def get_policy_for_mode(mode: PresenceMode) -> PresencePolicy:
    if mode == PresenceMode.DEEP_WORK:
        return PresencePolicy(mode, max_whispers_per_hour=2, interruption_sensitivity=0.9, narration_density=0.1, silence_priority=0.9)
    if mode == PresenceMode.SILENT:
        return PresencePolicy(mode, max_whispers_per_hour=0, interruption_sensitivity=1.0, narration_density=0.0, silence_priority=1.0)
    if mode == PresenceMode.CONVERSATIONAL:
        return PresencePolicy(mode, max_whispers_per_hour=20, interruption_sensitivity=0.3, narration_density=0.8, silence_priority=0.2)
    if mode == PresenceMode.OBSERVATORY:
        return PresencePolicy(mode, max_whispers_per_hour=50, interruption_sensitivity=0.0, narration_density=1.0, silence_priority=0.0)
    # Default AMBIENT
    return PresencePolicy(mode, max_whispers_per_hour=10, interruption_sensitivity=0.6, narration_density=0.4, silence_priority=0.5)
