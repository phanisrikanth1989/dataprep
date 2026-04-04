"""Tests for DieConverter (tDie -> v1 die config)."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.control.die import DieConverter
from src.converters.talend_to_v1.components.registry import REGISTRY


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


def _make_node(params=None, schema=None, component_id="die_1",
               component_type="tDie"):
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
        """tDie resolves to DieConverter in the registry."""
        assert REGISTRY.get("tDie") is DieConverter


class TestDefaults:
    """Verify all parameters have correct defaults when no params provided."""

    def test_message_default(self):
        """Default MESSAGE is 'the end is near' per _java.xml."""
        node = _make_node()
        result = DieConverter().convert(node, [], {})
        assert result.component["config"]["message"] == "the end is near"

    def test_code_default(self):
        """Default CODE is '4' per _java.xml."""
        node = _make_node()
        result = DieConverter().convert(node, [], {})
        assert result.component["config"]["code"] == "4"

    def test_priority_default(self):
        """Default PRIORITY is '5' (ERROR) per _java.xml."""
        node = _make_node()
        result = DieConverter().convert(node, [], {})
        assert result.component["config"]["priority"] == "5"

    def test_exit_jvm_default(self):
        """Default EXIT_JVM is False per _java.xml."""
        node = _make_node()
        result = DieConverter().convert(node, [], {})
        assert result.component["config"]["exit_jvm"] is False


class TestParameterExtraction:
    """Verify each parameter is correctly extracted from XML params."""

    def test_message_extracted(self):
        """MESSAGE with quotes is extracted and unquoted."""
        node = _make_node(params={"MESSAGE": '"Custom die message"'})
        result = DieConverter().convert(node, [], {})
        assert result.component["config"]["message"] == "Custom die message"

    def test_message_without_quotes(self):
        """MESSAGE without surrounding quotes passes through as-is."""
        node = _make_node(params={"MESSAGE": "Plain message"})
        result = DieConverter().convert(node, [], {})
        assert result.component["config"]["message"] == "Plain message"

    def test_code_extracted(self):
        """CODE is extracted as string."""
        node = _make_node(params={"CODE": '"99"'})
        result = DieConverter().convert(node, [], {})
        assert result.component["config"]["code"] == "99"

    def test_code_unquoted(self):
        """CODE without quotes is extracted as-is."""
        node = _make_node(params={"CODE": "42"})
        result = DieConverter().convert(node, [], {})
        assert result.component["config"]["code"] == "42"

    def test_priority_trace(self):
        """PRIORITY=1 (TRACE) extracted correctly."""
        node = _make_node(params={"PRIORITY": '"1"'})
        result = DieConverter().convert(node, [], {})
        assert result.component["config"]["priority"] == "1"

    def test_priority_fatal(self):
        """PRIORITY=6 (FATAL) extracted correctly."""
        node = _make_node(params={"PRIORITY": '"6"'})
        result = DieConverter().convert(node, [], {})
        assert result.component["config"]["priority"] == "6"

    def test_exit_jvm_true(self):
        """EXIT_JVM=true extracted correctly."""
        node = _make_node(params={"EXIT_JVM": "true"})
        result = DieConverter().convert(node, [], {})
        assert result.component["config"]["exit_jvm"] is True


class TestFrameworkParams:
    """Verify tstatcatcher_stats and label extraction."""

    def test_tstatcatcher_stats_default_false(self):
        """Default TSTATCATCHER_STATS is False."""
        node = _make_node()
        result = DieConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is False

    def test_tstatcatcher_stats_true(self):
        """TSTATCATCHER_STATS=true extracted correctly."""
        node = _make_node(params={"TSTATCATCHER_STATS": "true"})
        result = DieConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is True

    def test_label_default_empty(self):
        """Default LABEL is empty string."""
        node = _make_node()
        result = DieConverter().convert(node, [], {})
        assert result.component["config"]["label"] == ""

    def test_label_extracted(self):
        """LABEL with quotes is extracted and unquoted."""
        node = _make_node(params={"LABEL": '"die-step"'})
        result = DieConverter().convert(node, [], {})
        assert result.component["config"]["label"] == "die-step"


class TestSchema:
    """Verify schema extraction."""

    def test_schema_is_dict(self):
        """tDie schema is a dict with input/output keys (control component, no data flow)."""
        node = _make_node(schema=_make_schema_columns())
        result = DieConverter().convert(node, [], {})
        schema = result.component["schema"]
        assert isinstance(schema, dict)
        assert "input" in schema
        assert "output" in schema

    def test_empty_schema_when_no_columns(self):
        """tDie with no schema columns produces empty dict."""
        node = _make_node()
        result = DieConverter().convert(node, [], {})
        assert result.component["schema"] == {"input": [], "output": []}


class TestNeedsReview:
    """Verify needs_review entries for engine gaps."""

    def test_needs_review_count(self):
        """3 needs_review entries: message default, code default, EXIT_JVM."""
        node = _make_node()
        result = DieConverter().convert(node, [], {})
        assert len(result.needs_review) == 3

    def test_needs_review_message_default_mismatch(self):
        """Engine message default differs from Talend default."""
        node = _make_node()
        result = DieConverter().convert(node, [], {})
        issues = [e["issue"] for e in result.needs_review]
        assert any("message" in i.lower() and "Job execution stopped" in i for i in issues)

    def test_needs_review_code_default_mismatch(self):
        """Engine code default differs from Talend default."""
        node = _make_node()
        result = DieConverter().convert(node, [], {})
        issues = [e["issue"] for e in result.needs_review]
        assert any("code" in i.lower() and "1" in i for i in issues)

    def test_needs_review_exit_jvm_not_supported(self):
        """EXIT_JVM not read by engine."""
        node = _make_node()
        result = DieConverter().convert(node, [], {})
        issues = [e["issue"] for e in result.needs_review]
        assert any("EXIT_JVM" in i for i in issues)

    def test_needs_review_severity_engine_gap(self):
        """All needs_review entries have severity 'engine_gap'."""
        node = _make_node()
        result = DieConverter().convert(node, [], {})
        for entry in result.needs_review:
            assert entry["severity"] == "engine_gap"

    def test_needs_review_has_component_id(self):
        """All needs_review entries contain correct component_id."""
        node = _make_node(component_id="test_die_comp")
        result = DieConverter().convert(node, [], {})
        for entry in result.needs_review:
            assert entry["component"] == "test_die_comp"

    def test_no_framework_param_needs_review(self):
        """Framework params (tstatcatcher_stats, label) must NOT have needs_review."""
        node = _make_node()
        result = DieConverter().convert(node, [], {})
        issues = [e["issue"] for e in result.needs_review]
        for issue in issues:
            assert "tstatcatcher_stats" not in issue
            assert "label" not in issue.lower().split()


class TestCompleteness:
    """Verify all expected config keys are present."""

    def test_all_config_keys_present(self):
        """All 6 config keys must be present."""
        node = _make_node()
        result = DieConverter().convert(node, [], {})
        cfg = result.component["config"]
        expected_keys = {
            "message", "code", "priority", "exit_jvm",
            "tstatcatcher_stats", "label",
        }
        missing = expected_keys - set(cfg.keys())
        assert not missing, f"Missing config keys: {missing}"

    def test_base_keys_present(self):
        """Base component dict keys must be present."""
        node = _make_node()
        result = DieConverter().convert(node, [], {})
        comp = result.component
        assert "id" in comp
        assert "type" in comp
        assert "original_type" in comp
        assert "position" in comp
        assert "config" in comp
        assert "schema" in comp
        assert "inputs" in comp
        assert "outputs" in comp

    def test_component_type_and_id(self):
        """Component type is 'Die' and id matches node."""
        node = _make_node(component_id="my_die")
        result = DieConverter().convert(node, [], {})
        assert result.component["id"] == "my_die"
        assert result.component["type"] == "Die"
        assert result.component["original_type"] == "tDie"


class TestPhantomParams:
    """Verify params NOT in _java.xml are NOT extracted."""

    def test_no_exit_code_key(self):
        """exit_code is an engine phantom -- must NOT be in converter output."""
        node = _make_node()
        result = DieConverter().convert(node, [], {})
        assert "exit_code" not in result.component["config"]

    def test_exit_code_not_extracted_even_when_provided(self):
        """Even if EXIT_CODE param is in XML, converter must not extract it."""
        node = _make_node(params={"EXIT_CODE": "99"})
        result = DieConverter().convert(node, [], {})
        assert "exit_code" not in result.component["config"]
