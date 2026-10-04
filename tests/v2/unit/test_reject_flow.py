"""
Tests for row-level reject flows (Task 8.1).

Tests the safe compilation mode in the expression compiler and the
reject flow routing in the Map component.
"""
import pytest
import polars as pl

from src.v2.expressions import compile_expression
from src.v2.components.transform.map_component import Map


class TestSafeCompilation:
    def test_safe_cast_to_integer_with_invalid(self):
        """Safe mode should produce null for invalid casts instead of error."""
        expr = compile_expression("TO_INTEGER(val)", safe=True)
        df = pl.DataFrame({"val": ["123", "abc", "456"]}).lazy()
        result = df.select(expr.alias("result")).collect()
        assert result["result"][0] == 123
        assert result["result"][1] is None  # "abc" can't be cast
        assert result["result"][2] == 456

    def test_unsafe_cast_to_integer_with_invalid(self):
        """Unsafe mode should raise error for invalid casts."""
        expr = compile_expression("TO_INTEGER(val)", safe=False)
        df = pl.DataFrame({"val": ["123", "abc"]}).lazy()
        with pytest.raises(Exception):
            df.select(expr.alias("result")).collect()

    def test_safe_cast_to_float(self):
        expr = compile_expression("TO_FLOAT(val)", safe=True)
        df = pl.DataFrame({"val": ["1.5", "bad", "3.0"]}).lazy()
        result = df.select(expr.alias("result")).collect()
        assert result["result"][0] == 1.5
        assert result["result"][1] is None
        assert result["result"][2] == 3.0

    def test_safe_mode_default_off(self):
        """Default should be unsafe (strict)."""
        expr = compile_expression("TO_INTEGER(val)")
        df = pl.DataFrame({"val": ["abc"]}).lazy()
        with pytest.raises(Exception):
            df.select(expr.alias("result")).collect()

    def test_safe_does_not_affect_valid_casts(self):
        expr = compile_expression("TO_INTEGER(val)", safe=True)
        df = pl.DataFrame({"val": ["100", "200"]}).lazy()
        result = df.select(expr.alias("result")).collect()
        assert result["result"].to_list() == [100, 200]

    def test_safe_cast_to_boolean(self):
        """Safe mode should handle boolean casts gracefully."""
        expr = compile_expression("TO_BOOLEAN(val)", safe=True)
        df = pl.DataFrame({"val": [1, 0]}).lazy()
        result = df.select(expr.alias("result")).collect()
        assert result["result"][0] is True
        assert result["result"][1] is False

    def test_safe_cast_to_decimal(self):
        """Safe mode TO_DECIMAL should produce null for invalid values."""
        expr = compile_expression("TO_DECIMAL(val)", safe=True)
        df = pl.DataFrame({"val": ["1.23", "nope", "4.56"]}).lazy()
        result = df.select(expr.alias("result")).collect()
        assert result["result"][0] == 1.23
        assert result["result"][1] is None
        assert result["result"][2] == 4.56


class TestMapRejectFlow:
    def test_die_on_error_false_routes_bad_rows(self):
        comp = Map("m", {
            "die_on_error": False,
            "error_reject_output": "reject",
            "outputs": [
                {"name": "main", "columns": [
                    {"name": "id", "expression": "id"},
                    {"name": "amount", "expression": "TO_INTEGER(raw_amount)"},
                ]},
                {"name": "reject", "columns": []},
            ],
        })
        df = pl.DataFrame({
            "id": [1, 2, 3],
            "raw_amount": ["100", "bad", "300"],
        }).lazy()
        result = comp.apply({"main": df})

        assert "main" in result
        assert "reject" in result

        main = result["main"].collect()
        reject = result["reject"].collect()

        assert len(main) == 2  # rows 1 and 3
        assert len(reject) == 1  # row 2
        assert main["amount"].to_list() == [100, 300]

    def test_die_on_error_true_raises(self):
        comp = Map("m", {
            "die_on_error": True,
            "outputs": [{"name": "main", "columns": [
                {"name": "amount", "expression": "TO_INTEGER(raw_amount)"},
            ]}],
        })
        df = pl.DataFrame({"raw_amount": ["bad"]}).lazy()
        result = comp.apply({"main": df})
        with pytest.raises(Exception):
            result["main"].collect()

    def test_die_on_error_default_true(self):
        comp = Map("m", {
            "outputs": [{"name": "main", "columns": [
                {"name": "amount", "expression": "TO_INTEGER(raw_amount)"},
            ]}],
        })
        df = pl.DataFrame({"raw_amount": ["bad"]}).lazy()
        result = comp.apply({"main": df})
        with pytest.raises(Exception):
            result["main"].collect()

    def test_no_errors_means_empty_reject(self):
        comp = Map("m", {
            "die_on_error": False,
            "error_reject_output": "reject",
            "outputs": [
                {"name": "main", "columns": [
                    {"name": "amount", "expression": "TO_INTEGER(raw_amount)"},
                ]},
                {"name": "reject", "columns": []},
            ],
        })
        df = pl.DataFrame({"raw_amount": ["100", "200"]}).lazy()
        result = comp.apply({"main": df})

        main = result["main"].collect()
        reject = result["reject"].collect()

        assert len(main) == 2
        assert len(reject) == 0

    def test_reject_has_error_metadata(self):
        comp = Map("m", {
            "die_on_error": False,
            "error_reject_output": "reject",
            "outputs": [
                {"name": "main", "columns": [
                    {"name": "val", "expression": "TO_INTEGER(raw)"},
                ]},
                {"name": "reject", "columns": []},
            ],
        })
        df = pl.DataFrame({"raw": ["bad"]}).lazy()
        result = comp.apply({"main": df})
        reject = result["reject"].collect()
        assert "_error_message" in reject.columns

    def test_passthrough_columns_not_affected(self):
        """Direct column references should not trigger reject even if null."""
        comp = Map("m", {
            "die_on_error": False,
            "error_reject_output": "reject",
            "outputs": [
                {"name": "main", "columns": [
                    {"name": "id", "expression": "id"},
                    {"name": "amount", "expression": "TO_INTEGER(raw)"},
                ]},
                {"name": "reject", "columns": []},
            ],
        })
        df = pl.DataFrame({"id": [1, 2], "raw": ["100", "bad"]}).lazy()
        result = comp.apply({"main": df})
        main = result["main"].collect()
        reject = result["reject"].collect()
        assert len(main) == 1
        assert len(reject) == 1
        assert reject["id"][0] == 2
