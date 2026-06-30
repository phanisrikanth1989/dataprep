import os

import pytest

from src.v1.engine.child_job_runner import ChildJobRunner, ChildResult, RunContext
from src.v1.engine.exceptions import ConfigurationError


@pytest.mark.unit
def test_dataclass_defaults():
    rc = RunContext(base_dir="/d", jobs_dir=None, call_stack=["/d/a.json"], depth=0)
    assert rc.max_depth == 2
    res = ChildResult(status="success", return_code=0)
    assert res.stacktrace is None


# ---------------------------------------------------------------------------
# ChildJobRunner -- path resolution + cycle/depth guards (Task 3)
# ---------------------------------------------------------------------------

def _runner(base_dir=None, jobs_dir=None, call_stack=None, depth=0, max_depth=2):
    return ChildJobRunner(RunContext(base_dir=base_dir, jobs_dir=jobs_dir,
                                    call_stack=call_stack or [], depth=depth, max_depth=max_depth))


@pytest.mark.unit
def test_resolve_path_uses_base_dir(tmp_path):
    r = _runner(base_dir=str(tmp_path))
    assert r._resolve_path("Child") == os.path.join(str(tmp_path), "Child.json")


@pytest.mark.unit
def test_resolve_path_falls_back_to_jobs_dir(tmp_path):
    r = _runner(base_dir=None, jobs_dir=str(tmp_path))
    assert r._resolve_path("Child") == os.path.join(str(tmp_path), "Child.json")


@pytest.mark.unit
def test_resolve_path_no_base_raises():
    with pytest.raises(ConfigurationError):
        _runner(base_dir=None, jobs_dir=None)._resolve_path("Child")


@pytest.mark.unit
def test_cycle_detected_by_abspath(tmp_path):
    p = os.path.join(str(tmp_path), "A.json")
    r = _runner(base_dir=str(tmp_path), call_stack=[p])
    with pytest.raises(ConfigurationError, match="cycle"):
        r._check_cycle_and_depth(p)


@pytest.mark.unit
def test_depth_limit(tmp_path):
    r = _runner(base_dir=str(tmp_path), depth=2, max_depth=2)
    with pytest.raises(ConfigurationError, match="depth"):
        r._check_cycle_and_depth(os.path.join(str(tmp_path), "B.json"))


@pytest.mark.unit
def test_child_run_context_increments(tmp_path):
    p = os.path.join(str(tmp_path), "B.json")
    child = _runner(base_dir=str(tmp_path), call_stack=["/root/A.json"], depth=0)._child_run_context(p)
    assert child.depth == 1 and child.call_stack == ["/root/A.json", p]
    assert child.base_dir == str(tmp_path)


@pytest.mark.unit
def test_depth_at_limit_allowed(tmp_path):
    # depth+1 == max_depth must NOT raise (kills the > -> >= mutant)
    r = _runner(base_dir=str(tmp_path), depth=1, max_depth=2)
    assert r._check_cycle_and_depth(os.path.join(str(tmp_path), "B.json")) is None


@pytest.mark.unit
def test_no_cycle_no_depth_passes(tmp_path):
    r = _runner(base_dir=str(tmp_path), call_stack=["/root/A.json"], depth=0, max_depth=2)
    assert r._check_cycle_and_depth(os.path.join(str(tmp_path), "B.json")) is None
