"""
Schema type mappings for file components.

Shared type mapping from config types to Polars types.
"""
import polars as pl

# Type mapping from config types to Polars types
TYPE_MAPPING = {
    # String types
    'string': pl.Utf8,
    'str': pl.Utf8,
    'id_String': pl.Utf8,

    # Integer types
    'integer': pl.Int64,
    'int': pl.Int64,
    'long': pl.Int64,
    'id_Integer': pl.Int64,
    'id_Long': pl.Int64,

    # Float types
    'float': pl.Float64,
    'double': pl.Float64,
    'id_Float': pl.Float64,
    'id_Double': pl.Float64,

    # Boolean
    'boolean': pl.Boolean,
    'bool': pl.Boolean,
    'id_Boolean': pl.Boolean,

    # Date/DateTime - native Polars date types
    'date': pl.Date,
    'datetime': pl.Datetime,
    'id_Date': pl.Date,

    # Decimal - read as string (Polars doesn't have Decimal)
    'decimal': pl.Utf8,
    'id_BigDecimal': pl.Utf8,
}

# Set of config type names that represent date/datetime types.
# Used by source components to apply date parsing after CSV read.
DATE_TYPES = {'date', 'datetime', 'id_Date'}
