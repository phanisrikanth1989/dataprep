"""Tests for SplitRowConverter (tSplitRow -> v1 SplitRow config)."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.transform.split_row import (
    SplitRowConverter,
    _parse_col_mapping,
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
    """Return a sample FLOW schema for the output of tSplitRow."""
    return {
        "FLOW": [
            SchemaColumn(name="id", type="id_Integer", nullable=False, key=True, length=10),
            SchemaColumn(name="name", type="id_String", nullable=True, length=50),
            SchemaColumn(name="Month", type="id_String", nullable=False),
            SchemaColumn(name="amount", type="id_Integer", nullable=True),
        ]
    }


def _make_col_mapping_table(*groups):
    """Build COL_MAPPING raw TABLE data from group dicts.

    Each positional argument is a dict {target_col: source_expr}.
    Groups are concatenated in order; repeated target column names across
    groups signal new groups to the parser.

    Example:
        _make_col_mapping_table(
            {"id": "row1.id", "Month": '"Jan"'},
            {"id": "row1.id", "Month": '"Feb"'},
        )
    """
    result = []
    for group in groups:
        for target_col, source_expr in group.items():
            result.append({"elementRef": target_col, "value": source_expr})
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

    def test_col_mapping_single_group(self):
        """One group of 3 columns -> one group dict."""
        table = _make_col_mapping_table(
            {"id": "row1.id", "Month": '"Jan"', "amount": "row1.Jan"}
        )
        node = _make_node(params={"COL_MAPPING": table})
        result = SplitRowConverter().convert(node, [], {})
        assert result.component["config"]["col_mapping"] == [
            {"id": "row1.id", "Month": '"Jan"', "amount": "row1.Jan"}
        ]

    def test_col_mapping_multiple_groups(self):
        """Three groups -> three group dicts in order."""
        table = _make_col_mapping_table(
            {"id": "row1.id", "Month": '"Jan"', "amount": "row1.Jan"},
            {"id": "row1.id", "Month": '"Feb"', "amount": "row1.Feb"},
            {"id": "row1.id", "Month": '"Mar"', "amount": "row1.Mar"},
        )
        node = _make_node(params={"COL_MAPPING": table})
        result = SplitRowConverter().convert(node, [], {})
        assert len(result.component["config"]["col_mapping"]) == 3
        assert result.component["config"]["col_mapping"][0]["Month"] == '"Jan"'
        assert result.component["config"]["col_mapping"][1]["Month"] == '"Feb"'
        assert result.component["config"]["col_mapping"][2]["Month"] == '"Mar"'


class TestColMappingTable:
    """Verify COL_MAPPING TABLE parsing via _parse_col_mapping()."""

    def test_single_group_all_keys_present(self):
        raw = [
            {"elementRef": "id", "value": "row1.id"},
            {"elementRef": "name", "value": "row1.name"},
        ]
        result = _parse_col_mapping(raw)
        assert len(result) == 1
        assert result[0]["id"] == "row1.id"
        assert result[0]["name"] == "row1.name"

    def test_repeated_ref_starts_new_group(self):
        raw = [
            {"elementRef": "id", "value": "row1.id"},
            {"elementRef": "Month", "value": '"Jan"'},
            {"elementRef": "id", "value": "row1.id"},  # starts group 2
            {"elementRef": "Month", "value": '"Feb"'},
        ]
        result = _parse_col_mapping(raw)
        assert len(result) == 2
        assert result[0]["Month"] == '"Jan"'
        assert result[1]["Month"] == '"Feb"'

    def test_col_mapping_empty_list(self):
        """Empty raw TABLE -> empty list."""
        assert _parse_col_mapping([]) == []

    def test_col_mapping_none(self):
        assert _parse_col_mapping(None) == []

    def test_col_mapping_preserves_expression_as_is(self):
        """Source expressions are stored verbatim (not evaluated or stripped)."""
        raw = [{"elementRef": "Month", "value": '"Jan"'}]
        result = _parse_col_mapping(raw)
        assert result[0]["Month"] == '"Jan"'

    def test_col_mapping_flow_reference_preserved(self):
        raw = [{"elementRef": "id", "value": "row1.id"}]
        result = _parse_col_mapping(raw)
        assert result[0]["id"] == "row1.id"

    def test_non_dict_entries_skipped(self):
        raw = [
            {"elementRef": "id", "value": "row1.id"},
            "not_a_dict",
            {"elementRef": "name", "value": "row1.name"},
        ]
        result = _parse_col_mapping(raw)
        assert len(result) == 1
        assert result[0]["id"] == "row1.id"
        assert result[0]["name"] == "row1.name"


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
        """Transform component: input == output (schema is from node metadata)."""
        node = _make_node(schema=_make_schema_columns())
        result = SplitRowConverter().convert(node, [], {})
        schema = result.component["schema"]
        assert schema["input"] == schema["output"]

    def test_schema_columns_populated(self):
        """Schema columns are properly populated from FLOW schema."""
        node = _make_node(schema=_make_schema_columns())
        result = SplitRowConverter().convert(node, [], {})
        schema = result.component["schema"]
        assert len(schema["input"]) == 4
        assert schema["input"][0]["name"] == "id"
        assert schema["input"][2]["name"] == "Month"
        assert schema["input"][3]["name"] == "amount"


class TestNeedsReview:
    """Verify needs_review is empty (engine is implemented)."""

    def test_needs_review_empty(self):
        """Engine is implemented -- no needs_review entries."""
        node = _make_node()
        result = SplitRowConverter().convert(node, [], {})
        assert result.needs_review == []


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
        """type_name='SplitRow' (V1 engine name)."""
        node = _make_node()
        result = SplitRowConverter().convert(node, [], {})
        assert result.component["type"] == "SplitRow"

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
