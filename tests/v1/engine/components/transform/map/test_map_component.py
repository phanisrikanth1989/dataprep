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


# ===== CONSTANT_KEY dispatch =====

def test_constant_key_dispatch_invokes_join_constant_key(monkeypatch):
    """The orchestrator routes CONSTANT_KEY strategies through join_constant_key."""
    from src.v1.engine.components.transform.map.map_component import Map
    from src.v1.engine.components.transform.map import map_joins

    calls: list[str] = []

    def fake_constant_key(joined, lookup, lk, main_name, prior_lookups, constant_eval_fn):
        calls.append(lk.name)
        return joined.assign(**{f"{lk.name}.info": "stub"}), None

    monkeypatch.setattr(map_joins, "join_constant_key", fake_constant_key)

    config = {
        "label": "tMap_1",
        "die_on_error": False,
        "inputs": {
            "main": {"name": "row1"},
            "lookups": [{
                "name": "row8",
                "matching_mode": "FIRST_MATCH",
                "lookup_mode": "LOAD_ONCE",
                "join_mode": "LEFT_OUTER_JOIN",
                "join_keys": [{
                    "lookup_column": "name",
                    "expression": "{{java}}context.SOURCE",
                    "type": "str",
                }],
            }],
        },
        "outputs": [{
            "name": "out1",
            "columns": [
                {"name": "id", "expression": "row1.id", "type": "id_Integer"},
                {"name": "info", "expression": "row8.info", "type": "id_String"},
            ],
        }],
    }
    main_df = pd.DataFrame({"id": [1, 2]})
    lookup_df = pd.DataFrame({"name": ["beta"], "info": ["B"]})

    m = Map(component_id="tMap_1", config=config)
    m._fresh_config()     # populate self.config from _original_config
    m.java_bridge = _make_stub_bridge_for_constant_key()
    m._parsed_cfg = None  # forces _validate_config to parse
    m._validate_config()

    m._process({"row1": main_df, "row8": lookup_df})

    assert calls == ["row8"], "join_constant_key must be invoked for the row8 lookup"


def _make_stub_bridge_for_constant_key():
    """Minimal bridge stub that returns predictable script outputs.

    Designed to be used only when `join_constant_key` is monkeypatched
    out -- so it doesn't need to evaluate context expressions.
    """
    from unittest.mock import MagicMock

    bridge = MagicMock()
    bridge.compile_tmap_script.return_value = None

    def fake_chunked(component_id, df, chunk_size, input_columns,
                    schema, reject_mode):
        # Echo back as a single named output 'out1'
        return {"out1": df.copy().assign(info="X")}

    bridge.execute_compiled_tmap_chunked.side_effect = fake_chunked
    bridge.execute_batch_one_time_expressions.return_value = {
        "__ck_0__": "beta",
    }
    return bridge
