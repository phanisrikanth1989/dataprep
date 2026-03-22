"""Tests for tFlowToIterate -> FlowToIterate converter."""
from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendNode,
)
from src.converters.talend_to_v1.components.iterate.flow_to_iterate import (
    FlowToIterateConverter,
)


def _make_node(params=None, schema=None):
    return TalendNode(
        component_id="tFlowToIterate_1",
        component_type="tFlowToIterate",
        params=params or {},
        schema=schema or {},
        position={"x": 352, "y": 96},
    )


class TestFlowToIterateBasicConfig:
    """Core config extraction tests."""

    def test_default_map_true_with_row_format(self):
        """Typical default usage: DEFAULT_MAP=true, CONNECTION_FORMAT=row."""
        node = _make_node(params={
            "DEFAULT_MAP": True,
            "CONNECTION_FORMAT": "row",
            "MAP": [],
        })
        result = FlowToIterateConverter().convert(node, [], {})
        comp = result.component

        assert comp["type"] == "FlowToIterate"
        assert comp["original_type"] == "tFlowToIterate"
        assert comp["id"] == "tFlowToIterate_1"
        assert comp["position"] == {"x": 352, "y": 96}

        cfg = comp["config"]
        assert cfg["default_map"] is True
        assert cfg["connection_format"] == "row"
        assert cfg["map_entries"] == []
        assert result.warnings == []

    def test_default_map_false_with_explicit_entries(self):
        """DEFAULT_MAP=false with explicit MAP table entries."""
        node = _make_node(params={
            "DEFAULT_MAP": False,
            "CONNECTION_FORMAT": "row",
            "MAP": [
                {"elementRef": "SCHEMA_COLUMN", "value": '"col_a"'},
                {"elementRef": "COLUMN", "value": '"var_a"'},
                {"elementRef": "SCHEMA_COLUMN", "value": '"col_b"'},
                {"elementRef": "COLUMN", "value": '"var_b"'},
            ],
        })
        result = FlowToIterateConverter().convert(node, [], {})
        cfg = result.component["config"]

        assert cfg["default_map"] is False
        assert len(cfg["map_entries"]) == 2
        assert cfg["map_entries"][0] == {
            "schema_column": "col_a",
            "column": "var_a",
        }
        assert cfg["map_entries"][1] == {
            "schema_column": "col_b",
            "column": "var_b",
        }
        assert result.warnings == []

    def test_connection_format_defaults_to_row(self):
        """When CONNECTION_FORMAT is missing, default to 'row'."""
        node = _make_node(params={"DEFAULT_MAP": True})
        result = FlowToIterateConverter().convert(node, [], {})
        assert result.component["config"]["connection_format"] == "row"

    def test_default_map_defaults_to_true(self):
        """When DEFAULT_MAP is missing, default to True."""
        node = _make_node(params={})
        result = FlowToIterateConverter().convert(node, [], {})
        assert result.component["config"]["default_map"] is True


class TestFlowToIterateDefaults:
    """Edge cases for missing / empty params."""

    def test_all_params_missing(self):
        """All params absent: sensible defaults, no crash."""
        node = _make_node(params={})
        result = FlowToIterateConverter().convert(node, [], {})
        cfg = result.component["config"]

        assert cfg["default_map"] is True
        assert cfg["connection_format"] == "row"
        assert cfg["map_entries"] == []
        # No warning expected since default_map is True
        assert result.warnings == []

    def test_default_map_false_no_entries_warns(self):
        """DEFAULT_MAP=false but no MAP entries: should warn."""
        node = _make_node(params={
            "DEFAULT_MAP": False,
            "MAP": [],
        })
        result = FlowToIterateConverter().convert(node, [], {})

        assert any("no explicit MAP entries" in w for w in result.warnings)

    def test_default_map_false_missing_map_param_warns(self):
        """DEFAULT_MAP=false with MAP param entirely absent: should warn."""
        node = _make_node(params={
            "DEFAULT_MAP": False,
        })
        result = FlowToIterateConverter().convert(node, [], {})

        assert result.component["config"]["map_entries"] == []
        assert any("no explicit MAP entries" in w for w in result.warnings)


class TestFlowToIterateMapParsing:
    """Tests for MAP TABLE parsing edge cases."""

    def test_single_mapping(self):
        """A single SCHEMA_COLUMN/COLUMN pair."""
        node = _make_node(params={
            "DEFAULT_MAP": False,
            "MAP": [
                {"elementRef": "SCHEMA_COLUMN", "value": '"input_col"'},
                {"elementRef": "COLUMN", "value": '"output_var"'},
            ],
        })
        result = FlowToIterateConverter().convert(node, [], {})
        entries = result.component["config"]["map_entries"]

        assert len(entries) == 1
        assert entries[0] == {
            "schema_column": "input_col",
            "column": "output_var",
        }

    def test_trailing_schema_column_skipped_with_warning(self):
        """A trailing SCHEMA_COLUMN without COLUMN is skipped with warning."""
        node = _make_node(params={
            "DEFAULT_MAP": False,
            "MAP": [
                {"elementRef": "SCHEMA_COLUMN", "value": '"good_col"'},
                {"elementRef": "COLUMN", "value": '"good_var"'},
                {"elementRef": "SCHEMA_COLUMN", "value": '"orphan_col"'},
            ],
        })
        result = FlowToIterateConverter().convert(node, [], {})
        entries = result.component["config"]["map_entries"]

        assert len(entries) == 1
        assert entries[0]["schema_column"] == "good_col"
        assert any("orphan_col" in w for w in result.warnings)

    def test_column_without_schema_column_skipped(self):
        """A COLUMN without a preceding SCHEMA_COLUMN is skipped."""
        node = _make_node(params={
            "DEFAULT_MAP": False,
            "MAP": [
                {"elementRef": "COLUMN", "value": '"orphan_var"'},
                {"elementRef": "SCHEMA_COLUMN", "value": '"col_x"'},
                {"elementRef": "COLUMN", "value": '"var_x"'},
            ],
        })
        result = FlowToIterateConverter().convert(node, [], {})
        entries = result.component["config"]["map_entries"]

        assert len(entries) == 1
        assert entries[0] == {"schema_column": "col_x", "column": "var_x"}
        assert any("orphan_var" in w for w in result.warnings)

    def test_consecutive_schema_columns_warns(self):
        """Two consecutive SCHEMA_COLUMNs: first is skipped with warning."""
        node = _make_node(params={
            "DEFAULT_MAP": False,
            "MAP": [
                {"elementRef": "SCHEMA_COLUMN", "value": '"first"'},
                {"elementRef": "SCHEMA_COLUMN", "value": '"second"'},
                {"elementRef": "COLUMN", "value": '"var"'},
            ],
        })
        result = FlowToIterateConverter().convert(node, [], {})
        entries = result.component["config"]["map_entries"]

        assert len(entries) == 1
        assert entries[0] == {"schema_column": "second", "column": "var"}
        assert any("first" in w and "no matching COLUMN" in w for w in result.warnings)

    def test_map_not_a_list_warns(self):
        """MAP param is not a list -- produce warning."""
        node = _make_node(params={
            "DEFAULT_MAP": False,
            "MAP": "bad_value",
        })
        result = FlowToIterateConverter().convert(node, [], {})

        assert result.component["config"]["map_entries"] == []
        assert any("not a list" in w for w in result.warnings)


class TestFlowToIterateSchema:
    """Schema passthrough tests."""

    def test_schema_input_equals_output(self):
        """FlowToIterate passes schema through: input == output."""
        node = _make_node(
            params={"DEFAULT_MAP": True},
            schema={
                "FLOW": [
                    SchemaColumn(
                        name="file_directory", type="id_String", nullable=True
                    ),
                    SchemaColumn(
                        name="file_name", type="id_String", nullable=True
                    ),
                    SchemaColumn(
                        name="row_count", type="id_Integer",
                        key=True, nullable=False,
                    ),
                ]
            },
        )
        result = FlowToIterateConverter().convert(node, [], {})
        schema = result.component["schema"]

        assert schema["input"] == schema["output"]
        assert len(schema["output"]) == 3
        assert schema["output"][0]["name"] == "file_directory"
        assert schema["output"][2]["name"] == "row_count"
        assert schema["output"][2]["key"] is True
        assert schema["output"][2]["nullable"] is False

    def test_empty_schema(self):
        """No schema defined produces empty lists."""
        node = _make_node(params={})
        result = FlowToIterateConverter().convert(node, [], {})
        assert result.component["schema"] == {"input": [], "output": []}


class TestFlowToIterateStructure:
    """Component dict structure and registration tests."""

    def test_component_dict_structure(self):
        """Output dict has all required top-level keys."""
        node = _make_node(params={})
        result = FlowToIterateConverter().convert(node, [], {})
        comp = result.component
        expected_keys = {
            "id", "type", "original_type", "position",
            "config", "schema", "inputs", "outputs",
        }
        assert set(comp.keys()) == expected_keys
        assert comp["inputs"] == []
        assert comp["outputs"] == []

    def test_result_type(self):
        """convert() returns a ComponentResult."""
        node = _make_node(params={})
        result = FlowToIterateConverter().convert(node, [], {})
        assert isinstance(result, ComponentResult)

    def test_registration(self):
        """The converter is registered under 'tFlowToIterate'."""
        from src.converters.talend_to_v1.components.registry import REGISTRY
        cls = REGISTRY.get("tFlowToIterate")
        assert cls is FlowToIterateConverter
