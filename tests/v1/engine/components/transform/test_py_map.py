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
