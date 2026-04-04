"""Tests for FileTouchConverter (tFileTouch -> v1 FileTouch config)."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.file.file_touch import FileTouchConverter
from src.converters.talend_to_v1.components.registry import REGISTRY


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

def _make_node(params=None, schema=None, component_id="ft_1",
               component_type="tFileTouch"):
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
        assert REGISTRY.get("tFileTouch") is FileTouchConverter


class TestDefaults:
    """Verify all parameters have correct defaults when no params provided."""

    def test_filename_default(self):
        node = _make_node()
        result = FileTouchConverter().convert(node, [], {})
        assert result.component["config"]["filename"] == ""

    def test_createdir_default(self):
        """CRITICAL: _java.xml says CREATEDIR default=false."""
        node = _make_node()
        result = FileTouchConverter().convert(node, [], {})
        assert result.component["config"]["createdir"] is False


class TestParameterExtraction:
    """Verify each parameter is correctly extracted from XML params."""

    def test_filename_extracted(self):
        node = _make_node(params={"FILENAME": '"path/to/file.txt"'})
        result = FileTouchConverter().convert(node, [], {})
        assert result.component["config"]["filename"] == "path/to/file.txt"

    def test_createdir_true(self):
        node = _make_node(params={"CREATEDIR": "true"})
        result = FileTouchConverter().convert(node, [], {})
        assert result.component["config"]["createdir"] is True


class TestFrameworkParams:
    """Verify tstatcatcher_stats and label extraction."""

    def test_tstatcatcher_stats_default_false(self):
        node = _make_node()
        result = FileTouchConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is False

    def test_tstatcatcher_stats_true(self):
        node = _make_node(params={"TSTATCATCHER_STATS": "true"})
        result = FileTouchConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is True

    def test_label_default_empty(self):
        node = _make_node()
        result = FileTouchConverter().convert(node, [], {})
        assert result.component["config"]["label"] == ""

    def test_label_extracted(self):
        node = _make_node(params={"LABEL": '"my_label"'})
        result = FileTouchConverter().convert(node, [], {})
        assert result.component["config"]["label"] == "my_label"


class TestSchema:
    """Verify schema extraction for utility component."""

    def test_schema_is_dict_with_input_output(self):
        """Schema has 'input' and 'output' keys per D-41."""
        node = _make_node()
        result = FileTouchConverter().convert(node, [], {})
        schema = result.component["schema"]
        assert "input" in schema
        assert "output" in schema

    def test_schema_input_empty(self):
        """Utility component per D-56 -- no input schema."""
        node = _make_node()
        result = FileTouchConverter().convert(node, [], {})
        assert result.component["schema"]["input"] == []

    def test_schema_output_empty(self):
        """Utility component per D-56 -- no output schema."""
        node = _make_node()
        result = FileTouchConverter().convert(node, [], {})
        assert result.component["schema"]["output"] == []


class TestNeedsReview:
    """Verify needs_review entries for engine gaps."""

    def test_needs_review_count(self):
        """1 engine gap: createdir vs create_directory."""
        node = _make_node()
        result = FileTouchConverter().convert(node, [], {})
        assert len(result.needs_review) == 1

    def test_needs_review_engine_gap(self):
        node = _make_node()
        result = FileTouchConverter().convert(node, [], {})
        assert result.needs_review[0]["severity"] == "engine_gap"

    def test_needs_review_has_component_id(self):
        node = _make_node(component_id="test_comp")
        result = FileTouchConverter().convert(node, [], {})
        assert result.needs_review[0]["component"] == "test_comp"

    def test_no_framework_param_needs_review(self):
        """Framework params (tstatcatcher_stats, label) must NOT have needs_review."""
        node = _make_node()
        result = FileTouchConverter().convert(node, [], {})
        issues = [e["issue"] for e in result.needs_review]
        for issue in issues:
            assert "tstatcatcher_stats" not in issue
            assert "label" not in issue.lower().split()


class TestCompleteness:
    """Verify all expected config keys are present."""

    def test_all_config_keys_present(self):
        node = _make_node()
        result = FileTouchConverter().convert(node, [], {})
        expected_keys = {
            "filename", "createdir",
            "tstatcatcher_stats", "label",
        }
        actual_keys = set(result.component["config"].keys())
        missing = expected_keys - actual_keys
        assert not missing, f"Missing config keys: {missing}"


class TestComponentStructure:
    """Verify _build_component_dict wrapper output."""

    def test_has_id(self):
        node = _make_node()
        result = FileTouchConverter().convert(node, [], {})
        assert result.component["id"] == "ft_1"

    def test_has_type(self):
        node = _make_node()
        result = FileTouchConverter().convert(node, [], {})
        assert result.component["type"] == "FileTouch"

    def test_has_original_type(self):
        node = _make_node()
        result = FileTouchConverter().convert(node, [], {})
        assert result.component["original_type"] == "tFileTouch"

    def test_has_config(self):
        node = _make_node()
        result = FileTouchConverter().convert(node, [], {})
        assert "config" in result.component

    def test_has_schema(self):
        node = _make_node()
        result = FileTouchConverter().convert(node, [], {})
        assert "schema" in result.component
