"""Tests for OracleInputConverter (tOracleInput -> No Engine Implementation)."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.database.oracle_input import (
    OracleInputConverter,
)
from src.converters.talend_to_v1.components.registry import REGISTRY


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

def _make_node(params=None, schema=None, component_id="tOracleInput_1",
               component_type="tOracleInput"):
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


def _convert(node, connections=None, context=None):
    """Helper to run the converter."""
    converter = OracleInputConverter()
    return converter.convert(
        node=node,
        connections=connections or [],
        context=context or {},
    )


# ------------------------------------------------------------------
# Registration
# ------------------------------------------------------------------

class TestRegistration:
    """Verify component is registered correctly."""

    def test_registered_in_registry(self):
        """tOracleInput maps to OracleInputConverter in the registry."""
        assert REGISTRY.get("tOracleInput") is OracleInputConverter


# ------------------------------------------------------------------
# Structure
# ------------------------------------------------------------------

class TestStructure:
    """Verify standard component dict structure from _build_component_dict."""

    def test_id_at_top_level(self):
        """Component dict has 'id' at top level."""
        result = _convert(_make_node())
        assert result.component["id"] == "tOracleInput_1"

    def test_type_at_top_level(self):
        """Component dict has 'type' at top level."""
        result = _convert(_make_node())
        assert result.component["type"] == "tOracleInput"

    def test_original_type_at_top_level(self):
        """Component dict has 'original_type' at top level."""
        result = _convert(_make_node())
        assert result.component["original_type"] == "tOracleInput"

    def test_config_is_nested_dict(self):
        """Config params are nested under 'config' key."""
        result = _convert(_make_node())
        assert isinstance(result.component["config"], dict)

    def test_position_at_top_level(self):
        """Component dict has 'position' at top level."""
        result = _convert(_make_node())
        assert result.component["position"] == {"x": 100, "y": 200}

    def test_inputs_outputs_at_top_level(self):
        """Component dict has 'inputs' and 'outputs' at top level."""
        result = _convert(_make_node())
        assert result.component["inputs"] == []
        assert result.component["outputs"] == []


# ------------------------------------------------------------------
# Defaults
# ------------------------------------------------------------------

class TestDefaults:
    """Verify all parameters have correct defaults when no params provided."""

    def test_use_existing_connection_default(self):
        """USE_EXISTING_CONNECTION defaults to False."""
        result = _convert(_make_node())
        assert result.component["config"]["use_existing_connection"] is False

    def test_connection_default(self):
        """CONNECTION defaults to empty string."""
        result = _convert(_make_node())
        assert result.component["config"]["connection"] == ""

    def test_connection_type_default(self):
        """CONNECTION_TYPE defaults to ORACLE_SID."""
        result = _convert(_make_node())
        assert result.component["config"]["connection_type"] == "ORACLE_SID"

    def test_db_version_default(self):
        """DB_VERSION defaults to ORACLE_18."""
        result = _convert(_make_node())
        assert result.component["config"]["db_version"] == "ORACLE_18"

    def test_rac_url_default(self):
        """RAC_URL defaults to empty string."""
        result = _convert(_make_node())
        assert result.component["config"]["rac_url"] == ""

    def test_host_default(self):
        """HOST defaults to empty string."""
        result = _convert(_make_node())
        assert result.component["config"]["host"] == ""

    def test_port_default(self):
        """PORT defaults to 1521 (standard Oracle port, as string)."""
        result = _convert(_make_node())
        assert result.component["config"]["port"] == "1521"

    def test_dbname_default(self):
        """DBNAME defaults to empty string."""
        result = _convert(_make_node())
        assert result.component["config"]["dbname"] == ""

    def test_local_service_name_default(self):
        """LOCAL_SERVICE_NAME defaults to empty string."""
        result = _convert(_make_node())
        assert result.component["config"]["local_service_name"] == ""

    def test_schema_db_default(self):
        """SCHEMA_DB -> schema_db defaults to empty string."""
        result = _convert(_make_node())
        assert result.component["config"]["schema_db"] == ""

    def test_user_default(self):
        """USER defaults to empty string."""
        result = _convert(_make_node())
        assert result.component["config"]["user"] == ""

    def test_password_default(self):
        """PASS -> password defaults to empty string."""
        result = _convert(_make_node())
        assert result.component["config"]["password"] == ""

    def test_jdbc_url_default(self):
        """JDBC_URL defaults to empty string."""
        result = _convert(_make_node())
        assert result.component["config"]["jdbc_url"] == ""

    def test_table_default(self):
        """TABLE defaults to empty string."""
        result = _convert(_make_node())
        assert result.component["config"]["table"] == ""

    def test_query_default(self):
        """QUERY defaults to the example query from _java.xml."""
        result = _convert(_make_node())
        assert result.component["config"]["query"] == "select id, name from employee"

    def test_specify_datasource_alias_default(self):
        """SPECIFY_DATASOURCE_ALIAS defaults to False."""
        result = _convert(_make_node())
        assert result.component["config"]["specify_datasource_alias"] is False

    def test_datasource_alias_default(self):
        """DATASOURCE_ALIAS defaults to empty string."""
        result = _convert(_make_node())
        assert result.component["config"]["datasource_alias"] == ""

    def test_properties_default(self):
        """PROPERTIES defaults to empty string."""
        result = _convert(_make_node())
        assert result.component["config"]["properties"] == ""

    def test_is_convert_xmltype_default(self):
        """IS_CONVERT_XMLTYPE defaults to False."""
        result = _convert(_make_node())
        assert result.component["config"]["is_convert_xmltype"] is False

    def test_convert_xmltype_default(self):
        """CONVERT_XMLTYPE defaults to empty list."""
        result = _convert(_make_node())
        assert result.component["config"]["convert_xmltype"] == []

    def test_encoding_default(self):
        """ENCODING defaults to ISO-8859-15 (not UTF-8)."""
        result = _convert(_make_node())
        assert result.component["config"]["encoding"] == "ISO-8859-15"

    def test_use_cursor_default(self):
        """USE_CURSOR defaults to False."""
        result = _convert(_make_node())
        assert result.component["config"]["use_cursor"] is False

    def test_cursor_size_default(self):
        """CURSOR_SIZE defaults to 1000."""
        result = _convert(_make_node())
        assert result.component["config"]["cursor_size"] == 1000

    def test_trim_all_column_default(self):
        """TRIM_ALL_COLUMN defaults to False."""
        result = _convert(_make_node())
        assert result.component["config"]["trim_all_column"] is False

    def test_trim_column_default(self):
        """TRIM_COLUMN defaults to empty list."""
        result = _convert(_make_node())
        assert result.component["config"]["trim_column"] == []

    def test_no_null_values_default(self):
        """NO_NULL_VALUES defaults to False."""
        result = _convert(_make_node())
        assert result.component["config"]["no_null_values"] is False

    def test_support_nls_default(self):
        """SUPPORT_NLS defaults to False."""
        result = _convert(_make_node())
        assert result.component["config"]["support_nls"] is False


# ------------------------------------------------------------------
# Parameter Extraction
# ------------------------------------------------------------------

class TestParameterExtraction:
    """Verify each parameter is correctly extracted from XML params."""

    def test_use_existing_connection_true(self):
        """USE_EXISTING_CONNECTION extracted as True when set."""
        node = _make_node(params={"USE_EXISTING_CONNECTION": "true"})
        result = _convert(node)
        assert result.component["config"]["use_existing_connection"] is True

    def test_connection_extracted(self):
        """CONNECTION component name extracted."""
        node = _make_node(params={"CONNECTION": '"tOracleConnection_1"'})
        result = _convert(node)
        assert result.component["config"]["connection"] == "tOracleConnection_1"

    def test_connection_type_extracted(self):
        """CONNECTION_TYPE closed list value extracted."""
        node = _make_node(params={"CONNECTION_TYPE": '"ORACLE_SERVICE_NAME"'})
        result = _convert(node)
        assert result.component["config"]["connection_type"] == "ORACLE_SERVICE_NAME"

    def test_db_version_extracted(self):
        """DB_VERSION closed list value extracted."""
        node = _make_node(params={"DB_VERSION": '"ORACLE_12"'})
        result = _convert(node)
        assert result.component["config"]["db_version"] == "ORACLE_12"

    def test_rac_url_extracted(self):
        """RAC_URL extracted."""
        node = _make_node(params={"RAC_URL": '"jdbc:oracle:thin:@(DESCRIPTION=(LOAD_BALANCE=on))"'})
        result = _convert(node)
        assert result.component["config"]["rac_url"] == "jdbc:oracle:thin:@(DESCRIPTION=(LOAD_BALANCE=on))"

    def test_host_extracted(self):
        """HOST extracted from quoted value."""
        node = _make_node(params={"HOST": '"oracle.example.com"'})
        result = _convert(node)
        assert result.component["config"]["host"] == "oracle.example.com"

    def test_port_extracted(self):
        """PORT extracted as string."""
        node = _make_node(params={"PORT": '"1522"'})
        result = _convert(node)
        assert result.component["config"]["port"] == "1522"

    def test_dbname_extracted(self):
        """DBNAME extracted."""
        node = _make_node(params={"DBNAME": '"ORCL"'})
        result = _convert(node)
        assert result.component["config"]["dbname"] == "ORCL"

    def test_local_service_name_extracted(self):
        """LOCAL_SERVICE_NAME extracted."""
        node = _make_node(params={"LOCAL_SERVICE_NAME": '"orcl_local"'})
        result = _convert(node)
        assert result.component["config"]["local_service_name"] == "orcl_local"

    def test_schema_db_extracted(self):
        """SCHEMA_DB -> schema_db extracted."""
        node = _make_node(params={"SCHEMA_DB": '"HR"'})
        result = _convert(node)
        assert result.component["config"]["schema_db"] == "HR"

    def test_user_extracted(self):
        """USER extracted."""
        node = _make_node(params={"USER": '"scott"'})
        result = _convert(node)
        assert result.component["config"]["user"] == "scott"

    def test_password_extracted_via_pass(self):
        """PASS -> password extracted (NOT PASSWORD)."""
        node = _make_node(params={"PASS": '"tiger"'})
        result = _convert(node)
        assert result.component["config"]["password"] == "tiger"

    def test_jdbc_url_extracted(self):
        """JDBC_URL extracted."""
        node = _make_node(params={"JDBC_URL": '"jdbc:oracle:thin:/@wallet_alias"'})
        result = _convert(node)
        assert result.component["config"]["jdbc_url"] == "jdbc:oracle:thin:/@wallet_alias"

    def test_table_extracted(self):
        """TABLE extracted."""
        node = _make_node(params={"TABLE": '"EMPLOYEES"'})
        result = _convert(node)
        assert result.component["config"]["table"] == "EMPLOYEES"

    def test_query_extracted(self):
        """QUERY extracted from memo field."""
        node = _make_node(params={"QUERY": '"SELECT * FROM emp WHERE dept_id = 10"'})
        result = _convert(node)
        assert result.component["config"]["query"] == "SELECT * FROM emp WHERE dept_id = 10"

    def test_specify_datasource_alias_true(self):
        """SPECIFY_DATASOURCE_ALIAS extracted as True."""
        node = _make_node(params={"SPECIFY_DATASOURCE_ALIAS": "true"})
        result = _convert(node)
        assert result.component["config"]["specify_datasource_alias"] is True

    def test_datasource_alias_extracted(self):
        """DATASOURCE_ALIAS extracted."""
        node = _make_node(params={"DATASOURCE_ALIAS": '"oracleDS"'})
        result = _convert(node)
        assert result.component["config"]["datasource_alias"] == "oracleDS"

    def test_properties_extracted(self):
        """PROPERTIES extracted."""
        node = _make_node(params={"PROPERTIES": '"oracle.jdbc.timezoneAsRegion=false"'})
        result = _convert(node)
        assert result.component["config"]["properties"] == "oracle.jdbc.timezoneAsRegion=false"

    def test_is_convert_xmltype_true(self):
        """IS_CONVERT_XMLTYPE extracted as True."""
        node = _make_node(params={"IS_CONVERT_XMLTYPE": "true"})
        result = _convert(node)
        assert result.component["config"]["is_convert_xmltype"] is True

    def test_encoding_extracted(self):
        """ENCODING extracted, overriding default."""
        node = _make_node(params={"ENCODING": '"UTF-8"'})
        result = _convert(node)
        assert result.component["config"]["encoding"] == "UTF-8"

    def test_use_cursor_true(self):
        """USE_CURSOR extracted as True."""
        node = _make_node(params={"USE_CURSOR": "true"})
        result = _convert(node)
        assert result.component["config"]["use_cursor"] is True

    def test_cursor_size_extracted(self):
        """CURSOR_SIZE extracted as int."""
        node = _make_node(params={"CURSOR_SIZE": '"500"'})
        result = _convert(node)
        assert result.component["config"]["cursor_size"] == 500

    def test_trim_all_column_true(self):
        """TRIM_ALL_COLUMN extracted as True."""
        node = _make_node(params={"TRIM_ALL_COLUMN": "true"})
        result = _convert(node)
        assert result.component["config"]["trim_all_column"] is True

    def test_no_null_values_true(self):
        """NO_NULL_VALUES extracted as True."""
        node = _make_node(params={"NO_NULL_VALUES": "true"})
        result = _convert(node)
        assert result.component["config"]["no_null_values"] is True

    def test_support_nls_true(self):
        """SUPPORT_NLS extracted as True."""
        node = _make_node(params={"SUPPORT_NLS": "true"})
        result = _convert(node)
        assert result.component["config"]["support_nls"] is True

    def test_host_port_extracted_together(self):
        """HOST and PORT extracted together correctly."""
        node = _make_node(params={"HOST": '"db.example.com"', "PORT": '"1525"'})
        result = _convert(node)
        assert result.component["config"]["host"] == "db.example.com"
        assert result.component["config"]["port"] == "1525"


# ------------------------------------------------------------------
# TABLE Parsing: CONVERT_XMLTYPE
# ------------------------------------------------------------------

class TestConvertXmltypeParsing:
    """Verify CONVERT_XMLTYPE TABLE parameter parsing."""

    def test_convert_xmltype_parsed(self):
        """CONVERT_XMLTYPE table entries parsed correctly."""
        raw_table = [
            {"elementRef": "SCHEMA_COLUMN", "value": '"xml_data"'},
            {"elementRef": "XML_COLUMN", "value": '"XML_COL"'},
        ]
        node = _make_node(params={"CONVERT_XMLTYPE": raw_table})
        result = _convert(node)
        assert len(result.component["config"]["convert_xmltype"]) == 1
        assert result.component["config"]["convert_xmltype"][0]["schema_column"] == "xml_data"
        assert result.component["config"]["convert_xmltype"][0]["xml_column"] == "XML_COL"

    def test_convert_xmltype_empty_when_missing(self):
        """CONVERT_XMLTYPE defaults to empty list."""
        result = _convert(_make_node())
        assert result.component["config"]["convert_xmltype"] == []

    def test_convert_xmltype_multiple_rows(self):
        """Multiple CONVERT_XMLTYPE rows parsed."""
        raw_table = [
            {"elementRef": "SCHEMA_COLUMN", "value": '"col1"'},
            {"elementRef": "XML_COLUMN", "value": '"XML_A"'},
            {"elementRef": "SCHEMA_COLUMN", "value": '"col2"'},
            {"elementRef": "XML_COLUMN", "value": '"XML_B"'},
        ]
        node = _make_node(params={"CONVERT_XMLTYPE": raw_table})
        result = _convert(node)
        assert len(result.component["config"]["convert_xmltype"]) == 2
        assert result.component["config"]["convert_xmltype"][0]["schema_column"] == "col1"
        assert result.component["config"]["convert_xmltype"][1]["schema_column"] == "col2"

    def test_convert_xmltype_incomplete_stride_skipped(self):
        """Incomplete trailing CONVERT_XMLTYPE group is skipped."""
        raw_table = [
            {"elementRef": "SCHEMA_COLUMN", "value": '"col1"'},
            {"elementRef": "XML_COLUMN", "value": '"XML_A"'},
            {"elementRef": "SCHEMA_COLUMN", "value": '"col2"'},
            # Missing XML_COLUMN -- incomplete stride
        ]
        node = _make_node(params={"CONVERT_XMLTYPE": raw_table})
        result = _convert(node)
        assert len(result.component["config"]["convert_xmltype"]) == 1


# ------------------------------------------------------------------
# TABLE Parsing: TRIM_COLUMN
# ------------------------------------------------------------------

class TestTrimColumnParsing:
    """Verify TRIM_COLUMN TABLE parameter parsing."""

    def test_trim_column_parsed(self):
        """TRIM_COLUMN table entries parsed."""
        raw_table = [
            {"elementRef": "SCHEMA_COLUMN", "value": '"first_name"'},
        ]
        node = _make_node(params={"TRIM_COLUMN": raw_table})
        result = _convert(node)
        assert len(result.component["config"]["trim_column"]) == 1

    def test_trim_column_empty_when_missing(self):
        """TRIM_COLUMN defaults to empty list."""
        result = _convert(_make_node())
        assert result.component["config"]["trim_column"] == []


# ------------------------------------------------------------------
# PASS vs PASSWORD Fix
# ------------------------------------------------------------------

class TestPassVsPasswordFix:
    """Verify the PASS extraction fix (NOT PASSWORD)."""

    def test_pass_extracted_not_password(self):
        """Converter uses PASS not PASSWORD for extraction."""
        node = _make_node(params={"PASS": '"correct_pass"', "PASSWORD": '"wrong_pass"'})
        result = _convert(node)
        assert result.component["config"]["password"] == "correct_pass"

    def test_password_param_ignored(self):
        """PASSWORD param alone does NOT populate the password config key."""
        node = _make_node(params={"PASSWORD": '"should_not_appear"'})
        result = _convert(node)
        assert result.component["config"]["password"] == ""


# ------------------------------------------------------------------
# Framework Params
# ------------------------------------------------------------------

class TestFrameworkParams:
    """Verify tstatcatcher_stats and label extraction."""

    def test_tstatcatcher_stats_default_false(self):
        """TSTATCATCHER_STATS defaults to False."""
        result = _convert(_make_node())
        assert result.component["config"]["tstatcatcher_stats"] is False

    def test_tstatcatcher_stats_true(self):
        """TSTATCATCHER_STATS extracted as True."""
        node = _make_node(params={"TSTATCATCHER_STATS": "true"})
        result = _convert(node)
        assert result.component["config"]["tstatcatcher_stats"] is True

    def test_label_default_empty(self):
        """LABEL defaults to empty string."""
        result = _convert(_make_node())
        assert result.component["config"]["label"] == ""

    def test_label_extracted(self):
        """LABEL extracted from quoted value."""
        node = _make_node(params={"LABEL": '"my_label"'})
        result = _convert(node)
        assert result.component["config"]["label"] == "my_label"


# ------------------------------------------------------------------
# Schema
# ------------------------------------------------------------------

class TestSchema:
    """Verify schema extraction with source pattern (output has schema, input is empty)."""

    def test_schema_is_dict_with_input_output(self):
        """Schema is a dict with 'input' and 'output' keys (source pattern)."""
        result = _convert(_make_node())
        schema = result.component["schema"]
        assert isinstance(schema, dict)
        assert "input" in schema
        assert "output" in schema

    def test_schema_input_always_empty(self):
        """Source components have empty input schema (data flows OUT)."""
        node = _make_node(schema=_make_schema_columns())
        result = _convert(node)
        assert result.component["schema"]["input"] == []

    def test_schema_output_extracted(self):
        """FLOW schema columns are parsed into the output schema."""
        node = _make_node(schema=_make_schema_columns())
        result = _convert(node)
        schema_output = result.component["schema"]["output"]
        assert len(schema_output) == 2
        assert schema_output[0]["name"] == "id"
        assert schema_output[0]["key"] is True
        assert schema_output[0]["nullable"] is False
        assert schema_output[1]["name"] == "name"
        assert schema_output[1]["length"] == 50

    def test_empty_schema_when_no_flow(self):
        """No FLOW schema produces empty output list."""
        result = _convert(_make_node())
        assert result.component["schema"]["input"] == []
        assert result.component["schema"]["output"] == []


# ------------------------------------------------------------------
# Needs Review
# ------------------------------------------------------------------

class TestNeedsReview:
    """Verify needs_review entries for engine gaps."""

    def test_needs_review_count(self):
        """Single consolidated needs_review entry per D-27."""
        result = _convert(_make_node())
        assert len(result.needs_review) == 1

    def test_needs_review_is_engine_gap(self):
        """needs_review severity is engine_gap."""
        result = _convert(_make_node())
        assert result.needs_review[0]["severity"] == "engine_gap"

    def test_needs_review_has_component_id(self):
        """needs_review includes the component ID."""
        node = _make_node(component_id="tOracleInput_42")
        result = _convert(node)
        assert result.needs_review[0]["component"] == "tOracleInput_42"

    def test_no_framework_param_needs_review(self):
        """Framework params must NOT appear in needs_review issues."""
        result = _convert(_make_node())
        issues = [e["issue"] for e in result.needs_review]
        for issue in issues:
            assert "tstatcatcher_stats" not in issue
            assert "label" not in issue.lower().split()


# ------------------------------------------------------------------
# Completeness
# ------------------------------------------------------------------

class TestCompleteness:
    """Verify all expected config keys are present."""

    def test_all_config_keys_present(self):
        """All 28 config keys present in output (26 unique + 2 framework)."""
        node = _make_node(schema=_make_schema_columns())
        result = _convert(node)
        expected_keys = {
            "use_existing_connection", "connection",
            "connection_type", "db_version", "rac_url",
            "host", "port", "dbname", "local_service_name",
            "schema_db", "user", "password", "jdbc_url",
            "table", "query",
            "specify_datasource_alias", "datasource_alias",
            "properties", "is_convert_xmltype", "convert_xmltype",
            "encoding", "use_cursor", "cursor_size",
            "trim_all_column", "trim_column",
            "no_null_values", "support_nls",
            "tstatcatcher_stats", "label",
        }
        actual_keys = set(result.component["config"].keys())
        missing = expected_keys - actual_keys
        assert not missing, f"Missing config keys: {missing}"

    def test_top_level_keys(self):
        """Standard component dict has all required top-level keys."""
        result = _convert(_make_node())
        expected_top = {"id", "type", "original_type", "position", "config", "schema", "inputs", "outputs"}
        actual_top = set(result.component.keys())
        missing = expected_top - actual_top
        assert not missing, f"Missing top-level keys: {missing}"

    def test_result_type_is_component_result(self):
        """convert() returns a ComponentResult."""
        result = _convert(_make_node())
        assert isinstance(result, ComponentResult)
