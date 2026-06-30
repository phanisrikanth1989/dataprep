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


@pytest.mark.unit
def test_die_on_error_false_not_aborted(tmp_path):
    # tFileInputDelimited pointing at a non-existent file raises FileOperationError
    # and lands in failed_components WITHOUT setting _job_terminated.
    # With die_on_error=False the subjob runs to completion -> job_aborted must be False.
    nonexistent = str(tmp_path / "nonexistent.csv")
    stats = _run([{
        "id": "file_1",
        "type": "tFileInputDelimited",
        "config": {"filepath": nonexistent, "die_on_error": False},
        "schema": {},
    }])
    assert stats["status"] == "failed"
    assert stats["job_aborted"] is False


@pytest.mark.unit
def test_die_on_error_true_aborted(tmp_path):
    # Same failure scenario but die_on_error=True:
    # the component attribute is set in step 4 (before _process raises) so
    # the job_aborted aggregation picks it up -> job_aborted must be True.
    nonexistent = str(tmp_path / "nonexistent.csv")
    stats = _run([{
        "id": "file_1",
        "type": "tFileInputDelimited",
        "config": {"filepath": nonexistent, "die_on_error": True},
        "schema": {},
    }])
    assert stats["status"] == "failed"
    assert stats["job_aborted"] is True
