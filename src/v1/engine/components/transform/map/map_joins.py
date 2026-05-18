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

import pandas as pd

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


# ---- Task 4.3: SIMPLE strategy join ----


def join_simple_equality(
    joined_df: pd.DataFrame,
    lookup_df: pd.DataFrame,
    lk: LookupCfg,
) -> tuple[pd.DataFrame, pd.DataFrame | None]:
    """SIMPLE strategy: pandas merge directly using plain column refs.

    All join keys are simple column references (verified by
    classify_join_strategy). Apply matching mode dedup to the lookup, then
    pandas.merge with prefixed lookup columns.

    Args:
        joined_df: current joined frame (main + prior lookups).
        lookup_df: the current lookup's frame.
        lk: this lookup's config.

    Returns:
        (merged_frame, inner_join_rejects_or_None)
    """
    left_keys: list[str] = []
    for jk in lk.join_keys:
        match = _SIMPLE_COL_RE.match(_strip_marker(jk.expression).strip())
        # We are in SIMPLE strategy, so match is guaranteed
        table = match.group(1)
        col = match.group(2)
        # column could be unprefixed (from main) or prefixed (from prior lookup)
        prefixed = f"{table}.{col}"
        if prefixed in joined_df.columns:
            left_keys.append(prefixed)
        elif col in joined_df.columns:
            left_keys.append(col)
        else:
            # Fall back to prefixed form; merge will error helpfully if absent
            left_keys.append(prefixed)
    right_keys = [jk.lookup_column for jk in lk.join_keys]

    # Apply matching mode to the lookup BEFORE prefixing column names
    lookup_df = _apply_matching_mode(lookup_df, right_keys, lk.matching_mode)

    # Prefix lookup columns to avoid collisions with main / prior lookups
    lookup_df = _prefix_lookup_columns(lookup_df, lk.name)
    prefixed_right_keys = [f"{lk.name}.{k}" for k in right_keys]

    # Null-key pre-filter: SQL / Talend null-never-matches semantics
    main_nonnull, main_null = _prefilter_null_keys(joined_df, left_keys)
    lookup_nonnull, _ = _prefilter_null_keys(lookup_df, prefixed_right_keys)

    if main_nonnull.empty:
        merged = pd.DataFrame(
            columns=list(joined_df.columns) + list(lookup_df.columns)
        )
        rejects = main_null.copy() if lk.join_mode == "INNER_JOIN" else None
    else:
        merged = pd.merge(
            main_nonnull, lookup_nonnull,
            left_on=left_keys, right_on=prefixed_right_keys,
            how="left", indicator=True, suffixes=("", "__dup__"),
        )
        rejects = None
        if lk.join_mode == "INNER_JOIN":
            unmatched = merged["_merge"] == "left_only"
            if unmatched.any():
                rejects = merged.loc[unmatched].drop(columns=["_merge"]).copy()
            if not main_null.empty:
                rejects = (
                    pd.concat([rejects, main_null], ignore_index=True)
                    if rejects is not None else main_null.copy()
                )
            merged = merged.loc[~unmatched].copy()
        if "_merge" in merged.columns:
            merged = merged.drop(columns=["_merge"])

    # For LEFT_OUTER join, re-add null-key main rows (lookup cols stay NaN)
    if lk.join_mode != "INNER_JOIN" and not main_null.empty:
        merged = pd.concat([merged, main_null], ignore_index=True)

    # Drop duplicate join-key cols on the lookup side (left side keeps the value)
    dup_cols = [c for c in merged.columns if c.endswith("__dup__")]
    if dup_cols:
        merged = merged.drop(columns=dup_cols)

    return merged, rejects


def _apply_matching_mode(
    lookup_df: pd.DataFrame, key_cols: list[str], mode: str,
) -> pd.DataFrame:
    """Dedup lookup rows per matching mode (Talend HashMap.put semantic).

    UNIQUE_MATCH and LAST_MATCH both keep the LAST occurrence -- Talend's
    HashMap.put overwrites on duplicate key, so the last write wins.
    FIRST_MATCH keeps the first. ALL_MATCHES disables dedup.
    """
    if lookup_df.empty or mode == "ALL_MATCHES":
        return lookup_df
    existing = [k for k in key_cols if k in lookup_df.columns]
    if not existing:
        return lookup_df
    if mode == "FIRST_MATCH":
        return lookup_df.drop_duplicates(subset=existing, keep="first")
    # UNIQUE_MATCH and LAST_MATCH
    return lookup_df.drop_duplicates(subset=existing, keep="last")


def _prefix_lookup_columns(
    lookup_df: pd.DataFrame, lookup_name: str,
) -> pd.DataFrame:
    """Rename lookup columns to lookup_name.col so they don't collide."""
    renamed = {
        col: f"{lookup_name}.{col}"
        for col in lookup_df.columns
        if not str(col).startswith(f"{lookup_name}.")
    }
    return lookup_df.rename(columns=renamed) if renamed else lookup_df


def _prefilter_null_keys(
    df: pd.DataFrame, key_cols: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split into (rows with all keys non-null, rows with any key null).

    Null keys never match in SQL/Talend; pre-filtering keeps the merge
    fast-path correct.
    """
    if df.empty:
        return df.copy(), pd.DataFrame(columns=df.columns)
    existing = [k for k in key_cols if k in df.columns]
    if not existing:
        return df.copy(), pd.DataFrame(columns=df.columns)
    null_mask = df[existing].isna().any(axis=1)
    return df[~null_mask].copy(), df[null_mask].copy()
