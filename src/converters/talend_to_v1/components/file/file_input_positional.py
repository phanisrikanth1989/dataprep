"""Converter for tFileInputPositional -> FileInputPositional."""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("tFileInputPositional")
class FileInputPositionalConverter(ComponentConverter):
    """Convert a Talend tFileInputPositional node to v1 FileInputPositional."""

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []

        config: Dict[str, Any] = {
            "filepath": self._get_str(node, "FILENAME"),
            "row_separator": self._get_str(node, "ROWSEPARATOR", "\\n"),
            "pattern": self._get_str(node, "PATTERN"),
            "pattern_units": self._get_str(node, "PATTERN_UNITS", "SYMBOLS"),
            "remove_empty_row": self._get_bool(node, "REMOVE_EMPTY_ROW", False),
            "trim_all": self._get_bool(node, "TRIMALL", False),
            "encoding": self._get_str(node, "ENCODING", "UTF-8"),
            "header_rows": self._get_int(node, "HEADER", 0),
            "footer_rows": self._get_int(node, "FOOTER", 0),
            "limit": self._get_int(node, "LIMIT", 0),
            "die_on_error": self._get_bool(node, "DIE_ON_ERROR", False),
            "process_long_row": self._get_bool(node, "PROCESS_LONG_ROW", False),
            "advanced_separator": self._get_bool(node, "ADVANCED_SEPARATOR", False),
            "thousands_separator": self._get_str(node, "THOUSANDS_SEPARATOR", ","),
            "decimal_separator": self._get_str(node, "DECIMAL_SEPARATOR", "."),
            "check_date": self._get_bool(node, "CHECK_DATE", False),
            "uncompress": self._get_bool(node, "UNCOMPRESS", False),
        }

        # Warn when filepath is empty — it is mandatory in Talend
        if not config["filepath"]:
            warnings.append("FILENAME is empty — this is a required parameter")

        # Warn when pattern is empty — positional parsing requires a pattern
        if not config["pattern"]:
            warnings.append("PATTERN is empty — positional file parsing requires a pattern")

        component = self._build_component_dict(
            node=node,
            type_name="FileInputPositional",
            config=config,
            schema={"input": [], "output": self._parse_schema(node)},
        )

        return ComponentResult(component=component, warnings=warnings)
