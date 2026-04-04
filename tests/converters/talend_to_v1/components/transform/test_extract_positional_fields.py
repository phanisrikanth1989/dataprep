"""Tests for ExtractPositionalFieldsConverter (tExtractPositionalFields -> v1 ExtractPositionalFields config)."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.transform.extract_positional_fields import (
    ExtractPositionalFieldsConverter,
)
from src.converters.talend_to_v1.components.registry import REGISTRY


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


def _make_node(params=None, schema=None, component_id="epf_1",
               component_type="tExtractPositionalFields"):
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


def _make_formats_data(rows):
    """Generate FORMATS TABLE data with stride-4 per row.

    rows: list of tuples (column, size, padding_char, align)
    """
    result = []
    for row_values in rows:
        for field_name, value in zip(("COLUMN", "SIZE", "PADDING_CHAR", "ALIGN"), row_values):
            result.append({"elementRef": field_name, "value": value})
    return result


# ------------------------------------------------------------------
# Test Classes (one per concern)
# ------------------------------------------------------------------


class TestRegistration:
    """Verify component is registered correctly."""

    def test_registered_in_registry(self):
        assert REGISTRY.get("tExtractPositionalFields") is ExtractPositionalFieldsConverter


class TestDefaults:
    """Verify all parameters have correct defaults when no params provided."""

    def test_field_default_empty(self):
        node = _make_node()
        result = ExtractPositionalFieldsConverter().convert(node, [], {})
        assert result.component["config"]["field"] == ""

    def test_ignore_source_null_default_true(self):
        node = _make_node()
        result = ExtractPositionalFieldsConverter().convert(node, [], {})
        assert result.component["config"]["ignore_source_null"] is True

    def test_advanced_option_default_false(self):
        node = _make_node()
        result = ExtractPositionalFieldsConverter().convert(node, [], {})
        assert result.component["config"]["advanced_option"] is False

    def test_pattern_default(self):
        node = _make_node()
        result = ExtractPositionalFieldsConverter().convert(node, [], {})
        assert result.component["config"]["pattern"] == "5,4,5"

    def test_formats_default_empty(self):
        node = _make_node()
        result = ExtractPositionalFieldsConverter().convert(node, [], {})
        assert result.component["config"]["formats"] == []

    def test_die_on_error_default_false(self):
        node = _make_node()
        result = ExtractPositionalFieldsConverter().convert(node, [], {})
        assert result.component["config"]["die_on_error"] is False

    def test_advanced_separator_default_false(self):
        node = _make_node()
        result = ExtractPositionalFieldsConverter().convert(node, [], {})
        assert result.component["config"]["advanced_separator"] is False

    def test_thousands_separator_default(self):
        node = _make_node()
        result = ExtractPositionalFieldsConverter().convert(node, [], {})
        assert result.component["config"]["thousands_separator"] == ","

    def test_decimal_separator_default(self):
        node = _make_node()
        result = ExtractPositionalFieldsConverter().convert(node, [], {})
        assert result.component["config"]["decimal_separator"] == "."

    def test_trim_default_false(self):
        node = _make_node()
        result = ExtractPositionalFieldsConverter().convert(node, [], {})
        assert result.component["config"]["trim"] is False

    def test_check_fields_num_default_false(self):
        node = _make_node()
        result = ExtractPositionalFieldsConverter().convert(node, [], {})
        assert result.component["config"]["check_fields_num"] is False

    def test_tstatcatcher_stats_default_false(self):
        node = _make_node()
        result = ExtractPositionalFieldsConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is False

    def test_label_default_empty(self):
        node = _make_node()
        result = ExtractPositionalFieldsConverter().convert(node, [], {})
        assert result.component["config"]["label"] == ""


class TestParameterExtraction:
    """Verify each parameter is correctly extracted from XML params."""

    def test_field_custom(self):
        node = _make_node(params={"FIELD": '"col1"'})
        result = ExtractPositionalFieldsConverter().convert(node, [], {})
        assert result.component["config"]["field"] == "col1"

    def test_pattern_custom(self):
        node = _make_node(params={"PATTERN": '"10,8,12"'})
        result = ExtractPositionalFieldsConverter().convert(node, [], {})
        assert result.component["config"]["pattern"] == "10,8,12"

    def test_ignore_source_null_false(self):
        node = _make_node(params={"IGNORE_SOURCE_NULL": "false"})
        result = ExtractPositionalFieldsConverter().convert(node, [], {})
        assert result.component["config"]["ignore_source_null"] is False

    def test_advanced_option_true(self):
        node = _make_node(params={"ADVANCED_OPTION": "true"})
        result = ExtractPositionalFieldsConverter().convert(node, [], {})
        assert result.component["config"]["advanced_option"] is True

    def test_die_on_error_true(self):
        node = _make_node(params={"DIE_ON_ERROR": "true"})
        result = ExtractPositionalFieldsConverter().convert(node, [], {})
        assert result.component["config"]["die_on_error"] is True

    def test_advanced_separator_true(self):
        node = _make_node(params={"ADVANCED_SEPARATOR": "true"})
        result = ExtractPositionalFieldsConverter().convert(node, [], {})
        assert result.component["config"]["advanced_separator"] is True

    def test_thousands_separator_custom(self):
        node = _make_node(params={"THOUSANDS_SEPARATOR": '"."'})
        result = ExtractPositionalFieldsConverter().convert(node, [], {})
        assert result.component["config"]["thousands_separator"] == "."

    def test_decimal_separator_custom(self):
        node = _make_node(params={"DECIMAL_SEPARATOR": '","'})
        result = ExtractPositionalFieldsConverter().convert(node, [], {})
        assert result.component["config"]["decimal_separator"] == ","

    def test_trim_true(self):
        node = _make_node(params={"TRIM": "true"})
        result = ExtractPositionalFieldsConverter().convert(node, [], {})
        assert result.component["config"]["trim"] is True

    def test_check_fields_num_true(self):
        node = _make_node(params={"CHECK_FIELDS_NUM": "true"})
        result = ExtractPositionalFieldsConverter().convert(node, [], {})
        assert result.component["config"]["check_fields_num"] is True

    def test_formats_parsing(self):
        """FORMATS TABLE with stride-4 entries parsed into list of dicts."""
        formats_data = _make_formats_data([
            ("first_name", "10", "' '", "-1"),
            ("last_name", "20", "'*'", "1"),
        ])
        node = _make_node(params={"FORMATS": formats_data})
        result = ExtractPositionalFieldsConverter().convert(node, [], {})
        formats = result.component["config"]["formats"]
        assert len(formats) == 2
        assert formats[0] == {"column": "first_name", "size": "10", "padding_char": " ", "align": "left"}
        assert formats[1] == {"column": "last_name", "size": "20", "padding_char": "*", "align": "right"}

    def test_formats_align_center(self):
        """ALIGN value '0' maps to 'center'."""
        formats_data = _make_formats_data([("middle", "15", "' '", "0")])
        node = _make_node(params={"FORMATS": formats_data})
        result = ExtractPositionalFieldsConverter().convert(node, [], {})
        assert result.component["config"]["formats"][0]["align"] == "center"

    def test_formats_incomplete_stride_skipped(self):
        """Incomplete trailing group (< 4 entries) is skipped."""
        formats_data = _make_formats_data([("col_a", "10", "' '", "-1")])
        # Add incomplete trailing group (only 2 of 4)
        formats_data.append({"elementRef": "COLUMN", "value": "col_b"})
        formats_data.append({"elementRef": "SIZE", "value": "5"})
        node = _make_node(params={"FORMATS": formats_data})
        result = ExtractPositionalFieldsConverter().convert(node, [], {})
        formats = result.component["config"]["formats"]
        assert len(formats) == 1
        assert formats[0]["column"] == "col_a"


class TestFrameworkParams:
    """Verify tstatcatcher_stats and label extraction."""

    def test_tstatcatcher_stats_default_false(self):
        node = _make_node()
        result = ExtractPositionalFieldsConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is False

    def test_tstatcatcher_stats_true(self):
        node = _make_node(params={"TSTATCATCHER_STATS": "true"})
        result = ExtractPositionalFieldsConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is True

    def test_label_default_empty(self):
        node = _make_node()
        result = ExtractPositionalFieldsConverter().convert(node, [], {})
        assert result.component["config"]["label"] == ""

    def test_label_extracted(self):
        node = _make_node(params={"LABEL": '"my_label"'})
        result = ExtractPositionalFieldsConverter().convert(node, [], {})
        assert result.component["config"]["label"] == "my_label"


class TestSchema:
    """Verify schema extraction."""

    def test_schema_passthrough(self):
        """Both input and output schema must match FLOW schema (transform passthrough)."""
        node = _make_node(schema=_make_schema_columns())
        result = ExtractPositionalFieldsConverter().convert(node, [], {})
        schema = result.component["schema"]
        assert schema["input"] == schema["output"]
        assert len(schema["output"]) == 2
        assert schema["output"][0]["name"] == "id"
        assert schema["output"][1]["name"] == "name"


class TestNeedsReview:
    """Verify needs_review entries for engine gaps."""

    def test_needs_review_has_entries(self):
        """needs_review has 6 entries: 1 pattern default mismatch + 5 engine-unread keys."""
        node = _make_node()
        result = ExtractPositionalFieldsConverter().convert(node, [], {})
        assert len(result.needs_review) == 6

    def test_needs_review_engine_gap_severity(self):
        node = _make_node()
        result = ExtractPositionalFieldsConverter().convert(node, [], {})
        for entry in result.needs_review:
            assert entry["severity"] == "engine_gap"

    def test_needs_review_has_component_id(self):
        node = _make_node(component_id="test_comp")
        result = ExtractPositionalFieldsConverter().convert(node, [], {})
        for entry in result.needs_review:
            assert entry["component"] == "test_comp"

    def test_no_framework_param_needs_review(self):
        """Framework params (tstatcatcher_stats, label) must NOT have needs_review."""
        node = _make_node()
        result = ExtractPositionalFieldsConverter().convert(node, [], {})
        issues = [e["issue"] for e in result.needs_review]
        for issue in issues:
            assert "tstatcatcher_stats" not in issue
            assert "label" not in issue.lower().split()

    def test_pattern_default_mismatch_entry(self):
        """Pattern default mismatch entry exists."""
        node = _make_node()
        result = ExtractPositionalFieldsConverter().convert(node, [], {})
        pattern_entries = [nr for nr in result.needs_review if "pattern" in nr["issue"].lower()]
        assert len(pattern_entries) == 1

    def test_engine_unread_keys(self):
        """5 keys not read by engine are documented."""
        node = _make_node()
        result = ExtractPositionalFieldsConverter().convert(node, [], {})
        unread_entries = [nr for nr in result.needs_review if "does not read" in nr["issue"].lower()]
        assert len(unread_entries) == 5


class TestCompleteness:
    """Verify all expected config keys are present."""

    def test_all_config_keys_present(self):
        """Config dict has exactly 13 keys: 11 unique + 2 framework."""
        node = _make_node(schema=_make_schema_columns())
        result = ExtractPositionalFieldsConverter().convert(node, [], {})
        expected_keys = {
            "field", "ignore_source_null", "advanced_option", "pattern",
            "formats", "die_on_error", "advanced_separator",
            "thousands_separator", "decimal_separator", "trim",
            "check_fields_num", "tstatcatcher_stats", "label",
        }
        actual_keys = set(result.component["config"].keys())
        missing = expected_keys - actual_keys
        assert not missing, f"Missing config keys: {missing}"
        assert len(result.component["config"]) == 13


class TestComponentStructure:
    """Verify the component dict structure from _build_component_dict."""

    def test_has_type(self):
        node = _make_node()
        result = ExtractPositionalFieldsConverter().convert(node, [], {})
        assert result.component["type"] == "ExtractPositionalFields"

    def test_has_original_type(self):
        node = _make_node()
        result = ExtractPositionalFieldsConverter().convert(node, [], {})
        assert result.component["original_type"] == "tExtractPositionalFields"

    def test_has_id(self):
        node = _make_node(component_id="epf_1")
        result = ExtractPositionalFieldsConverter().convert(node, [], {})
        assert result.component["id"] == "epf_1"

    def test_has_position(self):
        node = _make_node()
        result = ExtractPositionalFieldsConverter().convert(node, [], {})
        assert result.component["position"] == {"x": 100, "y": 200}

    def test_has_all_top_level_keys(self):
        node = _make_node()
        result = ExtractPositionalFieldsConverter().convert(node, [], {})
        expected_keys = {"id", "type", "original_type", "position", "config", "schema", "inputs", "outputs"}
        assert set(result.component.keys()) == expected_keys

    def test_inputs_outputs_empty(self):
        node = _make_node()
        result = ExtractPositionalFieldsConverter().convert(node, [], {})
        assert result.component["inputs"] == []
        assert result.component["outputs"] == []

    def test_result_is_component_result(self):
        node = _make_node()
        result = ExtractPositionalFieldsConverter().convert(node, [], {})
        assert isinstance(result, ComponentResult)


class TestWarnings:
    """Verify warning generation."""

    def test_empty_pattern_warning(self):
        """An empty PATTERN produces a warning."""
        node = _make_node(params={"PATTERN": '""'})
        result = ExtractPositionalFieldsConverter().convert(node, [], {})
        assert any("PATTERN" in w for w in result.warnings)
        assert result.component["config"]["pattern"] == ""

    def test_no_warning_with_valid_pattern(self):
        """No warnings when a valid pattern is provided."""
        node = _make_node(params={"PATTERN": '"10,20,15"'})
        result = ExtractPositionalFieldsConverter().convert(node, [], {})
        assert not result.warnings

    def test_no_warning_when_pattern_defaults(self):
        """With empty params (pattern defaults to '5,4,5'), no PATTERN warning."""
        node = _make_node()
        result = ExtractPositionalFieldsConverter().convert(node, [], {})
        assert not any("PATTERN" in w for w in result.warnings)
