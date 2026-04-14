"""Tests for ComponentRegistry -- decorator-based engine component registry.

Covers: registration, lookup, duplicate detection, decorator pattern, len/contains.
Tests for StubComponent fixture are included since it is created alongside the registry.

Each test creates a fresh ComponentRegistry() instance (NOT the module-level
REGISTRY singleton) to ensure test isolation.
"""
import pytest
import pandas as pd

from src.v1.engine.component_registry import ComponentRegistry
from src.v1.engine.exceptions import ComponentExecutionError
from tests.v1.engine.conftest import StubComponent, make_stub_component


# ---------------------------------------------------------------------------
# TestComponentRegistryRegistration
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestComponentRegistryRegistration:
    """Tests for registering components."""

    def test_register_single_name(self):
        """Register a class under one name, get() returns it."""
        registry = ComponentRegistry()

        @registry.register("TestComp")
        class MyComp(StubComponent):
            pass

        assert registry.get("TestComp") is MyComp

    def test_register_multiple_names(self):
        """Register under two names, both get() calls return same class."""
        registry = ComponentRegistry()

        @registry.register("TestComp", "tTestComp")
        class MyComp(StubComponent):
            pass

        assert registry.get("TestComp") is MyComp
        assert registry.get("tTestComp") is MyComp

    def test_register_duplicate_name_different_class_raises(self):
        """Register ClassA under 'TestComp', then ClassB -> ValueError."""
        registry = ComponentRegistry()

        @registry.register("TestComp")
        class ClassA(StubComponent):
            pass

        with pytest.raises(ValueError, match="TestComp"):
            @registry.register("TestComp")
            class ClassB(StubComponent):
                pass

    def test_register_same_class_same_name_idempotent(self):
        """Register same class under same name twice -> no error."""
        registry = ComponentRegistry()

        @registry.register("TestComp")
        class MyComp(StubComponent):
            pass

        # Re-registering should not raise
        registry.register("TestComp")(MyComp)
        assert registry.get("TestComp") is MyComp

    def test_register_returns_original_class(self):
        """Verify decorator returns the class unchanged (not a wrapper)."""
        registry = ComponentRegistry()

        @registry.register("TestComp")
        class MyComp(StubComponent):
            pass

        # The class itself should be returned, not a wrapper
        assert MyComp.__name__ == "MyComp"
        assert issubclass(MyComp, StubComponent)


# ---------------------------------------------------------------------------
# TestComponentRegistryLookup
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestComponentRegistryLookup:
    """Tests for looking up registered components."""

    def test_get_registered_returns_class(self):
        """get() after registration returns the class."""
        registry = ComponentRegistry()

        @registry.register("TestComp")
        class MyComp(StubComponent):
            pass

        assert registry.get("TestComp") is MyComp

    def test_get_unregistered_returns_none(self):
        """get() for unregistered name returns None."""
        registry = ComponentRegistry()
        assert registry.get("NonExistent") is None

    def test_contains_registered(self):
        """'TestComp' in registry -> True after registration."""
        registry = ComponentRegistry()

        @registry.register("TestComp")
        class MyComp(StubComponent):
            pass

        assert "TestComp" in registry

    def test_contains_unregistered(self):
        """'NonExistent' in registry -> False."""
        registry = ComponentRegistry()
        assert "NonExistent" not in registry

    def test_len_empty(self):
        """Fresh registry -> len == 0."""
        registry = ComponentRegistry()
        assert len(registry) == 0

    def test_len_after_registrations(self):
        """Register under 3 names -> len == 3."""
        registry = ComponentRegistry()

        @registry.register("Alpha", "Beta", "Gamma")
        class MyComp(StubComponent):
            pass

        assert len(registry) == 3

    def test_list_types_sorted(self):
        """Register 'Zebra', 'Apple', 'Mango' -> list_types returns sorted."""
        registry = ComponentRegistry()

        @registry.register("Zebra", "Apple", "Mango")
        class MyComp(StubComponent):
            pass

        assert registry.list_types() == ["Apple", "Mango", "Zebra"]

    def test_list_types_empty(self):
        """Fresh registry -> list_types returns []."""
        registry = ComponentRegistry()
        assert registry.list_types() == []


# ---------------------------------------------------------------------------
# TestComponentRegistryDecoratorPattern
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestComponentRegistryDecoratorPattern:
    """Tests verifying the decorator-based usage pattern."""

    def test_decorator_usage(self):
        """Use @registry.register() on a class, verify it works."""
        registry = ComponentRegistry()

        @registry.register("TestComp", "tTestComp")
        class MyComponent(StubComponent):
            pass

        assert registry.get("TestComp") is MyComponent
        assert registry.get("tTestComp") is MyComponent


# ---------------------------------------------------------------------------
# TestStubComponent
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestStubComponent:
    """Tests for StubComponent test fixture."""

    def test_process_returns_output_data(self):
        """StubComponent._process() returns main DataFrame from config['output_data']."""
        output_data = [{"id": 1, "name": "alice"}, {"id": 2, "name": "bob"}]
        comp = make_stub_component("stub1", config={"output_data": output_data})
        result = comp._process(None)
        assert "main" in result
        assert isinstance(result["main"], pd.DataFrame)
        assert len(result["main"]) == 2
        assert list(result["main"]["name"]) == ["alice", "bob"]

    def test_process_with_should_fail_raises(self):
        """StubComponent._process() with should_fail=True raises ComponentExecutionError."""
        comp = make_stub_component("stub1", config={"should_fail": True})
        with pytest.raises(ComponentExecutionError, match="stub1"):
            comp._process(None)

    def test_process_with_reject_data(self):
        """StubComponent._process() with reject_data returns reject DataFrame."""
        reject_data = [{"id": 1, "error": "bad"}]
        comp = make_stub_component(
            "stub1",
            config={
                "output_data": [{"id": 1, "name": "alice"}],
                "reject_data": reject_data,
            },
        )
        result = comp._process(None)
        assert "reject" in result
        assert isinstance(result["reject"], pd.DataFrame)
        assert len(result["reject"]) == 1

    def test_process_passthrough_input(self):
        """StubComponent._process() with no output_data passes through input_data."""
        comp = make_stub_component("stub1", config={})
        input_df = pd.DataFrame({"x": [1, 2, 3]})
        result = comp._process(input_df)
        assert "main" in result
        pd.testing.assert_frame_equal(result["main"], input_df)

    def test_process_no_output_no_input_returns_empty(self):
        """StubComponent._process() with no output_data and no input returns empty DataFrame."""
        comp = make_stub_component("stub1", config={})
        result = comp._process(None)
        assert "main" in result
        assert isinstance(result["main"], pd.DataFrame)
        assert len(result["main"]) == 0
