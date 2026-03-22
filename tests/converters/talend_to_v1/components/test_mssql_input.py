"""Tests for tMSSqlInput -> MSSqlInput converter."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.database.mssql_input import (
    MSSqlInputConverter,
)
from src.converters.talend_to_v1.components.registry import REGISTRY


def _make_node(params=None, schema=None, component_id="tMSSqlInput_1",
               component_type="tMSSqlInput"):
    """Create a TalendNode for tMSSqlInput with given params."""
    return TalendNode(
        component_id=component_id,
        component_type=component_type,
        params=params or {},
        schema=schema or {},
        position={"x": 256, "y": 128},
        raw_xml=ET.Element("node"),
    )


def _convert(node, connections=None, context=None):
    """Helper to run the converter."""
    converter = MSSqlInputConverter()
    return converter.convert(
        node=node,
        connections=connections or [],
        context=context or {},
    )


# ------------------------------------------------------------------ #
# Registration
# ------------------------------------------------------------------ #

class TestMSSqlInputRegistration:
    """Verify the converter is registered under the Talend type name."""

    def test_registered_for_tMSSqlInput(self):
        cls = REGISTRY.get("tMSSqlInput")
        assert cls is MSSqlInputConverter


# ------------------------------------------------------------------ #
# Basic conversion -- full parameter set
# ------------------------------------------------------------------ #

class TestMSSqlInputBasicConversion:
    """Test basic parameter extraction and component structure."""

    def test_full_params(self):
        node = _make_node(params={
            "HOST": '"sql.example.com"',
            "PORT": '"1433"',
            "DBNAME": '"AdventureWorks"',
            "USER": '"sa"',
            "PASSWORD": '"S3cret!"',
            "QUERY": '"SELECT * FROM dbo.Orders"',
            "PROPERTIES": '"encrypt=true"',
            "QUERY_TIMEOUT_IN_SECONDS": "60",
            "TRIM_ALL_COLUMN": "true",
        })
        result = _convert(node)

        comp = result.component
        assert comp["id"] == "tMSSqlInput_1"
        assert comp["type"] == "MSSqlInput"
        assert comp["original_type"] == "tMSSqlInput"
        assert comp["position"] == {"x": 256, "y": 128}

        cfg = comp["config"]
        assert cfg["host"] == "sql.example.com"
        assert cfg["port"] == 1433
        assert cfg["dbname"] == "AdventureWorks"
        assert cfg["user"] == "sa"
        assert cfg["password"] == "S3cret!"
        assert cfg["query"] == "SELECT * FROM dbo.Orders"
        assert cfg["properties"] == "encrypt=true"
        assert cfg["query_timeout"] == 60
        assert cfg["trim_all_columns"] is True
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

    def test_result_type_is_component_result(self):
        node = _make_node(params={
            "HOST": '"h"',
            "DBNAME": '"d"',
            "QUERY": '"q"',
        })
        result = _convert(node)
        assert isinstance(result, ComponentResult)


# ------------------------------------------------------------------ #
# Defaults -- missing parameters
# ------------------------------------------------------------------ #

class TestMSSqlInputDefaults:
    """Verify default values when parameters are missing."""

    def test_defaults_when_empty_params(self):
        node = _make_node(params={})
        result = _convert(node)
        cfg = result.component["config"]

        assert cfg["host"] == ""
        assert cfg["port"] == 1433
        assert cfg["dbname"] == ""
        assert cfg["user"] == ""
        assert cfg["password"] == ""
        assert cfg["query"] == ""
        assert cfg["properties"] == ""
        assert cfg["query_timeout"] == 30
        assert cfg["trim_all_columns"] is False

    def test_port_defaults_to_1433(self):
        node = _make_node(params={"HOST": '"h"', "DBNAME": '"d"', "QUERY": '"q"'})
        result = _convert(node)
        assert result.component["config"]["port"] == 1433

    def test_query_timeout_defaults_to_30(self):
        node = _make_node(params={"HOST": '"h"', "DBNAME": '"d"', "QUERY": '"q"'})
        result = _convert(node)
        assert result.component["config"]["query_timeout"] == 30

    def test_trim_all_columns_defaults_to_false(self):
        node = _make_node(params={"HOST": '"h"', "DBNAME": '"d"', "QUERY": '"q"'})
        result = _convert(node)
        assert result.component["config"]["trim_all_columns"] is False


# ------------------------------------------------------------------ #
# Type coercion
# ------------------------------------------------------------------ #

class TestMSSqlInputTypeParsing:
    """Test PORT (int), QUERY_TIMEOUT (int), TRIM_ALL_COLUMN (bool)."""

    def test_port_parsed_as_int(self):
        node = _make_node(params={
            "HOST": '"h"', "DBNAME": '"d"', "QUERY": '"q"',
            "PORT": '"5432"',
        })
        result = _convert(node)
        assert result.component["config"]["port"] == 5432
        assert isinstance(result.component["config"]["port"], int)

    def test_port_unquoted_int(self):
        node = _make_node(params={
            "HOST": '"h"', "DBNAME": '"d"', "QUERY": '"q"',
            "PORT": "3306",
        })
        result = _convert(node)
        assert result.component["config"]["port"] == 3306

    def test_port_raw_integer(self):
        node = _make_node(params={
            "HOST": '"h"', "DBNAME": '"d"', "QUERY": '"q"',
            "PORT": 1434,
        })
        result = _convert(node)
        assert result.component["config"]["port"] == 1434

    def test_port_non_numeric_falls_back_to_default(self):
        node = _make_node(params={
            "HOST": '"h"', "DBNAME": '"d"', "QUERY": '"q"',
            "PORT": '"context.DB_PORT"',
        })
        result = _convert(node)
        assert result.component["config"]["port"] == 1433

    def test_query_timeout_parsed_as_int(self):
        node = _make_node(params={
            "HOST": '"h"', "DBNAME": '"d"', "QUERY": '"q"',
            "QUERY_TIMEOUT_IN_SECONDS": "120",
        })
        result = _convert(node)
        assert result.component["config"]["query_timeout"] == 120
        assert isinstance(result.component["config"]["query_timeout"], int)

    def test_trim_all_column_true(self):
        node = _make_node(params={
            "HOST": '"h"', "DBNAME": '"d"', "QUERY": '"q"',
            "TRIM_ALL_COLUMN": "true",
        })
        result = _convert(node)
        assert result.component["config"]["trim_all_columns"] is True

    def test_trim_all_column_false(self):
        node = _make_node(params={
            "HOST": '"h"', "DBNAME": '"d"', "QUERY": '"q"',
            "TRIM_ALL_COLUMN": "false",
        })
        result = _convert(node)
        assert result.component["config"]["trim_all_columns"] is False

    def test_trim_all_column_native_bool(self):
        node = _make_node(params={
            "HOST": '"h"', "DBNAME": '"d"', "QUERY": '"q"',
            "TRIM_ALL_COLUMN": True,
        })
        result = _convert(node)
        assert result.component["config"]["trim_all_columns"] is True


# ------------------------------------------------------------------ #
# Encrypted password handling
# ------------------------------------------------------------------ #

class TestMSSqlInputPassword:
    """Test password extraction including encrypted prefix stripping."""

    def test_encrypted_password_prefix_stripped(self):
        node = _make_node(params={
            "HOST": '"h"', "DBNAME": '"d"', "QUERY": '"q"',
            "PASSWORD": "enc:system.encryption.key.v1:aBcDeFgHiJk==",
        })
        result = _convert(node)
        assert result.component["config"]["password"] == "aBcDeFgHiJk=="

    def test_plain_quoted_password(self):
        node = _make_node(params={
            "HOST": '"h"', "DBNAME": '"d"', "QUERY": '"q"',
            "PASSWORD": '"mypassword"',
        })
        result = _convert(node)
        assert result.component["config"]["password"] == "mypassword"

    def test_plain_unquoted_password(self):
        node = _make_node(params={
            "HOST": '"h"', "DBNAME": '"d"', "QUERY": '"q"',
            "PASSWORD": "plaintext",
        })
        result = _convert(node)
        assert result.component["config"]["password"] == "plaintext"

    def test_missing_password_defaults_to_empty(self):
        node = _make_node(params={
            "HOST": '"h"', "DBNAME": '"d"', "QUERY": '"q"',
        })
        result = _convert(node)
        assert result.component["config"]["password"] == ""

    def test_encrypted_prefix_with_empty_value(self):
        node = _make_node(params={
            "HOST": '"h"', "DBNAME": '"d"', "QUERY": '"q"',
            "PASSWORD": "enc:system.encryption.key.v1:",
        })
        result = _convert(node)
        assert result.component["config"]["password"] == ""


# ------------------------------------------------------------------ #
# Warnings
# ------------------------------------------------------------------ #

class TestMSSqlInputWarnings:
    """Test that appropriate warnings are generated."""

    def test_warning_when_host_empty(self):
        node = _make_node(params={"DBNAME": '"d"', "QUERY": '"q"'})
        result = _convert(node)
        assert any("HOST" in w and "empty" in w for w in result.warnings)

    def test_warning_when_dbname_empty(self):
        node = _make_node(params={"HOST": '"h"', "QUERY": '"q"'})
        result = _convert(node)
        assert any("DBNAME" in w and "empty" in w for w in result.warnings)

    def test_warning_when_query_empty(self):
        node = _make_node(params={"HOST": '"h"', "DBNAME": '"d"'})
        result = _convert(node)
        assert any("QUERY" in w and "empty" in w for w in result.warnings)

    def test_no_warnings_when_all_valid(self):
        node = _make_node(params={
            "HOST": '"sql.example.com"',
            "DBNAME": '"AdventureWorks"',
            "QUERY": '"SELECT 1"',
        })
        result = _convert(node)
        assert result.warnings == []

    def test_multiple_warnings(self):
        """When host, dbname, and query are all empty, three warnings appear."""
        node = _make_node(params={})
        result = _convert(node)
        assert len(result.warnings) == 3


# ------------------------------------------------------------------ #
# Schema parsing
# ------------------------------------------------------------------ #

class TestMSSqlInputSchema:
    """Test schema extraction for input/output."""

    def test_input_schema_always_empty(self):
        """MSSqlInput is a source -- input schema must be empty."""
        node = _make_node(params={
            "HOST": '"h"', "DBNAME": '"d"', "QUERY": '"q"',
        })
        result = _convert(node)
        assert result.component["schema"]["input"] == []

    def test_output_schema_parsed(self):
        """Schema columns are parsed into output schema dicts."""
        node = _make_node(
            params={
                "HOST": '"localhost"',
                "DBNAME": '"testdb"',
                "QUERY": '"SELECT * FROM orders"',
            },
            schema={
                "FLOW": [
                    SchemaColumn(name="order_id", type="id_Integer", key=True,
                                 nullable=False),
                    SchemaColumn(name="customer_name", type="id_String",
                                 key=False, length=255),
                    SchemaColumn(name="order_date", type="id_Date",
                                 date_pattern="yyyy-MM-dd"),
                ]
            },
        )
        result = _convert(node)
        output_schema = result.component["schema"]["output"]

        assert len(output_schema) == 3
        assert output_schema[0]["name"] == "order_id"
        assert output_schema[0]["key"] is True
        assert output_schema[0]["nullable"] is False
        assert output_schema[1]["name"] == "customer_name"
        assert output_schema[1]["length"] == 255
        assert output_schema[2]["name"] == "order_date"
        assert output_schema[2]["date_pattern"] == "%Y-%m-%d"


# ------------------------------------------------------------------ #
# Edge cases
# ------------------------------------------------------------------ #

class TestMSSqlInputEdgeCases:
    """Edge case tests."""

    def test_custom_component_id(self):
        node = _make_node(
            params={"HOST": '"h"', "DBNAME": '"d"', "QUERY": '"q"'},
            component_id="tMSSqlInput_42",
        )
        result = _convert(node)
        assert result.component["id"] == "tMSSqlInput_42"

    def test_connections_do_not_affect_config(self):
        node = _make_node(params={
            "HOST": '"h"', "DBNAME": '"d"', "QUERY": '"q"',
        })
        conns = [
            TalendConnection(
                name="row1", source="tMSSqlInput_1", target="tLogRow_1",
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
            "QUERY": "SELECT 1",
        })
        result = _convert(node)
        cfg = result.component["config"]
        assert cfg["host"] == "db.example.com"
        assert cfg["dbname"] == "AdventureWorks"
        assert cfg["user"] == "sa"
        assert cfg["query"] == "SELECT 1"

    def test_properties_preserved(self):
        """PROPERTIES value is passed through correctly."""
        node = _make_node(params={
            "HOST": '"h"', "DBNAME": '"d"', "QUERY": '"q"',
            "PROPERTIES": '"encrypt=true;trustServerCertificate=false"',
        })
        result = _convert(node)
        assert result.component["config"]["properties"] == \
            "encrypt=true;trustServerCertificate=false"

    def test_all_params_processed_not_just_first(self):
        """Regression: old code returned inside the for-loop after the first
        parameter.  Verify all parameters are present in the output."""
        node = _make_node(params={
            "HOST": '"sql.host.com"',
            "PORT": '"2000"',
            "DBNAME": '"mydb"',
            "USER": '"admin"',
            "PASSWORD": '"pass"',
            "QUERY": '"SELECT id FROM t"',
            "PROPERTIES": '"prop=val"',
            "QUERY_TIMEOUT_IN_SECONDS": "45",
            "TRIM_ALL_COLUMN": "true",
        })
        result = _convert(node)
        cfg = result.component["config"]

        # Every single parameter must be present and correct
        assert cfg["host"] == "sql.host.com"
        assert cfg["port"] == 2000
        assert cfg["dbname"] == "mydb"
        assert cfg["user"] == "admin"
        assert cfg["password"] == "pass"
        assert cfg["query"] == "SELECT id FROM t"
        assert cfg["properties"] == "prop=val"
        assert cfg["query_timeout"] == 45
        assert cfg["trim_all_columns"] is True
