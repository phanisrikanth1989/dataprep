"""Tests for tOracleClose -> OracleClose converter."""
import xml.etree.ElementTree as ET

import pytest

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.database.oracle_close import (
    OracleCloseConverter,
)
from src.converters.talend_to_v1.components.registry import REGISTRY


def _make_node(params=None, component_id="tOracleClose_1",
               component_type="tOracleClose"):
    """Create a TalendNode for tOracleClose with given params."""
    return TalendNode(
        component_id=component_id,
        component_type=component_type,
        params=params or {},
        schema={},
        position={"x": 320, "y": 160},
        raw_xml=ET.Element("node"),
    )


def _convert(node, connections=None, context=None):
    """Helper to run the converter."""
    converter = OracleCloseConverter()
    return converter.convert(
        node=node,
        connections=connections or [],
        context=context or {},
    )


# ------------------------------------------------------------------ #
# Registration
# ------------------------------------------------------------------ #

class TestOracleCloseRegistration:
    """Verify the converter is registered under the Talend type name."""

    def test_registered_for_tOracleClose(self):
        cls = REGISTRY.get("tOracleClose")
        assert cls is OracleCloseConverter


# ------------------------------------------------------------------ #
# Basic conversion
# ------------------------------------------------------------------ #

class TestOracleCloseBasicConversion:
    """Test basic parameter extraction and component structure."""

    def test_full_params(self):
        node = _make_node(params={
            "CONNECTION": '"tOracleConnection_1"',
        })
        result = _convert(node)

        comp = result.component
        assert comp["id"] == "tOracleClose_1"
        assert comp["type"] == "OracleClose"
        assert comp["original_type"] == "tOracleClose"
        assert comp["position"] == {"x": 320, "y": 160}

        cfg = comp["config"]
        assert cfg["connection"] == "tOracleConnection_1"
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
            "CONNECTION": '"conn_1"',
        })
        result = _convert(node)
        assert isinstance(result, ComponentResult)

    def test_utility_schema_empty(self):
        """OracleClose is a utility component with no data flow schema."""
        node = _make_node(params={"CONNECTION": '"conn_1"'})
        result = _convert(node)
        assert result.component["schema"] == {"input": [], "output": []}


# ------------------------------------------------------------------ #
# Defaults and warnings
# ------------------------------------------------------------------ #

class TestOracleCloseDefaults:
    """Verify default values and warnings when parameters are missing."""

    def test_defaults_when_empty_params(self):
        node = _make_node(params={})
        result = _convert(node)
        cfg = result.component["config"]
        assert cfg["connection"] == ""

    def test_warning_when_connection_empty(self):
        node = _make_node(params={})
        result = _convert(node)
        assert any("CONNECTION" in w and "empty" in w for w in result.warnings)

    def test_no_warnings_when_connection_provided(self):
        node = _make_node(params={"CONNECTION": '"tOracleConnection_1"'})
        result = _convert(node)
        assert result.warnings == []


# ------------------------------------------------------------------ #
# Edge cases
# ------------------------------------------------------------------ #

class TestOracleCloseEdgeCases:
    """Edge case and audit-specific tests."""

    def test_custom_component_id(self):
        node = _make_node(
            params={"CONNECTION": '"conn_1"'},
            component_id="tOracleClose_42",
        )
        result = _convert(node)
        assert result.component["id"] == "tOracleClose_42"

    def test_unquoted_connection_string(self):
        """Params without surrounding quotes should still work."""
        node = _make_node(params={
            "CONNECTION": "tOracleConnection_1",
        })
        result = _convert(node)
        assert result.component["config"]["connection"] == "tOracleConnection_1"

    def test_connections_do_not_affect_config(self):
        node = _make_node(params={
            "CONNECTION": '"tOracleConnection_1"',
        })
        conns = [
            TalendConnection(
                name="row1", source="tOracleClose_1", target="tLogRow_1",
                connector_type="FLOW",
            ),
        ]
        result = _convert(node, connections=conns)
        assert result.component["config"]["connection"] == "tOracleConnection_1"

    def test_context_variable_as_connection(self):
        """A context variable reference is kept as-is (no resolution)."""
        node = _make_node(params={
            "CONNECTION": '"context.myConn"',
        })
        result = _convert(node)
        assert result.component["config"]["connection"] == "context.myConn"
        assert result.warnings == []
