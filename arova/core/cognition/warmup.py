import logging
import time
from enum import Enum
from typing import Dict, Any

class MultiTierWarmth(Enum):
    COLD = 0        # Minimal daemon footprint
    SEMANTIC = 1    # CPU-only: Memory prefetch, Qdrant vectors, graph skeleton
    INTENT = 2      # Hydrating templates, establishing session (delayed inference)
    ACTIVE = 3      # Active Ollama generation

class PredictiveCacheTopology:
    """
    Holds prewarmed context to provide zero-latency access when the user finally interacts.
    """
    def __init__(self):
        self.semantic_cache: Dict[str, Any] = {}
        self.last_warmed_time = 0.0
        
    def populate(self, trigger_source: str, context: dict):
        if len(self.semantic_cache) >= 50 and trigger_source not in self.semantic_cache:
            first_key = next(iter(self.semantic_cache))
            del self.semantic_cache[first_key]
        self.semantic_cache[trigger_source] = context
        self.last_warmed_time = time.time()
        
    def get(self, trigger_source: str) -> dict:
        # Cache expires after 10 minutes of inactivity
        if time.time() - self.last_warmed_time > 600:
            self.semantic_cache.clear()
            return {}
        return self.semantic_cache.get(trigger_source, {})

class ContextPrewarmer:
    """
    Silently loads context based on environmental shifts without invoking inference models.
    """
    def __init__(self):
        self.cache = PredictiveCacheTopology()
        self.current_tier = MultiTierWarmth.COLD
        
    def handle_environment_shift(self, active_window: str, window_class: str):
        """
        Triggered by Phase 10's AmbientIntent.
        """
        # Tier 1: Semantic Prewarm
        if "Code" in window_class or "Terminal" in window_class:
            self._prewarm_semantic_layer("development", active_window)
        elif "Firefox" in window_class or "Chrome" in window_class:
            self._prewarm_semantic_layer("research", active_window)
        else:
            self.current_tier = MultiTierWarmth.COLD
            
    def _prewarm_semantic_layer(self, domain: str, focus: str):
        self.current_tier = MultiTierWarmth.SEMANTIC
        logging.info(f"[Warmup] Tier 1 Semantic Prewarm started for domain: {domain}")
        
        # Simulate CPU-bound prefetching (e.g., querying Qdrant, retrieving Git status)
        time.sleep(0.1) 
        
        prefetched_data = {
            "domain": domain,
            "focus": focus,
            "likely_intent_graph": f"{domain}_workflow_skeleton",
            "semantic_vectors_loaded": True
        }
        self.cache.populate(domain, prefetched_data)
        logging.info(f"[Warmup] Tier 1 completed. Cache populated. Inference remains DORMANT.")
        
    def escalate_to_intent(self):
        """Called when wake word is proximity detected or user pauses typing significantly."""
        if self.current_tier.value >= MultiTierWarmth.SEMANTIC.value:
            self.current_tier = MultiTierWarmth.INTENT
            logging.info("[Warmup] Tier 2 Intent Warmth: Hydrating prompt templates...")
            
    def escalate_to_active(self):
        """Called only on explicit user request."""
        self.current_tier = MultiTierWarmth.ACTIVE
        logging.info("[Warmup] Tier 3 Active Cognition: Inference allocated.")
