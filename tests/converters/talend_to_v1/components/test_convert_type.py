"""Tests for tConvertType -> ConvertType converter."""
from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendNode,
)
from src.converters.talend_to_v1.components.transform.convert_type import (
    ConvertTypeConverter,
)


def _make_node(params=None, schema=None, component_type="tConvertType"):
    return TalendNode(
        component_id=f"{component_type}_1",
        component_type=component_type,
        params=params or {},
        schema=schema or {},
        position={"x": 100, "y": 200},
    )


class TestConvertTypeConverter:
    """Tests for ConvertTypeConverter."""

    def test_basic_config(self):
        """All config params are extracted correctly."""
        node = _make_node(params={
            "AUTOCAST": "true",
            "EMPTYTONULL": "true",
            "DIEONERROR": "false",
            "MANUALTABLE": [
                {"elementRef": "SCHEMA_COLUMN", "value": "age"},
                {"elementRef": "CONVERT_TO", "value": "Integer"},
                {"elementRef": "SCHEMA_COLUMN", "value": "salary"},
                {"elementRef": "CONVERT_TO", "value": "Double"},
            ],
        })
        result = ConvertTypeConverter().convert(node, [], {})
        comp = result.component

        assert comp["type"] == "ConvertType"
        assert comp["original_type"] == "tConvertType"
        assert comp["id"] == "tConvertType_1"
        assert comp["position"] == {"x": 100, "y": 200}

        cfg = comp["config"]
        assert cfg["autocast"] is True
        assert cfg["empty_to_null"] is True
        assert cfg["die_on_error"] is False
        assert len(cfg["manual_table"]) == 2
        assert cfg["manual_table"][0] == {"column": "age", "target_type": "Integer"}
        assert cfg["manual_table"][1] == {"column": "salary", "target_type": "Double"}

    def test_defaults_when_params_missing(self):
        """Missing params fall back to defaults and produce a warning."""
        node = _make_node(params={})
        result = ConvertTypeConverter().convert(node, [], {})
        cfg = result.component["config"]

        assert cfg["autocast"] is False
        assert cfg["empty_to_null"] is False
        assert cfg["die_on_error"] is False
        assert cfg["manual_table"] == []
        # Should warn about no conversion effect
        assert any("no effect" in w.lower() for w in result.warnings)

    def test_autocast_only_no_warning(self):
        """When AUTOCAST is true but manual_table is empty, no warning."""
        node = _make_node(params={
            "AUTOCAST": "true",
            "EMPTYTONULL": "false",
            "DIEONERROR": "false",
        })
        result = ConvertTypeConverter().convert(node, [], {})
        cfg = result.component["config"]

        assert cfg["autocast"] is True
        assert cfg["manual_table"] == []
        assert not any("no effect" in w.lower() for w in result.warnings)

    def test_manual_table_only_no_warning(self):
        """When AUTOCAST is false but manual_table has entries, no warning."""
        node = _make_node(params={
            "AUTOCAST": "false",
            "MANUALTABLE": [
                {"elementRef": "SCHEMA_COLUMN", "value": "col1"},
                {"elementRef": "CONVERT_TO", "value": "String"},
            ],
        })
        result = ConvertTypeConverter().convert(node, [], {})
        cfg = result.component["config"]

        assert cfg["autocast"] is False
        assert len(cfg["manual_table"]) == 1
        assert not any("no effect" in w.lower() for w in result.warnings)

    def test_manual_table_parsing_multiple_entries(self):
        """Multiple MANUALTABLE rows are parsed into separate dicts."""
        node = _make_node(params={
            "MANUALTABLE": [
                {"elementRef": "SCHEMA_COLUMN", "value": "id"},
                {"elementRef": "CONVERT_TO", "value": "Long"},
                {"elementRef": "SCHEMA_COLUMN", "value": "name"},
                {"elementRef": "CONVERT_TO", "value": "String"},
                {"elementRef": "SCHEMA_COLUMN", "value": "active"},
                {"elementRef": "CONVERT_TO", "value": "Boolean"},
            ],
        })
        result = ConvertTypeConverter().convert(node, [], {})
        table = result.component["config"]["manual_table"]

        assert len(table) == 3
        assert table[0] == {"column": "id", "target_type": "Long"}
        assert table[1] == {"column": "name", "target_type": "String"}
        assert table[2] == {"column": "active", "target_type": "Boolean"}

    def test_manual_table_empty_list(self):
        """MANUALTABLE as an empty list produces an empty manual_table."""
        node = _make_node(params={
            "AUTOCAST": "true",
            "MANUALTABLE": [],
        })
        result = ConvertTypeConverter().convert(node, [], {})
        assert result.component["config"]["manual_table"] == []

    def test_schema_passthrough(self):
        """ConvertType passes through schema: input == output."""
        node = _make_node(
            params={"AUTOCAST": "true"},
            schema={
                "FLOW": [
                    SchemaColumn(name="id", type="id_Integer", key=True, nullable=False),
                    SchemaColumn(name="name", type="id_String", length=100),
                    SchemaColumn(name="created", type="id_Date", date_pattern="yyyy-MM-dd"),
                ]
            },
        )
        result = ConvertTypeConverter().convert(node, [], {})
        schema = result.component["schema"]

        assert schema["input"] == schema["output"]
        assert len(schema["output"]) == 3
        assert schema["output"][0]["name"] == "id"
        assert schema["output"][0]["key"] is True
        assert schema["output"][0]["nullable"] is False
        assert schema["output"][1]["name"] == "name"
        assert schema["output"][1]["length"] == 100
        assert schema["output"][2]["name"] == "created"

    def test_component_dict_structure(self):
        """Output dict has all required top-level keys."""
        node = _make_node(params={})
        result = ConvertTypeConverter().convert(node, [], {})
        comp = result.component
        expected_keys = {"id", "type", "original_type", "position", "config", "schema", "inputs", "outputs"}
        assert set(comp.keys()) == expected_keys
        assert comp["inputs"] == []
        assert comp["outputs"] == []

    def test_result_type(self):
        """convert() returns a ComponentResult."""
        node = _make_node(params={})
        result = ConvertTypeConverter().convert(node, [], {})
        assert isinstance(result, ComponentResult)

    def test_registration(self):
        """The converter is registered under 'tConvertType'."""
        from src.converters.talend_to_v1.components.registry import REGISTRY
        cls = REGISTRY.get("tConvertType")
        assert cls is ConvertTypeConverter

    def test_die_on_error_true(self):
        """DIEONERROR=true is correctly parsed."""
        node = _make_node(params={
            "AUTOCAST": "true",
            "DIEONERROR": "true",
        })
        result = ConvertTypeConverter().convert(node, [], {})
        assert result.component["config"]["die_on_error"] is True

    def test_manual_table_partial_entry(self):
        """A column entry without a CONVERT_TO is still captured (partial)."""
        node = _make_node(params={
            "MANUALTABLE": [
                {"elementRef": "SCHEMA_COLUMN", "value": "orphan_col"},
            ],
        })
        result = ConvertTypeConverter().convert(node, [], {})
        table = result.component["config"]["manual_table"]
        assert len(table) == 1
        assert table[0] == {"column": "orphan_col"}
