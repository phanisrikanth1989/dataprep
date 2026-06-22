"""Tests for src.converters.talend_to_v1.expression_converter.ExpressionConverter.

Covers:
- detect_java_expression: empty/non-string short-circuits, ${...} pre-resolved
  context, routine calls, CamelCase static method calls, instance method calls,
  unary operators (!, ~), increment/decrement (++, --), Java casts, Java binary
  operators with their false-positive carve-outs (URLs, file paths, negative
  numbers, hyphenated identifiers), globalMap.get/put, Java comments,
  string-concatenation patterns.
- mark_java_expression: empty / non-string passthrough, already-marked
  passthrough, marker prepending.
- convert: short-circuit on empty, casts removed, row references, context
  references, globalMap, string methods, null checks, logical operators,
  StringHandling, TalendDate, Numeric.

Pattern: pure unit tests around a stateless static-method API; no fixtures.
Plan 14-11 reference: 8 converter modules to >= 95%; this raises
expression_converter from 78% to >= 95% line coverage.
"""
from __future__ import annotations

import pytest

from src.converters.talend_to_v1.expression_converter import ExpressionConverter


# ---------------------------------------------------------------------------
# detect_java_expression -- short-circuits & non-string inputs
# ---------------------------------------------------------------------------


class TestDetectShortCircuits:
    """Cover lines 25, 31, 35: empty/non-string/whitespace/${...} short-circuits."""

    @pytest.mark.parametrize("value", [None, "", 0, 42, [], {}, b"bytes"])
    def test_empty_or_non_string_returns_false(self, value):
        """None / non-string / falsy non-string returns False (line 25)."""
        assert ExpressionConverter.detect_java_expression(value) is False

    def test_whitespace_only_string_returns_false(self):
        """'   ' strips to '' which is empty -> False (line 31)."""
        assert ExpressionConverter.detect_java_expression("   ") is False

    def test_already_resolved_context_reference_returns_false(self):
        """${context.var} is handled by ContextManager, not Java (line 35)."""
        assert (
            ExpressionConverter.detect_java_expression("${context.host}") is False
        )
        # Wrapping whitespace still strips down to a wrapped reference
        assert (
            ExpressionConverter.detect_java_expression("  ${context.port}  ") is False
        )

    def test_partial_dollar_brace_does_not_short_circuit(self):
        """${... without trailing } is NOT a wrapped reference."""
        # Should fall through to method-call check on .substring( (line 49)
        assert ExpressionConverter.detect_java_expression(
            "${incomplete.substring(0)"
        ) is True


# ---------------------------------------------------------------------------
# detect_java_expression -- structural Java patterns
# ---------------------------------------------------------------------------


class TestDetectStructuralPatterns:
    """Cover routines.*, CamelCase static call, instance method call (lines 41, 45-46, 49)."""

    def test_routines_prefix_detected(self):
        """Anything containing 'routines.' is Java (line 41)."""
        assert ExpressionConverter.detect_java_expression(
            "routines.DataOperation.format(x)"
        ) is True

    def test_camelcase_static_call_detected(self):
        """ValidationUtils.method() -> Java (line 45-46)."""
        assert ExpressionConverter.detect_java_expression(
            "ValidationUtils.checkRequired(input)"
        ) is True

    def test_instance_method_call_detected(self):
        """foo.bar() -> Java (line 49)."""
        assert ExpressionConverter.detect_java_expression(
            "foo.bar()"
        ) is True


# ---------------------------------------------------------------------------
# detect_java_expression -- unary + cast operators
# ---------------------------------------------------------------------------


class TestDetectUnaryAndCast:
    """Cover lines 55, 57, 59: ! ~ ++/-- and lines 63-64 casts."""

    def test_bang_followed_by_word_detected(self):
        """!flag -> Java (line 55)."""
        assert ExpressionConverter.detect_java_expression("!isReady") is True

    def test_bang_followed_by_paren_detected(self):
        """!(condition) -> Java (line 55)."""
        assert ExpressionConverter.detect_java_expression("!(x > 0)") is True

    def test_tilde_followed_by_word_detected(self):
        """~mask -> Java (line 57)."""
        assert ExpressionConverter.detect_java_expression("~mask") is True

    def test_tilde_followed_by_paren_detected(self):
        """~(x) -> Java (line 57)."""
        assert ExpressionConverter.detect_java_expression("~(0xff)") is True

    def test_increment_detected(self):
        """x++ -> Java (line 59)."""
        assert ExpressionConverter.detect_java_expression("x++") is True

    def test_decrement_detected(self):
        """y-- -> Java (line 59)."""
        assert ExpressionConverter.detect_java_expression("y--") is True

    def test_string_cast_detected(self):
        """(String)value -> Java (line 64)."""
        assert ExpressionConverter.detect_java_expression(
            "(String)value"
        ) is True

    def test_integer_cast_with_space_detected(self):
        """(Integer) count -> Java (line 64)."""
        assert ExpressionConverter.detect_java_expression(
            "(Integer) count"
        ) is True


# ---------------------------------------------------------------------------
# detect_java_expression -- binary operator carve-outs
# ---------------------------------------------------------------------------


class TestDetectOperatorCarveouts:
    """Carve-outs that keep URLs / file paths / negative numbers / hyphenated
    identifiers from being misdetected as Java expressions.
    """

    def test_http_url_not_detected_as_java(self):
        """http://... is a literal URL, not a Java expression.

        ``_looks_like_file_path`` recognises URL-like locators (http://,
        https://, ftp://, file://, and protocol-relative //) and short-circuits
        detection to False so they are not wrapped as ``{{java}}`` markers.
        """
        assert ExpressionConverter.detect_java_expression(
            "http://example.com/path"
        ) is False

    def test_https_url_not_detected_as_java(self):
        assert ExpressionConverter.detect_java_expression(
            "https://example.com/x"
        ) is False

    def test_protocol_relative_url_not_detected_as_java(self):
        """Protocol-relative ``//host/...`` is treated as a literal locator."""
        assert ExpressionConverter.detect_java_expression("//cdn/host/x") is False

    def test_ftp_url_not_detected_as_java(self):
        """ftp://... is a literal URL, not Java."""
        assert ExpressionConverter.detect_java_expression("ftp://srv/a") is False

    def test_unix_filepath_not_detected(self):
        """/var/log/foo.log -> not Java (line 99)."""
        assert ExpressionConverter.detect_java_expression(
            "/var/log/foo.log"
        ) is False

    def test_windows_filepath_not_detected(self):
        """C:/path/to/file -> not Java (line 99)."""
        assert ExpressionConverter.detect_java_expression(
            "C:/path/to/file"
        ) is False

    def test_relative_path_with_only_slashes_not_detected(self):
        """data/file.csv (no other operators) -> not Java (line 99)."""
        # No other operators among +-"%><?=&|!() means this is a path-like value
        assert ExpressionConverter.detect_java_expression("data/file.csv") is False

    def test_negative_integer_literal_not_detected(self):
        """-5 -> not Java (line 103)."""
        assert ExpressionConverter.detect_java_expression("-5") is False

    def test_negative_float_literal_not_detected(self):
        """-5.2 -> not Java (line 103)."""
        assert ExpressionConverter.detect_java_expression("-5.2") is False

    def test_hyphenated_encoding_not_detected(self):
        """UTF-8 -> not Java (line 108-110)."""
        assert ExpressionConverter.detect_java_expression("UTF-8") is False

    def test_hyphenated_locale_not_detected(self):
        """en-US -> not Java (line 108-110)."""
        assert ExpressionConverter.detect_java_expression("en-US") is False

    def test_uuid_with_hyphens_not_detected(self):
        """UUID-shaped strings -> not Java (line 108-110)."""
        assert ExpressionConverter.detect_java_expression(
            "550e8400-e29b-41d4-a716-446655440000"
        ) is False

    def test_subtraction_with_spaces_around_dash_is_detected(self):
        """'a - b' has spaced subtraction -> Java (line 110-111 'not re.search(spaces)' fails)."""
        # The hyphen-identifier carve-out only applies if there are NO spaces
        # around the '-'. With spaces, this falls through to `return True`.
        assert ExpressionConverter.detect_java_expression("a - b") is True


# ---------------------------------------------------------------------------
# detect_java_expression -- post-operator branches
# ---------------------------------------------------------------------------


class TestDetectPostOperatorBranches:
    """Cover lines 124, 128, 134: globalMap, // /*  comments, "x" + "y"."""

    def test_globalmap_detected(self):
        """globalMap.get('K') -> Java (line 124)."""
        # Use a value that doesn't trigger earlier patterns
        # Plain "globalMap." inside an identifier-only string
        assert ExpressionConverter.detect_java_expression(
            "globalMap"
        ) is False  # mere word doesn't trigger; only 'globalMap.' does
        # Plain reference also picks up the '.' instance-method check earlier (line 49)
        # so we go for one without parens-ish:
        assert ExpressionConverter.detect_java_expression("globalMap.X") is True

    def test_inline_comment_detected(self):
        """value with // -> Java (line 128)."""
        # Use something that doesn't trip the earlier path-skip carve-out
        assert ExpressionConverter.detect_java_expression(
            "x // inline note"
        ) is True

    def test_block_comment_detected(self):
        """value with /* -> Java (line 128)."""
        assert ExpressionConverter.detect_java_expression(
            "x /* note */"
        ) is True

    def test_string_concat_detected(self):
        """'a' + 'b' style concatenation -> Java (line 134)."""
        # The + operator is in java_operators, but the concat regex (line 133)
        # is the explicit detector; either path returns True.
        assert ExpressionConverter.detect_java_expression(
            '"file" + ".csv"'
        ) is True

    def test_simple_literal_not_detected(self):
        """A simple word literal returns False (line 137)."""
        assert ExpressionConverter.detect_java_expression(
            "simpleLiteral"
        ) is False

    def test_pure_number_literal_not_detected(self):
        """A pure positive number returns False (no operators)."""
        assert ExpressionConverter.detect_java_expression("42") is False


# ---------------------------------------------------------------------------
# mark_java_expression -- short-circuits, idempotency, and marker prepend
# ---------------------------------------------------------------------------


class TestMarkJavaExpression:
    """Cover line 151 (non-string passthrough), 155 (already-marked
    passthrough), and the prepend path."""

    @pytest.mark.parametrize("value", [None, "", 0, 42, []])
    def test_empty_or_non_string_passthrough(self, value):
        """Falsy / non-string values pass through unchanged (line 151)."""
        assert ExpressionConverter.mark_java_expression(value) == value

    def test_already_marked_passthrough(self):
        """A {{java}}-prefixed string is returned unchanged (line 155)."""
        marked = "{{java}}routines.X.method()"
        assert ExpressionConverter.mark_java_expression(marked) == marked

    def test_java_expression_gets_marked(self):
        """A Java expression gets {{java}} prepended."""
        result = ExpressionConverter.mark_java_expression("routines.X.method()")
        assert result.startswith("{{java}}")
        assert "routines.X.method()" in result

    def test_simple_literal_unchanged(self):
        """A non-Java literal is returned unchanged."""
        assert (
            ExpressionConverter.mark_java_expression("plain") == "plain"
        )


# ---------------------------------------------------------------------------
# convert -- short-circuit + transformations
# ---------------------------------------------------------------------------


class TestConvert:
    """Cover line 175 (empty short-circuit) and the transformation rules."""

    @pytest.mark.parametrize("value", [None, "", 0])
    def test_empty_value_returned_unchanged(self, value):
        """Empty/None/0 is returned unchanged (line 175)."""
        assert ExpressionConverter.convert(value) == value

    def test_string_cast_removed(self):
        """(String) prefix is stripped."""
        assert ExpressionConverter.convert("(String)value") == "value"

    def test_integer_cast_removed(self):
        """(Integer) prefix is stripped."""
        assert ExpressionConverter.convert("(Integer)x") == "x"

    def test_double_cast_removed(self):
        """(Double) prefix is stripped."""
        assert ExpressionConverter.convert("(Double)y") == "y"

    def test_boolean_cast_removed(self):
        """(Boolean) prefix is stripped."""
        assert ExpressionConverter.convert("(Boolean)flag") == "flag"

    def test_row_reference_translated(self):
        """row1.column -> df['column']."""
        assert ExpressionConverter.convert("row1.col_a") == "df['col_a']"

    def test_context_reference_wrapped(self):
        """context.var -> ${context.var}."""
        assert (
            ExpressionConverter.convert("context.host")
            == "${context.host}"
        )

    def test_globalmap_get_normalized(self):
        """globalMap.get(\"key\") -> globalMap.get('key')."""
        assert (
            ExpressionConverter.convert('globalMap.get("KEY")')
            == "globalMap.get('KEY')"
        )

    def test_globalmap_put_normalized(self):
        """globalMap.put(\"key\", val) -> globalMap.put('key', val)."""
        assert (
            ExpressionConverter.convert('globalMap.put("K", value)')
            == "globalMap.put('K', value)"
        )

    def test_string_methods_translated(self):
        """toUpperCase/toLowerCase/trim/length/equals/contains/startsWith/endsWith."""
        assert (
            ".upper()" in ExpressionConverter.convert("foo.toUpperCase()")
        )
        assert (
            ".lower()" in ExpressionConverter.convert("foo.toLowerCase()")
        )
        assert (
            ".strip()" in ExpressionConverter.convert("foo.trim()")
        )
        assert (
            ".__len__()" in ExpressionConverter.convert("foo.length()")
        )
        # equals -> ' == '
        assert " == " in ExpressionConverter.convert('a.equals("b")')
        # equalsIgnoreCase -> .lower() == str(
        out = ExpressionConverter.convert('a.equalsIgnoreCase("B")')
        assert ".lower() == str(" in out
        # contains -> '<arg> in <receiver>'
        assert ExpressionConverter.convert('a.contains("b")') == '"b" in a'
        # startsWith -> .startswith
        assert ".startswith(" in ExpressionConverter.convert(
            'a.startsWith("b")'
        )
        # endsWith -> .endswith
        assert ".endswith(" in ExpressionConverter.convert(
            'a.endsWith("b")'
        )

    def test_null_checks_translated(self):
        """== null / != null / null."""
        assert "is None" in ExpressionConverter.convert("x == null")
        assert "is not None" in ExpressionConverter.convert("x != null")
        # bare null becomes None
        assert "None" in ExpressionConverter.convert("null")

    def test_logical_operators_translated(self):
        """&& -> ' and ', || -> ' or ', ! -> ' not '."""
        assert " and " in ExpressionConverter.convert("a && b")
        assert " or " in ExpressionConverter.convert("a || b")
        assert " not " in ExpressionConverter.convert("!a")

    def test_string_handling_translated(self):
        """StringHandling.LEN/UPCASE/DOWNCASE/TRIM."""
        assert "len(" in ExpressionConverter.convert(
            "StringHandling.LEN(x)"
        )
        assert "str(" in ExpressionConverter.convert(
            "StringHandling.UPCASE(x)"
        )
        assert "str(" in ExpressionConverter.convert(
            "StringHandling.DOWNCASE(x)"
        )
        assert "str(" in ExpressionConverter.convert(
            "StringHandling.TRIM(x)"
        )

    def test_talend_date_translated(self):
        """TalendDate.getCurrentDate / TalendDate.getDate."""
        assert "datetime.now()" in ExpressionConverter.convert(
            "TalendDate.getCurrentDate()"
        )
        assert "datetime.strptime(" in ExpressionConverter.convert(
            'TalendDate.getDate("yyyy-MM-dd")'
        )

    def test_numeric_translated(self):
        """Numeric.round / Numeric.abs."""
        assert "round(" in ExpressionConverter.convert("Numeric.round(x)")
        assert "abs(" in ExpressionConverter.convert("Numeric.abs(x)")
