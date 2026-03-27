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
            "delimiter": self._get_str(node, "FIELDSEPARATOR", ";"),
            "row_separator": self._get_str(node, "ROWSEPARATOR", "\\n"),
            "encoding": self._get_str(node, "ENCODING", "ISO-8859-15"),
            "text_enclosure": text_enclosure,
            "include_header": self._get_bool(node, "INCLUDEHEADER", False),
            "append": self._get_bool(node, "APPEND", False),
            "create_directory": self._get_bool(node, "CREATE", True),
            "delete_empty_file": self._get_bool(node, "DELETE_EMPTYFILE", False),
            "csv_option": csv_option,
            # Escape character (only meaningful with csv_option)
            "escape_char": self._get_str(node, "ESCAPE_CHAR"),
            # Compression
            "compress": self._get_bool(node, "COMPRESS", False),
            # Advanced separators
            "advanced_separator": self._get_bool(node, "ADVANCED_SEPARATOR", False),
            "thousands_separator": self._get_str(node, "THOUSANDS_SEPARATOR", ","),
            "decimal_separator": self._get_str(node, "DECIMAL_SEPARATOR", "."),
            "csv_row_separator": self._get_str(node, "CSVROWSEPARATOR", "\\n"),
            # File splitting
            "split": self._get_bool(node, "SPLIT", False),
            "split_every": self._get_int(node, "SPLIT_EVERY", 1000),
            # Buffer flushing
            "flush_on_row": self._get_bool(node, "FLUSHONROW", False),
            "flush_row_count": self._get_int(node, "FLUSHONROW_NUM", 1),
            "row_mode": self._get_bool(node, "ROW_MODE", False),
            # Error handling
            "file_exist_exception": self._get_bool(node, "FILE_EXIST_EXCEPTION", False),
            # OS line separator
            "os_line_separator": self._get_bool(node, "OS_LINE_SEPARATOR_AS_ROW_SEPARATOR", True),
            # Stream mode
            "use_stream": self._get_bool(node, "USESTREAM", False),
            "stream_name": self._get_str(node, "STREAMNAME"),
            # Metadata
            "tstatcatcher_stats": self._get_bool(node, "TSTATCATCHER_STATS", False),
            "label": self._get_str(node, "LABEL"),
        }

        # Warn when filepath is empty -- it is mandatory in Talend
        if not config["filepath"]:
            warnings.append("FILENAME is empty — this is a required parameter")

        # Engine-gap warnings
        if config["compress"]:
            warnings.append("COMPRESS=true: engine does not support ZIP-compressed output")
        if config["split"]:
            warnings.append("SPLIT=true: engine does not support splitting output into multiple files")
        if config["use_stream"]:
            warnings.append("USESTREAM=true: engine does not support OutputStream writing")
        if config["row_mode"]:
            warnings.append("ROW_MODE=true: engine does not support atomic per-row flush")
        if config["file_exist_exception"]:
            warnings.append("FILE_EXIST_EXCEPTION=true: engine does not check for file existence before writing")
        if config["flush_on_row"]:
            warnings.append("FLUSHONROW=true: engine does not support custom buffer flushing interval")
        if config["advanced_separator"]:
            warnings.append("ADVANCED_SEPARATOR=true: engine has partial support — applies to all columns, not just numeric")
        if not config["os_line_separator"]:
            warnings.append("OS_LINE_SEPARATOR=false: engine always uses the configured row_separator, ignoring OS line separator")
        if config["csv_row_separator"] and config["csv_row_separator"] != config["row_separator"]:
            warnings.append("CSVROWSEPARATOR differs from ROWSEPARATOR: engine uses only row_separator")
        if config["csv_option"] and config["escape_char"] and config["escape_char"] not in ('"\\\\"', '\\\\'):
            warnings.append(f"ESCAPE_CHAR={config['escape_char']} with CSV_OPTION: engine hardcodes escape character to \\\\")

        component = self._build_component_dict(
            node=node,
            type_name="FileOutputDelimited",
            config=config,
            schema={"input": self._parse_schema(node), "output": []},
        )

        return ComponentResult(component=component, warnings=warnings)
