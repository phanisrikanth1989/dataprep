"""Tests for LogRowConverter (tLogRow -> v1 LogRow config)."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.transform.log_row import (
    LogRowConverter,
)
from src.converters.talend_to_v1.components.registry import REGISTRY


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

def _make_node(params=None, schema=None, component_id="lr_1",
               component_type="tLogRow"):
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


def _make_lengths_data(widths):
    """Generate LENGTHS TABLE data with stride-1 (LENGTH only).

    widths: list of int values for column widths
    """
    result = []
    for w in widths:
        result.append({"elementRef": "LENGTH", "value": str(w)})
    return result


# ------------------------------------------------------------------
# Test Classes
# ------------------------------------------------------------------


class TestRegistration:
    """Verify component is registered correctly."""

    def test_registered_in_registry(self):
        assert REGISTRY.get("tLogRow") is LogRowConverter


class TestDefaults:
    """Verify all parameters have correct defaults when no params provided."""

    def test_basic_mode_default_true(self):
        node = _make_node()
        result = LogRowConverter().convert(node, [], {})
        assert result.component["config"]["basic_mode"] is True

    def test_table_print_default_false(self):
        node = _make_node()
        result = LogRowConverter().convert(node, [], {})
        assert result.component["config"]["table_print"] is False

    def test_vertical_default_false(self):
        node = _make_node()
        result = LogRowConverter().convert(node, [], {})
        assert result.component["config"]["vertical"] is False

    def test_print_unique_default_true(self):
        node = _make_node()
        result = LogRowConverter().convert(node, [], {})
        assert result.component["config"]["print_unique"] is True

    def test_print_label_default_false(self):
        node = _make_node()
        result = LogRowConverter().convert(node, [], {})
        assert result.component["config"]["print_label"] is False

    def test_print_unique_label_default_false(self):
        node = _make_node()
        result = LogRowConverter().convert(node, [], {})
        assert result.component["config"]["print_unique_label"] is False

    def test_fieldseparator_default(self):
        node = _make_node()
        result = LogRowConverter().convert(node, [], {})
        assert result.component["config"]["fieldseparator"] == "|"

    def test_print_header_default_false(self):
        node = _make_node()
        result = LogRowConverter().convert(node, [], {})
        assert result.component["config"]["print_header"] is False

    def test_print_unique_name_default_false(self):
        node = _make_node()
        result = LogRowConverter().convert(node, [], {})
        assert result.component["config"]["print_unique_name"] is False

    def test_print_colnames_default_false(self):
        node = _make_node()
        result = LogRowConverter().convert(node, [], {})
        assert result.component["config"]["print_colnames"] is False

    def test_use_fixed_length_default_false(self):
        node = _make_node()
        result = LogRowConverter().convert(node, [], {})
        assert result.component["config"]["use_fixed_length"] is False

    def test_lengths_default_empty(self):
        node = _make_node()
        result = LogRowConverter().convert(node, [], {})
        assert result.component["config"]["lengths"] == []

    def test_print_content_with_log4j_default_true(self):
        node = _make_node()
        result = LogRowConverter().convert(node, [], {})
        assert result.component["config"]["print_content_with_log4j"] is True

    # max_rows removed in a943b5f (hidden Talend param)

    def test_tstatcatcher_stats_default_false(self):
        node = _make_node()
        result = LogRowConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is False

    def test_label_default_empty(self):
        node = _make_node()
        result = LogRowConverter().convert(node, [], {})
        assert result.component["config"]["label"] == ""


class TestParameterExtraction:
    """Verify each parameter is correctly extracted from XML params."""

    def test_fieldseparator_custom(self):
        """FIELDSEPARATOR='","' -> ","."""
        node = _make_node(params={"FIELDSEPARATOR": '","'})
        result = LogRowConverter().convert(node, [], {})
        assert result.component["config"]["fieldseparator"] == ","

    # max_rows extraction test removed in a943b5f (hidden Talend param)

    def test_lengths_parsing(self):
        """LENGTHS TABLE with 3 entries -> [10, 20, 15]."""
        lengths_data = _make_lengths_data([10, 20, 15])
        node = _make_node(params={"LENGTHS": lengths_data})
        result = LogRowConverter().convert(node, [], {})
        assert result.component["config"]["lengths"] == [10, 20, 15]

    def test_vertical_true(self):
        """VERTICAL="true" -> True."""
        node = _make_node(params={"VERTICAL": "true"})
        result = LogRowConverter().convert(node, [], {})
        assert result.component["config"]["vertical"] is True

    def test_table_print_true(self):
        """TABLE_PRINT="true" -> True."""
        node = _make_node(params={"TABLE_PRINT": "true"})
        result = LogRowConverter().convert(node, [], {})
        assert result.component["config"]["table_print"] is True


class TestFrameworkParams:
    """Verify tstatcatcher_stats and label extraction."""

    def test_tstatcatcher_stats_true(self):
        node = _make_node(params={"TSTATCATCHER_STATS": "true"})
        result = LogRowConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is True

    def test_label_extracted(self):
        node = _make_node(params={"LABEL": '"my_label"'})
        result = LogRowConverter().convert(node, [], {})
        assert result.component["config"]["label"] == "my_label"


class TestSchema:
    """Verify schema extraction."""

    def test_schema_passthrough(self):
        """LogRow is passthrough: input schema == output schema."""
        node = _make_node(schema=_make_schema_columns())
        result = LogRowConverter().convert(node, [], {})
        schema = result.component["schema"]
        assert schema["input"] == schema["output"]

    def test_schema_columns_populated(self):
        """Schema columns are populated from FLOW schema."""
        node = _make_node(schema=_make_schema_columns())
        result = LogRowConverter().convert(node, [], {})
        schema = result.component["schema"]
        assert len(schema["input"]) == 2
        assert schema["input"][0]["name"] == "id"
        assert schema["input"][1]["name"] == "name"


class TestNeedsReview:
    """Verify needs_review entries for engine gaps."""

    def test_needs_review_has_entries(self):
        """Per-feature needs_review for engine gaps."""
        node = _make_node()
        result = LogRowConverter().convert(node, [], {})
        # Should have entries for engine-unread params and default mismatches
        assert len(result.needs_review) > 0

    def test_needs_review_engine_gap_severity(self):
        """All entries have severity == 'engine_gap'."""
        node = _make_node()
        result = LogRowConverter().convert(node, [], {})
        for entry in result.needs_review:
            assert entry["severity"] == "engine_gap"

    def test_needs_review_has_component_id(self):
        node = _make_node(component_id="test_comp")
        result = LogRowConverter().convert(node, [], {})
        for entry in result.needs_review:
            assert entry["component"] == "test_comp"

    def test_no_framework_param_needs_review(self):
        """Framework params (tstatcatcher_stats, label) must NOT have needs_review."""
        node = _make_node()
        result = LogRowConverter().convert(node, [], {})
        issues = [e["issue"] for e in result.needs_review]
        for issue in issues:
            assert "tstatcatcher_stats" not in issue
            assert "label" not in issue.lower().split()


class TestCompleteness:
    """Verify all expected config keys are present."""

    def test_all_config_keys_present(self):
        """12 unique + 2 framework = 14 total config keys.

        max_rows removed in a943b5f (hidden Talend param).
        """
        node = _make_node(schema=_make_schema_columns())
        result = LogRowConverter().convert(node, [], {})
        expected_keys = {
            "basic_mode", "table_print", "vertical",
            "print_unique", "print_label", "print_unique_label",
            "fieldseparator", "print_header", "print_unique_name",
            "print_colnames", "use_fixed_length", "lengths",
            "print_content_with_log4j",
            "tstatcatcher_stats", "label",
        }
        actual_keys = set(result.component["config"].keys())
        missing = expected_keys - actual_keys
        assert not missing, f"Missing config keys: {missing}"


class TestComponentStructure:
    """Verify component wrapper structure."""

    def test_has_type(self):
        node = _make_node()
        result = LogRowConverter().convert(node, [], {})
        assert result.component["type"] == "LogRow"

    def test_has_original_type(self):
        node = _make_node()
        result = LogRowConverter().convert(node, [], {})
        assert result.component["original_type"] == "tLogRow"
