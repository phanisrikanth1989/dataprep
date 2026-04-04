"""Tests for tPythonDataFrame -> PythonDataFrameComponent converter."""
from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendNode,
)
from src.converters.talend_to_v1.components.transform.python_dataframe_component import (
    PythonDataFrameComponentConverter,
)


def _make_node(params=None, schema=None, component_type="tPythonDataFrame"):
    return TalendNode(
        component_id=f"{component_type}_1",
        component_type=component_type,
        params=params or {},
        schema=schema or {},
        position={"x": 200, "y": 300},
    )


class TestPythonDataFrameComponentConverter:
    """Tests for PythonDataFrameComponentConverter."""

    def test_basic_code_and_die_on_error(self):
        """CODE and DIE_ON_ERROR params are correctly mapped to config."""
        node = _make_node(params={
            "CODE": "df = df.dropna()",
            "DIE_ON_ERROR": "true",
        })
        result = PythonDataFrameComponentConverter().convert(node, [], {})
        comp = result.component

        assert comp["type"] == "PythonDataFrameComponent"
        assert comp["original_type"] == "tPythonDataFrame"
        assert comp["id"] == "tPythonDataFrame_1"
        assert comp["position"] == {"x": 200, "y": 300}

        cfg = comp["config"]
        assert cfg["python_code"] == "df = df.dropna()"
        assert cfg["die_on_error"] is True
        assert not result.warnings

    def test_empty_code_produces_warning(self):
        """When CODE is empty, a warning is emitted."""
        node = _make_node(params={"CODE": "", "DIE_ON_ERROR": "false"})
        result = PythonDataFrameComponentConverter().convert(node, [], {})

        assert any("empty" in w.lower() for w in result.warnings)
        assert result.component["config"]["python_code"] == ""

    def test_missing_params_defaults(self):
        """Missing CODE and DIE_ON_ERROR default to empty/false with a warning."""
        node = _make_node(params={})
        result = PythonDataFrameComponentConverter().convert(node, [], {})
        cfg = result.component["config"]

        assert cfg["python_code"] == ""
        assert cfg["die_on_error"] is False
        assert any("empty" in w.lower() for w in result.warnings)

    def test_die_on_error_false(self):
        """DIE_ON_ERROR 'false' maps to False."""
        node = _make_node(params={
            "CODE": "print('hello')",
            "DIE_ON_ERROR": "false",
        })
        result = PythonDataFrameComponentConverter().convert(node, [], {})
        assert result.component["config"]["die_on_error"] is False
        assert not result.warnings

    def test_schema_passthrough(self):
        """Schema is parsed and set as both input and output."""
        node = _make_node(
            params={"CODE": "df = df.rename(columns={'a': 'b'})", "DIE_ON_ERROR": "true"},
            schema={
                "FLOW": [
                    SchemaColumn(name="id", type="id_Integer", key=True, nullable=False),
                    SchemaColumn(name="name", type="id_String", length=100),
                    SchemaColumn(name="amount", type="id_Double", precision=2),
                ]
            },
        )
        result = PythonDataFrameComponentConverter().convert(node, [], {})
        schema = result.component["schema"]

        assert schema["input"] == schema["output"]
        assert len(schema["output"]) == 3
        assert schema["output"][0]["name"] == "id"
        assert schema["output"][0]["key"] is True
        assert schema["output"][0]["nullable"] is False
        assert schema["output"][1]["name"] == "name"
        assert schema["output"][1]["length"] == 100
        assert schema["output"][2]["name"] == "amount"
        assert schema["output"][2]["precision"] == 2

    def test_component_dict_structure(self):
        """Output dict has all required top-level keys."""
        node = _make_node(params={"CODE": "# noop"})
        result = PythonDataFrameComponentConverter().convert(node, [], {})
        comp = result.component
        expected_keys = {"id", "type", "original_type", "position", "config", "schema", "inputs", "outputs"}
        assert set(comp.keys()) == expected_keys
        assert comp["inputs"] == []
        assert comp["outputs"] == []

    def test_result_type(self):
        """convert() returns a ComponentResult."""
        node = _make_node(params={})
        result = PythonDataFrameComponentConverter().convert(node, [], {})
        assert isinstance(result, ComponentResult)

    def test_registry_registration(self):
        """The converter is registered under 'tPythonDataFrame'."""
        from src.converters.talend_to_v1.components.registry import REGISTRY
        cls = REGISTRY.get("tPythonDataFrame")
        assert cls is PythonDataFrameComponentConverter

    def test_die_on_error_boolean_true(self):
        """DIE_ON_ERROR as Python bool True is handled."""
        node = _make_node(params={
            "CODE": "df['x'] = df['x'].fillna(0)",
            "DIE_ON_ERROR": True,
        })
        result = PythonDataFrameComponentConverter().convert(node, [], {})
        assert result.component["config"]["die_on_error"] is True
