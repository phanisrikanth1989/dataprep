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
