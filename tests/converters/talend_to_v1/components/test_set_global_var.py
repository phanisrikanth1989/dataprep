"""Tests for the SetGlobalVarConverter (tSetGlobalVar -> SetGlobalVar)."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.file.set_global_var import (
    SetGlobalVarConverter,
)
from src.converters.talend_to_v1.components.registry import REGISTRY


def _make_node(params=None, component_id="sgv_1",
               component_type="tSetGlobalVar"):
    return TalendNode(
        component_id=component_id,
        component_type=component_type,
        params=params or {},
        schema={},
        position={"x": 100, "y": 200},
        raw_xml=ET.Element("node"),
    )


class TestSetGlobalVarRegistration:
    def test_registered_in_registry(self):
        assert REGISTRY.get("tSetGlobalVar") is SetGlobalVarConverter


class TestSetGlobalVarBasic:
    def test_single_variable(self):
        node = _make_node(params={
            "VARIABLES": [
                {"elementRef": "KEY", "value": '"myVar"'},
                {"elementRef": "VALUE", "value": '"hello"'},
            ],
        })
        result = SetGlobalVarConverter().convert(node, [], {})

        assert isinstance(result, ComponentResult)
        comp = result.component
        assert comp["id"] == "sgv_1"
        assert comp["type"] == "SetGlobalVar"
        assert comp["original_type"] == "tSetGlobalVar"
        assert comp["position"] == {"x": 100, "y": 200}
        assert comp["config"]["variables"] == [
            {"name": "myVar", "value": "hello"},
        ]
        assert comp["schema"] == {"input": [], "output": []}
        assert comp["inputs"] == []
        assert comp["outputs"] == []
        assert result.warnings == []

    def test_multiple_variables(self):
        node = _make_node(params={
            "VARIABLES": [
                {"elementRef": "KEY", "value": '"var1"'},
                {"elementRef": "VALUE", "value": '"value1"'},
                {"elementRef": "KEY", "value": '"var2"'},
                {"elementRef": "VALUE", "value": '"value2"'},
                {"elementRef": "KEY", "value": '"var3"'},
                {"elementRef": "VALUE", "value": '"value3"'},
            ],
        })
        result = SetGlobalVarConverter().convert(node, [], {})

        variables = result.component["config"]["variables"]
        assert len(variables) == 3
        assert variables[0] == {"name": "var1", "value": "value1"}
        assert variables[1] == {"name": "var2", "value": "value2"}
        assert variables[2] == {"name": "var3", "value": "value3"}
        assert result.warnings == []

    def test_expression_values(self):
        """Values may contain Talend expressions or Java code."""
        node = _make_node(params={
            "VARIABLES": [
                {"elementRef": "KEY", "value": '"runDate"'},
                {"elementRef": "VALUE", "value": '"TalendDate.getDate()"'},
                {"elementRef": "KEY", "value": '"count"'},
                {"elementRef": "VALUE", "value": '"(Integer)globalMap.get(\"row_count\")"'},
            ],
        })
        result = SetGlobalVarConverter().convert(node, [], {})

        variables = result.component["config"]["variables"]
        assert len(variables) == 2
        assert variables[0] == {
            "name": "runDate",
            "value": "TalendDate.getDate()",
        }
        assert variables[1]["name"] == "count"
        assert "globalMap" in variables[1]["value"]


class TestSetGlobalVarEmptyAndMissing:
    def test_empty_variables_list(self):
        node = _make_node(params={"VARIABLES": []})
        result = SetGlobalVarConverter().convert(node, [], {})

        assert result.component["config"]["variables"] == []
        assert any("No variables defined" in w for w in result.warnings)

    def test_missing_variables_param(self):
        node = _make_node(params={})
        result = SetGlobalVarConverter().convert(node, [], {})

        assert result.component["config"]["variables"] == []
        assert any("No variables defined" in w for w in result.warnings)

    def test_variables_not_a_list(self):
        """If VARIABLES is not a list (unexpected), produce a warning."""
        node = _make_node(params={"VARIABLES": "not_a_list"})
        result = SetGlobalVarConverter().convert(node, [], {})

        assert result.component["config"]["variables"] == []
        assert any("not a list" in w for w in result.warnings)


class TestSetGlobalVarUnpairedEntries:
    def test_key_without_value(self):
        """A trailing KEY with no VALUE is skipped with a warning."""
        node = _make_node(params={
            "VARIABLES": [
                {"elementRef": "KEY", "value": '"goodVar"'},
                {"elementRef": "VALUE", "value": '"goodVal"'},
                {"elementRef": "KEY", "value": '"orphanKey"'},
            ],
        })
        result = SetGlobalVarConverter().convert(node, [], {})

        variables = result.component["config"]["variables"]
        assert len(variables) == 1
        assert variables[0] == {"name": "goodVar", "value": "goodVal"}
        assert any("orphanKey" in w for w in result.warnings)

    def test_value_without_key(self):
        """A VALUE without a preceding KEY is skipped with a warning."""
        node = _make_node(params={
            "VARIABLES": [
                {"elementRef": "VALUE", "value": '"orphanVal"'},
                {"elementRef": "KEY", "value": '"myKey"'},
                {"elementRef": "VALUE", "value": '"myVal"'},
            ],
        })
        result = SetGlobalVarConverter().convert(node, [], {})

        variables = result.component["config"]["variables"]
        assert len(variables) == 1
        assert variables[0] == {"name": "myKey", "value": "myVal"}
        assert any("orphanVal" in w for w in result.warnings)

    def test_consecutive_keys_without_values(self):
        """Two consecutive KEYs: the first is skipped with a warning."""
        node = _make_node(params={
            "VARIABLES": [
                {"elementRef": "KEY", "value": '"first"'},
                {"elementRef": "KEY", "value": '"second"'},
                {"elementRef": "VALUE", "value": '"val"'},
            ],
        })
        result = SetGlobalVarConverter().convert(node, [], {})

        variables = result.component["config"]["variables"]
        assert len(variables) == 1
        assert variables[0] == {"name": "second", "value": "val"}
        assert any("first" in w and "no matching VALUE" in w for w in result.warnings)


class TestSetGlobalVarSchema:
    def test_utility_component_has_empty_schema(self):
        """SetGlobalVar is a utility component with no data flow schema."""
        node = _make_node(params={
            "VARIABLES": [
                {"elementRef": "KEY", "value": '"x"'},
                {"elementRef": "VALUE", "value": '"1"'},
            ],
        })
        result = SetGlobalVarConverter().convert(node, [], {})

        assert result.component["schema"] == {"input": [], "output": []}
