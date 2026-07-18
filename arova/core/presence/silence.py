import time
from dataclasses import dataclass, field
from typing import List, Dict, Any
from arova.core.presence.policy import PresencePolicy, PresenceCooldown

@dataclass
class DeferredWhisper:
    text: str
    urgency: 'WhisperUrgency' # Will be defined in whisper.py
    timestamp: float = field(default_factory=time.time)

class SilenceEngine:
    """
    Evaluates when to suppress presence.
    Tracks Silence Debt and Presence Momentum.
    """
    def __init__(self, policy: PresencePolicy, cooldown: PresenceCooldown):
        self.policy = policy
        self.cooldown = cooldown
        
        self.silence_debt: List[DeferredWhisper] = []
        self.presence_momentum: float = 0.5 # 0.0 (Dormant) to 1.0 (Highly Active)
        self.last_whisper_time: float = 0.0
        self.whispers_this_hour: int = 0
        self.hour_start: float = time.time()
        
        # Adaptive Humility & Recovery Curves
        self.in_retreat: bool = False
        self.retreat_start_time: float = 0.0
        self.recovery_duration: float = 1800.0 # 30 mins to fully recover from a hard retreat
        
    def _update_momentum(self, is_active_execution: bool, prolonged_silence_seconds: float):
        """Scales Arova's temporal activity state."""
        if is_active_execution:
            # Intense execution increases spatial energy
            self.presence_momentum = min(1.0, self.presence_momentum + 0.1)
        else:
            # Prolonged silence lowers orb activity
            decay = (prolonged_silence_seconds / 300) * 0.05 # Decay 5% every 5 mins of silence
            self.presence_momentum = max(0.0, self.presence_momentum - decay)
            
    def check_adaptive_humility(self):
        """Monitors interruption penalty for rapid spikes indicating prolonged frustration."""
        if self.cooldown.interruption_penalty > 8.0 and not self.in_retreat:
            # Graceful Retreat
            self.in_retreat = True
            self.retreat_start_time = time.time()
            self.silence_debt.clear() # Drop banked items, user is stressed
            self.whispers_this_hour = self.policy.max_whispers_per_hour # Zero out budget
            
    def get_recovery_progress(self) -> float:
        """Returns 0.0 to 1.0 indicating how far along the recovery curve we are."""
        if not self.in_retreat:
            return 1.0
            
        elapsed = time.time() - self.retreat_start_time
        if elapsed > self.recovery_duration:
            self.in_retreat = False
            self.cooldown.interruption_penalty = 0.0 # Forgive the debt after full recovery
            return 1.0
            
        return elapsed / self.recovery_duration

    def should_suppress(self, urgency: 'WhisperUrgency', current_focus_depth: float) -> bool:
        """
        Determines if Arova should remain silent.
        """
        self.cooldown.recover() # Process gradual cooldowns
        self.check_adaptive_humility()
        
        # 1. Critical urgency bypasses all silence rules
        if urgency.name == "CRITICAL":
            return False
            
        # If in retreat, aggressively suppress everything else
        if self.in_retreat:
            # Even warnings are suppressed if we just started the retreat (progress < 0.2)
            if urgency.name == "WARNING" and self.get_recovery_progress() > 0.2:
                pass # allow warning
            else:
                return True
                
        # 2. Check Interruption Penalty (Social Restraint)
        if self.cooldown.interruption_penalty > 5.0 and urgency.name != "WARNING":
            return True # User is annoyed, stay quiet unless it's a warning
            
        # 3. Check Deep Work / Focus Depth
        if current_focus_depth > (1.0 - self.policy.interruption_sensitivity):
            # User is focused. Suppress low-urgency whispers.
            if urgency.name in ("AMBIENT", "CONTEXTUAL"):
                return True
            # For extremely sensitive policies (e.g. Deep Work), also suppress ADVISORY
            if self.policy.interruption_sensitivity >= 0.8 and urgency.name == "ADVISORY":
                return True
                
        # 4. Check Whisper Budget
        if time.time() - self.hour_start > 3600:
            self.hour_start = time.time()
            self.whispers_this_hour = 0
            
        if self.whispers_this_hour >= self.policy.max_whispers_per_hour:
            return True
            
        return False
        
    def defer_whisper(self, text: str, urgency: 'WhisperUrgency'):
        """Tracks deferred insights to prevent presence starvation."""
        self.silence_debt.append(DeferredWhisper(text=text, urgency=urgency))
        # Keep debt manageable
        if len(self.silence_debt) > 10:
            self.silence_debt.pop(0)
            
    def flush_debt(self) -> List[str]:
        """Batches contextual insights when silence is lifted."""
        if not self.silence_debt:
            return []
            
        # Compile a summary of deferred items
        compiled = [w.text for w in self.silence_debt]
        self.silence_debt.clear()
        return compiled
        
    def record_whisper(self):
        self.whispers_this_hour += 1
        self.last_whisper_time = time.time()
        self._update_momentum(is_active_execution=True, prolonged_silence_seconds=0)
