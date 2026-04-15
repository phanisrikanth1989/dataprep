"""Tests for Unite (tUnite engine implementation).

Covers requirements UNIT-01 (UNION ALL concat) and UNIT-02 (mismatched schemas).
"""
import pytest
import numpy as np
import pandas as pd

from src.v1.engine.components.transform.unite import Unite
from src.v1.engine.component_registry import REGISTRY
from src.v1.engine.context_manager import ContextManager
from src.v1.engine.global_map import GlobalMap


# ------------------------------------------------------------------
# Test Helpers
# ------------------------------------------------------------------

_DEFAULT_CONFIG = {"component_type": "Unite"}


def _make_component(config=None, global_map=None, output_schema=None):
    """Create a Unite with test defaults."""
    gm = global_map if global_map is not None else GlobalMap()
    cm = ContextManager()
    comp = Unite(
        component_id="tUnite_1",
        config=config or dict(_DEFAULT_CONFIG),
        global_map=gm,
        context_manager=cm,
    )
    comp.output_schema = output_schema or []
    comp.input_schema = []
    comp.inputs = ["row1", "row2"]
    return comp


# ------------------------------------------------------------------
# TestRegistration
# ------------------------------------------------------------------


@pytest.mark.unit
class TestRegistration:
    """Component registry registration."""

    def test_registry_unite(self):
        assert REGISTRY.get("Unite") is Unite

    def test_registry_tunite(self):
        assert REGISTRY.get("tUnite") is Unite


# ------------------------------------------------------------------
# TestUnionConcat -- covers UNIT-01
# ------------------------------------------------------------------


@pytest.mark.unit
class TestUnionConcat:
    """UNION ALL concat behavior."""

    def test_two_inputs_same_schema(self):
        """Two DataFrames with same columns are concatenated."""
        comp = _make_component()
        df1 = pd.DataFrame({"x": [1, 2], "y": ["a", "b"]})
        df2 = pd.DataFrame({"x": [3, 4], "y": ["c", "d"]})
        result = comp.execute({"row1": df1, "row2": df2})
        assert len(result["main"]) == 4
        assert list(result["main"]["x"]) == [1, 2, 3, 4]
        assert list(result["main"]["y"]) == ["a", "b", "c", "d"]

    def test_three_inputs(self):
        """Three DataFrames all concatenated."""
        comp = _make_component()
        comp.inputs = ["row1", "row2", "row3"]
        df1 = pd.DataFrame({"x": [1]})
        df2 = pd.DataFrame({"x": [2]})
        df3 = pd.DataFrame({"x": [3]})
        result = comp.execute({"row1": df1, "row2": df2, "row3": df3})
        assert len(result["main"]) == 3
        assert list(result["main"]["x"]) == [1, 2, 3]

    def test_row_count_correct(self):
        """2 + 3 rows = 5 rows total."""
        comp = _make_component()
        df1 = pd.DataFrame({"v": [1, 2]})
        df2 = pd.DataFrame({"v": [3, 4, 5]})
        result = comp.execute({"row1": df1, "row2": df2})
        assert len(result["main"]) == 5

    def test_column_order_preserved(self):
        """Output columns match first input's column order."""
        comp = _make_component()
        df1 = pd.DataFrame({"b": [1], "a": [2]})
        df2 = pd.DataFrame({"b": [3], "a": [4]})
        result = comp.execute({"row1": df1, "row2": df2})
        assert list(result["main"].columns) == ["b", "a"]

    def test_ignore_index_true(self):
        """Output index is 0..N-1 (reset, not carried from inputs)."""
        comp = _make_component()
        df1 = pd.DataFrame({"x": [1, 2]}, index=[10, 20])
        df2 = pd.DataFrame({"x": [3, 4]}, index=[30, 40])
        result = comp.execute({"row1": df1, "row2": df2})
        assert list(result["main"].index) == [0, 1, 2, 3]


# ------------------------------------------------------------------
# TestMismatchedSchemas -- covers UNIT-02
# ------------------------------------------------------------------


@pytest.mark.unit
class TestMismatchedSchemas:
    """Mismatched schema UNION ALL behavior (NaN fills)."""

    def test_mismatched_columns_fills_nan(self):
        """input1 [a,b], input2 [a,c] -> output [a,b,c] with NaN fills."""
        comp = _make_component()
        df1 = pd.DataFrame({"a": [1], "b": [2]})
        df2 = pd.DataFrame({"a": [3], "c": [4]})
        result = comp.execute({"row1": df1, "row2": df2})
        main = result["main"]
        assert set(main.columns) == {"a", "b", "c"}
        # df1 row: b=2, c=NaN
        assert main.loc[0, "b"] == 2
        assert pd.isna(main.loc[0, "c"])
        # df2 row: b=NaN, c=4
        assert pd.isna(main.loc[1, "b"])
        assert main.loc[1, "c"] == 4

    def test_extra_columns_preserved(self):
        """input1 has extra column not in input2 -> NaN for input2 rows."""
        comp = _make_component()
        df1 = pd.DataFrame({"a": [1], "b": [2], "extra": [99]})
        df2 = pd.DataFrame({"a": [3], "b": [4]})
        result = comp.execute({"row1": df1, "row2": df2})
        main = result["main"]
        assert "extra" in main.columns
        assert main.loc[0, "extra"] == 99
        assert pd.isna(main.loc[1, "extra"])

    def test_identical_schemas_no_nan(self):
        """Both inputs same columns -> no NaN in output."""
        comp = _make_component()
        df1 = pd.DataFrame({"a": [1], "b": [2]})
        df2 = pd.DataFrame({"a": [3], "b": [4]})
        result = comp.execute({"row1": df1, "row2": df2})
        assert not result["main"].isna().any().any()


# ------------------------------------------------------------------
# TestEdgeCases
# ------------------------------------------------------------------


@pytest.mark.unit
class TestEdgeCases:
    """Edge cases."""

    def test_empty_dict_input(self):
        """Empty dict -> empty DataFrame."""
        comp = _make_component()
        result = comp.execute({})
        assert isinstance(result["main"], pd.DataFrame)
        assert result["main"].empty

    def test_none_input(self):
        """None input -> empty DataFrame."""
        comp = _make_component()
        result = comp.execute(None)
        assert isinstance(result["main"], pd.DataFrame)
        assert result["main"].empty

    def test_single_input(self):
        """One DataFrame in dict -> returned as-is."""
        comp = _make_component()
        df = pd.DataFrame({"x": [1, 2, 3]})
        result = comp.execute({"row1": df})
        assert len(result["main"]) == 3
        assert list(result["main"]["x"]) == [1, 2, 3]

    def test_one_empty_one_valid(self):
        """One empty DF + one valid -> valid DF returned."""
        comp = _make_component()
        df1 = pd.DataFrame()
        df2 = pd.DataFrame({"x": [1, 2]})
        result = comp.execute({"row1": df1, "row2": df2})
        assert len(result["main"]) == 2

    def test_all_empty_inputs(self):
        """All empty DataFrames -> empty output."""
        comp = _make_component()
        df1 = pd.DataFrame()
        df2 = pd.DataFrame()
        result = comp.execute({"row1": df1, "row2": df2})
        assert result["main"].empty

    def test_stats_updated(self):
        """GlobalMap has NB_LINE stats after execute."""
        gm = GlobalMap()
        comp = _make_component(global_map=gm)
        df1 = pd.DataFrame({"x": [1, 2]})
        df2 = pd.DataFrame({"x": [3]})
        comp.execute({"row1": df1, "row2": df2})
        # _process calls _update_stats(3, 3, 0) + _update_stats_from_result adds (3 main, 0 reject)
        # NB_LINE = 3 + 3 = 6
        assert gm.get_nb_line("tUnite_1") == 6

    def test_no_execute_override(self):
        """Verify Unite does NOT have a custom execute() method (D-12)."""
        assert "execute" not in Unite.__dict__

    def test_no_input_data_map_state(self):
        """Verify Unite instance has no input_data_map attribute."""
        comp = _make_component()
        assert not hasattr(comp, "input_data_map")
