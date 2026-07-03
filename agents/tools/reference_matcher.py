"""Independent Phase-A exact-match reference matcher (the oracle-of-oracle).

Recomputes the recon match with pure pandas so the engine's output can be
cross-checked against a second, independent implementation.
"""
from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger(__name__)

_VALID_ON_MULTI = ("first", "all", "break")


def match_phase_a(main: pd.DataFrame, lookup: pd.DataFrame, keys: list, on_multi: str = "first") -> dict:
    """Compute Phase-A {matched, breaks, stats} independently of the engine.

    Args:
        main: left/driving rows.
        lookup: reference rows.
        keys: equality join key columns (present in both frames).
        on_multi: how to treat a main row matching >1 lookup row -- "first"
            (keep first), "all" (fan-out), or "break" (flag as multi_match break).

    Returns:
        {"matched": DataFrame, "breaks": DataFrame (with break_reason), "stats": {...}}.
    """
    if on_multi not in _VALID_ON_MULTI:
        raise ValueError(f"on_multi must be one of {_VALID_ON_MULTI}, got {on_multi!r}")
    main_cols = list(main.columns)
    lookup_extra = [c for c in lookup.columns if c not in keys]

    # count lookup matches per key tuple
    counts = lookup.groupby(keys, dropna=False).size().rename("_n").reset_index()
    m = main.merge(counts, on=keys, how="left")
    n = m["_n"].fillna(0).astype(int)

    no_match = m[n == 0]
    multi = m[n > 1]
    single = m[n == 1]

    break_frames = [no_match[main_cols].assign(break_reason="no_match")]
    matched_seed = single

    if on_multi == "break":
        break_frames.append(multi[main_cols].assign(break_reason="multi_match"))
        n_break_multi = len(multi)
    else:
        matched_seed = m[n >= 1] if on_multi == "all" else pd.concat([single, multi], ignore_index=True)
        n_break_multi = 0

    # join matched_seed to lookup for the carried lookup columns
    if on_multi == "all":
        matched = matched_seed[main_cols].merge(lookup, on=keys, how="inner")
    else:
        # first-match: one lookup row per key
        first_lookup = lookup.drop_duplicates(subset=keys, keep="first")
        matched = matched_seed[main_cols].merge(first_lookup, on=keys, how="inner")

    breaks = pd.concat(break_frames, ignore_index=True) if break_frames else pd.DataFrame(columns=main_cols + ["break_reason"])
    stats = {
        "n_matched": int(len(matched)),
        "n_break_no_match": int(len(no_match)),
        "n_break_multi": int(n_break_multi),
    }
    logger.debug("[reference_matcher] %s", stats)
    return {"matched": matched.reset_index(drop=True), "breaks": breaks.reset_index(drop=True), "stats": stats}
