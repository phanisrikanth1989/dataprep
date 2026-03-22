"""Tests for tDenormalize -> Denormalize converter."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.transform.denormalize import (
    DenormalizeConverter,
)
from src.converters.talend_to_v1.components.registry import REGISTRY


def _make_node(
    params=None,
    schema=None,
    component_id="tDenormalize_1",
):
    """Create a TalendNode for tDenormalize with the given params."""
    return TalendNode(
        component_id=component_id,
        component_type="tDenormalize",
        params=params or {},
        schema=schema or {},
        position={"x": 400, "y": 200},
        raw_xml=ET.Element("node"),
    )


def _make_schema_columns():
    """Return a sample FLOW schema for testing."""
    return {
        "FLOW": [
            SchemaColumn(name="group_key", type="id_String", nullable=False, key=True),
            SchemaColumn(name="value", type="id_String", nullable=True),
            SchemaColumn(name="count", type="id_Integer", nullable=True),
        ]
    }


def _make_denormalize_table(*rows):
    """Build a flat DENORMALIZE_COLUMNS list from (col, delim, merge) tuples."""
    entries = []
    for col, delim, merge in rows:
        entries.append({"elementRef": "INPUT_COLUMN", "value": col})
        entries.append({"elementRef": "DELIMITER", "value": delim})
        entries.append({"elementRef": "MERGE", "value": str(merge).lower()})
    return entries


def _convert(node, connections=None, context=None):
    """Helper to run the converter."""
    converter = DenormalizeConverter()
    return converter.convert(
        node=node,
        connections=connections or [],
        context=context or {},
    )


# ------------------------------------------------------------------
# Registration
# ------------------------------------------------------------------


class TestDenormalizeRegistration:
    """Verify the converter is registered in the global registry."""

    def test_registered_for_tdenormalize(self):
        cls = REGISTRY.get("tDenormalize")
        assert cls is DenormalizeConverter


# ------------------------------------------------------------------
# Basic conversion
# ------------------------------------------------------------------


class TestDenormalizeBasicConversion:
    """Test basic conversion with proper parameters."""

    def test_single_denormalize_column(self):
        node = _make_node(params={
            "NULL_AS_EMPTY": "true",
            "CONNECTION_FORMAT": "row",
            "DENORMALIZE_COLUMNS": _make_denormalize_table(
                ("value", ",", False),
            ),
        })
        result = _convert(node)

        comp = result.component
        assert comp["id"] == "tDenormalize_1"
        assert comp["type"] == "Denormalize"
        assert comp["original_type"] == "tDenormalize"
        assert comp["position"] == {"x": 400, "y": 200}
        assert comp["config"]["null_as_empty"] is True
        assert comp["config"]["connection_format"] == "row"
        assert len(comp["config"]["denormalize_columns"]) == 1
        assert comp["config"]["denormalize_columns"][0] == {
            "input_column": "value",
            "delimiter": ",",
            "merge": False,
        }
        assert comp["inputs"] == []
        assert comp["outputs"] == []
        assert result.warnings == []

    def test_multiple_denormalize_columns(self):
        node = _make_node(params={
            "DENORMALIZE_COLUMNS": _make_denormalize_table(
                ("col_a", ",", False),
                ("col_b", ";", True),
                ("col_c", "|", False),
            ),
        })
        result = _convert(node)

        cols = result.component["config"]["denormalize_columns"]
        assert len(cols) == 3
        assert cols[0] == {"input_column": "col_a", "delimiter": ",", "merge": False}
        assert cols[1] == {"input_column": "col_b", "delimiter": ";", "merge": True}
        assert cols[2] == {"input_column": "col_c", "delimiter": "|", "merge": False}
        assert result.warnings == []

    def test_component_structure_has_required_keys(self):
        node = _make_node(params={
            "DENORMALIZE_COLUMNS": _make_denormalize_table(
                ("value", ",", False),
            ),
        })
        result = _convert(node)
        comp = result.component
        assert set(comp.keys()) == {
            "id", "type", "original_type", "position",
            "config", "schema", "inputs", "outputs",
        }

    def test_result_type_is_component_result(self):
        node = _make_node(params={
            "DENORMALIZE_COLUMNS": _make_denormalize_table(
                ("value", ",", False),
            ),
        })
        result = _convert(node)
        assert isinstance(result, ComponentResult)


# ------------------------------------------------------------------
# Audit fix CONV-DNR-002: merge defaults to false
# ------------------------------------------------------------------


class TestDenormalizeMergeDefault:
    """CONV-DNR-002: Talend defaults merge to false, old code used True."""

    def test_merge_defaults_to_false(self):
        """When MERGE is not present in a triplet, default should be False."""
        node = _make_node(params={
            "DENORMALIZE_COLUMNS": [
                {"elementRef": "INPUT_COLUMN", "value": "my_col"},
                {"elementRef": "DELIMITER", "value": ","},
                # MERGE intentionally missing — replaced by unrecognised ref
                {"elementRef": "UNKNOWN_REF", "value": "whatever"},
            ],
        })
        result = _convert(node)

        cols = result.component["config"]["denormalize_columns"]
        assert len(cols) == 1
        assert cols[0]["merge"] is False

    def test_merge_true_when_explicitly_set(self):
        node = _make_node(params={
            "DENORMALIZE_COLUMNS": _make_denormalize_table(
                ("col_x", "|", True),
            ),
        })
        result = _convert(node)

        cols = result.component["config"]["denormalize_columns"]
        assert cols[0]["merge"] is True

    def test_merge_false_when_explicitly_set(self):
        node = _make_node(params={
            "DENORMALIZE_COLUMNS": _make_denormalize_table(
                ("col_x", "|", False),
            ),
        })
        result = _convert(node)

        cols = result.component["config"]["denormalize_columns"]
        assert cols[0]["merge"] is False


# ------------------------------------------------------------------
# Parameter parsing
# ------------------------------------------------------------------


class TestDenormalizeParameterParsing:
    """Test NULL_AS_EMPTY, CONNECTION_FORMAT, and delimiter parsing."""

    def test_null_as_empty_true(self):
        node = _make_node(params={
            "NULL_AS_EMPTY": "true",
            "DENORMALIZE_COLUMNS": _make_denormalize_table(("c", ",", False)),
        })
        result = _convert(node)
        assert result.component["config"]["null_as_empty"] is True

    def test_null_as_empty_false(self):
        node = _make_node(params={
            "NULL_AS_EMPTY": "false",
            "DENORMALIZE_COLUMNS": _make_denormalize_table(("c", ",", False)),
        })
        result = _convert(node)
        assert result.component["config"]["null_as_empty"] is False

    def test_null_as_empty_defaults_to_false(self):
        node = _make_node(params={
            "DENORMALIZE_COLUMNS": _make_denormalize_table(("c", ",", False)),
        })
        result = _convert(node)
        assert result.component["config"]["null_as_empty"] is False

    def test_connection_format_default(self):
        node = _make_node(params={
            "DENORMALIZE_COLUMNS": _make_denormalize_table(("c", ",", False)),
        })
        result = _convert(node)
        assert result.component["config"]["connection_format"] == "row"

    def test_connection_format_custom(self):
        node = _make_node(params={
            "CONNECTION_FORMAT": '"column"',
            "DENORMALIZE_COLUMNS": _make_denormalize_table(("c", ",", False)),
        })
        result = _convert(node)
        assert result.component["config"]["connection_format"] == "column"

    def test_delimiter_with_xml_encoded_quotes(self):
        node = _make_node(params={
            "DENORMALIZE_COLUMNS": [
                {"elementRef": "INPUT_COLUMN", "value": "col"},
                {"elementRef": "DELIMITER", "value": "&quot;,&quot;"},
                {"elementRef": "MERGE", "value": "false"},
            ],
        })
        result = _convert(node)

        cols = result.component["config"]["denormalize_columns"]
        assert cols[0]["delimiter"] == ","

    def test_delimiter_with_plain_quotes(self):
        node = _make_node(params={
            "DENORMALIZE_COLUMNS": [
                {"elementRef": "INPUT_COLUMN", "value": "col"},
                {"elementRef": "DELIMITER", "value": '","'},
                {"elementRef": "MERGE", "value": "false"},
            ],
        })
        result = _convert(node)

        cols = result.component["config"]["denormalize_columns"]
        assert cols[0]["delimiter"] == ","

    def test_delimiter_defaults_to_comma(self):
        """When DELIMITER is missing from triplet, default to comma."""
        node = _make_node(params={
            "DENORMALIZE_COLUMNS": [
                {"elementRef": "INPUT_COLUMN", "value": "col"},
                {"elementRef": "UNKNOWN", "value": "x"},
                {"elementRef": "MERGE", "value": "false"},
            ],
        })
        result = _convert(node)

        cols = result.component["config"]["denormalize_columns"]
        assert cols[0]["delimiter"] == ","


# ------------------------------------------------------------------
# Schema passthrough (CONV-DNR-003)
# ------------------------------------------------------------------


class TestDenormalizeSchema:
    """CONV-DNR-003: Schema should pass through (input == output)."""

    def test_schema_passthrough(self):
        node = _make_node(
            params={
                "DENORMALIZE_COLUMNS": _make_denormalize_table(("value", ",", False)),
            },
            schema=_make_schema_columns(),
        )
        result = _convert(node)

        schema = result.component["schema"]
        assert schema["input"] == schema["output"]
        assert len(schema["input"]) == 3
        assert schema["input"][0]["name"] == "group_key"
        assert schema["input"][1]["name"] == "value"
        assert schema["input"][2]["name"] == "count"

    def test_empty_schema(self):
        node = _make_node(params={
            "DENORMALIZE_COLUMNS": _make_denormalize_table(("col", ",", False)),
        })
        result = _convert(node)

        schema = result.component["schema"]
        assert schema == {"input": [], "output": []}


# ------------------------------------------------------------------
# Empty / missing / malformed DENORMALIZE_COLUMNS
# ------------------------------------------------------------------


class TestDenormalizeEmptyAndMalformed:
    """Test edge cases and malformed DENORMALIZE_COLUMNS."""

    def test_missing_denormalize_columns(self):
        node = _make_node(params={})
        result = _convert(node)

        assert result.component["config"]["denormalize_columns"] == []
        assert any("No denormalize columns" in w for w in result.warnings)

    def test_empty_denormalize_columns(self):
        node = _make_node(params={"DENORMALIZE_COLUMNS": []})
        result = _convert(node)

        assert result.component["config"]["denormalize_columns"] == []
        assert any("No denormalize columns" in w for w in result.warnings)

    def test_denormalize_columns_not_a_list(self):
        node = _make_node(params={"DENORMALIZE_COLUMNS": "not_a_list"})
        result = _convert(node)

        assert result.component["config"]["denormalize_columns"] == []
        assert any("not a list" in w for w in result.warnings)

    def test_triplet_without_input_column_skipped(self):
        node = _make_node(params={
            "DENORMALIZE_COLUMNS": [
                {"elementRef": "DELIMITER", "value": ","},
                {"elementRef": "MERGE", "value": "false"},
                {"elementRef": "UNKNOWN", "value": "x"},
            ],
        })
        result = _convert(node)

        assert result.component["config"]["denormalize_columns"] == []
        assert any("no INPUT_COLUMN" in w for w in result.warnings)

    def test_incomplete_trailing_triplet(self):
        """A partial triplet (fewer than 3 entries) should still parse if it has INPUT_COLUMN."""
        node = _make_node(params={
            "DENORMALIZE_COLUMNS": [
                {"elementRef": "INPUT_COLUMN", "value": "col_a"},
                {"elementRef": "DELIMITER", "value": ";"},
                {"elementRef": "MERGE", "value": "true"},
                # Trailing partial triplet: only INPUT_COLUMN
                {"elementRef": "INPUT_COLUMN", "value": "col_b"},
            ],
        })
        result = _convert(node)

        cols = result.component["config"]["denormalize_columns"]
        assert len(cols) == 2
        assert cols[0] == {"input_column": "col_a", "delimiter": ";", "merge": True}
        # Partial triplet uses defaults for delimiter and merge
        assert cols[1] == {"input_column": "col_b", "delimiter": ",", "merge": False}

    def test_custom_component_id(self):
        node = _make_node(
            params={
                "DENORMALIZE_COLUMNS": _make_denormalize_table(("c", ",", False)),
            },
            component_id="tDenormalize_42",
        )
        result = _convert(node)
        assert result.component["id"] == "tDenormalize_42"

    def test_input_column_with_quotes_stripped(self):
        """INPUT_COLUMN values with surrounding quotes should be stripped."""
        node = _make_node(params={
            "DENORMALIZE_COLUMNS": [
                {"elementRef": "INPUT_COLUMN", "value": '"my_col"'},
                {"elementRef": "DELIMITER", "value": ","},
                {"elementRef": "MERGE", "value": "false"},
            ],
        })
        result = _convert(node)

        cols = result.component["config"]["denormalize_columns"]
        assert cols[0]["input_column"] == "my_col"
