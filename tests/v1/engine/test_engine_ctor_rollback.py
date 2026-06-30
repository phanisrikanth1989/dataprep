"""Tests for ETLEngine constructor rollback (Task 5: no orphaned child JVM).

If construction fails AFTER the JVM starts (e.g. ExecutionPlan raises on a
flow cycle), `with ETLEngine(...)` never binds the object so __exit__ never
runs.  The constructor must call self._cleanup() and re-raise so the JVM /
connection managers are always released.
"""
import pytest
from src.v1.engine import engine as engine_mod
from src.v1.engine.engine import ETLEngine


@pytest.mark.unit
def test_cleanup_called_on_construction_failure(monkeypatch):
    calls = {"n": 0}
    monkeypatch.setattr(ETLEngine, "_cleanup", lambda self: calls.__setitem__("n", calls["n"] + 1))
    bad = {"job_name": "bad",
           "components": [{"id": "a", "type": "tFilterRow", "config": {}, "schema": {}},
                          {"id": "b", "type": "tFilterRow", "config": {}, "schema": {}}],
           "triggers": [],
           # 2-node flow cycle -> ExecutionPlan topo-sort raises ConfigurationError during
           # construction (engine.py:144), inside the Step-3 wrapped post-JVM region.
           "flows": [{"name": "f1", "from": "a", "to": "b", "type": "flow"},
                     {"name": "f2", "from": "b", "to": "a", "type": "flow"}],
           "subjobs": {}, "context": {"Default": {}}}
    with pytest.raises(Exception):
        ETLEngine(bad)
    assert calls["n"] >= 1
