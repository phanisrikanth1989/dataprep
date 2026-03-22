"""Converter for tFileOutputPositional -> FileOutputPositional."""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("tFileOutputPositional")
class FileOutputPositionalConverter(ComponentConverter):
    """Convert a Talend tFileOutputPositional node to v1 FileOutputPositional."""

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
            "append": self._get_bool(node, "APPEND", False),
            "include_header": self._get_bool(node, "INCLUDEHEADER", False),
            "compress": self._get_bool(node, "COMPRESS", False),
            "encoding": self._get_str(node, "ENCODING", "UTF-8"),
            "create": self._get_bool(node, "CREATE", True),
            "flush_on_row": self._get_bool(node, "FLUSHONROW", False),
            "flush_on_row_num": self._get_int(node, "FLUSHONROW_NUM", 1),
            "delete_empty_file": self._get_bool(node, "DELETE_EMPTYFILE", False),
            "die_on_error": self._get_bool(node, "DIE_ON_ERROR", True),
        }

        # Parse FORMATS TABLE param — list of positional format entries
        formats_raw = node.params.get("FORMATS", [])
        formats: List[Dict[str, str]] = []
        for entry in formats_raw:
            fmt: Dict[str, str] = {}
            if "SCHEMA_COLUMN" in entry:
                fmt["schema_column"] = entry["SCHEMA_COLUMN"]
            if "size" in entry:
                fmt["size"] = entry["size"]
            if "padding_char" in entry:
                fmt["padding_char"] = entry["padding_char"]
            if "align" in entry:
                fmt["align"] = entry["align"]
            if fmt:
                formats.append(fmt)
        config["formats"] = formats

        # Warn when filename is empty — it is mandatory in Talend
        if not config["filename"]:
            warnings.append("FILENAME is empty — this is a required parameter")

        component = self._build_component_dict(
            node=node,
            type_name="FileOutputPositional",
            config=config,
            schema={"input": self._parse_schema(node), "output": []},
        )

        return ComponentResult(component=component, warnings=warnings)
