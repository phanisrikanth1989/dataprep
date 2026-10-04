# Recon Doc Extraction (`extract_doc`) Implementation Plan

> **SUPERSEDED IN PART (2026-07-03) -- see `docs/superpowers/specs/2026-07-03-enrichment-scope-correction.md`.**
> This plan is historical. The rule `kind` enum in this plan body (`Kind is one of match, tolerance, filter, aggregate, derive`, and the `match`/`tolerance` rule fixtures) is the PRE-CORRECTION reconciliation set. The SHIPPED `extract_doc` and `agents/templates/recon_requirements_template.md` use the ENRICHMENT kinds instead: `join | schema_validate | filter | aggregate | sort | derive`. The doc-contract, block iteration, derived-facts, and conformance-gate machinery below remain accurate; only the rule-kind vocabulary was recast by the enrichment correction. Do not rewrite the body.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a deterministic tool that parses a recon requirements `.docx` into structured data (schema, rules, real sample/expected rows, output keys) and computes per-column structural facts — the front door of the Copilot ETL agent system.

**Architecture:** A single pure-Python module, `agents/tools/extract_doc.py`, that walks a `.docx` in document order (interleaved paragraphs + tables via python-docx), segments it into four required blocks by their Heading-1 titles, parses each block's table(s) into typed structures, computes derived structural facts from the real sample rows, and enforces a conformance gate that fails fast on a malformed doc. Real sample/expected rows are returned for LOCAL oracle use only; downstream LLM roles receive the *derived facts*, never the values.

**Tech Stack:** Python 3.12, `python-docx` (from the Citi internal artifact repo), `pytest`.

## Global Constraints

- **Python 3.12+.** (project floor)
- **Only hard external platform constraint: VS Code 1.106** — irrelevant to this pure-Python tool, but no assumption may depend on a newer VS Code.
- **ASCII-only in all logs and code** — no emojis/unicode (RHEL servers).
- **Dependencies only from the internal artifact repo** — this tool may use `python-docx`; add no other third-party dependency.
- **Real sample/expected rows are LOCAL-only** — `extract_doc` returns them for the deterministic oracle; they must never be placed in anything sent to a model. Downstream consumers receive `derived_facts` (structure), not values.
- **Fix-at-source** — no defensive fallbacks that paper over a malformed doc; a bad doc fails the conformance gate loudly.
- **95% per-module line coverage** on `agents/tools/extract_doc.py` (project coverage gate).
- Per-module logger `logger = logging.getLogger(__name__)`; log messages prefixed `[extract_doc]`.

---

## File Structure

- `agents/__init__.py` — namespace package marker (empty).
- `agents/tools/__init__.py` — namespace package marker (empty).
- `agents/tools/extract_doc.py` — the extractor: dataclasses, block iteration, per-block parsers, derived facts, conformance gate, and the `extract_doc()` entry point. One responsibility: `.docx` -> `ExtractResult`.
- `agents/templates/recon_requirements_template.md` — human-facing description of the required `.docx` structure (the four blocks + table formats).
- `tests/agents/__init__.py`, `tests/agents/tools/__init__.py` — test package markers (empty).
- `tests/agents/tools/test_extract_doc.py` — all tests; each builds its own `.docx` fixture inline with `python-docx`.

**Doc contract (the four required Heading-1 blocks, in the template):**
1. `Inputs and Schema` — one table, header `Source | Column | Type | Nullable | Key`.
2. `Transformation Rules` — one table, header `ID | Kind | Description`.
3. `Sample Input` — one Heading-2 per source (the source name), each followed by a table whose header row is that source's column names.
4. `Expected Output` — one Heading-2 per output (the output name), each followed by a table whose header row is the output's column names; **key columns are suffixed with `*`** (e.g. `txn_id*`).

---

### Task 1: Module scaffold, block iteration, and section reader

**Files:**
- Create: `agents/__init__.py` (empty), `agents/tools/__init__.py` (empty)
- Create: `agents/tools/extract_doc.py`
- Create: `tests/agents/__init__.py` (empty), `tests/agents/tools/__init__.py` (empty)
- Test: `tests/agents/tools/test_extract_doc.py`

**Interfaces:**
- Consumes: nothing (first task).
- Produces:
  - `ColumnSpec(name: str, type: str, nullable: bool = True, key: bool = False)` dataclass.
  - `ConformanceReport(ok: bool, missing_blocks: list[str], parse_errors: list[str])` dataclass.
  - `ConformanceError(Exception)` carrying `.report: ConformanceReport`.
  - `_read_sections(doc) -> dict[str, list[tuple[str | None, Table]]]` — maps each Heading-1 title to an ordered list of `(current_heading2_or_None, table)` pairs.

- [ ] **Step 1: Write the failing test**

```python
# tests/agents/tools/test_extract_doc.py
from docx import Document

from agents.tools.extract_doc import _read_sections


def test_read_sections_associates_tables_with_headings(tmp_path):
    doc = Document()
    doc.add_heading("Inputs and Schema", level=1)
    t1 = doc.add_table(rows=1, cols=1)
    t1.rows[0].cells[0].text = "schema-table"
    doc.add_heading("Sample Input", level=1)
    doc.add_heading("ledger", level=2)
    t2 = doc.add_table(rows=1, cols=1)
    t2.rows[0].cells[0].text = "ledger-table"
    path = tmp_path / "d.docx"
    doc.save(str(path))

    sections = _read_sections(Document(str(path)))

    assert set(sections.keys()) == {"Inputs and Schema", "Sample Input"}
    assert sections["Inputs and Schema"][0][0] is None
    assert sections["Inputs and Schema"][0][1].rows[0].cells[0].text == "schema-table"
    assert sections["Sample Input"][0][0] == "ledger"
    assert sections["Sample Input"][0][1].rows[0].cells[0].text == "ledger-table"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/agents/tools/test_extract_doc.py::test_read_sections_associates_tables_with_headings -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agents.tools.extract_doc'`

- [ ] **Step 3: Write minimal implementation**

Create the four empty `__init__.py` files, then:

```python
# agents/tools/extract_doc.py
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
    name: str
    type: str
    nullable: bool = True
    key: bool = False


@dataclass
class ConformanceReport:
    ok: bool
    missing_blocks: list = field(default_factory=list)
    parse_errors: list = field(default_factory=list)


class ConformanceError(Exception):
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/agents/tools/test_extract_doc.py::test_read_sections_associates_tables_with_headings -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add agents/__init__.py agents/tools/__init__.py agents/tools/extract_doc.py \
        tests/agents/__init__.py tests/agents/tools/__init__.py tests/agents/tools/test_extract_doc.py
git commit -m "feat(agents): extract_doc section reader over docx block items"
```

---

### Task 2: Schema table parser

**Files:**
- Modify: `agents/tools/extract_doc.py`
- Test: `tests/agents/tools/test_extract_doc.py`

**Interfaces:**
- Consumes: `ColumnSpec` (Task 1).
- Produces:
  - `_table_records(table) -> tuple[list[str], list[dict]]` — `(header, [row-dict, ...])`, cells stripped.
  - `_parse_schema_table(table) -> dict[str, list[ColumnSpec]]` — source name -> columns.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/agents/tools/test_extract_doc.py
from agents.tools.extract_doc import _parse_schema_table


def _table(doc, header, rows):
    t = doc.add_table(rows=1, cols=len(header))
    for i, h in enumerate(header):
        t.rows[0].cells[i].text = h
    for r in rows:
        cells = t.add_row().cells
        for i, v in enumerate(r):
            cells[i].text = v
    return t


def test_parse_schema_table_groups_by_source():
    doc = Document()
    t = _table(
        doc,
        ["Source", "Column", "Type", "Nullable", "Key"],
        [
            ["ledger", "txn_id", "str", "false", "true"],
            ["ledger", "amt", "float", "false", "false"],
            ["statement", "ref_id", "str", "false", "true"],
        ],
    )
    schema = _parse_schema_table(t)
    assert list(schema.keys()) == ["ledger", "statement"]
    assert schema["ledger"][0].name == "txn_id"
    assert schema["ledger"][0].type == "str"
    assert schema["ledger"][0].nullable is False
    assert schema["ledger"][0].key is True
    assert schema["ledger"][1].key is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/agents/tools/test_extract_doc.py::test_parse_schema_table_groups_by_source -v`
Expected: FAIL — `ImportError: cannot import name '_parse_schema_table'`

- [ ] **Step 3: Write minimal implementation**

```python
# add to agents/tools/extract_doc.py
_TRUE = ("true", "yes", "y", "1")


def _table_records(table):
    matrix = [[cell.text.strip() for cell in row.cells] for row in table.rows]
    if not matrix:
        return [], []
    header = matrix[0]
    return header, [dict(zip(header, r)) for r in matrix[1:]]


def _parse_schema_table(table):
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/agents/tools/test_extract_doc.py::test_parse_schema_table_groups_by_source -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add agents/tools/extract_doc.py tests/agents/tools/test_extract_doc.py
git commit -m "feat(agents): extract_doc schema table parser"
```

---

### Task 3: Rules table parser

**Files:**
- Modify: `agents/tools/extract_doc.py`
- Test: `tests/agents/tools/test_extract_doc.py`

**Interfaces:**
- Consumes: `_table_records` (Task 2).
- Produces: `_parse_rules_table(table) -> list[dict]` — each `{"id": str, "kind": str, "description": str}`; `kind` lowercased.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/agents/tools/test_extract_doc.py
from agents.tools.extract_doc import _parse_rules_table


def test_parse_rules_table():
    doc = Document()
    t = _table(
        doc,
        ["ID", "Kind", "Description"],
        [
            ["R1", "Match", "match ledger.txn_id to statement.ref_id"],
            ["R2", "Tolerance", "amounts equal within 0.01"],
            ["", "", ""],  # blank row ignored
        ],
    )
    rules = _parse_rules_table(t)
    assert len(rules) == 2
    assert rules[0] == {"id": "R1", "kind": "match", "description": "match ledger.txn_id to statement.ref_id"}
    assert rules[1]["kind"] == "tolerance"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/agents/tools/test_extract_doc.py::test_parse_rules_table -v`
Expected: FAIL — `ImportError: cannot import name '_parse_rules_table'`

- [ ] **Step 3: Write minimal implementation**

```python
# add to agents/tools/extract_doc.py
def _parse_rules_table(table):
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/agents/tools/test_extract_doc.py::test_parse_rules_table -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add agents/tools/extract_doc.py tests/agents/tools/test_extract_doc.py
git commit -m "feat(agents): extract_doc rules table parser"
```

---

### Task 4: Data-block parser (sample input + expected output with keys)

**Files:**
- Modify: `agents/tools/extract_doc.py`
- Test: `tests/agents/tools/test_extract_doc.py`

**Interfaces:**
- Consumes: `_read_sections` output shape (Task 1).
- Produces: `_parse_data_block(items, extract_keys: bool = False)` where `items` is a list of `(subheading, table)` pairs.
  - `extract_keys=False` -> `dict[str, list[dict]]` (name -> rows).
  - `extract_keys=True` -> `tuple[dict[str, list[dict]], dict[str, list[str]]]` (rows, and name -> key columns). Header cells ending in `*` are key columns; the `*` is stripped from the stored column name.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/agents/tools/test_extract_doc.py
from agents.tools.extract_doc import _parse_data_block


def _named_table(doc, header, rows):
    return _table(doc, header, rows)


def test_parse_data_block_sample_input():
    doc = Document()
    items = [
        ("ledger", _named_table(doc, ["txn_id", "amt"], [["T1", "100.00"], ["T2", "50.00"]])),
        ("statement", _named_table(doc, ["ref_id", "amt"], [["T1", "100.00"]])),
    ]
    data = _parse_data_block(items)
    assert data["ledger"] == [{"txn_id": "T1", "amt": "100.00"}, {"txn_id": "T2", "amt": "50.00"}]
    assert data["statement"] == [{"ref_id": "T1", "amt": "100.00"}]


def test_parse_data_block_expected_output_extracts_composite_key():
    doc = Document()
    items = [
        ("matched", _named_table(doc, ["txn_id*", "src*", "amt"], [["T1", "ledger", "100.00"]])),
    ]
    data, keys = _parse_data_block(items, extract_keys=True)
    assert keys["matched"] == ["txn_id", "src"]
    assert data["matched"] == [{"txn_id": "T1", "src": "ledger", "amt": "100.00"}]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/agents/tools/test_extract_doc.py -k parse_data_block -v`
Expected: FAIL — `ImportError: cannot import name '_parse_data_block'`

- [ ] **Step 3: Write minimal implementation**

```python
# add to agents/tools/extract_doc.py
def _parse_data_block(items, extract_keys=False):
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
            keys[name] = [h[:-1].strip() for h in raw_header if h.endswith("*")]
            header = [(h[:-1].strip() if h.endswith("*") else h.strip()) for h in raw_header]
        else:
            header = [h.strip() for h in raw_header]
        data[name] = [dict(zip(header, r)) for r in matrix[1:]]
    return (data, keys) if extract_keys else data
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/agents/tools/test_extract_doc.py -k parse_data_block -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add agents/tools/extract_doc.py tests/agents/tools/test_extract_doc.py
git commit -m "feat(agents): extract_doc data-block parser with composite key extraction"
```

---

### Task 5: Derived structural facts

**Files:**
- Modify: `agents/tools/extract_doc.py`
- Test: `tests/agents/tools/test_extract_doc.py`

**Interfaces:**
- Consumes: `sample_input: dict[str, list[dict]]` (Task 4 shape).
- Produces: `compute_derived_facts(sample_input) -> dict[str, dict[str, dict]]` — `source -> column -> {"n_distinct": int, "null_rate": float, "unique": bool, "max_group_size": int}`. An empty cell (`""`) counts as null. `unique` is True only when there are non-null values and no value repeats.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/agents/tools/test_extract_doc.py
from agents.tools.extract_doc import compute_derived_facts


def test_compute_derived_facts():
    sample = {
        "ledger": [
            {"txn_id": "T1", "amt": "100"},
            {"txn_id": "T2", "amt": ""},
            {"txn_id": "T2", "amt": "50"},
        ]
    }
    facts = compute_derived_facts(sample)["ledger"]
    assert facts["txn_id"]["unique"] is False          # T2 repeats
    assert facts["txn_id"]["max_group_size"] == 2
    assert facts["txn_id"]["n_distinct"] == 2
    assert facts["txn_id"]["null_rate"] == 0.0
    assert facts["amt"]["null_rate"] == round(1 / 3, 4)  # one empty cell
    assert facts["amt"]["unique"] is True                # 100, 50 distinct among non-null
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/agents/tools/test_extract_doc.py::test_compute_derived_facts -v`
Expected: FAIL — `ImportError: cannot import name 'compute_derived_facts'`

- [ ] **Step 3: Write minimal implementation**

```python
# add to agents/tools/extract_doc.py
def compute_derived_facts(sample_input):
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
                "null_rate": round((n - len(non_null)) / n, 4) if n else 0.0,
                "unique": bool(non_null) and max_group <= 1,
                "max_group_size": max_group,
            }
        facts[source] = col_facts
    return facts
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/agents/tools/test_extract_doc.py::test_compute_derived_facts -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add agents/tools/extract_doc.py tests/agents/tools/test_extract_doc.py
git commit -m "feat(agents): extract_doc derived structural facts from real rows"
```

---

### Task 6: Conformance gate

**Files:**
- Modify: `agents/tools/extract_doc.py`
- Test: `tests/agents/tools/test_extract_doc.py`

**Interfaces:**
- Consumes: `REQUIRED_BLOCKS`, `ConformanceReport` (Task 1), and the parsed structures from Tasks 2-4.
- Produces: `_check_conformance(sections, sources_schema, rules, sample_input, expected_output) -> ConformanceReport`. `ok` is True only when all four blocks are present AND each yielded content (schema columns, >=1 rule, >=1 sample row, >=1 expected row). A present-but-empty/image-only table shows up as a `parse_errors` entry.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/agents/tools/test_extract_doc.py
from agents.tools.extract_doc import _check_conformance


def test_conformance_ok():
    sections = {b: [] for b in ("Inputs and Schema", "Transformation Rules", "Sample Input", "Expected Output")}
    report = _check_conformance(
        sections,
        sources_schema={"ledger": ["x"]},
        rules=[{"id": "R1"}],
        sample_input={"ledger": [{"a": "1"}]},
        expected_output={"matched": [{"a": "1"}]},
    )
    assert report.ok is True


def test_conformance_missing_block():
    sections = {"Inputs and Schema": [], "Transformation Rules": [], "Sample Input": []}
    report = _check_conformance(sections, {"ledger": ["x"]}, [{"id": "R1"}], {"ledger": [{"a": "1"}]}, {})
    assert report.ok is False
    assert "Expected Output" in report.missing_blocks


def test_conformance_empty_table_is_parse_error():
    sections = {b: [] for b in ("Inputs and Schema", "Transformation Rules", "Sample Input", "Expected Output")}
    report = _check_conformance(sections, {"ledger": ["x"]}, [{"id": "R1"}], {"ledger": []}, {"matched": [{"a": "1"}]})
    assert report.ok is False
    assert any("Sample Input" in e for e in report.parse_errors)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/agents/tools/test_extract_doc.py -k conformance -v`
Expected: FAIL — `ImportError: cannot import name '_check_conformance'`

- [ ] **Step 3: Write minimal implementation**

```python
# add to agents/tools/extract_doc.py
def _check_conformance(sections, sources_schema, rules, sample_input, expected_output):
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/agents/tools/test_extract_doc.py -k conformance -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add agents/tools/extract_doc.py tests/agents/tools/test_extract_doc.py
git commit -m "feat(agents): extract_doc conformance gate"
```

---

### Task 7: `extract_doc` entry point + the requirements template

**Files:**
- Modify: `agents/tools/extract_doc.py`
- Create: `agents/templates/recon_requirements_template.md`
- Test: `tests/agents/tools/test_extract_doc.py`

**Interfaces:**
- Consumes: everything from Tasks 1-6.
- Produces:
  - `ExtractResult` dataclass with fields: `sources_schema: dict[str, list[ColumnSpec]]`, `rules: list[dict]`, `sample_input: dict[str, list[dict]]`, `expected_output: dict[str, list[dict]]`, `output_keys: dict[str, list[str]]`, `derived_facts: dict`, `conformance: ConformanceReport`.
  - `extract_doc(path: str, raise_on_error: bool = True) -> ExtractResult`. Raises `ConformanceError` when `raise_on_error` and the doc is non-conformant, or immediately if the file exceeds `MAX_DOCX_BYTES` (25 MB).

- [ ] **Step 1: Write the failing test**

```python
# append to tests/agents/tools/test_extract_doc.py
import pytest

from agents.tools.extract_doc import ConformanceError, extract_doc


def _build_recon_docx(path):
    doc = Document()
    doc.add_heading("Inputs and Schema", level=1)
    _table(doc, ["Source", "Column", "Type", "Nullable", "Key"], [
        ["ledger", "txn_id", "str", "false", "true"],
        ["ledger", "amt", "float", "false", "false"],
        ["statement", "ref_id", "str", "false", "true"],
        ["statement", "amt", "float", "false", "false"],
    ])
    doc.add_heading("Transformation Rules", level=1)
    _table(doc, ["ID", "Kind", "Description"], [
        ["R1", "match", "match ledger.txn_id to statement.ref_id"],
        ["R2", "tolerance", "amounts equal within 0.01"],
    ])
    doc.add_heading("Sample Input", level=1)
    doc.add_heading("ledger", level=2)
    _table(doc, ["txn_id", "amt"], [["T1", "100.00"], ["T2", "50.00"]])
    doc.add_heading("statement", level=2)
    _table(doc, ["ref_id", "amt"], [["T1", "100.00"]])
    doc.add_heading("Expected Output", level=1)
    doc.add_heading("matched", level=2)
    _table(doc, ["txn_id*", "amt"], [["T1", "100.00"]])
    doc.add_heading("breaks", level=2)
    _table(doc, ["txn_id*", "reason"], [["T2", "no_match"]])
    doc.save(str(path))


def test_extract_doc_end_to_end(tmp_path):
    path = tmp_path / "recon.docx"
    _build_recon_docx(path)

    result = extract_doc(str(path))

    assert result.conformance.ok is True
    assert set(result.sources_schema) == {"ledger", "statement"}
    assert result.rules[1]["kind"] == "tolerance"
    assert result.sample_input["ledger"][0] == {"txn_id": "T1", "amt": "100.00"}
    assert result.output_keys["matched"] == ["txn_id"]
    assert result.expected_output["breaks"][0] == {"txn_id": "T2", "reason": "no_match"}
    assert result.derived_facts["ledger"]["txn_id"]["unique"] is True


def test_extract_doc_raises_on_missing_block(tmp_path):
    doc = Document()
    doc.add_heading("Inputs and Schema", level=1)
    _table(doc, ["Source", "Column", "Type", "Nullable", "Key"], [["ledger", "txn_id", "str", "false", "true"]])
    path = tmp_path / "bad.docx"
    doc.save(str(path))

    with pytest.raises(ConformanceError) as exc:
        extract_doc(str(path))
    assert "Transformation Rules" in exc.value.report.missing_blocks
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/agents/tools/test_extract_doc.py -k extract_doc_end_to_end or extract_doc_raises -v`
Expected: FAIL — `ImportError: cannot import name 'extract_doc'`

- [ ] **Step 3: Write minimal implementation**

```python
# add to agents/tools/extract_doc.py (imports at top of file)
from pathlib import Path

from docx import Document

MAX_DOCX_BYTES = 25 * 1024 * 1024


@dataclass
class ExtractResult:
    sources_schema: dict
    rules: list
    sample_input: dict
    expected_output: dict
    output_keys: dict
    derived_facts: dict
    conformance: ConformanceReport


def extract_doc(path, raise_on_error=True):
    file_path = Path(path)
    size = file_path.stat().st_size
    if size > MAX_DOCX_BYTES:
        report = ConformanceReport(ok=False, parse_errors=[f"file too large: {size} bytes"])
        raise ConformanceError(report)

    doc = Document(str(file_path))
    sections = _read_sections(doc)

    sources_schema = {}
    if sections.get("Inputs and Schema"):
        sources_schema = _parse_schema_table(sections["Inputs and Schema"][0][1])
    rules = []
    if sections.get("Transformation Rules"):
        rules = _parse_rules_table(sections["Transformation Rules"][0][1])
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
```

Then create `agents/templates/recon_requirements_template.md`:

```markdown
# Recon Requirements Template

Author the requirements as a `.docx` with exactly these four Heading-1 blocks.
`extract_doc` parses them deterministically; keep them as real Word tables
(not screenshots).

## Inputs and Schema
One table. Header row: `Source | Column | Type | Nullable | Key`.
One row per column of each input source. Type is one of
`str, int, float, bool, date, datetime, decimal`.

## Transformation Rules
One table. Header row: `ID | Kind | Description`.
Kind is one of `match, tolerance, filter, aggregate, derive`.

## Sample Input
One Heading-2 per source (named exactly as in "Inputs and Schema").
Under each, one table whose header row is that source's column names, with a
handful of real rows (include a null, a break, and a tolerance edge).

## Expected Output
One Heading-2 per output (e.g. `matched`, `breaks`, `summary`).
Under each, one table whose header row is the output's columns; suffix each
composite-key column with `*` (e.g. `txn_id*`). Rows are the expected result
for the Sample Input above. These rows are the test oracle and stay local.
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/agents/tools/test_extract_doc.py -v`
Expected: PASS (all tests)

- [ ] **Step 5: Verify coverage, then commit**

Run: `python -m pytest tests/agents/tools/test_extract_doc.py --cov=agents/tools/extract_doc --cov-report=term-missing`
Expected: `agents/tools/extract_doc.py` at >= 95% line coverage. If below, add a test for the uncovered line (e.g. the file-too-large branch: monkeypatch `MAX_DOCX_BYTES` to a tiny value and assert `ConformanceError`) before committing.

```bash
git add agents/tools/extract_doc.py agents/templates/recon_requirements_template.md \
        tests/agents/tools/test_extract_doc.py
git commit -m "feat(agents): extract_doc entry point + recon requirements template"
```

---

## Self-Review

**1. Spec coverage (this plan's slice):** `extract_doc` deterministic extraction (design Sec 3, 8.1) — Tasks 1-7. Real sample/expected kept local (C2) — returned in `ExtractResult`, never sampled; template documents this. Derived structural facts from real rows (Sec 10.4) — Task 5. Conformance gate / fail-fast (Sec 8.1) — Task 6. Composite output keys (Sec 5.3) — Task 4. Hardened parsing (Sec 2.7) — partial: file-size cap in Task 7; deeper `defusedxml`/decompression-ratio hardening is a documented backlog item (backlog Section B) and out of this trusted-internal first slice. No spec requirement for this slice is left without a task.

**2. Placeholder scan:** No TBD/TODO; every code step contains complete code; every test step contains a full test; the coverage-gap remedy in Task 7 Step 5 names the concrete missing branch and how to test it.

**3. Type consistency:** `ColumnSpec`, `ConformanceReport`, `ConformanceError.report`, `_table_records`, `_parse_schema_table`, `_parse_rules_table`, `_parse_data_block(extract_keys=)`, `compute_derived_facts`, `_check_conformance`, `ExtractResult`, and `extract_doc(path, raise_on_error=)` names/signatures are identical everywhere they appear across tasks. The `_read_sections` shape `{h1: [(h2|None, Table)]}` is consumed consistently by Task 7.

---

## Next plans (not built here)
2. Curated knowledge extractor + config-key validator. 3. Test harness + multi-signal oracle + reference matcher. 4. MCP server + kickoff agent + sampling preflight. 5. Roles + deterministic feedback loop. Each will consume `ExtractResult` from this plan.
