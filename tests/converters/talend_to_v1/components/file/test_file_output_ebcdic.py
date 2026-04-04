"""Tests for FileOutputEbcdicConverter (tFileOutputEBCDIC -> tFileOutputEBCDIC).

No-engine component -- converter uses Talend name as type_name per D-43.
Enterprise-only component -- _java.xml not available, LOW confidence params.
"""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.file.file_output_ebcdic import (
    FileOutputEbcdicConverter,
)
from src.converters.talend_to_v1.components.registry import REGISTRY


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

def _make_node(params=None, schema=None, component_id="ebcdic_out_1",
               component_type="tFileOutputEBCDIC"):
    """Create a TalendNode for testing."""
    return TalendNode(
        component_id=component_id,
        component_type=component_type,
        params=params or {},
        schema=schema or {},
        position={"x": 300, "y": 400},
        raw_xml=ET.Element("node"),
    )


def _make_schema_columns():
    """Return a sample FLOW schema for testing."""
    return {
        "FLOW": [
            SchemaColumn(name="record_id", type="id_Integer", nullable=False, key=True, length=10),
            SchemaColumn(name="name", type="id_String", nullable=True, length=50),
            SchemaColumn(name="amount", type="id_Double", precision=2),
        ]
    }


# ------------------------------------------------------------------
# Test Classes (one per concern)
# ------------------------------------------------------------------


class TestRegistration:
    """Verify component is registered correctly."""

    def test_registered_in_registry(self):
        assert REGISTRY.get("tFileOutputEBCDIC") is FileOutputEbcdicConverter


class TestDefaults:
    """Verify all parameters have correct defaults when no params provided."""

    def test_filename_default(self):
        node = _make_node()
        result = FileOutputEbcdicConverter().convert(node, [], {})
        assert result.component["config"]["filename"] == ""

    def test_encoding_default(self):
        """EBCDIC encoding -- Cp1047 is the default EBCDIC codepage."""
        node = _make_node()
        result = FileOutputEbcdicConverter().convert(node, [], {})
        assert result.component["config"]["encoding"] == "Cp1047"

    def test_append_default(self):
        node = _make_node()
        result = FileOutputEbcdicConverter().convert(node, [], {})
        assert result.component["config"]["append"] is False

    def test_rowseparator_default(self):
        node = _make_node()
        result = FileOutputEbcdicConverter().convert(node, [], {})
        assert result.component["config"]["rowseparator"] == "\\n"

    def test_die_on_error_default(self):
        node = _make_node()
        result = FileOutputEbcdicConverter().convert(node, [], {})
        assert result.component["config"]["die_on_error"] is False


class TestParameterExtraction:
    """Verify each parameter is correctly extracted from XML params."""

    def test_filename_extracted(self):
        node = _make_node(params={"FILENAME": '"output.ebcdic"'})
        result = FileOutputEbcdicConverter().convert(node, [], {})
        assert result.component["config"]["filename"] == "output.ebcdic"

    def test_encoding_custom(self):
        node = _make_node(params={"ENCODING": '"Cp037"'})
        result = FileOutputEbcdicConverter().convert(node, [], {})
        assert result.component["config"]["encoding"] == "Cp037"

    def test_append_true(self):
        node = _make_node(params={"APPEND": "true"})
        result = FileOutputEbcdicConverter().convert(node, [], {})
        assert result.component["config"]["append"] is True

    def test_rowseparator_custom(self):
        node = _make_node(params={"ROWSEPARATOR": '"\\r\\n"'})
        result = FileOutputEbcdicConverter().convert(node, [], {})
        assert result.component["config"]["rowseparator"] == "\\r\\n"

    def test_die_on_error_true(self):
        node = _make_node(params={"DIE_ON_ERROR": "true"})
        result = FileOutputEbcdicConverter().convert(node, [], {})
        assert result.component["config"]["die_on_error"] is True


class TestFrameworkParams:
    """Verify tstatcatcher_stats and label extraction."""

    def test_tstatcatcher_stats_default_false(self):
        node = _make_node()
        result = FileOutputEbcdicConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is False

    def test_tstatcatcher_stats_true(self):
        node = _make_node(params={"TSTATCATCHER_STATS": "true"})
        result = FileOutputEbcdicConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is True

    def test_label_default_empty(self):
        node = _make_node()
        result = FileOutputEbcdicConverter().convert(node, [], {})
        assert result.component["config"]["label"] == ""

    def test_label_extracted(self):
        node = _make_node(params={"LABEL": '"my_label"'})
        result = FileOutputEbcdicConverter().convert(node, [], {})
        assert result.component["config"]["label"] == "my_label"


class TestSchema:
    """Verify schema extraction -- SINK per D-55."""

    def test_schema_input_populated(self):
        """SINK component: schema input has columns from FLOW."""
        node = _make_node(schema=_make_schema_columns())
        result = FileOutputEbcdicConverter().convert(node, [], {})
        schema = result.component["schema"]
        assert len(schema["input"]) == 3
        assert schema["input"][0]["name"] == "record_id"

    def test_schema_output_empty(self):
        """SINK component: output schema is always empty."""
        node = _make_node(schema=_make_schema_columns())
        result = FileOutputEbcdicConverter().convert(node, [], {})
        assert result.component["schema"]["output"] == []

    def test_schema_empty_when_no_flow(self):
        """When no FLOW schema provided, both input and output are empty."""
        node = _make_node()
        result = FileOutputEbcdicConverter().convert(node, [], {})
        assert result.component["schema"]["input"] == []
        assert result.component["schema"]["output"] == []


class TestNeedsReview:
    """Verify needs_review entries for engine gaps."""

    def test_single_consolidated_needs_review(self):
        """Exactly 1 entry per D-51 (no engine)."""
        node = _make_node()
        result = FileOutputEbcdicConverter().convert(node, [], {})
        assert len(result.needs_review) == 1

    def test_needs_review_severity(self):
        node = _make_node()
        result = FileOutputEbcdicConverter().convert(node, [], {})
        assert result.needs_review[0]["severity"] == "engine_gap"

    def test_needs_review_has_component_id(self):
        node = _make_node(component_id="test_comp")
        result = FileOutputEbcdicConverter().convert(node, [], {})
        assert result.needs_review[0]["component"] == "test_comp"

    def test_no_framework_param_needs_review(self):
        """Framework params (tstatcatcher_stats, label) must NOT have needs_review."""
        node = _make_node()
        result = FileOutputEbcdicConverter().convert(node, [], {})
        issues = [e["issue"] for e in result.needs_review]
        for issue in issues:
            assert "tstatcatcher_stats" not in issue
            assert "label" not in issue.lower().split()


class TestCompleteness:
    """Verify all expected config keys are present."""

    def test_all_config_keys_present(self):
        node = _make_node(schema=_make_schema_columns())
        result = FileOutputEbcdicConverter().convert(node, [], {})
        expected_keys = {
            "filename", "encoding", "append", "rowseparator", "die_on_error",
            "tstatcatcher_stats", "label",
        }
        actual_keys = set(result.component["config"].keys())
        missing = expected_keys - actual_keys
        assert not missing, f"Missing config keys: {missing}"


class TestComponentStructure:
    """Verify the overall component dict structure."""

    def test_has_type(self):
        """No-engine per D-43: type_name is Talend name."""
        node = _make_node()
        result = FileOutputEbcdicConverter().convert(node, [], {})
        assert result.component["type"] == "tFileOutputEBCDIC"

    def test_has_original_type(self):
        node = _make_node()
        result = FileOutputEbcdicConverter().convert(node, [], {})
        assert result.component["original_type"] == "tFileOutputEBCDIC"

    def test_has_id(self):
        node = _make_node(component_id="my_ebcdic_out")
        result = FileOutputEbcdicConverter().convert(node, [], {})
        assert result.component["id"] == "my_ebcdic_out"

    def test_has_position(self):
        node = _make_node()
        result = FileOutputEbcdicConverter().convert(node, [], {})
        assert result.component["position"] == {"x": 300, "y": 400}

    def test_uses_build_component_dict(self):
        """Verify _build_component_dict wrapper structure."""
        node = _make_node()
        result = FileOutputEbcdicConverter().convert(node, [], {})
        assert "config" in result.component
        assert "schema" in result.component
        assert "inputs" in result.component
        assert "outputs" in result.component
