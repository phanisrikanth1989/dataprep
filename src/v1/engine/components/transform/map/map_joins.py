"""Join execution + strategy classification + joined_df schema composition.

Three strategies for non-RELOAD lookups:
  SIMPLE          -- all join keys are plain column refs; pandas merge directly
  COMPUTED        -- at least one key is an expression; batch-eval once, then merge
  FILTER_AS_MATCH -- no equality keys; lookup filter (or none) does the matching;
                     chunked cross-product

RELOAD is a separate dispatch for RELOAD_AT_EACH_ROW lookups.

See spec section 6 for full semantics.
"""
from __future__ import annotations

import re
from enum import Enum
from typing import Any

from .map_config import JoinKeyCfg, LookupCfg


_JAVA_MARKER = "{{java}}"
_SIMPLE_COL_RE = re.compile(r"^([a-zA-Z_]\w*)\.([a-zA-Z_]\w*)$")


class JoinStrategy(Enum):
    SIMPLE = "simple"
    COMPUTED = "computed"
    FILTER_AS_MATCH = "filter_as_match"
    RELOAD = "reload"


def classify_join_strategy(lk: LookupCfg) -> JoinStrategy:
    """Classify a lookup's join strategy by its config.

    RELOAD takes precedence over key-based classification (RELOAD changes
    the execution model entirely, regardless of key shape).
    """
    if lk.lookup_mode == "RELOAD_AT_EACH_ROW":
        return JoinStrategy.RELOAD
    if not lk.join_keys:
        return JoinStrategy.FILTER_AS_MATCH
    if all(_is_simple_col_ref(_strip_marker(jk.expression)) for jk in lk.join_keys):
        return JoinStrategy.SIMPLE
    return JoinStrategy.COMPUTED


def compute_joined_df_schema(
    main_schema: list[dict[str, Any]],
    consumed_lookups: list[tuple[str, list[dict[str, Any]]]],
    variables: list[Any],
    temp_join_key_cols: dict[str, str],
) -> dict[str, str]:
    """Compose the schema for joined_df from declared types.

    Single source of truth for joined_df column types. Used by the bridge
    for Arrow serialization (no inference, no fallback to 'str').

    Args:
        main_schema: List of {name, type, ...} dicts for main input columns
            (unprefixed names).
        consumed_lookups: Per-lookup [(name, schema_list)] for each lookup
            already joined. Schema entries are unprefixed; this function
            adds the lookup_name prefix.
        variables: List of VariableCfg; Var columns added as 'Var.<name>'.
        temp_join_key_cols: Map of temp column name (e.g. '__jk_main_0__')
            to its type. Used by COMPUTED strategy.

    Returns:
        Dict of {column_name: type_string} covering every column expected
        in joined_df at script-execution time.
    """
    schema: dict[str, str] = {}
    for col in main_schema:
        schema[col["name"]] = col["type"]
    for lookup_name, lookup_schema in consumed_lookups:
        for col in lookup_schema:
            schema[f"{lookup_name}.{col['name']}"] = col["type"]
    for v in variables:
        schema[f"Var.{v.name}"] = v.type
    for tmp_col, tmp_type in temp_join_key_cols.items():
        schema[tmp_col] = tmp_type
    return schema


# ---- private helpers ----


def _strip_marker(expr: str) -> str:
    return expr[len(_JAVA_MARKER):] if expr.startswith(_JAVA_MARKER) else expr


def _is_simple_col_ref(expr: str) -> bool:
    return bool(_SIMPLE_COL_RE.match(expr.strip()))
