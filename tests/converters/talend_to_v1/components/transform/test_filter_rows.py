"""Tests for FilterRowsConverter (tFilterRow/tFilterRows -> v1 FilterRows config)."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.transform.filter_rows import (
    FilterRowsConverter,
)
from src.converters.talend_to_v1.components.registry import REGISTRY


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

def _make_node(params=None, schema=None, component_id="fr_1",
               component_type="tFilterRow"):
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


def _make_conditions_data(rows):
    """Generate CONDITIONS TABLE data with stride-4 per row.

    rows: list of tuples (input_column, function, operator, rvalue)
    """
    result = []
    for row_values in rows:
        for field_name, value in zip(
            ("INPUT_COLUMN", "FUNCTION", "OPERATOR", "RVALUE"), row_values
        ):
            result.append({"elementRef": field_name, "value": value})
    return result


# ------------------------------------------------------------------
# Test Classes
# ------------------------------------------------------------------


class TestRegistration:
    """Verify component is registered correctly."""

    def test_registered_as_tfilterrow(self):
        assert REGISTRY.get("tFilterRow") is FilterRowsConverter

    def test_registered_as_tfilterrows(self):
        assert REGISTRY.get("tFilterRows") is FilterRowsConverter


class TestDefaults:
    """Verify all parameters have correct defaults when no params provided."""

    def test_logical_op_default_and(self):
        node = _make_node()
        result = FilterRowsConverter().convert(node, [], {})
        assert result.component["config"]["logical_op"] == "AND"

    def test_conditions_default_empty(self):
        node = _make_node()
        result = FilterRowsConverter().convert(node, [], {})
        assert result.component["config"]["conditions"] == []

    def test_use_advanced_default_false(self):
        node = _make_node()
        result = FilterRowsConverter().convert(node, [], {})
        assert result.component["config"]["use_advanced"] is False

    def test_advanced_cond_default_empty(self):
        node = _make_node()
        result = FilterRowsConverter().convert(node, [], {})
        assert result.component["config"]["advanced_cond"] == ""

    def test_tstatcatcher_stats_default_false(self):
        node = _make_node()
        result = FilterRowsConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is False

    def test_label_default_empty(self):
        node = _make_node()
        result = FilterRowsConverter().convert(node, [], {})
        assert result.component["config"]["label"] == ""


class TestParameterExtraction:
    """Verify each parameter is correctly extracted from XML params."""

    def test_logical_op_or(self):
        node = _make_node(params={"LOGICAL_OP": '"OR"'})
        result = FilterRowsConverter().convert(node, [], {})
        assert result.component["config"]["logical_op"] == "OR"

    def test_use_advanced_true(self):
        node = _make_node(params={"USE_ADVANCED": "true"})
        result = FilterRowsConverter().convert(node, [], {})
        assert result.component["config"]["use_advanced"] is True

    def test_advanced_cond_extracted(self):
        node = _make_node(params={"ADVANCED_COND": '"row.col > 5"'})
        result = FilterRowsConverter().convert(node, [], {})
        assert result.component["config"]["advanced_cond"] == "row.col > 5"

    def test_conditions_single(self):
        """4-element group -> {column, function, operator, value}."""
        conds = _make_conditions_data([("age", "EMPTY", ">", "18")])
        node = _make_node(params={"CONDITIONS": conds})
        result = FilterRowsConverter().convert(node, [], {})
        conditions = result.component["config"]["conditions"]
        assert len(conditions) == 1
        assert conditions[0] == {
            "column": "age",
            "function": "EMPTY",
            "operator": ">",
            "value": "18",
        }

    def test_conditions_multiple(self):
        """8-element group -> 2 condition dicts."""
        conds = _make_conditions_data([
            ("age", "EMPTY", ">", "18"),
            ("name", "LENGTH", "!=", '"test"'),
        ])
        node = _make_node(params={"CONDITIONS": conds})
        result = FilterRowsConverter().convert(node, [], {})
        conditions = result.component["config"]["conditions"]
        assert len(conditions) == 2
        assert conditions[0]["column"] == "age"
        assert conditions[1]["column"] == "name"
        assert conditions[1]["function"] == "LENGTH"
        assert conditions[1]["value"] == "test"


class TestConditionsTable:
    """Verify CONDITIONS TABLE stride-4 parsing."""

    def test_conditions_stride_4(self):
        """Each group has exactly 4 fields (INPUT_COLUMN, FUNCTION, OPERATOR, RVALUE)."""
        conds = _make_conditions_data([("col1", "EMPTY", "==", "val1")])
        node = _make_node(params={"CONDITIONS": conds})
        result = FilterRowsConverter().convert(node, [], {})
        conditions = result.component["config"]["conditions"]
        assert len(conditions) == 1
        assert set(conditions[0].keys()) == {"column", "function", "operator", "value"}

    def test_conditions_no_prefilter(self):
        """PREFILTER is NOT a field in parsed conditions."""
        conds = _make_conditions_data([("col1", "EMPTY", "==", "val1")])
        node = _make_node(params={"CONDITIONS": conds})
        result = FilterRowsConverter().convert(node, [], {})
        conditions = result.component["config"]["conditions"]
        assert len(conditions) == 1
        assert "prefilter" not in conditions[0]

    def test_conditions_empty_list(self):
        """Empty raw -> []."""
        node = _make_node(params={"CONDITIONS": []})
        result = FilterRowsConverter().convert(node, [], {})
        assert result.component["config"]["conditions"] == []


class TestFrameworkParams:
    """Verify tstatcatcher_stats and label extraction."""

    def test_tstatcatcher_stats_true(self):
        node = _make_node(params={"TSTATCATCHER_STATS": "true"})
        result = FilterRowsConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is True

    def test_label_extracted(self):
        node = _make_node(params={"LABEL": '"my_filter"'})
        result = FilterRowsConverter().convert(node, [], {})
        assert result.component["config"]["label"] == "my_filter"


class TestSchema:
    """Verify schema extraction for transform component (passthrough)."""

    def test_schema_passthrough(self):
        """FilterRows passes through schema: both input and output match."""
        node = _make_node(schema=_make_schema_columns())
        result = FilterRowsConverter().convert(node, [], {})
        schema = result.component["schema"]
        assert schema["input"] == schema["output"]

    def test_schema_columns_populated(self):
        """Schema columns are correctly populated from FLOW schema."""
        node = _make_node(schema=_make_schema_columns())
        result = FilterRowsConverter().convert(node, [], {})
        schema = result.component["schema"]
        assert len(schema["output"]) == 2
        assert schema["output"][0]["name"] == "id"
        assert schema["output"][1]["name"] == "name"


class TestNeedsReview:
    """Verify needs_review entries for engine gaps."""

    def test_needs_review_has_entries(self):
        node = _make_node()
        result = FilterRowsConverter().convert(node, [], {})
        assert len(result.needs_review) >= 1

    def test_needs_review_engine_gap_severity(self):
        node = _make_node()
        result = FilterRowsConverter().convert(node, [], {})
        for entry in result.needs_review:
            assert entry["severity"] == "engine_gap"

    def test_needs_review_has_component_id(self):
        node = _make_node(component_id="test_comp")
        result = FilterRowsConverter().convert(node, [], {})
        for entry in result.needs_review:
            assert entry["component"] == "test_comp"

    def test_no_framework_param_needs_review(self):
        """Framework params (tstatcatcher_stats, label) must NOT have needs_review."""
        node = _make_node()
        result = FilterRowsConverter().convert(node, [], {})
        issues = [e["issue"] for e in result.needs_review]
        for issue in issues:
            assert "tstatcatcher_stats" not in issue
            assert "label" not in issue.lower().split()


class TestPhantomParams:
    """Verify params NOT in _java.xml are NOT extracted."""

    def test_die_on_error_not_in_config(self):
        """DIE_ON_ERROR is phantom -- NOT extracted even when provided."""
        node = _make_node(params={"DIE_ON_ERROR": "true"})
        result = FilterRowsConverter().convert(node, [], {})
        assert "die_on_error" not in result.component["config"]

    def test_prefilter_not_in_conditions(self):
        """PREFILTER is NOT a column in conditions (phantom)."""
        # Even if raw data includes PREFILTER entries, they should be ignored
        raw = [
            {"elementRef": "INPUT_COLUMN", "value": "col1"},
            {"elementRef": "FUNCTION", "value": "EMPTY"},
            {"elementRef": "OPERATOR", "value": "=="},
            {"elementRef": "RVALUE", "value": "val1"},
            {"elementRef": "PREFILTER", "value": "some_expr"},
        ]
        node = _make_node(params={"CONDITIONS": raw})
        result = FilterRowsConverter().convert(node, [], {})
        conditions = result.component["config"]["conditions"]
        assert len(conditions) == 1
        assert "prefilter" not in conditions[0]


class TestCompleteness:
    """Verify all expected config keys are present."""

    def test_all_config_keys_present(self):
        """logical_op, conditions, use_advanced, advanced_cond + 2 framework."""
        node = _make_node(schema=_make_schema_columns())
        result = FilterRowsConverter().convert(node, [], {})
        expected_keys = {
            "logical_op", "conditions", "use_advanced", "advanced_cond",
            "tstatcatcher_stats", "label",
        }
        actual_keys = set(result.component["config"].keys())
        missing = expected_keys - actual_keys
        assert not missing, f"Missing config keys: {missing}"


class TestComponentStructure:
    """Verify component dict structure."""

    def test_has_type(self):
        node = _make_node()
        result = FilterRowsConverter().convert(node, [], {})
        assert result.component["type"] == "FilterRows"

    def test_has_original_type(self):
        node = _make_node(component_type="tFilterRow")
        result = FilterRowsConverter().convert(node, [], {})
        assert result.component["original_type"] == "tFilterRow"

    def test_has_original_type_tfilterrows(self):
        node = _make_node(component_type="tFilterRows")
        result = FilterRowsConverter().convert(node, [], {})
        assert result.component["original_type"] == "tFilterRows"

    def test_component_dict_keys(self):
        """Output dict has all required top-level keys."""
        node = _make_node()
        result = FilterRowsConverter().convert(node, [], {})
        expected_keys = {"id", "type", "original_type", "position", "config", "schema", "inputs", "outputs"}
        assert set(result.component.keys()) == expected_keys

    def test_result_type(self):
        """convert() returns a ComponentResult."""
        node = _make_node()
        result = FilterRowsConverter().convert(node, [], {})
        assert isinstance(result, ComponentResult)
