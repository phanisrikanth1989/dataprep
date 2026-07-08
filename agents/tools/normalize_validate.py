"""Deterministic validator: resolve exploder handles, derive a rung from handle TYPE, and merge located handles into exact row-dicts."""
from __future__ import annotations

import csv
import io
import logging
import re

logger = logging.getLogger(__name__)


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


# ------------------------------------------------------------------
# Role/content-distinctness guard: a graded output must differ from every
# input (else a byte-passthrough oracle can't tell a transform from a no-op).
# ------------------------------------------------------------------
def _materialized_bytes(rows) -> bytes:
    """Serialize rows to the exact ';'-delimited CSV bytes materialize_golden would write (header = first row's keys)."""
    if not rows:
        return b""
    header = list(rows[0].keys())
    buf = io.StringIO(newline="")
    writer = csv.writer(buf, delimiter=";", quotechar='"', quoting=csv.QUOTE_MINIMAL, lineterminator="\n")
    writer.writerow(header)
    for row in rows:
        writer.writerow([row.get(col, "") for col in header])
    return buf.getvalue().encode("utf-8")


def _distinctness(sample_input, expected_output) -> set:
    """Return graded-output names to DEGRADE: content byte-identical to a sample source (passthrough) or shared across roles."""
    source_keys = {_materialized_bytes(rows) for rows in (sample_input or {}).values() if rows}
    output_keys: dict[bytes, list] = {}
    for name, rows in (expected_output or {}).items():
        if rows:  # only graded (>=1 row) outputs are gradable, so only they can be degraded
            output_keys.setdefault(_materialized_bytes(rows), []).append(name)
    degrade: set = set()
    for key, names in output_keys.items():
        if key in source_keys or len(names) > 1:  # before==after passthrough, or one handle in >1 role
            degrade.update(names)
    return degrade


# ------------------------------------------------------------------
# Name normalization: NL BRD label -> safe filename component, with
# deterministic collision disambiguation (never collapse two into one key).
# ------------------------------------------------------------------
_ILLEGAL_NAME_CHARS = re.compile(r"[^A-Za-z0-9._-]+")  # keep filename-safe chars; fold the rest to "_"


def _safe_output_name(name) -> str:
    """Sanitize a natural-language name into one safe filename component (fold illegal chars to '_', collapse, strip)."""
    folded = re.sub(r"_+", "_", _ILLEGAL_NAME_CHARS.sub("_", str(name))).strip("_")
    return folded if folded not in ("", ".", "..") else "_"  # neutralize empty and dot-traversal components


def _safe_output_names(names) -> dict:
    """Map each name to a UNIQUE safe filename component, disambiguating collisions with a deterministic '_N' suffix."""
    mapping: dict = {}
    used: set = set()
    for name in names:
        base = _safe_output_name(name)
        candidate, index = base, 2
        while candidate in used:
            candidate, index = f"{base}_{index}", index + 1
        used.add(candidate)
        mapping[name] = candidate
    return mapping


# ------------------------------------------------------------------
# output_keys verification (COMPOSITE tuple-uniqueness) + conformance synthesis.
# ------------------------------------------------------------------
def _verify_output_keys(name, keys, expected_rows) -> list:
    """Accept a COMPOSITE key only if its tuple is unique across every expected row; else fall back to [] (bag) + low_confidence."""
    keys = list(keys or [])
    rows = list(expected_rows or [])
    if keys and len({tuple(r.get(c) for c in keys) for r in rows}) == len(rows):
        return keys
    if keys:
        logger.warning(
            "[normalize_validate] output %s: composite key %s not unique across %d expected row(s); "
            "falling back to bag/multiset (low_confidence)", name, keys, len(rows))
    return []


def _conformance_ok() -> dict:
    """Synthesize a passing conformance report for a real BRD (no template blocks; completeness lives in extraction.status)."""
    return {"ok": True, "missing_blocks": [], "parse_errors": []}
