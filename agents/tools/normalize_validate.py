"""Deterministic validator: resolve exploder handles, derive a rung from handle TYPE, and merge located handles into exact row-dicts."""
from __future__ import annotations

import csv
import re


class NeedsHuman(Exception):
    """Raised when a merge/reorder cannot be reconciled deterministically; the caller routes to needs_human."""


def _resolve(handle_id, inventory) -> dict | None:
    """Return the inventory handle dict whose id matches handle_id, or None when it is not a member."""
    for handle in inventory.get("handles", []):
        if handle.get("id") == handle_id:
            return handle
    return None


def _derive_rung(handle_id, inventory) -> str:
    """Grade a handle into "1"|"2"|"3a"|"needs_human" from its type alone; fail-closed catch-all is needs_human."""
    handle = _resolve(handle_id, inventory)
    if handle is None:
        return "needs_human"  # unresolved -> cannot grade
    htype = handle.get("type")
    ref = (handle.get("path") or handle.get("id") or "").lower()  # path when extracted, else id (both carry the ext)
    if htype in ("embed", "sibling"):
        if ref.endswith((".xlsx", ".xls")):
            return "needs_human"  # Phase 2 adds the xlsx reader
        if ref.endswith(".csv") and handle.get("csv_dialect") is not None:
            return "1"
    if htype == "table":
        return "2"
    if htype in ("image", "prose"):
        return "3a"
    return "needs_human"  # fail-closed default: null-dialect CSV, unrecognized handle -> never a silent grade


# ------------------------------------------------------------------
# Exact-byte readers: located handle -> list of raw-string row-dicts.
# ------------------------------------------------------------------
def _read_csv_handle(handle) -> list[dict]:
    """Read a rung-1 CSV at handle['path'] with the recorded dialect; first row = header, cells emitted as str."""
    dialect = handle.get("csv_dialect") or {}
    delimiter = dialect.get("delimiter") or ","
    quotechar = dialect.get("quotechar") or '"'
    with open(handle["path"], "r", encoding="utf-8", errors="replace", newline="") as fh:
        raw = list(csv.reader(fh, delimiter=delimiter, quotechar=quotechar))
    if not raw:
        return []
    header = [str(cell) for cell in raw[0]]
    rows: list[dict] = []
    for record in raw[1:]:
        rows.append({header[i]: (str(record[i]) if i < len(record) else "") for i in range(len(header))})
    return rows


def _read_table_handle(handle) -> list[dict]:
    """Read a rung-2 table handle: disambiguated 'columns' are keys, 'cells[1:]' are data rows (str)."""
    columns = [str(c) for c in (handle.get("columns") or [])]
    cells = handle.get("cells") or []
    rows: list[dict] = []
    for record in cells[1:]:  # cells[0] is the header row
        rows.append({columns[i]: (str(record[i]) if i < len(record) else "") for i in range(len(columns))})
    return rows


# ------------------------------------------------------------------
# Merge: pick the winning candidate by precedence, read its exact rows.
# ------------------------------------------------------------------
_RUNG_RANK = {"1": 0, "2": 1, "3a": 2}  # lower is better: CSV file > Word table > transcription


def _merge_source(name, candidates, proposal, inventory, side="sample_input"):
    """Pick the best-rung candidate (file>table>transcribed) and read its exact rows; return (rows, provenance)."""
    best = None  # (rank, rung, handle_id)
    for handle_id in candidates:
        rung = _derive_rung(handle_id, inventory)
        rank = _RUNG_RANK.get(rung)
        if rank is None:
            continue  # a needs_human candidate is unusable; skip it
        if best is None or rank < best[0]:
            best = (rank, rung, handle_id)
    if best is None:
        raise NeedsHuman(f"source {name!r}: no usable candidate handle (all needs_human): {candidates}")
    _rank, rung, handle_id = best
    if rung == "1":
        rows = _read_csv_handle(_resolve(handle_id, inventory))
    elif rung == "2":
        rows = _read_table_handle(_resolve(handle_id, inventory))
    else:  # "3a": the LLM transcribed the rows into the proposal (image/prose only)
        rows = list(proposal.get(side, {}).get(name, []))
    return rows, {"rung": rung, "handle": handle_id}


# ------------------------------------------------------------------
# Column-order reconciliation (the engine binds CSV columns POSITIONALLY).
# ------------------------------------------------------------------
def _normalize_col(name) -> str:
    """Fold a column name to a match key: lowercase, then drop all whitespace and punctuation."""
    return re.sub(r"[^a-z0-9]+", "", str(name).strip().lower())


def _reconcile_columns(src_cols, schema_cols) -> dict:
    """Map each schema col to a source col by exact, then normalized, then positional; raise NeedsHuman otherwise."""
    src_cols = list(src_cols)
    schema_cols = list(schema_cols)
    # (i) exact: identical name-set (order-independent), no duplicates, 1:1.
    if (len(src_cols) == len(schema_cols)
            and len(set(src_cols)) == len(src_cols)
            and set(src_cols) == set(schema_cols)):
        return {sc: sc for sc in schema_cols}
    # (ii) normalized: fold case/space/punct; require a clean 1:1 on both sides.
    src_norm = {_normalize_col(c): c for c in src_cols}
    sch_norm = [_normalize_col(c) for c in schema_cols]
    if (len(src_cols) == len(schema_cols)
            and len(src_norm) == len(src_cols)           # no source collisions
            and len(set(sch_norm)) == len(schema_cols)   # no schema collisions
            and set(src_norm.keys()) == set(sch_norm)):
        return {sc: src_norm[_normalize_col(sc)] for sc in schema_cols}
    # (iii) positional: counts match -> bind by position (matches the engine's positional binding).
    if len(src_cols) == len(schema_cols):
        return {schema_cols[i]: src_cols[i] for i in range(len(schema_cols))}
    # Unreconcilable name/count mismatch -> only the validator guards this; fail closed.
    raise NeedsHuman(
        f"cannot reconcile columns {src_cols} to schema order {schema_cols} "
        f"(count {len(src_cols)} != {len(schema_cols)})")


def _reorder_to_schema(rows, schema_cols) -> list[dict]:
    """Reorder each row-dict so its key order MATCHES schema_cols; reconcile exact/normalized/positional or raise NeedsHuman."""
    if not rows:
        return list(rows)  # empty stays empty; nothing to reorder
    mapping = _reconcile_columns(list(rows[0].keys()), schema_cols)
    return [{sc: row[mapping[sc]] for sc in schema_cols} for row in rows]


def _reconcile_expected(rows, output_cols):
    """Reorder expected rows to the proposed output name-space if it reconciles; else keep the header and flag low-confidence (Phase 1 never hard-fails the expected side)."""
    if not output_cols:
        return list(rows), (
            "expected-output name-space not reconciled: no proposed output columns supplied; kept expected header")
    try:
        return _reorder_to_schema(rows, output_cols), None
    except NeedsHuman as exc:
        return list(rows), f"expected-output name-space not reconciled ({exc}); kept expected header"
