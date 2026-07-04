"""Tests for Replicate (tReplicate engine implementation)."""
import pytest
import pandas as pd

from src.v1.engine.components.transform.replicate import Replicate
from src.v1.engine.component_registry import REGISTRY
from src.v1.engine.context_manager import ContextManager
from src.v1.engine.exceptions import ConfigurationError
from src.v1.engine.global_map import GlobalMap


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

_DEFAULT_CONFIG = {
    "component_type": "Replicate",
    "output_count": 2,
}


def _make_component(config=None, global_map=None):
    """Create a Replicate with test defaults."""
    gm = global_map if global_map is not None else GlobalMap()
    cm = ContextManager()
    return Replicate(
        component_id="tReplicate_1",
        config=config or dict(_DEFAULT_CONFIG),
        global_map=gm,
        context_manager=cm,
    )


def _make_input_df(rows=None):
    """Create a standard test input DataFrame."""
    if rows is None:
        rows = [
            {"id": 1, "name": "Alice", "amount": 100.0},
            {"id": 2, "name": "Bob", "amount": 200.0},
            {"id": 3, "name": "Charlie", "amount": 300.0},
        ]
    return pd.DataFrame(rows)


# ------------------------------------------------------------------
# TestRegistration
# ------------------------------------------------------------------


@pytest.mark.unit
class TestRegistration:
    """Both V1 and Talend alias are registered in REGISTRY."""

    def test_v1_name_registered(self):
        assert REGISTRY.get("Replicate") is Replicate

    def test_talend_alias_registered(self):
        assert REGISTRY.get("tReplicate") is Replicate

    def test_both_aliases_resolve_same_class(self):
        assert REGISTRY.get("Replicate") is REGISTRY.get("tReplicate")


# ------------------------------------------------------------------
# TestValidation
# ------------------------------------------------------------------


@pytest.mark.unit
class TestValidation:
    """_validate_config raises ConfigurationError for invalid output_count."""

    def test_output_count_not_integer_raises(self):
        config = {**_DEFAULT_CONFIG, "output_count": "three"}
        comp = _make_component(config=config)
        with pytest.raises(ConfigurationError, match="output_count"):
            comp.execute(_make_input_df())

    def test_output_count_float_raises(self):
        config = {**_DEFAULT_CONFIG, "output_count": 2.5}
        comp = _make_component(config=config)
        with pytest.raises(ConfigurationError, match="output_count"):
            comp.execute(_make_input_df())

    def test_output_count_zero_raises(self):
        config = {**_DEFAULT_CONFIG, "output_count": 0}
        comp = _make_component(config=config)
        with pytest.raises(ConfigurationError, match="output_count"):
            comp.execute(_make_input_df())

    def test_output_count_negative_raises(self):
        config = {**_DEFAULT_CONFIG, "output_count": -1}
        comp = _make_component(config=config)
        with pytest.raises(ConfigurationError, match="output_count"):
            comp.execute(_make_input_df())

    def test_output_count_eleven_raises(self):
        config = {**_DEFAULT_CONFIG, "output_count": 11}
        comp = _make_component(config=config)
        with pytest.raises(ConfigurationError, match="output_count"):
            comp.execute(_make_input_df())

    def test_valid_output_count_one_does_not_raise(self):
        config = {**_DEFAULT_CONFIG, "output_count": 1}
        comp = _make_component(config=config)
        result = comp.execute(_make_input_df())
        assert result["main"] is not None

    def test_valid_output_count_ten_does_not_raise(self):
        config = {**_DEFAULT_CONFIG, "output_count": 10}
        comp = _make_component(config=config)
        result = comp.execute(_make_input_df())
        assert result["main"] is not None


# ------------------------------------------------------------------
# TestMainFlow
# ------------------------------------------------------------------


@pytest.mark.unit
class TestMainFlow:
    """Core _process logic: output content and named flow keys."""

    def test_main_output_contains_all_input_rows(self):
        comp = _make_component()
        df = _make_input_df()
        result = comp.execute(df)
        assert isinstance(result["main"], pd.DataFrame)
        assert len(result["main"]) == len(df)

    def test_main_output_columns_match_input(self):
        comp = _make_component()
        df = _make_input_df()
        result = comp.execute(df)
        assert list(result["main"].columns) == list(df.columns)

    def test_main_output_data_matches_input(self):
        comp = _make_component()
        df = _make_input_df([{"id": 42, "val": "x"}])
        result = comp.execute(df)
        assert result["main"].iloc[0]["id"] == 42
        assert result["main"].iloc[0]["val"] == "x"

    def test_named_outputs_produced_for_output_count_two(self):
        config = {**_DEFAULT_CONFIG, "output_count": 2}
        comp = _make_component(config=config)
        result = comp.execute(_make_input_df())
        assert "output_1" in result
        assert "output_2" in result

    def test_named_outputs_count_matches_output_count(self):
        config = {**_DEFAULT_CONFIG, "output_count": 3}
        comp = _make_component(config=config)
        result = comp.execute(_make_input_df())
        assert "output_1" in result
        assert "output_2" in result
        assert "output_3" in result

    def test_named_outputs_have_same_rows_as_main(self):
        config = {**_DEFAULT_CONFIG, "output_count": 2}
        comp = _make_component(config=config)
        df = _make_input_df()
        result = comp.execute(df)
        assert len(result["output_1"]) == len(df)
        assert len(result["output_2"]) == len(df)

    def test_output_is_independent_copy_not_same_object(self):
        """Each output key must be an independent DataFrame copy."""
        comp = _make_component()
        df = _make_input_df()
        result = comp.execute(df)
        # Modifying one output must not affect another
        result["main"].iloc[0, 0] = 9999
        assert result["output_1"].iloc[0, 0] != 9999

    def test_output_count_one_produces_only_main_and_output_1(self):
        config = {**_DEFAULT_CONFIG, "output_count": 1}
        comp = _make_component(config=config)
        result = comp.execute(_make_input_df())
        assert "main" in result
        assert "output_1" in result
        assert "output_2" not in result


# ------------------------------------------------------------------
# TestEdgeCases
# ------------------------------------------------------------------


@pytest.mark.unit
class TestEdgeCases:
    """Empty DataFrame, None input, single row, large input."""

    def test_none_input_returns_empty_main(self):
        comp = _make_component()
        result = comp.execute(None)
        assert "main" in result
        assert isinstance(result["main"], pd.DataFrame)
        assert result["main"].empty

    def test_empty_dataframe_returns_empty_main(self):
        comp = _make_component()
        result = comp.execute(pd.DataFrame())
        assert "main" in result
        assert result["main"].empty

    def test_single_row_replicated(self):
        comp = _make_component()
        df = _make_input_df([{"id": 1, "name": "only"}])
        result = comp.execute(df)
        assert len(result["main"]) == 1

    def test_large_input(self):
        comp = _make_component()
        rows = [{"id": i, "name": f"user_{i}"} for i in range(1000)]
        df = pd.DataFrame(rows)
        result = comp.execute(df)
        assert len(result["main"]) == 1000

    def test_no_output_count_in_config_defaults_to_two(self):
        config = {"component_type": "Replicate"}
        comp = _make_component(config=config)
        result = comp.execute(_make_input_df())
        assert "main" in result
        assert "output_1" in result
        assert "output_2" in result


# ------------------------------------------------------------------
# TestGlobalMapVariables
# ------------------------------------------------------------------


@pytest.mark.unit
class TestGlobalMapVariables:
    """Stats pushed to GlobalMap after execute()."""

    def test_nb_line_pushed_for_non_empty_input(self):
        gm = GlobalMap()
        comp = _make_component(global_map=gm)
        df = _make_input_df()
        comp.execute(df)
        assert gm.get_component_stat("tReplicate_1", "NB_LINE") == len(df)

    def test_nb_line_ok_equals_input_row_count(self):
        gm = GlobalMap()
        comp = _make_component(global_map=gm)
        df = _make_input_df()
        comp.execute(df)
        assert gm.get_component_stat("tReplicate_1", "NB_LINE_OK") == len(df)

    def test_nb_line_reject_is_zero(self):
        gm = GlobalMap()
        comp = _make_component(global_map=gm)
        comp.execute(_make_input_df())
        assert gm.get_component_stat("tReplicate_1", "NB_LINE_REJECT") == 0

    def test_stats_zero_for_empty_input(self):
        gm = GlobalMap()
        comp = _make_component(global_map=gm)
        comp.execute(pd.DataFrame())
        assert gm.get_component_stat("tReplicate_1", "NB_LINE") == 0

    def test_works_without_global_map(self):
        """Component must not raise when global_map is None."""
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

    def test_config_not_mutated_across_executions(self):
        comp = _make_component()
        df = _make_input_df()
        comp.execute(df)
        snapshot = comp._original_config.copy()
        comp.reset()
        comp.execute(df)
        assert comp._original_config == snapshot
