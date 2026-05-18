"""Tests for ContextManager -- context variable resolution and type conversion.

Covers: ENG-05 (type conversion), ENG-18 (code field corruption), NEW-01 (dead imports),
NEW-02 (list-of-dict recursion), edge cases.

Organized by concern: one test class per area, following the project test pattern.
"""
import datetime

import pytest
from decimal import Decimal

from src.v1.engine.context_manager import ContextManager


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


def _make_cm(**context_vars):
    """Create a ContextManager with the given context variables pre-loaded."""
    cm = ContextManager()
    for key, value in context_vars.items():
        cm.set(key, value)
    return cm


def _make_cm_typed(**typed_vars):
    """Create a ContextManager with typed context variables.

    Args:
        **typed_vars: key=(value, type) pairs.
    """
    cm = ContextManager()
    for key, (value, value_type) in typed_vars.items():
        cm.set(key, value, value_type)
    return cm


# ------------------------------------------------------------------
# 1. Set / Get
# ------------------------------------------------------------------


@pytest.mark.unit
class TestContextManagerSetGet:
    """Basic set/get operations."""

    def test_set_and_get_string(self):
        cm = ContextManager()
        cm.set("name", "Alice")
        assert cm.get("name") == "Alice"

    def test_set_with_type_conversion(self):
        cm = ContextManager()
        cm.set("count", "42", "id_Integer")
        assert cm.get("count") == 42
        assert isinstance(cm.get("count"), int)

    def test_get_missing_returns_none(self):
        cm = ContextManager()
        assert cm.get("nonexistent") is None

    def test_get_missing_with_default(self):
        cm = ContextManager()
        assert cm.get("nonexistent", "fallback") == "fallback"

    def test_overwrite_value(self):
        cm = ContextManager()
        cm.set("key", "first")
        cm.set("key", "second")
        assert cm.get("key") == "second"

    def test_get_all_returns_copy(self):
        cm = _make_cm(a="1", b="2")
        all_vars = cm.get_all()
        assert all_vars == {"a": "1", "b": "2"}
        # Modifying the copy should not affect the original
        all_vars["c"] = "3"
        assert cm.get("c") is None

    def test_contains_existing_key(self):
        cm = _make_cm(x="val")
        assert cm.contains("x") is True

    def test_contains_missing_key(self):
        cm = ContextManager()
        assert cm.contains("missing") is False

    def test_remove_key(self):
        cm = _make_cm(x="val")
        cm.remove("x")
        assert cm.get("x") is None
        assert cm.contains("x") is False

    def test_remove_nonexistent_key_no_error(self):
        cm = ContextManager()
        cm.remove("nonexistent")  # Should not raise

    def test_clear(self):
        cm = _make_cm(a="1", b="2")
        cm.clear()
        assert cm.get_all() == {}

    def test_get_type(self):
        cm = ContextManager()
        cm.set("count", "10", "id_Integer")
        assert cm.get_type("count") == "id_Integer"

    def test_get_type_missing(self):
        cm = ContextManager()
        cm.set("plain", "value")
        assert cm.get_type("plain") is None


# ------------------------------------------------------------------
# 2. Type Conversion
# ------------------------------------------------------------------


@pytest.mark.unit
class TestContextManagerTypeConversion:
    """Type conversion via _convert_type and set()."""

    def test_id_string(self):
        cm = ContextManager()
        cm.set("val", 123, "id_String")
        assert cm.get("val") == "123"
        assert isinstance(cm.get("val"), str)

    def test_id_integer(self):
        cm = ContextManager()
        cm.set("val", "100", "id_Integer")
        assert cm.get("val") == 100
        assert isinstance(cm.get("val"), int)

    def test_id_long(self):
        cm = ContextManager()
        cm.set("val", "9999999999", "id_Long")
        assert cm.get("val") == 9999999999
        assert isinstance(cm.get("val"), int)

    def test_id_short(self):
        cm = ContextManager()
        cm.set("val", "32767", "id_Short")
        assert cm.get("val") == 32767
        assert isinstance(cm.get("val"), int)

    def test_id_byte(self):
        cm = ContextManager()
        cm.set("val", "127", "id_Byte")
        assert cm.get("val") == 127
        assert isinstance(cm.get("val"), int)

    def test_id_float(self):
        cm = ContextManager()
        cm.set("val", "1.5", "id_Float")
        assert cm.get("val") == 1.5
        assert isinstance(cm.get("val"), float)

    def test_id_double(self):
        cm = ContextManager()
        cm.set("val", "3.14159", "id_Double")
        assert cm.get("val") == 3.14159
        assert isinstance(cm.get("val"), float)

    def test_id_boolean_true(self):
        cm = ContextManager()
        cm.set("val", "true", "id_Boolean")
        assert cm.get("val") is True

    def test_id_boolean_false(self):
        cm = ContextManager()
        cm.set("val", "false", "id_Boolean")
        assert cm.get("val") is False

    def test_id_boolean_1(self):
        cm = ContextManager()
        cm.set("val", "1", "id_Boolean")
        assert cm.get("val") is True

    def test_id_boolean_0(self):
        cm = ContextManager()
        cm.set("val", "0", "id_Boolean")
        assert cm.get("val") is False

    def test_id_boolean_yes(self):
        cm = ContextManager()
        cm.set("val", "yes", "id_Boolean")
        assert cm.get("val") is True

    def test_id_boolean_no(self):
        cm = ContextManager()
        cm.set("val", "no", "id_Boolean")
        assert cm.get("val") is False

    def test_id_character(self):
        cm = ContextManager()
        cm.set("val", "ABC", "id_Character")
        assert cm.get("val") == "A"

    def test_id_character_empty(self):
        cm = ContextManager()
        cm.set("val", "", "id_Character")
        # Empty string returns empty (not converted, value == "")
        assert cm.get("val") == ""

    def test_id_date_parses_to_datetime(self):
        """id_Date parses input strings to datetime objects so the Java bridge
        receives a real java.util.Date (Task 0.5 of the tMap rewrite). The
        previous behavior -- keeping the value as a string -- was a bug that
        broke parseDate(String, Date) and other date-typed Talend routines."""
        cm = ContextManager()
        cm.set("val", "2024-01-15", "id_Date")
        result = cm.get("val")
        assert result == datetime.datetime(2024, 1, 15, 0, 0)
        assert isinstance(result, datetime.datetime)

    def test_id_bigdecimal(self):
        cm = ContextManager()
        cm.set("val", "99.99", "id_BigDecimal")
        assert cm.get("val") == Decimal("99.99")
        assert isinstance(cm.get("val"), Decimal)

    def test_id_object(self):
        cm = ContextManager()
        cm.set("val", 42, "id_Object")
        assert cm.get("val") == "42"
        assert isinstance(cm.get("val"), str)

    def test_python_str_type(self):
        cm = ContextManager()
        cm.set("val", 42, "str")
        assert cm.get("val") == "42"

    def test_python_int_type(self):
        cm = ContextManager()
        cm.set("val", "10", "int")
        assert cm.get("val") == 10

    def test_python_float_type(self):
        cm = ContextManager()
        cm.set("val", "2.5", "float")
        assert cm.get("val") == 2.5

    def test_python_bool_type(self):
        cm = ContextManager()
        cm.set("val", "true", "bool")
        assert cm.get("val") is True

    def test_python_decimal_type(self):
        cm = ContextManager()
        cm.set("val", "10.01", "Decimal")
        assert cm.get("val") == Decimal("10.01")

    def test_python_datetime_type(self):
        cm = ContextManager()
        cm.set("val", "2024-01-01", "datetime")
        assert cm.get("val") == "2024-01-01"
        assert isinstance(cm.get("val"), str)

    def test_python_object_type(self):
        cm = ContextManager()
        cm.set("val", 42, "object")
        assert cm.get("val") == "42"

    def test_unknown_type_returns_original(self):
        """Unknown type should log warning and return original value."""
        cm = ContextManager()
        cm.set("val", "hello", "id_UnknownType")
        assert cm.get("val") == "hello"

    def test_none_value_not_converted(self):
        cm = ContextManager()
        cm.set("val", None, "id_Integer")
        assert cm.get("val") is None

    def test_empty_string_not_converted(self):
        cm = ContextManager()
        cm.set("val", "", "id_Integer")
        assert cm.get("val") == ""

    def test_invalid_integer_conversion_returns_original(self):
        """Invalid conversion should return original value, not crash."""
        cm = ContextManager()
        cm.set("val", "not_a_number", "id_Integer")
        assert cm.get("val") == "not_a_number"


# ------------------------------------------------------------------
# 3. resolve_string
# ------------------------------------------------------------------


@pytest.mark.unit
class TestContextManagerResolveString:
    """String resolution patterns."""

    def test_dollar_brace_pattern(self):
        cm = _make_cm(name="Alice")
        assert cm.resolve_string("${context.name}") == "Alice"

    def test_bare_context_pattern(self):
        cm = _make_cm(name="Alice")
        assert cm.resolve_string("context.name") == "Alice"

    def test_multiple_vars_in_one_string(self):
        cm = _make_cm(first="Hello", second="World")
        result = cm.resolve_string("${context.first} ${context.second}")
        assert result == "Hello World"

    def test_mixed_patterns(self):
        cm = _make_cm(a="X", b="Y")
        # Note: _context.b does NOT match bare pattern because \b requires
        # a word boundary before "context" -- underscore is a word character
        result = cm.resolve_string("${context.a} context.b")
        assert result == "X Y"

    def test_missing_var_stays_as_is(self):
        cm = ContextManager()
        assert cm.resolve_string("${context.missing}") == "${context.missing}"

    def test_missing_bare_var_stays_as_is(self):
        cm = ContextManager()
        assert cm.resolve_string("context.missing") == "context.missing"

    def test_numeric_var_resolved_to_string(self):
        cm = _make_cm(count="42")
        cm.set("count", "42", "id_Integer")
        result = cm.resolve_string("Count is ${context.count}")
        assert result == "Count is 42"

    def test_non_string_input_returned_as_is(self):
        cm = ContextManager()
        assert cm.resolve_string(42) == 42
        assert cm.resolve_string(None) is None

    def test_java_marker_not_resolved(self):
        cm = _make_cm(x="val")
        result = cm.resolve_string("{{java}}context.x + 1")
        assert result == "{{java}}context.x + 1"

    def test_empty_string(self):
        cm = ContextManager()
        assert cm.resolve_string("") == ""

    def test_no_context_references(self):
        cm = ContextManager()
        assert cm.resolve_string("plain text") == "plain text"

    def test_partial_match_not_resolved(self):
        """context.x should resolve but xcontext.x should not match 'context.x'."""
        cm = _make_cm(x="val")
        # The \b boundary should prevent matching inside a word
        result = cm.resolve_string("context.x")
        assert result == "val"


# ------------------------------------------------------------------
# 4. resolve_dict -- Basic
# ------------------------------------------------------------------


@pytest.mark.unit
class TestContextManagerResolveDictBasic:
    """Basic resolve_dict behavior."""

    def test_string_values_resolved(self):
        cm = _make_cm(host="localhost")
        result = cm.resolve_dict({"url": "${context.host}"})
        assert result["url"] == "localhost"

    def test_nested_dict_resolved(self):
        cm = _make_cm(db="mydb")
        result = cm.resolve_dict({"connection": {"database": "${context.db}"}})
        assert result["connection"]["database"] == "mydb"

    def test_non_string_values_passed_through(self):
        cm = ContextManager()
        result = cm.resolve_dict({"count": 42, "flag": True, "rate": 3.14})
        assert result["count"] == 42
        assert result["flag"] is True
        assert result["rate"] == 3.14

    def test_returns_new_dict(self):
        cm = _make_cm(x="val")
        original = {"key": "${context.x}"}
        result = cm.resolve_dict(original)
        assert result["key"] == "val"
        assert original["key"] == "${context.x}"

    def test_deeply_nested_dict(self):
        cm = _make_cm(v="deep")
        config = {"a": {"b": {"c": "${context.v}"}}}
        result = cm.resolve_dict(config)
        assert result["a"]["b"]["c"] == "deep"

    def test_empty_dict(self):
        cm = ContextManager()
        assert cm.resolve_dict({}) == {}


# ------------------------------------------------------------------
# 5. resolve_dict -- Skip Code Fields (ENG-18)
# ------------------------------------------------------------------


@pytest.mark.unit
class TestContextManagerResolveDictSkipKeys:
    """ENG-18: Code fields must NOT be resolved."""

    def test_python_code_unchanged(self):
        cm = _make_cm(threshold="50")
        result = cm.resolve_dict({"python_code": "if context.threshold > 0: pass"})
        assert result["python_code"] == "if context.threshold > 0: pass"

    def test_java_code_unchanged(self):
        cm = _make_cm(val="x")
        result = cm.resolve_dict({"java_code": "String s = context.val;"})
        assert result["java_code"] == "String s = context.val;"

    def test_imports_unchanged(self):
        cm = _make_cm(mod="os")
        result = cm.resolve_dict({"imports": "import context.mod"})
        assert result["imports"] == "import context.mod"

    def test_skip_keys_alongside_resolved_keys(self):
        cm = _make_cm(name="Alice")
        result = cm.resolve_dict({
            "greeting": "Hello ${context.name}",
            "python_code": "print(context.name)",
        })
        assert result["greeting"] == "Hello Alice"
        assert result["python_code"] == "print(context.name)"

    def test_skip_key_with_dollar_brace_pattern(self):
        cm = _make_cm(x="42")
        result = cm.resolve_dict({"python_code": "val = ${context.x}"})
        assert result["python_code"] == "val = ${context.x}"


# ------------------------------------------------------------------
# 6. resolve_dict -- List Recursion (NEW-02)
# ------------------------------------------------------------------


@pytest.mark.unit
class TestContextManagerResolveDictListRecursion:
    """NEW-02: resolve_dict must recurse into dicts inside lists."""

    def test_list_of_strings_resolved(self):
        cm = _make_cm(a="X", b="Y")
        result = cm.resolve_dict({"items": ["${context.a}", "${context.b}"]})
        assert result["items"] == ["X", "Y"]

    def test_list_of_dicts_resolved(self):
        cm = _make_cm(threshold="100")
        result = cm.resolve_dict({
            "conditions": [{"field": "amount", "value": "${context.threshold}"}]
        })
        assert result["conditions"][0]["value"] == "100"

    def test_list_of_mixed_types(self):
        cm = _make_cm(x="val")
        result = cm.resolve_dict({
            "items": ["${context.x}", 42, {"nested": "${context.x}"}, True]
        })
        assert result["items"] == ["val", 42, {"nested": "val"}, True]

    def test_deeply_nested_list_of_list_of_dict(self):
        cm = _make_cm(v="deep")
        result = cm.resolve_dict({
            "outer": [[{"val": "${context.v}"}]]
        })
        assert result["outer"][0][0]["val"] == "deep"

    def test_list_with_nested_dict_containing_skip_key(self):
        """Skip keys should be respected even inside list-of-dict."""
        cm = _make_cm(x="val")
        result = cm.resolve_dict({
            "items": [{"python_code": "context.x", "other": "${context.x}"}]
        })
        assert result["items"][0]["python_code"] == "context.x"
        assert result["items"][0]["other"] == "val"

    def test_empty_list(self):
        cm = ContextManager()
        result = cm.resolve_dict({"items": []})
        assert result["items"] == []

    def test_list_input_not_mutated(self):
        cm = _make_cm(x="val")
        original_list = [{"v": "${context.x}"}]
        original = {"items": original_list}
        cm.resolve_dict(original)
        assert original_list[0]["v"] == "${context.x}"


# ------------------------------------------------------------------
# 7. load_context
# ------------------------------------------------------------------


@pytest.mark.unit
class TestContextManagerLoadContext:
    """Loading context from dict structures."""

    def test_load_simple_dict(self):
        cm = ContextManager()
        cm.load_context({"name": {"value": "Alice", "type": "id_String"}})
        assert cm.get("name") == "Alice"

    def test_load_with_type_conversion(self):
        cm = ContextManager()
        cm.load_context({"count": {"value": "42", "type": "id_Integer"}})
        assert cm.get("count") == 42
        assert isinstance(cm.get("count"), int)

    def test_load_overwrites_existing(self):
        cm = _make_cm(key="old")
        cm.load_context({"key": {"value": "new", "type": "id_String"}})
        assert cm.get("key") == "new"

    def test_load_plain_values(self):
        """Plain values (not dicts) should be loaded as-is."""
        cm = ContextManager()
        cm.load_context({"simple": "value"})
        assert cm.get("simple") == "value"

    def test_load_mixed_format(self):
        cm = ContextManager()
        cm.load_context({
            "typed": {"value": "10", "type": "id_Integer"},
            "plain": "hello",
        })
        assert cm.get("typed") == 10
        assert cm.get("plain") == "hello"


# ------------------------------------------------------------------
# 8. Constructor
# ------------------------------------------------------------------


@pytest.mark.unit
class TestContextManagerConstructor:
    """Constructor and initial_context loading."""

    def test_empty_constructor(self):
        cm = ContextManager()
        assert cm.get_all() == {}

    def test_initial_context_with_default_group(self):
        cm = ContextManager(
            initial_context={"Default": {"x": {"value": "1", "type": "id_Integer"}}},
            default_context="Default",
        )
        assert cm.get("x") == 1

    def test_initial_context_with_named_group(self):
        cm = ContextManager(
            initial_context={
                "Default": {"x": {"value": "1"}},
                "Prod": {"x": {"value": "2"}},
            },
            default_context="Prod",
        )
        assert cm.get("x") == "2"

    def test_initial_context_fallback_when_group_missing(self):
        """If default_context group is not found, load the whole dict."""
        cm = ContextManager(
            initial_context={"key": {"value": "val"}},
            default_context="NonExistent",
        )
        assert cm.get("key") == "val"

    def test_java_bridge_manager_stored(self):
        sentinel = object()
        cm = ContextManager(java_bridge_manager=sentinel)
        assert cm.java_bridge_manager is sentinel


# ------------------------------------------------------------------
# 9. load_from_file
# ------------------------------------------------------------------


@pytest.mark.unit
class TestContextManagerLoadFromFile:
    """Loading context from key=value files."""

    def test_load_from_file(self, tmp_path):
        f = tmp_path / "ctx.txt"
        f.write_text("host=localhost\nport=5432\n")
        cm = ContextManager()
        cm.load_from_file(str(f))
        assert cm.get("host") == "localhost"
        assert cm.get("port") == "5432"

    def test_load_from_file_skips_comments(self, tmp_path):
        f = tmp_path / "ctx.txt"
        f.write_text("# comment\nkey=value\n")
        cm = ContextManager()
        cm.load_from_file(str(f))
        assert cm.get("key") == "value"
        assert cm.get("# comment") is None

    def test_load_from_file_custom_delimiter(self, tmp_path):
        f = tmp_path / "ctx.txt"
        f.write_text("key:value\n")
        cm = ContextManager()
        cm.load_from_file(str(f), delimiter=":")
        assert cm.get("key") == "value"

    def test_load_from_file_missing_raises(self):
        cm = ContextManager()
        with pytest.raises(FileNotFoundError):
            cm.load_from_file("/nonexistent/path/ctx.txt")

    def test_load_from_file_value_with_equals(self, tmp_path):
        """Value containing the delimiter should be preserved."""
        f = tmp_path / "ctx.txt"
        f.write_text("url=jdbc:oracle:thin:@host:1521:sid\n")
        cm = ContextManager()
        cm.load_from_file(str(f))
        assert cm.get("url") == "jdbc:oracle:thin:@host:1521:sid"


# ------------------------------------------------------------------
# 10. Java Bridge Integration
# ------------------------------------------------------------------


@pytest.mark.unit
class TestContextManagerJavaBridge:
    """Java bridge delegation methods."""

    def test_get_java_bridge_none_when_no_manager(self):
        cm = ContextManager()
        assert cm.get_java_bridge() is None

    def test_is_java_enabled_false_when_no_manager(self):
        cm = ContextManager()
        assert cm.is_java_enabled() is False

    def test_repr_without_java(self):
        cm = _make_cm(a="1", b="2")
        r = repr(cm)
        assert "variables=2" in r
        assert "java_bridge=disabled" in r


# ------------------------------------------------------------------
# 11. ENG-05 Regression Tests
# ------------------------------------------------------------------


@pytest.mark.unit
class TestENG05Regression:
    """ENG-05: Type conversion must use callables, not string literals.

    The old code had entries like 'id_Integer': 'int' (string) instead of
    'id_Integer': int (builtin). This caused converter(value) to fail because
    'int'('100') calls str.__call__ which returns 'int', not int('100').
    """

    def test_integer_conversion_returns_int(self):
        cm = ContextManager()
        cm.set("count", "100", "id_Integer")
        result = cm.get("count")
        assert result == 100
        assert isinstance(result, int), f"Expected int, got {type(result)}"

    def test_boolean_conversion_returns_bool(self):
        cm = ContextManager()
        cm.set("flag", "true", "id_Boolean")
        assert cm.get("flag") is True

    def test_date_parses_to_datetime(self):
        """id_Date parses input strings to datetime objects (Task 0.5 of the
        tMap rewrite). The previous str-coercion behavior was a bug that
        broke Talend routines requiring a real java.util.Date."""
        cm = ContextManager()
        cm.set("start_date", "2024-01-15", "id_Date")
        result = cm.get("start_date")
        assert result == datetime.datetime(2024, 1, 15, 0, 0)
        assert isinstance(result, datetime.datetime)

    def test_bigdecimal_conversion_returns_decimal(self):
        cm = ContextManager()
        cm.set("price", "99.99", "id_BigDecimal")
        result = cm.get("price")
        assert result == Decimal("99.99")
        assert isinstance(result, Decimal)

    def test_float_conversion_returns_float(self):
        cm = ContextManager()
        cm.set("rate", "3.14", "id_Float")
        result = cm.get("rate")
        assert result == 3.14
        assert isinstance(result, float)

    def test_long_conversion_returns_int(self):
        cm = ContextManager()
        cm.set("big", "1000000", "id_Long")
        result = cm.get("big")
        assert result == 1000000
        assert isinstance(result, int)

    def test_all_type_converters_are_callable(self):
        """Verify every entry in _TYPE_CONVERTERS is actually callable."""
        for type_name, converter in ContextManager._TYPE_CONVERTERS.items():
            assert callable(converter), (
                f"_TYPE_CONVERTERS['{type_name}'] = {converter!r} is not callable"
            )


# ------------------------------------------------------------------
# 12. ENG-18 Regression Tests
# ------------------------------------------------------------------


@pytest.mark.unit
class TestENG18Regression:
    """ENG-18: resolve_dict must NOT corrupt python_code fields.

    The old code only skipped 'java_code' and 'imports'. 'python_code' was
    being resolved, which corrupted Python code that referenced context
    variables for runtime use.
    """

    def test_python_code_with_context_reference_preserved(self):
        cm = ContextManager()
        cm.set("threshold", "50", "id_Integer")
        result = cm.resolve_dict({"python_code": "if context.threshold > 0: pass"})
        assert result["python_code"] == "if context.threshold > 0: pass"

    def test_python_code_with_dollar_brace_preserved(self):
        cm = _make_cm(x="val")
        result = cm.resolve_dict({"python_code": "v = ${context.x}"})
        assert result["python_code"] == "v = ${context.x}"

    def test_python_code_multiline_preserved(self):
        cm = _make_cm(x="val")
        code = "for row in data:\n    if context.x == 'test':\n        pass"
        result = cm.resolve_dict({"python_code": code})
        assert result["python_code"] == code


# ------------------------------------------------------------------
# 13. NEW-01 Regression Tests
# ------------------------------------------------------------------


@pytest.mark.unit
class TestNEW01Regression:
    """NEW-01: No dead imports (os, sys) in context_manager.py."""

    def test_no_os_import(self):
        import inspect
        module = inspect.getmodule(ContextManager)
        source = inspect.getsource(module)
        assert "import os" not in source

    def test_no_sys_import(self):
        import inspect
        module = inspect.getmodule(ContextManager)
        source = inspect.getsource(module)
        assert "import sys" not in source

    def test_no_print_statements(self):
        import inspect
        module = inspect.getmodule(ContextManager)
        source = inspect.getsource(module)
        # Allow "print" in comments/docstrings but not as function call
        lines = source.split("\n")
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("#") or stripped.startswith('"""') or stripped.startswith("'"):
                continue
            assert not stripped.startswith("print("), (
                f"Line {i}: Found print() statement: {stripped}"
            )


# ------------------------------------------------------------------
# 14. NEW-02 Regression Tests
# ------------------------------------------------------------------


@pytest.mark.unit
class TestNEW02Regression:
    """NEW-02: resolve_dict must recurse into dicts inside lists.

    The old code only resolved string elements in lists:
        [self.resolve_string(v) if isinstance(v, str) else v for v in value]
    Dict elements were passed through unresolved.
    """

    def test_list_of_dicts_resolved(self):
        cm = ContextManager()
        cm.set("val", "42")
        result = cm.resolve_dict({"items": [{"threshold": "${context.val}"}]})
        assert result["items"][0]["threshold"] == "42"

    def test_tmap_mappings_resolved(self):
        """tMap-style config with list of mapping dicts."""
        cm = _make_cm(table="customers")
        result = cm.resolve_dict({
            "mappings": [
                {"source": "${context.table}.id", "target": "out.id"},
                {"source": "${context.table}.name", "target": "out.name"},
            ]
        })
        assert result["mappings"][0]["source"] == "customers.id"
        assert result["mappings"][1]["source"] == "customers.name"

    def test_filter_conditions_resolved(self):
        """tFilterRows-style config with list of condition dicts."""
        cm = _make_cm(min_amount="100")
        result = cm.resolve_dict({
            "conditions": [
                {"field": "amount", "operator": ">", "value": "${context.min_amount}"}
            ]
        })
        assert result["conditions"][0]["value"] == "100"

    def test_aggregate_operations_resolved(self):
        """tAggregateRow-style config with list of operation dicts."""
        cm = _make_cm(agg_col="revenue")
        result = cm.resolve_dict({
            "operations": [
                {"column": "${context.agg_col}", "function": "sum"}
            ]
        })
        assert result["operations"][0]["column"] == "revenue"


# ------------------------------------------------------------------
# 15. SKIP_RESOLUTION_KEYS Class Constant
# ------------------------------------------------------------------


@pytest.mark.unit
class TestSkipResolutionKeysConstant:
    """Verify SKIP_RESOLUTION_KEYS is properly defined."""

    def test_is_frozenset(self):
        assert isinstance(ContextManager.SKIP_RESOLUTION_KEYS, frozenset)

    def test_contains_python_code(self):
        assert "python_code" in ContextManager.SKIP_RESOLUTION_KEYS

    def test_contains_java_code(self):
        assert "java_code" in ContextManager.SKIP_RESOLUTION_KEYS

    def test_contains_imports(self):
        assert "imports" in ContextManager.SKIP_RESOLUTION_KEYS


# ------------------------------------------------------------------
# 16. _resolve_list Method
# ------------------------------------------------------------------


@pytest.mark.unit
class TestResolveListMethod:
    """Verify _resolve_list exists and works correctly."""

    def test_method_exists(self):
        assert hasattr(ContextManager, "_resolve_list")

    def test_resolves_strings(self):
        cm = _make_cm(x="val")
        result = cm._resolve_list(["${context.x}", "plain"])
        assert result == ["val", "plain"]

    def test_resolves_nested_dicts(self):
        cm = _make_cm(x="val")
        result = cm._resolve_list([{"k": "${context.x}"}])
        assert result == [{"k": "val"}]

    def test_resolves_nested_lists(self):
        cm = _make_cm(x="val")
        result = cm._resolve_list([["${context.x}"]])
        assert result == [["val"]]

    def test_passes_through_non_string_non_dict_non_list(self):
        cm = ContextManager()
        result = cm._resolve_list([42, True, None, 3.14])
        assert result == [42, True, None, 3.14]


# ------------------------------------------------------------------
# 17. Edge Cases
# ------------------------------------------------------------------


@pytest.mark.unit
class TestContextManagerEdgeCases:
    """Edge cases and boundary conditions."""

    def test_resolve_string_with_none_value_in_context(self):
        """Context variable set to None -- should keep original pattern."""
        cm = ContextManager()
        cm.set("x", None)
        result = cm.resolve_string("${context.x}")
        assert result == "${context.x}"

    def test_resolve_dict_with_none_value(self):
        cm = ContextManager()
        result = cm.resolve_dict({"key": None})
        assert result["key"] is None

    def test_resolve_dict_with_int_value(self):
        cm = ContextManager()
        result = cm.resolve_dict({"count": 42})
        assert result["count"] == 42

    def test_resolve_dict_with_bool_value(self):
        cm = ContextManager()
        result = cm.resolve_dict({"flag": True})
        assert result["flag"] is True

    def test_large_nested_config(self):
        """Realistic complex config resolution."""
        cm = _make_cm(
            db_host="prod-db.example.com",
            db_port="5432",
            db_name="etl_data",
            batch_size="1000",
        )
        config = {
            "connection": {
                "host": "${context.db_host}",
                "port": "${context.db_port}",
                "database": "${context.db_name}",
            },
            "processing": {
                "batch_size": "${context.batch_size}",
                "conditions": [
                    {"field": "status", "value": "active"},
                    {"field": "host", "value": "${context.db_host}"},
                ],
            },
            "python_code": "conn = connect(context.db_host)",
        }
        result = cm.resolve_dict(config)
        assert result["connection"]["host"] == "prod-db.example.com"
        assert result["connection"]["port"] == "5432"
        assert result["processing"]["conditions"][1]["value"] == "prod-db.example.com"
        assert result["python_code"] == "conn = connect(context.db_host)"
