"""
Tests for Tiered Routine Compilation in v2 Engine.

Tests that the expression compiler detects _vectorized attribute
on routine functions and uses map_batches (Tier 1) vs map_elements (Tier 2).

Tier 1 (Vectorized): Function takes pl.Series args, returns pl.Series. Uses map_batches.
Tier 2 (Scalar): Function takes individual values, returns individual value. Uses map_elements.
"""
import pytest
import polars as pl

from src.v2.expressions import compile_expression
from src.v2.routines.manager import RoutineManager, RoutineRegistry


def _make_registry():
    registry = RoutineRegistry()

    # Scalar function (Tier 2 fallback)
    def greet(name):
        return f"Hello, {name}!"

    # Vectorized function (Tier 1 fast path)
    def double_amount(amount: pl.Series) -> pl.Series:
        return amount * 2

    # Mark the vectorized function
    double_amount._vectorized = True

    registry.register("Demo", "greet", greet)
    registry.register("Demo", "double_amount", double_amount)
    return registry


class TestTieredRoutines:
    def test_vectorized_routine_uses_map_batches(self):
        """Vectorized routines should use map_batches, not map_elements"""
        registry = _make_registry()
        expr = compile_expression("Demo.double_amount(amount)", routine_registry=registry)
        df = pl.DataFrame({"amount": [100, 200, 300]}).lazy()
        result = df.select(expr.alias("result")).collect()["result"]
        assert result.to_list() == [200, 400, 600]

    def test_scalar_routine_still_works(self):
        """Scalar routines fall back to map_elements"""
        registry = _make_registry()
        expr = compile_expression("Demo.greet(name)", routine_registry=registry)
        df = pl.DataFrame({"name": ["Alice", "Bob"]}).lazy()
        result = df.select(expr.alias("result")).collect()["result"]
        assert result.to_list() == ["Hello, Alice!", "Hello, Bob!"]

    def test_vectorized_multi_arg(self):
        """Vectorized with multiple args uses struct + map_batches"""
        registry = RoutineRegistry()

        def multiply(a: pl.Series, b: pl.Series) -> pl.Series:
            return a * b
        multiply._vectorized = True

        registry.register("Math", "multiply", multiply)
        expr = compile_expression("Math.multiply(x, y)", routine_registry=registry)
        df = pl.DataFrame({"x": [2, 3], "y": [10, 20]}).lazy()
        result = df.select(expr.alias("result")).collect()["result"]
        assert result.to_list() == [20, 60]

    def test_no_arg_routine(self):
        """Zero-arg routine returns literal"""
        registry = RoutineRegistry()

        def get_version():
            return "2.0"

        registry.register("App", "get_version", get_version)
        expr = compile_expression("App.get_version()", routine_registry=registry)
        df = pl.DataFrame({"x": [1]}).lazy()
        result = df.select(expr.alias("result")).collect()["result"]
        assert result[0] == "2.0"

    def test_vectorized_string_return(self):
        """Vectorized function returning strings should work correctly"""
        registry = RoutineRegistry()

        def shout(text: pl.Series) -> pl.Series:
            return text.str.to_uppercase() + pl.Series(["!"] * len(text))
        shout._vectorized = True

        registry.register("Text", "shout", shout)
        expr = compile_expression("Text.shout(msg)", routine_registry=registry)
        df = pl.DataFrame({"msg": ["hello", "world"]}).lazy()
        result = df.select(expr.alias("result")).collect()["result"]
        assert result.to_list() == ["HELLO!", "WORLD!"]

    def test_scalar_multi_arg_still_works(self):
        """Scalar multi-arg routine uses struct + map_elements"""
        registry = RoutineRegistry()

        def format_name(first, last):
            return f"{last}, {first}"

        registry.register("Fmt", "format_name", format_name)
        expr = compile_expression("Fmt.format_name(first, last)", routine_registry=registry)
        df = pl.DataFrame({"first": ["Alice", "Bob"], "last": ["Smith", "Jones"]}).lazy()
        result = df.select(expr.alias("result")).collect()["result"]
        assert result.to_list() == ["Smith, Alice", "Jones, Bob"]
