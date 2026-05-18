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

import logging
import re
from enum import Enum
from typing import Any, Callable

import numpy as np
import pandas as pd

from .map_config import JoinKeyCfg, LookupCfg
from src.v1.engine.exceptions import ComponentExecutionError


logger = logging.getLogger(__name__)


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


BridgeEvalFn = Callable[
    [pd.DataFrame, dict[str, str], str, list[str]],
    dict[str, list],
]


def join_computed_equality(
    joined_df: pd.DataFrame,
    lookup_df: pd.DataFrame,
    lk: LookupCfg,
    main_name: str,
    prior_lookups: list[str],
    bridge_eval_fn: BridgeEvalFn,
) -> tuple[pd.DataFrame, pd.DataFrame | None]:
    """COMPUTED strategy: batch-eval key expressions on joined_df, then merge.

    For each join key, the expression is batch-evaluated once across all
    rows of joined_df via the Java bridge. The results are materialized
    as temp columns __jk_main_<i>__ and used as left keys in a pandas
    merge against the lookup. Temp columns are dropped from the result.

    Args:
        joined_df: current joined frame (main + prior lookups).
        lookup_df: the lookup being joined.
        lk: this lookup's config (join_keys contain expressions).
        main_name: name of the main table (for the bridge eval).
        prior_lookups: names of lookups already in joined_df (for bridge
            row binding so expressions can reference row3.col when row3
            was joined earlier).
        bridge_eval_fn: callable that executes the bridge eval. Injected
            for testability; production wires this through
            JavaBridge.execute_tmap_preprocessing.

    Returns:
        (merged_frame, inner_join_rejects_or_None)
    """
    # Step 1: batch-eval all join key expressions on joined_df
    exprs = {
        f"__jk_main_{i}__": _strip_marker(jk.expression)
        for i, jk in enumerate(lk.join_keys)
    }
    eval_results = bridge_eval_fn(joined_df, exprs, main_name, prior_lookups)

    # Step 2: materialize temp columns on a copy of joined_df
    joined_df = joined_df.copy()
    temp_cols: list[str] = []
    for i in range(len(lk.join_keys)):
        col = f"__jk_main_{i}__"
        temp_cols.append(col)
        joined_df[col] = eval_results.get(col, [None] * len(joined_df))

    # Step 3: dedup lookup per matching mode, prefix lookup cols
    right_keys = [jk.lookup_column for jk in lk.join_keys]
    lookup_df = _apply_matching_mode(lookup_df, right_keys, lk.matching_mode)
    lookup_df = _prefix_lookup_columns(lookup_df, lk.name)
    prefixed_right = [f"{lk.name}.{k}" for k in right_keys]

    # Step 4: merge using temp cols as left keys, with null pre-filter
    main_nonnull, main_null = _prefilter_null_keys(joined_df, temp_cols)
    lookup_nonnull, _ = _prefilter_null_keys(lookup_df, prefixed_right)

    if main_nonnull.empty:
        merged = pd.DataFrame(
            columns=list(joined_df.columns) + list(lookup_df.columns)
        )
        rejects = main_null.copy() if lk.join_mode == "INNER_JOIN" else None
    else:
        merged = pd.merge(
            main_nonnull, lookup_nonnull,
            left_on=temp_cols, right_on=prefixed_right,
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

    if lk.join_mode != "INNER_JOIN" and not main_null.empty:
        merged = pd.concat([merged, main_null], ignore_index=True)

    # Step 5: drop temp cols and __dup__ cols
    drop_cols = temp_cols + [c for c in merged.columns if c.endswith("__dup__")]
    existing_drop = [c for c in drop_cols if c in merged.columns]
    if existing_drop:
        merged = merged.drop(columns=existing_drop)
    if rejects is not None:
        rej_drop = [c for c in temp_cols if c in rejects.columns]
        if rej_drop:
            rejects = rejects.drop(columns=rej_drop)

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


# ---- Task 4.5: FILTER_AS_MATCH strategy ----

_WARN_RESULT_ROWS = 10_000_000
_FAIL_RESULT_ROWS = 100_000_000


def _check_cross_size_guard(main_n: int, lookup_n: int) -> None:
    """Raise ComponentExecutionError if main_n * lookup_n >= 100M.

    Preserves the legacy 10M warn / 100M fail thresholds. WARN logging
    happens in join_filter_as_match itself, near the chunking decision.
    """
    product = main_n * lookup_n
    if product >= _FAIL_RESULT_ROWS:
        raise ComponentExecutionError(
            "tMap",
            f"Cross-product would produce ~{product:,} rows "
            f"(main={main_n:,} x lookup={lookup_n:,}). "
            f"Exceeds safety limit of {_FAIL_RESULT_ROWS:,}."
        )


def _compute_cross_chunk_size(lookup_rows: int) -> int:
    """Auto-tune chunk size to bound peak intermediate memory at ~100M cells.

    Mirrors the legacy heuristic. chunk_size * lookup_rows <= 100M cells.
    Floor 100, ceiling 10_000.
    """
    return max(100, min(10_000, 100_000_000 // max(1, lookup_rows)))


def join_filter_as_match(
    joined_df: pd.DataFrame,
    lookup_df: pd.DataFrame,
    lk: LookupCfg,
    main_name: str,
    prior_lookups: list[str],
    bridge_eval_fn: BridgeEvalFn | None,
) -> tuple[pd.DataFrame, pd.DataFrame | None]:
    """FILTER_AS_MATCH: chunked cross-product, optionally filtered by lk.filter.

    For each chunk of joined_df:
      - Cross-product chunk x full lookup
      - If lk.filter set: bridge-eval the filter once per chunk (one bridge
        call per chunk, NOT per row); apply the boolean mask
      - If no filter (pure cartesian): keep all

    INNER_JOIN: main rows that survived 0 matches go to rejects.
    LEFT_OUTER_JOIN: empty lookup -> joined_df unchanged.

    Size guard: 10M product warns; 100M product raises
    ComponentExecutionError.
    """
    if lookup_df.empty:
        empty = pd.DataFrame(columns=list(joined_df.columns) + list(lookup_df.columns))
        return empty, (joined_df.copy() if lk.join_mode == "INNER_JOIN" else None)

    _check_cross_size_guard(len(joined_df), len(lookup_df))

    product = len(joined_df) * len(lookup_df)
    if product >= _WARN_RESULT_ROWS:
        logger.warning(
            "[tMap] Cross-product with '%s': ~%d rows (main=%d x lookup=%d)",
            lk.name, product, len(joined_df), len(lookup_df),
        )

    lookup_prefixed = _prefix_lookup_columns(lookup_df, lk.name)

    has_filter = lk.activate_filter and lk.filter
    filter_expr = _strip_marker(lk.filter) if has_filter else None

    chunk_size = _compute_cross_chunk_size(len(lookup_prefixed))
    result_chunks: list[pd.DataFrame] = []

    for start in range(0, len(joined_df), chunk_size):
        chunk = joined_df.iloc[start:start + chunk_size]
        cross = pd.merge(chunk, lookup_prefixed, how="cross")
        if filter_expr is None:
            result_chunks.append(cross)
            continue
        if bridge_eval_fn is None:
            raise RuntimeError(
                "FILTER_AS_MATCH has a filter but bridge_eval_fn was not provided"
            )
        eval_results = bridge_eval_fn(
            cross, {"__filter__": filter_expr},
            main_name, prior_lookups + [lk.name],
        )
        if "__filter__" in eval_results:
            mask = pd.Series(
                eval_results["__filter__"]
            ).fillna(False).astype(bool).values
            result_chunks.append(cross[mask])

    if not result_chunks:
        merged = pd.DataFrame(
            columns=list(joined_df.columns) + list(lookup_prefixed.columns)
        )
    else:
        merged = pd.concat(result_chunks, ignore_index=True)

    rejects: pd.DataFrame | None = None
    if lk.join_mode == "INNER_JOIN":
        main_cols = list(joined_df.columns)
        if not merged.empty:
            matched_main = merged[main_cols].drop_duplicates()
            flagged = joined_df.merge(
                matched_main.assign(__matched__=True),
                on=main_cols, how="left",
            )
            unmatched = flagged[flagged["__matched__"].isna()].drop(columns=["__matched__"])
            if not unmatched.empty:
                rejects = unmatched.copy()
        else:
            rejects = joined_df.copy()

    return merged, rejects


def join_reload_per_row(
    joined_df: pd.DataFrame,
    lookup_df: pd.DataFrame,
    lk: LookupCfg,
    bridge_eval_fn: BridgeEvalFn | None,
    main_name: str = "row1",
) -> tuple[pd.DataFrame, pd.DataFrame | None]:
    """RELOAD_AT_EACH_ROW: re-match the lookup for every main row.

    For each main row, when the lookup has an active filter, substitute main
    row column values into the filter expression (_substitute_row_refs), then
    bridge-evaluate the substituted filter against the lookup to produce a
    per-row filtered lookup before key matching.

    Null-safe: TypeError/ValueError/ComponentExecutionError from the bridge
    eval treat the filtered lookup as empty (no match for that row).

    Args:
        joined_df: current joined frame (main + prior lookups).
        lookup_df: the current lookup's full unfiltered frame.
        lk: this lookup's config.
        bridge_eval_fn: callable for bridge evaluation (required when the
            lookup has an active filter expression).
        main_name: name of the main input table (used for ref substitution).

    Returns:
        (merged_frame, inner_join_rejects_or_None)
    """
    key_cols = [jk.lookup_column for jk in lk.join_keys]
    lookup_prefixed_cols = [
        col if col.startswith(f"{lk.name}.") else f"{lk.name}.{col}"
        for col in lookup_df.columns
    ]

    has_filter = lk.activate_filter and lk.filter
    base_filter_expr = lk.filter if has_filter else None

    result_rows: list[pd.Series] = []
    reject_rows: list[pd.Series] = []

    for _, main_row in joined_df.iterrows():
        # Per-row lookup filter substitution: replace main row column values
        # into the filter expression, then bridge-evaluate against lookup.
        if has_filter and base_filter_expr is not None:
            # Strip {{java}} marker, substitute, re-attach
            raw_expr = _strip_marker(base_filter_expr)
            substituted = _substitute_row_refs(raw_expr, main_row, main_name)
            marked_expr = _JAVA_MARKER + substituted
            try:
                filtered = apply_filter(
                    lookup_df, marked_expr, bridge_eval_fn, main_name, [lk.name],
                )
            except (TypeError, ValueError, ComponentExecutionError):
                filtered = lookup_df.iloc[0:0]
        else:
            filtered = lookup_df

        if filtered.empty:
            if lk.join_mode == "INNER_JOIN":
                reject_rows.append(main_row)
            else:
                result_rows.append(main_row)
            continue

        filtered = _apply_matching_mode(filtered, key_cols, lk.matching_mode)
        filtered_prefixed = _prefix_lookup_columns(filtered, lk.name)

        matched = False
        for _, lookup_row in filtered_prefixed.iterrows():
            key_match = True
            for jk in lk.join_keys:
                expr = _strip_marker(jk.expression)
                m = _SIMPLE_COL_RE.match(expr.strip())
                if m:
                    table, col = m.group(1), m.group(2)
                    src_col = (
                        f"{table}.{col}" if f"{table}.{col}" in joined_df.columns
                        else col
                    )
                    main_val = main_row.get(src_col)
                else:
                    main_val = None
                lookup_val = lookup_row.get(f"{lk.name}.{jk.lookup_column}")
                if pd.isna(main_val) or pd.isna(lookup_val) or main_val != lookup_val:
                    key_match = False
                    break
            if key_match:
                combined = pd.concat([main_row, lookup_row])
                result_rows.append(combined)
                matched = True
                if lk.matching_mode in ("UNIQUE_MATCH", "FIRST_MATCH", "LAST_MATCH"):
                    break

        if not matched:
            if lk.join_mode == "INNER_JOIN":
                reject_rows.append(main_row)
            else:
                combined = main_row.copy()
                for col in lookup_prefixed_cols:
                    combined[col] = np.nan
                result_rows.append(combined)

    result_df = (
        pd.DataFrame(result_rows).reset_index(drop=True)
        if result_rows
        else pd.DataFrame(columns=list(joined_df.columns) + lookup_prefixed_cols)
    )
    rejects = (
        pd.DataFrame(reject_rows).reset_index(drop=True)
        if reject_rows else None
    )
    return result_df, rejects


def apply_filter(
    df: pd.DataFrame,
    filter_expr: str,
    bridge_eval_fn: BridgeEvalFn | None,
    main_name: str,
    lookup_names: list[str],
) -> pd.DataFrame:
    """Apply a filter expression to a DataFrame via the bridge.

    Returns df unchanged when filter_expr is empty. Empty DataFrame
    short-circuits without invoking the bridge.

    Bridge eval is required for any non-empty filter (the rewrite has no
    Python-eval path for filters). Raises RuntimeError if filter is
    non-empty but bridge_eval_fn is None.
    """
    if not filter_expr:
        return df
    if df.empty:
        return df
    if bridge_eval_fn is None:
        raise RuntimeError(
            "apply_filter called with a non-empty filter but no bridge_eval_fn"
        )
    expr = _strip_marker(filter_expr)
    results = bridge_eval_fn(df, {"__filter__": expr}, main_name, lookup_names)
    mask = pd.Series(
        results.get("__filter__", [])
    ).fillna(False).astype(bool).values
    return df[mask].copy() if mask.size == len(df) else df


# ---- RELOAD per-row filter substitution ----

_ROW_REF_PATTERN = re.compile(
    r'\b([a-zA-Z_][a-zA-Z0-9_]*)\.([a-zA-Z_][a-zA-Z0-9_]*)\b'
)


def _substitute_row_refs(
    expr: str,
    main_row: "pd.Series",
    main_name: str,
) -> str:
    """Replace main_name.col references in expr with literal values from main_row.

    Quote-aware: references whose span falls inside a double-quoted string
    literal in expr are left untouched (they are part of a string value, not
    a row reference).

    Value-to-literal rules:
      - None / pd.isna  -> ``None``
      - str             -> ``"<escaped>"`` (backslashes + quotes escaped)
      - bool / np.bool_ -> ``True`` / ``False``
      - numeric         -> ``repr(val)``

    Args:
        expr: filter expression string ({{java}} marker already stripped).
        main_row: the current main row as a pandas Series.
        main_name: name of the main table (e.g. ``"row1"``).

    Returns:
        Expression with main_name.col references substituted by their values.
    """
    # Precompute spans of double-quoted string literals in the expression.
    # Matches simple double-quoted strings; escaped quotes handled via the
    # negative lookbehind on the closing quote.
    quoted_ranges: list[tuple[int, int]] = []
    for m in re.finditer(r'"(?:[^"\\]|\\.)*"', expr):
        quoted_ranges.append(m.span())

    def _in_quoted(start: int, end: int) -> bool:
        for qs, qe in quoted_ranges:
            if start >= qs and end <= qe:
                return True
        return False

    def _to_literal(val: Any) -> str:
        if val is None or (not isinstance(val, bool) and isinstance(val, float)
                           and np.isnan(val)):
            return "None"
        try:
            if pd.isna(val):
                return "None"
        except (TypeError, ValueError):
            pass
        if isinstance(val, (bool, np.bool_)):
            return "True" if val else "False"
        if isinstance(val, str):
            escaped = val.replace("\\", "\\\\").replace('"', '\\"')
            return f'"{escaped}"'
        return repr(val)

    result_parts: list[str] = []
    last_end = 0

    for m in _ROW_REF_PATTERN.finditer(expr):
        table, col = m.group(1), m.group(2)
        if table != main_name:
            continue
        if _in_quoted(m.start(), m.end()):
            continue
        # Resolve column value from main_row
        val = main_row.get(col)
        result_parts.append(expr[last_end:m.start()])
        result_parts.append(_to_literal(val))
        last_end = m.end()

    result_parts.append(expr[last_end:])
    return "".join(result_parts)
