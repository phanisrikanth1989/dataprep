# tests/converters/talend_to_v2/test_type_mapping.py
import pytest
from src.converters.talend_to_v2.type_mapping import (
    convert_talend_type,
    convert_schema,
    convert_context_type,
)
from src.converters.talend_to_v2.xml_parser import SchemaColumn


class TestConvertTalendType:
    def test_string_types(self):
        assert convert_talend_type("id_String") == "string"

    def test_integer_types(self):
        assert convert_talend_type("id_Integer") == "integer"
        assert convert_talend_type("id_Long") == "integer"

    def test_float_types(self):
        assert convert_talend_type("id_Float") == "float"
        assert convert_talend_type("id_Double") == "float"

    def test_boolean(self):
        assert convert_talend_type("id_Boolean") == "boolean"

    def test_date(self):
        assert convert_talend_type("id_Date") == "date"

    def test_decimal(self):
        assert convert_talend_type("id_BigDecimal") == "string"

    def test_unknown_lowercased(self):
        assert convert_talend_type("id_SomeCustom") == "id_somecustom"


class TestConvertSchema:
    def test_basic_schema(self):
        columns = [
            SchemaColumn(name="id", type="id_Integer", nullable=True),
            SchemaColumn(name="name", type="id_String", nullable=True),
        ]
        result = convert_schema(columns)
        assert result == [
            {"name": "id", "type": "integer"},
            {"name": "name", "type": "string"},
        ]

    def test_date_with_pattern(self):
        columns = [
            SchemaColumn(name="created", type="id_Date", nullable=True,
                        date_pattern="yyyy-MM-dd"),
        ]
        result = convert_schema(columns)
        assert result == [
            {"name": "created", "type": "date", "date_pattern": "%Y-%m-%d"},
        ]


class TestConvertContextType:
    def test_maps_to_v2_types(self):
        assert convert_context_type("id_String") == "str"
        assert convert_context_type("id_Integer") == "int"
        assert convert_context_type("id_Double") == "float"
        assert convert_context_type("id_Boolean") == "bool"
        assert convert_context_type("id_Date") == "date"
