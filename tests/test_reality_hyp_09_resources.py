import pytest
from arova.core.cognition.warmup import PredictiveCacheTopology

def test_cache_bounding_under_load():
    """
    HYP-09 Regression Test: Proves that caches (e.g. PredictiveCacheTopology) strictly enforce
    capacity boundaries (max 50 entries) and do not grow unbounded under high event volume.
    """
    cache = PredictiveCacheTopology()
    for i in range(100):
        cache.populate(f"source_{i}", {"data": i})
        
    assert len(cache.semantic_cache) <= 50, f"HYP-09 REGRESSION: Cache exceeded bound: {len(cache.semantic_cache)} entries"
