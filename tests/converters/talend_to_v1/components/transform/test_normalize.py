"""Tests for NormalizeConverter (tNormalize -> v1 Normalize config)."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendNode,
)
from src.converters.talend_to_v1.components.registry import REGISTRY
from src.converters.talend_to_v1.components.transform.normalize import (
    NormalizeConverter,
)


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


def _make_node(params=None, schema=None, component_id="norm_1",
               component_type="tNormalize"):
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
            SchemaColumn(name="items", type="id_String", nullable=True, length=100),
        ]
    }


# ------------------------------------------------------------------
# Test Classes (one per concern)
# ------------------------------------------------------------------


class TestRegistration:
    """Verify component is registered correctly."""

    def test_registered_in_registry(self):
        assert REGISTRY.get("tNormalize") is NormalizeConverter


class TestDefaults:
    """Verify all parameters have correct defaults when no params provided."""

    def test_normalize_column_default_empty(self):
        node = _make_node()
        result = NormalizeConverter().convert(node, [], {})
        assert result.component["config"]["normalize_column"] == ""

    def test_itemseparator_default_comma(self):
        node = _make_node()
        result = NormalizeConverter().convert(node, [], {})
        assert result.component["config"]["itemseparator"] == ","

    def test_deduplicate_default_false(self):
        node = _make_node()
        result = NormalizeConverter().convert(node, [], {})
        assert result.component["config"]["deduplicate"] is False

    def test_csv_option_default_false(self):
        node = _make_node()
        result = NormalizeConverter().convert(node, [], {})
        assert result.component["config"]["csv_option"] is False

    def test_escape_char_default(self):
        node = _make_node()
        result = NormalizeConverter().convert(node, [], {})
        assert result.component["config"]["escape_char"] == "ESCAPE_MODE_DOUBLED"

    def test_text_enclosure_default(self):
        node = _make_node()
        result = NormalizeConverter().convert(node, [], {})
        assert result.component["config"]["text_enclosure"] == '"'

    def test_discard_trailing_empty_str_default_false(self):
        node = _make_node()
        result = NormalizeConverter().convert(node, [], {})
        assert result.component["config"]["discard_trailing_empty_str"] is False

    def test_trim_default_false(self):
        node = _make_node()
        result = NormalizeConverter().convert(node, [], {})
        assert result.component["config"]["trim"] is False

    def test_tstatcatcher_stats_default_false(self):
        node = _make_node()
        result = NormalizeConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is False

    def test_label_default_empty(self):
        node = _make_node()
        result = NormalizeConverter().convert(node, [], {})
        assert result.component["config"]["label"] == ""


class TestParameterExtraction:
    """Verify each parameter is correctly extracted from XML params."""

    def test_normalize_column_custom(self):
        node = _make_node(params={"NORMALIZE_COLUMN": '"col1"'})
        result = NormalizeConverter().convert(node, [], {})
        assert result.component["config"]["normalize_column"] == "col1"

    def test_itemseparator_custom(self):
        node = _make_node(params={"ITEMSEPARATOR": '";"'})
        result = NormalizeConverter().convert(node, [], {})
        assert result.component["config"]["itemseparator"] == ";"

    def test_csv_option_true(self):
        node = _make_node(params={"CSV_OPTION": "true"})
        result = NormalizeConverter().convert(node, [], {})
        assert result.component["config"]["csv_option"] is True

    def test_escape_char_backslash(self):
        node = _make_node(params={"ESCAPE_CHAR": '"ESCAPE_MODE_BACKSLASH"'})
        result = NormalizeConverter().convert(node, [], {})
        assert result.component["config"]["escape_char"] == "ESCAPE_MODE_BACKSLASH"

    def test_text_enclosure_custom(self):
        node = _make_node(params={"TEXT_ENCLOSURE": '"\'"'})
        result = NormalizeConverter().convert(node, [], {})
        assert result.component["config"]["text_enclosure"] == "'"


class TestFrameworkParams:
    """Verify tstatcatcher_stats and label extraction."""

    def test_tstatcatcher_stats_true(self):
        node = _make_node(params={"TSTATCATCHER_STATS": "true"})
        result = NormalizeConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is True

    def test_label_extracted(self):
        node = _make_node(params={"LABEL": '"my_label"'})
        result = NormalizeConverter().convert(node, [], {})
        assert result.component["config"]["label"] == "my_label"


class TestSchema:
    """Verify schema extraction."""

    def test_schema_passthrough(self):
        """Normalize passes through schema: both input and output match."""
        node = _make_node(schema=_make_schema_columns())
        result = NormalizeConverter().convert(node, [], {})
        schema = result.component["schema"]
        assert schema["input"] == schema["output"]

    def test_schema_columns_populated(self):
        """Schema columns have correct structure."""
        node = _make_node(schema=_make_schema_columns())
        result = NormalizeConverter().convert(node, [], {})
        schema = result.component["schema"]
        assert len(schema["output"]) == 2
        assert schema["output"][0]["name"] == "id"
        assert schema["output"][0]["key"] is True
        assert schema["output"][0]["nullable"] is False
        assert schema["output"][1]["name"] == "items"
        assert schema["output"][1]["length"] == 100


class TestNeedsReview:
    """Verify needs_review entries for engine gaps."""

    def test_needs_review_has_entries(self):
        """Per-feature needs_review for engine gaps."""
        node = _make_node()
        result = NormalizeConverter().convert(node, [], {})
        assert len(result.needs_review) >= 1

    def test_needs_review_engine_gap_severity(self):
        """All needs_review entries have severity == 'engine_gap'."""
        node = _make_node()
        result = NormalizeConverter().convert(node, [], {})
        for entry in result.needs_review:
            assert entry["severity"] == "engine_gap"

    def test_needs_review_has_component_id(self):
        node = _make_node(component_id="test_comp")
        result = NormalizeConverter().convert(node, [], {})
        for entry in result.needs_review:
            assert entry["component"] == "test_comp"

    def test_no_framework_param_needs_review(self):
        """Framework params (tstatcatcher_stats, label) must NOT have needs_review."""
        node = _make_node()
        result = NormalizeConverter().convert(node, [], {})
        issues = [e["issue"] for e in result.needs_review]
        for issue in issues:
            assert "tstatcatcher_stats" not in issue
            assert "label" not in issue.lower().split()


class TestPhantomParams:
    """Verify params NOT in _java.xml are NOT extracted."""

    def test_die_on_error_not_in_config(self):
        """DIE_ON_ERROR is phantom (not in _java.xml) -- must NOT be in config."""
        node = _make_node(params={"DIE_ON_ERROR": "true"})
        result = NormalizeConverter().convert(node, [], {})
        assert "die_on_error" not in result.component["config"]


class TestCompleteness:
    """Verify all expected config keys are present."""

    def test_all_config_keys_present(self):
        """9 unique + 2 framework = 11 total config keys."""
        node = _make_node(schema=_make_schema_columns())
        result = NormalizeConverter().convert(node, [], {})
        expected_keys = {
            "normalize_column", "itemseparator", "deduplicate", "csv_option",
            "escape_char", "text_enclosure", "discard_trailing_empty_str", "trim",
            # framework
            "tstatcatcher_stats", "label",
        }
        actual_keys = set(result.component["config"].keys())
        missing = expected_keys - actual_keys
        extra = actual_keys - expected_keys
        assert not missing, f"Missing config keys: {missing}"
        assert not extra, f"Extra config keys: {extra}"


class TestComponentStructure:
    """Verify component dict structure."""

    def test_has_type(self):
        node = _make_node()
        result = NormalizeConverter().convert(node, [], {})
        assert result.component["type"] == "Normalize"

    def test_has_original_type(self):
        node = _make_node()
        result = NormalizeConverter().convert(node, [], {})
        assert result.component["original_type"] == "tNormalize"

    def test_result_type(self):
        node = _make_node()
        result = NormalizeConverter().convert(node, [], {})
        assert isinstance(result, ComponentResult)

    def test_component_dict_keys(self):
        node = _make_node()
        result = NormalizeConverter().convert(node, [], {})
        expected_keys = {"id", "type", "original_type", "position", "config", "schema", "inputs", "outputs"}
        assert set(result.component.keys()) == expected_keys
