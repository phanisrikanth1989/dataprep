"""Tests for ParallelizeConverter (tParallelize -> v1 parallelize config)."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    SchemaColumn,
    TalendNode,
)
from src.converters.talend_to_v1.components.control.parallelize import (
    ParallelizeConverter,
)
from src.converters.talend_to_v1.components.registry import REGISTRY


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


def _make_node(params=None, schema=None, component_id="par_1",
               component_type="tParallelize"):
    """Create a TalendNode for testing."""
    return TalendNode(
        component_id=component_id,
        component_type=component_type,
        params=params or {},
        schema=schema or {},
        position={"x": 100, "y": 200},
        raw_xml=ET.Element("node"),
    )


def _make_schema_columns():
    """Return a sample FLOW schema for testing."""
    return {
        "FLOW": [
            SchemaColumn(name="id", type="id_Integer", nullable=False, key=True, length=10),
            SchemaColumn(name="name", type="id_String", nullable=True, length=50),
        ]
    }


# ------------------------------------------------------------------
# Test Classes (one per concern)
# ------------------------------------------------------------------


class TestRegistration:
    """Verify component is registered correctly."""

    def test_registered_in_registry(self):
        assert REGISTRY.get("tParallelize") is ParallelizeConverter


class TestDefaults:
    """Verify all parameters have correct defaults when no params provided."""

    def test_wait_for_default(self):
        """WAIT_FOR defaults to 'All' (wait for end of all subJobs)."""
        node = _make_node()
        result = ParallelizeConverter().convert(node, [], {})
        assert result.component["config"]["wait_for"] == "All"

    def test_sleeptime_default(self):
        """SLEEPTIME defaults to empty string (no _java.xml default available)."""
        node = _make_node()
        result = ParallelizeConverter().convert(node, [], {})
        assert result.component["config"]["sleeptime"] == ""

    def test_die_on_error_default(self):
        """DIE_ON_ERROR defaults to False."""
        node = _make_node()
        result = ParallelizeConverter().convert(node, [], {})
        assert result.component["config"]["die_on_error"] is False


class TestParameterExtraction:
    """Verify each parameter is correctly extracted from XML params."""

    def test_wait_for_first(self):
        """WAIT_FOR='First' extracts correctly."""
        node = _make_node(params={"WAIT_FOR": '"First"'})
        result = ParallelizeConverter().convert(node, [], {})
        assert result.component["config"]["wait_for"] == "First"

    def test_wait_for_all(self):
        """WAIT_FOR='All' extracts correctly."""
        node = _make_node(params={"WAIT_FOR": '"All"'})
        result = ParallelizeConverter().convert(node, [], {})
        assert result.component["config"]["wait_for"] == "All"

    def test_wait_for_without_quotes(self):
        """WAIT_FOR without surrounding quotes passes through as-is."""
        node = _make_node(params={"WAIT_FOR": "First"})
        result = ParallelizeConverter().convert(node, [], {})
        assert result.component["config"]["wait_for"] == "First"

    def test_sleeptime_extracted(self):
        """SLEEPTIME extracts as string (milliseconds)."""
        node = _make_node(params={"SLEEPTIME": '"1000"'})
        result = ParallelizeConverter().convert(node, [], {})
        assert result.component["config"]["sleeptime"] == "1000"

    def test_die_on_error_true(self):
        """DIE_ON_ERROR=true extracts as True."""
        node = _make_node(params={"DIE_ON_ERROR": "true"})
        result = ParallelizeConverter().convert(node, [], {})
        assert result.component["config"]["die_on_error"] is True

    def test_die_on_error_false_string(self):
        """DIE_ON_ERROR='false' extracts as False."""
        node = _make_node(params={"DIE_ON_ERROR": "false"})
        result = ParallelizeConverter().convert(node, [], {})
        assert result.component["config"]["die_on_error"] is False


class TestFrameworkParams:
    """Verify tstatcatcher_stats and label extraction."""

    def test_tstatcatcher_stats_default_false(self):
        node = _make_node()
        result = ParallelizeConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is False

    def test_tstatcatcher_stats_true(self):
        node = _make_node(params={"TSTATCATCHER_STATS": "true"})
        result = ParallelizeConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is True

    def test_label_default_empty(self):
        node = _make_node()
        result = ParallelizeConverter().convert(node, [], {})
        assert result.component["config"]["label"] == ""

    def test_label_extracted(self):
        node = _make_node(params={"LABEL": '"my_label"'})
        result = ParallelizeConverter().convert(node, [], {})
        assert result.component["config"]["label"] == "my_label"


class TestSchema:
    """Verify schema extraction."""

    def test_schema_at_top_level(self):
        """Schema is at top level of component dict via _build_component_dict."""
        node = _make_node()
        result = ParallelizeConverter().convert(node, [], {})
        assert "schema" in result.component
        assert result.component["schema"] == {"input": [], "output": []}

    def test_schema_is_empty_for_control_component(self):
        """Control component has empty schema even with FLOW schema columns defined."""
        node = _make_node(schema=_make_schema_columns())
        result = ParallelizeConverter().convert(node, [], {})
        assert result.component["schema"] == {"input": [], "output": []}


class TestNeedsReview:
    """Verify needs_review entries for engine gaps."""

    def test_needs_review_count(self):
        """Single consolidated needs_review per D-23 (no-engine component)."""
        node = _make_node()
        result = ParallelizeConverter().convert(node, [], {})
        assert len(result.needs_review) == 1

    def test_needs_review_is_engine_gap(self):
        """needs_review severity is 'engine_gap'."""
        node = _make_node()
        result = ParallelizeConverter().convert(node, [], {})
        assert result.needs_review[0]["severity"] == "engine_gap"

    def test_needs_review_has_component_id(self):
        """needs_review includes the component_id."""
        node = _make_node(component_id="test_comp")
        result = ParallelizeConverter().convert(node, [], {})
        assert result.needs_review[0]["component"] == "test_comp"

    def test_needs_review_message(self):
        """needs_review message mentions no engine implementation."""
        node = _make_node()
        result = ParallelizeConverter().convert(node, [], {})
        assert "No concrete engine implementation for tParallelize" in result.needs_review[0]["issue"]

    def test_no_framework_param_needs_review(self):
        """Framework params (tstatcatcher_stats, label) must NOT have needs_review."""
        node = _make_node()
        result = ParallelizeConverter().convert(node, [], {})
        issues = [e["issue"] for e in result.needs_review]
        for issue in issues:
            assert "tstatcatcher_stats" not in issue
            assert "label" not in issue.lower().split()


class TestCompleteness:
    """Verify all expected config keys are present."""

    def test_all_config_keys_present(self):
        node = _make_node(schema=_make_schema_columns())
        result = ParallelizeConverter().convert(node, [], {})
        expected_keys = {
            "wait_for", "sleeptime", "die_on_error",
            "tstatcatcher_stats", "label",
        }
        actual_keys = set(result.component["config"].keys())
        missing = expected_keys - actual_keys
        assert not missing, f"Missing config keys: {missing}"

    def test_standard_component_structure(self):
        """Component dict has standard top-level keys from _build_component_dict."""
        node = _make_node(component_id="par_1")
        result = ParallelizeConverter().convert(node, [], {})
        assert result.component["id"] == "par_1"
        assert result.component["type"] == "tParallelize"
        assert result.component["original_type"] == "tParallelize"
        assert result.component["position"] == {"x": 100, "y": 200}
        assert isinstance(result.component["config"], dict)
        assert isinstance(result.component["schema"], dict)
        assert result.component["inputs"] == []
        assert result.component["outputs"] == []


class TestPhantomParams:
    """No phantom params removed in this rewrite (placeholder for pattern compliance)."""

    def test_no_unexpected_config_keys(self):
        """Verify no unexpected keys sneak into the config dict."""
        node = _make_node()
        result = ParallelizeConverter().convert(node, [], {})
        allowed_keys = {
            "wait_for", "sleeptime", "die_on_error",
            "tstatcatcher_stats", "label",
        }
        actual_keys = set(result.component["config"].keys())
        unexpected = actual_keys - allowed_keys
        assert not unexpected, f"Unexpected config keys: {unexpected}"
