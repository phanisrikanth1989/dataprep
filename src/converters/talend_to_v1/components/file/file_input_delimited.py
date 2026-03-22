"""Converter for tFileInputDelimited -> FileInputDelimited."""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("tFileInputDelimited")
class FileInputDelimitedConverter(ComponentConverter):
    """Convert a Talend tFileInputDelimited node to v1 FileInputDelimited."""

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []

        config: Dict[str, Any] = {
            "filepath": self._get_str(node, "FILENAME"),
            "delimiter": self._get_str(node, "FIELDSEPARATOR", ","),
            "row_separator": self._get_str(node, "ROWSEPARATOR", "\\n"),
            "header_rows": self._get_int(node, "HEADER", 0),
            "footer_rows": self._get_int(node, "FOOTER", 0),
            "limit": self._get_int(node, "LIMIT", 0),
            "encoding": self._get_str(node, "ENCODING", "UTF-8"),
            "text_enclosure": self._get_str(node, "TEXT_ENCLOSURE"),
            "escape_char": self._get_str(node, "ESCAPE_CHAR"),
            "remove_empty_rows": self._get_bool(node, "REMOVE_EMPTY_ROW", False),
            "trim_all": self._get_bool(node, "TRIMALL", False),
            "die_on_error": self._get_bool(node, "DIE_ON_ERROR", False),
        }

        # Warn when filepath is empty — it is mandatory in Talend
        if not config["filepath"]:
            warnings.append("FILENAME is empty — this is a required parameter")

        component = self._build_component_dict(
            node=node,
            type_name="FileInputDelimited",
            config=config,
            schema={"input": [], "output": self._parse_schema(node)},
        )

        return ComponentResult(component=component, warnings=warnings)
