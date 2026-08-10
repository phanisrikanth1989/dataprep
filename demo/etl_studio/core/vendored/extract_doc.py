"""Docx block-stream + derived-facts library (the extract_doc remnant).

Vendored from agents/tools/extract_doc.py (ticket 17; map invariant: never
import from agents/). Ticket 04 demoted extract_doc to LIBRARY code: the
studio's BRD door has no conformance/template route -- every .docx takes the
explode -> doc-normalizer -> normalize_validate chain -- so only the block
iteration, table flattening and derived-facts helpers survive here. The full
template parser stays behind in agents/ unused by the studio.
"""
from __future__ import annotations

from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import Table
from docx.text.paragraph import Paragraph


def _iter_block_items(doc):
    for child in doc.element.body.iterchildren():
        if isinstance(child, CT_P):
            yield Paragraph(child, doc)
        elif isinstance(child, CT_Tbl):
            yield Table(child, doc)


def _table_records(table):
    """Flatten a docx table into (header row, [row-dict, ...]) with cells stripped."""
    matrix = [[cell.text.strip() for cell in row.cells] for row in table.rows]
    if not matrix:
        return [], []
    header = matrix[0]
    return header, [dict(zip(header, r)) for r in matrix[1:]]


def compute_derived_facts(sample_input: dict[str, list[dict]]) -> dict[str, dict[str, dict]]:
    """Compute per-column structural facts from real sample rows.

    Returns source -> column -> ``{"n_distinct", "null_rate", "unique",
    "max_group_size"}``. An empty cell (``""``) counts as null; ``unique`` is
    True only when there are non-null values and no value repeats.
    """
    facts = {}
    for source, rows in sample_input.items():
        n = len(rows)
        columns = list(rows[0].keys()) if rows else []
        col_facts = {}
        for col in columns:
            values = [r.get(col, "") for r in rows]
            non_null = [v for v in values if v != ""]
            counts = {}
            for v in non_null:
                counts[v] = counts.get(v, 0) + 1
            max_group = max(counts.values()) if counts else 0
            col_facts[col] = {
                "n_distinct": len(counts),
                "null_rate": round((n - len(non_null)) / n, 4),  # n >= 1: the loop only runs for non-empty sources
                "unique": bool(non_null) and max_group <= 1,
                "max_group_size": max_group,
            }
        facts[source] = col_facts
    return facts
