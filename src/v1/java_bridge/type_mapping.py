"""Bridge-side type mapping: 7 Python types to Arrow types.

This module defines the ONLY valid type strings for the Java bridge layer.
The converter layer maps raw Talend types to Python type strings
(see ``src/converters/talend_to_v1/type_mapping.py``). This module then
maps those Python type strings to Arrow types for serialization.

The two modules form a pipeline:
    Talend raw type -> Python type string -> Arrow type

If an invalid type string reaches this module, it raises ValueError
immediately. There are NO Talend raw type entries here -- they must be
resolved before data reaches the bridge.
"""

import logging
from typing import Any

import pyarrow as pa

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Python type string -> Arrow type
# ------------------------------------------------------------------

PYTHON_TO_ARROW: dict[str, pa.DataType] = {
    "str": pa.string(),
    "int": pa.int64(),
    "float": pa.float64(),
    "bool": pa.bool_(),
    "datetime": pa.timestamp("ns"),
    "Decimal": pa.decimal128(38, 18),
    "object": pa.string(),
}

# ------------------------------------------------------------------
# Python type string -> Java type name (for schema conversion)
# ------------------------------------------------------------------

PYTHON_TO_JAVA: dict[str, str] = {
    "str": "String",
    "int": "Long",
    "float": "Double",
    "bool": "Boolean",
    "datetime": "Date",
    "Decimal": "BigDecimal",
    "object": "String",
}

# ------------------------------------------------------------------
# Valid type set (frozen for fast membership checks)
# ------------------------------------------------------------------

VALID_TYPES: frozenset[str] = frozenset(PYTHON_TO_ARROW.keys())


# ------------------------------------------------------------------
# Validation
# ------------------------------------------------------------------

def validate_schema_types(schema: dict[str, str]) -> None:
    """Validate that all type strings in a schema dict are in the 7 valid types.

    Args:
        schema: Mapping of column name to Python type string.

    Raises:
        ValueError: If any type string is not in VALID_TYPES.
    """
    invalid = {
        col: col_type
        for col, col_type in schema.items()
        if col_type not in VALID_TYPES
    }
    if invalid:
        raise ValueError(
            f"Invalid type strings in schema: {invalid}. "
            f"Valid types are: {sorted(VALID_TYPES)}"
        )


# ------------------------------------------------------------------
# Arrow schema construction
# ------------------------------------------------------------------

def build_arrow_schema(
    schema_dict: dict[str, str],
    precision_map: dict[str, tuple[int, int]] | None = None,
) -> pa.Schema:
    """Build a PyArrow Schema from a Python type string schema dict.

    For Decimal columns, checks ``precision_map`` for per-column
    (precision, scale) overrides. Falls back to (38, 18) if not provided.

    Args:
        schema_dict: Mapping of column name to Python type string.
        precision_map: Optional mapping of column name to (precision, scale)
            for Decimal columns.

    Returns:
        PyArrow Schema with one field per column.
    """
    if precision_map is None:
        precision_map = {}

    fields: list[pa.Field] = []
    for col_name, col_type in schema_dict.items():
        if col_type == "Decimal" and col_name in precision_map:
            precision, scale = precision_map[col_name]
            arrow_type = pa.decimal128(precision, scale)
        elif col_type in PYTHON_TO_ARROW:
            arrow_type = PYTHON_TO_ARROW[col_type]
        else:
            # Should never happen after validate_schema_types, but be safe
            logger.warning(
                "[WARN] Unknown type '%s' for column '%s' -- defaulting to string",
                col_type,
                col_name,
            )
            arrow_type = pa.string()
        fields.append(pa.field(col_name, arrow_type))

    return pa.schema(fields)


# ------------------------------------------------------------------
# Precision map extraction
# ------------------------------------------------------------------

def extract_precision_map(
    schema_columns: list[dict[str, Any]],
) -> dict[str, tuple[int, int]]:
    """Extract Decimal precision/scale info from full schema column list.

    In the converter schema format (inherited from Talend convention):
        - ``"length"`` holds the total number of digits (precision)
        - ``"precision"`` holds the number of decimal places (scale)

    This is the Talend convention, not the usual SQL convention where
    "precision" means total digits.

    Args:
        schema_columns: List of column dicts with keys: name, type,
            nullable, length, precision, etc.

    Returns:
        Mapping of column name to (precision, scale) for Decimal columns only.
    """
    precision_map: dict[str, tuple[int, int]] = {}

    for col in schema_columns:
        if col.get("type") != "Decimal":
            continue

        col_name = col.get("name", "")
        if not col_name:
            continue

        # length = total digits (precision), precision = decimal places (scale)
        total_digits = col.get("length", 38)
        if not isinstance(total_digits, int) or total_digits <= 0:
            total_digits = 38

        decimal_places = col.get("precision", 18)
        if not isinstance(decimal_places, int) or decimal_places < 0:
            decimal_places = 18

        precision_map[col_name] = (total_digits, decimal_places)

    return precision_map
