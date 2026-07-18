import logging
import time
from typing import Optional
from arova.core.intention.graph import IntentGraph
from arova.core.intention.threads import ThreadManager
from arova.core.environment.trajectory import AttentionTrajectory

logger = logging.getLogger(__name__)

class PlanningContinuityEngine:
    """
    Opportunistically surfaces dormant threads and intents when cognitive alignment is high.
    It calculates 'continuity resonance' based on attention state and environment.
    """
    def __init__(self, intent_graph: IntentGraph, thread_manager: ThreadManager, event_bus=None):
        self.intent_graph = intent_graph
        self.thread_manager = thread_manager
        self.event_bus = event_bus
        self.last_evaluation = 0.0
        
    def evaluate_resonance(self, trajectory: AttentionTrajectory, environment_snapshot: dict):
        """
        Evaluate if we should surface any latent threads or deferred intents.
        Should be called periodically or when environment stabilizes.
        """
        now = time.time()
        if now - self.last_evaluation < 30.0: # Enforce 30s cooldown between evaluations
            return
            
        self.last_evaluation = now
        probs = trajectory.probabilities
        
        # We only surface opportunistically when the user is not actively deep_work or fragmented
        if probs.get("deep_work", 0.0) > 0.4 or probs.get("fragmented", 0.0) > 0.5:
            return # Too busy or too distracted
            
        # User is somewhat idle or recovering, perfect time for continuity
        
        # 1. Evaluate dormant threads
        latent_threads = self.thread_manager.get_threads_by_state("latent")
        best_thread = None
        highest_resonance = 0.0
        
        for thread in latent_threads:
            resonance = self._calculate_thread_resonance(thread, environment_snapshot)
            if resonance > highest_resonance:
                highest_resonance = resonance
                best_thread = thread
                
        # 2. Evaluate high-pressure deferred intents
        high_pressure_intents = [i for i in self.intent_graph.get_all_intents() if i.status == "paused" and i.pressure > 0.6]
        
        if highest_resonance > 0.7 and best_thread and self.event_bus:
            logger.info(f"ContinuityEngine: Surfacing latent thread '{best_thread.title}' [Resonance: {highest_resonance:.2f}]")
            # Spike the resonance temporarily and accumulate fatigue
            best_thread.continuity_resonance = highest_resonance
            best_thread.surface_fatigue = min(1.0, best_thread.surface_fatigue + 0.3)
            
            # Emit signal to PriorityEngine
            self.event_bus.emit("intention", "CONTINUITY_RESONANCE_SPIKE", {
                "source": "continuity_engine",
                "semantic_type": "THREAD_RESURFACED",
                "confidence": highest_resonance,
                "payload": {
                    "thread_id": best_thread.thread_id,
                    "title": best_thread.title,
                    "resonance": highest_resonance
                }
            })
            # Once surfaced, we shouldn't spam it. 
            # PriorityEngine will handle suppression if it's surfaced too often.

    def _calculate_thread_resonance(self, thread, env_snap: dict) -> float:
        resonance = 0.0
        
        if not thread.continuity_snapshot:
            return 0.1
            
        snap = thread.continuity_snapshot
        snap_env = snap.environment_context
        current_derived = env_snap.get("_derived", {})
        
        # 1. Workspace Similarity (High weight)
        if snap_env.get("workspace") == current_derived.get("current_workspace_type"):
            resonance += 0.4
            
        # 2. Temporal Proximity (Medium weight)
        elapsed = time.time() - snap.timestamp
        if elapsed < 3600:
            resonance += 0.2
        elif elapsed < 86400:
            resonance += 0.1
            
        # 3. Unresolved Pressure (High weight)
        resonance += (snap.active_pressures * 0.3)
        
        # 4. Continuity Entropy (Penalty for fragmented threads)
        resonance -= (snap.continuity_entropy * 0.2)
        
        # 5. Surface Fatigue Damping (Critical)
        fatigue_penalty = thread.surface_fatigue * 0.5
        resonance -= fatigue_penalty
        
        return max(0.0, min(1.0, resonance))
