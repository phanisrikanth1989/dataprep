"""Tests for tAdvancedFileOutputXML converter."""
import pytest

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.file.file_output_xml import (
    AdvancedFileOutputXMLConverter,
)
from src.converters.talend_to_v1.components.registry import REGISTRY


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_node(params=None, schema_columns=None, component_id="xml_out_1"):
    """Build a TalendNode for testing."""
    schema = {}
    if schema_columns is not None:
        schema["FLOW"] = schema_columns
    return TalendNode(
        component_id=component_id,
        component_type="tAdvancedFileOutputXML",
        params=params or {},
        schema=schema,
        position={"x": 320, "y": 160},
    )


@pytest.fixture
def converter():
    return AdvancedFileOutputXMLConverter()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestRegistration:
    """Verify the converter is registered correctly."""

    def test_registry_lookup(self):
        cls = REGISTRY.get("tAdvancedFileOutputXML")
        assert cls is AdvancedFileOutputXMLConverter


class TestDefaultValues:
    """When no params are provided, defaults should be used."""

    def test_default_values(self, converter):
        node = _make_node()
        result = converter.convert(node, [], {})

        assert isinstance(result, ComponentResult)
        cfg = result.component["config"]
        assert cfg["filename"] == ""
        assert cfg["encoding"] == "UTF-8"
        assert cfg["pretty_compact"] is False
        assert cfg["create"] is True
        assert cfg["create_empty_element"] is True
        assert cfg["add_blank_line_after_declaration"] is False


class TestAllParamsMapped:
    """All config parameters should be extracted correctly."""

    def test_all_params(self, converter):
        node = _make_node(params={
            "FILENAME": '"/data/output.xml"',
            "ENCODING": '"ISO-8859-1"',
            "PRETTY_COMPACT": "true",
            "CREATE": "false",
            "CREATE_EMPTY_ELEMENT": "false",
            "ADD_BLANK_LINE_AFTER_DECLARATION": "true",
        })

        result = converter.convert(node, [], {})
        cfg = result.component["config"]

        assert cfg["filename"] == "/data/output.xml"
        assert cfg["encoding"] == "ISO-8859-1"
        assert cfg["pretty_compact"] is True
        assert cfg["create"] is False
        assert cfg["create_empty_element"] is False
        assert cfg["add_blank_line_after_declaration"] is True


class TestComponentStructure:
    """Verify the overall component dict structure."""

    def test_structure(self, converter):
        node = _make_node(
            params={"FILENAME": '"/data/out.xml"'},
            component_id="my_xml_output",
        )
        result = converter.convert(node, [], {})
        comp = result.component

        assert comp["id"] == "my_xml_output"
        assert comp["type"] == "AdvancedFileOutputXMLComponent"
        assert comp["original_type"] == "tAdvancedFileOutputXML"
        assert comp["position"] == {"x": 320, "y": 160}
        assert comp["inputs"] == []
        assert comp["outputs"] == []


class TestWarnings:
    """Validate warning generation."""

    def test_empty_filename_warning(self, converter):
        """An empty FILENAME should produce a warning."""
        node = _make_node()
        result = converter.convert(node, [], {})
        assert len(result.warnings) == 1
        assert "FILENAME" in result.warnings[0]

    def test_no_warning_when_filename_present(self, converter):
        """No warning when FILENAME is provided."""
        node = _make_node(params={"FILENAME": '"/data/output.xml"'})
        result = converter.convert(node, [], {})
        assert len(result.warnings) == 0


class TestSchemaHandling:
    """Verify schema columns are parsed for the output component."""

    def test_schema_parsed_into_input(self, converter):
        """Schema columns should appear under schema.input for output component."""
        columns = [
            SchemaColumn(name="id", type="id_Integer", nullable=False, key=True),
            SchemaColumn(name="name", type="id_String", nullable=True),
            SchemaColumn(name="amount", type="id_Double", precision=2),
        ]
        node = _make_node(
            params={"FILENAME": '"/data/output.xml"'},
            schema_columns=columns,
        )
        result = converter.convert(node, [], {})
        schema = result.component["schema"]

        assert schema["output"] == []
        assert len(schema["input"]) == 3

        id_col = schema["input"][0]
        assert id_col["name"] == "id"
        assert id_col["type"] == "int"
        assert id_col["nullable"] is False
        assert id_col["key"] is True

        name_col = schema["input"][1]
        assert name_col["name"] == "name"
        assert name_col["type"] == "str"
        assert name_col["nullable"] is True

        amount_col = schema["input"][2]
        assert amount_col["name"] == "amount"
        assert amount_col["type"] == "float"
        assert amount_col["precision"] == 2

    def test_empty_schema(self, converter):
        """When no schema is provided, input should be empty."""
        node = _make_node(params={"FILENAME": '"/data/output.xml"'})
        result = converter.convert(node, [], {})
        assert result.component["schema"]["input"] == []
        assert result.component["schema"]["output"] == []


class TestBooleanEdgeCases:
    """Test boolean parameter edge cases."""

    def test_boolean_as_native_bool(self, converter):
        """Native Python bools should be handled."""
        node = _make_node(params={
            "FILENAME": '"/data/output.xml"',
            "CREATE": True,
            "PRETTY_COMPACT": False,
        })
        result = converter.convert(node, [], {})
        cfg = result.component["config"]
        assert cfg["create"] is True
        assert cfg["pretty_compact"] is False

    def test_boolean_string_variants(self, converter):
        """Boolean strings '1' and '0' should be handled."""
        node = _make_node(params={
            "FILENAME": '"/data/output.xml"',
            "CREATE": "1",
            "PRETTY_COMPACT": "0",
        })
        result = converter.convert(node, [], {})
        cfg = result.component["config"]
        assert cfg["create"] is True
        assert cfg["pretty_compact"] is False
