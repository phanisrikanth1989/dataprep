"""Tests for the SleepConverter (tSleep -> SleepComponent)."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.control.sleep import SleepConverter
from src.converters.talend_to_v1.components.registry import REGISTRY


def _make_node(params=None, schema=None, component_id="sleep_1",
               component_type="tSleep"):
    return TalendNode(
        component_id=component_id,
        component_type=component_type,
        params=params or {},
        schema=schema or {},
        position={"x": 320, "y": 160},
        raw_xml=ET.Element("node"),
    )


class TestSleepConverterRegistration:
    def test_registered_in_registry(self):
        assert REGISTRY.get("tSleep") is SleepConverter


class TestSleepConverterBasic:
    def test_basic_integer_pause(self):
        node = _make_node(params={"PAUSE": "5000"})
        result = SleepConverter().convert(node, [], {})

        assert isinstance(result, ComponentResult)
        comp = result.component
        assert comp["id"] == "sleep_1"
        assert comp["type"] == "SleepComponent"
        assert comp["original_type"] == "tSleep"
        assert comp["position"] == {"x": 320, "y": 160}
        assert comp["config"]["pause_duration"] == 5000.0
        assert comp["schema"] == {"input": [], "output": []}
        assert comp["inputs"] == []
        assert comp["outputs"] == []
        assert result.warnings == []

    def test_float_pause_duration(self):
        node = _make_node(params={"PAUSE": "1500.5"})
        result = SleepConverter().convert(node, [], {})

        assert result.component["config"]["pause_duration"] == 1500.5
        assert result.warnings == []

    def test_quoted_pause_value(self):
        """Talend parameters are often stored with surrounding quotes."""
        node = _make_node(params={"PAUSE": '"3000"'})
        result = SleepConverter().convert(node, [], {})

        assert result.component["config"]["pause_duration"] == 3000.0
        assert result.warnings == []

    def test_defaults_when_pause_missing(self):
        node = _make_node(params={})
        result = SleepConverter().convert(node, [], {})

        assert result.component["config"]["pause_duration"] == 0.0
        assert result.warnings == []


class TestSleepConverterWarnings:
    def test_invalid_pause_produces_warning(self):
        node = _make_node(params={"PAUSE": "not_a_number"})
        result = SleepConverter().convert(node, [], {})

        assert result.component["config"]["pause_duration"] == 0.0
        assert len(result.warnings) == 1
        assert "PAUSE" in result.warnings[0]
        assert "not_a_number" in result.warnings[0]

    def test_no_warnings_for_valid_input(self):
        node = _make_node(params={"PAUSE": "1000"})
        result = SleepConverter().convert(node, [], {})

        assert result.warnings == []
        assert result.needs_review == []


class TestSleepConverterSchema:
    def test_utility_component_has_empty_schema(self):
        """SleepComponent is a utility component -- no data flow schema."""
        node = _make_node(params={"PAUSE": "100"})
        result = SleepConverter().convert(node, [], {})

        assert result.component["schema"] == {"input": [], "output": []}
