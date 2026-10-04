# tests/converters/talend_to_v2/test_expression_translator.py
import pytest
from src.converters.talend_to_v2.expression_translator import (
    EdgeContext,
    TranslationResult,
    translate_expression,
    convert_date_pattern,
)


@pytest.fixture
def tmap_edge_context():
    return EdgeContext(
        main_edge="orders",
        lookup_edges={"products": "products", "customers": "customers"},
    )


class TestMainEdgeStripping:
    def test_strips_main_edge_prefix(self, tmap_edge_context):
        result = translate_expression("orders.order_id", tmap_edge_context)
        assert result.expression == "order_id"
        assert not result.needs_review

    def test_strips_main_in_arithmetic(self, tmap_edge_context):
        result = translate_expression("orders.quantity * orders.unit_price", tmap_edge_context)
        assert result.expression == "quantity * unit_price"

    def test_no_edge_context_passes_through(self):
        result = translate_expression("column_name")
        assert result.expression == "column_name"

    def test_strips_custom_main_name(self):
        ctx = EdgeContext(main_edge="input_data", lookup_edges={})
        result = translate_expression("input_data.amount > 100", ctx)
        assert result.expression == "amount > 100"

    def test_does_not_strip_partial_match(self, tmap_edge_context):
        """'orders_extra.col' should NOT be stripped — 'orders_extra' != 'orders'."""
        result = translate_expression("orders_extra.col", tmap_edge_context)
        assert result.expression == "orders_extra.col"


class TestLookupPrefixPreservation:
    def test_preserves_lookup_prefix(self, tmap_edge_context):
        result = translate_expression("customers.customer_name", tmap_edge_context)
        assert result.expression == "customers.customer_name"

    def test_preserves_multiple_lookups(self, tmap_edge_context):
        result = translate_expression(
            "customers.name + ' - ' + products.product_name",
            tmap_edge_context,
        )
        assert "customers.name" in result.expression
        assert "products.product_name" in result.expression


class TestVarConversion:
    def test_converts_var_case(self, tmap_edge_context):
        result = translate_expression("Var.total_amount", tmap_edge_context)
        assert result.expression == "var.total_amount"

    def test_converts_var_in_expression(self, tmap_edge_context):
        result = translate_expression("Var.subtotal * 1.1", tmap_edge_context)
        assert result.expression == "var.subtotal * 1.1"

    def test_no_double_conversion(self, tmap_edge_context):
        """Already lowercase var. should stay as-is."""
        result = translate_expression("var.total", tmap_edge_context)
        assert result.expression == "var.total"


class TestRoutinePrefix:
    def test_strips_routines_prefix(self, tmap_edge_context):
        result = translate_expression(
            "routines.OrderManagement.orderTotal(orders.quantity, orders.unit_price)",
            tmap_edge_context,
        )
        assert result.expression == "OrderManagement.orderTotal(quantity, unit_price)"

    def test_routine_without_routines_prefix(self, tmap_edge_context):
        result = translate_expression(
            "OrderManagement.isVip(Var.total_amount, context.vip_threshold)",
            tmap_edge_context,
        )
        assert result.expression == "OrderManagement.isVip(var.total_amount, context.vip_threshold)"


class TestStringQuotes:
    def test_converts_double_to_single_quotes(self, tmap_edge_context):
        result = translate_expression('"COMPLETED"', tmap_edge_context)
        assert result.expression == "'COMPLETED'"

    def test_mixed_quotes_in_expression(self, tmap_edge_context):
        result = translate_expression('orders.status == "ACTIVE"', tmap_edge_context)
        assert result.expression == "status == 'ACTIVE'"

    def test_escapes_embedded_single_quotes(self, tmap_edge_context):
        result = translate_expression('"it\'s here"', tmap_edge_context)
        assert result.expression == "'it\\'s here'"


class TestTernaryConversion:
    def test_simple_ternary(self, tmap_edge_context):
        result = translate_expression("orders.amount > 100 ? orders.amount : 0", tmap_edge_context)
        assert result.expression == "IF(amount > 100, amount, 0)"

    def test_nested_ternary_flagged(self, tmap_edge_context):
        result = translate_expression("a ? b ? c : d : e", tmap_edge_context)
        assert result.needs_review
        assert "ternary" in result.review_reason.lower()

    def test_ternary_skipped_when_colon_in_string(self, tmap_edge_context):
        """Ternary with colon inside a string literal should not be converted."""
        result = translate_expression("orders.x > 0 ? 'a:b' : 'c'", tmap_edge_context)
        # Should pass through unchanged (except main edge stripping)
        assert "IF(" not in result.expression


class TestJavaDetection:
    def test_detects_substring(self, tmap_edge_context):
        result = translate_expression('orders.name.substring(0, 5)', tmap_edge_context)
        assert result.needs_review
        assert "substring" in result.review_reason.lower()

    def test_detects_equals(self, tmap_edge_context):
        result = translate_expression('"ACTIVE".equals(orders.status)', tmap_edge_context)
        assert result.needs_review

    def test_detects_talend_date(self, tmap_edge_context):
        result = translate_expression("TalendDate.getDate()", tmap_edge_context)
        assert result.needs_review

    def test_detects_global_map(self, tmap_edge_context):
        result = translate_expression('(String)globalMap.get("key")', tmap_edge_context)
        assert result.needs_review


class TestContextRefs:
    def test_preserves_context_refs(self, tmap_edge_context):
        result = translate_expression("context.vip_threshold", tmap_edge_context)
        assert result.expression == "context.vip_threshold"


class TestEmptyAndNull:
    def test_empty_string(self):
        result = translate_expression("")
        assert result.expression == ""

    def test_whitespace_only(self):
        result = translate_expression("   ")
        assert result.expression == ""

    def test_none(self):
        result = translate_expression(None)
        assert result.expression == ""


class TestDatePatternConversion:
    def test_standard_date(self):
        assert convert_date_pattern("yyyy-MM-dd") == "%Y-%m-%d"

    def test_datetime_with_time(self):
        assert convert_date_pattern("yyyy-MM-dd HH:mm:ss") == "%Y-%m-%d %H:%M:%S"

    def test_short_year(self):
        assert convert_date_pattern("dd/MM/yy") == "%d/%m/%y"

    def test_none(self):
        assert convert_date_pattern(None) is None

    def test_empty(self):
        assert convert_date_pattern("") == ""

    def test_datetime_with_milliseconds(self):
        assert convert_date_pattern("yyyy-MM-dd HH:mm:ss.SSS") == "%Y-%m-%d %H:%M:%S.%f"
