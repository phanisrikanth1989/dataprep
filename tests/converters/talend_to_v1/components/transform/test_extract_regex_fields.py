"""Tests for ExtractRegexFieldsConverter (tExtractRegexFields -> v1 tExtractRegexFields config)."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.transform.extract_regex_fields import (
    ExtractRegexFieldsConverter,
)
from src.converters.talend_to_v1.components.registry import REGISTRY


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

def _make_node(params=None, schema=None, component_id="erf_1",
               component_type="tExtractRegexFields"):
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
        assert REGISTRY.get("tExtractRegexFields") is ExtractRegexFieldsConverter


class TestDefaults:
    """Verify all parameters have correct defaults when no params provided."""

    def test_field_default_empty(self):
        """FIELD default is '' (empty string)."""
        node = _make_node()
        result = ExtractRegexFieldsConverter().convert(node, [], {})
        assert result.component["config"]["field"] == ""

    def test_regex_default(self):
        """REGEX default is '' (empty string when not specified)."""
        node = _make_node()
        result = ExtractRegexFieldsConverter().convert(node, [], {})
        assert result.component["config"]["regex"] == ""

    def test_die_on_error_default_true(self):
        """DIE_ON_ERROR default is True per _java.xml (FIXED from False)."""
        node = _make_node()
        result = ExtractRegexFieldsConverter().convert(node, [], {})
        assert result.component["config"]["die_on_error"] is True

    def test_check_fields_num_default_false(self):
        """CHECK_FIELDS_NUM default is False per _java.xml."""
        node = _make_node()
        result = ExtractRegexFieldsConverter().convert(node, [], {})
        assert result.component["config"]["check_fields_num"] is False

    def test_tstatcatcher_stats_default_false(self):
        node = _make_node()
        result = ExtractRegexFieldsConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is False

    def test_label_default_empty(self):
        node = _make_node()
        result = ExtractRegexFieldsConverter().convert(node, [], {})
        assert result.component["config"]["label"] == ""


class TestParameterExtraction:
    """Verify each parameter is correctly extracted from XML params."""

    def test_field_custom(self):
        """FIELD='"source_col"' -> 'source_col'."""
        node = _make_node(params={"FIELD": '"source_col"'})
        result = ExtractRegexFieldsConverter().convert(node, [], {})
        assert result.component["config"]["field"] == "source_col"

    def test_regex_custom(self):
        """REGEX='"^(\\w+)$"' -> '^(\\w+)$'."""
        node = _make_node(params={"REGEX": '"^(\\\\w+)$"'})
        result = ExtractRegexFieldsConverter().convert(node, [], {})
        assert result.component["config"]["regex"] == "^(\\\\w+)$"

    def test_die_on_error_false(self):
        """DIE_ON_ERROR='false' -> False."""
        node = _make_node(params={"DIE_ON_ERROR": "false"})
        result = ExtractRegexFieldsConverter().convert(node, [], {})
        assert result.component["config"]["die_on_error"] is False

    def test_check_fields_num_true(self):
        """CHECK_FIELDS_NUM='true' -> True."""
        node = _make_node(params={"CHECK_FIELDS_NUM": "true"})
        result = ExtractRegexFieldsConverter().convert(node, [], {})
        assert result.component["config"]["check_fields_num"] is True


class TestFrameworkParams:
    """Verify tstatcatcher_stats and label extraction."""

    def test_tstatcatcher_stats_true(self):
        node = _make_node(params={"TSTATCATCHER_STATS": "true"})
        result = ExtractRegexFieldsConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is True

    def test_label_extracted(self):
        node = _make_node(params={"LABEL": '"my_label"'})
        result = ExtractRegexFieldsConverter().convert(node, [], {})
        assert result.component["config"]["label"] == "my_label"


class TestSchema:
    """Verify schema extraction (passthrough: input == output)."""

    def test_schema_passthrough(self):
        """tExtractRegexFields is passthrough: input schema == output schema."""
        node = _make_node(schema=_make_schema_columns())
        result = ExtractRegexFieldsConverter().convert(node, [], {})
        schema = result.component["schema"]
        assert schema["input"] == schema["output"]

    def test_schema_columns_populated(self):
        """Schema columns are extracted from FLOW schema."""
        node = _make_node(schema=_make_schema_columns())
        result = ExtractRegexFieldsConverter().convert(node, [], {})
        cols = result.component["schema"]["input"]
        assert len(cols) == 2
        assert cols[0]["name"] == "id"
        assert cols[1]["name"] == "name"


class TestNeedsReview:
    """Verify needs_review entries for engine gaps."""

    def test_needs_review_count(self):
        """Single consolidated needs_review per D-27 (no engine)."""
        node = _make_node()
        result = ExtractRegexFieldsConverter().convert(node, [], {})
        assert len(result.needs_review) == 1

    def test_needs_review_engine_gap(self):
        node = _make_node()
        result = ExtractRegexFieldsConverter().convert(node, [], {})
        assert result.needs_review[0]["severity"] == "engine_gap"

    def test_needs_review_no_engine(self):
        node = _make_node()
        result = ExtractRegexFieldsConverter().convert(node, [], {})
        assert "No v1 engine implementation" in result.needs_review[0]["issue"]

    def test_needs_review_has_component_id(self):
        node = _make_node(component_id="test_comp")
        result = ExtractRegexFieldsConverter().convert(node, [], {})
        assert result.needs_review[0]["component"] == "test_comp"

    def test_no_framework_param_needs_review(self):
        """Framework params (tstatcatcher_stats, label) must NOT have needs_review."""
        node = _make_node()
        result = ExtractRegexFieldsConverter().convert(node, [], {})
        issues = [e["issue"] for e in result.needs_review]
        for issue in issues:
            assert "tstatcatcher_stats" not in issue
            assert "label" not in issue.lower().split()


class TestPhantomParams:
    """Verify params NOT in _java.xml are NOT extracted."""

    def test_group_not_in_config(self):
        """GROUP is phantom -- NOT in _java.xml, must not appear in config."""
        node = _make_node(params={"GROUP": "1"})
        result = ExtractRegexFieldsConverter().convert(node, [], {})
        assert "group" not in result.component["config"]


class TestCompleteness:
    """Verify all expected config keys are present."""

    def test_all_config_keys_present(self):
        """Config should have 4 unique + 2 framework = 6 keys."""
        node = _make_node(schema=_make_schema_columns())
        result = ExtractRegexFieldsConverter().convert(node, [], {})
        expected_keys = {
            "field", "regex", "die_on_error", "check_fields_num",
            "tstatcatcher_stats", "label",
        }
        actual_config_keys = set(result.component["config"].keys())
        missing = expected_keys - actual_config_keys
        assert not missing, f"Missing config keys: {missing}"


class TestComponentStructure:
    """Verify component wrapper structure."""

    def test_has_type(self):
        """No-engine: type_name='tExtractRegexFields' per D-43."""
        node = _make_node()
        result = ExtractRegexFieldsConverter().convert(node, [], {})
        assert result.component["type"] == "tExtractRegexFields"

    def test_has_original_type(self):
        node = _make_node()
        result = ExtractRegexFieldsConverter().convert(node, [], {})
        assert result.component["original_type"] == "tExtractRegexFields"
