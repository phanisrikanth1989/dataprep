"""Tests for FileOutputPositionalConverter (tFileOutputPositional -> FileOutputPositional)."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.file.file_output_positional import (
    FileOutputPositionalConverter,
)
from src.converters.talend_to_v1.components.registry import REGISTRY


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

def _make_node(params=None, schema=None, component_id="fop_1",
               component_type="tFileOutputPositional"):
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
    """Return a sample FLOW schema for testing."""
    return {
        "FLOW": [
            SchemaColumn(name="id", type="id_Integer", nullable=False, key=True, length=10),
            SchemaColumn(name="name", type="id_String", nullable=True, length=50),
        ]
    }


def _make_formats_data(rows):
    """Generate FORMATS TABLE data with stride-5 per row.

    rows: list of tuples (schema_column, size, padding_char, align, keep)
    """
    result = []
    for schema_column, size, padding_char, align, keep in rows:
        result.append({"elementRef": "SCHEMA_COLUMN", "value": schema_column})
        result.append({"elementRef": "SIZE", "value": size})
        result.append({"elementRef": "PADDING_CHAR", "value": padding_char})
        result.append({"elementRef": "ALIGN", "value": align})
        result.append({"elementRef": "KEEP", "value": keep})
    return result


# ------------------------------------------------------------------
# Test Classes (one per concern)
# ------------------------------------------------------------------


class TestRegistration:
    """Verify component is registered correctly."""

    def test_registered_in_registry(self):
        assert REGISTRY.get("tFileOutputPositional") is FileOutputPositionalConverter


class TestDefaults:
    """Verify all parameters have correct defaults when no params provided."""

    def test_use_existing_dynamic_default(self):
        """USE_EXISTING_DYNAMIC defaults to False (was MISSING)."""
        node = _make_node()
        result = FileOutputPositionalConverter().convert(node, [], {})
        assert result.component["config"]["use_existing_dynamic"] is False

    def test_dynamic_default(self):
        """DYNAMIC defaults to empty string (was MISSING)."""
        node = _make_node()
        result = FileOutputPositionalConverter().convert(node, [], {})
        assert result.component["config"]["dynamic"] == ""

    def test_usestream_default(self):
        """USESTREAM defaults to False (was MISSING)."""
        node = _make_node()
        result = FileOutputPositionalConverter().convert(node, [], {})
        assert result.component["config"]["usestream"] is False

    def test_streamname_default(self):
        """STREAMNAME defaults to 'outputStream' (was MISSING)."""
        node = _make_node()
        result = FileOutputPositionalConverter().convert(node, [], {})
        assert result.component["config"]["streamname"] == "outputStream"

    def test_filename_default(self):
        node = _make_node()
        result = FileOutputPositionalConverter().convert(node, [], {})
        assert result.component["config"]["filepath"] == ""

    def test_row_separator_default(self):
        node = _make_node()
        result = FileOutputPositionalConverter().convert(node, [], {})
        assert result.component["config"]["row_separator"] == "\\n"

    def test_append_default(self):
        node = _make_node()
        result = FileOutputPositionalConverter().convert(node, [], {})
        assert result.component["config"]["append"] is False

    def test_include_header_default(self):
        node = _make_node()
        result = FileOutputPositionalConverter().convert(node, [], {})
        assert result.component["config"]["include_header"] is False

    def test_compress_default(self):
        node = _make_node()
        result = FileOutputPositionalConverter().convert(node, [], {})
        assert result.component["config"]["compress"] is False

    def test_formats_default(self):
        node = _make_node()
        result = FileOutputPositionalConverter().convert(node, [], {})
        assert result.component["config"]["formats"] == []

    def test_advanced_separator_default(self):
        node = _make_node()
        result = FileOutputPositionalConverter().convert(node, [], {})
        assert result.component["config"]["advanced_separator"] is False

    def test_thousands_separator_default(self):
        node = _make_node()
        result = FileOutputPositionalConverter().convert(node, [], {})
        assert result.component["config"]["thousands_separator"] == ","

    def test_decimal_separator_default(self):
        node = _make_node()
        result = FileOutputPositionalConverter().convert(node, [], {})
        assert result.component["config"]["decimal_separator"] == "."

    def test_use_byte_default(self):
        node = _make_node()
        result = FileOutputPositionalConverter().convert(node, [], {})
        assert result.component["config"]["use_byte"] is False

    def test_create_default(self):
        node = _make_node()
        result = FileOutputPositionalConverter().convert(node, [], {})
        assert result.component["config"]["create"] is True

    def test_flushonrow_default(self):
        node = _make_node()
        result = FileOutputPositionalConverter().convert(node, [], {})
        assert result.component["config"]["flushonrow"] is False

    def test_flushonrow_num_default(self):
        node = _make_node()
        result = FileOutputPositionalConverter().convert(node, [], {})
        assert result.component["config"]["flushonrow_num"] == "1"

    def test_row_mode_default(self):
        node = _make_node()
        result = FileOutputPositionalConverter().convert(node, [], {})
        assert result.component["config"]["row_mode"] is False

    def test_encoding_default(self):
        node = _make_node()
        result = FileOutputPositionalConverter().convert(node, [], {})
        assert result.component["config"]["encoding"] == "ISO-8859-15"

    def test_delete_empty_file_default(self):
        node = _make_node()
        result = FileOutputPositionalConverter().convert(node, [], {})
        assert result.component["config"]["delete_empty_file"] is False


class TestParameterExtraction:
    """Verify each parameter is correctly extracted from XML params."""

    def test_filename_extracted(self):
        node = _make_node(params={"FILENAME": '"/data/output.pos"'})
        result = FileOutputPositionalConverter().convert(node, [], {})
        assert result.component["config"]["filepath"] == "/data/output.pos"

    def test_append_true(self):
        node = _make_node(params={"APPEND": "true"})
        result = FileOutputPositionalConverter().convert(node, [], {})
        assert result.component["config"]["append"] is True

    def test_encoding_custom(self):
        node = _make_node(params={"ENCODING": '"UTF-8"'})
        result = FileOutputPositionalConverter().convert(node, [], {})
        assert result.component["config"]["encoding"] == "UTF-8"

    def test_use_existing_dynamic_true(self):
        node = _make_node(params={"USE_EXISTING_DYNAMIC": "true"})
        result = FileOutputPositionalConverter().convert(node, [], {})
        assert result.component["config"]["use_existing_dynamic"] is True

    def test_dynamic_extracted(self):
        node = _make_node(params={"DYNAMIC": '"tFileOutputPositional_2"'})
        result = FileOutputPositionalConverter().convert(node, [], {})
        assert result.component["config"]["dynamic"] == "tFileOutputPositional_2"

    def test_usestream_true(self):
        node = _make_node(params={"USESTREAM": "true"})
        result = FileOutputPositionalConverter().convert(node, [], {})
        assert result.component["config"]["usestream"] is True

    def test_streamname_custom(self):
        node = _make_node(params={"STREAMNAME": '"myStream"'})
        result = FileOutputPositionalConverter().convert(node, [], {})
        assert result.component["config"]["streamname"] == "myStream"

    def test_flushonrow_num_as_str(self):
        """FLUSHONROW_NUM stored as str for expression support."""
        node = _make_node(params={"FLUSHONROW_NUM": '"50"'})
        result = FileOutputPositionalConverter().convert(node, [], {})
        assert result.component["config"]["flushonrow_num"] == "50"

    def test_formats_single(self):
        """FORMATS TABLE with 1 entry -> list of 1 dict with 5 fields."""
        fmt_data = _make_formats_data([("id", "10", "' '", "'LEFT'", "'ALL'")])
        node = _make_node(params={"FORMATS": fmt_data})
        result = FileOutputPositionalConverter().convert(node, [], {})
        fmts = result.component["config"]["formats"]
        assert len(fmts) == 1
        assert fmts[0] == {
            "schema_column": "id",
            "size": "10",
            "padding_char": " ",
            "align": "LEFT",
            "keep": "ALL",
        }

    def test_formats_multiple(self):
        """FORMATS TABLE with 3 entries."""
        fmt_data = _make_formats_data([
            ("id", "10", "' '", "'LEFT'", "'ALL'"),
            ("name", "30", "' '", "'RIGHT'", "'LEFT'"),
            ("amount", "15", "'0'", "'RIGHT'", "'RIGHT'"),
        ])
        node = _make_node(params={"FORMATS": fmt_data})
        result = FileOutputPositionalConverter().convert(node, [], {})
        fmts = result.component["config"]["formats"]
        assert len(fmts) == 3
        assert fmts[0]["schema_column"] == "id"
        assert fmts[0]["align"] == "LEFT"
        assert fmts[1]["schema_column"] == "name"
        assert fmts[1]["keep"] == "LEFT"
        assert fmts[2]["padding_char"] == "0"
        assert fmts[2]["align"] == "RIGHT"

    def test_formats_empty_when_missing(self):
        """FORMATS missing -> empty list."""
        node = _make_node()
        result = FileOutputPositionalConverter().convert(node, [], {})
        assert result.component["config"]["formats"] == []

    def test_formats_incomplete_stride_skipped(self):
        """Incomplete trailing group (< 5 entries) is skipped."""
        fmt_data = _make_formats_data([("id", "10", "' '", "'LEFT'", "'ALL'")])
        # Add incomplete trailing entry
        fmt_data.append({"elementRef": "SCHEMA_COLUMN", "value": "orphan"})
        fmt_data.append({"elementRef": "SIZE", "value": "5"})
        node = _make_node(params={"FORMATS": fmt_data})
        result = FileOutputPositionalConverter().convert(node, [], {})
        fmts = result.component["config"]["formats"]
        assert len(fmts) == 1  # Only the complete group


class TestFrameworkParams:
    """Verify tstatcatcher_stats and label extraction."""

    def test_tstatcatcher_stats_default_false(self):
        node = _make_node()
        result = FileOutputPositionalConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is False

    def test_tstatcatcher_stats_true(self):
        node = _make_node(params={"TSTATCATCHER_STATS": "true"})
        result = FileOutputPositionalConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is True

    def test_label_default_empty(self):
        node = _make_node()
        result = FileOutputPositionalConverter().convert(node, [], {})
        assert result.component["config"]["label"] == ""

    def test_label_extracted(self):
        node = _make_node(params={"LABEL": '"my_label"'})
        result = FileOutputPositionalConverter().convert(node, [], {})
        assert result.component["config"]["label"] == "my_label"


class TestSchema:
    """Verify schema extraction for sink component."""

    def test_schema_input_populated(self):
        """Sink component: schema['input'] has columns from FLOW."""
        node = _make_node(schema=_make_schema_columns())
        result = FileOutputPositionalConverter().convert(node, [], {})
        schema = result.component["schema"]
        assert len(schema["input"]) == 2
        assert schema["input"][0]["name"] == "id"
        assert schema["input"][1]["name"] == "name"

    def test_schema_output_empty(self):
        """Sink component: schema['output'] is always empty."""
        node = _make_node(schema=_make_schema_columns())
        result = FileOutputPositionalConverter().convert(node, [], {})
        assert result.component["schema"]["output"] == []


class TestNeedsReview:
    """Verify needs_review entries for engine gaps."""

    def test_needs_review_has_entries(self):
        """Registration gap + engine key mismatches produce needs_review."""
        node = _make_node()
        result = FileOutputPositionalConverter().convert(node, [], {})
        assert len(result.needs_review) >= 1

    def test_all_needs_review_are_engine_gap(self):
        node = _make_node()
        result = FileOutputPositionalConverter().convert(node, [], {})
        for entry in result.needs_review:
            assert entry["severity"] == "engine_gap"

    def test_needs_review_has_component_id(self):
        node = _make_node(component_id="test_comp")
        result = FileOutputPositionalConverter().convert(node, [], {})
        for entry in result.needs_review:
            assert entry["component"] == "test_comp"

    def test_no_framework_param_needs_review(self):
        """Framework params (tstatcatcher_stats, label) must NOT have needs_review."""
        node = _make_node()
        result = FileOutputPositionalConverter().convert(node, [], {})
        issues = [e["issue"] for e in result.needs_review]
        for issue in issues:
            assert "tstatcatcher_stats" not in issue
            assert "label" not in issue.lower().split()

    def test_registration_gap_documented(self):
        """Engine COMPONENT_REGISTRY registration gap is documented."""
        node = _make_node()
        result = FileOutputPositionalConverter().convert(node, [], {})
        issues = [e["issue"] for e in result.needs_review]
        assert any("COMPONENT_REGISTRY" in i or "not registered" in i for i in issues)


class TestCompleteness:
    """Verify all expected config keys are present."""

    def test_all_config_keys_present(self):
        node = _make_node(schema=_make_schema_columns())
        result = FileOutputPositionalConverter().convert(node, [], {})
        expected_keys = {
            # 20 unique params
            "use_existing_dynamic", "dynamic", "usestream", "streamname",
            "filepath", "row_separator", "append", "include_header",
            "compress", "formats", "advanced_separator", "thousands_separator",
            "decimal_separator", "use_byte", "create", "flushonrow",
            "flushonrow_num", "row_mode", "encoding", "delete_empty_file",
            # 2 framework
            "tstatcatcher_stats", "label",
        }
        actual_keys = set(result.component["config"].keys())
        missing = expected_keys - actual_keys
        assert not missing, f"Missing config keys: {missing}"


class TestComponentStructure:
    """Verify the component dict structure."""

    def test_has_type(self):
        node = _make_node()
        result = FileOutputPositionalConverter().convert(node, [], {})
        assert result.component["type"] == "FileOutputPositional"

    def test_has_standard_keys(self):
        node = _make_node()
        result = FileOutputPositionalConverter().convert(node, [], {})
        expected = {"id", "type", "original_type", "position", "config", "schema", "inputs", "outputs"}
        assert set(result.component.keys()) == expected

    def test_returns_component_result(self):
        node = _make_node()
        result = FileOutputPositionalConverter().convert(node, [], {})
        assert isinstance(result, ComponentResult)
