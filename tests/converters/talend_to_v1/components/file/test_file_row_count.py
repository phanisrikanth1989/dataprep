"""Tests for FileRowCountConverter (tFileRowCount -> v1 FileRowCount config)."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.file.file_row_count import (
    FileRowCountConverter,
)
from src.converters.talend_to_v1.components.registry import REGISTRY


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

def _make_node(params=None, schema=None, component_id="frc_1",
               component_type="tFileRowCount"):
    """Create a TalendNode for testing."""
    return TalendNode(
        component_id=component_id,
        component_type=component_type,
        params=params or {},
        schema=schema or {},
        position={"x": 100, "y": 200},
        raw_xml=ET.Element("node"),
    )


# ------------------------------------------------------------------
# Test Classes (one per concern)
# ------------------------------------------------------------------


class TestRegistration:
    """Verify component is registered correctly."""

    def test_registered_in_registry(self):
        assert REGISTRY.get("tFileRowCount") is FileRowCountConverter


class TestDefaults:
    """Verify all parameters have correct defaults when no params provided."""

    def test_filename_default(self):
        node = _make_node()
        result = FileRowCountConverter().convert(node, [], {})
        assert result.component["config"]["filename"] == ""

    def test_row_separator_default(self):
        node = _make_node()
        result = FileRowCountConverter().convert(node, [], {})
        assert result.component["config"]["row_separator"] == "\\n"

    def test_ignore_empty_row_default(self):
        node = _make_node()
        result = FileRowCountConverter().convert(node, [], {})
        assert result.component["config"]["ignore_empty_row"] is False

    def test_encoding_default(self):
        """CRITICAL: _java.xml says ENCODING default=ISO-8859-15, NOT UTF-8."""
        node = _make_node()
        result = FileRowCountConverter().convert(node, [], {})
        assert result.component["config"]["encoding"] == "ISO-8859-15"


class TestParameterExtraction:
    """Verify each parameter is correctly extracted from XML params."""

    def test_filename_extracted(self):
        node = _make_node(params={"FILENAME": '"data.csv"'})
        result = FileRowCountConverter().convert(node, [], {})
        assert result.component["config"]["filename"] == "data.csv"

    def test_row_separator_custom(self):
        node = _make_node(params={"ROWSEPARATOR": '"\\r\\n"'})
        result = FileRowCountConverter().convert(node, [], {})
        assert result.component["config"]["row_separator"] == "\\r\\n"

    def test_ignore_empty_row_true(self):
        node = _make_node(params={"IGNORE_EMPTY_ROW": "true"})
        result = FileRowCountConverter().convert(node, [], {})
        assert result.component["config"]["ignore_empty_row"] is True

    def test_encoding_custom(self):
        node = _make_node(params={"ENCODING": '"UTF-8"'})
        result = FileRowCountConverter().convert(node, [], {})
        assert result.component["config"]["encoding"] == "UTF-8"


class TestFrameworkParams:
    """Verify tstatcatcher_stats and label extraction."""

    def test_tstatcatcher_stats_default_false(self):
        node = _make_node()
        result = FileRowCountConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is False

    def test_tstatcatcher_stats_true(self):
        node = _make_node(params={"TSTATCATCHER_STATS": "true"})
        result = FileRowCountConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is True

    def test_label_default_empty(self):
        node = _make_node()
        result = FileRowCountConverter().convert(node, [], {})
        assert result.component["config"]["label"] == ""

    def test_label_extracted(self):
        node = _make_node(params={"LABEL": '"my_label"'})
        result = FileRowCountConverter().convert(node, [], {})
        assert result.component["config"]["label"] == "my_label"


class TestSchema:
    """Verify schema extraction for utility component."""

    def test_schema_input_empty(self):
        """Utility component per D-56 -- no input schema."""
        node = _make_node()
        result = FileRowCountConverter().convert(node, [], {})
        assert result.component["schema"]["input"] == []

    def test_schema_output_empty(self):
        """Utility component per D-56 -- no output schema."""
        node = _make_node()
        result = FileRowCountConverter().convert(node, [], {})
        assert result.component["schema"]["output"] == []


class TestNeedsReview:
    """Verify needs_review entries for engine gaps."""

    def test_needs_review_encoding_mismatch(self):
        """Engine default UTF-8 vs _java.xml ISO-8859-15."""
        node = _make_node()
        result = FileRowCountConverter().convert(node, [], {})
        issues = [e["issue"] for e in result.needs_review]
        assert any("encoding" in i for i in issues)

    def test_all_needs_review_are_engine_gap(self):
        node = _make_node()
        result = FileRowCountConverter().convert(node, [], {})
        for entry in result.needs_review:
            assert entry["severity"] == "engine_gap"

    def test_needs_review_has_component_id(self):
        node = _make_node(component_id="test_comp")
        result = FileRowCountConverter().convert(node, [], {})
        for entry in result.needs_review:
            assert entry["component"] == "test_comp"

    def test_no_framework_param_needs_review(self):
        """Framework params (tstatcatcher_stats, label) must NOT have needs_review."""
        node = _make_node()
        result = FileRowCountConverter().convert(node, [], {})
        issues = [e["issue"] for e in result.needs_review]
        for issue in issues:
            assert "tstatcatcher_stats" not in issue
            assert "label" not in issue.lower().split()


class TestPhantomParams:
    """Verify params NOT in _java.xml are NOT extracted."""

    def test_no_die_on_error_key(self):
        """DIE_ON_ERROR is phantom -- not in _java.xml for tFileRowCount."""
        node = _make_node(params={"DIE_ON_ERROR": "true"})
        result = FileRowCountConverter().convert(node, [], {})
        assert "die_on_error" not in result.component["config"]


class TestCompleteness:
    """Verify all expected config keys are present."""

    def test_all_config_keys_present(self):
        node = _make_node()
        result = FileRowCountConverter().convert(node, [], {})
        expected_keys = {
            "filename", "row_separator", "ignore_empty_row", "encoding",
            "tstatcatcher_stats", "label",
        }
        actual_keys = set(result.component["config"].keys())
        missing = expected_keys - actual_keys
        assert not missing, f"Missing config keys: {missing}"


class TestComponentStructure:
    """Verify _build_component_dict wrapper output."""

    def test_has_type(self):
        node = _make_node()
        result = FileRowCountConverter().convert(node, [], {})
        assert result.component["type"] == "FileRowCount"

    def test_has_id(self):
        node = _make_node()
        result = FileRowCountConverter().convert(node, [], {})
        assert result.component["id"] == "frc_1"

    def test_has_original_type(self):
        node = _make_node()
        result = FileRowCountConverter().convert(node, [], {})
        assert result.component["original_type"] == "tFileRowCount"

    def test_has_config(self):
        node = _make_node()
        result = FileRowCountConverter().convert(node, [], {})
        assert "config" in result.component

    def test_has_schema(self):
        node = _make_node()
        result = FileRowCountConverter().convert(node, [], {})
        assert "schema" in result.component
