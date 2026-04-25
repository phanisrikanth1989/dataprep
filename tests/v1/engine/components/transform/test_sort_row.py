"""Tests for SortRow (tSortRow engine implementation)."""
import pytest
import pandas as pd

from src.v1.engine.components.transform.sort_row import SortRow
from src.v1.engine.component_registry import REGISTRY
from src.v1.engine.context_manager import ContextManager
from src.v1.engine.exceptions import ConfigurationError
from src.v1.engine.global_map import GlobalMap


# ------------------------------------------------------------------
# Test Helpers
# ------------------------------------------------------------------

_DEFAULT_CONFIG = {
    "component_type": "SortRow",
    "criteria": [
        {"column": "name", "sort_type": "alpha", "order": "asc"},
    ],
}


def _make_component(config=None, global_map=None, schema=None):
    """Create a SortRow with test defaults."""
    gm = global_map if global_map is not None else GlobalMap()
    cm = ContextManager()
    comp = SortRow(
        component_id="tSort_1",
        config=config or dict(_DEFAULT_CONFIG),
        global_map=gm,
        context_manager=cm,
    )
    comp.output_schema = schema
    return comp


def _sample_df():
    """Standard test DataFrame for sorting."""
    return pd.DataFrame({
        "name": ["Charlie", "Alice", "Bob", "Alice"],
        "age": [30, 25, 35, 28],
        "salary": [50000.0, 60000.0, 45000.0, 55000.0],
        "hire_date": ["2020-01-15", "2019-06-01", "2021-03-10", "2018-09-20"],
    })


# ------------------------------------------------------------------
# TestValidation
# ------------------------------------------------------------------


@pytest.mark.unit
class TestValidation:
    """Validate that config errors are caught before processing."""

    def test_missing_criteria(self):
        config = {"component_type": "SortRow", "criteria": []}
        comp = _make_component(config=config)
        with pytest.raises(ConfigurationError, match="criteria"):
            comp.execute(_sample_df())

    def test_criteria_not_list(self):
        config = {"component_type": "SortRow", "criteria": "not_a_list"}
        comp = _make_component(config=config)
        with pytest.raises(ConfigurationError, match="criteria"):
            comp.execute(_sample_df())

    def test_invalid_sort_type(self):
        config = {
            "component_type": "SortRow",
            "criteria": [{"column": "name", "sort_type": "bogus", "order": "asc"}],
        }
        comp = _make_component(config=config)
        with pytest.raises(ConfigurationError, match="sort_type"):
            comp.execute(_sample_df())

    def test_invalid_order(self):
        config = {
            "component_type": "SortRow",
            "criteria": [{"column": "name", "sort_type": "alpha", "order": "sideways"}],
        }
        comp = _make_component(config=config)
        with pytest.raises(ConfigurationError, match="order"):
            comp.execute(_sample_df())


# ------------------------------------------------------------------
# TestAlphaSort -- covers SORT-01
# ------------------------------------------------------------------


@pytest.mark.unit
class TestAlphaSort:
    """Alphabetic (string) sorting."""

    def test_alpha_ascending(self):
        """SORT-01: string sort ascending."""
        comp = _make_component()
        result = comp.execute(_sample_df())
        names = result["main"]["name"].tolist()
        assert names == ["Alice", "Alice", "Bob", "Charlie"]

    def test_alpha_descending(self):
        config = dict(_DEFAULT_CONFIG)
        config["criteria"] = [{"column": "name", "sort_type": "alpha", "order": "desc"}]
        comp = _make_component(config=config)
        result = comp.execute(_sample_df())
        names = result["main"]["name"].tolist()
        assert names == ["Charlie", "Bob", "Alice", "Alice"]

    def test_alpha_case_sensitive(self):
        """'Z' sorts before 'a' in alpha mode (standard string comparison)."""
        df = pd.DataFrame({"name": ["banana", "Apple", "Zebra", "cherry"]})
        config = dict(_DEFAULT_CONFIG)
        config["criteria"] = [{"column": "name", "sort_type": "alpha", "order": "asc"}]
        comp = _make_component(config=config)
        result = comp.execute(df)
        names = result["main"]["name"].tolist()
        # Uppercase comes first in string comparison: A < Z < b < c
        assert names == ["Apple", "Zebra", "banana", "cherry"]


# ------------------------------------------------------------------
# TestNumericSort -- covers SORT-01
# ------------------------------------------------------------------


@pytest.mark.unit
class TestNumericSort:
    """Numeric sorting."""

    def test_num_ascending(self):
        config = dict(_DEFAULT_CONFIG)
        config["criteria"] = [{"column": "age", "sort_type": "num", "order": "asc"}]
        comp = _make_component(config=config)
        result = comp.execute(_sample_df())
        ages = result["main"]["age"].tolist()
        assert ages == [25, 28, 30, 35]

    def test_num_descending(self):
        config = dict(_DEFAULT_CONFIG)
        config["criteria"] = [{"column": "age", "sort_type": "num", "order": "desc"}]
        comp = _make_component(config=config)
        result = comp.execute(_sample_df())
        ages = result["main"]["age"].tolist()
        assert ages == [35, 30, 28, 25]

    def test_num_with_string_numbers(self):
        """String column containing '1', '2', '10' sorted as numbers (1, 2, 10 not 1, 10, 2)."""
        df = pd.DataFrame({"val": ["10", "1", "2", "20", "3"]})
        config = dict(_DEFAULT_CONFIG)
        config["criteria"] = [{"column": "val", "sort_type": "num", "order": "asc"}]
        comp = _make_component(config=config)
        result = comp.execute(df)
        vals = result["main"]["val"].tolist()
        # Numeric coercion: 1, 2, 3, 10, 20
        assert vals == ["1", "2", "3", "10", "20"]

    def test_num_with_nan(self):
        """NaN values go to end (na_position=last)."""
        import numpy as np
        df = pd.DataFrame({"val": [3.0, np.nan, 1.0, 2.0]})
        config = dict(_DEFAULT_CONFIG)
        config["criteria"] = [{"column": "val", "sort_type": "num", "order": "asc"}]
        comp = _make_component(config=config)
        result = comp.execute(df)
        vals = result["main"]["val"].tolist()
        # NaN at end
        assert vals[:3] == [1.0, 2.0, 3.0]
        assert pd.isna(vals[3])


# ------------------------------------------------------------------
# TestDateSort -- covers SORT-01
# ------------------------------------------------------------------


@pytest.mark.unit
class TestDateSort:
    """Date sorting."""

    def test_date_ascending(self):
        """Date strings sorted chronologically."""
        config = dict(_DEFAULT_CONFIG)
        config["criteria"] = [{"column": "hire_date", "sort_type": "date", "order": "asc"}]
        comp = _make_component(config=config)
        result = comp.execute(_sample_df())
        dates = result["main"]["hire_date"].tolist()
        assert dates == ["2018-09-20", "2019-06-01", "2020-01-15", "2021-03-10"]

    def test_date_descending(self):
        config = dict(_DEFAULT_CONFIG)
        config["criteria"] = [{"column": "hire_date", "sort_type": "date", "order": "desc"}]
        comp = _make_component(config=config)
        result = comp.execute(_sample_df())
        dates = result["main"]["hire_date"].tolist()
        assert dates == ["2021-03-10", "2020-01-15", "2019-06-01", "2018-09-20"]


# ------------------------------------------------------------------
# TestMultiColumnSort
# ------------------------------------------------------------------


@pytest.mark.unit
class TestMultiColumnSort:
    """Multi-column sorting."""

    def test_two_column_sort(self):
        """Sort by name asc, then salary desc."""
        config = dict(_DEFAULT_CONFIG)
        config["criteria"] = [
            {"column": "name", "sort_type": "alpha", "order": "asc"},
            {"column": "salary", "sort_type": "num", "order": "desc"},
        ]
        comp = _make_component(config=config)
        result = comp.execute(_sample_df())
        main = result["main"]
        # Alice rows: salary 60000 (idx=1 orig), 55000 (idx=3 orig)
        alice_rows = main[main["name"] == "Alice"]
        assert alice_rows.iloc[0]["salary"] == 60000.0  # desc salary
        assert alice_rows.iloc[1]["salary"] == 55000.0

    def test_mixed_sort_types(self):
        """Alpha on name, num on salary."""
        config = dict(_DEFAULT_CONFIG)
        config["criteria"] = [
            {"column": "name", "sort_type": "alpha", "order": "asc"},
            {"column": "age", "sort_type": "num", "order": "asc"},
        ]
        comp = _make_component(config=config)
        result = comp.execute(_sample_df())
        main = result["main"]
        # Alice rows: age 25, 28
        alice_rows = main[main["name"] == "Alice"]
        assert alice_rows.iloc[0]["age"] == 25
        assert alice_rows.iloc[1]["age"] == 28

    def test_stable_sort(self):
        """Equal values in first column maintain relative order from second column."""
        df = pd.DataFrame({
            "group": ["A", "A", "A"],
            "order_col": [3, 1, 2],
        })
        config = dict(_DEFAULT_CONFIG)
        config["criteria"] = [
            {"column": "group", "sort_type": "alpha", "order": "asc"},
        ]
        comp = _make_component(config=config)
        result = comp.execute(df)
        # All "A" -- stable sort preserves original order: 3, 1, 2
        orders = result["main"]["order_col"].tolist()
        assert orders == [3, 1, 2]


# ------------------------------------------------------------------
# TestExternalFlag -- covers SORT-02, SORT-03
# ------------------------------------------------------------------


@pytest.mark.unit
class TestExternalFlag:
    """External sort flag behavior."""

    def test_external_flag_ignored(self):
        """SORT-02: external=True does not change behavior (logs info)."""
        config = dict(_DEFAULT_CONFIG)
        config["external"] = True
        comp = _make_component(config=config)
        result = comp.execute(_sample_df())
        names = result["main"]["name"].tolist()
        assert names == ["Alice", "Alice", "Bob", "Charlie"]

    def test_no_streaming_mode(self):
        """SORT-03: sort always processes full DataFrame."""
        comp = _make_component()
        result = comp.execute(_sample_df())
        assert len(result["main"]) == 4  # all rows present


# ------------------------------------------------------------------
# TestConfigKeys -- covers SORT-04
# ------------------------------------------------------------------


@pytest.mark.unit
class TestConfigKeys:
    """Config key naming compliance."""

    def test_reads_criteria_not_sort_columns(self):
        """Component reads 'criteria' key."""
        config = dict(_DEFAULT_CONFIG)
        # criteria is correctly set, should work
        comp = _make_component(config=config)
        result = comp.execute(_sample_df())
        assert len(result["main"]) == 4

    def test_no_na_position_config(self):
        """Component does not read na_position from config -- hardcoded to 'last'."""
        config = dict(_DEFAULT_CONFIG)
        config["na_position"] = "first"  # should be ignored
        comp = _make_component(config=config)
        import numpy as np
        df = pd.DataFrame({"name": [np.nan, "Alice", "Bob"]})
        result = comp.execute(df)
        # NaN should still be last regardless of config key
        names = result["main"]["name"].tolist()
        assert names[0] == "Alice"
        assert names[1] == "Bob"
        assert pd.isna(names[2])

    def test_no_case_sensitive_config(self):
        """Component does not read case_sensitive from config."""
        config = dict(_DEFAULT_CONFIG)
        config["case_sensitive"] = False  # should be ignored
        comp = _make_component(config=config)
        result = comp.execute(_sample_df())
        # Still case-sensitive sort
        assert len(result["main"]) == 4

    def test_no_chunk_size_config(self):
        """Component does not read chunk_size from config."""
        config = dict(_DEFAULT_CONFIG)
        config["chunk_size"] = 1  # should be ignored
        comp = _make_component(config=config)
        result = comp.execute(_sample_df())
        # All rows still present
        assert len(result["main"]) == 4


# ------------------------------------------------------------------
# TestEdgeCases
# ------------------------------------------------------------------


@pytest.mark.unit
class TestEdgeCases:
    """Edge cases for empty data, single row, missing columns."""

    def test_empty_input(self):
        comp = _make_component()
        result = comp.execute(pd.DataFrame())
        assert result["main"].empty

    def test_none_input(self):
        comp = _make_component()
        result = comp.execute(None)
        assert result["main"].empty

    def test_single_row(self):
        df = pd.DataFrame({"name": ["Alice"], "age": [25]})
        comp = _make_component()
        result = comp.execute(df)
        assert len(result["main"]) == 1
        assert result["main"]["name"].iloc[0] == "Alice"

    def test_missing_column_in_criteria(self):
        """Criteria column not in input is silently skipped (warning logged)."""
        config = dict(_DEFAULT_CONFIG)
        config["criteria"] = [
            {"column": "nonexistent", "sort_type": "alpha", "order": "asc"},
        ]
        comp = _make_component(config=config)
        result = comp.execute(_sample_df())
        # Returns data as-is since no valid criteria columns found
        assert len(result["main"]) == 4

    def test_stats_updated(self):
        gm = GlobalMap()
        comp = _make_component(global_map=gm)
        comp.execute(_sample_df())
        # _process calls _update_stats(4, 4, 0); _stats_set_by_component=True so
        # _update_stats_from_result is a no-op (post-07.1 contract: no double-count)
        # NB_LINE = 4, NB_LINE_OK = 4
        assert gm.get_nb_line("tSort_1") == 4
        assert gm.get_nb_line_ok("tSort_1") == 4


# ------------------------------------------------------------------
# TestRegistration -- covers SORT-05
# ------------------------------------------------------------------


@pytest.mark.unit
class TestRegistration:
    """Component registry registration."""

    def test_registered_as_sort_row(self):
        cls = REGISTRY.get("SortRow")
        assert cls is SortRow

    def test_registered_as_t_sort_row(self):
        cls = REGISTRY.get("tSortRow")
        assert cls is SortRow
