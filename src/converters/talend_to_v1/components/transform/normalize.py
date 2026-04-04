"""Converter for Talend tNormalize component.

Denormalizes a column by splitting its values into multiple rows.

Config mapping (9 unique params + framework):
  NORMALIZE_COLUMN         -> normalize_column         (str, PREV_COLUMN_LIST, default "")
  ITEMSEPARATOR            -> itemseparator            (str, TEXT, default ",")
  DEDUPLICATE              -> deduplicate              (bool, CHECK, default False)
  CSV_OPTION               -> csv_option               (bool, CHECK, default False)
  ESCAPE_CHAR              -> escape_char              (str, CLOSED_LIST, default "ESCAPE_MODE_DOUBLED")
                                                        values: ESCAPE_MODE_DOUBLED, ESCAPE_MODE_BACKSLASH
  TEXT_ENCLOSURE            -> text_enclosure           (str, TEXT, default '"')
  DISCARD_TRAILING_EMPTY_STR -> discard_trailing_empty_str (bool, CHECK, default False)
  TRIM                     -> trim                     (bool, CHECK, default False)
  --- framework ---
  TSTATCATCHER_STATS -> tstatcatcher_stats (bool, default False)
  LABEL              -> label              (str, default "")

Phantom params REMOVED: DIE_ON_ERROR (not in _java.xml)

Engine reads: normalize_column, item_separator, deduplicate, csv_option, trim.
Engine does NOT read: escape_char, text_enclosure, discard_trailing_empty_str.
"""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("tNormalize")
class NormalizeConverter(ComponentConverter):
    """Convert Talend tNormalize to v1 engine config."""

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []
        needs_review: List[Dict[str, Any]] = []

        # ---- 1. Core TEXT parameters ----
        config: Dict[str, Any] = {}
        config["normalize_column"] = self._get_str(node, "NORMALIZE_COLUMN", "")
        config["itemseparator"] = self._get_str(node, "ITEMSEPARATOR", ",")

        # ---- 2. CHECK parameters ----
        config["deduplicate"] = self._get_bool(node, "DEDUPLICATE", False)
        config["csv_option"] = self._get_bool(node, "CSV_OPTION", False)
        config["discard_trailing_empty_str"] = self._get_bool(node, "DISCARD_TRAILING_EMPTY_STR", False)
        config["trim"] = self._get_bool(node, "TRIM", False)

        # ---- 3. CLOSED_LIST / conditional parameters (CSV_OPTION-gated) ----
        config["escape_char"] = self._get_str(node, "ESCAPE_CHAR", "ESCAPE_MODE_DOUBLED")
        config["text_enclosure"] = self._get_str(node, "TEXT_ENCLOSURE", '"')

        # ---- 4. Framework parameters (ALWAYS LAST) ----
        config["tstatcatcher_stats"] = self._get_bool(node, "TSTATCATCHER_STATS", False)
        config["label"] = self._get_str(node, "LABEL", "")

        # ---- 5. Schema (passthrough: input == output) ----
        schema_cols = self._parse_schema(node)
        schema = {"input": schema_cols, "output": schema_cols}

        # ---- 6. Engine gap needs_review entries ----
        _engine_gap_keys = [
            ("escape_char", "engine does not read CSV escape mode"),
            ("text_enclosure", "engine does not read CSV text enclosure character"),
            ("discard_trailing_empty_str", "engine filters ALL empty strings, not just trailing"),
        ]
        for key, detail in _engine_gap_keys:
            needs_review.append({
                "issue": f"Engine does not read '{key}' config key -- {detail}",
                "component": node.component_id,
                "severity": "engine_gap",
            })

        # ---- 7. Build component wrapper ----
        component = self._build_component_dict(
            node=node,
            type_name="Normalize",
            config=config,
            schema=schema,
        )

        # ---- 8. Return ----
        return ComponentResult(
            component=component,
            warnings=warnings,
            needs_review=needs_review,
        )
