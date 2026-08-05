import pytest
from arova.core.cognition.priority import evaluate_permission_ladder

def test_permission_ladder_low_confidence_suppressed():
    # Confidence < 60% should stay completely silent
    result = evaluate_permission_ladder(confidence=0.55, reversibility="high", blast_radius="tiny")
    assert result == "suppress_silent"

def test_permission_ladder_high_confidence_automatic():
    # Confidence >= 90%, Reversible, Tiny blast radius -> Automatic Execution
    result = evaluate_permission_ladder(confidence=0.95, reversibility="high", blast_radius="tiny")
    assert result == "execute_automatically"

def test_permission_ladder_prepare_and_ask():
    # Confidence >= 90%, Local edits -> Prepare + Ask
    result = evaluate_permission_ladder(confidence=0.92, reversibility="medium", blast_radius="local")
    assert result == "prepare_and_ask"

def test_permission_ladder_explicit_approval_low_reversibility():
    # Low reversibility (git push / delete branch) -> Explicit approval
    result = evaluate_permission_ladder(confidence=0.98, reversibility="low", blast_radius="large")
    assert result == "require_explicit_approval"

def test_permission_ladder_explicit_approval_large_blast_radius():
    # Large blast radius -> Explicit approval
    result = evaluate_permission_ladder(confidence=0.95, reversibility="high", blast_radius="large")
    assert result == "require_explicit_approval"
