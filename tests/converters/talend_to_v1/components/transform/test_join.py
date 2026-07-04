"""Tests for JoinConverter (tJoin -> v1 Join config)."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.transform.join import JoinConverter
from src.converters.talend_to_v1.components.registry import REGISTRY


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

def _make_node(params=None, schema=None, component_id="j_1",
               component_type="tJoin"):
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


def _make_schema_with_reject():
    """Return FLOW + REJECT schemas for testing."""
    return {
        "FLOW": [
            SchemaColumn(name="emp_id", type="id_Integer", nullable=False, key=False),
            SchemaColumn(name="name", type="id_String", nullable=False, length=100),
            SchemaColumn(name="dept_id", type="id_String", nullable=False, length=10),
            SchemaColumn(name="salary", type="id_Integer", nullable=False),
            SchemaColumn(name="dept_name", type="id_String", nullable=False, length=50),
            SchemaColumn(name="location", type="id_String", nullable=False, length=50),
        ],
        "REJECT": [
            SchemaColumn(name="emp_id", type="id_Integer", nullable=False, key=False),
            SchemaColumn(name="name", type="id_String", nullable=False, length=100),
            SchemaColumn(name="dept_id", type="id_String", nullable=False, length=10),
            SchemaColumn(name="salary", type="id_Integer", nullable=False),
            SchemaColumn(name="dept_name", type="id_String", nullable=False, length=50),
            SchemaColumn(name="location", type="id_String", nullable=False, length=50),
        ],
    }


def _make_join_key_data(rows):
    """Generate JOIN_KEY TABLE data with stride-2 per row.

    rows: list of tuples (input_column_value, lookup_column_value)
    """
    result = []
    for input_col, lookup_col in rows:
        result.append({"elementRef": "INPUT_COLUMN", "value": input_col})
        result.append({"elementRef": "LOOKUP_COLUMN", "value": lookup_col})
    return result


def _make_lookup_cols_data(rows):
    """Generate LOOKUP_COLS TABLE data with stride-2 per row.

    rows: list of tuples (output_column_value, lookup_column_value)
    """
    result = []
    for output_col, lookup_col in rows:
        result.append({"elementRef": "OUTPUT_COLUMN", "value": output_col})
        result.append({"elementRef": "LOOKUP_COLUMN", "value": lookup_col})
    return result


# ------------------------------------------------------------------
# Test Classes
# ------------------------------------------------------------------


class TestRegistration:
    """Verify component is registered correctly."""

    def test_registered_in_registry(self):
        assert REGISTRY.get("tJoin") is JoinConverter


class TestDefaults:
    """Verify all parameters have correct defaults when no params provided."""

    def test_use_inner_join_default_false(self):
        node = _make_node()
        result = JoinConverter().convert(node, [], {})
        assert result.component["config"]["use_inner_join"] is False

    def test_join_key_default_empty(self):
        node = _make_node()
        result = JoinConverter().convert(node, [], {})
        assert result.component["config"]["join_key"] == []

    def test_use_lookup_cols_default_false(self):
        node = _make_node()
        result = JoinConverter().convert(node, [], {})
        assert result.component["config"]["use_lookup_cols"] is False

    def test_lookup_cols_default_empty(self):
        node = _make_node()
        result = JoinConverter().convert(node, [], {})
        assert result.component["config"]["lookup_cols"] == []

    def test_tstatcatcher_stats_default_false(self):
        node = _make_node()
        result = JoinConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is False

    def test_label_default_empty(self):
        node = _make_node()
        result = JoinConverter().convert(node, [], {})
        assert result.component["config"]["label"] == ""


class TestParameterExtraction:
    """Verify each parameter is correctly extracted from XML params."""

    def test_use_inner_join_true(self):
        node = _make_node(params={"USE_INNER_JOIN": "true"})
        result = JoinConverter().convert(node, [], {})
        assert result.component["config"]["use_inner_join"] is True

    def test_join_key_parsing(self):
        """JOIN_KEY TABLE with INPUT_COLUMN+LOOKUP_COLUMN entries."""
        table_data = _make_join_key_data([
            ('"employee_id"', '"emp_id"'),
            ('"dept_id"', '"department_id"'),
        ])
        node = _make_node(params={"JOIN_KEY": table_data})
        result = JoinConverter().convert(node, [], {})
        keys = result.component["config"]["join_key"]
        assert len(keys) == 2
        assert keys[0] == {"input_column": "employee_id", "lookup_column": "emp_id"}
        assert keys[1] == {"input_column": "dept_id", "lookup_column": "department_id"}

    def test_join_key_fallback(self):
        """JOIN_KEY TABLE with LEFT_COLUMN+RIGHT_COLUMN entries (backward compat)."""
        table_data = [
            {"elementRef": "LEFT_COLUMN", "value": '"col_a"'},
            {"elementRef": "RIGHT_COLUMN", "value": '"col_b"'},
        ]
        node = _make_node(params={"JOIN_KEY": table_data})
        result = JoinConverter().convert(node, [], {})
        keys = result.component["config"]["join_key"]
        assert len(keys) == 1
        assert keys[0] == {"input_column": "col_a", "lookup_column": "col_b"}

    def test_use_lookup_cols_true(self):
        node = _make_node(params={"USE_LOOKUP_COLS": "true"})
        result = JoinConverter().convert(node, [], {})
        assert result.component["config"]["use_lookup_cols"] is True

    def test_lookup_cols_parsing(self):
        """LOOKUP_COLS TABLE with OUTPUT_COLUMN+LOOKUP_COLUMN entries."""
        table_data = _make_lookup_cols_data([
            ('"out_name"', '"lk_name"'),
            ('"out_age"', '"lk_age"'),
        ])
        node = _make_node(params={"LOOKUP_COLS": table_data})
        result = JoinConverter().convert(node, [], {})
        cols = result.component["config"]["lookup_cols"]
        assert len(cols) == 2
        assert cols[0] == {"output_column": "out_name", "lookup_column": "lk_name"}
        assert cols[1] == {"output_column": "out_age", "lookup_column": "lk_age"}


class TestFrameworkParams:
    """Verify tstatcatcher_stats and label extraction."""

    def test_tstatcatcher_stats_true(self):
        node = _make_node(params={"TSTATCATCHER_STATS": "true"})
        result = JoinConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is True

    def test_label_extracted(self):
        node = _make_node(params={"LABEL": '"my_join"'})
        result = JoinConverter().convert(node, [], {})
        assert result.component["config"]["label"] == "my_join"


class TestSchema:
    """Verify schema extraction."""

    def test_schema_passthrough(self):
        """Join passes schema through: input == output."""
        node = _make_node(schema=_make_schema_columns())
        result = JoinConverter().convert(node, [], {})
        schema = result.component["schema"]
        assert schema["input"] == schema["output"]
        assert len(schema["input"]) == 2
        assert schema["input"][0]["name"] == "id"
        assert schema["input"][1]["name"] == "name"

    def test_no_reject_schema_when_absent(self):
        """When REJECT metadata is absent, schema has no 'reject' key."""
        node = _make_node(schema=_make_schema_columns())
        result = JoinConverter().convert(node, [], {})
        assert "reject" not in result.component["schema"]

    def test_reject_schema_parsed(self):
        """When REJECT metadata exists, schema includes 'reject' key."""
        node = _make_node(schema=_make_schema_with_reject())
        result = JoinConverter().convert(node, [], {})
        schema = result.component["schema"]
        assert "reject" in schema
        assert len(schema["reject"]) == 6
        reject_names = [c["name"] for c in schema["reject"]]
        assert reject_names == ["emp_id", "name", "dept_id", "salary", "dept_name", "location"]

    def test_reject_schema_columns_match_flow(self):
        """REJECT schema columns typically mirror FLOW schema."""
        node = _make_node(schema=_make_schema_with_reject())
        result = JoinConverter().convert(node, [], {})
        schema = result.component["schema"]
        assert schema["output"] == schema["reject"]


class TestNeedsReview:
    """Verify needs_review entries for engine gaps."""

    def test_needs_review_has_entries(self):
        """Per-feature needs_review for engine UPPERCASE key mismatches."""
        node = _make_node()
        result = JoinConverter().convert(node, [], {})
        assert len(result.needs_review) >= 1

    def test_needs_review_engine_gap_severity(self):
        node = _make_node()
        result = JoinConverter().convert(node, [], {})
        for entry in result.needs_review:
            assert entry["severity"] == "engine_gap"

    def test_needs_review_has_component_id(self):
        node = _make_node(component_id="test_join")
        result = JoinConverter().convert(node, [], {})
        for entry in result.needs_review:
            assert entry["component"] == "test_join"

    def test_no_framework_param_needs_review(self):
        """Framework params (tstatcatcher_stats, label) must NOT have needs_review."""
        node = _make_node()
        result = JoinConverter().convert(node, [], {})
        issues = [e["issue"] for e in result.needs_review]
        for issue in issues:
            assert "tstatcatcher_stats" not in issue
            assert "label" not in issue.lower().split()


class TestPhantomParams:
    """Verify params NOT in _java.xml are NOT extracted."""

    def test_case_sensitive_not_in_config(self):
        """CASE_SENSITIVE is a phantom param -- must NOT appear in config."""
        node = _make_node(params={"CASE_SENSITIVE": "true"})
        result = JoinConverter().convert(node, [], {})
        assert "case_sensitive" not in result.component["config"]

    def test_die_on_error_not_in_config(self):
        """DIE_ON_ERROR is a phantom param -- must NOT appear in config."""
        node = _make_node(params={"DIE_ON_ERROR": "true"})
        result = JoinConverter().convert(node, [], {})
        assert "die_on_error" not in result.component["config"]


class TestCompleteness:
    """Verify all expected config keys are present."""

    def test_all_config_keys_present(self):
        """use_inner_join, join_key, use_lookup_cols, lookup_cols + 2 framework = 6 keys."""
        node = _make_node(schema=_make_schema_columns())
        result = JoinConverter().convert(node, [], {})
        expected_keys = {
            "use_inner_join", "join_key", "use_lookup_cols", "lookup_cols",
            "tstatcatcher_stats", "label",
        }
        actual_config_keys = set(result.component["config"].keys())
        missing = expected_keys - actual_config_keys
        assert not missing, f"Missing config keys: {missing}"
        assert len(result.component["config"]) == 6


class TestComponentStructure:
    """Verify component dict structure."""

    def test_has_type(self):
        node = _make_node()
        result = JoinConverter().convert(node, [], {})
        assert result.component["type"] == "Join"

    def test_has_id(self):
        node = _make_node(component_id="my_join_1")
        result = JoinConverter().convert(node, [], {})
        assert result.component["id"] == "my_join_1"

    def test_has_original_type(self):
        node = _make_node()
        result = JoinConverter().convert(node, [], {})
        assert result.component["original_type"] == "tJoin"

    def test_has_config_dict(self):
        node = _make_node()
        result = JoinConverter().convert(node, [], {})
        assert isinstance(result.component["config"], dict)


class TestParseHelperEdgeCases:
    """Cover the trailing-incomplete-group and non-dict-entry branches in
    _parse_join_key / _parse_lookup_cols (PLAN 14-12-extras gap closure)."""

    def test_join_keys_incomplete_trailing_group_is_skipped(self):
        from src.converters.talend_to_v1.components.transform.join import _parse_join_key
        raw = [
            {"elementRef": "INPUT_COLUMN", "value": '"id"'},
            {"elementRef": "LOOKUP_COLUMN", "value": '"id"'},
            {"elementRef": "INPUT_COLUMN", "value": '"orphan"'},
        ]
        assert _parse_join_key(raw) == [
            {"input_column": "id", "lookup_column": "id"}
        ]

    def test_join_keys_non_dict_entry_is_ignored(self):
        from src.converters.talend_to_v1.components.transform.join import _parse_join_key
        raw = [
            "not-a-dict",
            {"elementRef": "LOOKUP_COLUMN", "value": '"id"'},
        ]
        assert _parse_join_key(raw) == [{"lookup_column": "id"}]

    def test_lookup_cols_incomplete_trailing_group_is_skipped(self):
        from src.converters.talend_to_v1.components.transform.join import _parse_lookup_cols
        raw = [
            {"elementRef": "OUTPUT_COLUMN", "value": '"name"'},
            {"elementRef": "LOOKUP_COLUMN", "value": '"name"'},
            {"elementRef": "OUTPUT_COLUMN", "value": '"orphan"'},
        ]
        assert _parse_lookup_cols(raw) == [
            {"output_column": "name", "lookup_column": "name"}
        ]

    def test_lookup_cols_non_dict_entry_is_ignored(self):
        from src.converters.talend_to_v1.components.transform.join import _parse_lookup_cols
        raw = [
            42,
            {"elementRef": "LOOKUP_COLUMN", "value": '"id"'},
        ]
        assert _parse_lookup_cols(raw) == [{"lookup_column": "id"}]
