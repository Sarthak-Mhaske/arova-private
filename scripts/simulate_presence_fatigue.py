import time
import logging
import sys

from arova.core.presence.policy import PresenceMode, PresenceCooldown, get_policy_for_mode
from arova.core.presence.silence import SilenceEngine
from arova.core.presence.whisper import WhisperEngine, WhisperUrgency

logging.basicConfig(level=logging.INFO, format='%(message)s')

class MockEventBus:
    def __init__(self):
        self.emitted_whispers = []
        
    def publish(self, event_type, payload):
        if event_type == "PRESENCE_WHISPER":
            self.emitted_whispers.append(payload)
            logging.info(f"   [UI RENDER] {payload['urgency'].upper()}: {payload['text']}")

def simulate_interruption_fatigue():
    print("\n=== Test 1: Interruption Fatigue & Social Restraint ===")
    policy = get_policy_for_mode(PresenceMode.CONVERSATIONAL)
    cooldown = PresenceCooldown()
    silence_engine = SilenceEngine(policy, cooldown)
    bus = MockEventBus()
    whisper_engine = WhisperEngine(silence_engine, bus)
    
    print("Arova emits a conversational whisper...")
    whisper_engine.emit("I noticed you opened VS Code.", WhisperUrgency.CONTEXTUAL, current_focus_depth=0.2)
    
    print("User dismisses/interrupts Arova heavily (Penalty +6)...")
    cooldown.apply_penalty(6.0)
    
    print("Arova attempts another conversational whisper...")
    whisper_engine.emit("Would you like me to fetch the docs?", WhisperUrgency.CONTEXTUAL, current_focus_depth=0.2)
    
    print("Arova attempts a WARNING whisper...")
    whisper_engine.emit("High memory usage detected.", WhisperUrgency.WARNING, current_focus_depth=0.2)
    
    assert len(bus.emitted_whispers) == 2, "Should have emitted 1 contextual and 1 warning whisper, dropping the second contextual."
    print("✓ Passed: Interruption penalty successfully suppressed non-critical whispers.")

def simulate_deep_work_debt():
    print("\n=== Test 2: Deep Work & Silence Debt ===")
    policy = get_policy_for_mode(PresenceMode.DEEP_WORK)
    cooldown = PresenceCooldown()
    silence_engine = SilenceEngine(policy, cooldown)
    bus = MockEventBus()
    whisper_engine = WhisperEngine(silence_engine, bus)
    
    print("User enters Deep Work (Focus Depth 0.95)...")
    whisper_engine.emit("Repository analysis complete.", WhisperUrgency.ADVISORY, current_focus_depth=0.95)
    whisper_engine.emit("Lint errors found in 3 files.", WhisperUrgency.ADVISORY, current_focus_depth=0.95)
    
    assert len(bus.emitted_whispers) == 0, "Should not emit advisory whispers during deep work."
    assert len(silence_engine.silence_debt) == 2, "Whispers should be deferred to silence debt."
    print("✓ Passed: Whispers correctly suppressed and deferred.")
    
    print("User focus drops (Focus Depth 0.2)... Flushing debt...")
    whisper_engine.check_debt()
    assert len(bus.emitted_whispers) == 1, "Should have emitted 1 combined summary whisper."
    print("✓ Passed: Silence debt flushed successfully.")

if __name__ == "__main__":
    simulate_interruption_fatigue()
    simulate_deep_work_debt()
    print("\nAll Presence Simulation Tests Passed. Psychological boundaries verified.")
