"""Shared utilities for Talend-to-V2 component converters."""
from __future__ import annotations

from typing import Any, Dict, List


def _parse_table_rows(flat_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Group a flat TABLE param list into rows by detecting when the first elementRef repeats."""
    if not flat_list:
        return []

    first_ref = flat_list[0].get("elementRef")
    if not first_ref:
        return []

    rows: List[Dict[str, Any]] = []
    current: Dict[str, Any] = {}

    for entry in flat_list:
        ref = entry.get("elementRef")
        if not ref:
            continue
        if ref == first_ref and current:
            rows.append(current)
            current = {}
        current[ref] = entry.get("value", "")

    if current:
        rows.append(current)

    return rows
