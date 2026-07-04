"""Post-bridge reject routing for 3 reject types.

- is_reject:           populated inline by active script; pass through
- inner_join_reject:   populated by reject-pass script (only when
                       inner_join_reject_dfs from the join phase is
                       non-empty); pass through. The reject-pass script 
                       evaluates the outputs own 'filter' before omitting rows, 
                       so this dict already reflects post filter row counts.
                       
- catch_output_reject: joined_df rows selected by __errors__ rowIndex; user
                       column exprs evaluated, then framework errorMessage /
                       errorStackTrace columns overlaid (D-06 reserved-col
                       policy: framework wins).
"""
from __future__ import annotations

import pandas as pd

from .map_config import MapConfig


_RESERVED_COLS = ("errorMessage", "errorStackTrace")


def route_rejects(
    active_results: dict[str, pd.DataFrame],
    reject_results: dict[str, pd.DataFrame],
    errors_df: pd.DataFrame | None,
    inner_join_reject_dfs: dict[str, pd.DataFrame],
    cfg: MapConfig,
    joined_df: pd.DataFrame,
) -> dict[str, pd.DataFrame]:
    """Produce the final dict[output_name -> DataFrame].

    Args:
        active_results: Output frames from the active-pass bridge call,
            keyed by output name. Includes is_reject outputs (populated
            inline by the script).
        reject_results: Output frames from the reject-pass bridge call
            (only the inner_join_reject outputs; empty dict if no reject
            pass invoked).
        errors_df: The __errors__ DataFrame extracted from the active
            bridge result (rowIndex / errorMessage / errorStackTrace),
            or None if no expression errors.
        inner_join_reject_dfs: Per-failing-lookup reject rows from the
            join phase. Used for sanity (its emptiness drives whether
            the reject pass was invoked).
        cfg: Parsed MapConfig.
        joined_df: The frame the active script ran against. Used to
            select failing rows for catch_output_reject by rowIndex.

    Returns:
        Dict from output name to its final DataFrame.
    """
    result: dict[str, pd.DataFrame] = {}

    for out in cfg.outputs:
        if out.catch_output_reject:
            result[out.name] = _route_catch_output(
                out, errors_df, joined_df,
            )
        elif out.inner_join_reject:
            result[out.name] = reject_results.get(
                out.name,
                _empty_frame_for(out),
            )
        else:
            # active output OR is_reject -- both already populated by
            # the active script.
            result[out.name] = active_results.get(
                out.name,
                _empty_frame_for(out),
            )

    return result


def _empty_frame_for(out) -> pd.DataFrame:
    return pd.DataFrame(columns=[c.name for c in out.columns])


def _route_catch_output(out, errors_df, joined_df) -> pd.DataFrame:
    """Build a catch_output_reject frame from errors_df + joined_df.

    For each failing row (by rowIndex into joined_df):
      - Evaluate user-defined column expressions against the failing row's
        data (simple ref resolution: 'row1.col' or bare 'col' looks up the
        column in joined_df).
      - Overlay framework 'errorMessage' / 'errorStackTrace' columns if the
        user declared them (D-06 reserved-col policy: framework value WINS).

    Args:
        out: OutputCfg for this catch_output_reject output.
        errors_df: __errors__ DataFrame or None.
        joined_df: frame the active script ran against.

    Returns:
        Frame with columns matching out.columns. Empty if no failing rows.
    """
    if errors_df is None or errors_df.empty:
        return _empty_frame_for(out)

    col_names = [c.name for c in out.columns]

    if "rowIndex" in errors_df.columns and joined_df is not None and not joined_df.empty:
        row_indices = [
            int(i) for i in errors_df["rowIndex"].tolist()
            if isinstance(i, (int, float)) and 0 <= int(i) < len(joined_df)
        ]
        failing_rows = joined_df.iloc[row_indices].reset_index(drop=True)
    else:
        # No rowIndex column or no joined_df -- user-defined cols cannot
        # resolve; emit framework cols only against errors_df length.
        failing_rows = pd.DataFrame(index=range(len(errors_df)))

    n = len(failing_rows)

    # Evaluate user-defined columns from failing_rows. Simple ref resolution:
    # 'row1.col' -> failing_rows['col']; bare 'col' -> failing_rows['col'].
    # Complex expressions are out of scope for this MVP; default to None.
    user_data: dict[str, list] = {}
    for col in out.columns:
        if col.name in _RESERVED_COLS:
            continue
        expr = col.expression.replace("{{java}}", "").strip()
        if "." in expr and "(" not in expr and len(expr.split(".")) == 2:
            _, plain = expr.split(".", 1)
            if plain in failing_rows.columns:
                user_data[col.name] = failing_rows[plain].tolist()
                continue
        if expr in failing_rows.columns:
            user_data[col.name] = failing_rows[expr].tolist()
            continue
        user_data[col.name] = [None] * n

    # Reserved columns (framework value wins).
    msgs = (
        errors_df["errorMessage"].tolist()
        if "errorMessage" in errors_df.columns else []
    )
    traces = (
        errors_df["errorStackTrace"].tolist()
        if "errorStackTrace" in errors_df.columns else []
    )
    if "errorMessage" in col_names:
        user_data["errorMessage"] = (msgs + [""] * n)[:n] if n else []
    if "errorStackTrace" in col_names:
        user_data["errorStackTrace"] = (traces + [""] * n)[:n] if n else []

    if n == 0:
        return _empty_frame_for(out)

    return pd.DataFrame(user_data, columns=col_names)
