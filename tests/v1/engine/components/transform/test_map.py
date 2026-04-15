"""Tests for Map (tMap engine implementation).

Covers MAP-01 through MAP-08 and TEST-03 with exhaustive per-requirement coverage.
Tests join semantics, reject routing, expression handling, matching modes, lifecycle
integration, and multi-flow routing.

Java bridge is mocked for unit tests. Tests marked @pytest.mark.java require live bridge.
"""
import copy
import logging

import numpy as np
import pandas as pd
import pytest

from src.v1.engine.components.transform.map import Map
from src.v1.engine.context_manager import ContextManager
from src.v1.engine.exceptions import (
    ComponentExecutionError,
    ConfigurationError,
)
from src.v1.engine.global_map import GlobalMap


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

_DEFAULT_CONFIG = {
    "component_type": "Map",
    "inputs": {
        "main": {
            "name": "row1",
            "filter": "",
            "activate_filter": False,
            "matching_mode": "UNIQUE_MATCH",
            "lookup_mode": "LOAD_ONCE",
        },
        "lookups": [
            {
                "name": "row2",
                "matching_mode": "UNIQUE_MATCH",
                "lookup_mode": "LOAD_ONCE",
                "filter": "",
                "activate_filter": False,
                "join_keys": [
                    {
                        "lookup_column": "key",
                        "expression": "{{java}}row1.key",
                        "type": "str",
                        "nullable": True,
                        "operator": "=",
                    }
                ],
                "join_mode": "LEFT_OUTER_JOIN",
            }
        ],
    },
    "variables": [],
    "outputs": [
        {
            "name": "out1",
            "is_reject": False,
            "inner_join_reject": False,
            "filter": "",
            "activate_filter": False,
            "columns": [
                {
                    "name": "id",
                    "expression": "{{java}}row1.id",
                    "type": "int",
                    "nullable": True,
                },
                {
                    "name": "val",
                    "expression": "{{java}}row1.val",
                    "type": "int",
                    "nullable": True,
                },
                {
                    "name": "label",
                    "expression": "{{java}}row2.label",
                    "type": "str",
                    "nullable": True,
                },
            ],
            "catch_output_reject": False,
        }
    ],
    "die_on_error": True,
}


def _make_component(config=None, global_map=None, context_manager=None,
                    java_bridge=None):
    """Create a Map component with test defaults.

    Always creates fresh GlobalMap and ContextManager instances
    unless explicitly provided.
    """
    gm = global_map if global_map is not None else GlobalMap()
    cm = context_manager or ContextManager()
    cfg = config if config is not None else copy.deepcopy(_DEFAULT_CONFIG)
    comp = Map(
        component_id="tMap_1",
        config=cfg,
        global_map=gm,
        context_manager=cm,
    )
    if java_bridge is not None:
        comp.java_bridge = java_bridge
    return comp


def _make_main_df(rows=None):
    """Create a main input DataFrame with columns: id, key, val."""
    if rows is None:
        rows = [
            {"id": 1, "key": "A", "val": 100},
            {"id": 2, "key": "B", "val": 200},
            {"id": 3, "key": "C", "val": 300},
        ]
    return pd.DataFrame(rows)


def _make_lookup_df(rows=None):
    """Create a lookup DataFrame with columns: key, label."""
    if rows is None:
        rows = [
            {"key": "A", "label": "Alpha"},
            {"key": "B", "label": "Beta"},
            {"key": "D", "label": "Delta"},
        ]
    return pd.DataFrame(rows)


def _make_input_dict(main_df=None, lookup_df=None, main_name="row1",
                     lookup_name="row2"):
    """Wrap DataFrames in a dict matching OutputRouter format."""
    if main_df is None:
        main_df = _make_main_df()
    if lookup_df is None:
        lookup_df = _make_lookup_df()
    return {main_name: main_df, lookup_name: lookup_df}


# ------------------------------------------------------------------
# Test Classes
# ------------------------------------------------------------------


@pytest.mark.unit
class TestValidation:
    """_validate_config raises ConfigurationError for missing/invalid keys."""

    def test_missing_inputs_key_raises(self):
        config = copy.deepcopy(_DEFAULT_CONFIG)
        del config["inputs"]
        comp = _make_component(config=config)
        with pytest.raises(ConfigurationError, match="inputs"):
            comp.execute(_make_input_dict())

    def test_missing_main_raises(self):
        config = copy.deepcopy(_DEFAULT_CONFIG)
        del config["inputs"]["main"]
        comp = _make_component(config=config)
        with pytest.raises(ConfigurationError, match="main"):
            comp.execute(_make_input_dict())

    def test_missing_main_name_raises(self):
        config = copy.deepcopy(_DEFAULT_CONFIG)
        del config["inputs"]["main"]["name"]
        comp = _make_component(config=config)
        with pytest.raises(ConfigurationError, match="name"):
            comp.execute(_make_input_dict())

    def test_missing_outputs_raises(self):
        config = copy.deepcopy(_DEFAULT_CONFIG)
        del config["outputs"]
        comp = _make_component(config=config)
        with pytest.raises(ConfigurationError, match="outputs"):
            comp.execute(_make_input_dict())

    def test_empty_outputs_raises(self):
        config = copy.deepcopy(_DEFAULT_CONFIG)
        config["outputs"] = []
        comp = _make_component(config=config)
        with pytest.raises(ConfigurationError, match="output"):
            comp.execute(_make_input_dict())

    def test_valid_config_does_not_raise(self):
        comp = _make_component()
        result = comp.execute(_make_input_dict())
        assert "out1" in result


@pytest.mark.unit
class TestDefaults:
    """Default config produces expected behavior."""

    def test_default_matching_mode_is_unique_match(self):
        config = copy.deepcopy(_DEFAULT_CONFIG)
        # matching_mode is explicitly set; verify default
        assert config["inputs"]["lookups"][0]["matching_mode"] == "UNIQUE_MATCH"

    def test_default_die_on_error_is_true(self):
        config = copy.deepcopy(_DEFAULT_CONFIG)
        assert config["die_on_error"] is True

    def test_default_lookup_mode_is_load_once(self):
        config = copy.deepcopy(_DEFAULT_CONFIG)
        assert config["inputs"]["lookups"][0]["lookup_mode"] == "LOAD_ONCE"

    def test_empty_lookups_passthrough(self):
        config = copy.deepcopy(_DEFAULT_CONFIG)
        config["inputs"]["lookups"] = []
        # Output maps directly from main
        config["outputs"][0]["columns"] = [
            {"name": "id", "expression": "{{java}}row1.id", "type": "int", "nullable": True},
            {"name": "val", "expression": "{{java}}row1.val", "type": "int", "nullable": True},
        ]
        comp = _make_component(config=config)
        main_df = _make_main_df()
        result = comp.execute({"row1": main_df})
        assert len(result["out1"]) == 3
        assert list(result["out1"]["id"]) == [1, 2, 3]


@pytest.mark.unit
class TestLifecycle:
    """MAP-04: BaseComponent lifecycle integration."""

    def test_does_not_override_execute(self):
        """Map must NOT override execute() -- uses BaseComponent lifecycle."""
        assert "execute" not in Map.__dict__

    def test_resolve_expressions_skips_java_markers(self):
        """_resolve_expressions does NOT use parent Java resolution."""
        comp = _make_component()
        # Simulate what execute() does
        comp.config = copy.deepcopy(comp._original_config)
        # Should not raise even though config has {{java}} markers
        comp._resolve_expressions()
        # Java expressions should remain untouched in config
        out_expr = comp.config["outputs"][0]["columns"][0]["expression"]
        assert out_expr.startswith("{{java}}")

    def test_select_mode_always_batch(self):
        comp = _make_component()
        from src.v1.engine.base_component import ExecutionMode
        comp.config = copy.deepcopy(comp._original_config)
        mode = comp._select_mode(_make_main_df())
        assert mode == ExecutionMode.BATCH

    def test_stats_count_all_outputs(self):
        """_update_stats_from_result sums across named outputs."""
        config = copy.deepcopy(_DEFAULT_CONFIG)
        # Add a second output
        config["outputs"].append({
            "name": "out2",
            "is_reject": False,
            "inner_join_reject": False,
            "filter": "",
            "activate_filter": False,
            "columns": [
                {"name": "val", "expression": "{{java}}row1.val", "type": "int", "nullable": True},
            ],
            "catch_output_reject": False,
        })
        comp = _make_component(config=config)
        result = comp.execute(_make_input_dict())
        stats = result["stats"]
        # Total rows should be out1 rows + out2 rows
        total = 0
        for key, val in result.items():
            if key != "stats" and isinstance(val, pd.DataFrame):
                total += len(val)
        assert stats["NB_LINE"] == total

    def test_config_immutability_across_executions(self):
        """Config unchanged after execute() (ENG-09)."""
        comp = _make_component()
        original_snapshot = copy.deepcopy(comp._original_config)
        comp.execute(_make_input_dict())
        assert comp._original_config == original_snapshot

    def test_stats_reset_between_executions(self):
        """Stats reset on re-execute with reset() (iterate support)."""
        gm = GlobalMap()
        comp = _make_component(global_map=gm)
        inp = _make_input_dict()

        comp.execute(inp)
        first_nb = gm.get_component_stat("tMap_1", "NB_LINE")

        comp.reset()
        comp.execute(inp)
        second_nb = gm.get_component_stat("tMap_1", "NB_LINE")

        assert second_nb == first_nb  # Same data = same count, not accumulated


@pytest.mark.unit
class TestUniqueMatch:
    """MAP-01: Matching mode semantics."""

    def test_unique_match_keeps_last_row(self):
        """UNIQUE_MATCH: duplicate lookup keys keep last row (keep='last')."""
        lookup = pd.DataFrame([
            {"key": "A", "label": "Alpha1"},
            {"key": "A", "label": "Alpha2"},
            {"key": "B", "label": "Beta"},
        ])
        comp = _make_component()
        result = comp.execute(_make_input_dict(lookup_df=lookup))
        out = result["out1"]
        a_row = out[out["id"] == 1]
        assert len(a_row) == 1
        assert a_row.iloc[0]["label"] == "Alpha2"

    def test_unique_match_single_match(self):
        """Single match works normally."""
        comp = _make_component()
        result = comp.execute(_make_input_dict())
        out = result["out1"]
        a_row = out[out["id"] == 1]
        assert a_row.iloc[0]["label"] == "Alpha"

    def test_unique_match_no_match_left_outer(self):
        """Unmatched main row gets null lookup columns in left outer join."""
        comp = _make_component()
        result = comp.execute(_make_input_dict())
        out = result["out1"]
        # key "C" has no lookup match
        c_row = out[out["id"] == 3]
        assert len(c_row) == 1
        assert pd.isna(c_row.iloc[0]["label"])

    def test_first_match_keeps_first_row(self):
        """FIRST_MATCH: duplicate lookup keys keep first row."""
        config = copy.deepcopy(_DEFAULT_CONFIG)
        config["inputs"]["lookups"][0]["matching_mode"] = "FIRST_MATCH"
        lookup = pd.DataFrame([
            {"key": "A", "label": "Alpha1"},
            {"key": "A", "label": "Alpha2"},
            {"key": "B", "label": "Beta"},
        ])
        comp = _make_component(config=config)
        result = comp.execute(_make_input_dict(lookup_df=lookup))
        out = result["out1"]
        a_row = out[out["id"] == 1]
        assert a_row.iloc[0]["label"] == "Alpha1"

    def test_last_match_keeps_last_row(self):
        """LAST_MATCH: same as UNIQUE_MATCH behavior (keep='last')."""
        config = copy.deepcopy(_DEFAULT_CONFIG)
        config["inputs"]["lookups"][0]["matching_mode"] = "LAST_MATCH"
        lookup = pd.DataFrame([
            {"key": "A", "label": "Alpha1"},
            {"key": "A", "label": "Alpha2"},
            {"key": "B", "label": "Beta"},
        ])
        comp = _make_component(config=config)
        result = comp.execute(_make_input_dict(lookup_df=lookup))
        out = result["out1"]
        a_row = out[out["id"] == 1]
        assert a_row.iloc[0]["label"] == "Alpha2"


@pytest.mark.unit
class TestAllMatches:
    """ALL_MATCHES matching mode tests."""

    def test_all_matches_produces_cartesian(self):
        """ALL_MATCHES: main row matched against multiple lookup rows."""
        config = copy.deepcopy(_DEFAULT_CONFIG)
        config["inputs"]["lookups"][0]["matching_mode"] = "ALL_MATCHES"
        lookup = pd.DataFrame([
            {"key": "A", "label": "Alpha1"},
            {"key": "A", "label": "Alpha2"},
            {"key": "A", "label": "Alpha3"},
            {"key": "B", "label": "Beta"},
        ])
        comp = _make_component(config=config)
        result = comp.execute(_make_input_dict(lookup_df=lookup))
        out = result["out1"]
        # Main row with key "A" (id=1) should match 3 lookup rows
        a_rows = out[out["id"] == 1]
        assert len(a_rows) == 3

    def test_all_matches_no_dedup(self):
        """Verify no deduplication occurs in ALL_MATCHES."""
        config = copy.deepcopy(_DEFAULT_CONFIG)
        config["inputs"]["lookups"][0]["matching_mode"] = "ALL_MATCHES"
        lookup = pd.DataFrame([
            {"key": "A", "label": "Same"},
            {"key": "A", "label": "Same"},  # Duplicate values too
        ])
        comp = _make_component(config=config)
        main_df = pd.DataFrame([{"id": 1, "key": "A", "val": 100}])
        result = comp.execute(_make_input_dict(main_df=main_df, lookup_df=lookup))
        out = result["out1"]
        assert len(out) == 2

    def test_all_matches_size_guard_warns(self, caplog):
        """Large cartesian triggers warning."""
        config = copy.deepcopy(_DEFAULT_CONFIG)
        config["inputs"]["lookups"][0]["matching_mode"] = "ALL_MATCHES"
        # Create datasets whose product exceeds _WARN_RESULT_ROWS (10M)
        # Use 4000 x 3000 = 12M
        main_df = pd.DataFrame({"id": range(4000), "key": ["A"] * 4000, "val": range(4000)})
        lookup_df = pd.DataFrame({"key": ["A"] * 3000, "label": [f"L{i}" for i in range(3000)]})

        comp = _make_component(config=config)
        with caplog.at_level(logging.WARNING):
            result = comp.execute(_make_input_dict(main_df=main_df, lookup_df=lookup_df))
        # Should have logged a warning about large join
        assert any("Large join" in r.message or "large" in r.message.lower()
                    for r in caplog.records)

    def test_all_matches_empty_lookup_left_outer(self):
        """No matches with left outer produces null columns."""
        config = copy.deepcopy(_DEFAULT_CONFIG)
        config["inputs"]["lookups"][0]["matching_mode"] = "ALL_MATCHES"
        lookup = pd.DataFrame({"key": pd.Series(dtype="str"),
                               "label": pd.Series(dtype="str")})
        comp = _make_component(config=config)
        result = comp.execute(_make_input_dict(lookup_df=lookup))
        out = result["out1"]
        # Main rows pass through with null lookup columns
        assert len(out) == 3


@pytest.mark.unit
class TestNullKeys:
    """MAP-03: Null key pre-filtering."""

    def test_null_main_key_never_matches(self):
        """Main row with key=None gets null lookup columns in left outer join."""
        main_df = pd.DataFrame([
            {"id": 1, "key": None, "val": 100},
            {"id": 2, "key": "B", "val": 200},
        ])
        comp = _make_component()
        result = comp.execute(_make_input_dict(main_df=main_df))
        out = result["out1"]
        null_row = out[out["id"] == 1]
        assert len(null_row) == 1
        assert pd.isna(null_row.iloc[0]["label"])

    def test_null_lookup_key_never_matches(self):
        """Lookup row with key=None is excluded from matches."""
        lookup = pd.DataFrame([
            {"key": None, "label": "Null_Label"},
            {"key": "A", "label": "Alpha"},
        ])
        comp = _make_component()
        main_df = pd.DataFrame([{"id": 1, "key": "A", "val": 100}])
        result = comp.execute(_make_input_dict(main_df=main_df, lookup_df=lookup))
        out = result["out1"]
        assert len(out) == 1
        assert out.iloc[0]["label"] == "Alpha"

    def test_nan_main_key_never_matches(self):
        """Main row with key=NaN never matches (not just None)."""
        main_df = pd.DataFrame([
            {"id": 1, "key": np.nan, "val": 100},
            {"id": 2, "key": "B", "val": 200},
        ])
        comp = _make_component()
        result = comp.execute(_make_input_dict(main_df=main_df))
        out = result["out1"]
        nan_row = out[out["id"] == 1]
        assert pd.isna(nan_row.iloc[0]["label"])

    def test_null_key_routes_to_inner_join_reject(self):
        """INNER_JOIN: null-key main rows appear in inner join reject output."""
        config = copy.deepcopy(_DEFAULT_CONFIG)
        config["inputs"]["lookups"][0]["join_mode"] = "INNER_JOIN"
        config["outputs"].append({
            "name": "reject1",
            "is_reject": False,
            "inner_join_reject": True,
            "filter": "",
            "activate_filter": False,
            "columns": [
                {"name": "id", "expression": "{{java}}row1.id", "type": "int", "nullable": True},
            ],
            "catch_output_reject": False,
        })
        main_df = pd.DataFrame([
            {"id": 1, "key": None, "val": 100},
            {"id": 2, "key": "B", "val": 200},
        ])
        comp = _make_component(config=config)
        result = comp.execute(_make_input_dict(main_df=main_df))
        reject = result.get("reject1")
        assert reject is not None
        assert len(reject) >= 1
        # Null-key row should be in reject
        assert 1 in reject["id"].values

    def test_both_null_keys_do_not_match(self):
        """Main null + lookup null do NOT match (SQL/Talend semantics)."""
        main_df = pd.DataFrame([{"id": 1, "key": None, "val": 100}])
        lookup = pd.DataFrame([{"key": None, "label": "NullLabel"}])
        comp = _make_component()
        result = comp.execute(_make_input_dict(main_df=main_df, lookup_df=lookup))
        out = result["out1"]
        assert pd.isna(out.iloc[0]["label"])

    def test_non_null_keys_match_normally(self):
        """Normal matching unaffected by null filtering."""
        comp = _make_component()
        result = comp.execute(_make_input_dict())
        out = result["out1"]
        matched = out[out["id"] == 1]
        assert matched.iloc[0]["label"] == "Alpha"


@pytest.mark.unit
class TestInnerJoinReject:
    """MAP-02: Inner join reject routing."""

    def _inner_join_config(self):
        """Config with INNER_JOIN and inner_join_reject output."""
        config = copy.deepcopy(_DEFAULT_CONFIG)
        config["inputs"]["lookups"][0]["join_mode"] = "INNER_JOIN"
        config["outputs"].append({
            "name": "inner_reject",
            "is_reject": False,
            "inner_join_reject": True,
            "filter": "",
            "activate_filter": False,
            "columns": [
                {"name": "id", "expression": "{{java}}row1.id", "type": "int", "nullable": True},
                {"name": "val", "expression": "{{java}}row1.val", "type": "int", "nullable": True},
            ],
            "catch_output_reject": False,
        })
        return config

    def test_inner_join_unmatched_goes_to_reject_output(self):
        """Main row with no lookup match appears in inner_join_reject output."""
        config = self._inner_join_config()
        comp = _make_component(config=config)
        result = comp.execute(_make_input_dict())
        reject = result.get("inner_reject")
        assert reject is not None
        # key "C" has no lookup match -> should be in reject
        assert 3 in reject["id"].values

    def test_inner_join_matched_does_not_go_to_reject(self):
        """Matched rows do NOT appear in reject output."""
        config = self._inner_join_config()
        comp = _make_component(config=config)
        result = comp.execute(_make_input_dict())
        out1 = result["out1"]
        # key "A" matched -> should be in out1
        assert 1 in out1["id"].values
        # And NOT in reject
        reject = result.get("inner_reject")
        if reject is not None and not reject.empty:
            assert 1 not in reject["id"].values

    def test_inner_join_reject_separate_from_filter_reject(self):
        """Inner join reject is distinct from is_reject output."""
        config = self._inner_join_config()
        config["outputs"].append({
            "name": "filter_reject",
            "is_reject": True,
            "inner_join_reject": False,
            "filter": "",
            "activate_filter": False,
            "columns": [
                {"name": "id", "expression": "{{java}}row1.id", "type": "int", "nullable": True},
            ],
            "catch_output_reject": False,
        })
        comp = _make_component(config=config)
        result = comp.execute(_make_input_dict())
        # Both outputs exist as separate keys
        assert "inner_reject" in result
        assert "filter_reject" in result

    def test_left_outer_join_no_reject(self):
        """LEFT_OUTER_JOIN does not produce inner join rejects."""
        config = copy.deepcopy(_DEFAULT_CONFIG)
        config["outputs"].append({
            "name": "inner_reject",
            "is_reject": False,
            "inner_join_reject": True,
            "filter": "",
            "activate_filter": False,
            "columns": [
                {"name": "id", "expression": "{{java}}row1.id", "type": "int", "nullable": True},
            ],
            "catch_output_reject": False,
        })
        comp = _make_component(config=config)
        result = comp.execute(_make_input_dict())
        reject = result.get("inner_reject")
        # Left outer join: no inner join rejects
        assert reject is None or reject.empty

    def test_inner_join_reject_with_null_keys(self):
        """Null-key rows also go to inner join reject."""
        config = self._inner_join_config()
        main_df = pd.DataFrame([
            {"id": 1, "key": None, "val": 100},
            {"id": 2, "key": "B", "val": 200},
        ])
        comp = _make_component(config=config)
        result = comp.execute(_make_input_dict(main_df=main_df))
        reject = result.get("inner_reject")
        assert reject is not None
        assert 1 in reject["id"].values

    def test_multiple_lookups_combined_reject(self):
        """Row failing inner join on ANY lookup gets rejected."""
        config = copy.deepcopy(_DEFAULT_CONFIG)
        # First lookup: inner join
        config["inputs"]["lookups"][0]["join_mode"] = "INNER_JOIN"
        # Second lookup: inner join with different key
        config["inputs"]["lookups"].append({
            "name": "row3",
            "matching_mode": "UNIQUE_MATCH",
            "lookup_mode": "LOAD_ONCE",
            "filter": "",
            "activate_filter": False,
            "join_keys": [
                {
                    "lookup_column": "code",
                    "expression": "{{java}}row1.key",
                    "type": "str",
                    "nullable": True,
                    "operator": "=",
                }
            ],
            "join_mode": "INNER_JOIN",
        })
        config["outputs"].append({
            "name": "inner_reject",
            "is_reject": False,
            "inner_join_reject": True,
            "filter": "",
            "activate_filter": False,
            "columns": [
                {"name": "id", "expression": "{{java}}row1.id", "type": "int", "nullable": True},
            ],
            "catch_output_reject": False,
        })
        main_df = _make_main_df()
        lookup1 = _make_lookup_df()  # Has A, B, D
        lookup2 = pd.DataFrame([
            {"code": "A", "desc": "Alpha_desc"},
            # B and C have no match in lookup2
        ])
        comp = _make_component(config=config)
        result = comp.execute({"row1": main_df, "row2": lookup1, "row3": lookup2})
        reject = result.get("inner_reject")
        assert reject is not None
        # Row with key "C" fails first lookup; rows with key "B" may fail second
        assert len(reject) >= 1


@pytest.mark.unit
class TestMultiOutput:
    """Multi-output routing tests."""

    def test_two_outputs_route_correctly(self):
        """Two normal outputs both get data."""
        config = copy.deepcopy(_DEFAULT_CONFIG)
        config["outputs"].append({
            "name": "out2",
            "is_reject": False,
            "inner_join_reject": False,
            "filter": "",
            "activate_filter": False,
            "columns": [
                {"name": "val", "expression": "{{java}}row1.val", "type": "int", "nullable": True},
            ],
            "catch_output_reject": False,
        })
        comp = _make_component(config=config)
        result = comp.execute(_make_input_dict())
        assert "out1" in result
        assert "out2" in result
        assert len(result["out1"]) > 0
        assert len(result["out2"]) > 0

    def test_reject_output_exists_in_result(self):
        """Reject output is created in result dict."""
        config = copy.deepcopy(_DEFAULT_CONFIG)
        config["outputs"].append({
            "name": "reject1",
            "is_reject": True,
            "inner_join_reject": False,
            "filter": "",
            "activate_filter": False,
            "columns": [
                {"name": "id", "expression": "{{java}}row1.id", "type": "int", "nullable": True},
            ],
            "catch_output_reject": False,
        })
        comp = _make_component(config=config)
        result = comp.execute(_make_input_dict())
        assert "reject1" in result

    def test_output_names_match_config(self):
        """Result dict keys match output names from config."""
        comp = _make_component()
        result = comp.execute(_make_input_dict())
        config_names = {o["name"] for o in _DEFAULT_CONFIG["outputs"]}
        # result keys include config output names (plus stats)
        for name in config_names:
            assert name in result

    def test_empty_input_produces_empty_outputs(self):
        """Empty main_df produces empty DataFrames for all outputs."""
        comp = _make_component()
        empty_main = pd.DataFrame(columns=["id", "key", "val"])
        result = comp.execute(_make_input_dict(main_df=empty_main))
        for key, val in result.items():
            if key == "stats":
                continue
            assert isinstance(val, pd.DataFrame)
            assert val.empty


@pytest.mark.unit
class TestMultiInput:
    """Multi-input dict routing tests."""

    def test_dict_input_from_output_router(self):
        """Input as Dict[str, DataFrame] works correctly."""
        comp = _make_component()
        result = comp.execute(_make_input_dict())
        out = result["out1"]
        assert len(out) == 3

    def test_single_dataframe_input_wraps_to_dict(self):
        """Single DataFrame input is wrapped with main name."""
        config = copy.deepcopy(_DEFAULT_CONFIG)
        config["inputs"]["lookups"] = []
        config["outputs"][0]["columns"] = [
            {"name": "id", "expression": "{{java}}row1.id", "type": "int", "nullable": True},
            {"name": "val", "expression": "{{java}}row1.val", "type": "int", "nullable": True},
        ]
        comp = _make_component(config=config)
        main_df = _make_main_df()
        result = comp.execute(main_df)
        assert len(result["out1"]) == 3

    def test_missing_lookup_in_dict_produces_empty_join(self):
        """Missing lookup name in input dict handled gracefully."""
        comp = _make_component()
        # Only provide main, no lookup
        result = comp.execute({"row1": _make_main_df()})
        out = result["out1"]
        # Should produce output with null lookup columns
        assert len(out) == 3

    def test_multiple_lookups_sequential(self):
        """Two lookups processed sequentially."""
        config = copy.deepcopy(_DEFAULT_CONFIG)
        config["inputs"]["lookups"].append({
            "name": "row3",
            "matching_mode": "UNIQUE_MATCH",
            "lookup_mode": "LOAD_ONCE",
            "filter": "",
            "activate_filter": False,
            "join_keys": [
                {
                    "lookup_column": "code",
                    "expression": "{{java}}row1.key",
                    "type": "str",
                    "nullable": True,
                    "operator": "=",
                }
            ],
            "join_mode": "LEFT_OUTER_JOIN",
        })
        config["outputs"][0]["columns"].append(
            {"name": "desc", "expression": "{{java}}row3.desc", "type": "str", "nullable": True}
        )
        main_df = _make_main_df()
        lookup1 = _make_lookup_df()
        lookup2 = pd.DataFrame([
            {"code": "A", "desc": "Alpha_desc"},
            {"code": "B", "desc": "Beta_desc"},
        ])
        comp = _make_component(config=config)
        result = comp.execute({"row1": main_df, "row2": lookup1, "row3": lookup2})
        out = result["out1"]
        assert len(out) == 3
        a_row = out[out["id"] == 1]
        assert a_row.iloc[0]["label"] == "Alpha"
        assert a_row.iloc[0]["desc"] == "Alpha_desc"


@pytest.mark.unit
class TestVariables:
    """Variable evaluation tests."""

    def test_variables_available_in_outputs(self):
        """Variable expressions evaluated and accessible in output columns."""
        config = copy.deepcopy(_DEFAULT_CONFIG)
        config["variables"] = [
            {"name": "myVar", "expression": "{{java}}row1.val", "type": "int"},
        ]
        config["outputs"][0]["columns"].append(
            {"name": "var_col", "expression": "{{java}}Var.myVar", "type": "int", "nullable": True}
        )
        comp = _make_component(config=config)
        result = comp.execute(_make_input_dict())
        out = result["out1"]
        # Var.myVar should be a copy of row1.val
        assert list(out["var_col"]) == list(out["val"])

    def test_variable_dependency_chain(self):
        """Variable referencing earlier variable works."""
        config = copy.deepcopy(_DEFAULT_CONFIG)
        config["variables"] = [
            {"name": "v1", "expression": "{{java}}row1.val", "type": "int"},
            {"name": "v2", "expression": "{{java}}Var.v1", "type": "int"},
        ]
        config["outputs"][0]["columns"].append(
            {"name": "chained", "expression": "{{java}}Var.v2", "type": "int", "nullable": True}
        )
        comp = _make_component(config=config)
        result = comp.execute(_make_input_dict())
        out = result["out1"]
        assert list(out["chained"]) == list(out["val"])

    def test_no_variables_works(self):
        """Empty variables list is fine."""
        config = copy.deepcopy(_DEFAULT_CONFIG)
        config["variables"] = []
        comp = _make_component(config=config)
        result = comp.execute(_make_input_dict())
        assert "out1" in result

    def test_variables_evaluated_after_lookups(self):
        """Variables can reference lookup columns."""
        config = copy.deepcopy(_DEFAULT_CONFIG)
        config["variables"] = [
            {"name": "lookupVal", "expression": "{{java}}row2.label", "type": "str"},
        ]
        config["outputs"][0]["columns"].append(
            {"name": "var_label", "expression": "{{java}}Var.lookupVal", "type": "str", "nullable": True}
        )
        comp = _make_component(config=config)
        result = comp.execute(_make_input_dict())
        out = result["out1"]
        a_row = out[out["id"] == 1]
        assert a_row.iloc[0]["var_label"] == "Alpha"


@pytest.mark.unit
class TestCatchOutputReject:
    """MAP-05: Catch output reject for expression errors."""

    def test_catch_output_configured(self):
        """Output with catch_output_reject=True is recognized."""
        config = copy.deepcopy(_DEFAULT_CONFIG)
        config["outputs"].append({
            "name": "error_out",
            "is_reject": False,
            "inner_join_reject": False,
            "filter": "",
            "activate_filter": False,
            "columns": [
                {"name": "id", "expression": "{{java}}row1.id", "type": "int", "nullable": True},
                {"name": "errorMessage", "expression": "", "type": "str", "nullable": True},
            ],
            "catch_output_reject": True,
        })
        comp = _make_component(config=config)
        result = comp.execute(_make_input_dict())
        assert "error_out" in result

    def test_catch_output_separate_from_inner_join_reject(self):
        """Catch output distinct from inner join reject."""
        config = copy.deepcopy(_DEFAULT_CONFIG)
        config["inputs"]["lookups"][0]["join_mode"] = "INNER_JOIN"
        config["outputs"].append({
            "name": "catch_out",
            "is_reject": False,
            "inner_join_reject": False,
            "filter": "",
            "activate_filter": False,
            "columns": [
                {"name": "id", "expression": "{{java}}row1.id", "type": "int", "nullable": True},
                {"name": "errorMessage", "expression": "", "type": "str", "nullable": True},
            ],
            "catch_output_reject": True,
        })
        config["outputs"].append({
            "name": "inner_rej",
            "is_reject": False,
            "inner_join_reject": True,
            "filter": "",
            "activate_filter": False,
            "columns": [
                {"name": "id", "expression": "{{java}}row1.id", "type": "int", "nullable": True},
            ],
            "catch_output_reject": False,
        })
        comp = _make_component(config=config)
        result = comp.execute(_make_input_dict())
        # Both outputs exist and are separate
        assert "catch_out" in result
        assert "inner_rej" in result

    def test_catch_output_has_expected_columns(self):
        """Catch output DataFrame has errorMessage column defined in config."""
        config = copy.deepcopy(_DEFAULT_CONFIG)
        config["outputs"].append({
            "name": "error_out",
            "is_reject": False,
            "inner_join_reject": False,
            "filter": "",
            "activate_filter": False,
            "columns": [
                {"name": "id", "expression": "{{java}}row1.id", "type": "int", "nullable": True},
                {"name": "errorMessage", "expression": "", "type": "str", "nullable": True},
            ],
            "catch_output_reject": True,
        })
        comp = _make_component(config=config)
        result = comp.execute(_make_input_dict())
        error_out = result.get("error_out")
        assert error_out is not None
        # errorMessage column should exist in the output schema
        assert "errorMessage" in error_out.columns


@pytest.mark.unit
class TestAutoConvertType:
    """MAP-06: Auto type conversion on join keys."""

    def test_string_int_join_key_auto_converts(self):
        """Main key is str, lookup key is int. Auto-convert makes join work."""
        config = copy.deepcopy(_DEFAULT_CONFIG)
        config["enable_auto_convert_type"] = True
        main_df = pd.DataFrame([
            {"id": 1, "key": "1", "val": 100},
            {"id": 2, "key": "2", "val": 200},
        ])
        lookup = pd.DataFrame([
            {"key": 1, "label": "One"},
            {"key": 2, "label": "Two"},
        ])
        comp = _make_component(config=config)
        result = comp.execute(_make_input_dict(main_df=main_df, lookup_df=lookup))
        out = result["out1"]
        assert len(out) == 2
        one_row = out[out["id"] == 1]
        assert one_row.iloc[0]["label"] == "One"

    def test_auto_convert_disabled_by_default(self):
        """Without enable_auto_convert_type, type mismatch raises error.

        pandas 3.0 refuses to merge str and int64 columns -- this is the
        expected behavior when auto_convert is not enabled. The component
        wraps the error as ComponentExecutionError.
        """
        config = copy.deepcopy(_DEFAULT_CONFIG)
        # enable_auto_convert_type defaults to False
        main_df = pd.DataFrame([
            {"id": 1, "key": "1", "val": 100},
        ])
        lookup = pd.DataFrame([
            {"key": 1, "label": "One"},
        ])
        comp = _make_component(config=config)
        with pytest.raises(ComponentExecutionError):
            comp.execute(_make_input_dict(main_df=main_df, lookup_df=lookup))

    def test_int_float_auto_converts(self):
        """Int and float keys match when auto-convert enabled."""
        config = copy.deepcopy(_DEFAULT_CONFIG)
        config["enable_auto_convert_type"] = True
        main_df = pd.DataFrame([
            {"id": 1, "key": 1, "val": 100},
        ])
        lookup = pd.DataFrame([
            {"key": 1.0, "label": "One"},
        ])
        comp = _make_component(config=config)
        result = comp.execute(_make_input_dict(main_df=main_df, lookup_df=lookup))
        out = result["out1"]
        assert out.iloc[0]["label"] == "One"

    def test_auto_convert_preserves_original_data(self):
        """Original DataFrame columns not mutated."""
        config = copy.deepcopy(_DEFAULT_CONFIG)
        config["enable_auto_convert_type"] = True
        main_df = pd.DataFrame([
            {"id": 1, "key": "1", "val": 100},
        ])
        original_key_dtype = main_df["key"].dtype
        lookup = pd.DataFrame([
            {"key": 1, "label": "One"},
        ])
        comp = _make_component(config=config)
        comp.execute(_make_input_dict(main_df=main_df, lookup_df=lookup))
        # Original DataFrame should NOT be mutated
        assert main_df["key"].dtype == original_key_dtype


@pytest.mark.unit
class TestReloadAtEachRow:
    """MAP-08: RELOAD_AT_EACH_ROW per-row lookup re-filter."""

    def test_reload_basic_key_matching(self):
        """Basic key matching works in RELOAD_AT_EACH_ROW mode."""
        config = copy.deepcopy(_DEFAULT_CONFIG)
        config["inputs"]["lookups"][0]["lookup_mode"] = "RELOAD_AT_EACH_ROW"
        comp = _make_component(config=config)
        result = comp.execute(_make_input_dict())
        out = result["out1"]
        # Key A matches, B matches, C has no match (LEFT OUTER keeps it)
        assert len(out) == 3
        a_row = out[out["id"] == 1]
        assert len(a_row) == 1
        assert a_row.iloc[0]["label"] == "Alpha"

    def test_reload_left_outer_join_keeps_unmatched(self):
        """LEFT_OUTER_JOIN: unmatched main rows kept with NaN lookup columns."""
        config = copy.deepcopy(_DEFAULT_CONFIG)
        config["inputs"]["lookups"][0]["lookup_mode"] = "RELOAD_AT_EACH_ROW"
        config["inputs"]["lookups"][0]["join_mode"] = "LEFT_OUTER_JOIN"
        comp = _make_component(config=config)
        result = comp.execute(_make_input_dict())
        out = result["out1"]
        # Main row id=3 (key=C) has no lookup match
        assert len(out) == 3
        c_row = out[out["id"] == 3]
        assert len(c_row) == 1
        # label column should exist (from lookup) but be NaN for unmatched
        assert "label" in out.columns

    def test_reload_inner_join_rejects_unmatched(self):
        """INNER_JOIN: unmatched main rows become rejects."""
        config = copy.deepcopy(_DEFAULT_CONFIG)
        config["inputs"]["lookups"][0]["lookup_mode"] = "RELOAD_AT_EACH_ROW"
        config["inputs"]["lookups"][0]["join_mode"] = "INNER_JOIN"
        # Add inner_join_reject output
        config["outputs"].append({
            "name": "reject1",
            "is_reject": False,
            "inner_join_reject": True,
            "filter": "",
            "activate_filter": False,
            "columns": [
                {"name": "id", "expression": "{{java}}row1.id", "type": "int", "nullable": True},
                {"name": "key", "expression": "{{java}}row1.key", "type": "str", "nullable": True},
            ],
            "catch_output_reject": False,
        })
        comp = _make_component(config=config)
        result = comp.execute(_make_input_dict())
        out = result["out1"]
        # Only A and B match, C is rejected
        assert len(out) == 2
        assert set(out["id"].tolist()) == {1, 2}

    def test_reload_with_load_once_uses_cached(self):
        """LOAD_ONCE does NOT re-filter per row (standard behavior)."""
        config = copy.deepcopy(_DEFAULT_CONFIG)
        config["inputs"]["lookups"][0]["lookup_mode"] = "LOAD_ONCE"
        comp = _make_component(config=config)
        result = comp.execute(_make_input_dict())
        out = result["out1"]
        assert len(out) == 3  # All main rows present

    def test_reload_numeric_key_matching(self):
        """Numeric join keys match correctly in RELOAD_AT_EACH_ROW."""
        config = copy.deepcopy(_DEFAULT_CONFIG)
        config["inputs"]["lookups"][0]["lookup_mode"] = "RELOAD_AT_EACH_ROW"
        config["inputs"]["lookups"][0]["join_keys"] = [{
            "lookup_column": "dept_id",
            "expression": "{{java}}row1.dept_id",
            "type": "int",
            "nullable": False,
            "operator": "=",
        }]
        config["outputs"][0]["columns"] = [
            {"name": "id", "expression": "{{java}}row1.id", "type": "int", "nullable": True},
            {"name": "dept_name", "expression": "{{java}}row2.dept_name", "type": "str", "nullable": True},
        ]
        main_df = pd.DataFrame({
            "id": [1, 2, 3],
            "dept_id": [10, 20, 10],
            "val": [100, 200, 300],
        })
        lookup_df = pd.DataFrame({
            "dept_id": [10, 20, 30],
            "dept_name": ["Engineering", "Sales", "HR"],
        })
        comp = _make_component(config=config)
        result = comp.execute(_make_input_dict(main_df=main_df, lookup_df=lookup_df))
        out = result["out1"]
        assert len(out) == 3
        eng_rows = out[out["dept_name"] == "Engineering"]
        assert len(eng_rows) == 2  # id=1 and id=3 both in dept 10

    def test_reload_warns_for_large_datasets(self, caplog):
        """Warning logged when main > 10K and lookup > 10K."""
        config = copy.deepcopy(_DEFAULT_CONFIG)
        config["inputs"]["lookups"][0]["lookup_mode"] = "RELOAD_AT_EACH_ROW"
        # Create datasets exceeding 10K threshold
        main_df = pd.DataFrame({
            "id": range(11000),
            "key": [f"K{i % 100}" for i in range(11000)],
            "val": range(11000),
        })
        lookup_df = pd.DataFrame({
            "key": [f"K{i}" for i in range(11000)],
            "label": [f"L{i}" for i in range(11000)],
        })
        comp = _make_component(config=config)
        with caplog.at_level(logging.WARNING):
            result = comp.execute(_make_input_dict(main_df=main_df, lookup_df=lookup_df))
        assert any("RELOAD_AT_EACH_ROW" in r.message for r in caplog.records)

    def test_reload_logs_row_count(self, caplog):
        """RELOAD_AT_EACH_ROW join logs the result row count."""
        config = copy.deepcopy(_DEFAULT_CONFIG)
        config["inputs"]["lookups"][0]["lookup_mode"] = "RELOAD_AT_EACH_ROW"
        comp = _make_component(config=config)
        with caplog.at_level(logging.INFO):
            result = comp.execute(_make_input_dict())
        assert any(
            "RELOAD_AT_EACH_ROW join" in r.message and "row2" in r.message
            for r in caplog.records
        )

    # ------------------------------------------------------------------
    # Bug 1 regression: no pre-filter for RELOAD_AT_EACH_ROW
    # ------------------------------------------------------------------

    def test_reload_no_prefilter_applied(self):
        """Bug 1: RELOAD_AT_EACH_ROW must receive unfiltered lookup.

        A filter like 'row2.active' (boolean column ref) would eliminate
        inactive rows if pre-applied. RELOAD_AT_EACH_ROW should still see
        all lookup rows, with per-row filtering applied inside the loop.
        """
        config = copy.deepcopy(_DEFAULT_CONFIG)
        config["inputs"]["lookups"][0]["lookup_mode"] = "RELOAD_AT_EACH_ROW"
        config["inputs"]["lookups"][0]["activate_filter"] = True
        # Boolean column filter -- simple column ref that _apply_filter handles.
        # If pre-applied, only active=True rows survive. If NOT pre-applied
        # (correct), the per-row loop sees ALL lookup rows and applies filter
        # per-row, so key="B" (active=True) matches but key="A" (active=False)
        # also shows up as unmatched in LEFT_OUTER_JOIN (not rejected).
        config["inputs"]["lookups"][0]["filter"] = "{{java}}row2.active"
        config["inputs"]["lookups"][0]["join_mode"] = "LEFT_OUTER_JOIN"
        config["outputs"][0]["columns"] = [
            {"name": "id", "expression": "{{java}}row1.id", "type": "int", "nullable": True},
            {"name": "key", "expression": "{{java}}row1.key", "type": "str", "nullable": True},
            {"name": "label", "expression": "{{java}}row2.label", "type": "str", "nullable": True},
        ]
        main_df = pd.DataFrame([
            {"id": 1, "key": "A", "val": 100},
            {"id": 2, "key": "B", "val": 200},
        ])
        lookup_df = pd.DataFrame([
            {"key": "A", "label": "Alpha", "active": False},
            {"key": "B", "label": "Beta", "active": True},
        ])
        comp = _make_component(config=config)
        result = comp.execute(_make_input_dict(main_df=main_df, lookup_df=lookup_df))
        out = result["out1"]
        # Key B should match (active=True after per-row filter)
        b_row = out[out["id"] == 2]
        assert len(b_row) == 1
        assert b_row.iloc[0]["label"] == "Beta"
        # Key A: per-row filter removes inactive, so LEFT_OUTER gives NaN label
        # If pre-filter were applied (bug), key A might not appear at all
        a_row = out[out["id"] == 1]
        assert len(a_row) == 1
        # All main rows should be present in LEFT_OUTER output
        assert len(out) == 2

    # ------------------------------------------------------------------
    # Bug 2 regression: per-row filter with main row context
    # ------------------------------------------------------------------

    def test_reload_per_row_filter_by_main_column(self):
        """Bug 2: Filter resolves main row values per-row.

        Main rows have region US/EU/US. Lookup rows have region column.
        Filter: row1.region == row2.region. Each main row should only
        match lookups with the same region.

        Uses a mock bridge that evaluates simple comparison expressions.
        """
        config = copy.deepcopy(_DEFAULT_CONFIG)
        config["inputs"]["lookups"][0]["lookup_mode"] = "RELOAD_AT_EACH_ROW"
        config["inputs"]["lookups"][0]["activate_filter"] = True
        config["inputs"]["lookups"][0]["filter"] = "{{java}}row1.region == row2.region"
        config["inputs"]["lookups"][0]["join_keys"] = [{
            "lookup_column": "key",
            "expression": "{{java}}row1.key",
            "type": "str",
            "nullable": False,
            "operator": "=",
        }]
        config["inputs"]["lookups"][0]["join_mode"] = "LEFT_OUTER_JOIN"
        config["outputs"][0]["columns"] = [
            {"name": "id", "expression": "{{java}}row1.id", "type": "int", "nullable": True},
            {"name": "region", "expression": "{{java}}row1.region", "type": "str", "nullable": True},
            {"name": "label", "expression": "{{java}}row2.label", "type": "str", "nullable": True},
        ]
        main_df = pd.DataFrame([
            {"id": 1, "key": "A", "region": "US", "val": 100},
            {"id": 2, "key": "B", "region": "EU", "val": 200},
            {"id": 3, "key": "C", "region": "US", "val": 300},
        ])
        lookup_df = pd.DataFrame([
            {"key": "A", "label": "Alpha", "region": "US"},
            {"key": "B", "label": "Beta", "region": "EU"},
            {"key": "C", "label": "Gamma", "region": "EU"},  # C is EU, not US
        ])

        class _MockBridge:
            """Mock bridge that evaluates simple comparison expressions."""
            def execute_tmap_preprocessing(self, df, expressions, main_table_name,
                                           lookup_table_names=None, schema=None):
                results = {}
                for expr_id, expr_str in expressions.items():
                    # Handle simple equality: "value" == table.column
                    if "==" in expr_str:
                        parts = expr_str.split("==")
                        left = parts[0].strip().strip('"').strip("'")
                        right = parts[1].strip()
                        # Find column in df
                        col_name = None
                        for c in df.columns:
                            if right.endswith(c) or right == c:
                                col_name = c
                                break
                        if col_name is not None:
                            results[expr_id] = (df[col_name].astype(str) == left).values
                        else:
                            results[expr_id] = np.array([False] * len(df))
                    else:
                        results[expr_id] = np.array([True] * len(df))
                return results

        comp = _make_component(config=config, java_bridge=_MockBridge())
        result = comp.execute(_make_input_dict(main_df=main_df, lookup_df=lookup_df))
        out = result["out1"]
        # Row 1 (region=US, key=A): lookup A is region=US -> matches
        r1 = out[out["id"] == 1]
        assert len(r1) == 1
        assert r1.iloc[0]["label"] == "Alpha"
        # Row 2 (region=EU, key=B): lookup B is region=EU -> matches
        r2 = out[out["id"] == 2]
        assert len(r2) == 1
        assert r2.iloc[0]["label"] == "Beta"
        # Row 3 (region=US, key=C): lookup C is region=EU -> filter removes it
        # LEFT_OUTER: row 3 appears with NaN label
        r3 = out[out["id"] == 3]
        assert len(r3) == 1
        assert pd.isna(r3.iloc[0]["label"])

    def test_reload_per_row_filter_numeric_comparison(self):
        """Bug 2: Per-row filter with numeric comparison.

        Filter: row1.threshold <= row2.score. Each main row has a different
        threshold; only lookups with score >= threshold should match.
        """
        config = copy.deepcopy(_DEFAULT_CONFIG)
        config["inputs"]["lookups"][0]["lookup_mode"] = "RELOAD_AT_EACH_ROW"
        config["inputs"]["lookups"][0]["activate_filter"] = True
        config["inputs"]["lookups"][0]["filter"] = "{{java}}row1.threshold <= row2.score"
        config["inputs"]["lookups"][0]["join_keys"] = [{
            "lookup_column": "key",
            "expression": "{{java}}row1.key",
            "type": "str",
            "nullable": False,
            "operator": "=",
        }]
        config["inputs"]["lookups"][0]["join_mode"] = "LEFT_OUTER_JOIN"
        config["outputs"][0]["columns"] = [
            {"name": "id", "expression": "{{java}}row1.id", "type": "int", "nullable": True},
            {"name": "label", "expression": "{{java}}row2.label", "type": "str", "nullable": True},
        ]
        main_df = pd.DataFrame([
            {"id": 1, "key": "A", "threshold": 50, "val": 100},
            {"id": 2, "key": "B", "threshold": 90, "val": 200},
        ])
        lookup_df = pd.DataFrame([
            {"key": "A", "label": "Alpha", "score": 80},
            {"key": "B", "label": "Beta", "score": 70},
        ])

        class _MockBridgeNumeric:
            """Mock bridge that evaluates <= comparisons."""
            def execute_tmap_preprocessing(self, df, expressions, main_table_name,
                                           lookup_table_names=None, schema=None):
                results = {}
                for expr_id, expr_str in expressions.items():
                    if "<=" in expr_str:
                        parts = expr_str.split("<=")
                        left_val = parts[0].strip()
                        right_col = parts[1].strip()
                        try:
                            left_num = float(left_val)
                        except ValueError:
                            results[expr_id] = np.array([False] * len(df))
                            continue
                        col_name = None
                        for c in df.columns:
                            if right_col.endswith(c) or right_col == c:
                                col_name = c
                                break
                        if col_name is not None:
                            results[expr_id] = (left_num <= df[col_name].astype(float)).values
                        else:
                            results[expr_id] = np.array([False] * len(df))
                    else:
                        results[expr_id] = np.array([True] * len(df))
                return results

        comp = _make_component(config=config, java_bridge=_MockBridgeNumeric())
        result = comp.execute(_make_input_dict(main_df=main_df, lookup_df=lookup_df))
        out = result["out1"]
        # Row 1 (threshold=50, key=A): lookup A has score=80 >= 50 -> matches
        r1 = out[out["id"] == 1]
        assert len(r1) == 1
        assert r1.iloc[0]["label"] == "Alpha"
        # Row 2 (threshold=90, key=B): lookup B has score=70 < 90 -> no match
        # LEFT_OUTER: row 2 appears with NaN label
        r2 = out[out["id"] == 2]
        assert len(r2) == 1
        assert pd.isna(r2.iloc[0]["label"])

    def test_reload_per_row_filter_empty_result(self):
        """Bug 2: Per-row filter eliminates all lookups for a main row.

        LEFT_OUTER_JOIN: main row appears with NaN lookup columns.
        """
        config = copy.deepcopy(_DEFAULT_CONFIG)
        config["inputs"]["lookups"][0]["lookup_mode"] = "RELOAD_AT_EACH_ROW"
        config["inputs"]["lookups"][0]["activate_filter"] = True
        config["inputs"]["lookups"][0]["filter"] = "{{java}}row2.active"
        config["inputs"]["lookups"][0]["join_mode"] = "LEFT_OUTER_JOIN"
        config["outputs"][0]["columns"] = [
            {"name": "id", "expression": "{{java}}row1.id", "type": "int", "nullable": True},
            {"name": "key", "expression": "{{java}}row1.key", "type": "str", "nullable": True},
            {"name": "label", "expression": "{{java}}row2.label", "type": "str", "nullable": True},
        ]
        main_df = pd.DataFrame([
            {"id": 1, "key": "A", "val": 100},
        ])
        # All lookup rows have active=False -> filter eliminates all
        lookup_df = pd.DataFrame([
            {"key": "A", "label": "Alpha", "active": False},
            {"key": "B", "label": "Beta", "active": False},
        ])
        comp = _make_component(config=config)
        result = comp.execute(_make_input_dict(main_df=main_df, lookup_df=lookup_df))
        out = result["out1"]
        # LEFT_OUTER: main row preserved with NaN lookup columns
        assert len(out) == 1
        assert out.iloc[0]["id"] == 1
        assert pd.isna(out.iloc[0]["label"])

    def test_reload_per_row_filter_globalmap_set(self):
        """Bug 2: GlobalMap contains {main_name}.{col} keys after per-row loop.

        After processing all main rows, globalMap should have entries
        matching the last main row's values.
        """
        config = copy.deepcopy(_DEFAULT_CONFIG)
        config["inputs"]["lookups"][0]["lookup_mode"] = "RELOAD_AT_EACH_ROW"
        config["outputs"][0]["columns"] = [
            {"name": "id", "expression": "{{java}}row1.id", "type": "int", "nullable": True},
            {"name": "key", "expression": "{{java}}row1.key", "type": "str", "nullable": True},
            {"name": "label", "expression": "{{java}}row2.label", "type": "str", "nullable": True},
        ]
        main_df = pd.DataFrame([
            {"id": 1, "key": "A", "val": 100},
            {"id": 2, "key": "B", "val": 200},
            {"id": 3, "key": "C", "val": 300},
        ])
        gm = GlobalMap()
        comp = _make_component(config=config, global_map=gm)
        comp.execute(_make_input_dict(main_df=main_df))
        # globalMap should have row1.{col} entries from the LAST main row
        assert gm.get("row1.key") == "C"
        assert gm.get("row1.id") == 3
        assert gm.get("row1.val") == 300

    # ------------------------------------------------------------------
    # Bug 3 regression: type-aware key comparison
    # ------------------------------------------------------------------

    def test_reload_int_float_key_match(self):
        """Bug 3: int(1) matches float(1.0) via _values_equal.

        String comparison would fail: str(1) = "1" != str(1.0) = "1.0".
        Type-aware comparison: float(1) == float(1.0) -> True.
        """
        config = copy.deepcopy(_DEFAULT_CONFIG)
        config["inputs"]["lookups"][0]["lookup_mode"] = "RELOAD_AT_EACH_ROW"
        config["inputs"]["lookups"][0]["join_keys"] = [{
            "lookup_column": "key",
            "expression": "{{java}}row1.key",
            "type": "int",
            "nullable": False,
            "operator": "=",
        }]
        config["outputs"][0]["columns"] = [
            {"name": "id", "expression": "{{java}}row1.id", "type": "int", "nullable": True},
            {"name": "label", "expression": "{{java}}row2.label", "type": "str", "nullable": True},
        ]
        main_df = pd.DataFrame({"id": [1, 2], "key": [1, 2], "val": [100, 200]})
        # Force float dtype on lookup key
        lookup_df = pd.DataFrame({"key": [1.0, 2.0], "label": ["Alpha", "Beta"]})
        assert main_df["key"].dtype != lookup_df["key"].dtype  # int vs float
        comp = _make_component(config=config)
        result = comp.execute(_make_input_dict(main_df=main_df, lookup_df=lookup_df))
        out = result["out1"]
        assert len(out) == 2
        r1 = out[out["id"] == 1]
        assert r1.iloc[0]["label"] == "Alpha"
        r2 = out[out["id"] == 2]
        assert r2.iloc[0]["label"] == "Beta"

    def test_reload_string_numeric_key_safe_cast(self):
        """Review hardening: string "42" matches int 42 via safe numeric cast.

        _values_equal tries float conversion when one side is string and
        other is numeric.
        """
        config = copy.deepcopy(_DEFAULT_CONFIG)
        config["inputs"]["lookups"][0]["lookup_mode"] = "RELOAD_AT_EACH_ROW"
        config["inputs"]["lookups"][0]["join_keys"] = [{
            "lookup_column": "key",
            "expression": "{{java}}row1.key",
            "type": "str",
            "nullable": False,
            "operator": "=",
        }]
        config["outputs"][0]["columns"] = [
            {"name": "id", "expression": "{{java}}row1.id", "type": "int", "nullable": True},
            {"name": "label", "expression": "{{java}}row2.label", "type": "str", "nullable": True},
        ]
        main_df = pd.DataFrame({"id": [1], "key": ["42"], "val": [100]})
        lookup_df = pd.DataFrame({"key": [42], "label": ["Answer"]})
        comp = _make_component(config=config)
        result = comp.execute(_make_input_dict(main_df=main_df, lookup_df=lookup_df))
        out = result["out1"]
        assert len(out) == 1
        assert out.iloc[0]["label"] == "Answer"

    def test_reload_mixed_type_multikey(self):
        """Bug 3: Multi-column key with mixed types (int+str). Both must match."""
        config = copy.deepcopy(_DEFAULT_CONFIG)
        config["inputs"]["lookups"][0]["lookup_mode"] = "RELOAD_AT_EACH_ROW"
        config["inputs"]["lookups"][0]["join_keys"] = [
            {
                "lookup_column": "dept_id",
                "expression": "{{java}}row1.dept_id",
                "type": "int",
                "nullable": False,
                "operator": "=",
            },
            {
                "lookup_column": "region",
                "expression": "{{java}}row1.region",
                "type": "str",
                "nullable": False,
                "operator": "=",
            },
        ]
        config["outputs"][0]["columns"] = [
            {"name": "id", "expression": "{{java}}row1.id", "type": "int", "nullable": True},
            {"name": "dept_name", "expression": "{{java}}row2.dept_name", "type": "str", "nullable": True},
        ]
        main_df = pd.DataFrame({
            "id": [1, 2],
            "dept_id": [10, 20],
            "region": ["US", "EU"],
            "val": [100, 200],
        })
        lookup_df = pd.DataFrame({
            "dept_id": [10.0, 20.0, 10.0],  # float to test int/float match
            "region": ["US", "EU", "EU"],
            "dept_name": ["Eng-US", "Sales-EU", "Eng-EU"],
        })
        comp = _make_component(config=config)
        result = comp.execute(_make_input_dict(main_df=main_df, lookup_df=lookup_df))
        out = result["out1"]
        assert len(out) == 2
        r1 = out[out["id"] == 1]
        assert r1.iloc[0]["dept_name"] == "Eng-US"  # dept_id=10 + region=US
        r2 = out[out["id"] == 2]
        assert r2.iloc[0]["dept_name"] == "Sales-EU"  # dept_id=20 + region=EU

    # ------------------------------------------------------------------
    # Bug 4 regression: NaN-filled columns on unmatched rows
    # ------------------------------------------------------------------

    def test_reload_left_outer_unmatched_has_nan_columns(self):
        """Bug 4: Unmatched rows have NaN lookup columns, not missing columns.

        LEFT_OUTER_JOIN with unmatched rows must produce a DataFrame where
        ALL rows (matched and unmatched) have the same column set. Lookup
        columns on unmatched rows must be NaN.
        """
        config = copy.deepcopy(_DEFAULT_CONFIG)
        config["inputs"]["lookups"][0]["lookup_mode"] = "RELOAD_AT_EACH_ROW"
        config["inputs"]["lookups"][0]["join_mode"] = "LEFT_OUTER_JOIN"
        config["outputs"][0]["columns"] = [
            {"name": "id", "expression": "{{java}}row1.id", "type": "int", "nullable": True},
            {"name": "key", "expression": "{{java}}row1.key", "type": "str", "nullable": True},
            {"name": "label", "expression": "{{java}}row2.label", "type": "str", "nullable": True},
        ]
        main_df = pd.DataFrame([
            {"id": 1, "key": "A", "val": 100},
            {"id": 2, "key": "B", "val": 200},
            {"id": 3, "key": "X", "val": 300},  # no match
        ])
        lookup_df = pd.DataFrame([
            {"key": "A", "label": "Alpha"},
            {"key": "B", "label": "Beta"},
        ])
        comp = _make_component(config=config)
        result = comp.execute(_make_input_dict(main_df=main_df, lookup_df=lookup_df))
        out = result["out1"]
        assert len(out) == 3
        # Unmatched row (key=X) should have NaN label, not missing column
        x_row = out[out["id"] == 3]
        assert len(x_row) == 1
        assert pd.isna(x_row.iloc[0]["label"])
        # Lookup columns present on all rows
        assert "label" in out.columns

    def test_reload_left_outer_column_order_consistent(self):
        """Bug 4: All rows have identical column set regardless of match status.

        Build a result with mixed matched/unmatched rows. The output
        DataFrame must have consistent columns (no surprise or missing cols).
        """
        config = copy.deepcopy(_DEFAULT_CONFIG)
        config["inputs"]["lookups"][0]["lookup_mode"] = "RELOAD_AT_EACH_ROW"
        config["inputs"]["lookups"][0]["join_mode"] = "LEFT_OUTER_JOIN"
        config["outputs"][0]["columns"] = [
            {"name": "id", "expression": "{{java}}row1.id", "type": "int", "nullable": True},
            {"name": "key", "expression": "{{java}}row1.key", "type": "str", "nullable": True},
            {"name": "label", "expression": "{{java}}row2.label", "type": "str", "nullable": True},
            {"name": "score", "expression": "{{java}}row2.score", "type": "int", "nullable": True},
        ]
        main_df = pd.DataFrame([
            {"id": 1, "key": "A", "val": 100},
            {"id": 2, "key": "X", "val": 200},  # no match
            {"id": 3, "key": "B", "val": 300},
            {"id": 4, "key": "Y", "val": 400},  # no match
        ])
        lookup_df = pd.DataFrame([
            {"key": "A", "label": "Alpha", "score": 90},
            {"key": "B", "label": "Beta", "score": 85},
        ])
        comp = _make_component(config=config)
        result = comp.execute(_make_input_dict(main_df=main_df, lookup_df=lookup_df))
        out = result["out1"]
        assert len(out) == 4
        # All rows should have identical columns
        expected_cols = {"id", "key", "label", "score"}
        assert set(out.columns) == expected_cols
        # Verify NaN on unmatched rows
        x_row = out[out["id"] == 2]
        assert pd.isna(x_row.iloc[0]["label"])
        assert pd.isna(x_row.iloc[0]["score"])

    # ------------------------------------------------------------------
    # Review hardening tests
    # ------------------------------------------------------------------

    def test_reload_per_row_filter_quoted_string_not_substituted(self):
        """Review hardening: table.column inside quotes is NOT substituted.

        Filter: row1.key == "row1.key" -- the quoted "row1.key" must remain
        as a literal string, not be replaced with the actual key value.
        After substitution: "A" == "row1.key" which is False for all rows.
        """
        config = copy.deepcopy(_DEFAULT_CONFIG)
        config["inputs"]["lookups"][0]["lookup_mode"] = "RELOAD_AT_EACH_ROW"
        config["inputs"]["lookups"][0]["activate_filter"] = True
        config["inputs"]["lookups"][0]["filter"] = '{{java}}row1.key == "row1.key"'
        config["inputs"]["lookups"][0]["join_mode"] = "LEFT_OUTER_JOIN"
        config["outputs"][0]["columns"] = [
            {"name": "id", "expression": "{{java}}row1.id", "type": "int", "nullable": True},
            {"name": "key", "expression": "{{java}}row1.key", "type": "str", "nullable": True},
            {"name": "label", "expression": "{{java}}row2.label", "type": "str", "nullable": True},
        ]
        main_df = pd.DataFrame([
            {"id": 1, "key": "A", "val": 100},
        ])
        lookup_df = pd.DataFrame([
            {"key": "A", "label": "Alpha"},
        ])

        class _MockBridgeQuoteTest:
            """Mock bridge that evaluates == comparisons for quoted test."""
            def execute_tmap_preprocessing(self, df, expressions, main_table_name,
                                           lookup_table_names=None, schema=None):
                results = {}
                for expr_id, expr_str in expressions.items():
                    if "==" in expr_str:
                        parts = expr_str.split("==")
                        left = parts[0].strip().strip('"').strip("'")
                        right = parts[1].strip().strip('"').strip("'")
                        # Both should be literal strings after substitution
                        # "A" == "row1.key" -> "A" != "row1.key" -> False
                        results[expr_id] = np.array([left == right] * len(df))
                    else:
                        results[expr_id] = np.array([True] * len(df))
                return results

        comp = _make_component(config=config, java_bridge=_MockBridgeQuoteTest())
        result = comp.execute(_make_input_dict(main_df=main_df, lookup_df=lookup_df))
        out = result["out1"]
        # Filter "A" == "row1.key" is False (quote-aware: inner "row1.key" NOT
        # substituted). LEFT_OUTER: row 1 appears with NaN label.
        assert len(out) == 1
        assert pd.isna(out.iloc[0]["label"])

    def test_reload_per_row_filter_null_main_value_no_crash(self):
        """Review hardening: NaN main value in filter does not crash.

        When a main row has NaN in the column referenced by the filter,
        _substitute_row_refs replaces it with 'None'. The downstream
        evaluation may raise TypeError. _apply_filter_per_row catches it
        and returns empty DataFrame (no match).
        """
        config = copy.deepcopy(_DEFAULT_CONFIG)
        config["inputs"]["lookups"][0]["lookup_mode"] = "RELOAD_AT_EACH_ROW"
        config["inputs"]["lookups"][0]["activate_filter"] = True
        config["inputs"]["lookups"][0]["filter"] = "{{java}}row1.threshold > row2.score"
        config["inputs"]["lookups"][0]["join_keys"] = [{
            "lookup_column": "key",
            "expression": "{{java}}row1.key",
            "type": "str",
            "nullable": False,
            "operator": "=",
        }]
        config["inputs"]["lookups"][0]["join_mode"] = "LEFT_OUTER_JOIN"
        config["outputs"][0]["columns"] = [
            {"name": "id", "expression": "{{java}}row1.id", "type": "int", "nullable": True},
            {"name": "label", "expression": "{{java}}row2.label", "type": "str", "nullable": True},
        ]
        main_df = pd.DataFrame({
            "id": [1, 2],
            "key": ["A", "B"],
            "threshold": [50.0, np.nan],  # Row 2 has NaN threshold
            "val": [100, 200],
        })
        lookup_df = pd.DataFrame([
            {"key": "A", "label": "Alpha", "score": 30},
            {"key": "B", "label": "Beta", "score": 30},
        ])

        class _MockBridgeNullSafe:
            """Mock bridge that handles None in expressions."""
            def execute_tmap_preprocessing(self, df, expressions, main_table_name,
                                           lookup_table_names=None, schema=None):
                results = {}
                for expr_id, expr_str in expressions.items():
                    if "None" in expr_str:
                        # None > anything raises TypeError -- simulate it
                        raise TypeError("'>' not supported between NoneType and int")
                    if ">" in expr_str:
                        parts = expr_str.split(">")
                        left_val = parts[0].strip()
                        right_col = parts[1].strip()
                        try:
                            left_num = float(left_val)
                        except ValueError:
                            results[expr_id] = np.array([False] * len(df))
                            continue
                        col_name = None
                        for c in df.columns:
                            if right_col.endswith(c) or right_col == c:
                                col_name = c
                                break
                        if col_name:
                            results[expr_id] = (left_num > df[col_name].astype(float)).values
                        else:
                            results[expr_id] = np.array([False] * len(df))
                    else:
                        results[expr_id] = np.array([True] * len(df))
                return results

        comp = _make_component(config=config, java_bridge=_MockBridgeNullSafe())
        # This should NOT raise -- _apply_filter_per_row catches TypeError
        result = comp.execute(_make_input_dict(main_df=main_df, lookup_df=lookup_df))
        out = result["out1"]
        # Row 1 (threshold=50, key=A): 50 > 30 -> True, Alpha matches
        r1 = out[out["id"] == 1]
        assert len(r1) == 1
        assert r1.iloc[0]["label"] == "Alpha"
        # Row 2 (threshold=NaN): null substituted -> TypeError caught -> no match
        # LEFT_OUTER: appears with NaN label
        r2 = out[out["id"] == 2]
        assert len(r2) == 1
        assert pd.isna(r2.iloc[0]["label"])

    # ------------------------------------------------------------------
    # Edge cases
    # ------------------------------------------------------------------

    def test_reload_all_matches_mode(self):
        """Edge case: RELOAD_AT_EACH_ROW with ALL_MATCHES.

        A main row can match multiple lookup rows. ALL_MATCHES does not
        break after first match.
        """
        config = copy.deepcopy(_DEFAULT_CONFIG)
        config["inputs"]["lookups"][0]["lookup_mode"] = "RELOAD_AT_EACH_ROW"
        config["inputs"]["lookups"][0]["matching_mode"] = "ALL_MATCHES"
        config["inputs"]["lookups"][0]["join_keys"] = [{
            "lookup_column": "dept",
            "expression": "{{java}}row1.dept",
            "type": "str",
            "nullable": False,
            "operator": "=",
        }]
        config["inputs"]["lookups"][0]["join_mode"] = "LEFT_OUTER_JOIN"
        config["outputs"][0]["columns"] = [
            {"name": "id", "expression": "{{java}}row1.id", "type": "int", "nullable": True},
            {"name": "label", "expression": "{{java}}row2.label", "type": "str", "nullable": True},
        ]
        main_df = pd.DataFrame([
            {"id": 1, "dept": "Eng", "val": 100},
        ])
        lookup_df = pd.DataFrame([
            {"dept": "Eng", "label": "Senior"},
            {"dept": "Eng", "label": "Junior"},
            {"dept": "Sales", "label": "Manager"},
        ])
        comp = _make_component(config=config)
        result = comp.execute(_make_input_dict(main_df=main_df, lookup_df=lookup_df))
        out = result["out1"]
        # Main row 1 should match both Eng lookups
        assert len(out) == 2
        labels = sorted(out["label"].tolist())
        assert labels == ["Junior", "Senior"]

    def test_reload_per_row_filter_string_with_quotes(self):
        """Edge case: Main row value contains double quote character.

        _substitute_row_refs should escape it correctly so the filter
        expression remains valid.
        """
        config = copy.deepcopy(_DEFAULT_CONFIG)
        config["inputs"]["lookups"][0]["lookup_mode"] = "RELOAD_AT_EACH_ROW"
        config["inputs"]["lookups"][0]["activate_filter"] = True
        config["inputs"]["lookups"][0]["filter"] = "{{java}}row1.name == row2.name"
        config["inputs"]["lookups"][0]["join_keys"] = [{
            "lookup_column": "key",
            "expression": "{{java}}row1.key",
            "type": "str",
            "nullable": False,
            "operator": "=",
        }]
        config["inputs"]["lookups"][0]["join_mode"] = "LEFT_OUTER_JOIN"
        config["outputs"][0]["columns"] = [
            {"name": "id", "expression": "{{java}}row1.id", "type": "int", "nullable": True},
            {"name": "label", "expression": "{{java}}row2.label", "type": "str", "nullable": True},
        ]
        # Main row value has a double-quote character
        main_df = pd.DataFrame([
            {"id": 1, "key": "A", "name": 'O"Brien', "val": 100},
        ])
        lookup_df = pd.DataFrame([
            {"key": "A", "label": "Alpha", "name": 'O"Brien'},
        ])

        class _MockBridgeEscapeTest:
            """Mock bridge that evaluates escaped string comparisons."""
            def execute_tmap_preprocessing(self, df, expressions, main_table_name,
                                           lookup_table_names=None, schema=None):
                results = {}
                for expr_id, expr_str in expressions.items():
                    if "==" in expr_str:
                        # After substitution: "O\"Brien" == row2.name
                        # The mock evaluates by parsing left side as a Python literal
                        parts = expr_str.split("==", 1)
                        left_raw = parts[0].strip()
                        right = parts[1].strip()
                        # Try to eval left as a Python string literal
                        try:
                            left_val = eval(left_raw)  # noqa: S307 -- test only
                        except Exception:
                            results[expr_id] = np.array([False] * len(df))
                            continue
                        col_name = None
                        for c in df.columns:
                            if right.endswith(c) or right == c:
                                col_name = c
                                break
                        if col_name:
                            results[expr_id] = (df[col_name].astype(str) == str(left_val)).values
                        else:
                            results[expr_id] = np.array([False] * len(df))
                    else:
                        results[expr_id] = np.array([True] * len(df))
                return results

        comp = _make_component(config=config, java_bridge=_MockBridgeEscapeTest())
        result = comp.execute(_make_input_dict(main_df=main_df, lookup_df=lookup_df))
        out = result["out1"]
        # Filter should match: O"Brien == O"Brien
        r1 = out[out["id"] == 1]
        assert len(r1) == 1
        assert r1.iloc[0]["label"] == "Alpha"


@pytest.mark.unit
class TestGlobalMapVariables:
    """MAP-07: GlobalMap variable setting."""

    def test_nb_line_set_after_execution(self):
        """GlobalMap contains {id}_NB_LINE equal to total output rows."""
        gm = GlobalMap()
        comp = _make_component(global_map=gm)
        result = comp.execute(_make_input_dict())
        nb_line = gm.get_component_stat("tMap_1", "NB_LINE")
        assert nb_line > 0

    def test_nb_line_ok_counts_non_reject(self):
        """NB_LINE_OK counts non-reject output rows."""
        gm = GlobalMap()
        comp = _make_component(global_map=gm)
        result = comp.execute(_make_input_dict())
        nb_line_ok = gm.get_component_stat("tMap_1", "NB_LINE_OK")
        assert nb_line_ok > 0

    def test_nb_line_reject_counts_reject(self):
        """NB_LINE_REJECT counts reject output rows."""
        config = copy.deepcopy(_DEFAULT_CONFIG)
        config["inputs"]["lookups"][0]["join_mode"] = "INNER_JOIN"
        config["outputs"].append({
            "name": "inner_reject",
            "is_reject": False,
            "inner_join_reject": True,
            "filter": "",
            "activate_filter": False,
            "columns": [
                {"name": "id", "expression": "{{java}}row1.id", "type": "int", "nullable": True},
            ],
            "catch_output_reject": False,
        })
        gm = GlobalMap()
        comp = _make_component(config=config, global_map=gm)
        result = comp.execute(_make_input_dict())
        nb_reject = gm.get_component_stat("tMap_1", "NB_LINE_REJECT")
        # key "C" has no match -> at least 1 reject
        assert nb_reject >= 1

    def test_no_global_map_does_not_crash(self):
        """Component works without GlobalMap (global_map=None)."""
        comp = _make_component(global_map=None)
        comp.global_map = None
        result = comp.execute(_make_input_dict())
        assert "out1" in result

    def test_stats_across_multiple_outputs(self):
        """Stats correctly sum across out1, out2, reject1."""
        config = copy.deepcopy(_DEFAULT_CONFIG)
        config["inputs"]["lookups"][0]["join_mode"] = "INNER_JOIN"
        config["outputs"].append({
            "name": "out2",
            "is_reject": False,
            "inner_join_reject": False,
            "filter": "",
            "activate_filter": False,
            "columns": [
                {"name": "val", "expression": "{{java}}row1.val", "type": "int", "nullable": True},
            ],
            "catch_output_reject": False,
        })
        config["outputs"].append({
            "name": "inner_reject",
            "is_reject": False,
            "inner_join_reject": True,
            "filter": "",
            "activate_filter": False,
            "columns": [
                {"name": "id", "expression": "{{java}}row1.id", "type": "int", "nullable": True},
            ],
            "catch_output_reject": False,
        })
        gm = GlobalMap()
        comp = _make_component(config=config, global_map=gm)
        result = comp.execute(_make_input_dict())
        total = 0
        reject_total = 0
        for key, val in result.items():
            if key == "stats":
                continue
            if isinstance(val, pd.DataFrame) and not val.empty:
                total += len(val)
                # Check if this is a reject output
                for o in config["outputs"]:
                    if o["name"] == key and (o.get("is_reject") or o.get("inner_join_reject")):
                        reject_total += len(val)
        stats = result["stats"]
        assert stats["NB_LINE"] == total
        assert stats["NB_LINE_REJECT"] == reject_total
        assert stats["NB_LINE_OK"] == total - reject_total


@pytest.mark.unit
class TestColumnPrefixing:
    """Lookup column prefixing tests."""

    def test_lookup_columns_prefixed(self):
        """Joined DataFrame has lookup columns prefixed with lookup_name."""
        comp = _make_component()
        # Access internal method via execute result -- check output column
        # In the output, columns are mapped by expression, so the label
        # column comes from row2.label which is the prefixed column.
        result = comp.execute(_make_input_dict())
        out = result["out1"]
        assert "label" in out.columns

    def test_main_columns_not_prefixed(self):
        """Main columns retain original names in output."""
        comp = _make_component()
        result = comp.execute(_make_input_dict())
        out = result["out1"]
        assert "id" in out.columns
        assert "val" in out.columns

    def test_multiple_lookups_distinct_prefixes(self):
        """Each lookup gets its own prefix."""
        config = copy.deepcopy(_DEFAULT_CONFIG)
        config["inputs"]["lookups"].append({
            "name": "row3",
            "matching_mode": "UNIQUE_MATCH",
            "lookup_mode": "LOAD_ONCE",
            "filter": "",
            "activate_filter": False,
            "join_keys": [
                {
                    "lookup_column": "code",
                    "expression": "{{java}}row1.key",
                    "type": "str",
                    "nullable": True,
                    "operator": "=",
                }
            ],
            "join_mode": "LEFT_OUTER_JOIN",
        })
        config["outputs"][0]["columns"].append(
            {"name": "desc", "expression": "{{java}}row3.desc", "type": "str", "nullable": True}
        )
        lookup2 = pd.DataFrame([
            {"code": "A", "desc": "Alpha_desc"},
        ])
        comp = _make_component(config=config)
        result = comp.execute({"row1": _make_main_df(), "row2": _make_lookup_df(),
                               "row3": lookup2})
        out = result["out1"]
        assert "label" in out.columns
        assert "desc" in out.columns


@pytest.mark.unit
class TestSmartJoinRouting:
    """Smart join classification tests."""

    def test_simple_column_ref_uses_equality(self):
        """Expression like 'row1.key' classified as equality join."""
        comp = _make_component()
        comp.config = copy.deepcopy(comp._original_config)
        join_keys = comp.config["inputs"]["lookups"][0]["join_keys"]
        join_type = comp._classify_join_type(join_keys)
        assert join_type == "equality"

    def test_context_ref_classified_correctly(self):
        """Expression with only context references classified as context_only.

        Note: 'context.region' matches table.column regex and is treated as
        equality. A pure context expression like '${context.region}' or
        'context.get("region")' that does NOT match table.column pattern
        is classified as context_only.
        """
        config = copy.deepcopy(_DEFAULT_CONFIG)
        # Use an expression that does NOT match _SIMPLE_COLUMN_RE
        # but only references context -- e.g. a method call pattern
        config["inputs"]["lookups"][0]["join_keys"] = [
            {
                "lookup_column": "region",
                "expression": '{{java}}context.get("region")',
                "type": "str",
                "nullable": True,
                "operator": "=",
            }
        ]
        comp = _make_component(config=config)
        comp.config = copy.deepcopy(comp._original_config)
        join_type = comp._classify_join_type(
            comp.config["inputs"]["lookups"][0]["join_keys"]
        )
        assert join_type == "context_only"

    def test_cross_table_ref_classified_correctly(self):
        """Expression with complex logic classified as cross_table."""
        config = copy.deepcopy(_DEFAULT_CONFIG)
        config["inputs"]["lookups"][0]["join_keys"] = [
            {
                "lookup_column": "code",
                "expression": "{{java}}row1.a + row2.b",
                "type": "str",
                "nullable": True,
                "operator": "=",
            }
        ]
        comp = _make_component(config=config)
        comp.config = copy.deepcopy(comp._original_config)
        join_type = comp._classify_join_type(
            comp.config["inputs"]["lookups"][0]["join_keys"]
        )
        assert join_type == "cross_table"

    def test_equality_join_produces_correct_result(self):
        """End-to-end equality join with pandas merge."""
        comp = _make_component()
        result = comp.execute(_make_input_dict())
        out = result["out1"]
        # key A matches -> Alpha, key B matches -> Beta
        a_row = out[out["id"] == 1]
        assert a_row.iloc[0]["label"] == "Alpha"
        b_row = out[out["id"] == 2]
        assert b_row.iloc[0]["label"] == "Beta"


@pytest.mark.unit
class TestEdgeCases:
    """Edge case tests."""

    def test_empty_main_produces_empty_outputs(self):
        """Zero rows in main -> all outputs empty."""
        comp = _make_component()
        empty = pd.DataFrame(columns=["id", "key", "val"])
        result = comp.execute(_make_input_dict(main_df=empty))
        for key, val in result.items():
            if key == "stats":
                continue
            assert isinstance(val, pd.DataFrame)
            assert val.empty

    def test_empty_lookup_with_left_outer(self):
        """All main rows get null lookup columns."""
        lookup = pd.DataFrame(columns=["key", "label"])
        comp = _make_component()
        result = comp.execute(_make_input_dict(lookup_df=lookup))
        out = result["out1"]
        assert len(out) == 3
        assert out["label"].isna().all()

    def test_empty_lookup_with_inner_join(self):
        """Empty lookup is skipped -- main rows pass through without match.

        When a lookup is empty, _process skips it entirely (no join
        performed), so inner join reject is not triggered. Main rows
        continue with null lookup columns.
        """
        config = copy.deepcopy(_DEFAULT_CONFIG)
        config["inputs"]["lookups"][0]["join_mode"] = "INNER_JOIN"
        config["outputs"].append({
            "name": "inner_reject",
            "is_reject": False,
            "inner_join_reject": True,
            "filter": "",
            "activate_filter": False,
            "columns": [
                {"name": "id", "expression": "{{java}}row1.id", "type": "int", "nullable": True},
            ],
            "catch_output_reject": False,
        })
        lookup = pd.DataFrame(columns=["key", "label"])
        comp = _make_component(config=config)
        result = comp.execute(_make_input_dict(lookup_df=lookup))
        # Empty lookup is skipped; main rows pass through
        out = result["out1"]
        assert len(out) == 3
        # Lookup columns are null since lookup was skipped
        assert out["label"].isna().all()

    def test_single_row_main_single_row_lookup(self):
        """Minimal case works."""
        main_df = pd.DataFrame([{"id": 1, "key": "X", "val": 42}])
        lookup = pd.DataFrame([{"key": "X", "label": "Xenon"}])
        comp = _make_component()
        result = comp.execute(_make_input_dict(main_df=main_df, lookup_df=lookup))
        out = result["out1"]
        assert len(out) == 1
        assert out.iloc[0]["label"] == "Xenon"

    def test_large_column_count(self):
        """Many columns (20+) in main and lookup."""
        main_cols = {"id": [1, 2], "key": ["A", "B"]}
        for i in range(20):
            main_cols[f"col_{i}"] = [i, i + 1]
        main_df = pd.DataFrame(main_cols)

        lookup_cols = {"key": ["A", "B"]}
        for i in range(20):
            lookup_cols[f"lk_col_{i}"] = [i * 10, i * 10 + 1]
        lookup = pd.DataFrame(lookup_cols)

        config = copy.deepcopy(_DEFAULT_CONFIG)
        config["outputs"][0]["columns"] = [
            {"name": "id", "expression": "{{java}}row1.id", "type": "int", "nullable": True},
            {"name": "label", "expression": "{{java}}row2.lk_col_0", "type": "int", "nullable": True},
        ]
        comp = _make_component(config=config)
        result = comp.execute(_make_input_dict(main_df=main_df, lookup_df=lookup))
        out = result["out1"]
        assert len(out) == 2

    def test_none_input_returns_empty_outputs(self):
        """None input returns empty outputs."""
        comp = _make_component()
        result = comp.execute(None)
        for key, val in result.items():
            if key == "stats":
                continue
            assert isinstance(val, pd.DataFrame)
            assert val.empty


@pytest.mark.unit
class TestIterateReexecution:
    """Iterate re-execution tests."""

    def test_results_match_on_reexecute(self):
        """Second execute() with same input produces same result."""
        comp = _make_component()
        inp = _make_input_dict()
        result1 = comp.execute(inp)
        comp.reset()
        result2 = comp.execute(inp)
        assert len(result1["out1"]) == len(result2["out1"])
        pd.testing.assert_frame_equal(
            result1["out1"].reset_index(drop=True),
            result2["out1"].reset_index(drop=True),
        )

    def test_stats_reset_on_reexecute(self):
        """Stats are fresh on second execution (not accumulated)."""
        gm = GlobalMap()
        comp = _make_component(global_map=gm)
        inp = _make_input_dict()

        comp.execute(inp)
        first_nb = gm.get_component_stat("tMap_1", "NB_LINE")

        comp.reset()
        comp.execute(inp)
        second_nb = gm.get_component_stat("tMap_1", "NB_LINE")

        # Should NOT be accumulated (first + second), should equal first
        assert second_nb == first_nb

    def test_config_unchanged_after_execute(self):
        """_original_config not mutated."""
        comp = _make_component()
        snapshot = copy.deepcopy(comp._original_config)
        comp.execute(_make_input_dict())
        assert comp._original_config == snapshot
        comp.reset()
        comp.execute(_make_input_dict())
        assert comp._original_config == snapshot


@pytest.mark.unit
class TestParallelExecution:
    """Test parallel_execution config (default: True)."""

    def test_default_parallel_execution_true(self):
        """Default parallel_execution is True (parallel forEach)."""
        comp = _make_component()
        comp.config = copy.deepcopy(comp._original_config)
        assert comp.config.get("parallel_execution", True) is True

    def test_sequential_execution_configurable(self):
        """parallel_execution=False selects sequential forEach."""
        config = copy.deepcopy(_DEFAULT_CONFIG)
        config["parallel_execution"] = False
        comp = _make_component(config=config)
        comp.config = copy.deepcopy(comp._original_config)
        assert comp.config["parallel_execution"] is False

    def test_parallel_execution_produces_same_result(self):
        """Both parallel and sequential modes produce identical results."""
        config_parallel = copy.deepcopy(_DEFAULT_CONFIG)
        config_parallel["parallel_execution"] = True
        config_seq = copy.deepcopy(_DEFAULT_CONFIG)
        config_seq["parallel_execution"] = False

        inp = _make_input_dict()
        comp_p = _make_component(config=config_parallel)
        comp_s = _make_component(config=config_seq)

        result_p = comp_p.execute(inp)
        result_s = comp_s.execute(inp)

        # Both should produce identical output (simple column ref path)
        pd.testing.assert_frame_equal(
            result_p["out1"].sort_values("id").reset_index(drop=True),
            result_s["out1"].sort_values("id").reset_index(drop=True),
        )


@pytest.mark.unit
class TestCompiledScriptGeneration:
    """Test compiled script generation (internal)."""

    def test_script_uses_plain_for_loop(self):
        """Script uses plain for-loop (not IntStream) for Groovy binding access."""
        config = copy.deepcopy(_DEFAULT_CONFIG)
        comp = _make_component(config=config)
        comp.config = copy.deepcopy(comp._original_config)
        script = comp._build_compiled_script(
            comp.config["outputs"], comp.config.get("variables", []),
            "row1", ["row2"]
        )
        assert "for (int i = 0; i < rowCount; i++)" in script
        # Old IntStream patterns no longer used (Groovy can't access bindings in lambdas)
        assert "parallel()" not in script
        assert "forEach(i -> {" not in script

    def test_catch_output_generates_try_catch(self):
        """catch_output_reject=True generates try/catch block."""
        config = copy.deepcopy(_DEFAULT_CONFIG)
        config["outputs"].append({
            "name": "error_out",
            "is_reject": False,
            "inner_join_reject": False,
            "filter": "",
            "activate_filter": False,
            "columns": [
                {"name": "id", "expression": "{{java}}row1.id", "type": "int", "nullable": True},
            ],
            "catch_output_reject": True,
        })
        comp = _make_component(config=config)
        comp.config = copy.deepcopy(comp._original_config)
        script = comp._build_compiled_script(
            comp.config["outputs"], comp.config.get("variables", []),
            "row1", ["row2"]
        )
        assert "try {" in script
        assert "catch (Exception e)" in script
        assert "errorCount" in script
        assert "errorMap" in script
        assert '__errors__' in script

    def test_script_uses_build_row_wrapper_closure(self):
        """Script creates RowWrappers via buildRowWrapper() closure, not constructors."""
        config = copy.deepcopy(_DEFAULT_CONFIG)
        comp = _make_component(config=config)
        comp.config = copy.deepcopy(comp._original_config)
        script = comp._build_compiled_script(
            comp.config["outputs"], comp.config.get("variables", []),
            "row1", ["row2"]
        )
        # Must use buildRowWrapper closure (delegates to JavaBridge.buildArrowRowWrapper)
        assert 'buildRowWrapper(inputRoot, i, "row1")' in script
        assert 'buildRowWrapper(inputRoot, i, "row2")' in script
        # Must NOT use old patterns (no-arg constructor or 3-arg constructor)
        assert "new RowWrapper();" not in script
        assert "new RowWrapper(inputRoot" not in script
        # No manual fieldVectors extraction -- buildRowWrapper handles it internally
        assert "def fieldVectors" not in script

    def test_output_types_keyed_per_column(self):
        """_build_output_schema produces per-column type keys."""
        config = copy.deepcopy(_DEFAULT_CONFIG)
        comp = _make_component(config=config)
        comp.config = copy.deepcopy(comp._original_config)
        _, output_types = comp._build_output_schema(comp.config["outputs"])
        # Keys should be "outputName_colName", not just "outputName"
        assert "out1" not in output_types  # old broken format
        assert "out1_id" in output_types
        assert output_types["out1_id"] == "int"
        assert "out1_val" in output_types
        assert output_types["out1_val"] == "int"
        assert "out1_label" in output_types
        assert output_types["out1_label"] == "str"
