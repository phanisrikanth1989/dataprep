"""Tests for the AggregateRowConverter (tAggregateRow -> AggregateRow)."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.aggregate.aggregate_row import (
    AggregateRowConverter,
    _normalise_function,
)
from src.converters.talend_to_v1.components.registry import REGISTRY


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_node(params=None, schema=None, component_id="agg_1",
               component_type="tAggregateRow"):
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
            SchemaColumn(name="department", type="id_String", nullable=False, key=True),
            SchemaColumn(name="employee_count", type="id_Integer", nullable=True),
            SchemaColumn(name="total_salary", type="id_Double", nullable=True),
        ]
    }


def _make_groupbys(*columns):
    """Build a GROUPBYS TABLE param list from column names."""
    return [{"elementRef": "INPUT_COLUMN", "value": f'"{col}"'} for col in columns]


def _make_operation(output_col, input_col, function, ignore_null=False):
    """Build a single OPERATIONS group (4 elementValue entries)."""
    return [
        {"elementRef": "OUTPUT_COLUMN", "value": f'"{output_col}"'},
        {"elementRef": "INPUT_COLUMN", "value": f'"{input_col}"'},
        {"elementRef": "FUNCTION", "value": f'"{function}"'},
        {"elementRef": "IGNORE_NULL", "value": "true" if ignore_null else "false"},
    ]


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class TestAggregateRowRegistration:
    def test_registered_in_registry(self):
        assert REGISTRY.get("tAggregateRow") is AggregateRowConverter


# ---------------------------------------------------------------------------
# Basic conversion
# ---------------------------------------------------------------------------

class TestAggregateRowBasic:
    def test_single_group_single_operation(self):
        ops = _make_operation("total_salary", "salary", "sum", ignore_null=True)
        node = _make_node(params={
            "GROUPBYS": _make_groupbys("department"),
            "OPERATIONS": ops,
        })
        result = AggregateRowConverter().convert(node, [], {})

        assert isinstance(result, ComponentResult)
        comp = result.component
        assert comp["id"] == "agg_1"
        assert comp["type"] == "AggregateRow"
        assert comp["original_type"] == "tAggregateRow"
        assert comp["position"] == {"x": 100, "y": 200}
        assert comp["config"]["group_by"] == ["department"]
        assert len(comp["config"]["operations"]) == 1
        assert comp["config"]["operations"][0] == {
            "output_column": "total_salary",
            "input_column": "salary",
            "function": "sum",
            "ignore_null": True,
        }
        assert comp["inputs"] == []
        assert comp["outputs"] == []
        assert result.warnings == []

    def test_multiple_groups_multiple_operations(self):
        ops = (
            _make_operation("emp_count", "employee_id", "count")
            + _make_operation("avg_salary", "salary", "avg", ignore_null=True)
        )
        node = _make_node(params={
            "GROUPBYS": _make_groupbys("department", "region"),
            "OPERATIONS": ops,
        })
        result = AggregateRowConverter().convert(node, [], {})

        cfg = result.component["config"]
        assert cfg["group_by"] == ["department", "region"]
        assert len(cfg["operations"]) == 2
        assert cfg["operations"][0]["function"] == "count"
        assert cfg["operations"][0]["ignore_null"] is False
        assert cfg["operations"][1]["function"] == "avg"
        assert cfg["operations"][1]["ignore_null"] is True
        assert result.warnings == []


# ---------------------------------------------------------------------------
# CONV-AGG-001: 'distinct' function normalisation
# ---------------------------------------------------------------------------

class TestAggregateRowFunctionMapping:
    """CONV-AGG-001: function name 'distinct' must map to 'count_distinct'."""

    def test_distinct_mapped_to_count_distinct(self):
        ops = _make_operation("unique_count", "customer_id", "distinct")
        node = _make_node(params={
            "GROUPBYS": _make_groupbys("region"),
            "OPERATIONS": ops,
        })
        result = AggregateRowConverter().convert(node, [], {})

        assert result.component["config"]["operations"][0]["function"] == "count_distinct"

    def test_count_distinct_passthrough(self):
        ops = _make_operation("unique_count", "customer_id", "count_distinct")
        node = _make_node(params={
            "GROUPBYS": _make_groupbys("region"),
            "OPERATIONS": ops,
        })
        result = AggregateRowConverter().convert(node, [], {})

        assert result.component["config"]["operations"][0]["function"] == "count_distinct"

    def test_unknown_function_passed_through(self):
        """Unknown functions are preserved so downstream can flag them."""
        ops = _make_operation("out", "inp", "percentile_90")
        node = _make_node(params={
            "GROUPBYS": _make_groupbys("key"),
            "OPERATIONS": ops,
        })
        result = AggregateRowConverter().convert(node, [], {})

        assert result.component["config"]["operations"][0]["function"] == "percentile_90"

    def test_normalise_function_helper(self):
        assert _normalise_function("distinct") == "count_distinct"
        assert _normalise_function("DISTINCT") == "count_distinct"
        assert _normalise_function("sum") == "sum"
        assert _normalise_function("SUM") == "sum"
        assert _normalise_function("Count") == "count"
        assert _normalise_function("unknown_func") == "unknown_func"


# ---------------------------------------------------------------------------
# Empty / missing parameters
# ---------------------------------------------------------------------------

class TestAggregateRowEmptyAndMissing:
    def test_empty_groupbys_and_operations(self):
        node = _make_node(params={
            "GROUPBYS": [],
            "OPERATIONS": [],
        })
        result = AggregateRowConverter().convert(node, [], {})

        cfg = result.component["config"]
        assert cfg["group_by"] == []
        assert cfg["operations"] == []
        assert any("No group_by or operations" in w for w in result.warnings)

    def test_missing_params_entirely(self):
        node = _make_node(params={})
        result = AggregateRowConverter().convert(node, [], {})

        cfg = result.component["config"]
        assert cfg["group_by"] == []
        assert cfg["operations"] == []
        assert any("No group_by or operations" in w for w in result.warnings)

    def test_groupbys_not_a_list(self):
        node = _make_node(params={
            "GROUPBYS": "not_a_list",
            "OPERATIONS": _make_operation("total", "amount", "sum"),
        })
        result = AggregateRowConverter().convert(node, [], {})

        assert any("GROUPBYS param is not a list" in w for w in result.warnings)
        assert result.component["config"]["group_by"] == []

    def test_operations_not_a_list(self):
        node = _make_node(params={
            "GROUPBYS": _make_groupbys("id"),
            "OPERATIONS": "not_a_list",
        })
        result = AggregateRowConverter().convert(node, [], {})

        assert any("OPERATIONS param is not a list" in w for w in result.warnings)
        assert result.component["config"]["operations"] == []


# ---------------------------------------------------------------------------
# Schema passthrough
# ---------------------------------------------------------------------------

class TestAggregateRowSchema:
    def test_schema_passthrough(self):
        """Input and output schema are both built from FLOW metadata."""
        ops = _make_operation("total_salary", "salary", "sum")
        node = _make_node(
            params={
                "GROUPBYS": _make_groupbys("department"),
                "OPERATIONS": ops,
            },
            schema=_make_schema_columns(),
        )
        result = AggregateRowConverter().convert(node, [], {})

        schema = result.component["schema"]
        assert schema["input"] == schema["output"]
        assert len(schema["input"]) == 3
        assert schema["input"][0]["name"] == "department"
        assert schema["input"][1]["name"] == "employee_count"
        assert schema["input"][2]["name"] == "total_salary"

    def test_empty_schema(self):
        """When no FLOW schema is present, input and output are empty lists."""
        ops = _make_operation("total", "amount", "sum")
        node = _make_node(params={
            "GROUPBYS": _make_groupbys("id"),
            "OPERATIONS": ops,
        })
        result = AggregateRowConverter().convert(node, [], {})

        schema = result.component["schema"]
        assert schema == {"input": [], "output": []}


# ---------------------------------------------------------------------------
# Operation edge-cases (CONV-AGG-005: non-stride-4 resilience)
# ---------------------------------------------------------------------------

class TestAggregateRowOperationEdgeCases:
    def test_ignore_null_true_string(self):
        ops = [
            {"elementRef": "OUTPUT_COLUMN", "value": '"out"'},
            {"elementRef": "INPUT_COLUMN", "value": '"inp"'},
            {"elementRef": "FUNCTION", "value": '"max"'},
            {"elementRef": "IGNORE_NULL", "value": "true"},
        ]
        node = _make_node(params={
            "GROUPBYS": _make_groupbys("key"),
            "OPERATIONS": ops,
        })
        result = AggregateRowConverter().convert(node, [], {})
        assert result.component["config"]["operations"][0]["ignore_null"] is True

    def test_ignore_null_false_string(self):
        ops = [
            {"elementRef": "OUTPUT_COLUMN", "value": '"out"'},
            {"elementRef": "INPUT_COLUMN", "value": '"inp"'},
            {"elementRef": "FUNCTION", "value": '"min"'},
            {"elementRef": "IGNORE_NULL", "value": "false"},
        ]
        node = _make_node(params={
            "GROUPBYS": _make_groupbys("key"),
            "OPERATIONS": ops,
        })
        result = AggregateRowConverter().convert(node, [], {})
        assert result.component["config"]["operations"][0]["ignore_null"] is False

    def test_operations_without_ignore_null_field(self):
        """CONV-AGG-005: operations missing IGNORE_NULL should still parse."""
        ops = [
            {"elementRef": "OUTPUT_COLUMN", "value": '"out"'},
            {"elementRef": "INPUT_COLUMN", "value": '"inp"'},
            {"elementRef": "FUNCTION", "value": '"sum"'},
            # no IGNORE_NULL entry
            {"elementRef": "OUTPUT_COLUMN", "value": '"out2"'},
            {"elementRef": "INPUT_COLUMN", "value": '"inp2"'},
            {"elementRef": "FUNCTION", "value": '"count"'},
        ]
        node = _make_node(params={
            "GROUPBYS": _make_groupbys("key"),
            "OPERATIONS": ops,
        })
        result = AggregateRowConverter().convert(node, [], {})

        parsed_ops = result.component["config"]["operations"]
        assert len(parsed_ops) == 2
        assert parsed_ops[0]["output_column"] == "out"
        assert parsed_ops[0]["function"] == "sum"
        assert "ignore_null" not in parsed_ops[0]
        assert parsed_ops[1]["output_column"] == "out2"
        assert parsed_ops[1]["function"] == "count"

    def test_entries_with_extra_unknown_refs_skipped(self):
        """Unknown elementRef entries are silently ignored."""
        ops = [
            {"elementRef": "OUTPUT_COLUMN", "value": '"out"'},
            {"elementRef": "UNKNOWN_REF", "value": "whatever"},
            {"elementRef": "INPUT_COLUMN", "value": '"inp"'},
            {"elementRef": "FUNCTION", "value": '"sum"'},
            {"elementRef": "IGNORE_NULL", "value": "true"},
        ]
        node = _make_node(params={
            "GROUPBYS": _make_groupbys("key"),
            "OPERATIONS": ops,
        })
        result = AggregateRowConverter().convert(node, [], {})

        parsed_ops = result.component["config"]["operations"]
        assert len(parsed_ops) == 1
        assert parsed_ops[0]["output_column"] == "out"
        assert parsed_ops[0]["input_column"] == "inp"
        assert parsed_ops[0]["function"] == "sum"
        assert parsed_ops[0]["ignore_null"] is True

    def test_operations_unparseable_entries_produce_warning(self):
        """Non-empty OPERATIONS with no OUTPUT_COLUMN refs => warning."""
        ops = [
            {"elementRef": "UNKNOWN", "value": "something"},
        ]
        node = _make_node(params={
            "GROUPBYS": _make_groupbys("id"),
            "OPERATIONS": ops,
        })
        result = AggregateRowConverter().convert(node, [], {})

        assert result.component["config"]["operations"] == []
        assert any("no valid operations" in w for w in result.warnings)
