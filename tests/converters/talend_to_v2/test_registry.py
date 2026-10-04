from __future__ import annotations

import pytest

from src.converters.talend_to_v2.components.base import (
    ComponentConverter,
    ComponentResult,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v2.components.registry import ConverterRegistry


class _DummyConverter(ComponentConverter):
    """Minimal concrete converter for testing."""

    def convert(
        self,
        node: TalendNode,
        connections: list[TalendConnection],
        context: dict,
    ) -> ComponentResult:
        return ComponentResult(component={}, flows=[], warnings=[], needs_review=[])


class _AnotherConverter(ComponentConverter):
    """Second dummy converter for alias tests."""

    def convert(
        self,
        node: TalendNode,
        connections: list[TalendConnection],
        context: dict,
    ) -> ComponentResult:
        return ComponentResult(component={}, flows=[], warnings=[], needs_review=[])


class TestConverterRegistry:
    """Tests for ConverterRegistry."""

    def test_register_and_get(self) -> None:
        registry = ConverterRegistry()

        @registry.register("tFoo")
        class FooConverter(_DummyConverter):
            pass

        assert registry.get("tFoo") is FooConverter

    def test_get_unknown_returns_none(self) -> None:
        registry = ConverterRegistry()
        assert registry.get("tNonExistent") is None

    def test_register_multiple_aliases(self) -> None:
        registry = ConverterRegistry()

        @registry.register("tBar", "tBarRow")
        class BarConverter(_DummyConverter):
            pass

        assert registry.get("tBar") is BarConverter
        assert registry.get("tBarRow") is BarConverter

    def test_case_sensitive_lookup(self) -> None:
        registry = ConverterRegistry()

        @registry.register("tFileInputDelimited")
        class FIDConverter(_DummyConverter):
            pass

        assert registry.get("tFileInputDelimited") is FIDConverter
        assert registry.get("tfileinputdelimited") is None
        assert registry.get("TFILEINPUTDELIMITED") is None

    def test_duplicate_registration_raises(self) -> None:
        registry = ConverterRegistry()

        @registry.register("tFoo")
        class First(_DummyConverter):
            pass

        with pytest.raises(ValueError, match="already registered"):

            @registry.register("tFoo")
            class Second(_DummyConverter):
                pass

    def test_list_types_sorted(self) -> None:
        registry = ConverterRegistry()

        @registry.register("tZebra")
        class ZebraConverter(_DummyConverter):
            pass

        @registry.register("tApple", "tBanana")
        class FruitConverter(_DummyConverter):
            pass

        assert registry.list_types() == ["tApple", "tBanana", "tZebra"]
