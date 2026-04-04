"""Tests for FileCopyConverter (tFileCopy -> v1 FileCopy config)."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.file.file_copy import FileCopyConverter
from src.converters.talend_to_v1.components.registry import REGISTRY


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

def _make_node(params=None, schema=None, component_id="fc_1",
               component_type="tFileCopy"):
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
        assert REGISTRY.get("tFileCopy") is FileCopyConverter


class TestDefaults:
    """Verify all parameters have correct defaults when no params provided."""

    def test_filename_default(self):
        node = _make_node()
        result = FileCopyConverter().convert(node, [], {})
        assert result.component["config"]["filename"] == ""

    def test_enable_copy_directory_default(self):
        node = _make_node()
        result = FileCopyConverter().convert(node, [], {})
        assert result.component["config"]["enable_copy_directory"] is False

    def test_source_derectory_default(self):
        """Talend typo preserved: SOURCE_DERECTORY (not DIRECTORY)."""
        node = _make_node()
        result = FileCopyConverter().convert(node, [], {})
        assert result.component["config"]["source_derectory"] == ""

    def test_destination_default(self):
        node = _make_node()
        result = FileCopyConverter().convert(node, [], {})
        assert result.component["config"]["destination"] == ""

    def test_rename_default(self):
        node = _make_node()
        result = FileCopyConverter().convert(node, [], {})
        assert result.component["config"]["rename"] is False

    def test_destination_rename_default(self):
        node = _make_node()
        result = FileCopyConverter().convert(node, [], {})
        assert result.component["config"]["destination_rename"] == "NewName.temp"

    def test_remove_file_default(self):
        """CRITICAL: _java.xml name is REMOVE_FILE not REMOVE_SOURCE_FILE."""
        node = _make_node()
        result = FileCopyConverter().convert(node, [], {})
        assert result.component["config"]["remove_file"] is False

    def test_replace_file_default(self):
        """CRITICAL: _java.xml default is True (was False in old converter)."""
        node = _make_node()
        result = FileCopyConverter().convert(node, [], {})
        assert result.component["config"]["replace_file"] is True

    def test_create_directory_default(self):
        """CRITICAL: _java.xml default is True (was False in old converter)."""
        node = _make_node()
        result = FileCopyConverter().convert(node, [], {})
        assert result.component["config"]["create_directory"] is True

    def test_failon_default(self):
        node = _make_node()
        result = FileCopyConverter().convert(node, [], {})
        assert result.component["config"]["failon"] is False

    def test_force_copy_delete_default(self):
        node = _make_node()
        result = FileCopyConverter().convert(node, [], {})
        assert result.component["config"]["force_copy_delete"] is False

    def test_preserve_last_modified_time_default(self):
        node = _make_node()
        result = FileCopyConverter().convert(node, [], {})
        assert result.component["config"]["preserve_last_modified_time"] is False


class TestParameterExtraction:
    """Verify each parameter is correctly extracted from XML params."""

    def test_filename_extracted(self):
        node = _make_node(params={"FILENAME": '"source.csv"'})
        result = FileCopyConverter().convert(node, [], {})
        assert result.component["config"]["filename"] == "source.csv"

    def test_enable_copy_directory_true(self):
        node = _make_node(params={"ENABLE_COPY_DIRECTORY": "true"})
        result = FileCopyConverter().convert(node, [], {})
        assert result.component["config"]["enable_copy_directory"] is True

    def test_source_derectory_extracted(self):
        node = _make_node(params={"SOURCE_DERECTORY": '"/tmp/src"'})
        result = FileCopyConverter().convert(node, [], {})
        assert result.component["config"]["source_derectory"] == "/tmp/src"

    def test_destination_extracted(self):
        node = _make_node(params={"DESTINATION": '"/tmp/dest"'})
        result = FileCopyConverter().convert(node, [], {})
        assert result.component["config"]["destination"] == "/tmp/dest"

    def test_rename_true(self):
        node = _make_node(params={"RENAME": "true"})
        result = FileCopyConverter().convert(node, [], {})
        assert result.component["config"]["rename"] is True

    def test_destination_rename_extracted(self):
        node = _make_node(params={"DESTINATION_RENAME": '"backup.csv"'})
        result = FileCopyConverter().convert(node, [], {})
        assert result.component["config"]["destination_rename"] == "backup.csv"

    def test_remove_file_true(self):
        node = _make_node(params={"REMOVE_FILE": "true"})
        result = FileCopyConverter().convert(node, [], {})
        assert result.component["config"]["remove_file"] is True

    def test_replace_file_false(self):
        node = _make_node(params={"REPLACE_FILE": "false"})
        result = FileCopyConverter().convert(node, [], {})
        assert result.component["config"]["replace_file"] is False

    def test_create_directory_false(self):
        node = _make_node(params={"CREATE_DIRECTORY": "false"})
        result = FileCopyConverter().convert(node, [], {})
        assert result.component["config"]["create_directory"] is False

    def test_failon_true(self):
        node = _make_node(params={"FAILON": "true"})
        result = FileCopyConverter().convert(node, [], {})
        assert result.component["config"]["failon"] is True

    def test_force_copy_delete_true(self):
        node = _make_node(params={"FORCE_COPY_DELETE": "true"})
        result = FileCopyConverter().convert(node, [], {})
        assert result.component["config"]["force_copy_delete"] is True

    def test_preserve_last_modified_time_true(self):
        node = _make_node(params={"PRESERVE_LAST_MODIFIED_TIME": "true"})
        result = FileCopyConverter().convert(node, [], {})
        assert result.component["config"]["preserve_last_modified_time"] is True


class TestFrameworkParams:
    """Verify tstatcatcher_stats and label extraction."""

    def test_tstatcatcher_stats_default_false(self):
        node = _make_node()
        result = FileCopyConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is False

    def test_tstatcatcher_stats_true(self):
        node = _make_node(params={"TSTATCATCHER_STATS": "true"})
        result = FileCopyConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is True

    def test_label_default_empty(self):
        node = _make_node()
        result = FileCopyConverter().convert(node, [], {})
        assert result.component["config"]["label"] == ""

    def test_label_extracted(self):
        node = _make_node(params={"LABEL": '"my_label"'})
        result = FileCopyConverter().convert(node, [], {})
        assert result.component["config"]["label"] == "my_label"


class TestSchema:
    """Verify schema extraction for utility component."""

    def test_schema_is_dict_with_input_output(self):
        """Schema has 'input' and 'output' keys per D-41."""
        node = _make_node()
        result = FileCopyConverter().convert(node, [], {})
        schema = result.component["schema"]
        assert "input" in schema
        assert "output" in schema

    def test_schema_input_empty(self):
        """Utility component per D-56 -- no input schema."""
        node = _make_node()
        result = FileCopyConverter().convert(node, [], {})
        assert result.component["schema"]["input"] == []

    def test_schema_output_empty(self):
        """Utility component per D-56 -- no output schema."""
        node = _make_node()
        result = FileCopyConverter().convert(node, [], {})
        assert result.component["schema"]["output"] == []


class TestNeedsReview:
    """Verify needs_review entries for engine gaps."""

    def test_needs_review_has_entries(self):
        node = _make_node()
        result = FileCopyConverter().convert(node, [], {})
        assert len(result.needs_review) >= 1

    def test_all_needs_review_are_engine_gap(self):
        node = _make_node()
        result = FileCopyConverter().convert(node, [], {})
        for entry in result.needs_review:
            assert entry["severity"] == "engine_gap"

    def test_needs_review_has_component_id(self):
        node = _make_node(component_id="test_comp")
        result = FileCopyConverter().convert(node, [], {})
        for entry in result.needs_review:
            assert entry["component"] == "test_comp"

    def test_no_framework_param_needs_review(self):
        """Framework params (tstatcatcher_stats, label) must NOT have needs_review."""
        node = _make_node()
        result = FileCopyConverter().convert(node, [], {})
        issues = [e["issue"] for e in result.needs_review]
        for issue in issues:
            assert "tstatcatcher_stats" not in issue
            assert "label" not in issue.lower().split()


class TestPhantomParams:
    """Verify params NOT in _java.xml are NOT extracted."""

    def test_no_copy_directory_key(self):
        """COPY_DIRECTORY is phantom -- actual _java.xml param is ENABLE_COPY_DIRECTORY."""
        node = _make_node(params={"COPY_DIRECTORY": "true"})
        result = FileCopyConverter().convert(node, [], {})
        assert "copy_directory" not in result.component["config"]

    def test_no_remove_source_file_key(self):
        """REMOVE_SOURCE_FILE is phantom -- actual _java.xml param is REMOVE_FILE."""
        node = _make_node(params={"REMOVE_SOURCE_FILE": "true"})
        result = FileCopyConverter().convert(node, [], {})
        assert "remove_source_file" not in result.component["config"]


class TestCompleteness:
    """Verify all expected config keys are present."""

    def test_all_config_keys_present(self):
        node = _make_node()
        result = FileCopyConverter().convert(node, [], {})
        expected_keys = {
            "filename", "enable_copy_directory", "source_derectory",
            "destination", "rename", "destination_rename",
            "remove_file", "replace_file", "create_directory",
            "failon", "force_copy_delete", "preserve_last_modified_time",
            "tstatcatcher_stats", "label",
        }
        actual_keys = set(result.component["config"].keys())
        missing = expected_keys - actual_keys
        assert not missing, f"Missing config keys: {missing}"


class TestComponentStructure:
    """Verify _build_component_dict wrapper output."""

    def test_has_type(self):
        node = _make_node()
        result = FileCopyConverter().convert(node, [], {})
        assert result.component["type"] == "FileCopy"

    def test_has_original_type(self):
        node = _make_node()
        result = FileCopyConverter().convert(node, [], {})
        assert result.component["original_type"] == "tFileCopy"

    def test_has_id(self):
        node = _make_node()
        result = FileCopyConverter().convert(node, [], {})
        assert result.component["id"] == "fc_1"

    def test_has_config(self):
        node = _make_node()
        result = FileCopyConverter().convert(node, [], {})
        assert "config" in result.component

    def test_has_schema(self):
        node = _make_node()
        result = FileCopyConverter().convert(node, [], {})
        assert "schema" in result.component
