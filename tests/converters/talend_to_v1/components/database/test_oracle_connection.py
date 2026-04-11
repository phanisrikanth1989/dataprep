"""Tests for OracleConnectionConverter (tOracleConnection / tDBConnection -> OracleConnection)."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.database.oracle_connection import (
    OracleConnectionConverter,
)
from src.converters.talend_to_v1.components.registry import REGISTRY


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

def _make_node(params=None, schema=None, component_id="tOracleConnection_1",
               component_type="tOracleConnection"):
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
    converter = OracleConnectionConverter()
    return converter.convert(
        node=node,
        connections=connections or [],
        context=context or {},
    )


# ------------------------------------------------------------------
# Registration
# ------------------------------------------------------------------

class TestRegistration:
    """Verify component is registered correctly under both names."""

    def test_registered_as_oracle_connection(self):
        """tOracleConnection resolves to OracleConnectionConverter."""
        assert REGISTRY.get("tOracleConnection") is OracleConnectionConverter

    def test_registered_as_db_connection(self):
        """tDBConnection resolves to OracleConnectionConverter (dual registration)."""
        assert REGISTRY.get("tDBConnection") is OracleConnectionConverter


# ------------------------------------------------------------------
# Defaults -- all 28 unique params + 2 framework
# ------------------------------------------------------------------

class TestDefaults:
    """Verify all parameters have correct defaults when no params provided."""

    def test_connection_type_default(self):
        """CONNECTION_TYPE defaults to ORACLE_SID."""
        node = _make_node()
        result = _convert(node)
        assert result.component["config"]["connection_type"] == "ORACLE_SID"

    def test_db_version_default(self):
        """DB_VERSION defaults to ORACLE_18."""
        node = _make_node()
        result = _convert(node)
        assert result.component["config"]["db_version"] == "ORACLE_18"

    def test_rac_url_default(self):
        """RAC_URL defaults to empty string."""
        node = _make_node()
        result = _convert(node)
        assert result.component["config"]["rac_url"] == ""

    def test_use_tns_file_default(self):
        """USE_TNS_FILE defaults to False."""
        node = _make_node()
        result = _convert(node)
        assert result.component["config"]["use_tns_file"] is False

    def test_tns_file_default(self):
        """TNS_FILE defaults to empty string."""
        node = _make_node()
        result = _convert(node)
        assert result.component["config"]["tns_file"] == ""

    def test_host_default(self):
        """HOST defaults to empty string."""
        node = _make_node()
        result = _convert(node)
        assert result.component["config"]["host"] == ""

    def test_port_default(self):
        """PORT defaults to 1521."""
        node = _make_node()
        result = _convert(node)
        assert result.component["config"]["port"] == "1521"

    def test_dbname_default(self):
        """DBNAME defaults to empty string."""
        node = _make_node()
        result = _convert(node)
        assert result.component["config"]["dbname"] == ""

    def test_local_service_name_default(self):
        """LOCAL_SERVICE_NAME defaults to empty string."""
        node = _make_node()
        result = _convert(node)
        assert result.component["config"]["local_service_name"] == ""

    def test_schema_db_default(self):
        """SCHEMA_DB defaults to empty string."""
        node = _make_node()
        result = _convert(node)
        assert result.component["config"]["schema_db"] == ""

    def test_user_default(self):
        """USER defaults to empty string."""
        node = _make_node()
        result = _convert(node)
        assert result.component["config"]["user"] == ""

    def test_password_default(self):
        """PASS -> password defaults to empty string."""
        node = _make_node()
        result = _convert(node)
        assert result.component["config"]["password"] == ""

    def test_jdbc_url_default(self):
        """JDBC_URL defaults to standard Wallet URL."""
        node = _make_node()
        result = _convert(node)
        assert result.component["config"]["jdbc_url"] == "jdbc:oracle:thin:USER/MDP@server"

    def test_encoding_default(self):
        """ENCODING defaults to ISO-8859-15."""
        node = _make_node()
        result = _convert(node)
        assert result.component["config"]["encoding"] == "ISO-8859-15"

    def test_properties_default(self):
        """PROPERTIES defaults to empty string."""
        node = _make_node()
        result = _convert(node)
        assert result.component["config"]["properties"] == ""

    def test_use_shared_connection_default(self):
        """USE_SHARED_CONNECTION defaults to False."""
        node = _make_node()
        result = _convert(node)
        assert result.component["config"]["use_shared_connection"] is False

    def test_shared_connection_name_default(self):
        """SHARED_CONNECTION_NAME defaults to empty string."""
        node = _make_node()
        result = _convert(node)
        assert result.component["config"]["shared_connection_name"] == ""

    def test_specify_datasource_alias_default(self):
        """SPECIFY_DATASOURCE_ALIAS defaults to False."""
        node = _make_node()
        result = _convert(node)
        assert result.component["config"]["specify_datasource_alias"] is False

    def test_datasource_alias_default(self):
        """DATASOURCE_ALIAS defaults to empty string."""
        node = _make_node()
        result = _convert(node)
        assert result.component["config"]["datasource_alias"] == ""

    def test_use_ssl_default(self):
        """USE_SSL defaults to False."""
        node = _make_node()
        result = _convert(node)
        assert result.component["config"]["use_ssl"] is False

    def test_ssl_trustserver_truststore_default(self):
        """SSL_TRUSTSERVER_TRUSTSTORE defaults to empty string."""
        node = _make_node()
        result = _convert(node)
        assert result.component["config"]["ssl_trustserver_truststore"] == ""

    def test_need_client_auth_default(self):
        """NEED_CLIENT_AUTH defaults to False."""
        node = _make_node()
        result = _convert(node)
        assert result.component["config"]["need_client_auth"] is False

    def test_ssl_keystore_default(self):
        """SSL_KEYSTORE defaults to empty string."""
        node = _make_node()
        result = _convert(node)
        assert result.component["config"]["ssl_keystore"] == ""

    def test_disable_cbc_protection_default(self):
        """DISABLE_CBC_PROTECTION defaults to True (unusual -- most CHECKs default false)."""
        node = _make_node()
        result = _convert(node)
        assert result.component["config"]["disable_cbc_protection"] is True

    def test_auto_commit_default(self):
        """AUTO_COMMIT defaults to False."""
        node = _make_node()
        result = _convert(node)
        assert result.component["config"]["auto_commit"] is False

    def test_support_nls_default(self):
        """SUPPORT_NLS defaults to False."""
        node = _make_node()
        result = _convert(node)
        assert result.component["config"]["support_nls"] is False


# ------------------------------------------------------------------
# Parameter extraction
# ------------------------------------------------------------------

class TestParameterExtraction:
    """Verify each parameter is correctly extracted from XML params."""

    def test_connection_type_service_name(self):
        """CONNECTION_TYPE = ORACLE_SERVICE_NAME extracted."""
        node = _make_node(params={"CONNECTION_TYPE": '"ORACLE_SERVICE_NAME"'})
        result = _convert(node)
        assert result.component["config"]["connection_type"] == "ORACLE_SERVICE_NAME"

    def test_connection_type_rac(self):
        """CONNECTION_TYPE = ORACLE_RAC extracted."""
        node = _make_node(params={"CONNECTION_TYPE": '"ORACLE_RAC"'})
        result = _convert(node)
        assert result.component["config"]["connection_type"] == "ORACLE_RAC"

    def test_db_version_oracle_12(self):
        """DB_VERSION = ORACLE_12 extracted."""
        node = _make_node(params={"DB_VERSION": '"ORACLE_12"'})
        result = _convert(node)
        assert result.component["config"]["db_version"] == "ORACLE_12"

    def test_host_extracted(self):
        """HOST extracted with quotes stripped."""
        node = _make_node(params={"HOST": '"db.example.com"'})
        result = _convert(node)
        assert result.component["config"]["host"] == "db.example.com"

    def test_port_extracted(self):
        """PORT extracted as string."""
        node = _make_node(params={"PORT": '"1522"'})
        result = _convert(node)
        assert result.component["config"]["port"] == "1522"

    def test_dbname_extracted(self):
        """DBNAME extracted with quotes stripped."""
        node = _make_node(params={"DBNAME": '"ORCL"'})
        result = _convert(node)
        assert result.component["config"]["dbname"] == "ORCL"

    def test_user_extracted(self):
        """USER extracted."""
        node = _make_node(params={"USER": '"scott"'})
        result = _convert(node)
        assert result.component["config"]["user"] == "scott"

    def test_password_from_pass(self):
        """PASS XML name -> password config key per D-30."""
        node = _make_node(params={"PASS": '"tiger"'})
        result = _convert(node)
        assert result.component["config"]["password"] == "tiger"

    def test_use_ssl_true(self):
        """USE_SSL = true extracted as boolean."""
        node = _make_node(params={"USE_SSL": "true"})
        result = _convert(node)
        assert result.component["config"]["use_ssl"] is True

    def test_ssl_truststore_extracted(self):
        """SSL_TRUSTSERVER_TRUSTSTORE extracted."""
        node = _make_node(params={"SSL_TRUSTSERVER_TRUSTSTORE": '"/path/to/truststore.jks"'})
        result = _convert(node)
        assert result.component["config"]["ssl_trustserver_truststore"] == "/path/to/truststore.jks"

    def test_ssl_keystore_extracted(self):
        """SSL_KEYSTORE extracted."""
        node = _make_node(params={"SSL_KEYSTORE": '"/path/to/keystore.jks"'})
        result = _convert(node)
        assert result.component["config"]["ssl_keystore"] == "/path/to/keystore.jks"

    def test_need_client_auth_true(self):
        """NEED_CLIENT_AUTH = true extracted as boolean."""
        node = _make_node(params={"NEED_CLIENT_AUTH": "true"})
        result = _convert(node)
        assert result.component["config"]["need_client_auth"] is True

    def test_disable_cbc_protection_false(self):
        """DISABLE_CBC_PROTECTION = false (overriding default True)."""
        node = _make_node(params={"DISABLE_CBC_PROTECTION": "false"})
        result = _convert(node)
        assert result.component["config"]["disable_cbc_protection"] is False

    def test_use_tns_file_true(self):
        """USE_TNS_FILE = true extracted."""
        node = _make_node(params={"USE_TNS_FILE": "true"})
        result = _convert(node)
        assert result.component["config"]["use_tns_file"] is True

    def test_tns_file_extracted(self):
        """TNS_FILE extracted."""
        node = _make_node(params={"TNS_FILE": '"/etc/tnsnames.ora"'})
        result = _convert(node)
        assert result.component["config"]["tns_file"] == "/etc/tnsnames.ora"

    def test_rac_url_extracted(self):
        """RAC_URL extracted."""
        node = _make_node(params={"RAC_URL": '"(DESCRIPTION=(ADDRESS_LIST=(ADDRESS=(PROTOCOL=TCP))))"'})
        result = _convert(node)
        assert result.component["config"]["rac_url"] == "(DESCRIPTION=(ADDRESS_LIST=(ADDRESS=(PROTOCOL=TCP))))"

    def test_local_service_name_extracted(self):
        """LOCAL_SERVICE_NAME extracted."""
        node = _make_node(params={"LOCAL_SERVICE_NAME": '"ORCL_OCI"'})
        result = _convert(node)
        assert result.component["config"]["local_service_name"] == "ORCL_OCI"

    def test_schema_db_extracted(self):
        """SCHEMA_DB extracted."""
        node = _make_node(params={"SCHEMA_DB": '"HR"'})
        result = _convert(node)
        assert result.component["config"]["schema_db"] == "HR"

    def test_jdbc_url_extracted(self):
        """JDBC_URL extracted."""
        node = _make_node(params={"JDBC_URL": '"jdbc:oracle:thin:@//myhost:1521/mydb"'})
        result = _convert(node)
        assert result.component["config"]["jdbc_url"] == "jdbc:oracle:thin:@//myhost:1521/mydb"

    def test_encoding_extracted(self):
        """ENCODING extracted."""
        node = _make_node(params={"ENCODING": '"UTF-8"'})
        result = _convert(node)
        assert result.component["config"]["encoding"] == "UTF-8"

    def test_properties_extracted(self):
        """PROPERTIES extracted."""
        node = _make_node(params={"PROPERTIES": '"oracle.net.ssl_version=1.2"'})
        result = _convert(node)
        assert result.component["config"]["properties"] == "oracle.net.ssl_version=1.2"

    def test_use_shared_connection_true(self):
        """USE_SHARED_CONNECTION = true extracted."""
        node = _make_node(params={"USE_SHARED_CONNECTION": "true"})
        result = _convert(node)
        assert result.component["config"]["use_shared_connection"] is True

    def test_shared_connection_name_extracted(self):
        """SHARED_CONNECTION_NAME extracted."""
        node = _make_node(params={"SHARED_CONNECTION_NAME": '"sharedConn1"'})
        result = _convert(node)
        assert result.component["config"]["shared_connection_name"] == "sharedConn1"

    def test_specify_datasource_alias_true(self):
        """SPECIFY_DATASOURCE_ALIAS = true extracted."""
        node = _make_node(params={"SPECIFY_DATASOURCE_ALIAS": "true"})
        result = _convert(node)
        assert result.component["config"]["specify_datasource_alias"] is True

    def test_datasource_alias_extracted(self):
        """DATASOURCE_ALIAS extracted."""
        node = _make_node(params={"DATASOURCE_ALIAS": '"jdbc/OracleDS"'})
        result = _convert(node)
        assert result.component["config"]["datasource_alias"] == "jdbc/OracleDS"

    def test_auto_commit_true(self):
        """AUTO_COMMIT = true extracted."""
        node = _make_node(params={"AUTO_COMMIT": "true"})
        result = _convert(node)
        assert result.component["config"]["auto_commit"] is True

    def test_support_nls_true(self):
        """SUPPORT_NLS = true extracted."""
        node = _make_node(params={"SUPPORT_NLS": "true"})
        result = _convert(node)
        assert result.component["config"]["support_nls"] is True

    def test_port_context_variable_preserved(self):
        """PORT with context variable preserves expression string."""
        node = _make_node(params={"PORT": '"context.DB_PORT"'})
        result = _convert(node)
        assert result.component["config"]["port"] == "context.DB_PORT"


# ------------------------------------------------------------------
# Framework parameters
# ------------------------------------------------------------------

class TestFrameworkParams:
    """Verify tstatcatcher_stats and label extraction."""

    def test_tstatcatcher_stats_default_false(self):
        """TSTATCATCHER_STATS defaults to False."""
        node = _make_node()
        result = _convert(node)
        assert result.component["config"]["tstatcatcher_stats"] is False

    def test_tstatcatcher_stats_true(self):
        """TSTATCATCHER_STATS = true extracted."""
        node = _make_node(params={"TSTATCATCHER_STATS": "true"})
        result = _convert(node)
        assert result.component["config"]["tstatcatcher_stats"] is True

    def test_label_default_empty(self):
        """LABEL defaults to empty string."""
        node = _make_node()
        result = _convert(node)
        assert result.component["config"]["label"] == ""

    def test_label_extracted(self):
        """LABEL extracted with quotes stripped."""
        node = _make_node(params={"LABEL": '"Oracle Connection"'})
        result = _convert(node)
        assert result.component["config"]["label"] == "Oracle Connection"


# ------------------------------------------------------------------
# Schema
# ------------------------------------------------------------------

class TestSchema:
    """Verify schema extraction."""

    def test_schema_extracted(self):
        """Schema is a dict with input/output lists (connection has no data flow)."""
        node = _make_node(schema=_make_schema_columns())
        result = _convert(node)
        assert isinstance(result.component["schema"], dict)
        assert result.component["schema"] == {"input": [], "output": []}

    def test_schema_empty_when_no_schema(self):
        """Schema is dict with empty input/output lists when no schema defined."""
        node = _make_node()
        result = _convert(node)
        assert result.component["schema"] == {"input": [], "output": []}


# ------------------------------------------------------------------
# Needs review
# ------------------------------------------------------------------

class TestNeedsReview:
    """Verify needs_review entries for engine gaps."""

    def test_needs_review_count(self):
        """Exactly 1 consolidated needs_review entry per D-27."""
        node = _make_node()
        result = _convert(node)
        assert len(result.needs_review) == 1

    def test_needs_review_is_engine_gap(self):
        """The needs_review entry has severity engine_gap."""
        node = _make_node()
        result = _convert(node)
        assert result.needs_review[0]["severity"] == "engine_gap"

    def test_needs_review_has_component_id(self):
        """The needs_review entry includes the component_id."""
        node = _make_node(component_id="tOracleConnection_42")
        result = _convert(node)
        assert result.needs_review[0]["component"] == "tOracleConnection_42"

    def test_no_framework_param_needs_review(self):
        """Framework params (tstatcatcher_stats, label) must NOT appear in needs_review."""
        node = _make_node()
        result = _convert(node)
        issues = [e["issue"] for e in result.needs_review]
        for issue in issues:
            assert "tstatcatcher_stats" not in issue
            assert "label" not in issue.lower().split()


# ------------------------------------------------------------------
# Completeness
# ------------------------------------------------------------------

class TestCompleteness:
    """Verify all expected config keys are present."""

    def test_all_top_level_keys_present(self):
        """All top-level keys present in _build_component_dict output."""
        node = _make_node(schema=_make_schema_columns())
        result = _convert(node)
        expected_top_keys = {"id", "type", "original_type", "position", "config", "schema", "inputs", "outputs"}
        actual_top_keys = set(result.component.keys())
        missing = expected_top_keys - actual_top_keys
        assert not missing, f"Missing top-level keys: {missing}"

    def test_no_extra_top_level_keys(self):
        """No unexpected top-level keys."""
        node = _make_node(schema=_make_schema_columns())
        result = _convert(node)
        expected_top_keys = {"id", "type", "original_type", "position", "config", "schema", "inputs", "outputs"}
        actual_top_keys = set(result.component.keys())
        extra = actual_top_keys - expected_top_keys
        assert not extra, f"Unexpected top-level keys: {extra}"

    def test_all_config_keys_present(self):
        """All 28 config keys present (26 params + 2 framework)."""
        node = _make_node(schema=_make_schema_columns())
        result = _convert(node)
        expected_config_keys = {
            # Connection type params
            "connection_type", "db_version", "rac_url", "use_tns_file", "tns_file",
            # Core connection params
            "host", "port", "dbname", "local_service_name", "schema_db",
            "user", "password", "jdbc_url",
            # Configuration
            "encoding", "properties",
            # Shared connection
            "use_shared_connection", "shared_connection_name",
            # Datasource alias
            "specify_datasource_alias", "datasource_alias",
            # SSL
            "use_ssl", "ssl_trustserver_truststore",
            "need_client_auth", "ssl_keystore",
            "disable_cbc_protection",
            # Advanced
            "auto_commit", "support_nls",
            # Framework (ALWAYS LAST)
            "tstatcatcher_stats", "label",
        }
        actual_config_keys = set(result.component["config"].keys())
        missing = expected_config_keys - actual_config_keys
        assert not missing, f"Missing config keys: {missing}"

    def test_no_extra_config_keys(self):
        """No unexpected keys in config."""
        node = _make_node(schema=_make_schema_columns())
        result = _convert(node)
        expected_config_keys = {
            "connection_type", "db_version", "rac_url", "use_tns_file", "tns_file",
            "host", "port", "dbname", "local_service_name", "schema_db",
            "user", "password", "jdbc_url",
            "encoding", "properties",
            "use_shared_connection", "shared_connection_name",
            "specify_datasource_alias", "datasource_alias",
            "use_ssl", "ssl_trustserver_truststore",
            "need_client_auth", "ssl_keystore",
            "disable_cbc_protection",
            "auto_commit", "support_nls",
            "tstatcatcher_stats", "label",
        }
        actual_config_keys = set(result.component["config"].keys())
        extra = actual_config_keys - expected_config_keys
        assert not extra, f"Unexpected config keys: {extra}"


# ------------------------------------------------------------------
# Edge cases
# ------------------------------------------------------------------

class TestEdgeCases:
    """Edge case and component-specific tests."""

    def test_type_set(self):
        """type is tOracleConnection."""
        node = _make_node()
        result = _convert(node)
        assert result.component["type"] == "tOracleConnection"

    def test_original_type_set(self):
        """original_type matches the node component_type."""
        node = _make_node()
        result = _convert(node)
        assert result.component["original_type"] == "tOracleConnection"

    def test_id_set(self):
        """id matches the node component_id."""
        node = _make_node(component_id="tOracleConnection_42")
        result = _convert(node)
        assert result.component["id"] == "tOracleConnection_42"

    def test_tdb_connection_type_preserved(self):
        """tDBConnection original_type is preserved."""
        node = _make_node(component_type="tDBConnection", component_id="tDBConnection_1")
        result = _convert(node)
        assert result.component["original_type"] == "tDBConnection"
        assert result.component["id"] == "tDBConnection_1"

    def test_result_is_component_result(self):
        """Result is a ComponentResult instance."""
        node = _make_node()
        result = _convert(node)
        assert isinstance(result, ComponentResult)

    def test_no_warnings(self):
        """No warnings emitted (connection component has no validation warnings)."""
        node = _make_node()
        result = _convert(node)
        assert result.warnings == []

    def test_port_unquoted(self):
        """PORT without quotes is extracted as string."""
        node = _make_node(params={"PORT": "5432"})
        result = _convert(node)
        assert result.component["config"]["port"] == "5432"
