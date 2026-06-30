# tests/v1/engine/test_executor_job_aborted.py
import pytest
from src.v1.engine.engine import ETLEngine


def _run(components, **extra):
    cfg = {"job_name": "abort_probe", "components": components,
           "flows": [], "triggers": [], "subjobs": {}, "context": {"Default": {}}}
    cfg.update(extra)
    with ETLEngine(cfg) as engine:
        return engine.execute()


@pytest.mark.unit
def test_clean_success_is_not_aborted():
    stats = _run([{"id": "pre_1", "type": "tPrejob", "config": {}, "schema": {}}])
    assert stats["status"] == "success"
    assert stats["job_aborted"] is False


@pytest.mark.unit
def test_tdie_is_aborted():
    stats = _run([{"id": "die_1", "type": "tDie",
                   "config": {"message": "boom", "exit_code": 3}, "schema": {}}])
    assert stats["status"] == "error"
    assert stats["job_aborted"] is True
