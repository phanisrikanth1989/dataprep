# Real-BRD Doc-Normalizer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a second, LLM-driven front door that ingests an arbitrary real BRD (STTM sheets, prose, screenshots, sibling CSVs) and emits a shape-conforming `extract_doc.json`, so the entire downstream pipeline and the engine (`src/`) stay untouched.

**Architecture:** A deterministic **exploder** turns the docx into an inventory + jailed extracted files; a vision-capable **doc-normalizer agent** emits intent + candidate data locations (`normalizer_proposal.json`); a deterministic **validator/merge** resolves handles, derives the provenance rung from the handle type, copies exact bytes, and enforces the oracle-safety tier cap. The tier cap is made deterministic at the grading boundary by a small rung-aware change to `materialize_golden`. Everything after `extract_doc.json` is unchanged.

**Tech Stack:** Python 3.12+, `python-docx` (docx parsing), `openpyxl` (Phase 2 xlsx), stdlib `zipfile`/`csv`/`pathlib`/`json`. New tools live in `agents/tools/`; agents in `.github/agents/`. NO engine (`src/`) changes.

## Global Constraints

- **NO changes to `src/`** (engine). The only tooling change to an existing file is a small rung-aware tweak to `agents/tools/materialize_golden.py`. New code is new files under `agents/tools/` + one new `.github/agents/*.agent.md`.
- **Model-agnostic:** NO `model:` key in any `.agent.md` (`validate_agents` enforces).
- **ASCII-only** in code, logs, and authored markdown (RHEL-clean). No emojis/unicode.
- **CLIs create their parent dirs** before writing (`Path(out).parent.mkdir(parents=True, exist_ok=True)`), matching `extract_doc --out` / `materialize_golden`.
- **VS Code 1.122 tool IDs** (valid only): `read`, `edit`, `search/codebase`, `agent/runSubagent`, `execute/runInTerminal`, `execute/getTerminalOutput`. Never use `read/files`, `edit/files`, `run/terminal`, `runCommands`.
- **Discovery-phase testing:** NO golden-doc suite. Write tests ONLY for the deterministic silent-corruption guardrails (the rung-aware tier cap; the path jails; the tier computation). Verify the rest by manual end-to-end runs against a generated sample real-BRD docx.
- **Reuse the existing jail:** `materialize_golden._safe_name` (validator, RAISES) and `_jailed` (realpath + `is_relative_to`). `_safe_name` is a VALIDATOR, not a reducer -- reduce to a basename first, then validate.
- **Oracle-exactness invariant (load-bearing):** the LLM never supplies gradable bytes on rungs 1-2, and a rung-3 (LLM/unverified) oracle can NEVER be graded. This is enforced deterministically by the validator's rung derivation + the rung-aware `materialize_golden`.
- **Git:** branch `feature/real-brd-ingestion` (never `main`); stage files by name; commit per task; confirm before push/PR.

Full design rationale: `docs/superpowers/specs/2026-07-08-real-brd-doc-normalizer-design.md`.

---

## Artifact-bus contracts (locked interfaces)

These JSON shapes are the contracts between tasks. All under `agents/work/<job>/`.

**`exploder_inventory.json`** (exploder -> validator):
```json
{
  "handles": [
    {"id": "table:0", "type": "table", "columns": ["Trade ID", "Amount"], "n_rows": 3},
    {"id": "image:0", "type": "image", "path": "_explode/image_0.png"},
    {"id": "embed:accounts.xlsx", "type": "embed", "path": "_explode/accounts.xlsx"},
    {"id": "sibling:trades.csv", "type": "sibling", "path": "_explode/sibling/trades.csv",
     "csv_dialect": {"delimiter": ",", "quotechar": "\""}},
    {"id": "para:0", "type": "prose", "text_ref": "block-range 0-4"}
  ],
  "prose_text": "full concatenated prose, verbatim",
  "purity": {"has_images": true, "has_embeds": true, "has_headingless_content": false,
             "conformance_fail": true}
}
```
- Table cells are exact strings; blank/duplicate headers are index-suffixed (`""` -> `col_1`, dup `id` -> `id`, `id_2`).
- `type` in `table | image | embed | sibling | prose`. Only `table`/`embed`/`sibling` can carry oracle data.

**`normalizer_proposal.json`** (normalizer agent -> validator):
```json
{
  "sources_schema": {"trades": [{"name": "trade_id", "type": "str", "nullable": false, "key": true}]},
  "rules": [{"id": "R1", "kind": "join", "description": "enrich trades with account name"}],
  "notes": "verbatim prose",
  "extra_sections": {"Glossary": {"prose": "...", "tables": []}},
  "output_keys": {"result": ["trade_id"]},
  "located": {
    "sample_input": {"trades": ["sibling:trades.csv", "table:0"]},
    "expected_output": {"result": ["table:2"]}
  },
  "coverage_map": [{"handle": "table:0", "disposition": "extracted_to", "refs": ["trades.trade_id"]}],
  "low_confidence": []
}
```
- `located.*.<name>` is a LIST of candidate handles (alternatives). Rung hints are optional and advisory.

**`extract_doc.json`** (validator output): the existing shape (see `extract_doc.py:ExtractResult` / `to_dict`) PLUS additive `provenance`, `coverage_map`, `extraction`, `normalization`. `provenance[name] = {"rung": "1"|"2"|"3a"|"3b", "handle": "<id>"}`. **`rung` is ALWAYS a string** (matches `_derive_rung`'s return, `_compute_tier`'s membership test, and the rung-aware `materialize_golden`). The validator MUST emit a `provenance` entry for every source AND every graded `expected_output` (a graded output with no provenance entry is a hard error -> `needs_human`, never a silent grade).

**`normalizer_feedback.json`** (validator -> orchestrator -> normalizer, on shape error): `{"errors": [{"pointer": "rules[2].kind", "why": "...", "fix": "..."}]}`.

---

## File structure

- Create `agents/tools/docx_purity.py` -- pre-branch purity scanner (Task 1).
- Create `agents/tools/explode_doc.py` -- the exploder (Tasks 2-4).
- Create `agents/tools/normalize_validate.py` -- the validator/merge CLI (Tasks 6-10).
- Create `.github/agents/doc-normalizer.agent.md` -- the vision agent (Task 5).
- Modify `agents/tools/materialize_golden.py` -- rung-aware grading cap (Task 11).
- Modify `.github/agents/etl-orchestrator.agent.md` -- step-0 real-BRD branch + extraction gate + shape-repair loop + extended final gate (Task 12).
- Create `agents/examples/gen_sample_real_brd.py` -- generator for a messy sample BRD for manual E2E (Task 13).
- Tests (guardrails only): `tests/agents/test_docx_purity.py`, `test_explode_jail.py`, `test_normalize_tier.py`, `test_materialize_rung_aware.py`.

---

# PHASE 1 -- Minimal real-BRD ingestion (CSV + Word tables), with the deterministic oracle-safety cap

Phase-1 scope: CSV siblings/embeds and clean Word tables are the exact rungs (1 and 2); images/prose are rung-3a (transcribed, capped at smoke); **xlsx is deferred -- in Phase 1 an xlsx-typed handle located as oracle data resolves to `needs_human`** (Phase 2 adds the round-trip reader). This gets a real BRD flowing end-to-end with the safety invariant, minimally.

### Task 1: `docx_purity` pre-branch scanner

**Files:**
- Create: `agents/tools/docx_purity.py`
- Test: `tests/agents/test_docx_purity.py`

**Interfaces:**
- Produces: `scan_purity(path: str) -> dict` returning `{"has_images": bool, "has_embeds": bool, "has_headingless_content": bool, "conformance_fail": bool, "tripped": bool}`. `tripped = has_images or has_embeds or has_headingless_content or conformance_fail`. CLI: `python -m agents.tools.docx_purity <docx> [--out FILE]` prints/writes the dict; exit 0.

- [ ] **Step 1: Write the scanner.** Open the docx as a zip; `has_images = any name.startswith("word/media/")`; `has_embeds = any name.startswith("word/embeddings/")`. For `has_headingless_content`: reuse `extract_doc._read_sections` -- if the two REQUIRED_BLOCKS are NOT both present as H1s, set True (real BRD). For `conformance_fail`: call `extract_doc.extract_doc(path, raise_on_error=False)` and read `.conformance.ok`; `conformance_fail = not ok`. Do NOT reuse this as a completeness check -- it is only a trip signal. Create `--out` parent dir before writing.

```python
"""Deterministic pre-branch purity scan: does this docx have content outside the
template parser's lossless envelope? Trip -> the orchestrator routes to the
real-BRD normalizer (or pauses for human opt-in). Never modifies extract_doc."""
from __future__ import annotations
import zipfile
from pathlib import Path
from agents.tools.extract_doc import extract_doc, REQUIRED_BLOCKS, _read_sections
from docx import Document


def scan_purity(path: str) -> dict:
    names = zipfile.ZipFile(path).namelist()
    has_images = any(n.startswith("word/media/") for n in names)
    has_embeds = any(n.startswith("word/embeddings/") for n in names)
    sections = _read_sections(Document(path))
    has_headingless = not all(b in sections for b in REQUIRED_BLOCKS)
    result = extract_doc(path, raise_on_error=False)
    conformance_fail = not result.conformance.ok
    tripped = has_images or has_embeds or has_headingless or conformance_fail
    return {"has_images": has_images, "has_embeds": has_embeds,
            "has_headingless_content": has_headingless,
            "conformance_fail": conformance_fail, "tripped": tripped}
```
(Add a `main(argv)` CLI mirroring `extract_doc.main`'s `--out` + parent-dir-mkdir pattern.)

- [ ] **Step 2: Write the guardrail tests.** (a) The existing template docx must NOT trip on headingless/conformance (satisfiable now). (b) The image trip is tested with an inline image-bearing docx built in the test (no dependency on Task 13's fixture).

```python
import base64, io
from docx import Document
from agents.tools.docx_purity import scan_purity

# 1x1 transparent PNG
_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==")

def test_template_docx_not_headingless():
    r = scan_purity("agents/examples/sample_etl_requirements.docx")
    assert r["has_headingless_content"] is False
    assert r["conformance_fail"] is False

def test_image_docx_trips(tmp_path):
    doc = Document()
    doc.add_paragraph("prose only, no template headings")
    doc.add_picture(io.BytesIO(_PNG))
    p = tmp_path / "img.docx"; doc.save(p)
    r = scan_purity(str(p))
    assert r["has_images"] is True and r["tripped"] is True
```

- [ ] **Step 3: Run.** `python -m pytest tests/agents/test_docx_purity.py -v` -> PASS.
- [ ] **Step 4: Commit.** `git add agents/tools/docx_purity.py tests/agents/test_docx_purity.py && git commit -m "feat(normalizer): docx_purity pre-branch scanner"`

---

### Task 2: Exploder -- inventory the full block stream (no extraction yet)

**Files:**
- Create: `agents/tools/explode_doc.py`
- Test: (manual E2E later; no unit test -- pure python-docx traversal)

**Interfaces:**
- Produces: `_inventory_blocks(doc) -> list[dict]` -- one handle per table (`table:N`, with disambiguated `columns` + `n_rows`) and grouped prose block-ranges (`para:N`). Reuses `extract_doc._iter_block_items`, `_table_records`. Table headers are disambiguated via `_dedup_headers(header) -> list[str]` (blank -> `col_<i>`; duplicate -> suffix `_2`, `_3`).

- [ ] **Step 1: Write `_dedup_headers` and `_inventory_blocks`.** For each table, build `columns = _dedup_headers([c.text.strip() for c in row0.cells])`; store the exact cell-strings too (for rung-2 later). Walk `_iter_block_items`; group consecutive paragraphs into `para:N` block-ranges; number tables `table:0,1,...`. Never `dict(zip(header,row))` with a raw header.

```python
def _dedup_headers(header: list[str]) -> list[str]:
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
```

- [ ] **Step 2: Commit.** `git add agents/tools/explode_doc.py && git commit -m "feat(normalizer): exploder block-stream inventory + header disambiguation"`

---

### Task 3: Exploder -- jailed extraction of images + embedded/sibling files (with zip-slip + zip-bomb guards)

**Files:**
- Modify: `agents/tools/explode_doc.py`
- Test: `tests/agents/test_explode_jail.py`

**Interfaces:**
- Produces: `_extract_media(zippath, out_dir) -> list[dict]` (image/embed handles with jailed paths); `_inventory_siblings(docx_dir, out_dir) -> list[dict]` (sibling CSVs from the docx's own directory). Reduce-then-validate: `_safe_basename(member) -> str` using `PurePosixPath(member).name`, strip backslash components, then `materialize_golden._safe_name` on the basename; write via `_jailed`. Enforce a decompression bound (`MAX_EXTRACT_BYTES`, per-entry cap, count cap) checked against `ZipInfo.file_size` BEFORE extracting.

- [ ] **Step 1: Write `_safe_basename` + jailed extraction + the decompression bound.**

```python
from pathlib import PurePosixPath, Path
from agents.tools.materialize_golden import _safe_name, _jailed

MAX_EXTRACT_BYTES = 50 * 1024 * 1024
MAX_ENTRY_BYTES = 25 * 1024 * 1024
MAX_MEMBERS = 500

def _safe_basename(member: str) -> str:
    base = PurePosixPath(member.replace("\\", "/")).name
    return _safe_name(base)  # RAISES on empty/./..; base has no separators by construction
```
Before extracting each member: `if info.file_size > MAX_ENTRY_BYTES or total + info.file_size > MAX_EXTRACT_BYTES: raise ConformanceError(...)`. Disambiguate colliding basenames with an index suffix.

- [ ] **Step 2: Write the jail guardrail test.** A crafted zip member (relative `../` OR absolute) must be REDUCED to a bare basename inside the jail (reduce-then-validate never escapes); a member that reduces to an empty/`.`/`..` basename must RAISE.

```python
import pytest
from agents.tools.explode_doc import _safe_basename, _resolve_sibling

def test_zip_slip_and_absolute_reduced_to_basename():
    assert _safe_basename("word/media/../../evil.png") == "evil.png"
    assert _safe_basename("/abs/evil.png") == "evil.png"       # absolute -> basename, does NOT raise

def test_unsafe_basename_raises():
    with pytest.raises(ValueError):
        _safe_basename("..")                                    # reduces to ".." -> _safe_name raises

def test_sibling_read_rejects_escape(tmp_path):
    with pytest.raises(ValueError):
        _resolve_sibling(str(tmp_path), "../secret.csv")        # read-jail: escape rejected
```

- [ ] **Step 3: Write `_resolve_sibling` (read-jail).** `base = realpath(docx_dir)`; reject absolute or `..` in the reference; `target = realpath(base / name)`; require `target.is_relative_to(base)`; else `raise ValueError`.

- [ ] **Step 4: Run + commit.** `pytest tests/agents/test_explode_jail.py -v` -> PASS. `git add agents/tools/explode_doc.py tests/agents/test_explode_jail.py && git commit -m "feat(normalizer): jailed extraction, zip-slip/zip-bomb + sibling read-jail"`

---

### Task 4: Exploder -- CSV dialect recording + `explode_doc.json` CLI

**Files:**
- Modify: `agents/tools/explode_doc.py`

**Interfaces:**
- Produces: `explode(docx_path, out_dir) -> dict` (the full inventory) and CLI `python -m agents.tools.explode_doc <docx> --out-dir agents/work/<job>/_explode --inventory agents/work/<job>/exploder_inventory.json`. Records `csv_dialect` per CSV via `csv.Sniffer().sniff(sample)`; a CSV whose dialect cannot be sniffed gets `csv_dialect: null` (NOT rung-1 eligible downstream).

- [ ] **Step 1: Wire `explode()`** to combine Tasks 2-3 + dialect sniff + the `docx_purity.scan_purity` result into one `exploder_inventory.json`. Create parent dirs. Emit `prose_text` verbatim.
- [ ] **Step 2: Manual smoke.** Run against `agents/examples/sample_etl_requirements.docx`; confirm `exploder_inventory.json` lists the schema/rules tables as `table:N` with disambiguated columns. (No unit test -- E2E covers it.)
- [ ] **Step 3: Commit.** `git add agents/tools/explode_doc.py && git commit -m "feat(normalizer): exploder CLI + CSV dialect recording"`

---

### Task 5: The `doc-normalizer` agent

**Files:**
- Create: `.github/agents/doc-normalizer.agent.md`

**Interfaces:**
- Consumes: `exploder_inventory.json` + the jailed files (reads text via `read`, PNGs via native vision). Produces: `normalizer_proposal.json` (the contract above). Tools: `read`, `edit`, `search/codebase`. NO `model:` key. `user-invocable: false`.

- [ ] **Step 1: Author the agent markdown.** Full content (ASCII, model-agnostic). It must: **on a re-invoke, FIRST read `agents/work/<job>/normalizer_feedback.json` if present and apply each `errors[].{pointer,why,fix}` before regenerating** (mirrors the doc-interpreter feedback contract; without this the shape-repair loop burns all 3 iterations with no directed correction); read the inventory; for every handle emit a `coverage_map` entry (`extracted_to` with real refs / `irrelevant` / `could_not_interpret`); emit Bucket-1 intent in the exact `extract_doc.json` field shapes; for each source/output emit a LIST of candidate handles in `located`; author values ONLY for image/prose handles; never invent a path not in the inventory; flag low-confidence rather than fabricate. Include the "locate, do not author on data files" discipline and the coverage-map schema verbatim from the spec Section 9.

- [ ] **Step 2: Validate structure.** `validate_agents` has no `__main__` CLI, so exercise the library directly: `python -c "from agents.tools.validate_agents import validate_tree; e=validate_tree('.github/agents','.github/skills'); assert not e, e"` -> no error (no `model:` key, valid tools list). (Note: `validate_tree` flags only refs to UNKNOWN agents, not missing ones -- see Task 12.)
- [ ] **Step 3: Commit.** `git add .github/agents/doc-normalizer.agent.md && git commit -m "feat(normalizer): doc-normalizer vision agent"`

---

### Task 6: Validator -- resolve handles + derive rung from handle type

**Files:**
- Create: `agents/tools/normalize_validate.py`
- Test: `tests/agents/test_normalize_tier.py` (started here; extended in Task 9)

**Interfaces:**
- Produces: `_resolve(handle_id, inventory) -> dict | None`; `_derive_rung(handle_id, inventory) -> "1"|"2"|"3a"|"needs_human"`. Phase-1 rung map: a handle whose path ends `.xlsx`/`.xls` (embed OR sibling) -> `"needs_human"` (Phase 2 adds the xlsx reader); a CSV handle (sibling/embed `.csv`) with non-null `csv_dialect` -> "1"; a `table` handle -> "2"; an `image`/`prose` handle -> "3a". **The catch-all default is `"needs_human"`, never a silent "1"/"2"** -- an unrecognized handle type can never be graded. A hint the type cannot honor -> `needs_human`.

- [ ] **Step 1: Write `_resolve` + `_derive_rung`.** `_resolve` returns the inventory handle or None (unresolved). `_derive_rung` reads only the handle type + dialect presence; the LLM's hint is ignored for authority.
- [ ] **Step 2: Write the rung-derivation test.**

```python
def test_rung_derived_from_type_not_hint():
    inv = {"handles": [{"id": "image:0", "type": "image"},
                       {"id": "sibling:t.csv", "type": "sibling", "csv_dialect": {"delimiter": ","}}]}
    assert _derive_rung("image:0", inv) == "3a"      # even if the LLM hinted rung-2
    assert _derive_rung("sibling:t.csv", inv) == "1"
```

- [ ] **Step 3: Run + commit.** `pytest tests/agents/test_normalize_tier.py -v` -> PASS. `git add agents/tools/normalize_validate.py tests/agents/test_normalize_tier.py && git commit -m "feat(normalizer): validator handle-resolve + rung derivation"`

---

### Task 7: Validator -- exact merge (rung 1 CSV, rung 2 table, rung 3a transcribed) + column-order reconciliation

**Files:**
- Modify: `agents/tools/normalize_validate.py`

**Interfaces:**
- Produces: `_merge_source(name, candidates, proposal, inventory) -> (rows, provenance)`. Rung-1: read the CSV with the recorded dialect, first row = header, cells as `str`. Rung-2: the table's exact cell-strings. Rung-3a: the LLM rows from `proposal` (stamped). Then `_reorder_to_schema(rows, schema_cols) -> rows` so the row-dict key order MATCHES `sources_schema` order (the engine binds positionally -- `file_input_delimited.py:462-469`). A name present in a different order is REORDERED; an unreconcilable name/count mismatch -> raise -> `needs_human`.

- [ ] **Step 1: Write the readers + `_reorder_to_schema`.** Reconcile by exact match, then normalized (case/space/punct fold), then positional if counts match; else raise `NeedsHuman`. Reorder the emitted `sample_input` columns to schema order. For `expected_output`, emit the header in the flow output name-space (Phase 1: use the schema/rule-derived output names the normalizer proposed for that output; carry a name-map if they differ from the source header).
- [ ] **Step 2: Manual check** with a hand-made inventory fixture where the CSV columns are in reverse order vs the schema; confirm the emitted rows are reordered to schema order. (E2E covers the full path.)
- [ ] **Step 3: Commit.** `git add agents/tools/normalize_validate.py && git commit -m "feat(normalizer): exact merge + positional column-order reconciliation"`

---

### Task 8: Validator -- role/content-distinctness guard + name normalization + output_keys + conformance

**Files:**
- Modify: `agents/tools/normalize_validate.py`

**Interfaces:**
- Produces: `_distinctness(sample_input, expected_output) -> set[str]` (names of graded outputs to degrade because their bytes == a sample source's bytes, OR a handle bound to two roles); `_safe_output_name(name) -> str` (reproducible sanitizer + collision index suffix, applied across the co-key set); `_verify_output_keys(name, keys, expected_rows) -> list` (COMPOSITE tuple-uniqueness; else `[]` + low_confidence); `conformance = {"ok": True, "missing_blocks": [], "parse_errors": []}` on shape success.

- [ ] **Step 1: Write the four helpers.** `_distinctness` compares merged bytes (header+rows) exactly. `_safe_output_name` folds illegal chars to `_`, collapses repeats, strips edges, then disambiguates collisions with an index suffix consistently across `sources_schema`/`sample_input`/`expected_output`/`output_keys`/`provenance`. `_verify_output_keys` checks `len({tuple(r[c] for c in keys) for r in rows}) == len(rows)`.
- [ ] **Step 2: Commit.** `git add agents/tools/normalize_validate.py && git commit -m "feat(normalizer): distinctness guard + name/output_keys/conformance"`

---

### Task 9: Validator -- tier computation + rung-aware derived_facts + assemble `extract_doc.json`

**Files:**
- Modify: `agents/tools/normalize_validate.py`
- Test: `tests/agents/test_normalize_tier.py` (extend)

**Interfaces:**
- Produces:
  - `_compute_tier(provenance, expected_graded, distinct_ok) -> "verified"|"smoke"|"build"` per spec Section 7 (EVERY source AND EVERY graded output rung in `{"1","2"}`, AND distinctness holds -> verified; ANY rung-3/needs_human/missing or distinctness violation -> smoke; no sample -> build).
  - `_cross_check_coverage(inventory, coverage_map, emitted) -> (unaccounted: list, unresolved: list)` -- the Section-9 completeness guard: a handle is `accounted` only if it has a `coverage_map` disposition AND (for `extracted_to`) non-empty `refs` that ALL resolve to an emitted target (schema field `<source>.<col>`, rule id, sanitized source/output name, or `extra_sections` heading). `unaccounted = {every inventory handle id} - {accounted}`.
  - `_rung_aware_facts(sample_input, provenance)` -- for a rung-3 source do NOT emit `unique:true`/`max_group_size<=1` (emit the conservative ambiguity-raising value).
  - `assemble(...) -> extract_doc.json dict` -- all existing fields + `provenance`/`coverage_map`/`extraction`/`normalization`. **`assemble` MUST emit a `provenance` entry for every source AND every graded `expected_output`**; a graded output with no derivable provenance is a hard error -> `extraction.status=needs_human`. It sets `extraction = {"status", "unaccounted", "unresolved", "low_confidence"}` with `status=needs_human` when `unaccounted` OR `unresolved` is non-empty OR a graded output lacks provenance, else `status=ok`.

- [ ] **Step 1: Write `_compute_tier` + `_cross_check_coverage` + `_rung_aware_facts` + `assemble`** (with the provenance-per-graded-output and unaccounted-hard-blocker rules above).
- [ ] **Step 2: Write the tier guardrail test (the load-bearing invariant).**

```python
def test_rung3_expected_caps_verified_to_smoke():
    prov = {"trades": {"rung": "1"}, "result": {"rung": "3a"}}   # answer key transcribed
    assert _compute_tier(prov, expected_graded=["result"], distinct_ok=True) == "smoke"

def test_all_exact_earns_verified():
    prov = {"trades": {"rung": "1"}, "result": {"rung": "2"}}
    assert _compute_tier(prov, expected_graded=["result"], distinct_ok=True) == "verified"

def test_distinctness_violation_degrades():
    prov = {"trades": {"rung": "1"}, "result": {"rung": "2"}}
    assert _compute_tier(prov, expected_graded=["result"], distinct_ok=False) == "smoke"
```

- [ ] **Step 3: Run + commit.** `pytest tests/agents/test_normalize_tier.py -v` -> PASS. `git add agents/tools/normalize_validate.py tests/agents/test_normalize_tier.py && git commit -m "feat(normalizer): tier computation + rung-aware derived_facts + assemble"`

---

### Task 10: Validator -- shape-validation + CLI (emit extract_doc.json or normalizer_feedback.json)

**Files:**
- Modify: `agents/tools/normalize_validate.py`

**Interfaces:**
- Produces: `validate(inventory_path, proposal_path, out_path) -> status` in `ok | shape_error | needs_human`; CLI `python -m agents.tools.normalize_validate --inventory ... --proposal ... --out agents/work/<job>/extract_doc.json --feedback agents/work/<job>/normalizer_feedback.json`. On `shape_error` write feedback + return exit 3; on `needs_human` write `extraction.status=needs_human` into a partial extract_doc.json + exit 4; on ok write extract_doc.json + exit 0.

- [ ] **Step 1: Write the shape predicate** (enumerated: every rule has a valid kind; every source has >=1 column; located names match schema/output names; every located candidate resolves; an `extracted_to` coverage entry has non-empty refs that resolve = `shape_error`). Classify failures shape_error vs needs_human vs soft. **Wire the Section-9 coverage hard-blocker:** call `_cross_check_coverage` (Task 9); if `extraction.status == needs_human` (non-empty `unaccounted`/`unresolved`, or a graded output missing provenance), the CLI writes the partial extract_doc.json with that `extraction` block and exits 4 (the orchestrator's extraction gate keys on this). A `shape_error` (empty/unresolvable `extracted_to` refs) writes `normalizer_feedback.json` and exits 3.
- [ ] **Step 2: Write the CLI** (create parent dirs; ASCII logs).
- [ ] **Step 3: Commit.** `git add agents/tools/normalize_validate.py && git commit -m "feat(normalizer): shape validation + validator CLI"`

---

### Task 11: Rung-aware `materialize_golden` (the deterministic tier cap)

**Files:**
- Modify: `agents/tools/materialize_golden.py:89-111` (`materialize_expected`)
- Test: `tests/agents/test_materialize_rung_aware.py`

**Interfaces:**
- Consumes: the additive `provenance[name].rung` in `extract_doc.json`. Produces: for a rung-3 (3a/3b) output, `graded: false` and NO `<name>_expected.csv` written -- so no transcribed answer key ever sits on disk as gradable. Rung-1/2 outputs materialize exactly as today.

- [ ] **Step 1: Write the failing tests (allow-list, fail-closed -- covers rung-3 AND a MISSING provenance entry).**

```python
def test_rung3_output_not_graded_and_no_csv(tmp_path):
    extract = {"expected_output": {"result": [{"id": "1"}]},
               "output_keys": {"result": ["id"]},
               "provenance": {"result": {"rung": "3a", "handle": "image:0"}}}
    manifest = materialize_expected(extract, tmp_path)
    assert manifest["outputs"]["result"]["graded"] is False
    assert not (tmp_path / "golden" / "result_expected.csv").exists()

def test_missing_provenance_entry_on_normalizer_path_not_graded(tmp_path):
    # normalizer path (provenance key present) but NO entry for 'result' -> fail-closed, never graded
    extract = {"expected_output": {"result": [{"id": "1"}]},
               "output_keys": {"result": ["id"]},
               "provenance": {"trades": {"rung": "1", "handle": "sibling:t.csv"}}}
    manifest = materialize_expected(extract, tmp_path)
    assert manifest["outputs"]["result"]["graded"] is False
    assert not (tmp_path / "golden" / "result_expected.csv").exists()

def test_rung1_output_graded_as_today(tmp_path):
    extract = {"expected_output": {"result": [{"id": "1"}]},
               "output_keys": {"result": ["id"]},
               "provenance": {"result": {"rung": "2", "handle": "table:2"}}}
    manifest = materialize_expected(extract, tmp_path)
    assert manifest["outputs"]["result"]["graded"] is True
    assert (tmp_path / "golden" / "result_expected.csv").exists()
```

- [ ] **Step 2: Run -> FAIL** (today `graded = len(rows) > 0` grades all three). `pytest tests/agents/test_materialize_rung_aware.py -v`
- [ ] **Step 3: Implement as a fail-closed ALLOW-LIST (not a deny-list).** In `materialize_expected`, branch on the presence of the top-level `provenance` KEY (the template path via `extract_doc.to_dict` emits no such key -- verified `extract_doc.py:335-344,444-447`):

```python
prov = extract.get("provenance")
if prov is None:                                  # template path -> unchanged
    graded = len(rows) > 0
else:                                             # normalizer path -> fail-closed allow-list
    rung = str(prov.get(name, {}).get("rung"))    # missing entry -> "None" -> not in the set
    graded = len(rows) > 0 and rung in ("1", "2")
```
Write the `<name>_expected.csv` ONLY when `graded`. A missing entry, `3a`/`3b`, `needs_human`, or any unknown token all fail to `graded:false`. (`str(rung)` also absorbs the int-vs-string rung question safely.)

- [ ] **Step 4: Run -> PASS** (all three), and confirm the existing `materialize_golden` tests still pass (`pytest tests/agents/ -k materialize -v`).
- [ ] **Step 5: Commit.** `git add agents/tools/materialize_golden.py tests/agents/test_materialize_rung_aware.py && git commit -m "feat(normalizer): rung-aware materialize_golden -- deterministic tier cap"`

---

### Task 12: Orchestrator step-0 real-BRD branch + extraction gate + shape-repair loop + extended final gate

**Files:**
- Modify: `.github/agents/etl-orchestrator.agent.md`

**Interfaces:**
- Consumes: all Phase-1 tools. Produces: the real-BRD step-0 sequence and the two new control loops, in the orchestrator's prose.

- [ ] **Step 1: Edit step 0.** Add: run `docx_purity`; if `tripped` and not real-BRD mode, PAUSE for human opt-in. In real-BRD mode: `mkdir -p` the work dir; run `explode_doc`; `#runSubagent doc-normalizer`; run `normalize_validate`. On exit 3 (shape_error), re-run the normalizer with `normalizer_feedback.json` up to 3 times then human. On exit 4 (needs_human) or `extraction.status=needs_human`, PAUSE at the extraction gate showing the coverage map + unaccounted/low-confidence. On exit 0, proceed to `materialize_golden` exactly as today (it is now rung-aware).
- [ ] **Step 2: Add `doc-normalizer` to the orchestrator's `agents:` frontmatter allowlist** (`.github/agents/etl-orchestrator.agent.md:13-19`, currently the six specialists). Under VS Code 1.122 native subagents this `agents:` list is the spawn allowlist -- `#runSubagent doc-normalizer` cannot dispatch unless `- doc-normalizer` is listed. IMPORTANT: `validate_tree` does NOT catch a MISSING entry (it only flags refs to UNKNOWN agents, `validate_agents.py:104-105`), so this is easy to forget and green-passes anyway -- the Task 13 E2E dispatch is the real check. `doc-normalizer` (created in Task 5) is a known agent, so adding it keeps `validate_tree` green.
- [ ] **Step 3: Extend Safety-net-3 (final gate) presentation** to also print the `tier` + per-source/output `provenance` rung + role-binding + coverage-map disposition summary + low_confidence (additive; surface-not-block).
- [ ] **Step 4: Validate + commit.** `python -c "from agents.tools.validate_agents import validate_tree; e=validate_tree('.github/agents','.github/skills'); assert not e, e"`; `git add .github/agents/etl-orchestrator.agent.md && git commit -m "feat(normalizer): orchestrator real-BRD step-0 branch + extraction gate"`

---

### Task 13: Generate a sample real-BRD + manual end-to-end verification

**Files:**
- Create: `agents/examples/gen_sample_real_brd.py` (+ generated `sample_real_brd.docx` + a sibling `trades.csv`)

- [ ] **Step 1: Write a generator** producing a MESSY docx: prose rules (no template headings), one STTM-style table with arbitrary headers, one embedded screenshot-image of a small sample table, and a sibling `trades.csv` in the same dir. ASCII content.
- [ ] **Step 2: Run the full pipeline manually** (real Copilot or CLI dry-run of the deterministic tools): `docx_purity` (tripped=True) -> `explode_doc` -> (normalizer in Copilot) -> `normalize_validate` -> confirm `extract_doc.json` is shape-valid, the sibling CSV is rung-1, the screenshot sample is rung-3a, and `tier=smoke` (because the answer key is a screenshot). Confirm `materialize_golden` writes NO expected CSV for the rung-3a output.
- [ ] **Step 3: Commit.** `git add agents/examples/gen_sample_real_brd.py && git commit -m "test(normalizer): sample real-BRD generator + manual E2E notes"`

---

# PHASE 2 -- Robustness for messy inputs (outline; detail when Phase 1 lands and we have real BRDs)

- **xlsx exact reader + round-trip assertion (rung-2 vs rung-3b):** `openpyxl` read_only, render each cell's displayed text via `number_format`, re-parse and require zero-loss equality; unproven -> rung-3b (capped at smoke). Extend the decompression bound to the extracted xlsx's own zip. Replaces the Phase-1 `xlsx -> needs_human`.
- **Consistency compare for multi-candidate sources:** when a source has both a file and a table candidate, compare (order-independent canonicalized-header multiset); file-wins; mismatch on a graded oracle -> smoke.
- **Coverage-map ref-grammar enforcement:** validate refs resolve per the Section 9 grammar; dangling `extracted_to` -> shape_error.
- **Caching key emission hardening** (still deferred to build, but ensure `normalization.model_id` is populated).

# PHASE 3 -- Deferred (do NOT build now)

- Reproducibility cache (doc+model hash, freeze-on-approval, repair-loop bypass).
- Human-promote channel (LLM-unwritable) to lift a verified rung-3 oracle.
- A golden-doc test fixture library + the deterministic-module 95% coverage push (once templates standardize).

---

## Self-Review

**Spec coverage:** exploder (T2-4), normalizer agent (T5), validator resolve/rung/merge/guards/tier/shape (T6-10), rung-aware cap (T11), orchestrator branch + gates (T12), purity scanner (T1), E2E (T13). Deferred items (xlsx, consistency, caching, human-promote, test-suite) explicitly Phase 2/3. The oracle-safety invariant is covered by T9 (tier) + T11 (grading-boundary cap) with tests.

**Placeholder scan:** no "TBD/handle edge cases" — each task names concrete helpers, signatures, and the guardrail tests carry real assertions. Larger modules (exploder, validator) are decomposed into typed helpers per task rather than one opaque blob.

**Type consistency:** `_derive_rung` returns `"1"|"2"|"3a"|"needs_human"`; `provenance[name].rung` uses the same tokens; `materialize_golden` checks `rung not in ("3a","3b")`; `_compute_tier` treats anything not in `{"1","2"}` as non-exact. Handle ids (`table:N`,`image:N`,`embed:<name>`,`sibling:<name>`,`para:N`) are consistent across inventory, proposal `located`, and `provenance.handle`.
