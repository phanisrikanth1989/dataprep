"""Tests for MSSqlInputConverter (tMSSqlInput -> No Engine Implementation)."""
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


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

def _make_node(params=None, schema=None, component_id="tMSSqlInput_1",
               component_type="tMSSqlInput"):
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
    converter = MSSqlInputConverter()
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
        """tMSSqlInput maps to MSSqlInputConverter in the registry."""
        assert REGISTRY.get("tMSSqlInput") is MSSqlInputConverter


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

    def test_driver_default(self):
        """DRIVER defaults to MSSQL_PROP."""
        result = _convert(_make_node())
        assert result.component["config"]["driver"] == "MSSQL_PROP"

    def test_host_default(self):
        """HOST defaults to empty string."""
        result = _convert(_make_node())
        assert result.component["config"]["host"] == ""

    def test_port_default(self):
        """PORT defaults to 1433 (standard MSSQL port)."""
        result = _convert(_make_node())
        assert result.component["config"]["port"] == "1433"

    def test_schema_db_default(self):
        """DB_SCHEMA -> schema_db defaults to empty string."""
        result = _convert(_make_node())
        assert result.component["config"]["schema_db"] == ""

    def test_dbname_default(self):
        """DBNAME defaults to empty string."""
        result = _convert(_make_node())
        assert result.component["config"]["dbname"] == ""

    def test_user_default(self):
        """USER defaults to empty string."""
        result = _convert(_make_node())
        assert result.component["config"]["user"] == ""

    def test_password_default(self):
        """PASS defaults to empty string."""
        result = _convert(_make_node())
        assert result.component["config"]["password"] == ""

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
        """PROPERTIES defaults to 'noDatetimeStringSync=true' (non-empty!)."""
        result = _convert(_make_node())
        assert result.component["config"]["properties"] == "noDatetimeStringSync=true"

    def test_active_dir_auth_default(self):
        """ACTIVE_DIR_AUTH defaults to False."""
        result = _convert(_make_node())
        assert result.component["config"]["active_dir_auth"] is False

    def test_encoding_default(self):
        """ENCODING defaults to ISO-8859-15 (not UTF-8)."""
        result = _convert(_make_node())
        assert result.component["config"]["encoding"] == "ISO-8859-15"

    def test_trim_all_column_default(self):
        """TRIM_ALL_COLUMN defaults to False."""
        result = _convert(_make_node())
        assert result.component["config"]["trim_all_column"] is False

    def test_trim_column_default(self):
        """TRIM_COLUMN defaults to empty list."""
        result = _convert(_make_node())
        assert result.component["config"]["trim_column"] == []

    def test_set_query_timeout_default(self):
        """SET_QUERY_TIMEOUT defaults to False."""
        result = _convert(_make_node())
        assert result.component["config"]["set_query_timeout"] is False

    def test_query_timeout_in_seconds_default(self):
        """QUERY_TIMEOUT_IN_SECONDS defaults to 30."""
        result = _convert(_make_node())
        assert result.component["config"]["query_timeout_in_seconds"] == 30


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
        node = _make_node(params={"CONNECTION": '"tMSSqlConnection_1"'})
        result = _convert(node)
        assert result.component["config"]["connection"] == "tMSSqlConnection_1"

    def test_driver_extracted(self):
        """DRIVER closed list value extracted."""
        node = _make_node(params={"DRIVER": '"JTDS_PROP"'})
        result = _convert(node)
        assert result.component["config"]["driver"] == "JTDS_PROP"

    def test_host_extracted(self):
        """HOST extracted from quoted value."""
        node = _make_node(params={"HOST": '"sql.example.com"'})
        result = _convert(node)
        assert result.component["config"]["host"] == "sql.example.com"

    def test_port_extracted(self):
        """PORT extracted as string."""
        node = _make_node(params={"PORT": '"2433"'})
        result = _convert(node)
        assert result.component["config"]["port"] == "2433"

    def test_schema_db_extracted(self):
        """DB_SCHEMA -> schema_db extracted."""
        node = _make_node(params={"DB_SCHEMA": '"dbo"'})
        result = _convert(node)
        assert result.component["config"]["schema_db"] == "dbo"

    def test_dbname_extracted(self):
        """DBNAME extracted."""
        node = _make_node(params={"DBNAME": '"AdventureWorks"'})
        result = _convert(node)
        assert result.component["config"]["dbname"] == "AdventureWorks"

    def test_user_extracted(self):
        """USER extracted."""
        node = _make_node(params={"USER": '"sa"'})
        result = _convert(node)
        assert result.component["config"]["user"] == "sa"

    def test_query_extracted(self):
        """QUERY extracted from memo field."""
        node = _make_node(params={"QUERY": '"SELECT * FROM dbo.Orders"'})
        result = _convert(node)
        assert result.component["config"]["query"] == "SELECT * FROM dbo.Orders"

    def test_host_port_extracted(self):
        """HOST and PORT extracted together."""
        node = _make_node(params={"HOST": '"db.example.com"', "PORT": '"1434"'})
        result = _convert(node)
        assert result.component["config"]["host"] == "db.example.com"
        assert result.component["config"]["port"] == "1434"

    def test_specify_datasource_alias_true(self):
        """SPECIFY_DATASOURCE_ALIAS extracted as True."""
        node = _make_node(params={"SPECIFY_DATASOURCE_ALIAS": "true"})
        result = _convert(node)
        assert result.component["config"]["specify_datasource_alias"] is True

    def test_datasource_alias_extracted(self):
        """DATASOURCE_ALIAS extracted."""
        node = _make_node(params={"DATASOURCE_ALIAS": '"myDatasource"'})
        result = _convert(node)
        assert result.component["config"]["datasource_alias"] == "myDatasource"

    def test_properties_extracted(self):
        """PROPERTIES extracted, overriding non-empty default."""
        node = _make_node(params={"PROPERTIES": '"encrypt=true;trustServerCertificate=false"'})
        result = _convert(node)
        assert result.component["config"]["properties"] == "encrypt=true;trustServerCertificate=false"

    def test_active_dir_auth_true(self):
        """ACTIVE_DIR_AUTH extracted as True."""
        node = _make_node(params={"ACTIVE_DIR_AUTH": "true"})
        result = _convert(node)
        assert result.component["config"]["active_dir_auth"] is True

    def test_encoding_extracted(self):
        """ENCODING extracted."""
        node = _make_node(params={"ENCODING": '"UTF-8"'})
        result = _convert(node)
        assert result.component["config"]["encoding"] == "UTF-8"

    def test_trim_all_column_true(self):
        """TRIM_ALL_COLUMN extracted as True."""
        node = _make_node(params={"TRIM_ALL_COLUMN": "true"})
        result = _convert(node)
        assert result.component["config"]["trim_all_column"] is True

    def test_set_query_timeout_true(self):
        """SET_QUERY_TIMEOUT extracted as True."""
        node = _make_node(params={"SET_QUERY_TIMEOUT": "true"})
        result = _convert(node)
        assert result.component["config"]["set_query_timeout"] is True

    def test_query_timeout_in_seconds_extracted(self):
        """QUERY_TIMEOUT_IN_SECONDS extracted as int."""
        node = _make_node(params={"QUERY_TIMEOUT_IN_SECONDS": "120"})
        result = _convert(node)
        assert result.component["config"]["query_timeout_in_seconds"] == 120


# ------------------------------------------------------------------
# Password Handling
# ------------------------------------------------------------------

class TestPasswordHandling:
    """Verify encrypted password prefix stripping."""

    def test_plain_password(self):
        """Quoted password extracted without quotes."""
        node = _make_node(params={"PASS": '"mypassword"'})
        result = _convert(node)
        assert result.component["config"]["password"] == "mypassword"

    def test_encrypted_password_prefix_stripped(self):
        """Encrypted prefix is stripped, leaving the encrypted value."""
        node = _make_node(params={"PASS": "enc:system.encryption.key.v1:aBcDeFgHiJk=="})
        result = _convert(node)
        assert result.component["config"]["password"] == "aBcDeFgHiJk=="

    def test_plain_unquoted_password(self):
        """Plain unquoted password passed through."""
        node = _make_node(params={"PASS": "plaintext"})
        result = _convert(node)
        assert result.component["config"]["password"] == "plaintext"

    def test_missing_password_defaults_to_empty(self):
        """Missing PASS defaults to empty string."""
        result = _convert(_make_node())
        assert result.component["config"]["password"] == ""

    def test_encrypted_prefix_with_empty_value(self):
        """Encrypted prefix with no trailing value yields empty string."""
        node = _make_node(params={"PASS": "enc:system.encryption.key.v1:"})
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
        """No FLOW schema produces empty input and output lists."""
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
        node = _make_node(component_id="tMSSqlInput_42")
        result = _convert(node)
        assert result.needs_review[0]["component"] == "tMSSqlInput_42"

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
        """All 20 config keys present in output."""
        node = _make_node(schema=_make_schema_columns())
        result = _convert(node)
        expected_keys = {
            "use_existing_connection", "connection",
            "driver", "host", "port", "schema_db",
            "dbname", "user", "password", "query",
            "specify_datasource_alias", "datasource_alias",
            "properties", "active_dir_auth", "encoding",
            "trim_all_column", "trim_column",
            "set_query_timeout", "query_timeout_in_seconds",
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


# ------------------------------------------------------------------
# Plan 14-11: password and TRIM_COLUMN parser branch coverage
# ------------------------------------------------------------------


class TestExtractPasswordEdges:
    """Cover line 124 (return str(raw) for non-string non-None PASS)."""

    def test_password_int_value_str_coerced(self):
        """PASS as int -> str(raw) (line 124)."""
        node = _make_node(params={"PASS": 12345})
        result = _convert(node)
        assert result.component["config"]["password"] == "12345"

    def test_password_list_value_str_coerced(self):
        """PASS as list -> str(raw) (line 124)."""
        node = _make_node(params={"PASS": ["a", "b"]})
        result = _convert(node)
        # str(['a', 'b']) -> "['a', 'b']"
        assert result.component["config"]["password"] == "['a', 'b']"

    def test_password_none_returns_empty(self):
        """PASS as None -> '' (line 116)."""
        node = _make_node(params={"PASS": None})
        result = _convert(node)
        assert result.component["config"]["password"] == ""

    def test_password_with_encrypted_prefix(self):
        """Encrypted PASS -> prefix stripped (line 117-118)."""
        node = _make_node(params={
            "PASS": "enc:system.encryption.key.v1:secret_payload",
        })
        result = _convert(node)
        assert result.component["config"]["password"] == "secret_payload"

    def test_password_quoted_string_unquoted(self):
        """PASS as a quoted string -> quotes stripped (lines 121-122)."""
        node = _make_node(params={"PASS": '"plaintext"'})
        result = _convert(node)
        assert result.component["config"]["password"] == "plaintext"

    def test_password_unquoted_string_returned_as_is(self):
        """PASS as an unquoted string -> returned as-is (line 123)."""
        node = _make_node(params={"PASS": "plain_no_quotes"})
        result = _convert(node)
        assert result.component["config"]["password"] == "plain_no_quotes"


class TestParseTrimColumnEdges:
    """Cover lines 139-149: TRIM_COLUMN list-with-dicts parser body."""

    def test_trim_column_with_dict_entries_parsed(self):
        """TRIM_COLUMN list of dicts -> list of {ref_lower: stripped_value}
        (lines 139-149)."""
        node = _make_node(params={
            "TRIM_COLUMN": [
                {"elementRef": "SCHEMA_COLUMN", "value": '"id"'},
                {"elementRef": "TRIM", "value": "true"},
            ],
        })
        result = _convert(node)
        trim_col = result.component["config"]["trim_column"]
        assert isinstance(trim_col, list)
        assert len(trim_col) == 2
        # ref is lowercased; value is quote-stripped if it was a quoted string
        assert trim_col[0] == {"schema_column": "id"}
        assert trim_col[1] == {"trim": "true"}

    def test_trim_column_with_non_string_value_passed_through(self):
        """TRIM_COLUMN dict entry whose value is non-str is stored as-is (line 146)."""
        node = _make_node(params={
            "TRIM_COLUMN": [
                {"elementRef": "TRIM", "value": True},  # bool, not str
            ],
        })
        result = _convert(node)
        trim_col = result.component["config"]["trim_column"]
        assert len(trim_col) == 1
        assert trim_col[0] == {"trim": True}

    def test_trim_column_with_empty_ref_skipped(self):
        """TRIM_COLUMN entry with empty elementRef -> empty row -> not appended
        (line 145 conditional)."""
        node = _make_node(params={
            "TRIM_COLUMN": [
                {"elementRef": "", "value": "x"},  # empty ref
            ],
        })
        result = _convert(node)
        trim_col = result.component["config"]["trim_column"]
        # Empty ref -> row is {} -> not appended
        assert trim_col == []

    def test_trim_column_with_non_dict_entry_skipped(self):
        """A non-dict entry in TRIM_COLUMN raw is silently skipped (line 141)."""
        node = _make_node(params={
            "TRIM_COLUMN": [
                "not_a_dict",  # skipped (line 141 isinstance check)
                {"elementRef": "TRIM", "value": "false"},
            ],
        })
        result = _convert(node)
        trim_col = result.component["config"]["trim_column"]
        assert len(trim_col) == 1
        assert trim_col[0] == {"trim": "false"}
