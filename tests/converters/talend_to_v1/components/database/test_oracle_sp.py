"""Tests for OracleSPConverter (tOracleSP -> No Engine Implementation)."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.database.oracle_sp import OracleSPConverter
from src.converters.talend_to_v1.components.registry import REGISTRY


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


def _make_node(params=None, schema=None, component_id="oracle_sp_1",
               component_type="tOracleSP"):
    """Create a TalendNode for testing."""
    return TalendNode(
        component_id=component_id,
        component_type=component_type,
        params=params or {},
        schema=schema or {},
        position={"x": 100, "y": 200},
        raw_xml=ET.Element("node"),
    )


def _make_schema_columns():
    """Return a sample FLOW schema for testing."""
    return {
        "FLOW": [
            SchemaColumn(name="id", type="id_Integer", nullable=False, key=True, length=10),
            SchemaColumn(name="name", type="id_String", nullable=True, length=50),
        ]
    }


def _make_sp_args_data(rows):
    """Generate SP_ARGS TABLE data with stride-6 per row.

    rows: list of tuples (column, type, dbtype, is_custom, custom_type, custom_name)
    """
    result = []
    for row_values in rows:
        fields = ("COLUMN", "TYPE", "DBTYPE", "ISCUSTOME", "CUSTOME_TYPE", "CUSTOMENAME")
        for field_name, value in zip(fields, row_values):
            result.append({"elementRef": field_name, "value": value})
    return result


# ------------------------------------------------------------------
# Test Classes
# ------------------------------------------------------------------


class TestRegistration:
    """Verify component is registered correctly."""

    def test_registered_in_registry(self):
        assert REGISTRY.get("tOracleSP") is OracleSPConverter


class TestDefaults:
    """Verify all parameters have correct defaults when no params provided."""

    def test_use_existing_connection_default(self):
        node = _make_node()
        result = OracleSPConverter().convert(node, [], {})
        assert result.component["config"]["use_existing_connection"] is False

    def test_connection_default(self):
        node = _make_node()
        result = OracleSPConverter().convert(node, [], {})
        assert result.component["config"]["connection"] == ""

    def test_connection_type_default(self):
        node = _make_node()
        result = OracleSPConverter().convert(node, [], {})
        assert result.component["config"]["connection_type"] == "ORACLE_SID"

    def test_db_version_default(self):
        node = _make_node()
        result = OracleSPConverter().convert(node, [], {})
        assert result.component["config"]["db_version"] == "ORACLE_18"

    def test_host_default(self):
        node = _make_node()
        result = OracleSPConverter().convert(node, [], {})
        assert result.component["config"]["host"] == ""

    def test_port_default(self):
        node = _make_node()
        result = OracleSPConverter().convert(node, [], {})
        assert result.component["config"]["port"] == "1521"

    def test_dbname_default(self):
        node = _make_node()
        result = OracleSPConverter().convert(node, [], {})
        assert result.component["config"]["dbname"] == ""

    def test_local_service_name_default(self):
        node = _make_node()
        result = OracleSPConverter().convert(node, [], {})
        assert result.component["config"]["local_service_name"] == ""

    def test_schema_db_default(self):
        node = _make_node()
        result = OracleSPConverter().convert(node, [], {})
        assert result.component["config"]["schema_db"] == ""

    def test_user_default(self):
        node = _make_node()
        result = OracleSPConverter().convert(node, [], {})
        assert result.component["config"]["user"] == ""

    def test_password_default(self):
        node = _make_node()
        result = OracleSPConverter().convert(node, [], {})
        assert result.component["config"]["password"] == ""

    def test_sp_name_default(self):
        node = _make_node()
        result = OracleSPConverter().convert(node, [], {})
        assert result.component["config"]["sp_name"] == "myfunction"

    def test_is_function_default(self):
        node = _make_node()
        result = OracleSPConverter().convert(node, [], {})
        assert result.component["config"]["is_function"] is False

    def test_return_column_default(self):
        node = _make_node()
        result = OracleSPConverter().convert(node, [], {})
        assert result.component["config"]["return_column"] == ""

    def test_return_bdtype_default(self):
        node = _make_node()
        result = OracleSPConverter().convert(node, [], {})
        assert result.component["config"]["return_bdtype"] == "AUTOMAPPING"

    def test_sp_args_default(self):
        node = _make_node()
        result = OracleSPConverter().convert(node, [], {})
        assert result.component["config"]["sp_args"] == []

    def test_specify_datasource_alias_default(self):
        node = _make_node()
        result = OracleSPConverter().convert(node, [], {})
        assert result.component["config"]["specify_datasource_alias"] is False

    def test_datasource_alias_default(self):
        node = _make_node()
        result = OracleSPConverter().convert(node, [], {})
        assert result.component["config"]["datasource_alias"] == ""

    def test_properties_default(self):
        node = _make_node()
        result = OracleSPConverter().convert(node, [], {})
        assert result.component["config"]["properties"] == ""

    def test_encoding_default(self):
        node = _make_node()
        result = OracleSPConverter().convert(node, [], {})
        assert result.component["config"]["encoding"] == "ISO-8859-15"

    def test_nls_language_default(self):
        node = _make_node()
        result = OracleSPConverter().convert(node, [], {})
        assert result.component["config"]["nls_language"] == "NONE"

    def test_nls_territory_default(self):
        node = _make_node()
        result = OracleSPConverter().convert(node, [], {})
        assert result.component["config"]["nls_territory"] == "NONE"

    def test_support_nls_default(self):
        node = _make_node()
        result = OracleSPConverter().convert(node, [], {})
        assert result.component["config"]["support_nls"] is False


class TestParameterExtraction:
    """Verify each parameter is correctly extracted from XML params."""

    def test_sp_name_extracted(self):
        node = _make_node(params={"SP_NAME": '"my_proc"'})
        result = OracleSPConverter().convert(node, [], {})
        assert result.component["config"]["sp_name"] == "my_proc"

    def test_is_function_true(self):
        node = _make_node(params={"IS_FUNCTION": "true"})
        result = OracleSPConverter().convert(node, [], {})
        assert result.component["config"]["is_function"] is True

    def test_return_column_extracted(self):
        node = _make_node(params={"RETURN": '"result_col"'})
        result = OracleSPConverter().convert(node, [], {})
        assert result.component["config"]["return_column"] == "result_col"

    def test_return_bdtype_extracted(self):
        node = _make_node(params={"RETURN_BDTYPE": '"VARCHAR2"'})
        result = OracleSPConverter().convert(node, [], {})
        assert result.component["config"]["return_bdtype"] == "VARCHAR2"

    def test_use_existing_connection_true(self):
        node = _make_node(params={"USE_EXISTING_CONNECTION": "true"})
        result = OracleSPConverter().convert(node, [], {})
        assert result.component["config"]["use_existing_connection"] is True

    def test_connection_extracted(self):
        node = _make_node(params={"CONNECTION": '"tOracleConnection_1"'})
        result = OracleSPConverter().convert(node, [], {})
        assert result.component["config"]["connection"] == "tOracleConnection_1"

    def test_connection_type_service_name(self):
        node = _make_node(params={"CONNECTION_TYPE": '"ORACLE_SERVICE_NAME"'})
        result = OracleSPConverter().convert(node, [], {})
        assert result.component["config"]["connection_type"] == "ORACLE_SERVICE_NAME"

    def test_host_extracted(self):
        node = _make_node(params={"HOST": '"db-host.example.com"'})
        result = OracleSPConverter().convert(node, [], {})
        assert result.component["config"]["host"] == "db-host.example.com"

    def test_port_extracted(self):
        node = _make_node(params={"PORT": '"1522"'})
        result = OracleSPConverter().convert(node, [], {})
        assert result.component["config"]["port"] == "1522"

    def test_password_extracted_from_pass(self):
        """PASS is the XML name -- config key is password."""
        node = _make_node(params={"PASS": '"secret123"'})
        result = OracleSPConverter().convert(node, [], {})
        assert result.component["config"]["password"] == "secret123"

    def test_schema_db_extracted(self):
        node = _make_node(params={"SCHEMA_DB": '"MY_SCHEMA"'})
        result = OracleSPConverter().convert(node, [], {})
        assert result.component["config"]["schema_db"] == "MY_SCHEMA"

    def test_specify_datasource_alias_true(self):
        node = _make_node(params={"SPECIFY_DATASOURCE_ALIAS": "true"})
        result = OracleSPConverter().convert(node, [], {})
        assert result.component["config"]["specify_datasource_alias"] is True

    def test_datasource_alias_extracted(self):
        node = _make_node(params={"DATASOURCE_ALIAS": '"jdbc/myDS"'})
        result = OracleSPConverter().convert(node, [], {})
        assert result.component["config"]["datasource_alias"] == "jdbc/myDS"

    def test_encoding_extracted(self):
        node = _make_node(params={"ENCODING": '"UTF-8"'})
        result = OracleSPConverter().convert(node, [], {})
        assert result.component["config"]["encoding"] == "UTF-8"

    def test_support_nls_true(self):
        node = _make_node(params={"SUPPORT_NLS": "true"})
        result = OracleSPConverter().convert(node, [], {})
        assert result.component["config"]["support_nls"] is True

    def test_nls_language_extracted(self):
        node = _make_node(params={"NLS_LANGUAGE": '"AMERICAN"'})
        result = OracleSPConverter().convert(node, [], {})
        assert result.component["config"]["nls_language"] == "AMERICAN"

    def test_nls_territory_extracted(self):
        node = _make_node(params={"NLS_TERRITORY": '"AMERICA"'})
        result = OracleSPConverter().convert(node, [], {})
        assert result.component["config"]["nls_territory"] == "AMERICA"


class TestSpArgsTable:
    """Verify SP_ARGS TABLE stride-6 parsing."""

    def test_empty_sp_args(self):
        node = _make_node()
        result = OracleSPConverter().convert(node, [], {})
        assert result.component["config"]["sp_args"] == []

    def test_sp_args_single_row(self):
        """Single argument row with all 6 fields."""
        sp_args = _make_sp_args_data([
            ('"id"', '"IN"', '"INTEGER"', "false", '"STRUCT"', '""'),
        ])
        node = _make_node(params={"SP_ARGS": sp_args})
        result = OracleSPConverter().convert(node, [], {})
        assert len(result.component["config"]["sp_args"]) == 1
        arg = result.component["config"]["sp_args"][0]
        assert arg["column"] == "id"
        assert arg["type"] == "IN"
        assert arg["dbtype"] == "INTEGER"
        assert arg["is_custom"] is False
        assert arg["custom_type"] == "STRUCT"
        assert arg["custom_name"] == ""

    def test_sp_args_multiple_rows(self):
        """Multiple argument rows parsed correctly."""
        sp_args = _make_sp_args_data([
            ('"id"', '"IN"', '"INTEGER"', "false", '"STRUCT"', '""'),
            ('"name"', '"OUT"', '"VARCHAR2"', "false", '"STRUCT"', '""'),
            ('"result"', '"INOUT"', '"NUMBER"', "true", '"ARRAY"', '"MY_ARRAY_TYPE"'),
        ])
        node = _make_node(params={"SP_ARGS": sp_args})
        result = OracleSPConverter().convert(node, [], {})
        assert len(result.component["config"]["sp_args"]) == 3
        assert result.component["config"]["sp_args"][0]["column"] == "id"
        assert result.component["config"]["sp_args"][1]["type"] == "OUT"
        assert result.component["config"]["sp_args"][2]["is_custom"] is True
        assert result.component["config"]["sp_args"][2]["custom_type"] == "ARRAY"
        assert result.component["config"]["sp_args"][2]["custom_name"] == "MY_ARRAY_TYPE"

    def test_sp_args_incomplete_group_skipped(self):
        """Trailing incomplete groups (< 6 entries) are ignored."""
        sp_args = _make_sp_args_data([
            ('"id"', '"IN"', '"INTEGER"', "false", '"STRUCT"', '""'),
        ])
        # Add 3 trailing entries (incomplete group)
        sp_args.append({"elementRef": "COLUMN", "value": '"extra"'})
        sp_args.append({"elementRef": "TYPE", "value": '"IN"'})
        sp_args.append({"elementRef": "DBTYPE", "value": '"VARCHAR2"'})
        node = _make_node(params={"SP_ARGS": sp_args})
        result = OracleSPConverter().convert(node, [], {})
        assert len(result.component["config"]["sp_args"]) == 1

    def test_sp_args_none_value(self):
        """None value for SP_ARGS returns empty list."""
        node = _make_node(params={"SP_ARGS": None})
        result = OracleSPConverter().convert(node, [], {})
        assert result.component["config"]["sp_args"] == []

    def test_sp_args_non_list_value(self):
        """Non-list value for SP_ARGS returns empty list."""
        node = _make_node(params={"SP_ARGS": "invalid"})
        result = OracleSPConverter().convert(node, [], {})
        assert result.component["config"]["sp_args"] == []


class TestFrameworkParams:
    """Verify tstatcatcher_stats and label extraction."""

    def test_tstatcatcher_stats_default_false(self):
        node = _make_node()
        result = OracleSPConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is False

    def test_tstatcatcher_stats_true(self):
        node = _make_node(params={"TSTATCATCHER_STATS": "true"})
        result = OracleSPConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is True

    def test_label_default_empty(self):
        node = _make_node()
        result = OracleSPConverter().convert(node, [], {})
        assert result.component["config"]["label"] == ""

    def test_label_extracted(self):
        node = _make_node(params={"LABEL": '"my_sp_label"'})
        result = OracleSPConverter().convert(node, [], {})
        assert result.component["config"]["label"] == "my_sp_label"


class TestSchema:
    """Verify schema extraction (bidirectional: SP reads input and produces output)."""

    def test_schema_has_input_and_output(self):
        node = _make_node(schema=_make_schema_columns())
        result = OracleSPConverter().convert(node, [], {})
        schema = result.component["schema"]
        assert "input" in schema
        assert "output" in schema

    def test_schema_input_extracted(self):
        node = _make_node(schema=_make_schema_columns())
        result = OracleSPConverter().convert(node, [], {})
        assert len(result.component["schema"]["input"]) == 2
        assert result.component["schema"]["input"][0]["name"] == "id"
        assert result.component["schema"]["input"][1]["name"] == "name"

    def test_schema_output_extracted(self):
        node = _make_node(schema=_make_schema_columns())
        result = OracleSPConverter().convert(node, [], {})
        assert len(result.component["schema"]["output"]) == 2
        assert result.component["schema"]["output"][0]["name"] == "id"
        assert result.component["schema"]["output"][1]["name"] == "name"

    def test_schema_empty_when_no_schema(self):
        node = _make_node()
        result = OracleSPConverter().convert(node, [], {})
        assert result.component["schema"] == {"input": [], "output": []}


class TestNeedsReview:
    """Verify needs_review entries for engine gaps."""

    def test_needs_review_count(self):
        """Single consolidated needs_review per D-27 (no engine)."""
        node = _make_node()
        result = OracleSPConverter().convert(node, [], {})
        assert len(result.needs_review) == 1

    def test_needs_review_severity(self):
        node = _make_node()
        result = OracleSPConverter().convert(node, [], {})
        for entry in result.needs_review:
            assert entry["severity"] == "engine_gap"

    def test_needs_review_has_component_id(self):
        node = _make_node(component_id="test_comp")
        result = OracleSPConverter().convert(node, [], {})
        for entry in result.needs_review:
            assert entry["component"] == "test_comp"

    def test_no_framework_param_needs_review(self):
        """Framework params (tstatcatcher_stats, label) must NOT have needs_review."""
        node = _make_node()
        result = OracleSPConverter().convert(node, [], {})
        issues = [e["issue"] for e in result.needs_review]
        for issue in issues:
            assert "tstatcatcher_stats" not in issue
            assert "label" not in issue.lower().split()


class TestCompleteness:
    """Verify all expected config keys are present and standard structure."""

    def test_all_config_keys_present(self):
        node = _make_node(schema=_make_schema_columns())
        result = OracleSPConverter().convert(node, [], {})
        expected_keys = {
            "use_existing_connection", "connection", "connection_type",
            "db_version", "host", "port", "dbname", "local_service_name",
            "schema_db", "user", "password",
            "sp_name", "is_function", "return_column", "return_bdtype",
            "sp_args",
            "specify_datasource_alias", "datasource_alias",
            "properties", "encoding",
            "nls_language", "nls_territory", "support_nls",
            "tstatcatcher_stats", "label",
        }
        actual_keys = set(result.component["config"].keys())
        missing = expected_keys - actual_keys
        assert not missing, f"Missing config keys: {missing}"

    def test_standard_component_structure(self):
        """Component dict has standard top-level keys from _build_component_dict."""
        node = _make_node(schema=_make_schema_columns())
        result = OracleSPConverter().convert(node, [], {})
        assert result.component["id"] == "oracle_sp_1"
        assert result.component["type"] == "tOracleSP"
        assert result.component["original_type"] == "tOracleSP"
        assert result.component["position"] == {"x": 100, "y": 200}
        assert isinstance(result.component["config"], dict)
        assert isinstance(result.component["schema"], dict)
        assert result.component["inputs"] == []
        assert result.component["outputs"] == []


class TestPhantomParams:
    """Verify params NOT in _java.xml are NOT extracted."""

    def test_procedure_not_in_output(self):
        """Old converter used PROCEDURE -- must not appear in output."""
        node = _make_node(params={"PROCEDURE": '"my_proc"'})
        result = OracleSPConverter().convert(node, [], {})
        assert "procedure" not in result.component["config"]

    def test_die_on_error_not_in_output(self):
        """Old converter extracted DIE_ON_ERROR -- not in _java.xml."""
        node = _make_node(params={"DIE_ON_ERROR": "true"})
        result = OracleSPConverter().convert(node, [], {})
        assert "die_on_error" not in result.component["config"]
        assert "DIE_ON_ERROR" not in result.component["config"]
