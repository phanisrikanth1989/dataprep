"""Tests for the JoinConverter (tJoin -> Join).

Covers JOIN_KEY TABLE parsing (flat elementRef/value pairs grouped into
{main, lookup} dicts), boolean config params, schema passthrough,
edge cases (empty keys, unpaired entries), and registry integration.
"""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.transform.join import JoinConverter
from src.converters.talend_to_v1.components.registry import REGISTRY


def _make_node(params=None, schema=None, component_id="join_1",
               component_type="tJoin"):
    return TalendNode(
        component_id=component_id,
        component_type=component_type,
        params=params or {},
        schema=schema or {},
        position={"x": 400, "y": 500},
        raw_xml=ET.Element("node"),
    )


def _make_schema():
    """Return a simple FLOW schema with three columns."""
    return {
        "FLOW": [
            SchemaColumn(name="id", type="id_Integer", nullable=False, key=True),
            SchemaColumn(name="name", type="id_String", nullable=True),
            SchemaColumn(name="amount", type="id_Double", nullable=True),
        ]
    }


class TestJoinConverterRegistration:
    def test_registered_in_registry(self):
        assert REGISTRY.get("tJoin") is JoinConverter


class TestJoinConverterBasic:
    def test_single_join_key(self):
        """Single LEFT_COLUMN/RIGHT_COLUMN pair produces one join key."""
        node = _make_node(params={
            "JOIN_KEY": [
                {"elementRef": "LEFT_COLUMN", "value": '"employee_id"'},
                {"elementRef": "RIGHT_COLUMN", "value": '"emp_id"'},
            ],
            "USE_INNER_JOIN": "true",
            "CASE_SENSITIVE": "true",
            "DIE_ON_ERROR": "false",
        })
        result = JoinConverter().convert(node, [], {})

        assert isinstance(result, ComponentResult)
        comp = result.component
        assert comp["id"] == "join_1"
        assert comp["type"] == "Join"
        assert comp["original_type"] == "tJoin"
        assert comp["position"] == {"x": 400, "y": 500}
        assert comp["config"]["join_keys"] == [
            {"main": "employee_id", "lookup": "emp_id"},
        ]
        assert comp["config"]["use_inner_join"] is True
        assert comp["config"]["case_sensitive"] is True
        assert comp["config"]["die_on_error"] is False
        assert comp["inputs"] == []
        assert comp["outputs"] == []
        assert result.warnings == []

    def test_multiple_join_keys(self):
        """Multiple LEFT/RIGHT pairs are grouped correctly."""
        node = _make_node(params={
            "JOIN_KEY": [
                {"elementRef": "LEFT_COLUMN", "value": '"dept_id"'},
                {"elementRef": "RIGHT_COLUMN", "value": '"department_id"'},
                {"elementRef": "LEFT_COLUMN", "value": '"region"'},
                {"elementRef": "RIGHT_COLUMN", "value": '"region_code"'},
                {"elementRef": "LEFT_COLUMN", "value": '"year"'},
                {"elementRef": "RIGHT_COLUMN", "value": '"fiscal_year"'},
            ],
        })
        result = JoinConverter().convert(node, [], {})

        keys = result.component["config"]["join_keys"]
        assert len(keys) == 3
        assert keys[0] == {"main": "dept_id", "lookup": "department_id"}
        assert keys[1] == {"main": "region", "lookup": "region_code"}
        assert keys[2] == {"main": "year", "lookup": "fiscal_year"}
        assert result.warnings == []

    def test_alternative_ref_names(self):
        """INPUT_COLUMN and LOOKUP_COLUMN are accepted as aliases."""
        node = _make_node(params={
            "JOIN_KEY": [
                {"elementRef": "INPUT_COLUMN", "value": '"col_a"'},
                {"elementRef": "LOOKUP_COLUMN", "value": '"col_b"'},
            ],
        })
        result = JoinConverter().convert(node, [], {})

        keys = result.component["config"]["join_keys"]
        assert keys == [{"main": "col_a", "lookup": "col_b"}]
        assert result.warnings == []


class TestJoinConverterDefaults:
    def test_default_boolean_params(self):
        """When no boolean params are set, defaults apply."""
        node = _make_node(params={
            "JOIN_KEY": [
                {"elementRef": "LEFT_COLUMN", "value": '"id"'},
                {"elementRef": "RIGHT_COLUMN", "value": '"id"'},
            ],
        })
        result = JoinConverter().convert(node, [], {})

        cfg = result.component["config"]
        assert cfg["use_inner_join"] is False
        assert cfg["case_sensitive"] is True
        assert cfg["die_on_error"] is False

    def test_all_booleans_true(self):
        node = _make_node(params={
            "JOIN_KEY": [
                {"elementRef": "LEFT_COLUMN", "value": '"id"'},
                {"elementRef": "RIGHT_COLUMN", "value": '"id"'},
            ],
            "USE_INNER_JOIN": "true",
            "CASE_SENSITIVE": "true",
            "DIE_ON_ERROR": "true",
        })
        result = JoinConverter().convert(node, [], {})

        cfg = result.component["config"]
        assert cfg["use_inner_join"] is True
        assert cfg["case_sensitive"] is True
        assert cfg["die_on_error"] is True

    def test_case_sensitive_false(self):
        node = _make_node(params={
            "JOIN_KEY": [
                {"elementRef": "LEFT_COLUMN", "value": '"id"'},
                {"elementRef": "RIGHT_COLUMN", "value": '"id"'},
            ],
            "CASE_SENSITIVE": "false",
        })
        result = JoinConverter().convert(node, [], {})

        assert result.component["config"]["case_sensitive"] is False


class TestJoinConverterEmptyAndMissing:
    def test_empty_join_key_list(self):
        """Empty JOIN_KEY list produces a warning."""
        node = _make_node(params={"JOIN_KEY": []})
        result = JoinConverter().convert(node, [], {})

        cfg = result.component["config"]
        assert cfg["join_keys"] == []
        assert any("No join keys" in w for w in result.warnings)

    def test_missing_join_key_param(self):
        """Missing JOIN_KEY param produces a warning."""
        node = _make_node(params={})
        result = JoinConverter().convert(node, [], {})

        cfg = result.component["config"]
        assert cfg["join_keys"] == []
        assert any("No join keys" in w for w in result.warnings)

    def test_join_key_not_a_list(self):
        """Non-list JOIN_KEY param produces a warning."""
        node = _make_node(params={"JOIN_KEY": "not_a_list"})
        result = JoinConverter().convert(node, [], {})

        cfg = result.component["config"]
        assert cfg["join_keys"] == []
        assert any("not a list" in w for w in result.warnings)


class TestJoinConverterUnpairedEntries:
    def test_left_column_without_right(self):
        """Trailing LEFT_COLUMN with no RIGHT_COLUMN is skipped with warning."""
        node = _make_node(params={
            "JOIN_KEY": [
                {"elementRef": "LEFT_COLUMN", "value": '"good_left"'},
                {"elementRef": "RIGHT_COLUMN", "value": '"good_right"'},
                {"elementRef": "LEFT_COLUMN", "value": '"orphan_left"'},
            ],
        })
        result = JoinConverter().convert(node, [], {})

        keys = result.component["config"]["join_keys"]
        assert len(keys) == 1
        assert keys[0] == {"main": "good_left", "lookup": "good_right"}
        assert any("orphan_left" in w for w in result.warnings)

    def test_consecutive_left_columns(self):
        """Two consecutive LEFT_COLUMNs: first is skipped with warning."""
        node = _make_node(params={
            "JOIN_KEY": [
                {"elementRef": "LEFT_COLUMN", "value": '"first_left"'},
                {"elementRef": "LEFT_COLUMN", "value": '"second_left"'},
                {"elementRef": "RIGHT_COLUMN", "value": '"right_col"'},
            ],
        })
        result = JoinConverter().convert(node, [], {})

        keys = result.component["config"]["join_keys"]
        assert len(keys) == 1
        assert keys[0] == {"main": "second_left", "lookup": "right_col"}
        assert any("first_left" in w for w in result.warnings)

    def test_right_column_without_left(self):
        """A RIGHT_COLUMN appearing before any LEFT_COLUMN is skipped with warning."""
        node = _make_node(params={
            "JOIN_KEY": [
                {"elementRef": "RIGHT_COLUMN", "value": '"orphan_right"'},
                {"elementRef": "LEFT_COLUMN", "value": '"left_col"'},
                {"elementRef": "RIGHT_COLUMN", "value": '"right_col"'},
            ],
        })
        result = JoinConverter().convert(node, [], {})

        keys = result.component["config"]["join_keys"]
        assert len(keys) == 1
        assert keys[0] == {"main": "left_col", "lookup": "right_col"}
        assert any("orphan_right" in w for w in result.warnings)


class TestJoinConverterSchema:
    def test_schema_passthrough(self):
        """Join passes schema through: input == output."""
        node = _make_node(
            params={
                "JOIN_KEY": [
                    {"elementRef": "LEFT_COLUMN", "value": '"id"'},
                    {"elementRef": "RIGHT_COLUMN", "value": '"id"'},
                ],
            },
            schema=_make_schema(),
        )
        result = JoinConverter().convert(node, [], {})

        schema = result.component["schema"]
        assert schema["input"] == schema["output"]
        assert len(schema["input"]) == 3
        assert schema["input"][0]["name"] == "id"
        assert schema["input"][1]["name"] == "name"
        assert schema["input"][2]["name"] == "amount"

    def test_empty_schema(self):
        """When no FLOW schema is present, input and output are empty lists."""
        node = _make_node(params={
            "JOIN_KEY": [
                {"elementRef": "LEFT_COLUMN", "value": '"id"'},
                {"elementRef": "RIGHT_COLUMN", "value": '"id"'},
            ],
        })
        result = JoinConverter().convert(node, [], {})

        schema = result.component["schema"]
        assert schema == {"input": [], "output": []}


class TestJoinConverterWarnings:
    def test_no_warnings_for_valid_config(self):
        node = _make_node(params={
            "JOIN_KEY": [
                {"elementRef": "LEFT_COLUMN", "value": '"id"'},
                {"elementRef": "RIGHT_COLUMN", "value": '"id"'},
            ],
            "USE_INNER_JOIN": "true",
            "CASE_SENSITIVE": "true",
            "DIE_ON_ERROR": "false",
        })
        result = JoinConverter().convert(node, [], {})

        assert result.warnings == []
        assert result.needs_review == []
