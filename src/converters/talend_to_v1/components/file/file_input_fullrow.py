"""Converter for tFileInputFullRow -> FileInputFullRowComponent."""
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
            # Core params
            "filename": self._get_str(node, "FILENAME"),
            "row_separator": self._get_str(node, "ROWSEPARATOR", "\\n"),
            "remove_empty_row": self._get_bool(node, "REMOVE_EMPTY_ROW", True),
            "encoding": self._get_str(node, "ENCODING", "ISO-8859-15"),
            "limit": self._get_str(node, "LIMIT", ""),
            "header_rows": self._get_int(node, "HEADER", 0),
            "footer_rows": self._get_int(node, "FOOTER", 0),
            "die_on_error": self._get_bool(node, "DIE_ON_ERROR", True),
            # Advanced params
            "random": self._get_bool(node, "RANDOM", False),
            "nb_random": self._get_int(node, "NB_RANDOM", 10),
            # Metadata
            "tstatcatcher_stats": self._get_bool(node, "TSTATCATCHER_STATS", False),
            "label": self._get_str(node, "LABEL"),
        }

        # Warn when filename is empty -- it is mandatory in Talend
        if not config["filename"]:
            warnings.append("FILENAME is empty — this is a required parameter")

        # Engine-gap warnings
        if config["header_rows"] > 0:
            warnings.append(
                f"HEADER={config['header_rows']}: engine does not skip header rows"
            )
        if config["footer_rows"] > 0:
            warnings.append(
                f"FOOTER={config['footer_rows']}: engine does not skip footer rows"
            )
        if config["random"]:
            warnings.append(
                "RANDOM=true: engine does not support random line extraction"
            )

        # Column name warning: only when schema defines a non-default name
        schema_cols = self._parse_schema(node)
        if schema_cols and schema_cols[0].get("name") != "line":
            warnings.append(
                f"Engine hardcodes output column name to 'line', "
                f"ignoring schema-defined column name '{schema_cols[0]['name']}'"
            )

        component = self._build_component_dict(
            node=node,
            type_name="FileInputFullRowComponent",
            config=config,
            schema={"input": [], "output": schema_cols},
        )

        return ComponentResult(component=component, warnings=warnings)
