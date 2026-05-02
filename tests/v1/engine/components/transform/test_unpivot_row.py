"""Tests for UnpivotRow (tUnpivotRow engine implementation).

Coverage classes:
  TestRegistration  -- @REGISTRY.register active; class hierarchy
  TestValidation    -- _validate_config raises ConfigurationError; returns None
  TestTalendParity  -- Talend behavioral contract (output columns, str coercion, etc.)
  TestEdgeCases     -- empty input, all-row_keys, die_on_error=False
  TestStatistics    -- NB_LINE / NB_LINE_OK / NB_LINE_REJECT GlobalMap values
"""
import copy

import pytest
import pandas as pd

from src.v1.engine.components.transform.unpivot_row import UnpivotRow
from src.v1.engine.component_registry import REGISTRY
from src.v1.engine.base_component import BaseComponent
from src.v1.engine.global_map import GlobalMap
from src.v1.engine.context_manager import ContextManager
from src.v1.engine.exceptions import ConfigurationError


# ------------------------------------------------------------------
# Fixtures / helpers
# ------------------------------------------------------------------

_DEFAULT_CONFIG = {
    "component_type": "UnpivotRow",
    "row_keys": ["id", "name"],
    "pivot_key": "pivot_key",
    "pivot_value": "pivot_value",
    "include_empty_values": True,
}


def _make_component(config=None, global_map=None, context_manager=None):
    """Create an UnpivotRow component with test defaults."""
    gm = global_map or GlobalMap()
    cm = context_manager or ContextManager()
    return UnpivotRow(
        component_id="tUnpivotRow_1",
        config=config or copy.deepcopy(_DEFAULT_CONFIG),
        global_map=gm,
        context_manager=cm,
    )


def _wide_df():
    """3-value-column wide input: id, name, jan, feb, mar."""
    return pd.DataFrame({
        "id":   [1, 2],
        "name": ["Alice", "Bob"],
        "jan":  [100, 200],
        "feb":  [150, 250],
        "mar":  [120, 180],
    })


# ------------------------------------------------------------------
# TestRegistration
# ------------------------------------------------------------------

@pytest.mark.unit
class TestRegistration:
    """Component is registered under both V1 and Talend names."""

    def test_registered_v1_name(self):
        assert REGISTRY.get("UnpivotRow") is UnpivotRow

    def test_registered_talend_name(self):
        assert REGISTRY.get("tUnpivotRow") is UnpivotRow

    def test_extends_base_component(self):
        assert issubclass(UnpivotRow, BaseComponent)


# ------------------------------------------------------------------
# TestValidation
# ------------------------------------------------------------------

@pytest.mark.unit
class TestValidation:
    """_validate_config raises ConfigurationError for invalid config."""

    def test_missing_row_keys_raises(self):
        """Missing row_keys key -> ConfigurationError on execute."""
        config = copy.deepcopy(_DEFAULT_CONFIG)
        del config["row_keys"]
        comp = _make_component(config=config)
        with pytest.raises(ConfigurationError, match="row_keys"):
            comp.execute(_wide_df())

    def test_row_keys_not_list_raises(self):
        """row_keys='id' (string, not list) -> ConfigurationError."""
        config = copy.deepcopy(_DEFAULT_CONFIG)
        config["row_keys"] = "id"
        comp = _make_component(config=config)
        with pytest.raises(ConfigurationError, match="row_keys"):
            comp.execute(_wide_df())

    def test_validate_config_returns_none(self):
        """BaseComponent ABC contract: _validate_config() must return None (not a list)."""
        comp = _make_component()
        comp.config = copy.deepcopy(comp._original_config)
        result = comp._validate_config()
        assert result is None, (
            f"_validate_config() must return None (raises on error), "
            f"got {type(result)}: {result!r}"
        )

    def test_empty_row_keys_raises(self):
        """row_keys=[] -> ConfigurationError (deferred content check in _process)."""
        config = copy.deepcopy(_DEFAULT_CONFIG)
        config["row_keys"] = []
        comp = _make_component(config=config)
        with pytest.raises(ConfigurationError, match="row_keys"):
            comp.execute(_wide_df())

    def test_missing_row_key_column_raises(self):
        """row_keys column absent from input DataFrame -> ConfigurationError."""
        config = copy.deepcopy(_DEFAULT_CONFIG)
        config["row_keys"] = ["id", "nonexistent"]
        comp = _make_component(config=config)
        with pytest.raises(ConfigurationError, match="row_keys columns not found"):
            comp.execute(_wide_df())


# ------------------------------------------------------------------
# TestTalendParity
# ------------------------------------------------------------------

@pytest.mark.unit
class TestTalendParity:
    """Talend tUnpivotRow behavioral contract tests."""

    def test_basic_unpivot_output_columns(self):
        """ENG-UPR-001 fix: output contains only row_keys + pivot_key + pivot_value."""
        comp = _make_component()
        result = comp.execute(_wide_df())
        out = result["main"]
        assert list(out.columns) == ["id", "name", "pivot_key", "pivot_value"]

    def test_no_schema_pollution(self):
        """ENG-UPR-001 fix: original value columns must NOT appear in output."""
        comp = _make_component()
        result = comp.execute(_wide_df())
        out = result["main"]
        for col in ["jan", "feb", "mar"]:
            assert col not in out.columns, f"Column '{col}' must not be in output"

    def test_basic_unpivot_row_count(self):
        """2 input rows x 3 value columns = 6 output rows."""
        comp = _make_component()
        result = comp.execute(_wide_df())
        assert len(result["main"]) == 6

    def test_pivot_key_contains_column_names(self):
        """pivot_key column contains the original column names."""
        comp = _make_component()
        result = comp.execute(_wide_df())
        assert set(result["main"]["pivot_key"]) == {"jan", "feb", "mar"}

    def test_pivot_value_string_coercion(self):
        """ENG-UPR-002 fix: all non-null pivot_value cells are coerced to str."""
        comp = _make_component()
        result = comp.execute(_wide_df())
        notnull = result["main"]["pivot_value"].dropna()
        bad = [v for v in notnull if not isinstance(v, str)]
        assert not bad, f"Expected all str, got non-str values: {bad}"

    def test_row_key_values_replicated(self):
        """Each original row's key values appear once per value column."""
        comp = _make_component()
        result = comp.execute(_wide_df())
        alice_rows = result["main"][result["main"]["name"] == "Alice"]
        assert len(alice_rows) == 3  # jan, feb, mar

    def test_include_empty_values_false_drops_nulls(self):
        """ENG-UPR-002 + include_empty_values=False drops null pivot_value rows."""
        df = pd.DataFrame({
            "id": [1],
            "name": ["Alice"],
            "jan": [100],
            "feb": [None],
            "mar": [120],
        })
        config = copy.deepcopy(_DEFAULT_CONFIG)
        config["include_empty_values"] = False
        comp = _make_component(config=config)
        result = comp.execute(df)
        out = result["main"]
        assert len(out) == 2  # feb dropped
        assert "feb" not in out["pivot_key"].values

    def test_include_empty_values_true_keeps_nulls(self):
        """include_empty_values=True (default) preserves null pivot_value rows."""
        df = pd.DataFrame({
            "id": [1],
            "name": ["Alice"],
            "jan": [100],
            "feb": [None],
        })
        comp = _make_component()  # include_empty_values=True
        result = comp.execute(df)
        assert len(result["main"]) == 2  # both jan and feb present

    def test_custom_pivot_column_names(self):
        """Custom pivot_key and pivot_value names appear in output."""
        config = copy.deepcopy(_DEFAULT_CONFIG)
        config["pivot_key"] = "attribute"
        config["pivot_value"] = "amount"
        comp = _make_component(config=config)
        result = comp.execute(_wide_df())
        out = result["main"]
        assert "attribute" in out.columns
        assert "amount" in out.columns
        assert "pivot_key" not in out.columns
        assert "pivot_value" not in out.columns

    def test_return_has_reject_key(self):
        """ENG-UPR-004 fix: return dict contains 'reject' key (Rule 3 compliance)."""
        comp = _make_component()
        result = comp.execute(_wide_df())
        assert "reject" in result


# ------------------------------------------------------------------
# TestEdgeCases
# ------------------------------------------------------------------

@pytest.mark.unit
class TestEdgeCases:
    """Edge case and error path tests."""

    def test_none_input_returns_empty(self):
        """None input returns empty DataFrame without error."""
        comp = _make_component()
        result = comp.execute(None)
        assert isinstance(result["main"], pd.DataFrame)
        assert len(result["main"]) == 0

    def test_empty_dataframe_returns_empty(self):
        """Empty DataFrame input returns empty DataFrame."""
        comp = _make_component()
        result = comp.execute(pd.DataFrame())
        assert isinstance(result["main"], pd.DataFrame)
        assert len(result["main"]) == 0

    def test_all_columns_as_row_keys_returns_empty_with_schema(self):
        """When all columns are row_keys, nothing to melt — empty output with pivot columns."""
        config = copy.deepcopy(_DEFAULT_CONFIG)
        config["row_keys"] = ["id", "name", "jan", "feb", "mar"]
        comp = _make_component(config=config)
        result = comp.execute(_wide_df())
        out = result["main"]
        assert len(out) == 0
        assert "pivot_key" in out.columns
        assert "pivot_value" in out.columns

    def test_die_on_error_false_missing_column_returns_empty(self):
        """ENG-UPR-003 fix: die_on_error=False returns empty instead of raising."""
        config = copy.deepcopy(_DEFAULT_CONFIG)
        config["row_keys"] = ["id", "missing_col"]
        config["die_on_error"] = False
        comp = _make_component(config=config)
        result = comp.execute(_wide_df())
        assert isinstance(result["main"], pd.DataFrame)
        assert len(result["main"]) == 0

    def test_die_on_error_false_empty_row_keys_returns_empty(self):
        """die_on_error=False with empty row_keys returns empty instead of raising."""
        config = copy.deepcopy(_DEFAULT_CONFIG)
        config["row_keys"] = []
        config["die_on_error"] = False
        comp = _make_component(config=config)
        result = comp.execute(_wide_df())
        assert isinstance(result["main"], pd.DataFrame)
        assert len(result["main"]) == 0

    def test_single_row_key_single_value_column(self):
        """Minimal: 1 row_key + 1 value column -> 1 output row per input row."""
        config = copy.deepcopy(_DEFAULT_CONFIG)
        config["row_keys"] = ["id"]
        comp = _make_component(config=config)
        df = pd.DataFrame({"id": [1, 2, 3], "val": [10, 20, 30]})
        result = comp.execute(df)
        out = result["main"]
        assert len(out) == 3
        assert list(out.columns) == ["id", "pivot_key", "pivot_value"]
        assert list(out["pivot_key"]) == ["val", "val", "val"]
        # Values coerced to string
        assert list(out["pivot_value"]) == ["10", "20", "30"]

    def test_original_order_column_collision_safe(self):
        """Input column named '_original_order' does not cause errors (ENG-UPR-007 fix)."""
        config = copy.deepcopy(_DEFAULT_CONFIG)
        config["row_keys"] = ["id"]
        comp = _make_component(config=config)
        df = pd.DataFrame({"id": [1], "_original_order": [99], "val": [42]})
        result = comp.execute(df)
        out = result["main"]
        # _original_order should be unpivoted as a value column, not corrupt output
        assert "pivot_key" in out.columns
        assert "pivot_value" in out.columns
        assert "_original_order" not in out.columns or out.columns.tolist() == ["id", "pivot_key", "pivot_value"]


# ------------------------------------------------------------------
# TestStatistics
# ------------------------------------------------------------------

@pytest.mark.unit
class TestStatistics:
    """GlobalMap NB_LINE statistics are set correctly."""

    def test_nb_line_is_input_row_count(self):
        """NB_LINE = number of input rows."""
        gm = GlobalMap()
        comp = _make_component(global_map=gm)
        comp.execute(_wide_df())
        assert gm.get_nb_line("tUnpivotRow_1") == 2

    def test_nb_line_ok_is_output_row_count(self):
        """NB_LINE_OK = input_rows * unpivot_column_count."""
        gm = GlobalMap()
        comp = _make_component(global_map=gm)
        comp.execute(_wide_df())
        # 2 rows * 3 value cols = 6
        assert gm.get_nb_line_ok("tUnpivotRow_1") == 6

    def test_nb_line_reject_always_zero(self):
        """NB_LINE_REJECT = 0 (no reject flow for this component)."""
        gm = GlobalMap()
        comp = _make_component(global_map=gm)
        comp.execute(_wide_df())
        assert gm.get_nb_line_reject("tUnpivotRow_1") == 0

    def test_empty_input_stats_all_zero(self):
        """Empty input -> all stats are 0."""
        gm = GlobalMap()
        comp = _make_component(global_map=gm)
        comp.execute(None)
        assert gm.get_nb_line("tUnpivotRow_1") == 0
        assert gm.get_nb_line_ok("tUnpivotRow_1") == 0
        assert gm.get_nb_line_reject("tUnpivotRow_1") == 0
