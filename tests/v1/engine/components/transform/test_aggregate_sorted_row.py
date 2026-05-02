"""Tests for AggregateSortedRow (tAggregateSortedRow engine implementation)."""
from decimal import Decimal

import pytest
import pandas as pd

from src.v1.engine.components.transform.aggregate_sorted_row import AggregateSortedRow
from src.v1.engine.component_registry import REGISTRY
from src.v1.engine.context_manager import ContextManager
from src.v1.engine.exceptions import ConfigurationError
from src.v1.engine.global_map import GlobalMap


# ------------------------------------------------------------------
# Test helpers
# ------------------------------------------------------------------

_DEFAULT_CONFIG = {
    "component_type": "AggregateSortedRow",
    "groupbys": [{"output_column": "dept", "input_column": "department"}],
    "operations": [
        {"output_column": "total", "function": "sum", "input_column": "amount", "ignore_null": True},
    ],
    "list_delimiter": ",",
    "use_financial_precision": False,
}


def _make_component(config=None, global_map=None, schema=None):
    """Create an AggregateSortedRow with test defaults."""
    gm = global_map if global_map is not None else GlobalMap()
    cm = ContextManager()
    comp = AggregateSortedRow(
        component_id="tAggSorted_1",
        config=config or dict(_DEFAULT_CONFIG),
        global_map=gm,
        context_manager=cm,
    )
    comp.output_schema = schema
    return comp


def _sample_df():
    """Pre-sorted test DataFrame (sorted by department, as Talend requires)."""
    return pd.DataFrame({
        "department": ["A", "A", "B", "B", "B"],
        "product": ["x", "y", "x", "y", "z"],
        "amount": [100.0, 200.0, 150.0, 250.0, 300.0],
        "quantity": [1, 2, 3, 4, 5],
    })


# ------------------------------------------------------------------
# TestRegistration
# ------------------------------------------------------------------

@pytest.mark.unit
class TestRegistration:
    """Registry decorator places component under both V1 and Talend names."""

    def test_v1_name_registered(self):
        assert REGISTRY.get("AggregateSortedRow") is AggregateSortedRow

    def test_talend_alias_registered(self):
        assert REGISTRY.get("tAggregateSortedRow") is AggregateSortedRow

    def test_inherits_base_component(self):
        from src.v1.engine.base_component import BaseComponent
        assert issubclass(AggregateSortedRow, BaseComponent)


# ------------------------------------------------------------------
# TestValidation
# ------------------------------------------------------------------

@pytest.mark.unit
class TestValidation:
    """_validate_config() catches structural errors only (Rule 12)."""

    def test_operations_not_a_list_raises(self):
        config = dict(_DEFAULT_CONFIG)
        config["operations"] = "not_a_list"
        comp = _make_component(config=config)
        with pytest.raises(ConfigurationError, match="operations.*list"):
            comp.execute(_sample_df())

    def test_operation_not_a_dict_raises(self):
        config = dict(_DEFAULT_CONFIG)
        config["operations"] = ["bad_entry"]
        comp = _make_component(config=config)
        with pytest.raises(ConfigurationError, match="must be a dict"):
            comp.execute(_sample_df())

    def test_groupbys_not_a_list_raises(self):
        config = dict(_DEFAULT_CONFIG)
        config["groupbys"] = "department"
        comp = _make_component(config=config)
        with pytest.raises(ConfigurationError, match="groupbys.*list"):
            comp.execute(_sample_df())

    def test_validate_config_returns_none(self):
        """_validate_config must return None (not a list) per Rule 2."""
        comp = _make_component()
        result = comp._validate_config()
        assert result is None

    def test_unsupported_function_raises_in_process(self):
        """Unknown function caught in _process after resolution."""
        config = dict(_DEFAULT_CONFIG)
        config["operations"] = [
            {"output_column": "x", "function": "bogus_func", "input_column": "amount"},
        ]
        comp = _make_component(config=config)
        with pytest.raises(ConfigurationError, match="unsupported function"):
            comp.execute(_sample_df())

    def test_missing_function_key_raises(self):
        config = dict(_DEFAULT_CONFIG)
        config["operations"] = [{"output_column": "x", "input_column": "amount"}]
        comp = _make_component(config=config)
        with pytest.raises(ConfigurationError, match="missing required key 'function'"):
            comp.execute(_sample_df())

    def test_missing_input_column_key_raises(self):
        config = dict(_DEFAULT_CONFIG)
        config["operations"] = [{"output_column": "x", "function": "sum"}]
        comp = _make_component(config=config)
        with pytest.raises(ConfigurationError, match="missing required key 'input_column'"):
            comp.execute(_sample_df())

    def test_empty_operations_raises_in_process(self):
        """Empty operations list is deferred to _process (Rule 12)."""
        config = dict(_DEFAULT_CONFIG)
        config["operations"] = []
        comp = _make_component(config=config)
        with pytest.raises(ConfigurationError, match="non-empty list"):
            comp.execute(_sample_df())


# ------------------------------------------------------------------
# TestCoreGrouped
# ------------------------------------------------------------------

@pytest.mark.unit
class TestCoreGrouped:
    """Grouped aggregation — happy paths."""

    def test_grouped_sum(self):
        comp = _make_component()
        result = comp.execute(_sample_df())
        df = result["main"]
        assert list(df.columns) == ["dept", "total"]
        row_a = df[df["dept"] == "A"]["total"].iloc[0]
        row_b = df[df["dept"] == "B"]["total"].iloc[0]
        assert row_a == pytest.approx(300.0)
        assert row_b == pytest.approx(700.0)

    def test_grouped_count(self):
        config = dict(_DEFAULT_CONFIG)
        config["operations"] = [
            {"output_column": "cnt", "function": "count", "input_column": "amount"},
        ]
        comp = _make_component(config=config)
        result = comp.execute(_sample_df())
        df = result["main"]
        assert df[df["dept"] == "A"]["cnt"].iloc[0] == 2
        assert df[df["dept"] == "B"]["cnt"].iloc[0] == 3

    def test_grouped_min_max(self):
        config = dict(_DEFAULT_CONFIG)
        config["operations"] = [
            {"output_column": "lo", "function": "min", "input_column": "amount"},
            {"output_column": "hi", "function": "max", "input_column": "amount"},
        ]
        comp = _make_component(config=config)
        result = comp.execute(_sample_df())
        df = result["main"]
        row_b = df[df["dept"] == "B"].iloc[0]
        assert row_b["lo"] == pytest.approx(150.0)
        assert row_b["hi"] == pytest.approx(300.0)

    def test_grouped_avg(self):
        config = dict(_DEFAULT_CONFIG)
        config["operations"] = [
            {"output_column": "avg_amt", "function": "avg", "input_column": "amount"},
        ]
        comp = _make_component(config=config)
        result = comp.execute(_sample_df())
        df = result["main"]
        assert df[df["dept"] == "A"]["avg_amt"].iloc[0] == pytest.approx(150.0)

    def test_grouped_first_last(self):
        config = dict(_DEFAULT_CONFIG)
        config["operations"] = [
            {"output_column": "first_prod", "function": "first", "input_column": "product"},
            {"output_column": "last_prod", "function": "last", "input_column": "product"},
        ]
        comp = _make_component(config=config)
        result = comp.execute(_sample_df())
        df = result["main"]
        row_b = df[df["dept"] == "B"].iloc[0]
        assert row_b["first_prod"] == "x"
        assert row_b["last_prod"] == "z"

    def test_grouped_count_distinct(self):
        config = dict(_DEFAULT_CONFIG)
        config["operations"] = [
            {"output_column": "uniq", "function": "count_distinct", "input_column": "product"},
        ]
        comp = _make_component(config=config)
        result = comp.execute(_sample_df())
        df = result["main"]
        assert df[df["dept"] == "A"]["uniq"].iloc[0] == 2
        assert df[df["dept"] == "B"]["uniq"].iloc[0] == 3

    def test_grouped_list_function(self):
        config = dict(_DEFAULT_CONFIG)
        config["operations"] = [
            {"output_column": "products", "function": "list", "input_column": "product"},
        ]
        comp = _make_component(config=config)
        result = comp.execute(_sample_df())
        df = result["main"]
        val_a = df[df["dept"] == "A"]["products"].iloc[0]
        # list function returns delimiter-joined string by default
        assert "x" in val_a and "y" in val_a

    def test_column_order_group_then_ops(self):
        """Group-by columns come first, then operation output columns."""
        comp = _make_component()
        result = comp.execute(_sample_df())
        cols = list(result["main"].columns)
        assert cols.index("dept") < cols.index("total")

    def test_output_has_only_declared_columns(self):
        """Output contains only group-by outputs + operation outputs, no extra columns."""
        comp = _make_component()
        result = comp.execute(_sample_df())
        assert set(result["main"].columns) == {"dept", "total"}

    def test_reject_key_always_present(self):
        """Rule 3: result must have 'reject' key."""
        comp = _make_component()
        result = comp.execute(_sample_df())
        assert "reject" in result
        assert result["reject"] is None

    def test_group_by_column_renaming(self):
        """ENG-ASR-003: output_column may differ from input_column in groupbys."""
        config = dict(_DEFAULT_CONFIG)
        config["groupbys"] = [{"output_column": "dept_out", "input_column": "department"}]
        comp = _make_component(config=config)
        result = comp.execute(_sample_df())
        df = result["main"]
        assert "dept_out" in df.columns
        assert "department" not in df.columns

    def test_ignore_null_false_propagates(self):
        """ENG-ASR-001: ignore_null=False propagates NaN into sum result."""
        data = pd.DataFrame({
            "department": ["A", "A"],
            "amount": [100.0, None],
        })
        config = dict(_DEFAULT_CONFIG)
        config["groupbys"] = [{"output_column": "department", "input_column": "department"}]
        config["operations"] = [
            {"output_column": "total", "function": "sum", "input_column": "amount", "ignore_null": False},
        ]
        comp = _make_component(config=config)
        result = comp.execute(data)
        df = result["main"]
        # When ignore_null=False and a null exists, result should be NaN/None
        assert pd.isna(df["total"].iloc[0])

    def test_ignore_null_true_skips_nulls(self):
        """ENG-ASR-001: ignore_null=True (default) skips NaN in sum."""
        data = pd.DataFrame({
            "department": ["A", "A"],
            "amount": [100.0, None],
        })
        config = dict(_DEFAULT_CONFIG)
        config["groupbys"] = [{"output_column": "department", "input_column": "department"}]
        config["operations"] = [
            {"output_column": "total", "function": "sum", "input_column": "amount", "ignore_null": True},
        ]
        comp = _make_component(config=config)
        result = comp.execute(data)
        df = result["main"]
        assert df["total"].iloc[0] == pytest.approx(100.0)

    def test_multiple_group_by_columns(self):
        """Multiple group-by columns produce correct composite keys."""
        config = dict(_DEFAULT_CONFIG)
        config["groupbys"] = [
            {"output_column": "dept", "input_column": "department"},
            {"output_column": "prod", "input_column": "product"},
        ]
        config["operations"] = [
            {"output_column": "total", "function": "sum", "input_column": "amount"},
        ]
        comp = _make_component(config=config)
        result = comp.execute(_sample_df())
        df = result["main"]
        # Each (dept, product) pair is its own group in sorted input
        assert len(df) == 5

    def test_preserves_first_seen_group_order(self):
        """sort=False preserves insertion order (Talend LinkedHashMap behaviour)."""
        data = pd.DataFrame({
            "department": ["B", "B", "A", "A"],
            "amount": [10.0, 20.0, 5.0, 15.0],
        })
        config = dict(_DEFAULT_CONFIG)
        comp = _make_component(config=config)
        result = comp.execute(data)
        # First group seen should be B
        assert result["main"]["dept"].iloc[0] == "B"


# ------------------------------------------------------------------
# TestCoreUngrouped
# ------------------------------------------------------------------

@pytest.mark.unit
class TestCoreUngrouped:
    """No group-by columns — aggregate entire dataset to one row."""

    def _make_ungrouped(self, function="sum", output_col="total", use_fp=False):
        config = {
            "component_type": "AggregateSortedRow",
            "groupbys": [],
            "operations": [
                {"output_column": output_col, "function": function, "input_column": "amount"},
            ],
            "list_delimiter": ",",
            "use_financial_precision": use_fp,
        }
        return _make_component(config=config)

    def test_ungrouped_sum(self):
        comp = self._make_ungrouped("sum")
        result = comp.execute(_sample_df())
        df = result["main"]
        assert len(df) == 1
        assert df["total"].iloc[0] == pytest.approx(1000.0)

    def test_ungrouped_count(self):
        comp = self._make_ungrouped("count")
        result = comp.execute(_sample_df())
        assert result["main"]["total"].iloc[0] == 5

    def test_ungrouped_returns_single_row(self):
        comp = self._make_ungrouped("max")
        result = comp.execute(_sample_df())
        assert len(result["main"]) == 1

    def test_ungrouped_avg(self):
        comp = self._make_ungrouped("avg")
        result = comp.execute(_sample_df())
        assert result["main"]["total"].iloc[0] == pytest.approx(200.0)

    def test_ungrouped_with_financial_precision(self):
        """BUG-ASR-001 (fixed): empty group_bys with financial_precision must work."""
        comp = self._make_ungrouped("sum", use_fp=True)
        result = comp.execute(_sample_df())
        assert len(result["main"]) == 1
        # Result may be Decimal but should equal 1000
        val = result["main"]["total"].iloc[0]
        assert float(val) == pytest.approx(1000.0)


# ------------------------------------------------------------------
# TestEdgeCases
# ------------------------------------------------------------------

@pytest.mark.unit
class TestEdgeCases:
    """Edge cases: None/empty input, nulls, single-row groups."""

    def test_none_input_returns_empty_df(self):
        comp = _make_component()
        result = comp.execute(None)
        assert isinstance(result["main"], pd.DataFrame)
        assert result["main"].empty

    def test_empty_df_returns_empty_df(self):
        comp = _make_component()
        result = comp.execute(pd.DataFrame({"department": [], "amount": []}))
        assert result["main"].empty

    def test_single_group_all_rows(self):
        data = pd.DataFrame({
            "department": ["A", "A", "A"],
            "amount": [10.0, 20.0, 30.0],
        })
        comp = _make_component()
        result = comp.execute(data)
        df = result["main"]
        assert len(df) == 1
        assert df["total"].iloc[0] == pytest.approx(60.0)

    def test_single_row_input(self):
        data = pd.DataFrame({"department": ["A"], "amount": [42.0]})
        comp = _make_component()
        result = comp.execute(data)
        df = result["main"]
        assert len(df) == 1
        assert df["total"].iloc[0] == pytest.approx(42.0)

    def test_all_nulls_in_agg_column(self):
        data = pd.DataFrame({
            "department": ["A", "A"],
            "amount": [None, None],
        })
        config = dict(_DEFAULT_CONFIG)
        config["operations"] = [
            {"output_column": "total", "function": "sum", "input_column": "amount", "ignore_null": True},
        ]
        comp = _make_component(config=config)
        result = comp.execute(data)
        # pandas sum of all-NaN with skipna=True returns 0
        assert result["main"]["total"].iloc[0] == pytest.approx(0.0)

    def test_group_by_column_not_in_df_skipped(self):
        """Non-existent group-by column: groupby silently skips or raises; verify no crash."""
        config = dict(_DEFAULT_CONFIG)
        config["groupbys"] = [{"output_column": "missing", "input_column": "missing_col"}]
        comp = _make_component(config=config)
        # Should raise a KeyError from pandas — not a silent wrong answer
        with pytest.raises(Exception):
            comp.execute(_sample_df())

    def test_no_original_columns_leaked_to_output(self):
        """Output must not contain passthrough columns not in groupbys or operations."""
        comp = _make_component()
        result = comp.execute(_sample_df())
        # 'product' and 'quantity' are in the input but not declared in groupbys/operations
        assert "product" not in result["main"].columns
        assert "quantity" not in result["main"].columns


# ------------------------------------------------------------------
# TestStatistics
# ------------------------------------------------------------------

@pytest.mark.unit
class TestStatistics:
    """GlobalMap stats updated correctly after execution."""

    def test_nb_line_equals_input_rows(self):
        gm = GlobalMap()
        comp = _make_component(global_map=gm)
        comp.execute(_sample_df())
        assert gm.get_nb_line("tAggSorted_1") == 5

    def test_nb_line_ok_equals_output_rows(self):
        gm = GlobalMap()
        comp = _make_component(global_map=gm)
        comp.execute(_sample_df())
        assert gm.get_nb_line_ok("tAggSorted_1") == 2  # 2 groups (A, B)

    def test_nb_line_reject_is_zero(self):
        gm = GlobalMap()
        comp = _make_component(global_map=gm)
        comp.execute(_sample_df())
        assert gm.get_nb_line_reject("tAggSorted_1") == 0

    def test_stats_not_double_counted(self):
        """Component calls _update_stats manually; base class must NOT add again."""
        gm = GlobalMap()
        comp = _make_component(global_map=gm)
        comp.execute(_sample_df())
        # NB_LINE should be exactly 5 (input rows), not 10
        assert gm.get_nb_line("tAggSorted_1") == 5

    def test_empty_input_stats_zero(self):
        gm = GlobalMap()
        comp = _make_component(global_map=gm)
        comp.execute(None)
        assert gm.get_nb_line("tAggSorted_1") == 0
        assert gm.get_nb_line_ok("tAggSorted_1") == 0
        assert gm.get_nb_line_reject("tAggSorted_1") == 0
