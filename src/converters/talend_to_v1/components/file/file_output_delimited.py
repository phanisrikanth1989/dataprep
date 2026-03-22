"""Converter for tFileOutputDelimited -> FileOutputDelimited."""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("tFileOutputDelimited")
class FileOutputDelimitedConverter(ComponentConverter):
    """Convert a Talend tFileOutputDelimited node to v1 FileOutputDelimited."""

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []

        csv_option = self._get_bool(node, "CSV_OPTION", False)

        # text_enclosure is only meaningful when csv_option is enabled
        if csv_option:
            text_enclosure = self._get_str(node, "TEXT_ENCLOSURE")
        else:
            text_enclosure = None

        config: Dict[str, Any] = {
            "filepath": self._get_str(node, "FILENAME"),
            "delimiter": self._get_str(node, "FIELDSEPARATOR", ","),
            "row_separator": self._get_str(node, "ROWSEPARATOR", "\\n"),
            "encoding": self._get_str(node, "ENCODING", "UTF-8"),
            "text_enclosure": text_enclosure,
            "include_header": self._get_bool(node, "INCLUDEHEADER", True),
            "append": self._get_bool(node, "APPEND", False),
            "create_directory": self._get_bool(node, "CREATE", True),
            "delete_empty_file": self._get_bool(node, "DELETE_EMPTYFILE", True),
            "die_on_error": self._get_bool(node, "DIE_ON_ERROR", False),
            "csv_option": csv_option,
        }

        # Warn when filepath is empty -- it is mandatory in Talend
        if not config["filepath"]:
            warnings.append("FILENAME is empty — this is a required parameter")

        component = self._build_component_dict(
            node=node,
            type_name="FileOutputDelimited",
            config=config,
            schema={"input": self._parse_schema(node), "output": []},
        )

        return ComponentResult(component=component, warnings=warnings)
