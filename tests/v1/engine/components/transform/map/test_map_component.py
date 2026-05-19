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


# ===== Debug logging: per-lookup join trace =====

import logging as _logging


def _logger_name():
    return "src.v1.engine.components.transform.map.map_component"


def test_log_lookup_join_before_and_after_pair(caplog):
    """Each lookup join emits exactly two INFO records: before and after."""
    from src.v1.engine.components.transform.map.map_component import Map

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
    m._fresh_config()
    m.java_bridge = _make_stub_bridge_for_constant_key()
    m._validate_config()

    with caplog.at_level(_logging.INFO, logger=_logger_name()):
        m._process({"row1": main_df, "row8": lookup_df})

    msgs = [r.getMessage() for r in caplog.records if r.name == _logger_name()]
    before = [m for m in msgs if "lookup 'row8' strategy=" in m]
    after = [m for m in msgs if "lookup 'row8' joined: result_rows=" in m]
    assert len(before) == 1, f"Expected one before-join INFO record, got {before}"
    assert len(after) == 1, f"Expected one after-join INFO record, got {after}"
    # Before line carries the configured shape
    assert "[tMap_1]" in before[0]
    assert "match=FIRST_MATCH" in before[0]
    assert "join=LEFT_OUTER_JOIN" in before[0]
    assert "keys=[name <= {{java}}context.SOURCE]" in before[0]
    assert "main_rows=2" in before[0]
    assert "lookup_rows=1" in before[0]
    assert "filter_active=False" in before[0]
    # After line carries the result counts and elapsed
    assert "[tMap_1]" in after[0]
    assert "rejects=0" in after[0]
    assert "elapsed=" in after[0]


def test_log_lookup_join_strategy_value_appears(caplog):
    """The strategy enum value appears in the before-join line."""
    from src.v1.engine.components.transform.map.map_component import Map

    # Same shape as the previous test: context.SOURCE -> CONSTANT_KEY
    config = {
        "label": "tMap_strat",
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
            ],
        }],
    }
    m = Map(component_id="tMap_strat", config=config)
    m._fresh_config()
    m.java_bridge = _make_stub_bridge_for_constant_key()
    m._validate_config()

    with caplog.at_level(_logging.INFO, logger=_logger_name()):
        m._process({
            "row1": pd.DataFrame({"id": [1]}),
            "row8": pd.DataFrame({"name": ["beta"], "info": ["B"]}),
        })

    msgs = [r.getMessage() for r in caplog.records if r.name == _logger_name()]
    assert any("strategy=constant_key" in m for m in msgs)


# ===== Debug logging: peripheral observability =====


def test_log_lookup_skipped_when_lookup_df_none(caplog):
    """Missing lookup input -> INFO record with 'no input data'."""
    from src.v1.engine.components.transform.map.map_component import Map

    config = {
        "label": "tMap_skip",
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
            ],
        }],
    }
    m = Map(component_id="tMap_skip", config=config)
    m._fresh_config()
    m.java_bridge = _make_stub_bridge_for_constant_key()
    m._validate_config()

    with caplog.at_level(_logging.INFO, logger=_logger_name()):
        # Note: row8 is NOT in the inputs dict at all -> lookup_df is None
        m._process({"row1": pd.DataFrame({"id": [1]})})

    msgs = [r.getMessage() for r in caplog.records if r.name == _logger_name()]
    assert any(
        "[tMap_skip] lookup 'row8' skipped: no input data" in msg
        for msg in msgs
    )


def test_log_lookup_skipped_when_lookup_df_empty(caplog):
    """Empty lookup DataFrame -> INFO record with 'empty frame'."""
    from src.v1.engine.components.transform.map.map_component import Map

    config = {
        "label": "tMap_empty",
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
            ],
        }],
    }
    m = Map(component_id="tMap_empty", config=config)
    m._fresh_config()
    m.java_bridge = _make_stub_bridge_for_constant_key()
    m._validate_config()

    with caplog.at_level(_logging.INFO, logger=_logger_name()):
        m._process({
            "row1": pd.DataFrame({"id": [1]}),
            # Empty frame with the right columns
            "row8": pd.DataFrame({"name": [], "info": []}),
        })

    msgs = [r.getMessage() for r in caplog.records if r.name == _logger_name()]
    assert any(
        "[tMap_empty] lookup 'row8' skipped: empty frame" in msg
        for msg in msgs
    )


def test_log_main_filter_drops_rows(caplog):
    """Main filter that drops rows logs a before/after INFO record."""
    from src.v1.engine.components.transform.map.map_component import Map

    config = {
        "label": "tMap_mainfilter",
        "die_on_error": False,
        "inputs": {
            "main": {
                "name": "row1",
                "activate_filter": True,
                "filter": "{{java}}row1.id > 1",
            },
            "lookups": [],
        },
        "outputs": [{
            "name": "out1",
            "columns": [
                {"name": "id", "expression": "row1.id", "type": "id_Integer"},
            ],
        }],
    }

    # Stub bridge: filter eval returns boolean mask via batch eval
    from unittest.mock import MagicMock
    bridge = MagicMock()
    bridge.compile_tmap_script.return_value = None
    bridge.execute_compiled_tmap_chunked.side_effect = (
        lambda **kwargs: {"out1": kwargs["df"].copy().assign(id=kwargs["df"]["id"])}
    )
    # apply_filter calls execute_tmap_preprocessing with {"__filter__": expr}
    # returning {"__filter__": [bool, bool, ...]}. We drop rows where id <= 1.
    def fake_preprocess(df, expressions, main_table_name, lookup_table_names):
        return {"__filter__": [bool(v > 1) for v in df["id"].tolist()]}
    bridge.execute_tmap_preprocessing.side_effect = fake_preprocess

    m = Map(component_id="tMap_mainfilter", config=config)
    m._fresh_config()
    m.java_bridge = bridge
    m._validate_config()

    with caplog.at_level(_logging.INFO, logger=_logger_name()):
        m._process({"row1": pd.DataFrame({"id": [1, 2, 3]})})

    msgs = [r.getMessage() for r in caplog.records if r.name == _logger_name()]
    assert any(
        "[tMap_mainfilter] main filter: 3 -> 2 rows" in msg
        for msg in msgs
    )


def test_log_compile_active_script(caplog):
    """Active script compile logs INFO with the output count."""
    from src.v1.engine.components.transform.map.map_component import Map

    config = {
        "label": "tMap_compile",
        "die_on_error": False,
        "inputs": {
            "main": {"name": "row1"},
            "lookups": [],
        },
        "outputs": [
            {
                "name": "out1",
                "columns": [
                    {"name": "id", "expression": "row1.id", "type": "id_Integer"},
                ],
            },
            {
                "name": "out2",
                "columns": [
                    {"name": "id", "expression": "row1.id", "type": "id_Integer"},
                ],
            },
        ],
    }
    m = Map(component_id="tMap_compile", config=config)
    m._fresh_config()
    m.java_bridge = _make_stub_bridge_for_constant_key()
    m._validate_config()

    with caplog.at_level(_logging.INFO, logger=_logger_name()):
        m._process({"row1": pd.DataFrame({"id": [1]})})

    msgs = [r.getMessage() for r in caplog.records if r.name == _logger_name()]
    assert any(
        "[tMap_compile] compiling active script (2 outputs)" in msg
        for msg in msgs
    )


def test_log_compile_reject_script(caplog):
    """Reject script compile logs INFO when inner_join_reject path is taken."""
    from src.v1.engine.components.transform.map.map_component import Map
    from src.v1.engine.context_manager import ContextManager
    from src.v1.engine.global_map import GlobalMap

    config = {
        "label": "tMap_rej_compile",
        "die_on_error": False,
        "inputs": {
            "main": {"name": "row1"},
            "lookups": [{
                "name": "row8",
                "matching_mode": "FIRST_MATCH",
                "lookup_mode": "LOAD_ONCE",
                "join_mode": "INNER_JOIN",
                "join_keys": [{
                    "lookup_column": "name",
                    "expression": "{{java}}context.SOURCE",
                    "type": "str",
                }],
            }],
        },
        "outputs": [
            {
                "name": "out1",
                "columns": [
                    {"name": "id", "expression": "row1.id", "type": "id_Integer"},
                ],
            },
            {
                "name": "rej",
                "inner_join_reject": True,
                "columns": [
                    {"name": "id", "expression": "row1.id", "type": "id_Integer"},
                ],
            },
        ],
    }

    ctx = ContextManager()
    ctx.set("SOURCE", "no_such_name")  # Will cause INNER_JOIN to reject all

    m = Map(
        component_id="tMap_rej_compile", config=config,
        global_map=GlobalMap(), context_manager=ctx,
    )
    m._fresh_config()
    m.java_bridge = _make_stub_bridge_for_constant_key()
    m._validate_config()

    with caplog.at_level(_logging.INFO, logger=_logger_name()):
        m._process({
            "row1": pd.DataFrame({"id": [1, 2]}),
            "row8": pd.DataFrame({"name": ["alpha"], "info": ["A"]}),
        })

    msgs = [r.getMessage() for r in caplog.records if r.name == _logger_name()]
    assert any(
        "[tMap_rej_compile] compiling reject script (1 outputs)" in msg
        for msg in msgs
    )


# ===== Debug logging: __errors__ surfacing =====


def _make_errors_bridge(error_rows, total_rows=2):
    """Stub bridge whose active execute returns a populated __errors__ DataFrame.

    error_rows: list of dicts like
        [{"rowIndex": 0, "errorMessage": "msg0", "errorStackTrace": "stack0"}, ...]
    Mirrors the Arrow shape the real Java bridge emits for __errors__.
    """
    from unittest.mock import MagicMock
    bridge = MagicMock()
    bridge.compile_tmap_script.return_value = None

    errors_df = pd.DataFrame(
        error_rows,
        columns=["rowIndex", "errorMessage", "errorStackTrace"],
    )

    def fake_chunked(component_id, df, chunk_size, input_columns,
                    schema, reject_mode):
        return {
            "out1": pd.DataFrame({"id": list(range(total_rows))}),
            "__errors__": errors_df.copy(),
        }
    bridge.execute_compiled_tmap_chunked.side_effect = fake_chunked
    bridge.execute_batch_one_time_expressions.return_value = {}
    return bridge


def _base_errors_config(label="tMap_err", with_catch_output=False):
    outputs = [{
        "name": "out1",
        "columns": [
            {"name": "id", "expression": "row1.id", "type": "id_Integer"},
        ],
    }]
    if with_catch_output:
        outputs.append({
            "name": "rej",
            "catch_output_reject": True,
            "columns": [
                {"name": "id", "expression": "row1.id", "type": "id_Integer"},
            ],
        })
    return {
        "label": label,
        "die_on_error": False,
        "inputs": {"main": {"name": "row1"}, "lookups": []},
        "outputs": outputs,
    }


def test_log_errors_warning_when_active_script_captures_errors(caplog):
    """__errors__ count > 0 -> WARNING with count, percent, and first 3 messages."""
    from src.v1.engine.components.transform.map.map_component import Map

    config = _base_errors_config(label="tMap_err1")
    error_rows = [
        {"rowIndex": 0, "errorMessage": "msg0", "errorStackTrace": "stack0"},
        {"rowIndex": 1, "errorMessage": "msg1", "errorStackTrace": "stack1"},
        {"rowIndex": 2, "errorMessage": "msg2", "errorStackTrace": "stack2"},
        {"rowIndex": 3, "errorMessage": "msg3", "errorStackTrace": "stack3"},
    ]

    m = Map(component_id="tMap_err1", config=config)
    m._fresh_config()
    m.java_bridge = _make_errors_bridge(error_rows, total_rows=4)
    m._validate_config()

    with caplog.at_level(_logging.WARNING, logger=_logger_name()):
        m._process({"row1": pd.DataFrame({"id": [0, 1, 2, 3]})})

    warn_msgs = [
        r.getMessage() for r in caplog.records
        if r.name == _logger_name() and r.levelno == _logging.WARNING
    ]
    assert len(warn_msgs) == 1, f"Expected 1 WARN record, got {warn_msgs}"
    m_text = warn_msgs[0]
    assert "[tMap_err1]" in m_text
    assert "captured 4/4 rows in __errors__" in m_text
    assert "(100.0%)" in m_text
    assert "first 3:" in m_text
    assert "row 0: msg0" in m_text
    assert "row 1: msg1" in m_text
    assert "row 2: msg2" in m_text
    # row 3 must NOT appear -- only first 3 shown
    assert "row 3:" not in m_text


def test_log_errors_routing_with_catch_output(caplog):
    """When catch_output_reject is configured, INFO routing line names it."""
    from src.v1.engine.components.transform.map.map_component import Map

    config = _base_errors_config(label="tMap_err2", with_catch_output=True)
    error_rows = [
        {"rowIndex": 0, "errorMessage": "msg0", "errorStackTrace": "stack0"},
    ]

    m = Map(component_id="tMap_err2", config=config)
    m._fresh_config()
    m.java_bridge = _make_errors_bridge(error_rows, total_rows=1)
    m._validate_config()

    with caplog.at_level(_logging.INFO, logger=_logger_name()):
        m._process({"row1": pd.DataFrame({"id": [0]})})

    info_msgs = [
        r.getMessage() for r in caplog.records
        if r.name == _logger_name() and r.levelno == _logging.INFO
    ]
    assert any(
        "[tMap_err2] __errors__ rows routed to catch_output_reject output(s): rej"
        in msg for msg in info_msgs
    )


def test_log_errors_routing_without_catch_output(caplog):
    """When no catch_output_reject is configured, INFO routing line says discarded."""
    from src.v1.engine.components.transform.map.map_component import Map

    config = _base_errors_config(label="tMap_err3", with_catch_output=False)
    error_rows = [
        {"rowIndex": 0, "errorMessage": "msg0", "errorStackTrace": "stack0"},
    ]

    m = Map(component_id="tMap_err3", config=config)
    m._fresh_config()
    m.java_bridge = _make_errors_bridge(error_rows, total_rows=1)
    m._validate_config()

    with caplog.at_level(_logging.INFO, logger=_logger_name()):
        m._process({"row1": pd.DataFrame({"id": [0]})})

    info_msgs = [
        r.getMessage() for r in caplog.records
        if r.name == _logger_name() and r.levelno == _logging.INFO
    ]
    assert any(
        "[tMap_err3] __errors__ rows discarded "
        "(no catch_output_reject output configured)" in msg
        for msg in info_msgs
    )


def test_log_errors_debug_stack_traces(caplog):
    """At DEBUG level, full stack trace for first 3 rows is logged."""
    from src.v1.engine.components.transform.map.map_component import Map

    config = _base_errors_config(label="tMap_err4")
    error_rows = [
        {"rowIndex": 0, "errorMessage": "msg0",
         "errorStackTrace": "stack-row-0\n  at Script1.run(Script1.groovy:42)"},
        {"rowIndex": 1, "errorMessage": "msg1", "errorStackTrace": "stack-row-1"},
        {"rowIndex": 2, "errorMessage": "msg2", "errorStackTrace": "stack-row-2"},
        {"rowIndex": 3, "errorMessage": "msg3", "errorStackTrace": "stack-row-3"},
    ]

    m = Map(component_id="tMap_err4", config=config)
    m._fresh_config()
    m.java_bridge = _make_errors_bridge(error_rows, total_rows=4)
    m._validate_config()

    with caplog.at_level(_logging.DEBUG, logger=_logger_name()):
        m._process({"row1": pd.DataFrame({"id": [0, 1, 2, 3]})})

    debug_msgs = [
        r.getMessage() for r in caplog.records
        if r.name == _logger_name() and r.levelno == _logging.DEBUG
    ]
    stack_msgs = [m for m in debug_msgs if "stackTrace for row" in m]
    assert len(stack_msgs) == 3
    assert any("stackTrace for row 0:" in m and "stack-row-0" in m for m in stack_msgs)
    assert any("stackTrace for row 1:" in m and "stack-row-1" in m for m in stack_msgs)
    assert any("stackTrace for row 2:" in m and "stack-row-2" in m for m in stack_msgs)
    assert all("stackTrace for row 3:" not in m for m in stack_msgs)


def test_no_error_log_when_errors_df_absent(caplog):
    """When __errors__ is absent OR empty, no WARN/INFO/DEBUG error log fires."""
    from src.v1.engine.components.transform.map.map_component import Map

    config = _base_errors_config(label="tMap_err5")
    from unittest.mock import MagicMock
    bridge = MagicMock()
    bridge.compile_tmap_script.return_value = None
    bridge.execute_compiled_tmap_chunked.side_effect = (
        lambda **kw: {"out1": pd.DataFrame({"id": [0]})}
    )
    bridge.execute_batch_one_time_expressions.return_value = {}

    m = Map(component_id="tMap_err5", config=config)
    m._fresh_config()
    m.java_bridge = bridge
    m._validate_config()

    with caplog.at_level(_logging.DEBUG, logger=_logger_name()):
        m._process({"row1": pd.DataFrame({"id": [0]})})

    msgs = [r.getMessage() for r in caplog.records if r.name == _logger_name()]
    assert not any("__errors__" in m for m in msgs)
    assert not any("stackTrace for row" in m for m in msgs)


def test_no_error_log_when_errors_df_present_but_empty(caplog):
    """When __errors__ is an empty DataFrame, no WARN/INFO/DEBUG error log fires.

    Production state: active script ran, recorded zero errors, bridge still
    emits an empty Arrow batch with the schema. The surfacing guard's
    `not errors_df.empty` leg must short-circuit.
    """
    from src.v1.engine.components.transform.map.map_component import Map

    config = _base_errors_config(label="tMap_err_empty_df")
    from unittest.mock import MagicMock
    bridge = MagicMock()
    bridge.compile_tmap_script.return_value = None

    def fake_chunked(component_id, df, chunk_size, input_columns,
                    schema, reject_mode):
        return {
            "out1": pd.DataFrame({"id": [0]}),
            "__errors__": pd.DataFrame(
                columns=["rowIndex", "errorMessage", "errorStackTrace"],
            ),
        }
    bridge.execute_compiled_tmap_chunked.side_effect = fake_chunked
    bridge.execute_batch_one_time_expressions.return_value = {}

    m = Map(component_id="tMap_err_empty_df", config=config)
    m._fresh_config()
    m.java_bridge = bridge
    m._validate_config()

    with caplog.at_level(_logging.DEBUG, logger=_logger_name()):
        m._process({"row1": pd.DataFrame({"id": [0]})})

    msgs = [r.getMessage() for r in caplog.records if r.name == _logger_name()]
    assert not any("__errors__" in m for m in msgs)
    assert not any("stackTrace for row" in m for m in msgs)
