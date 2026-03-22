"""Converter for tJavaRow -> JavaRowComponent.

tJavaRow is a transform component that executes custom Java code on each row,
producing an output row.  Key parameters:

* ``CODE``   -- Java source code to execute per row (XML-entity-encoded).
* ``IMPORT`` -- Java import statements (XML-entity-encoded).

The converter also builds an ``output_schema`` dict that maps each output
column name to its Java type (e.g. ``{"name": "String", "age": "Integer"}``),
derived from the FLOW schema metadata.
"""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)

# Python type -> Java type mapping (reverse of the Talend type conversion)
_PYTHON_TYPE_TO_JAVA: Dict[str, str] = {
    "str": "String",
    "int": "Integer",
    "float": "Double",
    "bool": "Boolean",
    "date": "Date",
    "datetime": "Date",
    "bytes": "byte[]",
    "Decimal": "BigDecimal",
    "object": "Object",
}


def _decode_xml_linebreaks(value: str) -> str:
    """Decode XML line-break entities to real newlines.

    Talend stores CODE and IMPORT values with XML-encoded line breaks:
    ``&#xD;&#xA;`` (CRLF), ``&#xA;`` (LF), ``&#xD;`` (CR).
    Order matters: replace the two-char sequence first so partial matches
    don't leave stray characters.
    """
    return (
        value
        .replace("&#xD;&#xA;", "\n")
        .replace("&#xA;", "\n")
        .replace("&#xD;", "\n")
    )


def _python_type_to_java(python_type: str) -> str:
    """Convert a Python type name to a Java type name for output_schema."""
    return _PYTHON_TYPE_TO_JAVA.get(python_type, "String")


@REGISTRY.register("tJavaRow")
class JavaRowComponentConverter(ComponentConverter):
    """Convert a Talend tJavaRow node to v1 JavaRowComponent."""

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []

        # Extract and decode CODE
        raw_code = self._get_param(node, "CODE", "")
        java_code = _decode_xml_linebreaks(raw_code) if raw_code else ""

        # Extract and decode IMPORT
        raw_imports = self._get_param(node, "IMPORT", "")
        imports = _decode_xml_linebreaks(raw_imports) if raw_imports else ""

        if not java_code:
            warnings.append("CODE is empty -- JavaRowComponent will have no logic")

        # Build output_schema from FLOW schema columns
        schema_cols = self._parse_schema(node)
        output_schema: Dict[str, str] = {}
        for col in schema_cols:
            output_schema[col["name"]] = _python_type_to_java(col["type"])

        config: Dict[str, Any] = {
            "java_code": java_code,
            "imports": imports,
            "output_schema": output_schema,
        }

        component = self._build_component_dict(
            node=node,
            type_name="JavaRowComponent",
            config=config,
            schema={"input": schema_cols, "output": schema_cols},
        )

        return ComponentResult(component=component, warnings=warnings)
