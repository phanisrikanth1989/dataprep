"""Tests for V1-to-V2 expression translation."""
import pytest
from src.converters.v1_to_v2.expression_mapper import translate_expression


class TestMainPrefixStripping:
    """Strip main. prefix from column references."""

    def test_simple_column(self):
        result = translate_expression("main.order_id")
        assert result.expression == "order_id"
        assert not result.needs_review

    def test_multiple_columns(self):
        result = translate_expression("main.a + main.b")
        assert result.expression == "a + b"
        assert not result.needs_review

    def test_null_check(self):
        result = translate_expression("main.amount != null")
        assert result.expression == "amount != null"
        assert not result.needs_review

    def test_preserves_lookup_prefix(self):
        result = translate_expression("lookup1.customer_name")
        assert result.expression == "lookup1.customer_name"
        assert not result.needs_review

    def test_preserves_var_prefix(self):
        result = translate_expression("var.tax_amount")
        assert result.expression == "var.tax_amount"
        assert not result.needs_review

    def test_preserves_context_prefix(self):
        result = translate_expression("context.tax_rate")
        assert result.expression == "context.tax_rate"
        assert not result.needs_review

    def test_mixed_main_and_lookup(self):
        result = translate_expression("main.order_id == lookup1.id")
        assert result.expression == "order_id == lookup1.id"
        assert not result.needs_review


class TestStringLiterals:
    """Convert Java double-quoted strings to single-quoted."""

    def test_double_to_single_quotes(self):
        result = translate_expression('"ACTIVE"')
        assert result.expression == "'ACTIVE'"
        assert not result.needs_review

    def test_embedded_quotes_in_expression(self):
        result = translate_expression('main.status == "ACTIVE"')
        assert result.expression == "status == 'ACTIVE'"
        assert not result.needs_review


class TestTernaryConversion:
    """Convert simple Java ternaries to IF()."""

    def test_simple_ternary(self):
        result = translate_expression("main.amount > 100 ? main.amount : 0")
        assert result.expression == "IF(amount > 100, amount, 0)"
        assert not result.needs_review

    def test_nested_ternary_flagged(self):
        result = translate_expression("main.a > 1 ? main.a > 2 ? 3 : 2 : 1")
        assert result.needs_review
        assert "nested ternary" in result.review_reason.lower()


class TestJavaExpressionsFlagged:
    """Java code and methods should be flagged for review."""

    def test_java_block(self):
        result = translate_expression("{{java}} row.get('name').toUpperCase()")
        assert result.needs_review
        assert "java" in result.review_reason.lower()

    def test_substring_method(self):
        result = translate_expression("main.name.substring(0, 5)")
        assert result.needs_review
        assert "java" in result.review_reason.lower()

    def test_length_method(self):
        result = translate_expression("main.name.length()")
        assert result.needs_review

    def test_trim_method(self):
        result = translate_expression("main.name.trim()")
        assert result.needs_review

    def test_talend_date_routine(self):
        result = translate_expression("TalendDate.getDate(main.date_col)")
        assert result.needs_review
        assert "talend" in result.review_reason.lower()

    def test_talend_string_routine(self):
        result = translate_expression("TalendString.trim(main.name)")
        assert result.needs_review

    def test_global_map(self):
        result = translate_expression('globalMap.get("NB_LINE")')
        assert result.needs_review
        assert "globalmap" in result.review_reason.lower()


class TestDatePatternConversion:
    """Convert Java date patterns to Python strftime patterns."""

    def test_iso_date(self):
        from src.converters.v1_to_v2.expression_mapper import convert_date_pattern
        assert convert_date_pattern("yyyy-MM-dd") == "%Y-%m-%d"

    def test_datetime(self):
        from src.converters.v1_to_v2.expression_mapper import convert_date_pattern
        assert convert_date_pattern("yyyy-MM-dd HH:mm:ss") == "%Y-%m-%d %H:%M:%S"

    def test_us_date(self):
        from src.converters.v1_to_v2.expression_mapper import convert_date_pattern
        assert convert_date_pattern("MM/dd/yyyy") == "%m/%d/%Y"

    def test_none_passthrough(self):
        from src.converters.v1_to_v2.expression_mapper import convert_date_pattern
        assert convert_date_pattern(None) is None

    def test_empty_passthrough(self):
        from src.converters.v1_to_v2.expression_mapper import convert_date_pattern
        assert convert_date_pattern("") == ""


class TestEdgeCases:
    """Edge cases and empty inputs."""

    def test_empty_string(self):
        result = translate_expression("")
        assert result.expression == ""
        assert not result.needs_review

    def test_none_returns_empty(self):
        result = translate_expression(None)
        assert result.expression == ""

    def test_pure_number(self):
        result = translate_expression("42")
        assert result.expression == "42"
        assert not result.needs_review

    def test_pure_column_name(self):
        """No prefix — pass through unchanged."""
        result = translate_expression("order_id")
        assert result.expression == "order_id"
        assert not result.needs_review
