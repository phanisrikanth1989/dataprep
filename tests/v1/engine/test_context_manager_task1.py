"""Failing tests for Task 1 -- ContextManager rewrite.

These tests verify the 4 bugs being fixed:
- ENG-05: Type conversion uses callables, not string literals
- ENG-18: resolve_dict skips python_code fields
- NEW-01: No dead imports (os, sys)
- NEW-02: resolve_dict recurses into dicts inside lists
"""
import pytest
from decimal import Decimal
from src.v1.engine.context_manager import ContextManager


class TestTask1TypeConversion:
    """ENG-05: _convert_type must use actual callables."""

    def test_integer_conversion_returns_int(self):
        cm = ContextManager()
        cm.set("count", "100", "id_Integer")
        result = cm.get("count")
        assert result == 100
        assert isinstance(result, int)

    def test_boolean_conversion_returns_bool(self):
        cm = ContextManager()
        cm.set("flag", "true", "id_Boolean")
        assert cm.get("flag") is True

    def test_double_conversion_returns_float(self):
        cm = ContextManager()
        cm.set("rate", "3.14", "id_Double")
        result = cm.get("rate")
        assert result == 3.14
        assert isinstance(result, float)

    def test_long_conversion_returns_int(self):
        cm = ContextManager()
        cm.set("big", "1000000", "id_Long")
        result = cm.get("big")
        assert result == 1000000
        assert isinstance(result, int)

    def test_bigdecimal_conversion_returns_decimal(self):
        cm = ContextManager()
        cm.set("price", "99.99", "id_BigDecimal")
        result = cm.get("price")
        assert result == Decimal("99.99")
        assert isinstance(result, Decimal)

    def test_date_stays_as_string(self):
        """id_Date must remain a string -- date parsing is format-specific and
        delegated to individual components (per Gemini review)."""
        cm = ContextManager()
        cm.set("start_date", "2024-01-15", "id_Date")
        result = cm.get("start_date")
        assert result == "2024-01-15"
        assert isinstance(result, str)


class TestTask1SkipCodeFields:
    """ENG-18: resolve_dict must NOT corrupt python_code fields."""

    def test_python_code_not_resolved(self):
        cm = ContextManager()
        cm.set("var", "hello")
        result = cm.resolve_dict({"python_code": "context.var + 1"})
        assert result["python_code"] == "context.var + 1"

    def test_java_code_not_resolved(self):
        cm = ContextManager()
        cm.set("var", "hello")
        result = cm.resolve_dict({"java_code": "context.var"})
        assert result["java_code"] == "context.var"

    def test_imports_not_resolved(self):
        cm = ContextManager()
        cm.set("var", "hello")
        result = cm.resolve_dict({"imports": "import foo"})
        assert result["imports"] == "import foo"


class TestTask1ListOfDictRecursion:
    """NEW-02: resolve_dict must recurse into dicts inside lists."""

    def test_list_of_dicts_resolved(self):
        cm = ContextManager()
        cm.set("x", "42")
        result = cm.resolve_dict({"conditions": [{"value": "${context.x}"}]})
        assert result["conditions"][0]["value"] == "42"

    def test_deeply_nested_list_of_dicts(self):
        cm = ContextManager()
        cm.set("y", "deep")
        result = cm.resolve_dict({
            "outer": [{"inner": [{"val": "${context.y}"}]}]
        })
        assert result["outer"][0]["inner"][0]["val"] == "deep"


class TestTask1ResolveDictImmutability:
    """resolve_dict must return NEW dict, never mutate input."""

    def test_input_not_mutated(self):
        cm = ContextManager()
        cm.set("name", "Alice")
        original = {"greeting": "${context.name}"}
        result = cm.resolve_dict(original)
        assert result["greeting"] == "Alice"
        assert original["greeting"] == "${context.name}"  # Must be unchanged


class TestTask1ResolveString:
    """Basic resolve_string tests."""

    def test_dollar_brace_pattern(self):
        cm = ContextManager()
        cm.set("name", "Alice")
        assert cm.resolve_string("${context.name}") == "Alice"

    def test_bare_context_pattern(self):
        cm = ContextManager()
        cm.set("name", "Alice")
        assert cm.resolve_string("context.name") == "Alice"


class TestTask1NoDeadImports:
    """NEW-01: No os or sys imports."""

    def test_no_os_import(self):
        import inspect
        source = inspect.getsource(ContextManager)
        module = inspect.getmodule(ContextManager)
        module_source = inspect.getsource(module)
        assert "import os" not in module_source

    def test_no_sys_import(self):
        import inspect
        module = inspect.getmodule(ContextManager)
        module_source = inspect.getsource(module)
        assert "import sys" not in module_source


class TestTask1SkipResolutionKeysConstant:
    """SKIP_RESOLUTION_KEYS must be a frozenset on the class."""

    def test_skip_resolution_keys_exists(self):
        assert hasattr(ContextManager, "SKIP_RESOLUTION_KEYS")

    def test_python_code_in_skip_keys(self):
        assert "python_code" in ContextManager.SKIP_RESOLUTION_KEYS

    def test_java_code_in_skip_keys(self):
        assert "java_code" in ContextManager.SKIP_RESOLUTION_KEYS

    def test_imports_in_skip_keys(self):
        assert "imports" in ContextManager.SKIP_RESOLUTION_KEYS


class TestTask1ResolveListMethod:
    """_resolve_list method must exist."""

    def test_resolve_list_exists(self):
        assert hasattr(ContextManager, "_resolve_list")
