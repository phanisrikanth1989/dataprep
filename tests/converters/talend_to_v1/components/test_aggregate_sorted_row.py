"""Tests for the AggregateSortedRowConverter (tAggregateSortedRow -> TAggregateSortedRow)."""
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


def _make_node(params=None, schema=None, component_id="agg_sorted_1",
               component_type="tAggregateSortedRow"):
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


class TestAggregateSortedRowRegistration:
    def test_registered_in_registry(self):
        assert REGISTRY.get("tAggregateSortedRow") is AggregateSortedRowConverter


class TestAggregateSortedRowBasic:
    def test_single_group_single_operation(self):
        ops = _make_operation("total_salary", "salary", "sum", ignore_null=True)
        node = _make_node(params={
            "GROUPBYS": _make_groupbys("department"),
            "OPERATIONS": ops,
            "DIE_ON_ERROR": "true",
        })
        result = AggregateSortedRowConverter().convert(node, [], {})

        assert isinstance(result, ComponentResult)
        comp = result.component
        assert comp["id"] == "agg_sorted_1"
        assert comp["type"] == "TAggregateSortedRow"
        assert comp["original_type"] == "tAggregateSortedRow"
        assert comp["position"] == {"x": 100, "y": 200}
        assert comp["config"]["group_bys"] == ["department"]
        assert len(comp["config"]["operations"]) == 1
        assert comp["config"]["operations"][0] == {
            "output_column": "total_salary",
            "input_column": "salary",
            "function": "sum",
            "ignore_null": True,
        }
        assert comp["config"]["die_on_error"] is True
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
            "DIE_ON_ERROR": "false",
        })
        result = AggregateSortedRowConverter().convert(node, [], {})

        cfg = result.component["config"]
        assert cfg["group_bys"] == ["department", "region"]
        assert len(cfg["operations"]) == 2
        assert cfg["operations"][0]["function"] == "count"
        assert cfg["operations"][0]["ignore_null"] is False
        assert cfg["operations"][1]["function"] == "avg"
        assert cfg["operations"][1]["ignore_null"] is True
        assert cfg["die_on_error"] is False
        assert result.warnings == []

    def test_die_on_error_defaults_false(self):
        """CONV-ASR-001: die_on_error must be present and default to False."""
        ops = _make_operation("total", "amount", "sum")
        node = _make_node(params={
            "GROUPBYS": _make_groupbys("id"),
            "OPERATIONS": ops,
        })
        result = AggregateSortedRowConverter().convert(node, [], {})

        assert result.component["config"]["die_on_error"] is False


class TestAggregateSortedRowOptionalParams:
    def test_row_count_included_when_present(self):
        ops = _make_operation("total", "amount", "sum")
        node = _make_node(params={
            "GROUPBYS": _make_groupbys("id"),
            "OPERATIONS": ops,
            "ROW_COUNT": '"100"',
        })
        result = AggregateSortedRowConverter().convert(node, [], {})

        assert result.component["config"]["row_count"] == "100"

    def test_connection_format_included_when_present(self):
        ops = _make_operation("total", "amount", "sum")
        node = _make_node(params={
            "GROUPBYS": _make_groupbys("id"),
            "OPERATIONS": ops,
            "CONNECTION_FORMAT": '"row"',
        })
        result = AggregateSortedRowConverter().convert(node, [], {})

        assert result.component["config"]["connection_format"] == "row"

    def test_optional_params_omitted_when_empty(self):
        ops = _make_operation("total", "amount", "sum")
        node = _make_node(params={
            "GROUPBYS": _make_groupbys("id"),
            "OPERATIONS": ops,
        })
        result = AggregateSortedRowConverter().convert(node, [], {})

        assert "row_count" not in result.component["config"]
        assert "connection_format" not in result.component["config"]


class TestAggregateSortedRowEmptyAndMissing:
    def test_empty_groupbys_and_operations(self):
        node = _make_node(params={
            "GROUPBYS": [],
            "OPERATIONS": [],
        })
        result = AggregateSortedRowConverter().convert(node, [], {})

        cfg = result.component["config"]
        assert cfg["group_bys"] == []
        assert cfg["operations"] == []
        assert any("No group_bys or operations" in w for w in result.warnings)

    def test_missing_params_entirely(self):
        node = _make_node(params={})
        result = AggregateSortedRowConverter().convert(node, [], {})

        cfg = result.component["config"]
        assert cfg["group_bys"] == []
        assert cfg["operations"] == []
        assert any("No group_bys or operations" in w for w in result.warnings)

    def test_groupbys_not_a_list(self):
        node = _make_node(params={
            "GROUPBYS": "not_a_list",
            "OPERATIONS": _make_operation("total", "amount", "sum"),
        })
        result = AggregateSortedRowConverter().convert(node, [], {})

        assert any("GROUPBYS param is not a list" in w for w in result.warnings)
        assert result.component["config"]["group_bys"] == []

    def test_operations_not_a_list(self):
        node = _make_node(params={
            "GROUPBYS": _make_groupbys("id"),
            "OPERATIONS": "not_a_list",
        })
        result = AggregateSortedRowConverter().convert(node, [], {})

        assert any("OPERATIONS param is not a list" in w for w in result.warnings)
        assert result.component["config"]["operations"] == []


class TestAggregateSortedRowSchema:
    def test_schema_passthrough(self):
        """Transform component: input and output schema from FLOW metadata."""
        ops = _make_operation("total_salary", "salary", "sum")
        node = _make_node(
            params={
                "GROUPBYS": _make_groupbys("department"),
                "OPERATIONS": ops,
            },
            schema=_make_schema_columns(),
        )
        result = AggregateSortedRowConverter().convert(node, [], {})

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
        result = AggregateSortedRowConverter().convert(node, [], {})

        schema = result.component["schema"]
        assert schema == {"input": [], "output": []}


class TestAggregateSortedRowOperationEdgeCases:
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
        result = AggregateSortedRowConverter().convert(node, [], {})
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
        result = AggregateSortedRowConverter().convert(node, [], {})
        assert result.component["config"]["operations"][0]["ignore_null"] is False
