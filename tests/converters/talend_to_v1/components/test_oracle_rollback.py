"""Tests for tOracleRollback -> OracleRollback converter."""
import xml.etree.ElementTree as ET

import pytest

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.database.oracle_rollback import (
    OracleRollbackConverter,
)
from src.converters.talend_to_v1.components.registry import REGISTRY


def _make_node(params=None, component_id="tOracleRollback_1",
               component_type="tOracleRollback"):
    """Create a TalendNode for tOracleRollback with given params."""
    return TalendNode(
        component_id=component_id,
        component_type=component_type,
        params=params or {},
        schema={},
        position={"x": 100, "y": 200},
        raw_xml=ET.Element("node"),
    )


def _convert(node, connections=None, context=None):
    """Helper to run the converter."""
    converter = OracleRollbackConverter()
    return converter.convert(
        node=node,
        connections=connections or [],
        context=context or {},
    )


# ------------------------------------------------------------------ #
# Registration
# ------------------------------------------------------------------ #

class TestOracleRollbackRegistration:
    """Verify the converter is registered under the Talend type name."""

    def test_registered_for_tOracleRollback(self):
        cls = REGISTRY.get("tOracleRollback")
        assert cls is OracleRollbackConverter


# ------------------------------------------------------------------ #
# Basic conversion — full parameter set
# ------------------------------------------------------------------ #

class TestOracleRollbackBasicConversion:
    """Test basic parameter extraction and component structure."""

    def test_full_params(self):
        node = _make_node(params={
            "CONNECTION": '"tOracleConnection_1"',
            "CLOSE": "false",
            "CONNECTION_FORMAT": '"row"',
        })
        result = _convert(node)

        comp = result.component
        assert comp["id"] == "tOracleRollback_1"
        assert comp["type"] == "OracleRollback"
        assert comp["original_type"] == "tOracleRollback"
        assert comp["position"] == {"x": 100, "y": 200}

        cfg = comp["config"]
        assert cfg["connection"] == "tOracleConnection_1"
        assert cfg["close"] is False
        assert cfg["connection_format"] == "row"
        assert result.warnings == []

    def test_component_structure_has_required_keys(self):
        node = _make_node(params={
            "CONNECTION": '"tOracleConnection_1"',
        })
        result = _convert(node)
        comp = result.component
        assert set(comp.keys()) == {
            "id", "type", "original_type", "position",
            "config", "schema", "inputs", "outputs",
        }
        assert comp["inputs"] == []
        assert comp["outputs"] == []
        assert comp["schema"] == {"input": [], "output": []}

    def test_result_type_is_component_result(self):
        node = _make_node(params={
            "CONNECTION": '"conn"',
        })
        result = _convert(node)
        assert isinstance(result, ComponentResult)


# ------------------------------------------------------------------ #
# Defaults — missing parameters
# ------------------------------------------------------------------ #

class TestOracleRollbackDefaults:
    """Verify default values when parameters are missing."""

    def test_defaults_when_empty_params(self):
        node = _make_node(params={})
        result = _convert(node)
        cfg = result.component["config"]

        assert cfg["connection"] == ""
        assert cfg["close"] is True  # default is True
        assert cfg["connection_format"] == ""

    def test_close_defaults_to_true(self):
        """CLOSE defaults to True when not specified."""
        node = _make_node(params={"CONNECTION": '"conn"'})
        result = _convert(node)
        assert result.component["config"]["close"] is True


# ------------------------------------------------------------------ #
# Type coercion
# ------------------------------------------------------------------ #

class TestOracleRollbackTypeParsing:
    """Test CLOSE (bool) parsing."""

    def test_close_true_string(self):
        node = _make_node(params={
            "CONNECTION": '"conn"',
            "CLOSE": "true",
        })
        result = _convert(node)
        assert result.component["config"]["close"] is True

    def test_close_false_string(self):
        node = _make_node(params={
            "CONNECTION": '"conn"',
            "CLOSE": "false",
        })
        result = _convert(node)
        assert result.component["config"]["close"] is False

    def test_close_native_bool(self):
        node = _make_node(params={
            "CONNECTION": '"conn"',
            "CLOSE": True,
        })
        result = _convert(node)
        assert result.component["config"]["close"] is True

    def test_close_string_one(self):
        node = _make_node(params={
            "CONNECTION": '"conn"',
            "CLOSE": "1",
        })
        result = _convert(node)
        assert result.component["config"]["close"] is True


# ------------------------------------------------------------------ #
# Warnings
# ------------------------------------------------------------------ #

class TestOracleRollbackWarnings:
    """Test that appropriate warnings are generated."""

    def test_warning_when_connection_empty(self):
        node = _make_node(params={})
        result = _convert(node)
        assert any("CONNECTION" in w and "empty" in w for w in result.warnings)

    def test_no_warnings_when_connection_set(self):
        node = _make_node(params={"CONNECTION": '"tOracleConnection_1"'})
        result = _convert(node)
        assert result.warnings == []


# ------------------------------------------------------------------ #
# Edge cases
# ------------------------------------------------------------------ #

class TestOracleRollbackEdgeCases:
    """Edge case and audit-specific tests."""

    def test_custom_component_id(self):
        node = _make_node(
            params={"CONNECTION": '"conn"'},
            component_id="tOracleRollback_42",
        )
        result = _convert(node)
        assert result.component["id"] == "tOracleRollback_42"

    def test_connections_do_not_affect_config(self):
        node = _make_node(params={
            "CONNECTION": '"conn"',
        })
        conns = [
            TalendConnection(
                name="trigger1", source="tOracleRollback_1", target="tLogRow_1",
                connector_type="COMPONENT_OK",
            ),
        ]
        result = _convert(node, connections=conns)
        assert result.component["config"]["connection"] == "conn"

    def test_unquoted_strings(self):
        """Params without surrounding quotes should still work."""
        node = _make_node(params={
            "CONNECTION": "tOracleConnection_1",
            "CONNECTION_FORMAT": "row",
        })
        result = _convert(node)
        cfg = result.component["config"]
        assert cfg["connection"] == "tOracleConnection_1"
        assert cfg["connection_format"] == "row"

    def test_close_explicitly_true(self):
        """Explicit CLOSE=true should work the same as the default."""
        node = _make_node(params={
            "CONNECTION": '"conn"',
            "CLOSE": "true",
        })
        result = _convert(node)
        assert result.component["config"]["close"] is True
