import time
import logging
from arova.core.cognition.warmup import ContextPrewarmer, MultiTierWarmth
from arova.core.presence.ethics import EthicsEngine, PredictiveSignal
from arova.core.presence.atmosphere import AtmosphereEngine

logging.basicConfig(level=logging.INFO, format='%(message)s')

def simulate_context_warmup():
    print("\n=== Test 1: Multi-Tier Cognitive Warmth ===")
    warmer = ContextPrewarmer()
    assert warmer.current_tier == MultiTierWarmth.COLD
    
    print("User opens VSCode (Environment Shift)...")
    warmer.handle_environment_shift("code_workspace", "Code")
    assert warmer.current_tier == MultiTierWarmth.SEMANTIC
    
    # Check Predictive Cache Topology
    cached = warmer.cache.get("development")
    assert cached["semantic_vectors_loaded"] is True
    assert cached["likely_intent_graph"] == "development_workflow_skeleton"
    print("✓ Passed: Semantic Cache explicitly warmed without inferencing (Tier 1).")
    
    print("User pauses typing heavily (Wake Word proximity)...")
    warmer.escalate_to_intent()
    assert warmer.current_tier == MultiTierWarmth.INTENT
    print("✓ Passed: Hydrating prompt templates silently (Tier 2).")

def simulate_ethics_spam_protection():
    print("\n=== Test 2: Presence Ethics & Familiarity Decay ===")
    engine = EthicsEngine()
    
    # First time seeing VSCode open, might be useful to surface
    signal = PredictiveSignal(
        topic="workspace_setup",
        confidence=0.9,
        utility_score=0.8,
        psychological_cost=0.5 # Normal focus
    )
    
    decision = engine.should_surface_prediction(signal)
    assert decision is True, "First time highly confident prediction should surface."
    print("✓ Passed: Surfaced useful prediction.")
    
    # Second time quickly after, utility drops due to familiarity decay
    decision2 = engine.should_surface_prediction(signal)
    assert decision2 is False, "Should suppress repetitive prediction due to familiarity decay."
    print("✓ Passed: Familiarity tracker vetoed predictive narration spam.")

def simulate_emotional_hysteresis():
    print("\n=== Test 3: Emotional Continuity Hysteresis ===")
    atmosphere = AtmosphereEngine()
    
    print("Simulating rapid app switching (High Interruption Rate)...")
    # Simulate multiple evaluations
    atmosphere.evaluate(focus_depth=0.2, interruption_rate=0.9, silence_debt_size=0, active_execution=False)
    assert atmosphere.current_atmosphere.name == "CALM", "Atmosphere should not shift immediately (Jitter prevention)."
    
    atmosphere.evaluate(focus_depth=0.2, interruption_rate=0.9, silence_debt_size=0, active_execution=False)
    atmosphere.evaluate(focus_depth=0.2, interruption_rate=0.9, silence_debt_size=0, active_execution=False)
    atmosphere.evaluate(focus_depth=0.2, interruption_rate=0.9, silence_debt_size=0, active_execution=False)
    atmosphere.evaluate(focus_depth=0.2, interruption_rate=0.9, silence_debt_size=0, active_execution=False)
    import unittest.mock
    with unittest.mock.patch('time.time', return_value=time.time() + 35.0):
        atmosphere.evaluate(focus_depth=0.2, interruption_rate=0.9, silence_debt_size=0, active_execution=False) # Should hit candidate_score >= 1.0
    
    assert atmosphere.current_atmosphere.name == "FRAGMENTED", f"Atmosphere should eventually shift after sustained telemetry. Got {atmosphere.current_atmosphere.name}"
    print("✓ Passed: Atmosphere gracefully shifted to FRAGMENTED with hysteresis protection.")

if __name__ == "__main__":
    simulate_context_warmup()
    simulate_ethics_spam_protection()
    simulate_emotional_hysteresis()
    print("\nAll Predictive Presence Simulation Tests Passed. The uncanny valley has been avoided.")
