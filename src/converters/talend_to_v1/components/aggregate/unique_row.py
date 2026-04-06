"""Converter for Talend tUniqueRow component.

Deduplicates input rows based on specified key columns, routing unique rows
to UNIQUE output and duplicates to DUPLICATE output.

Config mapping (9 params total):
  UNIQUE_KEY                              -> key_columns (list[dict], default [])
  (derived from UNIQUE_KEY)               -> case_sensitive (bool, default True)
  (derived from ONLY_ONCE_EACH_DUPLICATED_KEY) -> keep (str, default "first")
  ONLY_ONCE_EACH_DUPLICATED_KEY           -> only_once_each_duplicated_key (bool, default False)
  IS_VIRTUAL_COMPONENT                    -> is_virtual_component (bool, default False)
  BUFFER_SIZE                             -> buffer_size (str, default "M")
  CHANGE_HASH_AND_EQUALS_FOR_BIGDECIMAL   -> change_hash_and_equals_for_bigdecimal (bool, default False)
  TSTATCATCHER_STATS                      -> tstatcatcher_stats (bool, default False)
  LABEL                                   -> label (str, default ""
"""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# TABLE constants
# ------------------------------------------------------------------
_UNIQUE_KEY_FIELDS = ("SCHEMA_COLUMN", "KEY_ATTRIBUTE", "CASE_SENSITIVE")
_UNIQUE_KEY_GROUP_SIZE = len(_UNIQUE_KEY_FIELDS)


# ------------------------------------------------------------------
# TABLE parser
# ------------------------------------------------------------------
def _parse_unique_key(raw: Any) -> List[Dict[str, Any]]:
    """Parse UNIQUE_KEY TABLE into list of key column dicts.

    Each group of 3 consecutive elementRef entries maps to one row:
      SCHEMA_COLUMN   -> column (str, quotes stripped)
      KEY_ATTRIBUTE   -> is_key (bool) -- only rows with is_key=True are included
      CASE_SENSITIVE  -> case_sensitive (bool)

    Incomplete trailing groups (< 3 entries) are skipped.
    Returns only rows where KEY_ATTRIBUTE is true.
    """
    if not raw or not isinstance(raw, list):
        return []
    result: List[Dict[str, Any]] = []
    for i in range(0, len(raw), _UNIQUE_KEY_GROUP_SIZE):
        group = raw[i: i + _UNIQUE_KEY_GROUP_SIZE]
        if len(group) < _UNIQUE_KEY_GROUP_SIZE:
            break
        # Extract entries by position (stride-3: SCHEMA_COLUMN, KEY_ATTRIBUTE, CASE_SENSITIVE)
        schema_col_entry = group[0]
        key_attr_entry = group[1]
        case_sens_entry = group[2]

        # Only include rows where KEY_ATTRIBUTE is true
        is_key = key_attr_entry.get("value", "false").lower() in ("true", "1")
        if not is_key:
            continue

        col_name = schema_col_entry.get("value", "").strip('"')
        if not col_name:
            continue

        case_sensitive = case_sens_entry.get("value", "true").lower() in ("true", "1")
        result.append({
            "column": col_name,
            "case_sensitive": case_sensitive,
        })
    return result


@REGISTRY.register("tUniqueRow", "tUniqRow", "tUnqRow")
class UniqueRowConverter(ComponentConverter):
    """Convert Talend tUniqueRow to v1 engine config."""

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        params = node.params
        warnings: List[str] = []
        needs_review: List[Dict[str, Any]] = []

        # ---- 1. Core parameters ----
        only_once = self._get_bool(node, "ONLY_ONCE_EACH_DUPLICATED_KEY", default=False)
        keep = "last" if only_once else "first"

        # ---- 2. TABLE parameters: UNIQUE_KEY ----
        raw_unique_key = self._get_param(node, "UNIQUE_KEY", [])
        if not isinstance(raw_unique_key, list):
            warnings.append("UNIQUE_KEY param is not a list -- expected TABLE structure")
            raw_unique_key = []
        key_columns = _parse_unique_key(raw_unique_key)

        # Derive global case_sensitive from per-column values
        if key_columns:
            cs_values = [kc["case_sensitive"] for kc in key_columns]
            if all(cs_values):
                case_sensitive = True
            elif not any(cs_values):
                case_sensitive = False
            else:
                # Mixed: some columns case-sensitive, some not
                case_sensitive = True  # Conservative
                needs_review.append({
                    "issue": (
                        "Mixed per-column CASE_SENSITIVE in UNIQUE_KEY table -- "
                        "engine only supports a single global case_sensitive flag. "
                        "Using case_sensitive=True (conservative). "
                        f"Per-column values: {dict((kc['column'], kc['case_sensitive']) for kc in key_columns)}"
                    ),
                    "component": node.component_id,
                    "severity": "engine_gap",
                })
        else:
            case_sensitive = True  # Default when no key columns

        if not key_columns:
            warnings.append("No key columns defined -- component cannot determine uniqueness")

        # ---- 3. Advanced parameters ----
        is_virtual = self._get_bool(node, "IS_VIRTUAL_COMPONENT", default=False)
        buffer_size = self._get_str(node, "BUFFER_SIZE", default="M")
        change_hash = self._get_bool(node, "CHANGE_HASH_AND_EQUALS_FOR_BIGDECIMAL", default=False)

        # ---- 4. Framework parameters (ALWAYS LAST) ----
        tstatcatcher_stats = self._get_bool(node, "TSTATCATCHER_STATS", default=False)
        label = self._get_str(node, "LABEL", default="")

        # ---- 6. Build config ----
        config: Dict[str, Any] = {
            "key_columns": key_columns,
            "keep": keep,
            "case_sensitive": case_sensitive,
            "only_once_each_duplicated_key": only_once,
            "is_virtual_component": is_virtual,
            "buffer_size": buffer_size,
            "change_hash_and_equals_for_bigdecimal": change_hash,
            "tstatcatcher_stats": tstatcatcher_stats,
            "label": label,
        }

        # ---- 7. Schema ----
        schema_cols = self._parse_schema(node)
        schema = {"input": schema_cols, "output": schema_cols}

        # ---- 8. Engine gap needs_review entries ----
        _engine_gap_keys = [
            ("case_sensitive", "Engine uses global case_sensitive only; Talend supports per-column CASE_SENSITIVE"),
            ("is_virtual_component", "Engine does not implement IS_VIRTUAL_COMPONENT disk-based processing mode"),
            ("only_once_each_duplicated_key", "Engine approximates via keep=first/last; does not suppress repeat duplicates"),
        ]
        for key, detail in _engine_gap_keys:
            needs_review.append({
                "issue": f"Engine does not fully support '{key}' config key -- {detail}",
                "component": node.component_id,
                "severity": "engine_gap",
            })

        # Conditional: CHANGE_HASH only relevant when enabled
        if change_hash:
            needs_review.append({
                "issue": (
                    "CHANGE_HASH_AND_EQUALS_FOR_BIGDECIMAL is enabled but "
                    "engine does not implement BigDecimal trailing zero "
                    "normalization -- Decimal('1.00') and Decimal('1.0') may "
                    "be treated as different values during deduplication"
                ),
                "component": node.component_id,
                "severity": "engine_gap",
            })

        # ---- 9. Return ----
        component = self._build_component_dict(
            node=node,
            type_name="UniqueRow",
            config=config,
            schema=schema,
        )
        return ComponentResult(
            component=component,
            warnings=warnings,
            needs_review=needs_review,
        )
