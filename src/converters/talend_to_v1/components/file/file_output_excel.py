"""Converter for tFileOutputExcel -> FileOutputExcel."""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("tFileOutputExcel")
class FileOutputExcelConverter(ComponentConverter):
    """Convert a Talend tFileOutputExcel node to v1 FileOutputExcel."""

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []

        filename = self._get_str(node, "FILENAME")
        if not filename:
            warnings.append("FILENAME is empty — this is a required parameter")

        config: Dict[str, Any] = {
            # Core
            "filename": filename,
            "sheetname": self._get_str(node, "SHEETNAME", "Sheet1"),
            "version_2007": self._get_bool(node, "VERSION_2007", False),
            "includeheader": self._get_bool(node, "INCLUDEHEADER", False),
            "append_file": self._get_bool(node, "APPEND_FILE", False),
            "append_sheet": self._get_bool(node, "APPEND_SHEET", False),
            "create_directory": self._get_bool(node, "CREATE", True),
            "die_on_error": self._get_bool(node, "DIE_ON_ERROR", False),
            "encoding": self._get_str(node, "ENCODING", "UTF-8"),
            "font": self._get_str(node, "FONT", "Arial"),
            "auto_size_all": self._get_bool(node, "AUTO_SIZE_SETTING", False),
            # Positioning
            "first_cell_y_absolute": self._get_bool(node, "FIRST_CELL_Y_ABSOLUTE", False),
            "first_cell_x": self._get_int(node, "FIRST_CELL_X", 0),
            "first_cell_y": self._get_int(node, "FIRST_CELL_Y", 0),
            "keep_cell_formatting": self._get_bool(node, "KEEP_CELL_FORMATING", False),
            # Advanced
            "advanced_separator": self._get_bool(node, "ADVANCED_SEPARATOR", False),
            "thousands_separator": self._get_str(node, "THOUSANDS_SEPARATOR", ","),
            "decimal_separator": self._get_str(node, "DECIMAL_SEPARATOR", "."),
            "truncate_exceeding_characters": self._get_bool(
                node, "TRUNCATE_EXCEEDING_CHARACTERS", False
            ),
            "delete_empty_file": self._get_bool(node, "DELETE_EMPTYFILE", False),
            "recalculate_formula": self._get_bool(node, "RECALCULATE_FORMULA", False),
            # Version-gated (xlsx only)
            "protect_file": self._get_bool(node, "PROTECT_FILE", False),
            "password": self._get_str(node, "PASSWORD"),
            "custom_flush_buffer": self._get_bool(node, "CUSTOM_FLUSH_BUFFER", False),
            "flush_on_row": self._get_int(node, "FLUSH_ON_ROW", 1000),
            "streaming_append": self._get_bool(node, "STREAMING_APPEND", False),
            "use_shared_strings_table": self._get_bool(
                node, "USE_SHARED_STRINGS_TABLE", False
            ),
            # Metadata
            "tstatcatcher_stats": self._get_bool(node, "TSTATCATCHER_STATS", False),
            "label": self._get_str(node, "LABEL"),
        }

        # --- Engine-gap warnings ---
        if not config["version_2007"]:
            warnings.append(
                "VERSION_2007=false: engine only writes .xlsx format (openpyxl); "
                ".xls output not supported"
            )
        if config["protect_file"]:
            warnings.append(
                "PROTECT_FILE=true: engine does not support workbook password protection"
            )
        if config["first_cell_y_absolute"]:
            warnings.append(
                "FIRST_CELL_Y_ABSOLUTE=true: engine does not support cell offset positioning"
            )
        if config["font"] and config["font"] != "Arial":
            warnings.append(
                f"FONT={config['font']}: engine does not support font selection"
            )
        if config["auto_size_all"]:
            warnings.append(
                "AUTO_SIZE_SETTING=true: engine does not support column auto-sizing"
            )
        if config["keep_cell_formatting"]:
            warnings.append(
                "KEEP_CELL_FORMATING=true: engine does not preserve existing cell formatting"
            )
        if config["advanced_separator"]:
            warnings.append(
                "ADVANCED_SEPARATOR=true: engine does not support locale-aware "
                "number formatting on output"
            )
        if config["truncate_exceeding_characters"]:
            warnings.append(
                "TRUNCATE_EXCEEDING_CHARACTERS=true: engine does not truncate "
                "cell content at 32,767 chars"
            )
        if config["delete_empty_file"]:
            warnings.append(
                "DELETE_EMPTYFILE=true: engine always creates output file even "
                "when no data rows written"
            )
        if config["recalculate_formula"]:
            warnings.append(
                "RECALCULATE_FORMULA=true: engine does not force formula recalculation"
            )
        if config["streaming_append"]:
            warnings.append(
                "STREAMING_APPEND=true: engine does not support SXSSF streaming write mode"
            )
        if config["use_shared_strings_table"]:
            warnings.append(
                "USE_SHARED_STRINGS_TABLE=true: engine does not support "
                "shared strings table optimization"
            )
        if config["custom_flush_buffer"]:
            warnings.append(
                "CUSTOM_FLUSH_BUFFER=true: engine does not support flush buffer control"
            )
        # Check for USE_OUTPUT_STREAM (not extracted but warn if present)
        if self._get_bool(node, "USE_OUTPUT_STREAM", False):
            warnings.append(
                "USE_OUTPUT_STREAM detected: engine does not support OutputStream mode"
            )

        component = self._build_component_dict(
            node=node,
            type_name="FileOutputExcel",
            config=config,
            schema={"input": self._parse_schema(node), "output": []},
        )

        return ComponentResult(component=component, warnings=warnings)
