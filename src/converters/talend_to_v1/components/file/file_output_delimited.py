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

        csv_option_enabled = self._get_bool(node, "CSV_OPTION", False)
        advanced_separator_enabled = self._get_bool(node, "ADVANCED_SEPARATOR", False)
        split_enabled = self._get_bool(node, "SPLIT", False)
        file_exist_exception = self._get_bool(node, "FILE_EXIST_EXCEPTION", False)

        config: Dict[str, Any] = {
            "filepath": self._get_str(node, "FILENAME"),
            "delimiter": self._get_str(node, "FIELDSEPARATOR", ","),
            "row_separator": self._get_str(node, "ROWSEPARATOR", "\\n"),
            "encoding": self._get_str(node, "ENCODING", "UTF-8"),
            "include_header": self._get_bool(node, "INCLUDEHEADER", True),
            "append": self._get_bool(node, "APPEND", False),
            "create_directory": self._get_bool(node, "CREATE", True),
            "delete_empty_file": self._get_bool(node, "DELETE_EMPTYFILE", True),
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

        # split_every is only used when SPLIT is enabled
        if split_enabled:
            split_every = self._get_int(node, "SPLIT_EVERY", 1000)
            config["split_every"] = split_every
        else:
            # Check if SPLIT_EVERY is set but SPLIT is disabled
            split_every = node.params.get("SPLIT_EVERY")
            if split_every and str(split_every).strip('"'):
                warnings.append(
                    "SPLIT_EVERY is set but SPLIT is disabled — this parameter will be ignored"
                )

        # FILE_EXIST_EXCEPTION is a conditional parameter that controls error behavior
        if file_exist_exception:
            config["file_exist_exception"] = True
        else:
            config["file_exist_exception"] = False

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
