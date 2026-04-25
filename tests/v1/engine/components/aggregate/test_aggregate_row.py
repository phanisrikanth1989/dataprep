"""Tests for AggregateRow (tAggregateRow engine implementation)."""
from decimal import Decimal

import pytest
import numpy as np
import pandas as pd

from src.v1.engine.components.aggregate.aggregate_row import AggregateRow
from src.v1.engine.component_registry import REGISTRY
from src.v1.engine.context_manager import ContextManager
from src.v1.engine.exceptions import ConfigurationError
from src.v1.engine.global_map import GlobalMap


# ------------------------------------------------------------------
# Test Helpers
# ------------------------------------------------------------------

_DEFAULT_CONFIG = {
    "component_type": "AggregateRow",
    "groupbys": [{"output_column": "dept", "input_column": "department"}],
    "operations": [
        {"output_column": "total", "function": "sum", "input_column": "amount", "ignore_null": True},
    ],
    "list_delimiter": ",",
    "use_financial_precision": False,
}


def _make_component(config=None, global_map=None, schema=None):
    """Create an AggregateRow with test defaults."""
    gm = global_map if global_map is not None else GlobalMap()
    cm = ContextManager()
    comp = AggregateRow(
        component_id="tAgg_1",
        config=config or dict(_DEFAULT_CONFIG),
        global_map=gm,
        context_manager=cm,
    )
    comp.output_schema = schema
    return comp


def _sample_df():
    """Standard test DataFrame with departments and amounts."""
    return pd.DataFrame({
        "department": ["A", "A", "B", "B", "B"],
        "product": ["x", "y", "x", "y", "z"],
        "amount": [100.0, 200.0, 150.0, 250.0, 300.0],
        "quantity": [1, 2, 3, 4, 5],
    })


# ------------------------------------------------------------------
# TestValidation
# ------------------------------------------------------------------


@pytest.mark.unit
class TestValidation:
    """Validate that config errors are caught before processing."""

    def test_missing_operations_key(self):
        config = dict(_DEFAULT_CONFIG)
        config["operations"] = "not_a_list"
        comp = _make_component(config=config)
        with pytest.raises(ConfigurationError, match="operations.*list"):
            comp.execute(_sample_df())

    def test_invalid_function_name(self):
        config = dict(_DEFAULT_CONFIG)
        config["operations"] = [
            {"output_column": "x", "function": "bogus_func", "input_column": "amount"},
        ]
        comp = _make_component(config=config)
        with pytest.raises(ConfigurationError, match="unsupported function"):
            comp.execute(_sample_df())

    def test_missing_input_column(self):
        config = dict(_DEFAULT_CONFIG)
        config["operations"] = [
            {"output_column": "x", "function": "sum"},
        ]
        comp = _make_component(config=config)
        with pytest.raises(ConfigurationError, match="input_column"):
            comp.execute(_sample_df())


# ------------------------------------------------------------------
# TestBasicAggregation -- covers AGGR-01, AGGR-02, AGGR-05
# ------------------------------------------------------------------


@pytest.mark.unit
class TestBasicAggregation:
    """Basic grouped aggregation functions."""

    def test_sum_grouped(self):
        comp = _make_component()
        result = comp.execute(_sample_df())
        main = result["main"]
        assert len(main) == 2  # two departments
        assert "total" in main.columns
        a_total = main.loc[main["dept"] == "A", "total"].iloc[0]
        b_total = main.loc[main["dept"] == "B", "total"].iloc[0]
        assert a_total == 300.0  # 100 + 200
        assert b_total == 700.0  # 150 + 250 + 300

    def test_count_grouped(self):
        config = dict(_DEFAULT_CONFIG)
        config["operations"] = [
            {"output_column": "cnt", "function": "count", "input_column": "amount", "ignore_null": True},
        ]
        comp = _make_component(config=config)
        result = comp.execute(_sample_df())
        main = result["main"]
        a_cnt = main.loc[main["dept"] == "A", "cnt"].iloc[0]
        b_cnt = main.loc[main["dept"] == "B", "cnt"].iloc[0]
        assert a_cnt == 2
        assert b_cnt == 3

    def test_avg_grouped(self):
        config = dict(_DEFAULT_CONFIG)
        config["operations"] = [
            {"output_column": "avg_amt", "function": "avg", "input_column": "amount", "ignore_null": True},
        ]
        comp = _make_component(config=config)
        result = comp.execute(_sample_df())
        main = result["main"]
        a_avg = main.loc[main["dept"] == "A", "avg_amt"].iloc[0]
        b_avg = main.loc[main["dept"] == "B", "avg_amt"].iloc[0]
        assert a_avg == pytest.approx(150.0)
        assert b_avg == pytest.approx(233.333, rel=1e-2)

    def test_min_max_grouped(self):
        config = dict(_DEFAULT_CONFIG)
        config["operations"] = [
            {"output_column": "min_amt", "function": "min", "input_column": "amount", "ignore_null": True},
            {"output_column": "max_amt", "function": "max", "input_column": "amount", "ignore_null": True},
        ]
        comp = _make_component(config=config)
        result = comp.execute(_sample_df())
        main = result["main"]
        a_min = main.loc[main["dept"] == "A", "min_amt"].iloc[0]
        a_max = main.loc[main["dept"] == "A", "max_amt"].iloc[0]
        b_min = main.loc[main["dept"] == "B", "min_amt"].iloc[0]
        b_max = main.loc[main["dept"] == "B", "max_amt"].iloc[0]
        assert a_min == 100.0
        assert a_max == 200.0
        assert b_min == 150.0
        assert b_max == 300.0

    def test_first_last_grouped(self):
        config = dict(_DEFAULT_CONFIG)
        config["operations"] = [
            {"output_column": "first_prod", "function": "first", "input_column": "product", "ignore_null": True},
            {"output_column": "last_prod", "function": "last", "input_column": "product", "ignore_null": True},
        ]
        comp = _make_component(config=config)
        result = comp.execute(_sample_df())
        main = result["main"]
        a_first = main.loc[main["dept"] == "A", "first_prod"].iloc[0]
        a_last = main.loc[main["dept"] == "A", "last_prod"].iloc[0]
        assert a_first == "x"
        assert a_last == "y"

    def test_output_column_respected(self):
        """AGGR-02: Operation output_column is used as result column name, NOT input_column."""
        config = dict(_DEFAULT_CONFIG)
        config["operations"] = [
            {"output_column": "my_total", "function": "sum", "input_column": "amount", "ignore_null": True},
        ]
        comp = _make_component(config=config)
        result = comp.execute(_sample_df())
        main = result["main"]
        assert "my_total" in main.columns
        assert "amount" not in main.columns

    def test_output_only_contains_groupby_and_operation_columns(self):
        """AGGR-01: No input columns leak into output."""
        comp = _make_component()
        result = comp.execute(_sample_df())
        main = result["main"]
        # Only dept (groupby output) and total (operation output) should be present
        assert set(main.columns) == {"dept", "total"}

    def test_multiple_operations_single_pass(self):
        """AGGR-05: Multiple operations on same input produce correct results."""
        config = dict(_DEFAULT_CONFIG)
        config["operations"] = [
            {"output_column": "total", "function": "sum", "input_column": "amount", "ignore_null": True},
            {"output_column": "avg_amt", "function": "avg", "input_column": "amount", "ignore_null": True},
            {"output_column": "cnt", "function": "count", "input_column": "amount", "ignore_null": True},
        ]
        comp = _make_component(config=config)
        result = comp.execute(_sample_df())
        main = result["main"]
        assert set(main.columns) == {"dept", "total", "avg_amt", "cnt"}
        a_row = main[main["dept"] == "A"].iloc[0]
        assert a_row["total"] == 300.0
        assert a_row["avg_amt"] == pytest.approx(150.0)
        assert a_row["cnt"] == 2


# ------------------------------------------------------------------
# TestGlobalAggregation
# ------------------------------------------------------------------


@pytest.mark.unit
class TestGlobalAggregation:
    """Aggregation without group-by columns (global/single-row result)."""

    def test_sum_no_groupby(self):
        config = dict(_DEFAULT_CONFIG)
        config["groupbys"] = []
        comp = _make_component(config=config)
        result = comp.execute(_sample_df())
        main = result["main"]
        assert len(main) == 1
        assert main["total"].iloc[0] == 1000.0  # 100+200+150+250+300

    def test_count_no_groupby(self):
        config = dict(_DEFAULT_CONFIG)
        config["groupbys"] = []
        config["operations"] = [
            {"output_column": "cnt", "function": "count", "input_column": "amount", "ignore_null": True},
        ]
        comp = _make_component(config=config)
        result = comp.execute(_sample_df())
        main = result["main"]
        assert len(main) == 1
        assert main["cnt"].iloc[0] == 5

    def test_multiple_operations_no_groupby(self):
        config = dict(_DEFAULT_CONFIG)
        config["groupbys"] = []
        config["operations"] = [
            {"output_column": "total", "function": "sum", "input_column": "amount", "ignore_null": True},
            {"output_column": "cnt", "function": "count", "input_column": "quantity", "ignore_null": True},
        ]
        comp = _make_component(config=config)
        result = comp.execute(_sample_df())
        main = result["main"]
        assert len(main) == 1
        assert main["total"].iloc[0] == 1000.0
        assert main["cnt"].iloc[0] == 5


# ------------------------------------------------------------------
# TestGroupbyColumnRenaming -- covers AGGR-08
# ------------------------------------------------------------------


@pytest.mark.unit
class TestGroupbyColumnRenaming:
    """Groupby output_column renaming."""

    def test_groupby_output_column_differs_from_input(self):
        """AGGR-08: groupby with output_column != input_column renames correctly."""
        config = dict(_DEFAULT_CONFIG)
        config["groupbys"] = [{"output_column": "grp", "input_column": "department"}]
        comp = _make_component(config=config)
        result = comp.execute(_sample_df())
        main = result["main"]
        assert "grp" in main.columns
        assert "department" not in main.columns

    def test_no_column_collision(self):
        """AGGR-08: groupby output_column and operation output_column don't collide."""
        config = dict(_DEFAULT_CONFIG)
        config["groupbys"] = [{"output_column": "group_col", "input_column": "department"}]
        config["operations"] = [
            {"output_column": "op_col", "function": "sum", "input_column": "amount", "ignore_null": True},
        ]
        comp = _make_component(config=config)
        result = comp.execute(_sample_df())
        main = result["main"]
        assert "group_col" in main.columns
        assert "op_col" in main.columns
        assert len(main.columns) == 2


# ------------------------------------------------------------------
# TestIgnoreNull -- covers AGGR-03
# ------------------------------------------------------------------


@pytest.mark.unit
class TestIgnoreNull:
    """Null handling in aggregation operations."""

    def _df_with_nan(self):
        return pd.DataFrame({
            "department": ["A", "A", "B", "B"],
            "amount": [100.0, np.nan, 150.0, 250.0],
        })

    def test_ignore_null_true_skips_nan(self):
        config = dict(_DEFAULT_CONFIG)
        config["operations"] = [
            {"output_column": "total", "function": "sum", "input_column": "amount", "ignore_null": True},
        ]
        comp = _make_component(config=config)
        result = comp.execute(self._df_with_nan())
        main = result["main"]
        a_total = main.loc[main["dept"] == "A", "total"].iloc[0]
        assert a_total == 100.0  # NaN skipped

    def test_ignore_null_false_propagates_nan(self):
        """AGGR-03: sum with NaN and ignore_null=False returns NaN."""
        config = dict(_DEFAULT_CONFIG)
        config["operations"] = [
            {"output_column": "total", "function": "sum", "input_column": "amount", "ignore_null": False},
        ]
        comp = _make_component(config=config)
        result = comp.execute(self._df_with_nan())
        main = result["main"]
        a_total = main.loc[main["dept"] == "A", "total"].iloc[0]
        assert pd.isna(a_total), "NaN should propagate when ignore_null=False"

    def test_ignore_null_false_avg(self):
        config = dict(_DEFAULT_CONFIG)
        config["operations"] = [
            {"output_column": "avg_amt", "function": "avg", "input_column": "amount", "ignore_null": False},
        ]
        comp = _make_component(config=config)
        result = comp.execute(self._df_with_nan())
        main = result["main"]
        a_avg = main.loc[main["dept"] == "A", "avg_amt"].iloc[0]
        assert pd.isna(a_avg), "NaN should propagate in avg when ignore_null=False"

    def test_ignore_null_per_operation(self):
        """One operation with ignore_null=True, another with ignore_null=False."""
        config = dict(_DEFAULT_CONFIG)
        config["operations"] = [
            {"output_column": "sum_skip", "function": "sum", "input_column": "amount", "ignore_null": True},
            {"output_column": "sum_prop", "function": "sum", "input_column": "amount", "ignore_null": False},
        ]
        comp = _make_component(config=config)
        result = comp.execute(self._df_with_nan())
        main = result["main"]
        a_skip = main.loc[main["dept"] == "A", "sum_skip"].iloc[0]
        a_prop = main.loc[main["dept"] == "A", "sum_prop"].iloc[0]
        assert a_skip == 100.0
        assert pd.isna(a_prop)


# ------------------------------------------------------------------
# TestSpecialFunctions -- covers AGGR-04
# ------------------------------------------------------------------


@pytest.mark.unit
class TestSpecialFunctions:
    """Special aggregation functions: count_distinct, list, median, variance, std, population_std_dev."""

    def test_count_distinct(self):
        config = dict(_DEFAULT_CONFIG)
        config["operations"] = [
            {"output_column": "n_unique", "function": "count_distinct", "input_column": "product", "ignore_null": True},
        ]
        comp = _make_component(config=config)
        result = comp.execute(_sample_df())
        main = result["main"]
        a_uniq = main.loc[main["dept"] == "A", "n_unique"].iloc[0]
        b_uniq = main.loc[main["dept"] == "B", "n_unique"].iloc[0]
        assert a_uniq == 2  # x, y
        assert b_uniq == 3  # x, y, z

    def test_list_aggregation(self):
        """D-09: list produces comma-separated string of values."""
        config = dict(_DEFAULT_CONFIG)
        config["operations"] = [
            {"output_column": "products", "function": "list", "input_column": "product", "ignore_null": True},
        ]
        comp = _make_component(config=config)
        result = comp.execute(_sample_df())
        main = result["main"]
        a_list = main.loc[main["dept"] == "A", "products"].iloc[0]
        assert isinstance(a_list, str)
        assert "x" in a_list
        assert "y" in a_list
        assert "," in a_list

    def test_list_object_aggregation(self):
        """CR-05 (supersedes Phase 6 D-09): list_object produces Python list, NOT a delimited string.

        Talaxie tAggregateRow_messages.properties: LIST_DELIMITER.NAME=Delimiter (only for list operation)
        list_delimiter does NOT apply to list_object; list_object returns a Python list.
        """
        config = dict(_DEFAULT_CONFIG)
        config["operations"] = [
            {"output_column": "products", "function": "list_object", "input_column": "product", "ignore_null": True},
        ]
        comp = _make_component(config=config)
        result = comp.execute(_sample_df())
        main = result["main"]
        a_list = main.loc[main["dept"] == "A", "products"].iloc[0]
        assert isinstance(a_list, list), f"Expected list, got {type(a_list).__name__}: {a_list!r}"

    def test_list_custom_delimiter(self):
        config = dict(_DEFAULT_CONFIG)
        config["list_delimiter"] = "|"
        config["operations"] = [
            {"output_column": "products", "function": "list", "input_column": "product", "ignore_null": True},
        ]
        comp = _make_component(config=config)
        result = comp.execute(_sample_df())
        main = result["main"]
        a_list = main.loc[main["dept"] == "A", "products"].iloc[0]
        assert "|" in a_list
        assert "," not in a_list  # should use | not ,

    def test_median(self):
        config = dict(_DEFAULT_CONFIG)
        config["operations"] = [
            {"output_column": "med", "function": "median", "input_column": "amount", "ignore_null": True},
        ]
        comp = _make_component(config=config)
        result = comp.execute(_sample_df())
        main = result["main"]
        a_med = main.loc[main["dept"] == "A", "med"].iloc[0]
        assert a_med == pytest.approx(150.0)  # median of 100, 200

    def test_variance(self):
        config = dict(_DEFAULT_CONFIG)
        config["operations"] = [
            {"output_column": "var", "function": "variance", "input_column": "amount", "ignore_null": True},
        ]
        comp = _make_component(config=config)
        result = comp.execute(_sample_df())
        main = result["main"]
        a_var = main.loc[main["dept"] == "A", "var"].iloc[0]
        # variance of [100, 200] with ddof=1 = 5000
        assert a_var == pytest.approx(5000.0)

    def test_std_dev_sample(self):
        config = dict(_DEFAULT_CONFIG)
        config["operations"] = [
            {"output_column": "sd", "function": "std", "input_column": "amount", "ignore_null": True},
        ]
        comp = _make_component(config=config)
        result = comp.execute(_sample_df())
        main = result["main"]
        a_std = main.loc[main["dept"] == "A", "sd"].iloc[0]
        # std of [100, 200] with ddof=1 ~ 70.71
        assert a_std == pytest.approx(70.710678, rel=1e-3)

    def test_population_std_dev(self):
        """AGGR-04, D-10: population_std_dev with ddof=0 produces different result than std."""
        config = dict(_DEFAULT_CONFIG)
        config["operations"] = [
            {"output_column": "pop_std", "function": "population_std_dev", "input_column": "amount", "ignore_null": True},
            {"output_column": "sample_std", "function": "std", "input_column": "amount", "ignore_null": True},
        ]
        comp = _make_component(config=config)
        result = comp.execute(_sample_df())
        main = result["main"]
        a_pop = main.loc[main["dept"] == "A", "pop_std"].iloc[0]
        a_sample = main.loc[main["dept"] == "A", "sample_std"].iloc[0]
        # population std of [100, 200] = 50.0; sample std ~ 70.71
        assert a_pop == pytest.approx(50.0)
        assert a_sample == pytest.approx(70.710678, rel=1e-3)
        assert a_pop != a_sample  # they must differ

    def test_union_deduplicates(self):
        """CR-05-bis: union deduplicates and sorts distinct values before joining.

        Unlike list (which preserves duplicates), union produces sorted unique values.
        Sample data: dept A has products [x, y], B has [x, y, z].
        No duplicates in _sample_df, so union = sorted(set(...)) = same as sorted list.
        """
        config = dict(_DEFAULT_CONFIG)
        config["operations"] = [
            {"output_column": "products", "function": "union", "input_column": "product", "ignore_null": True},
        ]
        comp = _make_component(config=config)
        result = comp.execute(_sample_df())
        main = result["main"]
        a_union = main.loc[main["dept"] == "A", "products"].iloc[0]
        assert isinstance(a_union, str), f"Expected str, got {type(a_union).__name__}: {a_union!r}"
        # sorted distinct values for A: [x, y] -> "x,y"
        assert a_union == "x,y"


# ------------------------------------------------------------------
# TestFinancialPrecision -- covers AGGR-06, AGGR-07
# ------------------------------------------------------------------


@pytest.mark.unit
class TestFinancialPrecision:
    """Decimal arithmetic when use_financial_precision=True."""

    def test_decimal_sum(self):
        """AGGR-07: use_financial_precision=True produces Decimal sum."""
        config = dict(_DEFAULT_CONFIG)
        config["use_financial_precision"] = True
        comp = _make_component(config=config)
        result = comp.execute(_sample_df())
        main = result["main"]
        a_total = main.loc[main["dept"] == "A", "total"].iloc[0]
        assert isinstance(a_total, Decimal)
        assert a_total == Decimal("300")

    def test_decimal_avg(self):
        """AGGR-07: use_financial_precision=True produces correct Decimal mean."""
        config = dict(_DEFAULT_CONFIG)
        config["use_financial_precision"] = True
        config["operations"] = [
            {"output_column": "avg_amt", "function": "avg", "input_column": "amount", "ignore_null": True},
        ]
        comp = _make_component(config=config)
        result = comp.execute(_sample_df())
        main = result["main"]
        a_avg = main.loc[main["dept"] == "A", "avg_amt"].iloc[0]
        assert isinstance(a_avg, Decimal)
        assert float(a_avg) == pytest.approx(150.0)

    def test_decimal_std(self):
        """AGGR-06, AGGR-07: use_financial_precision=True computes std with Decimal arithmetic."""
        config = dict(_DEFAULT_CONFIG)
        config["use_financial_precision"] = True
        config["operations"] = [
            {"output_column": "sd", "function": "std", "input_column": "amount", "ignore_null": True},
        ]
        comp = _make_component(config=config)
        result = comp.execute(_sample_df())
        main = result["main"]
        a_std = main.loc[main["dept"] == "A", "sd"].iloc[0]
        assert isinstance(a_std, Decimal)
        assert float(a_std) == pytest.approx(70.710678, rel=1e-3)

    def test_non_financial_uses_float(self):
        config = dict(_DEFAULT_CONFIG)
        config["use_financial_precision"] = False
        comp = _make_component(config=config)
        result = comp.execute(_sample_df())
        main = result["main"]
        a_total = main.loc[main["dept"] == "A", "total"].iloc[0]
        assert isinstance(a_total, (float, np.floating, int, np.integer))


# ------------------------------------------------------------------
# TestEdgeCases
# ------------------------------------------------------------------


@pytest.mark.unit
class TestEdgeCases:
    """Edge cases for empty data, single row, all-null columns."""

    def test_empty_input(self):
        comp = _make_component()
        result = comp.execute(pd.DataFrame())
        assert result["main"].empty

    def test_none_input(self):
        comp = _make_component()
        result = comp.execute(None)
        assert result["main"].empty

    def test_single_row(self):
        df = pd.DataFrame({"department": ["A"], "amount": [42.0]})
        comp = _make_component()
        result = comp.execute(df)
        main = result["main"]
        assert len(main) == 1
        assert main["total"].iloc[0] == 42.0

    def test_all_null_column_ignore_true(self):
        df = pd.DataFrame({
            "department": ["A", "A"],
            "amount": [np.nan, np.nan],
        })
        config = dict(_DEFAULT_CONFIG)
        config["operations"] = [
            {"output_column": "total", "function": "sum", "input_column": "amount", "ignore_null": True},
        ]
        comp = _make_component(config=config)
        result = comp.execute(df)
        main = result["main"]
        # Sum of nothing should be 0 (pandas skipna=True behavior)
        assert len(main) == 1
        # Decimal("0") or 0.0 both acceptable
        total = main["total"].iloc[0]
        assert total == 0 or total == Decimal("0")

    def test_all_null_column_ignore_false(self):
        df = pd.DataFrame({
            "department": ["A", "A"],
            "amount": [np.nan, np.nan],
        })
        config = dict(_DEFAULT_CONFIG)
        config["operations"] = [
            {"output_column": "total", "function": "sum", "input_column": "amount", "ignore_null": False},
        ]
        comp = _make_component(config=config)
        result = comp.execute(df)
        main = result["main"]
        total = main["total"].iloc[0]
        assert pd.isna(total), "All-null sum with ignore_null=False should be NaN"

    def test_stats_updated(self):
        gm = GlobalMap()
        comp = _make_component(global_map=gm)
        comp.execute(_sample_df())
        # Phase 7.1-01 BaseComponent contract: when _update_stats() is called from
        # _process(), _stats_set_by_component=True so _update_stats_from_result() skips.
        # NB_LINE = 5 (input rows, set by _process)
        # NB_LINE_OK = 2 (output groups, set by _process)
        assert gm.get_nb_line("tAgg_1") == 5
        assert gm.get_nb_line_ok("tAgg_1") == 2


# ------------------------------------------------------------------
# TestListObject -- covers CR-05 (supersedes Phase 6 D-09)
# ------------------------------------------------------------------


@pytest.mark.unit
class TestListObject:
    """list_object returns Python list, NOT delimited string.

    CR-05: Talaxie tAggregateRow_messages.properties:
    LIST_DELIMITER.NAME=Delimiter (only for list operation)
    list_delimiter does NOT apply to list_object.
    Phase 6 D-09 was wrong; this test enforces the corrected behavior.
    """

    def test_returns_list(self):
        """list_object produces a Python list, not a delimited string."""
        config = dict(_DEFAULT_CONFIG)
        config["groupbys"] = [{"output_column": "grp", "input_column": "group_col"}]
        config["operations"] = [
            {"output_column": "items", "function": "list_object", "input_column": "value", "ignore_null": True},
        ]
        df = pd.DataFrame({
            "group_col": ["g1", "g1", "g1", "g1"],
            "value": ["a", "b", "a", "c"],
        })
        comp = _make_component(config=config)
        result = comp.execute(df)
        main = result["main"]
        items = main.loc[main["grp"] == "g1", "items"].iloc[0]
        assert isinstance(items, list), f"Expected list, got {type(items).__name__}: {items!r}"
        assert items == ["a", "b", "a", "c"]

    def test_ignore_null_drops_na(self):
        """list_object with ignore_null=True drops NaN values from list."""
        config = dict(_DEFAULT_CONFIG)
        config["groupbys"] = [{"output_column": "grp", "input_column": "group_col"}]
        config["operations"] = [
            {"output_column": "items", "function": "list_object", "input_column": "value", "ignore_null": True},
        ]
        df = pd.DataFrame({
            "group_col": ["g1", "g1", "g1", "g1"],
            "value": ["a", "b", np.nan, "c"],
        })
        comp = _make_component(config=config)
        result = comp.execute(df)
        main = result["main"]
        items = main.loc[main["grp"] == "g1", "items"].iloc[0]
        assert isinstance(items, list), f"Expected list, got {type(items).__name__}: {items!r}"
        assert items == ["a", "b", "c"]
        assert len(items) == 3  # NaN dropped


# ------------------------------------------------------------------
# TestUnion -- covers CR-05-bis
# ------------------------------------------------------------------


@pytest.mark.unit
class TestUnion:
    """union deduplicates, sorts, then joins with list_delimiter.

    CR-05-bis: Talend union aggregator collects distinct values.
    Unlike list (which preserves duplicates), union produces sorted unique values.
    """

    def test_distinct_join(self):
        """union deduplicates and sorts before joining with delimiter."""
        config = dict(_DEFAULT_CONFIG)
        config["groupbys"] = [{"output_column": "grp", "input_column": "group_col"}]
        config["list_delimiter"] = ","
        config["operations"] = [
            {"output_column": "items", "function": "union", "input_column": "value", "ignore_null": True},
        ]
        df = pd.DataFrame({
            "group_col": ["g1", "g1", "g1", "g1"],
            "value": ["a", "b", "a", "c"],
        })
        comp = _make_component(config=config)
        result = comp.execute(df)
        main = result["main"]
        items = main.loc[main["grp"] == "g1", "items"].iloc[0]
        assert isinstance(items, str), f"Expected str, got {type(items).__name__}: {items!r}"
        assert items == "a,b,c"  # sorted distinct values, joined

    def test_dedupe_with_nulls(self):
        """union with ignore_null=True drops NaN before deduplicating."""
        config = dict(_DEFAULT_CONFIG)
        config["groupbys"] = [{"output_column": "grp", "input_column": "group_col"}]
        config["list_delimiter"] = ","
        config["operations"] = [
            {"output_column": "items", "function": "union", "input_column": "value", "ignore_null": True},
        ]
        df = pd.DataFrame({
            "group_col": ["g1", "g1", "g1", "g1"],
            "value": [1.0, 2.0, 1.0, np.nan],
        })
        comp = _make_component(config=config)
        result = comp.execute(df)
        main = result["main"]
        items = main.loc[main["grp"] == "g1", "items"].iloc[0]
        assert isinstance(items, str), f"Expected str, got {type(items).__name__}: {items!r}"
        assert items == "1.0,2.0"  # NaN dropped, sorted distinct, joined


# ------------------------------------------------------------------
# TestMedian -- covers WR-09
# ------------------------------------------------------------------


@pytest.mark.unit
class TestMedian:
    """median with use_financial_precision warns once when falling back to float.

    WR-09: Decimal median is genuinely complex. Engine falls back to float median.
    For regulatory/financial use cases with use_financial_precision=True, the
    precision loss must be visible to operators via a logged warning.
    """

    def test_decimal_warns_once(self, caplog):
        """median + use_financial_precision=True logs exactly one warning per execute()."""
        import logging
        config = dict(_DEFAULT_CONFIG)
        config["use_financial_precision"] = True
        config["groupbys"] = []
        config["operations"] = [
            {"output_column": "med", "function": "median", "input_column": "amount", "ignore_null": True},
        ]
        df = pd.DataFrame({"amount": [100.0, 200.0, 150.0]})
        comp = _make_component(config=config)

        with caplog.at_level(logging.WARNING, logger="src.v1.engine.components.aggregate.aggregate_row"):
            result = comp.execute(df)

        # Warning must fire exactly once per execute()
        warn_records = [r for r in caplog.records if "median" in r.message.lower() and "precision" in r.message.lower()]
        assert len(warn_records) == 1, (
            f"Expected exactly 1 warning about median+precision, got {len(warn_records)}: "
            f"{[r.message for r in warn_records]}"
        )

        # Result must still be computed (not None)
        main = result["main"]
        med = main["med"].iloc[0]
        assert med is not None
        assert not (isinstance(med, float) and np.isnan(med))
        assert med == pytest.approx(150.0)


# ------------------------------------------------------------------
# TestOrdering -- covers WR-11
# ------------------------------------------------------------------


@pytest.mark.unit
class TestOrdering:
    """groupby sort=False preserves input-order (first-seen) group ordering.

    WR-11: Talend tAggregateRow uses LinkedHashMap internally, which preserves
    insertion order (first-seen group ordering). groupby(sort=True) alphabetizes
    output by group key, breaking job output ordering for downstream components.
    Fix: groupby(sort=False).
    """

    def test_input_order_preserved(self):
        """Groups appear in input-first-seen order, not alphabetical order."""
        config = dict(_DEFAULT_CONFIG)
        config["groupbys"] = [{"output_column": "grp", "input_column": "group_col"}]
        config["operations"] = [
            {"output_column": "total", "function": "sum", "input_column": "val", "ignore_null": True},
        ]
        # Input order: c, a, b (NOT alphabetical a, b, c)
        df = pd.DataFrame({
            "group_col": ["c", "c", "a", "a", "b", "b"],
            "val": [10.0, 20.0, 30.0, 40.0, 50.0, 60.0],
        })
        comp = _make_component(config=config)
        result = comp.execute(df)
        main = result["main"]
        # Expected: c first, then a, then b (input first-seen order)
        assert list(main["grp"]) == ["c", "a", "b"], (
            f"Expected input-order grouping [c, a, b], got {list(main['grp'])!r}"
        )
        assert main.loc[main["grp"] == "c", "total"].iloc[0] == 30.0
        assert main.loc[main["grp"] == "a", "total"].iloc[0] == 70.0
        assert main.loc[main["grp"] == "b", "total"].iloc[0] == 110.0


# ------------------------------------------------------------------
# TestCountIgnoreNull -- covers WR-10 regression guard
# ------------------------------------------------------------------


@pytest.mark.unit
class TestCountIgnoreNull:
    """Regression guard: count = non-null count regardless of ignore_null.

    WR-10 WRONG finding (per RESEARCH.md verdict): The audit claimed count +
    ignore_null=False should count all rows including nulls. This is incorrect.

    SQL convention: COUNT(col) = non-null count regardless of any null-handling flag.
    Talend docs (help.qlik.com/talend tAggregateRow): "count = counts the number
    of rows" -- no specification of null inclusion under ignore_null=False.

    No public Talend job-runtime source available to verify alternative behavior.
    Current behavior (count = non-null) matches SQL convention and is kept.
    This test is a regression guard so future audits do not re-flag this as a bug.
    """

    def test_count_ignores_null_regardless(self):
        """count returns non-null count even when ignore_null=False.

        WR-10 REGRESSION GUARD: DO NOT change this to return 3 (all rows).
        See RESEARCH.md verdict and 07.1-06-SUMMARY.md WRONG findings table.
        Talend docs: help.qlik.com/talend tAggregateRow
        """
        config = dict(_DEFAULT_CONFIG)
        config["groupbys"] = []
        config["operations"] = [
            {"output_column": "cnt", "function": "count", "input_column": "value", "ignore_null": False},
        ]
        df = pd.DataFrame({"value": [1.0, np.nan, 2.0]})
        comp = _make_component(config=config)
        result = comp.execute(df)
        main = result["main"]
        cnt = main["cnt"].iloc[0]
        # count = non-null count = 2, NOT 3 (WR-10 WRONG finding)
        assert cnt == 2, (
            f"count should return non-null count (2), not all-rows count (3). "
            f"Got {cnt!r}. See WR-10 REGRESSION GUARD docstring."
        )


# ------------------------------------------------------------------
# TestRegistration -- covers AGGR-09
# ------------------------------------------------------------------


@pytest.mark.unit
class TestRegistration:
    """Component registry registration."""

    def test_registered_as_aggregate_row(self):
        cls = REGISTRY.get("AggregateRow")
        assert cls is AggregateRow

    def test_registered_as_t_aggregate_row(self):
        cls = REGISTRY.get("tAggregateRow")
        assert cls is AggregateRow
