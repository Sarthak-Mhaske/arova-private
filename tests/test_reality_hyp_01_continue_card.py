import pytest
from arova.core.cognition.workspace_manager import WorkspaceManager
from arova.core.cognition.workspace import CognitiveWorkspace

def test_zero_continue_card_fabrications():
    """
    HYP-01 Regression Test: Proves that WorkspaceManager.get_continue_context does NOT inject
    fabricated confidence scores or fallback narratives when no empirical session history exists.
    """
    wm = WorkspaceManager()
    ws = CognitiveWorkspace('clean_ws', 'Clean Workspace')
    wm._workspaces['clean_ws'] = ws
    wm._active_workspace_id = 'clean_ws'
    
    ctx = wm.get_continue_context('clean_ws')
    
    # Verify zero confidence fallbacks
    breakdown = ctx.get('confidence_breakdown', {})
    assert breakdown.get('Goal') == 0, f"HYP-01 REGRESSION: Goal score fabricated: {breakdown.get('Goal')}"
    assert breakdown.get('Blocker') == 0, f"HYP-01 REGRESSION: Blocker score fabricated: {breakdown.get('Blocker')}"
    assert breakdown.get('Browser docs') == 0, f"HYP-01 REGRESSION: Browser docs score fabricated: {breakdown.get('Browser docs')}"
    assert breakdown.get('Terminal') == 0, f"HYP-01 REGRESSION: Terminal score fabricated: {breakdown.get('Terminal')}"
    
    # Verify zero story narrative fallbacks
    assert ctx.get('story_narrative') == [], f"HYP-01 REGRESSION: Fabricated story narrative found: {ctx.get('story_narrative')}"
    assert ctx.get('confidence_score') is None, f"HYP-01 REGRESSION: Fabricated confidence score found: {ctx.get('confidence_score')}"
