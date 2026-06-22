# tests/v1/engine/components/transform/test_java_flex.py
import pandas as pd
import pytest
from src.v1.engine.components.transform.java_flex import JavaFlexComponent
from src.v1.engine.global_map import GlobalMap
from src.v1.engine.context_manager import ContextManager
from src.v1.engine.exceptions import ComponentExecutionError


def _make(cfg, gm=None, cm=None):
    c = JavaFlexComponent("tJavaFlex_1", cfg, gm or GlobalMap(), cm or ContextManager())
    c.config = dict(cfg)            # mirror engine deepcopy (direct-construction footgun)
    return c


@pytest.mark.java
def test_main_and_start_end_once(java_bridge):
    cfg = {
        "code_start": "int n=0;",
        "code_main": "n++; row2.id=row1.id; row2.total=n;",
        "code_end": "globalMap.put(\"final\", n);",
        "auto_propagate": False, "propagate_timing": "before",
        "input_row_name": "row1", "output_row_name": "row2",
        "output_schema": [{"name": "id", "type": "int"}, {"name": "total", "type": "int"}],
    }
    gm = GlobalMap()
    comp = _make(cfg, gm=gm)
    comp.java_bridge = java_bridge
    out = comp._process(pd.DataFrame({"id": [10, 20, 30]}))
    assert list(out["main"]["total"]) == [1, 2, 3]
    assert out["reject"] is None
    assert gm.get("final") == 3


@pytest.mark.java
def test_empty_input_still_runs_start_end(java_bridge):
    cfg = {"code_start": "globalMap.put(\"ran\",\"y\");", "code_main": "", "code_end": "",
           "auto_propagate": False, "propagate_timing": "before",
           "input_row_name": "row1", "output_row_name": "row2",
           "output_schema": [{"name": "id", "type": "int"}]}
    gm = GlobalMap(); comp = _make(cfg, gm=gm); comp.java_bridge = java_bridge
    out = comp._process(pd.DataFrame({"id": []}))
    assert out["main"].empty and gm.get("ran") == "y"


@pytest.mark.java
def test_auto_propagate_copies_matching_input_cols(java_bridge):
    cfg = {"code_start": "", "code_main": "", "code_end": "",
           "auto_propagate": True, "propagate_timing": "before",
           "input_row_name": "row1", "output_row_name": "row2",
           "output_schema": [{"name": "id", "type": "int"}, {"name": "name", "type": "str"}]}
    comp = _make(cfg); comp.java_bridge = java_bridge
    # input_cols come from schema_inputs_map (engine wires this from schema.inputs);
    # set it directly since we bypass ETLEngine here.
    comp.schema_inputs_map = {"row1": [{"name": "id", "type": "int"},
                                       {"name": "name", "type": "str"}]}
    out = comp._process(pd.DataFrame({"id": [1], "name": ["a"]}))
    # MAIN is empty -> values arrive ONLY via auto-propagate
    assert out["main"].iloc[0]["id"] == 1 and out["main"].iloc[0]["name"] == "a"


def test_validate_config_rejects_bad_timing():
    with pytest.raises(Exception):
        _make({"propagate_timing": "sideways"})._validate_config()


# ---------------------------------------------------------------------------
# Task-8: targeted unit tests to reach >= 95% line coverage
# ---------------------------------------------------------------------------

from src.v1.engine.exceptions import ConfigurationError  # noqa: E402


class _FakeBridge:
    """Minimal stand-in for JavaBridge -- no JVM required."""

    def __init__(self):
        self.global_map = {}
        self.context = {}

    def execute_java_flex(self, df, *, script, output_schema, input_schema=None):
        return df  # echo input unchanged


class _FakeBridgeWithContextWrite:
    """FakeBridge that also writes a new key into context after the call."""

    def __init__(self):
        self.global_map = {}
        self.context = {}

    def execute_java_flex(self, df, *, script, output_schema, input_schema=None):
        self.context["bridge_wrote"] = "hello"
        return df


class _FakeBridgeRaises:
    """FakeBridge that always raises on execute_java_flex."""

    def __init__(self):
        self.global_map = {}
        self.context = {}

    def execute_java_flex(self, df, *, script, output_schema, input_schema=None):
        raise RuntimeError("simulated bridge failure")


# ---- _validate_config branches (lines 95, 101, 107, 120) ----

def test_validate_config_rejects_non_str_code_start():
    """Line 95: code_start is not a string -> ConfigurationError."""
    with pytest.raises(ConfigurationError):
        _make({"code_start": 123})._validate_config()


def test_validate_config_rejects_non_str_code_main():
    """Line 95 (code_main branch): non-str code_main -> ConfigurationError."""
    with pytest.raises(ConfigurationError):
        _make({"code_main": 99})._validate_config()


def test_validate_config_rejects_non_str_code_end():
    """Line 95 (code_end branch): non-str code_end -> ConfigurationError."""
    with pytest.raises(ConfigurationError):
        _make({"code_end": []})._validate_config()


def test_validate_config_rejects_non_str_imports():
    """Line 101: non-str imports -> ConfigurationError."""
    with pytest.raises(ConfigurationError):
        _make({"imports": 42})._validate_config()


def test_validate_config_rejects_non_bool_auto_propagate():
    """Line 107: non-bool auto_propagate -> ConfigurationError."""
    with pytest.raises(ConfigurationError):
        _make({"auto_propagate": "yes"})._validate_config()


def test_validate_config_rejects_bad_output_schema_type():
    """Line 120: output_schema that is neither dict nor list -> ConfigurationError."""
    with pytest.raises(ConfigurationError):
        _make({"output_schema": "id:int"})._validate_config()


# ---- Line 166: None input normalised to empty DataFrame ----

def test_process_none_input_creates_empty_dataframe():
    """Line 166: input_data=None -> internally becomes empty DataFrame."""
    comp = _make({})
    comp.java_bridge = _FakeBridge()
    result = comp._process(None)
    assert isinstance(result["main"], pd.DataFrame)
    assert result["reject"] is None


# ---- Lines 181-183: output_schema as dict ----

def test_process_output_schema_as_dict():
    """Lines 181-183: dict output_schema -> keys become output_cols."""
    comp = _make({"output_schema": {"id": "int", "name": "str"}})
    comp.java_bridge = _FakeBridge()
    result = comp._process(pd.DataFrame({"id": [1], "name": ["a"]}))
    assert isinstance(result["main"], pd.DataFrame)


# ---- Lines 185-186: output_schema missing/None -> empty ----

def test_process_output_schema_missing():
    """Lines 185-186: no output_schema -> empty output_cols / output_schema_dict."""
    comp = _make({})  # no output_schema key
    comp.java_bridge = _FakeBridge()
    result = comp._process(pd.DataFrame())
    assert isinstance(result["main"], pd.DataFrame)


# ---- Lines 200-201: input_schema flat-list fallback ----

def test_process_input_schema_flat_list_fallback():
    """Lines 200-201: schema_inputs_map empty but input_schema set -> fallback used."""
    comp = _make({})
    comp.input_schema = [{"name": "id", "type": "int"}, {"name": "val", "type": "str"}]
    # schema_inputs_map intentionally NOT set (defaults to None/empty via getattr)
    comp.java_bridge = _FakeBridge()
    result = comp._process(pd.DataFrame({"id": [1], "val": ["x"]}))
    assert isinstance(result["main"], pd.DataFrame)


# ---- Line 239: java_bridge is None -> ComponentExecutionError ----

def test_process_raises_when_no_bridge():
    """Line 239: java_bridge=None -> ComponentExecutionError."""
    comp = _make({})
    comp.java_bridge = None
    with pytest.raises(ComponentExecutionError):
        comp._process(pd.DataFrame())


# ---- Line 249: context push loop (context_manager -> bridge.context) ----

def test_process_context_push_to_bridge():
    """Line 249: ContextManager vars are pushed into bridge.context before the call."""
    cm = ContextManager()
    cm.set("my_var", "pushed_value")
    comp = _make({}, cm=cm)
    bridge = _FakeBridge()
    comp.java_bridge = bridge
    comp._process(pd.DataFrame())
    assert bridge.context.get("my_var") == "pushed_value"


# ---- Lines 259-264: bridge raises -> wrapped ComponentExecutionError ----

def test_process_bridge_exception_wrapped():
    """Lines 259-264: bridge.execute_java_flex raises -> ComponentExecutionError."""
    comp = _make({})
    comp.java_bridge = _FakeBridgeRaises()
    with pytest.raises(ComponentExecutionError) as exc_info:
        comp._process(pd.DataFrame())
    assert exc_info.value.cause.__class__ == RuntimeError


# ---- Lines 273-274: context read-back after bridge call ----

def test_process_context_readback_after_bridge():
    """Lines 273-274: values written by bridge into bridge.context are copied back."""
    cm = ContextManager()
    comp = _make({}, cm=cm)
    comp.java_bridge = _FakeBridgeWithContextWrite()
    comp._process(pd.DataFrame())
    assert cm.get("bridge_wrote") == "hello"
