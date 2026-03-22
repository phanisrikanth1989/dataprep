"""Tests for the PrejobConverter (tPrejob -> PrejobComponent)."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.control.prejob import PrejobConverter
from src.converters.talend_to_v1.components.registry import REGISTRY


def _make_node(params=None, schema=None, component_id="prejob_1",
               component_type="tPrejob"):
    return TalendNode(
        component_id=component_id,
        component_type=component_type,
        params=params or {},
        schema=schema or {},
        position={"x": 64, "y": 64},
        raw_xml=ET.Element("node"),
    )


class TestPrejobConverterRegistration:
    def test_registered_in_registry(self):
        assert REGISTRY.get("tPrejob") is PrejobConverter


class TestPrejobConverterBasic:
    def test_basic_conversion(self):
        node = _make_node()
        result = PrejobConverter().convert(node, [], {})

        assert isinstance(result, ComponentResult)
        comp = result.component
        assert comp["id"] == "prejob_1"
        assert comp["type"] == "PrejobComponent"
        assert comp["original_type"] == "tPrejob"
        assert comp["position"] == {"x": 64, "y": 64}
        assert comp["config"] == {}
        assert comp["inputs"] == []
        assert comp["outputs"] == []

    def test_custom_component_id_and_position(self):
        node = TalendNode(
            component_id="prejob_custom_99",
            component_type="tPrejob",
            params={},
            schema={},
            position={"x": 200, "y": 400},
            raw_xml=ET.Element("node"),
        )
        result = PrejobConverter().convert(node, [], {})

        comp = result.component
        assert comp["id"] == "prejob_custom_99"
        assert comp["position"] == {"x": 200, "y": 400}

    def test_extra_params_are_ignored(self):
        """Any unexpected params on the node should not affect output."""
        node = _make_node(params={
            "UNKNOWN_PARAM": "some_value",
            "ANOTHER": "42",
        })
        result = PrejobConverter().convert(node, [], {})

        assert result.component["config"] == {}


class TestPrejobConverterSchema:
    def test_utility_component_has_empty_schema(self):
        """tPrejob is a utility component -- no data flow schema."""
        node = _make_node()
        result = PrejobConverter().convert(node, [], {})

        assert result.component["schema"] == {"input": [], "output": []}


class TestPrejobConverterWarnings:
    def test_no_warnings(self):
        node = _make_node()
        result = PrejobConverter().convert(node, [], {})

        assert result.warnings == []
        assert result.needs_review == []


class TestPrejobConverterConnections:
    def test_connections_do_not_affect_output(self):
        """Connections are not used by tPrejob but should not cause errors."""
        node = _make_node()
        connections = [
            TalendConnection(
                name="trigger_1",
                source="prejob_1",
                target="other_1",
                connector_type="SUBJOB_OK",
            ),
        ]
        result = PrejobConverter().convert(node, connections, {})

        comp = result.component
        assert comp["type"] == "PrejobComponent"
        assert comp["config"] == {}
        assert result.warnings == []
