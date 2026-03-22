"""Tests for the LoopConverter (tLoop -> Loop)."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.control.loop import LoopConverter
from src.converters.talend_to_v1.components.registry import REGISTRY


def _make_node(params=None, schema=None, component_id="loop_1",
               component_type="tLoop"):
    return TalendNode(
        component_id=component_id,
        component_type=component_type,
        params=params or {},
        schema=schema or {},
        position={"x": 320, "y": 160},
        raw_xml=ET.Element("node"),
    )


class TestLoopConverterRegistration:
    def test_registered_in_registry(self):
        assert REGISTRY.get("tLoop") is LoopConverter


class TestLoopConverterBasic:
    def test_basic_conversion_with_all_params(self):
        node = _make_node(params={
            "LOOP_TYPE": '"FOR"',
            "START_VALUE": '"1"',
            "END_VALUE": '"100"',
            "STEP_VALUE": '"5"',
            "ITERATE_ON": '"row.column"',
            "DIE_ON_ERROR": "true",
        })
        result = LoopConverter().convert(node, [], {})

        assert isinstance(result, ComponentResult)
        comp = result.component
        assert comp["id"] == "loop_1"
        assert comp["type"] == "Loop"
        assert comp["original_type"] == "tLoop"
        assert comp["position"] == {"x": 320, "y": 160}
        assert comp["config"]["loop_type"] == "FOR"
        assert comp["config"]["start_value"] == "1"
        assert comp["config"]["end_value"] == "100"
        assert comp["config"]["step_value"] == "5"
        assert comp["config"]["iterate_on"] == "row.column"
        assert comp["config"]["die_on_error"] is True
        assert comp["inputs"] == []
        assert comp["outputs"] == []

    def test_defaults_when_params_missing(self):
        node = _make_node(params={})
        result = LoopConverter().convert(node, [], {})

        cfg = result.component["config"]
        assert cfg["loop_type"] == "FOR"
        assert cfg["start_value"] == "0"
        assert cfg["end_value"] == "10"
        assert cfg["step_value"] == "1"
        assert cfg["iterate_on"] == ""
        assert cfg["die_on_error"] is False

    def test_while_loop_type(self):
        """Loop type can be WHILE, not just FOR."""
        node = _make_node(params={"LOOP_TYPE": '"WHILE"'})
        result = LoopConverter().convert(node, [], {})

        assert result.component["config"]["loop_type"] == "WHILE"

    def test_die_on_error_false_string(self):
        node = _make_node(params={"DIE_ON_ERROR": "false"})
        result = LoopConverter().convert(node, [], {})

        assert result.component["config"]["die_on_error"] is False

    def test_iterate_on_without_quotes(self):
        """ITERATE_ON without surrounding quotes should pass through as-is."""
        node = _make_node(params={"ITERATE_ON": "globalMap.get(key)"})
        result = LoopConverter().convert(node, [], {})

        assert result.component["config"]["iterate_on"] == "globalMap.get(key)"


class TestLoopConverterSchema:
    def test_utility_component_has_empty_schema(self):
        """Loop is a utility component -- no data flow schema."""
        node = _make_node(params={"LOOP_TYPE": "FOR"})
        result = LoopConverter().convert(node, [], {})

        assert result.component["schema"] == {"input": [], "output": []}


class TestLoopConverterWarnings:
    def test_no_warnings_for_valid_config(self):
        node = _make_node(params={
            "LOOP_TYPE": '"FOR"',
            "START_VALUE": '"0"',
            "END_VALUE": '"10"',
            "STEP_VALUE": '"1"',
            "ITERATE_ON": '""',
            "DIE_ON_ERROR": "false",
        })
        result = LoopConverter().convert(node, [], {})

        assert result.warnings == []
        assert result.needs_review == []

    def test_no_warnings_for_empty_params(self):
        """tLoop has sensible defaults -- missing params should not warn."""
        node = _make_node(params={})
        result = LoopConverter().convert(node, [], {})

        assert result.warnings == []
        assert result.needs_review == []
