"""Tests for FileOutputDelimitedConverter (tFileOutputDelimited -> FileOutputDelimited)."""
import xml.etree.ElementTree as ET

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


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

def _make_node(params=None, schema=None, component_id="output_1",
               component_type="tFileOutputDelimited"):
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
    """Return a sample FLOW schema for testing (sink component)."""
    return {
        "FLOW": [
            SchemaColumn(name="id", type="id_Integer", nullable=False, key=True, length=10),
            SchemaColumn(name="name", type="id_String", nullable=True, length=50),
            SchemaColumn(name="amount", type="id_Double", nullable=True, precision=2),
        ]
    }


# ------------------------------------------------------------------
# Test Classes
# ------------------------------------------------------------------


class TestRegistration:
    """Verify component is registered correctly."""

    def test_registered_in_registry(self):
        assert REGISTRY.get("tFileOutputDelimited") is FileOutputDelimitedConverter


class TestDefaults:
    """Verify all parameters have correct defaults when no params provided."""

    def test_usestream_default(self):
        node = _make_node()
        result = FileOutputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["usestream"] is False

    def test_streamname_default(self):
        node = _make_node()
        result = FileOutputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["streamname"] == "outputStream"

    def test_filepath_default(self):
        node = _make_node()
        result = FileOutputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["filepath"] == ""

    def test_row_separator_default(self):
        node = _make_node()
        result = FileOutputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["row_separator"] == "\\n"

    def test_fieldseparator_default(self):
        node = _make_node()
        result = FileOutputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["fieldseparator"] == ";"

    def test_append_default(self):
        node = _make_node()
        result = FileOutputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["append"] is False

    def test_include_header_default(self):
        node = _make_node()
        result = FileOutputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["include_header"] is False

    def test_compress_default(self):
        node = _make_node()
        result = FileOutputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["compress"] is False

    def test_csv_option_default(self):
        node = _make_node()
        result = FileOutputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["csv_option"] is False

    def test_escape_char_default(self):
        node = _make_node()
        result = FileOutputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["escape_char"] == '"'

    def test_text_enclosure_default(self):
        node = _make_node()
        result = FileOutputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["text_enclosure"] == '"'

    def test_os_line_separator_default(self):
        node = _make_node()
        result = FileOutputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["os_line_separator"] is True

    def test_csvrowseparator_default(self):
        node = _make_node()
        result = FileOutputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["csvrowseparator"] == "LF"

    def test_create_directory_default(self):
        node = _make_node()
        result = FileOutputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["create_directory"] is True

    def test_split_default(self):
        node = _make_node()
        result = FileOutputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["split"] is False

    def test_split_every_default(self):
        node = _make_node()
        result = FileOutputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["split_every"] == "1000"

    def test_flushonrow_default(self):
        node = _make_node()
        result = FileOutputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["flushonrow"] is False

    def test_flush_row_count_default(self):
        node = _make_node()
        result = FileOutputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["flush_row_count"] == "1"

    def test_row_mode_default(self):
        node = _make_node()
        result = FileOutputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["row_mode"] is False

    def test_encoding_default(self):
        node = _make_node()
        result = FileOutputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["encoding"] == "ISO-8859-15"

    def test_delete_empty_file_default(self):
        node = _make_node()
        result = FileOutputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["delete_empty_file"] is False

    def test_file_exist_exception_default(self):
        """CRITICAL: FILE_EXIST_EXCEPTION defaults to True per _java.xml (was False)."""
        node = _make_node()
        result = FileOutputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["file_exist_exception"] is True

    def test_advanced_separator_default(self):
        node = _make_node()
        result = FileOutputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["advanced_separator"] is False

    def test_thousands_separator_default(self):
        node = _make_node()
        result = FileOutputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["thousands_separator"] == ","

    def test_decimal_separator_default(self):
        node = _make_node()
        result = FileOutputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["decimal_separator"] == "."


class TestParameterExtraction:
    """Verify each parameter is correctly extracted from XML params."""

    def test_filepath_extracted(self):
        node = _make_node(params={"FILENAME": '"/tmp/output.csv"'})
        result = FileOutputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["filepath"] == "/tmp/output.csv"

    def test_fieldseparator_custom(self):
        node = _make_node(params={"FIELDSEPARATOR": '"|"'})
        result = FileOutputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["fieldseparator"] == "|"

    def test_encoding_custom(self):
        node = _make_node(params={"ENCODING": '"UTF-8"'})
        result = FileOutputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["encoding"] == "UTF-8"

    def test_file_exist_exception_false(self):
        node = _make_node(params={"FILE_EXIST_EXCEPTION": "false"})
        result = FileOutputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["file_exist_exception"] is False

    def test_csvrowseparator_custom(self):
        node = _make_node(params={"CSVROWSEPARATOR": '"CRLF"'})
        result = FileOutputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["csvrowseparator"] == "CRLF"

    def test_split_every_extracted(self):
        node = _make_node(params={"SPLIT_EVERY": '"500"'})
        result = FileOutputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["split_every"] == "500"

    def test_flush_row_count_extracted(self):
        node = _make_node(params={"FLUSHONROW_NUM": '"100"'})
        result = FileOutputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["flush_row_count"] == "100"

    def test_streamname_extracted(self):
        node = _make_node(params={"STREAMNAME": '"myStream"'})
        result = FileOutputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["streamname"] == "myStream"

    def test_text_enclosure_extracted(self):
        node = _make_node(params={"TEXT_ENCLOSURE": "\"'\""})
        result = FileOutputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["text_enclosure"] == "'"


class TestFrameworkParams:
    """Verify tstatcatcher_stats and label extraction."""

    def test_tstatcatcher_stats_default_false(self):
        node = _make_node()
        result = FileOutputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is False

    def test_tstatcatcher_stats_true(self):
        node = _make_node(params={"TSTATCATCHER_STATS": "true"})
        result = FileOutputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is True

    def test_label_default_empty(self):
        node = _make_node()
        result = FileOutputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["label"] == ""

    def test_label_extracted(self):
        node = _make_node(params={"LABEL": '"my_label"'})
        result = FileOutputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["label"] == "my_label"


class TestSchema:
    """Verify schema extraction -- sink component: input populated, output empty."""

    def test_schema_input_populated(self):
        """Sink component: schema.input has columns from _parse_schema."""
        node = _make_node(schema=_make_schema_columns())
        result = FileOutputDelimitedConverter().convert(node, [], {})
        schema = result.component["schema"]
        assert len(schema["input"]) == 3
        assert schema["input"][0]["name"] == "id"
        assert schema["input"][0]["type"] == "int"

    def test_schema_output_empty(self):
        """Sink component: schema.output is always empty."""
        node = _make_node(schema=_make_schema_columns())
        result = FileOutputDelimitedConverter().convert(node, [], {})
        assert result.component["schema"]["output"] == []


class TestNeedsReview:
    """Verify needs_review entries for engine gaps."""

    def test_needs_review_delimiter_mismatch(self):
        """Engine uses ',' delimiter default, _java.xml uses ';'."""
        node = _make_node()
        result = FileOutputDelimitedConverter().convert(node, [], {})
        issues = [e["issue"] for e in result.needs_review]
        assert any("fieldseparator" in i or "delimiter" in i for i in issues)

    def test_needs_review_encoding_mismatch(self):
        """Engine uses UTF-8 encoding default, _java.xml uses ISO-8859-15."""
        node = _make_node()
        result = FileOutputDelimitedConverter().convert(node, [], {})
        issues = [e["issue"] for e in result.needs_review]
        assert any("encoding" in i.lower() for i in issues)

    def test_needs_review_include_header_mismatch(self):
        """Engine uses include_header=True default, _java.xml uses False."""
        node = _make_node()
        result = FileOutputDelimitedConverter().convert(node, [], {})
        issues = [e["issue"] for e in result.needs_review]
        assert any("include_header" in i for i in issues)

    def test_all_needs_review_are_engine_gap(self):
        node = _make_node()
        result = FileOutputDelimitedConverter().convert(node, [], {})
        for entry in result.needs_review:
            assert entry["severity"] == "engine_gap"

    def test_needs_review_has_component_id(self):
        node = _make_node(component_id="test_comp")
        result = FileOutputDelimitedConverter().convert(node, [], {})
        for entry in result.needs_review:
            assert entry["component"] == "test_comp"

    def test_no_framework_param_needs_review(self):
        """Framework params (tstatcatcher_stats, label) must NOT have needs_review."""
        node = _make_node()
        result = FileOutputDelimitedConverter().convert(node, [], {})
        issues = [e["issue"] for e in result.needs_review]
        for issue in issues:
            assert "tstatcatcher_stats" not in issue
            assert "label" not in issue.lower().split()


class TestCompleteness:
    """Verify all expected config keys are present."""

    def test_all_config_keys_present(self):
        node = _make_node(schema=_make_schema_columns())
        result = FileOutputDelimitedConverter().convert(node, [], {})
        expected_keys = {
            # ~28 unique params
            "usestream", "streamname", "filepath", "row_separator",
            "fieldseparator", "append", "include_header", "compress",
            "csv_option", "escape_char", "text_enclosure",
            "os_line_separator", "csvrowseparator",
            "create_directory", "split", "split_every",
            "flushonrow", "flush_row_count", "row_mode",
            "encoding", "delete_empty_file", "file_exist_exception",
            "advanced_separator", "thousands_separator", "decimal_separator",
            # framework
            "tstatcatcher_stats", "label",
        }
        actual_keys = set(result.component["config"].keys())
        missing = expected_keys - actual_keys
        extra = actual_keys - expected_keys
        assert not missing, f"Missing config keys: {missing}"
        assert not extra, f"Extra config keys: {extra}"


class TestComponentStructure:
    """Verify the component dict structure."""

    def test_has_type(self):
        node = _make_node()
        result = FileOutputDelimitedConverter().convert(node, [], {})
        assert result.component["type"] == "FileOutputDelimited"

    def test_has_original_type(self):
        node = _make_node()
        result = FileOutputDelimitedConverter().convert(node, [], {})
        assert result.component["original_type"] == "tFileOutputDelimited"

    def test_has_id(self):
        node = _make_node(component_id="my_output")
        result = FileOutputDelimitedConverter().convert(node, [], {})
        assert result.component["id"] == "my_output"

    def test_returns_component_result(self):
        node = _make_node()
        result = FileOutputDelimitedConverter().convert(node, [], {})
        assert isinstance(result, ComponentResult)

    def test_has_position(self):
        node = _make_node()
        result = FileOutputDelimitedConverter().convert(node, [], {})
        assert result.component["position"] == {"x": 100, "y": 200}
