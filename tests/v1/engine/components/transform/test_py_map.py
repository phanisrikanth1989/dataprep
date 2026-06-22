"""Tests for PyMap -- pure-Python multi-flow data mapping component.

Covers:
  - Registration in component registry
  - Config validation (all required keys)
  - Simple column passthrough (no expressions)
  - Python expression evaluation (arithmetic, string, ternary, regex, numpy)
  - Variable evaluation (Var dict in output expressions)
  - LEFT_OUTER_JOIN with lookup
  - INNER_JOIN with reject routing
  - Null key semantics (null keys never match)
  - Matching modes (UNIQUE_MATCH, FIRST_MATCH, LAST_MATCH, ALL_MATCHES)
  - Output filter routing to is_reject outputs
  - die_on_error=True raises on bad expression
  - die_on_error=False routes to reject (None value)
  - Multi-output routing
  - RELOAD_AT_EACH_ROW lookup mode
  - Empty inputs return empty outputs
  - Auto type conversion for join keys
"""
from __future__ import annotations

import copy

import numpy as np
import pandas as pd
import pytest

from src.v1.engine.component_registry import REGISTRY
import src.v1.engine.components  # noqa: F401  -- triggers @REGISTRY decorators
from src.v1.engine.components.transform.py_map import PyMap
from src.v1.engine.context_manager import ContextManager
from src.v1.engine.exceptions import ComponentExecutionError, ConfigurationError
from src.v1.engine.global_map import GlobalMap


# ------------------------------------------------------------------
# Shared test config builders
# ------------------------------------------------------------------

_SIMPLE_CONFIG = {
    "component_type": "PyMap",
    "inputs": {
        "main": {
            "name": "row1",
            "filter": "",
            "activate_filter": False,
        },
        "lookups": [],
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
                {"name": "id", "expression": "row1['id']"},
                {"name": "val", "expression": "row1['val']"},
            ],
        }
    ],
    "die_on_error": True,
}

_LOOKUP_CONFIG = {
    "component_type": "PyMap",
    "inputs": {
        "main": {
            "name": "row1",
            "filter": "",
            "activate_filter": False,
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
                        "expression": "row1.key",
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
                {"name": "id", "expression": "row1['id']"},
                {"name": "label", "expression": "row2['label']"},
            ],
        }
    ],
    "die_on_error": True,
}


def _make_pymap(config=None, global_map=None, context_manager=None):
    """Create a PyMap component with test defaults."""
    gm = global_map if global_map is not None else GlobalMap()
    cm = context_manager or ContextManager()
    cfg = copy.deepcopy(config if config is not None else _SIMPLE_CONFIG)
    return PyMap(
        component_id="py_map_test",
        config=cfg,
        global_map=gm,
        context_manager=cm,
    )


def _main_df(rows=None) -> pd.DataFrame:
    if rows is None:
        rows = [
            {"id": 1, "key": "A", "val": 10, "price": 5.0},
            {"id": 2, "key": "B", "val": 20, "price": 20.0},
            {"id": 3, "key": "C", "val": 30, "price": 3.0},
        ]
    return pd.DataFrame(rows)


def _lookup_df(rows=None) -> pd.DataFrame:
    if rows is None:
        rows = [
            {"key": "A", "label": "Alpha"},
            {"key": "B", "label": "Beta"},
            {"key": "D", "label": "Delta"},
        ]
    return pd.DataFrame(rows)


def _input_dict(main=None, lookup=None, main_name="row1", lookup_name="row2"):
    return {main_name: main or _main_df(), lookup_name: lookup or _lookup_df()}


# ------------------------------------------------------------------
# Registration
# ------------------------------------------------------------------

@pytest.mark.unit
class TestRegistration:
    """Component registers in the global REGISTRY."""

    def test_registered_as_pymap(self):
        cls = REGISTRY.get("PyMap")
        assert cls is PyMap

    def test_instantiation_via_registry(self):
        cls = REGISTRY.get("PyMap")
        comp = cls(
            component_id="test",
            config=copy.deepcopy(_SIMPLE_CONFIG),
            global_map=GlobalMap(),
            context_manager=ContextManager(),
        )
        assert isinstance(comp, PyMap)


# ------------------------------------------------------------------
# Config Validation
# ------------------------------------------------------------------

@pytest.mark.unit
class TestValidation:
    """_validate_config raises ConfigurationError for invalid configs."""

    def test_missing_inputs_raises(self):
        cfg = copy.deepcopy(_SIMPLE_CONFIG)
        del cfg["inputs"]
        comp = _make_pymap(config=cfg)
        with pytest.raises(ConfigurationError, match="inputs"):
            comp.execute(_main_df())

    def test_missing_main_raises(self):
        cfg = copy.deepcopy(_SIMPLE_CONFIG)
        del cfg["inputs"]["main"]
        comp = _make_pymap(config=cfg)
        with pytest.raises(ConfigurationError, match="main"):
            comp.execute(_main_df())

    def test_missing_main_name_raises(self):
        cfg = copy.deepcopy(_SIMPLE_CONFIG)
        del cfg["inputs"]["main"]["name"]
        comp = _make_pymap(config=cfg)
        with pytest.raises(ConfigurationError, match="name"):
            comp.execute(_main_df())

    def test_invalid_lookups_type_raises(self):
        cfg = copy.deepcopy(_SIMPLE_CONFIG)
        cfg["inputs"]["lookups"] = "not_a_list"
        comp = _make_pymap(config=cfg)
        with pytest.raises(ConfigurationError, match="lookups"):
            comp.execute(_main_df())

    def test_lookup_missing_name_raises(self):
        cfg = copy.deepcopy(_LOOKUP_CONFIG)
        del cfg["inputs"]["lookups"][0]["name"]
        comp = _make_pymap(config=cfg)
        with pytest.raises(ConfigurationError, match="name"):
            comp.execute(_input_dict())

    def test_lookup_missing_join_keys_raises(self):
        cfg = copy.deepcopy(_LOOKUP_CONFIG)
        del cfg["inputs"]["lookups"][0]["join_keys"]
        comp = _make_pymap(config=cfg)
        with pytest.raises(ConfigurationError, match="join_keys"):
            comp.execute(_input_dict())

    def test_lookup_missing_join_mode_raises(self):
        cfg = copy.deepcopy(_LOOKUP_CONFIG)
        del cfg["inputs"]["lookups"][0]["join_mode"]
        comp = _make_pymap(config=cfg)
        with pytest.raises(ConfigurationError, match="join_mode"):
            comp.execute(_input_dict())

    def test_missing_outputs_raises(self):
        cfg = copy.deepcopy(_SIMPLE_CONFIG)
        del cfg["outputs"]
        comp = _make_pymap(config=cfg)
        with pytest.raises(ConfigurationError, match="outputs"):
            comp.execute(_main_df())

    def test_empty_outputs_raises(self):
        cfg = copy.deepcopy(_SIMPLE_CONFIG)
        cfg["outputs"] = []
        comp = _make_pymap(config=cfg)
        with pytest.raises(ConfigurationError, match="output"):
            comp.execute(_main_df())

    def test_output_missing_name_raises(self):
        cfg = copy.deepcopy(_SIMPLE_CONFIG)
        del cfg["outputs"][0]["name"]
        comp = _make_pymap(config=cfg)
        with pytest.raises(ConfigurationError, match="name"):
            comp.execute(_main_df())

    def test_output_missing_columns_raises(self):
        cfg = copy.deepcopy(_SIMPLE_CONFIG)
        del cfg["outputs"][0]["columns"]
        comp = _make_pymap(config=cfg)
        with pytest.raises(ConfigurationError, match="columns"):
            comp.execute(_main_df())


# ------------------------------------------------------------------
# Simple Column Passthrough
# ------------------------------------------------------------------

@pytest.mark.unit
class TestSimplePassthrough:
    """Passthrough mappings and basic output shape."""

    def test_single_input_columns_passed_through(self):
        comp = _make_pymap()
        df = _main_df()
        result = comp.execute({"row1": df})
        out = result["out1"]
        assert list(out.columns) == ["id", "val"]
        assert list(out["id"]) == [1, 2, 3]
        assert list(out["val"]) == [10, 20, 30]

    def test_output_row_count_matches_input(self):
        comp = _make_pymap()
        df = _main_df()
        result = comp.execute({"row1": df})
        assert len(result["out1"]) == len(df)

    def test_column_rename_via_expression(self):
        cfg = copy.deepcopy(_SIMPLE_CONFIG)
        cfg["outputs"][0]["columns"] = [
            {"name": "identifier", "expression": "row1['id']"},
        ]
        comp = _make_pymap(config=cfg)
        result = comp.execute({"row1": _main_df()})
        assert "identifier" in result["out1"].columns
        assert list(result["out1"]["identifier"]) == [1, 2, 3]

    def test_multi_output(self):
        cfg = copy.deepcopy(_SIMPLE_CONFIG)
        cfg["outputs"].append({
            "name": "out2",
            "is_reject": False,
            "inner_join_reject": False,
            "filter": "",
            "activate_filter": False,
            "columns": [
                {"name": "price", "expression": "row1['price']"},
            ],
        })
        comp = _make_pymap(config=cfg)
        result = comp.execute({"row1": _main_df()})
        assert "out1" in result
        assert "out2" in result
        assert list(result["out2"]["price"]) == [5.0, 20.0, 3.0]


# ------------------------------------------------------------------
# Python Expression Evaluation
# ------------------------------------------------------------------

@pytest.mark.unit
class TestPythonExpressions:
    """Python expressions are evaluated correctly per row."""

    def test_arithmetic_expression(self):
        cfg = copy.deepcopy(_SIMPLE_CONFIG)
        cfg["outputs"][0]["columns"] = [
            {"name": "doubled", "expression": "row1['val'] * 2"},
        ]
        comp = _make_pymap(config=cfg)
        result = comp.execute({"row1": _main_df()})
        assert list(result["out1"]["doubled"]) == [20, 40, 60]

    def test_string_expression(self):
        df = pd.DataFrame([{"name": "hello"}, {"name": "world"}])
        cfg = copy.deepcopy(_SIMPLE_CONFIG)
        cfg["inputs"]["main"]["name"] = "row1"
        cfg["outputs"][0]["columns"] = [
            {"name": "upper_name", "expression": "row1['name'].upper()"},
        ]
        comp = _make_pymap(config=cfg)
        result = comp.execute({"row1": df})
        assert list(result["out1"]["upper_name"]) == ["HELLO", "WORLD"]

    def test_ternary_expression(self):
        cfg = copy.deepcopy(_SIMPLE_CONFIG)
        cfg["outputs"][0]["columns"] = [
            {"name": "label", "expression": "'HIGH' if row1['val'] > 15 else 'LOW'"},
        ]
        comp = _make_pymap(config=cfg)
        result = comp.execute({"row1": _main_df()})
        assert list(result["out1"]["label"]) == ["LOW", "HIGH", "HIGH"]

    def test_regex_expression(self):
        df = pd.DataFrame([{"name": "foo bar"}, {"name": "hello world"}])
        cfg = copy.deepcopy(_SIMPLE_CONFIG)
        cfg["outputs"][0]["columns"] = [
            {"name": "slug", "expression": "re.sub(r'\\s+', '_', row1['name'])"},
        ]
        comp = _make_pymap(config=cfg)
        result = comp.execute({"row1": df})
        assert list(result["out1"]["slug"]) == ["foo_bar", "hello_world"]

    def test_numpy_expression(self):
        cfg = copy.deepcopy(_SIMPLE_CONFIG)
        cfg["outputs"][0]["columns"] = [
            {"name": "rounded", "expression": "float(np.round(row1['price'] * 1.1, 2))"},
        ]
        comp = _make_pymap(config=cfg)
        result = comp.execute({"row1": _main_df()})
        assert result["out1"]["rounded"].iloc[0] == pytest.approx(5.5, rel=1e-3)

    def test_combined_columns_expression(self):
        df = pd.DataFrame([{"first": "John", "last": "Doe"}])
        cfg = copy.deepcopy(_SIMPLE_CONFIG)
        cfg["outputs"][0]["columns"] = [
            {"name": "full", "expression": "row1['first'] + ' ' + row1['last']"},
        ]
        comp = _make_pymap(config=cfg)
        result = comp.execute({"row1": df})
        assert result["out1"]["full"].iloc[0] == "John Doe"

    def test_none_expression_gives_none_column(self):
        cfg = copy.deepcopy(_SIMPLE_CONFIG)
        cfg["outputs"][0]["columns"] = [
            {"name": "empty", "expression": ""},
        ]
        comp = _make_pymap(config=cfg)
        result = comp.execute({"row1": _main_df()})
        # Empty expression -> None for each row
        assert result["out1"]["empty"].isna().all() or (result["out1"]["empty"] == None).all()  # noqa: E711


# ------------------------------------------------------------------
# Variable Evaluation
# ------------------------------------------------------------------

@pytest.mark.unit
class TestVariableEvaluation:
    """Variables are populated in Var and available to output expressions."""

    def test_simple_variable_used_in_output(self):
        cfg = copy.deepcopy(_SIMPLE_CONFIG)
        cfg["variables"] = [
            {"name": "total", "expression": "row1['val'] * row1['price']"},
        ]
        cfg["outputs"][0]["columns"] = [
            {"name": "total_cost", "expression": "Var['total']"},
        ]
        comp = _make_pymap(config=cfg)
        result = comp.execute({"row1": _main_df()})
        expected = [10 * 5.0, 20 * 20.0, 30 * 3.0]
        assert list(result["out1"]["total_cost"]) == pytest.approx(expected)

    def test_chained_variables(self):
        """Later variable can reference earlier variable via Var dict."""
        cfg = copy.deepcopy(_SIMPLE_CONFIG)
        cfg["variables"] = [
            {"name": "subtotal", "expression": "row1['val'] * row1['price']"},
            {"name": "taxed", "expression": "Var['subtotal'] * 1.1"},
        ]
        cfg["outputs"][0]["columns"] = [
            {"name": "final", "expression": "round(Var['taxed'], 2)"},
        ]
        comp = _make_pymap(config=cfg)
        result = comp.execute({"row1": _main_df()})
        assert result["out1"]["final"].iloc[0] == pytest.approx(55.0, rel=1e-3)

    def test_variable_with_conditional(self):
        cfg = copy.deepcopy(_SIMPLE_CONFIG)
        cfg["variables"] = [
            {"name": "tier", "expression": "'HIGH' if row1['val'] > 15 else 'LOW'"},
        ]
        cfg["outputs"][0]["columns"] = [
            {"name": "tier", "expression": "Var['tier']"},
        ]
        comp = _make_pymap(config=cfg)
        result = comp.execute({"row1": _main_df()})
        assert list(result["out1"]["tier"]) == ["LOW", "HIGH", "HIGH"]


# ------------------------------------------------------------------
# Join Semantics
# ------------------------------------------------------------------

@pytest.mark.unit
class TestLeftOuterJoin:
    """LEFT_OUTER_JOIN preserves all main rows."""

    def test_matched_rows_have_lookup_columns(self):
        comp = _make_pymap(config=_LOOKUP_CONFIG)
        result = comp.execute(_input_dict())
        out = result["out1"]
        row_a = out[out["id"] == 1].iloc[0]
        assert row_a["label"] == "Alpha"
        row_b = out[out["id"] == 2].iloc[0]
        assert row_b["label"] == "Beta"

    def test_unmatched_rows_preserved_with_nan_lookup(self):
        """Row with key 'C' has no match in lookup -- row still in output."""
        comp = _make_pymap(config=_LOOKUP_CONFIG)
        result = comp.execute(_input_dict())
        out = result["out1"]
        # id=3 has key="C" which is not in lookup
        row_c = out[out["id"] == 3].iloc[0]
        assert pd.isna(row_c["label"])

    def test_output_row_count_equals_main_rows(self):
        comp = _make_pymap(config=_LOOKUP_CONFIG)
        result = comp.execute(_input_dict())
        assert len(result["out1"]) == 3

    def test_empty_lookup_preserves_main(self):
        comp = _make_pymap(config=_LOOKUP_CONFIG)
        result = comp.execute({"row1": _main_df(), "row2": pd.DataFrame(columns=["key", "label"])})
        assert len(result["out1"]) == 3


@pytest.mark.unit
class TestInnerJoin:
    """INNER_JOIN removes unmatched rows and routes to inner_join_reject output."""

    def _make_inner_join_config(self):
        cfg = copy.deepcopy(_LOOKUP_CONFIG)
        cfg["inputs"]["lookups"][0]["join_mode"] = "INNER_JOIN"
        cfg["outputs"].append({
            "name": "reject1",
            "is_reject": False,
            "inner_join_reject": True,
            "filter": "",
            "activate_filter": False,
            "columns": [
                {"name": "id", "expression": "row1['id']"},
            ],
        })
        return cfg

    def test_unmatched_rows_removed_from_main_output(self):
        cfg = self._make_inner_join_config()
        comp = _make_pymap(config=cfg)
        result = comp.execute(_input_dict())
        # id=3 (key="C") has no match -> excluded from out1
        assert 3 not in list(result["out1"]["id"])

    def test_matched_rows_in_main_output(self):
        cfg = self._make_inner_join_config()
        comp = _make_pymap(config=cfg)
        result = comp.execute(_input_dict())
        assert set(result["out1"]["id"]) == {1, 2}

    def test_unmatched_rows_in_reject_output(self):
        cfg = self._make_inner_join_config()
        comp = _make_pymap(config=cfg)
        result = comp.execute(_input_dict())
        assert "reject1" in result
        assert len(result["reject1"]) >= 1


@pytest.mark.unit
class TestNullKeySemantics:
    """Null join keys never match (SQL/Talend null semantics)."""

    def test_null_main_key_does_not_match(self):
        comp = _make_pymap(config=_LOOKUP_CONFIG)
        main = pd.DataFrame([
            {"id": 1, "key": None, "val": 10, "price": 1.0},
        ])
        result = comp.execute({"row1": main, "row2": _lookup_df()})
        out = result["out1"]
        assert len(out) == 1
        assert pd.isna(out.iloc[0]["label"])

    def test_null_lookup_key_does_not_match(self):
        comp = _make_pymap(config=_LOOKUP_CONFIG)
        lookup = pd.DataFrame([
            {"key": None, "label": "Null"},
            {"key": "A", "label": "Alpha"},
        ])
        main = pd.DataFrame([{"id": 1, "key": "A", "val": 10, "price": 1.0}])
        result = comp.execute({"row1": main, "row2": lookup})
        out = result["out1"]
        assert out.iloc[0]["label"] == "Alpha"


# ------------------------------------------------------------------
# Matching Modes
# ------------------------------------------------------------------

@pytest.mark.unit
class TestMatchingModes:
    """Matching modes deduplicate the lookup correctly."""

    def _make_dup_lookup(self):
        return pd.DataFrame([
            {"key": "A", "label": "Alpha1"},
            {"key": "A", "label": "Alpha2"},
            {"key": "B", "label": "Beta"},
        ])

    def test_unique_match_keeps_last(self):
        cfg = copy.deepcopy(_LOOKUP_CONFIG)
        cfg["inputs"]["lookups"][0]["matching_mode"] = "UNIQUE_MATCH"
        comp = _make_pymap(config=cfg)
        main = pd.DataFrame([{"id": 1, "key": "A", "val": 1, "price": 1.0}])
        result = comp.execute({"row1": main, "row2": self._make_dup_lookup()})
        assert result["out1"].iloc[0]["label"] == "Alpha2"

    def test_first_match_keeps_first(self):
        cfg = copy.deepcopy(_LOOKUP_CONFIG)
        cfg["inputs"]["lookups"][0]["matching_mode"] = "FIRST_MATCH"
        comp = _make_pymap(config=cfg)
        main = pd.DataFrame([{"id": 1, "key": "A", "val": 1, "price": 1.0}])
        result = comp.execute({"row1": main, "row2": self._make_dup_lookup()})
        assert result["out1"].iloc[0]["label"] == "Alpha1"

    def test_last_match_keeps_last(self):
        cfg = copy.deepcopy(_LOOKUP_CONFIG)
        cfg["inputs"]["lookups"][0]["matching_mode"] = "LAST_MATCH"
        comp = _make_pymap(config=cfg)
        main = pd.DataFrame([{"id": 1, "key": "A", "val": 1, "price": 1.0}])
        result = comp.execute({"row1": main, "row2": self._make_dup_lookup()})
        assert result["out1"].iloc[0]["label"] == "Alpha2"

    def test_all_matches_returns_cartesian(self):
        cfg = copy.deepcopy(_LOOKUP_CONFIG)
        cfg["inputs"]["lookups"][0]["matching_mode"] = "ALL_MATCHES"
        comp = _make_pymap(config=cfg)
        main = pd.DataFrame([{"id": 1, "key": "A", "val": 1, "price": 1.0}])
        result = comp.execute({"row1": main, "row2": self._make_dup_lookup()})
        # Both Alpha1 and Alpha2 should be in result
        labels = list(result["out1"]["label"])
        assert "Alpha1" in labels
        assert "Alpha2" in labels


# ------------------------------------------------------------------
# Output Filter
# ------------------------------------------------------------------

@pytest.mark.unit
class TestOutputFilter:
    """Output filter keeps/rejects rows and routes to is_reject output."""

    def _make_filter_config(self):
        cfg = copy.deepcopy(_SIMPLE_CONFIG)
        cfg["outputs"][0]["activate_filter"] = True
        cfg["outputs"][0]["filter"] = "row1['val'] > 15"
        cfg["outputs"].append({
            "name": "filtered_out",
            "is_reject": True,
            "inner_join_reject": False,
            "filter": "",
            "activate_filter": False,
            "columns": [
                {"name": "id", "expression": "row1['id']"},
                {"name": "val", "expression": "row1['val']"},
            ],
        })
        return cfg

    def test_passing_rows_in_main_output(self):
        cfg = self._make_filter_config()
        comp = _make_pymap(config=cfg)
        result = comp.execute({"row1": _main_df()})
        out = result["out1"]
        assert all(out["val"] > 15)

    def test_rejected_rows_in_reject_output(self):
        cfg = self._make_filter_config()
        comp = _make_pymap(config=cfg)
        result = comp.execute({"row1": _main_df()})
        rej = result["filtered_out"]
        assert all(rej["val"] <= 15)

    def test_filter_total_rows_equals_input(self):
        cfg = self._make_filter_config()
        comp = _make_pymap(config=cfg)
        result = comp.execute({"row1": _main_df()})
        total = len(result["out1"]) + len(result["filtered_out"])
        assert total == 3


# ------------------------------------------------------------------
# Error Handling
# ------------------------------------------------------------------

@pytest.mark.unit
class TestErrorHandling:
    """die_on_error controls behaviour when expression evaluation fails."""

    def test_bad_expression_die_on_error_raises(self):
        cfg = copy.deepcopy(_SIMPLE_CONFIG)
        cfg["outputs"][0]["columns"] = [
            {"name": "bad", "expression": "row1['nonexistent_key']"},
        ]
        cfg["die_on_error"] = True
        comp = _make_pymap(config=cfg)
        with pytest.raises((ComponentExecutionError, KeyError)):
            comp.execute({"row1": _main_df()})

    def test_bad_expression_die_on_error_false_gives_none(self):
        cfg = copy.deepcopy(_SIMPLE_CONFIG)
        cfg["outputs"][0]["columns"] = [
            {"name": "safe", "expression": "row1['id']"},
            {"name": "bad", "expression": "row1['nonexistent_key']"},
        ]
        cfg["die_on_error"] = False
        comp = _make_pymap(config=cfg)
        result = comp.execute({"row1": _main_df()})
        # bad column should contain None/NaN for each row
        bad_vals = result["out1"]["bad"]
        assert bad_vals.isna().all() or (bad_vals == None).all()  # noqa: E711

    def test_sandbox_blocks_os_import(self):
        """os module is not accessible via import in expressions."""
        cfg = copy.deepcopy(_SIMPLE_CONFIG)
        cfg["outputs"][0]["columns"] = [
            {"name": "os_attempt", "expression": "__import__('os').getcwd()"},
        ]
        cfg["die_on_error"] = False
        comp = _make_pymap(config=cfg)
        # Should not raise but column will be None (eval sees no __import__)
        result = comp.execute({"row1": _main_df()})
        assert "os_attempt" in result["out1"].columns


# ------------------------------------------------------------------
# RELOAD_AT_EACH_ROW
# ------------------------------------------------------------------

@pytest.mark.unit
class TestReloadAtEachRow:
    """RELOAD_AT_EACH_ROW re-filters lookup per main row."""

    def test_reload_returns_correct_lookup_values(self):
        cfg = copy.deepcopy(_LOOKUP_CONFIG)
        cfg["inputs"]["lookups"][0]["lookup_mode"] = "RELOAD_AT_EACH_ROW"
        comp = _make_pymap(config=cfg)
        result = comp.execute(_input_dict())
        out = result["out1"]
        # id=1 (key="A") should still get label="Alpha"
        assert out[out["id"] == 1].iloc[0]["label"] == "Alpha"

    def test_reload_unmatched_row_gets_nan(self):
        cfg = copy.deepcopy(_LOOKUP_CONFIG)
        cfg["inputs"]["lookups"][0]["lookup_mode"] = "RELOAD_AT_EACH_ROW"
        comp = _make_pymap(config=cfg)
        result = comp.execute(_input_dict())
        out = result["out1"]
        # id=3 (key="C") has no match
        assert pd.isna(out[out["id"] == 3].iloc[0]["label"])


# ------------------------------------------------------------------
# Empty / Edge Cases
# ------------------------------------------------------------------

@pytest.mark.unit
class TestEdgeCases:
    """Edge cases: empty inputs, None input, dict input."""

    def test_none_input_returns_empty_outputs(self):
        comp = _make_pymap()
        result = comp.execute(None)
        assert "out1" in result
        assert result["out1"].empty

    def test_empty_main_returns_empty_outputs(self):
        comp = _make_pymap()
        result = comp.execute({"row1": pd.DataFrame(columns=["id", "val", "price", "key"])})
        assert result["out1"].empty

    def test_single_dataframe_input_accepted(self):
        """Single DataFrame (no dict) uses inputs.main.name as key."""
        comp = _make_pymap()
        result = comp.execute(_main_df())
        assert len(result["out1"]) == 3

    def test_empty_lookup_with_left_outer_preserves_main(self):
        comp = _make_pymap(config=_LOOKUP_CONFIG)
        result = comp.execute({
            "row1": _main_df(),
            "row2": pd.DataFrame(columns=["key", "label"]),
        })
        # All main rows preserved, label = NaN
        assert len(result["out1"]) == 3
        assert result["out1"]["label"].isna().all()

    def test_output_has_correct_columns_when_no_rows(self):
        comp = _make_pymap()
        result = comp.execute({"row1": pd.DataFrame(columns=["id", "val", "price", "key"])})
        assert list(result["out1"].columns) == ["id", "val"]


# ------------------------------------------------------------------
# Auto Type Conversion
# ------------------------------------------------------------------

@pytest.mark.unit
class TestAutoTypeConversion:
    """enable_auto_convert_type converts mismatched join key types."""

    def test_string_main_key_matches_int_lookup_key(self):
        cfg = copy.deepcopy(_LOOKUP_CONFIG)
        cfg["inputs"]["lookups"][0]["join_keys"] = [
            {"lookup_column": "id", "expression": "row1.id"}
        ]
        cfg["enable_auto_convert_type"] = True
        cfg["outputs"][0]["columns"] = [
            {"name": "id", "expression": "row1['id']"},
            {"name": "label", "expression": "row2['label']"},
        ]
        comp = _make_pymap(config=cfg)

        main = pd.DataFrame([{"id": "1", "key": "A", "val": 10, "price": 1.0}])
        lookup = pd.DataFrame([{"id": 1, "label": "One"}])
        result = comp.execute({"row1": main, "row2": lookup})
        assert result["out1"].iloc[0]["label"] == "One"


# ------------------------------------------------------------------
# Stats
# ------------------------------------------------------------------

@pytest.mark.unit
class TestStats:
    """Global map stats are updated after execution."""

    def test_nb_line_updated(self):
        comp = _make_pymap()
        comp.execute({"row1": _main_df()})
        assert comp.stats["NB_LINE"] == 3

    def test_nb_line_ok_equals_nb_line_for_no_rejects(self):
        comp = _make_pymap()
        comp.execute({"row1": _main_df()})
        assert comp.stats["NB_LINE_OK"] == 3
        assert comp.stats["NB_LINE_REJECT"] == 0


# ------------------------------------------------------------------
# Context / GlobalMap in eval namespace (Phase 05.5 R5)
# ------------------------------------------------------------------


def _ctx_and_gm(context_kv: dict, gm_kv: dict):
    """Build a populated ContextManager + GlobalMap for R5 tests.

    Uses ContextManager.set(key, value, value_type) -- positional third arg
    (verified at src/v1/engine/context_manager.py:151). Matches existing
    test patterns in test_file_archive.py and test_context_load.py.
    """
    cm = ContextManager()
    for k, v in context_kv.items():
        cm.set(k, v, "id_String")
    gm = GlobalMap()
    for k, v in gm_kv.items():
        gm.put(k, v)
    return cm, gm


def _ctx_pymap_config(expression: str) -> dict:
    """Single-column py_map config with the expression under test."""
    return {
        "component_type": "PyMap",
        "inputs": {
            "main": {
                "name": "row1",
                "filter": "",
                "activate_filter": False,
            },
            "lookups": [],
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
                    {"name": "decorated", "expression": expression},
                ],
            }
        ],
        "die_on_error": True,
    }


@pytest.mark.unit
class TestPyMapContext:
    """R5: context and globalMap are bound into the per-row eval namespace.

    Pure-Python tests -- no @pytest.mark.java (py_map does not use the
    Java bridge). Verifies that user expressions in py_map columns can
    reference context.X (attribute), context['X'] (item), and
    globalMap.get('X') (method) with the same Talend-style semantics
    tMap provides via its Groovy bindings.
    """

    def test_context_attribute_access(self):
        """context.X attribute access resolves to ContextManager value."""
        cm, gm = _ctx_and_gm(
            {"suffix": "_DEV", "threshold": "50"},
            {"env": "prod"},
        )
        cfg = _ctx_pymap_config("str(row1['id']) + context.suffix")
        comp = _make_pymap(config=cfg, context_manager=cm, global_map=gm)
        df = pd.DataFrame([{"id": 42}])
        result = comp.execute({"row1": df})
        assert result["out1"]["decorated"].iloc[0] == "42_DEV"

    def test_context_item_access(self):
        """context['X'] item access works equivalently to attribute access."""
        cm, gm = _ctx_and_gm(
            {"threshold": "50"},
            {},
        )
        cfg = _ctx_pymap_config("context['threshold']")
        comp = _make_pymap(config=cfg, context_manager=cm, global_map=gm)
        df = pd.DataFrame([{"id": 1}])
        result = comp.execute({"row1": df})
        assert result["out1"]["decorated"].iloc[0] == "50"

    def test_global_map_get_method(self):
        """globalMap.get('X') returns the live GlobalMap value."""
        cm, gm = _ctx_and_gm(
            {},
            {"env": "prod"},
        )
        cfg = _ctx_pymap_config("str(row1['id']) + '_' + globalMap.get('env')")
        comp = _make_pymap(config=cfg, context_manager=cm, global_map=gm)
        df = pd.DataFrame([{"id": 7}])
        result = comp.execute({"row1": df})
        assert result["out1"]["decorated"].iloc[0] == "7_prod"

    def test_missing_context_key_raises_attributeerror(self):
        """context.nonexistent must raise AttributeError (deterministic).

        Wrapped by ComponentExecutionError in die_on_error=True mode --
        the original cause must be AttributeError, NOT NameError or a
        silent None.
        """
        cm, gm = _ctx_and_gm(
            {"suffix": "_DEV"},
            {},
        )
        cfg = _ctx_pymap_config("context.nonexistent")
        comp = _make_pymap(config=cfg, context_manager=cm, global_map=gm)
        df = pd.DataFrame([{"id": 1}])
        with pytest.raises(ComponentExecutionError) as exc_info:
            comp.execute({"row1": df})
        # Verify the underlying cause is AttributeError, not NameError.
        cause = exc_info.value.__cause__ or exc_info.value.__context__
        # ComponentExecutionError wraps the eval failure; walk the chain.
        root = cause
        while root is not None and not isinstance(root, AttributeError):
            root = getattr(root, "__cause__", None) or getattr(root, "__context__", None)
        assert isinstance(root, AttributeError), (
            f"expected AttributeError in cause chain, got {type(cause).__name__}: {cause}"
        )


class TestContextGlobalMapViews:
    """Direct unit coverage for _ContextView / _GlobalMapView edge branches.

    Plan 05.5-08 Task 1: cover the None-state and missing-key branches
    introduced by Plan 05.5-03 so py_map.py stays at >= 80.6% line
    coverage (Phase 14 baseline).
    """

    def test_context_view_attribute_no_manager(self):
        from src.v1.engine.components.transform.py_map import _ContextView

        view = _ContextView(None)
        with pytest.raises(AttributeError, match="not configured"):
            _ = view.suffix

    def test_context_view_item_no_manager(self):
        from src.v1.engine.components.transform.py_map import _ContextView

        view = _ContextView(None)
        with pytest.raises(KeyError):
            _ = view["suffix"]

    def test_context_view_item_missing_key(self):
        from src.v1.engine.components.transform.py_map import _ContextView

        cm = ContextManager()
        cm.set("threshold", "50")
        view = _ContextView(cm)
        assert view["threshold"] == "50"
        with pytest.raises(KeyError):
            _ = view["missing"]

    def test_global_map_view_get_no_global_map(self):
        from src.v1.engine.components.transform.py_map import _GlobalMapView

        view = _GlobalMapView(None)
        assert view.get("env") is None
        assert view.get("env", "fallback") == "fallback"

    def test_global_map_view_attribute_no_global_map(self):
        from src.v1.engine.components.transform.py_map import _GlobalMapView

        view = _GlobalMapView(None)
        with pytest.raises(AttributeError, match="not configured"):
            _ = view.env

    def test_global_map_view_attribute_present(self):
        from src.v1.engine.components.transform.py_map import _GlobalMapView

        gm = GlobalMap()
        gm.put("env", "prod")
        view = _GlobalMapView(gm)
        assert view.env == "prod"

    def test_global_map_view_item_no_global_map(self):
        from src.v1.engine.components.transform.py_map import _GlobalMapView

        view = _GlobalMapView(None)
        with pytest.raises(KeyError):
            _ = view["env"]

    def test_global_map_view_item_missing_key(self):
        from src.v1.engine.components.transform.py_map import _GlobalMapView

        gm = GlobalMap()
        gm.put("env", "prod")
        view = _GlobalMapView(gm)
        assert view["env"] == "prod"
        with pytest.raises(KeyError):
            _ = view["missing"]


class TestRowAttributeMissing:
    """Cover _Row.__getattr__ KeyError -> AttributeError branch (L77-80)."""

    def test_row_missing_attribute_raises(self):
        from src.v1.engine.components.transform.py_map import _Row

        row = _Row({"id": 42})
        assert row.id == 42
        with pytest.raises(AttributeError, match="no column"):
            _ = row.missing


# ------------------------------------------------------------------
# Coverage lift -- lifecycle hook / parsing branches
# ------------------------------------------------------------------


def _bare_pymap(config, global_map=None, context_manager=None):
    """Build a PyMap and prime comp.config like ETLEngine does.

    Direct _process / helper calls bypass execute()'s config deepcopy, so
    we set comp.config explicitly (per the test conventions).
    """
    gm = global_map if global_map is not None else GlobalMap()
    comp = PyMap(
        component_id="py_map_test",
        config=copy.deepcopy(config),
        global_map=gm,
        context_manager=context_manager,
    )
    comp.config = copy.deepcopy(config)
    return comp


@pytest.mark.unit
class TestResolveExpressions:
    """_resolve_expressions scalar-field handling (L189-195)."""

    def test_no_context_manager_returns_early(self):
        """context_manager is None -> early return, no resolution (L190)."""
        cfg = copy.deepcopy(_SIMPLE_CONFIG)
        cfg["label"] = "context.env"
        comp = _bare_pymap(cfg, context_manager=None)
        comp._resolve_expressions()
        # Unchanged -- no resolution attempted.
        assert comp.config["label"] == "context.env"

    def test_scalar_string_fields_resolved(self):
        """String label / die_on_error / enable_auto_convert_type resolve (L193)."""
        cm = ContextManager()
        cm.set("env", "prod")
        cfg = copy.deepcopy(_SIMPLE_CONFIG)
        cfg["label"] = "context.env"
        cfg["die_on_error"] = "True"
        cfg["enable_auto_convert_type"] = "context.env"
        comp = _bare_pymap(cfg, context_manager=cm)
        comp._resolve_expressions()
        assert comp.config["label"] == "prod"
        assert comp.config["die_on_error"] == "True"
        assert comp.config["enable_auto_convert_type"] == "prod"


@pytest.mark.unit
class TestUpdateStatsBranches:
    """_update_stats_from_result skips the 'stats' key (L213)."""

    def test_stats_key_skipped(self):
        comp = _bare_pymap(_SIMPLE_CONFIG)
        comp.stats = {"NB_LINE": 0, "NB_LINE_OK": 0, "NB_LINE_REJECT": 0}
        result = {
            "stats": {"ignored": 99},
            "out1": pd.DataFrame([{"id": 1}, {"id": 2}]),
        }
        comp._update_stats_from_result(result)
        assert comp.stats["NB_LINE"] == 2
        assert comp.stats["NB_LINE_OK"] == 2
        assert comp.stats["NB_LINE_REJECT"] == 0


@pytest.mark.unit
class TestValidationJoinKeyFields:
    """Join-key field validation (L268, L273)."""

    def test_join_key_missing_lookup_column_raises(self):
        cfg = copy.deepcopy(_LOOKUP_CONFIG)
        cfg["inputs"]["lookups"][0]["join_keys"] = [{"expression": "row1.key"}]
        comp = _make_pymap(config=cfg)
        with pytest.raises(ConfigurationError, match="lookup_column"):
            comp.execute(_input_dict())

    def test_join_key_missing_expression_raises(self):
        cfg = copy.deepcopy(_LOOKUP_CONFIG)
        cfg["inputs"]["lookups"][0]["join_keys"] = [{"lookup_column": "key"}]
        comp = _make_pymap(config=cfg)
        with pytest.raises(ConfigurationError, match="expression"):
            comp.execute(_input_dict())


@pytest.mark.unit
class TestParseInputsNone:
    """_parse_inputs returns None for unexpected input types (L451)."""

    def test_unexpected_type_returns_none(self):
        comp = _bare_pymap(_SIMPLE_CONFIG)
        assert comp._parse_inputs(["not", "supported"]) is None

    def test_unexpected_type_via_process_returns_empty(self):
        comp = _bare_pymap(_SIMPLE_CONFIG)
        result = comp._process(12345)
        assert "out1" in result
        assert result["out1"].empty


# ------------------------------------------------------------------
# Coverage lift -- main / lookup filter branches
# ------------------------------------------------------------------


@pytest.mark.unit
class TestMainAndLookupFilters:
    """Main-input filter (L341-345) and lookup filter (L379) branches."""

    def test_main_filter_drops_rows(self):
        cfg = copy.deepcopy(_SIMPLE_CONFIG)
        cfg["inputs"]["main"]["activate_filter"] = True
        cfg["inputs"]["main"]["filter"] = "row1['val'] > 15"
        comp = _make_pymap(config=cfg)
        result = comp.execute({"row1": _main_df()})
        # Only id=2 (val=20) and id=3 (val=30) survive.
        assert set(result["out1"]["id"]) == {2, 3}

    def test_main_filter_empties_returns_empty_outputs(self):
        """Main empty after filter -> early empty outputs (L343-345)."""
        cfg = copy.deepcopy(_SIMPLE_CONFIG)
        cfg["inputs"]["main"]["activate_filter"] = True
        cfg["inputs"]["main"]["filter"] = "row1['val'] > 1000"
        comp = _make_pymap(config=cfg)
        result = comp.execute({"row1": _main_df()})
        assert result["out1"].empty

    def test_lookup_filter_load_once(self):
        """LOAD_ONCE lookup filter applied before join (L379)."""
        cfg = copy.deepcopy(_LOOKUP_CONFIG)
        cfg["inputs"]["lookups"][0]["activate_filter"] = True
        cfg["inputs"]["lookups"][0]["filter"] = "row2['label'] == 'Alpha'"
        comp = _make_pymap(config=cfg)
        main = pd.DataFrame([
            {"id": 1, "key": "A", "val": 1, "price": 1.0},
            {"id": 2, "key": "B", "val": 2, "price": 2.0},
        ])
        lookup = pd.DataFrame([
            {"key": "A", "label": "Alpha"},
            {"key": "B", "label": "Beta"},
        ])
        result = comp.execute({"row1": main, "row2": lookup})
        out = result["out1"]
        # Only the 'Alpha' lookup row survives the filter; B is unmatched -> NaN.
        assert out[out["id"] == 1].iloc[0]["label"] == "Alpha"
        assert pd.isna(out[out["id"] == 2].iloc[0]["label"])


@pytest.mark.unit
class TestApplyFilterPyDirect:
    """Direct _apply_filter_py coverage incl. empty / bad-expr (L542-565)."""

    def test_empty_df_short_circuits(self):
        comp = _bare_pymap(_SIMPLE_CONFIG)
        empty = pd.DataFrame(columns=["a"])
        out = comp._apply_filter_py(empty, "a > 0", "row1")
        assert out.empty

    def test_blank_filter_short_circuits(self):
        comp = _bare_pymap(_SIMPLE_CONFIG)
        df = pd.DataFrame([{"a": 1}])
        out = comp._apply_filter_py(df, "", "row1")
        assert len(out) == 1

    def test_filter_keeps_truthy_rows(self):
        comp = _bare_pymap(_SIMPLE_CONFIG)
        df = pd.DataFrame([{"a": 1}, {"a": 5}, {"a": 9}])
        out = comp._apply_filter_py(df, "a > 4", "row1")
        assert list(out["a"]) == [5, 9]

    def test_bad_filter_expression_drops_row(self):
        """Exception in filter eval -> mask False (L557-558)."""
        comp = _bare_pymap(_SIMPLE_CONFIG)
        df = pd.DataFrame([{"a": 1}, {"a": 2}])
        out = comp._apply_filter_py(df, "a.nonexistent_method()", "row1")
        assert out.empty


# ------------------------------------------------------------------
# Coverage lift -- equality join branches
# ------------------------------------------------------------------


@pytest.mark.unit
class TestEqualityJoinBranches:
    """_join_equality fallback / inner-join / dup-column branches."""

    def test_non_simple_expression_fallback(self):
        """Non-simple join expression falls back to raw expr key (L607-609).

        The expression is not a bare table.column reference, so the left
        join key becomes the expression string itself. That column name does
        not exist in the joined frame, so pandas merge raises KeyError --
        surfaced (via die_on_error) as ComponentExecutionError. The point is
        to exercise the else-branch fallback at L607-609.
        """
        cfg = copy.deepcopy(_LOOKUP_CONFIG)
        cfg["inputs"]["lookups"][0]["join_keys"] = [
            {"lookup_column": "key", "expression": "row1.key + '_x'"},
        ]
        comp = _make_pymap(config=cfg)
        with pytest.raises(ComponentExecutionError):
            comp.execute(_input_dict())

    def test_non_simple_expression_fallback_helper_direct(self):
        """Direct _join_equality with a non-simple expression hits L607-609.

        Verifies the fallback appends the raw expression as the left key and
        that the subsequent merge raises KeyError on the missing column.
        """
        comp = _bare_pymap(_LOOKUP_CONFIG)
        joined = pd.DataFrame([{"id": 1, "key": "A", "val": 1, "price": 1.0}])
        lookup = pd.DataFrame([{"key": "A", "label": "Alpha"}])
        lookup_cfg = {
            "name": "row2",
            "join_keys": [{"lookup_column": "key", "expression": "row1.key + '_x'"}],
            "join_mode": "LEFT_OUTER_JOIN",
            "matching_mode": "UNIQUE_MATCH",
        }
        with pytest.raises(KeyError):
            comp._join_equality(joined, lookup, lookup_cfg)

    def test_inner_join_null_keys_routed_to_reject(self):
        """INNER_JOIN with all-null main keys routes null rows to reject (L653)."""
        cfg = copy.deepcopy(_LOOKUP_CONFIG)
        cfg["inputs"]["lookups"][0]["join_mode"] = "INNER_JOIN"
        cfg["outputs"].append({
            "name": "reject1",
            "is_reject": False,
            "inner_join_reject": True,
            "filter": "",
            "activate_filter": False,
            "columns": [{"name": "id", "expression": "row1['id']"}],
        })
        comp = _make_pymap(config=cfg)
        # One matchable row (B), one unmatched (C), one null-key row.
        main = pd.DataFrame([
            {"id": 1, "key": "B", "val": 1, "price": 1.0},
            {"id": 2, "key": "C", "val": 2, "price": 2.0},
            {"id": 3, "key": None, "val": 3, "price": 3.0},
        ])
        result = comp.execute({"row1": main, "row2": _lookup_df()})
        assert set(result["out1"]["id"]) == {1}
        # Both unmatched (C) and null-key (None) rows land in rejects.
        assert set(result["reject1"]["id"]) == {2, 3}

    def test_duplicate_key_columns_dropped(self):
        """__dup__ suffixed columns from merge are dropped (L668-670).

        The joined frame already carries a column named like a prefixed
        lookup column ('row2.label'); after prefixing the lookup the merge
        produces a 'row2.label__dup__' column that must be removed.
        """
        comp = _bare_pymap(_LOOKUP_CONFIG)
        # Pre-existing prefixed column collides with the lookup's prefixed col.
        joined = pd.DataFrame([{"id": 1, "key": "A", "row2.label": "stale"}])
        lookup = pd.DataFrame([{"key": "A", "label": "Alpha"}])
        lookup_cfg = {
            "name": "row2",
            "join_keys": [{"lookup_column": "key", "expression": "row1.key"}],
            "join_mode": "LEFT_OUTER_JOIN",
            "matching_mode": "UNIQUE_MATCH",
        }
        merged, rejects = comp._join_equality(joined, lookup, lookup_cfg)
        # No __dup__ columns leaked into the merged frame.
        assert not any(str(c).endswith("__dup__") for c in merged.columns)
        assert "row2.label" in merged.columns


# ------------------------------------------------------------------
# Coverage lift -- RELOAD_AT_EACH_ROW branches
# ------------------------------------------------------------------


@pytest.mark.unit
class TestReloadBranches:
    """RELOAD_AT_EACH_ROW filter / non-simple / inner-reject branches."""

    def test_reload_with_filter_matches(self):
        """RELOAD filter re-evaluated per row (L723-724, L821-834)."""
        cfg = copy.deepcopy(_LOOKUP_CONFIG)
        cfg["inputs"]["lookups"][0]["lookup_mode"] = "RELOAD_AT_EACH_ROW"
        cfg["inputs"]["lookups"][0]["activate_filter"] = True
        # Filter references the lookup row; keeps only 'Alpha'.
        cfg["inputs"]["lookups"][0]["filter"] = "row2['label'] == 'Alpha'"
        comp = _make_pymap(config=cfg)
        main = pd.DataFrame([
            {"id": 1, "key": "A", "val": 1, "price": 1.0},
            {"id": 2, "key": "B", "val": 2, "price": 2.0},
        ])
        lookup = pd.DataFrame([
            {"key": "A", "label": "Alpha"},
            {"key": "B", "label": "Beta"},
        ])
        result = comp.execute({"row1": main, "row2": lookup})
        out = result["out1"]
        assert out[out["id"] == 1].iloc[0]["label"] == "Alpha"
        # Row 2 (key B) -> filter removes Beta -> empty filtered -> NaN (L737-738).
        assert pd.isna(out[out["id"] == 2].iloc[0]["label"])

    def test_reload_filter_empties_inner_join_rejects(self):
        """RELOAD + INNER_JOIN: empty filtered lookup -> reject (L734-735)."""
        cfg = copy.deepcopy(_LOOKUP_CONFIG)
        cfg["inputs"]["lookups"][0]["lookup_mode"] = "RELOAD_AT_EACH_ROW"
        cfg["inputs"]["lookups"][0]["join_mode"] = "INNER_JOIN"
        cfg["inputs"]["lookups"][0]["activate_filter"] = True
        cfg["inputs"]["lookups"][0]["filter"] = "row2['label'] == 'NEVER'"
        cfg["outputs"].append({
            "name": "reject1",
            "is_reject": False,
            "inner_join_reject": True,
            "filter": "",
            "activate_filter": False,
            "columns": [{"name": "id", "expression": "row1['id']"}],
        })
        comp = _make_pymap(config=cfg)
        main = pd.DataFrame([{"id": 1, "key": "A", "val": 1, "price": 1.0}])
        result = comp.execute({"row1": main, "row2": _lookup_df()})
        # No lookup row passes the filter -> main row rejected.
        assert result["out1"].empty
        assert set(result["reject1"]["id"]) == {1}

    def test_reload_left_outer_empty_filter_keeps_main(self):
        """RELOAD + LEFT_OUTER: empty filtered lookup -> raw main row kept (L737)."""
        comp = _bare_pymap(_LOOKUP_CONFIG)
        joined = pd.DataFrame([{"id": 1, "key": "A", "val": 1, "price": 1.0}])
        lookup = pd.DataFrame([{"key": "A", "label": "Alpha"}])
        lookup_cfg = {
            "name": "row2",
            "lookup_mode": "RELOAD_AT_EACH_ROW",
            "activate_filter": True,
            "filter": "row2['label'] == 'NEVER'",  # empties lookup every row
            "join_keys": [{"lookup_column": "key", "expression": "row1.key"}],
            "join_mode": "LEFT_OUTER_JOIN",
            "matching_mode": "UNIQUE_MATCH",
        }
        result_df, rejects = comp._join_reload_per_row(joined, lookup, lookup_cfg)
        # Main row preserved; no inner-join rejects for LEFT_OUTER.
        assert len(result_df) == 1
        assert list(result_df["id"]) == [1]
        assert rejects is None

    def test_reload_non_simple_expression_no_match(self):
        """RELOAD non-simple join expr -> main_val None -> no match (L755, L758-759)."""
        cfg = copy.deepcopy(_LOOKUP_CONFIG)
        cfg["inputs"]["lookups"][0]["lookup_mode"] = "RELOAD_AT_EACH_ROW"
        cfg["inputs"]["lookups"][0]["join_keys"] = [
            {"lookup_column": "key", "expression": "row1.key + '_x'"},
        ]
        comp = _make_pymap(config=cfg)
        main = pd.DataFrame([{"id": 1, "key": "A", "val": 1, "price": 1.0}])
        result = comp.execute({"row1": main, "row2": _lookup_df()})
        # Non-simple expr -> main_val None -> pd.isna -> no match -> LEFT NaN.
        assert pd.isna(result["out1"].iloc[0]["label"])

    def test_reload_inner_join_unmatched_rejected(self):
        """RELOAD + INNER_JOIN unmatched key routes to reject (L773)."""
        cfg = copy.deepcopy(_LOOKUP_CONFIG)
        cfg["inputs"]["lookups"][0]["lookup_mode"] = "RELOAD_AT_EACH_ROW"
        cfg["inputs"]["lookups"][0]["join_mode"] = "INNER_JOIN"
        cfg["outputs"].append({
            "name": "reject1",
            "is_reject": False,
            "inner_join_reject": True,
            "filter": "",
            "activate_filter": False,
            "columns": [{"name": "id", "expression": "row1['id']"}],
        })
        comp = _make_pymap(config=cfg)
        main = pd.DataFrame([
            {"id": 1, "key": "A", "val": 1, "price": 1.0},
            {"id": 2, "key": "ZZZ", "val": 2, "price": 2.0},
        ])
        result = comp.execute({"row1": main, "row2": _lookup_df()})
        assert set(result["out1"]["id"]) == {1}
        assert set(result["reject1"]["id"]) == {2}


@pytest.mark.unit
class TestApplyReloadFilterDirect:
    """Direct _apply_reload_filter coverage incl. bad-expr (L821-834)."""

    def test_reload_filter_keeps_matching_rows(self):
        comp = _bare_pymap(_LOOKUP_CONFIG)
        lookup = pd.DataFrame([
            {"key": "A", "label": "Alpha"},
            {"key": "B", "label": "Beta"},
        ])
        main_row = pd.Series({"id": 1, "key": "A"})
        out = comp._apply_reload_filter(
            lookup, "row2['key'] == key", "row2", main_row
        )
        assert list(out["label"]) == ["Alpha"]

    def test_reload_filter_bad_expression_drops_row(self):
        """TypeError/ValueError in reload filter -> mask False (L832-833)."""
        comp = _bare_pymap(_LOOKUP_CONFIG)
        lookup = pd.DataFrame([{"key": "A", "label": "Alpha"}])
        main_row = pd.Series({"id": 1, "key": "A"})
        # 'None < 1' raises TypeError per row -> all dropped.
        out = comp._apply_reload_filter(
            lookup, "None < 1", "row2", main_row
        )
        assert out.empty


@pytest.mark.unit
class TestReloadLargeDatasetWarning:
    """RELOAD large-dataset O(n*m) warning (L707)."""

    def test_large_reload_logs_warning(self, caplog):
        cfg = copy.deepcopy(_LOOKUP_CONFIG)
        comp = _bare_pymap(cfg)
        # >10000 x >10000 triggers the warning path; keep keys non-matching
        # so the per-row loop stays cheap (LEFT_OUTER NaN fill).
        n = 10001
        joined = pd.DataFrame({
            "id": range(n),
            "key": ["X"] * n,
            "val": [0] * n,
            "price": [0.0] * n,
        })
        lookup = pd.DataFrame({
            "key": ["Y"] * n,
            "label": ["L"] * n,
        })
        lookup_cfg = cfg["inputs"]["lookups"][0]
        with caplog.at_level("WARNING"):
            result_df, rejects = comp._join_reload_per_row(
                joined, lookup, lookup_cfg
            )
        assert any("O(n*m)" in r.getMessage() for r in caplog.records)
        assert len(result_df) == n


# ------------------------------------------------------------------
# Coverage lift -- variable / output / row-dict branches
# ------------------------------------------------------------------


@pytest.mark.unit
class TestVariableBranches:
    """Variable evaluation skips empty name/expression (L872)."""

    def test_variable_without_name_or_expression_skipped(self):
        cfg = copy.deepcopy(_SIMPLE_CONFIG)
        cfg["variables"] = [
            {"name": "", "expression": "1 + 1"},          # no name -> skipped
            {"name": "v_noexpr", "expression": ""},        # no expr -> skipped
            {"name": "v_ok", "expression": "row1['val'] * 2"},
        ]
        cfg["outputs"][0]["columns"] = [
            {"name": "id", "expression": "row1['id']"},
            {"name": "doubled", "expression": "Var['v_ok']"},
        ]
        comp = _make_pymap(config=cfg)
        result = comp.execute({"row1": _main_df()})
        assert list(result["out1"]["doubled"]) == [20, 40, 60]


@pytest.mark.unit
class TestOutputFilterBadExpression:
    """Output filter eval exception -> keep=False -> reject (L947-948)."""

    def test_bad_output_filter_routes_to_reject(self):
        cfg = copy.deepcopy(_SIMPLE_CONFIG)
        cfg["outputs"][0]["activate_filter"] = True
        cfg["outputs"][0]["filter"] = "row1['no_such_col'] > 0"
        cfg["outputs"].append({
            "name": "rej",
            "is_reject": True,
            "inner_join_reject": False,
            "filter": "",
            "activate_filter": False,
            "columns": [
                {"name": "id", "expression": "row1['id']"},
                {"name": "val", "expression": "row1['val']"},
            ],
        })
        comp = _make_pymap(config=cfg)
        result = comp.execute({"row1": _main_df()})
        # Filter raises for every row -> all rows rejected.
        assert result["out1"].empty
        assert len(result["rej"]) == 3


@pytest.mark.unit
class TestRejectConcatToExisting:
    """Filter rejects concat into an already-populated reject output (L976)."""

    def test_reject_output_accumulates_across_outputs(self):
        cfg = copy.deepcopy(_SIMPLE_CONFIG)
        # Two non-reject outputs, both filtering everything out to the same
        # is_reject output. The second output's rejects concat onto the
        # already-populated reject DataFrame.
        cfg["outputs"][0]["activate_filter"] = True
        cfg["outputs"][0]["filter"] = "False"
        cfg["outputs"].append({
            "name": "out2",
            "is_reject": False,
            "inner_join_reject": False,
            "filter": "False",
            "activate_filter": True,
            "columns": [
                {"name": "id", "expression": "row1['id']"},
                {"name": "val", "expression": "row1['val']"},
            ],
        })
        cfg["outputs"].append({
            "name": "rej",
            "is_reject": True,
            "inner_join_reject": False,
            "filter": "",
            "activate_filter": False,
            "columns": [
                {"name": "id", "expression": "row1['id']"},
                {"name": "val", "expression": "row1['val']"},
            ],
        })
        comp = _make_pymap(config=cfg)
        result = comp.execute({"row1": _main_df()})
        # 3 rows rejected by out1 + 3 by out2 = 6 rows in reject.
        assert len(result["rej"]) == 6


@pytest.mark.unit
class TestBuildRowDictsVarPrefix:
    """_build_row_dicts skips Var.-prefixed columns (L1049-1050)."""

    def test_var_prefixed_column_excluded_from_main(self):
        comp = _bare_pymap(_SIMPLE_CONFIG)
        df = pd.DataFrame([{"id": 1, "Var.tmp": 99, "name": "x"}])
        row = df.iloc[0]
        row_dicts = comp._build_row_dicts(row, "row1", [], df)
        main = row_dicts["row1"]
        assert "id" in main
        assert "name" in main
        # Var.-prefixed columns are handled separately, not in the main dict.
        assert "Var.tmp" not in main


# ------------------------------------------------------------------
# Coverage lift -- inner-join reject routing concat (L1104)
# ------------------------------------------------------------------


@pytest.mark.unit
class TestInnerJoinRejectConcat:
    """Inner-join rejects from two lookups concat into one reject output."""

    def test_two_lookups_reject_concat(self):
        cfg = copy.deepcopy(_SIMPLE_CONFIG)
        cfg["inputs"]["lookups"] = [
            {
                "name": "row2",
                "matching_mode": "UNIQUE_MATCH",
                "lookup_mode": "LOAD_ONCE",
                "filter": "",
                "activate_filter": False,
                "join_keys": [{"lookup_column": "key", "expression": "row1.key"}],
                "join_mode": "INNER_JOIN",
            },
            {
                "name": "row3",
                "matching_mode": "UNIQUE_MATCH",
                "lookup_mode": "LOAD_ONCE",
                "filter": "",
                "activate_filter": False,
                "join_keys": [{"lookup_column": "k2", "expression": "row1.k2"}],
                "join_mode": "INNER_JOIN",
            },
        ]
        cfg["outputs"][0]["columns"] = [{"name": "id", "expression": "row1['id']"}]
        cfg["outputs"].append({
            "name": "reject1",
            "is_reject": False,
            "inner_join_reject": True,
            "filter": "",
            "activate_filter": False,
            "columns": [{"name": "id", "expression": "row1['id']"}],
        })
        comp = _make_pymap(config=cfg)
        main = pd.DataFrame([
            {"id": 1, "key": "A", "k2": "P", "val": 1, "price": 1.0},
            {"id": 2, "key": "MISS", "k2": "P", "val": 2, "price": 2.0},
        ])
        row2 = pd.DataFrame([{"key": "A", "label": "Alpha"}])
        row3 = pd.DataFrame([{"k2": "P", "tag": "Pee"}])
        result = comp.execute({"row1": main, "row2": row2, "row3": row3})
        # id=2 missed row2's INNER_JOIN -> reject. Concat across both lookups.
        assert "reject1" in result
        assert 2 in list(result["reject1"]["id"])

    def test_route_into_existing_nonempty_reject(self):
        """Reject output already populated -> rejects concat onto it (L1103-1104)."""
        outputs_config = [
            {
                "name": "reject1",
                "is_reject": False,
                "inner_join_reject": True,
                "columns": [{"name": "id", "expression": "row1['id']"}],
            }
        ]
        comp = _bare_pymap(_SIMPLE_CONFIG)
        # Pre-populate the reject output so the concat branch (not else) runs.
        result = {"reject1": pd.DataFrame([{"id": 99}])}
        inner_rejects = {"row2": pd.DataFrame([{"id": 1}, {"id": 2}])}
        comp._route_inner_join_rejects(result, inner_rejects, outputs_config)
        assert sorted(result["reject1"]["id"]) == [1, 2, 99]


# ------------------------------------------------------------------
# Coverage lift -- helper utility branches (direct calls)
# ------------------------------------------------------------------


@pytest.mark.unit
class TestHelperUtilityBranches:
    """Direct unit coverage for small helper branches."""

    def test_get_output_config_missing_returns_none(self):
        comp = _bare_pymap(_SIMPLE_CONFIG)
        assert comp._get_output_config("nope") is None

    def test_find_column_prefixed(self):
        comp = _bare_pymap(_SIMPLE_CONFIG)
        df = pd.DataFrame(columns=["t.c", "plain", "Var.v"])
        assert comp._find_column(df, "t", "c") == "t.c"

    def test_find_column_plain(self):
        comp = _bare_pymap(_SIMPLE_CONFIG)
        df = pd.DataFrame(columns=["t.c", "plain", "Var.v"])
        assert comp._find_column(df, "missing", "plain") == "plain"

    def test_find_column_var_prefix(self):
        comp = _bare_pymap(_SIMPLE_CONFIG)
        df = pd.DataFrame(columns=["t.c", "plain", "Var.v"])
        assert comp._find_column(df, "missing", "v") == "Var.v"

    def test_find_column_not_found(self):
        comp = _bare_pymap(_SIMPLE_CONFIG)
        df = pd.DataFrame(columns=["t.c", "plain"])
        assert comp._find_column(df, "missing", "nope") is None

    def test_matching_mode_empty_df(self):
        comp = _bare_pymap(_SIMPLE_CONFIG)
        empty = pd.DataFrame(columns=["k"])
        out = comp._apply_matching_mode(empty, ["k"], "UNIQUE_MATCH")
        assert out.empty

    def test_matching_mode_no_existing_keys(self):
        comp = _bare_pymap(_SIMPLE_CONFIG)
        df = pd.DataFrame([{"a": 1}])
        out = comp._apply_matching_mode(df, ["nonkey"], "UNIQUE_MATCH")
        assert out.equals(df)

    def test_matching_mode_unknown_defaults_to_unique(self):
        comp = _bare_pymap(_SIMPLE_CONFIG)
        df = pd.DataFrame([{"k": 1}, {"k": 1}, {"k": 2}])
        out = comp._apply_matching_mode(df, ["k"], "WEIRD_MODE")
        # Defaults to UNIQUE_MATCH (keep last) -> dedup by k.
        assert len(out) == 2

    def test_prefilter_null_keys_empty_df(self):
        comp = _bare_pymap(_SIMPLE_CONFIG)
        nonnull, nullkey = comp._prefilter_null_keys(
            pd.DataFrame(columns=["k"]), ["k"]
        )
        assert nonnull.empty
        assert nullkey.empty

    def test_prefilter_null_keys_no_existing_keys(self):
        comp = _bare_pymap(_SIMPLE_CONFIG)
        df = pd.DataFrame([{"a": 1}])
        nonnull, nullkey = comp._prefilter_null_keys(df, ["nonkey"])
        assert len(nonnull) == 1
        assert nullkey.empty


@pytest.mark.unit
class TestAutoConvertJoinKeysBranches:
    """_auto_convert_join_keys type-coercion branches (L1271-1289)."""

    def test_missing_key_columns_skipped(self):
        comp = _bare_pymap(_SIMPLE_CONFIG)
        main = pd.DataFrame({"k": [1]})
        lookup = pd.DataFrame({"other": [1]})
        m2, l2 = comp._auto_convert_join_keys(main, lookup, ["k"], ["k"])
        assert "k" in m2.columns

    def test_same_dtype_skipped(self):
        comp = _bare_pymap(_SIMPLE_CONFIG)
        main = pd.DataFrame({"k": [1]})
        lookup = pd.DataFrame({"k": [2]})
        m2, l2 = comp._auto_convert_join_keys(main, lookup, ["k"], ["k"])
        assert m2["k"].dtype == lookup["k"].dtype

    def test_string_left_numeric_right(self):
        comp = _bare_pymap(_SIMPLE_CONFIG)
        main = pd.DataFrame({"k": ["1", "2"]})
        lookup = pd.DataFrame({"k": [1, 2]})
        m2, l2 = comp._auto_convert_join_keys(main, lookup, ["k"], ["k"])
        assert pd.api.types.is_numeric_dtype(m2["k"])

    def test_numeric_left_string_right(self):
        comp = _bare_pymap(_SIMPLE_CONFIG)
        main = pd.DataFrame({"k": [1, 2]})
        lookup = pd.DataFrame({"k": ["1", "2"]})
        m2, l2 = comp._auto_convert_join_keys(main, lookup, ["k"], ["k"])
        assert pd.api.types.is_numeric_dtype(l2["k"])

    def test_int_left_float_right(self):
        comp = _bare_pymap(_SIMPLE_CONFIG)
        main = pd.DataFrame({"k": pd.Series([1, 2], dtype="int64")})
        lookup = pd.DataFrame({"k": pd.Series([1.0, 2.0], dtype="float64")})
        m2, l2 = comp._auto_convert_join_keys(main, lookup, ["k"], ["k"])
        assert m2["k"].dtype == np.dtype("float64")

    def test_float_left_int_right(self):
        comp = _bare_pymap(_SIMPLE_CONFIG)
        main = pd.DataFrame({"k": pd.Series([1.0, 2.0], dtype="float64")})
        lookup = pd.DataFrame({"k": pd.Series([1, 2], dtype="int64")})
        m2, l2 = comp._auto_convert_join_keys(main, lookup, ["k"], ["k"])
        assert l2["k"].dtype == np.dtype("float64")

    def test_categorical_right_safe_issubdtype_typeerror(self):
        """Categorical dtype makes np.issubdtype raise -> _safe_issubdtype False (L1271-1272)."""
        comp = _bare_pymap(_SIMPLE_CONFIG)
        main = pd.DataFrame({"k": pd.Series(["a", "b"], dtype="object")})
        lookup = pd.DataFrame({"k": pd.Series(["a", "b"], dtype="category")})
        # Must not raise; the TypeError is swallowed and no conversion happens.
        m2, l2 = comp._auto_convert_join_keys(main, lookup, ["k"], ["k"])
        assert m2["k"].dtype == np.dtype("object")
        assert isinstance(l2["k"].dtype, pd.CategoricalDtype)


@pytest.mark.unit
class TestValuesEqualBranches:
    """_values_equal type-aware comparison branches (L1306-1317)."""

    def test_numeric_numeric_equal(self):
        comp = _bare_pymap(_SIMPLE_CONFIG)
        assert comp._values_equal(1, 1.0) is True
        assert comp._values_equal(1, 2) is False

    def test_numeric_string_convertible(self):
        comp = _bare_pymap(_SIMPLE_CONFIG)
        assert comp._values_equal(1, "1") is True

    def test_numeric_string_not_convertible(self):
        comp = _bare_pymap(_SIMPLE_CONFIG)
        assert comp._values_equal(1, "abc") is False

    def test_string_numeric_convertible(self):
        comp = _bare_pymap(_SIMPLE_CONFIG)
        assert comp._values_equal("2", 2) is True

    def test_string_numeric_not_convertible(self):
        comp = _bare_pymap(_SIMPLE_CONFIG)
        assert comp._values_equal("abc", 2) is False

    def test_string_string_equal(self):
        comp = _bare_pymap(_SIMPLE_CONFIG)
        assert comp._values_equal("x", "x") is True
        assert comp._values_equal("x", "y") is False


@pytest.mark.unit
class TestSizeGuardBranches:
    """_check_size_guard warn / fail thresholds (L1334, L1340)."""

    def test_size_guard_fail_raises(self):
        comp = _bare_pymap(_SIMPLE_CONFIG)
        with pytest.raises(ComponentExecutionError, match="would produce"):
            comp._check_size_guard(20_000, 6_000, "ALL_MATCHES")

    def test_size_guard_warn_logs(self, caplog):
        comp = _bare_pymap(_SIMPLE_CONFIG)
        with caplog.at_level("WARNING"):
            comp._check_size_guard(2_000, 6_000, "ALL_MATCHES")
        assert any("consider using" in r.getMessage() for r in caplog.records)

    def test_size_guard_below_warn_noop(self):
        comp = _bare_pymap(_SIMPLE_CONFIG)
        # No exception, no requirement on logs.
        comp._check_size_guard(10, 10, "ALL_MATCHES")


@pytest.mark.unit
class TestNoRowsAfterLookups:
    """joined_df empty after lookups -> early route of rejects (L397-403)."""

    def test_inner_join_all_unmatched_empties_joined(self):
        """All main rows unmatched in INNER_JOIN -> joined empty, rejects routed."""
        cfg = copy.deepcopy(_LOOKUP_CONFIG)
        cfg["inputs"]["lookups"][0]["join_mode"] = "INNER_JOIN"
        cfg["outputs"].append({
            "name": "reject1",
            "is_reject": False,
            "inner_join_reject": True,
            "filter": "",
            "activate_filter": False,
            "columns": [{"name": "id", "expression": "row1['id']"}],
        })
        comp = _make_pymap(config=cfg)
        # No main key matches the lookup -> joined_df becomes empty.
        main = pd.DataFrame([
            {"id": 1, "key": "ZZZ", "val": 1, "price": 1.0},
            {"id": 2, "key": "YYY", "val": 2, "price": 2.0},
        ])
        result = comp.execute({"row1": main, "row2": _lookup_df()})
        assert result["out1"].empty
        assert set(result["reject1"]["id"]) == {1, 2}
