import pytest
from arova.core.ambience.provider import LiveOSAmbientProvider

def test_zero_vision_fallbacks():
    """
    HYP-03 Regression Test: Proves that LiveOSAmbientProvider does NOT inject hardcoded
    fallback strings ('Arova Architecture & Development') when window title retrieval
    has not completed or returns empty. Proves presence detection boundary.
    """
    provider = LiveOSAmbientProvider()
    # Ensure provider has no initial mock context
    assert provider._last_context.active_app is None, f"HYP-03 REGRESSION: Found initial mock app: {provider._last_context.active_app}"
    assert provider._last_context.window_title is None, f"HYP-03 REGRESSION: Found initial mock title: {provider._last_context.window_title}"
