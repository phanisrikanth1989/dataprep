"""
Unit tests for v2 Expression Built-in Functions.

Tests all function categories: string, numeric, null, conditional, type cast, date.
"""
import pytest
import polars as pl
from datetime import date, datetime
from src.v2.expressions import compile_expression


class TestStringFunctions:
    def _eval(self, expr_str, df):
        expr = compile_expression(expr_str)
        return df.lazy().select(expr.alias("result")).collect()["result"]

    def test_upper(self):
        df = pl.DataFrame({"name": ["alice"]})
        assert self._eval("UPPER(name)", df)[0] == "ALICE"

    def test_lower(self):
        df = pl.DataFrame({"name": ["ALICE"]})
        assert self._eval("LOWER(name)", df)[0] == "alice"

    def test_trim(self):
        df = pl.DataFrame({"s": ["  hello  "]})
        assert self._eval("TRIM(s)", df)[0] == "hello"

    def test_ltrim(self):
        df = pl.DataFrame({"s": ["  hello  "]})
        assert self._eval("LTRIM(s)", df)[0] == "hello  "

    def test_rtrim(self):
        df = pl.DataFrame({"s": ["  hello  "]})
        assert self._eval("RTRIM(s)", df)[0] == "  hello"

    def test_lpad(self):
        df = pl.DataFrame({"s": ["42"]})
        assert self._eval("LPAD(s, 5, '0')", df)[0] == "00042"

    def test_rpad(self):
        df = pl.DataFrame({"s": ["hi"]})
        assert self._eval("RPAD(s, 5, '.')", df)[0] == "hi..."

    def test_length(self):
        df = pl.DataFrame({"s": ["hello"]})
        assert self._eval("LENGTH(s)", df)[0] == 5

    def test_substring(self):
        df = pl.DataFrame({"s": ["hello world"]})
        assert self._eval("SUBSTRING(s, 0, 5)", df)[0] == "hello"

    def test_replace(self):
        df = pl.DataFrame({"s": ["hello world"]})
        assert self._eval("REPLACE(s, 'world', 'earth')", df)[0] == "hello earth"

    def test_concat(self):
        df = pl.DataFrame({"a": ["hello"], "b": [" world"]})
        assert self._eval("CONCAT(a, b)", df)[0] == "hello world"

    def test_concat_with_null(self):
        df = pl.DataFrame({"a": ["hello"], "b": [None]})
        assert self._eval("CONCAT(a, b)", df)[0] == "hello"

    def test_contains(self):
        df = pl.DataFrame({"s": ["hello world"]})
        assert self._eval("CONTAINS(s, 'world')", df)[0] is True

    def test_starts_with(self):
        df = pl.DataFrame({"s": ["hello"]})
        assert self._eval("STARTS_WITH(s, 'hel')", df)[0] is True

    def test_ends_with(self):
        df = pl.DataFrame({"s": ["hello"]})
        assert self._eval("ENDS_WITH(s, 'llo')", df)[0] is True

    def test_regex_match(self):
        df = pl.DataFrame({"s": ["abc123"]})
        assert self._eval("REGEX_MATCH(s, '^[a-z]+\\\\d+$')", df)[0] is True

    def test_regex_extract(self):
        df = pl.DataFrame({"s": ["order-123"]})
        result = self._eval("REGEX_EXTRACT(s, '(\\\\d+)')", df)[0]
        assert result == "123"

    def test_split(self):
        df = pl.DataFrame({"s": ["a,b,c"]})
        result = self._eval("SPLIT(s, ',')", df)[0].to_list()
        assert result == ["a", "b", "c"]


class TestNumericFunctions:
    def _eval(self, expr_str, df):
        expr = compile_expression(expr_str)
        return df.lazy().select(expr.alias("result")).collect()["result"]

    def test_abs(self):
        df = pl.DataFrame({"n": [-5]})
        assert self._eval("ABS(n)", df)[0] == 5

    def test_round(self):
        df = pl.DataFrame({"n": [3.14159]})
        assert self._eval("ROUND(n, 2)", df)[0] == 3.14

    def test_floor(self):
        df = pl.DataFrame({"n": [3.7]})
        assert self._eval("FLOOR(n)", df)[0] == 3.0

    def test_ceil(self):
        df = pl.DataFrame({"n": [3.2]})
        assert self._eval("CEIL(n)", df)[0] == 4.0

    def test_mod(self):
        df = pl.DataFrame({"n": [10]})
        assert self._eval("MOD(n, 3)", df)[0] == 1

    def test_power(self):
        df = pl.DataFrame({"n": [2]})
        assert self._eval("POWER(n, 3)", df)[0] == 8.0


class TestNullFunctions:
    def _eval(self, expr_str, df):
        expr = compile_expression(expr_str)
        return df.lazy().select(expr.alias("result")).collect()["result"]

    def test_coalesce(self):
        df = pl.DataFrame({"a": [None], "b": [42]})
        assert self._eval("COALESCE(a, b)", df)[0] == 42

    def test_ifnull(self):
        df = pl.DataFrame({"a": [None]})
        assert self._eval("IFNULL(a, 0)", df)[0] == 0

    def test_isnull_true(self):
        df = pl.DataFrame({"a": [None]})
        assert self._eval("ISNULL(a)", df)[0] is True

    def test_isnull_false(self):
        df = pl.DataFrame({"a": [42]})
        assert self._eval("ISNULL(a)", df)[0] is False

    def test_nvl(self):
        df = pl.DataFrame({"a": pl.Series([None], dtype=pl.Utf8)})
        assert self._eval("NVL(a, 'default')", df)[0] == "default"


class TestConditionalFunctions:
    def _eval(self, expr_str, df, context=None):
        expr = compile_expression(expr_str, context)
        return df.lazy().select(expr.alias("result")).collect()["result"]

    def test_if_function(self):
        df = pl.DataFrame({"amount": [150, 50]})
        result = self._eval("IF(amount > 100, 'high', 'low')", df)
        assert result.to_list() == ["high", "low"]

    def test_ternary(self):
        df = pl.DataFrame({"amount": [150, 50]})
        result = self._eval("amount > 100 ? 'high' : 'low'", df)
        assert result.to_list() == ["high", "low"]


class TestTypeCastFunctions:
    def _eval(self, expr_str, df):
        expr = compile_expression(expr_str)
        return df.lazy().select(expr.alias("result")).collect()["result"]

    def test_to_integer(self):
        df = pl.DataFrame({"s": [3.14]})
        assert self._eval("TO_INTEGER(s)", df)[0] == 3

    def test_to_float(self):
        df = pl.DataFrame({"s": [42]})
        result = self._eval("TO_FLOAT(s)", df)[0]
        assert result == 42.0

    def test_to_string(self):
        df = pl.DataFrame({"n": [42]})
        assert self._eval("TO_STRING(n)", df)[0] == "42"

    def test_to_decimal(self):
        df = pl.DataFrame({"s": ["3.14"]})
        result = self._eval("TO_DECIMAL(s)", df)[0]
        assert result == 3.14


class TestDateFunctions:
    def _eval(self, expr_str, df):
        expr = compile_expression(expr_str)
        return df.lazy().select(expr.alias("result")).collect()["result"]

    def test_year(self):
        df = pl.DataFrame({"d": [date(2024, 6, 15)]})
        assert self._eval("YEAR(d)", df)[0] == 2024

    def test_month(self):
        df = pl.DataFrame({"d": [date(2024, 6, 15)]})
        assert self._eval("MONTH(d)", df)[0] == 6

    def test_day(self):
        df = pl.DataFrame({"d": [date(2024, 6, 15)]})
        assert self._eval("DAY(d)", df)[0] == 15
