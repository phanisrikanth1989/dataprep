"""Tests for OracleBulkExecConverter (tOracleBulkExec -> No Engine Implementation)."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendNode,
)
from src.converters.talend_to_v1.components.database.oracle_bulk_exec import (
    OracleBulkExecConverter,
)
from src.converters.talend_to_v1.components.registry import REGISTRY


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

def _make_node(params=None, schema=None, component_id="tOracleBulkExec_1",
               component_type="tOracleBulkExec"):
    """Create a TalendNode for testing."""
    return TalendNode(
        component_id=component_id,
        component_type=component_type,
        params=params or {},
        schema=schema or {},
        position={"x": 320, "y": 160},
        raw_xml=ET.Element("node"),
    )


def _make_schema_columns():
    """Return a sample FLOW schema for testing."""
    return {
        "FLOW": [
            SchemaColumn(name="id", type="id_Integer", nullable=False, key=True, length=10),
            SchemaColumn(name="name", type="id_String", nullable=True, length=100),
            SchemaColumn(name="amount", type="id_Double", nullable=True, precision=2),
        ]
    }


def _make_options_table(rows):
    """Generate OPTIONS TABLE data with stride-1 per row.

    rows: list of str values for each option
    """
    result = []
    for value in rows:
        result.append({"elementRef": "OPTIONS", "value": value})
    return result


# ------------------------------------------------------------------
# Test Classes
# ------------------------------------------------------------------


class TestRegistration:
    """Verify component is registered correctly."""

    def test_registered_in_registry(self):
        assert REGISTRY.get("tOracleBulkExec") is OracleBulkExecConverter


class TestDefaults:
    """Verify all parameters have correct defaults when no params provided."""

    # ---- Connection mode ----
    def test_use_existing_connection_default(self):
        node = _make_node()
        result = OracleBulkExecConverter().convert(node, [], {})
        assert result.component["config"]["use_existing_connection"] is False

    def test_connection_default(self):
        node = _make_node()
        result = OracleBulkExecConverter().convert(node, [], {})
        assert result.component["config"]["connection"] == ""

    # ---- Connection type ----
    def test_connection_type_default(self):
        node = _make_node()
        result = OracleBulkExecConverter().convert(node, [], {})
        assert result.component["config"]["connection_type"] == "ORACLE_SID"

    def test_db_version_default(self):
        node = _make_node()
        result = OracleBulkExecConverter().convert(node, [], {})
        assert result.component["config"]["db_version"] == "ORACLE_18"

    # ---- Core connection ----
    def test_host_default(self):
        node = _make_node()
        result = OracleBulkExecConverter().convert(node, [], {})
        assert result.component["config"]["host"] == ""

    def test_port_default(self):
        node = _make_node()
        result = OracleBulkExecConverter().convert(node, [], {})
        assert result.component["config"]["port"] == "1521"

    def test_dbname_default(self):
        node = _make_node()
        result = OracleBulkExecConverter().convert(node, [], {})
        assert result.component["config"]["dbname"] == ""

    def test_local_service_name_default(self):
        node = _make_node()
        result = OracleBulkExecConverter().convert(node, [], {})
        assert result.component["config"]["local_service_name"] == ""

    def test_schema_db_default(self):
        node = _make_node()
        result = OracleBulkExecConverter().convert(node, [], {})
        assert result.component["config"]["schema_db"] == ""

    def test_user_default(self):
        node = _make_node()
        result = OracleBulkExecConverter().convert(node, [], {})
        assert result.component["config"]["user"] == ""

    def test_password_default(self):
        """Password extracted from PASS XML param, config key is 'password'."""
        node = _make_node()
        result = OracleBulkExecConverter().convert(node, [], {})
        assert result.component["config"]["password"] == ""

    # ---- Target ----
    def test_table_default(self):
        node = _make_node()
        result = OracleBulkExecConverter().convert(node, [], {})
        assert result.component["config"]["table"] == ""

    def test_table_action_default(self):
        node = _make_node()
        result = OracleBulkExecConverter().convert(node, [], {})
        assert result.component["config"]["table_action"] == "NONE"

    def test_data_default(self):
        node = _make_node()
        result = OracleBulkExecConverter().convert(node, [], {})
        assert result.component["config"]["data"] == ""

    def test_data_action_default(self):
        node = _make_node()
        result = OracleBulkExecConverter().convert(node, [], {})
        assert result.component["config"]["data_action"] == "INSERT"

    # ---- Separators ----
    def test_properties_default(self):
        node = _make_node()
        result = OracleBulkExecConverter().convert(node, [], {})
        assert result.component["config"]["properties"] == ""

    def test_advanced_separator_default(self):
        node = _make_node()
        result = OracleBulkExecConverter().convert(node, [], {})
        assert result.component["config"]["advanced_separator"] is False

    def test_thousands_separator_default(self):
        node = _make_node()
        result = OracleBulkExecConverter().convert(node, [], {})
        assert result.component["config"]["thousands_separator"] == ","

    def test_decimal_separator_default(self):
        node = _make_node()
        result = OracleBulkExecConverter().convert(node, [], {})
        assert result.component["config"]["decimal_separator"] == "."

    # ---- Control file ----
    def test_use_existing_clt_file_default(self):
        node = _make_node()
        result = OracleBulkExecConverter().convert(node, [], {})
        assert result.component["config"]["use_existing_clt_file"] is False

    def test_clt_file_default(self):
        node = _make_node()
        result = OracleBulkExecConverter().convert(node, [], {})
        assert result.component["config"]["clt_file"] == ""

    # ---- Record format ----
    def test_record_format_default(self):
        node = _make_node()
        result = OracleBulkExecConverter().convert(node, [], {})
        assert result.component["config"]["record_format"] == "DEFAULT"

    def test_input_into_table_clause_default(self):
        node = _make_node()
        result = OracleBulkExecConverter().convert(node, [], {})
        assert result.component["config"]["input_into_table_clause"] is False

    def test_fields_terminator_default(self):
        node = _make_node()
        result = OracleBulkExecConverter().convert(node, [], {})
        assert result.component["config"]["fields_terminator"] == "OTHER"

    def test_terminator_value_default(self):
        node = _make_node()
        result = OracleBulkExecConverter().convert(node, [], {})
        assert result.component["config"]["terminator_value"] == ";"

    def test_use_fields_enclosure_default(self):
        node = _make_node()
        result = OracleBulkExecConverter().convert(node, [], {})
        assert result.component["config"]["use_fields_enclosure"] is False

    def test_use_date_pattern_default(self):
        node = _make_node()
        result = OracleBulkExecConverter().convert(node, [], {})
        assert result.component["config"]["use_date_pattern"] is False

    def test_preserve_blanks_default(self):
        node = _make_node()
        result = OracleBulkExecConverter().convert(node, [], {})
        assert result.component["config"]["preserve_blanks"] is False

    def test_trailing_nullcols_default(self):
        node = _make_node()
        result = OracleBulkExecConverter().convert(node, [], {})
        assert result.component["config"]["trailing_nullcols"] is False

    # ---- Options TABLE ----
    def test_options_default(self):
        node = _make_node()
        result = OracleBulkExecConverter().convert(node, [], {})
        assert result.component["config"]["options"] == []

    # ---- NLS ----
    def test_nls_language_default(self):
        node = _make_node()
        result = OracleBulkExecConverter().convert(node, [], {})
        assert result.component["config"]["nls_language"] == "DEFAULT"

    def test_nls_date_language_default(self):
        node = _make_node()
        result = OracleBulkExecConverter().convert(node, [], {})
        assert result.component["config"]["nls_date_language"] == "DEFAULT"

    def test_set_nls_territory_default(self):
        """SET_NLS_TERRITORY uniquely defaults to True (not False like most CHECK params)."""
        node = _make_node()
        result = OracleBulkExecConverter().convert(node, [], {})
        assert result.component["config"]["set_nls_territory"] is True

    def test_nls_territory_default(self):
        node = _make_node()
        result = OracleBulkExecConverter().convert(node, [], {})
        assert result.component["config"]["nls_territory"] == "DEFAULT"

    # ---- Other advanced ----
    def test_encoding_default(self):
        """Encoding defaults to UTF8 -- unique among Oracle components (others use ISO-8859-15)."""
        node = _make_node()
        result = OracleBulkExecConverter().convert(node, [], {})
        assert result.component["config"]["encoding"] == "UTF8"

    def test_output_default(self):
        node = _make_node()
        result = OracleBulkExecConverter().convert(node, [], {})
        assert result.component["config"]["output"] == "OUTPUT_TO_CONSOLE"

    def test_convert_column_table_to_uppercase_default(self):
        node = _make_node()
        result = OracleBulkExecConverter().convert(node, [], {})
        assert result.component["config"]["convert_column_table_to_uppercase"] is False

    def test_support_nls_default(self):
        node = _make_node()
        result = OracleBulkExecConverter().convert(node, [], {})
        assert result.component["config"]["support_nls"] is False


class TestParameterExtraction:
    """Verify each parameter is correctly extracted from XML params."""

    def test_table_extracted(self):
        node = _make_node(params={"TABLE": '"staging_orders"'})
        result = OracleBulkExecConverter().convert(node, [], {})
        assert result.component["config"]["table"] == "staging_orders"

    def test_data_file_extracted(self):
        node = _make_node(params={"DATA": '"/data/export/orders.csv"'})
        result = OracleBulkExecConverter().convert(node, [], {})
        assert result.component["config"]["data"] == "/data/export/orders.csv"

    def test_encoding_custom(self):
        """Custom encoding value extracted correctly."""
        node = _make_node(params={"ENCODING": '"ISO-8859-15"'})
        result = OracleBulkExecConverter().convert(node, [], {})
        assert result.component["config"]["encoding"] == "ISO-8859-15"

    def test_record_format_custom(self):
        node = _make_node(params={"RECORD_FORMAT": '"STREAM"'})
        result = OracleBulkExecConverter().convert(node, [], {})
        assert result.component["config"]["record_format"] == "STREAM"

    def test_connection_type_service_name(self):
        node = _make_node(params={"CONNECTION_TYPE": '"ORACLE_SERVICE_NAME"'})
        result = OracleBulkExecConverter().convert(node, [], {})
        assert result.component["config"]["connection_type"] == "ORACLE_SERVICE_NAME"

    def test_host_extracted(self):
        node = _make_node(params={"HOST": '"db.prod.example.com"'})
        result = OracleBulkExecConverter().convert(node, [], {})
        assert result.component["config"]["host"] == "db.prod.example.com"

    def test_password_extracted_from_pass(self):
        """Password is extracted from XML param PASS (not PASSWORD)."""
        node = _make_node(params={"PASS": '"s3cret!pwd"'})
        result = OracleBulkExecConverter().convert(node, [], {})
        assert result.component["config"]["password"] == "s3cret!pwd"

    def test_table_action_truncate(self):
        node = _make_node(params={"TABLE_ACTION": '"TRUNCATE"'})
        result = OracleBulkExecConverter().convert(node, [], {})
        assert result.component["config"]["table_action"] == "TRUNCATE"

    def test_data_action_append(self):
        node = _make_node(params={"DATA_ACTION": '"APPEND"'})
        result = OracleBulkExecConverter().convert(node, [], {})
        assert result.component["config"]["data_action"] == "APPEND"

    def test_use_existing_connection_true(self):
        node = _make_node(params={"USE_EXISTING_CONNECTION": "true"})
        result = OracleBulkExecConverter().convert(node, [], {})
        assert result.component["config"]["use_existing_connection"] is True

    def test_connection_extracted(self):
        node = _make_node(params={"CONNECTION": '"tOracleConnection_1"'})
        result = OracleBulkExecConverter().convert(node, [], {})
        assert result.component["config"]["connection"] == "tOracleConnection_1"

    def test_clt_file_extracted(self):
        node = _make_node(params={"CLT_FILE": '"/opt/oracle/custom.ctl"'})
        result = OracleBulkExecConverter().convert(node, [], {})
        assert result.component["config"]["clt_file"] == "/opt/oracle/custom.ctl"

    def test_set_nls_territory_false(self):
        """SET_NLS_TERRITORY can be explicitly set to false."""
        node = _make_node(params={"SET_NLS_TERRITORY": "false"})
        result = OracleBulkExecConverter().convert(node, [], {})
        assert result.component["config"]["set_nls_territory"] is False

    def test_trailing_nullcols_true(self):
        node = _make_node(params={"TRAILING_NULLCOLS": "true"})
        result = OracleBulkExecConverter().convert(node, [], {})
        assert result.component["config"]["trailing_nullcols"] is True

    def test_fields_terminator_comma(self):
        node = _make_node(params={"FIELDS_TERMINATOR": '"COMMA"'})
        result = OracleBulkExecConverter().convert(node, [], {})
        assert result.component["config"]["fields_terminator"] == "COMMA"

    def test_output_to_file(self):
        node = _make_node(params={"OUTPUT": '"OUTPUT_TO_FILE"'})
        result = OracleBulkExecConverter().convert(node, [], {})
        assert result.component["config"]["output"] == "OUTPUT_TO_FILE"

    def test_port_extracted(self):
        """Port is extracted as string (TEXT type in _java.xml)."""
        node = _make_node(params={"PORT": '"1522"'})
        result = OracleBulkExecConverter().convert(node, [], {})
        assert result.component["config"]["port"] == "1522"


class TestOptionsTable:
    """Verify OPTIONS TABLE parameter parsing."""

    def test_empty_options(self):
        """Missing OPTIONS returns empty list."""
        node = _make_node()
        result = OracleBulkExecConverter().convert(node, [], {})
        assert result.component["config"]["options"] == []

    def test_options_parsed(self):
        """OPTIONS TABLE rows are parsed correctly."""
        options_data = _make_options_table(['"ROWS=10000"', '"DIRECT=TRUE"'])
        node = _make_node(params={"OPTIONS": options_data})
        result = OracleBulkExecConverter().convert(node, [], {})
        assert len(result.component["config"]["options"]) == 2
        assert result.component["config"]["options"][0] == "ROWS=10000"
        assert result.component["config"]["options"][1] == "DIRECT=TRUE"

    def test_options_none(self):
        """OPTIONS set to None returns empty list."""
        node = _make_node(params={"OPTIONS": None})
        result = OracleBulkExecConverter().convert(node, [], {})
        assert result.component["config"]["options"] == []

    def test_options_empty_list(self):
        """OPTIONS set to empty list returns empty list."""
        node = _make_node(params={"OPTIONS": []})
        result = OracleBulkExecConverter().convert(node, [], {})
        assert result.component["config"]["options"] == []


class TestFrameworkParams:
    """Verify tstatcatcher_stats and label extraction."""

    def test_tstatcatcher_stats_default_false(self):
        node = _make_node()
        result = OracleBulkExecConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is False

    def test_tstatcatcher_stats_true(self):
        node = _make_node(params={"TSTATCATCHER_STATS": "true"})
        result = OracleBulkExecConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is True

    def test_label_default_empty(self):
        node = _make_node()
        result = OracleBulkExecConverter().convert(node, [], {})
        assert result.component["config"]["label"] == ""

    def test_label_extracted(self):
        node = _make_node(params={"LABEL": '"bulk_load_step"'})
        result = OracleBulkExecConverter().convert(node, [], {})
        assert result.component["config"]["label"] == "bulk_load_step"


class TestSchema:
    """Verify schema extraction with sink pattern (input has schema, output is empty)."""

    def test_schema_is_dict_with_input_output(self):
        """Schema is a dict with 'input' and 'output' keys (sink pattern)."""
        result = OracleBulkExecConverter().convert(_make_node(), [], {})
        schema = result.component["schema"]
        assert isinstance(schema, dict)
        assert "input" in schema
        assert "output" in schema

    def test_schema_output_always_empty(self):
        """Sink components have empty output schema (data flows IN)."""
        node = _make_node(schema=_make_schema_columns())
        result = OracleBulkExecConverter().convert(node, [], {})
        assert result.component["schema"]["output"] == []

    def test_schema_input_extracted(self):
        """FLOW schema columns are parsed into the input schema."""
        node = _make_node(schema=_make_schema_columns())
        result = OracleBulkExecConverter().convert(node, [], {})
        schema_input = result.component["schema"]["input"]
        assert len(schema_input) == 3
        assert schema_input[0]["name"] == "id"
        assert schema_input[1]["name"] == "name"
        assert schema_input[2]["name"] == "amount"

    def test_empty_schema_when_no_flow(self):
        """No FLOW schema produces empty input and output lists."""
        result = OracleBulkExecConverter().convert(_make_node(), [], {})
        assert result.component["schema"]["input"] == []
        assert result.component["schema"]["output"] == []


class TestNeedsReview:
    """Verify needs_review entries for engine gaps."""

    def test_needs_review_count(self):
        """Single consolidated needs_review entry per D-27 (no engine)."""
        node = _make_node()
        result = OracleBulkExecConverter().convert(node, [], {})
        assert len(result.needs_review) == 1

    def test_needs_review_severity(self):
        node = _make_node()
        result = OracleBulkExecConverter().convert(node, [], {})
        for entry in result.needs_review:
            assert entry["severity"] == "engine_gap"

    def test_needs_review_has_component_id(self):
        node = _make_node(component_id="bulk_exec_test")
        result = OracleBulkExecConverter().convert(node, [], {})
        for entry in result.needs_review:
            assert entry["component"] == "bulk_exec_test"

    def test_no_framework_param_needs_review(self):
        """Framework params (tstatcatcher_stats, label) must NOT have needs_review."""
        node = _make_node()
        result = OracleBulkExecConverter().convert(node, [], {})
        issues = [e["issue"] for e in result.needs_review]
        for issue in issues:
            assert "tstatcatcher_stats" not in issue
            assert "label" not in issue.lower().split()


class TestCompleteness:
    """Verify all expected config keys are present."""

    def test_all_config_keys_present(self):
        node = _make_node(schema=_make_schema_columns())
        result = OracleBulkExecConverter().convert(node, [], {})
        expected_keys = {
            # Connection mode
            "use_existing_connection", "connection",
            # Connection type
            "connection_type", "db_version",
            # Core connection
            "host", "port", "dbname", "local_service_name", "schema_db",
            "user", "password",
            # Target
            "table", "table_action", "data", "data_action",
            # Separators
            "properties", "advanced_separator", "thousands_separator", "decimal_separator",
            # Control file
            "use_existing_clt_file", "clt_file",
            # Record format
            "record_format", "input_into_table_clause", "fields_terminator",
            "terminator_value", "use_fields_enclosure", "use_date_pattern",
            "preserve_blanks", "trailing_nullcols",
            # Options
            "options",
            # NLS
            "nls_language", "nls_date_language", "set_nls_territory", "nls_territory",
            # Other advanced
            "encoding", "output", "convert_column_table_to_uppercase", "support_nls",
            # Framework (ALWAYS LAST)
            "tstatcatcher_stats", "label",
        }
        actual_keys = set(result.component["config"].keys())
        missing = expected_keys - actual_keys
        assert not missing, f"Missing config keys: {missing}"

    def test_top_level_keys(self):
        """Standard component dict has all required top-level keys."""
        result = OracleBulkExecConverter().convert(_make_node(), [], {})
        expected_top = {"id", "type", "original_type", "position", "config", "schema", "inputs", "outputs"}
        actual_top = set(result.component.keys())
        missing = expected_top - actual_top
        assert not missing, f"Missing top-level keys: {missing}"


class TestPhantomParams:
    """Verify params NOT in _java.xml are NOT extracted."""

    def test_die_on_error_not_in_output(self):
        """DIE_ON_ERROR is a phantom param (not in _java.xml) -- must NOT appear in config."""
        node = _make_node(params={"DIE_ON_ERROR": "true"})
        result = OracleBulkExecConverter().convert(node, [], {})
        assert "die_on_error" not in result.component["config"]
        assert "DIE_ON_ERROR" not in result.component["config"]

    def test_die_on_error_not_in_empty_config(self):
        """DIE_ON_ERROR must NOT appear even with empty params."""
        node = _make_node()
        result = OracleBulkExecConverter().convert(node, [], {})
        assert "die_on_error" not in result.component["config"]
        assert "DIE_ON_ERROR" not in result.component["config"]
