"""Tests for the HashOutputConverter (tHashOutput -> HashOutput)."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.transform.hash_output import (
    HashOutputConverter,
)
from src.converters.talend_to_v1.components.registry import REGISTRY


def _make_node(params=None, schema=None, component_id="hash_output_1",
               component_type="tHashOutput"):
    return TalendNode(
        component_id=component_id,
        component_type=component_type,
        params=params or {},
        schema=schema or {},
        position={"x": 400, "y": 200},
        raw_xml=ET.Element("node"),
    )


def _sample_schema():
    """Return a FLOW schema with two columns for reuse across tests."""
    return {
        "FLOW": [
            SchemaColumn(name="id", type="id_Integer", nullable=False, key=True),
            SchemaColumn(name="value", type="id_String", nullable=True),
        ]
    }


# --------------------------------------------------------------------- #
#  Registration
# --------------------------------------------------------------------- #

class TestHashOutputConverterRegistration:
    def test_registered_in_registry(self):
        assert REGISTRY.get("tHashOutput") is HashOutputConverter


# --------------------------------------------------------------------- #
#  Basic conversion
# --------------------------------------------------------------------- #

class TestHashOutputConverterBasic:
    def test_basic_conversion_with_defaults(self):
        node = _make_node(schema=_sample_schema())
        result = HashOutputConverter().convert(node, [], {})

        assert isinstance(result, ComponentResult)
        comp = result.component
        assert comp["id"] == "hash_output_1"
        assert comp["type"] == "HashOutput"
        assert comp["original_type"] == "tHashOutput"
        assert comp["position"] == {"x": 400, "y": 200}
        assert comp["config"] == {}
        assert comp["inputs"] == []
        assert comp["outputs"] == []

    def test_no_warnings_on_valid_input(self):
        node = _make_node(schema=_sample_schema())
        result = HashOutputConverter().convert(node, [], {})

        assert result.warnings == []
        assert result.needs_review == []

    def test_empty_params_produces_empty_config(self):
        node = _make_node(params={})
        result = HashOutputConverter().convert(node, [], {})

        assert result.component["config"] == {}

    def test_unique_name_excluded_from_config(self):
        node = _make_node(params={
            "UNIQUE_NAME": "tHashOutput_1",
            "SOME_PARAM": '"value"',
        })
        result = HashOutputConverter().convert(node, [], {})

        config = result.component["config"]
        assert "UNIQUE_NAME" not in config
        assert config["SOME_PARAM"] == "value"


# --------------------------------------------------------------------- #
#  Parameter normalisation
# --------------------------------------------------------------------- #

class TestHashOutputConverterParams:
    def test_string_bool_true_normalised(self):
        node = _make_node(params={"APPEND_MODE": "true"})
        result = HashOutputConverter().convert(node, [], {})

        assert result.component["config"]["APPEND_MODE"] is True

    def test_string_bool_false_normalised(self):
        node = _make_node(params={"APPEND_MODE": "false"})
        result = HashOutputConverter().convert(node, [], {})

        assert result.component["config"]["APPEND_MODE"] is False

    def test_string_bool_case_insensitive(self):
        node = _make_node(params={"FLAG": "True"})
        result = HashOutputConverter().convert(node, [], {})

        assert result.component["config"]["FLAG"] is True

    def test_quoted_string_stripped(self):
        node = _make_node(params={"LABEL": '"my_hash"'})
        result = HashOutputConverter().convert(node, [], {})

        assert result.component["config"]["LABEL"] == "my_hash"

    def test_non_string_values_passed_through(self):
        node = _make_node(params={"COUNT": 42, "RATIO": 3.14})
        result = HashOutputConverter().convert(node, [], {})

        assert result.component["config"]["COUNT"] == 42
        assert result.component["config"]["RATIO"] == 3.14

    def test_multiple_params_copied(self):
        node = _make_node(params={
            "UNIQUE_NAME": "tHashOutput_1",
            "MATCH_KEY_COLUMNS": '"col_a,col_b"',
            "USE_EXISTING": "true",
            "CUSTOM_FLAG": "false",
            "BATCH_SIZE": 500,
        })
        result = HashOutputConverter().convert(node, [], {})

        config = result.component["config"]
        assert "UNIQUE_NAME" not in config
        assert config["MATCH_KEY_COLUMNS"] == "col_a,col_b"
        assert config["USE_EXISTING"] is True
        assert config["CUSTOM_FLAG"] is False
        assert config["BATCH_SIZE"] == 500


# --------------------------------------------------------------------- #
#  Schema handling
# --------------------------------------------------------------------- #

class TestHashOutputConverterSchema:
    def test_schema_input_equals_output(self):
        """HashOutput is a passthrough: input schema == output schema."""
        node = _make_node(schema=_sample_schema())
        result = HashOutputConverter().convert(node, [], {})

        schema = result.component["schema"]
        assert schema["input"] == schema["output"]
        assert len(schema["input"]) == 2

    def test_schema_column_details(self):
        node = _make_node(schema=_sample_schema())
        result = HashOutputConverter().convert(node, [], {})

        cols = result.component["schema"]["input"]
        id_col = cols[0]
        value_col = cols[1]

        assert id_col["name"] == "id"
        assert id_col["nullable"] is False
        assert id_col["key"] is True

        assert value_col["name"] == "value"
        assert value_col["nullable"] is True
        assert value_col["key"] is False

    def test_empty_schema(self):
        node = _make_node(schema={})
        result = HashOutputConverter().convert(node, [], {})

        assert result.component["schema"] == {"input": [], "output": []}
