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
            "EXIT_JVM": "true",
            "TSTATCATCHER_STATS": "true",
            "LABEL": '"die-step"',
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
        assert comp["config"]["exit_jvm"] is True
        assert comp["config"]["tstatcatcher_stats"] is True
        assert comp["config"]["label"] == "die-step"
        assert comp["inputs"] == []
        assert comp["outputs"] == []

    def test_defaults_when_params_missing(self):
        node = _make_node(params={})
        result = DieConverter().convert(node, [], {})

        cfg = result.component["config"]
        assert cfg["message"] == "Job execution stopped"
        assert cfg["code"] == 0
        assert cfg["priority"] == 0
        assert cfg["exit_jvm"] is False
        assert cfg["tstatcatcher_stats"] is False
        assert cfg["label"] == ""

    def test_quoted_integer_params(self):
        """Integer params may arrive as quoted strings like '"7"'."""
        node = _make_node(params={
            "MESSAGE": '"Stopped"',
            "CODE": '"10"',
            "PRIORITY": '"8"',
        })
        result = DieConverter().convert(node, [], {})

        cfg = result.component["config"]
        assert cfg["code"] == 10
        assert cfg["priority"] == 8

    def test_non_numeric_code_falls_back_to_default(self):
        """Non-numeric values for integer fields should fall back to defaults."""
        node = _make_node(params={
            "CODE": "abc",
            "PRIORITY": "high",
        })
        result = DieConverter().convert(node, [], {})

        cfg = result.component["config"]
        assert cfg["code"] == 0
        assert cfg["priority"] == 0

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
            "CODE": "0",
            "PRIORITY": "0",
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


class TestCompleteness:
    """Verify all config keys are present."""

    def test_all_6_config_keys_present(self):
        node = _make_node(params={})
        result = DieConverter().convert(node, [], {})
        cfg = result.component["config"]
        expected_keys = {
            "message", "code", "priority", "exit_jvm",
            "tstatcatcher_stats", "label",
        }
        assert set(cfg.keys()) == expected_keys

    def test_phantom_param_exit_code_removed(self):
        """exit_code is not a real Talend param — must NOT be in config."""
        node = _make_node(params={})
        result = DieConverter().convert(node, [], {})
        assert "exit_code" not in result.component["config"]


class TestEngineGapWarnings:
    """Verify engine-gap warnings."""

    def test_no_warnings_for_defaults(self):
        node = _make_node(params={})
        result = DieConverter().convert(node, [], {})
        engine_warnings = [w for w in result.warnings if "engine" in w.lower()]
        assert engine_warnings == []

    def test_exit_jvm_warning(self):
        node = _make_node(params={"EXIT_JVM": "true"})
        result = DieConverter().convert(node, [], {})
        assert any("EXIT_JVM" in w for w in result.warnings)
