"""Tests for ContextLoadConverter (tContextLoad -> v1 context load config)."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.context.context_load import (
    ContextLoadConverter,
)
from src.converters.talend_to_v1.components.registry import REGISTRY


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

def _make_node(params=None, schema=None, component_id="cl_1",
               component_type="tContextLoad"):
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
    """Return a sample FLOW schema with key/value columns."""
    return {
        "FLOW": [
            SchemaColumn(name="key", type="id_String", nullable=False, key=True, length=255),
            SchemaColumn(name="value", type="id_String", nullable=True, length=255),
        ]
    }


# ------------------------------------------------------------------
# Test Classes (one per concern)
# ------------------------------------------------------------------


class TestRegistration:
    """Verify component is registered correctly."""

    def test_registered_in_registry(self):
        """tContextLoad maps to ContextLoadConverter in the registry."""
        assert REGISTRY.get("tContextLoad") is ContextLoadConverter


class TestDefaults:
    """Verify all parameters have correct defaults when no params provided."""

    def test_print_operations_default_false(self):
        """print_operations defaults to False."""
        node = _make_node()
        result = ContextLoadConverter().convert(node, [], {})
        assert result.component["config"]["print_operations"] is False

    def test_die_on_error_default_false(self):
        """die_on_error defaults to False."""
        node = _make_node()
        result = ContextLoadConverter().convert(node, [], {})
        assert result.component["config"]["die_on_error"] is False

    def test_disable_error_default_false(self):
        """disable_error defaults to False."""
        node = _make_node()
        result = ContextLoadConverter().convert(node, [], {})
        assert result.component["config"]["disable_error"] is False

    def test_disable_warnings_default_true(self):
        """disable_warnings defaults to True per _java.xml."""
        node = _make_node()
        result = ContextLoadConverter().convert(node, [], {})
        assert result.component["config"]["disable_warnings"] is True

    def test_disable_info_default_true(self):
        """disable_info defaults to True per _java.xml."""
        node = _make_node()
        result = ContextLoadConverter().convert(node, [], {})
        assert result.component["config"]["disable_info"] is True

    def test_load_new_variable_default_warning(self):
        """load_new_variable defaults to 'WARNING' (uppercase per _java.xml)."""
        node = _make_node()
        result = ContextLoadConverter().convert(node, [], {})
        assert result.component["config"]["load_new_variable"] == "WARNING"

    def test_not_load_old_variable_default_warning(self):
        """not_load_old_variable defaults to 'WARNING' (uppercase per _java.xml)."""
        node = _make_node()
        result = ContextLoadConverter().convert(node, [], {})
        assert result.component["config"]["not_load_old_variable"] == "WARNING"


class TestParameterExtraction:
    """Verify each parameter is correctly extracted from XML params."""

    def test_load_new_variable_error(self):
        """LOAD_NEW_VARIABLE='ERROR' extracted correctly."""
        node = _make_node(params={"LOAD_NEW_VARIABLE": '"ERROR"'})
        result = ContextLoadConverter().convert(node, [], {})
        assert result.component["config"]["load_new_variable"] == "ERROR"

    def test_not_load_old_variable_info(self):
        """NOT_LOAD_OLD_VARIABLE='INFO' extracted correctly."""
        node = _make_node(params={"NOT_LOAD_OLD_VARIABLE": '"INFO"'})
        result = ContextLoadConverter().convert(node, [], {})
        assert result.component["config"]["not_load_old_variable"] == "INFO"

    def test_print_operations_true(self):
        """PRINT_OPERATIONS='true' extracted as True."""
        node = _make_node(params={"PRINT_OPERATIONS": "true"})
        result = ContextLoadConverter().convert(node, [], {})
        assert result.component["config"]["print_operations"] is True

    def test_die_on_error_via_dieonerror(self):
        """DIEONERROR='true' extracted as die_on_error=True (no underscore in XML)."""
        node = _make_node(params={"DIEONERROR": "true"})
        result = ContextLoadConverter().convert(node, [], {})
        assert result.component["config"]["die_on_error"] is True

    def test_die_on_error_via_die_on_error(self):
        """DIE_ON_ERROR='true' extracted as die_on_error=True (fallback name)."""
        node = _make_node(params={"DIE_ON_ERROR": "true"})
        result = ContextLoadConverter().convert(node, [], {})
        assert result.component["config"]["die_on_error"] is True

    def test_die_on_error_dieonerror_takes_priority(self):
        """When both DIEONERROR and DIE_ON_ERROR are set, DIEONERROR (canonical) wins."""
        node = _make_node(params={"DIEONERROR": "true", "DIE_ON_ERROR": "false"})
        result = ContextLoadConverter().convert(node, [], {})
        assert result.component["config"]["die_on_error"] is True

    def test_disable_error_true(self):
        """DISABLE_WARNINGS='false' overrides default True."""
        node = _make_node(params={"DISABLE_WARNINGS": "false"})
        result = ContextLoadConverter().convert(node, [], {})
        assert result.component["config"]["disable_warnings"] is False

    def test_disable_info_false(self):
        """DISABLE_INFO='false' overrides default True."""
        node = _make_node(params={"DISABLE_INFO": "false"})
        result = ContextLoadConverter().convert(node, [], {})
        assert result.component["config"]["disable_info"] is False


class TestFrameworkParams:
    """Verify tstatcatcher_stats and label extraction."""

    def test_tstatcatcher_stats_default_false(self):
        """tstatcatcher_stats defaults to False."""
        node = _make_node()
        result = ContextLoadConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is False

    def test_tstatcatcher_stats_true(self):
        """tstatcatcher_stats is True when TSTATCATCHER_STATS='true'."""
        node = _make_node(params={"TSTATCATCHER_STATS": "true"})
        result = ContextLoadConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is True

    def test_label_default_empty(self):
        """label defaults to empty string."""
        node = _make_node()
        result = ContextLoadConverter().convert(node, [], {})
        assert result.component["config"]["label"] == ""

    def test_label_extracted(self):
        """label extracted correctly from LABEL param."""
        node = _make_node(params={"LABEL": '"ctx-load-step"'})
        result = ContextLoadConverter().convert(node, [], {})
        assert result.component["config"]["label"] == "ctx-load-step"


class TestSchema:
    """Verify schema extraction."""

    def test_schema_extracted(self):
        """Utility component has empty input/output schema."""
        node = _make_node(schema=_make_schema_columns())
        result = ContextLoadConverter().convert(node, [], {})
        assert result.component["schema"] == {"input": [], "output": []}

    def test_no_inputs_outputs(self):
        """Utility component has empty inputs and outputs lists."""
        node = _make_node()
        result = ContextLoadConverter().convert(node, [], {})
        assert result.component["inputs"] == []
        assert result.component["outputs"] == []


class TestNeedsReview:
    """Verify needs_review entries for engine gaps."""

    def test_needs_review_count(self):
        """Exactly 6 needs_review entries for engine-gap params."""
        node = _make_node()
        result = ContextLoadConverter().convert(node, [], {})
        assert len(result.needs_review) == 6

    def test_needs_review_severity_engine_gap(self):
        """All needs_review entries have severity 'engine_gap'."""
        node = _make_node()
        result = ContextLoadConverter().convert(node, [], {})
        for entry in result.needs_review:
            assert entry["severity"] == "engine_gap"

    def test_needs_review_has_component_id(self):
        """All needs_review entries reference the correct component_id."""
        node = _make_node(component_id="ctx_test_5")
        result = ContextLoadConverter().convert(node, [], {})
        for entry in result.needs_review:
            assert entry["component"] == "ctx_test_5"

    def test_no_framework_param_needs_review(self):
        """Framework params (tstatcatcher_stats, label) must NOT have needs_review."""
        node = _make_node()
        result = ContextLoadConverter().convert(node, [], {})
        issues = [e["issue"] for e in result.needs_review]
        for issue in issues:
            assert "tstatcatcher_stats" not in issue
            assert "label" not in issue.lower().split()


class TestCompleteness:
    """Verify all expected config keys are present."""

    def test_all_config_keys_present(self):
        """Config dict has exactly 9 keys covering all params."""
        node = _make_node()
        result = ContextLoadConverter().convert(node, [], {})
        cfg = result.component["config"]

        expected_keys = {
            "print_operations", "die_on_error",
            "disable_error", "disable_warnings", "disable_info",
            "load_new_variable", "not_load_old_variable",
            "tstatcatcher_stats", "label",
        }
        assert set(cfg.keys()) == expected_keys


class TestPhantomParams:
    """Verify implicit context load params are NOT extracted."""

    def test_contextfile_not_extracted(self):
        """CONTEXTFILE is a job-level implicit context param, not a tContextLoad param."""
        node = _make_node(params={"CONTEXTFILE": '"/opt/ctx.properties"'})
        result = ContextLoadConverter().convert(node, [], {})
        assert "filepath" not in result.component["config"]

    def test_format_not_extracted(self):
        """FORMAT is a job-level implicit context param, not a tContextLoad param."""
        node = _make_node(params={"FORMAT": '"csv"'})
        result = ContextLoadConverter().convert(node, [], {})
        assert "format" not in result.component["config"]

    def test_csv_separator_not_extracted(self):
        """CSV_SEPARATOR is a job-level implicit context param, not a tContextLoad param."""
        node = _make_node(params={"CSV_SEPARATOR": '","'})
        result = ContextLoadConverter().convert(node, [], {})
        assert "csv_separator" not in result.component["config"]

    def test_error_if_not_exists_not_extracted(self):
        """ERROR_IF_NOT_EXISTS is a job-level implicit context param, not a tContextLoad param."""
        node = _make_node(params={"ERROR_IF_NOT_EXISTS": "false"})
        result = ContextLoadConverter().convert(node, [], {})
        assert "error_if_not_exists" not in result.component["config"]

    def test_component_dict_structure(self):
        """Component dict has standard structure fields."""
        node = _make_node()
        result = ContextLoadConverter().convert(node, [], {})
        comp = result.component
        assert comp["id"] == "cl_1"
        assert comp["type"] == "ContextLoad"
        assert comp["original_type"] == "tContextLoad"
        assert comp["position"] == {"x": 320, "y": 160}


class TestWarnings:
    """Verify warnings for edge cases."""

    def test_no_warnings_default(self):
        """No warnings with default params."""
        node = _make_node(params={})
        result = ContextLoadConverter().convert(node, [], {})
        assert result.warnings == []
