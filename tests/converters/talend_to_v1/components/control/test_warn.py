"""Tests for WarnConverter (tWarn -> v1 warn config)."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendNode,
)
from src.converters.talend_to_v1.components.control.warn import WarnConverter
from src.converters.talend_to_v1.components.registry import REGISTRY


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


def _make_node(params=None, schema=None, component_id="warn_1",
               component_type="tWarn"):
    """Create a TalendNode for testing."""
    return TalendNode(
        component_id=component_id,
        component_type=component_type,
        params=params or {},
        schema=schema or {},
        position={"x": 320, "y": 160},
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
        """tWarn maps to WarnConverter in the registry."""
        assert REGISTRY.get("tWarn") is WarnConverter


class TestDefaults:
    """Verify all parameters have correct defaults when no params provided."""

    def test_message_default(self):
        """MESSAGE defaults to 'this is a warning' per _java.xml."""
        node = _make_node()
        result = WarnConverter().convert(node, [], {})
        assert result.component["config"]["message"] == "this is a warning"

    def test_code_default(self):
        """CODE defaults to '42' per _java.xml (TEXT type, string value)."""
        node = _make_node()
        result = WarnConverter().convert(node, [], {})
        assert result.component["config"]["code"] == "42"

    def test_priority_default(self):
        """PRIORITY defaults to '4' (WARNING level) per _java.xml."""
        node = _make_node()
        result = WarnConverter().convert(node, [], {})
        assert result.component["config"]["priority"] == "4"


class TestParameterExtraction:
    """Verify each parameter is correctly extracted from XML params."""

    def test_message_extracted(self):
        """Quoted MESSAGE value is extracted with quotes stripped."""
        node = _make_node(params={"MESSAGE": '"Custom warning"'})
        result = WarnConverter().convert(node, [], {})
        assert result.component["config"]["message"] == "Custom warning"

    def test_code_extracted(self):
        """Quoted CODE value is extracted with quotes stripped."""
        node = _make_node(params={"CODE": '"99"'})
        result = WarnConverter().convert(node, [], {})
        assert result.component["config"]["code"] == "99"

    def test_priority_trace(self):
        """PRIORITY 1 (TRACE) is extracted correctly."""
        node = _make_node(params={"PRIORITY": '"1"'})
        result = WarnConverter().convert(node, [], {})
        assert result.component["config"]["priority"] == "1"

    def test_priority_fatal(self):
        """PRIORITY 6 (FATAL) is extracted correctly."""
        node = _make_node(params={"PRIORITY": '"6"'})
        result = WarnConverter().convert(node, [], {})
        assert result.component["config"]["priority"] == "6"

    def test_message_with_context_var(self):
        """MESSAGE containing context variable expression is preserved as-is."""
        node = _make_node(params={"MESSAGE": '"context.msg"'})
        result = WarnConverter().convert(node, [], {})
        assert result.component["config"]["message"] == "context.msg"


class TestFrameworkParams:
    """Verify tstatcatcher_stats and label extraction."""

    def test_tstatcatcher_stats_default_false(self):
        """TSTATCATCHER_STATS defaults to False."""
        node = _make_node()
        result = WarnConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is False

    def test_tstatcatcher_stats_true(self):
        """TSTATCATCHER_STATS 'true' is extracted as boolean True."""
        node = _make_node(params={"TSTATCATCHER_STATS": "true"})
        result = WarnConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is True

    def test_label_default_empty(self):
        """LABEL defaults to empty string."""
        node = _make_node()
        result = WarnConverter().convert(node, [], {})
        assert result.component["config"]["label"] == ""

    def test_label_extracted(self):
        """Quoted LABEL value is extracted with quotes stripped."""
        node = _make_node(params={"LABEL": '"warn-step"'})
        result = WarnConverter().convert(node, [], {})
        assert result.component["config"]["label"] == "warn-step"


class TestSchema:
    """Verify schema extraction."""

    def test_schema_extracted(self):
        """Schema is at top-level component dict (via _build_component_dict)."""
        node = _make_node(schema=_make_schema_columns())
        result = WarnConverter().convert(node, [], {})
        schema = result.component["schema"]
        assert isinstance(schema, dict)
        assert "input" in schema and "output" in schema


class TestNeedsReview:
    """Verify needs_review entries for engine gaps (per D-24: per-feature)."""

    def test_needs_review_message_default_mismatch(self):
        """Needs review entry emitted for message default mismatch."""
        node = _make_node()
        result = WarnConverter().convert(node, [], {})
        issues = [e["issue"] for e in result.needs_review]
        assert any("message" in i.lower() for i in issues)

    def test_needs_review_code_default_mismatch(self):
        """Needs review entry emitted for code default mismatch."""
        node = _make_node()
        result = WarnConverter().convert(node, [], {})
        issues = [e["issue"] for e in result.needs_review]
        assert any("code" in i.lower() for i in issues)

    def test_needs_review_severity_engine_gap(self):
        """All needs_review entries have severity 'engine_gap'."""
        node = _make_node()
        result = WarnConverter().convert(node, [], {})
        for entry in result.needs_review:
            assert entry["severity"] == "engine_gap"

    def test_needs_review_has_component_id(self):
        """All needs_review entries include the component ID."""
        node = _make_node(component_id="tWarn_3")
        result = WarnConverter().convert(node, [], {})
        for entry in result.needs_review:
            assert entry["component"] == "tWarn_3"

    def test_no_framework_param_needs_review(self):
        """Framework params (tstatcatcher_stats, label) must NOT have needs_review."""
        node = _make_node()
        result = WarnConverter().convert(node, [], {})
        issues = [e["issue"] for e in result.needs_review]
        for issue in issues:
            assert "tstatcatcher_stats" not in issue
            assert "label" not in issue.lower().split()


class TestCompleteness:
    """Verify all expected config keys are present."""

    def test_all_config_keys_present(self):
        """Config dict contains all 5 expected keys (3 unique + 2 framework)."""
        node = _make_node()
        result = WarnConverter().convert(node, [], {})
        cfg = result.component["config"]
        expected_keys = {
            "message", "code", "priority",
            "tstatcatcher_stats", "label",
        }
        # Config may also contain schema and base keys
        missing = expected_keys - set(cfg.keys())
        assert not missing, f"Missing config keys: {missing}"


class TestPhantomParams:
    """Verify no phantom params are extracted (none removed for tWarn)."""

    def test_no_phantom_params(self):
        """tWarn has no phantom params to remove -- config keys match _java.xml exactly."""
        node = _make_node()
        result = WarnConverter().convert(node, [], {})
        cfg = result.component["config"]
        # All keys should be from the known set (no schema, component_type, component_id in config)
        known_keys = {
            "message", "code", "priority",
            "tstatcatcher_stats", "label",
        }
        unexpected = set(cfg.keys()) - known_keys
        assert not unexpected, f"Unexpected config keys: {unexpected}"
