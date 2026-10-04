"""
Tests for Python Code Components in v2 Engine.

Tests:
- PythonCode component
- PythonRow component (scalar and vectorized modes)
- PythonDataFrame component
"""
import pytest
import polars as pl

from src.v2.components.python import PythonCode, PythonRow, PythonDataFrame

# Check optional dependencies
try:
    import numpy  # noqa: F401
    _has_numpy = True
except ImportError:
    _has_numpy = False

try:
    import pyarrow  # noqa: F401
    _has_pyarrow = True
except ImportError:
    _has_pyarrow = False


class TestPythonCode:
    """Tests for PythonCode component."""

    def test_simple_filter(self):
        comp = PythonCode("pc", {"code": "output_df = input_df.filter(pl.col('x') > 1)"})
        df = pl.DataFrame({"x": [1, 2, 3]}).lazy()
        result = comp.apply({"main": df})
        assert result["main"].collect()["x"].to_list() == [2, 3]

    def test_add_column(self):
        comp = PythonCode("pc", {"code": "output_df = input_df.with_columns((pl.col('a') * 2).alias('b'))"})
        df = pl.DataFrame({"a": [1, 2]}).lazy()
        result = comp.apply({"main": df})
        assert result["main"].collect()["b"].to_list() == [2, 4]

    def test_context_available(self):
        comp = PythonCode(
            "pc",
            {"code": "output_df = input_df.with_columns(pl.lit(context['rate']).alias('rate'))"},
            context={"rate": 0.05},
        )
        df = pl.DataFrame({"a": [1]}).lazy()
        result = comp.apply({"main": df})
        assert result["main"].collect()["rate"][0] == 0.05

    def test_returns_lazyframe(self):
        comp = PythonCode("pc", {"code": "output_df = input_df"})
        df = pl.DataFrame({"a": [1]}).lazy()
        result = comp.apply({"main": df})
        assert isinstance(result["main"], pl.LazyFrame)

    def test_is_barrier(self):
        comp = PythonCode("pc", {"code": "output_df = input_df"})
        assert comp.is_barrier is True

    def test_no_input_returns_empty(self):
        comp = PythonCode("pc", {"code": "output_df = input_df"})
        result = comp.apply({})
        assert result == {}

    def test_missing_output_df_raises(self):
        comp = PythonCode("pc", {"code": "x = 1"})
        df = pl.DataFrame({"a": [1]}).lazy()
        with pytest.raises(RuntimeError, match="output_df"):
            comp.apply({"main": df})

    def test_syntax_error_raises(self):
        comp = PythonCode("pc", {"code": "def :"})
        df = pl.DataFrame({"a": [1]}).lazy()
        with pytest.raises(ValueError, match="Syntax"):
            comp.apply({"main": df})

    def test_validate_missing_code(self):
        comp = PythonCode("pc", {})
        assert len(comp.validate()) > 0

    def test_validate_empty_code(self):
        comp = PythonCode("pc", {"code": "  "})
        assert len(comp.validate()) > 0

    def test_validate_valid(self):
        comp = PythonCode("pc", {"code": "output_df = input_df"})
        assert comp.validate() == []

    def test_imports(self):
        comp = PythonCode(
            "pc",
            {
                "code": "output_df = input_df.with_columns(pl.lit(json.dumps({'a': 1})).alias('j'))",
                "imports": ["json"],
            },
        )
        df = pl.DataFrame({"x": [1]}).lazy()
        result = comp.apply({"main": df})
        assert result["main"].collect()["j"][0] == '{"a": 1}'

    def test_code_cache(self):
        # Clear cache first to avoid interference from other tests
        PythonCode._code_cache.clear()
        code = "output_df = input_df"
        comp1 = PythonCode("pc1", {"code": code})
        comp2 = PythonCode("pc2", {"code": code})
        df = pl.DataFrame({"a": [1]}).lazy()
        comp1.apply({"main": df})
        comp2.apply({"main": df})
        # Both should use the same cached compiled code
        assert comp1._compiled_code is comp2._compiled_code

    def test_registry(self):
        from src.v2.components.registry import REGISTRY
        assert REGISTRY.get("python_code") is not None

    def test_runtime_error_in_code(self):
        comp = PythonCode("pc", {"code": "x = 1/0\noutput_df = input_df"})
        df = pl.DataFrame({"a": [1]}).lazy()
        with pytest.raises(RuntimeError, match="PythonCode execution failed"):
            comp.apply({"main": df})

    def test_accepts_eager_dataframe_input(self):
        """apply() should also handle eager DataFrame as input."""
        comp = PythonCode("pc", {"code": "output_df = input_df"})
        df = pl.DataFrame({"a": [1, 2]})
        result = comp.apply({"main": df})
        assert isinstance(result["main"], pl.LazyFrame)
        assert result["main"].collect()["a"].to_list() == [1, 2]

    def test_output_lazyframe_passthrough(self):
        """If code produces a LazyFrame, it should be returned as-is."""
        comp = PythonCode("pc", {"code": "output_df = input_df.lazy()"})
        df = pl.DataFrame({"a": [1]}).lazy()
        result = comp.apply({"main": df})
        assert isinstance(result["main"], pl.LazyFrame)


class TestPythonDataFrame:
    """Tests for PythonDataFrame component."""

    def test_simple_transform(self):
        comp = PythonDataFrame("pdf", {"code": "output_df = df.with_columns((pl.col('a') + 1).alias('b'))"})
        df = pl.DataFrame({"a": [1, 2]}).lazy()
        result = comp.apply({"main": df})
        assert result["main"].collect()["b"].to_list() == [2, 3]

    def test_is_barrier(self):
        comp = PythonDataFrame("pdf", {"code": "output_df = df"})
        assert comp.is_barrier is True

    def test_returns_lazyframe(self):
        comp = PythonDataFrame("pdf", {"code": "output_df = df"})
        df = pl.DataFrame({"a": [1]}).lazy()
        result = comp.apply({"main": df})
        assert isinstance(result["main"], pl.LazyFrame)

    def test_validate_missing_code(self):
        comp = PythonDataFrame("pdf", {})
        assert len(comp.validate()) > 0

    def test_validate_empty_code(self):
        comp = PythonDataFrame("pdf", {"code": "  "})
        assert len(comp.validate()) > 0

    def test_validate_valid(self):
        comp = PythonDataFrame("pdf", {"code": "output_df = df"})
        assert comp.validate() == []

    def test_registry(self):
        from src.v2.components.registry import REGISTRY
        assert REGISTRY.get("python_dataframe") is not None

    def test_no_input_returns_empty(self):
        comp = PythonDataFrame("pdf", {"code": "output_df = df"})
        result = comp.apply({})
        assert result == {}

    @pytest.mark.skipif(
        not _has_pyarrow,
        reason="pyarrow not installed (needed for pandas conversion)",
    )
    def test_pandas_mode(self):
        comp = PythonDataFrame(
            "pdf",
            {
                "code": "df['doubled'] = df['value'] * 2\noutput_df = df",
                "use_pandas": True,
            },
        )
        df = pl.DataFrame({"id": [1, 2, 3], "value": [10, 20, 30]}).lazy()
        result = comp.apply({"main": df})
        collected = result["main"].collect()
        assert "doubled" in collected.columns
        assert collected["doubled"].to_list() == [20, 40, 60]

    def test_groupby_aggregation(self):
        comp = PythonDataFrame(
            "pdf",
            {"code": "output_df = df.group_by('category').agg(pl.col('value').sum().alias('total'))"},
        )
        df = pl.DataFrame({
            "category": ["A", "A", "B", "B", "B"],
            "value": [10, 20, 5, 15, 10],
        }).lazy()
        result = comp.apply({"main": df})
        collected = result["main"].collect()
        totals = dict(zip(collected["category"].to_list(), collected["total"].to_list()))
        assert totals["A"] == 30
        assert totals["B"] == 30

    def test_missing_output_df_raises(self):
        comp = PythonDataFrame("pdf", {"code": "x = 1"})
        df = pl.DataFrame({"a": [1]}).lazy()
        with pytest.raises(RuntimeError, match="output_df"):
            comp.apply({"main": df})

    def test_runtime_error_in_code(self):
        comp = PythonDataFrame("pdf", {"code": "1/0"})
        df = pl.DataFrame({"a": [1]}).lazy()
        with pytest.raises(RuntimeError, match="PythonDataFrame execution failed"):
            comp.apply({"main": df})

    @pytest.mark.skipif(
        not _has_numpy,
        reason="numpy not installed",
    )
    def test_numpy_available(self):
        """np should be available in the execution environment."""
        comp = PythonDataFrame(
            "pdf",
            {"code": "output_df = df.with_columns(pl.lit(int(np.sum([1, 2, 3]))).alias('np_sum'))"},
        )
        df = pl.DataFrame({"a": [1]}).lazy()
        result = comp.apply({"main": df})
        assert result["main"].collect()["np_sum"][0] == 6

    def test_set_routine_manager(self):
        comp = PythonDataFrame("pdf", {"code": "output_df = df"})
        assert comp._routine_manager is None
        comp.set_routine_manager("fake_manager")
        assert comp._routine_manager == "fake_manager"


class TestPythonRow:
    """Tests for PythonRow component."""

    def test_scalar_mode(self):
        comp = PythonRow("pr", {
            "code": "return {'full': row['first'] + ' ' + row['last']}",
            "output_columns": [{"name": "full", "type": "String"}],
            "pass_through": False,
        })
        df = pl.DataFrame({"first": ["A", "B"], "last": ["X", "Y"]}).lazy()
        result = comp.apply({"main": df})
        collected = result["main"].collect()
        assert collected["full"].to_list() == ["A X", "B Y"]

    def test_is_barrier(self):
        comp = PythonRow("pr", {"code": "return {}", "output_columns": []})
        assert comp.is_barrier is True

    def test_returns_lazyframe(self):
        comp = PythonRow("pr", {
            "code": "return {'x': row['a'] * 2}",
            "output_columns": [{"name": "x", "type": "Integer"}],
            "pass_through": False,
        })
        df = pl.DataFrame({"a": [1]}).lazy()
        result = comp.apply({"main": df})
        assert isinstance(result["main"], pl.LazyFrame)

    def test_validate_missing_code(self):
        comp = PythonRow("pr", {"output_columns": []})
        assert len(comp.validate()) > 0

    def test_validate_missing_output_columns(self):
        comp = PythonRow("pr", {"code": "return {}"})
        assert len(comp.validate()) > 0

    def test_validate_valid(self):
        comp = PythonRow("pr", {
            "code": "return {}",
            "output_columns": [{"name": "x", "type": "String"}],
        })
        assert comp.validate() == []

    def test_registry(self):
        from src.v2.components.registry import REGISTRY
        assert REGISTRY.get("python_row") is not None

    def test_no_input_returns_empty(self):
        comp = PythonRow("pr", {"code": "return {}", "output_columns": []})
        result = comp.apply({})
        assert result == {}

    def test_pass_through_columns(self):
        comp = PythonRow("pr", {
            "code": "return {'doubled': row['a'] * 2}",
            "output_columns": [{"name": "doubled", "type": "Integer"}],
            "pass_through": True,
        })
        df = pl.DataFrame({"a": [1, 2], "b": ["x", "y"]}).lazy()
        result = comp.apply({"main": df})
        collected = result["main"].collect()
        assert "a" in collected.columns  # pass-through
        assert "b" in collected.columns  # pass-through
        assert collected["doubled"].to_list() == [2, 4]

    def test_vectorized_mode(self):
        comp = PythonRow("pr", {
            "code": "return [{'total': r['price'] * r['qty']} for r in rows]",
            "mode": "vectorized",
            "batch_size": 100,
            "output_columns": [{"name": "total", "type": "Float"}],
            "pass_through": False,
        })
        df = pl.DataFrame({
            "price": [10.0, 20.0, 15.0],
            "qty": [2, 3, 4],
        }).lazy()
        result = comp.apply({"main": df})
        assert result["main"].collect()["total"].to_list() == [20.0, 60.0, 60.0]

    def test_scalar_with_context(self):
        comp = PythonRow("pr", {
            "code": "return {'final': row['price'] * (1 - context.get('discount', 0))}",
            "output_columns": [{"name": "final", "type": "Float"}],
            "pass_through": False,
        }, context={"discount": 0.2})
        df = pl.DataFrame({"price": [100.0, 50.0]}).lazy()
        result = comp.apply({"main": df})
        collected = result["main"].collect()
        assert collected["final"][0] == 80.0
        assert collected["final"][1] == 40.0

    def test_validate_invalid_mode(self):
        comp = PythonRow("pr", {
            "code": "return {}",
            "mode": "invalid",
            "output_columns": [],
        })
        errors = comp.validate()
        assert any("mode" in e for e in errors)

    def test_validate_invalid_output_type(self):
        comp = PythonRow("pr", {
            "code": "return {}",
            "output_columns": [{"name": "x", "type": "UnknownType"}],
        })
        errors = comp.validate()
        assert any("unknown type" in e.lower() for e in errors)

    def test_large_dataframe_scalar(self):
        comp = PythonRow("pr", {
            "code": "return {'doubled': row['value'] * 2}",
            "output_columns": [{"name": "doubled", "type": "Integer"}],
            "pass_through": False,
        })
        large_df = pl.DataFrame({"value": list(range(1000))}).lazy()
        result = comp.apply({"main": large_df})
        collected = result["main"].collect()
        assert len(collected) == 1000
        assert collected["doubled"][0] == 0
        assert collected["doubled"][999] == 1998


class TestPythonComponentsCodeCache:
    """Tests for code caching behavior across Python components."""

    def test_python_code_cache_shared(self):
        PythonCode._code_cache.clear()
        code = "output_df = input_df"
        comp1 = PythonCode("c1", {"code": code})
        comp2 = PythonCode("c2", {"code": code})
        df = pl.DataFrame({"a": [1]}).lazy()
        comp1.apply({"main": df})
        comp2.apply({"main": df})
        assert comp1._compiled_code is comp2._compiled_code

    def test_python_row_cache_shared(self):
        PythonRow._code_cache.clear()
        code = "return {'x': row['a']}"
        comp1 = PythonRow("r1", {"code": code, "output_columns": [{"name": "x", "type": "Integer"}], "pass_through": False})
        comp2 = PythonRow("r2", {"code": code, "output_columns": [{"name": "x", "type": "Integer"}], "pass_through": False})
        df = pl.DataFrame({"a": [1]}).lazy()
        comp1.apply({"main": df})
        comp2.apply({"main": df})
        assert comp1._row_func is comp2._row_func
