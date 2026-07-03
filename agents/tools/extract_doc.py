"""Deterministic extraction of a recon requirements .docx into structured data.

Real sample/expected rows are returned for LOCAL oracle use only and must never
be sent to a model. Derived structural facts (Task 5) are what downstream LLM
roles receive.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import Table
from docx.text.paragraph import Paragraph

logger = logging.getLogger(__name__)

REQUIRED_BLOCKS = ("Inputs and Schema", "Transformation Rules", "Sample Input", "Expected Output")


@dataclass
class ColumnSpec:
    """A parsed schema column (name/type/nullable/key)."""
    name: str
    type: str
    nullable: bool = True
    key: bool = False


@dataclass
class ConformanceReport:
    """The result of the requirements-doc conformance check."""
    ok: bool
    missing_blocks: list = field(default_factory=list)
    parse_errors: list = field(default_factory=list)


class ConformanceError(Exception):
    """Raised when the doc fails the conformance gate; carries `.report`."""
    def __init__(self, report: ConformanceReport):
        self.report = report
        super().__init__(
            f"[extract_doc] conformance failed: missing={report.missing_blocks} "
            f"errors={report.parse_errors}"
        )


def _iter_block_items(doc):
    for child in doc.element.body.iterchildren():
        if isinstance(child, CT_P):
            yield Paragraph(child, doc)
        elif isinstance(child, CT_Tbl):
            yield Table(child, doc)


def _heading_level(paragraph):
    style = paragraph.style
    name = (style.name or "") if style is not None else ""
    if name.startswith("Heading "):
        try:
            return int(name.split(" ", 1)[1])
        except ValueError:
            return None
    return None


def _read_sections(doc):
    sections = {}
    current_h1 = None
    current_h2 = None
    for block in _iter_block_items(doc):
        if isinstance(block, Paragraph):
            level = _heading_level(block)
            if level == 1:
                current_h1 = block.text.strip()
                current_h2 = None
                sections.setdefault(current_h1, [])
            elif level == 2:
                current_h2 = block.text.strip()
        elif isinstance(block, Table) and current_h1 is not None:
            sections[current_h1].append((current_h2, block))
    return sections


_TRUE = ("true", "yes", "y", "1")


def _table_records(table):
    """Flatten a docx table into (header row, [row-dict, ...]) with cells stripped."""
    matrix = [[cell.text.strip() for cell in row.cells] for row in table.rows]
    if not matrix:
        return [], []
    header = matrix[0]
    return header, [dict(zip(header, r)) for r in matrix[1:]]


def _parse_schema_table(table):
    """Parse an Inputs-and-Schema table into source name -> list of ColumnSpec."""
    _, records = _table_records(table)
    out = {}
    for rec in records:
        source = rec.get("Source", "").strip()
        column = rec.get("Column", "").strip()
        if not source or not column:
            continue
        out.setdefault(source, []).append(
            ColumnSpec(
                name=column,
                type=(rec.get("Type", "").strip() or "str"),
                nullable=(rec.get("Nullable", "true").strip().lower() in _TRUE),
                key=(rec.get("Key", "").strip().lower() in _TRUE),
            )
        )
    return out


def _parse_rules_table(table):
    """Parse a Transformation-Rules table into a list of {id, kind, description} dicts."""
    _, records = _table_records(table)
    rules = []
    for rec in records:
        rid = rec.get("ID", "").strip()
        if not rid:
            continue
        rules.append(
            {
                "id": rid,
                "kind": rec.get("Kind", "").strip().lower(),
                "description": rec.get("Description", "").strip(),
            }
        )
    return rules
