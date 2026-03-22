"""Tests for tFilterRow / tFilterRows -> FilterRows converter."""
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
                {"elementRef": "OPERATOR", "value": ">"},
                {"elementRef": "RVALUE", "value": "18"},
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
        assert cfg["conditions"][0] == {"column": "age", "operator": ">", "value": "18"}

    def test_conditions_parsing_multiple(self):
        """Multiple CONDITIONS rows are parsed into condition dicts."""
        node = _make_node(params={
            "LOGICAL_OP": "&&",
            "CONDITIONS": [
                {"elementRef": "INPUT_COLUMN", "value": "status"},
                {"elementRef": "OPERATOR", "value": "=="},
                {"elementRef": "RVALUE", "value": '"active"'},
                {"elementRef": "INPUT_COLUMN", "value": "score"},
                {"elementRef": "OPERATOR", "value": ">="},
                {"elementRef": "RVALUE", "value": "50"},
                {"elementRef": "INPUT_COLUMN", "value": "name"},
                {"elementRef": "OPERATOR", "value": "!="},
                {"elementRef": "RVALUE", "value": '""'},
            ],
        })
        result = FilterRowsConverter().convert(node, [], {})
        conditions = result.component["config"]["conditions"]

        assert len(conditions) == 3
        assert conditions[0] == {"column": "status", "operator": "==", "value": '"active"'}
        assert conditions[1] == {"column": "score", "operator": ">=", "value": "50"}
        assert conditions[2] == {"column": "name", "operator": "!=", "value": '""'}

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
