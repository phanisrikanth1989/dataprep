"""Tests for FileExistConverter (tFileExist -> FileExistComponent)."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.file.file_exist import (
    FileExistConverter,
)
from src.converters.talend_to_v1.components.registry import REGISTRY


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


def _make_node(params=None, component_id="tFileExist_1",
               component_type="tFileExist"):
    """Create a TalendNode for tFileExist testing."""
    return TalendNode(
        component_id=component_id,
        component_type=component_type,
        params=params or {},
        schema={},
        position={"x": 100, "y": 200},
        raw_xml=ET.Element("node"),
    )


# ------------------------------------------------------------------
# Test Classes
# ------------------------------------------------------------------


class TestRegistration:
    """Verify component is registered correctly."""

    def test_registered(self):
        """tFileExist maps to FileExistConverter in the registry."""
        assert REGISTRY.get("tFileExist") is FileExistConverter


class TestDefaults:
    """Verify all parameters have correct defaults when no params provided."""

    def test_file_name_default(self):
        """Default file_name is empty string."""
        node = _make_node()
        result = FileExistConverter().convert(node, [], {})
        assert result.component["config"]["file_name"] == ""

    def test_tstatcatcher_stats_default(self):
        """Default tstatcatcher_stats is False."""
        node = _make_node()
        result = FileExistConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is False

    def test_label_default(self):
        """Default label is empty string."""
        node = _make_node()
        result = FileExistConverter().convert(node, [], {})
        assert result.component["config"]["label"] == ""


class TestParameterExtraction:
    """Verify each parameter is correctly extracted from XML params."""

    def test_file_name_extracted(self):
        """Quoted FILE_NAME is extracted with quotes stripped."""
        node = _make_node(params={"FILE_NAME": '"path/to/file.txt"'})
        result = FileExistConverter().convert(node, [], {})
        assert result.component["config"]["file_name"] == "path/to/file.txt"

    def test_file_name_unquoted(self):
        """Unquoted FILE_NAME (context var) is preserved as-is."""
        node = _make_node(params={"FILE_NAME": "context.input_path"})
        result = FileExistConverter().convert(node, [], {})
        assert result.component["config"]["file_name"] == "context.input_path"


class TestFrameworkParams:
    """Verify tstatcatcher_stats and label extraction."""

    def test_tstatcatcher_stats_default_false(self):
        """Default tstatcatcher_stats is False."""
        node = _make_node()
        result = FileExistConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is False

    def test_tstatcatcher_stats_true(self):
        """TSTATCATCHER_STATS=true is extracted correctly."""
        node = _make_node(params={"TSTATCATCHER_STATS": "true"})
        result = FileExistConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is True

    def test_label_default_empty(self):
        """Default label is empty string."""
        node = _make_node()
        result = FileExistConverter().convert(node, [], {})
        assert result.component["config"]["label"] == ""

    def test_label_extracted(self):
        """Quoted LABEL is extracted with quotes stripped."""
        node = _make_node(params={"LABEL": '"my_label"'})
        result = FileExistConverter().convert(node, [], {})
        assert result.component["config"]["label"] == "my_label"


class TestSchema:
    """Verify schema extraction for utility component."""

    def test_schema_is_dict(self):
        """Schema has 'input' and 'output' keys (D-41)."""
        node = _make_node()
        result = FileExistConverter().convert(node, [], {})
        schema = result.component["schema"]
        assert "input" in schema
        assert "output" in schema

    def test_schema_both_empty(self):
        """Utility component has empty input and output schema."""
        node = _make_node()
        result = FileExistConverter().convert(node, [], {})
        assert result.component["schema"] == {"input": [], "output": []}


class TestNeedsReview:
    """Verify needs_review entries for engine gaps."""

    def test_needs_review_engine_key_mismatch(self):
        """needs_review entry for file_name vs file_path engine key mismatch."""
        node = _make_node()
        result = FileExistConverter().convert(node, [], {})
        issues = [e["issue"] for e in result.needs_review]
        # Should mention both file_name (converter key) and file_path (engine key)
        matched = [i for i in issues if "file_name" in i and "file_path" in i]
        assert len(matched) >= 1, f"Expected needs_review about file_name vs file_path, got: {issues}"

    def test_all_engine_gap_severity(self):
        """All needs_review entries have severity='engine_gap'."""
        node = _make_node()
        result = FileExistConverter().convert(node, [], {})
        for entry in result.needs_review:
            assert entry["severity"] == "engine_gap"

    def test_needs_review_has_component_id(self):
        """needs_review entries use correct component_id."""
        node = _make_node(component_id="tFileExist_5")
        result = FileExistConverter().convert(node, [], {})
        for entry in result.needs_review:
            assert entry["component"] == "tFileExist_5"

    def test_no_framework_param_needs_review(self):
        """Framework params (tstatcatcher_stats, label) must NOT have needs_review."""
        node = _make_node()
        result = FileExistConverter().convert(node, [], {})
        issues = [e["issue"] for e in result.needs_review]
        for issue in issues:
            assert "tstatcatcher_stats" not in issue
            assert "label" not in issue.lower().split()


class TestCompleteness:
    """Verify all expected config keys are present."""

    def test_all_config_keys(self):
        """Config contains exactly file_name, tstatcatcher_stats, label."""
        node = _make_node()
        result = FileExistConverter().convert(node, [], {})
        expected_keys = {"file_name", "tstatcatcher_stats", "label"}
        actual_keys = set(result.component["config"].keys())
        assert expected_keys == actual_keys, f"Expected {expected_keys}, got {actual_keys}"


class TestComponentStructure:
    """Verify component dict structure from _build_component_dict."""

    def test_has_id(self):
        """Component has correct id."""
        node = _make_node(component_id="tFileExist_1")
        result = FileExistConverter().convert(node, [], {})
        assert result.component["id"] == "tFileExist_1"

    def test_has_type(self):
        """Component type is FileExistComponent (engine class name per D-43)."""
        node = _make_node()
        result = FileExistConverter().convert(node, [], {})
        assert result.component["type"] == "FileExistComponent"

    def test_has_original_type(self):
        """Component original_type is tFileExist."""
        node = _make_node()
        result = FileExistConverter().convert(node, [], {})
        assert result.component["original_type"] == "tFileExist"

    def test_has_config(self):
        """Component has config dict."""
        node = _make_node()
        result = FileExistConverter().convert(node, [], {})
        assert isinstance(result.component["config"], dict)

    def test_has_schema(self):
        """Component has schema dict."""
        node = _make_node()
        result = FileExistConverter().convert(node, [], {})
        assert isinstance(result.component["schema"], dict)

    def test_has_position(self):
        """Component has position from node."""
        node = _make_node()
        result = FileExistConverter().convert(node, [], {})
        assert result.component["position"] == {"x": 100, "y": 200}

    def test_has_inputs_outputs(self):
        """Component has inputs and outputs lists."""
        node = _make_node()
        result = FileExistConverter().convert(node, [], {})
        assert result.component["inputs"] == []
        assert result.component["outputs"] == []

    def test_result_is_component_result(self):
        """convert() returns a ComponentResult."""
        node = _make_node()
        result = FileExistConverter().convert(node, [], {})
        assert isinstance(result, ComponentResult)
