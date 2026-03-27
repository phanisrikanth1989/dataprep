"""Tests for tFileRowCount -> FileRowCount converter.

Covers audit fixes:
  CONV-FRC-001 — DIE_ON_ERROR must be extracted.
  CONV-FRC-002 — default encoding is "ISO-8859-15" (Talend default).
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

    def test_default_encoding_is_iso_8859_15(self):
        """Encoding must default to 'ISO-8859-15' when not specified (Talend default)."""
        node = _make_node(params={"FILENAME": '"/tmp/data.csv"'})
        result = FileRowCountConverter().convert(node, [], {})
        assert result.component["config"]["encoding"] == "ISO-8859-15"

    def test_null_safety_empty_params(self):
        """CONV-FRC-005: missing params must not crash; use safe defaults."""
        node = _make_node(params={})
        result = FileRowCountConverter().convert(node, [], {})

        cfg = result.component["config"]
        assert cfg["filename"] == ""
        assert cfg["row_separator"] == "\\n"
        assert cfg["ignore_empty_row"] is False
        assert cfg["encoding"] == "ISO-8859-15"
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


# ---------------------------------------------------------------------------
# New parameters
# ---------------------------------------------------------------------------

class TestNewParams:

    def test_tstatcatcher_stats_default_false(self):
        node = _make_node(params={"FILENAME": '"/tmp/data.csv"'})
        result = FileRowCountConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is False

    def test_tstatcatcher_stats_extracted(self):
        node = _make_node(params={
            "FILENAME": '"/tmp/data.csv"',
            "TSTATCATCHER_STATS": "true",
        })
        result = FileRowCountConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is True

    def test_label_default_empty(self):
        node = _make_node(params={"FILENAME": '"/tmp/data.csv"'})
        result = FileRowCountConverter().convert(node, [], {})
        assert result.component["config"]["label"] == ""

    def test_label_extracted(self):
        node = _make_node(params={
            "FILENAME": '"/tmp/data.csv"',
            "LABEL": '"row_count_step"',
        })
        result = FileRowCountConverter().convert(node, [], {})
        assert result.component["config"]["label"] == "row_count_step"


# ---------------------------------------------------------------------------
# Engine-gap warnings
# ---------------------------------------------------------------------------

class TestEngineGapWarnings:

    def test_no_engine_warnings_for_default_separator(self):
        """Default row_separator is \\n — no warning needed."""
        node = _make_node(params={"FILENAME": '"/tmp/data.csv"'})
        result = FileRowCountConverter().convert(node, [], {})
        engine_warnings = [w for w in result.warnings if "engine" in w.lower()]
        assert engine_warnings == []

    def test_warning_when_row_separator_non_standard(self):
        node = _make_node(params={
            "FILENAME": '"/tmp/data.csv"',
            "ROWSEPARATOR": '"\\r\\n"',
        })
        result = FileRowCountConverter().convert(node, [], {})
        assert any("ROWSEPARATOR" in w for w in result.warnings)

    def test_no_warning_when_row_separator_is_newline(self):
        node = _make_node(params={
            "FILENAME": '"/tmp/data.csv"',
            "ROWSEPARATOR": '"\\n"',
        })
        result = FileRowCountConverter().convert(node, [], {})
        separator_warnings = [w for w in result.warnings if "ROWSEPARATOR" in w]
        assert separator_warnings == []


# ---------------------------------------------------------------------------
# Completeness
# ---------------------------------------------------------------------------

class TestCompleteness:

    def test_all_7_config_keys_present(self):
        node = _make_node(params={"FILENAME": '"/tmp/data.csv"'})
        result = FileRowCountConverter().convert(node, [], {})
        cfg = result.component["config"]
        expected_keys = {
            "filename", "row_separator", "ignore_empty_row",
            "encoding", "die_on_error",
            "tstatcatcher_stats", "label",
        }
        assert set(cfg.keys()) == expected_keys
