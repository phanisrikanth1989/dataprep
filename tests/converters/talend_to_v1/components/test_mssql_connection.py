"""Tests for tMSSqlConnection -> MSSqlConnection converter."""
import xml.etree.ElementTree as ET

import pytest

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.database.mssql_connection import (
    MSSqlConnectionConverter,
)
from src.converters.talend_to_v1.components.registry import REGISTRY


def _make_node(params=None, component_id="tMSSqlConnection_1",
               component_type="tMSSqlConnection"):
    """Create a TalendNode for tMSSqlConnection with given params."""
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
    converter = MSSqlConnectionConverter()
    return converter.convert(
        node=node,
        connections=connections or [],
        context=context or {},
    )


# ------------------------------------------------------------------ #
# Registration tests
# ------------------------------------------------------------------ #

class TestMSSqlConnectionRegistration:
    """Verify the converter is registered under the Talend type name."""

    def test_registered_for_tMSSqlConnection(self):
        cls = REGISTRY.get("tMSSqlConnection")
        assert cls is MSSqlConnectionConverter


# ------------------------------------------------------------------ #
# Basic conversion — full parameter set
# ------------------------------------------------------------------ #

class TestMSSqlConnectionBasicConversion:
    """Test basic parameter extraction and component structure."""

    def test_full_params(self):
        node = _make_node(params={
            "HOST": '"sql.example.com"',
            "PORT": '"1433"',
            "DBNAME": '"AdventureWorks"',
            "USER": '"sa"',
            "PASSWORD": '"S3cret!"',
            "PROPERTIES": '"encrypt=true"',
            "AUTO_COMMIT": "true",
        })
        result = _convert(node)

        comp = result.component
        assert comp["id"] == "tMSSqlConnection_1"
        assert comp["type"] == "MSSqlConnection"
        assert comp["original_type"] == "tMSSqlConnection"
        assert comp["position"] == {"x": 100, "y": 200}

        cfg = comp["config"]
        assert cfg["host"] == "sql.example.com"
        assert cfg["port"] == 1433
        assert cfg["dbname"] == "AdventureWorks"
        assert cfg["user"] == "sa"
        assert cfg["password"] == "S3cret!"
        assert cfg["properties"] == "encrypt=true"
        assert cfg["auto_commit"] is True
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

class TestMSSqlConnectionDefaults:
    """Verify default values when parameters are missing."""

    def test_defaults_when_empty_params(self):
        node = _make_node(params={})
        result = _convert(node)
        cfg = result.component["config"]

        assert cfg["host"] == ""
        assert cfg["port"] == 1433  # default MSSQL port
        assert cfg["dbname"] == ""
        assert cfg["user"] == ""
        assert cfg["password"] == ""
        assert cfg["properties"] == ""
        assert cfg["auto_commit"] is False

    def test_port_defaults_to_1433(self):
        """PORT defaults to 1433 when not specified."""
        node = _make_node(params={"HOST": '"h"', "DBNAME": '"d"', "USER": '"u"'})
        result = _convert(node)
        assert result.component["config"]["port"] == 1433


# ------------------------------------------------------------------ #
# Type coercion
# ------------------------------------------------------------------ #

class TestMSSqlConnectionTypeParsing:
    """Test PORT (int), AUTO_COMMIT (bool) parsing."""

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

    def test_auto_commit_native_bool(self):
        node = _make_node(params={
            "HOST": '"h"', "DBNAME": '"d"', "USER": '"u"',
            "AUTO_COMMIT": True,
        })
        result = _convert(node)
        assert result.component["config"]["auto_commit"] is True

    def test_auto_commit_string_one(self):
        node = _make_node(params={
            "HOST": '"h"', "DBNAME": '"d"', "USER": '"u"',
            "AUTO_COMMIT": "1",
        })
        result = _convert(node)
        assert result.component["config"]["auto_commit"] is True


# ------------------------------------------------------------------ #
# Encrypted password handling
# ------------------------------------------------------------------ #

class TestMSSqlConnectionPassword:
    """Test password extraction including encrypted prefix stripping."""

    def test_encrypted_password_prefix_stripped(self):
        node = _make_node(params={
            "HOST": '"h"', "DBNAME": '"d"', "USER": '"u"',
            "PASSWORD": "enc:system.encryption.key.v1:aBcDeFgHiJk==",
        })
        result = _convert(node)
        assert result.component["config"]["password"] == "aBcDeFgHiJk=="

    def test_plain_quoted_password(self):
        node = _make_node(params={
            "HOST": '"h"', "DBNAME": '"d"', "USER": '"u"',
            "PASSWORD": '"mypassword"',
        })
        result = _convert(node)
        assert result.component["config"]["password"] == "mypassword"

    def test_plain_unquoted_password(self):
        node = _make_node(params={
            "HOST": '"h"', "DBNAME": '"d"', "USER": '"u"',
            "PASSWORD": "plaintext",
        })
        result = _convert(node)
        assert result.component["config"]["password"] == "plaintext"

    def test_missing_password_defaults_to_empty(self):
        node = _make_node(params={
            "HOST": '"h"', "DBNAME": '"d"', "USER": '"u"',
        })
        result = _convert(node)
        assert result.component["config"]["password"] == ""

    def test_encrypted_prefix_with_empty_value(self):
        node = _make_node(params={
            "HOST": '"h"', "DBNAME": '"d"', "USER": '"u"',
            "PASSWORD": "enc:system.encryption.key.v1:",
        })
        result = _convert(node)
        assert result.component["config"]["password"] == ""


# ------------------------------------------------------------------ #
# Warnings
# ------------------------------------------------------------------ #

class TestMSSqlConnectionWarnings:
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
            "HOST": '"sql.example.com"',
            "DBNAME": '"AdventureWorks"',
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

class TestMSSqlConnectionEdgeCases:
    """Edge case tests."""

    def test_custom_component_id(self):
        node = _make_node(
            params={"HOST": '"h"', "DBNAME": '"d"', "USER": '"u"'},
            component_id="tMSSqlConnection_42",
        )
        result = _convert(node)
        assert result.component["id"] == "tMSSqlConnection_42"

    def test_connections_do_not_affect_config(self):
        node = _make_node(params={
            "HOST": '"h"', "DBNAME": '"d"', "USER": '"u"',
        })
        conns = [
            TalendConnection(
                name="row1", source="tMSSqlConnection_1", target="tLogRow_1",
                connector_type="FLOW",
            ),
        ]
        result = _convert(node, connections=conns)
        assert result.component["config"]["host"] == "h"

    def test_unquoted_strings(self):
        """Params without surrounding quotes should still work."""
        node = _make_node(params={
            "HOST": "db.example.com",
            "DBNAME": "AdventureWorks",
            "USER": "sa",
        })
        result = _convert(node)
        cfg = result.component["config"]
        assert cfg["host"] == "db.example.com"
        assert cfg["dbname"] == "AdventureWorks"
        assert cfg["user"] == "sa"

    def test_port_non_numeric_falls_back_to_default(self):
        """Non-numeric PORT string falls back to default 1433."""
        node = _make_node(params={
            "HOST": '"h"', "DBNAME": '"d"', "USER": '"u"',
            "PORT": '"context.DB_PORT"',
        })
        result = _convert(node)
        assert result.component["config"]["port"] == 1433

    def test_properties_preserved(self):
        """PROPERTIES value is passed through correctly."""
        node = _make_node(params={
            "HOST": '"h"', "DBNAME": '"d"', "USER": '"u"',
            "PROPERTIES": '"encrypt=true;trustServerCertificate=false"',
        })
        result = _convert(node)
        assert result.component["config"]["properties"] == \
            "encrypt=true;trustServerCertificate=false"
