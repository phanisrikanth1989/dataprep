"""Converter for tJava -> JavaComponent."""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


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


@REGISTRY.register("tJava")
class JavaComponentConverter(ComponentConverter):
    """Convert a Talend tJava node to v1 JavaComponent."""

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
            warnings.append("CODE is empty -- JavaComponent will have no logic")

        config: Dict[str, Any] = {
            "java_code": java_code,
            "imports": imports,
        }

        schema_cols = self._parse_schema(node)
        component = self._build_component_dict(
            node=node,
            type_name="JavaComponent",
            config=config,
            schema={"input": schema_cols, "output": schema_cols},
        )

        return ComponentResult(component=component, warnings=warnings)
