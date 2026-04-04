"""Tests for FileDeleteConverter (tFileDelete -> v1 FileDelete config)."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.file.file_delete import FileDeleteConverter
from src.converters.talend_to_v1.components.registry import REGISTRY


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

def _make_node(params=None, schema=None, component_id="del_1",
               component_type="tFileDelete"):
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
        assert REGISTRY.get("tFileDelete") is FileDeleteConverter


class TestDefaults:
    """Verify all parameters have correct defaults when no params provided."""

    def test_filename_default(self):
        node = _make_node()
        result = FileDeleteConverter().convert(node, [], {})
        assert result.component["config"]["filename"] == ""

    def test_directory_default(self):
        node = _make_node()
        result = FileDeleteConverter().convert(node, [], {})
        assert result.component["config"]["directory"] == ""

    def test_path_default(self):
        node = _make_node()
        result = FileDeleteConverter().convert(node, [], {})
        assert result.component["config"]["path"] == ""

    def test_failon_default(self):
        """CRITICAL: _java.xml says FAILON default=true."""
        node = _make_node()
        result = FileDeleteConverter().convert(node, [], {})
        assert result.component["config"]["failon"] is True

    def test_folder_default(self):
        node = _make_node()
        result = FileDeleteConverter().convert(node, [], {})
        assert result.component["config"]["folder"] is False

    def test_folder_file_default(self):
        node = _make_node()
        result = FileDeleteConverter().convert(node, [], {})
        assert result.component["config"]["folder_file"] is False


class TestParameterExtraction:
    """Verify each parameter is correctly extracted from XML params."""

    def test_filename_extracted(self):
        node = _make_node(params={"FILENAME": '"file.txt"'})
        result = FileDeleteConverter().convert(node, [], {})
        assert result.component["config"]["filename"] == "file.txt"

    def test_directory_extracted(self):
        node = _make_node(params={"DIRECTORY": '"/tmp/dir"'})
        result = FileDeleteConverter().convert(node, [], {})
        assert result.component["config"]["directory"] == "/tmp/dir"

    def test_path_extracted(self):
        node = _make_node(params={"PATH": '"/tmp/path"'})
        result = FileDeleteConverter().convert(node, [], {})
        assert result.component["config"]["path"] == "/tmp/path"

    def test_failon_false(self):
        node = _make_node(params={"FAILON": "false"})
        result = FileDeleteConverter().convert(node, [], {})
        assert result.component["config"]["failon"] is False

    def test_folder_true(self):
        node = _make_node(params={"FOLDER": "true"})
        result = FileDeleteConverter().convert(node, [], {})
        assert result.component["config"]["folder"] is True

    def test_folder_file_true(self):
        node = _make_node(params={"FOLDER_FILE": "true"})
        result = FileDeleteConverter().convert(node, [], {})
        assert result.component["config"]["folder_file"] is True


class TestFrameworkParams:
    """Verify tstatcatcher_stats and label extraction."""

    def test_tstatcatcher_stats_default_false(self):
        node = _make_node()
        result = FileDeleteConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is False

    def test_tstatcatcher_stats_true(self):
        node = _make_node(params={"TSTATCATCHER_STATS": "true"})
        result = FileDeleteConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is True

    def test_label_default_empty(self):
        node = _make_node()
        result = FileDeleteConverter().convert(node, [], {})
        assert result.component["config"]["label"] == ""

    def test_label_extracted(self):
        node = _make_node(params={"LABEL": '"my_label"'})
        result = FileDeleteConverter().convert(node, [], {})
        assert result.component["config"]["label"] == "my_label"


class TestSchema:
    """Verify schema extraction for utility component."""

    def test_schema_input_empty(self):
        """Utility component per D-56 -- no input schema."""
        node = _make_node()
        result = FileDeleteConverter().convert(node, [], {})
        assert result.component["schema"]["input"] == []

    def test_schema_output_empty(self):
        """Utility component per D-56 -- no output schema."""
        node = _make_node()
        result = FileDeleteConverter().convert(node, [], {})
        assert result.component["schema"]["output"] == []


class TestNeedsReview:
    """Verify needs_review entries for engine gaps."""

    def test_needs_review_has_entries(self):
        """Engine key mismatches documented as needs_review."""
        node = _make_node()
        result = FileDeleteConverter().convert(node, [], {})
        assert len(result.needs_review) > 0

    def test_all_needs_review_are_engine_gap(self):
        node = _make_node()
        result = FileDeleteConverter().convert(node, [], {})
        for entry in result.needs_review:
            assert entry["severity"] == "engine_gap"

    def test_needs_review_has_component_id(self):
        node = _make_node(component_id="test_comp")
        result = FileDeleteConverter().convert(node, [], {})
        for entry in result.needs_review:
            assert entry["component"] == "test_comp"

    def test_no_framework_param_needs_review(self):
        """Framework params (tstatcatcher_stats, label) must NOT have needs_review."""
        node = _make_node()
        result = FileDeleteConverter().convert(node, [], {})
        issues = [e["issue"] for e in result.needs_review]
        for issue in issues:
            assert "tstatcatcher_stats" not in issue
            assert "label" not in issue.lower().split()


class TestPhantomParams:
    """Verify params NOT in _java.xml are NOT extracted."""

    def test_no_fail_on_error_key(self):
        """FAIL_ON_ERROR is phantom -- actual _java.xml name is FAILON."""
        node = _make_node(params={"FAIL_ON_ERROR": "true"})
        result = FileDeleteConverter().convert(node, [], {})
        assert "fail_on_error" not in result.component["config"]

    def test_no_folder_file_path_key(self):
        """FOLDER_FILE_PATH is phantom -- actual _java.xml name is PATH."""
        node = _make_node(params={"FOLDER_FILE_PATH": '"/tmp/test"'})
        result = FileDeleteConverter().convert(node, [], {})
        assert "folder_file_path" not in result.component["config"]


class TestCompleteness:
    """Verify all expected config keys are present."""

    def test_all_config_keys_present(self):
        node = _make_node()
        result = FileDeleteConverter().convert(node, [], {})
        expected_keys = {
            "filename", "directory", "path", "failon",
            "folder", "folder_file",
            "tstatcatcher_stats", "label",
        }
        actual_keys = set(result.component["config"].keys())
        missing = expected_keys - actual_keys
        assert not missing, f"Missing config keys: {missing}"


class TestComponentStructure:
    """Verify _build_component_dict wrapper output."""

    def test_has_type(self):
        node = _make_node()
        result = FileDeleteConverter().convert(node, [], {})
        assert result.component["type"] == "FileDelete"

    def test_has_id(self):
        node = _make_node()
        result = FileDeleteConverter().convert(node, [], {})
        assert result.component["id"] == "del_1"

    def test_has_original_type(self):
        node = _make_node()
        result = FileDeleteConverter().convert(node, [], {})
        assert result.component["original_type"] == "tFileDelete"

    def test_has_config(self):
        node = _make_node()
        result = FileDeleteConverter().convert(node, [], {})
        assert "config" in result.component

    def test_has_schema(self):
        node = _make_node()
        result = FileDeleteConverter().convert(node, [], {})
        assert "schema" in result.component
