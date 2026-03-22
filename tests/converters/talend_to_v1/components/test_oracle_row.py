"""Tests for tOracleRow -> OracleRow converter."""
import xml.etree.ElementTree as ET

import pytest

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.database.oracle_row import (
    OracleRowConverter,
)
from src.converters.talend_to_v1.components.registry import REGISTRY


def _make_node(params=None, schema=None, component_id="tOracleRow_1"):
    """Create a TalendNode for tOracleRow with given params."""
    return TalendNode(
        component_id=component_id,
        component_type="tOracleRow",
        params=params or {},
        schema=schema or {},
        position={"x": 320, "y": 180},
        raw_xml=ET.Element("node"),
    )


def _convert(node, connections=None, context=None):
    """Helper to run the converter."""
    converter = OracleRowConverter()
    return converter.convert(
        node=node,
        connections=connections or [],
        context=context or {},
    )


# ── Registration ──────────────────────────────────────────────────────


class TestOracleRowRegistration:
    """Verify the converter is registered in the global registry."""

    def test_registered_for_toraclerow(self):
        cls = REGISTRY.get("tOracleRow")
        assert cls is OracleRowConverter


# ── Basic conversion ──────────────────────────────────────────────────


class TestOracleRowBasicConversion:
    """Test full-parameter extraction and component structure."""

    def test_full_direct_connection_params(self):
        node = _make_node(params={
            "USE_EXISTING_CONNECTION": "false",
            "CONNECTION": "",
            "CONNECTION_TYPE": '"Oracle Custom"',
            "HOST": '"db.example.com"',
            "PORT": '"1521"',
            "DBNAME": '"PRODDB"',
            "USER": '"scott"',
            "PASSWORD": '"tiger"',
            "QUERY": '"UPDATE accounts SET status=1"',
            "ENCODING": '"UTF-8"',
            "COMMIT_EVERY": "5000",
            "SUPPORT_NLS": "true",
            "DIE_ON_ERROR": "true",
        })
        result = _convert(node)

        comp = result.component
        assert comp["id"] == "tOracleRow_1"
        assert comp["type"] == "OracleRow"
        assert comp["original_type"] == "tOracleRow"
        assert comp["position"] == {"x": 320, "y": 180}

        cfg = comp["config"]
        assert cfg["USE_EXISTING_CONNECTION"] is False
        assert cfg["CONNECTION_TYPE"] == "Oracle Custom"
        assert cfg["HOST"] == "db.example.com"
        assert cfg["PORT"] == 1521
        assert cfg["DBNAME"] == "PRODDB"
        assert cfg["USER"] == "scott"
        assert cfg["PASSWORD"] == "tiger"
        assert cfg["QUERY"] == "UPDATE accounts SET status=1"
        assert cfg["ENCODING"] == "UTF-8"
        assert cfg["COMMIT_EVERY"] == 5000
        assert cfg["SUPPORT_NLS"] is True
        assert cfg["DIE_ON_ERROR"] is True
        assert result.warnings == []

    def test_existing_connection_mode(self):
        node = _make_node(params={
            "USE_EXISTING_CONNECTION": "true",
            "CONNECTION": '"tOracleConnection_1"',
            "QUERY": '"SELECT 1 FROM dual"',
        })
        result = _convert(node)
        cfg = result.component["config"]
        assert cfg["USE_EXISTING_CONNECTION"] is True
        assert cfg["CONNECTION"] == "tOracleConnection_1"
        assert result.warnings == []

    def test_component_structure_has_required_keys(self):
        node = _make_node(params={
            "HOST": '"localhost"',
            "DBNAME": '"testdb"',
            "QUERY": '"SELECT 1"',
        })
        result = _convert(node)
        comp = result.component
        assert set(comp.keys()) == {
            "id", "type", "original_type", "position",
            "config", "schema", "inputs", "outputs",
        }
        assert comp["inputs"] == []
        assert comp["outputs"] == []


# ── Defaults ──────────────────────────────────────────────────────────


class TestOracleRowDefaults:
    """Verify default values when parameters are missing."""

    def test_defaults_when_empty_params(self):
        node = _make_node(params={})
        result = _convert(node)
        cfg = result.component["config"]

        assert cfg["USE_EXISTING_CONNECTION"] is False
        assert cfg["CONNECTION"] == ""
        assert cfg["CONNECTION_TYPE"] == ""
        assert cfg["HOST"] == ""
        assert cfg["PORT"] == 0
        assert cfg["DBNAME"] == ""
        assert cfg["USER"] == ""
        assert cfg["PASSWORD"] == ""
        assert cfg["QUERY"] == ""
        assert cfg["ENCODING"] == ""
        assert cfg["COMMIT_EVERY"] == 10000
        assert cfg["SUPPORT_NLS"] is False
        assert cfg["DIE_ON_ERROR"] is False

    def test_commit_every_default_10000(self):
        """COMMIT_EVERY defaults to 10000 when not specified."""
        node = _make_node(params={
            "HOST": '"h"', "DBNAME": '"d"', "QUERY": '"q"',
        })
        result = _convert(node)
        assert result.component["config"]["COMMIT_EVERY"] == 10000


# ── Warnings ──────────────────────────────────────────────────────────


class TestOracleRowWarnings:
    """Test that appropriate warnings are generated."""

    def test_warning_when_query_empty(self):
        node = _make_node(params={
            "HOST": '"h"', "DBNAME": '"d"',
        })
        result = _convert(node)
        assert any("QUERY" in w and "empty" in w for w in result.warnings)

    def test_warning_direct_connection_missing_host(self):
        node = _make_node(params={
            "USE_EXISTING_CONNECTION": "false",
            "DBNAME": '"mydb"',
            "QUERY": '"SELECT 1"',
        })
        result = _convert(node)
        assert any("HOST" in w and "empty" in w for w in result.warnings)

    def test_warning_direct_connection_missing_dbname(self):
        node = _make_node(params={
            "USE_EXISTING_CONNECTION": "false",
            "HOST": '"h"',
            "QUERY": '"SELECT 1"',
        })
        result = _convert(node)
        assert any("DBNAME" in w and "empty" in w for w in result.warnings)

    def test_warning_existing_connection_missing_connection(self):
        node = _make_node(params={
            "USE_EXISTING_CONNECTION": "true",
            "QUERY": '"SELECT 1"',
        })
        result = _convert(node)
        assert any("CONNECTION" in w and "empty" in w for w in result.warnings)

    def test_no_host_warning_when_using_existing_connection(self):
        """HOST/DBNAME are not required when USE_EXISTING_CONNECTION is true."""
        node = _make_node(params={
            "USE_EXISTING_CONNECTION": "true",
            "CONNECTION": '"tOracleConnection_1"',
            "QUERY": '"SELECT 1"',
        })
        result = _convert(node)
        assert not any("HOST" in w for w in result.warnings)
        assert not any("DBNAME" in w for w in result.warnings)

    def test_no_warnings_when_all_valid(self):
        node = _make_node(params={
            "HOST": '"h"', "DBNAME": '"d"', "QUERY": '"q"',
        })
        result = _convert(node)
        assert result.warnings == []


# ── Schema ────────────────────────────────────────────────────────────


class TestOracleRowSchema:
    """Test schema parsing for input and output."""

    def test_schema_parsed_into_input_and_output(self):
        node = _make_node(
            params={"HOST": '"h"', "DBNAME": '"d"', "QUERY": '"q"'},
            schema={
                "FLOW": [
                    SchemaColumn(name="id", type="id_Integer", key=True, nullable=False),
                    SchemaColumn(name="name", type="id_String", length=255),
                    SchemaColumn(
                        name="created_at",
                        type="id_Date",
                        date_pattern="yyyy-MM-dd HH:mm:ss",
                    ),
                ]
            },
        )
        result = _convert(node)
        input_schema = result.component["schema"]["input"]
        output_schema = result.component["schema"]["output"]

        # Both input and output should contain the same parsed columns
        assert len(input_schema) == 3
        assert len(output_schema) == 3

        assert input_schema[0]["name"] == "id"
        assert input_schema[0]["key"] is True
        assert input_schema[0]["nullable"] is False

        assert output_schema[1]["name"] == "name"
        assert output_schema[1]["length"] == 255

        assert output_schema[2]["name"] == "created_at"
        assert output_schema[2]["date_pattern"] == "%Y-%m-%d %H:%M:%S"

    def test_empty_schema_when_no_flow(self):
        node = _make_node(params={"HOST": '"h"', "DBNAME": '"d"', "QUERY": '"q"'})
        result = _convert(node)
        assert result.component["schema"]["input"] == []
        assert result.component["schema"]["output"] == []


# ── Boolean / int parsing ─────────────────────────────────────────────


class TestOracleRowTypeParsing:
    """Test type coercion for boolean and integer parameters."""

    def test_bool_true_string(self):
        node = _make_node(params={
            "HOST": '"h"', "DBNAME": '"d"', "QUERY": '"q"',
            "DIE_ON_ERROR": "true",
        })
        result = _convert(node)
        assert result.component["config"]["DIE_ON_ERROR"] is True

    def test_bool_false_string(self):
        node = _make_node(params={
            "HOST": '"h"', "DBNAME": '"d"', "QUERY": '"q"',
            "DIE_ON_ERROR": "false",
        })
        result = _convert(node)
        assert result.component["config"]["DIE_ON_ERROR"] is False

    def test_bool_native_true(self):
        node = _make_node(params={
            "HOST": '"h"', "DBNAME": '"d"', "QUERY": '"q"',
            "SUPPORT_NLS": True,
        })
        result = _convert(node)
        assert result.component["config"]["SUPPORT_NLS"] is True

    def test_int_from_quoted_string(self):
        node = _make_node(params={
            "HOST": '"h"', "DBNAME": '"d"', "QUERY": '"q"',
            "PORT": '"1521"',
            "COMMIT_EVERY": '"25000"',
        })
        result = _convert(node)
        cfg = result.component["config"]
        assert cfg["PORT"] == 1521
        assert cfg["COMMIT_EVERY"] == 25000

    def test_int_port_from_plain_string(self):
        node = _make_node(params={
            "HOST": '"h"', "DBNAME": '"d"', "QUERY": '"q"',
            "PORT": "1522",
        })
        result = _convert(node)
        assert result.component["config"]["PORT"] == 1522


# ── Edge cases ────────────────────────────────────────────────────────


class TestOracleRowEdgeCases:
    """Edge-case and structural tests."""

    def test_custom_component_id(self):
        node = _make_node(
            params={"HOST": '"h"', "DBNAME": '"d"', "QUERY": '"q"'},
            component_id="tOracleRow_99",
        )
        result = _convert(node)
        assert result.component["id"] == "tOracleRow_99"

    def test_connections_do_not_affect_config(self):
        node = _make_node(params={
            "HOST": '"h"', "DBNAME": '"d"', "QUERY": '"q"',
        })
        conns = [
            TalendConnection(
                name="row1", source="tOracleRow_1", target="tLogRow_1",
                connector_type="FLOW",
            ),
        ]
        result = _convert(node, connections=conns)
        assert result.component["config"]["HOST"] == "h"

    def test_result_type_is_component_result(self):
        node = _make_node(params={
            "HOST": '"h"', "DBNAME": '"d"', "QUERY": '"q"',
        })
        result = _convert(node)
        assert isinstance(result, ComponentResult)

    def test_commit_every_non_numeric_falls_back_to_default(self):
        """Non-numeric COMMIT_EVERY should fall back to 10000."""
        node = _make_node(params={
            "HOST": '"h"', "DBNAME": '"d"', "QUERY": '"q"',
            "COMMIT_EVERY": "abc",
        })
        result = _convert(node)
        assert result.component["config"]["COMMIT_EVERY"] == 10000
