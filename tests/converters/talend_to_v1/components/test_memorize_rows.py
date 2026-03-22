"""Tests for the MemorizeRowsConverter (tMemorizeRows -> MemorizeRows)."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.transform.memorize_rows import (
    MemorizeRowsConverter,
)
from src.converters.talend_to_v1.components.registry import REGISTRY


def _make_node(params=None, schema=None, component_id="memorize_1",
               component_type="tMemorizeRows"):
    return TalendNode(
        component_id=component_id,
        component_type=component_type,
        params=params or {},
        schema=schema or {},
        position={"x": 400, "y": 200},
        raw_xml=ET.Element("node"),
    )


def _sample_schema():
    """Return a FLOW schema with two columns for reuse across tests."""
    return {
        "FLOW": [
            SchemaColumn(name="id", type="id_Integer", nullable=False, key=True),
            SchemaColumn(name="value", type="id_String", nullable=True),
        ]
    }


# --------------------------------------------------------------------- #
#  Registration
# --------------------------------------------------------------------- #

class TestMemorizeRowsConverterRegistration:
    def test_registered_in_registry(self):
        assert REGISTRY.get("tMemorizeRows") is MemorizeRowsConverter


# --------------------------------------------------------------------- #
#  Basic conversion
# --------------------------------------------------------------------- #

class TestMemorizeRowsConverterBasic:
    def test_basic_conversion_with_defaults(self):
        node = _make_node(schema=_sample_schema())
        result = MemorizeRowsConverter().convert(node, [], {})

        assert isinstance(result, ComponentResult)
        comp = result.component
        assert comp["id"] == "memorize_1"
        assert comp["type"] == "MemorizeRows"
        assert comp["original_type"] == "tMemorizeRows"
        assert comp["position"] == {"x": 400, "y": 200}
        assert comp["config"]["row_count"] == 1
        assert comp["config"]["reset_on_condition"] is False
        assert comp["config"]["condition"] == ""
        assert comp["inputs"] == []
        assert comp["outputs"] == []

    def test_custom_row_count(self):
        node = _make_node(
            params={"ROW_COUNT": "5"},
            schema=_sample_schema(),
        )
        result = MemorizeRowsConverter().convert(node, [], {})

        assert result.component["config"]["row_count"] == 5

    def test_row_count_as_quoted_string(self):
        node = _make_node(
            params={"ROW_COUNT": '"3"'},
            schema=_sample_schema(),
        )
        result = MemorizeRowsConverter().convert(node, [], {})

        assert result.component["config"]["row_count"] == 3

    def test_reset_on_condition_with_condition(self):
        node = _make_node(
            params={
                "ROW_COUNT": "10",
                "RESET_ON_CONDITION": "true",
                "CONDITION": '"row.id == 0"',
            },
            schema=_sample_schema(),
        )
        result = MemorizeRowsConverter().convert(node, [], {})

        cfg = result.component["config"]
        assert cfg["row_count"] == 10
        assert cfg["reset_on_condition"] is True
        assert cfg["condition"] == "row.id == 0"

    def test_no_params_uses_defaults(self):
        node = _make_node(params={})
        result = MemorizeRowsConverter().convert(node, [], {})

        cfg = result.component["config"]
        assert cfg["row_count"] == 1
        assert cfg["reset_on_condition"] is False
        assert cfg["condition"] == ""

    def test_no_warnings_on_valid_input(self):
        node = _make_node(schema=_sample_schema())
        result = MemorizeRowsConverter().convert(node, [], {})

        assert result.warnings == []
        assert result.needs_review == []


# --------------------------------------------------------------------- #
#  Validation / warnings
# --------------------------------------------------------------------- #

class TestMemorizeRowsConverterWarnings:
    def test_invalid_row_count_zero_warns_and_defaults(self):
        node = _make_node(
            params={"ROW_COUNT": "0"},
            schema=_sample_schema(),
        )
        result = MemorizeRowsConverter().convert(node, [], {})

        assert result.component["config"]["row_count"] == 1
        assert len(result.warnings) == 1
        assert "ROW_COUNT" in result.warnings[0]

    def test_negative_row_count_warns_and_defaults(self):
        node = _make_node(
            params={"ROW_COUNT": "-2"},
            schema=_sample_schema(),
        )
        result = MemorizeRowsConverter().convert(node, [], {})

        assert result.component["config"]["row_count"] == 1
        assert len(result.warnings) == 1


# --------------------------------------------------------------------- #
#  Schema handling
# --------------------------------------------------------------------- #

class TestMemorizeRowsConverterSchema:
    def test_schema_input_equals_output(self):
        """MemorizeRows is a transform passthrough: input schema == output schema."""
        node = _make_node(schema=_sample_schema())
        result = MemorizeRowsConverter().convert(node, [], {})

        schema = result.component["schema"]
        assert schema["input"] == schema["output"]
        assert len(schema["input"]) == 2

    def test_schema_column_details(self):
        node = _make_node(schema=_sample_schema())
        result = MemorizeRowsConverter().convert(node, [], {})

        cols = result.component["schema"]["input"]
        id_col = cols[0]
        val_col = cols[1]

        assert id_col["name"] == "id"
        assert id_col["nullable"] is False
        assert id_col["key"] is True

        assert val_col["name"] == "value"
        assert val_col["nullable"] is True
        assert val_col["key"] is False

    def test_empty_schema(self):
        node = _make_node(schema={})
        result = MemorizeRowsConverter().convert(node, [], {})

        assert result.component["schema"] == {"input": [], "output": []}
