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

        # Check if CSV_OPTION is enabled
        csv_option_enabled = self._get_bool(node, "CSV_OPTION", False)
        # Check if ADVANCED_SEPARATOR is enabled
        advanced_separator_enabled = self._get_bool(node, "ADVANCED_SEPARATOR", False)

        config: Dict[str, Any] = {
            "filepath": self._get_str(node, "FILENAME"),
            "delimiter": self._get_str(node, "FIELDSEPARATOR", ","),
            "row_separator": self._get_str(node, "ROWSEPARATOR", "\\n"),
            "header_rows": self._get_int(node, "HEADER", 0),
            "footer_rows": self._get_int(node, "FOOTER", 0),
            "limit": self._get_int(node, "LIMIT", 0),
            "encoding": self._get_str(node, "ENCODING", "UTF-8"),
            "remove_empty_rows": self._get_bool(node, "REMOVE_EMPTY_ROW", False),
            "trim_all": self._get_bool(node, "TRIMALL", False),
            "die_on_error": self._get_bool(node, "DIE_ON_ERROR", False),
        }

        # text_enclosure and escape_char are only used when CSV_OPTION is enabled
        if csv_option_enabled:
            text_enclosure = self._get_str(node, "TEXT_ENCLOSURE")
            escape_char = self._get_str(node, "ESCAPE_CHAR")
            if text_enclosure:
                config["text_enclosure"] = text_enclosure
            if escape_char:
                config["escape_char"] = escape_char
        else:
            # Check if these parameters are set but CSV_OPTION is disabled
            text_enclosure = node.params.get("TEXT_ENCLOSURE")
            escape_char = node.params.get("ESCAPE_CHAR")
            if text_enclosure and str(text_enclosure).strip('"'):
                warnings.append(
                    "TEXT_ENCLOSURE is set but CSV_OPTION is disabled — this parameter will be ignored"
                )
            if escape_char and str(escape_char).strip('"'):
                warnings.append(
                    "ESCAPE_CHAR is set but CSV_OPTION is disabled — this parameter will be ignored"
                )

        # thousands_separator and decimal_separator are only used when ADVANCED_SEPARATOR is enabled
        if advanced_separator_enabled:
            thousands_separator = self._get_str(node, "THOUSANDS_SEPARATOR")
            decimal_separator = self._get_str(node, "DECIMAL_SEPARATOR")
            if thousands_separator:
                config["thousands_separator"] = thousands_separator
            if decimal_separator:
                config["decimal_separator"] = decimal_separator
        else:
            # Check if these parameters are set but ADVANCED_SEPARATOR is disabled
            thousands_separator = node.params.get("THOUSANDS_SEPARATOR")
            decimal_separator = node.params.get("DECIMAL_SEPARATOR")
            if thousands_separator and str(thousands_separator).strip('"'):
                warnings.append(
                    "THOUSANDS_SEPARATOR is set but ADVANCED_SEPARATOR is disabled — this parameter will be ignored"
                )
            if decimal_separator and str(decimal_separator).strip('"'):
                warnings.append(
                    "DECIMAL_SEPARATOR is set but ADVANCED_SEPARATOR is disabled — this parameter will be ignored"
                )

        # Parse TRIMSELECT table: per-column trim configuration
        trim_select = self._parse_trim_select(node)
        if trim_select:
            config["trim_columns"] = trim_select

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

    @staticmethod
    def _parse_trim_select(node: TalendNode) -> Dict[str, bool]:
        """Parse TRIMSELECT table to extract per-column trim configuration.
        
        Returns a dict mapping column names to trim boolean values.
        The TABLE structure alternates between SCHEMA_COLUMN and TRIM values.
        """
        trim_select_table = node.params.get("TRIMSELECT")
        if not trim_select_table:
            return {}
        
        # Convert list of {elementRef, value} dicts to column trim mapping
        trim_map: Dict[str, bool] = {}
        current_column = None
        
        for entry in trim_select_table:
            element_ref = entry.get("elementRef", "")
            value = entry.get("value", "")
            
            if element_ref == "SCHEMA_COLUMN":
                current_column = value
            elif element_ref == "TRIM" and current_column:
                trim_map[current_column] = value.lower() == "true"
        
        return trim_map
