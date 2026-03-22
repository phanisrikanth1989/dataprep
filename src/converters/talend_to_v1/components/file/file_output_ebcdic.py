"""Converter for tFileOutputEBCDIC -> FileOutputEBCDIC.

Fixes P0 bug CONV-MISSING-002: the old complex_converter referenced
``parse_tfileoutputebcdic`` which did not exist, causing an AttributeError
at runtime whenever a job contained this component.
"""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("tFileOutputEBCDIC")
class FileOutputEBCDICConverter(ComponentConverter):
    """Convert a Talend tFileOutputEBCDIC node to v1 FileOutputEBCDIC."""

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []

        config: Dict[str, Any] = {
            "filename": self._get_str(node, "FILENAME"),
            "encoding": self._get_str(node, "ENCODING", "Cp1047"),
            "append": self._get_bool(node, "APPEND", False),
            "row_separator": self._get_str(node, "ROWSEPARATOR", "\\n"),
            "die_on_error": self._get_bool(node, "DIE_ON_ERROR", True),
        }

        # Warn when filename is empty -- it is mandatory in Talend
        if not config["filename"]:
            warnings.append("FILENAME is empty — this is a required parameter")

        component = self._build_component_dict(
            node=node,
            type_name="FileOutputEBCDIC",
            config=config,
            schema={"input": self._parse_schema(node), "output": []},
        )

        return ComponentResult(component=component, warnings=warnings)
