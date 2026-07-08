"""Deterministic validator: resolve exploder handles and derive a rung from the handle TYPE (never the LLM hint)."""
from __future__ import annotations


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
