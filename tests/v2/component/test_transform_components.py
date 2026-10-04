"""
Tests for v2 Transform components (FilterRows, SortRow).

These tests validate the rewritten V2 components that use
TransformComponent base class and register with REGISTRY.
"""
import pytest
import polars as pl

from src.v2.components.transform import FilterRows, SortRow


class TestFilterRows:
    def test_basic_filter(self):
        comp = FilterRows("f", {"condition": "amount > 100"})
        df = pl.DataFrame({"id": [1, 2, 3], "amount": [50, 150, 200]}).lazy()
        result = comp.apply({"main": df})
        assert "main" in result
        assert isinstance(result["main"], pl.LazyFrame)
        collected = result["main"].collect()
        assert len(collected) == 2
        assert collected["id"].to_list() == [2, 3]

    def test_filter_not_barrier(self):
        comp = FilterRows("f", {"condition": "amount > 100"})
        assert comp.is_barrier is False

    def test_filter_barrier_when_reject_enabled(self):
        """FilterRows is a barrier when reject_output is True."""
        comp = FilterRows("f", {"condition": "amount > 100", "reject_output": True})
        assert comp.is_barrier is True

    def test_filter_with_reject(self):
        comp = FilterRows("f", {"condition": "amount > 100", "reject_output": True})
        df = pl.DataFrame({"id": [1, 2, 3], "amount": [50, 150, 200]}).lazy()
        result = comp.apply({"main": df})
        assert "main" in result
        assert "reject" in result
        main = result["main"].collect()
        reject = result["reject"].collect()
        assert len(main) == 2
        assert len(reject) == 1
        assert reject["id"][0] == 1

    def test_filter_with_context(self):
        comp = FilterRows("f", {"condition": "amount > context.threshold"}, context={"threshold": 100})
        df = pl.DataFrame({"amount": [50, 150]}).lazy()
        result = comp.apply({"main": df})
        assert result["main"].collect().shape[0] == 1

    def test_filter_with_string_comparison(self):
        comp = FilterRows("f", {"condition": "status == 'active'"})
        df = pl.DataFrame({
            "id": [1, 2, 3],
            "status": ["active", "inactive", "active"],
        }).lazy()
        result = comp.apply({"main": df})
        collected = result["main"].collect()
        assert len(collected) == 2

    def test_filter_with_and_condition(self):
        comp = FilterRows("f", {"condition": "amount > 100 && status == 'active'"})
        df = pl.DataFrame({
            "id": [1, 2, 3, 4],
            "amount": [50, 150, 200, 80],
            "status": ["active", "active", "inactive", "active"],
        }).lazy()
        result = comp.apply({"main": df})
        collected = result["main"].collect()
        assert len(collected) == 1
        assert collected["id"][0] == 2

    def test_filter_empty_result(self):
        comp = FilterRows("f", {"condition": "amount > 1000"})
        df = pl.DataFrame({"id": [1, 2], "amount": [50, 100]}).lazy()
        result = comp.apply({"main": df})
        collected = result["main"].collect()
        assert len(collected) == 0

    def test_filter_no_main_input(self):
        comp = FilterRows("f", {"condition": "amount > 100"})
        result = comp.apply({})
        assert result == {}

    def test_filter_validate(self):
        comp = FilterRows("f", {})
        errors = comp.validate()
        assert len(errors) > 0
        assert "condition" in errors[0].lower()

    def test_registry(self):
        from src.v2.components.registry import REGISTRY
        assert REGISTRY.get("filter") is not None
        assert REGISTRY.get("filter_rows") is not None


class TestSortRow:
    def test_basic_sort_asc(self):
        comp = SortRow("s", {"columns": [{"name": "amount", "order": "asc"}]})
        df = pl.DataFrame({"id": [1, 2, 3], "amount": [300, 100, 200]}).lazy()
        result = comp.apply({"main": df})
        collected = result["main"].collect()
        assert collected["amount"].to_list() == [100, 200, 300]

    def test_sort_desc(self):
        comp = SortRow("s", {"columns": [{"name": "amount", "order": "desc"}]})
        df = pl.DataFrame({"amount": [100, 300, 200]}).lazy()
        result = comp.apply({"main": df})
        collected = result["main"].collect()
        assert collected["amount"].to_list() == [300, 200, 100]

    def test_multi_column_sort(self):
        comp = SortRow("s", {"columns": [
            {"name": "category", "order": "asc"},
            {"name": "amount", "order": "desc"},
        ]})
        df = pl.DataFrame({
            "category": ["B", "A", "A", "B"],
            "amount": [100, 200, 300, 50],
        }).lazy()
        result = comp.apply({"main": df})
        collected = result["main"].collect()
        assert collected["category"].to_list() == ["A", "A", "B", "B"]
        assert collected["amount"].to_list() == [300, 200, 100, 50]

    def test_sort_not_barrier(self):
        comp = SortRow("s", {"columns": [{"name": "a", "order": "asc"}]})
        assert comp.is_barrier is False

    def test_sort_default_order(self):
        """Default order should be ascending."""
        comp = SortRow("s", {"columns": [{"name": "amount"}]})
        df = pl.DataFrame({"amount": [300, 100, 200]}).lazy()
        result = comp.apply({"main": df})
        collected = result["main"].collect()
        assert collected["amount"].to_list() == [100, 200, 300]

    def test_sort_no_main_input(self):
        comp = SortRow("s", {"columns": [{"name": "a", "order": "asc"}]})
        result = comp.apply({})
        assert result == {}

    def test_sort_validate(self):
        comp = SortRow("s", {})
        errors = comp.validate()
        assert len(errors) > 0
        assert "columns" in errors[0].lower()

    def test_registry(self):
        from src.v2.components.registry import REGISTRY
        assert REGISTRY.get("sort_row") is not None
        assert REGISTRY.get("sort") is None  # alias removed per D-20

    def test_sort_validate_columns_not_list(self):
        comp = SortRow("s", {"columns": "not_a_list"})
        errors = comp.validate()
        assert len(errors) == 1
        assert "must be a list" in errors[0].lower()

    def test_sort_validate_columns_empty(self):
        comp = SortRow("s", {"columns": []})
        errors = comp.validate()
        assert len(errors) == 1
        assert "must not be empty" in errors[0].lower()

    def test_sort_validate_column_missing_name(self):
        comp = SortRow("s", {"columns": [{"order": "asc"}]})
        errors = comp.validate()
        assert len(errors) == 1
        assert "requires 'name'" in errors[0].lower()

    def test_sort_validate_column_name_not_string(self):
        comp = SortRow("s", {"columns": [{"name": 123}]})
        errors = comp.validate()
        assert len(errors) == 1
        assert "must be a string" in errors[0].lower()

    def test_sort_validate_invalid_order(self):
        comp = SortRow("s", {"columns": [{"name": "a", "order": "sideways"}]})
        errors = comp.validate()
        assert len(errors) == 1
        assert "invalid order" in errors[0].lower()

    def test_sort_validate_invalid_nulls_last_component(self):
        comp = SortRow("s", {"columns": [{"name": "a"}], "nulls_last": "yes"})
        errors = comp.validate()
        assert len(errors) == 1
        assert "nulls_last" in errors[0].lower()
        assert "boolean" in errors[0].lower()

    def test_sort_validate_invalid_nulls_last_column(self):
        comp = SortRow("s", {"columns": [{"name": "a", "nulls_last": "yes"}]})
        errors = comp.validate()
        assert len(errors) == 1
        assert "nulls_last" in errors[0].lower()

    def test_sort_validate_invalid_maintain_order(self):
        comp = SortRow("s", {"columns": [{"name": "a"}], "maintain_order": "yes"})
        errors = comp.validate()
        assert len(errors) == 1
        assert "maintain_order" in errors[0].lower()
        assert "boolean" in errors[0].lower()

    def test_sort_validate_valid_full_config(self):
        comp = SortRow("s", {
            "columns": [
                {"name": "a", "order": "desc", "nulls_last": True},
                {"name": "b"},
            ],
            "nulls_last": False,
            "maintain_order": True,
        })
        errors = comp.validate()
        assert len(errors) == 0

    def test_sort_validate_string_column_rejected(self):
        """String shorthand must be rejected per D-23."""
        comp = SortRow("s", {"columns": ["a", "b"]})
        errors = comp.validate()
        assert len(errors) == 2
        assert "must be a dict" in errors[0].lower()

    def test_sort_nulls_default_first(self):
        """By default nulls appear first (Polars default)."""
        comp = SortRow("s", {"columns": [{"name": "amount", "order": "asc"}]})
        df = pl.DataFrame({"amount": [200, None, 100, None]}).lazy()
        result = comp.apply({"main": df})
        collected = result["main"].collect()
        assert collected["amount"].to_list() == [None, None, 100, 200]

    def test_sort_nulls_last_component_level(self):
        """Component-level nulls_last puts nulls at end."""
        comp = SortRow("s", {
            "columns": [{"name": "amount", "order": "asc"}],
            "nulls_last": True,
        })
        df = pl.DataFrame({"amount": [200, None, 100, None]}).lazy()
        result = comp.apply({"main": df})
        collected = result["main"].collect()
        assert collected["amount"].to_list() == [100, 200, None, None]

    def test_sort_nulls_last_per_column(self):
        """Per-column nulls_last overrides component default."""
        comp = SortRow("s", {
            "columns": [
                {"name": "amount", "order": "asc", "nulls_last": True},
            ],
            "nulls_last": False,
        })
        df = pl.DataFrame({"amount": [200, None, 100]}).lazy()
        result = comp.apply({"main": df})
        collected = result["main"].collect()
        assert collected["amount"].to_list() == [100, 200, None]

    def test_sort_nulls_last_mixed_columns(self):
        """Different nulls_last per column in multi-column sort."""
        comp = SortRow("s", {
            "columns": [
                {"name": "category", "order": "asc", "nulls_last": True},
                {"name": "amount", "order": "asc", "nulls_last": False},
            ],
        })
        df = pl.DataFrame({
            "category": [None, "A", "A", None],
            "amount": [None, 200, 100, 50],
        }).lazy()
        result = comp.apply({"main": df})
        collected = result["main"].collect()
        # Category: A first (nulls_last=True pushes None to end)
        assert collected["category"].to_list() == ["A", "A", None, None]

    def test_sort_nulls_last_descending(self):
        """Nulls last combined with descending order."""
        comp = SortRow("s", {
            "columns": [{"name": "amount", "order": "desc"}],
            "nulls_last": True,
        })
        df = pl.DataFrame({"amount": [100, None, 300, 200]}).lazy()
        result = comp.apply({"main": df})
        collected = result["main"].collect()
        assert collected["amount"].to_list() == [300, 200, 100, None]

    def test_sort_nulls_last_string_column(self):
        """Nulls last works with string columns too."""
        comp = SortRow("s", {
            "columns": [{"name": "name", "order": "asc"}],
            "nulls_last": True,
        })
        df = pl.DataFrame({"name": ["Charlie", None, "Alice", "Bob"]}).lazy()
        result = comp.apply({"main": df})
        collected = result["main"].collect()
        assert collected["name"].to_list() == ["Alice", "Bob", "Charlie", None]

    def test_sort_maintain_order(self):
        """Equal-valued rows preserve input order when maintain_order=True."""
        comp = SortRow("s", {
            "columns": [{"name": "category", "order": "asc"}],
            "maintain_order": True,
        })
        # Rows with same category should keep original order
        df = pl.DataFrame({
            "category": ["B", "A", "B", "A"],
            "id": [1, 2, 3, 4],
        }).lazy()
        result = comp.apply({"main": df})
        collected = result["main"].collect()
        assert collected["category"].to_list() == ["A", "A", "B", "B"]
        # Within same category, original order is preserved
        assert collected["id"].to_list() == [2, 4, 1, 3]

    def test_sort_maintain_order_default_false(self):
        """Default: maintain_order is false (no stability guarantee)."""
        comp = SortRow("s", {"columns": [{"name": "category", "order": "asc"}]})
        df = pl.DataFrame({
            "category": ["B", "A", "B", "A"],
            "id": [1, 2, 3, 4],
        }).lazy()
        result = comp.apply({"main": df})
        collected = result["main"].collect()
        # Categories are sorted correctly
        assert collected["category"].to_list() == ["A", "A", "B", "B"]
        # But we make no assertion about id order within same category


