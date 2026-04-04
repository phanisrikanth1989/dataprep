"""Tests for UnpivotRowConverter (tUnpivotRow -> v1 UnpivotRow config)."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.transform.unpivot_row import (
    UnpivotRowConverter,
)
from src.converters.talend_to_v1.components.registry import REGISTRY


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

def _make_node(params=None, schema=None, component_id="upvt_1",
               component_type="tUnpivotRow"):
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
            SchemaColumn(name="amount", type="id_Double", nullable=True),
        ]
    }


def _make_row_keys_table(columns):
    """Generate ROW_KEYS TABLE data with stride-1 (COLUMN elementRef).

    columns: list of column name strings
    """
    result = []
    for col in columns:
        result.append({"elementRef": "COLUMN", "value": f'"{col}"'})
    return result


# ------------------------------------------------------------------
# Test Classes
# ------------------------------------------------------------------


class TestRegistration:
    """Verify component is registered correctly."""

    def test_registered_in_registry(self):
        assert REGISTRY.get("tUnpivotRow") is UnpivotRowConverter


class TestDefaults:
    """Verify all parameters have correct defaults when no params provided."""

    def test_row_keys_default_empty(self):
        node = _make_node()
        result = UnpivotRowConverter().convert(node, [], {})
        assert result.component["config"]["row_keys"] == []

    def test_pivot_key_default(self):
        node = _make_node()
        result = UnpivotRowConverter().convert(node, [], {})
        assert result.component["config"]["pivot_key"] == "pivot_key"

    def test_pivot_value_default(self):
        node = _make_node()
        result = UnpivotRowConverter().convert(node, [], {})
        assert result.component["config"]["pivot_value"] == "pivot_value"

    def test_include_empty_values_default_true(self):
        node = _make_node()
        result = UnpivotRowConverter().convert(node, [], {})
        assert result.component["config"]["include_empty_values"] is True

    def test_tstatcatcher_stats_default_false(self):
        node = _make_node()
        result = UnpivotRowConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is False

    def test_label_default_empty(self):
        node = _make_node()
        result = UnpivotRowConverter().convert(node, [], {})
        assert result.component["config"]["label"] == ""


class TestParameterExtraction:
    """Verify each parameter is correctly extracted from XML params."""

    def test_row_keys_parsing(self):
        """ROW_KEYS TABLE with 3 entries parses correctly."""
        table = _make_row_keys_table(["col1", "col2", "col3"])
        node = _make_node(params={"ROW_KEYS": table})
        result = UnpivotRowConverter().convert(node, [], {})
        assert result.component["config"]["row_keys"] == ["col1", "col2", "col3"]

    def test_include_empty_values_false(self):
        """INCLUDE_EMPTY_VALUES='false' -> False."""
        node = _make_node(params={"INCLUDE_EMPTY_VALUES": "false"})
        result = UnpivotRowConverter().convert(node, [], {})
        assert result.component["config"]["include_empty_values"] is False

    def test_row_keys_filters_empty_values(self):
        """Empty-string COLUMN entries should be skipped."""
        table = [
            {"elementRef": "COLUMN", "value": '"key1"'},
            {"elementRef": "COLUMN", "value": '""'},
            {"elementRef": "COLUMN", "value": '"key2"'},
        ]
        node = _make_node(params={"ROW_KEYS": table})
        result = UnpivotRowConverter().convert(node, [], {})
        assert result.component["config"]["row_keys"] == ["key1", "key2"]

    def test_row_keys_ignores_non_column_refs(self):
        """Entries with elementRef != 'COLUMN' should be ignored."""
        table = [
            {"elementRef": "COLUMN", "value": '"keep_me"'},
            {"elementRef": "OTHER", "value": '"ignore_me"'},
            {"elementRef": "COLUMN", "value": '"also_keep"'},
        ]
        node = _make_node(params={"ROW_KEYS": table})
        result = UnpivotRowConverter().convert(node, [], {})
        assert result.component["config"]["row_keys"] == ["keep_me", "also_keep"]

    def test_row_keys_not_a_list_warns(self):
        """If ROW_KEYS is not a list, produce a warning and return empty."""
        node = _make_node(params={"ROW_KEYS": "bad_data"})
        result = UnpivotRowConverter().convert(node, [], {})
        assert result.component["config"]["row_keys"] == []
        assert any("not a list" in w for w in result.warnings)


class TestFrameworkParams:
    """Verify tstatcatcher_stats and label extraction."""

    def test_tstatcatcher_stats_true(self):
        node = _make_node(params={"TSTATCATCHER_STATS": "true"})
        result = UnpivotRowConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is True

    def test_label_extracted(self):
        node = _make_node(params={"LABEL": '"my_label"'})
        result = UnpivotRowConverter().convert(node, [], {})
        assert result.component["config"]["label"] == "my_label"


class TestSchema:
    """Verify schema extraction."""

    def test_schema_passthrough(self):
        """Transform component: input == output."""
        node = _make_node(schema=_make_schema_columns())
        result = UnpivotRowConverter().convert(node, [], {})
        schema = result.component["schema"]
        assert schema["input"] == schema["output"]
        assert len(schema["input"]) == 3
        assert schema["input"][0]["name"] == "id"

    def test_empty_schema(self):
        """When no FLOW schema is present, input and output are empty lists."""
        node = _make_node()
        result = UnpivotRowConverter().convert(node, [], {})
        schema = result.component["schema"]
        assert schema == {"input": [], "output": []}


class TestNeedsReview:
    """Verify needs_review entries -- 0 for tUnpivotRow (engine matches)."""

    def test_needs_review_empty(self):
        """needs_review must be empty -- engine reads all config params."""
        node = _make_node()
        result = UnpivotRowConverter().convert(node, [], {})
        assert len(result.needs_review) == 0

    def test_no_framework_param_needs_review(self):
        """Framework params (tstatcatcher_stats, label) must NOT have needs_review."""
        node = _make_node()
        result = UnpivotRowConverter().convert(node, [], {})
        issues = [e["issue"] for e in result.needs_review]
        for issue in issues:
            assert "tstatcatcher_stats" not in issue
            assert "label" not in issue.lower().split()


class TestCompleteness:
    """Verify all expected config keys are present."""

    def test_all_config_keys_present(self):
        """Config dict has exactly 6 keys: 4 unique + 2 framework."""
        node = _make_node(schema=_make_schema_columns())
        result = UnpivotRowConverter().convert(node, [], {})
        expected_keys = {
            "row_keys", "pivot_key", "pivot_value",
            "include_empty_values",
            "tstatcatcher_stats", "label",
        }
        actual_keys = set(result.component["config"].keys())
        missing = expected_keys - actual_keys
        assert not missing, f"Missing config keys: {missing}"
        extra = actual_keys - expected_keys
        assert not extra, f"Extra config keys: {extra}"


class TestComponentStructure:
    """Verify _build_component_dict output structure."""

    def test_has_type(self):
        node = _make_node()
        result = UnpivotRowConverter().convert(node, [], {})
        assert result.component["type"] == "UnpivotRow"

    def test_has_original_type(self):
        node = _make_node()
        result = UnpivotRowConverter().convert(node, [], {})
        assert result.component["original_type"] == "tUnpivotRow"

    def test_has_id(self):
        node = _make_node(component_id="upvt_1")
        result = UnpivotRowConverter().convert(node, [], {})
        assert result.component["id"] == "upvt_1"

    def test_has_position(self):
        node = _make_node()
        result = UnpivotRowConverter().convert(node, [], {})
        assert result.component["position"] == {"x": 100, "y": 200}

    def test_has_inputs_outputs(self):
        node = _make_node()
        result = UnpivotRowConverter().convert(node, [], {})
        assert result.component["inputs"] == []
        assert result.component["outputs"] == []


class TestPhantomParams:
    """Verify params NOT in _java.xml are NOT extracted."""

    def test_no_pivot_column_in_config(self):
        """PIVOT_COLUMN is phantom -- must not appear in config."""
        node = _make_node(params={"PIVOT_COLUMN": '"col_name"'})
        result = UnpivotRowConverter().convert(node, [], {})
        assert "pivot_column" not in result.component["config"]

    def test_no_value_column_in_config(self):
        """VALUE_COLUMN is phantom -- must not appear in config."""
        node = _make_node(params={"VALUE_COLUMN": '"val_col"'})
        result = UnpivotRowConverter().convert(node, [], {})
        assert "value_column" not in result.component["config"]

    def test_no_group_by_columns_in_config(self):
        """GROUP_BY_COLUMNS is phantom -- must not appear in config."""
        node = _make_node(params={"GROUP_BY_COLUMNS": "some_val"})
        result = UnpivotRowConverter().convert(node, [], {})
        assert "group_by_columns" not in result.component["config"]

    def test_no_die_on_error_in_config(self):
        """DIE_ON_ERROR is phantom -- must not appear in config."""
        node = _make_node(params={"DIE_ON_ERROR": "true"})
        result = UnpivotRowConverter().convert(node, [], {})
        assert "die_on_error" not in result.component["config"]
