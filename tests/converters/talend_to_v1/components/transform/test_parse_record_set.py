"""Tests for ParseRecordSetConverter (tParseRecordSet -> v1 tParseRecordSet config)."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.transform.parse_record_set import (
    ParseRecordSetConverter,
)
from src.converters.talend_to_v1.components.registry import REGISTRY


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


def _make_node(params=None, schema=None, component_id="prs_1",
               component_type="tParseRecordSet"):
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
            SchemaColumn(name="recordset", type="id_String", nullable=False, key=True, length=10),
            SchemaColumn(name="attr1", type="id_String", nullable=True, length=50),
            SchemaColumn(name="attr2", type="id_Integer", nullable=True),
        ]
    }


def _make_attribute_table(*values):
    """Generate ATTRIBUTE_TABLE data with stride-1 (VALUE only per schema).

    values: list of quoted attribute name strings
    """
    result = []
    for v in values:
        result.append({"elementRef": "VALUE", "value": v})
    return result


# ------------------------------------------------------------------
# Test Classes
# ------------------------------------------------------------------


class TestRegistration:
    """Verify component is registered correctly."""

    def test_registered_in_registry(self):
        assert REGISTRY.get("tParseRecordSet") is ParseRecordSetConverter


class TestDefaults:
    """Verify all parameters have correct defaults when no params provided."""

    def test_recordset_field_default_empty(self):
        node = _make_node()
        result = ParseRecordSetConverter().convert(node, [], {})
        assert result.component["config"]["recordset_field"] == ""

    def test_attribute_table_default_empty(self):
        node = _make_node()
        result = ParseRecordSetConverter().convert(node, [], {})
        assert result.component["config"]["attribute_table"] == []

    def test_tstatcatcher_stats_default_false(self):
        node = _make_node()
        result = ParseRecordSetConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is False

    def test_label_default_empty(self):
        node = _make_node()
        result = ParseRecordSetConverter().convert(node, [], {})
        assert result.component["config"]["label"] == ""


class TestParameterExtraction:
    """Verify each parameter is correctly extracted from XML params."""

    def test_recordset_field_custom(self):
        """RECORDSET_FIELD='"myField"' -> 'myField'."""
        node = _make_node(params={"RECORDSET_FIELD": '"myField"'})
        result = ParseRecordSetConverter().convert(node, [], {})
        assert result.component["config"]["recordset_field"] == "myField"

    def test_attribute_table_parsing(self):
        """ATTRIBUTE_TABLE stride-1 with VALUE entries -> list of strings."""
        table = _make_attribute_table('"col_a"', '"col_b"', '"col_c"')
        node = _make_node(params={"ATTRIBUTE_TABLE": table})
        result = ParseRecordSetConverter().convert(node, [], {})
        assert result.component["config"]["attribute_table"] == ["col_a", "col_b", "col_c"]

    def test_attribute_table_single_entry(self):
        table = _make_attribute_table('"only_one"')
        node = _make_node(params={"ATTRIBUTE_TABLE": table})
        result = ParseRecordSetConverter().convert(node, [], {})
        assert result.component["config"]["attribute_table"] == ["only_one"]

    def test_attribute_table_empty_value_skipped(self):
        """Entries with empty value should be skipped."""
        table = [
            {"elementRef": "VALUE", "value": '"good"'},
            {"elementRef": "VALUE", "value": ""},
            {"elementRef": "VALUE", "value": '"also_good"'},
        ]
        node = _make_node(params={"ATTRIBUTE_TABLE": table})
        result = ParseRecordSetConverter().convert(node, [], {})
        assert result.component["config"]["attribute_table"] == ["good", "also_good"]

    def test_attribute_table_non_dict_entries_skipped(self):
        """Non-dict entries in the table should be skipped gracefully."""
        table = [
            {"elementRef": "VALUE", "value": '"valid"'},
            "not_a_dict",
            42,
            {"elementRef": "VALUE", "value": '"another_valid"'},
        ]
        node = _make_node(params={"ATTRIBUTE_TABLE": table})
        result = ParseRecordSetConverter().convert(node, [], {})
        assert result.component["config"]["attribute_table"] == ["valid", "another_valid"]

    def test_attribute_table_missing(self):
        """Missing ATTRIBUTE_TABLE -> empty list."""
        node = _make_node(params={"RECORDSET_FIELD": '"rs"'})
        result = ParseRecordSetConverter().convert(node, [], {})
        assert result.component["config"]["attribute_table"] == []

    def test_attribute_table_not_a_list(self):
        """Non-list ATTRIBUTE_TABLE -> empty list."""
        node = _make_node(params={"ATTRIBUTE_TABLE": "not_a_list"})
        result = ParseRecordSetConverter().convert(node, [], {})
        assert result.component["config"]["attribute_table"] == []


class TestFrameworkParams:
    """Verify tstatcatcher_stats and label extraction."""

    def test_tstatcatcher_stats_true(self):
        node = _make_node(params={"TSTATCATCHER_STATS": "true"})
        result = ParseRecordSetConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is True

    def test_label_extracted(self):
        node = _make_node(params={"LABEL": '"my_label"'})
        result = ParseRecordSetConverter().convert(node, [], {})
        assert result.component["config"]["label"] == "my_label"


class TestSchema:
    """Verify schema extraction."""

    def test_schema_passthrough(self):
        """Transform component: input == output."""
        node = _make_node(schema=_make_schema_columns())
        result = ParseRecordSetConverter().convert(node, [], {})
        schema = result.component["schema"]
        assert schema["input"] == schema["output"]

    def test_schema_columns_populated(self):
        """Schema columns are properly populated from FLOW schema."""
        node = _make_node(schema=_make_schema_columns())
        result = ParseRecordSetConverter().convert(node, [], {})
        schema = result.component["schema"]
        assert len(schema["input"]) == 3
        assert schema["input"][0]["name"] == "recordset"
        assert schema["input"][1]["name"] == "attr1"
        assert schema["input"][2]["name"] == "attr2"

    def test_empty_schema(self):
        node = _make_node()
        result = ParseRecordSetConverter().convert(node, [], {})
        schema = result.component["schema"]
        assert schema == {"input": [], "output": []}


class TestNeedsReview:
    """Verify needs_review entries for engine gaps."""

    def test_needs_review_count(self):
        """Single consolidated needs_review per D-27 (no engine)."""
        node = _make_node()
        result = ParseRecordSetConverter().convert(node, [], {})
        assert len(result.needs_review) == 1

    def test_needs_review_no_engine(self):
        """needs_review mentions no v1 engine implementation."""
        node = _make_node()
        result = ParseRecordSetConverter().convert(node, [], {})
        assert "No v1 engine implementation" in result.needs_review[0]["issue"]

    def test_needs_review_severity(self):
        node = _make_node()
        result = ParseRecordSetConverter().convert(node, [], {})
        assert result.needs_review[0]["severity"] == "engine_gap"

    def test_needs_review_has_component_id(self):
        node = _make_node(component_id="test_comp")
        result = ParseRecordSetConverter().convert(node, [], {})
        assert result.needs_review[0]["component"] == "test_comp"

    def test_no_framework_param_needs_review(self):
        """Framework params (tstatcatcher_stats, label) must NOT have needs_review."""
        node = _make_node()
        result = ParseRecordSetConverter().convert(node, [], {})
        issues = [e["issue"] for e in result.needs_review]
        for issue in issues:
            assert "tstatcatcher_stats" not in issue
            assert "label" not in issue.lower().split()


class TestPhantomParams:
    """Verify params NOT in _java.xml are NOT extracted."""

    def test_connection_format_not_in_config(self):
        """CONNECTION_FORMAT is phantom (not in _java.xml) -- must NOT appear in config."""
        node = _make_node(params={"CONNECTION_FORMAT": '"row"'})
        result = ParseRecordSetConverter().convert(node, [], {})
        assert "connection_format" not in result.component["config"]


class TestCompleteness:
    """Verify all expected config keys are present."""

    def test_all_config_keys_present(self):
        node = _make_node(schema=_make_schema_columns())
        result = ParseRecordSetConverter().convert(node, [], {})
        expected_keys = {
            "recordset_field",
            "attribute_table",
            "tstatcatcher_stats",
            "label",
        }
        actual_keys = set(result.component["config"].keys())
        missing = expected_keys - actual_keys
        assert not missing, f"Missing config keys: {missing}"


class TestComponentStructure:
    """Verify component dict structure."""

    def test_has_type(self):
        """type_name='tParseRecordSet' per D-43 (no-engine)."""
        node = _make_node()
        result = ParseRecordSetConverter().convert(node, [], {})
        assert result.component["type"] == "tParseRecordSet"

    def test_has_original_type(self):
        node = _make_node()
        result = ParseRecordSetConverter().convert(node, [], {})
        assert result.component["original_type"] == "tParseRecordSet"

    def test_has_config_key(self):
        node = _make_node()
        result = ParseRecordSetConverter().convert(node, [], {})
        assert "config" in result.component

    def test_has_schema_key(self):
        node = _make_node()
        result = ParseRecordSetConverter().convert(node, [], {})
        assert "schema" in result.component

    def test_result_type_is_component_result(self):
        node = _make_node()
        result = ParseRecordSetConverter().convert(node, [], {})
        assert isinstance(result, ComponentResult)

    def test_required_component_keys(self):
        node = _make_node()
        result = ParseRecordSetConverter().convert(node, [], {})
        assert set(result.component.keys()) == {
            "id", "type", "original_type", "position",
            "config", "schema", "inputs", "outputs",
        }
