"""Converter for Talend tLogRow component.

Logs row data to console/log output in various formats.

Config mapping (13 unique params + framework):
  BASIC_MODE       -> basic_mode       (bool, RADIO GROUP=MODE, default True)
  TABLE_PRINT      -> table_print      (bool, RADIO GROUP=MODE, default False)
  VERTICAL         -> vertical         (bool, RADIO GROUP=MODE, default False)
  PRINT_UNIQUE     -> print_unique     (bool, RADIO GROUP=TITLE_PRINT, default True)
  PRINT_LABEL      -> print_label      (bool, RADIO GROUP=TITLE_PRINT, default False)
  PRINT_UNIQUE_LABEL -> print_unique_label (bool, RADIO GROUP=TITLE_PRINT, default False)
  FIELDSEPARATOR   -> fieldseparator   (str, default "|")
  PRINT_HEADER     -> print_header     (bool, default False)
  PRINT_UNIQUE_NAME -> print_unique_name (bool, default False)
  PRINT_COLNAMES   -> print_colnames   (bool, default False)
  USE_FIXED_LENGTH -> use_fixed_length (bool, default False)
  LENGTHS          -> lengths          (list, TABLE stride-1, default [])
  PRINT_CONTENT_WITH_LOG4J -> print_content_with_log4j (bool, default True)
  SCHEMA_OPT_NUM   -> max_rows         (str, hidden, default "100")
  --- framework ---
  TSTATCATCHER_STATS -> tstatcatcher_stats (bool, default False)
  LABEL              -> label              (str, default "")

Engine reads: basic_mode, table_print (default True), print_header (default True),
field_separator/FIELDSEPARATOR, max_rows/SCHEMA_OPT_NUM.
Engine does NOT read: vertical, print_colnames, use_fixed_length, lengths,
print_content_with_log4j, print_unique, print_label, print_unique_label, print_unique_name.
"""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# TABLE constants (LENGTHS TABLE -- stride-1, BASED_ON_SCHEMA=true)
# ------------------------------------------------------------------
_LENGTHS_FIELDS = ("LENGTH",)
_LENGTHS_GROUP_SIZE = len(_LENGTHS_FIELDS)


# ------------------------------------------------------------------
# TABLE parser functions
# ------------------------------------------------------------------
def _parse_lengths(raw: Any) -> List[int]:
    """Parse LENGTHS TABLE into list of column widths (stride-1, BASED_ON_SCHEMA=true)."""
    if not raw or not isinstance(raw, list):
        return []
    lengths: List[int] = []
    for i in range(0, len(raw), _LENGTHS_GROUP_SIZE):
        group = raw[i : i + _LENGTHS_GROUP_SIZE]
        if len(group) < _LENGTHS_GROUP_SIZE:
            break
        entry = group[0]
        if isinstance(entry, dict):
            val = entry.get("value", "10")
            try:
                lengths.append(int(str(val).strip('"')))
            except (ValueError, TypeError):
                lengths.append(10)
    return lengths


@REGISTRY.register("tLogRow")
class LogRowConverter(ComponentConverter):
    """Convert Talend tLogRow to v1 engine config."""

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []
        needs_review: List[Dict[str, Any]] = []

        config: Dict[str, Any] = {}

        # ---- 1. RADIO GROUP=MODE parameters ----
        config["basic_mode"] = self._get_bool(node, "BASIC_MODE", True)
        config["table_print"] = self._get_bool(node, "TABLE_PRINT", False)
        config["vertical"] = self._get_bool(node, "VERTICAL", False)

        # ---- 2. RADIO GROUP=TITLE_PRINT parameters ----
        config["print_unique"] = self._get_bool(node, "PRINT_UNIQUE", True)
        config["print_label"] = self._get_bool(node, "PRINT_LABEL", False)
        config["print_unique_label"] = self._get_bool(node, "PRINT_UNIQUE_LABEL", False)

        # ---- 3. CHECK parameters ----
        config["print_header"] = self._get_bool(node, "PRINT_HEADER", False)
        config["print_unique_name"] = self._get_bool(node, "PRINT_UNIQUE_NAME", False)
        config["print_colnames"] = self._get_bool(node, "PRINT_COLNAMES", False)
        config["use_fixed_length"] = self._get_bool(node, "USE_FIXED_LENGTH", False)
        config["print_content_with_log4j"] = self._get_bool(node, "PRINT_CONTENT_WITH_LOG4J", True)

        # ---- 4. TEXT parameters ----
        config["fieldseparator"] = self._get_str(node, "FIELDSEPARATOR", "|")
        config["max_rows"] = self._get_str(node, "SCHEMA_OPT_NUM", "100")

        # ---- 5. TABLE parameter ----
        config["lengths"] = _parse_lengths(node.params.get("LENGTHS", []))

        # ---- 6. Framework parameters (ALWAYS LAST) ----
        config["tstatcatcher_stats"] = self._get_bool(node, "TSTATCATCHER_STATS", False)
        config["label"] = self._get_str(node, "LABEL", "")

        # ---- 7. Schema: passthrough -- input == output ----
        schema_cols = self._parse_schema(node)
        schema = {"input": schema_cols, "output": schema_cols}

        # ---- 8. Engine gap needs_review entries ----
        # Engine does NOT read these params
        _engine_unread = [
            ("vertical", "engine only checks basic_mode and table_print for display mode"),
            ("print_unique", "engine does not implement vertical title group selection"),
            ("print_label", "engine does not implement vertical title group selection"),
            ("print_unique_label", "engine does not implement vertical title group selection"),
            ("print_unique_name", "engine does not read unique name printing option"),
            ("print_colnames", "engine does not read column name printing option"),
            ("use_fixed_length", "engine does not implement fixed-width formatting"),
            ("lengths", "engine does not implement fixed-width column lengths"),
            ("print_content_with_log4j", "engine does not implement Log4J output routing"),
        ]
        for key, detail in _engine_unread:
            needs_review.append({
                "issue": f"Engine does not read '{key}' config key -- {detail}",
                "component": node.component_id,
                "severity": "engine_gap",
            })

        # Engine default mismatches
        _default_mismatches = [
            ("basic_mode", True, False),
            ("table_print", False, True),
            ("print_header", False, True),
        ]
        for param, talend_default, engine_default in _default_mismatches:
            needs_review.append({
                "issue": (
                    f"Engine default for '{param}' is {engine_default} but "
                    f"Talend default is {talend_default} -- when converter "
                    f"emits the Talend default, engine behavior matches; but "
                    f"if the config key is stripped, engine falls back to "
                    f"wrong default"
                ),
                "component": node.component_id,
                "severity": "engine_gap",
            })

        # ---- 9. Build component wrapper ----
        component = self._build_component_dict(
            node=node,
            type_name="LogRow",
            config=config,
            schema=schema,
        )

        # ---- 10. Return ----
        return ComponentResult(
            component=component,
            warnings=warnings,
            needs_review=needs_review,
        )
