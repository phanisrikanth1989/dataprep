"""Tests for OracleOutputConverter (tOracleOutput -> no engine)."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendNode,
)
from src.converters.talend_to_v1.components.database.oracle_output import (
    OracleOutputConverter,
)
from src.converters.talend_to_v1.components.registry import REGISTRY


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

def _make_node(params=None, schema=None, component_id="tOracleOutput_1",
               component_type="tOracleOutput"):
    """Create a TalendNode for testing."""
    return TalendNode(
        component_id=component_id,
        component_type=component_type,
        params=params or {},
        schema=schema or {},
        position={"x": 480, "y": 240},
        raw_xml=ET.Element("node"),
    )


def _make_schema_columns():
    """Return a sample FLOW schema for testing."""
    return {
        "FLOW": [
            SchemaColumn(name="emp_id", type="id_Integer", nullable=False, key=True, length=10),
            SchemaColumn(name="emp_name", type="id_String", nullable=True, length=200),
            SchemaColumn(name="hire_date", type="id_Date", date_pattern="yyyy-MM-dd"),
        ]
    }


# ------------------------------------------------------------------
# TestRegistration
# ------------------------------------------------------------------

class TestRegistration:
    """Verify component is registered correctly."""

    def test_registered_in_registry(self):
        assert REGISTRY.get("tOracleOutput") is OracleOutputConverter


# ------------------------------------------------------------------
# TestStructure
# ------------------------------------------------------------------

class TestStructure:
    """Verify standard component dict structure from _build_component_dict."""

    def test_id_at_top_level(self):
        """Component dict has 'id' at top level."""
        node = _make_node()
        result = OracleOutputConverter().convert(node, [], {})
        assert result.component["id"] == "tOracleOutput_1"

    def test_type_at_top_level(self):
        """Component dict has 'type' at top level."""
        node = _make_node()
        result = OracleOutputConverter().convert(node, [], {})
        assert result.component["type"] == "tOracleOutput"

    def test_original_type_at_top_level(self):
        """Component dict has 'original_type' at top level."""
        node = _make_node()
        result = OracleOutputConverter().convert(node, [], {})
        assert result.component["original_type"] == "tOracleOutput"

    def test_config_is_nested_dict(self):
        """Config params are nested under 'config' key."""
        node = _make_node()
        result = OracleOutputConverter().convert(node, [], {})
        assert isinstance(result.component["config"], dict)

    def test_position_at_top_level(self):
        """Component dict has 'position' at top level."""
        node = _make_node()
        result = OracleOutputConverter().convert(node, [], {})
        assert result.component["position"] == {"x": 480, "y": 240}

    def test_inputs_outputs_at_top_level(self):
        """Component dict has 'inputs' and 'outputs' at top level."""
        node = _make_node()
        result = OracleOutputConverter().convert(node, [], {})
        assert result.component["inputs"] == []
        assert result.component["outputs"] == []


# ------------------------------------------------------------------
# TestDefaults
# ------------------------------------------------------------------

class TestDefaults:
    """Verify all parameters have correct defaults when no params provided."""

    def test_use_existing_connection_default(self):
        """USE_EXISTING_CONNECTION defaults to False."""
        node = _make_node()
        result = OracleOutputConverter().convert(node, [], {})
        assert result.component["config"]["use_existing_connection"] is False

    def test_connection_default(self):
        """CONNECTION defaults to empty string."""
        node = _make_node()
        result = OracleOutputConverter().convert(node, [], {})
        assert result.component["config"]["connection"] == ""

    def test_connection_type_default(self):
        """CONNECTION_TYPE defaults to ORACLE_SID."""
        node = _make_node()
        result = OracleOutputConverter().convert(node, [], {})
        assert result.component["config"]["connection_type"] == "ORACLE_SID"

    def test_db_version_default(self):
        """DB_VERSION defaults to ORACLE_18."""
        node = _make_node()
        result = OracleOutputConverter().convert(node, [], {})
        assert result.component["config"]["db_version"] == "ORACLE_18"

    def test_host_default(self):
        """HOST defaults to empty string."""
        node = _make_node()
        result = OracleOutputConverter().convert(node, [], {})
        assert result.component["config"]["host"] == ""

    def test_port_default(self):
        """PORT defaults to 1521."""
        node = _make_node()
        result = OracleOutputConverter().convert(node, [], {})
        assert result.component["config"]["port"] == "1521"

    def test_dbname_default(self):
        """DBNAME defaults to empty string."""
        node = _make_node()
        result = OracleOutputConverter().convert(node, [], {})
        assert result.component["config"]["dbname"] == ""

    def test_table_schema_default(self):
        """TABLESCHEMA defaults to empty string. Config key is schema_db (CR-01)."""
        node = _make_node()
        result = OracleOutputConverter().convert(node, [], {})
        assert result.component["config"]["schema_db"] == ""

    def test_user_default(self):
        """USER defaults to empty string."""
        node = _make_node()
        result = OracleOutputConverter().convert(node, [], {})
        assert result.component["config"]["user"] == ""

    def test_password_default(self):
        """PASS (not PASSWORD) defaults to empty string. Config key is password."""
        node = _make_node()
        result = OracleOutputConverter().convert(node, [], {})
        assert result.component["config"]["password"] == ""

    def test_table_default(self):
        """TABLE defaults to empty string."""
        node = _make_node()
        result = OracleOutputConverter().convert(node, [], {})
        assert result.component["config"]["table"] == ""

    def test_table_action_default(self):
        """TABLE_ACTION defaults to NONE."""
        node = _make_node()
        result = OracleOutputConverter().convert(node, [], {})
        assert result.component["config"]["table_action"] == "NONE"

    def test_data_action_default(self):
        """DATA_ACTION defaults to INSERT."""
        node = _make_node()
        result = OracleOutputConverter().convert(node, [], {})
        assert result.component["config"]["data_action"] == "INSERT"

    def test_commit_every_default(self):
        """COMMIT_EVERY defaults to 10000."""
        node = _make_node()
        result = OracleOutputConverter().convert(node, [], {})
        assert result.component["config"]["commit_every"] == 10000

    def test_use_batch_size_default(self):
        """USE_BATCH_SIZE defaults to True (not False like most CHECK params)."""
        node = _make_node()
        result = OracleOutputConverter().convert(node, [], {})
        assert result.component["config"]["use_batch_size"] is True

    def test_batch_size_default(self):
        """BATCH_SIZE defaults to 10000."""
        node = _make_node()
        result = OracleOutputConverter().convert(node, [], {})
        assert result.component["config"]["batch_size"] == 10000

    def test_use_field_options_default(self):
        """USE_FIELD_OPTIONS defaults to False."""
        node = _make_node()
        result = OracleOutputConverter().convert(node, [], {})
        assert result.component["config"]["use_field_options"] is False

    def test_use_hint_options_default(self):
        """USE_HINT_OPTIONS defaults to False."""
        node = _make_node()
        result = OracleOutputConverter().convert(node, [], {})
        assert result.component["config"]["use_hint_options"] is False

    def test_die_on_error_default(self):
        """DIE_ON_ERROR defaults to False."""
        node = _make_node()
        result = OracleOutputConverter().convert(node, [], {})
        assert result.component["config"]["die_on_error"] is False

    def test_enable_debug_mode_default(self):
        """ENABLE_DEBUG_MODE defaults to False."""
        node = _make_node()
        result = OracleOutputConverter().convert(node, [], {})
        assert result.component["config"]["enable_debug_mode"] is False

    def test_convert_column_table_to_uppercase_default(self):
        """CONVERT_COLUMN_TABLE_TO_UPPERCASE defaults to False."""
        node = _make_node()
        result = OracleOutputConverter().convert(node, [], {})
        assert result.component["config"]["convert_column_table_to_uppercase"] is False

    def test_use_timestamp_for_date_type_default(self):
        """USE_TIMESTAMP_FOR_DATE_TYPE defaults to True (not False)."""
        node = _make_node()
        result = OracleOutputConverter().convert(node, [], {})
        assert result.component["config"]["use_timestamp_for_date_type"] is True

    def test_trim_char_default(self):
        """TRIM_CHAR defaults to True (not False)."""
        node = _make_node()
        result = OracleOutputConverter().convert(node, [], {})
        assert result.component["config"]["trim_char"] is True

    def test_support_nls_default(self):
        """SUPPORT_NLS defaults to False."""
        node = _make_node()
        result = OracleOutputConverter().convert(node, [], {})
        assert result.component["config"]["support_nls"] is False


# ------------------------------------------------------------------
# TestParameterExtraction
# ------------------------------------------------------------------

class TestParameterExtraction:
    """Verify each parameter is correctly extracted from XML params."""

    def test_connection_type_extracted(self):
        """CONNECTION_TYPE CLOSED_LIST value extracted."""
        node = _make_node(params={"CONNECTION_TYPE": '"ORACLE_SERVICE_NAME"'})
        result = OracleOutputConverter().convert(node, [], {})
        assert result.component["config"]["connection_type"] == "ORACLE_SERVICE_NAME"

    def test_db_version_extracted(self):
        """DB_VERSION CLOSED_LIST value extracted."""
        node = _make_node(params={"DB_VERSION": '"ORACLE_12"'})
        result = OracleOutputConverter().convert(node, [], {})
        assert result.component["config"]["db_version"] == "ORACLE_12"

    def test_host_extracted(self):
        """HOST text value extracted with quote stripping."""
        node = _make_node(params={"HOST": '"db.example.com"'})
        result = OracleOutputConverter().convert(node, [], {})
        assert result.component["config"]["host"] == "db.example.com"

    def test_port_extracted(self):
        """PORT text value extracted."""
        node = _make_node(params={"PORT": '"1522"'})
        result = OracleOutputConverter().convert(node, [], {})
        assert result.component["config"]["port"] == "1522"

    def test_table_schema_extracted(self):
        """TABLESCHEMA extracted to canonical schema_db config key (CR-01)."""
        node = _make_node(params={"TABLESCHEMA": '"HR"'})
        result = OracleOutputConverter().convert(node, [], {})
        assert result.component["config"]["schema_db"] == "HR"

    def test_password_extracted_from_pass(self):
        """PASS (not PASSWORD) is the correct XML extraction name."""
        node = _make_node(params={"PASS": '"secret123"'})
        result = OracleOutputConverter().convert(node, [], {})
        assert result.component["config"]["password"] == "secret123"

    def test_table_action_create(self):
        """TABLE_ACTION=CREATE extracted."""
        node = _make_node(params={"TABLE_ACTION": '"CREATE"'})
        result = OracleOutputConverter().convert(node, [], {})
        assert result.component["config"]["table_action"] == "CREATE"

    def test_table_action_drop_create(self):
        """TABLE_ACTION=DROP_CREATE extracted."""
        node = _make_node(params={"TABLE_ACTION": '"DROP_CREATE"'})
        result = OracleOutputConverter().convert(node, [], {})
        assert result.component["config"]["table_action"] == "DROP_CREATE"

    def test_data_action_update(self):
        """DATA_ACTION=UPDATE extracted."""
        node = _make_node(params={"DATA_ACTION": '"UPDATE"'})
        result = OracleOutputConverter().convert(node, [], {})
        assert result.component["config"]["data_action"] == "UPDATE"

    def test_data_action_insert_or_update(self):
        """DATA_ACTION=INSERT_OR_UPDATE extracted."""
        node = _make_node(params={"DATA_ACTION": '"INSERT_OR_UPDATE"'})
        result = OracleOutputConverter().convert(node, [], {})
        assert result.component["config"]["data_action"] == "INSERT_OR_UPDATE"

    def test_data_action_delete(self):
        """DATA_ACTION=DELETE extracted."""
        node = _make_node(params={"DATA_ACTION": '"DELETE"'})
        result = OracleOutputConverter().convert(node, [], {})
        assert result.component["config"]["data_action"] == "DELETE"

    def test_commit_every_extracted(self):
        """COMMIT_EVERY integer value extracted."""
        node = _make_node(params={"COMMIT_EVERY": '"5000"'})
        result = OracleOutputConverter().convert(node, [], {})
        assert result.component["config"]["commit_every"] == 5000

    def test_batch_size_extracted(self):
        """BATCH_SIZE integer value extracted."""
        node = _make_node(params={"BATCH_SIZE": '"2000"'})
        result = OracleOutputConverter().convert(node, [], {})
        assert result.component["config"]["batch_size"] == 2000

    def test_use_batch_size_false(self):
        """USE_BATCH_SIZE can be set to false."""
        node = _make_node(params={"USE_BATCH_SIZE": "false"})
        result = OracleOutputConverter().convert(node, [], {})
        assert result.component["config"]["use_batch_size"] is False

    def test_die_on_error_true(self):
        """DIE_ON_ERROR can be set to true."""
        node = _make_node(params={"DIE_ON_ERROR": "true"})
        result = OracleOutputConverter().convert(node, [], {})
        assert result.component["config"]["die_on_error"] is True

    def test_use_existing_connection_true(self):
        """USE_EXISTING_CONNECTION can be set to true with CONNECTION reference."""
        node = _make_node(params={
            "USE_EXISTING_CONNECTION": "true",
            "CONNECTION": '"tOracleConnection_1"',
        })
        result = OracleOutputConverter().convert(node, [], {})
        assert result.component["config"]["use_existing_connection"] is True
        assert result.component["config"]["connection"] == "tOracleConnection_1"

    def test_use_timestamp_for_date_type_false(self):
        """USE_TIMESTAMP_FOR_DATE_TYPE can be set to false."""
        node = _make_node(params={"USE_TIMESTAMP_FOR_DATE_TYPE": "false"})
        result = OracleOutputConverter().convert(node, [], {})
        assert result.component["config"]["use_timestamp_for_date_type"] is False

    def test_trim_char_false(self):
        """TRIM_CHAR can be set to false."""
        node = _make_node(params={"TRIM_CHAR": "false"})
        result = OracleOutputConverter().convert(node, [], {})
        assert result.component["config"]["trim_char"] is False

    def test_support_nls_true(self):
        """SUPPORT_NLS can be set to true."""
        node = _make_node(params={"SUPPORT_NLS": "true"})
        result = OracleOutputConverter().convert(node, [], {})
        assert result.component["config"]["support_nls"] is True

    def test_enable_debug_mode_true(self):
        """ENABLE_DEBUG_MODE can be set to true."""
        node = _make_node(params={"ENABLE_DEBUG_MODE": "true"})
        result = OracleOutputConverter().convert(node, [], {})
        assert result.component["config"]["enable_debug_mode"] is True

    def test_convert_column_table_to_uppercase_true(self):
        """CONVERT_COLUMN_TABLE_TO_UPPERCASE can be set to true."""
        node = _make_node(params={"CONVERT_COLUMN_TABLE_TO_UPPERCASE": "true"})
        result = OracleOutputConverter().convert(node, [], {})
        assert result.component["config"]["convert_column_table_to_uppercase"] is True


# ------------------------------------------------------------------
# TestFrameworkParams
# ------------------------------------------------------------------

class TestFrameworkParams:
    """Verify tstatcatcher_stats and label extraction."""

    def test_tstatcatcher_stats_default_false(self):
        """TSTATCATCHER_STATS defaults to False."""
        node = _make_node()
        result = OracleOutputConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is False

    def test_tstatcatcher_stats_true(self):
        """TSTATCATCHER_STATS can be set to true."""
        node = _make_node(params={"TSTATCATCHER_STATS": "true"})
        result = OracleOutputConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is True

    def test_label_default_empty(self):
        """LABEL defaults to empty string."""
        node = _make_node()
        result = OracleOutputConverter().convert(node, [], {})
        assert result.component["config"]["label"] == ""

    def test_label_extracted(self):
        """LABEL value extracted with quote stripping."""
        node = _make_node(params={"LABEL": '"oracle_writer"'})
        result = OracleOutputConverter().convert(node, [], {})
        assert result.component["config"]["label"] == "oracle_writer"


# ------------------------------------------------------------------
# TestSchema
# ------------------------------------------------------------------

class TestSchema:
    """Verify schema extraction with sink pattern (input has schema, output is empty)."""

    def test_schema_is_dict_with_input_output(self):
        """Schema is a dict with 'input' and 'output' keys (sink pattern)."""
        node = _make_node()
        result = OracleOutputConverter().convert(node, [], {})
        schema = result.component["schema"]
        assert isinstance(schema, dict)
        assert "input" in schema
        assert "output" in schema

    def test_schema_output_always_empty(self):
        """Sink components have empty output schema (data flows IN)."""
        node = _make_node(schema=_make_schema_columns())
        result = OracleOutputConverter().convert(node, [], {})
        assert result.component["schema"]["output"] == []

    def test_schema_input_extracted(self):
        """FLOW schema columns are parsed into the input schema."""
        node = _make_node(schema=_make_schema_columns())
        result = OracleOutputConverter().convert(node, [], {})
        schema_input = result.component["schema"]["input"]
        assert len(schema_input) == 3
        assert schema_input[0]["name"] == "emp_id"
        assert schema_input[0]["key"] is True
        assert schema_input[0]["nullable"] is False
        assert schema_input[1]["name"] == "emp_name"
        assert schema_input[1]["length"] == 200
        assert schema_input[2]["name"] == "hire_date"
        assert schema_input[2]["date_pattern"] == "%Y-%m-%d"

    def test_schema_empty_when_no_flow(self):
        """Schema is empty for both input and output when no FLOW connector defined."""
        node = _make_node()
        result = OracleOutputConverter().convert(node, [], {})
        assert result.component["schema"]["input"] == []
        assert result.component["schema"]["output"] == []


# ------------------------------------------------------------------
# TestNeedsReview
# ------------------------------------------------------------------

class TestNeedsReview:
    """D-E1: Wallet/OCI emit a thick-mode needs_review; SID/SERVICE_NAME/RAC
    emit zero needs_review entries (Phase 11 ships those connection types)."""

    def test_no_needs_review_for_sid(self):
        """ORACLE_SID emits zero needs_review entries (engine ships it)."""
        node = _make_node(params={"CONNECTION_TYPE": '"ORACLE_SID"'})
        result = OracleOutputConverter().convert(node, [], {})
        assert len(result.needs_review) == 0

    def test_no_needs_review_for_service_name(self):
        """ORACLE_SERVICE_NAME emits zero needs_review entries."""
        node = _make_node(params={"CONNECTION_TYPE": '"ORACLE_SERVICE_NAME"'})
        result = OracleOutputConverter().convert(node, [], {})
        assert len(result.needs_review) == 0

    def test_no_needs_review_for_rac(self):
        """ORACLE_RAC emits zero needs_review entries."""
        node = _make_node(params={"CONNECTION_TYPE": '"ORACLE_RAC"'})
        result = OracleOutputConverter().convert(node, [], {})
        assert len(result.needs_review) == 0

    def test_needs_review_for_wallet(self):
        """ORACLE_WALLET emits a thick-mode needs_review entry (D-E1)."""
        node = _make_node(
            params={"CONNECTION_TYPE": '"ORACLE_WALLET"'},
            component_id="tOracleOutput_5",
        )
        result = OracleOutputConverter().convert(node, [], {})
        assert len(result.needs_review) == 1
        entry = result.needs_review[0]
        assert entry["severity"] == "needs_review"
        assert entry["component"] == "tOracleOutput_5"
        assert "thick_mode" in entry["issue"]
        assert "Instant Client" in entry["issue"]
        assert "ORACLE_WALLET" in entry["issue"]

    def test_needs_review_for_oci(self):
        """ORACLE_OCI emits a thick-mode needs_review entry (D-E1)."""
        node = _make_node(params={"CONNECTION_TYPE": '"ORACLE_OCI"'})
        result = OracleOutputConverter().convert(node, [], {})
        assert len(result.needs_review) == 1
        entry = result.needs_review[0]
        assert entry["severity"] == "needs_review"
        assert "thick_mode" in entry["issue"]
        assert "Instant Client" in entry["issue"]
        assert "ORACLE_OCI" in entry["issue"]

    def test_needs_review_message_no_secrets(self):
        """T-11-05 mitigation: needs_review message contains no auth detail."""
        node = _make_node(params={
            "CONNECTION_TYPE": '"ORACLE_WALLET"',
            "USER": '"scott"',
            "PASS": '"tiger"',
        })
        result = OracleOutputConverter().convert(node, [], {})
        issue = result.needs_review[0]["issue"]
        assert "scott" not in issue
        assert "tiger" not in issue


# ------------------------------------------------------------------
# TestCompleteness
# ------------------------------------------------------------------

class TestCompleteness:
    """Verify all expected config keys are present."""

    def test_all_config_keys_present(self):
        """All 26 config keys present in snake_case (24 unique + 2 framework)."""
        node = _make_node(schema=_make_schema_columns())
        result = OracleOutputConverter().convert(node, [], {})
        expected_keys = {
            # Basic settings
            "use_existing_connection",
            "connection",
            "connection_type",
            "db_version",
            "host",
            "port",
            "dbname",
            "schema_db",
            "user",
            "password",
            "table",
            "table_action",
            "data_action",
            # Advanced settings
            "commit_every",
            "use_batch_size",
            "batch_size",
            "use_field_options",
            "use_hint_options",
            "die_on_error",
            "enable_debug_mode",
            "convert_column_table_to_uppercase",
            "use_timestamp_for_date_type",
            "trim_char",
            "support_nls",
            # Framework
            "tstatcatcher_stats",
            "label",
        }
        actual_keys = set(result.component["config"].keys())
        missing = expected_keys - actual_keys
        assert not missing, f"Missing config keys: {missing}"

    def test_top_level_keys(self):
        """Standard component dict has all required top-level keys."""
        node = _make_node()
        result = OracleOutputConverter().convert(node, [], {})
        expected_top = {"id", "type", "original_type", "position", "config", "schema", "inputs", "outputs"}
        actual_top = set(result.component.keys())
        missing = expected_top - actual_top
        assert not missing, f"Missing top-level keys: {missing}"

    def test_no_uppercase_config_keys(self):
        """All config keys must be snake_case, not UPPERCASE."""
        node = _make_node()
        result = OracleOutputConverter().convert(node, [], {})
        for key in result.component["config"].keys():
            assert key == key.lower(), f"Config key '{key}' is not snake_case"

    def test_result_is_component_result(self):
        """convert() returns a ComponentResult."""
        node = _make_node()
        result = OracleOutputConverter().convert(node, [], {})
        assert isinstance(result, ComponentResult)


# ------------------------------------------------------------------
# TestPhantomParams
# ------------------------------------------------------------------

class TestPhantomParams:
    """Verify PASSWORD (wrong name) is not used as config key."""

    def test_password_key_not_from_wrong_xml_name(self):
        """PASSWORD param in XML should NOT be extracted -- only PASS is correct."""
        node = _make_node(params={"PASSWORD": '"wrong_source"'})
        result = OracleOutputConverter().convert(node, [], {})
        # password should be empty (default) because we only extract from PASS
        assert result.component["config"]["password"] == ""

    def test_schema_db_xml_param_not_used(self):
        """SCHEMA_DB XML param is NOT used for tOracleOutput; only TABLESCHEMA is.

        Post CR-01: the v1 engine config key is the canonical ``schema_db``,
        but the *Talend XML param* name remains TABLESCHEMA. A SCHEMA_DB XML
        param must be ignored (no fallback path), so config['schema_db']
        defaults to empty string when only SCHEMA_DB is supplied.
        """
        node = _make_node(params={"SCHEMA_DB": '"HR"'})
        result = OracleOutputConverter().convert(node, [], {})
        assert result.component["config"]["schema_db"] == ""
