"""Tests for SchemaComplianceCheckConverter (tSchemaComplianceCheck -> SchemaComplianceCheck)."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.transform.schema_compliance_check import (
    SchemaComplianceCheckConverter,
)
from src.converters.talend_to_v1.components.registry import REGISTRY


def _make_node(params=None, schema=None, component_id="scc_1",
               component_type="tSchemaComplianceCheck"):
    return TalendNode(
        component_id=component_id,
        component_type=component_type,
        params=params or {},
        schema=schema or {},
        position={"x": 100, "y": 200},
        raw_xml=ET.Element("node"),
    )


def _make_schema_columns():
    """Return a sample FLOW schema with varied types for testing."""
    return {
        "FLOW": [
            SchemaColumn(name="id", type="id_Integer", nullable=False, key=True, length=10),
            SchemaColumn(name="name", type="id_String", nullable=True, length=50),
            SchemaColumn(name="amount", type="id_Double", nullable=True),
            SchemaColumn(name="active", type="id_Boolean", nullable=False),
            SchemaColumn(name="created", type="id_Date", nullable=True,
                         date_pattern="yyyy-MM-dd"),
        ]
    }


# ------------------------------------------------------------------
# Registration
# ------------------------------------------------------------------


class TestSchemaComplianceCheckRegistration:
    def test_registered_in_registry(self):
        assert REGISTRY.get("tSchemaComplianceCheck") is SchemaComplianceCheckConverter


# ------------------------------------------------------------------
# Basic conversion
# ------------------------------------------------------------------


class TestSchemaComplianceCheckBasic:
    def test_basic_conversion_with_all_flags(self):
        """Full conversion with all four boolean flags set to true."""
        node = _make_node(
            params={
                "CHECK_ALL": "true",
                "SUB_STRING": "true",
                "STRICT_DATE_CHECK": "true",
                "ALL_EMPTY_ARE_NULL": "true",
            },
            schema=_make_schema_columns(),
        )
        result = SchemaComplianceCheckConverter().convert(node, [], {})

        assert isinstance(result, ComponentResult)
        comp = result.component
        assert comp["id"] == "scc_1"
        assert comp["type"] == "SchemaComplianceCheck"
        assert comp["original_type"] == "tSchemaComplianceCheck"
        assert comp["position"] == {"x": 100, "y": 200}
        assert comp["inputs"] == []
        assert comp["outputs"] == []

        cfg = comp["config"]
        assert cfg["check_all"] is True
        assert cfg["sub_string"] is True
        assert cfg["strict_date_check"] is True
        assert cfg["all_empty_are_null"] is True

        # Config schema should have 5 entries with converted Python types
        assert len(cfg["schema"]) == 5
        assert cfg["schema"][0] == {"name": "id", "type": "int", "nullable": False, "length": 10}
        assert cfg["schema"][1] == {"name": "name", "type": "str", "nullable": True, "length": 50}
        assert cfg["schema"][2] == {"name": "amount", "type": "float", "nullable": True}
        assert cfg["schema"][3] == {"name": "active", "type": "bool", "nullable": False}
        assert cfg["schema"][4] == {"name": "created", "type": "datetime", "nullable": True}

        assert result.warnings == []

    def test_default_flags_are_false(self):
        """When no boolean flags are set, they default to false."""
        node = _make_node(
            params={},
            schema=_make_schema_columns(),
        )
        result = SchemaComplianceCheckConverter().convert(node, [], {})

        cfg = result.component["config"]
        assert cfg["check_all"] is False
        assert cfg["sub_string"] is False
        assert cfg["strict_date_check"] is False
        assert cfg["all_empty_are_null"] is False
        assert result.warnings == []

    def test_mixed_flags(self):
        """Only some flags set; others default to false."""
        node = _make_node(
            params={
                "CHECK_ALL": "true",
                "SUB_STRING": "false",
                "STRICT_DATE_CHECK": "true",
            },
            schema=_make_schema_columns(),
        )
        result = SchemaComplianceCheckConverter().convert(node, [], {})

        cfg = result.component["config"]
        assert cfg["check_all"] is True
        assert cfg["sub_string"] is False
        assert cfg["strict_date_check"] is True
        assert cfg["all_empty_are_null"] is False


# ------------------------------------------------------------------
# Schema handling
# ------------------------------------------------------------------


class TestSchemaComplianceCheckSchema:
    def test_transform_schema_passthrough(self):
        """Input and output schemas should be identical (passthrough)."""
        node = _make_node(
            params={"CHECK_ALL": "true"},
            schema=_make_schema_columns(),
        )
        result = SchemaComplianceCheckConverter().convert(node, [], {})

        schema = result.component["schema"]
        assert schema["input"] == schema["output"]
        assert len(schema["input"]) == 5
        assert schema["input"][0]["name"] == "id"
        assert schema["input"][0]["type"] == "int"
        assert schema["input"][4]["name"] == "created"
        assert schema["input"][4]["type"] == "datetime"

    def test_empty_schema_produces_warning(self):
        """When no FLOW schema is present, a warning should be generated."""
        node = _make_node(params={"CHECK_ALL": "true"})
        result = SchemaComplianceCheckConverter().convert(node, [], {})

        assert result.component["schema"] == {"input": [], "output": []}
        assert result.component["config"]["schema"] == []
        assert any("No FLOW schema" in w for w in result.warnings)

    def test_schema_types_are_converted_from_talend(self):
        """Config schema types must be Python types, not raw Talend types."""
        node = _make_node(
            params={},
            schema={
                "FLOW": [
                    SchemaColumn(name="col_str", type="id_String", nullable=True),
                    SchemaColumn(name="col_long", type="id_Long", nullable=False),
                    SchemaColumn(name="col_decimal", type="id_BigDecimal", nullable=True),
                    SchemaColumn(name="col_char", type="id_Character", nullable=True),
                ]
            },
        )
        result = SchemaComplianceCheckConverter().convert(node, [], {})

        cfg_schema = result.component["config"]["schema"]
        assert cfg_schema[0]["type"] == "str"
        assert cfg_schema[1]["type"] == "int"     # id_Long -> int
        assert cfg_schema[2]["type"] == "Decimal"  # id_BigDecimal -> Decimal
        assert cfg_schema[3]["type"] == "str"      # id_Character -> str

    def test_length_only_included_when_present(self):
        """Length should only appear in config schema when >= 0 in source."""
        node = _make_node(
            params={},
            schema={
                "FLOW": [
                    SchemaColumn(name="with_len", type="id_String", nullable=True, length=100),
                    SchemaColumn(name="no_len", type="id_String", nullable=True),
                ]
            },
        )
        result = SchemaComplianceCheckConverter().convert(node, [], {})

        cfg_schema = result.component["config"]["schema"]
        assert cfg_schema[0] == {"name": "with_len", "type": "str", "nullable": True, "length": 100}
        assert cfg_schema[1] == {"name": "no_len", "type": "str", "nullable": True}
        assert "length" not in cfg_schema[1]


# ------------------------------------------------------------------
# Edge cases
# ------------------------------------------------------------------


class TestSchemaComplianceCheckEdgeCases:
    def test_boolean_params_as_actual_booleans(self):
        """Handle boolean params that arrive as Python bools (not strings)."""
        node = _make_node(
            params={
                "CHECK_ALL": True,
                "SUB_STRING": False,
                "STRICT_DATE_CHECK": True,
                "ALL_EMPTY_ARE_NULL": False,
            },
            schema=_make_schema_columns(),
        )
        result = SchemaComplianceCheckConverter().convert(node, [], {})

        cfg = result.component["config"]
        assert cfg["check_all"] is True
        assert cfg["sub_string"] is False
        assert cfg["strict_date_check"] is True
        assert cfg["all_empty_are_null"] is False

    def test_custom_component_id_and_position(self):
        """Verify component_id and position propagate correctly."""
        node = _make_node(
            params={"CHECK_ALL": "true"},
            schema=_make_schema_columns(),
            component_id="compliance_42",
        )
        node.position = {"x": 500, "y": 600}
        result = SchemaComplianceCheckConverter().convert(node, [], {})

        assert result.component["id"] == "compliance_42"
        assert result.component["position"] == {"x": 500, "y": 600}
