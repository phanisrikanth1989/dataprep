"""Converter for tPython -> PythonComponent.

Fixes CONV-PC-001: the old converter never extracted the CODE field,
leaving python_code always empty.  We use ``_get_param`` (not ``_get_str``)
because CODE contains raw Python source that must not have quotes stripped.
"""
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


@REGISTRY.register("tPython")
class PythonComponentConverter(ComponentConverter):
    """Convert a Talend tPython node to v1 PythonComponent."""

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []

        # Extract and decode CODE — use _get_param to preserve quotes in code
        raw_code = self._get_param(node, "CODE", "")
        python_code = _decode_xml_linebreaks(raw_code) if raw_code else ""

        # Extract and decode IMPORT
        raw_imports = self._get_param(node, "IMPORT", "")
        imports = _decode_xml_linebreaks(raw_imports) if raw_imports else ""

        if not python_code:
            warnings.append("CODE is empty -- PythonComponent will have no logic")

        config: Dict[str, Any] = {
            "python_code": python_code,
            "imports": imports,
        }

        schema_cols = self._parse_schema(node)
        component = self._build_component_dict(
            node=node,
            type_name="PythonComponent",
            config=config,
            schema={"input": schema_cols, "output": schema_cols},
        )

        return ComponentResult(component=component, warnings=warnings)
