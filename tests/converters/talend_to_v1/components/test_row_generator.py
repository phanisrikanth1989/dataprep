"""Tests for the RowGeneratorConverter (tRowGenerator -> RowGenerator)."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendNode,
)
from src.converters.talend_to_v1.components.transform.row_generator import (
    RowGeneratorConverter,
)
from src.converters.talend_to_v1.components.registry import REGISTRY


def _make_node(params=None, schema=None, component_id="tRowGenerator_1",
               component_type="tRowGenerator"):
    return TalendNode(
        component_id=component_id,
        component_type=component_type,
        params=params or {},
        schema=schema or {},
        position={"x": 100, "y": 200},
        raw_xml=ET.Element("node"),
    )


def _make_output_schema():
    """Return a sample FLOW schema for testing."""
    return {
        "FLOW": [
            SchemaColumn(name="id", type="id_Integer", nullable=False, key=True),
            SchemaColumn(name="name", type="id_String", nullable=True, length=50),
            SchemaColumn(name="amount", type="id_Double", nullable=True, precision=2),
        ]
    }


# ------------------------------------------------------------------
# Registration
# ------------------------------------------------------------------
class TestRowGeneratorRegistration:
    def test_registered_in_registry(self):
        assert REGISTRY.get("tRowGenerator") is RowGeneratorConverter


# ------------------------------------------------------------------
# Basic / happy-path
# ------------------------------------------------------------------
class TestRowGeneratorBasic:
    def test_basic_config(self):
        """NB_ROWS and VALUES are extracted correctly."""
        node = _make_node(params={
            "NB_ROWS": "10",
            "VALUES": [
                {"elementRef": "SCHEMA_COLUMN", "value": '"id"'},
                {"elementRef": "ARRAY", "value": '"sequence(1,1,1)"'},
                {"elementRef": "SCHEMA_COLUMN", "value": '"name"'},
                {"elementRef": "ARRAY", "value": '"TalendDataGenerator.getFirstName()"'},
            ],
        })
        result = RowGeneratorConverter().convert(node, [], {})

        assert isinstance(result, ComponentResult)
        comp = result.component
        assert comp["id"] == "tRowGenerator_1"
        assert comp["type"] == "RowGenerator"
        assert comp["original_type"] == "tRowGenerator"
        assert comp["position"] == {"x": 100, "y": 200}

        cfg = comp["config"]
        assert cfg["nb_rows"] == 10
        assert cfg["values"] == [
            {"schema_column": "id", "array": "sequence(1,1,1)"},
            {"schema_column": "name", "array": "TalendDataGenerator.getFirstName()"},
        ]
        assert comp["inputs"] == []
        assert comp["outputs"] == []
        assert result.warnings == []

    def test_single_value_pair(self):
        """A single SCHEMA_COLUMN/ARRAY pair works correctly."""
        node = _make_node(params={
            "NB_ROWS": "1",
            "VALUES": [
                {"elementRef": "SCHEMA_COLUMN", "value": '"col1"'},
                {"elementRef": "ARRAY", "value": '"constant_val"'},
            ],
        })
        result = RowGeneratorConverter().convert(node, [], {})
        cfg = result.component["config"]

        assert cfg["nb_rows"] == 1
        assert cfg["values"] == [
            {"schema_column": "col1", "array": "constant_val"},
        ]
        assert result.warnings == []

    def test_nb_rows_integer_param(self):
        """NB_ROWS provided as actual int (not string) is handled."""
        node = _make_node(params={"NB_ROWS": 50})
        result = RowGeneratorConverter().convert(node, [], {})
        assert result.component["config"]["nb_rows"] == 50

    def test_component_dict_structure(self):
        """Output dict has all required top-level keys."""
        node = _make_node(params={"NB_ROWS": "5"})
        result = RowGeneratorConverter().convert(node, [], {})
        comp = result.component
        expected_keys = {
            "id", "type", "original_type", "position",
            "config", "schema", "inputs", "outputs",
        }
        assert set(comp.keys()) == expected_keys

    def test_result_type(self):
        """convert() returns a ComponentResult."""
        node = _make_node(params={})
        result = RowGeneratorConverter().convert(node, [], {})
        assert isinstance(result, ComponentResult)


# ------------------------------------------------------------------
# Defaults
# ------------------------------------------------------------------
class TestRowGeneratorDefaults:
    def test_nb_rows_defaults_to_1(self):
        """When NB_ROWS is missing, default to 1."""
        node = _make_node(params={})
        result = RowGeneratorConverter().convert(node, [], {})
        assert result.component["config"]["nb_rows"] == 1

    def test_values_defaults_to_empty_list(self):
        """When VALUES is missing, values is an empty list."""
        node = _make_node(params={})
        result = RowGeneratorConverter().convert(node, [], {})
        assert result.component["config"]["values"] == []


# ------------------------------------------------------------------
# Source schema (input=[], output from FLOW)
# ------------------------------------------------------------------
class TestRowGeneratorSchema:
    def test_source_schema_no_input(self):
        """RowGenerator is a source: input schema is always empty."""
        node = _make_node(
            params={"NB_ROWS": "1"},
            schema=_make_output_schema(),
        )
        result = RowGeneratorConverter().convert(node, [], {})
        schema = result.component["schema"]

        assert schema["input"] == []
        assert len(schema["output"]) == 3

    def test_output_schema_columns(self):
        """Output schema columns are correctly parsed from FLOW metadata."""
        node = _make_node(
            params={"NB_ROWS": "1"},
            schema=_make_output_schema(),
        )
        result = RowGeneratorConverter().convert(node, [], {})
        output = result.component["schema"]["output"]

        assert output[0]["name"] == "id"
        assert output[0]["key"] is True
        assert output[0]["nullable"] is False

        assert output[1]["name"] == "name"
        assert output[1]["length"] == 50

        assert output[2]["name"] == "amount"
        assert output[2]["precision"] == 2

    def test_empty_schema_when_no_flow(self):
        """When no FLOW schema is present, output is an empty list."""
        node = _make_node(params={"NB_ROWS": "1"})
        result = RowGeneratorConverter().convert(node, [], {})
        schema = result.component["schema"]
        assert schema == {"input": [], "output": []}


# ------------------------------------------------------------------
# VALUES edge cases / warnings
# ------------------------------------------------------------------
class TestRowGeneratorValuesEdgeCases:
    def test_schema_column_without_array(self):
        """A trailing SCHEMA_COLUMN with no ARRAY is skipped with a warning."""
        node = _make_node(params={
            "VALUES": [
                {"elementRef": "SCHEMA_COLUMN", "value": '"good_col"'},
                {"elementRef": "ARRAY", "value": '"expr1"'},
                {"elementRef": "SCHEMA_COLUMN", "value": '"orphan_col"'},
            ],
        })
        result = RowGeneratorConverter().convert(node, [], {})

        cfg = result.component["config"]
        assert cfg["values"] == [{"schema_column": "good_col", "array": "expr1"}]
        assert any("orphan_col" in w for w in result.warnings)

    def test_array_without_schema_column(self):
        """An ARRAY without a preceding SCHEMA_COLUMN is skipped with a warning."""
        node = _make_node(params={
            "VALUES": [
                {"elementRef": "ARRAY", "value": '"lonely_expr"'},
                {"elementRef": "SCHEMA_COLUMN", "value": '"col"'},
                {"elementRef": "ARRAY", "value": '"expr"'},
            ],
        })
        result = RowGeneratorConverter().convert(node, [], {})

        cfg = result.component["config"]
        assert cfg["values"] == [{"schema_column": "col", "array": "expr"}]
        assert any("no preceding SCHEMA_COLUMN" in w for w in result.warnings)

    def test_consecutive_schema_columns(self):
        """Two consecutive SCHEMA_COLUMNs: the first is skipped with a warning."""
        node = _make_node(params={
            "VALUES": [
                {"elementRef": "SCHEMA_COLUMN", "value": '"first"'},
                {"elementRef": "SCHEMA_COLUMN", "value": '"second"'},
                {"elementRef": "ARRAY", "value": '"expr"'},
            ],
        })
        result = RowGeneratorConverter().convert(node, [], {})

        cfg = result.component["config"]
        assert cfg["values"] == [{"schema_column": "second", "array": "expr"}]
        assert any("first" in w and "no matching ARRAY" in w
                    for w in result.warnings)

    def test_values_not_a_list(self):
        """If VALUES is not a list (unexpected), produce a warning."""
        node = _make_node(params={"VALUES": "not_a_list"})
        result = RowGeneratorConverter().convert(node, [], {})

        cfg = result.component["config"]
        assert cfg["values"] == []
        assert any("not a list" in w for w in result.warnings)

    def test_empty_values_list(self):
        """An empty VALUES list produces no values and no warnings."""
        node = _make_node(params={"VALUES": []})
        result = RowGeneratorConverter().convert(node, [], {})

        cfg = result.component["config"]
        assert cfg["values"] == []
        assert result.warnings == []
