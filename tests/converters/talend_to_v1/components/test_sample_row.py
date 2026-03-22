"""Tests for the SampleRowConverter (tSampleRow -> SampleRow)."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.transform.sample_row import (
    SampleRowConverter,
)
from src.converters.talend_to_v1.components.registry import REGISTRY


def _make_node(params=None, schema=None, component_id="sample_row_1",
               component_type="tSampleRow"):
    return TalendNode(
        component_id=component_id,
        component_type=component_type,
        params=params or {},
        schema=schema or {},
        position={"x": 256, "y": 128},
        raw_xml=ET.Element("node"),
    )


def _sample_schema():
    """Return a FLOW schema with two columns for reuse across tests."""
    return {
        "FLOW": [
            SchemaColumn(name="id", type="id_Integer", nullable=False, key=True),
            SchemaColumn(name="name", type="id_String", nullable=True),
        ]
    }


# --------------------------------------------------------------------- #
#  Registration
# --------------------------------------------------------------------- #

class TestSampleRowConverterRegistration:
    def test_registered_in_registry(self):
        assert REGISTRY.get("tSampleRow") is SampleRowConverter


# --------------------------------------------------------------------- #
#  Basic conversion
# --------------------------------------------------------------------- #

class TestSampleRowConverterBasic:
    def test_basic_conversion_with_range(self):
        node = _make_node(
            params={"RANGE": '"1..100"', "CONNECTION_FORMAT": '"row"'},
            schema=_sample_schema(),
        )
        result = SampleRowConverter().convert(node, [], {})

        assert isinstance(result, ComponentResult)
        comp = result.component
        assert comp["id"] == "sample_row_1"
        assert comp["type"] == "SampleRow"
        assert comp["original_type"] == "tSampleRow"
        assert comp["position"] == {"x": 256, "y": 128}
        assert comp["config"]["range"] == "1..100"
        assert comp["config"]["connection_format"] == "row"
        assert comp["inputs"] == []
        assert comp["outputs"] == []

    def test_defaults_when_no_params(self):
        node = _make_node(params={})
        result = SampleRowConverter().convert(node, [], {})

        assert result.component["config"]["range"] == ""
        assert result.component["config"]["connection_format"] == "row"

    def test_explicit_connection_format(self):
        node = _make_node(
            params={"RANGE": '"1..10"', "CONNECTION_FORMAT": '"row"'},
            schema=_sample_schema(),
        )
        result = SampleRowConverter().convert(node, [], {})

        assert result.component["config"]["connection_format"] == "row"

    def test_no_warnings_when_range_present(self):
        node = _make_node(
            params={"RANGE": '"1..50"'},
            schema=_sample_schema(),
        )
        result = SampleRowConverter().convert(node, [], {})

        assert result.warnings == []
        assert result.needs_review == []

    def test_warning_when_range_missing(self):
        node = _make_node(params={}, schema=_sample_schema())
        result = SampleRowConverter().convert(node, [], {})

        assert any("RANGE" in w for w in result.warnings)

    def test_warning_when_range_empty_string(self):
        node = _make_node(params={"RANGE": '""'}, schema=_sample_schema())
        result = SampleRowConverter().convert(node, [], {})

        assert any("RANGE" in w for w in result.warnings)


# --------------------------------------------------------------------- #
#  Schema handling
# --------------------------------------------------------------------- #

class TestSampleRowConverterSchema:
    def test_schema_input_equals_output(self):
        """SampleRow is a passthrough: input schema == output schema."""
        node = _make_node(
            params={"RANGE": '"1..10"'},
            schema=_sample_schema(),
        )
        result = SampleRowConverter().convert(node, [], {})

        schema = result.component["schema"]
        assert schema["input"] == schema["output"]
        assert len(schema["input"]) == 2

    def test_schema_column_details(self):
        node = _make_node(
            params={"RANGE": '"1..10"'},
            schema=_sample_schema(),
        )
        result = SampleRowConverter().convert(node, [], {})

        cols = result.component["schema"]["input"]
        id_col = cols[0]
        name_col = cols[1]

        assert id_col["name"] == "id"
        assert id_col["nullable"] is False
        assert id_col["key"] is True

        assert name_col["name"] == "name"
        assert name_col["nullable"] is True
        assert name_col["key"] is False

    def test_empty_schema(self):
        node = _make_node(params={"RANGE": '"1..10"'}, schema={})
        result = SampleRowConverter().convert(node, [], {})

        assert result.component["schema"] == {"input": [], "output": []}
