"""Tests for LoopConverter (tLoop -> v1 loop config)."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.control.loop import LoopConverter
from src.converters.talend_to_v1.components.registry import REGISTRY


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

def _make_node(params=None, schema=None, component_id="loop_1",
               component_type="tLoop"):
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
        assert REGISTRY.get("tLoop") is LoopConverter


class TestDefaults:
    """Verify all parameters have correct defaults when no params provided."""

    def test_for_loop_default(self):
        """Default FORLOOP radio is true (For-loop mode selected)."""
        node = _make_node()
        result = LoopConverter().convert(node, [], {})
        assert result.component["config"]["for_loop"] is True

    def test_while_loop_default(self):
        """Default WHILELOOP radio is false."""
        node = _make_node()
        result = LoopConverter().convert(node, [], {})
        assert result.component["config"]["while_loop"] is False

    def test_from_default(self):
        """Default FROM value is '1'."""
        node = _make_node()
        result = LoopConverter().convert(node, [], {})
        assert result.component["config"]["from_value"] == "1"

    def test_to_default(self):
        """Default TO value is '10'."""
        node = _make_node()
        result = LoopConverter().convert(node, [], {})
        assert result.component["config"]["to_value"] == "10"

    def test_step_default(self):
        """Default STEP value is '1'."""
        node = _make_node()
        result = LoopConverter().convert(node, [], {})
        assert result.component["config"]["step"] == "1"

    def test_increase_default(self):
        """Default INCREASE is true (values increasing)."""
        node = _make_node()
        result = LoopConverter().convert(node, [], {})
        assert result.component["config"]["increase"] is True

    def test_declaration_default(self):
        """Default DECLARATION is 'int i=0'."""
        node = _make_node()
        result = LoopConverter().convert(node, [], {})
        assert result.component["config"]["declaration"] == "int i=0"

    def test_condition_default(self):
        """Default CONDITION is 'i<10'."""
        node = _make_node()
        result = LoopConverter().convert(node, [], {})
        assert result.component["config"]["condition"] == "i<10"

    def test_iteration_default(self):
        """Default ITERATION is 'i++'."""
        node = _make_node()
        result = LoopConverter().convert(node, [], {})
        assert result.component["config"]["iteration"] == "i++"


class TestParameterExtraction:
    """Verify each parameter is correctly extracted from XML params."""

    def test_while_loop_selected(self):
        """When WHILELOOP radio is true and FORLOOP is false, while_loop is True."""
        node = _make_node(params={"FORLOOP": "false", "WHILELOOP": "true"})
        result = LoopConverter().convert(node, [], {})
        assert result.component["config"]["for_loop"] is False
        assert result.component["config"]["while_loop"] is True

    def test_from_value_extracted(self):
        """FROM value extracted with quote stripping."""
        node = _make_node(params={"FROM": '"5"'})
        result = LoopConverter().convert(node, [], {})
        assert result.component["config"]["from_value"] == "5"

    def test_to_value_extracted(self):
        """TO value extracted with quote stripping."""
        node = _make_node(params={"TO": '"100"'})
        result = LoopConverter().convert(node, [], {})
        assert result.component["config"]["to_value"] == "100"

    def test_step_value_extracted(self):
        """STEP value extracted with quote stripping."""
        node = _make_node(params={"STEP": '"2"'})
        result = LoopConverter().convert(node, [], {})
        assert result.component["config"]["step"] == "2"

    def test_increase_false(self):
        """INCREASE can be set to false for decreasing sequences."""
        node = _make_node(params={"INCREASE": "false"})
        result = LoopConverter().convert(node, [], {})
        assert result.component["config"]["increase"] is False

    def test_declaration_extracted(self):
        """DECLARATION extracted with quote stripping."""
        node = _make_node(params={"DECLARATION": '"int j=5"'})
        result = LoopConverter().convert(node, [], {})
        assert result.component["config"]["declaration"] == "int j=5"

    def test_condition_extracted(self):
        """CONDITION extracted with quote stripping."""
        node = _make_node(params={"CONDITION": '"j<100"'})
        result = LoopConverter().convert(node, [], {})
        assert result.component["config"]["condition"] == "j<100"

    def test_iteration_extracted(self):
        """ITERATION extracted with quote stripping."""
        node = _make_node(params={"ITERATION": '"j+=5"'})
        result = LoopConverter().convert(node, [], {})
        assert result.component["config"]["iteration"] == "j+=5"


class TestFrameworkParams:
    """Verify tstatcatcher_stats and label extraction."""

    def test_tstatcatcher_stats_default_false(self):
        node = _make_node()
        result = LoopConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is False

    def test_tstatcatcher_stats_true(self):
        node = _make_node(params={"TSTATCATCHER_STATS": "true"})
        result = LoopConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is True

    def test_label_default_empty(self):
        node = _make_node()
        result = LoopConverter().convert(node, [], {})
        assert result.component["config"]["label"] == ""

    def test_label_extracted(self):
        node = _make_node(params={"LABEL": '"my_label"'})
        result = LoopConverter().convert(node, [], {})
        assert result.component["config"]["label"] == "my_label"


class TestSchema:
    """Verify schema extraction."""

    def test_schema_is_empty_control_pattern(self):
        """Control component has empty input/output schema (no data flow)."""
        node = _make_node()
        result = LoopConverter().convert(node, [], {})
        assert result.component["schema"] == {"input": [], "output": []}

    def test_standard_structure_keys(self):
        """Component dict has standard top-level keys from _build_component_dict."""
        node = _make_node(component_id="loop_1")
        result = LoopConverter().convert(node, [], {})
        assert result.component["id"] == "loop_1"
        assert result.component["type"] == "tLoop"
        assert result.component["original_type"] == "tLoop"
        assert result.component["position"] == {"x": 320, "y": 160}
        assert result.component["inputs"] == []
        assert result.component["outputs"] == []


class TestNeedsReview:
    """Verify needs_review entries for engine gaps."""

    def test_needs_review_count(self):
        """Single consolidated needs_review entry per D-23."""
        node = _make_node()
        result = LoopConverter().convert(node, [], {})
        assert len(result.needs_review) == 1

    def test_needs_review_is_engine_gap(self):
        node = _make_node()
        result = LoopConverter().convert(node, [], {})
        assert result.needs_review[0]["severity"] == "engine_gap"

    def test_needs_review_message(self):
        """Needs review message mentions no engine implementation."""
        node = _make_node()
        result = LoopConverter().convert(node, [], {})
        assert "No concrete engine implementation for tLoop" in result.needs_review[0]["issue"]

    def test_needs_review_has_component_id(self):
        node = _make_node(component_id="test_loop")
        result = LoopConverter().convert(node, [], {})
        assert result.needs_review[0]["component"] == "test_loop"

    def test_no_framework_param_needs_review(self):
        """Framework params (tstatcatcher_stats, label) must NOT have needs_review."""
        node = _make_node()
        result = LoopConverter().convert(node, [], {})
        issues = [e["issue"] for e in result.needs_review]
        for issue in issues:
            assert "tstatcatcher_stats" not in issue
            assert "label" not in issue.lower().split()


class TestCompleteness:
    """Verify all expected config keys are present."""

    def test_all_config_keys_present(self):
        node = _make_node(schema=_make_schema_columns())
        result = LoopConverter().convert(node, [], {})
        expected_keys = {
            "for_loop", "while_loop",
            "from_value", "to_value", "step", "increase",
            "declaration", "condition", "iteration",
            "tstatcatcher_stats", "label",
        }
        actual_keys = set(result.component["config"].keys())
        missing = expected_keys - actual_keys
        assert not missing, f"Missing config keys: {missing}"


class TestPhantomParams:
    """Verify params NOT in _java.xml are NOT extracted.

    The old converter extracted 6 phantom params that do not exist in tLoop _java.xml:
    LOOP_TYPE, START_VALUE, END_VALUE, STEP_VALUE, ITERATE_ON, DIE_ON_ERROR.
    These must NOT appear in the output config.
    """

    def test_no_loop_type_key(self):
        """Phantom LOOP_TYPE removed -- use FORLOOP/WHILELOOP radio bools instead."""
        node = _make_node(params={"LOOP_TYPE": '"FOR"'})
        result = LoopConverter().convert(node, [], {})
        assert "loop_type" not in result.component["config"]

    def test_no_start_value_key(self):
        """Phantom START_VALUE removed -- correct name is FROM."""
        node = _make_node(params={"START_VALUE": '"1"'})
        result = LoopConverter().convert(node, [], {})
        assert "start_value" not in result.component["config"]

    def test_no_end_value_key(self):
        """Phantom END_VALUE removed -- correct name is TO."""
        node = _make_node(params={"END_VALUE": '"10"'})
        result = LoopConverter().convert(node, [], {})
        assert "end_value" not in result.component["config"]

    def test_no_step_value_key(self):
        """Phantom STEP_VALUE removed -- correct name is STEP."""
        node = _make_node(params={"STEP_VALUE": '"1"'})
        result = LoopConverter().convert(node, [], {})
        assert "step_value" not in result.component["config"]

    def test_no_iterate_on_key(self):
        """Phantom ITERATE_ON does not exist in tLoop _java.xml."""
        node = _make_node(params={"ITERATE_ON": '"row.column"'})
        result = LoopConverter().convert(node, [], {})
        assert "iterate_on" not in result.component["config"]

    def test_no_die_on_error_key(self):
        """Phantom DIE_ON_ERROR not in tLoop _java.xml."""
        node = _make_node(params={"DIE_ON_ERROR": "true"})
        result = LoopConverter().convert(node, [], {})
        assert "die_on_error" not in result.component["config"]
