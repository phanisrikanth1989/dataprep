"""Tests for SortRowConverter (tSortRow -> v1 SortRow config)."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.transform.sort_row import (
    SortRowConverter,
)
from src.converters.talend_to_v1.components.registry import REGISTRY


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

def _make_node(params=None, schema=None, component_id="sr_1",
               component_type="tSortRow"):
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


def _make_criteria(rows):
    """Generate CRITERIA TABLE data with stride-3 per row.

    rows: list of tuples (column, sort_type, order)
        e.g. [("col1", "NUM", "ASC"), ("col2", "ALPHA", "DESC")]
    """
    result = []
    for col, sort_type, order in rows:
        result.append({"elementRef": "COLNAME", "value": f'"{col}"'})
        result.append({"elementRef": "SORT", "value": sort_type})
        result.append({"elementRef": "ORDER", "value": order})
    return result


# ------------------------------------------------------------------
# Test Classes
# ------------------------------------------------------------------


class TestRegistration:
    """Verify component is registered correctly."""

    def test_registered_in_registry(self):
        assert REGISTRY.get("tSortRow") is SortRowConverter


class TestDefaults:
    """Verify all parameters have correct defaults when no params provided."""

    def test_criteria_default_empty(self):
        node = _make_node()
        result = SortRowConverter().convert(node, [], {})
        assert result.component["config"]["criteria"] == []

    def test_external_default_false(self):
        node = _make_node()
        result = SortRowConverter().convert(node, [], {})
        assert result.component["config"]["external"] is False

    def test_tempfile_default(self):
        node = _make_node()
        result = SortRowConverter().convert(node, [], {})
        assert result.component["config"]["tempfile"] == "__COMP_DEFAULT_FILE_DIR__/temp"

    def test_createdir_default_true(self):
        node = _make_node()
        result = SortRowConverter().convert(node, [], {})
        assert result.component["config"]["createdir"] is True

    def test_external_sort_buffersize_default(self):
        node = _make_node()
        result = SortRowConverter().convert(node, [], {})
        assert result.component["config"]["external_sort_buffersize"] == "1000000"

    def test_tstatcatcher_stats_default_false(self):
        node = _make_node()
        result = SortRowConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is False

    def test_label_default_empty(self):
        node = _make_node()
        result = SortRowConverter().convert(node, [], {})
        assert result.component["config"]["label"] == ""


class TestCriteriaTable:
    """Verify CRITERIA TABLE parsing with correct SORT/ORDER semantics."""

    def test_criteria_single(self):
        """Single criterion: COLNAME=col1, SORT=NUM, ORDER=ASC."""
        node = _make_node(params={
            "CRITERIA": _make_criteria([("col1", "NUM", "ASC")]),
        })
        result = SortRowConverter().convert(node, [], {})
        criteria = result.component["config"]["criteria"]
        assert len(criteria) == 1
        assert criteria[0] == {"column": "col1", "sort_type": "num", "order": "asc"}

    def test_criteria_multiple(self):
        """Two criteria groups produce two criterion dicts."""
        node = _make_node(params={
            "CRITERIA": _make_criteria([
                ("last_name", "ALPHA", "ASC"),
                ("hire_date", "DATE", "DESC"),
            ]),
        })
        result = SortRowConverter().convert(node, [], {})
        criteria = result.component["config"]["criteria"]
        assert len(criteria) == 2
        assert criteria[0] == {"column": "last_name", "sort_type": "alpha", "order": "asc"}
        assert criteria[1] == {"column": "hire_date", "sort_type": "date", "order": "desc"}

    def test_criteria_sort_is_type_not_direction(self):
        """SORT=ALPHA -> sort_type='alpha' (data type, NOT direction)."""
        node = _make_node(params={
            "CRITERIA": _make_criteria([("name", "ALPHA", "ASC")]),
        })
        result = SortRowConverter().convert(node, [], {})
        criteria = result.component["config"]["criteria"]
        assert criteria[0]["sort_type"] == "alpha"

    def test_criteria_order_is_direction(self):
        """ORDER=DESC -> order='desc' (direction, NOT data type)."""
        node = _make_node(params={
            "CRITERIA": _make_criteria([("name", "NUM", "DESC")]),
        })
        result = SortRowConverter().convert(node, [], {})
        criteria = result.component["config"]["criteria"]
        assert criteria[0]["order"] == "desc"

    def test_criteria_sort_default_num(self):
        """Missing SORT value -> sort_type='num' (default)."""
        node = _make_node(params={
            "CRITERIA": [
                {"elementRef": "COLNAME", "value": '"col1"'},
                {"elementRef": "SORT", "value": ""},
                {"elementRef": "ORDER", "value": "ASC"},
            ],
        })
        result = SortRowConverter().convert(node, [], {})
        criteria = result.component["config"]["criteria"]
        assert criteria[0]["sort_type"] == "num"

    def test_criteria_order_default_asc(self):
        """Missing ORDER value -> order='asc' (default)."""
        node = _make_node(params={
            "CRITERIA": [
                {"elementRef": "COLNAME", "value": '"col1"'},
                {"elementRef": "SORT", "value": "NUM"},
                {"elementRef": "ORDER", "value": ""},
            ],
        })
        result = SortRowConverter().convert(node, [], {})
        criteria = result.component["config"]["criteria"]
        assert criteria[0]["order"] == "asc"

    def test_criteria_date_type(self):
        """SORT=DATE -> sort_type='date'."""
        node = _make_node(params={
            "CRITERIA": _make_criteria([("created_at", "DATE", "ASC")]),
        })
        result = SortRowConverter().convert(node, [], {})
        criteria = result.component["config"]["criteria"]
        assert criteria[0]["sort_type"] == "date"

    def test_criteria_empty_list(self):
        """Empty CRITERIA list -> empty criteria."""
        node = _make_node(params={"CRITERIA": []})
        result = SortRowConverter().convert(node, [], {})
        assert result.component["config"]["criteria"] == []

    def test_criteria_missing_param(self):
        """No CRITERIA param -> empty criteria."""
        node = _make_node()
        result = SortRowConverter().convert(node, [], {})
        assert result.component["config"]["criteria"] == []

    def test_criteria_incomplete_stride_skipped(self):
        """Incomplete trailing group (< 3 entries) is skipped."""
        node = _make_node(params={
            "CRITERIA": [
                {"elementRef": "COLNAME", "value": '"col1"'},
                {"elementRef": "SORT", "value": "NUM"},
                {"elementRef": "ORDER", "value": "ASC"},
                # Incomplete trailing group
                {"elementRef": "COLNAME", "value": '"col2"'},
                {"elementRef": "SORT", "value": "ALPHA"},
            ],
        })
        result = SortRowConverter().convert(node, [], {})
        criteria = result.component["config"]["criteria"]
        assert len(criteria) == 1
        assert criteria[0]["column"] == "col1"


class TestParameterExtraction:
    """Verify each parameter is correctly extracted from XML params."""

    def test_external_true(self):
        node = _make_node(params={"EXTERNAL": "true"})
        result = SortRowConverter().convert(node, [], {})
        assert result.component["config"]["external"] is True

    def test_tempfile_custom(self):
        node = _make_node(params={"TEMPFILE": '"custom/path"'})
        result = SortRowConverter().convert(node, [], {})
        assert result.component["config"]["tempfile"] == "custom/path"

    def test_createdir_false(self):
        node = _make_node(params={"CREATEDIR": "false"})
        result = SortRowConverter().convert(node, [], {})
        assert result.component["config"]["createdir"] is False

    def test_external_sort_buffersize_custom(self):
        node = _make_node(params={"EXTERNAL_SORT_BUFFERSIZE": '"500000"'})
        result = SortRowConverter().convert(node, [], {})
        assert result.component["config"]["external_sort_buffersize"] == "500000"


class TestFrameworkParams:
    """Verify tstatcatcher_stats and label extraction."""

    def test_tstatcatcher_stats_true(self):
        node = _make_node(params={"TSTATCATCHER_STATS": "true"})
        result = SortRowConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is True

    def test_label_extracted(self):
        node = _make_node(params={"LABEL": '"my_sort"'})
        result = SortRowConverter().convert(node, [], {})
        assert result.component["config"]["label"] == "my_sort"


class TestSchema:
    """Verify schema extraction (transform passthrough)."""

    def test_schema_passthrough(self):
        """SortRow passes the schema through: input == output."""
        node = _make_node(schema=_make_schema_columns())
        result = SortRowConverter().convert(node, [], {})
        schema = result.component["schema"]
        assert schema["input"] == schema["output"]
        assert len(schema["input"]) == 2

    def test_schema_columns_populated(self):
        """Schema columns have correct names."""
        node = _make_node(schema=_make_schema_columns())
        result = SortRowConverter().convert(node, [], {})
        schema = result.component["schema"]
        assert schema["input"][0]["name"] == "id"
        assert schema["input"][1]["name"] == "name"


class TestNeedsReview:
    """Verify needs_review entries for engine gaps."""

    def test_needs_review_has_entries(self):
        """At least 3 needs_review entries (na_position, case_sensitive, chunk_size)."""
        node = _make_node()
        result = SortRowConverter().convert(node, [], {})
        assert len(result.needs_review) >= 3

    def test_needs_review_engine_gap_severity(self):
        """All needs_review entries have severity 'engine_gap'."""
        node = _make_node()
        result = SortRowConverter().convert(node, [], {})
        for entry in result.needs_review:
            assert entry["severity"] == "engine_gap"

    def test_needs_review_has_component_id(self):
        node = _make_node(component_id="test_comp")
        result = SortRowConverter().convert(node, [], {})
        for entry in result.needs_review:
            assert entry["component"] == "test_comp"

    def test_no_framework_param_needs_review(self):
        """Framework params (tstatcatcher_stats, label) must NOT have needs_review."""
        node = _make_node()
        result = SortRowConverter().convert(node, [], {})
        issues = [e["issue"] for e in result.needs_review]
        for issue in issues:
            assert "tstatcatcher_stats" not in issue
            assert "label" not in issue.lower().split()


class TestPhantomParams:
    """Verify params NOT in _java.xml are NOT extracted."""

    def test_sort_type_not_in_criteria(self):
        """No 'sort_types' key in config (phantom SORT_TYPE column removed)."""
        node = _make_node(params={
            "CRITERIA": _make_criteria([("col1", "NUM", "ASC")]),
        })
        result = SortRowConverter().convert(node, [], {})
        cfg = result.component["config"]
        assert "sort_types" not in cfg
        assert "sort_columns" not in cfg
        assert "sort_orders" not in cfg

    def test_external_sort_not_param_name(self):
        """Config does NOT have 'external_sort' key (uses 'external' per _java.xml EXTERNAL)."""
        node = _make_node(params={"EXTERNAL": "true"})
        result = SortRowConverter().convert(node, [], {})
        cfg = result.component["config"]
        assert "external_sort" not in cfg
        assert "external" in cfg

    def test_buffer_size_not_param_name(self):
        """Config does NOT have 'buffer_size' key (uses 'external_sort_buffersize' per _java.xml)."""
        node = _make_node(params={"EXTERNAL_SORT_BUFFERSIZE": '"500000"'})
        result = SortRowConverter().convert(node, [], {})
        cfg = result.component["config"]
        assert "buffer_size" not in cfg
        assert "max_memory_rows" not in cfg
        assert "external_sort_buffersize" in cfg


class TestCompleteness:
    """Verify all expected config keys are present."""

    def test_all_config_keys_present(self):
        """All config keys: criteria, external, tempfile, createdir, external_sort_buffersize + 2 framework."""
        node = _make_node()
        result = SortRowConverter().convert(node, [], {})
        cfg = result.component["config"]
        expected_keys = {
            "criteria",
            "external",
            "tempfile",
            "createdir",
            "external_sort_buffersize",
            "tstatcatcher_stats",
            "label",
        }
        assert set(cfg.keys()) == expected_keys


class TestComponentStructure:
    """Verify component dict structure."""

    def test_has_type(self):
        node = _make_node()
        result = SortRowConverter().convert(node, [], {})
        assert result.component["type"] == "SortRow"

    def test_has_original_type(self):
        node = _make_node()
        result = SortRowConverter().convert(node, [], {})
        assert result.component["original_type"] == "tSortRow"

    def test_has_id(self):
        node = _make_node(component_id="my_sort")
        result = SortRowConverter().convert(node, [], {})
        assert result.component["id"] == "my_sort"

    def test_has_position(self):
        node = _make_node()
        result = SortRowConverter().convert(node, [], {})
        assert result.component["position"] == {"x": 100, "y": 200}
