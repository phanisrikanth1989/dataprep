"""Tests for tFilterRow / tFilterRows -> FilterRows converter."""
import pytest
from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendNode,
)
from src.converters.talend_to_v1.components.transform.filter_rows import (
    FilterRowsConverter,
)


def _make_node(params=None, schema=None, component_type="tFilterRow"):
    return TalendNode(
        component_id=f"{component_type}_1",
        component_type=component_type,
        params=params or {},
        schema=schema or {},
        position={"x": 200, "y": 300},
    )


class TestFilterRowsConverter:
    """Tests for FilterRowsConverter."""

    def test_basic_config(self):
        """Config params are extracted correctly."""
        node = _make_node(params={
            "LOGICAL_OP": "&&",
            "USE_ADVANCED": "false",
            "ADVANCED_COND": "",
            "CONDITIONS": [
                {"elementRef": "INPUT_COLUMN", "value": "age"},
                {"elementRef": "FUNCTION", "value": "EMPTY"},
                {"elementRef": "OPERATOR", "value": ">"},
                {"elementRef": "RVALUE", "value": "18"},
                {"elementRef": "PREFILTER", "value": ""},
            ],
        })
        result = FilterRowsConverter().convert(node, [], {})
        comp = result.component

        assert comp["type"] == "FilterRows"
        assert comp["original_type"] == "tFilterRow"
        assert comp["id"] == "tFilterRow_1"
        assert comp["position"] == {"x": 200, "y": 300}

        cfg = comp["config"]
        assert cfg["logical_operator"] == "AND"
        assert cfg["use_advanced"] is False
        assert cfg["advanced_condition"] == ""
        assert len(cfg["conditions"]) == 1
        assert cfg["conditions"][0] == {
            "column": "age", "function": "EMPTY", "operator": ">", "value": "18", "prefilter": ""
        }

    def test_conditions_parsing_multiple(self):
        """Multiple CONDITIONS rows are parsed into condition dicts."""
        node = _make_node(params={
            "LOGICAL_OP": "&&",
            "CONDITIONS": [
                {"elementRef": "INPUT_COLUMN", "value": "status"},
                {"elementRef": "FUNCTION", "value": "EMPTY"},
                {"elementRef": "OPERATOR", "value": "=="},
                {"elementRef": "RVALUE", "value": '"active"'},
                {"elementRef": "PREFILTER", "value": ""},
                {"elementRef": "INPUT_COLUMN", "value": "score"},
                {"elementRef": "FUNCTION", "value": "EMPTY"},
                {"elementRef": "OPERATOR", "value": ">="},
                {"elementRef": "RVALUE", "value": "50"},
                {"elementRef": "PREFILTER", "value": ""},
                {"elementRef": "INPUT_COLUMN", "value": "name"},
                {"elementRef": "FUNCTION", "value": "EMPTY"},
                {"elementRef": "OPERATOR", "value": "!="},
                {"elementRef": "RVALUE", "value": '""'},
                {"elementRef": "PREFILTER", "value": ""},
            ],
        })
        result = FilterRowsConverter().convert(node, [], {})
        conditions = result.component["config"]["conditions"]

        assert len(conditions) == 3
        assert conditions[0] == {"column": "status", "function": "EMPTY", "operator": "==", "value": '"active"', "prefilter": ""}
        assert conditions[1] == {"column": "score", "function": "EMPTY", "operator": ">=", "value": "50", "prefilter": ""}
        assert conditions[2] == {"column": "name", "function": "EMPTY", "operator": "!=", "value": '""', "prefilter": ""}

    def test_advanced_mode(self):
        """When USE_ADVANCED is true, advanced_condition is captured."""
        node = _make_node(params={
            "USE_ADVANCED": "true",
            "ADVANCED_COND": 'row.age > 18 && row.status.equals("active")',
            "CONDITIONS": [],
        })
        result = FilterRowsConverter().convert(node, [], {})
        cfg = result.component["config"]

        assert cfg["use_advanced"] is True
        assert cfg["advanced_condition"] == 'row.age > 18 && row.status.equals("active")'
        assert cfg["conditions"] == []
        # No warning when advanced mode is on, even without conditions
        assert not any("no effect" in w.lower() for w in result.warnings)

    def test_defaults_when_params_missing(self):
        """Missing params fall back to sensible defaults and produce a warning."""
        node = _make_node(params={})
        result = FilterRowsConverter().convert(node, [], {})
        cfg = result.component["config"]

        assert cfg["logical_operator"] == "AND"
        assert cfg["use_advanced"] is False
        assert cfg["advanced_condition"] == ""
        assert cfg["conditions"] == []
        # Should warn about no conditions
        assert any("no effect" in w.lower() for w in result.warnings)

    def test_logical_op_or(self):
        """|| is cleaned up to OR."""
        node = _make_node(params={
            "LOGICAL_OP": "||",
            "CONDITIONS": [
                {"INPUT_COLUMN": "a", "OPERATOR": "==", "RVALUE": "1"},
            ],
        })
        result = FilterRowsConverter().convert(node, [], {})
        assert result.component["config"]["logical_operator"] == "OR"

    def test_logical_op_xml_escaped(self):
        """&amp;&amp; (XML-escaped AND) is cleaned up to AND."""
        node = _make_node(params={
            "LOGICAL_OP": "&amp;&amp;",
            "CONDITIONS": [
                {"INPUT_COLUMN": "x", "OPERATOR": ">", "RVALUE": "0"},
            ],
        })
        result = FilterRowsConverter().convert(node, [], {})
        assert result.component["config"]["logical_operator"] == "AND"

    def test_tfilterrow_registration(self):
        """The converter is registered under 'tFilterRow'."""
        from src.converters.talend_to_v1.components.registry import REGISTRY
        cls = REGISTRY.get("tFilterRow")
        assert cls is FilterRowsConverter

    def test_tfilterrows_registration(self):
        """The converter is registered under 'tFilterRows'."""
        from src.converters.talend_to_v1.components.registry import REGISTRY
        cls = REGISTRY.get("tFilterRows")
        assert cls is FilterRowsConverter

    def test_schema_passthrough(self):
        """FilterRows passes through schema: both input and output match."""
        node = _make_node(
            params={
                "CONDITIONS": [
                    {"INPUT_COLUMN": "id", "OPERATOR": "!=", "RVALUE": "0"},
                ],
            },
            schema={
                "FLOW": [
                    SchemaColumn(name="id", type="id_Integer", key=True, nullable=False),
                    SchemaColumn(name="name", type="id_String", length=50),
                ]
            },
        )
        result = FilterRowsConverter().convert(node, [], {})
        schema = result.component["schema"]

        assert schema["input"] == schema["output"]
        assert len(schema["output"]) == 2
        assert schema["output"][0]["name"] == "id"
        assert schema["output"][0]["key"] is True
        assert schema["output"][0]["nullable"] is False
        assert schema["output"][1]["name"] == "name"
        assert schema["output"][1]["length"] == 50

    def test_component_dict_structure(self):
        """Output dict has all required top-level keys."""
        node = _make_node(params={})
        result = FilterRowsConverter().convert(node, [], {})
        comp = result.component
        expected_keys = {"id", "type", "original_type", "position", "config", "schema", "inputs", "outputs"}
        assert set(comp.keys()) == expected_keys
        assert comp["inputs"] == []
        assert comp["outputs"] == []

    def test_result_type(self):
        """convert() returns a ComponentResult."""
        node = _make_node(params={})
        result = FilterRowsConverter().convert(node, [], {})
        assert isinstance(result, ComponentResult)

    def test_tfilterrows_component_type(self):
        """When using tFilterRows, original_type reflects that."""
        node = _make_node(
            params={
                "CONDITIONS": [
                    {"INPUT_COLUMN": "col", "OPERATOR": "==", "RVALUE": "1"},
                ],
            },
            component_type="tFilterRows",
        )
        result = FilterRowsConverter().convert(node, [], {})
        assert result.component["original_type"] == "tFilterRows"
        assert result.component["type"] == "FilterRows"
        assert result.component["id"] == "tFilterRows_1"


# ---------------------------------------------------------------------------
# Enhanced CONDITIONS + new params
# ---------------------------------------------------------------------------

class TestConditionsFunctionAndPrefilter:

    def test_function_extracted(self):
        node = _make_node(params={
            "CONDITIONS": [
                {"elementRef": "INPUT_COLUMN", "value": "name"},
                {"elementRef": "FUNCTION", "value": "LENGTH"},
                {"elementRef": "OPERATOR", "value": "<="},
                {"elementRef": "RVALUE", "value": "50"},
                {"elementRef": "PREFILTER", "value": ""},
            ],
        })
        result = FilterRowsConverter().convert(node, [], {})
        cond = result.component["config"]["conditions"][0]
        assert cond["function"] == "LENGTH"
        assert cond["prefilter"] == ""

    def test_function_empty_when_not_set(self):
        node = _make_node(params={
            "CONDITIONS": [
                {"elementRef": "INPUT_COLUMN", "value": "age"},
                {"elementRef": "FUNCTION", "value": "EMPTY"},
                {"elementRef": "OPERATOR", "value": ">"},
                {"elementRef": "RVALUE", "value": "18"},
                {"elementRef": "PREFILTER", "value": ""},
            ],
        })
        result = FilterRowsConverter().convert(node, [], {})
        cond = result.component["config"]["conditions"][0]
        assert cond["function"] == "EMPTY"

    def test_prefilter_extracted(self):
        node = _make_node(params={
            "CONDITIONS": [
                {"elementRef": "INPUT_COLUMN", "value": "status"},
                {"elementRef": "FUNCTION", "value": "EMPTY"},
                {"elementRef": "OPERATOR", "value": "=="},
                {"elementRef": "RVALUE", "value": '"active"'},
                {"elementRef": "PREFILTER", "value": "row.enabled == true"},
            ],
        })
        result = FilterRowsConverter().convert(node, [], {})
        cond = result.component["config"]["conditions"][0]
        assert cond["prefilter"] == "row.enabled == true"

    def test_multiple_conditions_with_all_fields(self):
        node = _make_node(params={
            "CONDITIONS": [
                {"elementRef": "INPUT_COLUMN", "value": "name"},
                {"elementRef": "FUNCTION", "value": "LENGTH"},
                {"elementRef": "OPERATOR", "value": ">"},
                {"elementRef": "RVALUE", "value": "0"},
                {"elementRef": "PREFILTER", "value": ""},
                {"elementRef": "INPUT_COLUMN", "value": "amount"},
                {"elementRef": "FUNCTION", "value": "ABS_VALUE"},
                {"elementRef": "OPERATOR", "value": ">="},
                {"elementRef": "RVALUE", "value": "100"},
                {"elementRef": "PREFILTER", "value": ""},
            ],
        })
        result = FilterRowsConverter().convert(node, [], {})
        conditions = result.component["config"]["conditions"]
        assert len(conditions) == 2
        assert conditions[0]["function"] == "LENGTH"
        assert conditions[1]["function"] == "ABS_VALUE"


class TestNewTopLevelParams:

    def test_die_on_error_default(self):
        node = _make_node()
        result = FilterRowsConverter().convert(node, [], {})
        assert result.component["config"]["die_on_error"] is False

    def test_die_on_error_extracted(self):
        node = _make_node(params={"DIE_ON_ERROR": True})
        result = FilterRowsConverter().convert(node, [], {})
        assert result.component["config"]["die_on_error"] is True

    def test_tstatcatcher_stats_default(self):
        node = _make_node()
        result = FilterRowsConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is False

    def test_label_default(self):
        node = _make_node()
        result = FilterRowsConverter().convert(node, [], {})
        assert result.component["config"]["label"] == ""


# ---------------------------------------------------------------------------
# Engine-gap warnings
# ---------------------------------------------------------------------------

class TestEngineGapWarnings:

    def test_no_engine_warnings_for_defaults(self):
        node = _make_node(params={
            "CONDITIONS": [
                {"elementRef": "INPUT_COLUMN", "value": "age"},
                {"elementRef": "FUNCTION", "value": "EMPTY"},
                {"elementRef": "OPERATOR", "value": ">"},
                {"elementRef": "RVALUE", "value": "18"},
                {"elementRef": "PREFILTER", "value": ""},
            ],
        })
        result = FilterRowsConverter().convert(node, [], {})
        engine_warnings = [w for w in result.warnings if "engine" in w.lower()]
        assert engine_warnings == []

    def test_warning_for_die_on_error(self):
        node = _make_node(params={"DIE_ON_ERROR": True})
        result = FilterRowsConverter().convert(node, [], {})
        assert any("DIE_ON_ERROR" in w for w in result.warnings)

    def test_warning_for_function_pre_transform(self):
        node = _make_node(params={
            "CONDITIONS": [
                {"elementRef": "INPUT_COLUMN", "value": "name"},
                {"elementRef": "FUNCTION", "value": "LENGTH"},
                {"elementRef": "OPERATOR", "value": ">"},
                {"elementRef": "RVALUE", "value": "0"},
                {"elementRef": "PREFILTER", "value": ""},
            ],
        })
        result = FilterRowsConverter().convert(node, [], {})
        assert any("FUNCTION" in w for w in result.warnings)

    def test_no_warning_for_function_empty(self):
        node = _make_node(params={
            "CONDITIONS": [
                {"elementRef": "INPUT_COLUMN", "value": "age"},
                {"elementRef": "FUNCTION", "value": "EMPTY"},
                {"elementRef": "OPERATOR", "value": ">"},
                {"elementRef": "RVALUE", "value": "18"},
                {"elementRef": "PREFILTER", "value": ""},
            ],
        })
        result = FilterRowsConverter().convert(node, [], {})
        assert not any("FUNCTION" in w for w in result.warnings)

    @pytest.mark.parametrize("operator", [
        "CONTAINS", "NOT_CONTAINS", "STARTS_WITH", "ENDS_WITH", "MATCH_REGEX",
    ])
    def test_warning_for_string_operators(self, operator):
        node = _make_node(params={
            "CONDITIONS": [
                {"elementRef": "INPUT_COLUMN", "value": "name"},
                {"elementRef": "FUNCTION", "value": "EMPTY"},
                {"elementRef": "OPERATOR", "value": operator},
                {"elementRef": "RVALUE", "value": '"test"'},
                {"elementRef": "PREFILTER", "value": ""},
            ],
        })
        result = FilterRowsConverter().convert(node, [], {})
        assert any("string operator" in w.lower() for w in result.warnings)

    def test_warning_for_prefilter(self):
        node = _make_node(params={
            "CONDITIONS": [
                {"elementRef": "INPUT_COLUMN", "value": "status"},
                {"elementRef": "FUNCTION", "value": "EMPTY"},
                {"elementRef": "OPERATOR", "value": "=="},
                {"elementRef": "RVALUE", "value": '"active"'},
                {"elementRef": "PREFILTER", "value": "row.enabled == true"},
            ],
        })
        result = FilterRowsConverter().convert(node, [], {})
        assert any("PREFILTER" in w for w in result.warnings)


# ---------------------------------------------------------------------------
# Component completeness
# ---------------------------------------------------------------------------

class TestComponentCompleteness:

    def test_all_7_config_keys_present(self):
        node = _make_node()
        result = FilterRowsConverter().convert(node, [], {})
        cfg = result.component["config"]
        expected_keys = {
            "logical_operator", "use_advanced", "advanced_condition",
            "conditions", "die_on_error", "tstatcatcher_stats", "label",
        }
        assert set(cfg.keys()) == expected_keys

    def test_conditions_have_5_fields(self):
        node = _make_node(params={
            "CONDITIONS": [
                {"elementRef": "INPUT_COLUMN", "value": "col"},
                {"elementRef": "FUNCTION", "value": "EMPTY"},
                {"elementRef": "OPERATOR", "value": "=="},
                {"elementRef": "RVALUE", "value": "1"},
                {"elementRef": "PREFILTER", "value": ""},
            ],
        })
        result = FilterRowsConverter().convert(node, [], {})
        cond = result.component["config"]["conditions"][0]
        assert set(cond.keys()) == {"column", "function", "operator", "value", "prefilter"}
