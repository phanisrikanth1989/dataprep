"""Tests for tFileRowCount -> FileRowCount converter.

Covers audit fixes:
  CONV-FRC-001 — DIE_ON_ERROR must be extracted.
  CONV-FRC-002 — default encoding is "UTF-8".
  CONV-FRC-005 — null-safety (missing params must not crash).
"""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    TalendNode,
)
from src.converters.talend_to_v1.components.file.file_row_count import (
    FileRowCountConverter,
)
from src.converters.talend_to_v1.components.registry import REGISTRY


def _make_node(params=None, component_id="tFileRowCount_1",
               component_type="tFileRowCount", schema=None):
    return TalendNode(
        component_id=component_id,
        component_type=component_type,
        params=params or {},
        schema=schema or {},
        position={"x": 64, "y": 128},
        raw_xml=ET.Element("node"),
    )


class TestFileRowCountConverter:
    """Core conversion logic."""

    def test_basic_conversion_all_params(self):
        """All five config params should appear in the output."""
        node = _make_node(params={
            "FILENAME": '"/data/input.csv"',
            "ROWSEPARATOR": '"\\n"',
            "IGNORE_EMPTY_ROW": "true",
            "ENCODING": '"ISO-8859-1"',
            "DIE_ON_ERROR": "true",
        })
        result = FileRowCountConverter().convert(node, [], {})

        assert isinstance(result, ComponentResult)
        comp = result.component
        assert comp["id"] == "tFileRowCount_1"
        assert comp["type"] == "FileRowCount"
        assert comp["original_type"] == "tFileRowCount"
        assert comp["position"] == {"x": 64, "y": 128}

        cfg = comp["config"]
        assert cfg["filename"] == "/data/input.csv"
        assert cfg["row_separator"] == "\\n"
        assert cfg["ignore_empty_row"] is True
        assert cfg["encoding"] == "ISO-8859-1"
        assert cfg["die_on_error"] is True
        assert result.warnings == []

    def test_die_on_error_extracted(self):
        """CONV-FRC-001: die_on_error must be present in config."""
        node = _make_node(params={
            "FILENAME": '"/tmp/file.txt"',
            "DIE_ON_ERROR": "true",
        })
        result = FileRowCountConverter().convert(node, [], {})
        assert result.component["config"]["die_on_error"] is True

    def test_die_on_error_defaults_false(self):
        """CONV-FRC-001: die_on_error defaults to False when absent."""
        node = _make_node(params={
            "FILENAME": '"/tmp/file.txt"',
        })
        result = FileRowCountConverter().convert(node, [], {})
        assert result.component["config"]["die_on_error"] is False

    def test_default_encoding_is_utf8(self):
        """CONV-FRC-002: encoding must default to 'UTF-8' when not specified."""
        node = _make_node(params={"FILENAME": '"/tmp/data.csv"'})
        result = FileRowCountConverter().convert(node, [], {})
        assert result.component["config"]["encoding"] == "UTF-8"

    def test_null_safety_empty_params(self):
        """CONV-FRC-005: missing params must not crash; use safe defaults."""
        node = _make_node(params={})
        result = FileRowCountConverter().convert(node, [], {})

        cfg = result.component["config"]
        assert cfg["filename"] == ""
        assert cfg["row_separator"] == "\\n"
        assert cfg["ignore_empty_row"] is False
        assert cfg["encoding"] == "UTF-8"
        assert cfg["die_on_error"] is False
        # Missing filename should generate a warning
        assert len(result.warnings) == 1
        assert "FILENAME is empty" in result.warnings[0]

    def test_filename_without_quotes(self):
        node = _make_node(params={"FILENAME": "/opt/files/output.txt"})
        result = FileRowCountConverter().convert(node, [], {})
        assert result.component["config"]["filename"] == "/opt/files/output.txt"

    def test_empty_filename_generates_warning(self):
        node = _make_node(params={"FILENAME": ""})
        result = FileRowCountConverter().convert(node, [], {})
        assert result.component["config"]["filename"] == ""
        assert len(result.warnings) == 1
        assert "FILENAME is empty" in result.warnings[0]

    def test_ignore_empty_row_false_by_default(self):
        node = _make_node(params={"FILENAME": '"/tmp/f.csv"'})
        result = FileRowCountConverter().convert(node, [], {})
        assert result.component["config"]["ignore_empty_row"] is False

    def test_schema_structure(self):
        """Output should have input=[] and output=[] (or parsed schema)."""
        node = _make_node(params={"FILENAME": '"/tmp/test"'})
        result = FileRowCountConverter().convert(node, [], {})
        assert result.component["schema"]["input"] == []

    def test_component_structure_has_io_lists(self):
        node = _make_node(params={"FILENAME": '"/tmp/test"'})
        result = FileRowCountConverter().convert(node, [], {})
        assert result.component["inputs"] == []
        assert result.component["outputs"] == []


class TestFileRowCountRegistry:
    """Verify the converter is properly registered."""

    def test_registered_under_tfilerowcount(self):
        cls = REGISTRY.get("tFileRowCount")
        assert cls is FileRowCountConverter

    def test_tfilerowcount_in_type_list(self):
        assert "tFileRowCount" in REGISTRY.list_types()
