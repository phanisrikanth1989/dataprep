"""Tests for ForeachConverter (tForeach -> v1 iterate config)."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import ComponentResult, SchemaColumn, TalendNode
from src.converters.talend_to_v1.components.iterate.foreach import ForeachConverter
from src.converters.talend_to_v1.components.registry import REGISTRY

# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


def _make_node(params=None, schema=None, component_id="fe_1",
               component_type="tForeach"):
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


def _make_values_data(values_list):
    """Generate VALUES TABLE data with stride-1: VALUE per row.

    values_list: list of strings (each is one VALUE entry)
    """
    result = []
    for value in values_list:
        result.append({"elementRef": "VALUE", "value": value})
    return result


# ------------------------------------------------------------------
# Test Classes (one per concern)
# ------------------------------------------------------------------


class TestRegistration:
    """Verify component is registered correctly."""

    def test_registered_in_registry(self):
        """tForeach is registered in the converter registry."""
        assert REGISTRY.get("tForeach") is ForeachConverter


class TestDefaults:
    """Verify all parameters have correct defaults when no params provided."""

    def test_values_default_empty(self):
        """VALUES defaults to empty list when absent."""
        node = _make_node()
        result = ForeachConverter().convert(node, [], {})
        assert result.component["config"]["values"] == []

    # connection_format removed from converter in a943b5f

    def test_tstatcatcher_stats_default_false(self):
        """tstatcatcher_stats defaults to False when absent."""
        node = _make_node()
        result = ForeachConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is False

    def test_label_default_empty(self):
        """label defaults to empty string when absent."""
        node = _make_node()
        result = ForeachConverter().convert(node, [], {})
        assert result.component["config"]["label"] == ""


class TestParameterExtraction:
    """Verify each parameter is correctly extracted from XML params."""

    # connection_format removed from converter in a943b5f


class TestTableParsing:
    """Verify VALUES TABLE parameter parsing."""

    def test_values_table_parsed(self):
        """VALUES table with VALUE entries parsed into list of strings."""
        values_data = _make_values_data(['"hello"', '"world"', '"foo"'])
        node = _make_node(params={"VALUES": values_data})
        result = ForeachConverter().convert(node, [], {})
        values = result.component["config"]["values"]
        assert len(values) == 3
        assert values[0] == "hello"
        assert values[1] == "world"
        assert values[2] == "foo"

    def test_values_table_empty_when_missing(self):
        """No VALUES param produces empty list."""
        node = _make_node()
        result = ForeachConverter().convert(node, [], {})
        assert result.component["config"]["values"] == []

    def test_values_table_strip_quotes(self):
        """TABLE values like '"hello"' are stripped to 'hello'."""
        values_data = _make_values_data(['"my_value"'])
        node = _make_node(params={"VALUES": values_data})
        result = ForeachConverter().convert(node, [], {})
        assert result.component["config"]["values"][0] == "my_value"

    def test_values_table_non_list_returns_empty(self):
        """VALUES="not_a_list" produces empty list."""
        node = _make_node(params={"VALUES": "not_a_list"})
        result = ForeachConverter().convert(node, [], {})
        assert result.component["config"]["values"] == []


class TestFrameworkParams:
    """Verify tstatcatcher_stats and label extraction."""

    def test_tstatcatcher_stats_true(self):
        """TSTATCATCHER_STATS=true is correctly extracted."""
        node = _make_node(params={"TSTATCATCHER_STATS": "true"})
        result = ForeachConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is True

    def test_label_extracted(self):
        """LABEL with quotes is correctly extracted and unquoted."""
        node = _make_node(params={"LABEL": '"my_label"'})
        result = ForeachConverter().convert(node, [], {})
        assert result.component["config"]["label"] == "my_label"


class TestComponentStructure:
    """Verify standard component dict structure from _build_component_dict."""

    def test_has_id_at_top_level(self):
        """Component dict has 'id' at top level for orchestrator compatibility."""
        node = _make_node(component_id="fe_1")
        result = ForeachConverter().convert(node, [], {})
        assert result.component["id"] == "fe_1"

    def test_has_type_at_top_level(self):
        """Component dict has 'type' at top level."""
        node = _make_node()
        result = ForeachConverter().convert(node, [], {})
        assert result.component["type"] == "tForeach"

    def test_has_original_type_at_top_level(self):
        """Component dict has 'original_type' at top level."""
        node = _make_node()
        result = ForeachConverter().convert(node, [], {})
        assert result.component["original_type"] == "tForeach"

    def test_has_position(self):
        """Component dict has 'position' at top level."""
        node = _make_node()
        result = ForeachConverter().convert(node, [], {})
        assert result.component["position"] == {"x": 100, "y": 200}

    def test_has_config_dict(self):
        """Component dict has 'config' as a nested dict."""
        node = _make_node()
        result = ForeachConverter().convert(node, [], {})
        assert isinstance(result.component["config"], dict)

    def test_has_inputs_outputs_lists(self):
        """Component dict has 'inputs' and 'outputs' as empty lists."""
        node = _make_node()
        result = ForeachConverter().convert(node, [], {})
        assert result.component["inputs"] == []
        assert result.component["outputs"] == []

    def test_schema_is_empty_dict(self):
        """Schema is {input: [], output: []} for utility/control component."""
        node = _make_node(schema=_make_schema_columns())
        result = ForeachConverter().convert(node, [], {})
        assert result.component["schema"] == {"input": [], "output": []}


class TestNeedsReview:
    """Verify needs_review is empty (engine impl now exists)."""

    def test_needs_review_empty(self):
        """needs_review is empty: the engine implementation exists and is complete."""
        node = _make_node()
        result = ForeachConverter().convert(node, [], {})
        assert result.needs_review == []

    def test_no_framework_param_needs_review(self):
        """Framework params (tstatcatcher_stats, label) must NOT have needs_review."""
        node = _make_node()
        result = ForeachConverter().convert(node, [], {})
        issues = [e["issue"] for e in result.needs_review]
        for issue in issues:
            assert "tstatcatcher_stats" not in issue
            assert "label" not in issue.lower().split()


class TestCompleteness:
    """Verify all expected config keys are present."""

    def test_all_config_keys_present(self):
        """All expected config keys exist in result.component['config']."""
        node = _make_node(schema=_make_schema_columns())
        result = ForeachConverter().convert(node, [], {})
        # connection_format removed from converter in a943b5f
        expected_keys = {
            "values",
            "tstatcatcher_stats", "label",
        }
        actual_keys = set(result.component["config"].keys())
        missing = expected_keys - actual_keys
        assert not missing, f"Missing config keys: {missing}"


    # TestPhantomParams removed -- connection_format removed from converter in a943b5f


# ------------------------------------------------------------------
# Plan 14-11: VALUES TABLE parser branch coverage (lines 42, 45)
# ------------------------------------------------------------------


class TestValuesTableParserBranches:
    """Cover lines 42 (incomplete trailing group break) and 45 (entry not dict)."""

    def test_incomplete_trailing_group_skipped(self):
        """Trailing 1-stride group is just len(group) < 1 which never trips
        in practice -- the group is built via slice and at least one entry
        is always present. The break statement is reached only with raw[]
        producing an empty slice, which the outer 'if not raw' already
        catches. The branch is technically unreachable for stride-1 groups,
        but we exercise the path that comes closest: a single non-VALUE ref
        that is silently ignored without error.
        """
        from src.converters.talend_to_v1.components.iterate.foreach import (
            _parse_values_table,
        )
        # Two entries -- both are valid groups since stride is 1
        raw = [
            {"elementRef": "VALUE", "value": '"a"'},
            {"elementRef": "OTHER", "value": '"b"'},  # different ref -> ignored
        ]
        result = _parse_values_table(raw)
        # Only VALUE refs become rows
        assert result == ["a"]

    def test_non_dict_entry_skipped(self):
        """A non-dict entry inside the iteration is silently skipped (line 45)."""
        from src.converters.talend_to_v1.components.iterate.foreach import (
            _parse_values_table,
        )
        raw = [
            {"elementRef": "VALUE", "value": '"first"'},
            "not_a_dict",  # skipped
            {"elementRef": "VALUE", "value": '"third"'},
        ]
        result = _parse_values_table(raw)
        assert result == ["first", "third"]
