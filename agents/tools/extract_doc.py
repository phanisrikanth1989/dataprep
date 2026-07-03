"""Deterministic extraction of a recon requirements .docx into structured data.

Real sample/expected rows are returned for LOCAL oracle use only and must never
be sent to a model. Derived structural facts (Task 5) are what downstream LLM
roles receive.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from docx import Document
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import Table
from docx.text.paragraph import Paragraph

logger = logging.getLogger(__name__)

REQUIRED_BLOCKS = ("Inputs and Schema", "Transformation Rules", "Sample Input", "Expected Output")

MAX_DOCX_BYTES = 25 * 1024 * 1024


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


def _parse_data_block(items, extract_keys=False):
    """Parse (subheading, table) pairs into name -> rows; optionally extract `*`-marked key columns.

    Rows for a repeated name accumulate across tables (no silent overwrite). When
    ``extract_keys`` is True, the FIRST occurrence's key columns are kept even as
    later tables of the same name extend the row list.
    """
    data = {}
    keys = {}
    for subheading, table in items:
        name = (subheading or "").strip()
        if not name:
            continue
        matrix = [[cell.text.strip() for cell in row.cells] for row in table.rows]
        if not matrix:
            continue
        raw_header = matrix[0]
        if extract_keys:
            key_cols = [h[:-1].strip() for h in raw_header if h.endswith("*")]
            if name not in keys:
                keys[name] = key_cols
            header = [(h[:-1].strip() if h.endswith("*") else h.strip()) for h in raw_header]
        else:
            header = [h.strip() for h in raw_header]
        data.setdefault(name, []).extend(dict(zip(header, r)) for r in matrix[1:])
    return (data, keys) if extract_keys else data


def compute_derived_facts(sample_input: dict[str, list[dict]]) -> dict[str, dict[str, dict]]:
    """Compute per-column structural facts from real sample rows.

    These facts (not raw values) are what downstream LLM roles receive, so no
    sample cell content leaks into the returned structure.

    Args:
        sample_input: Mapping of source name -> list of row dicts (Task 4 shape).

    Returns:
        Mapping of source -> column -> ``{"n_distinct", "null_rate", "unique",
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


def _check_conformance(sections, sources_schema, rules, sample_input, expected_output):
    """Gate the parsed doc: ok only if all four blocks are present and non-empty.

    A required block that is absent lands in ``missing_blocks``; a present block
    whose table yielded no content (empty or image-only) lands in
    ``parse_errors``. ``ok`` is True only when neither list has entries.
    """
    missing = [b for b in REQUIRED_BLOCKS if b not in sections]
    errors = []
    if not missing:
        if not sources_schema:
            errors.append("Inputs and Schema: no columns parsed (empty or image-only table?)")
        if not rules:
            errors.append("Transformation Rules: no rules parsed")
        if not sample_input or all(len(rows) == 0 for rows in sample_input.values()):
            errors.append("Sample Input: no rows parsed")
        if not expected_output or all(len(rows) == 0 for rows in expected_output.values()):
            errors.append("Expected Output: no rows parsed")
    return ConformanceReport(ok=(not missing and not errors), missing_blocks=missing, parse_errors=errors)


@dataclass
class ExtractResult:
    """Structured result of parsing a recon requirements ``.docx``.

    ``sample_input`` and ``expected_output`` carry real cell values and are for
    LOCAL oracle use only -- never send them to a model. Downstream LLM roles
    receive ``derived_facts`` (structural facts) instead.

    All ``sample_input`` / ``expected_output`` cell values are raw STRINGS (the
    literal table text); output columns carry no declared type. Consumers must
    normalize types (e.g. parse numbers/dates) before comparing values.

    An empty ``output_keys[name]`` is a VALID state, not an error: it means the
    output declares no composite key, so the downstream oracle compares that
    output as a bag/multiset (order-independent, duplicates significant). A
    genuinely forgotten key is caught by human review, not by the conformance
    gate.

    Attributes:
        sources_schema: Source name -> list of ``ColumnSpec`` (Inputs and Schema).
        rules: List of ``{id, kind, description}`` dicts (Transformation Rules).
        sample_input: Source name -> list of real row dicts (Sample Input); all
            cell values are raw strings.
        expected_output: Output name -> list of real row dicts (Expected Output);
            all cell values are raw strings.
        output_keys: Output name -> list of composite-key column names (the
            ``*``-suffixed columns). An empty list means "no declared key ->
            bag/multiset comparison" and is valid.
        derived_facts: Source -> column -> structural facts; the only
            sample-derived data safe to send to a model.
        conformance: The ``ConformanceReport`` for the parsed doc.
    """
    sources_schema: dict[str, list[ColumnSpec]]
    rules: list[dict]
    sample_input: dict[str, list[dict]]
    expected_output: dict[str, list[dict]]
    output_keys: dict[str, list[str]]
    derived_facts: dict[str, dict[str, dict]]
    conformance: ConformanceReport


def extract_doc(path: str, raise_on_error: bool = True) -> ExtractResult:
    """Deterministically extract a recon requirements ``.docx`` into an ``ExtractResult``.

    Reads the four required Heading-1 blocks, parses each with its table parser,
    gates the result through the conformance check, and computes derived
    structural facts from the real sample rows. Schema and rules split across
    multiple tables under their heading are merged/concatenated in document order.

    Args:
        path: Filesystem path to the requirements ``.docx``.
        raise_on_error: When True (default), raise ``ConformanceError`` if the
            doc fails the conformance gate or cannot be opened/parsed. When
            False, return the ``ExtractResult`` with a non-ok ``conformance``
            report instead.

    Returns:
        An ``ExtractResult`` with the parsed schema, rules, sample input,
        expected output, composite output keys, derived facts, and the
        conformance report.

    Raises:
        ConformanceError: If the file exceeds ``MAX_DOCX_BYTES``; if the file is
            missing or is not a readable ``.docx`` and ``raise_on_error`` is
            True; or if ``raise_on_error`` is True and the doc is non-conformant.
            When ``raise_on_error`` is False, a missing/unreadable file yields an
            ``ExtractResult`` with empty structures and a non-ok ``conformance``
            instead of raising. This is the only exception type raised.
    """
    file_path = Path(path)

    # Size guard first, outside the parse try: its ConformanceError is
    # authoritative and must never be rewrapped as a parse error. A missing file
    # is left to the presence check inside the try below.
    if file_path.exists():
        size = file_path.stat().st_size
        if size > MAX_DOCX_BYTES:
            report = ConformanceReport(ok=False, parse_errors=[f"file too large: {size} bytes"])
            raise ConformanceError(report)

    try:
        file_path.stat()  # presence check: raises FileNotFoundError for a missing path
        doc = Document(str(file_path))
        sections = _read_sections(doc)
    except Exception as exc:  # FileNotFoundError / PackageNotFoundError / BadZipFile / XMLSyntaxError / ...
        report = ConformanceReport(ok=False, parse_errors=[f"could not open or parse docx: {exc}"])
        if raise_on_error:
            raise ConformanceError(report)
        return ExtractResult(
            sources_schema={},
            rules=[],
            sample_input={},
            expected_output={},
            output_keys={},
            derived_facts={},
            conformance=report,
        )

    sources_schema: dict[str, list[ColumnSpec]] = {}
    for _subheading, table in sections.get("Inputs and Schema", []):
        for source, cols in _parse_schema_table(table).items():
            sources_schema.setdefault(source, []).extend(cols)
    rules: list[dict] = []
    for _subheading, table in sections.get("Transformation Rules", []):
        rules.extend(_parse_rules_table(table))
    sample_input = _parse_data_block(sections.get("Sample Input", []))
    expected_output, output_keys = _parse_data_block(sections.get("Expected Output", []), extract_keys=True)

    conformance = _check_conformance(sections, sources_schema, rules, sample_input, expected_output)
    if raise_on_error and not conformance.ok:
        raise ConformanceError(conformance)

    derived_facts = compute_derived_facts(sample_input)
    logger.info(
        "[extract_doc] %s: %d sources, %d rules, %d outputs",
        file_path.name, len(sources_schema), len(rules), len(expected_output),
    )
    return ExtractResult(
        sources_schema=sources_schema,
        rules=rules,
        sample_input=sample_input,
        expected_output=expected_output,
        output_keys=output_keys,
        derived_facts=derived_facts,
        conformance=conformance,
    )
