"""Converter for tPythonRow -> PythonRowComponent.

tPythonRow is a transform component that executes custom Python code on each
row, producing an output row.  Key parameters:

* ``CODE``          -- Python source code to execute per row (XML-entity-encoded).
* ``DIE_ON_ERROR``  -- Whether to abort on error (bool, default ``True``).

The converter also builds an ``output_schema`` list of ``{name, type}`` dicts
derived from the FLOW schema metadata.

Audit fixes:
- CONV-PRC-001: CODE stored under correct key ``python_code`` (not ``CODE``).
- CONV-PRC-003: output_schema is now generated from FLOW metadata.
- CONV-PRC-005: DIE_ON_ERROR stored under correct key ``die_on_error`` (bool).
"""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


def _decode_xml_linebreaks(value: str) -> str:
    """Decode XML line-break entities to real newlines.

    Talend stores CODE values with XML-encoded line breaks:
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


@REGISTRY.register("tPythonRow")
class PythonRowComponentConverter(ComponentConverter):
    """Convert a Talend tPythonRow node to v1 PythonRowComponent."""

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []

        # Extract and decode CODE -> python_code  (fixes CONV-PRC-001)
        raw_code = self._get_param(node, "CODE", "")
        python_code = _decode_xml_linebreaks(raw_code) if raw_code else ""

        if not python_code:
            warnings.append("CODE is empty -- PythonRowComponent will have no logic")

        # Extract DIE_ON_ERROR -> die_on_error  (fixes CONV-PRC-005)
        die_on_error = self._get_bool(node, "DIE_ON_ERROR", True)

        # Build output_schema from FLOW schema columns  (fixes CONV-PRC-003)
        schema_cols = self._parse_schema(node)
        output_schema: List[Dict[str, str]] = [
            {"name": col["name"], "type": col["type"]}
            for col in schema_cols
        ]

        config: Dict[str, Any] = {
            "python_code": python_code,
            "die_on_error": die_on_error,
            "output_schema": output_schema,
        }

        component = self._build_component_dict(
            node=node,
            type_name="PythonRowComponent",
            config=config,
            schema={"input": schema_cols, "output": schema_cols},
        )

        return ComponentResult(component=component, warnings=warnings)
