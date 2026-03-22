"""Tests for the DieConverter (tDie -> Die)."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.control.die import DieConverter
from src.converters.talend_to_v1.components.registry import REGISTRY


def _make_node(params=None, schema=None, component_id="die_1",
               component_type="tDie"):
    return TalendNode(
        component_id=component_id,
        component_type=component_type,
        params=params or {},
        schema=schema or {},
        position={"x": 320, "y": 160},
        raw_xml=ET.Element("node"),
    )


class TestDieConverterRegistration:
    def test_registered_in_registry(self):
        assert REGISTRY.get("tDie") is DieConverter


class TestDieConverterBasic:
    def test_basic_conversion_with_all_params(self):
        node = _make_node(params={
            "MESSAGE": '"Fatal error occurred"',
            "CODE": "2",
            "PRIORITY": "3",
            "EXIT_CODE": "4",
        })
        result = DieConverter().convert(node, [], {})

        assert isinstance(result, ComponentResult)
        comp = result.component
        assert comp["id"] == "die_1"
        assert comp["type"] == "Die"
        assert comp["original_type"] == "tDie"
        assert comp["position"] == {"x": 320, "y": 160}
        assert comp["config"]["message"] == "Fatal error occurred"
        assert comp["config"]["code"] == 2
        assert comp["config"]["priority"] == 3
        assert comp["config"]["exit_code"] == 4
        assert comp["inputs"] == []
        assert comp["outputs"] == []

    def test_defaults_when_params_missing(self):
        node = _make_node(params={})
        result = DieConverter().convert(node, [], {})

        cfg = result.component["config"]
        assert cfg["message"] == "Job execution stopped"
        assert cfg["code"] == 1
        assert cfg["priority"] == 5
        assert cfg["exit_code"] == 1

    def test_quoted_integer_params(self):
        """Integer params may arrive as quoted strings like '"7"'."""
        node = _make_node(params={
            "MESSAGE": '"Stopped"',
            "CODE": '"10"',
            "PRIORITY": '"8"',
            "EXIT_CODE": '"99"',
        })
        result = DieConverter().convert(node, [], {})

        cfg = result.component["config"]
        assert cfg["code"] == 10
        assert cfg["priority"] == 8
        assert cfg["exit_code"] == 99

    def test_non_numeric_code_falls_back_to_default(self):
        """Non-numeric values for integer fields should fall back to defaults."""
        node = _make_node(params={
            "CODE": "abc",
            "PRIORITY": "high",
            "EXIT_CODE": "n/a",
        })
        result = DieConverter().convert(node, [], {})

        cfg = result.component["config"]
        assert cfg["code"] == 1
        assert cfg["priority"] == 5
        assert cfg["exit_code"] == 1

    def test_message_without_quotes(self):
        """MESSAGE without surrounding quotes should pass through as-is."""
        node = _make_node(params={
            "MESSAGE": "Plain message",
        })
        result = DieConverter().convert(node, [], {})

        assert result.component["config"]["message"] == "Plain message"


class TestDieConverterSchema:
    def test_utility_component_has_empty_schema(self):
        """Die is a utility component — no data flow schema."""
        node = _make_node(params={"MESSAGE": '"stop"'})
        result = DieConverter().convert(node, [], {})

        assert result.component["schema"] == {"input": [], "output": []}


class TestDieConverterWarnings:
    def test_no_warnings_for_valid_config(self):
        node = _make_node(params={
            "MESSAGE": '"Job execution stopped"',
            "CODE": "1",
            "PRIORITY": "5",
            "EXIT_CODE": "1",
        })
        result = DieConverter().convert(node, [], {})

        assert result.warnings == []
        assert result.needs_review == []

    def test_no_warnings_for_empty_params(self):
        """tDie has sensible defaults — missing params should not warn."""
        node = _make_node(params={})
        result = DieConverter().convert(node, [], {})

        assert result.warnings == []
        assert result.needs_review == []
