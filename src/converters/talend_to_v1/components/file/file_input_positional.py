"""Converter for tFileInputPositional -> FileInputPositional."""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("tFileInputPositional")
class FileInputPositionalConverter(ComponentConverter):
    """Convert a Talend tFileInputPositional node to v1 FileInputPositional."""

    @staticmethod
    def _parse_formats_table(raw: list) -> list:
        """Parse FORMATS TABLE from flat elementRef/value pairs into per-column dicts.

        Input (from XML parser):
            [{"elementRef": "SCHEMA_COLUMN", "value": "id"},
             {"elementRef": "SIZE", "value": "10"},
             {"elementRef": "PADDING_CHAR", "value": "' '"},
             {"elementRef": "ALIGN", "value": "'L'"},
             {"elementRef": "SCHEMA_COLUMN", "value": "name"}, ...]

        Output:
            [{"schema_column": "id", "size": "10", "padding_char": "' '", "align": "'L'"},
             {"schema_column": "name", ...}, ...]
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
        if current and "schema_column" in current:
            result.append(current)
        return result

    @staticmethod
    def _parse_trim_select(raw: list) -> list:
        """Parse TRIMSELECT TABLE from flat elementRef/value pairs.

        Input:  [{"elementRef": "SCHEMA_COLUMN", "value": "id"},
                 {"elementRef": "TRIM", "value": "false"}, ...]
        Output: [{"column": "id", "trim": False}, ...]
        """
        if not raw or not isinstance(raw, list):
            return []

        result: list = []
        current: dict = {}
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            ref = entry.get("elementRef", "")
            val = entry.get("value", "")
            if ref == "SCHEMA_COLUMN":
                if current and "column" in current:
                    result.append(current)
                current = {"column": val}
            elif ref == "TRIM":
                current["trim"] = val.lower() in ("true", "1")
        if current and "column" in current:
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
            "pattern": self._get_str(node, "PATTERN"),
            "pattern_units": self._get_str(node, "PATTERN_UNITS", "SYMBOLS"),
            "advanced_option": self._get_bool(node, "ADVANCED_OPTION", False),
            "remove_empty_row": self._get_bool(node, "REMOVE_EMPTY_ROW", True),
            "trim_all": self._get_bool(node, "TRIMALL", True),
            "encoding": self._get_str(node, "ENCODING", "ISO-8859-15"),
            "header_rows": self._get_int(node, "HEADER", 0),
            "footer_rows": self._get_int(node, "FOOTER", 0),
            "limit": self._get_int(node, "LIMIT", 0),
            "die_on_error": self._get_bool(node, "DIE_ON_ERROR", False),
            # Advanced params
            "process_long_row": self._get_bool(node, "PROCESS_LONG_ROW", False),
            "advanced_separator": self._get_bool(node, "ADVANCED_SEPARATOR", False),
            "thousands_separator": self._get_str(node, "THOUSANDS_SEPARATOR", ","),
            "decimal_separator": self._get_str(node, "DECIMAL_SEPARATOR", "."),
            "check_date": self._get_bool(node, "CHECK_DATE", False),
            "uncompress": self._get_bool(node, "UNCOMPRESS", False),
            "use_byte": self._get_bool(node, "USE_BYTE", False),
            # Metadata
            "tstatcatcher_stats": self._get_bool(node, "TSTATCATCHER_STATS", False),
            "label": self._get_str(node, "LABEL"),
            # Table parameters
            "formats": self._parse_formats_table(
                node.params.get("FORMATS", [])),
            "trim_select": self._parse_trim_select(
                node.params.get("TRIMSELECT", [])),
        }

        # Warn when filepath is empty — it is mandatory in Talend
        if not config["filepath"]:
            warnings.append("FILENAME is empty — this is a required parameter")

        # Warn when positional parsing config is incomplete:
        # ADVANCED_OPTION=true means FORMATS table is used instead of PATTERN
        if config["advanced_option"]:
            if not config["formats"]:
                warnings.append("FORMATS table is empty — 'Customize' positional parsing requires formats")
        elif not config["pattern"]:
            warnings.append("PATTERN is empty — positional file parsing requires a pattern")

        # Engine-gap warnings
        if config["uncompress"]:
            warnings.append("UNCOMPRESS=true: engine does not support reading from ZIP archives")
        if config["process_long_row"]:
            warnings.append("PROCESS_LONG_ROW=true: engine does not implement long-row buffering")
        if config["advanced_separator"]:
            warnings.append("ADVANCED_SEPARATOR=true: engine does not support locale-aware number formatting")
        if config["check_date"]:
            warnings.append("CHECK_DATE=true: engine does not validate date fields against schema patterns")
        if any(entry.get("trim", False) for entry in config["trim_select"]):
            warnings.append("TRIMSELECT has per-column trims: engine only supports all-or-nothing via TRIMALL")

        component = self._build_component_dict(
            node=node,
            type_name="FileInputPositional",
            config=config,
            schema={"input": [], "output": self._parse_schema(node)},
        )

        return ComponentResult(component=component, warnings=warnings)
