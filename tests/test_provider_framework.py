import asyncio
import logging
import time

from arova.core.config.awareness import AwarenessManager, AwarenessPolicy
from arova.core.cognition.providers.manager import ProviderManager
from arova.core.cognition.providers.window_provider import WindowObserverProvider
from arova.core.platform.windowing.base import WindowingBackend
from dataclasses import dataclass

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

@dataclass
class MockWindow:
    app_class: str
    title: str

class MockWindowBackend(WindowingBackend):
    def __init__(self):
        self.mock_window = MockWindow(app_class="vscode", title="manager.py - Arova")
        
    async def get_active_window(self):
        return self.mock_window
        
    async def subscribe_events(self):
        pass

async def test_provider_framework():
    print("\n--- TEST 1: Initialization & Registration ---")
    awareness_mgr = AwarenessManager()
    provider_mgr = ProviderManager(awareness_mgr)
    
    mock_backend = MockWindowBackend()
    window_provider = WindowObserverProvider(mock_backend)
    
    provider_mgr.register(window_provider)
    print(f"Registered Providers: {[p.get_id() for p in provider_mgr._providers.values()]}")
    
    print("\n--- TEST 2: Capability Gating (Presence Enabled) ---")
    # By default, Presence is enabled
    awareness_mgr.policy.presence.enabled = True
    active = provider_mgr.get_active_providers()
    print(f"Active Providers: {[p.get_id() for p in active]}")
    assert len(active) == 1, "WindowObserverProvider should be active."
    
    print("\n--- TEST 3: Polling for Context Fragments ---")
    fragments = await provider_mgr.poll()
    print(f"Polled Fragments: {len(fragments)}")
    assert len(fragments) == 1, "Should poll 1 fragment."
    frag = fragments[0]
    print(f"Fragment Data:\n  Provider: {frag.provider_id}\n  Activity: {frag.activity_summary}\n  Source: {frag.source_identity}\n  Tags: {frag.tags}")
    assert "development" in frag.tags, "Tags should correctly map vscode to development."
    
    print("\n--- TEST 4: Capability Gating (Presence Disabled) ---")
    # Now simulate user toggling off the Presence tier
    awareness_mgr.update_layer("presence", False)
    active = provider_mgr.get_active_providers()
    print(f"Active Providers: {[p.get_id() for p in active]}")
    assert len(active) == 0, "Provider should be inactive when Presence is disabled."
    
    fragments = await provider_mgr.poll()
    print(f"Polled Fragments: {len(fragments)}")
    assert len(fragments) == 0, "Should poll 0 fragments when capability is off."
    
    print("\n--- TEST 5: Visible Context UI Payload ---")
    # Re-enable
    awareness_mgr.update_layer("presence", True)
    
    visible = await provider_mgr.get_visible_context()
    print("Visible Context for UI:")
    for v in visible:
        print(f"  - {v}")
    assert len(visible) == 1, "Should have 1 visible item."
    assert visible[0]["provider"] == "Window Observer"
    
    print("\n✅ All Rigid Backend Tests Passed.")

if __name__ == "__main__":
    asyncio.run(test_provider_framework())
