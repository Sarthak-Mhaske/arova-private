import abc
import time
from typing import List
from dataclasses import dataclass, field
from arova.core.platform.windowing.base import RawWindowData

@dataclass(kw_only=True)
class SemanticContext:
    role: str
    confidence: float
    last_updated: float = field(default_factory=time.time)

class SemanticProvider(abc.ABC):
    @abc.abstractmethod
    async def classify(self, windows: List[RawWindowData]) -> SemanticContext:
        """Classify a group of windows (e.g. a workspace) into a semantic context."""
        pass

class HeuristicSemanticProvider(SemanticProvider):
    def __init__(self):
        # We map known app classes/titles to semantic domains
        # This is a fast, 0-latency heuristic baseline
        self._class_mapping = {
            "code": "development",
            "vscode": "development",
            "cursor": "development",
            "konsole": "development",
            "alacritty": "development",
            "kitty": "development",
            
            "firefox": "research",
            "chrome": "research",
            "brave": "research",
            
            "obsidian": "knowledge",
            "notion": "knowledge",
            
            "discord": "communication",
            "slack": "communication",
            "teams": "communication",
            
            "spotify": "media",
            "vlc": "media"
        }
        
        # Hysteresis state
        self._last_context = SemanticContext(role="idle", confidence=1.0)
        
    async def classify(self, windows: List[RawWindowData]) -> SemanticContext:
        if not windows:
            return SemanticContext(role="idle", confidence=1.0)
            
        role_scores = {}
        for w in windows:
            cls_lower = w.app_class.lower()
            role = self._class_mapping.get(cls_lower, "unknown")
            
            # Simple scoring: focused window (if we knew which it was) gets more weight, 
            # but here we just look at co-occurrence.
            role_scores[role] = role_scores.get(role, 0) + 1
            
        # Topology rules
        # e.g., development + research = development_workflow
        has_dev = "development" in role_scores
        has_research = "research" in role_scores
        has_comm = "communication" in role_scores
        
        predicted_role = "unknown"
        if has_dev and has_research:
            predicted_role = "research_assisted_development"
        elif has_dev:
            predicted_role = "development"
        elif has_research and "knowledge" in role_scores:
            predicted_role = "knowledge_synthesis"
        elif has_research:
            predicted_role = "research"
        elif has_comm:
            predicted_role = "communication"
        else:
            # Fallback to majority
            if role_scores:
                predicted_role = max(role_scores, key=role_scores.get)
                
        # Semantic Hysteresis: only switch if the new role is different AND 
        # we've been in the old role for a bit, OR it's a strong signal.
        # For this MVP, we'll just apply a time-based dampener if needed,
        # but for now, direct update.
        
        now = time.time()
        if predicted_role != self._last_context.role:
            # If less than 2 seconds since last change, resist change (hysteresis)
            if now - self._last_context.last_updated < 2.0:
                return self._last_context
                
            self._last_context = SemanticContext(
                role=predicted_role, 
                confidence=0.8,
                last_updated=now
            )
            
        return self._last_context
