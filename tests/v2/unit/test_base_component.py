"""
Tests for v2 base component system with apply() interface and registry.

Validates Component, SourceComponent, SinkComponent, TransformComponent,
PythonComponent, UtilityComponent interfaces and ComponentRegistry auto-registration.
"""
import pytest
import polars as pl
from src.v2.components.base import (
    Component, SourceComponent, SinkComponent, TransformComponent, PythonComponent,
)
from src.v2.components.file.file_output_delimited import FileOutputDelimited
from src.v2.components.registry import ComponentRegistry


class TestComponentInterface:
    def test_transform_component_apply(self):
        """TransformComponent.apply() receives and returns Dict[str, LazyFrame]"""
        class DoubleAmount(TransformComponent):
            def apply(self, inputs):
                data = inputs["main"]
                return {"main": data.with_columns((pl.col("amount") * 2).alias("amount"))}

        comp = DoubleAmount("test", {})
        df = pl.DataFrame({"amount": [100, 200]}).lazy()
        result = comp.apply({"main": df})
        assert "main" in result
        assert isinstance(result["main"], pl.LazyFrame)
        collected = result["main"].collect()
        assert collected["amount"].to_list() == [200, 400]

    def test_source_component_produce(self):
        """SourceComponent.apply() ignores inputs, calls produce()"""
        class DummySource(SourceComponent):
            def produce(self):
                return {"main": pl.DataFrame({"id": [1, 2]}).lazy()}

        comp = DummySource("test", {})
        result = comp.apply({})
        assert result["main"].collect()["id"].to_list() == [1, 2]

    def test_sink_component_is_barrier(self):
        class DummySink(SinkComponent):
            def consume(self, inputs):
                pass

        comp = DummySink("test", {})
        assert comp.is_barrier is True

    def test_transform_not_barrier_by_default(self):
        class DummyTransform(TransformComponent):
            def apply(self, inputs):
                return {"main": inputs["main"]}

        comp = DummyTransform("test", {})
        assert comp.is_barrier is False

    def test_validate_returns_empty_by_default(self):
        class DummyTransform(TransformComponent):
            def apply(self, inputs):
                return inputs

        comp = DummyTransform("test", {})
        assert comp.validate() == []

    def test_context_var_resolution(self):
        class PathSource(SourceComponent):
            def produce(self):
                path = self.resolve_context("${context.dir}/file.csv")
                return {"main": pl.DataFrame({"path": [path]}).lazy()}

        comp = PathSource("test", {}, context={"dir": "/data"})
        result = comp.produce()
        assert result["main"].collect()["path"][0] == "/data/file.csv"

    def test_python_component_is_barrier(self):
        """PythonComponent is always a barrier."""
        class DummyPython(PythonComponent):
            def apply(self, inputs):
                return inputs

        comp = DummyPython("test", {})
        assert comp.is_barrier is True

    def test_component_repr(self):
        class DummyTransform(TransformComponent):
            def apply(self, inputs):
                return inputs

        comp = DummyTransform("my_comp", {})
        assert repr(comp) == "DummyTransform(id=my_comp)"

    def test_context_var_no_match_preserves_original(self):
        """Unresolved context variables are preserved as-is."""
        class DummyTransform(TransformComponent):
            def apply(self, inputs):
                return inputs

        comp = DummyTransform("test", {}, context={})
        result = comp.resolve_context("${context.missing}/file.csv")
        assert result == "${context.missing}/file.csv"

    def test_resolve_context_non_string_passthrough(self):
        """Non-string values pass through resolve_context unchanged."""
        class DummyTransform(TransformComponent):
            def apply(self, inputs):
                return inputs

        comp = DummyTransform("test", {})
        assert comp.resolve_context(42) == 42
        assert comp.resolve_context(None) is None

    def test_sink_apply_returns_empty_dict(self):
        """SinkComponent.apply() returns empty dict after consuming."""
        consumed = {}

        class DummySink(SinkComponent):
            def consume(self, inputs):
                consumed["data"] = inputs

        comp = DummySink("test", {})
        df = pl.DataFrame({"x": [1]}).lazy()
        result = comp.apply({"main": df})
        assert result == {}
        assert "data" in consumed


class TestRegistry:
    def test_register_decorator(self):
        registry = ComponentRegistry()

        @registry.register("test_comp", "test_alias")
        class TestComp(TransformComponent):
            def apply(self, inputs):
                return inputs

        assert registry.get("test_comp") is TestComp
        assert registry.get("test_alias") is TestComp

    def test_get_unknown_returns_none(self):
        registry = ComponentRegistry()
        assert registry.get("nonexistent") is None

    def test_list_registered(self):
        registry = ComponentRegistry()

        @registry.register("comp_a")
        class CompA(TransformComponent):
            def apply(self, inputs):
                return inputs

        names = registry.list_types()
        assert "comp_a" in names

    def test_register_case_insensitive(self):
        """Registry lookups are case-insensitive."""
        registry = ComponentRegistry()

        @registry.register("MyComponent")
        class MyComp(TransformComponent):
            def apply(self, inputs):
                return inputs

        assert registry.get("mycomponent") is MyComp
        assert registry.get("MYCOMPONENT") is MyComp

    def test_list_types_sorted(self):
        """list_types() returns sorted unique names."""
        registry = ComponentRegistry()

        @registry.register("zebra", "alpha")
        class Comp1(TransformComponent):
            def apply(self, inputs):
                return inputs

        names = registry.list_types()
        assert names == ["alpha", "zebra"]

    def test_aud_reg_01_bug(self):
        """
        AUD-REG-01 regression (Phase 1.1 Tier 1 fix).

        Duplicate registration under the same name by a DIFFERENT component
        class must raise ValueError, not silently overwrite. PITFALLS #7
        prevention rule: registry fragility — "duplicate registration raises
        ValueError (not silent overwrite)". CLAUDE.md Architecture §Registry
        decorator case-insensitive: "Decorator collision raises ValueError".
        """
        registry = ComponentRegistry()

        @registry.register("duplicate_name")
        class FirstComp(TransformComponent):
            def apply(self, inputs):
                return inputs

        # Attempting to register a DIFFERENT class under the same name must raise.
        with pytest.raises(ValueError) as exc_info:
            @registry.register("duplicate_name")
            class SecondComp(TransformComponent):
                def apply(self, inputs):
                    return inputs

        # Error message must identify both the incumbent and the new class.
        msg = str(exc_info.value).lower()
        assert "duplicate_name" in msg
        assert "firstcomp" in msg
        assert "secondcomp" in msg

        # Incumbent must be unchanged (not silently overwritten).
        assert registry.get("duplicate_name") is FirstComp

    def test_aud_reg_01_idempotent_re_registration_allowed(self):
        """
        AUD-REG-01 idempotency guarantee.

        The duplicate-check uses `is not cls` so that registering the SAME
        class under the SAME name twice is a no-op. This matters for test
        reloads and import-side-effect idempotency.
        """
        registry = ComponentRegistry()

        @registry.register("same_name")
        class SameComp(TransformComponent):
            def apply(self, inputs):
                return inputs

        # Re-registering the identical class under the identical name must be a no-op.
        registry.register("same_name")(SameComp)
        assert registry.get("same_name") is SameComp

    def test_aud_reg_01_case_insensitive_collision(self):
        """
        AUD-REG-01 case-insensitive collision detection.

        Registry is case-insensitive (names stored lowercased), so a
        collision under "Foo" vs "foo" vs "FOO" must all raise ValueError.
        """
        registry = ComponentRegistry()

        @registry.register("Foo")
        class FooComp(TransformComponent):
            def apply(self, inputs):
                return inputs

        with pytest.raises(ValueError):
            @registry.register("FOO")
            class FooCompDifferent(TransformComponent):
                def apply(self, inputs):
                    return inputs

        # Incumbent preserved under lowercased key
        assert registry.get("foo") is FooComp


class TestUtilityComponent:
    def test_is_barrier(self):
        from src.v2.components.base import UtilityComponent

        class DummyUtility(UtilityComponent):
            def apply(self, inputs):
                return {}

        comp = DummyUtility("u1", {})
        assert comp.is_barrier is True

    def test_inherits_component(self):
        from src.v2.components.base import UtilityComponent, Component

        assert issubclass(UtilityComponent, Component)


class TestSinkOutputValidation:
    """Test sink schema validation."""

    def test_sink_validates_column_types(self, tmp_path):
        """Sink with schema should validate column types before writing."""
        output_file = tmp_path / "out.csv"
        comp = FileOutputDelimited("write", {
            "path": str(output_file),
            "schema": [
                {"name": "id", "type": "integer"},
                {"name": "name", "type": "string"},
            ],
        })
        df = pl.DataFrame({"id": [1, 2], "name": ["a", "b"]})
        comp.consume({"main": df.lazy()})
        assert output_file.exists()

    def test_sink_rejects_wrong_column_type(self, tmp_path):
        """Sink should crash if column type doesn't match schema."""
        output_file = tmp_path / "out.csv"
        comp = FileOutputDelimited("write", {
            "path": str(output_file),
            "schema": [
                {"name": "id", "type": "integer"},
                {"name": "amount", "type": "float"},
            ],
        })
        df = pl.DataFrame({"id": [1], "amount": ["not_a_float"]})
        with pytest.raises(ValueError, match="expected Float64, got String"):
            comp.consume({"main": df.lazy()})

    def test_sink_rejects_missing_column(self, tmp_path):
        """Sink should crash if expected column is missing."""
        output_file = tmp_path / "out.csv"
        comp = FileOutputDelimited("write", {
            "path": str(output_file),
            "schema": [
                {"name": "id", "type": "integer"},
                {"name": "missing_col", "type": "string"},
            ],
        })
        df = pl.DataFrame({"id": [1]})
        with pytest.raises(ValueError, match="not found"):
            comp.consume({"main": df.lazy()})

    def test_sink_no_schema_writes_anything(self, tmp_path):
        """Sink without schema should write any data without validation."""
        output_file = tmp_path / "out.csv"
        comp = FileOutputDelimited("write", {
            "path": str(output_file),
        })
        df = pl.DataFrame({"anything": ["goes"]})
        comp.consume({"main": df.lazy()})
        assert output_file.exists()
