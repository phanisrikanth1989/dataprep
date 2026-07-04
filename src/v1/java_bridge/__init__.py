"""Java Bridge Layer for ETL Engine.

This module provides Java execution capabilities for the ETL engine using:
- Apache Arrow for efficient data transfer (schema-driven, not inferred)
- Py4J for Java-Python communication
- Groovy for dynamic Java code execution

Main components:
- JavaBridge: Core bridge class for Java execution
- type_mapping: Python type -> Arrow type mapping (7-type contract)
"""

from .bridge import JavaBridge
from .type_mapping import (
    PYTHON_TO_ARROW,
    PYTHON_TO_JAVA,
    VALID_TYPES,
    build_arrow_schema,
    extract_precision_map,
    validate_schema_types,
)

__all__ = [
    "JavaBridge",
    "PYTHON_TO_ARROW",
    "PYTHON_TO_JAVA",
    "VALID_TYPES",
    "build_arrow_schema",
    "extract_precision_map",
    "validate_schema_types",
]
