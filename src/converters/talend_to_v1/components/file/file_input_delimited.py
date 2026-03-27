"""Converter for tFileInputDelimited -> FileInputDelimited."""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("tFileInputDelimited")
class FileInputDelimitedConverter(ComponentConverter):
    """Convert a Talend tFileInputDelimited node to v1 FileInputDelimited."""

    @staticmethod
    def _parse_table_pairs(
        raw: list,
        key_ref: str,
        value_ref: str,
        value_as_bool: bool = False,
    ) -> list:
        """Parse alternating elementRef/value pairs from a TABLE parameter.

        Input:  [{"elementRef": "SCHEMA_COLUMN", "value": "name"},
                 {"elementRef": "TRIM", "value": "true"}, ...]
        Output: [{"column": "name", "trim": True}, ...]
        """
        result = []
        current: dict = {}
        for entry in raw:
            ref = entry.get("elementRef", "")
            val = entry.get("value", "")
            if ref == key_ref:
                if current:
                    result.append(current)
                current = {"column": val}
            elif ref == value_ref:
                parsed = val.lower() in ("true", "1") if value_as_bool else val
                current[value_ref.lower()] = parsed
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
            "filepath": self._get_str(node, "FILENAME"),
            "delimiter": self._get_str(node, "FIELDSEPARATOR", ";"),
            "row_separator": self._get_str(node, "ROWSEPARATOR", "\\n"),
            "header_rows": self._get_int(node, "HEADER", 0),
            "footer_rows": self._get_int(node, "FOOTER", 0),
            "limit": self._get_int(node, "LIMIT", 0),
            "encoding": self._get_str(node, "ENCODING", "ISO-8859-15"),
            "text_enclosure": self._get_str(node, "TEXT_ENCLOSURE"),
            "escape_char": self._get_str(node, "ESCAPE_CHAR"),
            "remove_empty_rows": self._get_bool(node, "REMOVE_EMPTY_ROW", False),
            "trim_all": self._get_bool(node, "TRIMALL", False),
            "die_on_error": self._get_bool(node, "DIE_ON_ERROR", False),
            # CSV options
            "csv_option": self._get_bool(node, "CSV_OPTION", False),
            "split_record": self._get_bool(node, "SPLITRECORD", False),
            "csv_row_separator": self._get_str(node, "CSVROWSEPARATOR", "\\n"),
            # Compression
            "uncompress": self._get_bool(node, "UNCOMPRESS", False),
            # Validation
            "check_fields_num": self._get_bool(node, "CHECK_FIELDS_NUM", False),
            "check_date": self._get_bool(node, "CHECK_DATE", False),
            # Advanced separators
            "advanced_separator": self._get_bool(node, "ADVANCED_SEPARATOR", False),
            "thousands_separator": self._get_str(node, "THOUSANDS_SEPARATOR", ","),
            "decimal_separator": self._get_str(node, "DECIMAL_SEPARATOR", "."),
            # Random sampling
            "random": self._get_bool(node, "RANDOM", False),
            "nb_random": self._get_int(node, "NB_RANDOM", 10),
            # Hex/octal decode
            "enable_decode": self._get_bool(node, "ENABLE_DECODE", False),
            # Metadata
            "tstatcatcher_stats": self._get_bool(node, "TSTATCATCHER_STATS", False),
            "label": self._get_str(node, "LABEL"),
            # Table parameters
            "trim_select": self._parse_table_pairs(
                self._get_param(node, "TRIMSELECT") or [], "SCHEMA_COLUMN", "TRIM", value_as_bool=True),
            "decode_cols": self._parse_table_pairs(
                self._get_param(node, "DECODE_COLS") or [], "SCHEMA_COLUMN", "DECODE", value_as_bool=True),
        }

        # Warn when filepath is empty — it is mandatory in Talend
        if not config["filepath"]:
            warnings.append("FILENAME is empty — this is a required parameter")

        # Engine-gap warnings (parameter captured but engine doesn't support it yet)
        if config["uncompress"]:
            warnings.append("UNCOMPRESS=true: engine does not yet support compressed file reading")
        if config["csv_option"]:
            warnings.append("CSV_OPTION=true: engine does not have explicit RFC4180 toggle")
        if config["random"]:
            warnings.append("RANDOM=true: engine does not support random line extraction")
        if config["check_fields_num"]:
            warnings.append("CHECK_FIELDS_NUM=true: engine does not validate row field count")
        if config["check_date"]:
            warnings.append("CHECK_DATE=true: engine does not strictly validate dates against schema patterns")
        if config["enable_decode"]:
            warnings.append("ENABLE_DECODE=true: engine does not support hex/octal number parsing")
        if config["split_record"]:
            warnings.append("SPLITRECORD=true: engine does not have explicit multi-line field toggle")
        if config["advanced_separator"]:
            warnings.append("ADVANCED_SEPARATOR=true: engine has partial support — applies to all string columns, not just numeric")
        if any(entry.get("trim", False) for entry in config["trim_select"]):
            warnings.append("TRIMSELECT has per-column trims: engine only supports trim_all (all-or-nothing)")
        if config["csv_row_separator"] and config["csv_row_separator"] != config["row_separator"]:
            warnings.append("CSVROWSEPARATOR differs from ROWSEPARATOR: engine uses only row_separator, ignores csv_row_separator")

        component = self._build_component_dict(
            node=node,
            type_name="FileInputDelimited",
            config=config,
            schema={"input": [], "output": self._parse_schema(node)},
        )

        return ComponentResult(component=component, warnings=warnings)
