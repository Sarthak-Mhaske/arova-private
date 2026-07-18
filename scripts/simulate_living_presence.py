import time
import os
import shutil
import logging
from arova.core.presence.journal import PresenceReflection, PresenceJournalSystem
from arova.core.presence.trust_calibration import EarnedTrustScaling, PresenceResilienceMetrics
from arova.core.presence.silence import SilenceEngine
from arova.core.presence.policy import get_policy_for_mode, PresenceMode, PresenceCooldown
from arova.core.presence.whisper import WhisperUrgency

logging.basicConfig(level=logging.INFO, format='%(message)s')

def simulate_graceful_retreat():
    print("\n=== Test 1: Adaptive Humility (Graceful Retreat) ===")
    policy = get_policy_for_mode(PresenceMode.CONVERSATIONAL)
    cooldown = PresenceCooldown()
    silence = SilenceEngine(policy, cooldown)
    
    # Simulate rapid frustration (dismissing multiple whispers quickly)
    print("User is highly frustrated, repeatedly dismissing Arova...")
    cooldown.apply_penalty(4.0)
    cooldown.apply_penalty(5.0) # Penalty now 9.0
    
    silence.check_adaptive_humility()
    
    assert silence.in_retreat is True, "SilenceEngine should enter retreat mode on high interruption penalty."
    print("✓ Passed: Arova initiated Graceful Retreat (FATIGUED/SILENT clamped).")
    
    # Try to whisper during retreat
    suppressed = silence.should_suppress(WhisperUrgency.CONTEXTUAL, current_focus_depth=0.5)
    assert suppressed is True, "Should aggressively suppress whispers during early retreat."
    print("✓ Passed: Contextual whispers aggressively suppressed during retreat.")
    
    # Simulate time passing for recovery curve
    silence.retreat_start_time -= 1000.0 # Fast-forward 1000s
    progress = silence.get_recovery_progress()
    print(f"Recovery progress: {progress * 100:.1f}%")
    assert 0.0 < progress < 1.0, "Recovery curve should be gradual."
    print("✓ Passed: Recovery Curve successfully throttling presence restoration.")

def simulate_journal_and_trust():
    print("\n=== Test 2: Presence Journaling & Trust Scaling ===")
    
    # Use a temporary journal directory for the test
    test_dir = "/tmp/arova_test_journals"
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)
        
    journal = PresenceJournalSystem(journal_dir=test_dir)
    
    # Simulate positive interactions
    ref1 = PresenceReflection(time.time() - 100, "code_review", "focused", "ambient_hint", 0.0, 0.8, 0.1, 0.5)
    ref2 = PresenceReflection(time.time() - 50, "git_status", "exploratory", "contextual_whisper", 0.0, 0.9, 0.0, 0.2)
    journal.record_reflection(ref1)
    journal.record_reflection(ref2)
    
    reflections = journal.read_valid_reflections()
    assert len(reflections) == 2, "Journal should store and retrieve valid reflections."
    
    metrics = PresenceResilienceMetrics(reflections)
    trust_engine = EarnedTrustScaling()
    
    initial_trust = trust_engine.trust_multiplier
    trust_engine.recalibrate(metrics)
    
    assert trust_engine.trust_multiplier > initial_trust, "Trust should scale up on positive reflections."
    print("✓ Passed: Earned Trust Scaling successfully relaxed predictive thresholds.")
    
    # Cleanup
    shutil.rmtree(test_dir)

if __name__ == "__main__":
    simulate_graceful_retreat()
    simulate_journal_and_trust()
    print("\nAll Living Validation Tests Passed. Arova is emotionally sustainable.")
