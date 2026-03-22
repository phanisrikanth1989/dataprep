"""Tests for PivotToColumnsDelimitedConverter (tPivotToColumnsDelimited -> PivotToColumnsDelimited)."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.transform.pivot_to_columns_delimited import (
    PivotToColumnsDelimitedConverter,
)
from src.converters.talend_to_v1.components.registry import REGISTRY


def _make_node(params=None, schema=None, component_id="pivot_1",
               component_type="tPivotToColumnsDelimited"):
    return TalendNode(
        component_id=component_id,
        component_type=component_type,
        params=params or {},
        schema=schema or {},
        position={"x": 300, "y": 400},
        raw_xml=ET.Element("node"),
    )


def _make_schema_columns():
    """Return a sample FLOW schema for testing."""
    return {
        "FLOW": [
            SchemaColumn(name="region", type="id_String", nullable=False, key=True),
            SchemaColumn(name="product", type="id_String", nullable=True),
            SchemaColumn(name="sales", type="id_Double", nullable=True),
        ]
    }


# ------------------------------------------------------------------
# Registration
# ------------------------------------------------------------------
class TestPivotToColumnsDelimitedRegistration:
    def test_registered_in_registry(self):
        assert REGISTRY.get("tPivotToColumnsDelimited") is PivotToColumnsDelimitedConverter


# ------------------------------------------------------------------
# Basic / happy-path
# ------------------------------------------------------------------
class TestPivotToColumnsDelimitedBasic:
    def test_full_config(self):
        """All parameters supplied — no warnings expected."""
        node = _make_node(params={
            "PIVOT_COLUMN": '"product"',
            "AGGREGATION_COLUMN": '"sales"',
            "AGGREGATION_FUNCTION": '"sum"',
            "GROUPBYS": [
                {"value": '"region"'},
                {"value": '"quarter"'},
            ],
            "FILENAME": '"/tmp/output.csv"',
            "ROWSEPARATOR": '"\\n"',
            "FIELDSEPARATOR": '","',
            "ENCODING": '"UTF-8"',
            "CREATE": "true",
        })
        result = PivotToColumnsDelimitedConverter().convert(node, [], {})

        assert isinstance(result, ComponentResult)
        comp = result.component
        assert comp["id"] == "pivot_1"
        assert comp["type"] == "PivotToColumnsDelimited"
        assert comp["original_type"] == "tPivotToColumnsDelimited"
        assert comp["position"] == {"x": 300, "y": 400}
        cfg = comp["config"]
        assert cfg["pivot_column"] == "product"
        assert cfg["aggregation_column"] == "sales"
        assert cfg["aggregation_function"] == "sum"
        assert cfg["group_by_columns"] == ["region", "quarter"]
        assert cfg["filename"] == "/tmp/output.csv"
        assert cfg["row_separator"] == "\\n"
        assert cfg["field_separator"] == ","
        assert cfg["encoding"] == "UTF-8"
        assert cfg["create"] is True
        assert comp["inputs"] == []
        assert comp["outputs"] == []
        assert result.warnings == []

    def test_defaults_when_params_missing(self):
        """Missing scalar params should fall back to safe defaults."""
        node = _make_node(params={})
        result = PivotToColumnsDelimitedConverter().convert(node, [], {})

        cfg = result.component["config"]
        assert cfg["pivot_column"] == ""
        assert cfg["aggregation_column"] == ""
        assert cfg["aggregation_function"] == "sum"
        assert cfg["group_by_columns"] == []
        assert cfg["filename"] == ""
        assert cfg["row_separator"] == "\\n"
        assert cfg["field_separator"] == ";"
        assert cfg["encoding"] == "UTF-8"
        assert cfg["create"] is True
        # Should warn about empty pivot_column, aggregation_column, and filename
        assert any("PIVOT_COLUMN" in w for w in result.warnings)
        assert any("AGGREGATION_COLUMN" in w for w in result.warnings)
        assert any("FILENAME" in w for w in result.warnings)


# ------------------------------------------------------------------
# GROUPBYS table parameter
# ------------------------------------------------------------------
class TestPivotToColumnsDelimitedGroupBys:
    def test_single_group_by(self):
        node = _make_node(params={
            "PIVOT_COLUMN": '"col"',
            "AGGREGATION_COLUMN": '"val"',
            "FILENAME": '"/tmp/out.csv"',
            "GROUPBYS": [{"value": '"region"'}],
        })
        result = PivotToColumnsDelimitedConverter().convert(node, [], {})

        assert result.component["config"]["group_by_columns"] == ["region"]

    def test_multiple_group_bys(self):
        node = _make_node(params={
            "PIVOT_COLUMN": '"col"',
            "AGGREGATION_COLUMN": '"val"',
            "FILENAME": '"/tmp/out.csv"',
            "GROUPBYS": [
                {"value": '"region"'},
                {"value": '"year"'},
                {"value": '"quarter"'},
            ],
        })
        result = PivotToColumnsDelimitedConverter().convert(node, [], {})

        assert result.component["config"]["group_by_columns"] == [
            "region", "year", "quarter",
        ]

    def test_empty_group_bys(self):
        node = _make_node(params={
            "PIVOT_COLUMN": '"col"',
            "AGGREGATION_COLUMN": '"val"',
            "FILENAME": '"/tmp/out.csv"',
            "GROUPBYS": [],
        })
        result = PivotToColumnsDelimitedConverter().convert(node, [], {})

        assert result.component["config"]["group_by_columns"] == []

    def test_group_bys_skips_empty_values(self):
        """Entries with empty string values after quote-stripping are skipped."""
        node = _make_node(params={
            "PIVOT_COLUMN": '"col"',
            "AGGREGATION_COLUMN": '"val"',
            "FILENAME": '"/tmp/out.csv"',
            "GROUPBYS": [
                {"value": '"region"'},
                {"value": '""'},
                {"value": '"year"'},
            ],
        })
        result = PivotToColumnsDelimitedConverter().convert(node, [], {})

        assert result.component["config"]["group_by_columns"] == ["region", "year"]

    def test_group_bys_not_a_list_warns(self):
        """If GROUPBYS is not a list, produce a warning and return empty list."""
        node = _make_node(params={
            "PIVOT_COLUMN": '"col"',
            "AGGREGATION_COLUMN": '"val"',
            "FILENAME": '"/tmp/out.csv"',
            "GROUPBYS": "bad_data",
        })
        result = PivotToColumnsDelimitedConverter().convert(node, [], {})

        assert result.component["config"]["group_by_columns"] == []
        assert any("not a list" in w for w in result.warnings)


# ------------------------------------------------------------------
# Boolean / CREATE parameter
# ------------------------------------------------------------------
class TestPivotToColumnsDelimitedCreate:
    def test_create_false(self):
        node = _make_node(params={
            "PIVOT_COLUMN": '"col"',
            "AGGREGATION_COLUMN": '"val"',
            "FILENAME": '"/tmp/out.csv"',
            "CREATE": "false",
        })
        result = PivotToColumnsDelimitedConverter().convert(node, [], {})

        assert result.component["config"]["create"] is False

    def test_create_true_string(self):
        node = _make_node(params={
            "PIVOT_COLUMN": '"col"',
            "AGGREGATION_COLUMN": '"val"',
            "FILENAME": '"/tmp/out.csv"',
            "CREATE": "true",
        })
        result = PivotToColumnsDelimitedConverter().convert(node, [], {})

        assert result.component["config"]["create"] is True


# ------------------------------------------------------------------
# Schema
# ------------------------------------------------------------------
class TestPivotToColumnsDelimitedSchema:
    def test_schema_passthrough(self):
        """PivotToColumnsDelimited passes the schema through: input == output."""
        node = _make_node(
            params={
                "PIVOT_COLUMN": '"product"',
                "AGGREGATION_COLUMN": '"sales"',
                "FILENAME": '"/tmp/out.csv"',
            },
            schema=_make_schema_columns(),
        )
        result = PivotToColumnsDelimitedConverter().convert(node, [], {})

        schema = result.component["schema"]
        assert schema["input"] == schema["output"]
        assert len(schema["input"]) == 3
        assert schema["input"][0]["name"] == "region"

    def test_empty_schema(self):
        """When no FLOW schema is present, input and output are empty lists."""
        node = _make_node(params={})
        result = PivotToColumnsDelimitedConverter().convert(node, [], {})

        schema = result.component["schema"]
        assert schema == {"input": [], "output": []}


# ------------------------------------------------------------------
# Aggregation function variations
# ------------------------------------------------------------------
class TestPivotToColumnsDelimitedAggregation:
    def test_aggregation_function_avg(self):
        node = _make_node(params={
            "PIVOT_COLUMN": '"col"',
            "AGGREGATION_COLUMN": '"val"',
            "FILENAME": '"/tmp/out.csv"',
            "AGGREGATION_FUNCTION": '"avg"',
        })
        result = PivotToColumnsDelimitedConverter().convert(node, [], {})

        assert result.component["config"]["aggregation_function"] == "avg"

    def test_aggregation_function_default(self):
        """When AGGREGATION_FUNCTION is absent, it defaults to 'sum'."""
        node = _make_node(params={
            "PIVOT_COLUMN": '"col"',
            "AGGREGATION_COLUMN": '"val"',
            "FILENAME": '"/tmp/out.csv"',
        })
        result = PivotToColumnsDelimitedConverter().convert(node, [], {})

        assert result.component["config"]["aggregation_function"] == "sum"
