"""Tests for SampleRow (tSampleRow engine implementation)."""
import pytest
import pandas as pd

from src.v1.engine.components.transform.sample_row import SampleRow, _parse_range
from src.v1.engine.component_registry import REGISTRY
from src.v1.engine.context_manager import ContextManager
from src.v1.engine.exceptions import ConfigurationError
from src.v1.engine.global_map import GlobalMap


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

_DEFAULT_CONFIG = {
    "component_type": "tSampleRow",
    "range": "1,3",
}


def _make_component(config=None, global_map=None):
    """Create a SampleRow with test defaults."""
    gm = global_map if global_map is not None else GlobalMap()
    cm = ContextManager()
    return SampleRow(
        component_id="tSampleRow_1",
        config=config or dict(_DEFAULT_CONFIG),
        global_map=gm,
        context_manager=cm,
    )


def _make_input_df(rows=None):
    """Create a standard test input DataFrame (5 rows)."""
    if rows is None:
        rows = [
            {"id": 1, "name": "Alice"},
            {"id": 2, "name": "Bob"},
            {"id": 3, "name": "Charlie"},
            {"id": 4, "name": "Diana"},
            {"id": 5, "name": "Eve"},
        ]
    return pd.DataFrame(rows)


# ------------------------------------------------------------------
# TestRegistration
# ------------------------------------------------------------------


@pytest.mark.unit
class TestRegistration:
    """Both V1 and Talend alias are registered in REGISTRY."""

    def test_v1_name_registered(self):
        assert REGISTRY.get("SampleRow") is SampleRow

    def test_talend_alias_registered(self):
        assert REGISTRY.get("tSampleRow") is SampleRow

    def test_both_aliases_resolve_same_class(self):
        assert REGISTRY.get("SampleRow") is REGISTRY.get("tSampleRow")


# ------------------------------------------------------------------
# TestRangeParser (unit tests for _parse_range helper)
# ------------------------------------------------------------------


@pytest.mark.unit
class TestRangeParser:
    """_parse_range produces correct index sets for all format variants."""

    def test_single_index(self):
        assert _parse_range("1", "c") == {1}

    def test_multiple_indices(self):
        assert _parse_range("1,3,5", "c") == {1, 3, 5}

    def test_inclusive_range(self):
        assert _parse_range("2..5", "c") == {2, 3, 4, 5}

    def test_mixed_indices_and_range(self):
        assert _parse_range("1,5,10..12", "c") == {1, 5, 10, 11, 12}

    def test_default_range_spec(self):
        result = _parse_range("1,5,10..20", "c")
        assert 1 in result
        assert 5 in result
        assert 10 in result
        assert 20 in result
        assert len(result) == 13  # 1, 5, 10-20 (11 values)

    def test_single_element_range(self):
        assert _parse_range("3..3", "c") == {3}

    def test_whitespace_around_parts(self):
        assert _parse_range(" 1 , 3 , 5 ", "c") == {1, 3, 5}

    def test_whitespace_in_range(self):
        assert _parse_range("1 .. 3", "c") == {1, 2, 3}

    def test_invalid_non_integer_raises(self):
        with pytest.raises(ConfigurationError, match="Non-integer"):
            _parse_range("abc", "c")

    def test_invalid_range_non_integer_bound_raises(self):
        with pytest.raises(ConfigurationError, match="Non-integer"):
            _parse_range("1..abc", "c")

    def test_range_start_greater_than_end_raises(self):
        with pytest.raises(ConfigurationError, match="start .* > end"):
            _parse_range("5..3", "c")

    def test_zero_index_raises(self):
        with pytest.raises(ConfigurationError, match=">= 1"):
            _parse_range("0", "c")

    def test_negative_index_raises(self):
        with pytest.raises(ConfigurationError, match=">= 1"):
            _parse_range("-1", "c")

    def test_range_start_zero_raises(self):
        with pytest.raises(ConfigurationError, match=">= 1"):
            _parse_range("0..5", "c")


# ------------------------------------------------------------------
# TestValidation
# ------------------------------------------------------------------


@pytest.mark.unit
class TestValidation:
    """_validate_config raises ConfigurationError for missing/invalid range."""

    def test_missing_range_raises(self):
        config = {"component_type": "tSampleRow"}
        comp = _make_component(config=config)
        with pytest.raises(ConfigurationError, match="range"):
            comp.execute(_make_input_df())

    def test_range_not_string_raises(self):
        config = {**_DEFAULT_CONFIG, "range": 5}
        comp = _make_component(config=config)
        with pytest.raises(ConfigurationError, match="range"):
            comp.execute(_make_input_df())

    def test_empty_range_string_raises(self):
        config = {**_DEFAULT_CONFIG, "range": "   "}
        comp = _make_component(config=config)
        with pytest.raises(ConfigurationError, match="range"):
            comp.execute(_make_input_df())

    def test_invalid_range_syntax_raises(self):
        config = {**_DEFAULT_CONFIG, "range": "abc"}
        comp = _make_component(config=config)
        with pytest.raises(ConfigurationError):
            comp.execute(_make_input_df())

    def test_valid_config_does_not_raise(self):
        comp = _make_component()
        result = comp.execute(_make_input_df())
        assert result["main"] is not None


# ------------------------------------------------------------------
# TestMainFlow
# ------------------------------------------------------------------


@pytest.mark.unit
class TestMainFlow:
    """Core row selection behavior."""

    def test_single_index_selects_correct_row(self):
        config = {**_DEFAULT_CONFIG, "range": "2"}
        comp = _make_component(config=config)
        result = comp.execute(_make_input_df())
        assert len(result["main"]) == 1
        assert result["main"].iloc[0]["name"] == "Bob"

    def test_multiple_indices_select_correct_rows(self):
        config = {**_DEFAULT_CONFIG, "range": "1,3,5"}
        comp = _make_component(config=config)
        result = comp.execute(_make_input_df())
        assert len(result["main"]) == 3
        assert list(result["main"]["name"]) == ["Alice", "Charlie", "Eve"]

    def test_range_notation_selects_correct_rows(self):
        config = {**_DEFAULT_CONFIG, "range": "2..4"}
        comp = _make_component(config=config)
        result = comp.execute(_make_input_df())
        assert len(result["main"]) == 3
        assert list(result["main"]["name"]) == ["Bob", "Charlie", "Diana"]

    def test_mixed_notation(self):
        config = {**_DEFAULT_CONFIG, "range": "1,3..4"}
        comp = _make_component(config=config)
        result = comp.execute(_make_input_df())
        assert len(result["main"]) == 3
        assert list(result["main"]["name"]) == ["Alice", "Charlie", "Diana"]

    def test_output_preserves_original_row_order(self):
        """Selected rows must appear in their original DataFrame order."""
        config = {**_DEFAULT_CONFIG, "range": "5,1,3"}
        comp = _make_component(config=config)
        result = comp.execute(_make_input_df())
        # Original order: 1, 3, 5 regardless of spec order
        assert list(result["main"]["id"]) == [1, 3, 5]

    def test_main_columns_match_input(self):
        comp = _make_component()
        df = _make_input_df()
        result = comp.execute(df)
        assert list(result["main"].columns) == list(df.columns)


# ------------------------------------------------------------------
# TestRejectFlow
# ------------------------------------------------------------------


@pytest.mark.unit
class TestRejectFlow:
    """Reject output contains non-selected rows."""

    def test_reject_contains_unselected_rows(self):
        config = {**_DEFAULT_CONFIG, "range": "1"}
        comp = _make_component(config=config)
        result = comp.execute(_make_input_df())
        assert len(result["reject"]) == 4
        assert "Bob" in list(result["reject"]["name"])

    def test_main_plus_reject_equals_input(self):
        config = {**_DEFAULT_CONFIG, "range": "1,3"}
        comp = _make_component(config=config)
        df = _make_input_df()
        result = comp.execute(df)
        assert len(result["main"]) + len(result["reject"]) == len(df)

    def test_all_rows_selected_reject_is_empty(self):
        config = {**_DEFAULT_CONFIG, "range": "1..5"}
        comp = _make_component(config=config)
        result = comp.execute(_make_input_df())
        assert len(result["main"]) == 5
        assert result["reject"].empty

    def test_no_rows_selected_main_is_empty(self):
        """Index beyond length is silently ignored; all rows go to reject."""
        config = {**_DEFAULT_CONFIG, "range": "99"}
        comp = _make_component(config=config)
        result = comp.execute(_make_input_df())
        assert result["main"].empty
        assert len(result["reject"]) == 5

    def test_reject_preserves_original_row_order(self):
        config = {**_DEFAULT_CONFIG, "range": "1"}
        comp = _make_component(config=config)
        result = comp.execute(_make_input_df())
        assert list(result["reject"]["id"]) == [2, 3, 4, 5]


# ------------------------------------------------------------------
# TestEdgeCases
# ------------------------------------------------------------------


@pytest.mark.unit
class TestEdgeCases:
    """None input, empty DataFrame, single row, out-of-range indices."""

    def test_none_input_returns_empty_main_and_reject(self):
        comp = _make_component()
        result = comp.execute(None)
        assert result["main"].empty
        assert result["reject"].empty

    def test_empty_dataframe_returns_empty_main_and_reject(self):
        comp = _make_component()
        result = comp.execute(pd.DataFrame())
        assert result["main"].empty
        assert result["reject"].empty

    def test_single_row_selected(self):
        config = {**_DEFAULT_CONFIG, "range": "1"}
        comp = _make_component(config=config)
        df = _make_input_df([{"id": 99, "name": "only"}])
        result = comp.execute(df)
        assert len(result["main"]) == 1

    def test_out_of_range_indices_silently_ignored(self):
        config = {**_DEFAULT_CONFIG, "range": "1,100,200"}
        comp = _make_component(config=config)
        df = _make_input_df()  # 5 rows
        result = comp.execute(df)
        # Only row 1 is valid; 100 and 200 are silently dropped
        assert len(result["main"]) == 1

    def test_partial_overlap_with_out_of_range(self):
        config = {**_DEFAULT_CONFIG, "range": "3..10"}
        comp = _make_component(config=config)
        df = _make_input_df()  # 5 rows
        result = comp.execute(df)
        # Rows 3,4,5 are valid; 6-10 are out of range
        assert len(result["main"]) == 3

    def test_large_input(self):
        config = {**_DEFAULT_CONFIG, "range": "1..500"}
        comp = _make_component(config=config)
        rows = [{"id": i, "name": f"user_{i}"} for i in range(1, 1001)]
        df = pd.DataFrame(rows)
        result = comp.execute(df)
        assert len(result["main"]) == 500
        assert len(result["reject"]) == 500

    def test_default_range_spec(self):
        """Default '1,5,10..20' works correctly on a 25-row DataFrame."""
        config = {**_DEFAULT_CONFIG, "range": "1,5,10..20"}
        comp = _make_component(config=config)
        rows = [{"id": i} for i in range(1, 26)]
        df = pd.DataFrame(rows)
        result = comp.execute(df)
        assert len(result["main"]) == 13  # 1, 5, 10-20


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
        assert gm.get_component_stat("tSampleRow_1", "NB_LINE") == len(df)

    def test_nb_line_ok_equals_selected_row_count(self):
        gm = GlobalMap()
        config = {**_DEFAULT_CONFIG, "range": "1,3"}
        comp = _make_component(config=config, global_map=gm)
        comp.execute(_make_input_df())
        assert gm.get_component_stat("tSampleRow_1", "NB_LINE_OK") == 2

    def test_nb_line_reject_equals_unselected_row_count(self):
        gm = GlobalMap()
        config = {**_DEFAULT_CONFIG, "range": "1,3"}
        comp = _make_component(config=config, global_map=gm)
        comp.execute(_make_input_df())
        assert gm.get_component_stat("tSampleRow_1", "NB_LINE_REJECT") == 3

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
        assert len(result1["reject"]) == len(result2["reject"])

    def test_config_not_mutated_across_executions(self):
        comp = _make_component()
        df = _make_input_df()
        comp.execute(df)
        snapshot = comp._original_config.copy()
        comp.reset()
        comp.execute(df)
        assert comp._original_config == snapshot
