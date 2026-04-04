"""Tests for UniqueRowConverter (tUniqueRow/tUniqRow/tUnqRow -> v1 unique row config)."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.aggregate.unique_row import (
    UniqueRowConverter,
)
from src.converters.talend_to_v1.components.registry import REGISTRY


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

def _make_node(params=None, schema=None, component_id="ur_1",
               component_type="tUniqueRow"):
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
            SchemaColumn(name="amount", type="id_Double", nullable=True),
        ]
    }


def _make_unique_key_data(rows):
    """Generate UNIQUE_KEY TABLE data with stride-3 per row.

    rows: list of (column_name, is_key_str, case_sensitive_str) tuples.
    Each row produces 3 elementValue entries: SCHEMA_COLUMN, KEY_ATTRIBUTE, CASE_SENSITIVE.
    """
    result = []
    for col_name, is_key, case_sensitive in rows:
        result.append({"elementRef": "SCHEMA_COLUMN", "value": f'"{col_name}"'})
        result.append({"elementRef": "KEY_ATTRIBUTE", "value": is_key})
        result.append({"elementRef": "CASE_SENSITIVE", "value": case_sensitive})
    return result


# ------------------------------------------------------------------
# TestRegistration
# ------------------------------------------------------------------

class TestRegistration:
    """Verify component is registered correctly under all 3 aliases."""

    def test_registered_as_tuniquerow(self):
        assert REGISTRY.get("tUniqueRow") is UniqueRowConverter

    def test_registered_as_tuniqrow(self):
        assert REGISTRY.get("tUniqRow") is UniqueRowConverter

    def test_registered_as_tunqrow(self):
        assert REGISTRY.get("tUnqRow") is UniqueRowConverter


# ------------------------------------------------------------------
# TestDefaults
# ------------------------------------------------------------------

class TestDefaults:
    """Verify all parameters have correct defaults when no params provided."""

    def test_key_columns_default_empty(self):
        node = _make_node()
        result = UniqueRowConverter().convert(node, [], {})
        assert result.component["config"]["key_columns"] == []

    def test_keep_default_first(self):
        node = _make_node()
        result = UniqueRowConverter().convert(node, [], {})
        assert result.component["config"]["keep"] == "first"

    def test_case_sensitive_default_true(self):
        node = _make_node()
        result = UniqueRowConverter().convert(node, [], {})
        assert result.component["config"]["case_sensitive"] is True

    def test_only_once_each_duplicated_key_default_false(self):
        node = _make_node()
        result = UniqueRowConverter().convert(node, [], {})
        assert result.component["config"]["only_once_each_duplicated_key"] is False

    def test_is_virtual_component_default_false(self):
        node = _make_node()
        result = UniqueRowConverter().convert(node, [], {})
        assert result.component["config"]["is_virtual_component"] is False

    def test_buffer_size_default_m(self):
        node = _make_node()
        result = UniqueRowConverter().convert(node, [], {})
        assert result.component["config"]["buffer_size"] == "M"

    def test_temp_directory_default_empty(self):
        node = _make_node()
        result = UniqueRowConverter().convert(node, [], {})
        assert result.component["config"]["temp_directory"] == ""

    def test_change_hash_and_equals_default_false(self):
        node = _make_node()
        result = UniqueRowConverter().convert(node, [], {})
        assert result.component["config"]["change_hash_and_equals_for_bigdecimal"] is False

    def test_connection_format_default_row(self):
        node = _make_node()
        result = UniqueRowConverter().convert(node, [], {})
        assert result.component["config"]["connection_format"] == "row"


# ------------------------------------------------------------------
# TestParameterExtraction
# ------------------------------------------------------------------

class TestParameterExtraction:
    """Verify each parameter is correctly extracted from XML params."""

    def test_only_once_each_duplicated_key_true(self):
        node = _make_node(params={"ONLY_ONCE_EACH_DUPLICATED_KEY": "true"})
        result = UniqueRowConverter().convert(node, [], {})
        assert result.component["config"]["only_once_each_duplicated_key"] is True
        assert result.component["config"]["keep"] == "last"

    def test_only_once_each_duplicated_key_false(self):
        node = _make_node(params={"ONLY_ONCE_EACH_DUPLICATED_KEY": "false"})
        result = UniqueRowConverter().convert(node, [], {})
        assert result.component["config"]["only_once_each_duplicated_key"] is False
        assert result.component["config"]["keep"] == "first"

    def test_is_virtual_component_true(self):
        node = _make_node(params={"IS_VIRTUAL_COMPONENT": "true"})
        result = UniqueRowConverter().convert(node, [], {})
        assert result.component["config"]["is_virtual_component"] is True

    def test_buffer_size_extracted(self):
        node = _make_node(params={"BUFFER_SIZE": "B"})
        result = UniqueRowConverter().convert(node, [], {})
        assert result.component["config"]["buffer_size"] == "B"

    def test_buffer_size_small(self):
        node = _make_node(params={"BUFFER_SIZE": "S"})
        result = UniqueRowConverter().convert(node, [], {})
        assert result.component["config"]["buffer_size"] == "S"

    def test_temp_directory_extracted(self):
        node = _make_node(params={"TEMP_DIRECTORY": '"/tmp"'})
        result = UniqueRowConverter().convert(node, [], {})
        assert result.component["config"]["temp_directory"] == "/tmp"

    def test_change_hash_true(self):
        node = _make_node(params={"CHANGE_HASH_AND_EQUALS_FOR_BIGDECIMAL": "true"})
        result = UniqueRowConverter().convert(node, [], {})
        assert result.component["config"]["change_hash_and_equals_for_bigdecimal"] is True

    def test_connection_format_table(self):
        node = _make_node(params={"CONNECTION_FORMAT": '"table"'})
        result = UniqueRowConverter().convert(node, [], {})
        assert result.component["config"]["connection_format"] == "table"


# ------------------------------------------------------------------
# TestTableParsing (UNIQUE_KEY)
# ------------------------------------------------------------------

class TestTableParsing:
    """Verify UNIQUE_KEY TABLE parameter parsing with stride-3."""

    def test_unique_key_table_parsed(self):
        """Single key column parsed correctly."""
        data = _make_unique_key_data([("id", "true", "true")])
        node = _make_node(params={"UNIQUE_KEY": data})
        result = UniqueRowConverter().convert(node, [], {})
        keys = result.component["config"]["key_columns"]
        assert len(keys) == 1
        assert keys[0] == {"column": "id", "case_sensitive": True}

    def test_unique_key_multiple_columns(self):
        """Multiple key columns parsed correctly."""
        data = _make_unique_key_data([
            ("id", "true", "true"),
            ("name", "true", "false"),
        ])
        node = _make_node(params={"UNIQUE_KEY": data})
        result = UniqueRowConverter().convert(node, [], {})
        keys = result.component["config"]["key_columns"]
        assert len(keys) == 2
        assert keys[0] == {"column": "id", "case_sensitive": True}
        assert keys[1] == {"column": "name", "case_sensitive": False}

    def test_unique_key_empty_when_missing(self):
        """No UNIQUE_KEY param -> empty key_columns."""
        node = _make_node()
        result = UniqueRowConverter().convert(node, [], {})
        assert result.component["config"]["key_columns"] == []

    def test_unique_key_non_key_columns_excluded(self):
        """Columns with KEY_ATTRIBUTE=false are excluded from key_columns."""
        data = _make_unique_key_data([
            ("id", "true", "true"),
            ("name", "false", "true"),
            ("amount", "true", "false"),
        ])
        node = _make_node(params={"UNIQUE_KEY": data})
        result = UniqueRowConverter().convert(node, [], {})
        keys = result.component["config"]["key_columns"]
        assert len(keys) == 2
        assert keys[0]["column"] == "id"
        assert keys[1]["column"] == "amount"

    def test_unique_key_case_sensitive_per_column(self):
        """Each key column can have independent case_sensitive value."""
        data = _make_unique_key_data([
            ("id", "true", "true"),
            ("name", "true", "false"),
        ])
        node = _make_node(params={"UNIQUE_KEY": data})
        result = UniqueRowConverter().convert(node, [], {})
        keys = result.component["config"]["key_columns"]
        assert keys[0]["case_sensitive"] is True
        assert keys[1]["case_sensitive"] is False

    def test_unique_key_values_strip_quotes(self):
        """Column names have surrounding quotes stripped."""
        data = [
            {"elementRef": "SCHEMA_COLUMN", "value": '"quoted_name"'},
            {"elementRef": "KEY_ATTRIBUTE", "value": "true"},
            {"elementRef": "CASE_SENSITIVE", "value": "true"},
        ]
        node = _make_node(params={"UNIQUE_KEY": data})
        result = UniqueRowConverter().convert(node, [], {})
        assert result.component["config"]["key_columns"][0]["column"] == "quoted_name"

    def test_unique_key_incomplete_group_skipped(self):
        """Incomplete trailing group (< 3 entries) is skipped."""
        data = _make_unique_key_data([("id", "true", "true")])
        # Add incomplete group
        data.append({"elementRef": "SCHEMA_COLUMN", "value": '"orphan"'})
        data.append({"elementRef": "KEY_ATTRIBUTE", "value": "true"})
        node = _make_node(params={"UNIQUE_KEY": data})
        result = UniqueRowConverter().convert(node, [], {})
        assert len(result.component["config"]["key_columns"]) == 1

    def test_unique_key_not_a_list_warning(self):
        """Non-list UNIQUE_KEY produces warning."""
        node = _make_node(params={"UNIQUE_KEY": "not_a_list"})
        result = UniqueRowConverter().convert(node, [], {})
        assert result.component["config"]["key_columns"] == []
        assert any("not a list" in w for w in result.warnings)


# ------------------------------------------------------------------
# TestFrameworkParams
# ------------------------------------------------------------------

class TestFrameworkParams:
    """Verify tstatcatcher_stats and label extraction."""

    def test_tstatcatcher_stats_default_false(self):
        node = _make_node()
        result = UniqueRowConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is False

    def test_tstatcatcher_stats_true(self):
        node = _make_node(params={"TSTATCATCHER_STATS": "true"})
        result = UniqueRowConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is True

    def test_label_default_empty(self):
        node = _make_node()
        result = UniqueRowConverter().convert(node, [], {})
        assert result.component["config"]["label"] == ""

    def test_label_extracted(self):
        node = _make_node(params={"LABEL": '"my_label"'})
        result = UniqueRowConverter().convert(node, [], {})
        assert result.component["config"]["label"] == "my_label"


# ------------------------------------------------------------------
# TestSchema
# ------------------------------------------------------------------

class TestSchema:
    """Verify schema extraction."""

    def test_schema_extracted(self):
        node = _make_node(schema=_make_schema_columns())
        result = UniqueRowConverter().convert(node, [], {})
        schema = result.component["schema"]
        assert "input" in schema
        assert "output" in schema
        assert schema["input"] == schema["output"]
        assert len(schema["input"]) == 3
        assert schema["input"][0]["name"] == "id"

    def test_empty_schema(self):
        node = _make_node()
        result = UniqueRowConverter().convert(node, [], {})
        schema = result.component["schema"]
        assert schema == {"input": [], "output": []}


# ------------------------------------------------------------------
# TestNeedsReview
# ------------------------------------------------------------------

class TestNeedsReview:
    """Verify needs_review entries for engine gaps."""

    def test_needs_review_count(self):
        """Default params produce per-feature engine gap entries."""
        node = _make_node()
        result = UniqueRowConverter().convert(node, [], {})
        # Per-column case sensitivity, IS_VIRTUAL_COMPONENT, only_once approximation
        assert len(result.needs_review) >= 3

    def test_needs_review_severity_engine_gap(self):
        node = _make_node()
        result = UniqueRowConverter().convert(node, [], {})
        for entry in result.needs_review:
            assert entry["severity"] == "engine_gap"

    def test_needs_review_has_component_id(self):
        node = _make_node(component_id="test_comp")
        result = UniqueRowConverter().convert(node, [], {})
        for entry in result.needs_review:
            assert entry["component"] == "test_comp"

    def test_no_framework_param_needs_review(self):
        """Framework params (tstatcatcher_stats, label) must NOT have needs_review."""
        node = _make_node()
        result = UniqueRowConverter().convert(node, [], {})
        issues = [e["issue"] for e in result.needs_review]
        for issue in issues:
            assert "tstatcatcher_stats" not in issue
            assert "label" not in issue.lower().split()

    def test_change_hash_true_adds_needs_review(self):
        """CHANGE_HASH_AND_EQUALS_FOR_BIGDECIMAL=true adds conditional needs_review."""
        node = _make_node(params={"CHANGE_HASH_AND_EQUALS_FOR_BIGDECIMAL": "true"})
        result = UniqueRowConverter().convert(node, [], {})
        hash_entries = [
            nr for nr in result.needs_review
            if "CHANGE_HASH_AND_EQUALS_FOR_BIGDECIMAL" in nr["issue"]
        ]
        assert len(hash_entries) == 1

    def test_mixed_case_sensitivity_adds_needs_review(self):
        """Mixed per-column CASE_SENSITIVE triggers needs_review."""
        data = _make_unique_key_data([
            ("id", "true", "true"),
            ("name", "true", "false"),
        ])
        node = _make_node(params={"UNIQUE_KEY": data})
        result = UniqueRowConverter().convert(node, [], {})
        mixed_entries = [
            nr for nr in result.needs_review
            if "Mixed per-column CASE_SENSITIVE" in nr["issue"]
        ]
        assert len(mixed_entries) == 1


# ------------------------------------------------------------------
# TestCompleteness
# ------------------------------------------------------------------

class TestCompleteness:
    """Verify all expected config keys are present."""

    def test_all_config_keys_present(self):
        node = _make_node(schema=_make_schema_columns())
        result = UniqueRowConverter().convert(node, [], {})
        expected_keys = {
            "key_columns", "keep", "case_sensitive",
            "only_once_each_duplicated_key",
            "is_virtual_component", "buffer_size", "temp_directory",
            "change_hash_and_equals_for_bigdecimal",
            "connection_format",
            "tstatcatcher_stats", "label",
        }
        actual_keys = set(result.component["config"].keys())
        missing = expected_keys - actual_keys
        assert not missing, f"Missing config keys: {missing}"


# ------------------------------------------------------------------
# TestPhantomParams
# ------------------------------------------------------------------

class TestPhantomParams:
    """Verify phantom params documented but extracted."""

    def test_connection_format_not_in_java_xml(self):
        """CONNECTION_FORMAT is extracted but documented as phantom (not in _java.xml)."""
        node = _make_node(params={"CONNECTION_FORMAT": '"table"'})
        result = UniqueRowConverter().convert(node, [], {})
        # It IS extracted (phantom = present in .item but not _java.xml)
        assert result.component["config"]["connection_format"] == "table"
