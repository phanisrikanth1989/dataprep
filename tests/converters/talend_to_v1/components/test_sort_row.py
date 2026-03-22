"""Tests for the SortRowConverter (tSortRow -> SortRow)."""
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


def _make_node(params=None, schema=None, component_id="sort_1",
               component_type="tSortRow"):
    return TalendNode(
        component_id=component_id,
        component_type=component_type,
        params=params or {},
        schema=schema or {},
        position={"x": 200, "y": 300},
        raw_xml=ET.Element("node"),
    )


def _make_schema_columns():
    """Return a sample FLOW schema for testing."""
    return {
        "FLOW": [
            SchemaColumn(name="id", type="id_Integer", nullable=False, key=True),
            SchemaColumn(name="name", type="id_String", nullable=True),
            SchemaColumn(name="amount", type="id_Double", nullable=True),
        ]
    }


class TestSortRowRegistration:
    def test_registered_in_registry(self):
        assert REGISTRY.get("tSortRow") is SortRowConverter


class TestSortRowBasic:
    def test_single_sort_criterion(self):
        node = _make_node(params={
            "CRITERIA": [
                {"elementRef": "COLNAME", "value": '"name"'},
                {"elementRef": "SORT", "value": "asc"},
            ],
        })
        result = SortRowConverter().convert(node, [], {})

        assert isinstance(result, ComponentResult)
        comp = result.component
        assert comp["id"] == "sort_1"
        assert comp["type"] == "SortRow"
        assert comp["original_type"] == "tSortRow"
        assert comp["position"] == {"x": 200, "y": 300}
        assert comp["config"]["sort_columns"] == ["name"]
        assert comp["config"]["sort_orders"] == ["asc"]
        assert comp["config"]["external_sort"] is False
        assert "temp_file" not in comp["config"]
        assert comp["inputs"] == []
        assert comp["outputs"] == []
        assert result.warnings == []

    def test_multiple_sort_criteria(self):
        node = _make_node(params={
            "CRITERIA": [
                {"elementRef": "COLNAME", "value": '"last_name"'},
                {"elementRef": "SORT", "value": "asc"},
                {"elementRef": "COLNAME", "value": '"first_name"'},
                {"elementRef": "SORT", "value": "asc"},
                {"elementRef": "COLNAME", "value": '"hire_date"'},
                {"elementRef": "SORT", "value": "desc"},
            ],
        })
        result = SortRowConverter().convert(node, [], {})

        cfg = result.component["config"]
        assert cfg["sort_columns"] == ["last_name", "first_name", "hire_date"]
        assert cfg["sort_orders"] == ["asc", "asc", "desc"]
        assert result.warnings == []

    def test_sort_order_case_insensitive(self):
        node = _make_node(params={
            "CRITERIA": [
                {"elementRef": "COLNAME", "value": '"col_a"'},
                {"elementRef": "SORT", "value": "DESC"},
                {"elementRef": "COLNAME", "value": '"col_b"'},
                {"elementRef": "SORT", "value": "ASC"},
            ],
        })
        result = SortRowConverter().convert(node, [], {})

        cfg = result.component["config"]
        assert cfg["sort_orders"] == ["desc", "asc"]
        assert result.warnings == []


class TestSortRowExternalSort:
    def test_external_sort_enabled(self):
        node = _make_node(params={
            "CRITERIA": [
                {"elementRef": "COLNAME", "value": '"id"'},
                {"elementRef": "SORT", "value": "asc"},
            ],
            "EXTERNAL_SORT": "true",
            "TEMPFILE": '"/tmp/talend_sort"',
        })
        result = SortRowConverter().convert(node, [], {})

        cfg = result.component["config"]
        assert cfg["external_sort"] is True
        assert cfg["temp_file"] == "/tmp/talend_sort"
        assert result.warnings == []

    def test_external_sort_disabled(self):
        node = _make_node(params={
            "CRITERIA": [
                {"elementRef": "COLNAME", "value": '"id"'},
                {"elementRef": "SORT", "value": "asc"},
            ],
            "EXTERNAL_SORT": "false",
        })
        result = SortRowConverter().convert(node, [], {})

        cfg = result.component["config"]
        assert cfg["external_sort"] is False
        assert "temp_file" not in cfg

    def test_temp_file_omitted_when_empty(self):
        node = _make_node(params={
            "CRITERIA": [
                {"elementRef": "COLNAME", "value": '"id"'},
                {"elementRef": "SORT", "value": "asc"},
            ],
            "EXTERNAL_SORT": "true",
            "TEMPFILE": '""',
        })
        result = SortRowConverter().convert(node, [], {})

        # Empty string after stripping quotes -> not included
        assert "temp_file" not in result.component["config"]


class TestSortRowEmptyAndMissing:
    def test_empty_criteria_list(self):
        node = _make_node(params={"CRITERIA": []})
        result = SortRowConverter().convert(node, [], {})

        cfg = result.component["config"]
        assert cfg["sort_columns"] == []
        assert cfg["sort_orders"] == []
        assert any("No sort criteria" in w for w in result.warnings)

    def test_missing_criteria_param(self):
        node = _make_node(params={})
        result = SortRowConverter().convert(node, [], {})

        cfg = result.component["config"]
        assert cfg["sort_columns"] == []
        assert cfg["sort_orders"] == []
        assert any("No sort criteria" in w for w in result.warnings)

    def test_criteria_not_a_list(self):
        """If CRITERIA is not a list (unexpected), produce a warning."""
        node = _make_node(params={"CRITERIA": "not_a_list"})
        result = SortRowConverter().convert(node, [], {})

        cfg = result.component["config"]
        assert cfg["sort_columns"] == []
        assert cfg["sort_orders"] == []
        assert any("not a list" in w for w in result.warnings)


class TestSortRowUnpairedEntries:
    def test_colname_without_sort(self):
        """A trailing COLNAME with no SORT should default to asc with warning."""
        node = _make_node(params={
            "CRITERIA": [
                {"elementRef": "COLNAME", "value": '"good_col"'},
                {"elementRef": "SORT", "value": "desc"},
                {"elementRef": "COLNAME", "value": '"orphan_col"'},
            ],
        })
        result = SortRowConverter().convert(node, [], {})

        cfg = result.component["config"]
        assert cfg["sort_columns"] == ["good_col", "orphan_col"]
        assert cfg["sort_orders"] == ["desc", "asc"]
        assert any("orphan_col" in w for w in result.warnings)

    def test_sort_without_colname(self):
        """A SORT without a preceding COLNAME is skipped with a warning."""
        node = _make_node(params={
            "CRITERIA": [
                {"elementRef": "SORT", "value": "asc"},
                {"elementRef": "COLNAME", "value": '"my_col"'},
                {"elementRef": "SORT", "value": "desc"},
            ],
        })
        result = SortRowConverter().convert(node, [], {})

        cfg = result.component["config"]
        assert cfg["sort_columns"] == ["my_col"]
        assert cfg["sort_orders"] == ["desc"]
        assert any("no preceding COLNAME" in w for w in result.warnings)

    def test_consecutive_colnames_without_sorts(self):
        """Two consecutive COLNAMEs: the first defaults to asc with warning."""
        node = _make_node(params={
            "CRITERIA": [
                {"elementRef": "COLNAME", "value": '"first"'},
                {"elementRef": "COLNAME", "value": '"second"'},
                {"elementRef": "SORT", "value": "desc"},
            ],
        })
        result = SortRowConverter().convert(node, [], {})

        cfg = result.component["config"]
        assert cfg["sort_columns"] == ["first", "second"]
        assert cfg["sort_orders"] == ["asc", "desc"]
        assert any("first" in w and "no matching SORT" in w for w in result.warnings)


class TestSortRowSchema:
    def test_transform_schema_passthrough(self):
        """SortRow passes the schema through: input == output."""
        node = _make_node(
            params={
                "CRITERIA": [
                    {"elementRef": "COLNAME", "value": '"id"'},
                    {"elementRef": "SORT", "value": "asc"},
                ],
            },
            schema=_make_schema_columns(),
        )
        result = SortRowConverter().convert(node, [], {})

        schema = result.component["schema"]
        assert schema["input"] == schema["output"]
        assert len(schema["input"]) == 3
        assert schema["input"][0]["name"] == "id"
        assert schema["input"][1]["name"] == "name"
        assert schema["input"][2]["name"] == "amount"

    def test_empty_schema(self):
        """When no FLOW schema is present, input and output are empty lists."""
        node = _make_node(params={
            "CRITERIA": [
                {"elementRef": "COLNAME", "value": '"id"'},
                {"elementRef": "SORT", "value": "asc"},
            ],
        })
        result = SortRowConverter().convert(node, [], {})

        schema = result.component["schema"]
        assert schema == {"input": [], "output": []}
