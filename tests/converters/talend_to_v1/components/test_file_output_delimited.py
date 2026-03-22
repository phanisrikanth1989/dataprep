"""Tests for tFileOutputDelimited converter."""
import pytest

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.file.file_output_delimited import (
    FileOutputDelimitedConverter,
)
from src.converters.talend_to_v1.components.registry import REGISTRY


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_node(params=None, schema_columns=None, component_id="output_1"):
    """Build a TalendNode for testing."""
    schema = {}
    if schema_columns is not None:
        schema["FLOW"] = schema_columns
    return TalendNode(
        component_id=component_id,
        component_type="tFileOutputDelimited",
        params=params or {},
        schema=schema,
        position={"x": 100, "y": 200},
    )


@pytest.fixture
def converter():
    return FileOutputDelimitedConverter()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestRegistration:
    """Verify the converter is registered correctly."""

    def test_registry_lookup(self):
        cls = REGISTRY.get("tFileOutputDelimited")
        assert cls is FileOutputDelimitedConverter


class TestBasicConversion:
    """Test basic parameter mapping."""

    def test_default_values(self, converter):
        """When no params are provided, defaults should be used."""
        node = _make_node()
        result = converter.convert(node, [], {})

        assert isinstance(result, ComponentResult)
        cfg = result.component["config"]
        assert cfg["filepath"] == ""
        assert cfg["delimiter"] == ","
        assert cfg["row_separator"] == "\\n"
        assert cfg["encoding"] == "UTF-8"
        assert cfg["text_enclosure"] is None
        assert cfg["include_header"] is True
        assert cfg["append"] is False
        assert cfg["create_directory"] is True
        assert cfg["delete_empty_file"] is True
        assert cfg["die_on_error"] is False
        assert cfg["csv_option"] is False

    def test_all_params_mapped(self, converter):
        """All config parameters should be extracted correctly."""
        node = _make_node(params={
            "FILENAME": '"/tmp/output.csv"',
            "FIELDSEPARATOR": '"|"',
            "ROWSEPARATOR": '"\\r\\n"',
            "ENCODING": '"ISO-8859-1"',
            "CSV_OPTION": "true",
            "TEXT_ENCLOSURE": '"\\""',
            "INCLUDEHEADER": "true",
            "APPEND": "true",
            "CREATE": "false",
            "DELETE_EMPTYFILE": "false",
            "DIE_ON_ERROR": "true",
        })

        result = converter.convert(node, [], {})
        cfg = result.component["config"]

        assert cfg["filepath"] == "/tmp/output.csv"
        assert cfg["delimiter"] == "|"
        assert cfg["row_separator"] == "\\r\\n"
        assert cfg["encoding"] == "ISO-8859-1"
        assert cfg["text_enclosure"] == '\\"'
        assert cfg["include_header"] is True
        assert cfg["append"] is True
        assert cfg["create_directory"] is False
        assert cfg["delete_empty_file"] is False
        assert cfg["die_on_error"] is True
        assert cfg["csv_option"] is True

    def test_component_structure(self, converter):
        """Verify the overall component dict structure."""
        node = _make_node(
            params={"FILENAME": '"/data/out.tsv"'},
            component_id="my_output",
        )
        result = converter.convert(node, [], {})
        comp = result.component

        assert comp["id"] == "my_output"
        assert comp["type"] == "FileOutputDelimited"
        assert comp["original_type"] == "tFileOutputDelimited"
        assert comp["position"] == {"x": 100, "y": 200}
        assert comp["inputs"] == []
        assert comp["outputs"] == []


class TestCsvOptionLogic:
    """text_enclosure should only be set when csv_option is True."""

    def test_csv_option_true_text_enclosure_set(self, converter):
        """When CSV_OPTION is true, text_enclosure should be extracted."""
        node = _make_node(params={
            "CSV_OPTION": "true",
            "TEXT_ENCLOSURE": '"\\""',
        })
        result = converter.convert(node, [], {})
        cfg = result.component["config"]

        assert cfg["csv_option"] is True
        assert cfg["text_enclosure"] == '\\"'

    def test_csv_option_false_text_enclosure_none(self, converter):
        """When CSV_OPTION is false, text_enclosure must be None."""
        node = _make_node(params={
            "CSV_OPTION": "false",
            "TEXT_ENCLOSURE": '"\\""',
        })
        result = converter.convert(node, [], {})
        cfg = result.component["config"]

        assert cfg["csv_option"] is False
        assert cfg["text_enclosure"] is None

    def test_csv_option_absent_text_enclosure_none(self, converter):
        """When CSV_OPTION is absent, text_enclosure must be None."""
        node = _make_node(params={
            "TEXT_ENCLOSURE": '"\\""',
        })
        result = converter.convert(node, [], {})
        cfg = result.component["config"]

        assert cfg["csv_option"] is False
        assert cfg["text_enclosure"] is None


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
        node = _make_node(params={"FILENAME": '"/data/output.csv"'})
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
            params={"FILENAME": '"/data/output.csv"'},
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
        node = _make_node(params={"FILENAME": '"/data/output.csv"'})
        result = converter.convert(node, [], {})
        assert result.component["schema"]["input"] == []
        assert result.component["schema"]["output"] == []


class TestBooleanEdgeCases:
    """Test boolean parameter edge cases."""

    def test_boolean_as_native_bool(self, converter):
        """Native Python bools should be handled."""
        node = _make_node(params={
            "FILENAME": '"/data/output.csv"',
            "INCLUDEHEADER": True,
            "APPEND": False,
        })
        result = converter.convert(node, [], {})
        cfg = result.component["config"]
        assert cfg["include_header"] is True
        assert cfg["append"] is False

    def test_boolean_string_variants(self, converter):
        """Boolean strings '1' and '0' should be handled."""
        node = _make_node(params={
            "FILENAME": '"/data/output.csv"',
            "INCLUDEHEADER": "1",
            "APPEND": "0",
        })
        result = converter.convert(node, [], {})
        cfg = result.component["config"]
        assert cfg["include_header"] is True
        assert cfg["append"] is False
