"""Tests for SplitRowConverter (tSplitRow -> v1 tSplitRow config)."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.transform.split_row import (
    SplitRowConverter,
)
from src.converters.talend_to_v1.components.registry import REGISTRY


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


def _make_node(params=None, schema=None, component_id="sp_1",
               component_type="tSplitRow"):
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


def _make_col_mapping_table(*rows):
    """Generate COL_MAPPING TABLE data with stride-2 per row.

    rows: list of tuples (source_column, target_column)
    """
    result = []
    for source, target in rows:
        result.append({"elementRef": "SOURCE_COLUMN", "value": source})
        result.append({"elementRef": "TARGET_COLUMN", "value": target})
    return result


# ------------------------------------------------------------------
# Test Classes
# ------------------------------------------------------------------


class TestRegistration:
    """Verify component is registered correctly."""

    def test_registered_in_registry(self):
        assert REGISTRY.get("tSplitRow") is SplitRowConverter


class TestDefaults:
    """Verify all parameters have correct defaults when no params provided."""

    def test_col_mapping_default_empty(self):
        node = _make_node()
        result = SplitRowConverter().convert(node, [], {})
        assert result.component["config"]["col_mapping"] == []

    def test_tstatcatcher_stats_default_false(self):
        node = _make_node()
        result = SplitRowConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is False

    def test_label_default_empty(self):
        node = _make_node()
        result = SplitRowConverter().convert(node, [], {})
        assert result.component["config"]["label"] == ""


class TestParameterExtraction:
    """Verify each parameter is correctly extracted from XML params."""

    def test_col_mapping_single(self):
        """Single stride-2 group -> one {source_column, target_column} dict."""
        table = _make_col_mapping_table(('"src_col"', '"tgt_col"'))
        node = _make_node(params={"COL_MAPPING": table})
        result = SplitRowConverter().convert(node, [], {})
        assert result.component["config"]["col_mapping"] == [
            {"source_column": "src_col", "target_column": "tgt_col"}
        ]

    def test_col_mapping_multiple(self):
        """Two stride-2 groups -> two mapping dicts."""
        table = _make_col_mapping_table(
            ('"col_a"', '"out_a"'),
            ('"col_b"', '"out_b"'),
        )
        node = _make_node(params={"COL_MAPPING": table})
        result = SplitRowConverter().convert(node, [], {})
        assert result.component["config"]["col_mapping"] == [
            {"source_column": "col_a", "target_column": "out_a"},
            {"source_column": "col_b", "target_column": "out_b"},
        ]


class TestColMappingTable:
    """Verify COL_MAPPING TABLE stride-2 parsing."""

    def test_col_mapping_stride_2(self):
        """Each entry has SOURCE_COLUMN + TARGET_COLUMN."""
        table = _make_col_mapping_table(('"id"', '"out_id"'))
        node = _make_node(params={"COL_MAPPING": table})
        result = SplitRowConverter().convert(node, [], {})
        mapping = result.component["config"]["col_mapping"]
        assert len(mapping) == 1
        assert "source_column" in mapping[0]
        assert "target_column" in mapping[0]

    def test_col_mapping_empty_list(self):
        """Empty raw TABLE -> empty list."""
        node = _make_node(params={"COL_MAPPING": []})
        result = SplitRowConverter().convert(node, [], {})
        assert result.component["config"]["col_mapping"] == []

    def test_col_mapping_incomplete_stride_skipped(self):
        """Incomplete trailing group (< 2 entries) is skipped."""
        table = _make_col_mapping_table(('"src"', '"tgt"'))
        # Add a trailing orphan entry
        table.append({"elementRef": "SOURCE_COLUMN", "value": '"orphan"'})
        node = _make_node(params={"COL_MAPPING": table})
        result = SplitRowConverter().convert(node, [], {})
        # Only the complete pair should be parsed
        assert len(result.component["config"]["col_mapping"]) == 1


class TestFrameworkParams:
    """Verify tstatcatcher_stats and label extraction."""

    def test_tstatcatcher_stats_true(self):
        node = _make_node(params={"TSTATCATCHER_STATS": "true"})
        result = SplitRowConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is True

    def test_label_extracted(self):
        node = _make_node(params={"LABEL": '"my_label"'})
        result = SplitRowConverter().convert(node, [], {})
        assert result.component["config"]["label"] == "my_label"


class TestSchema:
    """Verify schema extraction."""

    def test_schema_passthrough(self):
        """Transform component: input == output."""
        node = _make_node(schema=_make_schema_columns())
        result = SplitRowConverter().convert(node, [], {})
        schema = result.component["schema"]
        assert schema["input"] == schema["output"]

    def test_schema_columns_populated(self):
        """Schema columns are properly populated from FLOW schema."""
        node = _make_node(schema=_make_schema_columns())
        result = SplitRowConverter().convert(node, [], {})
        schema = result.component["schema"]
        assert len(schema["input"]) == 3
        assert schema["input"][0]["name"] == "id"
        assert schema["input"][1]["name"] == "name"
        assert schema["input"][2]["name"] == "amount"


class TestNeedsReview:
    """Verify needs_review entries for engine gaps."""

    def test_needs_review_count(self):
        """Single consolidated needs_review per D-27 (no engine)."""
        node = _make_node()
        result = SplitRowConverter().convert(node, [], {})
        assert len(result.needs_review) == 1

    def test_needs_review_no_engine(self):
        """needs_review mentions no v1 engine implementation."""
        node = _make_node()
        result = SplitRowConverter().convert(node, [], {})
        assert "No v1 engine implementation" in result.needs_review[0]["issue"]

    def test_needs_review_severity(self):
        node = _make_node()
        result = SplitRowConverter().convert(node, [], {})
        assert result.needs_review[0]["severity"] == "engine_gap"

    def test_needs_review_has_component_id(self):
        node = _make_node(component_id="test_comp")
        result = SplitRowConverter().convert(node, [], {})
        assert result.needs_review[0]["component"] == "test_comp"

    def test_no_framework_param_needs_review(self):
        """Framework params (tstatcatcher_stats, label) must NOT have needs_review."""
        node = _make_node()
        result = SplitRowConverter().convert(node, [], {})
        issues = [e["issue"] for e in result.needs_review]
        for issue in issues:
            assert "tstatcatcher_stats" not in issue
            assert "label" not in issue.lower().split()


class TestPhantomParams:
    """Verify params NOT in _java.xml are NOT extracted."""

    def test_connection_format_not_in_config(self):
        """CONNECTION_FORMAT is phantom (not in _java.xml) -- must NOT appear in config."""
        node = _make_node(params={"CONNECTION_FORMAT": '"row"'})
        result = SplitRowConverter().convert(node, [], {})
        assert "connection_format" not in result.component["config"]


class TestCompleteness:
    """Verify all expected config keys are present."""

    def test_all_config_keys_present(self):
        node = _make_node(schema=_make_schema_columns())
        result = SplitRowConverter().convert(node, [], {})
        expected_keys = {
            "col_mapping",
            "tstatcatcher_stats",
            "label",
        }
        actual_keys = set(result.component["config"].keys())
        missing = expected_keys - actual_keys
        assert not missing, f"Missing config keys: {missing}"


class TestComponentStructure:
    """Verify component dict structure."""

    def test_has_type(self):
        """type_name='tSplitRow' per D-43 (no-engine)."""
        node = _make_node()
        result = SplitRowConverter().convert(node, [], {})
        assert result.component["type"] == "tSplitRow"

    def test_has_original_type(self):
        node = _make_node()
        result = SplitRowConverter().convert(node, [], {})
        assert result.component["original_type"] == "tSplitRow"

    def test_has_config_key(self):
        node = _make_node()
        result = SplitRowConverter().convert(node, [], {})
        assert "config" in result.component

    def test_has_schema_key(self):
        node = _make_node()
        result = SplitRowConverter().convert(node, [], {})
        assert "schema" in result.component
