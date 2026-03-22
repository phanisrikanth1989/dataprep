"""Tests for tNormalize -> Normalize converter."""
from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendNode,
)
from src.converters.talend_to_v1.components.transform.normalize import (
    NormalizeConverter,
)


def _make_node(params=None, schema=None):
    return TalendNode(
        component_id="tNormalize_1",
        component_type="tNormalize",
        params=params or {},
        schema=schema or {},
        position={"x": 100, "y": 200},
    )


class TestNormalizeConverter:
    """Tests for NormalizeConverter."""

    def test_basic_config(self):
        """All config params are extracted correctly."""
        node = _make_node(params={
            "NORMALIZE_COLUMN": '"tags"',
            "ITEMSEPARATOR": '","',
            "DEDUPLICATE": "true",
            "TRIM": "true",
            "DISCARD_TRAILING_EMPTY_STR": "false",
            "DIE_ON_ERROR": "true",
        })
        result = NormalizeConverter().convert(node, [], {})
        comp = result.component

        assert comp["type"] == "Normalize"
        assert comp["original_type"] == "tNormalize"
        assert comp["id"] == "tNormalize_1"
        assert comp["position"] == {"x": 100, "y": 200}

        cfg = comp["config"]
        assert cfg["normalize_column"] == "tags"
        assert cfg["item_separator"] == ","
        assert cfg["deduplicate"] is True
        assert cfg["trim"] is True
        assert cfg["discard_trailing_empty_str"] is False
        assert cfg["die_on_error"] is True

    def test_die_on_error_extracted(self):
        """CONV-NRM-001: die_on_error must be extracted (was missing in old code)."""
        node = _make_node(params={
            "NORMALIZE_COLUMN": '"col"',
            "DIE_ON_ERROR": "true",
        })
        result = NormalizeConverter().convert(node, [], {})
        cfg = result.component["config"]

        assert "die_on_error" in cfg, "die_on_error must be present in config"
        assert cfg["die_on_error"] is True

    def test_die_on_error_defaults_false(self):
        """die_on_error defaults to False when not provided."""
        node = _make_node(params={
            "NORMALIZE_COLUMN": '"col"',
        })
        result = NormalizeConverter().convert(node, [], {})
        assert result.component["config"]["die_on_error"] is False

    def test_defaults_when_params_missing(self):
        """Missing params fall back to sensible defaults and produce a warning."""
        node = _make_node(params={})
        result = NormalizeConverter().convert(node, [], {})
        cfg = result.component["config"]

        assert cfg["normalize_column"] == ""
        assert cfg["item_separator"] == ";"
        assert cfg["deduplicate"] is False
        assert cfg["trim"] is False
        assert cfg["discard_trailing_empty_str"] is False
        assert cfg["die_on_error"] is False
        # Should warn about empty normalize_column
        assert any("no effect" in w.lower() for w in result.warnings)

    def test_item_separator_default_semicolon(self):
        """When ITEMSEPARATOR is absent, default to semicolon."""
        node = _make_node(params={
            "NORMALIZE_COLUMN": '"data"',
        })
        result = NormalizeConverter().convert(node, [], {})
        assert result.component["config"]["item_separator"] == ";"

    def test_schema_passthrough(self):
        """Normalize passes through schema: both input and output match."""
        node = _make_node(
            params={"NORMALIZE_COLUMN": '"items"'},
            schema={
                "FLOW": [
                    SchemaColumn(name="id", type="id_Integer", key=True, nullable=False),
                    SchemaColumn(name="items", type="id_String", length=100),
                ]
            },
        )
        result = NormalizeConverter().convert(node, [], {})
        schema = result.component["schema"]

        assert schema["input"] == schema["output"]
        assert len(schema["output"]) == 2
        assert schema["output"][0]["name"] == "id"
        assert schema["output"][0]["key"] is True
        assert schema["output"][0]["nullable"] is False
        assert schema["output"][1]["name"] == "items"
        assert schema["output"][1]["length"] == 100

    def test_component_dict_structure(self):
        """Output dict has all required top-level keys."""
        node = _make_node(params={"NORMALIZE_COLUMN": '"col"'})
        result = NormalizeConverter().convert(node, [], {})
        comp = result.component
        expected_keys = {"id", "type", "original_type", "position", "config", "schema", "inputs", "outputs"}
        assert set(comp.keys()) == expected_keys
        assert comp["inputs"] == []
        assert comp["outputs"] == []

    def test_result_type(self):
        """convert() returns a ComponentResult."""
        node = _make_node(params={})
        result = NormalizeConverter().convert(node, [], {})
        assert isinstance(result, ComponentResult)

    def test_registration(self):
        """The converter is registered under 'tNormalize'."""
        from src.converters.talend_to_v1.components.registry import REGISTRY
        cls = REGISTRY.get("tNormalize")
        assert cls is NormalizeConverter
