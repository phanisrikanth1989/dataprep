"""Tests for the ForeachConverter (tForeach -> Foreach)."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    TalendNode,
)
from src.converters.talend_to_v1.components.iterate.foreach import ForeachConverter
from src.converters.talend_to_v1.components.registry import REGISTRY


def _make_node(params=None, schema=None, component_id="foreach_1",
               component_type="tForeach"):
    return TalendNode(
        component_id=component_id,
        component_type=component_type,
        params=params or {},
        schema=schema or {},
        position={"x": 300, "y": 400},
        raw_xml=ET.Element("node"),
    )


class TestForeachConverterRegistration:
    def test_registered_in_registry(self):
        assert REGISTRY.get("tForeach") is ForeachConverter


class TestForeachConverterBasic:
    def test_basic_conversion_with_multiple_values(self):
        node = _make_node(params={
            "VALUES": [
                {"elementRef": "value", "value": '"alpha"'},
                {"elementRef": "value", "value": '"beta"'},
                {"elementRef": "value", "value": '"gamma"'},
            ],
            "CONNECTION_FORMAT": '"row"',
        })
        result = ForeachConverter().convert(node, [], {})

        assert isinstance(result, ComponentResult)
        comp = result.component
        assert comp["id"] == "foreach_1"
        assert comp["type"] == "Foreach"
        assert comp["original_type"] == "tForeach"
        assert comp["position"] == {"x": 300, "y": 400}
        assert comp["config"]["values"] == ["alpha", "beta", "gamma"]
        assert comp["config"]["connection_format"] == "row"
        assert comp["schema"] == {"input": [], "output": []}
        assert comp["inputs"] == []
        assert comp["outputs"] == []
        assert result.warnings == []

    def test_single_value(self):
        node = _make_node(params={
            "VALUES": [
                {"elementRef": "value", "value": '"only_one"'},
            ],
            "CONNECTION_FORMAT": '"row"',
        })
        result = ForeachConverter().convert(node, [], {})

        assert result.component["config"]["values"] == ["only_one"]
        assert result.warnings == []

    def test_connection_format_preserved(self):
        node = _make_node(params={
            "VALUES": [
                {"elementRef": "value", "value": '"x"'},
            ],
            "CONNECTION_FORMAT": '"iterate"',
        })
        result = ForeachConverter().convert(node, [], {})

        assert result.component["config"]["connection_format"] == "iterate"

    def test_defaults_when_params_missing(self):
        node = _make_node(params={})
        result = ForeachConverter().convert(node, [], {})

        assert result.component["config"]["values"] == []
        assert result.component["config"]["connection_format"] == "row"


class TestForeachConverterWarnings:
    def test_empty_values_produces_warning(self):
        node = _make_node(params={
            "VALUES": [],
            "CONNECTION_FORMAT": '"row"',
        })
        result = ForeachConverter().convert(node, [], {})

        assert len(result.warnings) == 1
        assert "No iteration values" in result.warnings[0]

    def test_missing_values_param_produces_warning(self):
        node = _make_node(params={
            "CONNECTION_FORMAT": '"row"',
        })
        result = ForeachConverter().convert(node, [], {})

        assert any("No iteration values" in w for w in result.warnings)

    def test_non_list_values_produces_warning(self):
        node = _make_node(params={
            "VALUES": "not_a_list",
            "CONNECTION_FORMAT": '"row"',
        })
        result = ForeachConverter().convert(node, [], {})

        assert any("not a list" in w for w in result.warnings)
        assert any("No iteration values" in w for w in result.warnings)
        assert result.component["config"]["values"] == []

    def test_no_warnings_when_valid(self):
        node = _make_node(params={
            "VALUES": [
                {"elementRef": "value", "value": '"a"'},
                {"elementRef": "value", "value": '"b"'},
            ],
            "CONNECTION_FORMAT": '"row"',
        })
        result = ForeachConverter().convert(node, [], {})

        assert result.warnings == []
        assert result.needs_review == []


class TestForeachConverterSchema:
    def test_utility_component_has_empty_schema(self):
        """Foreach is a utility/iterate component — no data flow schema."""
        node = _make_node(params={
            "VALUES": [{"elementRef": "value", "value": '"v"'}],
        })
        result = ForeachConverter().convert(node, [], {})

        assert result.component["schema"] == {"input": [], "output": []}
