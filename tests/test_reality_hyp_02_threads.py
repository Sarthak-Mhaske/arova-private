import pytest
from arova.core.intention.threads import ThreadManager

def test_zero_startup_mock_threads():
    """
    HYP-02 Regression Test: Proves that ThreadManager does NOT inject any hardcoded or mock threads on startup.
    If zero threads exist empirically, zero threads must be rendered.
    """
    tm = ThreadManager(None)
    assert len(tm._threads) == 0, f"HYP-02 REGRESSION: Expected 0 threads on boot, found {len(tm._threads)}"
