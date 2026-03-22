"""Tests for tOracleCommit -> OracleCommit converter."""
import xml.etree.ElementTree as ET

import pytest

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.database.oracle_commit import (
    OracleCommitConverter,
)
from src.converters.talend_to_v1.components.registry import REGISTRY


def _make_node(params=None, component_id="tOracleCommit_1",
               component_type="tOracleCommit"):
    """Create a TalendNode for tOracleCommit with given params."""
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
    converter = OracleCommitConverter()
    return converter.convert(
        node=node,
        connections=connections or [],
        context=context or {},
    )


# ------------------------------------------------------------------ #
# Registration
# ------------------------------------------------------------------ #

class TestOracleCommitRegistration:
    """Verify the converter is registered under the Talend type name."""

    def test_registered_for_tOracleCommit(self):
        cls = REGISTRY.get("tOracleCommit")
        assert cls is OracleCommitConverter


# ------------------------------------------------------------------ #
# Basic conversion — full parameter set
# ------------------------------------------------------------------ #

class TestOracleCommitBasicConversion:
    """Test basic parameter extraction and component structure."""

    def test_full_params(self):
        node = _make_node(params={
            "CONNECTION": '"tOracleConnection_1"',
            "CLOSE": "true",
        })
        result = _convert(node)

        comp = result.component
        assert comp["id"] == "tOracleCommit_1"
        assert comp["type"] == "OracleCommit"
        assert comp["original_type"] == "tOracleCommit"
        assert comp["position"] == {"x": 320, "y": 160}

        cfg = comp["config"]
        assert cfg["connection"] == "tOracleConnection_1"
        assert cfg["close_connection"] is True
        assert result.warnings == []

    def test_component_structure_has_required_keys(self):
        node = _make_node(params={
            "CONNECTION": '"conn1"',
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
        node = _make_node(params={"CONNECTION": '"c"'})
        result = _convert(node)
        assert isinstance(result, ComponentResult)


# ------------------------------------------------------------------ #
# Defaults — missing parameters
# ------------------------------------------------------------------ #

class TestOracleCommitDefaults:
    """Verify default values when parameters are missing."""

    def test_defaults_when_empty_params(self):
        node = _make_node(params={})
        result = _convert(node)
        cfg = result.component["config"]

        assert cfg["connection"] == ""
        assert cfg["close_connection"] is True  # default True per spec

    def test_close_defaults_to_true(self):
        """CLOSE defaults to True when not specified."""
        node = _make_node(params={"CONNECTION": '"conn1"'})
        result = _convert(node)
        assert result.component["config"]["close_connection"] is True


# ------------------------------------------------------------------ #
# Type coercion for CLOSE (bool)
# ------------------------------------------------------------------ #

class TestOracleCommitTypeParsing:
    """Test CLOSE boolean parsing."""

    def test_close_true_string(self):
        node = _make_node(params={
            "CONNECTION": '"c"',
            "CLOSE": "true",
        })
        result = _convert(node)
        assert result.component["config"]["close_connection"] is True

    def test_close_false_string(self):
        node = _make_node(params={
            "CONNECTION": '"c"',
            "CLOSE": "false",
        })
        result = _convert(node)
        assert result.component["config"]["close_connection"] is False

    def test_close_native_bool_false(self):
        node = _make_node(params={
            "CONNECTION": '"c"',
            "CLOSE": False,
        })
        result = _convert(node)
        assert result.component["config"]["close_connection"] is False

    def test_close_string_one(self):
        node = _make_node(params={
            "CONNECTION": '"c"',
            "CLOSE": "1",
        })
        result = _convert(node)
        assert result.component["config"]["close_connection"] is True

    def test_close_string_zero(self):
        node = _make_node(params={
            "CONNECTION": '"c"',
            "CLOSE": "0",
        })
        result = _convert(node)
        assert result.component["config"]["close_connection"] is False


# ------------------------------------------------------------------ #
# Warnings
# ------------------------------------------------------------------ #

class TestOracleCommitWarnings:
    """Test that appropriate warnings are generated."""

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

class TestOracleCommitEdgeCases:
    """Edge case tests."""

    def test_custom_component_id(self):
        node = _make_node(
            params={"CONNECTION": '"c"'},
            component_id="tOracleCommit_42",
        )
        result = _convert(node)
        assert result.component["id"] == "tOracleCommit_42"

    def test_connections_do_not_affect_config(self):
        node = _make_node(params={"CONNECTION": '"c"'})
        conns = [
            TalendConnection(
                name="row1", source="tOracleCommit_1", target="tLogRow_1",
                connector_type="FLOW",
            ),
        ]
        result = _convert(node, connections=conns)
        assert result.component["config"]["connection"] == "c"

    def test_unquoted_connection_string(self):
        """Connection param without surrounding quotes should still work."""
        node = _make_node(params={"CONNECTION": "tOracleConnection_1"})
        result = _convert(node)
        assert result.component["config"]["connection"] == "tOracleConnection_1"
        assert result.warnings == []
