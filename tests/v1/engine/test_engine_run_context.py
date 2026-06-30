"""Tests for ETLEngine run-context wiring (Task 4: tRunJob engine integration).

Verifies that ETLEngine:
  - stores _job_path / _job_dir when loaded from a file path
  - builds a root RunContext and ChildJobRunner
  - accepts an inherited _run_context kwarg
  - injects child_job_runner into every component
"""
import json
import pytest
from src.v1.engine.engine import ETLEngine
from src.v1.engine.child_job_runner import RunContext


def _cfg():
    return {"job_name": "root", "components": [{"id": "pre_1", "type": "tPrejob",
            "config": {}, "schema": {}}], "flows": [], "triggers": [], "subjobs": {},
            "context": {"Default": {}}}


@pytest.mark.unit
def test_root_run_context_from_path(tmp_path):
    p = tmp_path / "root.json"
    p.write_text(json.dumps(_cfg()))
    eng = ETLEngine(str(p))
    assert eng._job_dir == str(tmp_path)
    assert eng._run_context.depth == 0
    assert eng._run_context.base_dir == str(tmp_path)
    assert eng.components["pre_1"].child_job_runner is eng._child_job_runner


@pytest.mark.unit
def test_dict_config_has_no_job_dir_but_has_runner():
    eng = ETLEngine(_cfg())
    assert eng._job_dir is None
    assert eng._child_job_runner is not None


@pytest.mark.unit
def test_inherited_run_context_is_used():
    rc = RunContext(base_dir="/d", jobs_dir=None, call_stack=["/d/root.json"], depth=1, max_depth=2)
    eng = ETLEngine(_cfg(), _run_context=rc)
    assert eng._run_context is rc
