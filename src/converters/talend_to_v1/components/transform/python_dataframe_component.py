"""Converter for tPythonDataFrame -> PythonDataFrameComponent."""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


def _decode_xml_linebreaks(text: str) -> str:
    """Decode XML-encoded line break entities in Talend code fields."""
    if not text:
        return text
    text = text.replace("&#xD;&#xA;", "\n")
    text = text.replace("&#xA;", "\n")
    text = text.replace("&#xD;", "\n")
    return text


@REGISTRY.register("tPythonDataFrame")
class PythonDataFrameComponentConverter(ComponentConverter):
    """Convert a Talend tPythonDataFrame node to v1 PythonDataFrameComponent."""

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []

        # Extract CODE (python_code) — decode XML linebreak entities
        raw_code = self._get_param(node, "CODE", "")
        python_code = _decode_xml_linebreaks(raw_code) if raw_code else ""
        if not python_code:
            warnings.append(
                "CODE is empty -- PythonDataFrameComponent will have no logic"
            )

        # Extract DIE_ON_ERROR (bool)
        die_on_error = self._get_bool(node, "DIE_ON_ERROR", default=False)

        config: Dict[str, Any] = {
            "python_code": python_code,
            "die_on_error": die_on_error,
        }

        schema_cols = self._parse_schema(node)
        component = self._build_component_dict(
            node=node,
            type_name="PythonDataFrameComponent",
            config=config,
            schema={"input": schema_cols, "output": schema_cols},
        )

        return ComponentResult(component=component, warnings=warnings)
