"""Converter for Talend tFileOutputDelimited component.

Writes data to delimited text files (CSV, TSV, etc.) with configurable
formatting, encoding, and output options.

Config mapping (25 unique params + 2 framework):
  USESTREAM                        -> usestream                (bool, default False)
  STREAMNAME                       -> streamname               (str, default "outputStream")
  FILENAME                         -> filepath                 (str, default "")
  ROWSEPARATOR                     -> row_separator            (str, default "\\n")
  FIELDSEPARATOR                   -> fieldseparator           (str, default ";")
  APPEND                           -> append                   (bool, default False)
  INCLUDEHEADER                    -> include_header           (bool, default False)
  COMPRESS                         -> compress                 (bool, default False)
  ADVANCED_SEPARATOR               -> advanced_separator       (bool, default False)
  THOUSANDS_SEPARATOR              -> thousands_separator      (str, default ",")
  DECIMAL_SEPARATOR                -> decimal_separator        (str, default ".")
  CSV_OPTION                       -> csv_option               (bool, default False)
  ESCAPE_CHAR                      -> escape_char              (str, default '"')
  TEXT_ENCLOSURE                   -> text_enclosure           (str, default '"')
  OS_LINE_SEPARATOR_AS_ROW_SEPARATOR -> os_line_separator      (bool, default True)
  CSVROWSEPARATOR                  -> csvrowseparator          (str, default "LF")
  CREATE                           -> create_directory         (bool, default True)
  SPLIT                            -> split                    (bool, default False)
  SPLIT_EVERY                      -> split_every              (str, default "1000")
  FLUSHONROW                       -> flushonrow               (bool, default False)
  FLUSHONROW_NUM                   -> flush_row_count          (str, default "1")
  ROW_MODE                         -> row_mode                 (bool, default False)
  ENCODING                         -> encoding                 (str, default "ISO-8859-15")
  DELETE_EMPTYFILE                 -> delete_empty_file        (bool, default False)
  FILE_EXIST_EXCEPTION             -> file_exist_exception     (bool, default True)
  --- framework ---
  TSTATCATCHER_STATS               -> tstatcatcher_stats       (bool, default False)
  LABEL                            -> label                    (str, default "")
"""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("tFileOutputDelimited")
class FileOutputDelimitedConverter(ComponentConverter):
    """Convert Talend tFileOutputDelimited to v1 engine config."""

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []
        needs_review: List[Dict[str, Any]] = []

        # ---- 1. Core parameters ----
        config: Dict[str, Any] = {}
        config["usestream"] = self._get_bool(node, "USESTREAM", False)
        config["streamname"] = self._get_str(node, "STREAMNAME", "outputStream")
        config["filepath"] = self._get_str(node, "FILENAME", "")
        config["row_separator"] = self._get_str(node, "ROWSEPARATOR", "\\n")
        config["fieldseparator"] = self._get_str(node, "FIELDSEPARATOR", ";")
        config["append"] = self._get_bool(node, "APPEND", False)
        config["include_header"] = self._get_bool(node, "INCLUDEHEADER", False)
        config["compress"] = self._get_bool(node, "COMPRESS", False)
        config["advanced_separator"] = self._get_bool(node, "ADVANCED_SEPARATOR", False)
        config["thousands_separator"] = self._get_str(node, "THOUSANDS_SEPARATOR", ",")
        config["decimal_separator"] = self._get_str(node, "DECIMAL_SEPARATOR", ".")
        config["csv_option"] = self._get_bool(node, "CSV_OPTION", False)
        config["escape_char"] = self._get_str(node, "ESCAPE_CHAR", '"')
        config["text_enclosure"] = self._get_str(node, "TEXT_ENCLOSURE", '"')
        config["os_line_separator"] = self._get_bool(node, "OS_LINE_SEPARATOR_AS_ROW_SEPARATOR", True)
        config["csvrowseparator"] = self._get_str(node, "CSVROWSEPARATOR", "LF")
        config["create_directory"] = self._get_bool(node, "CREATE", True)
        config["split"] = self._get_bool(node, "SPLIT", False)
        config["split_every"] = self._get_str(node, "SPLIT_EVERY", "1000")
        config["flushonrow"] = self._get_bool(node, "FLUSHONROW", False)
        config["flush_row_count"] = self._get_str(node, "FLUSHONROW_NUM", "1")
        config["row_mode"] = self._get_bool(node, "ROW_MODE", False)
        config["encoding"] = self._get_str(node, "ENCODING", "ISO-8859-15")
        config["delete_empty_file"] = self._get_bool(node, "DELETE_EMPTYFILE", False)
        config["file_exist_exception"] = self._get_bool(node, "FILE_EXIST_EXCEPTION", True)

        # ---- 5. Framework parameters (ALWAYS LAST) ----
        config["tstatcatcher_stats"] = self._get_bool(node, "TSTATCATCHER_STATS", False)
        config["label"] = self._get_str(node, "LABEL", "")

        # ---- 6. Schema ----
        # Sink component: input populated, output empty
        schema = {"input": self._parse_schema(node), "output": []}

        # ---- 7. Engine gap needs_review entries ----
        # Engine uses delimiter default ',' but _java.xml FIELDSEPARATOR default is ';'
        needs_review.append({
            "issue": "Engine default delimiter=',' but _java.xml FIELDSEPARATOR default is ';' -- converter outputs 'fieldseparator'",
            "component": node.component_id,
            "severity": "engine_gap",
        })
        # Engine uses encoding default 'UTF-8' but _java.xml ENCODING default is 'ISO-8859-15'
        needs_review.append({
            "issue": "Engine default encoding='UTF-8' but _java.xml ENCODING default is 'ISO-8859-15'",
            "component": node.component_id,
            "severity": "engine_gap",
        })
        # Engine uses include_header default True but _java.xml INCLUDEHEADER default is False
        needs_review.append({
            "issue": "Engine default include_header=True but _java.xml INCLUDEHEADER default is False",
            "component": node.component_id,
            "severity": "engine_gap",
        })

        # ---- 8. Build component wrapper ----
        component = self._build_component_dict(
            node=node,
            type_name="FileOutputDelimited",
            config=config,
            schema=schema,
        )

        # ---- 9. Return ----
        return ComponentResult(
            component=component,
            warnings=warnings,
            needs_review=needs_review,
        )
