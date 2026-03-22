"""Tests for tOracleConnection / tDBConnection -> OracleConnection converter."""
import xml.etree.ElementTree as ET

import pytest

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.database.oracle_connection import (
    OracleConnectionConverter,
)
from src.converters.talend_to_v1.components.registry import REGISTRY


def _make_node(params=None, component_id="tOracleConnection_1",
               component_type="tOracleConnection"):
    """Create a TalendNode for tOracleConnection with given params."""
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
    converter = OracleConnectionConverter()
    return converter.convert(
        node=node,
        connections=connections or [],
        context=context or {},
    )


# ------------------------------------------------------------------ #
# Registration tests — both Talend names must resolve to the same class
# ------------------------------------------------------------------ #

class TestOracleConnectionRegistration:
    """Verify the converter is registered under both Talend type names."""

    def test_registered_for_tOracleConnection(self):
        cls = REGISTRY.get("tOracleConnection")
        assert cls is OracleConnectionConverter

    def test_registered_for_tDBConnection(self):
        cls = REGISTRY.get("tDBConnection")
        assert cls is OracleConnectionConverter


# ------------------------------------------------------------------ #
# Basic conversion — full parameter set
# ------------------------------------------------------------------ #

class TestOracleConnectionBasicConversion:
    """Test basic parameter extraction and component structure."""

    def test_full_params(self):
        node = _make_node(params={
            "CONNECTION_TYPE": '"Oracle OCI"',
            "HOST": '"db.example.com"',
            "PORT": '"1521"',
            "DBNAME": '"ORCL"',
            "USER": '"scott"',
            "PASS": '"tiger"',
            "AUTO_COMMIT": "true",
            "SUPPORT_NLS": "false",
        })
        result = _convert(node)

        comp = result.component
        assert comp["id"] == "tOracleConnection_1"
        assert comp["type"] == "OracleConnection"
        assert comp["original_type"] == "tOracleConnection"
        assert comp["position"] == {"x": 100, "y": 200}

        cfg = comp["config"]
        assert cfg["connection_type"] == "Oracle OCI"
        assert cfg["host"] == "db.example.com"
        assert cfg["port"] == 1521
        assert cfg["dbname"] == "ORCL"
        assert cfg["user"] == "scott"
        assert cfg["password"] == "tiger"
        assert cfg["auto_commit"] is True
        assert cfg["support_nls"] is False
        assert result.warnings == []

    def test_component_structure_has_required_keys(self):
        node = _make_node(params={
            "HOST": '"localhost"',
            "DBNAME": '"testdb"',
            "USER": '"admin"',
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
            "HOST": '"h"',
            "DBNAME": '"d"',
            "USER": '"u"',
        })
        result = _convert(node)
        assert isinstance(result, ComponentResult)


# ------------------------------------------------------------------ #
# Defaults — missing parameters
# ------------------------------------------------------------------ #

class TestOracleConnectionDefaults:
    """Verify default values when parameters are missing."""

    def test_defaults_when_empty_params(self):
        node = _make_node(params={})
        result = _convert(node)
        cfg = result.component["config"]

        assert cfg["connection_type"] == ""
        assert cfg["host"] == ""
        assert cfg["port"] == 1521  # default Oracle port
        assert cfg["dbname"] == ""
        assert cfg["user"] == ""
        assert cfg["password"] == ""
        assert cfg["auto_commit"] is False
        assert cfg["support_nls"] is False

    def test_port_defaults_to_1521(self):
        """PORT defaults to 1521 when not specified."""
        node = _make_node(params={"HOST": '"h"', "DBNAME": '"d"', "USER": '"u"'})
        result = _convert(node)
        assert result.component["config"]["port"] == 1521


# ------------------------------------------------------------------ #
# Type coercion
# ------------------------------------------------------------------ #

class TestOracleConnectionTypeParsing:
    """Test PORT (int), AUTO_COMMIT and SUPPORT_NLS (bool) parsing."""

    def test_port_parsed_as_int(self):
        node = _make_node(params={
            "HOST": '"h"', "DBNAME": '"d"', "USER": '"u"',
            "PORT": '"5432"',
        })
        result = _convert(node)
        assert result.component["config"]["port"] == 5432
        assert isinstance(result.component["config"]["port"], int)

    def test_port_unquoted_int(self):
        node = _make_node(params={
            "HOST": '"h"', "DBNAME": '"d"', "USER": '"u"',
            "PORT": "3306",
        })
        result = _convert(node)
        assert result.component["config"]["port"] == 3306

    def test_auto_commit_true_string(self):
        node = _make_node(params={
            "HOST": '"h"', "DBNAME": '"d"', "USER": '"u"',
            "AUTO_COMMIT": "true",
        })
        result = _convert(node)
        assert result.component["config"]["auto_commit"] is True

    def test_auto_commit_false_string(self):
        node = _make_node(params={
            "HOST": '"h"', "DBNAME": '"d"', "USER": '"u"',
            "AUTO_COMMIT": "false",
        })
        result = _convert(node)
        assert result.component["config"]["auto_commit"] is False

    def test_support_nls_true(self):
        node = _make_node(params={
            "HOST": '"h"', "DBNAME": '"d"', "USER": '"u"',
            "SUPPORT_NLS": "true",
        })
        result = _convert(node)
        assert result.component["config"]["support_nls"] is True

    def test_bool_native_true(self):
        node = _make_node(params={
            "HOST": '"h"', "DBNAME": '"d"', "USER": '"u"',
            "AUTO_COMMIT": True,
        })
        result = _convert(node)
        assert result.component["config"]["auto_commit"] is True

    def test_bool_string_one(self):
        node = _make_node(params={
            "HOST": '"h"', "DBNAME": '"d"', "USER": '"u"',
            "SUPPORT_NLS": "1",
        })
        result = _convert(node)
        assert result.component["config"]["support_nls"] is True


# ------------------------------------------------------------------ #
# Warnings
# ------------------------------------------------------------------ #

class TestOracleConnectionWarnings:
    """Test that appropriate warnings are generated."""

    def test_warning_when_host_empty(self):
        node = _make_node(params={"DBNAME": '"d"', "USER": '"u"'})
        result = _convert(node)
        assert any("HOST" in w and "empty" in w for w in result.warnings)

    def test_warning_when_dbname_empty(self):
        node = _make_node(params={"HOST": '"h"', "USER": '"u"'})
        result = _convert(node)
        assert any("DBNAME" in w and "empty" in w for w in result.warnings)

    def test_warning_when_user_empty(self):
        node = _make_node(params={"HOST": '"h"', "DBNAME": '"d"'})
        result = _convert(node)
        assert any("USER" in w and "empty" in w for w in result.warnings)

    def test_no_warnings_when_all_valid(self):
        node = _make_node(params={
            "HOST": '"db.example.com"',
            "DBNAME": '"ORCL"',
            "USER": '"admin"',
        })
        result = _convert(node)
        assert result.warnings == []

    def test_multiple_warnings(self):
        """When host, dbname, and user are all empty, three warnings appear."""
        node = _make_node(params={})
        result = _convert(node)
        assert len(result.warnings) == 3


# ------------------------------------------------------------------ #
# Edge cases
# ------------------------------------------------------------------ #

class TestOracleConnectionEdgeCases:
    """Edge case and audit-specific tests."""

    def test_custom_component_id(self):
        node = _make_node(
            params={"HOST": '"h"', "DBNAME": '"d"', "USER": '"u"'},
            component_id="tOracleConnection_42",
        )
        result = _convert(node)
        assert result.component["id"] == "tOracleConnection_42"

    def test_tDBConnection_type_preserved(self):
        """When component_type is tDBConnection, original_type reflects it."""
        node = _make_node(
            params={"HOST": '"h"', "DBNAME": '"d"', "USER": '"u"'},
            component_type="tDBConnection",
            component_id="tDBConnection_1",
        )
        result = _convert(node)
        assert result.component["original_type"] == "tDBConnection"
        assert result.component["type"] == "OracleConnection"

    def test_connections_do_not_affect_config(self):
        node = _make_node(params={
            "HOST": '"h"', "DBNAME": '"d"', "USER": '"u"',
        })
        conns = [
            TalendConnection(
                name="row1", source="tOracleConnection_1", target="tLogRow_1",
                connector_type="FLOW",
            ),
        ]
        result = _convert(node, connections=conns)
        assert result.component["config"]["host"] == "h"

    def test_unquoted_strings(self):
        """Params without surrounding quotes should still work."""
        node = _make_node(params={
            "HOST": "db.example.com",
            "DBNAME": "ORCL",
            "USER": "scott",
        })
        result = _convert(node)
        cfg = result.component["config"]
        assert cfg["host"] == "db.example.com"
        assert cfg["dbname"] == "ORCL"
        assert cfg["user"] == "scott"

    def test_port_non_numeric_falls_back_to_default(self):
        """Non-numeric PORT string falls back to default 1521."""
        node = _make_node(params={
            "HOST": '"h"', "DBNAME": '"d"', "USER": '"u"',
            "PORT": '"context.DB_PORT"',
        })
        result = _convert(node)
        assert result.component["config"]["port"] == 1521
