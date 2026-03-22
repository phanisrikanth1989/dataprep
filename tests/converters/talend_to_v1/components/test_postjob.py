"""Tests for the PostjobConverter (tPostjob -> PostjobComponent)."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.control.postjob import PostjobConverter
from src.converters.talend_to_v1.components.registry import REGISTRY


def _make_node(params=None, schema=None, component_id="postjob_1",
               component_type="tPostjob"):
    return TalendNode(
        component_id=component_id,
        component_type=component_type,
        params=params or {},
        schema=schema or {},
        position={"x": 512, "y": 64},
        raw_xml=ET.Element("node"),
    )


class TestPostjobConverterRegistration:
    def test_registered_in_registry(self):
        assert REGISTRY.get("tPostjob") is PostjobConverter


class TestPostjobConverterBasic:
    def test_basic_conversion(self):
        node = _make_node()
        result = PostjobConverter().convert(node, [], {})

        assert isinstance(result, ComponentResult)
        comp = result.component
        assert comp["id"] == "postjob_1"
        assert comp["type"] == "PostjobComponent"
        assert comp["original_type"] == "tPostjob"
        assert comp["position"] == {"x": 512, "y": 64}
        assert comp["config"] == {}
        assert comp["inputs"] == []
        assert comp["outputs"] == []

    def test_custom_component_id_and_position(self):
        node = TalendNode(
            component_id="postjob_custom_42",
            component_type="tPostjob",
            params={},
            schema={},
            position={"x": 800, "y": 300},
            raw_xml=ET.Element("node"),
        )
        result = PostjobConverter().convert(node, [], {})

        comp = result.component
        assert comp["id"] == "postjob_custom_42"
        assert comp["position"] == {"x": 800, "y": 300}

    def test_extra_params_are_ignored(self):
        """Any unexpected params on the node should not affect output."""
        node = _make_node(params={
            "UNKNOWN_PARAM": "some_value",
            "ANOTHER": "42",
        })
        result = PostjobConverter().convert(node, [], {})

        assert result.component["config"] == {}


class TestPostjobConverterSchema:
    def test_utility_component_has_empty_schema(self):
        """tPostjob is a utility component -- no data flow schema."""
        node = _make_node()
        result = PostjobConverter().convert(node, [], {})

        assert result.component["schema"] == {"input": [], "output": []}


class TestPostjobConverterWarnings:
    def test_no_warnings(self):
        node = _make_node()
        result = PostjobConverter().convert(node, [], {})

        assert result.warnings == []
        assert result.needs_review == []


class TestPostjobConverterConnections:
    def test_connections_do_not_affect_output(self):
        """Connections are not used by tPostjob but should not cause errors."""
        node = _make_node()
        connections = [
            TalendConnection(
                name="trigger_1",
                source="other_1",
                target="postjob_1",
                connector_type="SUBJOB_OK",
            ),
        ]
        result = PostjobConverter().convert(node, connections, {})

        comp = result.component
        assert comp["type"] == "PostjobComponent"
        assert comp["config"] == {}
        assert result.warnings == []
