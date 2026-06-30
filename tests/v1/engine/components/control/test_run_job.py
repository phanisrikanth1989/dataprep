# tests/v1/engine/components/control/test_run_job.py
import logging
import re
import pytest
from src.v1.engine.component_registry import REGISTRY
from src.v1.engine.global_map import GlobalMap
from src.v1.engine.context_manager import ContextManager
from src.v1.engine.child_job_runner import ChildResult
from src.v1.engine.exceptions import ComponentExecutionError, ConfigurationError
from src.v1.engine.components.control.run_job import RunJob


class _FakeRunner:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def run(self, process, whole_context, param_overrides, context_name="Default"):
        self.calls.append((process, whole_context, param_overrides, context_name))
        return self.result


def _make(config, runner, gm=None, ctx=None):
    comp = RunJob("tRunJob_1", config, gm or GlobalMap(), ctx or ContextManager())
    comp.child_job_runner = runner
    return comp


@pytest.mark.unit
def test_registration():
    assert REGISTRY.get("tRunJob") is RunJob
    assert REGISTRY.get("RunJob") is RunJob


@pytest.mark.unit
def test_success_writes_zero_and_returns_none():
    gm = GlobalMap()
    comp = _make({"process": "Child", "die_on_child_error": True},
                 _FakeRunner(ChildResult("success", 0)), gm=gm)
    out = comp.execute(None)
    assert out["main"] is None and out["reject"] is None
    assert gm.get("tRunJob_1_CHILD_RETURN_CODE") == 0


@pytest.mark.unit
def test_die_on_child_error_kills_parent():
    comp = _make({"process": "Child", "die_on_child_error": True},
                 _FakeRunner(ChildResult("error", -1, "trace")))
    with pytest.raises(ComponentExecutionError) as ei:
        comp.execute(None)
    # execute() re-wraps the component's ComponentExecutionError, so the exit_code set in
    # _process lives on the ORIGINAL exception at ei.value.cause, NOT on the wrapper.
    assert ei.value.cause.exit_code == -1


@pytest.mark.unit
def test_die_off_continues_and_records_code():
    gm = GlobalMap()
    comp = _make({"process": "Child", "die_on_child_error": False},
                 _FakeRunner(ChildResult("error", -1, "trace")), gm=gm)
    out = comp.execute(None)
    assert out["main"] is None and out["reject"] is None
    assert gm.get("tRunJob_1_CHILD_RETURN_CODE") == -1
    assert gm.get("tRunJob_1_CHILD_EXCEPTION_STACKTRACE") == "trace"


@pytest.mark.unit
def test_globalmap_get_resolution_in_params():
    gm = GlobalMap()
    gm.put("tFileList_1_CURRENT_FILEPATH", "/data/today.csv")
    runner = _FakeRunner(ChildResult("success", 0))
    comp = _make({"process": "Child", "die_on_child_error": False, "context_params":
                  [{"param_name": "in_file",
                    "param_value": 'globalMap.get("tFileList_1_CURRENT_FILEPATH")'}]},
                 runner, gm=gm)
    comp.execute(None)
    _, _, param_overrides, _ = runner.calls[0]
    assert param_overrides == {"in_file": "/data/today.csv"}


@pytest.mark.unit
def test_validate_rejects_dynamic_job():
    comp = _make({"process": "Child", "use_dynamic_job": True},
                 _FakeRunner(ChildResult("success", 0)))
    with pytest.raises(ConfigurationError):
        comp.execute(None)


@pytest.mark.unit
def test_validate_rejects_empty_process():
    comp = _make({"process": ""}, _FakeRunner(ChildResult("success", 0)))
    with pytest.raises(ConfigurationError):
        comp.execute(None)


@pytest.mark.unit
def test_validate_rejects_dynamic_context():
    comp = _make({"process": "Child", "use_dynamic_context": True},
                 _FakeRunner(ChildResult("success", 0)))
    with pytest.raises(ConfigurationError):
        comp.execute(None)


@pytest.mark.unit
def test_ignored_key_warns_but_runs(caplog):
    gm = GlobalMap()
    comp = _make({"process": "Child", "die_on_child_error": False,
                  "use_independent_process": True},
                 _FakeRunner(ChildResult("success", 0)), gm=gm)
    with caplog.at_level(logging.WARNING):
        out = comp.execute(None)
    assert out["main"] is None and out["reject"] is None
    assert any("use_independent_process" in r.getMessage() for r in caplog.records)


@pytest.mark.unit
def test_missing_runner_raises():
    comp = _make({"process": "Child"}, _FakeRunner(ChildResult("success", 0)))
    comp.child_job_runner = None
    with pytest.raises(ConfigurationError):
        comp.execute(None)


@pytest.mark.unit
def test_empty_param_name_skipped():
    runner = _FakeRunner(ChildResult("success", 0))
    comp = _make({"process": "Child", "die_on_child_error": False, "context_params":
                  [{"param_name": "", "param_value": "x"},
                   {"param_name": "ok", "param_value": "v"}]}, runner)
    comp.execute(None)
    _, _, param_overrides, _ = runner.calls[0]
    assert param_overrides == {"ok": "v"}


@pytest.mark.unit
def test_param_value_passthrough_when_not_globalmap():
    runner = _FakeRunner(ChildResult("success", 0))
    comp = _make({"process": "Child", "die_on_child_error": False, "context_params":
                  [{"param_name": "p", "param_value": "literal"}]}, runner)
    comp.execute(None)
    _, _, param_overrides, _ = runner.calls[0]
    assert param_overrides == {"p": "literal"}


# ---------------------------------------------------------------------------
# M2: _resolve_globalmap -- full-match only, fail loud on composed expressions
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_cast_wrapped_globalmap_resolves():
    # L4: ((String)globalMap.get("KEY")) must resolve to the stored value
    gm = GlobalMap()
    gm.put("tFileList_1_CURRENT_FILEPATH", "/data/today.csv")
    runner = _FakeRunner(ChildResult("success", 0))
    comp = _make({"process": "Child", "die_on_child_error": False, "context_params":
                  [{"param_name": "in_file",
                    "param_value": '((String)globalMap.get("tFileList_1_CURRENT_FILEPATH"))'}]},
                 runner, gm=gm)
    comp.execute(None)
    _, _, param_overrides, _ = runner.calls[0]
    assert param_overrides == {"in_file": "/data/today.csv"}


@pytest.mark.unit
def test_composed_globalmap_raises_config_error():
    # L6: '"/data/" + globalMap.get("F")' must raise ConfigurationError, not silently mis-resolve
    gm = GlobalMap()
    gm.put("F", "filename")
    comp = _make({"process": "Child", "die_on_child_error": False, "context_params":
                  [{"param_name": "p",
                    "param_value": '"/data/" + globalMap.get("F")'}]},
                 _FakeRunner(ChildResult("success", 0)), gm=gm)
    with pytest.raises(ConfigurationError):
        comp.execute(None)


@pytest.mark.unit
def test_double_globalmap_raises_config_error():
    # L7: double globalMap.get in one expression must raise ConfigurationError
    gm = GlobalMap()
    gm.put("A", "a")
    gm.put("B", "b")
    comp = _make({"process": "Child", "die_on_child_error": False, "context_params":
                  [{"param_name": "p",
                    "param_value": 'globalMap.get("A")+globalMap.get("B")'}]},
                 _FakeRunner(ChildResult("success", 0)), gm=gm)
    with pytest.raises(ConfigurationError):
        comp.execute(None)


# ---------------------------------------------------------------------------
# L2: transmit_whole_context flag
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_transmit_whole_context_true():
    ctx = ContextManager()
    ctx.set("env", "prod", None)
    runner = _FakeRunner(ChildResult("success", 0))
    comp = _make({"process": "Child", "die_on_child_error": False, "transmit_whole_context": True},
                 runner, ctx=ctx)
    comp.execute(None)
    _, whole_context, _, _ = runner.calls[0]
    assert "env" in whole_context


@pytest.mark.unit
def test_transmit_whole_context_false():
    ctx = ContextManager()
    ctx.set("env", "prod", None)
    runner = _FakeRunner(ChildResult("success", 0))
    comp = _make({"process": "Child", "die_on_child_error": False},
                 runner, ctx=ctx)
    comp.execute(None)
    _, whole_context, _, _ = runner.calls[0]
    assert whole_context == {}


# ---------------------------------------------------------------------------
# L3: context_name passthrough to runner
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_context_name_passthrough():
    runner = _FakeRunner(ChildResult("success", 0))
    comp = _make({"process": "Child", "die_on_child_error": False, "context_name": "PROD"}, runner)
    comp.execute(None)
    _, _, _, context_name = runner.calls[0]
    assert context_name == "PROD"


# ---------------------------------------------------------------------------
# Broadened globalMap cast forms (FQN, array, generic, single-paren)
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_fqn_cast_resolves():
    # ((java.util.Date)globalMap.get("BATCH_DATE")) must resolve to the stored value.
    gm = GlobalMap()
    gm.put("BATCH_DATE", "2024-01-01")
    runner = _FakeRunner(ChildResult("success", 0))
    comp = _make({"process": "Child", "die_on_child_error": False, "context_params":
                  [{"param_name": "dt",
                    "param_value": '((java.util.Date)globalMap.get("BATCH_DATE"))'}]},
                 runner, gm=gm)
    comp.execute(None)
    _, _, param_overrides, _ = runner.calls[0]
    assert param_overrides == {"dt": "2024-01-01"}


@pytest.mark.unit
def test_array_cast_resolves():
    # ((Integer[])globalMap.get("ARR")) must resolve to the stored value.
    gm = GlobalMap()
    gm.put("ARR", [1, 2, 3])
    runner = _FakeRunner(ChildResult("success", 0))
    comp = _make({"process": "Child", "die_on_child_error": False, "context_params":
                  [{"param_name": "arr",
                    "param_value": '((Integer[])globalMap.get("ARR"))'}]},
                 runner, gm=gm)
    comp.execute(None)
    _, _, param_overrides, _ = runner.calls[0]
    assert param_overrides == {"arr": [1, 2, 3]}


@pytest.mark.unit
def test_generic_cast_resolves():
    # ((List<String>)globalMap.get("LST")) must resolve to the stored value.
    gm = GlobalMap()
    gm.put("LST", ["a", "b"])
    runner = _FakeRunner(ChildResult("success", 0))
    comp = _make({"process": "Child", "die_on_child_error": False, "context_params":
                  [{"param_name": "lst",
                    "param_value": '((List<String>)globalMap.get("LST"))'}]},
                 runner, gm=gm)
    comp.execute(None)
    _, _, param_overrides, _ = runner.calls[0]
    assert param_overrides == {"lst": ["a", "b"]}


@pytest.mark.unit
def test_single_paren_cast_resolves():
    # (String)globalMap.get("K") must resolve to the stored value.
    gm = GlobalMap()
    gm.put("K", "hello")
    runner = _FakeRunner(ChildResult("success", 0))
    comp = _make({"process": "Child", "die_on_child_error": False, "context_params":
                  [{"param_name": "p",
                    "param_value": '(String)globalMap.get("K")'}]},
                 runner, gm=gm)
    comp.execute(None)
    _, _, param_overrides, _ = runner.calls[0]
    assert param_overrides == {"p": "hello"}


@pytest.mark.unit
def test_whitespace_padded_resolves():
    # '  globalMap.get("K")  ' and '  ((String)globalMap.get("K"))  ' must resolve
    # after strip() -- pins the strip() call in _resolve_globalmap.
    gm = GlobalMap()
    gm.put("K", "world")
    runner = _FakeRunner(ChildResult("success", 0))
    comp = _make({"process": "Child", "die_on_child_error": False, "context_params":
                  [{"param_name": "bare", "param_value": '  globalMap.get("K")  '},
                   {"param_name": "cast", "param_value": '  ((String)globalMap.get("K"))  '}]},
                 runner, gm=gm)
    comp.execute(None)
    _, _, param_overrides, _ = runner.calls[0]
    assert param_overrides == {"bare": "world", "cast": "world"}


@pytest.mark.unit
def test_none_param_value_passthrough():
    # L2: a context_params row with param_name set but NO param_value key must produce
    # override value None (covers the non-string early-return branch in _resolve_globalmap).
    runner = _FakeRunner(ChildResult("success", 0))
    comp = _make({"process": "Child", "die_on_child_error": False, "context_params":
                  [{"param_name": "p"}]},  # no param_value key
                 runner)
    comp.execute(None)
    _, _, param_overrides, _ = runner.calls[0]
    assert param_overrides == {"p": None}
