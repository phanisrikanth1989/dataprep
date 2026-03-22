"""Converter for tFileInputFullRow -> FileInputFullRow."""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("tFileInputFullRow")
class FileInputFullRowConverter(ComponentConverter):
    """Convert a Talend tFileInputFullRow node to v1 FileInputFullRowComponent."""

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []

        config: Dict[str, Any] = {
            "filename": self._get_str(node, "FILENAME"),
            "row_separator": self._get_str(node, "ROWSEPARATOR", "\\n"),
            "remove_empty_row": self._get_bool(node, "REMOVE_EMPTY_ROW", False),
            "encoding": self._get_str(node, "ENCODING", "UTF-8"),
            "limit": self._get_int(node, "LIMIT", 0),
        }

        # Warn when filename is empty -- it is mandatory in Talend
        if not config["filename"]:
            warnings.append("FILENAME is empty — this is a required parameter")

        component = self._build_component_dict(
            node=node,
            type_name="FileInputFullRowComponent",
            config=config,
            schema={"input": [], "output": self._parse_schema(node)},
        )

        return ComponentResult(component=component, warnings=warnings)
