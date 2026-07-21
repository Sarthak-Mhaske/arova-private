import time
import uuid
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from arova.core.cognition.constants import (
    PRESSURE_COMPOUND_RATE, NOVELTY_DECAY_RATE, PRESSURE_DISSIPATION_RATE,
    MIN_COGNITIVE_PRESSURE_THRESHOLD, FOREGROUND_SURFACING_THRESHOLD, BACKGROUND_SURFACING_THRESHOLD
)

logger = logging.getLogger(__name__)

@dataclass
class CognitiveSignal:
    """A semantic signal vying for runtime attention."""
    source: str
    semantic_type: str
    priority: float
    emotional_weight: float
    visibility: str  # "foreground", "ambient", "silent", "interruptive"
    confidence: float
    decay_rate: float
    interruptible: bool
    payload: dict
    
    # Temporal & Pressure properties
    signal_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: float = field(default_factory=time.time)
    last_surface_time: float = 0.0
    recurrence_count: int = 1
    novelty_score: float = 1.0
    cognitive_pressure: float = 0.0

class CognitivePriorityEngine:
    """
    Arbitrates cognitive signals. Suppresses noise, prevents thematic loops,
    and manages pressure accumulation over time.
    """
    def __init__(self):
        # Active pool of signals currently accumulating or waiting
        self._active_signals: Dict[str, CognitiveSignal] = {}
        
        # History of surfaced signals (used to suppress thematic loops)
        self._surface_history: List[CognitiveSignal] = []
        
        # We track suppressed signals for observability
        self._suppressed_signals: List[CognitiveSignal] = []

    def ingest_signal(self, signal: CognitiveSignal):
        """Intake a new signal from the environment, memory, or planning."""
        # Find if a similar signal is already active
        similar = self._find_similar_active(signal)
        
        if similar:
            # Increase recurrence and pressure
            similar.recurrence_count += 1
            similar.cognitive_pressure += (signal.priority * PRESSURE_COMPOUND_RATE) # Pressure compounds
            similar.confidence = max(similar.confidence, signal.confidence)
            similar.last_surface_time = time.time()
            similar.novelty_score *= NOVELTY_DECAY_RATE # Decays novelty
            logger.debug(f"PriorityEngine: Reinforced signal {similar.semantic_type}. Pressure: {similar.cognitive_pressure:.2f}")
        else:
            # New signal
            signal.cognitive_pressure = signal.priority
            self._active_signals[signal.signal_id] = signal
            logger.debug(f"PriorityEngine: Ingested new signal {signal.semantic_type}. Pressure: {signal.cognitive_pressure:.2f}")

    def arbitrate(self) -> List[CognitiveSignal]:
        """
        Decide which signals get to surface to the LLM/UI in this tick.
        Signals that lose arbitration are either kept as pressure, suppressed, or downgraded.
        """
        now = time.time()
        
        # 1. Decay pressure and drop stale signals
        self._apply_pressure_decay(now)
        
        # 2. Filter candidates that meet the threshold to surface
        candidates = []
        for sig in self._active_signals.values():
            # Basic thresholding (can be more complex)
            threshold = FOREGROUND_SURFACING_THRESHOLD if sig.visibility == "foreground" else BACKGROUND_SURFACING_THRESHOLD
            if sig.cognitive_pressure * sig.confidence > threshold:
                candidates.append(sig)

        if not candidates:
            return []

        # 3. Sort by urgency (pressure * confidence * novelty)
        candidates.sort(key=lambda s: s.cognitive_pressure * s.confidence * s.novelty_score, reverse=True)
        
        surfaced = []
        # Highest priority foreground wins. Others get downgraded or suppressed.
        foreground_claimed = False
        
        for sig in candidates:
            # Check thematic loop suppression
            if self._is_thematic_loop(sig, now):
                self._suppress(sig, "thematic_loop")
                continue

            if sig.visibility in ("foreground", "interruptive"):
                if foreground_claimed:
                    # Downgrade to ambient
                    sig.visibility = "ambient"
                    surfaced.append(sig)
                else:
                    foreground_claimed = True
                    surfaced.append(sig)
            else:
                # Ambient or silent signals can pass through if threshold met
                surfaced.append(sig)
                
            # Update surface tracking
            sig.last_surface_time = now
            self._surface_history.append(sig)
            
            # Reduce pressure heavily after surfacing, but maybe don't delete if it's persistent
            sig.cognitive_pressure *= PRESSURE_DISSIPATION_RATE 
            
        # Keep history bounded
        if len(self._surface_history) > 100:
            self._surface_history = self._surface_history[-50:]
            
        return surfaced

    def _apply_pressure_decay(self, now: float):
        to_remove = []
        for sig_id, sig in self._active_signals.items():
            elapsed = now - sig.created_at
            # Decay pressure over time
            sig.cognitive_pressure -= sig.decay_rate * (elapsed / 60.0)
            
            if sig.cognitive_pressure <= MIN_COGNITIVE_PRESSURE_THRESHOLD:
                to_remove.append(sig_id)
                self._suppress(sig, "pressure_decay")
                
        for rid in to_remove:
            del self._active_signals[rid]

    def _find_similar_active(self, new_signal: CognitiveSignal) -> Optional[CognitiveSignal]:
        # Simple semantic similarity logic for now
        for sig in self._active_signals.values():
            if sig.semantic_type == new_signal.semantic_type and sig.source == new_signal.source:
                # If they share the same core intent payload
                if new_signal.payload.get("intent") == sig.payload.get("intent"):
                    return sig
        return None

    def _is_thematic_loop(self, signal: CognitiveSignal, now: float) -> bool:
        """Prevent Arova from repeating the same semantic theme endlessly."""
        recent = [s for s in self._surface_history if now - s.last_surface_time < 300] # Last 5 mins
        
        # Count how many times this exact semantic type surfaced
        count = sum(1 for s in recent if s.semantic_type == signal.semantic_type)
        
        if count >= 3:
            return True # Suppress
            
        return False

    def _suppress(self, signal: CognitiveSignal, reason: str):
        signal.payload["_suppress_reason"] = reason
        self._suppressed_signals.append(signal)
        if len(self._suppressed_signals) > 50:
            self._suppressed_signals = self._suppressed_signals[-50:]

    def get_inspector_state(self) -> dict:
        return {
            "active_signals": [self._sig_to_dict(s) for s in self._active_signals.values()],
            "suppressed_signals": [self._sig_to_dict(s) for s in self._suppressed_signals[-10:]]
        }

    def _sig_to_dict(self, sig: CognitiveSignal) -> dict:
        return {
            "type": sig.semantic_type,
            "pressure": round(sig.cognitive_pressure, 3),
            "confidence": round(sig.confidence, 3),
            "novelty": round(sig.novelty_score, 3),
            "recurrence": sig.recurrence_count,
            "visibility": sig.visibility,
            "reason": sig.payload.get("_suppress_reason", "")
        }
