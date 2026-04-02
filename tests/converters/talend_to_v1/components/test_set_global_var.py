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


def _make_node(params=None, schema=None, component_id="sgv_1",
               component_type="tSetGlobalVar"):
    return TalendNode(
        component_id=component_id,
        component_type=component_type,
        params=params or {},
        schema=schema or {},
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
        assert comp["inputs"] == []
        assert comp["outputs"] == []
        # No Java/context warnings for plain values
        assert not any("Java expression" in w for w in result.warnings)
        assert not any("context reference" in w for w in result.warnings)
        # needs_review always has the casing mismatch
        assert isinstance(result.needs_review, list)
        assert len(result.needs_review) >= 1

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
        # Only structural warnings should be absent for clean data
        assert not any("no matching VALUE" in w for w in result.warnings)
        assert isinstance(result.needs_review, list)

    def test_expression_values(self):
        """Values may contain Talend expressions or Java code."""
        node = _make_node(params={
            "VARIABLES": [
                {"elementRef": "KEY", "value": '"runDate"'},
                {"elementRef": "VALUE", "value": '"TalendDate.getDate()"'},
                {"elementRef": "KEY", "value": '"count"'},
                {"elementRef": "VALUE", "value": '"(Integer)globalMap.get(\\"row_count\\")"'},
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
        assert isinstance(result.needs_review, list)


class TestSetGlobalVarConfigKeys:
    def test_all_config_keys_present(self):
        """Exactly 3 config keys should be present."""
        node = _make_node(params={
            "VARIABLES": [
                {"elementRef": "KEY", "value": '"k"'},
                {"elementRef": "VALUE", "value": '"v"'},
            ],
            "TSTATCATCHER_STATS": "true",
            "LABEL": '"my_label"',
        })
        result = SetGlobalVarConverter().convert(node, [], {})
        cfg = result.component["config"]

        assert set(cfg.keys()) == {"variables", "tstatcatcher_stats", "label"}
        assert cfg["tstatcatcher_stats"] is True
        assert cfg["label"] == "my_label"

    def test_defaults_include_new_params(self):
        """New params default correctly when not in XML."""
        node = _make_node(params={
            "VARIABLES": [
                {"elementRef": "KEY", "value": '"k"'},
                {"elementRef": "VALUE", "value": '"v"'},
            ],
        })
        result = SetGlobalVarConverter().convert(node, [], {})
        cfg = result.component["config"]

        assert cfg["tstatcatcher_stats"] is False
        assert cfg["label"] == ""


class TestSetGlobalVarEmptyAndMissing:
    def test_empty_variables_list(self):
        node = _make_node(params={"VARIABLES": []})
        result = SetGlobalVarConverter().convert(node, [], {})

        assert result.component["config"]["variables"] == []
        assert any("No variables defined" in w for w in result.warnings)
        assert isinstance(result.needs_review, list)

    def test_missing_variables_param(self):
        node = _make_node(params={})
        result = SetGlobalVarConverter().convert(node, [], {})

        assert result.component["config"]["variables"] == []
        assert any("No variables defined" in w for w in result.warnings)
        assert isinstance(result.needs_review, list)

    def test_variables_not_a_list(self):
        """If VARIABLES is not a list (unexpected), produce a warning."""
        node = _make_node(params={"VARIABLES": "not_a_list"})
        result = SetGlobalVarConverter().convert(node, [], {})

        assert result.component["config"]["variables"] == []
        assert any("not a list" in w for w in result.warnings)
        assert isinstance(result.needs_review, list)


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
        assert isinstance(result.needs_review, list)

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
        assert isinstance(result.needs_review, list)

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
        assert isinstance(result.needs_review, list)


class TestSetGlobalVarSchema:
    def test_utility_component_has_empty_schema(self):
        """SetGlobalVar is a utility component with empty schema (matches tWarn, tDie pattern)."""
        node = _make_node(params={
            "VARIABLES": [
                {"elementRef": "KEY", "value": '"x"'},
                {"elementRef": "VALUE", "value": '"1"'},
            ],
        })
        result = SetGlobalVarConverter().convert(node, [], {})

        assert result.component["schema"] == {"input": [], "output": []}


class TestSetGlobalVarEngineGapWarnings:
    def test_needs_review_casing_mismatch(self):
        """Unconditional needs_review entry about VARIABLES casing mismatch."""
        node = _make_node(params={
            "VARIABLES": [
                {"elementRef": "KEY", "value": '"k"'},
                {"elementRef": "VALUE", "value": '"v"'},
            ],
        })
        result = SetGlobalVarConverter().convert(node, [], {})

        assert isinstance(result.needs_review, list)
        assert len(result.needs_review) >= 1
        review_text = str(result.needs_review)
        assert "variables" in review_text.lower() and "VARIABLES" in review_text

    def test_engine_gap_warning_nb_line(self):
        """Unconditional warning about NB_LINE always being 0."""
        node = _make_node(params={
            "VARIABLES": [
                {"elementRef": "KEY", "value": '"k"'},
                {"elementRef": "VALUE", "value": '"v"'},
            ],
        })
        result = SetGlobalVarConverter().convert(node, [], {})

        assert any("NB_LINE" in w for w in result.warnings)

    def test_java_expression_warning_get(self):
        """Variable with .get( pattern triggers Java expression warning."""
        node = _make_node(params={
            "VARIABLES": [
                {"elementRef": "KEY", "value": '"count"'},
                {"elementRef": "VALUE", "value": '"(Integer)globalMap.get(\\"row_count\\")"'},
            ],
        })
        result = SetGlobalVarConverter().convert(node, [], {})

        assert any("Java expression" in w for w in result.warnings)

    def test_java_expression_warning_equals(self):
        """Variable with .equals( pattern triggers Java expression warning."""
        node = _make_node(params={
            "VARIABLES": [
                {"elementRef": "KEY", "value": '"flag"'},
                {"elementRef": "VALUE", "value": '"status.equals(\\"DONE\\")"'},
            ],
        })
        result = SetGlobalVarConverter().convert(node, [], {})

        assert any("Java expression" in w for w in result.warnings)

    def test_java_expression_warning_ternary(self):
        """Variable with ternary pattern triggers Java expression warning."""
        node = _make_node(params={
            "VARIABLES": [
                {"elementRef": "KEY", "value": '"mode"'},
                {"elementRef": "VALUE", "value": '"x > 0 ? \\"positive\\" : \\"negative\\""'},
            ],
        })
        result = SetGlobalVarConverter().convert(node, [], {})

        assert any("Java expression" in w for w in result.warnings)

    def test_java_expression_warning_cast(self):
        """Variable with (( cast pattern triggers Java expression warning."""
        node = _make_node(params={
            "VARIABLES": [
                {"elementRef": "KEY", "value": '"val"'},
                {"elementRef": "VALUE", "value": '"((String)globalMap.get(\\"key\\"))"'},
            ],
        })
        result = SetGlobalVarConverter().convert(node, [], {})

        assert any("Java expression" in w for w in result.warnings)

    def test_no_java_warning_for_new_prefix(self):
        """Variable starting with 'new ' does NOT trigger warning (engine handles it)."""
        node = _make_node(params={
            "VARIABLES": [
                {"elementRef": "KEY", "value": '"date"'},
                {"elementRef": "VALUE", "value": '"new java.util.Date()"'},
            ],
        })
        result = SetGlobalVarConverter().convert(node, [], {})

        assert not any("Java expression" in w for w in result.warnings)

    def test_no_java_warning_for_plain_string(self):
        """Plain string values don't trigger Java expression warning."""
        node = _make_node(params={
            "VARIABLES": [
                {"elementRef": "KEY", "value": '"name"'},
                {"elementRef": "VALUE", "value": '"hello world"'},
            ],
        })
        result = SetGlobalVarConverter().convert(node, [], {})

        assert not any("Java expression" in w for w in result.warnings)

    def test_context_reference_warning(self):
        """Variable with context.xxx triggers context reference warning."""
        node = _make_node(params={
            "VARIABLES": [
                {"elementRef": "KEY", "value": '"env"'},
                {"elementRef": "VALUE", "value": '"context.environment"'},
            ],
        })
        result = SetGlobalVarConverter().convert(node, [], {})

        assert any("context reference" in w for w in result.warnings)

    def test_no_context_warning_for_plain_values(self):
        """Plain string values don't trigger context reference warning."""
        node = _make_node(params={
            "VARIABLES": [
                {"elementRef": "KEY", "value": '"env"'},
                {"elementRef": "VALUE", "value": '"production"'},
            ],
        })
        result = SetGlobalVarConverter().convert(node, [], {})

        assert not any("context reference" in w for w in result.warnings)


class TestSetGlobalVarComponentStructure:
    def test_component_dict_structure(self):
        """Output dict has all required top-level keys."""
        node = _make_node(params={
            "VARIABLES": [
                {"elementRef": "KEY", "value": '"k"'},
                {"elementRef": "VALUE", "value": '"v"'},
            ],
        })
        result = SetGlobalVarConverter().convert(node, [], {})
        comp = result.component
        expected_keys = {"id", "type", "original_type", "position", "config", "schema", "inputs", "outputs"}
        assert set(comp.keys()) == expected_keys

    def test_result_type(self):
        """convert() returns a ComponentResult."""
        node = _make_node(params={
            "VARIABLES": [
                {"elementRef": "KEY", "value": '"k"'},
                {"elementRef": "VALUE", "value": '"v"'},
            ],
        })
        result = SetGlobalVarConverter().convert(node, [], {})
        assert isinstance(result, ComponentResult)
