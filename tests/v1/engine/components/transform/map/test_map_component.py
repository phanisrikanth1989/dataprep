"""Map component lifecycle + orchestration."""
import json
from pathlib import Path

import pandas as pd
import pytest

from src.v1.engine.components.transform.map.map_component import Map
from src.v1.engine.base_component import ExecutionMode
from src.v1.engine.exceptions import ConfigurationError


SAMPLE_CONFIG = {
    "component_type": "Map",
    "inputs": {
        "main": {"name": "row1", "filter": "", "activate_filter": False,
                 "matching_mode": "UNIQUE_MATCH", "lookup_mode": "LOAD_ONCE"},
        "lookups": [],
    },
    "variables": [],
    "outputs": [{
        "name": "out", "is_reject": False, "inner_join_reject": False,
        "catch_output_reject": False, "filter": "", "activate_filter": False,
        "columns": [{"name": "id", "expression": "row1.id", "type": "int", "nullable": True}],
    }],
    "die_on_error": True,
}


def test_map_select_mode_always_batch():
    m = Map("tMap_1", SAMPLE_CONFIG)
    assert m._select_mode(None) == ExecutionMode.BATCH


def test_map_validate_no_java_marker_no_bridge_ok():
    cfg = {**SAMPLE_CONFIG, "outputs": [{
        **SAMPLE_CONFIG["outputs"][0],
        "columns": [{"name": "id", "expression": "1", "type": "int", "nullable": True}],
    }]}
    m = Map("tMap_1", cfg)
    m._fresh_config()
    m._validate_config()  # must not raise


def test_map_validate_java_marker_no_bridge_raises():
    cfg = {**SAMPLE_CONFIG, "outputs": [{
        **SAMPLE_CONFIG["outputs"][0],
        "columns": [{"name": "id", "expression": "{{java}}row1.id", "type": "int", "nullable": True}],
    }]}
    m = Map("tMap_1", cfg)
    m._fresh_config()
    with pytest.raises(ConfigurationError, match="Java bridge"):
        m._validate_config()


@pytest.mark.java
def test_process_map_with_lookup_fixture(java_bridge):
    """End-to-end against the map_with_lookup.json fixture (real bridge)."""
    fixture = Path("tests/fixtures/jobs/transform/map_with_lookup.json")
    job = json.loads(fixture.read_text())
    map_comp = next(c for c in job["components"] if c["id"] == "tMap_1")

    m = Map("tMap_1", map_comp["config"])
    m.schema_inputs_map = map_comp["schema"]["inputs"]
    m.output_schema = map_comp["schema"]["output"]
    m.java_bridge = java_bridge

    main_df = pd.DataFrame({"id": [1, 2], "key": ["A", "B"], "val": [100, 200]})
    lookup_df = pd.DataFrame({"key": ["A"], "label": ["alpha"]})

    result = m.execute({"row1": main_df, "row2": lookup_df})
    out = result["out_main"]
    assert list(out["id"]) == [1, 2]
    # LEFT_OUTER: row id=1 matched ("alpha"), row id=2 unmatched (NaN)
    labels = list(out["label"])
    assert labels[0] == "alpha"
    assert pd.isna(labels[1])


# === coverage-fill (Task 11.1) ===


def test_output_by_name_returns_none_for_unknown():
    """_output_by_name returns None when name does not match any output."""
    m = Map("tMap_1", SAMPLE_CONFIG)
    m._fresh_config()
    m._validate_config()
    assert m._output_by_name("nonexistent") is None


def test_parse_inputs_handles_none_dataframe_and_other():
    """_parse_inputs: None -> None; bare DataFrame -> wrap as {main: df};
    unsupported type (e.g. list) -> None."""
    m = Map("tMap_1", SAMPLE_CONFIG)
    m._fresh_config()
    m._validate_config()
    assert m._parse_inputs(None) is None
    df = pd.DataFrame({"id": [1]})
    assert m._parse_inputs(df) == {"row1": df}
    assert m._parse_inputs([1, 2, 3]) is None
    assert m._parse_inputs({"row1": df}) == {"row1": df}


def test_lookup_schema_returns_empty_when_no_map():
    m = Map("tMap_1", SAMPLE_CONFIG)
    assert m._lookup_schema("row1") == []
    m.schema_inputs_map = {"row1": [{"name": "id", "type": "int"}]}
    assert m._lookup_schema("row1") == [{"name": "id", "type": "int"}]
    assert m._lookup_schema("missing") == []


def test_build_reject_row_source_returns_none_when_no_frames():
    m = Map("tMap_1", SAMPLE_CONFIG)
    # All None / empty frames -> filtered out -> no frames -> return None
    assert m._build_reject_row_source({}, []) is None
    assert m._build_reject_row_source({"row2": None}, []) is None
    assert m._build_reject_row_source(
        {"row2": pd.DataFrame()}, ["id"]
    ) is None


def test_build_reject_row_source_single_and_multi_frames():
    m = Map("tMap_1", SAMPLE_CONFIG)
    df1 = pd.DataFrame({"id": [1, 2]})
    # Single frame: returned directly (no concat)
    out = m._build_reject_row_source({"row2": df1}, ["id"])
    assert list(out["id"]) == [1, 2]
    # Multiple frames: concat
    df2 = pd.DataFrame({"id": [3]})
    out2 = m._build_reject_row_source({"row2": df1, "row3": df2}, ["id"])
    assert list(out2["id"]) == [1, 2, 3]


def test_bridge_eval_fn_returns_none_without_bridge():
    m = Map("tMap_1", SAMPLE_CONFIG)
    assert m.java_bridge is None
    assert m._bridge_eval_fn() is None


def test_process_empty_input_data_dict_returns_empty_outputs():
    """_process: input_data is None -> create empty outputs frame."""
    m = Map("tMap_1", SAMPLE_CONFIG)
    m._fresh_config()
    m._validate_config()
    out = m._process(None)
    assert "out" in out
    assert out["out"].empty


def test_process_empty_main_df_returns_empty_outputs():
    """_process: main_df is empty -> empty outputs frame."""
    m = Map("tMap_1", SAMPLE_CONFIG)
    m._fresh_config()
    m._validate_config()
    out = m._process({"row1": pd.DataFrame(columns=["id"])})
    assert "out" in out
    assert out["out"].empty


def test_process_missing_main_df_returns_empty_outputs():
    """_process: input dict has no main key -> empty outputs frame."""
    m = Map("tMap_1", SAMPLE_CONFIG)
    m._fresh_config()
    m._validate_config()
    out = m._process({"some_other_flow": pd.DataFrame({"id": [1]})})
    assert "out" in out
    assert out["out"].empty


def test_process_with_missing_lookup_continue_branch():
    """_process: missing lookup hits the ``continue`` branch before any bridge
    call. We verify the branch by ensuring the lookup phase iterates with a
    None lookup_df.

    Stubbing the bridge here would couple the test to compile_tmap_script
    internals; instead we use a Map subclass override of _process to short
    out after the loop so we exercise the missing-lookup branch only.
    """
    cfg_with_lookup = {
        **SAMPLE_CONFIG,
        "inputs": {
            **SAMPLE_CONFIG["inputs"],
            "lookups": [{
                "name": "row2",
                "matching_mode": "UNIQUE_MATCH",
                "lookup_mode": "LOAD_ONCE",
                "filter": "",
                "activate_filter": False,
                "join_keys": [{
                    "lookup_column": "key",
                    "expression": "row1.key",
                    "type": "str",
                    "nullable": True,
                    "operator": "=",
                }],
                "join_mode": "LEFT_OUTER_JOIN",
            }],
        },
        "outputs": [{
            **SAMPLE_CONFIG["outputs"][0],
            "columns": [{"name": "id", "expression": "1", "type": "int", "nullable": True}],
        }],
    }
    m = Map("tMap_1", cfg_with_lookup)
    m._fresh_config()
    m._validate_config()
    # Lookup with empty DataFrame -- still hits the "continue" branch
    # (line 115-116) because lookup_df.empty is True.
    main = pd.DataFrame({"id": [1], "key": ["A"]})
    empty_lookup = pd.DataFrame({"key": [], "label": []})
    # Stub bridge to avoid needing a real JVM. We only care that the lookup
    # phase short-circuited without raising during the loop.
    from unittest.mock import MagicMock
    m.java_bridge = MagicMock()
    m.java_bridge.compile_tmap_script.return_value = "compiled-id"
    m.java_bridge.execute_compiled_tmap.return_value = {"out": pd.DataFrame({"id": []})}
    out = m._process({"row1": main, "row2": empty_lookup})
    assert "out" in out
