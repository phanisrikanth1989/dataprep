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
        assert cfg["delimiter"] == ";"
        assert cfg["row_separator"] == "\\n"
        assert cfg["encoding"] == "ISO-8859-15"
        assert cfg["text_enclosure"] is None
        assert cfg["include_header"] is False
        assert cfg["append"] is False
        assert cfg["create_directory"] is True
        assert cfg["delete_empty_file"] is False
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
        assert any("FILENAME" in w for w in result.warnings)

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


# ---------------------------------------------------------------------------
# New parameters
# ---------------------------------------------------------------------------

class TestNewBooleanParams:

    @pytest.mark.parametrize("xml_name,config_key,default", [
        ("COMPRESS", "compress", False),
        ("ADVANCED_SEPARATOR", "advanced_separator", False),
        ("SPLIT", "split", False),
        ("FLUSHONROW", "flush_on_row", False),
        ("ROW_MODE", "row_mode", False),
        ("FILE_EXIST_EXCEPTION", "file_exist_exception", False),
        ("USESTREAM", "use_stream", False),
        ("TSTATCATCHER_STATS", "tstatcatcher_stats", False),
    ])
    def test_bool_param_defaults(self, xml_name, config_key, default):
        node = _make_node()
        result = FileOutputDelimitedConverter().convert(node, [], {})
        assert result.component["config"][config_key] is default

    def test_os_line_separator_defaults_to_true(self):
        node = _make_node()
        result = FileOutputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["os_line_separator"] is True

    @pytest.mark.parametrize("xml_name,config_key", [
        ("COMPRESS", "compress"),
        ("ADVANCED_SEPARATOR", "advanced_separator"),
        ("SPLIT", "split"),
        ("FLUSHONROW", "flush_on_row"),
        ("ROW_MODE", "row_mode"),
        ("FILE_EXIST_EXCEPTION", "file_exist_exception"),
        ("OS_LINE_SEPARATOR_AS_ROW_SEPARATOR", "os_line_separator"),
        ("USESTREAM", "use_stream"),
        ("TSTATCATCHER_STATS", "tstatcatcher_stats"),
    ])
    def test_bool_param_extracted_when_true(self, xml_name, config_key):
        node = _make_node(params={xml_name: True})
        result = FileOutputDelimitedConverter().convert(node, [], {})
        assert result.component["config"][config_key] is True


class TestNewStringIntParams:

    def test_escape_char_default(self):
        node = _make_node()
        result = FileOutputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["escape_char"] == ""

    def test_escape_char_extracted(self):
        node = _make_node(params={"ESCAPE_CHAR": '"\\\\"'})
        result = FileOutputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["escape_char"] == "\\\\"

    def test_thousands_separator_default(self):
        node = _make_node()
        result = FileOutputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["thousands_separator"] == ","

    def test_decimal_separator_default(self):
        node = _make_node()
        result = FileOutputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["decimal_separator"] == "."

    def test_csv_row_separator_default(self):
        node = _make_node()
        result = FileOutputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["csv_row_separator"] == "\\n"

    def test_stream_name_default(self):
        node = _make_node()
        result = FileOutputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["stream_name"] == ""

    def test_label_default(self):
        node = _make_node()
        result = FileOutputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["label"] == ""

    def test_split_every_default(self):
        node = _make_node()
        result = FileOutputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["split_every"] == 1000

    def test_flush_row_count_default(self):
        node = _make_node()
        result = FileOutputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["flush_row_count"] == 1

    def test_split_every_extracted(self):
        node = _make_node(params={"SPLIT_EVERY": "500"})
        result = FileOutputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["split_every"] == 500

    def test_flush_row_count_extracted(self):
        node = _make_node(params={"FLUSHONROW_NUM": "100"})
        result = FileOutputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["flush_row_count"] == 100


# ---------------------------------------------------------------------------
# Engine-gap warnings
# ---------------------------------------------------------------------------

class TestEngineGapWarnings:

    def test_no_engine_warnings_for_defaults(self):
        node = _make_node(params={"FILENAME": '"/data/out.csv"'})
        result = FileOutputDelimitedConverter().convert(node, [], {})
        engine_warnings = [w for w in result.warnings if "engine" in w.lower()]
        assert engine_warnings == []

    @pytest.mark.parametrize("xml_name,expected_substring", [
        ("COMPRESS", "COMPRESS"),
        ("SPLIT", "SPLIT"),
        ("USESTREAM", "USESTREAM"),
        ("ROW_MODE", "ROW_MODE"),
        ("FILE_EXIST_EXCEPTION", "FILE_EXIST_EXCEPTION"),
        ("FLUSHONROW", "FLUSHONROW"),
        ("ADVANCED_SEPARATOR", "ADVANCED_SEPARATOR"),
    ])
    def test_warning_when_param_enabled(self, xml_name, expected_substring):
        node = _make_node(params={"FILENAME": '"/data/out.csv"', xml_name: True})
        result = FileOutputDelimitedConverter().convert(node, [], {})
        assert any(expected_substring in w for w in result.warnings)

    def test_warning_when_os_line_separator_disabled(self):
        node = _make_node(params={
            "FILENAME": '"/data/out.csv"',
            "OS_LINE_SEPARATOR_AS_ROW_SEPARATOR": False,
        })
        result = FileOutputDelimitedConverter().convert(node, [], {})
        assert any("OS_LINE_SEPARATOR" in w for w in result.warnings)

    def test_warning_when_csv_row_separator_differs(self):
        node = _make_node(params={
            "FILENAME": '"/data/out.csv"',
            "CSVROWSEPARATOR": '"\\r\\n"',
            "ROWSEPARATOR": '"\\n"',
        })
        result = FileOutputDelimitedConverter().convert(node, [], {})
        assert any("CSVROWSEPARATOR" in w for w in result.warnings)

    def test_warning_when_escape_char_differs(self):
        node = _make_node(params={
            "FILENAME": '"/data/out.csv"',
            "CSV_OPTION": "true",
            "ESCAPE_CHAR": '"|"',
        })
        result = FileOutputDelimitedConverter().convert(node, [], {})
        assert any("ESCAPE_CHAR" in w for w in result.warnings)

    def test_die_on_error_not_in_config(self):
        node = _make_node(params={"FILENAME": '"/data/out.csv"'})
        result = FileOutputDelimitedConverter().convert(node, [], {})
        assert "die_on_error" not in result.component["config"]


# ---------------------------------------------------------------------------
# Component completeness
# ---------------------------------------------------------------------------

class TestComponentCompleteness:

    def test_all_27_config_keys_present(self):
        node = _make_node()
        result = FileOutputDelimitedConverter().convert(node, [], {})
        cfg = result.component["config"]
        expected_keys = {
            "filepath", "delimiter", "row_separator", "encoding",
            "text_enclosure", "include_header", "append", "create_directory",
            "delete_empty_file", "csv_option",
            "escape_char", "compress",
            "advanced_separator", "thousands_separator", "decimal_separator",
            "csv_row_separator",
            "split", "split_every",
            "flush_on_row", "flush_row_count", "row_mode",
            "file_exist_exception", "os_line_separator",
            "use_stream", "stream_name",
            "tstatcatcher_stats", "label",
        }
        assert set(cfg.keys()) == expected_keys

    def test_die_on_error_absent(self):
        """DIE_ON_ERROR must NOT be in config keys."""
        node = _make_node()
        result = FileOutputDelimitedConverter().convert(node, [], {})
        assert "die_on_error" not in result.component["config"]
