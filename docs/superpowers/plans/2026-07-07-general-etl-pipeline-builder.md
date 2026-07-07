# General ETL Pipeline Builder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** De-bias the DataPrep Copilot agent system from "recon/enrichment" to general ETL, make doc extraction lossless (notes/extra-sections/tier, no LLM ever rewriting data), and close the input/output materialization gap with a deterministic `materialize_golden` tool plus a tier-aware run/grade path.

**Architecture:** Two deterministic Python tools bracket the LLM chain. `extract_doc` v2 parses a requirements `.docx` losslessly (schema, rules, sample, expected, prose notes, unrecognized sections, and a computed tier) without letting any model touch the exact data. `materialize_golden` turns that extract into real input CSVs (at the work-dir root) and a golden answer key (`<out>_expected.csv` + `manifest.json` under `golden/`). `run_and_validate` runs the assembled `job.json` in-process, and either diffs graded outputs (`verified` tier) or emits a distinct smoke verdict (`smoke` tier). Seven `.agent.md` specialists (body-only reframe, model-agnostic frontmatter frozen) and a renamed `dataprep-etl` skill carry the neutral framing and two load-bearing naming contracts (FileInput `filepath == <source-name>.csv`; terminal FileOutput `id == output name`).

**Tech Stack:** Python 3.12+, stdlib (`csv`, `json`, `argparse`, `dataclasses`, `pathlib`), `python-docx`, `pandas`, `pytest` (with `@pytest.mark.java` for live-bridge e2e). No new third-party dependency.

## Global Constraints

- Python 3.12+; ASCII-only in all code, logs, and authored markdown (RHEL-clean) - no emojis/unicode.
- No NEW third-party dependency: stdlib + `pandas`/`pyarrow`/`py4j`/`PyYAML`/`python-docx` already present.
- Model-agnostic: NO `model:` key in any `.agent.md` (`validate_agents` enforces); agent frontmatter stays byte-identical - reframe is body-only.
- Canonical tier tokens `verified | smoke | build` used verbatim everywhere (no synonyms).
- Determinism boundary: `extract_doc` + `materialize_golden` (and the exact data they emit) are deterministic; the LLM never authors or rewrites the oracle or the input data.
- Security-file carve-out (HARD): on `surface_code_cells.py` and `run_and_validate.py`, de-bias touches user-facing STRINGS ONLY - the jail/egress/nested-job/code-surfacing LOGIC and its existing tests are FROZEN (byte-unchanged except strings). The `run_and_validate.main()` grade-path rewrite (spec 4.3) is a SEPARATE, intended logic change - it is NOT the frozen jail/egress/nested/surfacing logic and is kept distinct from the string-scrub.
- Tests live under `tests/agents/`; `@pytest.mark.java` marks anything touching the live Java bridge (golden e2e).
- Manifest shape is `{"outputs": {<name>: {"keys": [...], "sep": ";", "graded": bool}}}` - NO `component` key.
- Skill folder + frontmatter `name` are `dataprep-etl` (must match, `validate_agents` enforces). No `dataprep-recon` string may remain in `.github/` or `agents/`.
- Coverage gate (`pyproject.toml`, 95% per-module) scopes `src/v1/engine` + `src/converters` only; `agents/tools/*` is out of that gate, but every new tool function still ships with tests.

---

## File Structure

**Tools (create/modify)**
- `agents/tools/extract_doc.py` (MODIFY) - v2 lossless: `notes`/`extra_sections`/`tier` fields, prose capture, data-blind extra-sections, `REQUIRED_BLOCKS` -> 2, presence-gated conformance.
- `agents/tools/materialize_golden.py` (CREATE) - deterministic input-CSV + golden answer-key writer; CLI emits tier.
- `agents/tools/run_and_validate.py` (MODIFY) - grade-path rewrite (graded-driven output_map, id==name), `--smoke` mode + distinct verdict, string-only de-bias of the two frozen messages.
- `agents/tools/render_skills.py` (MODIFY) - `dataprep-etl` frontmatter/body/prose, neutral `_JOB_ENVELOPE_EXAMPLE_JSON` with FileOutput `id == output name` + `csv_option: true` on delimited I/O.
- `agents/tools/validate_agents.py` (UNCHANGED logic; referenced by the no-recon-string test only).

**Knowledge / docs / templates / examples (modify/rename)**
- `agents/knowledge/landmines.py` (MODIFY) - docstring framing scrub (landmine engine-facts unchanged).
- `agents/schemas/config-surfaces.md` (MODIFY) - heading framing scrub.
- `agents/PLATFORM.md` (MODIFY) - operational rewrite: How-to-run (docx + job name), pipeline diagram (step-0 + tiers), tool table (+ `materialize_golden`, tiers).
- `agents/templates/recon_requirements_template.md` -> `agents/templates/etl_requirements_template.md` (RENAME + content: 2 required blocks + optional `Notes / Special Handling` + tiers).
- `agents/examples/sample_enrichment_requirements.docx` -> `agents/examples/sample_etl_requirements.docx` (RENAME via regeneration).
- `agents/examples/gen_sample_etl_requirements.py` (CREATE) - deterministic python-docx generator for the example.
- `agents/examples/README.md` (MODIFY) - neutral content + new template/docx names.

**Agent files (body-only; frontmatter byte-identical)**
- `.github/agents/{etl-orchestrator,doc-interpreter,flow-designer,configurator,assembler,test-runner,diagnostician}.agent.md` (MODIFY bodies).

**Skill (rename)**
- `.github/skills/dataprep-recon/` -> `.github/skills/dataprep-etl/` (regenerated by `render_skills`).

**Fixtures (migrate content)**
- `tests/fixtures/recon/golden_enrichment/job.json` (MODIFY) - terminal FileOutput `id` `out_enriched` -> `enriched` (+ its inbound flow `to`).
- `tests/fixtures/recon/golden_enrichment/manifest.json` (MODIFY) - drop `component`, add `graded: true`.

**Tests (create/modify)**
- `tests/agents/tools/test_extract_doc.py` (MODIFY) - update 2 v1-conformance tests; add v2 conformance tests.
- `tests/agents/tools/test_extract_doc_v2.py` (CREATE) - notes/extra_sections/tier.
- `tests/agents/tools/test_materialize_golden.py` (CREATE).
- `tests/agents/tools/test_oracle.py` (MODIFY) - `_write_cli_case` to new contract; add grade-path tests.
- `tests/agents/tools/test_golden_enrichment_e2e.py` (MODIFY) - `_output_map_and_keys` + output id.
- `tests/agents/tools/test_smoke_mode.py` (CREATE).
- `tests/agents/tools/test_render_skills.py` (MODIFY) - `dataprep-etl` dir + envelope id.
- `tests/agents/tools/test_no_recon_string.py` (CREATE).
- `tests/agents/tools/test_agent_contracts.py` (CREATE) - the body-contract doc assertions for phases 5.
- `tests/agents/tools/test_platform_doc.py` (MODIFY) - materialize_golden + tiers.
- `tests/agents/tools/test_etl_template.py` (CREATE).
- `tests/agents/tools/test_validate_agents.py` (MODIFY) - synthetic `dataprep-recon` strings -> `dataprep-etl`.

---

## PHASE 1 - extract_doc v2 (lossless)

### Task 1: Presence-gated conformance + `REQUIRED_BLOCKS` -> 2

**Files:**
- Modify: `agents/tools/extract_doc.py:21` (`REQUIRED_BLOCKS`), `:204-222` (`_check_conformance`)
- Test: `tests/agents/tools/test_extract_doc.py` (update 2 tests, add 3)

**Interfaces:**
- Consumes: nothing new.
- Produces: `REQUIRED_BLOCKS = ("Inputs and Schema", "Transformation Rules")`; `_check_conformance(sections, sources_schema, rules, sample_input, expected_output) -> ConformanceReport` (same signature, new rule: a PRESENT Sample/Expected H1 that yielded no parseable table -> `parse_errors`; an ABSENT one -> no error; the required 2 blocks still gate `missing_blocks`/emptiness).

- [ ] **Step 1: Write the failing tests**

In `tests/agents/tools/test_extract_doc.py`, REPLACE `test_conformance_missing_block` and `test_conformance_empty_table_is_parse_error` with the v2 behavior, and add three new tests:

```python
def test_conformance_missing_block():
    # Only Inputs+Rules are required now; a missing OPTIONAL block is not "missing".
    sections = {"Inputs and Schema": [], "Transformation Rules": []}
    report = _check_conformance(sections, {"ledger": ["x"]}, [{"id": "R1"}], {}, {})
    assert report.ok is True
    assert report.missing_blocks == []


def test_conformance_missing_required_rules_block():
    sections = {"Inputs and Schema": []}  # Transformation Rules absent (required)
    report = _check_conformance(sections, {"ledger": ["x"]}, [], {}, {})
    assert report.ok is False
    assert "Transformation Rules" in report.missing_blocks


def test_conformance_absent_sample_is_not_error():
    # Sample Input H1 absent -> only lowers the tier, never a conformance error.
    sections = {"Inputs and Schema": [], "Transformation Rules": []}
    report = _check_conformance(sections, {"ledger": ["x"]}, [{"id": "R1"}], {}, {})
    assert report.ok is True and report.parse_errors == []


def test_conformance_present_but_unparseable_sample_is_error():
    # Sample Input H1 present but nothing parsed (image-only / orphan table) -> hard-stop.
    sections = {"Inputs and Schema": [], "Transformation Rules": [], "Sample Input": []}
    report = _check_conformance(sections, {"ledger": ["x"]}, [{"id": "R1"}], {}, {})
    assert report.ok is False
    assert any("Sample Input" in e for e in report.parse_errors)


def test_conformance_declared_empty_expected_is_valid():
    # Expected present, one output with a header but zero data rows -> declared-empty (valid).
    sections = {"Inputs and Schema": [], "Transformation Rules": [], "Expected Output": []}
    report = _check_conformance(sections, {"ledger": ["x"]}, [{"id": "R1"}],
                                {}, {"matched": []})
    assert report.ok is True and report.parse_errors == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/agents/tools/test_extract_doc.py -k conformance -v`
Expected: FAIL - `test_conformance_missing_block` still asserts the old missing-block behavior against the current 4-tuple `REQUIRED_BLOCKS`, and the new presence-gated tests fail (present-but-unparseable Sample is not yet an error; absent Sample still errors under the old empty-rows check).

- [ ] **Step 3: Minimal implementation**

In `agents/tools/extract_doc.py`, change line 21:

```python
REQUIRED_BLOCKS = ("Inputs and Schema", "Transformation Rules")
```

Replace `_check_conformance` (lines 204-222) with:

```python
def _check_conformance(sections, sources_schema, rules, sample_input, expected_output):
    """Gate the parsed doc: the two REQUIRED blocks must be present and non-empty;
    a PRESENT-but-unparseable optional Sample/Expected block is a hard-stop.

    An absent Sample/Expected H1 is NOT an error -- it only lowers the tier
    (see _compute_tier). A present Sample/Expected H1 that yielded no parseable
    (header+rows) table lands in ``parse_errors`` (keeps the malformed-table
    detector alive). A declared-empty output (header row, zero data rows) parses
    to ``{name: []}`` -- a non-empty dict -- so it is VALID, not a hard-stop.
    """
    missing = [b for b in REQUIRED_BLOCKS if b not in sections]
    errors = []
    if not missing:
        if not sources_schema:
            errors.append("Inputs and Schema: no columns parsed (empty or image-only table?)")
        if not rules:
            errors.append("Transformation Rules: no rules parsed")
        if "Sample Input" in sections and not sample_input:
            errors.append("Sample Input: present but no parseable table (header+rows)")
        if "Expected Output" in sections and not expected_output:
            errors.append("Expected Output: present but no parseable table (header+rows)")
    return ConformanceReport(ok=(not missing and not errors), missing_blocks=missing, parse_errors=errors)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/agents/tools/test_extract_doc.py -v`
Expected: PASS (all conformance tests, plus the unchanged `test_extract_doc_raises_with_parse_errors_on_degenerate_blocks`, `test_extract_doc_end_to_end`, `test_extract_doc_raises_on_missing_block`).

- [ ] **Step 5: Commit**

```bash
git add agents/tools/extract_doc.py tests/agents/tools/test_extract_doc.py
git commit -m "feat(extract_doc): presence-gated conformance, 2 required blocks

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01CFnbyyDzMRERGWf9XeVSqq"
```

---

### Task 2: `ExtractResult` new defaulted fields + prose capture + `notes`

**Files:**
- Modify: `agents/tools/extract_doc.py` (`ExtractResult`, add `_read_section_prose`, populate `notes` in `extract_doc`)
- Test: `tests/agents/tools/test_extract_doc_v2.py` (CREATE)

**Interfaces:**
- Consumes: `_iter_block_items`, `_heading_level` (existing).
- Produces: `ExtractResult` gains `notes: str = ""`, `extra_sections: dict = field(default_factory=dict)`, `tier: str = "build"` (all defaulted, so `to_dict`/CLI/test-fakes keep working); `NOTES_BLOCK = "Notes / Special Handling"`; `_read_section_prose(doc) -> dict[str, str]` (H1 heading text -> "\n"-joined non-heading paragraph text under it).

- [ ] **Step 1: Write the failing test**

Create `tests/agents/tools/test_extract_doc_v2.py`:

```python
from docx import Document

from agents.tools.extract_doc import (
    ExtractResult, _read_section_prose, extract_doc, to_dict,
)


def _table(doc, header, rows):
    t = doc.add_table(rows=1, cols=len(header))
    for i, h in enumerate(header):
        t.rows[0].cells[i].text = h
    for r in rows:
        cells = t.add_row().cells
        for i, v in enumerate(r):
            cells[i].text = v
    return t


def test_extract_result_new_fields_default():
    r = ExtractResult(
        sources_schema={}, rules=[], sample_input={}, expected_output={},
        output_keys={}, derived_facts={}, conformance=None,
    )
    assert r.notes == "" and r.extra_sections == {} and r.tier == "build"
    d = to_dict(r)
    assert d["notes"] == "" and d["extra_sections"] == {} and d["tier"] == "build"


def test_read_section_prose_collects_paragraphs(tmp_path):
    doc = Document()
    doc.add_heading("Notes / Special Handling", level=1)
    doc.add_paragraph("Trim whitespace on all keys.")
    doc.add_paragraph("Amounts are in minor units.")
    path = tmp_path / "n.docx"
    doc.save(str(path))
    prose = _read_section_prose(Document(str(path)))
    assert prose["Notes / Special Handling"] == "Trim whitespace on all keys.\nAmounts are in minor units."


def _min_doc(path, with_notes=False):
    doc = Document()
    doc.add_heading("Inputs and Schema", level=1)
    _table(doc, ["Source", "Column", "Type", "Nullable", "Key"], [["src", "id", "str", "false", "true"]])
    doc.add_heading("Transformation Rules", level=1)
    _table(doc, ["ID", "Kind", "Description"], [["R1", "sort", "order by id"]])
    if with_notes:
        doc.add_heading("Notes / Special Handling", level=1)
        doc.add_paragraph("Keys are case-sensitive.")
    doc.save(str(path))


def test_extract_doc_captures_notes(tmp_path):
    path = tmp_path / "d.docx"
    _min_doc(path, with_notes=True)
    result = extract_doc(str(path))
    assert result.notes == "Keys are case-sensitive."


def test_extract_doc_no_notes_is_empty_string(tmp_path):
    path = tmp_path / "d.docx"
    _min_doc(path, with_notes=False)
    assert extract_doc(str(path)).notes == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/agents/tools/test_extract_doc_v2.py -v`
Expected: FAIL - `ExtractResult` has no `notes`/`extra_sections`/`tier`; `_read_section_prose` is undefined.

- [ ] **Step 3: Minimal implementation**

In `agents/tools/extract_doc.py`, add near the top (after `REQUIRED_BLOCKS`):

```python
NOTES_BLOCK = "Notes / Special Handling"
```

Add the three fields to `ExtractResult` (append after `conformance`):

```python
    notes: str = ""
    extra_sections: dict = field(default_factory=dict)
    tier: str = "build"
```

Add the prose reader (near `_read_sections`):

```python
def _read_section_prose(doc):
    """Return H1 heading text -> the non-heading paragraph text under it (verbatim).

    Prose is captured for EVERY H1 (today only tables are read). Text is joined
    with newlines in document order; empty paragraphs are skipped. This carries
    BA intent (notes, unrecognized-section prose) to the LLM without ever
    forwarding real table cell values.
    """
    prose = {}
    current_h1 = None
    for block in _iter_block_items(doc):
        if isinstance(block, Paragraph):
            level = _heading_level(block)
            if level == 1:
                current_h1 = block.text.strip()
                prose.setdefault(current_h1, [])
            elif level is None and current_h1 is not None:
                text = block.text.strip()
                if text:
                    prose[current_h1].append(text)
    return {h: "\n".join(lines) for h, lines in prose.items()}
```

In `extract_doc`, after `sections = _read_sections(doc)` (line 308), also read prose, and populate `notes` on the returned `ExtractResult`. Add before the `return ExtractResult(...)`:

```python
    prose = _read_section_prose(doc)
    notes = prose.get(NOTES_BLOCK, "")
```

Add `notes=notes,` to the successful `ExtractResult(...)` (the one at line 342), keeping `extra_sections`/`tier` at their defaults for now (later tasks populate them).

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/agents/tools/test_extract_doc_v2.py tests/agents/tools/test_extract_doc_cli.py -v`
Expected: PASS (new v2 tests green; `test_extract_doc_cli.py` still green - the test-fake constructor omits the new fields and defaults cover it).

- [ ] **Step 5: Commit**

```bash
git add agents/tools/extract_doc.py tests/agents/tools/test_extract_doc_v2.py
git commit -m "feat(extract_doc): add notes/extra_sections/tier fields + prose capture

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01CFnbyyDzMRERGWf9XeVSqq"
```

---

### Task 3: Data-blind `extra_sections`

**Files:**
- Modify: `agents/tools/extract_doc.py` (add `RECOGNIZED_BLOCKS`, `_table_structural_facts`, `_collect_extra_sections`, populate in `extract_doc`)
- Test: `tests/agents/tools/test_extract_doc_v2.py` (append)

**Interfaces:**
- Consumes: `_read_sections`, `_read_section_prose`, `_table_records`, `compute_derived_facts` (existing).
- Produces: `RECOGNIZED_BLOCKS` (frozenset of the 5 known H1s); `_table_structural_facts(table) -> dict` (`{"columns": [...], "row_count": int, "facts": {col: {...}}, "flag": "unrecognized table under '<h>' - review"}`); `_collect_extra_sections(doc, sections, prose) -> dict` (unrecognized H1 -> `{"prose": str, "tables": [structural-facts, ...]}`). No raw cell values are stored or returned.

- [ ] **Step 1: Write the failing test**

Append to `tests/agents/tools/test_extract_doc_v2.py`:

```python
def test_extra_sections_are_data_blind(tmp_path):
    doc = Document()
    doc.add_heading("Inputs and Schema", level=1)
    _table(doc, ["Source", "Column", "Type", "Nullable", "Key"], [["src", "id", "str", "false", "true"]])
    doc.add_heading("Transformation Rules", level=1)
    _table(doc, ["ID", "Kind", "Description"], [["R1", "sort", "order by id"]])
    doc.add_heading("Reference Codes", level=1)  # UNRECOGNIZED H1
    doc.add_paragraph("Map region codes to names.")
    _table(doc, ["code", "region"], [["EU", "Europe"], ["NA", "North America"]])
    path = tmp_path / "d.docx"
    doc.save(str(path))

    result = extract_doc(str(path))
    extra = result.extra_sections["Reference Codes"]
    assert extra["prose"] == "Map region codes to names."
    tbl = extra["tables"][0]
    assert tbl["columns"] == ["code", "region"]
    assert tbl["row_count"] == 2
    assert "region" in tbl["facts"] and "code" in tbl["facts"]
    assert "review" in tbl["flag"]
    # DATA-WALL: no raw cell value ('EU'/'Europe'/'NA') leaks into extra_sections.
    import json
    blob = json.dumps(result.extra_sections)
    assert "Europe" not in blob and "North America" not in blob and "EU" not in blob


def test_extra_sections_excludes_recognized_blocks(tmp_path):
    path = tmp_path / "d.docx"
    _min_doc(path, with_notes=True)
    result = extract_doc(str(path))
    # Notes / Special Handling is recognized (-> notes), never an extra section.
    assert result.extra_sections == {}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/agents/tools/test_extract_doc_v2.py -k extra_sections -v`
Expected: FAIL - `extra_sections` is still the default `{}` for the unrecognized-H1 doc.

- [ ] **Step 3: Minimal implementation**

In `agents/tools/extract_doc.py`, add after `NOTES_BLOCK`:

```python
RECOGNIZED_BLOCKS = frozenset(REQUIRED_BLOCKS) | {"Sample Input", "Expected Output", NOTES_BLOCK}
```

Add the two helpers (near `compute_derived_facts`):

```python
def _table_structural_facts(table, heading):
    """Derive DATA-BLIND structural facts from one table -- column names, row count,
    and per-column null-rate/uniqueness -- plus a review flag. No raw cell value is
    kept: the same data-wall applied to sample/expected rows."""
    header, records = _table_records(table)
    facts = compute_derived_facts({"_": records}).get("_", {}) if records else {c: {} for c in header}
    return {
        "columns": header,
        "row_count": len(records),
        "facts": facts,
        "flag": f"unrecognized table under '{heading}' - review",
    }


def _collect_extra_sections(sections, prose):
    """Per UNRECOGNIZED H1: verbatim prose (intent) + only STRUCTURAL facts for any
    table. Raw table cell values are never stored (same data-wall as sample/expected)."""
    extra = {}
    headings = set(sections) | set(prose)
    for heading in headings:
        if heading in RECOGNIZED_BLOCKS:
            continue
        tables = [_table_structural_facts(tbl, heading) for _subheading, tbl in sections.get(heading, [])]
        extra[heading] = {"prose": prose.get(heading, ""), "tables": tables}
    return extra
```

In `extract_doc`, after `notes = prose.get(NOTES_BLOCK, "")`, add:

```python
    extra_sections = _collect_extra_sections(sections, prose)
```

and pass `extra_sections=extra_sections,` into the successful `ExtractResult(...)`.

Note: `_read_sections` records every table under its current H1 as `(current_h2, table)` (the H2 may be `None`), so an unrecognized H1's table is captured whether or not it has an H2. `_collect_extra_sections` iterates those `(subheading, table)` tuples and keeps only the DATA-BLIND structural facts, never the raw cells. This reuses the existing section-reader unchanged and keeps `extract_doc` deterministic.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/agents/tools/test_extract_doc_v2.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add agents/tools/extract_doc.py tests/agents/tools/test_extract_doc_v2.py
git commit -m "feat(extract_doc): data-blind extra_sections capture

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01CFnbyyDzMRERGWf9XeVSqq"
```

---

### Task 4: Tier computation + CLI emit

**Files:**
- Modify: `agents/tools/extract_doc.py` (add `_compute_tier`, populate `tier`, expected-without-sample warning)
- Test: `tests/agents/tools/test_extract_doc_v2.py` (append)

**Interfaces:**
- Consumes: `sections`, `sample_input`, `expected_output` (in `extract_doc`).
- Produces: `_compute_tier(sections, sample_input, expected_output) -> str` returning exactly one of `"verified"|"smoke"|"build"`. `verified` iff Sample present-and-parseable AND >=1 expected output has >=1 data row; `smoke` iff Sample present-and-parseable but no graded expected; `build` otherwise. `to_dict`/CLI emit `tier` (via `asdict`, already wired).

- [ ] **Step 1: Write the failing test**

Append to `tests/agents/tools/test_extract_doc_v2.py`:

```python
import json as _json

from agents.tools import extract_doc as _ed


def _full_doc(path, with_sample=True, with_expected_rows=True):
    doc = Document()
    doc.add_heading("Inputs and Schema", level=1)
    _table(doc, ["Source", "Column", "Type", "Nullable", "Key"], [["src", "id", "str", "false", "true"]])
    doc.add_heading("Transformation Rules", level=1)
    _table(doc, ["ID", "Kind", "Description"], [["R1", "sort", "order by id"]])
    if with_sample:
        doc.add_heading("Sample Input", level=1)
        doc.add_heading("src", level=2)
        _table(doc, ["id"], [["1"], ["2"]])
    doc.add_heading("Expected Output", level=1)
    doc.add_heading("out", level=2)
    rows = [["1"], ["2"]] if with_expected_rows else []
    _table(doc, ["id*"], rows)
    doc.save(str(path))


def test_tier_verified_when_sample_and_graded_expected(tmp_path):
    p = tmp_path / "v.docx"; _full_doc(p, with_sample=True, with_expected_rows=True)
    assert extract_doc(str(p)).tier == "verified"


def test_tier_smoke_when_sample_only(tmp_path):
    p = tmp_path / "s.docx"; _full_doc(p, with_sample=True, with_expected_rows=False)
    r = extract_doc(str(p))
    assert r.tier == "smoke"


def test_tier_build_when_no_sample(tmp_path):
    p = tmp_path / "b.docx"; _full_doc(p, with_sample=False, with_expected_rows=True)
    assert extract_doc(str(p)).tier == "build"


def test_cli_emits_tier(tmp_path):
    p = tmp_path / "v.docx"; _full_doc(p, with_sample=True, with_expected_rows=True)
    out = tmp_path / "e.json"
    rc = _ed.main([str(p), "--out", str(out)])
    assert rc == 0
    assert _json.loads(out.read_text())["tier"] == "verified"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/agents/tools/test_extract_doc_v2.py -k tier -v`
Expected: FAIL - `tier` is still the default `"build"` for the verified/smoke docs.

- [ ] **Step 3: Minimal implementation**

Add the helper (near `_check_conformance`):

```python
def _compute_tier(sections, sample_input, expected_output):
    """Select the verification tier from which optional blocks are present+parseable.

    Tier is presence-driven (never a parsed row count of the required blocks):
      - ``verified``: Sample present+parseable AND >=1 expected output has >=1 data
        row (a gradable oracle exists).
      - ``smoke``: Sample present+parseable but no gradable expected output.
      - ``build``: no parseable Sample (build the job.json only; Expected-without-
        Sample also lands here -- an oracle with no input cannot be run).
    """
    has_sample = "Sample Input" in sections and bool(sample_input)
    has_graded = any(len(rows) > 0 for rows in expected_output.values())
    if has_sample and has_graded:
        return "verified"
    if has_sample:
        return "smoke"
    return "build"
```

In `extract_doc`, after `extra_sections = _collect_extra_sections(...)`, add:

```python
    tier = _compute_tier(sections, sample_input, expected_output)
    if tier == "build" and expected_output and "Sample Input" not in sections:
        logger.warning("[extract_doc] %s: Expected Output present without Sample Input; "
                       "tier=build (an oracle with no input cannot be run)", file_path.name)
```

Pass `tier=tier,` into the successful `ExtractResult(...)`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/agents/tools/test_extract_doc_v2.py tests/agents/tools/test_extract_doc.py tests/agents/tools/test_extract_doc_cli.py -v`
Expected: PASS (full extract_doc suite green).

- [ ] **Step 5: Commit**

```bash
git add agents/tools/extract_doc.py tests/agents/tools/test_extract_doc_v2.py
git commit -m "feat(extract_doc): compute verified|smoke|build tier, CLI emits it

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01CFnbyyDzMRERGWf9XeVSqq"
```

---

## PHASE 2 - materialize_golden (new deterministic tool)

### Task 5: `materialize_inputs` - write input CSVs at work-dir root

**Files:**
- Create: `agents/tools/materialize_golden.py`
- Test: `tests/agents/tools/test_materialize_golden.py` (CREATE)

**Interfaces:**
- Consumes: an `extract_doc.json` dict (keys `sample_input`, `sources_schema`).
- Produces: `_SEP = ";"`; `_write_csv(path, header, rows)` (RFC-4180, `csv.QUOTE_MINIMAL`, `;` delimiter, `"` quotechar, `\n` line terminator); `materialize_inputs(extract: dict, work_dir) -> list[str]` writing `<source>.csv` at the work-dir ROOT (one file per `sample_input` source), returning the written filenames.

- [ ] **Step 1: Write the failing test**

Create `tests/agents/tools/test_materialize_golden.py`:

```python
import csv
from pathlib import Path

from agents.tools.materialize_golden import materialize_inputs


def _read(path):
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.reader(fh, delimiter=";"))


def test_materialize_inputs_writes_named_csv_at_root(tmp_path):
    extract = {
        "sample_input": {"transactions": [{"id": "T1", "amt": "10"}, {"id": "T2", "amt": "20"}]},
        "sources_schema": {"transactions": [{"name": "id"}, {"name": "amt"}]},
    }
    written = materialize_inputs(extract, tmp_path)
    assert written == ["transactions.csv"]
    rows = _read(tmp_path / "transactions.csv")
    assert rows[0] == ["id", "amt"]
    assert rows[1] == ["T1", "10"] and rows[2] == ["T2", "20"]


def test_materialize_inputs_quotes_embedded_separator(tmp_path):
    extract = {"sample_input": {"src": [{"id": "T1", "note": "a;b"}]},
               "sources_schema": {"src": [{"name": "id"}, {"name": "note"}]}}
    materialize_inputs(extract, tmp_path)
    # RFC-4180: the ';' inside the value must be quoted, not column-shifted.
    raw = (tmp_path / "src.csv").read_text(encoding="utf-8")
    assert '"a;b"' in raw
    assert _read(tmp_path / "src.csv")[1] == ["T1", "a;b"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/agents/tools/test_materialize_golden.py -k inputs -v`
Expected: FAIL - `agents/tools/materialize_golden` does not exist.

- [ ] **Step 3: Minimal implementation**

Create `agents/tools/materialize_golden.py`:

```python
"""Deterministic materialization of an extract_doc.json into the exact input CSVs
and golden answer key the harness needs.

The LLM never touches this: it copies the extracted data verbatim into files.
Input CSVs go to the work-dir ROOT (the harness anchors a relative
``filepath: "x.csv"`` there); the ``<out>_expected.csv`` answer key + manifest
go under ``golden/``. All CSVs are RFC-4180 double-quoted so a value containing
the ';' separator round-trips (the configurator pairs this with ``csv_option:
true`` on the delimited I/O).
"""
from __future__ import annotations

import csv
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_SEP = ";"


def _write_csv(path, header, rows):
    """Write an RFC-4180 (QUOTE_MINIMAL) ';'-delimited CSV: header then row dicts."""
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh, delimiter=_SEP, quotechar='"',
                            quoting=csv.QUOTE_MINIMAL, lineterminator="\n")
        writer.writerow(header)
        for row in rows:
            writer.writerow([row.get(col, "") for col in header])


def _header_for(name, rows, schema):
    """Header = first row's keys (the literal table header); fall back to the
    declared schema column names when there are no data rows."""
    if rows:
        return list(rows[0].keys())
    return [c["name"] for c in schema.get(name, []) if isinstance(c, dict) and c.get("name")]


def materialize_inputs(extract: dict, work_dir) -> list[str]:
    """Write one ``<source>.csv`` per sample_input source at the work-dir ROOT.

    Returns the written filenames. The file name is the input-side naming
    contract: the configurator authors each FileInputDelimited ``filepath`` as
    exactly ``<source-name>.csv`` (a bare relative path anchored to the root)."""
    root = Path(work_dir)
    root.mkdir(parents=True, exist_ok=True)
    sample = extract.get("sample_input", {})
    schema = extract.get("sources_schema", {})
    written = []
    for source, rows in sample.items():
        header = _header_for(source, rows, schema)
        fname = f"{source}.csv"
        _write_csv(root / fname, header, rows)
        written.append(fname)
    logger.info("[materialize_golden] wrote %d input CSV(s) to %s", len(written), root)
    return written
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/agents/tools/test_materialize_golden.py -k inputs -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add agents/tools/materialize_golden.py tests/agents/tools/test_materialize_golden.py
git commit -m "feat(materialize_golden): write input CSVs at work-dir root

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01CFnbyyDzMRERGWf9XeVSqq"
```

---

### Task 6: `materialize_expected` - golden CSVs + manifest under `golden/`

**Files:**
- Modify: `agents/tools/materialize_golden.py`
- Test: `tests/agents/tools/test_materialize_golden.py` (append)

**Interfaces:**
- Consumes: `_write_csv`, `_header_for`; extract keys `expected_output`, `output_keys`.
- Produces: `materialize_expected(extract: dict, work_dir) -> dict` returning the manifest dict `{"outputs": {name: {"keys": [...], "sep": ";", "graded": bool}}}` (NO `component`), writing `golden/<name>_expected.csv` for graded outputs only (>=1 data row) and `golden/manifest.json`.

- [ ] **Step 1: Write the failing test**

Append to `tests/agents/tools/test_materialize_golden.py`:

```python
import json

from agents.tools.materialize_golden import materialize_expected


def test_materialize_expected_writes_manifest_and_graded_csv(tmp_path):
    extract = {
        "expected_output": {"enriched": [{"id": "T1", "name": "A"}]},
        "output_keys": {"enriched": ["id"]},
    }
    manifest = materialize_expected(extract, tmp_path)
    assert manifest == {"outputs": {"enriched": {"keys": ["id"], "sep": ";", "graded": True}}}
    assert "component" not in json.dumps(manifest)
    gdir = tmp_path / "golden"
    assert json.loads((gdir / "manifest.json").read_text()) == manifest
    assert (gdir / "enriched_expected.csv").exists()


def test_materialize_expected_declared_empty_is_graded_false_no_csv(tmp_path):
    extract = {"expected_output": {"rejects": []}, "output_keys": {"rejects": []}}
    manifest = materialize_expected(extract, tmp_path)
    assert manifest["outputs"]["rejects"]["graded"] is False
    # Declared-empty output: no expected CSV written (nothing to diff).
    assert not (tmp_path / "golden" / "rejects_expected.csv").exists()


def test_materialize_expected_embedded_sep_round_trips(tmp_path):
    extract = {"expected_output": {"o": [{"id": "T1", "note": "x;y"}]}, "output_keys": {"o": ["id"]}}
    materialize_expected(extract, tmp_path)
    import csv
    with open(tmp_path / "golden" / "o_expected.csv", newline="", encoding="utf-8") as fh:
        rows = list(csv.reader(fh, delimiter=";"))
    assert rows[1] == ["T1", "x;y"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/agents/tools/test_materialize_golden.py -k expected -v`
Expected: FAIL - `materialize_expected` is undefined.

- [ ] **Step 3: Minimal implementation**

Append to `agents/tools/materialize_golden.py`:

```python
def materialize_expected(extract: dict, work_dir) -> dict:
    """Write the golden answer key under ``golden/`` and return the manifest dict.

    Per expected output: ``graded`` is True iff it has >=1 data row (a declared-
    empty header-only output is ``graded: false``). A graded output gets a
    ``<name>_expected.csv``; an ungraded one gets no CSV (nothing to diff). The
    manifest carries NO ``component`` key -- run_and_validate derives the id
    deterministically from the FileOutput whose id == the output name."""
    gdir = Path(work_dir) / "golden"
    gdir.mkdir(parents=True, exist_ok=True)
    expected = extract.get("expected_output", {})
    output_keys = extract.get("output_keys", {})
    outputs = {}
    for name, rows in expected.items():
        graded = len(rows) > 0
        outputs[name] = {"keys": output_keys.get(name, []), "sep": _SEP, "graded": graded}
        if graded:
            _write_csv(gdir / f"{name}_expected.csv", list(rows[0].keys()), rows)
    manifest = {"outputs": outputs}
    (gdir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    logger.info("[materialize_golden] wrote manifest with %d output(s) to %s", len(outputs), gdir)
    return manifest
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/agents/tools/test_materialize_golden.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add agents/tools/materialize_golden.py tests/agents/tools/test_materialize_golden.py
git commit -m "feat(materialize_golden): golden expected CSVs + manifest under golden/

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01CFnbyyDzMRERGWf9XeVSqq"
```

---

### Task 7: `materialize_golden` orchestrator + CLI (emits tier)

**Files:**
- Modify: `agents/tools/materialize_golden.py`
- Test: `tests/agents/tools/test_materialize_golden.py` (append)

**Interfaces:**
- Consumes: `materialize_inputs`, `materialize_expected`; extract key `tier`.
- Produces: `materialize_golden(extract: dict, work_dir) -> dict` (`{"tier": str, "inputs": [...], "outputs": {...manifest.outputs...}}`); `main(argv=None) -> int` CLI (`--extract-doc <json>`, `--work-dir <dir>`, optional `--out`), exit 0 ok / 2 load error, emitting the result JSON (tier + inputs + outputs).

- [ ] **Step 1: Write the failing test**

Append to `tests/agents/tools/test_materialize_golden.py`:

```python
from agents.tools.materialize_golden import main, materialize_golden


def test_materialize_golden_end_to_end(tmp_path):
    extract = {
        "tier": "verified",
        "sample_input": {"src": [{"id": "T1"}]},
        "sources_schema": {"src": [{"name": "id"}]},
        "expected_output": {"out": [{"id": "T1"}]},
        "output_keys": {"out": ["id"]},
    }
    result = materialize_golden(extract, tmp_path)
    assert result["tier"] == "verified"
    assert result["inputs"] == ["src.csv"]
    assert result["outputs"]["out"]["graded"] is True
    assert (tmp_path / "src.csv").exists()
    assert (tmp_path / "golden" / "out_expected.csv").exists()


def test_cli_emits_tier_and_returns_zero(tmp_path):
    ed = tmp_path / "extract_doc.json"
    ed.write_text(json.dumps({
        "tier": "smoke",
        "sample_input": {"src": [{"id": "T1"}]},
        "sources_schema": {"src": [{"name": "id"}]},
        "expected_output": {}, "output_keys": {},
    }))
    out = tmp_path / "mat.json"
    rc = main(["--extract-doc", str(ed), "--work-dir", str(tmp_path), "--out", str(out)])
    assert rc == 0
    assert json.loads(out.read_text())["tier"] == "smoke"


def test_cli_bad_extract_doc_returns_two(tmp_path):
    rc = main(["--extract-doc", str(tmp_path / "nope.json"), "--work-dir", str(tmp_path)])
    assert rc == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/agents/tools/test_materialize_golden.py -k "golden or cli" -v`
Expected: FAIL - `materialize_golden` and `main` are undefined.

- [ ] **Step 3: Minimal implementation**

Append to `agents/tools/materialize_golden.py`:

```python
def materialize_golden(extract: dict, work_dir) -> dict:
    """Materialize input CSVs + the golden answer key and echo the tier.

    Deterministic: it writes the exact extracted data; no model is involved."""
    inputs = materialize_inputs(extract, work_dir)
    manifest = materialize_expected(extract, work_dir)
    return {"tier": extract.get("tier", "build"), "inputs": inputs, "outputs": manifest["outputs"]}


def main(argv=None) -> int:
    """CLI: extract_doc.json + work dir -> input CSVs (root) + golden/ answer key."""
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Materialize input CSVs + golden answer key from an extract_doc.json.")
    parser.add_argument("--extract-doc", required=True, help="path to extract_doc.json")
    parser.add_argument("--work-dir", required=True, help="work dir (job.json parent); inputs land at its root")
    parser.add_argument("--out", help="write the result JSON here (default: stdout)")
    args = parser.parse_args(argv)

    def _emit(payload):
        text = json.dumps(payload, indent=2)
        if args.out:
            Path(args.out).write_text(text, encoding="utf-8")
        else:
            sys.stdout.write(text + "\n")

    try:
        extract = json.loads(Path(args.extract_doc).read_text(encoding="utf-8"))
        result = materialize_golden(extract, args.work_dir)
    except (OSError, ValueError) as exc:
        _emit({"error": str(exc)})
        return 2
    _emit(result)
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/agents/tools/test_materialize_golden.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add agents/tools/materialize_golden.py tests/agents/tools/test_materialize_golden.py
git commit -m "feat(materialize_golden): orchestrator + CLI that emits the tier

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01CFnbyyDzMRERGWf9XeVSqq"
```

---

## PHASE 3 - run_and_validate grade-path + smoke (+ fixture migration)

### Task 8: Grade-path rewrite (graded-driven output_map, id==name) + golden fixture migration

**Files:**
- Modify: `agents/tools/run_and_validate.py:724-779` (`main` grade path only) - add `_output_component_ids`
- Modify: `tests/fixtures/recon/golden_enrichment/job.json`, `.../manifest.json`
- Modify: `tests/agents/tools/test_oracle.py` (`_write_cli_case` + new tests), `tests/agents/tools/test_golden_enrichment_e2e.py` (`_output_map_and_keys`, output id)

**Interfaces:**
- Consumes: `_FILE_OUTPUT_TYPES`, `_NON_DELIMITED_OUTPUT_TYPES`, `run_job_capture`, `check` (existing, unchanged).
- Produces: `_output_component_ids(job: dict) -> set[str]` (ids of every FileOutput-family writer). `main()` reads each manifest output's `graded`; for `graded: true` it sets `output_map[name] = name` after asserting a FileOutput component with `id == name` exists (else a clear error, exit 2, NOT a KeyError) and loads `<name>_expected.csv`; `graded: false` outputs are run but neither read nor diffed. The manifest no longer carries `component`.

- [ ] **Step 1: Write the failing tests**

In `tests/agents/tools/test_oracle.py`, update `_write_cli_case` to the new contract (output name == the job's FileOutput id `out1`, drop `component`, add `graded`, rename the expected file):

```python
def _write_cli_case(tmp_path, expected_csv_text):
    """Wire up job.json + golden dir (manifest OMITS sep, has graded, NO component) and return main() argv."""
    src = tmp_path / "source.csv"
    src.write_text("cc;amt\nUS;10\nUK;20\n")
    job_path = tmp_path / "job.json"
    job_path.write_text(json.dumps(_passthrough_job(src, tmp_path / "out.csv")))
    gdir = tmp_path / "golden"; gdir.mkdir()
    (gdir / "manifest.json").write_text(json.dumps({"outputs": {"out1": {"keys": ["cc"], "graded": True}}}))
    (gdir / "out1_expected.csv").write_text(expected_csv_text)
    report_path = tmp_path / "report.json"
    return ["--job", str(job_path), "--golden-dir", str(gdir), "--out", str(report_path)], report_path
```

Add two new grade-path tests to `tests/agents/tools/test_oracle.py`:

```python
def test_cli_graded_output_missing_component_id_is_clear_error(tmp_path):
    from agents.tools.run_and_validate import main
    job = tmp_path / "job.json"; job.write_text('{"components": [], "flows": []}')
    gdir = tmp_path / "g"; gdir.mkdir()
    (gdir / "manifest.json").write_text(json.dumps({"outputs": {"ghost": {"keys": ["id"], "graded": True}}}))
    report = tmp_path / "r.json"
    rc = main(["--job", str(job), "--golden-dir", str(gdir), "--out", str(report)])
    assert rc == 2
    err = json.loads(report.read_text())["error"]
    assert "ghost" in err and "id" in err  # a clear reason, not a bare KeyError


def test_cli_graded_false_output_is_run_not_diffed(tmp_path):
    from agents.tools.run_and_validate import main
    src = tmp_path / "source.csv"; src.write_text("cc;amt\nUS;10\nUK;20\n")
    job = tmp_path / "job.json"
    job.write_text(json.dumps(_passthrough_job(src, tmp_path / "out.csv")))
    gdir = tmp_path / "golden"; gdir.mkdir()
    # out1 graded (matches the job's FileOutput id); 'extra' graded:false, NO expected CSV.
    (gdir / "manifest.json").write_text(json.dumps({"outputs": {
        "out1": {"keys": ["cc"], "graded": True},
        "extra": {"keys": [], "graded": False},
    }}))
    (gdir / "out1_expected.csv").write_text("cc;amt\nUS;10\nUK;20\n")
    report = tmp_path / "r.json"
    rc = main(["--job", str(job), "--golden-dir", str(gdir), "--out", str(report)])
    assert rc == 0  # graded:false 'extra' does NOT crash on its missing expected CSV
    assert json.loads(report.read_text())["passed"] is True
```

In `tests/agents/tools/test_golden_enrichment_e2e.py`, replace `_output_map_and_keys` (drop `component`, derive id==name):

```python
def _output_map_and_keys():
    outs = _manifest_outputs()
    output_map = {name: name for name in outs}          # FileOutput id == output name
    keys = {name: spec.get("keys") for name, spec in outs.items()}
    return output_map, keys
```

and change both `rr.outputs["out_enriched"]` references (lines 84, 97 region) to `rr.outputs["enriched"]`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/agents/tools/test_oracle.py -k "cli_main or graded" -v`
Expected: FAIL - `main()` still reads `spec["component"]` (KeyError-wrapped exit 2), so `test_cli_main_passes_on_matching_output` breaks with the new component-less manifest and the graded tests fail.

- [ ] **Step 3: Minimal implementation**

In `agents/tools/run_and_validate.py`, add the helper (near `_FILE_OUTPUT_TYPES`):

```python
def _output_component_ids(job: dict) -> set:
    """Ids of every FileOutput-family writer -- the assembler binds each terminal
    FileOutput's id to its Expected-Output name, so this is the set of valid
    graded-output ids."""
    writers = _FILE_OUTPUT_TYPES | _NON_DELIMITED_OUTPUT_TYPES
    return {c.get("id") for c in job.get("components", []) if c.get("type") in writers}
```

Replace the mapping loop inside `main()` (lines 759-766) with:

```python
        expected, output_map, keys = {}, {}, {}
        fo_ids = _output_component_ids(job)
        for name, spec in outputs_spec.items():
            if not spec.get("graded", True):
                continue  # ungraded: run the job but do not read an expected CSV or diff
            if name not in fo_ids:
                _emit({"passed": False,
                       "error": f"graded output '{name}' has no FileOutput component with id == '{name}' in job.json"})
                return 2
            # Default to ';' -- the repo golden convention and what _read_output uses.
            sep = spec.get("sep", ";")
            expected[name] = pd.read_csv(gdir / f"{name}_expected.csv", sep=sep, dtype=str, keep_default_na=False)
            output_map[name] = name  # the Sec 4.4 contract: FileOutput id == output name
            keys[name] = spec.get("keys")
```

(The rest of `main()` - the `run_job_capture(...)`, `output_types`, `check(...)`, `_emit`, and the `except (OSError, ValueError, KeyError, TypeError, AttributeError)` wrapper - is unchanged.)

Migrate the fixture. In `tests/fixtures/recon/golden_enrichment/job.json`: rename the terminal FileOutput component `"id": "out_enriched"` -> `"id": "enriched"` and its inbound flow `{"name": "sort_out", "from": "sort", "to": "out_enriched"}` -> `"to": "enriched"`.

In `tests/fixtures/recon/golden_enrichment/manifest.json`:

```json
{
  "outputs": {
    "enriched": {"keys": ["cc"], "sep": ";", "graded": true}
  }
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/agents/tools/test_oracle.py -v && python -m pytest tests/agents/tools/test_golden_enrichment_e2e.py -v -m java`
Expected: PASS (oracle suite green; the golden e2e passes on the renamed id + component-less manifest when a JVM is present, else skips).

- [ ] **Step 5: Commit**

```bash
git add agents/tools/run_and_validate.py tests/agents/tools/test_oracle.py tests/agents/tools/test_golden_enrichment_e2e.py tests/fixtures/recon/golden_enrichment/job.json tests/fixtures/recon/golden_enrichment/manifest.json
git commit -m "feat(run_and_validate): graded-driven grade path (FileOutput id==name), migrate golden fixture

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01CFnbyyDzMRERGWf9XeVSqq"
```

---

### Task 9: `--smoke` mode + distinct verdict + string-only de-bias

**Files:**
- Modify: `agents/tools/run_and_validate.py` (`main` argparse + smoke branch; add `_smoke_verdict`; string-scrub the two frozen messages)
- Test: `tests/agents/tools/test_smoke_mode.py` (CREATE)

**Interfaces:**
- Consumes: `run_job_capture` (called UNCHANGED - all gates still fire), `RunResult`.
- Produces: `_smoke_verdict(rr: RunResult) -> dict` = `{"tier": "smoke", "ran_clean": bool, "status": str, "produced_outputs": {id: row_count}, "dropped_or_errored_components": [...]}` with NO `passed`. `main()` accepts `--smoke` (mutually exclusive with `--golden-dir`); with `--smoke` it runs the job through `run_job_capture` and emits the verdict; exit 0 iff `ran_clean`.

- [ ] **Step 1: Write the failing test**

Create `tests/agents/tools/test_smoke_mode.py`:

```python
import json

from agents.tools.run_and_validate import RunResult, _smoke_verdict


def test_smoke_verdict_has_no_passed_field():
    import pandas as pd
    rr = RunResult(status="success", outputs={"out1": pd.DataFrame({"cc": ["US"]})})
    v = _smoke_verdict(rr)
    assert "passed" not in v
    assert v["tier"] == "smoke"
    assert v["ran_clean"] is True
    assert v["produced_outputs"] == {"out1": 1}
    assert v["dropped_or_errored_components"] == []


def test_smoke_verdict_not_clean_on_dropped():
    rr = RunResult(status="success", dropped_components=["ghost"])
    v = _smoke_verdict(rr)
    assert v["ran_clean"] is False and "ghost" in v["dropped_or_errored_components"]


def test_smoke_verdict_not_clean_on_errored_component():
    rr = RunResult(status="success", component_stats={"c": {"status": "error"}})
    v = _smoke_verdict(rr)
    assert v["ran_clean"] is False and "c" in v["dropped_or_errored_components"]


def test_cli_smoke_runs_job_and_emits_verdict(tmp_path):
    from agents.tools.run_and_validate import main
    src = tmp_path / "source.csv"; src.write_text("cc;amt\nUS;10\n")
    out = tmp_path / "out.csv"
    job = {
        "job_name": "smoke", "flows": [{"name": "f1", "from": "in1", "to": "out1", "type": "flow"}],
        "components": [
            {"id": "in1", "type": "FileInputDelimited",
             "config": {"filepath": str(src), "fieldseparator": ";", "header_rows": 1, "die_on_error": False},
             "inputs": [], "outputs": ["f1"],
             "schema": {"input": [], "output": [{"name": "cc"}, {"name": "amt"}]},
             "subjob_id": "s1", "is_subjob_start": True},
            {"id": "out1", "type": "FileOutputDelimited",
             "config": {"filepath": str(out), "fieldseparator": ";", "include_header": True,
                        "file_exist_exception": False, "create_directory": True},
             "inputs": ["f1"], "outputs": [],
             "schema": {"input": [{"name": "cc"}, {"name": "amt"}], "output": []},
             "subjob_id": "s1", "is_subjob_start": False},
        ],
    }
    job_path = tmp_path / "job.json"; job_path.write_text(json.dumps(job))
    report = tmp_path / "smoke.json"
    rc = main(["--job", str(job_path), "--smoke", "--out", str(report)])
    assert rc == 0
    v = json.loads(report.read_text())
    assert v["tier"] == "smoke" and "passed" not in v and v["ran_clean"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/agents/tools/test_smoke_mode.py -v`
Expected: FAIL - `_smoke_verdict` is undefined and `main()` rejects `--smoke` (unknown arg / `--golden-dir` required).

- [ ] **Step 3: Minimal implementation**

In `agents/tools/run_and_validate.py`, add `_smoke_verdict` (near `check`):

```python
def _smoke_verdict(run_result) -> dict:
    """A smoke-tier verdict: the job RAN, but nothing was graded. Deliberately has
    NO ``passed`` field (a smoke job is never presented as correct). ``ran_clean``
    is true only if the engine succeeded AND no declared component was dropped or
    errored -- a weak signal (a job can run clean and still be wrong), which the
    gate label makes explicit."""
    errored = [cid for cid, s in run_result.component_stats.items()
               if isinstance(s, dict) and s.get("status") == "error"]
    problems = list(run_result.dropped_components) + errored
    return {
        "tier": "smoke",
        "ran_clean": run_result.status == "success" and not problems,
        "status": run_result.status,
        "produced_outputs": {cid: int(len(df)) for cid, df in run_result.outputs.items()},
        "dropped_or_errored_components": problems,
    }
```

Rewrite the `main()` argparse + dispatch. Replace the `parser.add_argument("--golden-dir", required=True, ...)` line and the body up to `run_result = run_job_capture(...)` so `--golden-dir` is optional, `--smoke` is added, and exactly one is required:

```python
    parser.add_argument("--job", required=True, help="path to the job.json")
    parser.add_argument("--golden-dir", help="dir with <name>_expected.csv + manifest.json (verified tier)")
    parser.add_argument("--smoke", action="store_true", help="smoke tier: run the job, emit a verdict, no diff")
    parser.add_argument("--out", help="write the report JSON here (default: stdout)")
    args = parser.parse_args(argv)

    def _emit(payload: dict) -> None:
        out_text = json.dumps(payload, indent=2, default=str)
        if args.out:
            Path(args.out).write_text(out_text, encoding="utf-8")
        else:
            sys.stdout.write(out_text + "\n")

    if bool(args.smoke) == bool(args.golden_dir):
        _emit({"error": "exactly one of --golden-dir (verified) or --smoke is required"})
        return 2

    if args.smoke:
        try:
            with open(args.job, encoding="utf-8") as fh:
                job = json.load(fh)
            run_result = run_job_capture(job, Path(args.job).parent)
        except (OSError, ValueError) as exc:
            _emit({"error": str(exc)})
            return 2
        verdict = _smoke_verdict(run_result)
        _emit(verdict)
        return 0 if verdict["ran_clean"] else 1
```

The existing verified-tier body (the `try:` that loads the manifest and diffs) follows unchanged.

String-only de-bias (the frozen `run_job_capture` messages): change the two occurrences of `"the enrichment harness"` to `"the ETL harness"`:
- line 555: `f"in the enrichment harness; requires human review before execution"` -> `f"in the ETL harness; requires human review before execution"`.
- line 563: `"harness (they bypass the safety nets); review/run the child job "` -> `"ETL harness (they bypass the safety nets); review/run the child job "` (i.e. change the preceding `"nested tRunJob child jobs are not permitted in the enrichment "` to `"...not permitted in the ETL "`).

NO other line of `run_job_capture` / the jail / egress / nested / swift LOGIC changes; the existing `test_run_capture.py` assertions (`"egress"`+`"not permitted"`, `"tRunJob"`+`"not permitted"`, `"inline transform_config required"`) all remain satisfied.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/agents/tools/test_smoke_mode.py tests/agents/tools/test_oracle.py tests/agents/tools/test_run_capture.py -v`
Expected: PASS (smoke suite green; the frozen run_capture security tests unchanged and green; oracle grade-path green).

- [ ] **Step 5: Commit**

```bash
git add agents/tools/run_and_validate.py tests/agents/tools/test_smoke_mode.py
git commit -m "feat(run_and_validate): --smoke tier verdict; string-only harness de-bias

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01CFnbyyDzMRERGWf9XeVSqq"
```

---

## PHASE 4 - Skill rename dataprep-recon -> dataprep-etl

### Task 10: render_skills de-bias + neutral envelope example + regenerate the skill folder

**Files:**
- Modify: `agents/tools/render_skills.py` (`_SKILL_FRONTMATTER`, `write_skill` default + body, `render_job_envelope` prose, `_JOB_ENVELOPE_EXAMPLE_JSON`)
- Rename: `.github/skills/dataprep-recon/` -> `.github/skills/dataprep-etl/` (via regeneration)
- Test: `tests/agents/tools/test_render_skills.py` (update dir name + envelope id)

**Interfaces:**
- Consumes: nothing new.
- Produces: skill `name: dataprep-etl`; `write_skill(root=".github/skills/dataprep-etl")`; `_JOB_ENVELOPE_EXAMPLE_JSON` with the terminal FileOutput `"id": "enriched"` (== its output name), `csv_option: true` + `text_enclosure: "\""` on both FileInputDelimited nodes and the FileOutputDelimited node, and neutral prose.

- [ ] **Step 1: Write the failing test**

In `tests/agents/tools/test_render_skills.py`, update the write-skill test to the new dir, and add contract assertions on the envelope example:

```python
def test_write_skill_produces_valid_skill(tmp_path):
    root = tmp_path / "dataprep-etl"
    write_skill(str(root))
    skill_md = (root / "SKILL.md").read_text(encoding="utf-8")
    assert validate_skill(skill_md, "dataprep-etl") == []
    assert (root / "config-reference.md").exists()
    assert (root / "job-envelope.md").exists()
    assert "dataprep-recon" not in skill_md


def test_envelope_example_teaches_id_equals_name_and_csv_option():
    from agents.tools.render_skills import _JOB_ENVELOPE_EXAMPLE_JSON
    payload = json.loads(_JOB_ENVELOPE_EXAMPLE_JSON)
    fo = next(c for c in payload["components"] if c["type"] == "FileOutputDelimited")
    # terminal FileOutput id == the output name it writes
    assert fo["id"] == "enriched"
    assert fo["config"]["csv_option"] is True
    # every delimited I/O carries csv_option:true (round-trips an embedded ';')
    for c in payload["components"]:
        if c["type"] in ("FileInputDelimited", "FileOutputDelimited"):
            assert c["config"]["csv_option"] is True
```

Update the existing java e2e test in the same file to the new FileOutput id:

```python
    enriched = rr.outputs["enriched"]
```

(replace the two `rr.outputs["out_enriched"]` references).

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/agents/tools/test_render_skills.py -v`
Expected: FAIL - the skill name is still `dataprep-recon`; the envelope FileOutput id is `out_enriched` with `csv_option` absent/false.

- [ ] **Step 3: Minimal implementation**

In `agents/tools/render_skills.py`:

Replace `_SKILL_FRONTMATTER`:

```python
_SKILL_FRONTMATTER = (
    "---\n"
    "name: dataprep-etl\n"
    "description: >-\n"
    "  Code-verified knowledge for building DataPrep ETL jobs on the Python engine: per-component\n"
    "  config keys and allowed values, config landmines, the job.json envelope contract, and the\n"
    "  join/lookup and transform patterns. Use when interpreting an ETL requirement, designing the\n"
    "  flow, configuring components, or assembling/repairing a job.json.\n"
    "---\n"
)
```

In `_JOB_ENVELOPE_EXAMPLE_JSON`, edit the JSON string: rename the FileOutput component id `"out_enriched"` -> `"enriched"`, and its flow `{"name": "enriched_flow", "from": "join1", "to": "out_enriched"}` -> `"to": "enriched"`; add `"csv_option": true, "text_enclosure": "\""` to the `config` of both FileInputDelimited nodes (`in_source`, `in_lookup`) and the FileOutputDelimited node (`enriched`). Concretely the three configs become:

```
"config": {"filepath": "source.csv", "fieldseparator": ";", "header_rows": 1, "csv_option": true, "text_enclosure": "\""},
...
"config": {"filepath": "countries.csv", "fieldseparator": ";", "header_rows": 1, "csv_option": true, "text_enclosure": "\""},
...
"config": {"filepath": "enriched.csv", "fieldseparator": ";", "include_header": true, "file_exist_exception": false, "csv_option": true, "text_enclosure": "\""},
```

In `render_job_envelope`, de-bias the prose: change `"The default enrichment join is a"` sentence lead-in to neutral wording (e.g. `"A common lookup-enrich join is a"`) and change `"Minimal connected enrichment example"` to `"Minimal connected lookup-enrich example"`. Add one sentence to the `prose` string documenting the two contracts:

```python
        "A terminal FileOutputDelimited's `id` MUST equal the output name it writes (the harness maps on "
        "this), and every delimited FileInput/FileOutput that reads/writes a materialized CSV MUST set "
        "`csv_option: true` (with `text_enclosure: \"\\\"\"`) so a value containing the `;` separator "
        "round-trips instead of shifting columns.\n"
```

In `write_skill`, change the default and the body:

```python
def write_skill(root: str = ".github/skills/dataprep-etl") -> None:
    """Write SKILL.md + the three resource files for the dataprep-etl skill."""
    root_path = Path(root)
    root_path.mkdir(parents=True, exist_ok=True)
    (root_path / "config-reference.md").write_text(render_config_reference(), encoding="utf-8")
    (root_path / "landmines.md").write_text(render_landmines(), encoding="utf-8")
    (root_path / "job-envelope.md").write_text(render_job_envelope(), encoding="utf-8")
    body = (
        _SKILL_FRONTMATTER
        + "# DataPrep ETL knowledge\n\n"
        "Code-verified knowledge for building DataPrep ETL jobs (sources -> transformations -> outputs) "
        "on the Python engine that replaces Talend.\n\n"
        "Load the resource that fits the task:\n\n"
        "- `config-reference.md` - every allowed component config key + its resolved allowed values.\n"
        "- `landmines.md` - config traps that silently produce wrong output; respect each.\n"
        "- `job-envelope.md` - the exact job.json wiring shape the engine requires.\n\n"
        "Validate any component config with `python -m agents.tools.validate_config --type T --config c.json` "
        "and test a whole job with `python -m agents.tools.run_and_validate --job job.json --golden-dir DIR` "
        "before claiming it is correct.\n"
    )
    (root_path / "SKILL.md").write_text(body, encoding="utf-8")
    logger.info("[render_skills] wrote dataprep-etl skill to %s", root)
```

Also update the module docstring line 1 (`"...into the workspace-global dataprep-recon Agent Skill."` -> `"...dataprep-etl Agent Skill."`).

Regenerate the skill folder and remove the old one:

```bash
git rm -r .github/skills/dataprep-recon
python -m agents.tools.render_skills
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/agents/tools/test_render_skills.py -v && python -c "import pathlib; assert pathlib.Path('.github/skills/dataprep-etl/SKILL.md').exists(); assert not pathlib.Path('.github/skills/dataprep-recon').exists()"`
Expected: PASS (render tests green; the new skill dir exists, old is gone). The `@pytest.mark.java` envelope-run test passes when a JVM is present.

- [ ] **Step 5: Commit**

```bash
git add agents/tools/render_skills.py tests/agents/tools/test_render_skills.py .github/skills/dataprep-etl
git rm -r --cached .github/skills/dataprep-recon
git commit -m "feat(render_skills): rename skill to dataprep-etl, teach id==name + csv_option

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01CFnbyyDzMRERGWf9XeVSqq"
```

---

### Task 11: Mechanical `dataprep-recon` -> `dataprep-etl` swap across the agent system + guard test

**Files:**
- Modify: all 7 `.github/agents/*.agent.md` (skill-name references in bodies only), `agents/PLATFORM.md`, `tests/agents/tools/test_validate_agents.py` (synthetic strings)
- Test: `tests/agents/tools/test_no_recon_string.py` (CREATE)

**Interfaces:**
- Consumes: `validate_tree` (existing).
- Produces: no `dataprep-recon` string anywhere under `.github/` or `agents/`.

- [ ] **Step 1: Write the failing test**

Create `tests/agents/tools/test_no_recon_string.py`:

```python
from pathlib import Path


def test_no_dataprep_recon_string_remains():
    offenders = []
    for base in (Path(".github"), Path("agents")):
        for f in base.rglob("*"):
            if not f.is_file() or f.suffix in (".pyc",) or "__pycache__" in f.parts:
                continue
            try:
                text = f.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue  # skip binaries (e.g. the example .docx)
            if "dataprep-recon" in text:
                offenders.append(str(f))
    assert offenders == [], f"dataprep-recon must not remain: {offenders}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/agents/tools/test_no_recon_string.py -v`
Expected: FAIL - the 7 agent bodies and `agents/PLATFORM.md` still say `dataprep-recon`.

- [ ] **Step 3: Minimal implementation**

Replace every literal `dataprep-recon` with `dataprep-etl` (skill-name reference only; no other prose change) in each file:
- `.github/agents/etl-orchestrator.agent.md`, `.github/agents/doc-interpreter.agent.md`, `.github/agents/flow-designer.agent.md`, `.github/agents/configurator.agent.md`, `.github/agents/assembler.agent.md`, `.github/agents/test-runner.agent.md`, `.github/agents/diagnostician.agent.md`
- `agents/PLATFORM.md` (all `dataprep-recon` occurrences, incl. the tool-table `render_skills` row and the prerequisites; PLATFORM's deeper operational rewrite is Task 17).

In `tests/agents/tools/test_validate_agents.py`, change the two synthetic uses of `"dataprep-recon"` (in `test_skill_name_must_match_dir` and `test_validate_tree_clean_and_flags_unknown_ref`) to `"dataprep-etl"` so the whole agent system is consistent.

Command to find any remaining occurrence:

```bash
grep -rn "dataprep-recon" .github agents | grep -v __pycache__
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/agents/tools/test_no_recon_string.py tests/agents/tools/test_validate_agents.py tests/agents/tools/test_orchestrator_agent.py tests/agents/tools/test_specialist_agents.py -v`
Expected: PASS (no `dataprep-recon` remains; `validate_tree('.github/agents', '.github/skills') == []` still holds - the skill dir is now `dataprep-etl`).

- [ ] **Step 5: Commit**

```bash
git add .github/agents agents/PLATFORM.md tests/agents/tools/test_no_recon_string.py tests/agents/tools/test_validate_agents.py
git commit -m "refactor(agents): rename dataprep-recon skill references to dataprep-etl

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01CFnbyyDzMRERGWf9XeVSqq"
```

---

## PHASE 5 - Agent files reframe + contracts (body-only; frontmatter byte-identical)

All Phase-5 tasks edit `.agent.md` BODIES only; the YAML frontmatter (incl. its existing `description`) stays byte-identical (per the Global Constraints). The gate for each task is `validate_tree('.github/agents', '.github/skills') == []` plus the new body-contract assertions in `tests/agents/tools/test_agent_contracts.py`.

### Task 12: doc-interpreter - consume notes/extra_sections/tier + plumb output names/keys/graded + tag note-rules

**Files:**
- Modify: `.github/agents/doc-interpreter.agent.md` (body)
- Test: `tests/agents/tools/test_agent_contracts.py` (CREATE)

**Interfaces:**
- Consumes: nothing (doc assertions).
- Produces: the doc-interpreter body references `notes`, `extra_sections`, `tier`, the per-output `graded` flag, and tags note-derived rules with `source: "note"`.

- [ ] **Step 1: Write the failing test**

Create `tests/agents/tools/test_agent_contracts.py`:

```python
from pathlib import Path

_AGENTS = Path(".github/agents")


def _body(name):
    text = (_AGENTS / f"{name}.agent.md").read_text(encoding="utf-8")
    return text.split("---", 2)[2].lower()  # body only (skip frontmatter)


def test_doc_interpreter_consumes_notes_extra_sections_tier_and_tags():
    b = _body("doc-interpreter")
    assert "notes" in b and "extra_sections" in b and "tier" in b
    assert "graded" in b
    assert 'source: "note"' in b or "derived_from_note" in b
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/agents/tools/test_agent_contracts.py::test_doc_interpreter_consumes_notes_extra_sections_tier_and_tags -v`
Expected: FAIL - the current body does not mention `notes`/`extra_sections`/`tier`/`graded`/note-tagging.

- [ ] **Step 3: Minimal implementation**

Edit `.github/agents/doc-interpreter.agent.md` body:
- In the `## Input` "Use only these fields" list, add:
  - `- notes -- verbatim BA prose from the "Notes / Special Handling" block. Fold each note into the rule/config it constrains; if you cannot confidently apply one, raise an ambiguity rather than drop it.`
  - `- extra_sections -- unrecognized-section prose + DATA-BLIND table structural facts (columns, row_count, per-column null-rate/uniqueness) and a review flag. Use the prose + flags as intent; NEVER treat the structural facts as data values.`
  - `- tier -- verified | smoke | build. Carry it through to requirement_spec.json so the orchestrator can branch.`
  - `- expected_output names + output_keys + each output's graded flag -- carry the OUTPUT NAMES, their composite keys, and graded into requirement_spec.json so the assembler can bind each terminal FileOutput id to its output name and the harness knows which outputs to diff.`
- In `## Output` for `requirement_spec.json`, add fields: `outputs` (list of `{name, keys, graded}`), `notes` (carried verbatim), `extra_sections` (carried), and `tier`.
- Add a subsection `## Note-derived rules are tagged`:
  `Any rule (or field) you derive from a note MUST carry source: "note" (or derived_from_note: true). This makes the note-vs-oracle guard enforceable: in the verified tier the diagnostician must never "repair" a failure by dropping a note-tagged rule to force green -- such a conflict routes to human. In smoke/build the note surfaces at the human gate.`
- Neutralize the enrichment-specific framing in the intro paragraph (`## doc-interpreter`) to general ETL (sources -> transformations -> outputs), keeping the data-blindness rules intact.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/agents/tools/test_agent_contracts.py::test_doc_interpreter_consumes_notes_extra_sections_tier_and_tags -v && python -c "from agents.tools.validate_agents import validate_tree; assert validate_tree('.github/agents','.github/skills')==[]"`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add .github/agents/doc-interpreter.agent.md tests/agents/tools/test_agent_contracts.py
git commit -m "docs(doc-interpreter): consume notes/extra_sections/tier, plumb outputs, tag note-rules

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01CFnbyyDzMRERGWf9XeVSqq"
```

---

### Task 13: configurator - csv_option/text_enclosure on materialized delimited I/O + FileInput filepath contract

**Files:**
- Modify: `.github/agents/configurator.agent.md` (body)
- Test: `tests/agents/tools/test_agent_contracts.py` (append)

**Interfaces:**
- Produces: the configurator body states the `filepath == "<source-name>.csv"` input contract and requires `csv_option: true` + `text_enclosure: "\""` on every delimited FileInput/FileOutput that reads/writes a materialized CSV.

- [ ] **Step 1: Write the failing test**

Append to `tests/agents/tools/test_agent_contracts.py`:

```python
def test_configurator_states_csv_option_and_filepath_contract():
    b = _body("configurator")
    assert "csv_option" in b and "text_enclosure" in b
    assert "<source-name>.csv" in b or "source-name>.csv" in b
    assert "quote_none" in b or "shift" in b or "round-trip" in b  # the WHY of csv_option
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/agents/tools/test_agent_contracts.py::test_configurator_states_csv_option_and_filepath_contract -v`
Expected: FAIL - the body does not mention `csv_option`/`text_enclosure`/the filepath contract.

- [ ] **Step 3: Minimal implementation**

Edit `.github/agents/configurator.agent.md` body - add a `## Materialized-CSV contract` subsection (before `## Knowledge and landmines`):

```
## Materialized-CSV contract (both sides)

The materialize_golden step writes every input CSV and the golden expected CSV as
RFC-4180 double-quoted files. To read/write them faithfully you MUST set, on every
FileInputDelimited that reads a materialized source AND every terminal
FileOutputDelimited the oracle reads back:
- `csv_option: true`
- `text_enclosure: "\""`
Without csv_option the engine reads with csv.QUOTE_NONE and writes unquoted, so any
value containing the `;` separator (or a quote/newline) shifts columns and a correct
job false-fails.

Input filepath contract: author each FileInputDelimited `filepath` as exactly
`"<source-name>.csv"` -- a bare relative path (no directory) that the harness anchors
to the work-dir root, matching the file materialize_golden wrote there. `source-name`
is the Sample-Input source name (== the Source value in Inputs and Schema).
```

Neutralize the intro/framing ("enrichment flow plan" -> "ETL flow plan", etc.) while keeping every landmine paragraph verbatim (they are engine facts).

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/agents/tools/test_agent_contracts.py::test_configurator_states_csv_option_and_filepath_contract -v && python -c "from agents.tools.validate_agents import validate_tree; assert validate_tree('.github/agents','.github/skills')==[]"`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add .github/agents/configurator.agent.md tests/agents/tools/test_agent_contracts.py
git commit -m "docs(configurator): csv_option/text_enclosure + <source-name>.csv filepath contract

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01CFnbyyDzMRERGWf9XeVSqq"
```

---

### Task 14: assembler - FileOutput id == output name contract

**Files:**
- Modify: `.github/agents/assembler.agent.md` (body)
- Test: `tests/agents/tools/test_agent_contracts.py` (append)

**Interfaces:**
- Produces: the assembler body states that each terminal FileOutput component's `id` MUST equal its Expected-Output name (the deterministic key the harness maps on).

- [ ] **Step 1: Write the failing test**

Append to `tests/agents/tools/test_agent_contracts.py`:

```python
def test_assembler_states_id_equals_output_name():
    b = _body("assembler")
    assert "id" in b and "output name" in b
    assert "harness" in b or "run_and_validate" in b or "maps on" in b
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/agents/tools/test_agent_contracts.py::test_assembler_states_id_equals_output_name -v`
Expected: FAIL - the body does not state the id==output-name contract.

- [ ] **Step 3: Minimal implementation**

Edit `.github/agents/assembler.agent.md` body - add to the `## Output` bullet list:

```
- OUTPUT-NAME CONTRACT (load-bearing): set each terminal FileOutput component's `id`
  EQUAL to its Expected-Output name from requirement_spec.json (`outputs[].name`).
  This is the deterministic key run_and_validate.main() maps on to diff the right
  file (FileOutput id == output name). Getting it wrong makes the harness fail with a
  clear "graded output '<name>' has no FileOutput component with id == '<name>'" error,
  not a silent pass. Wire the flow into that FileOutput as usual; only its id is fixed
  by the contract.
```

Neutralize the intro/framing ("configured but unwired draft" stays; change enrichment-specific asides to neutral ETL). Keep the tJoin/tMap wiring paragraphs verbatim.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/agents/tools/test_agent_contracts.py::test_assembler_states_id_equals_output_name -v && python -c "from agents.tools.validate_agents import validate_tree; assert validate_tree('.github/agents','.github/skills')==[]"`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add .github/agents/assembler.agent.md tests/agents/tools/test_agent_contracts.py
git commit -m "docs(assembler): state FileOutput id == output name contract

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01CFnbyyDzMRERGWf9XeVSqq"
```

---

### Task 15: orchestrator - step-0 (extract -> materialize), tier branching, gate + note-vs-oracle

**Files:**
- Modify: `.github/agents/etl-orchestrator.agent.md` (body)
- Test: `tests/agents/tools/test_agent_contracts.py` (append)

**Interfaces:**
- Produces: the orchestrator body has a step-0 (run `extract_doc` then `materialize_golden`), branches on the tier (`verified` -> `run_and_validate --golden-dir` + 3-iter repair; `smoke` -> `run_and_validate --smoke`, no loop; `build` -> skip run), presents notes/extra_sections + tier label at the gate, and states the note-vs-oracle no-silent-repair rule.

- [ ] **Step 1: Write the failing test**

Append to `tests/agents/tools/test_agent_contracts.py`:

```python
def test_orchestrator_has_step0_tier_branching_and_note_guard():
    b = _body("etl-orchestrator")
    assert "materialize_golden" in b
    assert "verified" in b and "smoke" in b and "build" in b
    assert "--smoke" in b
    assert "extract_doc" in b
    assert "notes" in b and "extra_sections" in b
    assert "note" in b and ("repair" in b or "silently" in b)  # note-vs-oracle guard
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/agents/tools/test_agent_contracts.py::test_orchestrator_has_step0_tier_branching_and_note_guard -v`
Expected: FAIL - the body has no step-0, no `materialize_golden`, no tier tokens, no `--smoke`.

- [ ] **Step 3: Minimal implementation**

Edit `.github/agents/etl-orchestrator.agent.md` body:
- Add a `## Step 0 - materialize (deterministic, before any subagent)` section:

```
## Step 0 - materialize (deterministic terminal commands)

You are invoked with a `<docx path>` and a `<job>` name. BEFORE the forward chain,
run these two terminal commands yourself:
1. `python -m agents.tools.extract_doc <docx path> --out agents/work/<job>/extract_doc.json`
2. When a Sample Input is present, `python -m agents.tools.materialize_golden --extract-doc agents/work/<job>/extract_doc.json --work-dir agents/work/<job>`
   -- this writes the input CSVs to the work-dir ROOT and `golden/{<out>_expected.csv, manifest.json}`.
Read the emitted `tier` (verified | smoke | build); it drives the run step below.
```

- In `## The free-agent loop`, replace step 6 (`#runSubagent test-runner`) with tier branching:

```
6. Run step, by the tier from step 0:
   - verified: `#runSubagent test-runner` running
     `python -m agents.tools.run_and_validate --job agents/work/<job>/job.json --golden-dir agents/work/<job>/golden --out agents/work/<job>/test_report.json`,
     then the 3-iteration diagnose -> re-run-owner repair loop keyed on `passed`.
   - smoke: `#runSubagent test-runner` running
     `python -m agents.tools.run_and_validate --job agents/work/<job>/job.json --smoke --out agents/work/<job>/test_report.json`.
     There is NO `passed` and NO repair loop -- the verdict (ran_clean/status/produced_outputs/
     dropped_or_errored_components) goes straight to the gate labelled "smoke: ran, not graded".
   - build: skip the run entirely; go to the gate labelled "build-only: not executed".
```

- In `## Safety net 3 - the human gate`, add bullets to present: the tier (token + label), captured `notes` (verbatim), and `extra_sections` (prose + flags).
- Add a `## Note-vs-oracle (never silently repair)` paragraph:

```
A rule tagged source: "note" in requirement_spec.json is BA intent, not an oracle
artifact. In the verified tier, if a failure can only be made green by dropping or
overriding a note-tagged rule, do NOT let the diagnostician do it -- route the
conflict to human. A green harness never silences a note.
```

Keep the surface_code_cells pre-exec review (step 5) exactly as-is (all tiers, including smoke, before any run).

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/agents/tools/test_agent_contracts.py::test_orchestrator_has_step0_tier_branching_and_note_guard tests/agents/tools/test_orchestrator_agent.py tests/agents/tools/test_agent_tool_refs.py -v`
Expected: PASS (the new `materialize_golden` `python -m` reference resolves - the tool has a `main()`).

- [ ] **Step 5: Commit**

```bash
git add .github/agents/etl-orchestrator.agent.md tests/agents/tools/test_agent_contracts.py
git commit -m "docs(orchestrator): step-0 materialize, tier branching, note-vs-oracle guard

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01CFnbyyDzMRERGWf9XeVSqq"
```

---

### Task 16: test-runner tier-aware + flow-designer/diagnostician neutral framing

**Files:**
- Modify: `.github/agents/test-runner.agent.md`, `.github/agents/flow-designer.agent.md`, `.github/agents/diagnostician.agent.md` (bodies)
- Test: `tests/agents/tools/test_agent_contracts.py` (append)

**Interfaces:**
- Produces: test-runner body documents both the `--golden-dir` (verified) and `--smoke` invocations; flow-designer and diagnostician bodies use neutral ETL framing (no "recon" / no "enrichment"-only role framing).

- [ ] **Step 1: Write the failing test**

Append to `tests/agents/tools/test_agent_contracts.py`:

```python
def test_test_runner_is_tier_aware():
    b = _body("test-runner")
    assert "--smoke" in b and "--golden-dir" in b


def test_flow_designer_and_diagnostician_are_neutral():
    for name in ("flow-designer", "diagnostician"):
        b = _body(name)
        assert "recon" not in b
        # role framing is general ETL, not enrichment-only
        assert "etl" in b or "sources -> transformations -> outputs" in b or "pipeline" in b
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/agents/tools/test_agent_contracts.py -k "tier_aware or neutral" -v`
Expected: FAIL - test-runner has no `--smoke`; flow-designer/diagnostician bodies still contain "recon" framing.

- [ ] **Step 3: Minimal implementation**

Edit `.github/agents/test-runner.agent.md` body - add, after the existing verified-tier command block, a smoke variant:

```
For a SMOKE-tier job (no golden to diff), the orchestrator instead tells you to run:

```
python -m agents.tools.run_and_validate \
  --job agents/work/<job>/job.json \
  --smoke \
  --out agents/work/<job>/test_report.json
```

The smoke verdict has NO `passed` field (ran_clean / status / produced_outputs /
dropped_or_errored_components). Relay it verbatim exactly as you relay the verified report.
```

Edit `.github/agents/flow-designer.agent.md` and `.github/agents/diagnostician.agent.md` bodies - neutralize the intro role framing to general ETL (sources -> transformations -> outputs / pipeline), and remove the word "recon" from the body prose (the `dataprep-etl` skill references from Task 11 stay). Keep all engine-fact paragraphs (streaming caveat, cartesian safety, owner-routing table) verbatim.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/agents/tools/test_agent_contracts.py tests/agents/tools/test_specialist_agents.py -v && python -c "from agents.tools.validate_agents import validate_tree; assert validate_tree('.github/agents','.github/skills')==[]"`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add .github/agents/test-runner.agent.md .github/agents/flow-designer.agent.md .github/agents/diagnostician.agent.md tests/agents/tools/test_agent_contracts.py
git commit -m "docs(agents): tier-aware test-runner; neutral flow-designer/diagnostician framing

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01CFnbyyDzMRERGWf9XeVSqq"
```

---

## PHASE 6 - Docs / template / examples / knowledge de-bias

### Task 17: PLATFORM.md operational rewrite (How-to-run + pipeline diagram + tool table)

**Files:**
- Modify: `agents/PLATFORM.md`
- Test: `tests/agents/tools/test_platform_doc.py` (append)

**Interfaces:**
- Produces: PLATFORM.md documents the docx-in + job-name run flow (no human GOLDEN_DIR), a pipeline diagram with step-0 + the 3 tiers, and a tool table row for `materialize_golden`.

- [ ] **Step 1: Write the failing test**

Append to `tests/agents/tools/test_platform_doc.py`:

```python
def test_platform_doc_names_materialize_and_tiers():
    text = Path("agents/PLATFORM.md").read_text(encoding="utf-8")
    assert "materialize_golden" in text
    low = text.lower()
    assert "verified" in low and "smoke" in low and "build" in low
    assert "extract_doc" in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/agents/tools/test_platform_doc.py -v`
Expected: FAIL - PLATFORM.md has no `materialize_golden` and no tier tokens.

- [ ] **Step 3: Minimal implementation**

Edit `agents/PLATFORM.md`:
- Title/intro: change "DataPrep Recon Agents" / "enrichment requirements document" to neutral ETL wording (general ETL: sources -> transformations -> outputs).
- `## 2. How to run`: rewrite so the human provides a `<docx path>` + `<job>` name and invokes `etl-orchestrator`; the orchestrator itself runs `extract_doc` then `materialize_golden` (step-0). Remove the manual "Place the golden data at `<GOLDEN_DIR>`" step - the harness materializes it.
- `### 1.2 The pipeline` diagram: insert `extract_doc` + `materialize_golden` step-0 and the tier-branched run step (verified -> `--golden-dir`; smoke -> `--smoke`; build -> skip).
- Add a `materialize_golden` row to the `## 1.5` tool table:

```
| materialize_golden | `python -m agents.tools.materialize_golden --extract-doc extract_doc.json --work-dir agents/work/<job>` | Deterministic: writes input CSVs to the work-dir root + `golden/{<out>_expected.csv, manifest.json}`; emits the tier. |
```

- Add a short "Verification tiers" note listing `verified | smoke | build` and their gate labels.
- Keep the CITI-VERIFICATION CHECKLIST and the safety-net sections (update only framing words, not the safety logic).

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/agents/tools/test_platform_doc.py -v`
Expected: PASS (both the existing checklist/run assertions and the new materialize/tier assertions).

- [ ] **Step 5: Commit**

```bash
git add agents/PLATFORM.md tests/agents/tools/test_platform_doc.py
git commit -m "docs(platform): step-0 materialize + tiers, add materialize_golden to tool table

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01CFnbyyDzMRERGWf9XeVSqq"
```

---

### Task 18: landmines.py + config-surfaces.md framing scrub (engine facts frozen)

**Files:**
- Modify: `agents/knowledge/landmines.py:1` (module docstring), `agents/schemas/config-surfaces.md:1` (heading)
- Test: `tests/agents/tools/test_render_skills.py` (existing suite guards content unchanged)

**Interfaces:**
- Produces: neutral docstring/heading; the `LANDMINES` list content and `_validation_note` engine facts are byte-unchanged.

- [ ] **Step 1: Write the failing test**

No new test - the guard is that the existing `test_landmines_rendered` and `test_config_reference_resolves_enum_refs_not_pointers` still pass (the landmine ids/summaries are unchanged), plus a one-shot grep. Reuse the no-recon-string test from Task 11 (it already scans `agents/`).

- [ ] **Step 2: Run to see current state**

Run: `grep -in "recon" agents/knowledge/landmines.py agents/schemas/config-surfaces.md`
Expected: matches at `landmines.py:1` ("recon slice") and `config-surfaces.md:1` ("Recon-slice ...").

- [ ] **Step 3: Minimal implementation**

- `agents/knowledge/landmines.py` line 1: change `"""Code-verified config landmines for the recon slice (from config-surfaces.md + spec)."""` to `"""Code-verified config landmines for the ETL component set (from config-surfaces.md + spec)."""`. Change nothing else in the file (every landmine dict is an engine fact - frozen).
- `agents/schemas/config-surfaces.md` line 1: change `# Recon-slice component config surfaces (code-verified ground truth)` to `# ETL component config surfaces (code-verified ground truth)`. Leave `map.json` `_validation_note` untouched (it is pure engine facts, no framing).

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/agents/tools/test_render_skills.py tests/agents/tools/test_check_schema_drift.py tests/agents/tools/test_no_recon_string.py -v`
Expected: PASS (landmine rendering unchanged; drift clean; no `recon` framing remains).

- [ ] **Step 5: Commit**

```bash
git add agents/knowledge/landmines.py agents/schemas/config-surfaces.md
git commit -m "docs(knowledge): neutral framing for landmines + config-surfaces (engine facts frozen)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01CFnbyyDzMRERGWf9XeVSqq"
```

---

### Task 19: Template rename + content (2 required blocks + optional Notes + tiers)

**Files:**
- Rename: `agents/templates/recon_requirements_template.md` -> `agents/templates/etl_requirements_template.md`
- Modify: content of the renamed template; `agents/examples/README.md` (template reference)
- Test: `tests/agents/tools/test_etl_template.py` (CREATE)

**Interfaces:**
- Produces: `agents/templates/etl_requirements_template.md` documenting 2 required blocks (`Inputs and Schema`, `Transformation Rules`), 3 optional blocks (`Sample Input`, `Expected Output`, `Notes / Special Handling`), and the tier they select.

- [ ] **Step 1: Write the failing test**

Create `tests/agents/tools/test_etl_template.py`:

```python
from pathlib import Path


def test_etl_template_exists_and_recon_template_gone():
    assert Path("agents/templates/etl_requirements_template.md").exists()
    assert not Path("agents/templates/recon_requirements_template.md").exists()


def test_etl_template_documents_required_optional_blocks_and_tiers():
    text = Path("agents/templates/etl_requirements_template.md").read_text(encoding="utf-8")
    low = text.lower()
    assert "inputs and schema" in low and "transformation rules" in low
    assert "notes / special handling" in low  # the new optional block
    assert "required" in low and "optional" in low
    assert "verified" in low and "smoke" in low and "build" in low
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/agents/tools/test_etl_template.py -v`
Expected: FAIL - the file is still named `recon_requirements_template.md` and lacks the optional-blocks/tier content.

- [ ] **Step 3: Minimal implementation**

```bash
git mv agents/templates/recon_requirements_template.md agents/templates/etl_requirements_template.md
```

Rewrite `agents/templates/etl_requirements_template.md`:
- Title `# ETL Requirements Template`.
- State the two REQUIRED Heading-1 blocks: `Inputs and Schema`, `Transformation Rules`.
- State the three OPTIONAL Heading-1 blocks and which tier each selects:
  - `Sample Input` + `Expected Output` (with rows) -> `verified`.
  - `Sample Input` only -> `smoke`.
  - neither -> `build`.
- Add a `## Notes / Special Handling` (optional) section: free prose captured verbatim into `notes` and folded into rules by the doc-interpreter.
- Keep the two parser rules (single-line cells; English Heading 1/2 styles).
- Keep the `Sample Input` / `Expected Output` table shapes (Heading-2 per source/output; `*`-suffixed composite-key columns) and note that a header-only Expected output is declared-empty (`graded: false`).
- Update `Kind` enum wording to general ETL (`join, schema_validate, filter, aggregate, sort, derive`).

Update `agents/examples/README.md`: change the template path reference `agents/templates/recon_requirements_template.md` -> `agents/templates/etl_requirements_template.md` (the fuller README rewrite is Task 20).

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/agents/tools/test_etl_template.py tests/agents/tools/test_no_recon_string.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add agents/templates/etl_requirements_template.md agents/examples/README.md tests/agents/tools/test_etl_template.py
git rm --cached agents/templates/recon_requirements_template.md 2>/dev/null || true
git commit -m "docs(template): rename to etl_requirements_template + 2 required/3 optional blocks + tiers

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01CFnbyyDzMRERGWf9XeVSqq"
```

---

### Task 20: Example docx regenerate (neutral) + generator script + README

**Files:**
- Create: `agents/examples/gen_sample_etl_requirements.py`
- Rename (regenerate): `agents/examples/sample_enrichment_requirements.docx` -> `agents/examples/sample_etl_requirements.docx`
- Modify: `agents/examples/README.md`
- Test: `tests/agents/tools/test_example_docx.py` (CREATE)

**Interfaces:**
- Consumes: `agents.tools.extract_doc.extract_doc` (round-trips the generated docx).
- Produces: a committed, deterministic generator that emits a conformant `verified`-tier example with a `Notes / Special Handling` block; `extract_doc` on it returns `tier == "verified"` and non-empty `notes`.

- [ ] **Step 1: Write the failing test**

Create `tests/agents/tools/test_example_docx.py`:

```python
from pathlib import Path

from agents.tools.extract_doc import extract_doc

_DOCX = Path("agents/examples/sample_etl_requirements.docx")


def test_example_docx_present_and_old_gone():
    assert _DOCX.exists()
    assert not Path("agents/examples/sample_enrichment_requirements.docx").exists()


def test_example_docx_is_verified_tier_with_notes():
    result = extract_doc(str(_DOCX))
    assert result.conformance.ok is True
    assert result.tier == "verified"
    assert result.notes != ""  # exercises the Notes / Special Handling capture
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/agents/tools/test_example_docx.py -v`
Expected: FAIL - the new docx does not exist yet.

- [ ] **Step 3: Minimal implementation**

Create `agents/examples/gen_sample_etl_requirements.py` (deterministic python-docx generator):

```python
"""Deterministically generate the neutral ETL example requirements .docx.

Run: python -m agents.examples.gen_sample_etl_requirements
Regenerate rather than hand-editing the tables when the schema changes.
"""
from pathlib import Path

from docx import Document

_OUT = Path("agents/examples/sample_etl_requirements.docx")


def _table(doc, header, rows):
    t = doc.add_table(rows=1, cols=len(header))
    for i, h in enumerate(header):
        t.rows[0].cells[i].text = h
    for r in rows:
        cells = t.add_row().cells
        for i, v in enumerate(r):
            cells[i].text = v
    return t


def build():
    doc = Document()
    doc.add_heading("Inputs and Schema", level=1)
    _table(doc, ["Source", "Column", "Type", "Nullable", "Key"], [
        ["transactions", "txn_id", "str", "false", "true"],
        ["transactions", "counterparty_code", "str", "true", "false"],
        ["transactions", "amount", "str", "true", "false"],
        ["counterparties", "counterparty_code", "str", "false", "true"],
        ["counterparties", "counterparty_name", "str", "true", "false"],
    ])
    doc.add_heading("Transformation Rules", level=1)
    _table(doc, ["ID", "Kind", "Description"], [
        ["R1", "join", "add counterparty_name from counterparties on counterparty_code (left join, keep all txns)"],
        ["R2", "sort", "order the result by txn_id ascending"],
    ])
    doc.add_heading("Sample Input", level=1)
    doc.add_heading("transactions", level=2)
    _table(doc, ["txn_id", "counterparty_code", "amount"], [
        ["T001", "CP1", "100"], ["T002", "CP2", "200"], ["T003", "CP999", "300"],
    ])
    doc.add_heading("counterparties", level=2)
    _table(doc, ["counterparty_code", "counterparty_name"], [
        ["CP1", "Acme"], ["CP2", "Globex"],
    ])
    doc.add_heading("Expected Output", level=1)
    doc.add_heading("enriched", level=2)
    _table(doc, ["txn_id*", "counterparty_code", "amount", "counterparty_name"], [
        ["T001", "CP1", "100", "Acme"],
        ["T002", "CP2", "200", "Globex"],
        ["T003", "CP999", "300", ""],   # no counterparty match -> null enrichment, row kept
    ])
    doc.add_heading("Notes / Special Handling", level=1)
    doc.add_paragraph("Keep every transaction row; an unmatched counterparty_code leaves counterparty_name empty.")
    doc.add_paragraph("counterparty_code is case-sensitive.")
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(_OUT))


if __name__ == "__main__":
    build()
```

Regenerate and remove the old docx:

```bash
python -m agents.examples.gen_sample_etl_requirements
git rm agents/examples/sample_enrichment_requirements.docx
```

Rewrite `agents/examples/README.md`: neutral title/framing (general ETL join-enrich example), reference `agents/examples/sample_etl_requirements.docx`, the `agents/templates/etl_requirements_template.md` template, and `agents/examples/gen_sample_etl_requirements.py` as the generator; describe the `Notes / Special Handling` block; drop the SmartStream/recon-specific framing.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/agents/tools/test_example_docx.py tests/agents/tools/test_no_recon_string.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add agents/examples/gen_sample_etl_requirements.py agents/examples/sample_etl_requirements.docx agents/examples/README.md tests/agents/tools/test_example_docx.py
git rm --cached agents/examples/sample_enrichment_requirements.docx 2>/dev/null || true
git commit -m "docs(examples): neutral ETL example docx + committed generator + README

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01CFnbyyDzMRERGWf9XeVSqq"
```

---

## Final verification (after Task 20)

- [ ] Run the full agent-tool suite:
  `python -m pytest tests/agents/ -v`
  Expected: all PASS (java-marked tests skip without a JVM, pass with one).
- [ ] Confirm the agent/skill gate:
  `python -c "from agents.tools.validate_agents import validate_tree; print(validate_tree('.github/agents','.github/skills'))"`
  Expected: `[]`.
- [ ] Confirm no residual framing:
  `grep -rn "dataprep-recon" .github agents | grep -v __pycache__` -> no output.
- [ ] Confirm the engine/converter coverage gate is untouched by this work (no `src/` change): run the Phase-14 gate command from CLAUDE.md if a full regression is desired; expected unchanged `PASS`.

---

## Self-review notes (spec coverage)

- Spec 3 (tiers) -> Task 4 (`_compute_tier`), Task 8/9 (grade vs smoke), Task 15 (orchestrator branching), Task 19/20 (template + example).
- Spec 4.1 (extract_doc v2) -> Tasks 1-4.
- Spec 4.2 (materialize_golden) -> Tasks 5-7 (root inputs, golden/ expected+manifest, RFC-4180 quoting, no `component`, emits tier).
- Spec 4.3 (run_and_validate grade path + smoke + string scrub) -> Tasks 8-9.
- Spec 4.4 (output plumbing + assembler/input contracts + orchestrator step-0) -> Tasks 8, 12, 13, 14, 15.
- Spec 4.5 (doc-interpreter consumes all intent + note tagging) -> Task 12.
- Spec 4.6 (system-wide de-bias; security carve-out) -> Tasks 9 (string-only), 10-11 (skill), 12-16 (agents), 17-20 (platform/knowledge/template/examples).
- Spec 6 (golden fixture migrates content) -> Task 8.
- Spec 7 (two load-bearing contracts + CSV round-trip test) -> Task 6 (embedded-`;` round-trip), Task 8 (id==name clear error), Task 13/14 (agent contracts), Task 10 (envelope teaches both).
