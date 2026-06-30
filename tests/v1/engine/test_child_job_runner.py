import json
import os
from types import SimpleNamespace

import pytest

from src.v1.engine.child_job_runner import ChildJobRunner, ChildResult, RunContext
from src.v1.engine.context_manager import ContextManager
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


# ---------------------------------------------------------------------------
# _seed_context (Task 6 -- B1 typed context merge)
# ---------------------------------------------------------------------------

def _child_with_group(group_name, var, value="/default", vtype="id_String"):
    ctx_block = {group_name: {var: {"value": value, "type": vtype}}}
    return SimpleNamespace(
        job_config={"context": ctx_block, "default_context": group_name},
        context_manager=ContextManager(initial_context=ctx_block, default_context=group_name),
    )


@pytest.mark.unit
def test_seed_applies_param_overrides_despite_context_name_mismatch():
    # B1: child has only a PROD group; tRunJob context_name defaults to "Default".
    child = _child_with_group("PROD", "input_path")
    _runner()._seed_context(child, {}, {"input_path": "/runtime/today.csv"}, context_name="Default")
    assert child.context_manager.get("input_path") == "/runtime/today.csv"


@pytest.mark.unit
def test_seed_params_win_over_whole_context():
    child = _child_with_group("Default", "input_path")
    _runner()._seed_context(child, {"input_path": "/whole"}, {"input_path": "/param"}, "Default")
    assert child.context_manager.get("input_path") == "/param"


@pytest.mark.unit
def test_seed_warns_and_skips_undeclared(caplog):
    child = _child_with_group("Default", "input_path")
    _runner()._seed_context(child, {}, {"nope": "x"}, "Default")
    assert "nope" in caplog.text


def _child_with_groups(ctx_block, default_context):
    """Build a child namespace with multiple context groups."""
    return SimpleNamespace(
        job_config={"context": ctx_block, "default_context": default_context},
        context_manager=ContextManager(initial_context=ctx_block, default_context=default_context),
    )


@pytest.mark.unit
def test_seed_uses_union_across_all_groups():
    # B1: override variable lives in PROD group only; context_name is DEV.
    # The union loop must discover 'x' from PROD and apply the override.
    ctx = {"DEV": {"y": {"value": "d", "type": "id_String"}},
           "PROD": {"x": {"value": "p", "type": "id_String"}}}
    child = _child_with_groups(ctx, default_context="DEV")
    _runner()._seed_context(child, {}, {"x": "/runtime/override.csv"}, context_name="DEV")
    assert child.context_manager.get("x") == "/runtime/override.csv"


@pytest.mark.unit
def test_seed_context_name_selects_group_values():
    # M1: when context_name points to a non-default group, that group's VALUES must win
    # over the child's own default-group values for variables not explicitly overridden.
    ctx = {"Default": {"db_host": {"value": "dev.db", "type": "id_String"}},
           "PROD": {"db_host": {"value": "prod.db", "type": "id_String"}}}
    child = _child_with_groups(ctx, default_context="Default")
    _runner()._seed_context(child, {}, {}, context_name="PROD")
    assert child.context_manager.get("db_host") == "prod.db"


@pytest.mark.unit
def test_seed_selected_group_type_wins():
    # B2: same variable in two groups with different type tokens.
    # PROD declares id_Integer; Default declares id_String.
    # When context_name=PROD, the integer coercion must be applied.
    ctx = {"Default": {"amt": {"value": "0", "type": "id_String"}},
           "PROD": {"amt": {"value": "0", "type": "id_Integer"}}}
    child = _child_with_groups(ctx, default_context="Default")
    _runner()._seed_context(child, {}, {"amt": "42"}, context_name="PROD")
    got = child.context_manager.get("amt")
    assert got == 42 and isinstance(got, int)


@pytest.mark.unit
def test_seed_whole_context_wins_over_selected_group():
    # L4: whole_context overlay must win over the selected-group value overlay.
    # db_host exists in both Default (dev.db) and PROD (prod.db).
    # Calling with whole_context={"db_host": "whole"} and context_name="PROD" must
    # yield "whole", not "prod.db".
    ctx = {"Default": {"db_host": {"value": "dev.db", "type": "id_String"}},
           "PROD": {"db_host": {"value": "prod.db", "type": "id_String"}}}
    child = _child_with_groups(ctx, default_context="Default")
    _runner()._seed_context(child, {"db_host": "whole"}, {}, context_name="PROD")
    assert child.context_manager.get("db_host") == "whole"


# ---------------------------------------------------------------------------
# _map_result (Task 7 -- pure unit, no engine)
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.parametrize("stats,exp_code", [
    ({"status": "success", "job_aborted": False}, 0),
    ({"status": "error", "job_aborted": True}, -1),
    ({"status": "failed", "job_aborted": True}, -1),
    ({"status": "failed", "job_aborted": False}, 0),    # tolerated die_on_error=false failure
    ({"status": "error", "error": "boom"}, -1),         # engine raised inside execute()
])
def test_map_result(stats, exp_code):
    assert ChildJobRunner._map_result(stats).return_code == exp_code


# ---------------------------------------------------------------------------
# run() integration tests with real fixture child JSONs (Task 7)
# ---------------------------------------------------------------------------

def _write_child(dirpath, name, components):
    cfg = {"job_name": name, "components": components, "flows": [], "triggers": [],
           "subjobs": {}, "context": {"Default": {}}}
    path = os.path.join(str(dirpath), f"{name}.json")
    with open(path, "w") as f:
        json.dump(cfg, f)
    return path


@pytest.mark.unit
def test_run_success_child(tmp_path):
    _write_child(tmp_path, "Child", [{"id": "pre_1", "type": "tPrejob", "config": {}, "schema": {}}])
    res = _runner(base_dir=str(tmp_path)).run("Child", {}, {})
    assert res.return_code == 0 and res.status == "success"


@pytest.mark.unit
def test_run_missing_child_is_negative_one_not_raise(tmp_path):
    res = _runner(base_dir=str(tmp_path)).run("Nope", {}, {})
    assert res.return_code == -1 and res.stacktrace


@pytest.mark.unit
def test_run_cycle_raises(tmp_path):
    p = os.path.join(str(tmp_path), "Child.json")
    _write_child(tmp_path, "Child", [{"id": "pre_1", "type": "tPrejob", "config": {}, "schema": {}}])
    with pytest.raises(ConfigurationError, match="cycle"):
        _runner(base_dir=str(tmp_path), call_stack=[p]).run("Child", {}, {})
