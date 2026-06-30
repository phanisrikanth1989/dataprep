import pytest
from src.v1.engine.child_job_runner import RunContext, ChildResult


@pytest.mark.unit
def test_dataclass_defaults():
    rc = RunContext(base_dir="/d", jobs_dir=None, call_stack=["/d/a.json"], depth=0)
    assert rc.max_depth == 2
    res = ChildResult(status="success", return_code=0)
    assert res.stacktrace is None
