import pytest

from src.converters.talend_to_v1.components.registry import ConverterRegistry


def test_register_and_get():
    reg = ConverterRegistry()

    @reg.register("tFoo")
    class FooConverter:
        pass

    assert reg.get("tFoo") is FooConverter
    assert reg.get("tBar") is None


def test_multi_register():
    reg = ConverterRegistry()

    @reg.register("tFoo", "tBar")
    class FooConverter:
        pass

    assert reg.get("tFoo") is FooConverter
    assert reg.get("tBar") is FooConverter


def test_list_types():
    reg = ConverterRegistry()

    @reg.register("tBeta", "tAlpha")
    class Converter:
        pass

    assert reg.list_types() == ["tAlpha", "tBeta"]


def test_duplicate_raises():
    reg = ConverterRegistry()

    @reg.register("tFoo")
    class First:
        pass

    with pytest.raises(ValueError):
        @reg.register("tFoo")
        class Second:
            pass
