"""Tests for FilterColumns (tFilterColumns engine implementation).

Covers requirements FCOL-01 (schema-based column selection) and FCOL-02 (passthrough).
"""
import pytest
import pandas as pd

from src.v1.engine.components.transform.filter_columns import FilterColumns
from src.v1.engine.component_registry import REGISTRY
from src.v1.engine.context_manager import ContextManager
from src.v1.engine.global_map import GlobalMap


# ------------------------------------------------------------------
# Test Helpers
# ------------------------------------------------------------------

_DEFAULT_CONFIG = {"component_type": "FilterColumns"}


def _make_component(config=None, global_map=None, output_schema=None):
    """Create a FilterColumns with test defaults."""
    gm = global_map if global_map is not None else GlobalMap()
    cm = ContextManager()
    comp = FilterColumns(
        component_id="tFilterColumns_1",
        config=config or dict(_DEFAULT_CONFIG),
        global_map=gm,
        context_manager=cm,
    )
    comp.output_schema = output_schema
    comp.input_schema = []
    return comp


def _sample_df():
    """Standard test DataFrame with 4 columns."""
    return pd.DataFrame({"a": [1, 2], "b": [3, 4], "c": [5, 6], "d": [7, 8]})


# ------------------------------------------------------------------
# TestRegistration
# ------------------------------------------------------------------


@pytest.mark.unit
class TestRegistration:
    """Component registry registration."""

    def test_registry_filter_columns(self):
        assert REGISTRY.get("FilterColumns") is FilterColumns

    def test_registry_tfilter_columns(self):
        assert REGISTRY.get("tFilterColumns") is FilterColumns


# ------------------------------------------------------------------
# TestSchemaFiltering -- covers FCOL-01, FCOL-02
# ------------------------------------------------------------------


@pytest.mark.unit
class TestSchemaFiltering:
    """Schema-based column filtering."""

    def test_select_subset_of_columns(self):
        """FCOL-01: schema [a, b] selects only columns a and b."""
        schema = [
            {"name": "a", "type": "int", "nullable": True},
            {"name": "b", "type": "int", "nullable": True},
        ]
        comp = _make_component(output_schema=schema)
        result = comp.execute(_sample_df())
        assert list(result["main"].columns) == ["a", "b"]

    def test_select_all_columns(self):
        """Schema listing all columns returns full DataFrame."""
        schema = [
            {"name": "a", "type": "int", "nullable": True},
            {"name": "b", "type": "int", "nullable": True},
            {"name": "c", "type": "int", "nullable": True},
            {"name": "d", "type": "int", "nullable": True},
        ]
        comp = _make_component(output_schema=schema)
        result = comp.execute(_sample_df())
        assert list(result["main"].columns) == ["a", "b", "c", "d"]

    def test_schema_column_not_in_input(self, caplog):
        """Schema includes column 'z' not in input -- base class fills it with null.

        Post-07.1 contract: _enforce_schema_column_order (step 7b) adds missing
        schema columns as null-filled Series. FilterColumns._process logs a warning
        for the missing columns.
        """
        import logging
        schema = [
            {"name": "a", "type": "int", "nullable": True},
            {"name": "b", "type": "int", "nullable": True},
            {"name": "z", "type": "str", "nullable": True},
        ]
        comp = _make_component(output_schema=schema)
        with caplog.at_level(logging.WARNING):
            result = comp.execute(_sample_df())
        # Base class _enforce_schema_column_order fills missing 'z' with null
        assert list(result["main"].columns) == ["a", "b", "z"]
        # 'z' column is null-filled (NaN/NA/None) for all rows
        assert result["main"]["z"].isna().all()
        # FilterColumns._process warns about missing schema columns
        assert any("z" in msg for msg in caplog.messages)

    def test_no_schema_passthrough(self):
        """FCOL-02: output_schema is None -> input returned as-is."""
        comp = _make_component(output_schema=None)
        result = comp.execute(_sample_df())
        assert list(result["main"].columns) == ["a", "b", "c", "d"]

    def test_empty_schema_passthrough(self):
        """FCOL-02: empty output_schema -> input returned as-is."""
        comp = _make_component(output_schema=[])
        result = comp.execute(_sample_df())
        assert list(result["main"].columns) == ["a", "b", "c", "d"]

    def test_preserves_column_order(self):
        """Schema [c, a] produces output columns in [c, a] order."""
        schema = [
            {"name": "c", "type": "int", "nullable": True},
            {"name": "a", "type": "int", "nullable": True},
        ]
        comp = _make_component(output_schema=schema)
        result = comp.execute(_sample_df())
        assert list(result["main"].columns) == ["c", "a"]

    def test_no_mode_config_key(self):
        """Verify component does NOT read 'mode' from config (D-09)."""
        config = dict(_DEFAULT_CONFIG)
        config["mode"] = "exclude"
        schema = [{"name": "a", "type": "int", "nullable": True}]
        comp = _make_component(config=config, output_schema=schema)
        result = comp.execute(_sample_df())
        # Should still return column 'a' (schema-driven, not mode-driven)
        assert list(result["main"].columns) == ["a"]

    def test_no_columns_config_key(self):
        """Verify component does NOT read 'columns' from config."""
        config = dict(_DEFAULT_CONFIG)
        config["columns"] = ["b", "c"]
        schema = [{"name": "a", "type": "int", "nullable": True}]
        comp = _make_component(config=config, output_schema=schema)
        result = comp.execute(_sample_df())
        assert list(result["main"].columns) == ["a"]

    def test_no_keep_row_order_config_key(self):
        """Verify component does NOT read 'keep_row_order' from config."""
        config = dict(_DEFAULT_CONFIG)
        config["keep_row_order"] = False
        schema = [{"name": "a", "type": "int", "nullable": True}]
        comp = _make_component(config=config, output_schema=schema)
        result = comp.execute(_sample_df())
        assert list(result["main"].columns) == ["a"]


# ------------------------------------------------------------------
# TestEdgeCases
# ------------------------------------------------------------------


@pytest.mark.unit
class TestEdgeCases:
    """Edge cases for empty data, None input, stats."""

    def test_empty_input(self):
        """Empty DataFrame returns empty DataFrame."""
        schema = [{"name": "a", "type": "int", "nullable": True}]
        comp = _make_component(output_schema=schema)
        result = comp.execute(pd.DataFrame())
        assert result["main"] is not None
        assert isinstance(result["main"], pd.DataFrame)
        assert result["main"].empty

    def test_none_input(self):
        """None input returns None."""
        schema = [{"name": "a", "type": "int", "nullable": True}]
        comp = _make_component(output_schema=schema)
        result = comp.execute(None)
        assert result["main"] is None

    def test_stats_updated(self):
        """GlobalMap has NB_LINE stats after execute."""
        gm = GlobalMap()
        schema = [{"name": "a", "type": "int", "nullable": True}]
        comp = _make_component(global_map=gm, output_schema=schema)
        comp.execute(_sample_df())
        # _process calls _update_stats(2, 2, 0); _stats_set_by_component=True so
        # _update_stats_from_result is a no-op (post-07.1 contract: no double-count)
        # NB_LINE = 2, NB_LINE_OK = 2
        assert gm.get_nb_line("tFilterColumns_1") == 2
        assert gm.get_nb_line_ok("tFilterColumns_1") == 2

    def test_all_rows_preserved(self):
        """Column filter does not remove rows -- row count same."""
        schema = [{"name": "a", "type": "int", "nullable": True}]
        comp = _make_component(output_schema=schema)
        df = _sample_df()
        result = comp.execute(df)
        assert len(result["main"]) == len(df)
