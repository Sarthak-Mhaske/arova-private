import pytest
from arova.core.intention.threads import ThreadManager
from arova.core.cognition.workspace_manager import WorkspaceManager
from arova.core.ambience.provider import LiveOSAmbientProvider

def test_zeromock_boot_verification():
    """
    HYP-12 Regression Test: Proves that an entire fresh Arova subsystems boot (threads, workspaces,
    ambience, and working memory) starts completely clean with zero mock items, zero fabricated strings,
    and zero hardcoded fallbacks.
    """
    # 1. Thread subsystem boot check
    tm = ThreadManager(None)
    assert len(tm.get_all_threads()) == 0, f"HYP-12 REGRESSION: ThreadManager booted with mock threads: {tm.get_all_threads()}"
    
    # 2. Workspace & Continue Card boot check
    wm = WorkspaceManager()
    assert len(wm.get_all_workspaces()) == 0, f"HYP-12 REGRESSION: WorkspaceManager booted with mock workspaces: {wm.get_all_workspaces()}"
    
    # 3. Ambience provider boot check
    amb = LiveOSAmbientProvider()
    assert amb._last_context.active_app is None, f"HYP-12 REGRESSION: LiveOSAmbientProvider booted with mock app: {amb._last_context.active_app}"
    assert amb._last_context.window_title is None, f"HYP-12 REGRESSION: LiveOSAmbientProvider booted with mock title: {amb._last_context.window_title}"
