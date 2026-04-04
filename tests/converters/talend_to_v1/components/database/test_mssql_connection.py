"""Tests for MSSqlConnectionConverter (tMSSqlConnection -> v1 MSSQL connection config)."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.database.mssql_connection import (
    MSSqlConnectionConverter,
)
from src.converters.talend_to_v1.components.registry import REGISTRY


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

def _make_node(params=None, schema=None, component_id="msc_1",
               component_type="tMSSqlConnection"):
    """Create a TalendNode for tMSSqlConnection testing."""
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


# ------------------------------------------------------------------
# TestRegistration
# ------------------------------------------------------------------

class TestRegistration:
    """Verify component is registered correctly."""

    def test_registered_in_registry(self):
        assert REGISTRY.get("tMSSqlConnection") is MSSqlConnectionConverter


# ------------------------------------------------------------------
# TestDefaults
# ------------------------------------------------------------------

class TestDefaults:
    """Verify all parameters have correct defaults when no params provided."""

    def test_driver_default(self):
        node = _make_node()
        result = MSSqlConnectionConverter().convert(node, [], {})
        assert result.component["config"]["driver"] == "MSSQL_PROP"

    def test_host_default(self):
        node = _make_node()
        result = MSSqlConnectionConverter().convert(node, [], {})
        assert result.component["config"]["host"] == ""

    def test_port_default(self):
        """PORT defaults to '1433' (MSSQL default, NOT 1521 Oracle)."""
        node = _make_node()
        result = MSSqlConnectionConverter().convert(node, [], {})
        assert result.component["config"]["port"] == "1433"

    def test_schema_db_default(self):
        node = _make_node()
        result = MSSqlConnectionConverter().convert(node, [], {})
        assert result.component["config"]["schema_db"] == ""

    def test_dbname_default(self):
        node = _make_node()
        result = MSSqlConnectionConverter().convert(node, [], {})
        assert result.component["config"]["dbname"] == ""

    def test_user_default(self):
        node = _make_node()
        result = MSSqlConnectionConverter().convert(node, [], {})
        assert result.component["config"]["user"] == ""

    def test_password_default(self):
        node = _make_node()
        result = MSSqlConnectionConverter().convert(node, [], {})
        assert result.component["config"]["password"] == ""

    def test_encoding_default(self):
        node = _make_node()
        result = MSSqlConnectionConverter().convert(node, [], {})
        assert result.component["config"]["encoding"] == "ISO-8859-15"

    def test_properties_default(self):
        node = _make_node()
        result = MSSqlConnectionConverter().convert(node, [], {})
        assert result.component["config"]["properties"] == ""

    def test_use_shared_connection_default(self):
        node = _make_node()
        result = MSSqlConnectionConverter().convert(node, [], {})
        assert result.component["config"]["use_shared_connection"] is False

    def test_shared_connection_name_default(self):
        node = _make_node()
        result = MSSqlConnectionConverter().convert(node, [], {})
        assert result.component["config"]["shared_connection_name"] == ""

    def test_specify_datasource_alias_default(self):
        node = _make_node()
        result = MSSqlConnectionConverter().convert(node, [], {})
        assert result.component["config"]["specify_datasource_alias"] is False

    def test_datasource_alias_default(self):
        node = _make_node()
        result = MSSqlConnectionConverter().convert(node, [], {})
        assert result.component["config"]["datasource_alias"] == ""

    def test_active_dir_auth_default(self):
        node = _make_node()
        result = MSSqlConnectionConverter().convert(node, [], {})
        assert result.component["config"]["active_dir_auth"] is False

    def test_auto_commit_default(self):
        node = _make_node()
        result = MSSqlConnectionConverter().convert(node, [], {})
        assert result.component["config"]["auto_commit"] is False

    def test_share_identity_setting_default(self):
        node = _make_node()
        result = MSSqlConnectionConverter().convert(node, [], {})
        assert result.component["config"]["share_identity_setting"] is False


# ------------------------------------------------------------------
# TestParameterExtraction
# ------------------------------------------------------------------

class TestParameterExtraction:
    """Verify each parameter is correctly extracted from XML params."""

    def test_host_extracted(self):
        node = _make_node(params={"HOST": '"sql.example.com"'})
        result = MSSqlConnectionConverter().convert(node, [], {})
        assert result.component["config"]["host"] == "sql.example.com"

    def test_port_extracted(self):
        node = _make_node(params={"PORT": '"5433"'})
        result = MSSqlConnectionConverter().convert(node, [], {})
        assert result.component["config"]["port"] == "5433"

    def test_dbname_extracted(self):
        node = _make_node(params={"DBNAME": '"AdventureWorks"'})
        result = MSSqlConnectionConverter().convert(node, [], {})
        assert result.component["config"]["dbname"] == "AdventureWorks"

    def test_driver_jtds(self):
        node = _make_node(params={"DRIVER": '"JTDS"'})
        result = MSSqlConnectionConverter().convert(node, [], {})
        assert result.component["config"]["driver"] == "JTDS"

    def test_schema_db_extracted(self):
        node = _make_node(params={"SCHEMA_DB": '"dbo"'})
        result = MSSqlConnectionConverter().convert(node, [], {})
        assert result.component["config"]["schema_db"] == "dbo"

    def test_user_extracted(self):
        node = _make_node(params={"USER": '"sa"'})
        result = MSSqlConnectionConverter().convert(node, [], {})
        assert result.component["config"]["user"] == "sa"

    def test_encoding_extracted(self):
        node = _make_node(params={"ENCODING": '"UTF-8"'})
        result = MSSqlConnectionConverter().convert(node, [], {})
        assert result.component["config"]["encoding"] == "UTF-8"

    def test_properties_extracted(self):
        node = _make_node(params={"PROPERTIES": '"encrypt=true;trustServerCertificate=false"'})
        result = MSSqlConnectionConverter().convert(node, [], {})
        assert result.component["config"]["properties"] == "encrypt=true;trustServerCertificate=false"

    def test_use_shared_connection_true(self):
        node = _make_node(params={"USE_SHARED_CONNECTION": "true"})
        result = MSSqlConnectionConverter().convert(node, [], {})
        assert result.component["config"]["use_shared_connection"] is True

    def test_shared_connection_name_extracted(self):
        node = _make_node(params={"SHARED_CONNECTION_NAME": '"sharedMssql"'})
        result = MSSqlConnectionConverter().convert(node, [], {})
        assert result.component["config"]["shared_connection_name"] == "sharedMssql"

    def test_specify_datasource_alias_true(self):
        node = _make_node(params={"SPECIFY_DATASOURCE_ALIAS": "true"})
        result = MSSqlConnectionConverter().convert(node, [], {})
        assert result.component["config"]["specify_datasource_alias"] is True

    def test_datasource_alias_extracted(self):
        node = _make_node(params={"DATASOURCE_ALIAS": '"jdbc/mssqlDS"'})
        result = MSSqlConnectionConverter().convert(node, [], {})
        assert result.component["config"]["datasource_alias"] == "jdbc/mssqlDS"

    def test_active_dir_auth_true(self):
        node = _make_node(params={"ACTIVE_DIR_AUTH": "true"})
        result = MSSqlConnectionConverter().convert(node, [], {})
        assert result.component["config"]["active_dir_auth"] is True

    def test_auto_commit_true(self):
        node = _make_node(params={"AUTO_COMMIT": "true"})
        result = MSSqlConnectionConverter().convert(node, [], {})
        assert result.component["config"]["auto_commit"] is True

    def test_share_identity_setting_true(self):
        node = _make_node(params={"SHARE_IDENTITY_SETTING": "true"})
        result = MSSqlConnectionConverter().convert(node, [], {})
        assert result.component["config"]["share_identity_setting"] is True


# ------------------------------------------------------------------
# TestPasswordHandling
# ------------------------------------------------------------------

class TestPasswordHandling:
    """Test password extraction including encrypted prefix stripping."""

    def test_plain_password(self):
        """Plain quoted password extracted normally."""
        node = _make_node(params={"PASS": '"secret"'})
        result = MSSqlConnectionConverter().convert(node, [], {})
        assert result.component["config"]["password"] == "secret"

    def test_encrypted_password_prefix_stripped(self):
        """Encrypted prefix enc:system.encryption.key.v1: is stripped."""
        node = _make_node(params={"PASS": "enc:system.encryption.key.v1:aBcDeFgHiJk=="})
        result = MSSqlConnectionConverter().convert(node, [], {})
        assert result.component["config"]["password"] == "aBcDeFgHiJk=="

    def test_empty_password(self):
        """Missing PASS defaults to empty string."""
        node = _make_node()
        result = MSSqlConnectionConverter().convert(node, [], {})
        assert result.component["config"]["password"] == ""

    def test_encrypted_prefix_with_empty_value(self):
        """Encrypted prefix with no value after it returns empty string."""
        node = _make_node(params={"PASS": "enc:system.encryption.key.v1:"})
        result = MSSqlConnectionConverter().convert(node, [], {})
        assert result.component["config"]["password"] == ""

    def test_unquoted_plain_password(self):
        """Unquoted plain password passed through."""
        node = _make_node(params={"PASS": "plaintext"})
        result = MSSqlConnectionConverter().convert(node, [], {})
        assert result.component["config"]["password"] == "plaintext"


# ------------------------------------------------------------------
# TestFrameworkParams
# ------------------------------------------------------------------

class TestFrameworkParams:
    """Verify tstatcatcher_stats and label extraction."""

    def test_tstatcatcher_stats_default_false(self):
        node = _make_node()
        result = MSSqlConnectionConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is False

    def test_tstatcatcher_stats_true(self):
        node = _make_node(params={"TSTATCATCHER_STATS": "true"})
        result = MSSqlConnectionConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is True

    def test_label_default_empty(self):
        node = _make_node()
        result = MSSqlConnectionConverter().convert(node, [], {})
        assert result.component["config"]["label"] == ""

    def test_label_extracted(self):
        node = _make_node(params={"LABEL": '"my_label"'})
        result = MSSqlConnectionConverter().convert(node, [], {})
        assert result.component["config"]["label"] == "my_label"


# ------------------------------------------------------------------
# TestSchema
# ------------------------------------------------------------------

class TestSchema:
    """Verify schema extraction."""

    def test_schema_extracted(self):
        node = _make_node(schema=_make_schema_columns())
        result = MSSqlConnectionConverter().convert(node, [], {})
        assert "schema" in result.component
        schema = result.component["schema"]
        assert isinstance(schema, dict)
        assert "input" in schema
        assert "output" in schema


# ------------------------------------------------------------------
# TestNeedsReview
# ------------------------------------------------------------------

class TestNeedsReview:
    """Verify needs_review entries for engine gaps."""

    def test_needs_review_count(self):
        """Single consolidated needs_review per D-27."""
        node = _make_node()
        result = MSSqlConnectionConverter().convert(node, [], {})
        assert len(result.needs_review) == 1

    def test_needs_review_is_engine_gap(self):
        node = _make_node()
        result = MSSqlConnectionConverter().convert(node, [], {})
        assert result.needs_review[0]["severity"] == "engine_gap"

    def test_needs_review_has_component_id(self):
        node = _make_node(component_id="test_comp")
        result = MSSqlConnectionConverter().convert(node, [], {})
        assert result.needs_review[0]["component"] == "test_comp"

    def test_no_framework_param_needs_review(self):
        """Framework params (tstatcatcher_stats, label) must NOT have needs_review."""
        node = _make_node()
        result = MSSqlConnectionConverter().convert(node, [], {})
        issues = [e["issue"] for e in result.needs_review]
        for issue in issues:
            assert "tstatcatcher_stats" not in issue
            assert "label" not in issue.lower().split()


# ------------------------------------------------------------------
# TestCompleteness
# ------------------------------------------------------------------

class TestCompleteness:
    """Verify all expected config keys are present."""

    def test_all_top_level_keys_present(self):
        node = _make_node(schema=_make_schema_columns())
        result = MSSqlConnectionConverter().convert(node, [], {})
        expected_top_keys = {"id", "type", "original_type", "position", "config", "schema", "inputs", "outputs"}
        actual_keys = set(result.component.keys())
        missing = expected_top_keys - actual_keys
        assert not missing, f"Missing top-level keys: {missing}"

    def test_all_config_keys_present(self):
        node = _make_node(schema=_make_schema_columns())
        result = MSSqlConnectionConverter().convert(node, [], {})
        expected_config_keys = {
            "driver",
            "host",
            "port",
            "schema_db",
            "dbname",
            "user",
            "password",
            "encoding",
            "properties",
            "use_shared_connection",
            "shared_connection_name",
            "specify_datasource_alias",
            "datasource_alias",
            "active_dir_auth",
            "auto_commit",
            "share_identity_setting",
            "tstatcatcher_stats",
            "label",
        }
        actual_keys = set(result.component["config"].keys())
        missing = expected_config_keys - actual_keys
        assert not missing, f"Missing config keys: {missing}"

    def test_no_extra_config_keys(self):
        """No unexpected keys in the config output."""
        node = _make_node()
        result = MSSqlConnectionConverter().convert(node, [], {})
        expected_config_keys = {
            "driver",
            "host",
            "port",
            "schema_db",
            "dbname",
            "user",
            "password",
            "encoding",
            "properties",
            "use_shared_connection",
            "shared_connection_name",
            "specify_datasource_alias",
            "datasource_alias",
            "active_dir_auth",
            "auto_commit",
            "share_identity_setting",
            "tstatcatcher_stats",
            "label",
        }
        actual_keys = set(result.component["config"].keys())
        extra = actual_keys - expected_config_keys
        assert not extra, f"Extra config keys: {extra}"
