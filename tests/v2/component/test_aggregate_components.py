"""
Tests for v2 Aggregate components (Aggregate) and transform UniqRow (fka Unique).

These tests validate the rewritten V2 components that use
TransformComponent base class and register with REGISTRY.
"""
import pytest
import polars as pl

from src.v2.components.aggregate import Aggregate
from src.v2.components.aggregate.unique_component import Unique  # deprecation stub -> UniqRow


class TestAggregate:
    """Test Aggregate component."""

    def test_group_by_single_column_sum(self):
        """Test group by a single column with sum aggregation."""
        comp = Aggregate("agg1", {
            "group_by": ["category"],
            "aggregations": [
                {"name": "total", "function": "sum", "column": "amount"},
            ],
        })
        df = pl.DataFrame({
            "category": ["A", "A", "B", "B"],
            "amount": [100, 200, 150, 50],
        }).lazy()
        result = comp.apply({"main": df})
        assert "main" in result
        assert isinstance(result["main"], pl.LazyFrame)
        collected = result["main"].collect().sort("category")
        assert len(collected) == 2
        assert collected["total"].to_list() == [300, 200]

    def test_group_by_multiple_columns_multiple_functions(self):
        """Test group by multiple columns with multiple aggregation functions."""
        comp = Aggregate("agg2", {
            "group_by": ["product", "region"],
            "aggregations": [
                {"name": "total_qty", "function": "sum", "column": "quantity"},
                {"name": "avg_price", "function": "avg", "column": "price"},
                {"name": "order_count", "function": "count", "column": "order_id"},
            ],
        })
        df = pl.DataFrame({
            "order_id": [1, 2, 3, 4],
            "product": ["Widget", "Widget", "Widget", "Gadget"],
            "region": ["East", "East", "West", "East"],
            "quantity": [5, 3, 2, 4],
            "price": [10.0, 10.0, 15.0, 25.0],
        }).lazy()
        result = comp.apply({"main": df})
        collected = result["main"].collect().sort(["product", "region"])
        # Gadget/East: qty=4, avg_price=25, count=1
        gadget_east = collected.filter(
            (pl.col("product") == "Gadget") & (pl.col("region") == "East")
        )
        assert gadget_east["total_qty"][0] == 4
        assert gadget_east["avg_price"][0] == 25.0
        assert gadget_east["order_count"][0] == 1
        # Widget/East: qty=8, avg_price=10, count=2
        widget_east = collected.filter(
            (pl.col("product") == "Widget") & (pl.col("region") == "East")
        )
        assert widget_east["total_qty"][0] == 8
        assert widget_east["avg_price"][0] == 10.0
        assert widget_east["order_count"][0] == 2

    def test_no_group_by_global_aggregate(self):
        """Test aggregation without group_by (aggregate entire dataset)."""
        comp = Aggregate("agg3", {
            "aggregations": [
                {"name": "total", "function": "sum", "column": "amount"},
                {"name": "avg_amount", "function": "avg", "column": "amount"},
            ],
        })
        df = pl.DataFrame({
            "id": [1, 2, 3],
            "amount": [100, 200, 300],
        }).lazy()
        result = comp.apply({"main": df})
        collected = result["main"].collect()
        assert len(collected) == 1
        assert collected["total"][0] == 600
        assert collected["avg_amount"][0] == 200.0

    def test_count_star(self):
        """Test count with '*' (count all rows)."""
        comp = Aggregate("agg4", {
            "group_by": ["status"],
            "aggregations": [
                {"name": "row_count", "function": "count", "column": "*"},
            ],
        })
        df = pl.DataFrame({
            "id": [1, 2, 3, 4, 5],
            "status": ["active", "active", "inactive", "active", "inactive"],
        }).lazy()
        result = comp.apply({"main": df})
        collected = result["main"].collect().sort("status")
        active_row = collected.filter(pl.col("status") == "active")
        inactive_row = collected.filter(pl.col("status") == "inactive")
        assert active_row["row_count"][0] == 3
        assert inactive_row["row_count"][0] == 2

    def test_count_distinct(self):
        """Test count_distinct aggregation."""
        comp = Aggregate("agg5", {
            "group_by": ["department"],
            "aggregations": [
                {"name": "unique_roles", "function": "count_distinct", "column": "role"},
            ],
        })
        df = pl.DataFrame({
            "department": ["eng", "eng", "eng", "sales", "sales"],
            "role": ["dev", "dev", "qa", "rep", "rep"],
        }).lazy()
        result = comp.apply({"main": df})
        collected = result["main"].collect().sort("department")
        eng_row = collected.filter(pl.col("department") == "eng")
        sales_row = collected.filter(pl.col("department") == "sales")
        assert eng_row["unique_roles"][0] == 2  # dev, qa
        assert sales_row["unique_roles"][0] == 1  # rep

    def test_sum_function(self):
        """Test sum aggregation function."""
        comp = Aggregate("agg", {
            "group_by": ["g"],
            "aggregations": [{"name": "s", "function": "sum", "column": "v"}],
        })
        df = pl.DataFrame({"g": ["a", "a"], "v": [10, 20]}).lazy()
        result = comp.apply({"main": df})["main"].collect()
        assert result["s"][0] == 30

    def test_count_function(self):
        """Test count aggregation function (non-star)."""
        comp = Aggregate("agg", {
            "group_by": ["g"],
            "aggregations": [{"name": "c", "function": "count", "column": "v"}],
        })
        df = pl.DataFrame({"g": ["a", "a", "a"], "v": [1, 2, 3]}).lazy()
        result = comp.apply({"main": df})["main"].collect()
        assert result["c"][0] == 3

    def test_avg_function(self):
        """Test avg aggregation function."""
        comp = Aggregate("agg", {
            "group_by": ["g"],
            "aggregations": [{"name": "a", "function": "avg", "column": "v"}],
        })
        df = pl.DataFrame({"g": ["x", "x"], "v": [10.0, 20.0]}).lazy()
        result = comp.apply({"main": df})["main"].collect()
        assert result["a"][0] == 15.0

    def test_mean_function(self):
        """Test mean aggregation function (alias for avg)."""
        comp = Aggregate("agg", {
            "group_by": ["g"],
            "aggregations": [{"name": "m", "function": "mean", "column": "v"}],
        })
        df = pl.DataFrame({"g": ["x", "x"], "v": [10.0, 20.0]}).lazy()
        result = comp.apply({"main": df})["main"].collect()
        assert result["m"][0] == 15.0

    def test_min_function(self):
        """Test min aggregation function."""
        comp = Aggregate("agg", {
            "group_by": ["g"],
            "aggregations": [{"name": "mn", "function": "min", "column": "v"}],
        })
        df = pl.DataFrame({"g": ["a", "a", "a"], "v": [30, 10, 20]}).lazy()
        result = comp.apply({"main": df})["main"].collect()
        assert result["mn"][0] == 10

    def test_max_function(self):
        """Test max aggregation function."""
        comp = Aggregate("agg", {
            "group_by": ["g"],
            "aggregations": [{"name": "mx", "function": "max", "column": "v"}],
        })
        df = pl.DataFrame({"g": ["a", "a", "a"], "v": [30, 10, 20]}).lazy()
        result = comp.apply({"main": df})["main"].collect()
        assert result["mx"][0] == 30

    def test_first_function(self):
        """Test first aggregation function."""
        comp = Aggregate("agg", {
            "group_by": ["g"],
            "aggregations": [{"name": "f", "function": "first", "column": "v"}],
        })
        df = pl.DataFrame({"g": ["a", "a", "a"], "v": [10, 20, 30]}).lazy()
        result = comp.apply({"main": df})["main"].collect()
        assert result["f"][0] == 10

    def test_last_function(self):
        """Test last aggregation function."""
        comp = Aggregate("agg", {
            "group_by": ["g"],
            "aggregations": [{"name": "l", "function": "last", "column": "v"}],
        })
        df = pl.DataFrame({"g": ["a", "a", "a"], "v": [10, 20, 30]}).lazy()
        result = comp.apply({"main": df})["main"].collect()
        assert result["l"][0] == 30

    def test_std_function(self):
        """Test std aggregation function."""
        comp = Aggregate("agg", {
            "group_by": ["g"],
            "aggregations": [{"name": "sd", "function": "std", "column": "v"}],
        })
        df = pl.DataFrame({"g": ["a", "a", "a", "a"], "v": [10.0, 20.0, 30.0, 40.0]}).lazy()
        result = comp.apply({"main": df})["main"].collect()
        # std of [10,20,30,40] with ddof=1 is ~12.91
        assert result["sd"][0] == pytest.approx(12.909944, rel=1e-4)

    def test_var_function(self):
        """Test var aggregation function."""
        comp = Aggregate("agg", {
            "group_by": ["g"],
            "aggregations": [{"name": "vr", "function": "var", "column": "v"}],
        })
        df = pl.DataFrame({"g": ["a", "a", "a", "a"], "v": [10.0, 20.0, 30.0, 40.0]}).lazy()
        result = comp.apply({"main": df})["main"].collect()
        # var of [10,20,30,40] with ddof=1 is ~166.67
        assert result["vr"][0] == pytest.approx(166.6667, rel=1e-3)

    def test_median_function(self):
        """Test median aggregation function."""
        comp = Aggregate("agg", {
            "group_by": ["g"],
            "aggregations": [{"name": "med", "function": "median", "column": "v"}],
        })
        df = pl.DataFrame({"g": ["a", "a", "a"], "v": [10.0, 30.0, 20.0]}).lazy()
        result = comp.apply({"main": df})["main"].collect()
        assert result["med"][0] == 20.0

    def test_validate_missing_aggregations(self):
        """Test validation error when aggregations config is missing."""
        comp = Aggregate("agg", {})
        errors = comp.validate()
        assert len(errors) > 0
        assert "aggregations" in errors[0].lower()

    def test_validate_with_aggregations(self):
        """Test validation passes when aggregations config is present."""
        comp = Aggregate("agg", {
            "aggregations": [{"name": "total", "function": "sum", "column": "v"}],
        })
        errors = comp.validate()
        assert len(errors) == 0

    def test_validate_aggregations_not_list(self):
        """Validation: aggregations is not a list."""
        comp = Aggregate("agg", {"aggregations": "not_a_list"})
        errors = comp.validate()
        assert any("must be a list" in e for e in errors)

    def test_validate_aggregations_empty(self):
        """Validation: empty aggregations list."""
        comp = Aggregate("agg", {"aggregations": []})
        errors = comp.validate()
        assert any("must not be empty" in e for e in errors)

    def test_validate_agg_entry_not_dict(self):
        """Validation: aggregation entry is not a dict."""
        comp = Aggregate("agg", {"aggregations": ["not_a_dict"]})
        errors = comp.validate()
        assert any("must be a dict" in e for e in errors)

    def test_validate_agg_missing_name(self):
        """Validation: aggregation entry missing name."""
        comp = Aggregate("agg", {"aggregations": [{"function": "sum", "column": "v"}]})
        errors = comp.validate()
        assert any("requires 'name'" in e for e in errors)

    def test_validate_agg_missing_function(self):
        """Validation: aggregation entry missing function."""
        comp = Aggregate("agg", {"aggregations": [{"name": "total", "column": "v"}]})
        errors = comp.validate()
        assert any("requires 'function'" in e for e in errors)

    def test_validate_agg_name_not_string(self):
        """Validation: name is not a string."""
        comp = Aggregate("agg", {"aggregations": [{"name": 123, "function": "sum", "column": "v"}]})
        errors = comp.validate()
        assert any("'name' must be a string" in e for e in errors)

    def test_validate_agg_function_not_string(self):
        """Validation: function is not a string."""
        comp = Aggregate("agg", {"aggregations": [{"name": "total", "function": 123, "column": "v"}]})
        errors = comp.validate()
        assert any("'function' must be a string" in e for e in errors)

    def test_validate_agg_unknown_function(self):
        """Validation: unknown aggregation function."""
        comp = Aggregate("agg", {"aggregations": [{"name": "total", "function": "unknown_fn", "column": "v"}]})
        errors = comp.validate()
        assert any("unknown function" in e for e in errors)

    def test_validate_agg_missing_column_non_count(self):
        """Validation: missing column for non-count function."""
        comp = Aggregate("agg", {"aggregations": [{"name": "total", "function": "sum"}]})
        errors = comp.validate()
        assert any("requires 'column'" in e for e in errors)

    def test_validate_agg_count_star_no_column_ok(self):
        """Validation: count function does not require column."""
        comp = Aggregate("agg", {"aggregations": [{"name": "cnt", "function": "count"}]})
        errors = comp.validate()
        assert len(errors) == 0

    def test_validate_group_by_not_list(self):
        """Validation: group_by is not a list."""
        comp = Aggregate("agg", {
            "group_by": "not_a_list",
            "aggregations": [{"name": "total", "function": "sum", "column": "v"}],
        })
        errors = comp.validate()
        assert any("'group_by' must be a list" in e for e in errors)

    def test_validate_group_by_invalid_entry(self):
        """Validation: group_by entry is not a string or dict."""
        comp = Aggregate("agg", {
            "group_by": [123],
            "aggregations": [{"name": "total", "function": "sum", "column": "v"}],
        })
        errors = comp.validate()
        assert any("must be a string or dict" in e for e in errors)

    def test_validate_group_by_dict_missing_input(self):
        """Validation: group_by dict entry missing 'input'."""
        comp = Aggregate("agg", {
            "group_by": [{"output": "cust"}],
            "aggregations": [{"name": "total", "function": "sum", "column": "v"}],
        })
        errors = comp.validate()
        assert any("requires 'input'" in e for e in errors)

    def test_validate_maintain_order_not_bool(self):
        """Validation: maintain_order is not a boolean."""
        comp = Aggregate("agg", {
            "maintain_order": "yes",
            "aggregations": [{"name": "total", "function": "sum", "column": "v"}],
        })
        errors = comp.validate()
        assert any("'maintain_order' must be a boolean" in e for e in errors)

    def test_validate_ignore_nulls_not_bool(self):
        """Validation: per-aggregation ignore_nulls not boolean."""
        comp = Aggregate("agg", {
            "aggregations": [{"name": "total", "function": "sum", "column": "v", "ignore_nulls": "yes"}],
        })
        errors = comp.validate()
        assert any("invalid ignore_nulls" in e for e in errors)

    def test_validate_separator_not_string(self):
        """Validation: per-aggregation separator not a string."""
        comp = Aggregate("agg", {
            "aggregations": [{"name": "vals", "function": "list", "column": "v", "separator": 123}],
        })
        errors = comp.validate()
        assert any("invalid separator" in e for e in errors)

    def test_validate_valid_full_config(self):
        """Validation passes with all options set correctly."""
        comp = Aggregate("agg", {
            "group_by": ["g", {"input": "customer_id", "output": "cust_id"}],
            "aggregations": [
                {"name": "total", "function": "sum", "column": "v"},
                {"name": "vals", "function": "list", "column": "v", "separator": ";", "ignore_nulls": True},
                {"name": "cnt", "function": "count"},
            ],
            "maintain_order": True,
        })
        errors = comp.validate()
        assert errors == []

    def test_unknown_function_raises(self):
        """Test that unknown aggregation function raises ValueError."""
        comp = Aggregate("agg", {
            "group_by": ["g"],
            "aggregations": [
                {"name": "total", "function": "sum", "column": "v"},
                {"name": "bad", "function": "unknown_func", "column": "v"},
            ],
        })
        df = pl.DataFrame({"g": ["a", "a"], "v": [10, 20]}).lazy()
        with pytest.raises(ValueError, match="Unknown aggregation function: 'unknown_func'"):
            comp.apply({"main": df})

    def test_no_main_input_returns_empty(self):
        """Test that missing main input returns empty dict."""
        comp = Aggregate("agg", {
            "aggregations": [{"name": "total", "function": "sum", "column": "v"}],
        })
        result = comp.apply({})
        assert result == {}

    def test_handles_dataframe_input(self):
        """Test that DataFrame input is converted to LazyFrame."""
        comp = Aggregate("agg", {
            "group_by": ["g"],
            "aggregations": [{"name": "total", "function": "sum", "column": "v"}],
        })
        df = pl.DataFrame({"g": ["a", "a"], "v": [10, 20]})
        result = comp.apply({"main": df})
        assert isinstance(result["main"], pl.LazyFrame)
        collected = result["main"].collect()
        assert collected["total"][0] == 30

    def test_not_barrier(self):
        """Test that Aggregate is not a barrier (lazy processing)."""
        comp = Aggregate("agg", {
            "aggregations": [{"name": "total", "function": "sum", "column": "v"}],
        })
        assert comp.is_barrier is False

    def test_registry_registration(self):
        """Test that Aggregate is registered in REGISTRY."""
        from src.v2.components.registry import REGISTRY
        assert REGISTRY.get("aggregate") is Aggregate
        assert REGISTRY.get("aggregate_rows") is Aggregate

    def test_list_function_default_separator(self):
        """List aggregation concatenates values with default comma."""
        comp = Aggregate("agg", {
            "group_by": ["g"],
            "aggregations": [{"name": "vals", "function": "list", "column": "v"}],
        })
        df = pl.DataFrame({"g": ["a", "a", "a"], "v": ["x", "y", "z"]}).lazy()
        result = comp.apply({"main": df})["main"].collect()
        assert result["vals"][0] == "x,y,z"

    def test_list_function_custom_separator(self):
        """List aggregation uses custom separator."""
        comp = Aggregate("agg", {
            "group_by": ["g"],
            "aggregations": [{"name": "vals", "function": "list", "column": "v", "separator": ";"}],
        })
        df = pl.DataFrame({"g": ["a", "a"], "v": ["x", "y"]}).lazy()
        result = comp.apply({"main": df})["main"].collect()
        assert result["vals"][0] == "x;y"

    def test_list_function_with_nulls_ignored(self):
        """List aggregation excludes nulls by default."""
        comp = Aggregate("agg", {
            "group_by": ["g"],
            "aggregations": [{"name": "vals", "function": "list", "column": "v"}],
        })
        df = pl.DataFrame({"g": ["a", "a", "a"], "v": ["x", None, "z"]}).lazy()
        result = comp.apply({"main": df})["main"].collect()
        assert result["vals"][0] == "x,z"

    def test_list_function_with_nulls_included(self):
        """List aggregation includes nulls when ignore_nulls=false."""
        comp = Aggregate("agg", {
            "group_by": ["g"],
            "aggregations": [{"name": "vals", "function": "list", "column": "v", "ignore_nulls": False}],
        })
        df = pl.DataFrame({"g": ["a", "a", "a"], "v": ["x", None, "z"]}).lazy()
        result = comp.apply({"main": df})["main"].collect()
        # null becomes "null" in the joined string
        assert "null" in result["vals"][0]

    def test_list_function_numeric_values(self):
        """List aggregation casts numeric values to string."""
        comp = Aggregate("agg", {
            "group_by": ["g"],
            "aggregations": [{"name": "vals", "function": "list", "column": "v"}],
        })
        df = pl.DataFrame({"g": ["a", "a", "a"], "v": [1, 2, 3]}).lazy()
        result = comp.apply({"main": df})["main"].collect()
        assert result["vals"][0] == "1,2,3"

    def test_ignore_nulls_count_true(self):
        """Count with ignore_nulls=true counts non-null values (default)."""
        comp = Aggregate("agg", {
            "group_by": ["g"],
            "aggregations": [{"name": "cnt", "function": "count", "column": "v", "ignore_nulls": True}],
        })
        df = pl.DataFrame({"g": ["a", "a", "a"], "v": [1, None, 3]}).lazy()
        result = comp.apply({"main": df})["main"].collect()
        assert result["cnt"][0] == 2  # null excluded

    def test_ignore_nulls_count_false(self):
        """Count with ignore_nulls=false counts all rows including nulls."""
        comp = Aggregate("agg", {
            "group_by": ["g"],
            "aggregations": [{"name": "cnt", "function": "count", "column": "v", "ignore_nulls": False}],
        })
        df = pl.DataFrame({"g": ["a", "a", "a"], "v": [1, None, 3]}).lazy()
        result = comp.apply({"main": df})["main"].collect()
        assert result["cnt"][0] == 3  # null included

    def test_ignore_nulls_first_true(self):
        """First with ignore_nulls=true skips null values."""
        comp = Aggregate("agg", {
            "group_by": ["g"],
            "aggregations": [{"name": "f", "function": "first", "column": "v"}],
        })
        df = pl.DataFrame({"g": ["a", "a", "a"], "v": [None, 20, 30]}).lazy()
        result = comp.apply({"main": df})["main"].collect()
        assert result["f"][0] == 20  # null skipped

    def test_ignore_nulls_first_false(self):
        """First with ignore_nulls=false returns null if first value is null."""
        comp = Aggregate("agg", {
            "group_by": ["g"],
            "aggregations": [{"name": "f", "function": "first", "column": "v", "ignore_nulls": False}],
        })
        df = pl.DataFrame({"g": ["a", "a", "a"], "v": [None, 20, 30]}).lazy()
        result = comp.apply({"main": df})["main"].collect()
        assert result["f"][0] is None

    def test_ignore_nulls_last_true(self):
        """Last with ignore_nulls=true skips null values."""
        comp = Aggregate("agg", {
            "group_by": ["g"],
            "aggregations": [{"name": "l", "function": "last", "column": "v"}],
        })
        df = pl.DataFrame({"g": ["a", "a", "a"], "v": [10, 20, None]}).lazy()
        result = comp.apply({"main": df})["main"].collect()
        assert result["l"][0] == 20  # null skipped

    def test_ignore_nulls_last_false(self):
        """Last with ignore_nulls=false returns null if last value is null."""
        comp = Aggregate("agg", {
            "group_by": ["g"],
            "aggregations": [{"name": "l", "function": "last", "column": "v", "ignore_nulls": False}],
        })
        df = pl.DataFrame({"g": ["a", "a", "a"], "v": [10, 20, None]}).lazy()
        result = comp.apply({"main": df})["main"].collect()
        assert result["l"][0] is None

    def test_maintain_order(self):
        """Group by with maintain_order preserves input order."""
        comp = Aggregate("agg", {
            "group_by": ["g"],
            "aggregations": [{"name": "total", "function": "sum", "column": "v"}],
            "maintain_order": True,
        })
        df = pl.DataFrame({"g": ["b", "a", "b", "a"], "v": [1, 2, 3, 4]}).lazy()
        result = comp.apply({"main": df})["main"].collect()
        # "b" appears first in input, so it should appear first in output
        assert result["g"].to_list() == ["b", "a"]
        assert result["total"].to_list() == [4, 6]

    def test_maintain_order_default_false(self):
        """Default: maintain_order is false (no order guarantee but test still validates result)."""
        comp = Aggregate("agg", {
            "group_by": ["g"],
            "aggregations": [{"name": "total", "function": "sum", "column": "v"}],
        })
        df = pl.DataFrame({"g": ["b", "a", "b"], "v": [1, 2, 3]}).lazy()
        result = comp.apply({"main": df})["main"].collect().sort("g")
        assert result["g"].to_list() == ["a", "b"]
        assert result["total"].to_list() == [2, 4]

    def test_n_unique_alias(self):
        """n_unique works as alias for count_distinct."""
        comp = Aggregate("agg", {
            "group_by": ["g"],
            "aggregations": [{"name": "u", "function": "n_unique", "column": "v"}],
        })
        df = pl.DataFrame({"g": ["a", "a", "a"], "v": [1, 1, 2]}).lazy()
        result = comp.apply({"main": df})["main"].collect()
        assert result["u"][0] == 2

    def test_group_by_rename(self):
        """Group by with column renaming (input != output)."""
        comp = Aggregate("agg", {
            "group_by": [{"input": "customer_id", "output": "cust_id"}],
            "aggregations": [{"name": "total", "function": "sum", "column": "amount"}],
        })
        df = pl.DataFrame({
            "customer_id": ["C1", "C1", "C2"],
            "amount": [100, 200, 300],
        }).lazy()
        result = comp.apply({"main": df})["main"].collect().sort("cust_id")
        assert "cust_id" in result.columns
        assert "customer_id" not in result.columns
        assert result["cust_id"].to_list() == ["C1", "C2"]
        assert result["total"].to_list() == [300, 300]

    def test_group_by_rename_mixed(self):
        """Group by with mix of string and dict entries."""
        comp = Aggregate("agg", {
            "group_by": ["region", {"input": "customer_id", "output": "cust_id"}],
            "aggregations": [{"name": "total", "function": "sum", "column": "amount"}],
        })
        df = pl.DataFrame({
            "region": ["East", "East", "West"],
            "customer_id": ["C1", "C1", "C2"],
            "amount": [100, 200, 300],
        }).lazy()
        result = comp.apply({"main": df})["main"].collect().sort(["region", "cust_id"])
        assert "cust_id" in result.columns
        assert "region" in result.columns
        assert "customer_id" not in result.columns

    def test_group_by_rename_same_name(self):
        """Group by dict with input == output is a no-op rename."""
        comp = Aggregate("agg", {
            "group_by": [{"input": "category", "output": "category"}],
            "aggregations": [{"name": "total", "function": "sum", "column": "v"}],
        })
        df = pl.DataFrame({"category": ["A", "A", "B"], "v": [1, 2, 3]}).lazy()
        result = comp.apply({"main": df})["main"].collect().sort("category")
        assert "category" in result.columns
        assert result["total"].to_list() == [3, 3]


class TestUniqRow:
    """Test UniqRow component (formerly Unique, now at transform/uniq_row.py)."""

    def test_default_unique_all_columns_keep_first(self):
        """Test default unique (all columns via empty key_columns, keep first)."""
        comp = Unique("u1", {"key_columns": []})
        df = pl.DataFrame({
            "id": [1, 1, 2, 2, 3],
            "name": ["Alice", "Alice", "Bob", "Bob", "Charlie"],
        }).lazy()
        result = comp.apply({"main": df})
        assert "unique" in result
        assert isinstance(result["unique"], pl.LazyFrame)
        collected = result["unique"].collect()
        assert len(collected) == 3

    def test_unique_specific_columns(self):
        """Test unique on specific columns subset."""
        comp = Unique("u2", {
            "key_columns": [{"column": "customer_id", "case_sensitive": True}],
        })
        df = pl.DataFrame({
            "customer_id": ["C1", "C1", "C2"],
            "order_id": [1, 2, 3],
            "amount": [100, 200, 300],
        }).lazy()
        result = comp.apply({"main": df})
        collected = result["unique"].collect()
        assert len(collected) == 2  # One row per customer

    def test_keep_last(self):
        """Test keep='last' keeps the last occurrence."""
        comp = Unique("u3", {
            "key_columns": [{"column": "customer_id", "case_sensitive": True}],
            "keep": "last",
        })
        df = pl.DataFrame({
            "customer_id": ["C1", "C1", "C1"],
            "seq": [1, 2, 3],
        }).lazy()
        result = comp.apply({"main": df})
        collected = result["unique"].collect()
        assert len(collected) == 1
        assert collected["seq"][0] == 3

    def test_keep_none_removes_all_duplicates(self):
        """Test keep='none' removes all rows that have duplicates."""
        comp = Unique("u4", {
            "key_columns": [{"column": "customer_id", "case_sensitive": True}],
            "keep": "none",
        })
        df = pl.DataFrame({
            "customer_id": ["C1", "C1", "C2", "C3", "C3"],
            "value": [10, 20, 30, 40, 50],
        }).lazy()
        result = comp.apply({"main": df})
        collected = result["unique"].collect()
        # Only C2 has no duplicate
        assert len(collected) == 1
        assert collected["customer_id"][0] == "C2"

    def test_no_duplicates_passthrough(self):
        """Test pass-through when there are no duplicates."""
        comp = Unique("u5", {"key_columns": []})
        df = pl.DataFrame({
            "id": [1, 2, 3],
            "name": ["Alice", "Bob", "Charlie"],
        }).lazy()
        result = comp.apply({"main": df})
        collected = result["unique"].collect()
        assert len(collected) == 3

    def test_handles_dataframe_input(self):
        """Test that DataFrame input is converted to LazyFrame."""
        comp = Unique("u6", {"key_columns": []})
        df = pl.DataFrame({
            "id": [1, 1, 2],
            "name": ["Alice", "Alice", "Bob"],
        })
        result = comp.apply({"main": df})
        assert isinstance(result["unique"], pl.LazyFrame)
        collected = result["unique"].collect()
        assert len(collected) == 2

    def test_no_main_input_returns_empty(self):
        """Test that missing main input returns empty dict."""
        comp = Unique("u7", {"key_columns": []})
        result = comp.apply({})
        assert result == {}

    def test_validate_requires_key_columns(self):
        """Test that validate returns error when key_columns missing."""
        comp = Unique("u8", {})
        errors = comp.validate()
        assert any("key_columns" in e for e in errors)

    def test_not_barrier_without_duplicate_output(self):
        """Test that UniqRow is not a barrier without duplicate_output."""
        comp = Unique("u9", {"key_columns": [{"column": "id", "case_sensitive": True}]})
        assert comp.is_barrier is False

    def test_is_barrier_with_duplicate_output(self):
        """Test that UniqRow IS a barrier with duplicate_output enabled."""
        comp = Unique("u9b", {
            "key_columns": [{"column": "id", "case_sensitive": True}],
            "duplicate_output": True,
        })
        assert comp.is_barrier is True

    def test_keep_first(self):
        """Test keep='first' keeps the first occurrence."""
        comp = Unique("u10", {
            "key_columns": [{"column": "customer_id", "case_sensitive": True}],
            "keep": "first",
        })
        df = pl.DataFrame({
            "customer_id": ["C1", "C1", "C1"],
            "seq": [1, 2, 3],
        }).lazy()
        result = comp.apply({"main": df})
        collected = result["unique"].collect()
        assert len(collected) == 1
        assert collected["seq"][0] == 1

    def test_registry_registration(self):
        """Test that UniqRow is registered in REGISTRY under new names."""
        from src.v2.components.registry import REGISTRY
        assert REGISTRY.get("uniq_row") is Unique
        assert REGISTRY.get("unique_row") is Unique

    def test_duplicate_output(self):
        """Test dual output when duplicate_output is enabled."""
        comp = Unique("u11", {
            "key_columns": [{"column": "id", "case_sensitive": True}],
            "duplicate_output": True,
        })
        df = pl.DataFrame({
            "id": [1, 1, 2, 3, 3, 3],
            "val": ["a", "b", "c", "d", "e", "f"],
        }).lazy()
        result = comp.apply({"main": df})
        assert "unique" in result
        assert "duplicate" in result
        unique_collected = result["unique"].collect()
        dup_collected = result["duplicate"].collect()
        assert len(unique_collected) == 3  # 1, 2, 3
        assert len(dup_collected) == 3  # second 1, second 3, third 3

    def test_case_insensitive_dedup(self):
        """Test case-insensitive deduplication via lowercased temp columns."""
        comp = Unique("u12", {
            "key_columns": [{"column": "name", "case_sensitive": False}],
        })
        df = pl.DataFrame({
            "name": ["Alice", "alice", "ALICE", "Bob"],
            "val": [1, 2, 3, 4],
        }).lazy()
        result = comp.apply({"main": df})
        collected = result["unique"].collect()
        assert len(collected) == 2  # Alice + Bob
        # Temp columns should not be in output
        assert all(not col.startswith("__uniq_lower_") for col in collected.columns)

    def test_keep_any(self):
        """Test v2-only keep='any' option."""
        comp = Unique("u13", {
            "key_columns": [{"column": "id", "case_sensitive": True}],
            "keep": "any",
        })
        df = pl.DataFrame({
            "id": [1, 1, 2],
            "val": ["a", "b", "c"],
        }).lazy()
        result = comp.apply({"main": df})
        collected = result["unique"].collect()
        assert len(collected) == 2  # One per id
