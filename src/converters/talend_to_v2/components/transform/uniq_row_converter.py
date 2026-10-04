"""Converter for Talend tUniqRow to v2 UniqRow component.

Parses UNIQUE_KEY TABLE (stride-3: SCHEMA_COLUMN, KEY_ATTRIBUTE, CASE_SENSITIVE)
into v2 key_columns config. Maps ONLY_ONCE_EACH_DUPLICATED_KEY to keep mode.
Handles UNIQUE/DUPLICATE named output connectors (NOT FLOW/REJECT).

Config mapping:
  UNIQUE_KEY TABLE             -> key_columns (list[dict])
  ONLY_ONCE_EACH_DUPLICATED_KEY -> keep ('last' if true, 'first' if false)
  ONLY_ONCE_EACH_DUPLICATED_KEY -> only_once (bool)
  (wired DUPLICATE connector)  -> duplicate_output (bool)
  IS_VIRTUAL_COMPONENT         -> warning (UNSUPPORTED per D-12)
  BUFFER_SIZE                  -> warning (UNSUPPORTED per D-13)
  TEMP_DIRECTORY               -> warning (UNSUPPORTED per D-13)
  CHANGE_HASH_AND_EQUALS_FOR_BIGDECIMAL -> warning (NOT_PLANNED per D-14)
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY as CONVERTER_REGISTRY

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
      KEY_ATTRIBUTE   -> is_key (bool) -- only rows with is_key=True included
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
        # Extract entries by position (stride-3), with elementRef validation
        schema_col_entry = group[0]
        key_attr_entry = group[1]
        case_sens_entry = group[2]

        # Defensive: verify elementRef ordering matches expectation
        actual_refs = tuple(e.get("elementRef", "") for e in group)
        if actual_refs != _UNIQUE_KEY_FIELDS:
            logger.warning(
                "UNIQUE_KEY TABLE elementRef order mismatch: expected %s, got %s. "
                "Falling back to elementRef-based lookup.",
                _UNIQUE_KEY_FIELDS, actual_refs,
            )
            by_ref = {e.get("elementRef", ""): e for e in group}
            schema_col_entry = by_ref.get("SCHEMA_COLUMN", group[0])
            key_attr_entry = by_ref.get("KEY_ATTRIBUTE", group[1])
            case_sens_entry = by_ref.get("CASE_SENSITIVE", group[2])

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


# ------------------------------------------------------------------
# Connection helpers
# ------------------------------------------------------------------
def _has_duplicate_connection(
    node: TalendNode,
    connections: list[TalendConnection],
) -> bool:
    """Return True if any outgoing connection from *node* has DUPLICATE type."""
    return any(
        c.source == node.component_id and c.connector_type == "DUPLICATE"
        for c in connections
    )


def _build_uniq_row_flows(
    node: TalendNode,
    connections: list[TalendConnection],
) -> list[dict]:
    """Build v2 flow dicts with UNIQUE/DUPLICATE output mapping.

    _build_simple_flows does NOT handle UNIQUE or DUPLICATE connector types,
    so this function handles them explicitly.

    * Incoming FLOW/MAIN -> standard flow
    * Outgoing UNIQUE   -> flow with output='unique'
    * Outgoing DUPLICATE -> flow with output='duplicate'
    * Outgoing FLOW/MAIN -> standard flow (fallback for non-standard wiring)
    """
    _MAIN_TYPES = {"FLOW", "MAIN"}
    flows: list[dict] = []

    for conn in connections:
        if conn.target == node.component_id and conn.connector_type in _MAIN_TYPES:
            flows.append({
                "name": conn.name,
                "source": conn.source,
                "target": conn.target,
            })
        elif conn.source == node.component_id:
            if conn.connector_type == "UNIQUE":
                flows.append({
                    "name": conn.name,
                    "source": conn.source,
                    "target": conn.target,
                    "output": "unique",
                })
            elif conn.connector_type == "DUPLICATE":
                flows.append({
                    "name": conn.name,
                    "source": conn.source,
                    "target": conn.target,
                    "output": "duplicate",
                })
            elif conn.connector_type in _MAIN_TYPES:
                flows.append({
                    "name": conn.name,
                    "source": conn.source,
                    "target": conn.target,
                })

    return flows


# ------------------------------------------------------------------
# Converter
# ------------------------------------------------------------------
@CONVERTER_REGISTRY.register("tUniqRow", "tUniqueRow", "tUnqRow")
class UniqRowConverter(ComponentConverter):
    """Convert Talend tUniqRow to v2 uniq_row config."""

    def convert(
        self,
        node: TalendNode,
        connections: list[TalendConnection],
        context: dict,
    ) -> ComponentResult:
        """Convert a TalendNode into a v2 UniqRow component dict."""
        warnings: List[str] = []
        needs_review: List[Dict[str, Any]] = []

        # ---- 1. Parse UNIQUE_KEY TABLE (stride-3) ----
        raw_unique_key = node.params.get("UNIQUE_KEY", [])
        if not isinstance(raw_unique_key, list):
            warnings.append("UNIQUE_KEY param is not a list -- expected TABLE structure")
            raw_unique_key = []
        key_columns = _parse_unique_key(raw_unique_key)

        if not key_columns:
            warnings.append("No key columns defined in UNIQUE_KEY table")

        # ---- 1b. Validate key columns against incoming schema ----
        # Cross-check parsed key column names against the node's schema metadata.
        # If a key column is not found in the schema, emit a warning so users
        # catch config errors at conversion time rather than at runtime.
        schema_columns: set[str] = set()
        if hasattr(node, "schema") and node.schema:
            if isinstance(node.schema, list):
                schema_columns = {
                    col.get("name", col.get("label", ""))
                    for col in node.schema
                    if isinstance(col, dict)
                }
            elif isinstance(node.schema, dict):
                # schema may be a dict with "input"/"output" keys
                for cols in node.schema.values():
                    if isinstance(cols, list):
                        schema_columns.update(
                            col.get("name", col.get("label", ""))
                            for col in cols
                            if isinstance(col, dict)
                        )
        if schema_columns and key_columns:
            for kc in key_columns:
                col_name = kc.get("column", "")
                if col_name and col_name not in schema_columns:
                    warnings.append(
                        f"Key column '{col_name}' not found in component schema "
                        f"(available: {sorted(schema_columns)}). Check column name spelling."
                    )

        # ---- 2. ONLY_ONCE_EACH_DUPLICATED_KEY -> keep + only_once ----
        only_once_raw = node.params.get("ONLY_ONCE_EACH_DUPLICATED_KEY", False)
        if isinstance(only_once_raw, str):
            only_once = only_once_raw.lower() == "true"
        else:
            only_once = bool(only_once_raw)
        keep = "last" if only_once else "first"

        # ---- 3. Detect duplicate output connection ----
        has_dup = _has_duplicate_connection(node, connections)

        # ---- 4. Build config ----
        config: Dict[str, Any] = {
            "key_columns": key_columns,
            "keep": keep,
            "maintain_order": True,
        }
        if has_dup:
            config["duplicate_output"] = True
        if only_once:
            config["only_once"] = True

        # ---- 5. UNSUPPORTED / NOT_PLANNED feature warnings ----
        is_virtual_raw = node.params.get("IS_VIRTUAL_COMPONENT", False)
        if isinstance(is_virtual_raw, str):
            is_virtual = is_virtual_raw.lower() == "true"
        else:
            is_virtual = bool(is_virtual_raw)
        if is_virtual:
            warnings.append(
                "Feature 'is_virtual_component' is UNSUPPORTED in v2: "
                "Disk-based processing has no Polars equivalent. "
                "Lazy evaluation + streaming is v2's answer to large data."
            )

        change_hash_raw = node.params.get("CHANGE_HASH_AND_EQUALS_FOR_BIGDECIMAL", False)
        if isinstance(change_hash_raw, str):
            change_hash = change_hash_raw.lower() == "true"
        else:
            change_hash = bool(change_hash_raw)
        if change_hash:
            warnings.append(
                "Feature 'change_hash_bigdecimal' is NOT_PLANNED in v2: "
                "Polars Decimal dtype has limited trailing-zero normalization. "
                "Decimal('1.00') and Decimal('1.0') may be treated as different values."
            )
            needs_review.append({
                "issue": "CHANGE_HASH_AND_EQUALS_FOR_BIGDECIMAL enabled but not supported in v2",
                "component": node.component_id,
                "severity": "engine_gap",
            })

        # ---- 6. Introspection: warn on any other UNSUPPORTED features ----
        try:
            from src.v2.components.capabilities import Support, get_supported_features
            from src.v2.components.transform.uniq_row import UniqRow

            features = get_supported_features(UniqRow)
            for feat_key, feat_support in features.items():
                if feat_support.support == Support.UNSUPPORTED:
                    param_name = feat_key.upper()
                    if node.params.get(param_name) and param_name not in (
                        "IS_VIRTUAL_COMPONENT",
                        "BUFFER_SIZE",
                        "TEMP_DIRECTORY",
                    ):
                        warnings.append(
                            f"Feature '{feat_key}' is UNSUPPORTED in v2: {feat_support.note}"
                        )
        except ImportError:
            logger.debug("Could not import UniqRow component for feature introspection")

        # ---- 7. Build component dict ----
        component = {
            "id": node.component_id,
            "type": "uniq_row",
            "config": config,
        }

        # ---- 8. Build flows (custom: handles UNIQUE/DUPLICATE connector types) ----
        flows = _build_uniq_row_flows(node, connections)

        return ComponentResult(
            component=component,
            flows=flows,
            warnings=warnings,
            needs_review=needs_review,
        )
