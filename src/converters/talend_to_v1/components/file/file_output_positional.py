"""Converter for tFileOutputPositional -> FileOutputPositional."""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("tFileOutputPositional")
class FileOutputPositionalConverter(ComponentConverter):
    """Convert a Talend tFileOutputPositional node to v1 FileOutputPositional."""

    @staticmethod
    def _parse_formats_table(raw: list) -> list:
        """Parse FORMATS TABLE from flat elementRef/value pairs into per-column dicts.

        Input (from XML parser):
            [{"elementRef": "SCHEMA_COLUMN", "value": "id"},
             {"elementRef": "SIZE", "value": "10"},
             {"elementRef": "PADDING_CHAR", "value": "' '"},
             {"elementRef": "ALIGN", "value": "'L'"},
             {"elementRef": "KEEP", "value": "'A'"},
             {"elementRef": "SCHEMA_COLUMN", "value": "name"}, ...]

        Output:
            [{"schema_column": "id", "size": "10", "padding_char": "' '",
              "align": "'L'", "keep": "'A'"}, ...]
        """
        if not raw or not isinstance(raw, list):
            return []

        result: list = []
        current: Dict[str, str] = {}
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            ref = entry.get("elementRef", "")
            val = entry.get("value", "")
            if ref == "SCHEMA_COLUMN":
                if current and "schema_column" in current:
                    result.append(current)
                current = {"schema_column": val}
            elif ref == "SIZE":
                current["size"] = val
            elif ref == "PADDING_CHAR":
                current["padding_char"] = val
            elif ref == "ALIGN":
                current["align"] = val
            elif ref == "KEEP":
                current["keep"] = val
        if current and "schema_column" in current:
            result.append(current)
        return result

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []

        config: Dict[str, Any] = {
            # Core params
            "filepath": self._get_str(node, "FILENAME"),
            "row_separator": self._get_str(node, "ROWSEPARATOR", "\\n"),
            "append": self._get_bool(node, "APPEND", False),
            "include_header": self._get_bool(node, "INCLUDEHEADER", False),
            "compress": self._get_bool(node, "COMPRESS", False),
            "encoding": self._get_str(node, "ENCODING", "ISO-8859-15"),
            "create": self._get_bool(node, "CREATE", True),
            "flush_on_row": self._get_bool(node, "FLUSHONROW", False),
            "flush_on_row_num": self._get_int(node, "FLUSHONROW_NUM", 1),
            "delete_empty_file": self._get_bool(node, "DELETE_EMPTYFILE", False),
            # Advanced params
            "advanced_separator": self._get_bool(node, "ADVANCED_SEPARATOR", False),
            "thousands_separator": self._get_str(node, "THOUSANDS_SEPARATOR", ","),
            "decimal_separator": self._get_str(node, "DECIMAL_SEPARATOR", "."),
            "use_byte": self._get_bool(node, "USE_BYTE", False),
            "row_mode": self._get_bool(node, "ROW_MODE", False),
            # Metadata
            "tstatcatcher_stats": self._get_bool(node, "TSTATCATCHER_STATS", False),
            "label": self._get_str(node, "LABEL"),
            # Table parameters
            "formats": self._parse_formats_table(
                node.params.get("FORMATS", [])),
        }

        # Warn when filepath is empty — it is mandatory in Talend
        if not config["filepath"]:
            warnings.append("FILENAME is empty — this is a required parameter")

        # Engine-gap warnings
        if config["compress"]:
            warnings.append("COMPRESS=true: engine uses gzip compression, Talend uses ZIP format")
        if config["advanced_separator"]:
            warnings.append("ADVANCED_SEPARATOR=true: engine does not support locale-aware number formatting")
        if config["use_byte"]:
            warnings.append("USE_BYTE=true: engine does not support byte-length column sizing")
        if config["flush_on_row"]:
            warnings.append("FLUSHONROW=true: engine does not support custom flush buffer sizing")
        if config["delete_empty_file"]:
            warnings.append("DELETE_EMPTYFILE=true: engine does not support suppressing empty file generation")
        if config["row_mode"]:
            warnings.append("ROW_MODE=true: engine always writes in row mode regardless of this setting")

        component = self._build_component_dict(
            node=node,
            type_name="FileOutputPositional",
            config=config,
            schema={"input": self._parse_schema(node), "output": []},
        )

        return ComponentResult(component=component, warnings=warnings)
