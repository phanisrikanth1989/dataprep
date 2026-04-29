"""Tests for AggregateRowConverter (tAggregateRow -> v1 aggregate config)."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.aggregate.aggregate_row import (
    AggregateRowConverter,
)
from src.converters.talend_to_v1.components.base import (
    SchemaColumn,
    TalendNode,
)
from src.converters.talend_to_v1.components.registry import REGISTRY


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

def _make_node(params=None, schema=None, component_id="ar_1",
               component_type="tAggregateRow"):
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
            SchemaColumn(name="count", type="id_Integer", nullable=True),
        ]
    }


def _make_groupbys_data(rows):
    """Generate GROUPBYS TABLE data with stride-2 per row.

    rows: list of tuples (output_column, input_column)
    """
    result = []
    for output_col, input_col in rows:
        result.append({"elementRef": "OUTPUT_COLUMN", "value": f'"{output_col}"'})
        result.append({"elementRef": "INPUT_COLUMN", "value": f'"{input_col}"'})
    return result


def _make_operations_data(rows):
    """Generate OPERATIONS TABLE data with stride-4 per row.

    rows: list of tuples (output_column, function, input_column, ignore_null)
    """
    result = []
    for output_col, function, input_col, ignore_null in rows:
        result.append({"elementRef": "OUTPUT_COLUMN", "value": f'"{output_col}"'})
        result.append({"elementRef": "FUNCTION", "value": f'"{function}"'})
        result.append({"elementRef": "INPUT_COLUMN", "value": f'"{input_col}"'})
        result.append({"elementRef": "IGNORE_NULL", "value": "true" if ignore_null else "false"})
    return result


# ------------------------------------------------------------------
# Test Classes
# ------------------------------------------------------------------


class TestRegistration:
    """Verify component is registered correctly."""

    def test_registered_in_registry(self):
        assert REGISTRY.get("tAggregateRow") is AggregateRowConverter


class TestDefaults:
    """Verify all parameters have correct defaults when no params provided."""

    def test_groupbys_default_empty(self):
        node = _make_node()
        result = AggregateRowConverter().convert(node, [], {})
        assert result.component["config"]["groupbys"] == []

    def test_operations_default_empty(self):
        node = _make_node()
        result = AggregateRowConverter().convert(node, [], {})
        assert result.component["config"]["operations"] == []

    def test_list_delimiter_default_comma(self):
        node = _make_node()
        result = AggregateRowConverter().convert(node, [], {})
        assert result.component["config"]["list_delimiter"] == ","

    def test_use_financial_precision_default_true(self):
        node = _make_node()
        result = AggregateRowConverter().convert(node, [], {})
        assert result.component["config"]["use_financial_precision"] is True

    def test_check_type_overflow_default_false(self):
        node = _make_node()
        result = AggregateRowConverter().convert(node, [], {})
        assert result.component["config"]["check_type_overflow"] is False

    def test_check_ulp_default_false(self):
        node = _make_node()
        result = AggregateRowConverter().convert(node, [], {})
        assert result.component["config"]["check_ulp"] is False


class TestParameterExtraction:
    """Verify each parameter is correctly extracted from XML params."""

    def test_list_delimiter_semicolon(self):
        node = _make_node(params={"LIST_DELIMITER": '";"'})
        result = AggregateRowConverter().convert(node, [], {})
        assert result.component["config"]["list_delimiter"] == ";"

    def test_use_financial_precision_false(self):
        node = _make_node(params={"USE_FINANCIAL_PRECISION": "false"})
        result = AggregateRowConverter().convert(node, [], {})
        assert result.component["config"]["use_financial_precision"] is False

    def test_check_type_overflow_true(self):
        node = _make_node(params={"CHECK_TYPE_OVERFLOW": "true"})
        result = AggregateRowConverter().convert(node, [], {})
        assert result.component["config"]["check_type_overflow"] is True

    def test_check_ulp_true(self):
        node = _make_node(params={"CHECK_ULP": "true"})
        result = AggregateRowConverter().convert(node, [], {})
        assert result.component["config"]["check_ulp"] is True


class TestTableParsingGroupbys:
    """Verify GROUPBYS TABLE parameter parsing."""

    def test_groupbys_parsed(self):
        """OUTPUT_COLUMN + INPUT_COLUMN pairs produce groupbys list of dicts."""
        groupbys = _make_groupbys_data([
            ("dept_name", "dept_id"),
            ("region_name", "region_code"),
        ])
        node = _make_node(params={"GROUPBYS": groupbys})
        result = AggregateRowConverter().convert(node, [], {})
        cfg = result.component["config"]
        assert cfg["groupbys"] == [
            {"output_column": "dept_name", "input_column": "dept_id"},
            {"output_column": "region_name", "input_column": "region_code"},
        ]

    def test_groupbys_empty_when_missing(self):
        node = _make_node()
        result = AggregateRowConverter().convert(node, [], {})
        assert result.component["config"]["groupbys"] == []

    def test_groupbys_strip_quotes(self):
        """Quote-wrapped values should be stripped."""
        groupbys = [
            {"elementRef": "OUTPUT_COLUMN", "value": '"department"'},
            {"elementRef": "INPUT_COLUMN", "value": '"department"'},
        ]
        node = _make_node(params={"GROUPBYS": groupbys})
        result = AggregateRowConverter().convert(node, [], {})
        assert result.component["config"]["groupbys"] == [
            {"output_column": "department", "input_column": "department"},
        ]


class TestTableParsingOperations:
    """Verify OPERATIONS TABLE parameter parsing."""

    def test_operations_parsed(self):
        """OUTPUT_COLUMN + FUNCTION + INPUT_COLUMN + IGNORE_NULL produce operation dicts."""
        ops = _make_operations_data([
            ("total_amount", "sum", "amount", False),
            ("max_value", "max", "value", True),
        ])
        node = _make_node(params={"OPERATIONS": ops})
        result = AggregateRowConverter().convert(node, [], {})
        operations = result.component["config"]["operations"]
        assert len(operations) == 2
        assert operations[0]["output_column"] == "total_amount"
        assert operations[0]["function"] == "sum"
        assert operations[0]["input_column"] == "amount"
        assert operations[0]["ignore_null"] is False
        assert operations[1]["output_column"] == "max_value"
        assert operations[1]["function"] == "max"
        assert operations[1]["input_column"] == "value"
        assert operations[1]["ignore_null"] is True

    def test_operations_empty_when_missing(self):
        node = _make_node()
        result = AggregateRowConverter().convert(node, [], {})
        assert result.component["config"]["operations"] == []

    def test_operations_function_normalized(self):
        """Function names are case-insensitive and normalized."""
        ops = _make_operations_data([
            ("out1", "Sum", "col1", False),
            ("out2", "COUNT", "col2", False),
        ])
        node = _make_node(params={"OPERATIONS": ops})
        result = AggregateRowConverter().convert(node, [], {})
        operations = result.component["config"]["operations"]
        assert operations[0]["function"] == "sum"
        assert operations[1]["function"] == "count"

    def test_operations_ignore_null_default_false(self):
        """When IGNORE_NULL entry is missing, ignore_null key is absent from dict."""
        ops = [
            {"elementRef": "OUTPUT_COLUMN", "value": '"out"'},
            {"elementRef": "FUNCTION", "value": '"sum"'},
            {"elementRef": "INPUT_COLUMN", "value": '"col"'},
            # No IGNORE_NULL entry
            {"elementRef": "OUTPUT_COLUMN", "value": '"out2"'},
            {"elementRef": "FUNCTION", "value": '"max"'},
            {"elementRef": "INPUT_COLUMN", "value": '"col2"'},
        ]
        node = _make_node(params={"OPERATIONS": ops})
        result = AggregateRowConverter().convert(node, [], {})
        operations = result.component["config"]["operations"]
        assert len(operations) == 2
        assert "ignore_null" not in operations[0]
        assert "ignore_null" not in operations[1]

    def test_operations_all_12_functions_valid(self):
        """All 12 _java.xml CLOSED_LIST functions are handled without error."""
        all_functions = [
            "count", "min", "max", "avg", "sum", "first",
            "last", "list", "list_object", "distinct", "std_dev", "union",
        ]
        for fn in all_functions:
            ops = _make_operations_data([("out", fn, "col", False)])
            node = _make_node(params={"OPERATIONS": ops})
            result = AggregateRowConverter().convert(node, [], {})
            # Should not raise and should produce exactly one operation
            assert len(result.component["config"]["operations"]) == 1, (
                f"Function '{fn}' failed to produce an operation"
            )

    def test_operations_list_delimiter_injected(self):
        """List-function operations have delimiter key injected from LIST_DELIMITER."""
        ops = _make_operations_data([("names", "list", "name", False)])
        node = _make_node(params={"OPERATIONS": ops, "LIST_DELIMITER": '";"'})
        result = AggregateRowConverter().convert(node, [], {})
        operations = result.component["config"]["operations"]
        assert operations[0]["delimiter"] == ";"

    def test_operations_list_object_preserved_no_warning(self):
        """list_object is preserved unchanged; no lossy-mapping warning emitted.

        Phase 6 fix (commit 125ddc6) changed _FUNCTION_MAP to pass list_object
        through unchanged because the engine implements it as a delimited string.
        The previous "maps to list with warning" behavior was lossy and was
        replaced with verbatim preservation.
        """
        ops = _make_operations_data([("out", "list_object", "col", False)])
        node = _make_node(params={"OPERATIONS": ops})
        result = AggregateRowConverter().convert(node, [], {})
        assert result.component["config"]["operations"][0]["function"] == "list_object"
        assert not any("list_object" in w and "not preserved" in w for w in result.warnings)

    def test_operations_missing_output_column_warns(self):
        """Operation without OUTPUT_COLUMN emits a warning about the missing field."""
        ops = [
            {"elementRef": "FUNCTION", "value": '"sum"'},
            {"elementRef": "INPUT_COLUMN", "value": '"amount"'},
        ]
        node = _make_node(params={"OPERATIONS": ops})
        result = AggregateRowConverter().convert(node, [], {})
        assert any("OUTPUT_COLUMN" in w for w in result.warnings)

    def test_operations_non_list_no_delimiter(self):
        """Non-list operations should NOT have delimiter key injected."""
        ops = _make_operations_data([("total", "sum", "amount", False)])
        node = _make_node(params={"OPERATIONS": ops, "LIST_DELIMITER": '";"'})
        result = AggregateRowConverter().convert(node, [], {})
        assert "delimiter" not in result.component["config"]["operations"][0]


class TestFrameworkParams:
    """Verify tstatcatcher_stats and label extraction."""

    def test_tstatcatcher_stats_default_false(self):
        node = _make_node()
        result = AggregateRowConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is False

    def test_tstatcatcher_stats_true(self):
        node = _make_node(params={"TSTATCATCHER_STATS": "true"})
        result = AggregateRowConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is True

    def test_label_default_empty(self):
        node = _make_node()
        result = AggregateRowConverter().convert(node, [], {})
        assert result.component["config"]["label"] == ""

    def test_label_extracted(self):
        node = _make_node(params={"LABEL": '"my_label"'})
        result = AggregateRowConverter().convert(node, [], {})
        assert result.component["config"]["label"] == "my_label"


class TestSchema:
    """Verify schema extraction."""

    def test_schema_extracted(self):
        node = _make_node(schema=_make_schema_columns())
        result = AggregateRowConverter().convert(node, [], {})
        schema = result.component["schema"]
        assert "input" in schema
        assert "output" in schema
        assert len(schema["input"]) == 4
        assert schema["input"][0]["name"] == "id"


class TestNeedsReview:
    """Verify needs_review entries for engine gaps."""

    def test_needs_review_count(self):
        """With default params (no triggers), needs_review should be empty."""
        node = _make_node()
        result = AggregateRowConverter().convert(node, [], {})
        # No conditions met (no groupby renaming, no ignore_null, no overflow/ulp/list)
        assert len(result.needs_review) == 0

    def test_needs_review_severity_engine_gap(self):
        """When triggered, all entries have severity engine_gap."""
        # Trigger: groupby renaming + ignore_null + check_type_overflow
        groupbys = _make_groupbys_data([("renamed", "original")])
        ops = _make_operations_data([("out", "sum", "col", True)])
        node = _make_node(params={
            "GROUPBYS": groupbys,
            "OPERATIONS": ops,
            "CHECK_TYPE_OVERFLOW": "true",
        })
        result = AggregateRowConverter().convert(node, [], {})
        assert len(result.needs_review) >= 3
        for entry in result.needs_review:
            assert entry["severity"] == "engine_gap"

    def test_needs_review_has_component_id(self):
        """All needs_review entries have the correct component ID."""
        groupbys = _make_groupbys_data([("renamed", "original")])
        ops = _make_operations_data([("out", "sum", "col", False)])
        node = _make_node(
            params={"GROUPBYS": groupbys, "OPERATIONS": ops},
            component_id="test_comp",
        )
        result = AggregateRowConverter().convert(node, [], {})
        for entry in result.needs_review:
            assert entry["component"] == "test_comp"

    def test_no_framework_param_needs_review(self):
        """Framework params (tstatcatcher_stats, label) must NOT have needs_review."""
        # Trigger all possible needs_review entries
        groupbys = _make_groupbys_data([("renamed", "original")])
        ops = _make_operations_data([("out", "list", "col", True)])
        node = _make_node(params={
            "GROUPBYS": groupbys,
            "OPERATIONS": ops,
            "CHECK_TYPE_OVERFLOW": "true",
            "CHECK_ULP": "true",
            "TSTATCATCHER_STATS": "true",
            "LABEL": '"test"',
        })
        result = AggregateRowConverter().convert(node, [], {})
        issues = [e["issue"] for e in result.needs_review]
        for issue in issues:
            assert "tstatcatcher_stats" not in issue
            assert "label" not in issue.lower().split()


class TestCompleteness:
    """Verify all expected config keys are present."""

    def test_all_config_keys_present(self):
        node = _make_node(schema=_make_schema_columns())
        result = AggregateRowConverter().convert(node, [], {})
        expected_keys = {
            "groupbys", "operations",
            "list_delimiter", "use_financial_precision",
            "check_type_overflow", "check_ulp",
            "tstatcatcher_stats", "label",
        }
        actual_keys = set(result.component["config"].keys())
        missing = expected_keys - actual_keys
        assert not missing, f"Missing config keys: {missing}"


class TestPhantomParams:
    """Verify no phantom params are extracted (tAggregateRow has no known phantoms)."""

    def test_connection_format_not_extracted(self):
        """CONNECTION_FORMAT is NOT a tAggregateRow param -- should not appear in config."""
        node = _make_node(params={"CONNECTION_FORMAT": "row"})
        result = AggregateRowConverter().convert(node, [], {})
        assert "connection_format" not in result.component["config"]
