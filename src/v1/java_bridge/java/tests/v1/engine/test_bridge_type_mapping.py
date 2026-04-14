"""Unit tests for src/v1/java_bridge/type_mapping.py.

Validates the 7-type contract: str, int, float, bool, datetime, Decimal, object.
Tests cover Arrow mapping, Java mapping, validation, schema building, and
precision map extraction.
"""

import pytest
import pyarrow as pa

from src.v1.java_bridge.type_mapping import (
    PYTHON_TO_ARROW,
    PYTHON_TO_JAVA,
    VALID_TYPES,
    build_arrow_schema,
    extract_precision_map,
    validate_schema_types,
)


# ------------------------------------------------------------------
# TestPythonToArrow
# ------------------------------------------------------------------


@pytest.mark.unit
class TestPythonToArrow:
    """Verify PYTHON_TO_ARROW dict maps all 7 types to correct Arrow types."""

    def test_all_seven_types_present(self):
        assert len(PYTHON_TO_ARROW) == 7
        expected_keys = {"str", "int", "float", "bool", "datetime", "Decimal", "object"}
        assert set(PYTHON_TO_ARROW.keys()) == expected_keys

    def test_str_maps_to_string(self):
        assert PYTHON_TO_ARROW["str"] == pa.string()

    def test_int_maps_to_int64(self):
        assert PYTHON_TO_ARROW["int"] == pa.int64()

    def test_float_maps_to_float64(self):
        assert PYTHON_TO_ARROW["float"] == pa.float64()

    def test_bool_maps_to_bool(self):
        assert PYTHON_TO_ARROW["bool"] == pa.bool_()

    def test_datetime_maps_to_timestamp(self):
        assert PYTHON_TO_ARROW["datetime"] == pa.timestamp("ns")

    def test_decimal_maps_to_decimal128(self):
        assert PYTHON_TO_ARROW["Decimal"] == pa.decimal128(38, 18)

    def test_object_maps_to_string(self):
        assert PYTHON_TO_ARROW["object"] == pa.string()


# ------------------------------------------------------------------
# TestPythonToJava
# ------------------------------------------------------------------


@pytest.mark.unit
class TestPythonToJava:
    """Verify PYTHON_TO_JAVA dict maps all 7 types to correct Java types."""

    def test_all_seven_types_present(self):
        assert len(PYTHON_TO_JAVA) == 7
        expected_keys = {"str", "int", "float", "bool", "datetime", "Decimal", "object"}
        assert set(PYTHON_TO_JAVA.keys()) == expected_keys

    def test_mappings(self):
        expected = {
            "str": "String",
            "int": "Long",
            "float": "Double",
            "bool": "Boolean",
            "datetime": "Date",
            "Decimal": "BigDecimal",
            "object": "String",
        }
        for py_type, java_type in expected.items():
            assert PYTHON_TO_JAVA[py_type] == java_type, (
                f"Expected {py_type} -> {java_type}, got {PYTHON_TO_JAVA[py_type]}"
            )


# ------------------------------------------------------------------
# TestValidateSchemaTypes
# ------------------------------------------------------------------


@pytest.mark.unit
class TestValidateSchemaTypes:
    """Verify validate_schema_types accepts valid types and rejects invalid."""

    def test_valid_schema_passes(self):
        validate_schema_types({"col1": "str", "col2": "int"})

    def test_all_seven_types_valid(self):
        schema = {f"col_{t}": t for t in VALID_TYPES}
        validate_schema_types(schema)

    def test_invalid_type_raises(self):
        with pytest.raises(ValueError, match="id_String"):
            validate_schema_types({"col": "id_String"})

    def test_multiple_invalid_types(self):
        with pytest.raises(ValueError):
            validate_schema_types({"a": "id_Integer", "b": "id_Long"})

    def test_empty_schema_passes(self):
        validate_schema_types({})

    def test_mixed_valid_invalid(self):
        with pytest.raises(ValueError, match="id_Float"):
            validate_schema_types({"a": "str", "b": "id_Float"})


# ------------------------------------------------------------------
# TestBuildArrowSchema
# ------------------------------------------------------------------


@pytest.mark.unit
class TestBuildArrowSchema:
    """Verify build_arrow_schema constructs correct Arrow schemas."""

    def test_basic_schema(self):
        schema = build_arrow_schema({"name": "str", "age": "int"})
        assert len(schema) == 2
        assert schema.field("name").type == pa.string()
        assert schema.field("age").type == pa.int64()

    def test_decimal_default_precision(self):
        schema = build_arrow_schema({"amount": "Decimal"})
        assert schema.field("amount").type == pa.decimal128(38, 18)

    def test_decimal_custom_precision(self):
        schema = build_arrow_schema(
            {"amount": "Decimal"},
            precision_map={"amount": (10, 2)},
        )
        assert schema.field("amount").type == pa.decimal128(10, 2)

    def test_decimal_mixed_precision(self):
        schema = build_arrow_schema(
            {"price": "Decimal", "tax": "Decimal"},
            precision_map={"price": (10, 2)},
        )
        assert schema.field("price").type == pa.decimal128(10, 2)
        assert schema.field("tax").type == pa.decimal128(38, 18)

    def test_all_seven_types(self):
        schema_dict = {
            "s": "str",
            "i": "int",
            "f": "float",
            "b": "bool",
            "d": "datetime",
            "dec": "Decimal",
            "o": "object",
        }
        schema = build_arrow_schema(schema_dict)
        assert len(schema) == 7
        assert schema.field("s").type == pa.string()
        assert schema.field("i").type == pa.int64()
        assert schema.field("f").type == pa.float64()
        assert schema.field("b").type == pa.bool_()
        assert schema.field("d").type == pa.timestamp("ns")
        assert schema.field("dec").type == pa.decimal128(38, 18)
        assert schema.field("o").type == pa.string()


# ------------------------------------------------------------------
# TestExtractPrecisionMap
# ------------------------------------------------------------------


@pytest.mark.unit
class TestExtractPrecisionMap:
    """Verify extract_precision_map extracts Decimal precision/scale info."""

    def test_decimal_column_extraction(self):
        schema_columns = [
            {"name": "amount", "type": "Decimal", "length": 10, "precision": 2},
        ]
        result = extract_precision_map(schema_columns)
        assert result == {"amount": (10, 2)}

    def test_non_decimal_ignored(self):
        schema_columns = [
            {"name": "name", "type": "str", "length": 255, "precision": 0},
            {"name": "age", "type": "int", "length": 10, "precision": 0},
        ]
        result = extract_precision_map(schema_columns)
        assert result == {}

    def test_defaults_when_missing(self):
        schema_columns = [
            {"name": "amount", "type": "Decimal"},
        ]
        result = extract_precision_map(schema_columns)
        assert result == {"amount": (38, 18)}

    def test_empty_schema(self):
        result = extract_precision_map([])
        assert result == {}

    def test_multiple_decimal_columns(self):
        schema_columns = [
            {"name": "price", "type": "Decimal", "length": 10, "precision": 2},
            {"name": "tax_rate", "type": "Decimal", "length": 5, "precision": 4},
        ]
        result = extract_precision_map(schema_columns)
        assert result == {"price": (10, 2), "tax_rate": (5, 4)}

    def test_talend_convention_length_is_total_precision_is_scale(self):
        """Verify Talend convention: 'length' = total digits, 'precision' = decimal places.

        This is opposite of SQL convention where 'precision' means total digits.
        """
        schema_columns = [
            {"name": "value", "type": "Decimal", "length": 20, "precision": 6},
        ]
        result = extract_precision_map(schema_columns)
        total_digits, decimal_places = result["value"]
        # length (20) -> total digits (first element)
        assert total_digits == 20
        # precision (6) -> decimal places (second element)
        assert decimal_places == 6
