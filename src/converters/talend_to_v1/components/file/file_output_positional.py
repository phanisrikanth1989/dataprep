"""Converter for Talend tFileOutputPositional component.

Writes fixed-width (positional) files with configurable column formatting.

Config mapping (20 unique params + 2 framework):
  USE_EXISTING_DYNAMIC -> use_existing_dynamic (bool, default False)
  DYNAMIC              -> dynamic              (str, default "")
  USESTREAM            -> usestream            (bool, default False)
  STREAMNAME           -> streamname           (str, default "outputStream")
  FILENAME             -> filepath             (str, default "")
  ROWSEPARATOR         -> row_separator        (str, default "\\n")
  APPEND               -> append               (bool, default False)
  INCLUDEHEADER        -> include_header       (bool, default False)
  COMPRESS             -> compress             (bool, default False)
  FORMATS              -> formats              (list, TABLE -- 5 fields: SCHEMA_COLUMN, SIZE, PADDING_CHAR, ALIGN, KEEP)
  ADVANCED_SEPARATOR   -> advanced_separator   (bool, default False)
  THOUSANDS_SEPARATOR  -> thousands_separator  (str, default ",")
  DECIMAL_SEPARATOR    -> decimal_separator    (str, default ".")
  USE_BYTE             -> use_byte             (bool, default False)
  CREATE               -> create               (bool, default True)
  FLUSHONROW           -> flushonrow           (bool, default False)
  FLUSHONROW_NUM       -> flushonrow_num       (str, default "1")
  ROW_MODE             -> row_mode             (bool, default False)
  ENCODING             -> encoding             (str, default "ISO-8859-15")
  DELETE_EMPTYFILE     -> delete_empty_file    (bool, default False)
  --- framework ---
  TSTATCATCHER_STATS -> tstatcatcher_stats (bool, default False)
  LABEL              -> label              (str, default "")
"""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# TABLE constants
# ------------------------------------------------------------------
_FORMATS_FIELDS = ("SCHEMA_COLUMN", "SIZE", "PADDING_CHAR", "ALIGN", "KEEP")
_FORMATS_GROUP_SIZE = len(_FORMATS_FIELDS)


# ------------------------------------------------------------------
# TABLE parser functions
# ------------------------------------------------------------------
def _parse_formats(raw: Any) -> List[Dict[str, Any]]:
    """Parse FORMATS TABLE into list of dicts.

    Each group of 5 consecutive elementRef entries maps to one row:
      SCHEMA_COLUMN -> schema_column (str)
      SIZE          -> size          (str)
      PADDING_CHAR  -> padding_char  (str, quotes stripped)
      ALIGN         -> align         (str, quotes stripped -- LEFT/CENTER/RIGHT)
      KEEP          -> keep          (str, quotes stripped -- ALL/LEFT/MIDDLE/RIGHT)

    Incomplete trailing groups (< 5 entries) are skipped.
    """
    if not raw or not isinstance(raw, list):
        return []
    result: List[Dict[str, Any]] = []
    for i in range(0, len(raw), _FORMATS_GROUP_SIZE):
        group = raw[i: i + _FORMATS_GROUP_SIZE]
        if len(group) < _FORMATS_GROUP_SIZE:
            break
        row: Dict[str, Any] = {}
        for entry in group:
            if not isinstance(entry, dict):
                continue
            ref = entry.get("elementRef", "")
            val = entry.get("value", "")
            if ref == "SCHEMA_COLUMN":
                row["schema_column"] = val.strip('"')
            elif ref == "SIZE":
                row["size"] = val.strip('"')
            elif ref == "PADDING_CHAR":
                row["padding_char"] = val.strip("'").strip('"')
            elif ref == "ALIGN":
                row["align"] = val.strip("'").strip('"')
            elif ref == "KEEP":
                row["keep"] = val.strip("'").strip('"')
        if row:
            result.append(row)
    return result


@REGISTRY.register("tFileOutputPositional")
class FileOutputPositionalConverter(ComponentConverter):
    """Convert Talend tFileOutputPositional to v1 engine config."""

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
        config["use_existing_dynamic"] = self._get_bool(node, "USE_EXISTING_DYNAMIC", False)
        config["dynamic"] = self._get_str(node, "DYNAMIC", "")
        config["usestream"] = self._get_bool(node, "USESTREAM", False)
        config["streamname"] = self._get_str(node, "STREAMNAME", "outputStream")
        config["filepath"] = self._get_str(node, "FILENAME", "")
        config["row_separator"] = self._get_str(node, "ROWSEPARATOR", "\\n")
        config["append"] = self._get_bool(node, "APPEND", False)
        config["include_header"] = self._get_bool(node, "INCLUDEHEADER", False)
        config["compress"] = self._get_bool(node, "COMPRESS", False)

        # ---- 2. TABLE parameters ----
        raw_formats = node.params.get("FORMATS", [])
        config["formats"] = _parse_formats(raw_formats)

        # ---- 3. Advanced parameters ----
        config["advanced_separator"] = self._get_bool(node, "ADVANCED_SEPARATOR", False)
        config["thousands_separator"] = self._get_str(node, "THOUSANDS_SEPARATOR", ",")
        config["decimal_separator"] = self._get_str(node, "DECIMAL_SEPARATOR", ".")
        config["use_byte"] = self._get_bool(node, "USE_BYTE", False)
        config["create"] = self._get_bool(node, "CREATE", True)
        config["flushonrow"] = self._get_bool(node, "FLUSHONROW", False)
        config["flushonrow_num"] = self._get_str(node, "FLUSHONROW_NUM", "1")
        config["row_mode"] = self._get_bool(node, "ROW_MODE", False)
        config["encoding"] = self._get_str(node, "ENCODING", "ISO-8859-15")
        config["delete_empty_file"] = self._get_bool(node, "DELETE_EMPTYFILE", False)

        # ---- 4. Framework parameters (ALWAYS LAST) ----
        config["tstatcatcher_stats"] = self._get_bool(node, "TSTATCATCHER_STATS", False)
        config["label"] = self._get_str(node, "LABEL", "")

        # ---- 5. Schema (SINK: input populated, output empty per D-55) ----
        schema = {"input": self._parse_schema(node), "output": []}

        # ---- 6. Engine gap needs_review entries ----
        # CRITICAL: FileOutputPositional is NOT registered in engine COMPONENT_REGISTRY
        needs_review.append({
            "issue": "FileOutputPositional engine file exists (468 lines) but is NOT registered in COMPONENT_REGISTRY -- component cannot be instantiated at runtime",
            "component": node.component_id,
            "severity": "engine_gap",
        })

        # Engine default mismatches
        _engine_gap_keys = [
            ("use_existing_dynamic", "engine does not read 'use_existing_dynamic' config key"),
            ("dynamic", "engine does not read 'dynamic' config key"),
            ("usestream", "engine does not read 'usestream' config key"),
            ("streamname", "engine does not read 'streamname' config key"),
            ("encoding", "engine defaults to 'utf-8', _java.xml defaults to 'ISO-8859-15'"),
            ("include_header", "engine defaults to True, _java.xml defaults to false"),
            ("advanced_separator", "engine does not read 'advanced_separator' config key"),
            ("thousands_separator", "engine does not read 'thousands_separator' config key"),
            ("decimal_separator", "engine does not read 'decimal_separator' config key"),
            ("use_byte", "engine does not read 'use_byte' config key"),
            ("row_mode", "engine does not read 'row_mode' config key"),
        ]
        for key, detail in _engine_gap_keys:
            needs_review.append({
                "issue": f"Engine gap for '{key}': {detail}",
                "component": node.component_id,
                "severity": "engine_gap",
            })

        # ---- 7. Build component wrapper ----
        component = self._build_component_dict(
            node=node,
            type_name="FileOutputPositional",
            config=config,
            schema=schema,
        )

        # ---- 8. Return ----
        return ComponentResult(
            component=component,
            warnings=warnings,
            needs_review=needs_review,
        )
