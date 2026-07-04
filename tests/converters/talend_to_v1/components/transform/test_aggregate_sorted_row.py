"""Tests for AggregateSortedRowConverter (tAggregateSortedRow -> v1 AggregateSortedRow config)."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.transform.aggregate_sorted_row import (
    AggregateSortedRowConverter,
)
from src.converters.talend_to_v1.components.registry import REGISTRY


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


def _make_node(params=None, schema=None, component_id="asr_1",
               component_type="tAggregateSortedRow"):
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
            SchemaColumn(name="department", type="id_String", nullable=False, key=True, length=50),
            SchemaColumn(name="employee_count", type="id_Integer", nullable=True),
            SchemaColumn(name="total_salary", type="id_Double", nullable=True),
        ]
    }


def _make_groupbys_table(*pairs):
    """Build GROUPBYS TABLE with stride-2 (OUTPUT_COLUMN, INPUT_COLUMN) per row.

    pairs: list of (output_column, input_column) tuples.
    """
    result = []
    for output_col, input_col in pairs:
        result.append({"elementRef": "OUTPUT_COLUMN", "value": f'"{output_col}"'})
        result.append({"elementRef": "INPUT_COLUMN", "value": f'"{input_col}"'})
    return result


def _make_operations_table(*ops):
    """Build OPERATIONS TABLE with stride-4 (OUTPUT_COLUMN, INPUT_COLUMN, FUNCTION, IGNORE_NULL).

    ops: list of (output_column, input_column, function, ignore_null) tuples.
    """
    result = []
    for output_col, input_col, function, ignore_null in ops:
        result.append({"elementRef": "OUTPUT_COLUMN", "value": f'"{output_col}"'})
        result.append({"elementRef": "INPUT_COLUMN", "value": f'"{input_col}"'})
        result.append({"elementRef": "FUNCTION", "value": f'"{function}"'})
        result.append({"elementRef": "IGNORE_NULL", "value": "true" if ignore_null else "false"})
    return result


# ------------------------------------------------------------------
# Test Classes
# ------------------------------------------------------------------


class TestRegistration:
    """Verify component is registered correctly."""

    def test_registered_in_registry(self):
        assert REGISTRY.get("tAggregateSortedRow") is AggregateSortedRowConverter


class TestDefaults:
    """Verify all parameters have correct defaults when no params provided."""

    def test_groupbys_default_empty(self):
        node = _make_node()
        result = AggregateSortedRowConverter().convert(node, [], {})
        assert result.component["config"]["groupbys"] == []

    def test_operations_default_empty(self):
        node = _make_node()
        result = AggregateSortedRowConverter().convert(node, [], {})
        assert result.component["config"]["operations"] == []

    def test_row_count_default(self):
        """ROW_COUNT is TEXT type in _java.xml -- use _get_str, default empty string."""
        node = _make_node()
        result = AggregateSortedRowConverter().convert(node, [], {})
        assert result.component["config"]["row_count"] == ""

    def test_tstatcatcher_stats_default_false(self):
        node = _make_node()
        result = AggregateSortedRowConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is False

    def test_label_default_empty(self):
        node = _make_node()
        result = AggregateSortedRowConverter().convert(node, [], {})
        assert result.component["config"]["label"] == ""


class TestParameterExtraction:
    """Verify each parameter is correctly extracted from XML params."""

    def test_groupbys_parsing(self):
        """GROUPBYS TABLE stride-2 (OUTPUT_COLUMN, INPUT_COLUMN) -> list of dicts."""
        groupbys = _make_groupbys_table(
            ("dept_out", "dept_in"),
            ("region_out", "region_in"),
        )
        node = _make_node(params={"GROUPBYS": groupbys})
        result = AggregateSortedRowConverter().convert(node, [], {})
        gb = result.component["config"]["groupbys"]
        assert len(gb) == 2
        assert gb[0] == {"output_column": "dept_out", "input_column": "dept_in"}
        assert gb[1] == {"output_column": "region_out", "input_column": "region_in"}

    def test_operations_parsing(self):
        """OPERATIONS TABLE stride-4 -> list of dicts with function mapping."""
        ops = _make_operations_table(
            ("total_salary", "salary", "sum", False),
            ("emp_count", "employee_id", "count", True),
        )
        node = _make_node(params={"OPERATIONS": ops})
        result = AggregateSortedRowConverter().convert(node, [], {})
        operations = result.component["config"]["operations"]
        assert len(operations) == 2
        assert operations[0] == {
            "output_column": "total_salary",
            "input_column": "salary",
            "function": "sum",
            "ignore_null": False,
        }
        assert operations[1] == {
            "output_column": "emp_count",
            "input_column": "employee_id",
            "function": "count",
            "ignore_null": True,
        }

    def test_operations_function_mapping(self):
        """distinct->count_distinct, list_object preserved as list_object."""
        ops = _make_operations_table(
            ("unique_count", "customer_id", "distinct", False),
            ("all_items", "item", "list_object", False),
        )
        node = _make_node(params={"OPERATIONS": ops})
        result = AggregateSortedRowConverter().convert(node, [], {})
        operations = result.component["config"]["operations"]
        assert operations[0]["function"] == "count_distinct"
        assert operations[1]["function"] == "list_object"

    def test_operations_ignore_null(self):
        """Optional IGNORE_NULL field handled correctly."""
        ops = _make_operations_table(
            ("total", "amount", "sum", True),
        )
        node = _make_node(params={"OPERATIONS": ops})
        result = AggregateSortedRowConverter().convert(node, [], {})
        assert result.component["config"]["operations"][0]["ignore_null"] is True

    def test_row_count_extracted(self):
        """ROW_COUNT is TEXT type -- extracted as str."""
        node = _make_node(params={"ROW_COUNT": '"100"'})
        result = AggregateSortedRowConverter().convert(node, [], {})
        assert result.component["config"]["row_count"] == "100"


class TestFrameworkParams:
    """Verify tstatcatcher_stats and label extraction."""

    def test_tstatcatcher_stats_true(self):
        node = _make_node(params={"TSTATCATCHER_STATS": "true"})
        result = AggregateSortedRowConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is True

    def test_label_extracted(self):
        node = _make_node(params={"LABEL": '"my_agg_label"'})
        result = AggregateSortedRowConverter().convert(node, [], {})
        assert result.component["config"]["label"] == "my_agg_label"


class TestSchema:
    """Verify schema extraction."""

    def test_schema_passthrough(self):
        """Transform component: input and output schema from FLOW metadata."""
        node = _make_node(schema=_make_schema_columns())
        result = AggregateSortedRowConverter().convert(node, [], {})
        schema = result.component["schema"]
        assert schema["input"] == schema["output"]
        assert len(schema["input"]) == 3
        assert schema["input"][0]["name"] == "department"

    def test_empty_schema(self):
        """When no FLOW schema is present, input and output are empty lists."""
        node = _make_node()
        result = AggregateSortedRowConverter().convert(node, [], {})
        assert result.component["schema"] == {"input": [], "output": []}


class TestNeedsReview:
    """Verify needs_review entries for engine gaps."""

    def test_needs_review_has_entries(self):
        """Per-feature needs_review for engine gaps."""
        node = _make_node()
        result = AggregateSortedRowConverter().convert(node, [], {})
        assert len(result.needs_review) >= 1

    def test_needs_review_engine_gap_severity(self):
        node = _make_node()
        result = AggregateSortedRowConverter().convert(node, [], {})
        for entry in result.needs_review:
            assert entry["severity"] == "engine_gap"

    def test_needs_review_has_component_id(self):
        node = _make_node(component_id="test_comp")
        result = AggregateSortedRowConverter().convert(node, [], {})
        for entry in result.needs_review:
            assert entry["component"] == "test_comp"

    def test_no_framework_param_needs_review(self):
        """Framework params (tstatcatcher_stats, label) must NOT have needs_review."""
        node = _make_node()
        result = AggregateSortedRowConverter().convert(node, [], {})
        issues = [e["issue"] for e in result.needs_review]
        for issue in issues:
            assert "tstatcatcher_stats" not in issue
            assert "label" not in issue.lower().split()

    def test_conditional_ignore_null_needs_review(self):
        """Operations with ignore_null trigger needs_review for engine gap."""
        ops = _make_operations_table(("total", "amount", "sum", True))
        node = _make_node(params={"OPERATIONS": ops}, component_id="asr_42")
        result = AggregateSortedRowConverter().convert(node, [], {})
        ignore_null_entries = [
            nr for nr in result.needs_review if "ignore_null" in nr["issue"]
        ]
        assert len(ignore_null_entries) == 1
        assert ignore_null_entries[0]["component"] == "asr_42"
        assert ignore_null_entries[0]["severity"] == "engine_gap"

    def test_conditional_groupby_renaming_needs_review(self):
        """GROUPBYS with different output/input columns triggers needs_review."""
        groupbys = _make_groupbys_table(("dept_name", "dept_id"))
        node = _make_node(params={"GROUPBYS": groupbys}, component_id="asr_99")
        result = AggregateSortedRowConverter().convert(node, [], {})
        rename_entries = [
            nr for nr in result.needs_review if "renaming" in nr["issue"].lower() or "OUTPUT_COLUMN" in nr["issue"]
        ]
        assert len(rename_entries) >= 1


class TestCompleteness:
    """Verify all expected config keys are present."""

    def test_all_config_keys_present(self):
        node = _make_node(schema=_make_schema_columns())
        result = AggregateSortedRowConverter().convert(node, [], {})
        expected_keys = {
            "groupbys", "operations", "row_count",
            "tstatcatcher_stats", "label",
        }
        actual_keys = set(result.component["config"].keys())
        missing = expected_keys - actual_keys
        assert not missing, f"Missing config keys: {missing}"


class TestComponentStructure:
    """Verify _build_component_dict output structure."""

    def test_has_type(self):
        node = _make_node()
        result = AggregateSortedRowConverter().convert(node, [], {})
        assert result.component["type"] == "AggregateSortedRow"

    def test_has_original_type(self):
        node = _make_node()
        result = AggregateSortedRowConverter().convert(node, [], {})
        assert result.component["original_type"] == "tAggregateSortedRow"

    def test_has_id(self):
        node = _make_node(component_id="asr_test")
        result = AggregateSortedRowConverter().convert(node, [], {})
        assert result.component["id"] == "asr_test"

    def test_has_config_nested(self):
        """Config is nested under 'config' key per _build_component_dict."""
        node = _make_node()
        result = AggregateSortedRowConverter().convert(node, [], {})
        assert "config" in result.component
        assert isinstance(result.component["config"], dict)

    def test_has_schema(self):
        node = _make_node()
        result = AggregateSortedRowConverter().convert(node, [], {})
        assert "schema" in result.component

    def test_has_inputs_outputs(self):
        node = _make_node()
        result = AggregateSortedRowConverter().convert(node, [], {})
        assert result.component["inputs"] == []
        assert result.component["outputs"] == []


class TestPhantomParams:
    """Verify params NOT in _java.xml are NOT extracted."""

    def test_die_on_error_not_in_config(self):
        """DIE_ON_ERROR is not in _java.xml for tAggregateSortedRow -- phantom param."""
        node = _make_node(params={"DIE_ON_ERROR": "true"})
        result = AggregateSortedRowConverter().convert(node, [], {})
        assert "die_on_error" not in result.component["config"]

    def test_connection_format_not_in_config(self):
        """CONNECTION_FORMAT is not in _java.xml for tAggregateSortedRow -- phantom param."""
        node = _make_node(params={"CONNECTION_FORMAT": '"row"'})
        result = AggregateSortedRowConverter().convert(node, [], {})
        assert "connection_format" not in result.component["config"]

    def test_group_by_output_columns_not_separate_key(self):
        """group_by_output_columns should NOT be a separate config key -- it is embedded in groupbys."""
        node = _make_node()
        result = AggregateSortedRowConverter().convert(node, [], {})
        assert "group_by_output_columns" not in result.component["config"]
