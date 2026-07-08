"""Exploder: inventory the FULL docx block stream into stable handles (no extraction)."""
from __future__ import annotations

import logging

from agents.tools.extract_doc import _iter_block_items, _table_records
from docx.table import Table

logger = logging.getLogger(__name__)


def _dedup_headers(header: list[str]) -> list[str]:
    """Disambiguate a header row so no column is silently dropped (blank -> col_<i>; dup -> _<n>)."""
    seen, out = {}, []
    for i, h in enumerate(header):
        name = h.strip() or f"col_{i}"
        if name in seen:
            seen[name] += 1
            name = f"{name}_{seen[name]}"
        else:
            seen[name] = 1
        out.append(name)
    return out


def _inventory_blocks(doc) -> list[dict]:
    """Walk the full block stream into ordered handles: one table:N per table, grouped para:N prose ranges."""
    blocks: list[dict] = []
    table_idx = 0
    para_idx = 0
    pending = None  # {"start": int, "end": int, "texts": list[str]} for the current prose run

    def _flush_pending() -> None:
        """Emit the accumulated consecutive-paragraph run as one para:N block-range handle."""
        nonlocal pending, para_idx
        if pending is None:
            return
        blocks.append(
            {
                "handle": f"para:{para_idx}",
                "kind": "para",
                "block_start": pending["start"],
                "block_end": pending["end"],
                "text": "\n".join(pending["texts"]),
            }
        )
        para_idx += 1
        pending = None

    for i, block in enumerate(_iter_block_items(doc)):
        if isinstance(block, Table):
            _flush_pending()
            # Reuse _table_records for header + data-row count; store the EXACT cell
            # matrix ourselves (dict(zip(header, r)) would collapse duplicate columns).
            header, records = _table_records(block)
            matrix = [[cell.text.strip() for cell in row.cells] for row in block.rows]
            blocks.append(
                {
                    "handle": f"table:{table_idx}",
                    "kind": "table",
                    "block_start": i,
                    "block_end": i,
                    "columns": _dedup_headers(header),
                    "n_rows": len(records),
                    "cells": matrix,
                }
            )
            table_idx += 1
        else:  # Paragraph
            if pending is None:
                pending = {"start": i, "end": i, "texts": []}
            pending["end"] = i
            text = block.text.strip()
            if text:
                pending["texts"].append(text)
    _flush_pending()

    logger.debug(
        "[explode_doc] inventoried %d handles: %d tables, %d prose groups",
        len(blocks), table_idx, para_idx,
    )
    return blocks
