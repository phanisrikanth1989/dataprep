"""Tests for SetGlobalVarConverter (tSetGlobalVar -> SetGlobalVar)."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.file.set_global_var import (
    SetGlobalVarConverter,
)
from src.converters.talend_to_v1.components.registry import REGISTRY


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

def _make_node(params=None, schema=None, component_id="sgv_1",
               component_type="tSetGlobalVar"):
    """Create a TalendNode for testing."""
    return TalendNode(
        component_id=component_id,
        component_type=component_type,
        params=params or {},
        schema=schema or {},
        position={"x": 100, "y": 200},
        raw_xml=ET.Element("node"),
    )


def _make_variables(pairs):
    """Generate VARIABLES TABLE data with stride-2 (KEY, VALUE) per pair.

    pairs: list of (key, value) tuples.
    """
    result = []
    for key, value in pairs:
        result.append({"elementRef": "KEY", "value": key})
        result.append({"elementRef": "VALUE", "value": value})
    return result


# ------------------------------------------------------------------
# Test Classes (one per concern)
# ------------------------------------------------------------------


class TestRegistration:
    """Verify component is registered correctly."""

    def test_registered_in_registry(self):
        assert REGISTRY.get("tSetGlobalVar") is SetGlobalVarConverter


class TestDefaults:
    """Verify all parameters have correct defaults when no params provided."""

    def test_variables_default(self):
        """Empty TABLE produces empty list."""
        node = _make_node()
        result = SetGlobalVarConverter().convert(node, [], {})
        assert result.component["config"]["variables"] == []


class TestParameterExtraction:
    """Verify TABLE parameter extraction from stride-2 KEY/VALUE entries."""

    def test_single_variable(self):
        """Single KEY/VALUE pair produces one dict."""
        table = _make_variables([('"myVar"', '"myVal"')])
        node = _make_node(params={"VARIABLES": table})
        result = SetGlobalVarConverter().convert(node, [], {})
        assert result.component["config"]["variables"] == [
            {"key": "myVar", "value": "myVal"},
        ]

    def test_multiple_variables(self):
        """Three KEY/VALUE pairs produce three dicts."""
        table = _make_variables([
            ('"var1"', '"val1"'),
            ('"var2"', '"val2"'),
            ('"var3"', '"val3"'),
        ])
        node = _make_node(params={"VARIABLES": table})
        result = SetGlobalVarConverter().convert(node, [], {})
        variables = result.component["config"]["variables"]
        assert len(variables) == 3
        assert variables[0] == {"key": "var1", "value": "val1"}
        assert variables[1] == {"key": "var2", "value": "val2"}
        assert variables[2] == {"key": "var3", "value": "val3"}

    def test_empty_variables_table(self):
        """Empty TABLE entries produce empty list."""
        node = _make_node(params={"VARIABLES": []})
        result = SetGlobalVarConverter().convert(node, [], {})
        assert result.component["config"]["variables"] == []

    def test_missing_variables_param(self):
        """Missing VARIABLES param produces empty list."""
        node = _make_node(params={})
        result = SetGlobalVarConverter().convert(node, [], {})
        assert result.component["config"]["variables"] == []

    def test_incomplete_trailing_stride(self):
        """Incomplete trailing group (single KEY without VALUE) is skipped."""
        table = _make_variables([('"var1"', '"val1"')])
        table.append({"elementRef": "KEY", "value": '"orphan"'})
        node = _make_node(params={"VARIABLES": table})
        result = SetGlobalVarConverter().convert(node, [], {})
        assert result.component["config"]["variables"] == [
            {"key": "var1", "value": "val1"},
        ]

    def test_expression_values_marked_java(self):
        """Java expression values are marked with {{java}} prefix."""
        table = _make_variables([
            ('"runDate"', '"TalendDate.getDate()"'),
        ])
        node = _make_node(params={"VARIABLES": table})
        result = SetGlobalVarConverter().convert(node, [], {})
        assert result.component["config"]["variables"][0]["value"] == "{{java}}TalendDate.getDate()"


class TestFrameworkParams:
    """Verify tstatcatcher_stats and label extraction."""

    def test_tstatcatcher_stats_default_false(self):
        node = _make_node()
        result = SetGlobalVarConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is False

    def test_tstatcatcher_stats_true(self):
        node = _make_node(params={"TSTATCATCHER_STATS": "true"})
        result = SetGlobalVarConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is True

    def test_label_default_empty(self):
        node = _make_node()
        result = SetGlobalVarConverter().convert(node, [], {})
        assert result.component["config"]["label"] == ""

    def test_label_extracted(self):
        node = _make_node(params={"LABEL": '"my_label"'})
        result = SetGlobalVarConverter().convert(node, [], {})
        assert result.component["config"]["label"] == "my_label"


class TestSchema:
    """Verify utility component empty schema."""

    def test_schema_input_empty(self):
        """Utility component has no input schema."""
        node = _make_node()
        result = SetGlobalVarConverter().convert(node, [], {})
        assert result.component["schema"]["input"] == []

    def test_schema_output_empty(self):
        """Utility component has no output schema."""
        node = _make_node()
        result = SetGlobalVarConverter().convert(node, [], {})
        assert result.component["schema"]["output"] == []


class TestNeedsReview:
    """Verify needs_review entries for engine gaps."""

    def test_needs_review_has_entries(self):
        """Engine reads VARIABLES (uppercase) and {name, value} -- needs_review emitted."""
        table = _make_variables([('"k"', '"v"')])
        node = _make_node(params={"VARIABLES": table})
        result = SetGlobalVarConverter().convert(node, [], {})
        assert len(result.needs_review) >= 1

    def test_all_needs_review_are_engine_gap(self):
        """All needs_review entries have severity 'engine_gap'."""
        table = _make_variables([('"k"', '"v"')])
        node = _make_node(params={"VARIABLES": table})
        result = SetGlobalVarConverter().convert(node, [], {})
        for entry in result.needs_review:
            assert entry["severity"] == "engine_gap"

    def test_needs_review_has_component_id(self):
        """All needs_review entries reference correct component_id."""
        node = _make_node(component_id="test_comp")
        result = SetGlobalVarConverter().convert(node, [], {})
        for entry in result.needs_review:
            assert entry["component"] == "test_comp"

    def test_no_framework_param_needs_review(self):
        """Framework params (tstatcatcher_stats, label) must NOT have needs_review."""
        node = _make_node()
        result = SetGlobalVarConverter().convert(node, [], {})
        issues = [e["issue"] for e in result.needs_review]
        for issue in issues:
            assert "tstatcatcher_stats" not in issue
            assert "label" not in issue.lower().split()


class TestCompleteness:
    """Verify all expected config keys are present."""

    def test_all_config_keys_present(self):
        """Config has variables + 2 framework keys."""
        table = _make_variables([('"k"', '"v"')])
        node = _make_node(params={"VARIABLES": table})
        result = SetGlobalVarConverter().convert(node, [], {})
        expected_keys = {"variables", "requires_java_bridge", "tstatcatcher_stats", "label"}
        actual_keys = set(result.component["config"].keys())
        missing = expected_keys - actual_keys
        assert not missing, f"Missing config keys: {missing}"
        extra = actual_keys - expected_keys
        assert not extra, f"Extra config keys: {extra}"


class TestComponentStructure:
    """Verify _build_component_dict output structure."""

    def test_has_type(self):
        node = _make_node()
        result = SetGlobalVarConverter().convert(node, [], {})
        assert result.component["type"] == "SetGlobalVar"

    def test_has_original_type(self):
        node = _make_node()
        result = SetGlobalVarConverter().convert(node, [], {})
        assert result.component["original_type"] == "tSetGlobalVar"

    def test_has_all_top_level_keys(self):
        """Output dict has all required top-level keys from _build_component_dict."""
        node = _make_node()
        result = SetGlobalVarConverter().convert(node, [], {})
        expected = {"id", "type", "original_type", "position", "config", "schema", "inputs", "outputs"}
        assert set(result.component.keys()) == expected

    def test_result_is_component_result(self):
        node = _make_node()
        result = SetGlobalVarConverter().convert(node, [], {})
        assert isinstance(result, ComponentResult)
