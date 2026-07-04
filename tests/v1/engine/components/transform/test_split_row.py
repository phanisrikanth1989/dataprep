"""Tests for SplitRow (tSplitRow) engine component."""
import pytest
import pandas as pd

from src.v1.engine.components.transform.split_row import SplitRow, _resolve_expression
from src.v1.engine.component_registry import REGISTRY
from src.v1.engine.global_map import GlobalMap
from src.v1.engine.context_manager import ContextManager
from src.v1.engine.base_component import BaseComponent
from src.v1.engine.exceptions import ConfigurationError


# ------------------------------------------------------------------
# Fixtures / helpers
# ------------------------------------------------------------------

# Default config mirrors a real tSplitRow unpivot job:
# Input columns: id, name, Jan, Feb, Mar
# Output columns: id, name, Month, amount
# 3 groups -> 3 output rows per input row
_DEFAULT_CONFIG = {
    "col_mapping": [
        {"id": "row1.id", "name": "row1.name", "Month": '"Jan"', "amount": "row1.Jan"},
        {"id": "row1.id", "name": "row1.name", "Month": '"Feb"', "amount": "row1.Feb"},
        {"id": "row1.id", "name": "row1.name", "Month": '"Mar"', "amount": "row1.Mar"},
    ],
    "tstatcatcher_stats": False,
    "label": "",
}


def _make_input_df(rows=None):
    if rows is None:
        rows = [
            {"id": 1, "name": "Alice", "Jan": 100, "Feb": 200, "Mar": 150},
            {"id": 2, "name": "Bob",   "Jan": 300, "Feb": 400, "Mar": 250},
        ]
    return pd.DataFrame(rows)


def _make_component(config=None, global_map=None):
    cfg = config if config is not None else _DEFAULT_CONFIG.copy()
    gm = global_map if global_map is not None else GlobalMap()
    return SplitRow(
        component_id="tSplitRow_1",
        config=cfg,
        global_map=gm,
        context_manager=ContextManager(),
    )


# ------------------------------------------------------------------
# TestRegistration
# ------------------------------------------------------------------


@pytest.mark.unit
class TestRegistration:
    """Component is registered under both V1 and Talend aliases."""

    def test_registered_under_v1_name(self):
        assert REGISTRY.get("SplitRow") is SplitRow

    def test_registered_under_talend_name(self):
        assert REGISTRY.get("tSplitRow") is SplitRow

    def test_instance_is_base_component(self):
        comp = _make_component()
        assert isinstance(comp, BaseComponent)


# ------------------------------------------------------------------
# TestExpressionResolver
# ------------------------------------------------------------------


@pytest.mark.unit
class TestExpressionResolver:
    """_resolve_expression() handles all expression types."""

    _row = {"id": 1, "name": "Alice", "Jan": 100}
    _cols = {"id", "name", "Jan"}

    def test_flow_column_reference(self):
        """row1.id -> input row value for 'id'."""
        assert _resolve_expression("row1.id", self._row, self._cols) == 1

    def test_flow_column_reference_string(self):
        assert _resolve_expression("row1.name", self._row, self._cols) == "Alice"

    def test_flow_column_arbitrary_prefix(self):
        """Any flow prefix (row1, row2, input) is stripped."""
        assert _resolve_expression("input.Jan", self._row, self._cols) == 100

    def test_double_quoted_literal(self):
        assert _resolve_expression('"Jan"', self._row, self._cols) == "Jan"

    def test_single_quoted_literal(self):
        assert _resolve_expression("'Feb'", self._row, self._cols) == "Feb"

    def test_integer_literal(self):
        assert _resolve_expression("42", self._row, self._cols) == 42

    def test_float_literal(self):
        assert _resolve_expression("3.14", self._row, self._cols) == pytest.approx(3.14)

    def test_unknown_column_returns_expr_as_is(self):
        """flow.unknownCol is returned as-is when col not in input."""
        result = _resolve_expression("row1.nonexistent", self._row, self._cols)
        assert result == "row1.nonexistent"

    def test_empty_string_returns_as_is(self):
        assert _resolve_expression("", self._row, self._cols) == ""


# ------------------------------------------------------------------
# TestValidation
# ------------------------------------------------------------------


@pytest.mark.unit
class TestValidation:
    """_validate_config() rejects bad configs."""

    def test_missing_col_mapping_raises(self):
        config = {"tstatcatcher_stats": False, "label": ""}
        comp = _make_component(config=config)
        with pytest.raises(ConfigurationError, match="col_mapping"):
            comp.execute(_make_input_df())

    def test_col_mapping_not_list_raises(self):
        config = {**_DEFAULT_CONFIG, "col_mapping": "not_a_list"}
        comp = _make_component(config=config)
        with pytest.raises(ConfigurationError, match="must be a list"):
            comp.execute(_make_input_df())

    def test_col_mapping_entry_not_dict_raises(self):
        config = {**_DEFAULT_CONFIG, "col_mapping": ["not_a_dict"]}
        comp = _make_component(config=config)
        with pytest.raises(ConfigurationError, match="must be a dict"):
            comp.execute(_make_input_df())

    def test_valid_config_does_not_raise(self):
        comp = _make_component()
        result = comp.execute(_make_input_df())
        assert result["main"] is not None


# ------------------------------------------------------------------
# TestRowExpansion
# ------------------------------------------------------------------


@pytest.mark.unit
class TestRowExpansion:
    """Core row-expansion semantics."""

    def test_one_input_row_produces_n_output_rows(self):
        """1 input row x 3 groups = 3 output rows."""
        df = _make_input_df([{"id": 1, "name": "Alice", "Jan": 100, "Feb": 200, "Mar": 150}])
        comp = _make_component()
        result = comp.execute(df)
        assert len(result["main"]) == 3

    def test_two_input_rows_produces_2n_output_rows(self):
        """2 input rows x 3 groups = 6 output rows."""
        comp = _make_component()
        result = comp.execute(_make_input_df())
        assert len(result["main"]) == 6

    def test_output_columns_match_group_keys(self):
        """Output columns = target column names from the mapping group."""
        comp = _make_component()
        result = comp.execute(_make_input_df())
        assert set(result["main"].columns) == {"id", "name", "Month", "amount"}

    def test_quoted_literal_resolved_correctly(self):
        """Month column should contain literal strings "Jan", "Feb", "Mar"."""
        comp = _make_component()
        df = _make_input_df([{"id": 1, "name": "Alice", "Jan": 100, "Feb": 200, "Mar": 150}])
        result = comp.execute(df)
        assert list(result["main"]["Month"]) == ["Jan", "Feb", "Mar"]

    def test_column_reference_resolved_correctly(self):
        """amount column should contain values from Jan, Feb, Mar columns."""
        comp = _make_component()
        df = _make_input_df([{"id": 1, "name": "Alice", "Jan": 100, "Feb": 200, "Mar": 150}])
        result = comp.execute(df)
        assert list(result["main"]["amount"]) == [100, 200, 150]

    def test_id_repeated_per_group(self):
        """id and name should be repeated once per group for each input row."""
        comp = _make_component()
        df = _make_input_df([{"id": 99, "name": "Zoe", "Jan": 1, "Feb": 2, "Mar": 3}])
        result = comp.execute(df)
        assert list(result["main"]["id"]) == [99, 99, 99]
        assert list(result["main"]["name"]) == ["Zoe", "Zoe", "Zoe"]

    def test_row_order_groups_then_rows(self):
        """Output order: all groups for row1, then all groups for row2."""
        comp = _make_component()
        result = comp.execute(_make_input_df())
        # First 3 rows belong to Alice (id=1), next 3 to Bob (id=2)
        assert list(result["main"]["id"].iloc[:3]) == [1, 1, 1]
        assert list(result["main"]["id"].iloc[3:]) == [2, 2, 2]


# ------------------------------------------------------------------
# TestEdgeCases
# ------------------------------------------------------------------


@pytest.mark.unit
class TestEdgeCases:
    """None input, empty DataFrame, empty mapping."""

    def test_none_input_returns_empty_main(self):
        comp = _make_component()
        result = comp.execute(None)
        assert result["main"].empty

    def test_empty_dataframe_returns_empty_main(self):
        comp = _make_component()
        result = comp.execute(pd.DataFrame())
        assert result["main"].empty

    def test_empty_col_mapping_returns_empty_dataframe(self):
        config = {**_DEFAULT_CONFIG, "col_mapping": []}
        comp = _make_component(config=config)
        result = comp.execute(_make_input_df())
        assert result["main"].empty

    def test_single_group_single_row(self):
        config = {**_DEFAULT_CONFIG, "col_mapping": [
            {"Month": '"Only"', "amount": "row1.Jan"},
        ]}
        comp = _make_component(config=config)
        df = _make_input_df([{"id": 1, "name": "X", "Jan": 99, "Feb": 0, "Mar": 0}])
        result = comp.execute(df)
        assert len(result["main"]) == 1
        assert result["main"]["Month"].iloc[0] == "Only"

    def test_reject_is_none(self):
        comp = _make_component()
        result = comp.execute(_make_input_df())
        assert result["reject"] is None

    def test_large_input(self):
        """100 input rows x 3 groups = 300 output rows."""
        comp = _make_component()
        rows = [{"id": i, "name": f"u{i}", "Jan": i, "Feb": i * 2, "Mar": i * 3}
                for i in range(1, 101)]
        df = pd.DataFrame(rows)
        result = comp.execute(df)
        assert len(result["main"]) == 300


# ------------------------------------------------------------------
# TestGlobalMapVariables
# ------------------------------------------------------------------


@pytest.mark.unit
class TestGlobalMapVariables:
    """Stats pushed to GlobalMap correctly after execute()."""

    def test_nb_line_equals_input_row_count(self):
        gm = GlobalMap()
        comp = _make_component(global_map=gm)
        df = _make_input_df()
        comp.execute(df)
        assert gm.get_component_stat("tSplitRow_1", "NB_LINE") == len(df)

    def test_nb_line_ok_equals_output_row_count(self):
        gm = GlobalMap()
        comp = _make_component(global_map=gm)
        df = _make_input_df()  # 2 rows x 3 groups = 6 output rows
        comp.execute(df)
        assert gm.get_component_stat("tSplitRow_1", "NB_LINE_OK") == 6

    def test_nb_line_reject_is_zero(self):
        gm = GlobalMap()
        comp = _make_component(global_map=gm)
        comp.execute(_make_input_df())
        assert gm.get_component_stat("tSplitRow_1", "NB_LINE_REJECT") == 0

    def test_works_without_global_map(self):
        comp = _make_component(global_map=None)
        comp.global_map = None
        result = comp.execute(_make_input_df())
        assert result["main"] is not None


# ------------------------------------------------------------------
# TestIterateReexecution
# ------------------------------------------------------------------


@pytest.mark.unit
class TestIterateReexecution:
    """execute() + reset() + execute() gives consistent results."""

    def test_second_execute_produces_correct_results(self):
        comp = _make_component()
        df = _make_input_df()
        result1 = comp.execute(df)
        comp.reset()
        result2 = comp.execute(df)
        assert len(result1["main"]) == len(result2["main"])
        assert list(result1["main"].columns) == list(result2["main"].columns)

    def test_config_not_mutated_across_executions(self):
        comp = _make_component()
        df = _make_input_df()
        comp.execute(df)
        snapshot = comp._original_config.copy()
        comp.reset()
        comp.execute(df)
        assert comp._original_config == snapshot
