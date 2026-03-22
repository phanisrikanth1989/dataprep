"""Tests for tParseRecordSet -> ParseRecordSet converter."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendNode,
)
from src.converters.talend_to_v1.components.transform.parse_record_set import (
    ParseRecordSetConverter,
)
from src.converters.talend_to_v1.components.registry import REGISTRY


def _make_node(
    params=None,
    schema=None,
    component_id="tParseRecordSet_1",
):
    """Create a TalendNode for tParseRecordSet with the given params."""
    return TalendNode(
        component_id=component_id,
        component_type="tParseRecordSet",
        params=params or {},
        schema=schema or {},
        position={"x": 300, "y": 150},
        raw_xml=ET.Element("node"),
    )


def _make_attribute_table(*values):
    """Build an ATTRIBUTE_TABLE list from plain attribute name strings."""
    return [{"elementRef": "ATTRIBUTE", "value": v} for v in values]


def _make_schema_columns():
    """Return a sample FLOW schema for testing."""
    return {
        "FLOW": [
            SchemaColumn(name="recordset", type="id_String", nullable=False, key=True),
            SchemaColumn(name="attr1", type="id_String", nullable=True),
            SchemaColumn(name="attr2", type="id_Integer", nullable=True),
        ]
    }


def _convert(node, connections=None, context=None):
    """Helper to run the converter."""
    converter = ParseRecordSetConverter()
    return converter.convert(
        node=node,
        connections=connections or [],
        context=context or {},
    )


# ------------------------------------------------------------------
# Registration
# ------------------------------------------------------------------


class TestParseRecordSetRegistration:
    """Verify the converter is registered in the global registry."""

    def test_registered_for_tparse_record_set(self):
        cls = REGISTRY.get("tParseRecordSet")
        assert cls is ParseRecordSetConverter


# ------------------------------------------------------------------
# Basic conversion
# ------------------------------------------------------------------


class TestParseRecordSetBasicConversion:
    """Test basic conversion with proper parameters."""

    def test_basic_config(self):
        """All config params are extracted correctly."""
        node = _make_node(params={
            "RECORDSET_FIELD": '"rs_field"',
            "CONNECTION_FORMAT": '"column"',
            "ATTRIBUTE_TABLE": _make_attribute_table("col_a", "col_b", "col_c"),
        })
        result = _convert(node)

        comp = result.component
        assert comp["id"] == "tParseRecordSet_1"
        assert comp["type"] == "ParseRecordSet"
        assert comp["original_type"] == "tParseRecordSet"
        assert comp["position"] == {"x": 300, "y": 150}

        cfg = comp["config"]
        assert cfg["recordset_field"] == "rs_field"
        assert cfg["connection_format"] == "column"
        assert cfg["attribute_table"] == ["col_a", "col_b", "col_c"]

        assert comp["inputs"] == []
        assert comp["outputs"] == []
        assert result.warnings == []

    def test_component_structure_has_required_keys(self):
        node = _make_node(params={
            "RECORDSET_FIELD": '"field"',
            "ATTRIBUTE_TABLE": _make_attribute_table("a"),
        })
        result = _convert(node)
        comp = result.component
        assert set(comp.keys()) == {
            "id", "type", "original_type", "position",
            "config", "schema", "inputs", "outputs",
        }

    def test_result_type_is_component_result(self):
        node = _make_node(params={
            "RECORDSET_FIELD": '"field"',
            "ATTRIBUTE_TABLE": _make_attribute_table("a"),
        })
        result = _convert(node)
        assert isinstance(result, ComponentResult)

    def test_custom_component_id(self):
        node = _make_node(
            params={
                "RECORDSET_FIELD": '"field"',
                "ATTRIBUTE_TABLE": _make_attribute_table("x"),
            },
            component_id="tParseRecordSet_42",
        )
        result = _convert(node)
        assert result.component["id"] == "tParseRecordSet_42"


# ------------------------------------------------------------------
# Parameter parsing
# ------------------------------------------------------------------


class TestParseRecordSetParameterParsing:
    """Test RECORDSET_FIELD, CONNECTION_FORMAT, and ATTRIBUTE_TABLE parsing."""

    def test_connection_format_default(self):
        """When CONNECTION_FORMAT is absent, default to 'row'."""
        node = _make_node(params={
            "RECORDSET_FIELD": '"rs"',
            "ATTRIBUTE_TABLE": _make_attribute_table("a"),
        })
        result = _convert(node)
        assert result.component["config"]["connection_format"] == "row"

    def test_connection_format_custom(self):
        node = _make_node(params={
            "RECORDSET_FIELD": '"rs"',
            "CONNECTION_FORMAT": '"column"',
            "ATTRIBUTE_TABLE": _make_attribute_table("a"),
        })
        result = _convert(node)
        assert result.component["config"]["connection_format"] == "column"

    def test_single_attribute(self):
        node = _make_node(params={
            "RECORDSET_FIELD": '"rs"',
            "ATTRIBUTE_TABLE": _make_attribute_table("only_one"),
        })
        result = _convert(node)
        assert result.component["config"]["attribute_table"] == ["only_one"]

    def test_multiple_attributes(self):
        node = _make_node(params={
            "RECORDSET_FIELD": '"rs"',
            "ATTRIBUTE_TABLE": _make_attribute_table("a", "b", "c", "d"),
        })
        result = _convert(node)
        assert result.component["config"]["attribute_table"] == ["a", "b", "c", "d"]

    def test_attribute_with_surrounding_quotes_stripped(self):
        """Attribute values with surrounding quotes should be stripped."""
        node = _make_node(params={
            "RECORDSET_FIELD": '"rs"',
            "ATTRIBUTE_TABLE": [
                {"elementRef": "ATTRIBUTE", "value": '"quoted_attr"'},
            ],
        })
        result = _convert(node)
        assert result.component["config"]["attribute_table"] == ["quoted_attr"]


# ------------------------------------------------------------------
# Empty / missing / malformed ATTRIBUTE_TABLE
# ------------------------------------------------------------------


class TestParseRecordSetEmptyAndMalformed:
    """Test edge cases and malformed ATTRIBUTE_TABLE."""

    def test_missing_recordset_field_warns(self):
        """Empty RECORDSET_FIELD produces a warning."""
        node = _make_node(params={
            "ATTRIBUTE_TABLE": _make_attribute_table("a"),
        })
        result = _convert(node)
        assert any("no effect" in w.lower() for w in result.warnings)

    def test_missing_attribute_table(self):
        node = _make_node(params={
            "RECORDSET_FIELD": '"rs"',
        })
        result = _convert(node)
        assert result.component["config"]["attribute_table"] == []

    def test_empty_attribute_table(self):
        node = _make_node(params={
            "RECORDSET_FIELD": '"rs"',
            "ATTRIBUTE_TABLE": [],
        })
        result = _convert(node)
        assert result.component["config"]["attribute_table"] == []

    def test_attribute_table_not_a_list(self):
        node = _make_node(params={
            "RECORDSET_FIELD": '"rs"',
            "ATTRIBUTE_TABLE": "not_a_list",
        })
        result = _convert(node)
        assert result.component["config"]["attribute_table"] == []
        assert any("not a list" in w for w in result.warnings)

    def test_entry_with_empty_value_skipped(self):
        """Entries with empty value should be skipped."""
        node = _make_node(params={
            "RECORDSET_FIELD": '"rs"',
            "ATTRIBUTE_TABLE": [
                {"elementRef": "ATTRIBUTE", "value": "good"},
                {"elementRef": "ATTRIBUTE", "value": ""},
                {"elementRef": "ATTRIBUTE", "value": "also_good"},
            ],
        })
        result = _convert(node)
        assert result.component["config"]["attribute_table"] == ["good", "also_good"]

    def test_non_dict_entries_skipped(self):
        """Non-dict entries in the table should be skipped gracefully."""
        node = _make_node(params={
            "RECORDSET_FIELD": '"rs"',
            "ATTRIBUTE_TABLE": [
                {"elementRef": "ATTRIBUTE", "value": "valid"},
                "not_a_dict",
                42,
                {"elementRef": "ATTRIBUTE", "value": "another_valid"},
            ],
        })
        result = _convert(node)
        assert result.component["config"]["attribute_table"] == ["valid", "another_valid"]

    def test_defaults_when_all_params_missing(self):
        """Fully empty params produce sensible defaults + warning."""
        node = _make_node(params={})
        result = _convert(node)
        cfg = result.component["config"]
        assert cfg["recordset_field"] == ""
        assert cfg["connection_format"] == "row"
        assert cfg["attribute_table"] == []
        assert any("no effect" in w.lower() for w in result.warnings)


# ------------------------------------------------------------------
# Schema passthrough
# ------------------------------------------------------------------


class TestParseRecordSetSchema:
    """Schema should pass through (input == output) for transform components."""

    def test_schema_passthrough(self):
        node = _make_node(
            params={
                "RECORDSET_FIELD": '"rs"',
                "ATTRIBUTE_TABLE": _make_attribute_table("a"),
            },
            schema=_make_schema_columns(),
        )
        result = _convert(node)

        schema = result.component["schema"]
        assert schema["input"] == schema["output"]
        assert len(schema["input"]) == 3
        assert schema["input"][0]["name"] == "recordset"
        assert schema["input"][1]["name"] == "attr1"
        assert schema["input"][2]["name"] == "attr2"

    def test_empty_schema(self):
        node = _make_node(params={
            "RECORDSET_FIELD": '"rs"',
            "ATTRIBUTE_TABLE": _make_attribute_table("a"),
        })
        result = _convert(node)

        schema = result.component["schema"]
        assert schema == {"input": [], "output": []}
