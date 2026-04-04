"""Tests for ExtractDelimitedFieldsConverter (tExtractDelimitedFields -> v1 ExtractDelimitedFields config)."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.transform.extract_delimited_fields import (
    ExtractDelimitedFieldsConverter,
)
from src.converters.talend_to_v1.components.registry import REGISTRY


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


def _make_node(params=None, schema=None, component_id="edf_1",
               component_type="tExtractDelimitedFields"):
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
# Test Classes
# ------------------------------------------------------------------


class TestRegistration:
    """Verify component is registered correctly."""

    def test_registered_in_registry(self):
        assert REGISTRY.get("tExtractDelimitedFields") is ExtractDelimitedFieldsConverter


class TestDefaults:
    """Verify all parameters have correct defaults when no params provided."""

    def test_field_default_empty(self):
        node = _make_node()
        result = ExtractDelimitedFieldsConverter().convert(node, [], {})
        assert result.component["config"]["field"] == ""

    def test_ignore_source_null_default_true(self):
        node = _make_node()
        result = ExtractDelimitedFieldsConverter().convert(node, [], {})
        assert result.component["config"]["ignore_source_null"] is True

    def test_fieldseparator_default(self):
        node = _make_node()
        result = ExtractDelimitedFieldsConverter().convert(node, [], {})
        assert result.component["config"]["fieldseparator"] == ";"

    def test_die_on_error_default_false(self):
        node = _make_node()
        result = ExtractDelimitedFieldsConverter().convert(node, [], {})
        assert result.component["config"]["die_on_error"] is False

    def test_advanced_separator_default_false(self):
        node = _make_node()
        result = ExtractDelimitedFieldsConverter().convert(node, [], {})
        assert result.component["config"]["advanced_separator"] is False

    def test_thousands_separator_default(self):
        node = _make_node()
        result = ExtractDelimitedFieldsConverter().convert(node, [], {})
        assert result.component["config"]["thousands_separator"] == ","

    def test_decimal_separator_default(self):
        node = _make_node()
        result = ExtractDelimitedFieldsConverter().convert(node, [], {})
        assert result.component["config"]["decimal_separator"] == "."

    def test_trim_default_false(self):
        node = _make_node()
        result = ExtractDelimitedFieldsConverter().convert(node, [], {})
        assert result.component["config"]["trim"] is False

    def test_check_fields_num_default_false(self):
        node = _make_node()
        result = ExtractDelimitedFieldsConverter().convert(node, [], {})
        assert result.component["config"]["check_fields_num"] is False

    def test_check_date_default_false(self):
        node = _make_node()
        result = ExtractDelimitedFieldsConverter().convert(node, [], {})
        assert result.component["config"]["check_date"] is False

    def test_schema_opt_num_default(self):
        node = _make_node()
        result = ExtractDelimitedFieldsConverter().convert(node, [], {})
        assert result.component["config"]["schema_opt_num"] == "100"

    def test_tstatcatcher_stats_default_false(self):
        node = _make_node()
        result = ExtractDelimitedFieldsConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is False

    def test_label_default_empty(self):
        node = _make_node()
        result = ExtractDelimitedFieldsConverter().convert(node, [], {})
        assert result.component["config"]["label"] == ""


class TestParameterExtraction:
    """Verify each parameter is correctly extracted from XML params."""

    def test_field_custom(self):
        node = _make_node(params={"FIELD": '"column1"'})
        result = ExtractDelimitedFieldsConverter().convert(node, [], {})
        assert result.component["config"]["field"] == "column1"

    def test_fieldseparator_custom(self):
        node = _make_node(params={"FIELDSEPARATOR": '","'})
        result = ExtractDelimitedFieldsConverter().convert(node, [], {})
        assert result.component["config"]["fieldseparator"] == ","

    def test_schema_opt_num_custom(self):
        node = _make_node(params={"SCHEMA_OPT_NUM": '"50"'})
        result = ExtractDelimitedFieldsConverter().convert(node, [], {})
        assert result.component["config"]["schema_opt_num"] == "50"

    def test_ignore_source_null_false(self):
        node = _make_node(params={"IGNORE_SOURCE_NULL": "false"})
        result = ExtractDelimitedFieldsConverter().convert(node, [], {})
        assert result.component["config"]["ignore_source_null"] is False

    def test_die_on_error_true(self):
        node = _make_node(params={"DIE_ON_ERROR": "true"})
        result = ExtractDelimitedFieldsConverter().convert(node, [], {})
        assert result.component["config"]["die_on_error"] is True

    def test_advanced_separator_true(self):
        node = _make_node(params={"ADVANCED_SEPARATOR": "true"})
        result = ExtractDelimitedFieldsConverter().convert(node, [], {})
        assert result.component["config"]["advanced_separator"] is True

    def test_thousands_separator_custom(self):
        node = _make_node(params={"THOUSANDS_SEPARATOR": '"."'})
        result = ExtractDelimitedFieldsConverter().convert(node, [], {})
        assert result.component["config"]["thousands_separator"] == "."

    def test_decimal_separator_custom(self):
        node = _make_node(params={"DECIMAL_SEPARATOR": '","'})
        result = ExtractDelimitedFieldsConverter().convert(node, [], {})
        assert result.component["config"]["decimal_separator"] == ","

    def test_trim_true(self):
        node = _make_node(params={"TRIM": "true"})
        result = ExtractDelimitedFieldsConverter().convert(node, [], {})
        assert result.component["config"]["trim"] is True

    def test_check_fields_num_true(self):
        node = _make_node(params={"CHECK_FIELDS_NUM": "true"})
        result = ExtractDelimitedFieldsConverter().convert(node, [], {})
        assert result.component["config"]["check_fields_num"] is True

    def test_check_date_true(self):
        node = _make_node(params={"CHECK_DATE": "true"})
        result = ExtractDelimitedFieldsConverter().convert(node, [], {})
        assert result.component["config"]["check_date"] is True

    def test_pipe_separator(self):
        """Pipe character as field separator is handled correctly."""
        node = _make_node(params={"FIELDSEPARATOR": '"|"'})
        result = ExtractDelimitedFieldsConverter().convert(node, [], {})
        assert result.component["config"]["fieldseparator"] == "|"


class TestFrameworkParams:
    """Verify tstatcatcher_stats and label extraction."""

    def test_tstatcatcher_stats_true(self):
        node = _make_node(params={"TSTATCATCHER_STATS": "true"})
        result = ExtractDelimitedFieldsConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is True

    def test_label_extracted(self):
        node = _make_node(params={"LABEL": '"my_label"'})
        result = ExtractDelimitedFieldsConverter().convert(node, [], {})
        assert result.component["config"]["label"] == "my_label"


class TestSchema:
    """Verify schema passthrough for transform component."""

    def test_schema_passthrough(self):
        """Both input and output schema must match FLOW schema."""
        node = _make_node(
            schema=_make_schema_columns(),
        )
        result = ExtractDelimitedFieldsConverter().convert(node, [], {})
        schema = result.component["schema"]
        assert schema["input"] == schema["output"]
        assert len(schema["output"]) == 2
        assert schema["output"][0]["name"] == "id"
        assert schema["output"][1]["name"] == "name"


class TestNeedsReview:
    """Verify needs_review entries for engine gaps."""

    def test_needs_review_has_entries(self):
        node = _make_node()
        result = ExtractDelimitedFieldsConverter().convert(node, [], {})
        assert len(result.needs_review) >= 1

    def test_needs_review_engine_gap_severity(self):
        node = _make_node()
        result = ExtractDelimitedFieldsConverter().convert(node, [], {})
        for entry in result.needs_review:
            assert entry["severity"] == "engine_gap"

    def test_needs_review_has_component_id(self):
        node = _make_node(component_id="test_comp")
        result = ExtractDelimitedFieldsConverter().convert(node, [], {})
        for entry in result.needs_review:
            assert entry["component"] == "test_comp"

    def test_no_framework_param_needs_review(self):
        """Framework params (tstatcatcher_stats, label) must NOT have needs_review."""
        node = _make_node()
        result = ExtractDelimitedFieldsConverter().convert(node, [], {})
        issues = [e["issue"] for e in result.needs_review]
        for issue in issues:
            assert "tstatcatcher_stats" not in issue
            assert "label" not in issue.lower().split()


class TestCompleteness:
    """Verify all expected config keys are present."""

    def test_all_config_keys_present(self):
        """Config must have 11 unique + 2 framework = 13 config keys."""
        node = _make_node(schema=_make_schema_columns())
        result = ExtractDelimitedFieldsConverter().convert(node, [], {})
        expected_keys = {
            "field", "ignore_source_null", "fieldseparator", "die_on_error",
            "advanced_separator", "thousands_separator", "decimal_separator",
            "trim", "check_fields_num", "check_date", "schema_opt_num",
            "tstatcatcher_stats", "label",
        }
        actual_keys = set(result.component["config"].keys())
        missing = expected_keys - actual_keys
        assert not missing, f"Missing config keys: {missing}"
        assert len(result.component["config"]) == 13


class TestComponentStructure:
    """Verify component wrapper structure."""

    def test_has_type(self):
        node = _make_node()
        result = ExtractDelimitedFieldsConverter().convert(node, [], {})
        assert result.component["type"] == "ExtractDelimitedFields"

    def test_has_original_type(self):
        node = _make_node()
        result = ExtractDelimitedFieldsConverter().convert(node, [], {})
        assert result.component["original_type"] == "tExtractDelimitedFields"

    def test_has_id(self):
        node = _make_node(component_id="edf_1")
        result = ExtractDelimitedFieldsConverter().convert(node, [], {})
        assert result.component["id"] == "edf_1"

    def test_wrapper_keys(self):
        node = _make_node()
        result = ExtractDelimitedFieldsConverter().convert(node, [], {})
        expected_keys = {"id", "type", "original_type", "position", "config", "schema", "inputs", "outputs"}
        assert set(result.component.keys()) == expected_keys

    def test_result_type(self):
        node = _make_node()
        result = ExtractDelimitedFieldsConverter().convert(node, [], {})
        assert isinstance(result, ComponentResult)


class TestPhantomParams:
    """Verify params NOT in _java.xml are NOT extracted."""

    def test_rowseparator_not_in_config(self):
        node = _make_node(params={"ROWSEPARATOR": '"\\n"'})
        result = ExtractDelimitedFieldsConverter().convert(node, [], {})
        assert "row_separator" not in result.component["config"]
        assert "rowseparator" not in result.component["config"]

    def test_remove_empty_row_not_in_config(self):
        node = _make_node(params={"REMOVE_EMPTY_ROW": "true"})
        result = ExtractDelimitedFieldsConverter().convert(node, [], {})
        assert "remove_empty_row" not in result.component["config"]

    def test_trimall_not_in_config(self):
        node = _make_node(params={"TRIMALL": "true"})
        result = ExtractDelimitedFieldsConverter().convert(node, [], {})
        assert "trim_all" not in result.component["config"]
        assert "trimall" not in result.component["config"]
