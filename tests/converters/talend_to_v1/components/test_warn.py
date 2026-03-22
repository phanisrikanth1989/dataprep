"""Tests for the WarnConverter (tWarn -> Warn)."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    TalendNode,
)
from src.converters.talend_to_v1.components.control.warn import WarnConverter
from src.converters.talend_to_v1.components.registry import REGISTRY


def _make_node(params=None, schema=None, component_id="warn_1",
               component_type="tWarn"):
    return TalendNode(
        component_id=component_id,
        component_type=component_type,
        params=params or {},
        schema=schema or {},
        position={"x": 320, "y": 160},
        raw_xml=ET.Element("node"),
    )


class TestWarnConverterRegistration:
    def test_registered_in_registry(self):
        assert REGISTRY.get("tWarn") is WarnConverter


class TestWarnConverterBasic:
    def test_basic_conversion(self):
        node = _make_node(params={
            "MESSAGE": '"Something went wrong"',
            "CODE": "42",
            "PRIORITY": "2",
        })
        result = WarnConverter().convert(node, [], {})

        assert isinstance(result, ComponentResult)
        comp = result.component
        assert comp["id"] == "warn_1"
        assert comp["type"] == "Warn"
        assert comp["original_type"] == "tWarn"
        assert comp["position"] == {"x": 320, "y": 160}
        assert comp["config"]["message"] == "Something went wrong"
        assert comp["config"]["code"] == 42
        assert comp["config"]["priority"] == 2
        assert comp["schema"] == {"input": [], "output": []}
        assert comp["inputs"] == []
        assert comp["outputs"] == []

    def test_defaults_when_params_missing(self):
        node = _make_node(params={})
        result = WarnConverter().convert(node, [], {})

        assert result.component["config"]["message"] == "Warning"
        assert result.component["config"]["code"] == 0
        assert result.component["config"]["priority"] == 4

    def test_quoted_code_and_priority(self):
        """CODE and PRIORITY may arrive as quoted strings from XML."""
        node = _make_node(params={
            "MESSAGE": '"Check data"',
            "CODE": '"7"',
            "PRIORITY": '"3"',
        })
        result = WarnConverter().convert(node, [], {})

        assert result.component["config"]["message"] == "Check data"
        assert result.component["config"]["code"] == 7
        assert result.component["config"]["priority"] == 3

    def test_non_numeric_code_falls_back_to_default(self):
        """Non-numeric CODE should fall back to the default of 0."""
        node = _make_node(params={
            "MESSAGE": '"alert"',
            "CODE": "abc",
            "PRIORITY": "xyz",
        })
        result = WarnConverter().convert(node, [], {})

        assert result.component["config"]["code"] == 0
        assert result.component["config"]["priority"] == 4


class TestWarnConverterSchema:
    def test_utility_component_has_empty_schema(self):
        """Warn is a utility component — no data flow schema."""
        node = _make_node(params={"MESSAGE": '"test"'})
        result = WarnConverter().convert(node, [], {})

        assert result.component["schema"] == {"input": [], "output": []}


class TestWarnConverterWarnings:
    def test_no_warnings_produced(self):
        node = _make_node(params={
            "MESSAGE": '"hello"',
            "CODE": "1",
            "PRIORITY": "5",
        })
        result = WarnConverter().convert(node, [], {})

        assert result.warnings == []
        assert result.needs_review == []
