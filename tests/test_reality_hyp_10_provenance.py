import pytest
from arova.core.cognition.restoration_engine import RestoreOutcomeItem

def test_recovered_state_provenance():
    """
    HYP-10 Regression Test: Proves that restored items and state records explicitly carry
    provenance metadata verifying they originated from empirical runtime probes rather than mocks.
    """
    item = RestoreOutcomeItem(name="VS Code", resource_id="file:///home/sarthak/arova/runtime.py", status="restored")
    d = item.to_dict()
    assert "provenance" in d, f"HYP-10 REGRESSION: No provenance in restored item dict: {d}"
    assert d["provenance"]["verification_method"] == "empirical_runtime_probe", f"HYP-10 REGRESSION: Invalid verification method: {d['provenance']}"
