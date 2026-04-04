"""Tests for FileUnarchiveConverter (tFileUnarchive -> FileUnarchiveComponent)."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.file.file_unarchive import (
    FileUnarchiveConverter,
)
from src.converters.talend_to_v1.components.registry import REGISTRY


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

def _make_node(params=None, schema=None, component_id="fu_1",
               component_type="tFileUnarchive"):
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
        assert REGISTRY.get("tFileUnarchive") is FileUnarchiveConverter


class TestDefaults:
    """Verify all parameters have correct defaults when no params provided."""

    def test_zipfile_default(self):
        node = _make_node()
        result = FileUnarchiveConverter().convert(node, [], {})
        assert result.component["config"]["zipfile"] == ""

    def test_directory_default(self):
        node = _make_node()
        result = FileUnarchiveConverter().convert(node, [], {})
        assert result.component["config"]["directory"] == ""

    def test_rootname_default(self):
        node = _make_node()
        result = FileUnarchiveConverter().convert(node, [], {})
        assert result.component["config"]["rootname"] is False

    def test_integrity_default(self):
        node = _make_node()
        result = FileUnarchiveConverter().convert(node, [], {})
        assert result.component["config"]["integrity"] is False

    def test_extractpath_default(self):
        """CRITICAL: _java.xml says EXTRACTPATH default=true."""
        node = _make_node()
        result = FileUnarchiveConverter().convert(node, [], {})
        assert result.component["config"]["extractpath"] is True

    def test_checkpassword_default(self):
        """CRITICAL: config key is checkpassword (not need_password)."""
        node = _make_node()
        result = FileUnarchiveConverter().convert(node, [], {})
        assert result.component["config"]["checkpassword"] is False

    def test_decrypt_method_default(self):
        """CRITICAL: config key is decrypt_method, default ZIP4J_DECRYPT."""
        node = _make_node()
        result = FileUnarchiveConverter().convert(node, [], {})
        assert result.component["config"]["decrypt_method"] == "ZIP4J_DECRYPT"

    def test_password_default(self):
        node = _make_node()
        result = FileUnarchiveConverter().convert(node, [], {})
        assert result.component["config"]["password"] == ""

    def test_die_on_error_default(self):
        node = _make_node()
        result = FileUnarchiveConverter().convert(node, [], {})
        assert result.component["config"]["die_on_error"] is False

    def test_printout_default(self):
        """Advanced param: PRINTOUT default=false."""
        node = _make_node()
        result = FileUnarchiveConverter().convert(node, [], {})
        assert result.component["config"]["printout"] is False

    def test_use_encoding_default(self):
        """Advanced param: USE_ENCODING default=false."""
        node = _make_node()
        result = FileUnarchiveConverter().convert(node, [], {})
        assert result.component["config"]["use_encoding"] is False

    def test_encording_default(self):
        """Advanced param: ENCORDING default=UTF-8 (Talend's typo preserved)."""
        node = _make_node()
        result = FileUnarchiveConverter().convert(node, [], {})
        assert result.component["config"]["encording"] == "UTF-8"


class TestParameterExtraction:
    """Verify each parameter is correctly extracted from XML params."""

    def test_zipfile_extracted(self):
        node = _make_node(params={"ZIPFILE": '"/data/archive.zip"'})
        result = FileUnarchiveConverter().convert(node, [], {})
        assert result.component["config"]["zipfile"] == "/data/archive.zip"

    def test_directory_extracted(self):
        node = _make_node(params={"DIRECTORY": '"/data/output"'})
        result = FileUnarchiveConverter().convert(node, [], {})
        assert result.component["config"]["directory"] == "/data/output"

    def test_extractpath_false(self):
        node = _make_node(params={"EXTRACTPATH": "false"})
        result = FileUnarchiveConverter().convert(node, [], {})
        assert result.component["config"]["extractpath"] is False

    def test_checkpassword_true(self):
        node = _make_node(params={"CHECKPASSWORD": "true"})
        result = FileUnarchiveConverter().convert(node, [], {})
        assert result.component["config"]["checkpassword"] is True

    def test_decrypt_method_custom(self):
        node = _make_node(params={"DECRYPT_METHOD": '"AES256"'})
        result = FileUnarchiveConverter().convert(node, [], {})
        assert result.component["config"]["decrypt_method"] == "AES256"

    def test_password_extracted(self):
        node = _make_node(params={"PASSWORD": '"secret"'})
        result = FileUnarchiveConverter().convert(node, [], {})
        assert result.component["config"]["password"] == "secret"

    def test_printout_true(self):
        node = _make_node(params={"PRINTOUT": "true"})
        result = FileUnarchiveConverter().convert(node, [], {})
        assert result.component["config"]["printout"] is True

    def test_use_encoding_true(self):
        node = _make_node(params={"USE_ENCODING": "true"})
        result = FileUnarchiveConverter().convert(node, [], {})
        assert result.component["config"]["use_encoding"] is True

    def test_encording_custom(self):
        node = _make_node(params={"ENCORDING": '"ISO-8859-15"'})
        result = FileUnarchiveConverter().convert(node, [], {})
        assert result.component["config"]["encording"] == "ISO-8859-15"


class TestFrameworkParams:
    """Verify tstatcatcher_stats and label extraction."""

    def test_tstatcatcher_stats_default_false(self):
        node = _make_node()
        result = FileUnarchiveConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is False

    def test_tstatcatcher_stats_true(self):
        node = _make_node(params={"TSTATCATCHER_STATS": "true"})
        result = FileUnarchiveConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is True

    def test_label_default_empty(self):
        node = _make_node()
        result = FileUnarchiveConverter().convert(node, [], {})
        assert result.component["config"]["label"] == ""

    def test_label_extracted(self):
        node = _make_node(params={"LABEL": '"my_label"'})
        result = FileUnarchiveConverter().convert(node, [], {})
        assert result.component["config"]["label"] == "my_label"


class TestSchema:
    """Verify schema extraction for utility component."""

    def test_schema_input_empty(self):
        """Utility component per D-56 -- no input schema."""
        node = _make_node()
        result = FileUnarchiveConverter().convert(node, [], {})
        assert result.component["schema"]["input"] == []

    def test_schema_output_empty(self):
        """Utility component per D-56 -- no output schema."""
        node = _make_node()
        result = FileUnarchiveConverter().convert(node, [], {})
        assert result.component["schema"]["output"] == []


class TestNeedsReview:
    """Verify needs_review entries for engine gaps."""

    def test_needs_review_has_entries(self):
        """Engine key mismatches: extractpath vs extract_path, checkpassword vs check_password."""
        node = _make_node()
        result = FileUnarchiveConverter().convert(node, [], {})
        assert len(result.needs_review) >= 2

    def test_all_needs_review_are_engine_gap(self):
        node = _make_node()
        result = FileUnarchiveConverter().convert(node, [], {})
        for entry in result.needs_review:
            assert entry["severity"] == "engine_gap"

    def test_needs_review_has_component_id(self):
        node = _make_node(component_id="test_comp")
        result = FileUnarchiveConverter().convert(node, [], {})
        for entry in result.needs_review:
            assert entry["component"] == "test_comp"

    def test_no_framework_param_needs_review(self):
        """Framework params (tstatcatcher_stats, label) must NOT have needs_review."""
        node = _make_node()
        result = FileUnarchiveConverter().convert(node, [], {})
        issues = [e["issue"] for e in result.needs_review]
        for issue in issues:
            assert "tstatcatcher_stats" not in issue
            assert "label" not in issue.lower().split()


class TestPhantomParams:
    """Verify params NOT in _java.xml are NOT extracted."""

    def test_no_need_password_key(self):
        """need_password was old wrong param name -- should be checkpassword."""
        node = _make_node(params={"CHECKPASSWORD": "true"})
        result = FileUnarchiveConverter().convert(node, [], {})
        assert "need_password" not in result.component["config"]

    def test_no_decrypt_type_key(self):
        """decrypt_type was old wrong param name -- should be decrypt_method."""
        node = _make_node(params={"DECRYPT_METHOD": '"AES256"'})
        result = FileUnarchiveConverter().convert(node, [], {})
        assert "decrypt_type" not in result.component["config"]

    def test_no_extract_path_key(self):
        """extract_path (with underscore) is engine key -- converter outputs extractpath."""
        node = _make_node(params={"EXTRACTPATH": "true"})
        result = FileUnarchiveConverter().convert(node, [], {})
        assert "extract_path" not in result.component["config"]


class TestCompleteness:
    """Verify all expected config keys are present."""

    def test_all_config_keys_present(self):
        node = _make_node()
        result = FileUnarchiveConverter().convert(node, [], {})
        expected_keys = {
            "zipfile", "directory", "rootname", "integrity",
            "extractpath", "checkpassword", "decrypt_method",
            "password", "die_on_error", "printout",
            "use_encoding", "encording",
            "tstatcatcher_stats", "label",
        }
        actual_keys = set(result.component["config"].keys())
        missing = expected_keys - actual_keys
        assert not missing, f"Missing config keys: {missing}"


class TestComponentStructure:
    """Verify _build_component_dict wrapper output."""

    def test_has_type(self):
        node = _make_node()
        result = FileUnarchiveConverter().convert(node, [], {})
        assert result.component["type"] == "FileUnarchiveComponent"

    def test_has_id(self):
        node = _make_node()
        result = FileUnarchiveConverter().convert(node, [], {})
        assert result.component["id"] == "fu_1"

    def test_has_original_type(self):
        node = _make_node()
        result = FileUnarchiveConverter().convert(node, [], {})
        assert result.component["original_type"] == "tFileUnarchive"

    def test_has_config(self):
        node = _make_node()
        result = FileUnarchiveConverter().convert(node, [], {})
        assert "config" in result.component

    def test_has_schema(self):
        node = _make_node()
        result = FileUnarchiveConverter().convert(node, [], {})
        assert "schema" in result.component
