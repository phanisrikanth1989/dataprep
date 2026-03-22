"""Single source of truth for Talend type to Python type mapping."""

TALEND_TO_PYTHON = {
    "id_String": "str",
    "id_Integer": "int",
    "id_Long": "int",
    "id_Double": "float",
    "id_Float": "float",
    "id_Boolean": "bool",
    "id_Date": "datetime",
    "id_BigDecimal": "Decimal",
    "id_Object": "object",
    "id_Character": "str",
    "id_Byte": "int",
    "id_Short": "int",
}


def convert_type(talend_type: str) -> str:
    """Convert a Talend type string to a Python type string.

    Returns 'str' for unknown types.
    """
    return TALEND_TO_PYTHON.get(talend_type, "str")
