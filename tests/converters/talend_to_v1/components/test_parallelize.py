"""Tests for the ParallelizeConverter (tParallelize -> Parallelize)."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.control.parallelize import ParallelizeConverter
from src.converters.talend_to_v1.components.registry import REGISTRY


def _make_node(params=None, schema=None, component_id="parallelize_1",
               component_type="tParallelize"):
    return TalendNode(
        component_id=component_id,
        component_type=component_type,
        params=params or {},
        schema=schema or {},
        position={"x": 320, "y": 160},
        raw_xml=ET.Element("node"),
    )


class TestParallelizeConverterRegistration:
    def test_registered_in_registry(self):
        assert REGISTRY.get("tParallelize") is ParallelizeConverter


class TestParallelizeConverterBasic:
    def test_basic_conversion_with_all_params(self):
        node = _make_node(params={
            "WAIT_FOR": '"All"',
            "SLEEPTIME": '"200"',
            "DIE_ON_ERROR": "true",
        })
        result = ParallelizeConverter().convert(node, [], {})

        assert isinstance(result, ComponentResult)
        comp = result.component
        assert comp["id"] == "parallelize_1"
        assert comp["type"] == "Parallelize"
        assert comp["original_type"] == "tParallelize"
        assert comp["position"] == {"x": 320, "y": 160}
        assert comp["config"]["wait_for"] == "All"
        assert comp["config"]["sleep_time"] == "200"
        assert comp["config"]["die_on_error"] is True
        assert comp["inputs"] == []
        assert comp["outputs"] == []

    def test_defaults_when_params_missing(self):
        node = _make_node(params={})
        result = ParallelizeConverter().convert(node, [], {})

        cfg = result.component["config"]
        assert cfg["wait_for"] == "All"
        assert cfg["sleep_time"] == "100"
        assert cfg["die_on_error"] is False

    def test_die_on_error_false_string(self):
        node = _make_node(params={"DIE_ON_ERROR": "false"})
        result = ParallelizeConverter().convert(node, [], {})

        assert result.component["config"]["die_on_error"] is False

    def test_wait_for_without_quotes(self):
        """WAIT_FOR without surrounding quotes should pass through as-is."""
        node = _make_node(params={"WAIT_FOR": "First"})
        result = ParallelizeConverter().convert(node, [], {})

        assert result.component["config"]["wait_for"] == "First"


class TestParallelizeConverterSchema:
    def test_utility_component_has_empty_schema(self):
        """Parallelize is a utility component -- no data flow schema."""
        node = _make_node(params={"WAIT_FOR": "All"})
        result = ParallelizeConverter().convert(node, [], {})

        assert result.component["schema"] == {"input": [], "output": []}


class TestParallelizeConverterWarnings:
    def test_no_warnings_for_valid_config(self):
        node = _make_node(params={
            "WAIT_FOR": '"All"',
            "SLEEPTIME": '"100"',
            "DIE_ON_ERROR": "false",
        })
        result = ParallelizeConverter().convert(node, [], {})

        assert result.warnings == []
        assert result.needs_review == []

    def test_no_warnings_for_empty_params(self):
        """tParallelize has sensible defaults -- missing params should not warn."""
        node = _make_node(params={})
        result = ParallelizeConverter().convert(node, [], {})

        assert result.warnings == []
        assert result.needs_review == []
