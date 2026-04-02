"""Tests for tFileOutputExcel -> FileOutputExcel converter."""
import pytest

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendNode,
)
from src.converters.talend_to_v1.components.file.file_output_excel import (
    FileOutputExcelConverter,
)
from src.converters.talend_to_v1.components.registry import REGISTRY


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_node(params=None, schema_columns=None, component_id="tFileOutputExcel_1"):
    """Build a TalendNode for testing."""
    schema = {}
    if schema_columns is not None:
        schema["FLOW"] = schema_columns
    return TalendNode(
        component_id=component_id,
        component_type="tFileOutputExcel",
        params=params or {},
        schema=schema,
        position={"x": 320, "y": 160},
    )


@pytest.fixture
def converter():
    return FileOutputExcelConverter()


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class TestRegistration:
    def test_registry_lookup(self):
        cls = REGISTRY.get("tFileOutputExcel")
        assert cls is FileOutputExcelConverter


# ---------------------------------------------------------------------------
# Basic conversion
# ---------------------------------------------------------------------------

class TestBasicConversion:
    def test_full_params(self, converter):
        """All params extracted and quote-stripped correctly."""
        node = _make_node(params={
            "FILENAME": '"/data/report.xlsx"',
            "SHEETNAME": '"DataSheet"',
            "VERSION_2007": "true",
            "INCLUDEHEADER": "true",
            "APPEND_FILE": "true",
            "APPEND_SHEET": "true",
            "CREATE": "false",
            "DIE_ON_ERROR": "true",
            "ENCODING": '"ISO-8859-1"',
            "FONT": '"Courier New"',
            "AUTO_SIZE_SETTING": "true",
            "FIRST_CELL_Y_ABSOLUTE": "true",
            "FIRST_CELL_X": "5",
            "FIRST_CELL_Y": "10",
            "KEEP_CELL_FORMATING": "true",
            "ADVANCED_SEPARATOR": "true",
            "THOUSANDS_SEPARATOR": '"."',
            "DECIMAL_SEPARATOR": '","',
            "TRUNCATE_EXCEEDING_CHARACTERS": "true",
            "DELETE_EMPTYFILE": "true",
            "RECALCULATE_FORMULA": "true",
            "PROTECT_FILE": "true",
            "PASSWORD": '"secret"',
            "CUSTOM_FLUSH_BUFFER": "true",
            "FLUSH_ON_ROW": "500",
            "STREAMING_APPEND": "true",
            "USE_SHARED_STRINGS_TABLE": "true",
            "TSTATCATCHER_STATS": "true",
            "LABEL": '"my-output"',
        })
        result = converter.convert(node, [], {})
        cfg = result.component["config"]

        assert cfg["filename"] == "/data/report.xlsx"
        assert cfg["sheetname"] == "DataSheet"
        assert cfg["version_2007"] is True
        assert cfg["includeheader"] is True
        assert cfg["append_file"] is True
        assert cfg["append_sheet"] is True
        assert cfg["create_directory"] is False
        assert cfg["die_on_error"] is True
        assert cfg["encoding"] == "ISO-8859-1"
        assert cfg["font"] == "Courier New"
        assert cfg["auto_size_all"] is True
        assert cfg["first_cell_y_absolute"] is True
        assert cfg["first_cell_x"] == 5
        assert cfg["first_cell_y"] == 10
        assert cfg["keep_cell_formatting"] is True
        assert cfg["advanced_separator"] is True
        assert cfg["thousands_separator"] == "."
        assert cfg["decimal_separator"] == ","
        assert cfg["truncate_exceeding_characters"] is True
        assert cfg["delete_empty_file"] is True
        assert cfg["recalculate_formula"] is True
        assert cfg["protect_file"] is True
        assert cfg["password"] == "secret"
        assert cfg["custom_flush_buffer"] is True
        assert cfg["flush_on_row"] == 500
        assert cfg["streaming_append"] is True
        assert cfg["use_shared_strings_table"] is True
        assert cfg["tstatcatcher_stats"] is True
        assert cfg["label"] == "my-output"

    def test_default_values(self, converter):
        """When no params provided, correct Talend defaults used."""
        node = _make_node(params={"FILENAME": '"/data/out.xlsx"'})
        result = converter.convert(node, [], {})
        cfg = result.component["config"]

        assert cfg["filename"] == "/data/out.xlsx"
        assert cfg["sheetname"] == "Sheet1"
        assert cfg["version_2007"] is False
        assert cfg["includeheader"] is False
        assert cfg["append_file"] is False
        assert cfg["append_sheet"] is False
        assert cfg["create_directory"] is True
        assert cfg["die_on_error"] is False
        assert cfg["encoding"] == "UTF-8"
        assert cfg["font"] == "Arial"
        assert cfg["auto_size_all"] is False
        assert cfg["first_cell_y_absolute"] is False
        assert cfg["first_cell_x"] == 0
        assert cfg["first_cell_y"] == 0
        assert cfg["keep_cell_formatting"] is False
        assert cfg["advanced_separator"] is False
        assert cfg["thousands_separator"] == ","
        assert cfg["decimal_separator"] == "."
        assert cfg["truncate_exceeding_characters"] is False
        assert cfg["delete_empty_file"] is False
        assert cfg["recalculate_formula"] is False
        assert cfg["protect_file"] is False
        assert cfg["password"] == ""
        assert cfg["custom_flush_buffer"] is False
        assert cfg["flush_on_row"] == 1000
        assert cfg["streaming_append"] is False
        assert cfg["use_shared_strings_table"] is False
        assert cfg["tstatcatcher_stats"] is False
        assert cfg["label"] == ""

    def test_component_structure(self, converter):
        """Verify component dict has correct top-level keys and metadata."""
        node = _make_node(
            params={"FILENAME": '"/data/out.xlsx"'},
            component_id="my_excel_out",
        )
        result = converter.convert(node, [], {})
        comp = result.component

        assert isinstance(result, ComponentResult)
        assert comp["id"] == "my_excel_out"
        assert comp["type"] == "FileOutputExcel"
        assert comp["original_type"] == "tFileOutputExcel"
        assert comp["position"] == {"x": 320, "y": 160}
        assert set(comp.keys()) == {
            "id", "type", "original_type", "position",
            "config", "schema", "inputs", "outputs",
        }
        assert comp["inputs"] == []
        assert comp["outputs"] == []


# ---------------------------------------------------------------------------
# Schema handling (sink component)
# ---------------------------------------------------------------------------

class TestSchemaHandling:
    def test_schema_parsed_into_input(self, converter):
        """Schema columns appear under schema.input for sink component."""
        columns = [
            SchemaColumn(name="id", type="id_Integer", nullable=False, key=True),
            SchemaColumn(name="name", type="id_String", nullable=True, length=100),
            SchemaColumn(name="amount", type="id_Double", precision=2),
        ]
        node = _make_node(
            params={"FILENAME": '"/data/out.xlsx"'},
            schema_columns=columns,
        )
        result = converter.convert(node, [], {})
        schema = result.component["schema"]

        assert schema["output"] == []
        assert len(schema["input"]) == 3
        assert schema["input"][0]["name"] == "id"
        assert schema["input"][0]["key"] is True
        assert schema["input"][1]["name"] == "name"
        assert schema["input"][1]["length"] == 100
        assert schema["input"][2]["name"] == "amount"
        assert schema["input"][2]["precision"] == 2

    def test_empty_schema(self, converter):
        """When no schema provided, both sides empty."""
        node = _make_node(params={"FILENAME": '"/data/out.xlsx"'})
        result = converter.convert(node, [], {})
        assert result.component["schema"]["input"] == []
        assert result.component["schema"]["output"] == []


# ---------------------------------------------------------------------------
# Warnings
# ---------------------------------------------------------------------------

class TestValidationWarnings:
    def test_empty_filename_warning(self, converter):
        node = _make_node(params={})
        result = converter.convert(node, [], {})
        assert any("FILENAME" in w for w in result.warnings)

    def test_no_warning_when_filename_present(self, converter):
        node = _make_node(params={"FILENAME": '"/data/out.xlsx"'})
        result = converter.convert(node, [], {})
        filename_warnings = [w for w in result.warnings if "FILENAME" in w]
        assert filename_warnings == []


class TestEngineGapWarnings:
    def test_no_engine_warnings_when_version_2007_true(self):
        """With VERSION_2007=true and default params, only no engine warnings."""
        node = _make_node(params={
            "FILENAME": '"/data/out.xlsx"',
            "VERSION_2007": "true",
        })
        result = FileOutputExcelConverter().convert(node, [], {})
        engine_warnings = [w for w in result.warnings if "engine" in w.lower()]
        assert engine_warnings == []

    def test_version_2007_false_warning(self):
        node = _make_node(params={"FILENAME": '"/data/out.xlsx"'})
        result = FileOutputExcelConverter().convert(node, [], {})
        assert any("VERSION_2007=false" in w for w in result.warnings)

    @pytest.mark.parametrize("xml_name,expected_substring", [
        ("PROTECT_FILE", "PROTECT_FILE"),
        ("FIRST_CELL_Y_ABSOLUTE", "FIRST_CELL_Y_ABSOLUTE"),
        ("AUTO_SIZE_SETTING", "AUTO_SIZE_SETTING"),
        ("KEEP_CELL_FORMATING", "KEEP_CELL_FORMATING"),
        ("ADVANCED_SEPARATOR", "ADVANCED_SEPARATOR"),
        ("TRUNCATE_EXCEEDING_CHARACTERS", "TRUNCATE_EXCEEDING_CHARACTERS"),
        ("DELETE_EMPTYFILE", "DELETE_EMPTYFILE"),
        ("RECALCULATE_FORMULA", "RECALCULATE_FORMULA"),
        ("STREAMING_APPEND", "STREAMING_APPEND"),
        ("USE_SHARED_STRINGS_TABLE", "USE_SHARED_STRINGS_TABLE"),
        ("CUSTOM_FLUSH_BUFFER", "CUSTOM_FLUSH_BUFFER"),
    ])
    def test_boolean_param_warning(self, xml_name, expected_substring):
        node = _make_node(params={
            "FILENAME": '"/data/out.xlsx"',
            "VERSION_2007": "true",
            xml_name: "true",
        })
        result = FileOutputExcelConverter().convert(node, [], {})
        assert any(expected_substring in w for w in result.warnings)

    def test_font_warning_when_not_arial(self):
        node = _make_node(params={
            "FILENAME": '"/data/out.xlsx"',
            "VERSION_2007": "true",
            "FONT": '"Times New Roman"',
        })
        result = FileOutputExcelConverter().convert(node, [], {})
        assert any("FONT=Times New Roman" in w for w in result.warnings)

    def test_no_font_warning_when_arial(self):
        node = _make_node(params={
            "FILENAME": '"/data/out.xlsx"',
            "VERSION_2007": "true",
            "FONT": '"Arial"',
        })
        result = FileOutputExcelConverter().convert(node, [], {})
        assert not any("FONT" in w for w in result.warnings)

    def test_use_output_stream_warning(self):
        node = _make_node(params={
            "FILENAME": '"/data/out.xlsx"',
            "VERSION_2007": "true",
            "USE_OUTPUT_STREAM": "true",
        })
        result = FileOutputExcelConverter().convert(node, [], {})
        assert any("USE_OUTPUT_STREAM" in w for w in result.warnings)


# ---------------------------------------------------------------------------
# Boolean edge cases
# ---------------------------------------------------------------------------

class TestBooleanEdgeCases:
    def test_native_bools(self, converter):
        node = _make_node(params={
            "FILENAME": '"/data/out.xlsx"',
            "INCLUDEHEADER": True,
            "APPEND_FILE": False,
        })
        result = converter.convert(node, [], {})
        cfg = result.component["config"]
        assert cfg["includeheader"] is True
        assert cfg["append_file"] is False

    def test_string_1_0(self, converter):
        node = _make_node(params={
            "FILENAME": '"/data/out.xlsx"',
            "INCLUDEHEADER": "1",
            "APPEND_FILE": "0",
        })
        result = converter.convert(node, [], {})
        cfg = result.component["config"]
        assert cfg["includeheader"] is True
        assert cfg["append_file"] is False


# ---------------------------------------------------------------------------
# Integer edge cases
# ---------------------------------------------------------------------------

class TestIntegerParams:
    def test_quoted_int_strings(self, converter):
        node = _make_node(params={
            "FILENAME": '"/data/out.xlsx"',
            "FIRST_CELL_X": '"3"',
            "FIRST_CELL_Y": '"7"',
            "FLUSH_ON_ROW": '"2000"',
        })
        result = converter.convert(node, [], {})
        cfg = result.component["config"]
        assert cfg["first_cell_x"] == 3
        assert cfg["first_cell_y"] == 7
        assert cfg["flush_on_row"] == 2000


# ---------------------------------------------------------------------------
# Completeness
# ---------------------------------------------------------------------------

class TestCompleteness:
    def test_all_29_config_keys_present(self):
        node = _make_node(params={"FILENAME": '"out.xlsx"'})
        result = FileOutputExcelConverter().convert(node, [], {})
        cfg = result.component["config"]
        expected_keys = {
            "filename", "sheetname", "version_2007", "includeheader",
            "append_file", "append_sheet", "create_directory", "die_on_error",
            "encoding", "font", "auto_size_all",
            "first_cell_y_absolute", "first_cell_x", "first_cell_y",
            "keep_cell_formatting",
            "advanced_separator", "thousands_separator", "decimal_separator",
            "truncate_exceeding_characters", "delete_empty_file", "recalculate_formula",
            "protect_file", "password", "custom_flush_buffer", "flush_on_row",
            "streaming_append", "use_shared_strings_table",
            "tstatcatcher_stats", "label",
        }
        assert set(cfg.keys()) == expected_keys
