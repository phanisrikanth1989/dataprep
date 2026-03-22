"""Tests for tFileOutputEBCDIC converter (fixes CONV-MISSING-002)."""
import pytest

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.file.file_output_ebcdic import (
    FileOutputEBCDICConverter,
)
from src.converters.talend_to_v1.components.registry import REGISTRY


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_node(params=None, schema_columns=None, component_id="ebcdic_out_1"):
    """Build a TalendNode for testing."""
    schema = {}
    if schema_columns is not None:
        schema["FLOW"] = schema_columns
    return TalendNode(
        component_id=component_id,
        component_type="tFileOutputEBCDIC",
        params=params or {},
        schema=schema,
        position={"x": 300, "y": 400},
    )


@pytest.fixture
def converter():
    return FileOutputEBCDICConverter()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestRegistration:
    """Verify the converter is registered correctly."""

    def test_registry_lookup(self):
        cls = REGISTRY.get("tFileOutputEBCDIC")
        assert cls is FileOutputEBCDICConverter


class TestBasicConversion:
    """Test basic parameter mapping."""

    def test_default_values(self, converter):
        """When no params are provided, defaults should be used."""
        node = _make_node()
        result = converter.convert(node, [], {})

        assert isinstance(result, ComponentResult)
        cfg = result.component["config"]
        assert cfg["filename"] == ""
        assert cfg["encoding"] == "Cp1047"
        assert cfg["append"] is False
        assert cfg["row_separator"] == "\\n"
        assert cfg["die_on_error"] is True  # output component default

    def test_all_params_mapped(self, converter):
        """All config parameters should be extracted correctly."""
        node = _make_node(params={
            "FILENAME": '"/data/output.ebcdic"',
            "ENCODING": '"Cp037"',
            "APPEND": "true",
            "ROWSEPARATOR": '"\\r\\n"',
            "DIE_ON_ERROR": "true",
        })

        result = converter.convert(node, [], {})
        cfg = result.component["config"]

        assert cfg["filename"] == "/data/output.ebcdic"
        assert cfg["encoding"] == "Cp037"
        assert cfg["append"] is True
        assert cfg["row_separator"] == "\\r\\n"
        assert cfg["die_on_error"] is True

    def test_component_structure(self, converter):
        """Verify the overall component dict structure."""
        node = _make_node(
            params={"FILENAME": '"/data/out.dat"'},
            component_id="my_ebcdic_output",
        )
        result = converter.convert(node, [], {})
        comp = result.component

        assert comp["id"] == "my_ebcdic_output"
        assert comp["type"] == "FileOutputEBCDIC"
        assert comp["original_type"] == "tFileOutputEBCDIC"
        assert comp["position"] == {"x": 300, "y": 400}
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
        node = _make_node(params={"FILENAME": '"/data/output.ebcdic"'})
        result = converter.convert(node, [], {})
        assert len(result.warnings) == 0


class TestSchemaHandling:
    """Verify schema columns are parsed for the output component."""

    def test_schema_parsed_into_input(self, converter):
        """Schema columns should appear under schema.input for output component."""
        columns = [
            SchemaColumn(name="record_id", type="id_Integer", nullable=False, key=True),
            SchemaColumn(name="name", type="id_String", nullable=True, length=50),
            SchemaColumn(name="amount", type="id_Double", precision=2),
        ]
        node = _make_node(
            params={"FILENAME": '"/data/output.ebcdic"'},
            schema_columns=columns,
        )
        result = converter.convert(node, [], {})
        schema = result.component["schema"]

        assert schema["output"] == []
        assert len(schema["input"]) == 3

        id_col = schema["input"][0]
        assert id_col["name"] == "record_id"
        assert id_col["type"] == "int"
        assert id_col["nullable"] is False
        assert id_col["key"] is True

        name_col = schema["input"][1]
        assert name_col["name"] == "name"
        assert name_col["type"] == "str"
        assert name_col["nullable"] is True
        assert name_col["length"] == 50

        amount_col = schema["input"][2]
        assert amount_col["name"] == "amount"
        assert amount_col["type"] == "float"
        assert amount_col["precision"] == 2

    def test_empty_schema(self, converter):
        """When no schema is provided, input should be empty."""
        node = _make_node(params={"FILENAME": '"/data/output.ebcdic"'})
        result = converter.convert(node, [], {})
        assert result.component["schema"]["input"] == []
        assert result.component["schema"]["output"] == []


class TestBooleanEdgeCases:
    """Test boolean parameter edge cases."""

    def test_boolean_as_native_bool(self, converter):
        """Native Python bools should be handled."""
        node = _make_node(params={
            "FILENAME": '"/data/output.ebcdic"',
            "APPEND": True,
            "DIE_ON_ERROR": False,
        })
        result = converter.convert(node, [], {})
        cfg = result.component["config"]
        assert cfg["append"] is True
        assert cfg["die_on_error"] is False

    def test_boolean_string_variants(self, converter):
        """Boolean strings '1' and '0' should be handled."""
        node = _make_node(params={
            "FILENAME": '"/data/output.ebcdic"',
            "APPEND": "1",
            "DIE_ON_ERROR": "0",
        })
        result = converter.convert(node, [], {})
        cfg = result.component["config"]
        assert cfg["append"] is True
        assert cfg["die_on_error"] is False
