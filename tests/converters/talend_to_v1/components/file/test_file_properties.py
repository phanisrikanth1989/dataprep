"""Tests for FilePropertiesConverter (tFileProperties -> FileProperties)."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.file.file_properties import (
    FilePropertiesConverter,
)
from src.converters.talend_to_v1.components.registry import REGISTRY


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

def _make_node(params=None, schema=None, component_id="tFileProperties_1",
               component_type="tFileProperties"):
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
        assert REGISTRY.get("tFileProperties") is FilePropertiesConverter

    def test_tfileproperties_in_type_list(self):
        assert "tFileProperties" in REGISTRY.list_types()


class TestDefaults:
    """Verify all parameters have correct defaults when no params provided."""

    def test_filename_default(self):
        """Empty FILENAME defaults to empty string."""
        node = _make_node()
        result = FilePropertiesConverter().convert(node, [], {})
        assert result.component["config"]["filename"] == ""

    def test_md5_default(self):
        """MD5 defaults to False when not provided."""
        node = _make_node()
        result = FilePropertiesConverter().convert(node, [], {})
        assert result.component["config"]["md5"] is False


class TestParameterExtraction:
    """Verify each parameter is correctly extracted from XML params."""

    def test_filename_extracted(self):
        """FILENAME with quotes is extracted and stripped."""
        node = _make_node(params={"FILENAME": '"path/file"'})
        result = FilePropertiesConverter().convert(node, [], {})
        assert result.component["config"]["filename"] == "path/file"

    def test_filename_without_quotes(self):
        """FILENAME without quotes is extracted as-is."""
        node = _make_node(params={"FILENAME": "/var/log/app.log"})
        result = FilePropertiesConverter().convert(node, [], {})
        assert result.component["config"]["filename"] == "/var/log/app.log"

    def test_md5_true(self):
        """MD5='true' extracts as True."""
        node = _make_node(params={"MD5": "true"})
        result = FilePropertiesConverter().convert(node, [], {})
        assert result.component["config"]["md5"] is True

    def test_md5_false(self):
        """MD5='false' extracts as False."""
        node = _make_node(params={"MD5": "false"})
        result = FilePropertiesConverter().convert(node, [], {})
        assert result.component["config"]["md5"] is False


class TestFrameworkParams:
    """Verify tstatcatcher_stats and label extraction."""

    def test_tstatcatcher_stats_default_false(self):
        node = _make_node()
        result = FilePropertiesConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is False

    def test_tstatcatcher_stats_true(self):
        node = _make_node(params={"TSTATCATCHER_STATS": "true"})
        result = FilePropertiesConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is True

    def test_label_default_empty(self):
        node = _make_node()
        result = FilePropertiesConverter().convert(node, [], {})
        assert result.component["config"]["label"] == ""

    def test_label_extracted(self):
        node = _make_node(params={"LABEL": '"my_label"'})
        result = FilePropertiesConverter().convert(node, [], {})
        assert result.component["config"]["label"] == "my_label"


class TestSchema:
    """Verify schema extraction for utility component."""

    def test_schema_both_empty(self):
        """tFileProperties is a utility component -- schema has empty input/output."""
        node = _make_node()
        result = FilePropertiesConverter().convert(node, [], {})
        assert result.component["schema"] == {"input": [], "output": []}


class TestNeedsReview:
    """Verify needs_review entries for engine key mismatches."""

    def test_needs_review_count(self):
        """Two needs_review entries: one for filename, one for md5 key mismatch."""
        node = _make_node()
        result = FilePropertiesConverter().convert(node, [], {})
        assert len(result.needs_review) == 2

    def test_needs_review_filename_key(self):
        """Engine reads FILENAME (uppercase) vs converter's 'filename' (snake_case)."""
        node = _make_node()
        result = FilePropertiesConverter().convert(node, [], {})
        issues = [e["issue"] for e in result.needs_review]
        assert any("FILENAME" in i and "filename" in i for i in issues)

    def test_needs_review_md5_key(self):
        """Engine reads MD5 (uppercase) vs converter's 'md5' (snake_case)."""
        node = _make_node()
        result = FilePropertiesConverter().convert(node, [], {})
        issues = [e["issue"] for e in result.needs_review]
        assert any("MD5" in i and "md5" in i for i in issues)

    def test_needs_review_severity(self):
        node = _make_node()
        result = FilePropertiesConverter().convert(node, [], {})
        for entry in result.needs_review:
            assert entry["severity"] == "engine_gap"

    def test_needs_review_has_component_id(self):
        node = _make_node(component_id="test_comp")
        result = FilePropertiesConverter().convert(node, [], {})
        for entry in result.needs_review:
            assert entry["component"] == "test_comp"

    def test_no_framework_param_needs_review(self):
        """Framework params (tstatcatcher_stats, label) must NOT have needs_review."""
        node = _make_node()
        result = FilePropertiesConverter().convert(node, [], {})
        issues = [e["issue"] for e in result.needs_review]
        for issue in issues:
            assert "tstatcatcher_stats" not in issue
            assert "label" not in issue.lower().split()


class TestCompleteness:
    """Verify all expected config keys are present."""

    def test_all_keys(self):
        node = _make_node()
        result = FilePropertiesConverter().convert(node, [], {})
        expected_keys = {
            "filename", "md5",
            "tstatcatcher_stats", "label",
        }
        actual_keys = set(result.component["config"].keys())
        missing = expected_keys - actual_keys
        assert not missing, f"Missing config keys: {missing}"

    def test_no_extra_keys(self):
        """No unexpected config keys beyond the 4 expected ones."""
        node = _make_node()
        result = FilePropertiesConverter().convert(node, [], {})
        expected_keys = {
            "filename", "md5",
            "tstatcatcher_stats", "label",
        }
        actual_keys = set(result.component["config"].keys())
        extra = actual_keys - expected_keys
        assert not extra, f"Extra config keys: {extra}"


class TestComponentStructure:
    """Verify _build_component_dict wrapper structure."""

    def test_type(self):
        """type_name should be 'FileProperties' (engine class name)."""
        node = _make_node()
        result = FilePropertiesConverter().convert(node, [], {})
        assert result.component["type"] == "FileProperties"

    def test_id(self):
        node = _make_node(component_id="tFileProperties_1")
        result = FilePropertiesConverter().convert(node, [], {})
        assert result.component["id"] == "tFileProperties_1"

    def test_original_type(self):
        node = _make_node()
        result = FilePropertiesConverter().convert(node, [], {})
        assert result.component["original_type"] == "tFileProperties"

    def test_position(self):
        node = _make_node()
        result = FilePropertiesConverter().convert(node, [], {})
        assert result.component["position"] == {"x": 100, "y": 200}

    def test_inputs_outputs(self):
        node = _make_node()
        result = FilePropertiesConverter().convert(node, [], {})
        assert result.component["inputs"] == []
        assert result.component["outputs"] == []

    def test_config_is_nested(self):
        """Config must be nested under 'config' key, not flat."""
        node = _make_node()
        result = FilePropertiesConverter().convert(node, [], {})
        assert "config" in result.component
        assert isinstance(result.component["config"], dict)

    def test_no_component_type_in_config(self):
        """component_type must NOT appear in config dict."""
        node = _make_node()
        result = FilePropertiesConverter().convert(node, [], {})
        assert "component_type" not in result.component["config"]
