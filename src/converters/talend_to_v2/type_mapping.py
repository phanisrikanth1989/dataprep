"""Talend type to V2 type mapping."""
from __future__ import annotations

from typing import Any, Dict, List

from .expression_translator import convert_date_pattern
from .xml_parser import SchemaColumn

# Talend type -> V2 schema type
_SCHEMA_TYPE_MAP = {
    "id_String": "string",
    "id_Integer": "integer",
    "id_Long": "integer",
    "id_Float": "float",
    "id_Double": "float",
    "id_Boolean": "boolean",
    "id_Date": "date",
    "id_BigDecimal": "string",
}

# Talend type -> V2 context variable type
_CONTEXT_TYPE_MAP = {
    "id_String": "str",
    "id_Integer": "int",
    "id_Long": "int",
    "id_Float": "float",
    "id_Double": "float",
    "id_Boolean": "bool",
    "id_Date": "date",
    "id_BigDecimal": "str",
}


def convert_talend_type(talend_type: str) -> str:
    """Convert a Talend type ID to a V2 schema type name."""
    return _SCHEMA_TYPE_MAP.get(talend_type, talend_type.lower())


def convert_context_type(talend_type: str) -> str:
    """Convert a Talend type ID to a V2 context variable type."""
    return _CONTEXT_TYPE_MAP.get(talend_type, "str")


def convert_schema(columns: List[SchemaColumn]) -> List[Dict[str, Any]]:
    """Convert a list of Talend schema columns to V2 format."""
    result = []
    for col in columns:
        v2_col: Dict[str, Any] = {
            "name": col.name,
            "type": convert_talend_type(col.type),
        }
        if col.date_pattern:
            v2_col["date_pattern"] = convert_date_pattern(col.date_pattern)
        result.append(v2_col)
    return result
