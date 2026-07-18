import time
import logging
from typing import List, Dict
from dataclasses import dataclass, field
from arova.core.platform.windowing.base import RawWindowData
from arova.core.environment.semantics import SemanticProvider, SemanticContext

logger = logging.getLogger(__name__)

@dataclass
class SemanticProbabilities:
    implementation: float = 0.0
    synthesis: float = 0.0
    exploration: float = 0.0
    fragmentation: float = 0.0
    planning: float = 0.0
    recovery: float = 0.0
    passive: float = 0.0

@dataclass(kw_only=True)
class ProbabilisticSemanticContext(SemanticContext):
    probabilities: SemanticProbabilities = field(default_factory=SemanticProbabilities)
    mode_velocity: float = 0.0
    mode_stability: float = 1.0

class WorkspaceSemanticAnalyzer(SemanticProvider):
    """
    Phase 4: Semantic Workspace Intelligence.
    Infers probabilistic cognitive modes based on app compositions, dwelling, and switching.
    Incorporates temporal stability (inertia) to prevent rapid mode oscillation.
    """
    def __init__(self):
        self._class_mapping = {
            "code": "implementation",
            "vscode": "implementation",
            "cursor": "implementation",
            "konsole": "implementation",
            "alacritty": "implementation",
            "kitty": "implementation",
            "wezterm": "implementation",
            
            "obsidian": "synthesis",
            "notion": "synthesis",
            "figma": "synthesis",
            
            "firefox": "exploration",
            "chrome": "exploration",
            "brave": "exploration",
            
            "discord": "passive",
            "slack": "passive",
            "spotify": "passive",
            "vlc": "passive"
        }
        
        self._last_context = ProbabilisticSemanticContext(
            role="passive", 
            confidence=1.0, 
            probabilities=SemanticProbabilities(passive=1.0)
        )
        self._window_history = []
        self._last_switch_time = time.time()
        
    async def classify(self, windows: List[RawWindowData]) -> ProbabilisticSemanticContext:
        if not windows:
            return self._last_context
            
        now = time.time()
        
        # 1. Base Probabilities from topology
        base_probs = {"implementation": 0.0, "synthesis": 0.0, "exploration": 0.0, "passive": 0.0, "fragmentation": 0.0, "planning": 0.0, "recovery": 0.0}
        total_weight = 0
        
        for w in windows:
            cls_lower = w.app_class.lower()
            role = self._class_mapping.get(cls_lower, "exploration") # Default unknown to exploration
            base_probs[role] += 1.0
            total_weight += 1.0
            
        if total_weight > 0:
            for k in base_probs:
                base_probs[k] /= total_weight
                
        # 2. Heuristics for Fragmentation vs Exploration
        # If there's a lot of rapid switching (simulated here by looking at just topology changes without true switch tracking)
        # Actually, let's track switch velocity. We'll assume `classify` is called when focus or topology changes.
        time_since_last = now - self._last_switch_time
        self._last_switch_time = now
        
        velocity = 1.0 / max(time_since_last, 0.1) # Switches per second
        
        # Damp velocity with EMA
        current_velocity = (self._last_context.mode_velocity * 0.8) + (velocity * 0.2)
        
        # If velocity is high, bleed exploration into fragmentation
        if current_velocity > 0.5:
            fragment_bleed = min(0.8, (current_velocity - 0.5) * 0.5)
            base_probs["fragmentation"] += base_probs["exploration"] * fragment_bleed
            base_probs["exploration"] *= (1.0 - fragment_bleed)
            
        # 3. Temporal Stability (Inertia)
        # We blend the new probabilities with the old ones based on stability.
        # If we've been in a stable mode, resist change.
        inertia = min(0.9, self._last_context.mode_stability * 0.95) # High stability = high inertia
        
        if current_velocity > 1.0:
            inertia *= 0.5 # Fast switching breaks inertia quickly
            
        blended_probs = SemanticProbabilities()
        
        # Blend each probability
        max_role = "passive"
        max_prob = 0.0
        
        for field_name in base_probs:
            old_val = getattr(self._last_context.probabilities, field_name)
            new_val = base_probs[field_name]
            blended_val = (old_val * inertia) + (new_val * (1.0 - inertia))
            setattr(blended_probs, field_name, blended_val)
            
            if blended_val > max_prob:
                max_prob = blended_val
                max_role = field_name
                
        # Update Stability: if the max role changed, stability drops. If it stayed same, it grows.
        new_stability = self._last_context.mode_stability
        if max_role == self._last_context.role:
            new_stability = min(1.0, new_stability + 0.1)
        else:
            new_stability = 0.2 # Dropped stability on mode flip
            
        self._last_context = ProbabilisticSemanticContext(
            role=max_role,
            confidence=max_prob,
            probabilities=blended_probs,
            mode_velocity=current_velocity,
            mode_stability=new_stability,
            last_updated=now
        )
        
        return self._last_context
