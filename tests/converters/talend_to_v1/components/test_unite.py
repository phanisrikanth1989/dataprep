"""Tests for the UniteConverter (tUnite -> Unite).

Includes a regression test verifying that the old indentation bug
(REMOVE_DUPLICATES check outside the for-loop) is fixed.
"""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.transform.unite import UniteConverter
from src.converters.talend_to_v1.components.registry import REGISTRY


def _make_node(params=None, schema=None, component_id="unite_1",
               component_type="tUnite"):
    return TalendNode(
        component_id=component_id,
        component_type=component_type,
        params=params or {},
        schema=schema or {},
        position={"x": 300, "y": 400},
        raw_xml=ET.Element("node"),
    )


def _make_schema():
    """Return a simple FLOW schema with two columns."""
    return {
        "FLOW": [
            SchemaColumn(name="id", type="id_Integer", nullable=False, key=True),
            SchemaColumn(name="name", type="id_String", nullable=True),
        ]
    }


class TestUniteConverterRegistration:
    def test_registered_in_registry(self):
        assert REGISTRY.get("tUnite") is UniteConverter


class TestUniteConverterBasic:
    def test_basic_conversion_defaults(self):
        """Default: no params -> remove_duplicates=False, mode=UNION."""
        node = _make_node()
        result = UniteConverter().convert(node, [], {})

        assert isinstance(result, ComponentResult)
        comp = result.component
        assert comp["id"] == "unite_1"
        assert comp["type"] == "Unite"
        assert comp["original_type"] == "tUnite"
        assert comp["position"] == {"x": 300, "y": 400}
        assert comp["config"]["remove_duplicates"] is False
        assert comp["config"]["mode"] == "UNION"
        assert comp["inputs"] == []
        assert comp["outputs"] == []

    def test_remove_duplicates_true(self):
        node = _make_node(params={
            "REMOVE_DUPLICATES": "true",
        })
        result = UniteConverter().convert(node, [], {})

        assert result.component["config"]["remove_duplicates"] is True

    def test_remove_duplicates_false_explicit(self):
        node = _make_node(params={
            "REMOVE_DUPLICATES": "false",
        })
        result = UniteConverter().convert(node, [], {})

        assert result.component["config"]["remove_duplicates"] is False

    def test_custom_mode(self):
        node = _make_node(params={
            "MODE": '"MERGE"',
        })
        result = UniteConverter().convert(node, [], {})

        assert result.component["config"]["mode"] == "MERGE"

    def test_all_params_together(self):
        node = _make_node(params={
            "REMOVE_DUPLICATES": "true",
            "MODE": '"INTERSECT"',
        })
        result = UniteConverter().convert(node, [], {})

        assert result.component["config"]["remove_duplicates"] is True
        assert result.component["config"]["mode"] == "INTERSECT"


class TestUniteConverterSchema:
    def test_schema_parsed_from_flow(self):
        node = _make_node(schema=_make_schema())
        result = UniteConverter().convert(node, [], {})

        schema = result.component["schema"]
        assert len(schema["input"]) == 2
        assert len(schema["output"]) == 2
        assert schema["input"][0]["name"] == "id"
        assert schema["input"][1]["name"] == "name"
        # Input and output schemas should be equal for Unite
        assert schema["input"] == schema["output"]

    def test_empty_schema_when_no_flow(self):
        node = _make_node(schema={})
        result = UniteConverter().convert(node, [], {})

        assert result.component["schema"]["input"] == []
        assert result.component["schema"]["output"] == []


class TestUniteConverterBugRegression:
    """Regression tests for the old indentation bug.

    The old code only checked the *last* parameter because the
    ``if name == 'REMOVE_DUPLICATES'`` was outside the for-loop.
    This meant that if REMOVE_DUPLICATES appeared before other params
    in the XML, it would be silently ignored.
    """

    def test_remove_duplicates_not_last_param_is_still_parsed(self):
        """The fixed code should pick up REMOVE_DUPLICATES regardless of order."""
        node = _make_node(params={
            "REMOVE_DUPLICATES": "true",
            "MODE": '"UNION"',
            "SOME_OTHER_PARAM": "xyz",
        })
        result = UniteConverter().convert(node, [], {})

        # With the old bug, this would have been False because the last
        # param iterated was not REMOVE_DUPLICATES.
        assert result.component["config"]["remove_duplicates"] is True

    def test_both_params_parsed_regardless_of_iteration_order(self):
        """Both config params must be extracted from the dict."""
        node = _make_node(params={
            "SOME_OTHER_PARAM": "abc",
            "REMOVE_DUPLICATES": "true",
            "MODE": '"MERGE"',
            "YET_ANOTHER": "123",
        })
        result = UniteConverter().convert(node, [], {})

        assert result.component["config"]["remove_duplicates"] is True
        assert result.component["config"]["mode"] == "MERGE"


class TestUniteConverterWarnings:
    def test_no_warnings_by_default(self):
        node = _make_node(params={
            "REMOVE_DUPLICATES": "false",
            "MODE": '"UNION"',
        })
        result = UniteConverter().convert(node, [], {})

        assert result.warnings == []
        assert result.needs_review == []
