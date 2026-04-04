"""Tests for FileArchiveConverter (tFileArchive -> v1 FileArchiveComponent config)."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.file.file_archive import FileArchiveConverter
from src.converters.talend_to_v1.components.registry import REGISTRY


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

def _make_node(params=None, schema=None, component_id="fa_1",
               component_type="tFileArchive"):
    """Create a TalendNode for testing."""
    return TalendNode(
        component_id=component_id,
        component_type=component_type,
        params=params or {},
        schema=schema or {},
        position={"x": 100, "y": 200},
        raw_xml=ET.Element("node"),
    )


def _make_mask_data(patterns):
    """Generate MASK TABLE data with stride-1 per row.

    patterns: list of str mask patterns (e.g., ["*.csv", "*.txt"])
    """
    result = []
    for pattern in patterns:
        result.append({"elementRef": "FILEMASK", "value": f'"{pattern}"'})
    return result


# ------------------------------------------------------------------
# Test Classes (one per concern)
# ------------------------------------------------------------------


class TestRegistration:
    """Verify component is registered correctly."""

    def test_registered_in_registry(self):
        assert REGISTRY.get("tFileArchive") is FileArchiveConverter


class TestDefaults:
    """Verify all parameters have correct defaults when no params provided."""

    def test_source_default(self):
        node = _make_node()
        result = FileArchiveConverter().convert(node, [], {})
        assert result.component["config"]["source"] == ""

    def test_source_file_default(self):
        node = _make_node()
        result = FileArchiveConverter().convert(node, [], {})
        assert result.component["config"]["source_file"] == ""

    def test_sub_directroy_default(self):
        """CRITICAL: _java.xml says SUB_DIRECTROY default=true (note Talend typo)."""
        node = _make_node()
        result = FileArchiveConverter().convert(node, [], {})
        assert result.component["config"]["sub_directroy"] is True

    def test_target_default(self):
        node = _make_node()
        result = FileArchiveConverter().convert(node, [], {})
        assert result.component["config"]["target"] == ""

    def test_mkdir_default(self):
        """CRITICAL: actual _java.xml param is MKDIR, not phantom CREATE_DIRECTORY."""
        node = _make_node()
        result = FileArchiveConverter().convert(node, [], {})
        assert result.component["config"]["mkdir"] is False

    def test_archive_format_default(self):
        node = _make_node()
        result = FileArchiveConverter().convert(node, [], {})
        assert result.component["config"]["archive_format"] == "ZIP"

    def test_level_default(self):
        """CRITICAL: _java.xml says LEVEL default='4', not 'Normal'."""
        node = _make_node()
        result = FileArchiveConverter().convert(node, [], {})
        assert result.component["config"]["level"] == "4"

    def test_all_files_default(self):
        node = _make_node()
        result = FileArchiveConverter().convert(node, [], {})
        assert result.component["config"]["all_files"] is True

    def test_mask_default(self):
        """MASK is a TABLE param, default is empty list."""
        node = _make_node()
        result = FileArchiveConverter().convert(node, [], {})
        assert result.component["config"]["mask"] == []

    def test_encoding_default(self):
        """CRITICAL: _java.xml says ENCODING default='ISO-8859-15', not empty."""
        node = _make_node()
        result = FileArchiveConverter().convert(node, [], {})
        assert result.component["config"]["encoding"] == "ISO-8859-15"

    def test_overwrite_default(self):
        node = _make_node()
        result = FileArchiveConverter().convert(node, [], {})
        assert result.component["config"]["overwrite"] is True

    def test_encrypt_files_default(self):
        node = _make_node()
        result = FileArchiveConverter().convert(node, [], {})
        assert result.component["config"]["encrypt_files"] is False

    def test_encrypt_method_default(self):
        node = _make_node()
        result = FileArchiveConverter().convert(node, [], {})
        assert result.component["config"]["encrypt_method"] == "ZIP4J_STANDARD"

    def test_aes_key_strength_default(self):
        node = _make_node()
        result = FileArchiveConverter().convert(node, [], {})
        assert result.component["config"]["aes_key_strength"] == "AES256"

    def test_password_default(self):
        node = _make_node()
        result = FileArchiveConverter().convert(node, [], {})
        assert result.component["config"]["password"] == ""

    def test_zip64_mode_default(self):
        node = _make_node()
        result = FileArchiveConverter().convert(node, [], {})
        assert result.component["config"]["zip64_mode"] == "ASNEEDED"

    def test_use_sync_flush_default(self):
        """Advanced param, default False."""
        node = _make_node()
        result = FileArchiveConverter().convert(node, [], {})
        assert result.component["config"]["use_sync_flush"] is False


class TestParameterExtraction:
    """Verify each parameter is correctly extracted from XML params."""

    def test_source_extracted(self):
        node = _make_node(params={"SOURCE": '"/data/input/reports"'})
        result = FileArchiveConverter().convert(node, [], {})
        assert result.component["config"]["source"] == "/data/input/reports"

    def test_target_extracted(self):
        node = _make_node(params={"TARGET": '"/data/output/reports.zip"'})
        result = FileArchiveConverter().convert(node, [], {})
        assert result.component["config"]["target"] == "/data/output/reports.zip"

    def test_sub_directroy_false(self):
        """SUB_DIRECTROY=false -> False."""
        node = _make_node(params={"SUB_DIRECTROY": "false"})
        result = FileArchiveConverter().convert(node, [], {})
        assert result.component["config"]["sub_directroy"] is False

    def test_mkdir_true(self):
        """MKDIR=true -> True."""
        node = _make_node(params={"MKDIR": "true"})
        result = FileArchiveConverter().convert(node, [], {})
        assert result.component["config"]["mkdir"] is True

    def test_level_custom(self):
        """LEVEL as quoted string."""
        node = _make_node(params={"LEVEL": '"6"'})
        result = FileArchiveConverter().convert(node, [], {})
        assert result.component["config"]["level"] == "6"

    def test_encoding_custom(self):
        """ENCODING as quoted string."""
        node = _make_node(params={"ENCODING": '"UTF-8"'})
        result = FileArchiveConverter().convert(node, [], {})
        assert result.component["config"]["encoding"] == "UTF-8"

    def test_archive_format_custom(self):
        node = _make_node(params={"ARCHIVE_FORMAT": '"GZIP"'})
        result = FileArchiveConverter().convert(node, [], {})
        assert result.component["config"]["archive_format"] == "GZIP"

    def test_source_file_extracted(self):
        node = _make_node(params={"SOURCE_FILE": '"/data/input.gz"'})
        result = FileArchiveConverter().convert(node, [], {})
        assert result.component["config"]["source_file"] == "/data/input.gz"

    def test_mask_single_entry(self):
        """MASK TABLE with 1 entry."""
        mask_data = _make_mask_data(["*.csv"])
        node = _make_node(params={"MASK": mask_data})
        result = FileArchiveConverter().convert(node, [], {})
        assert result.component["config"]["mask"] == ["*.csv"]

    def test_mask_multiple_entries(self):
        """MASK TABLE with multiple entries."""
        mask_data = _make_mask_data(["*.csv", "*.txt", "*.dat"])
        node = _make_node(params={"MASK": mask_data})
        result = FileArchiveConverter().convert(node, [], {})
        assert result.component["config"]["mask"] == ["*.csv", "*.txt", "*.dat"]

    def test_encrypt_files_true(self):
        node = _make_node(params={"ENCRYPT_FILES": "true"})
        result = FileArchiveConverter().convert(node, [], {})
        assert result.component["config"]["encrypt_files"] is True

    def test_encrypt_method_extracted(self):
        node = _make_node(params={"ENCRYPT_METHOD": '"AES"'})
        result = FileArchiveConverter().convert(node, [], {})
        assert result.component["config"]["encrypt_method"] == "AES"

    def test_password_extracted(self):
        node = _make_node(params={"PASSWORD": '"secret123"'})
        result = FileArchiveConverter().convert(node, [], {})
        assert result.component["config"]["password"] == "secret123"

    def test_zip64_mode_extracted(self):
        node = _make_node(params={"ZIP64_MODE": '"ALWAYS"'})
        result = FileArchiveConverter().convert(node, [], {})
        assert result.component["config"]["zip64_mode"] == "ALWAYS"

    def test_use_sync_flush_true(self):
        node = _make_node(params={"USE_SYNC_FLUSH": "true"})
        result = FileArchiveConverter().convert(node, [], {})
        assert result.component["config"]["use_sync_flush"] is True


class TestFrameworkParams:
    """Verify tstatcatcher_stats and label extraction."""

    def test_tstatcatcher_stats_default_false(self):
        node = _make_node()
        result = FileArchiveConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is False

    def test_tstatcatcher_stats_true(self):
        node = _make_node(params={"TSTATCATCHER_STATS": "true"})
        result = FileArchiveConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is True

    def test_label_default_empty(self):
        node = _make_node()
        result = FileArchiveConverter().convert(node, [], {})
        assert result.component["config"]["label"] == ""

    def test_label_extracted(self):
        node = _make_node(params={"LABEL": '"my_label"'})
        result = FileArchiveConverter().convert(node, [], {})
        assert result.component["config"]["label"] == "my_label"


class TestSchema:
    """Verify schema extraction for utility component."""

    def test_schema_input_empty(self):
        """Utility component per D-56 -- no input schema."""
        node = _make_node()
        result = FileArchiveConverter().convert(node, [], {})
        assert result.component["schema"]["input"] == []

    def test_schema_output_empty(self):
        """Utility component per D-56 -- no output schema."""
        node = _make_node()
        result = FileArchiveConverter().convert(node, [], {})
        assert result.component["schema"]["output"] == []


class TestNeedsReview:
    """Verify needs_review entries for engine gaps."""

    def test_needs_review_has_entries(self):
        """Engine gap needs_review for key mismatches."""
        node = _make_node()
        result = FileArchiveConverter().convert(node, [], {})
        assert len(result.needs_review) > 0

    def test_all_needs_review_are_engine_gap(self):
        node = _make_node()
        result = FileArchiveConverter().convert(node, [], {})
        for entry in result.needs_review:
            assert entry["severity"] == "engine_gap"

    def test_needs_review_has_component_id(self):
        node = _make_node(component_id="test_comp")
        result = FileArchiveConverter().convert(node, [], {})
        for entry in result.needs_review:
            assert entry["component"] == "test_comp"

    def test_no_framework_param_needs_review(self):
        """Framework params (tstatcatcher_stats, label) must NOT have needs_review."""
        node = _make_node()
        result = FileArchiveConverter().convert(node, [], {})
        issues = [e["issue"] for e in result.needs_review]
        for issue in issues:
            assert "tstatcatcher_stats" not in issue
            assert "label" not in issue.lower().split()


class TestPhantomParams:
    """Verify params NOT in _java.xml are NOT extracted."""

    def test_no_create_directory_key(self):
        """CREATE_DIRECTORY is phantom -- actual _java.xml param is MKDIR."""
        node = _make_node(params={"CREATE_DIRECTORY": "true"})
        result = FileArchiveConverter().convert(node, [], {})
        assert "create_directory" not in result.component["config"]

    def test_no_filemask_key(self):
        """FILEMASK is phantom -- actual _java.xml param is MASK TABLE."""
        node = _make_node(params={"FILEMASK": '"*.csv"'})
        result = FileArchiveConverter().convert(node, [], {})
        assert "filemask" not in result.component["config"]

    def test_no_die_on_error_key(self):
        """DIE_ON_ERROR is not in _java.xml basic params."""
        node = _make_node(params={"DIE_ON_ERROR": "true"})
        result = FileArchiveConverter().convert(node, [], {})
        assert "die_on_error" not in result.component["config"]

    def test_no_include_subdirectories_key(self):
        """include_subdirectories is old wrong key -- actual is sub_directroy."""
        node = _make_node()
        result = FileArchiveConverter().convert(node, [], {})
        assert "include_subdirectories" not in result.component["config"]

    def test_no_compression_level_key(self):
        """compression_level is old wrong key -- actual is level."""
        node = _make_node()
        result = FileArchiveConverter().convert(node, [], {})
        assert "compression_level" not in result.component["config"]


class TestCompleteness:
    """Verify all expected config keys are present."""

    def test_all_config_keys_present(self):
        node = _make_node()
        result = FileArchiveConverter().convert(node, [], {})
        expected_keys = {
            "source", "source_file", "sub_directroy", "target",
            "mkdir", "archive_format", "level", "all_files",
            "mask", "encoding", "overwrite", "encrypt_files",
            "encrypt_method", "aes_key_strength", "password",
            "zip64_mode", "use_sync_flush",
            "tstatcatcher_stats", "label",
        }
        actual_keys = set(result.component["config"].keys())
        missing = expected_keys - actual_keys
        extra = actual_keys - expected_keys
        assert not missing, f"Missing config keys: {missing}"
        assert not extra, f"Extra config keys: {extra}"


class TestComponentStructure:
    """Verify _build_component_dict wrapper output."""

    def test_has_type(self):
        node = _make_node()
        result = FileArchiveConverter().convert(node, [], {})
        assert result.component["type"] == "FileArchiveComponent"

    def test_has_id(self):
        node = _make_node()
        result = FileArchiveConverter().convert(node, [], {})
        assert result.component["id"] == "fa_1"

    def test_has_original_type(self):
        node = _make_node()
        result = FileArchiveConverter().convert(node, [], {})
        assert result.component["original_type"] == "tFileArchive"

    def test_has_config(self):
        node = _make_node()
        result = FileArchiveConverter().convert(node, [], {})
        assert "config" in result.component

    def test_has_schema(self):
        node = _make_node()
        result = FileArchiveConverter().convert(node, [], {})
        assert "schema" in result.component

    def test_result_is_component_result(self):
        node = _make_node()
        result = FileArchiveConverter().convert(node, [], {})
        assert isinstance(result, ComponentResult)
