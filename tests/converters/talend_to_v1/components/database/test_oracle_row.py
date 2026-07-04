"""Tests for OracleRowConverter (tOracleRow -> v1 oracle row config)."""
import xml.etree.ElementTree as ET

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


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

def _make_node(params=None, schema=None, component_id="orc_1",
               component_type="tOracleRow"):
    """Create a TalendNode for tOracleRow testing."""
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


def _make_prepared_params(rows):
    """Generate SET_PREPAREDSTATEMENT_PARAMETERS TABLE data with stride-3 per row.

    rows: list of tuples (index, type, value)
    """
    result = []
    for index, ptype, value in rows:
        result.append({"elementRef": "PARAMETER_INDEX", "value": index})
        result.append({"elementRef": "PARAMETER_TYPE", "value": ptype})
        result.append({"elementRef": "PARAMETER_VALUE", "value": value})
    return result


# ------------------------------------------------------------------
# TestRegistration
# ------------------------------------------------------------------

class TestRegistration:
    """Verify component is registered correctly."""

    def test_registered_in_registry(self):
        assert REGISTRY.get("tOracleRow") is OracleRowConverter


# ------------------------------------------------------------------
# TestDefaults
# ------------------------------------------------------------------

class TestDefaults:
    """Verify all parameters have correct defaults when no params provided."""

    def test_use_existing_connection_default(self):
        node = _make_node()
        result = OracleRowConverter().convert(node, [], {})
        assert result.component["config"]["use_existing_connection"] is False

    def test_connection_default(self):
        node = _make_node()
        result = OracleRowConverter().convert(node, [], {})
        assert result.component["config"]["connection"] == ""

    def test_connection_type_default(self):
        node = _make_node()
        result = OracleRowConverter().convert(node, [], {})
        assert result.component["config"]["connection_type"] == "ORACLE_SID"

    def test_db_version_default(self):
        node = _make_node()
        result = OracleRowConverter().convert(node, [], {})
        assert result.component["config"]["db_version"] == "ORACLE_18"

    def test_rac_url_default(self):
        node = _make_node()
        result = OracleRowConverter().convert(node, [], {})
        assert result.component["config"]["rac_url"] == ""

    def test_host_default(self):
        node = _make_node()
        result = OracleRowConverter().convert(node, [], {})
        assert result.component["config"]["host"] == ""

    def test_port_default(self):
        node = _make_node()
        result = OracleRowConverter().convert(node, [], {})
        assert result.component["config"]["port"] == "1521"

    def test_dbname_default(self):
        node = _make_node()
        result = OracleRowConverter().convert(node, [], {})
        assert result.component["config"]["dbname"] == ""

    def test_local_service_name_default(self):
        node = _make_node()
        result = OracleRowConverter().convert(node, [], {})
        assert result.component["config"]["local_service_name"] == ""

    def test_schema_db_default(self):
        node = _make_node()
        result = OracleRowConverter().convert(node, [], {})
        assert result.component["config"]["schema_db"] == ""

    def test_user_default(self):
        node = _make_node()
        result = OracleRowConverter().convert(node, [], {})
        assert result.component["config"]["user"] == ""

    def test_password_default(self):
        """Password config key should default to empty string."""
        node = _make_node()
        result = OracleRowConverter().convert(node, [], {})
        assert result.component["config"]["password"] == ""

    def test_table_default(self):
        node = _make_node()
        result = OracleRowConverter().convert(node, [], {})
        assert result.component["config"]["table"] == ""

    def test_query_default(self):
        node = _make_node()
        result = OracleRowConverter().convert(node, [], {})
        assert result.component["config"]["query"] == "select id, name from employee"

    def test_use_nb_line_default(self):
        node = _make_node()
        result = OracleRowConverter().convert(node, [], {})
        assert result.component["config"]["use_nb_line"] == "NONE"

    def test_specify_datasource_alias_default(self):
        node = _make_node()
        result = OracleRowConverter().convert(node, [], {})
        assert result.component["config"]["specify_datasource_alias"] is False

    def test_datasource_alias_default(self):
        node = _make_node()
        result = OracleRowConverter().convert(node, [], {})
        assert result.component["config"]["datasource_alias"] == ""

    def test_die_on_error_default(self):
        node = _make_node()
        result = OracleRowConverter().convert(node, [], {})
        assert result.component["config"]["die_on_error"] is False

    def test_properties_default(self):
        node = _make_node()
        result = OracleRowConverter().convert(node, [], {})
        assert result.component["config"]["properties"] == ""

    def test_propagate_record_set_default(self):
        node = _make_node()
        result = OracleRowConverter().convert(node, [], {})
        assert result.component["config"]["propagate_record_set"] is False

    def test_record_set_column_default(self):
        node = _make_node()
        result = OracleRowConverter().convert(node, [], {})
        assert result.component["config"]["record_set_column"] == ""

    def test_use_preparedstatement_default(self):
        node = _make_node()
        result = OracleRowConverter().convert(node, [], {})
        assert result.component["config"]["use_preparedstatement"] is False

    def test_set_preparedstatement_parameters_default(self):
        node = _make_node()
        result = OracleRowConverter().convert(node, [], {})
        assert result.component["config"]["set_preparedstatement_parameters"] == []

    def test_encoding_default(self):
        node = _make_node()
        result = OracleRowConverter().convert(node, [], {})
        assert result.component["config"]["encoding"] == "ISO-8859-15"

    def test_commit_every_default(self):
        node = _make_node()
        result = OracleRowConverter().convert(node, [], {})
        assert result.component["config"]["commit_every"] == 10000

    def test_support_nls_default(self):
        node = _make_node()
        result = OracleRowConverter().convert(node, [], {})
        assert result.component["config"]["support_nls"] is False


# ------------------------------------------------------------------
# TestParameterExtraction
# ------------------------------------------------------------------

class TestParameterExtraction:
    """Verify each parameter is correctly extracted from XML params."""

    def test_use_existing_connection_true(self):
        node = _make_node(params={"USE_EXISTING_CONNECTION": "true"})
        result = OracleRowConverter().convert(node, [], {})
        assert result.component["config"]["use_existing_connection"] is True

    def test_connection_extracted(self):
        node = _make_node(params={"CONNECTION": '"tOracleConnection_1"'})
        result = OracleRowConverter().convert(node, [], {})
        assert result.component["config"]["connection"] == "tOracleConnection_1"

    def test_connection_type_service_name(self):
        node = _make_node(params={"CONNECTION_TYPE": '"ORACLE_SERVICE_NAME"'})
        result = OracleRowConverter().convert(node, [], {})
        assert result.component["config"]["connection_type"] == "ORACLE_SERVICE_NAME"

    def test_db_version_extracted(self):
        node = _make_node(params={"DB_VERSION": '"ORACLE_12"'})
        result = OracleRowConverter().convert(node, [], {})
        assert result.component["config"]["db_version"] == "ORACLE_12"

    def test_rac_url_extracted(self):
        node = _make_node(params={"RAC_URL": '"jdbc:oracle:thin:@(DESCRIPTION=...)"'})
        result = OracleRowConverter().convert(node, [], {})
        assert result.component["config"]["rac_url"] == "jdbc:oracle:thin:@(DESCRIPTION=...)"

    def test_host_extracted(self):
        node = _make_node(params={"HOST": '"db.example.com"'})
        result = OracleRowConverter().convert(node, [], {})
        assert result.component["config"]["host"] == "db.example.com"

    def test_port_extracted(self):
        node = _make_node(params={"PORT": '"1522"'})
        result = OracleRowConverter().convert(node, [], {})
        assert result.component["config"]["port"] == "1522"

    def test_dbname_extracted(self):
        node = _make_node(params={"DBNAME": '"PRODDB"'})
        result = OracleRowConverter().convert(node, [], {})
        assert result.component["config"]["dbname"] == "PRODDB"

    def test_local_service_name_extracted(self):
        node = _make_node(params={"LOCAL_SERVICE_NAME": '"my_oci_svc"'})
        result = OracleRowConverter().convert(node, [], {})
        assert result.component["config"]["local_service_name"] == "my_oci_svc"

    def test_schema_db_extracted(self):
        node = _make_node(params={"SCHEMA_DB": '"HR"'})
        result = OracleRowConverter().convert(node, [], {})
        assert result.component["config"]["schema_db"] == "HR"

    def test_user_extracted(self):
        node = _make_node(params={"USER": '"scott"'})
        result = OracleRowConverter().convert(node, [], {})
        assert result.component["config"]["user"] == "scott"

    def test_password_extracted_from_pass(self):
        """CRITICAL: Password must be extracted from PASS (not PASSWORD)."""
        node = _make_node(params={"PASS": '"tiger"'})
        result = OracleRowConverter().convert(node, [], {})
        assert result.component["config"]["password"] == "tiger"

    def test_password_not_from_password_key(self):
        """Converter must use PASS, not PASSWORD. PASSWORD param should be ignored."""
        node = _make_node(params={"PASSWORD": '"wrong_key"'})
        result = OracleRowConverter().convert(node, [], {})
        assert result.component["config"]["password"] == ""

    def test_table_extracted(self):
        node = _make_node(params={"TABLE": '"employees"'})
        result = OracleRowConverter().convert(node, [], {})
        assert result.component["config"]["table"] == "employees"

    def test_query_extracted(self):
        node = _make_node(params={"QUERY": '"UPDATE accounts SET status=1"'})
        result = OracleRowConverter().convert(node, [], {})
        assert result.component["config"]["query"] == "UPDATE accounts SET status=1"

    def test_use_nb_line_inserted(self):
        node = _make_node(params={"USE_NB_LINE": '"NB_LINE_INSERTED"'})
        result = OracleRowConverter().convert(node, [], {})
        assert result.component["config"]["use_nb_line"] == "NB_LINE_INSERTED"

    def test_use_nb_line_updated(self):
        node = _make_node(params={"USE_NB_LINE": '"NB_LINE_UPDATED"'})
        result = OracleRowConverter().convert(node, [], {})
        assert result.component["config"]["use_nb_line"] == "NB_LINE_UPDATED"

    def test_use_nb_line_deleted(self):
        node = _make_node(params={"USE_NB_LINE": '"NB_LINE_DELETED"'})
        result = OracleRowConverter().convert(node, [], {})
        assert result.component["config"]["use_nb_line"] == "NB_LINE_DELETED"

    def test_die_on_error_true(self):
        node = _make_node(params={"DIE_ON_ERROR": "true"})
        result = OracleRowConverter().convert(node, [], {})
        assert result.component["config"]["die_on_error"] is True

    def test_propagate_record_set_true(self):
        node = _make_node(params={"PROPAGATE_RECORD_SET": "true"})
        result = OracleRowConverter().convert(node, [], {})
        assert result.component["config"]["propagate_record_set"] is True

    def test_record_set_column_extracted(self):
        node = _make_node(params={"RECORD_SET_COLUMN": '"rs_col"'})
        result = OracleRowConverter().convert(node, [], {})
        assert result.component["config"]["record_set_column"] == "rs_col"

    def test_use_preparedstatement_true(self):
        node = _make_node(params={"USE_PREPAREDSTATEMENT": "true"})
        result = OracleRowConverter().convert(node, [], {})
        assert result.component["config"]["use_preparedstatement"] is True

    def test_encoding_extracted(self):
        node = _make_node(params={"ENCODING": '"UTF-8"'})
        result = OracleRowConverter().convert(node, [], {})
        assert result.component["config"]["encoding"] == "UTF-8"

    def test_commit_every_extracted(self):
        node = _make_node(params={"COMMIT_EVERY": "5000"})
        result = OracleRowConverter().convert(node, [], {})
        assert result.component["config"]["commit_every"] == 5000

    def test_commit_every_quoted(self):
        node = _make_node(params={"COMMIT_EVERY": '"25000"'})
        result = OracleRowConverter().convert(node, [], {})
        assert result.component["config"]["commit_every"] == 25000

    def test_support_nls_true(self):
        node = _make_node(params={"SUPPORT_NLS": "true"})
        result = OracleRowConverter().convert(node, [], {})
        assert result.component["config"]["support_nls"] is True

    def test_specify_datasource_alias_true(self):
        node = _make_node(params={"SPECIFY_DATASOURCE_ALIAS": "true"})
        result = OracleRowConverter().convert(node, [], {})
        assert result.component["config"]["specify_datasource_alias"] is True

    def test_datasource_alias_extracted(self):
        node = _make_node(params={"DATASOURCE_ALIAS": '"myDS"'})
        result = OracleRowConverter().convert(node, [], {})
        assert result.component["config"]["datasource_alias"] == "myDS"

    def test_properties_extracted(self):
        node = _make_node(params={"PROPERTIES": '"oracle.net.CONNECT_TIMEOUT=5000"'})
        result = OracleRowConverter().convert(node, [], {})
        assert result.component["config"]["properties"] == "oracle.net.CONNECT_TIMEOUT=5000"


# ------------------------------------------------------------------
# TestPreparedStatementTable
# ------------------------------------------------------------------

class TestPreparedStatementTable:
    """Verify SET_PREPAREDSTATEMENT_PARAMETERS TABLE parsing."""

    def test_empty_prepared_params_default(self):
        """No TABLE data should yield empty list."""
        node = _make_node()
        result = OracleRowConverter().convert(node, [], {})
        assert result.component["config"]["set_preparedstatement_parameters"] == []

    def test_single_prepared_param(self):
        """Single prepared statement parameter with stride-3."""
        table_data = _make_prepared_params([("1", "String", '"hello"')])
        node = _make_node(params={"SET_PREPAREDSTATEMENT_PARAMETERS": table_data})
        result = OracleRowConverter().convert(node, [], {})
        params = result.component["config"]["set_preparedstatement_parameters"]
        assert len(params) == 1
        assert params[0]["parameter_index"] == "1"
        assert params[0]["parameter_type"] == "String"
        assert params[0]["parameter_value"] == "hello"

    def test_multiple_prepared_params(self):
        """Multiple prepared statement parameters."""
        table_data = _make_prepared_params([
            ("1", "Int", '"42"'),
            ("2", "String", '"test"'),
            ("3", "Date", '"2024-01-01"'),
        ])
        node = _make_node(params={"SET_PREPAREDSTATEMENT_PARAMETERS": table_data})
        result = OracleRowConverter().convert(node, [], {})
        params = result.component["config"]["set_preparedstatement_parameters"]
        assert len(params) == 3
        assert params[0]["parameter_index"] == "1"
        assert params[0]["parameter_type"] == "Int"
        assert params[0]["parameter_value"] == "42"
        assert params[1]["parameter_index"] == "2"
        assert params[1]["parameter_type"] == "String"
        assert params[2]["parameter_type"] == "Date"

    def test_incomplete_stride_skipped(self):
        """Incomplete trailing group (< 3 entries) should be skipped."""
        table_data = _make_prepared_params([("1", "String", '"val"')])
        # Add an incomplete trailing entry
        table_data.append({"elementRef": "PARAMETER_INDEX", "value": "2"})
        node = _make_node(params={"SET_PREPAREDSTATEMENT_PARAMETERS": table_data})
        result = OracleRowConverter().convert(node, [], {})
        params = result.component["config"]["set_preparedstatement_parameters"]
        assert len(params) == 1

    def test_none_table_returns_empty(self):
        """None raw TABLE data should yield empty list."""
        node = _make_node(params={"SET_PREPAREDSTATEMENT_PARAMETERS": None})
        result = OracleRowConverter().convert(node, [], {})
        assert result.component["config"]["set_preparedstatement_parameters"] == []

    def test_non_list_table_returns_empty(self):
        """Non-list raw TABLE data should yield empty list."""
        node = _make_node(params={"SET_PREPAREDSTATEMENT_PARAMETERS": "invalid"})
        result = OracleRowConverter().convert(node, [], {})
        assert result.component["config"]["set_preparedstatement_parameters"] == []

    # WR-03: malformed group with missing required key is skipped + warned
    def test_malformed_group_missing_key_dropped_with_warning(self):
        """A 3-entry group with a typo'd elementRef is not a valid row.

        The engine-side ``_coerce_prepared_param`` would silently fall back
        to ``parameter_type="Object"`` / ``parameter_value=None`` if we
        accepted the partial row -- masking corruption. WR-03 fix: drop
        the row and surface a warning.
        """
        table_data = [
            # Row 1: valid
            {"elementRef": "PARAMETER_INDEX", "value": '"1"'},
            {"elementRef": "PARAMETER_TYPE", "value": '"String"'},
            {"elementRef": "PARAMETER_VALUE", "value": '"good"'},
            # Row 2: typo on PARAMETER_TYPE -> only INDEX + VALUE land
            {"elementRef": "PARAMETER_INDEX", "value": '"2"'},
            {"elementRef": "PARAMETER_TIPE", "value": '"String"'},  # typo
            {"elementRef": "PARAMETER_VALUE", "value": '"bad"'},
        ]
        node = _make_node(
            params={"SET_PREPAREDSTATEMENT_PARAMETERS": table_data}
        )
        result = OracleRowConverter().convert(node, [], {})
        params = result.component["config"]["set_preparedstatement_parameters"]
        assert len(params) == 1
        assert params[0]["parameter_index"] == "1"
        # Warning surfaced via ComponentResult.warnings sink
        assert any(
            "Incomplete SET_PREPAREDSTATEMENT_PARAMETERS" in w
            for w in result.warnings
        )

    # WR-04: parameter_index validated as positive integer
    def test_non_numeric_parameter_index_dropped_with_warning(self):
        """Non-numeric parameter_index would crash the engine at int()."""
        table_data = _make_prepared_params([
            ("abc", "String", '"hello"'),  # non-numeric
            ("1", "String", '"world"'),
        ])
        node = _make_node(
            params={"SET_PREPAREDSTATEMENT_PARAMETERS": table_data}
        )
        result = OracleRowConverter().convert(node, [], {})
        params = result.component["config"]["set_preparedstatement_parameters"]
        assert len(params) == 1
        assert params[0]["parameter_index"] == "1"
        assert any(
            "Invalid parameter_index" in w for w in result.warnings
        )

    def test_zero_parameter_index_dropped_with_warning(self):
        """parameter_index must be 1-indexed (>= 1)."""
        table_data = _make_prepared_params([
            ("0", "String", '"hello"'),
            ("1", "String", '"world"'),
        ])
        node = _make_node(
            params={"SET_PREPAREDSTATEMENT_PARAMETERS": table_data}
        )
        result = OracleRowConverter().convert(node, [], {})
        params = result.component["config"]["set_preparedstatement_parameters"]
        assert len(params) == 1
        assert params[0]["parameter_index"] == "1"

    def test_negative_parameter_index_dropped_with_warning(self):
        """parameter_index must be positive."""
        table_data = _make_prepared_params([
            ("-3", "String", '"hello"'),
            ("1", "String", '"world"'),
        ])
        node = _make_node(
            params={"SET_PREPAREDSTATEMENT_PARAMETERS": table_data}
        )
        result = OracleRowConverter().convert(node, [], {})
        params = result.component["config"]["set_preparedstatement_parameters"]
        assert len(params) == 1


# ------------------------------------------------------------------
# TestFrameworkParams
# ------------------------------------------------------------------

class TestFrameworkParams:
    """Verify tstatcatcher_stats and label extraction."""

    def test_tstatcatcher_stats_default_false(self):
        node = _make_node()
        result = OracleRowConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is False

    def test_tstatcatcher_stats_true(self):
        node = _make_node(params={"TSTATCATCHER_STATS": "true"})
        result = OracleRowConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is True

    def test_label_default_empty(self):
        node = _make_node()
        result = OracleRowConverter().convert(node, [], {})
        assert result.component["config"]["label"] == ""

    def test_label_extracted(self):
        node = _make_node(params={"LABEL": '"my_label"'})
        result = OracleRowConverter().convert(node, [], {})
        assert result.component["config"]["label"] == "my_label"


# ------------------------------------------------------------------
# TestSchema
# ------------------------------------------------------------------

class TestSchema:
    """Verify schema extraction."""

    def test_schema_extracted(self):
        node = _make_node(schema=_make_schema_columns())
        result = OracleRowConverter().convert(node, [], {})
        schema = result.component["schema"]
        assert schema is not None
        assert "input" in schema
        assert "output" in schema
        assert len(schema["input"]) == 2
        assert len(schema["output"]) == 2

    def test_schema_empty_when_no_flow(self):
        node = _make_node()
        result = OracleRowConverter().convert(node, [], {})
        schema = result.component["schema"]
        assert schema["input"] == []
        assert schema["output"] == []


# ------------------------------------------------------------------
# TestNeedsReview
# ------------------------------------------------------------------

class TestNeedsReview:
    """D-E1: Wallet/OCI emit a thick-mode needs_review; SID/SERVICE_NAME/RAC
    emit zero needs_review entries (Phase 11 ships those connection types)."""

    def test_no_needs_review_for_sid(self):
        """ORACLE_SID emits zero needs_review entries (engine ships it)."""
        node = _make_node(params={"CONNECTION_TYPE": '"ORACLE_SID"'})
        result = OracleRowConverter().convert(node, [], {})
        assert len(result.needs_review) == 0

    def test_no_needs_review_for_service_name(self):
        """ORACLE_SERVICE_NAME emits zero needs_review entries."""
        node = _make_node(params={"CONNECTION_TYPE": '"ORACLE_SERVICE_NAME"'})
        result = OracleRowConverter().convert(node, [], {})
        assert len(result.needs_review) == 0

    def test_no_needs_review_for_rac(self):
        """ORACLE_RAC emits zero needs_review entries."""
        node = _make_node(params={"CONNECTION_TYPE": '"ORACLE_RAC"'})
        result = OracleRowConverter().convert(node, [], {})
        assert len(result.needs_review) == 0

    def test_needs_review_for_wallet(self):
        """ORACLE_WALLET emits a thick-mode needs_review entry (D-E1)."""
        node = _make_node(params={"CONNECTION_TYPE": '"ORACLE_WALLET"'},
                          component_id="orc_wallet")
        result = OracleRowConverter().convert(node, [], {})
        assert len(result.needs_review) == 1
        entry = result.needs_review[0]
        assert entry["severity"] == "needs_review"
        assert entry["component"] == "orc_wallet"
        assert "thick_mode" in entry["issue"]
        assert "Instant Client" in entry["issue"]
        assert "ORACLE_WALLET" in entry["issue"]

    def test_needs_review_for_oci(self):
        """ORACLE_OCI emits a thick-mode needs_review entry (D-E1)."""
        node = _make_node(params={"CONNECTION_TYPE": '"ORACLE_OCI"'})
        result = OracleRowConverter().convert(node, [], {})
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
        result = OracleRowConverter().convert(node, [], {})
        issue = result.needs_review[0]["issue"]
        assert "scott" not in issue
        assert "tiger" not in issue


# ------------------------------------------------------------------
# TestCompleteness
# ------------------------------------------------------------------

class TestCompleteness:
    """Verify all expected config keys are present."""

    def test_all_top_level_keys_present(self):
        node = _make_node(schema=_make_schema_columns())
        result = OracleRowConverter().convert(node, [], {})
        expected_top_keys = {"id", "type", "original_type", "position", "config", "schema", "inputs", "outputs"}
        actual_keys = set(result.component.keys())
        missing = expected_top_keys - actual_keys
        assert not missing, f"Missing top-level keys: {missing}"

    def test_all_config_keys_present(self):
        node = _make_node(schema=_make_schema_columns())
        result = OracleRowConverter().convert(node, [], {})
        expected_keys = {
            # Connection params
            "use_existing_connection", "connection", "connection_type",
            "db_version", "rac_url", "host", "port", "dbname",
            "local_service_name", "schema_db", "user", "password",
            # Query params
            "table", "query", "use_nb_line",
            # Datasource params
            "specify_datasource_alias", "datasource_alias",
            # Error handling
            "die_on_error",
            # Advanced params
            "properties", "propagate_record_set", "record_set_column",
            "use_preparedstatement", "set_preparedstatement_parameters",
            "encoding", "commit_every", "support_nls",
            # Framework params
            "tstatcatcher_stats", "label",
        }
        actual_keys = set(result.component["config"].keys())
        missing = expected_keys - actual_keys
        assert not missing, f"Missing config keys: {missing}"

    def test_config_key_count(self):
        """Verify config key count matches expected (26 unique params + 2 framework = 28)."""
        node = _make_node(schema=_make_schema_columns())
        result = OracleRowConverter().convert(node, [], {})
        # 26 unique params + 2 framework (tstatcatcher_stats, label) = 28
        assert len(result.component["config"]) == 28


# ------------------------------------------------------------------
# TestPhantomParams
# ------------------------------------------------------------------

class TestPhantomParams:
    """Verify params NOT in _java.xml are NOT extracted."""

    def test_password_key_not_in_config(self):
        """PASSWORD is a phantom param -- _java.xml uses PASS."""
        node = _make_node(params={"PASSWORD": '"should_not_appear"'})
        result = OracleRowConverter().convert(node, [], {})
        # The config key 'password' should exist but should be empty (not from PASSWORD param)
        assert result.component["config"]["password"] == ""
