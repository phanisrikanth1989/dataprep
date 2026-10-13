# Design: Real-BRD Ingestion -- LLM Doc-Normalizer

- **Date:** 2026-07-08
- **Branch:** `feature/real-brd-ingestion`
- **Status:** design approved via brainstorming; hardened by THREE adversarial multi-lens spec-review
  rounds on 2026-07-08 (round 1: 21 findings; round 2: 13; round 3: 11 -- round 3 reached into the
  engine and surfaced the deterministic-enforcement and positional-binding issues folded in here).
  Reproducibility/caching deferred; test suite deferred (discovery phase).
- **Companion to:** `2026-07-07-general-etl-pipeline-builder-design.md` and the backlog
  `2026-07-03-copilot-etl-agents-backlog.md` (item B.1).
- **Next step after user review:** `superpowers:writing-plans`, then subagent build with the
  adversarial-review loop (Opus everywhere).

---

## 1. Problem and goal

The general-ETL pipeline builder is done and demoed, but its front door -- `extract_doc` -- is a
**deterministic TEMPLATE parser**: it fails closed (conformance gate, exit 2) on any document not
authored to the exact template (real STTM spreadsheets, prose BRDs, Confluence pages, screenshots of
sample data, mapping tables with arbitrary headers). The manager's one ask after the demo: accept a
**real BRD** in whatever shape it arrives.

**Goal:** add an LLM **doc-normalizer** that ingests an arbitrary requirements document and produces a
shape-conforming `extract_doc.json`. Because every downstream stage AND `materialize_golden` consume
`extract_doc.json` (the artifact-bus contract), the work is localized to the front door.

**Non-goal:** this is NOT needed for the author-to-template workflow, which already works and stays
untouched. This branch adds a second, LLM-driven front door for arbitrary existing docs.

---

## 2. The load-bearing constraint: oracle exactness is a *provenance* rule, not blindness

`sample_input` and `expected_output` in `extract_doc.json` become the **input CSVs and the test
oracle**. A silently paraphrased value (`"1,000.50"` -> `1000.5`, a dropped trailing zero, a "fixed"
typo) **corrupts the grade with nothing downstream to catch it**.

The constraint is NOT "the LLM must never see the oracle data." Under don't-minimize-egress (trusted
Citi enclave) the model may see data, and for screenshots the LLM may be the *only* thing that can read
it. The constraint is:

> **The LLM must never be the *unverified final authority* on an oracle value.**

Two failure modes fall under this; the design guards both:

- **Value corruption** -- a wrong *value* becomes the grader (LLM paraphrase, OR a lossy deterministic
  read such as an xlsx float coercion -- Section 5.3.2).
- **Role misattribution** -- exact values bound to the *wrong role* (a table used as both input and
  answer key; a lookup file swapped for the driving source; **or columns transposed because the engine
  binds positionally** -- Section 5.3.4). Exact bytes in the wrong slot grade just as wrongly.

Intent (schema, rules, notes) is fuzzy-safe-with-review; only the *data path* -- values AND their
role/column-binding -- is held to exactness. This yields the provenance ladder of Section 6.

---

## 3. Environment capabilities (probed on the Citi laptop)

The design branches on what the live Citi VS Code Copilot runtime can do. Probed empirically (not
assumed), because `validate_agents` checks tools-list structure only, not live resolution:

| Capability | Result | Consequence |
|---|---|---|
| Parse a `.docx` via a python library in the enclave terminal | CONFIRMED | the deterministic exploder pattern holds |
| Agent reads a file off disk (CSV/Excel bytes) into context | CONFIRMED | the gold oracle rung (deterministic verbatim copy) is reachable |
| Native model **vision** on images, incl. images embedded in the docx | CONFIRMED (read a 10+ node flowchart with directional arrows) | screenshots become usable *intent*; the transcribe rung is alive; image handling is an AGENT capability |
| DLP does not gut file/image content | IMPLIED | acceptable under don't-minimize-egress |

**Guard that survives the good news:** "make sense of a flowchart" is *intent* comprehension
(fuzzy-safe). Transcribing dense numeric cells with zero digit errors is a *different* task -- so
screenshot-sourced **oracle data** rides the human-verify/rung-3 path; vision makes that rung
*reachable*, it does not collapse the ladder.

**To re-confirm during the build (see Section 16):** the exact autonomous path by which an
exploder-written PNG on disk reaches an `agent/runSubagent`-spawned normalizer's vision context (this
is load-bearing for rung-3a; the fallback if unavailable is rung-3a -> `needs_human`, never a silent
drop); DLP against realistic data; the stable model-id surface (deferred cache only).

---

## 4. Architecture overview

### 4.1 Two explicit front doors, deterministic default (resolved)

Completeness -- "did we capture everything the BRD means?" -- is **irreducibly semantic and cannot be
verified deterministically**. A deterministic layer verifies only (a) **shape** (is the JSON runnable)
and (b) **oracle exactness** (values verbatim AND correctly role/column-bound). So the front-door
choice must NOT be gated on the conformance check (which tests template *shape*, and would let a messy
BRD with two correctly-headed tables pass while its real content is silently dropped).

**Selection contract:**

- **Default = deterministic `extract_doc`** -- preserves the "author-to-template unchanged" guarantee.
- **The normalizer is entered only two ways, both explicit/deterministic:**
  1. an **explicit invocation flag** (orchestrator invoked in "real-BRD" mode; the flag surface is an
     orchestrator-`.agent.md` edit, Section 16), OR
  2. a **pre-branch purity trip**. A new deterministic CLI `agents/tools/docx_purity.py` (NOT a change
     to the frozen `extract_doc`) scans the docx BEFORE the branch and reports content outside the
     template parser's lossless envelope. Trip conditions, precisely: **inline images, embedded/OLE
     objects, heading-less content that `extract_doc` silently drops, or a conformance failure** -- and
     explicitly NOT the extra-section tables `extract_doc` already captures structurally as
     `extra_sections` (those keep the deterministic no-LLM path). Emits
     `{has_images, has_embeds, has_headingless_content, conformance_fail}` + offending handles.
- **Control flow on a purity trip (one behavior):** if the scanner trips and real-BRD mode was NOT
  requested, the orchestrator **pauses and asks the human to opt into real-BRD mode** -- it does NOT
  silently escalate a doc into the LLM. No doc reaches the LLM implicitly.

### 4.2 The flow (new pieces in CAPS; everything after `extract_doc.json` is downstream)

```
docx / BRD
   |
   v
[docx_purity scan]  (deterministic, pre-branch)
   |
   +-- template-pure AND not real-BRD mode --> [extract_doc] --> extract_doc.json -----+
   |                                                                                   |
   +-- purity trip AND not real-BRD mode --> PAUSE: ask human to opt into real-BRD ----.
   |                                                                              (human opt-in)
   +-- real-BRD mode (flag or opt-in):                                                 |
          |                                                                            |
          v                                                                            |
      [EXPLODER]  (deterministic) -> exploder_inventory.json (full block-stream +      |
          |        images + sibling-dir files, each a handle) + jailed extracted        |
          |        files (PNGs, CSV/xlsx) + recorded CSV dialects. Zip-slip/zip-bomb    |
          |        guards on the docx AND on every extracted xlsx.                      |
          v                                                                            |
      [DOC-NORMALIZER agent]  the one eyes-on component -> normalizer_proposal.json:    |
          |        Bucket-1 INTENT + COVERAGE MAP + located Bucket-2 as CANDIDATE        |
          |        inventory handles (never a free path); rung is a LOCATING HINT only   |
          v                                                                            |
      [VALIDATOR/MERGE tool]  (deterministic CLI) reads inventory + proposal +          |
          |        jailed files; resolve handles; DERIVE rung from handle type; merge    |
          |        exact bytes; column-order + name reconcile; role/content guards;      |
          |        synthesize conformance; tier; rung-aware derived_facts -> extract_doc.json
          v                                                                            |
      [ORCHESTRATOR]  bounded shape-repair re-invoke loop + EXTRACTION GATE             |
          |        (fail-closed on a hard blocker; else proceed)                        |
          v                                                                            v
      extract_doc.json  <-----------------------------------------------------------+
          |
          v
      materialize_golden (rung-aware, Section 11) -> doc-interpreter -> flow-designer ->
      configurator -> assembler -> test-runner -> (diagnostician) -> FINAL HUMAN GATE
```

---

## 5. Components

### 5.1 The exploder (deterministic pre-extract)

Does not interpret. Makes every part reachable and inventoried. Writes a named bus artifact
**`exploder_inventory.json`** plus the jailed extracted files. Contents:

- **A FULL-block-stream inventory** walking the *entire* document (every paragraph and table in order)
  plus every image, embedded object, and sibling file -- **NOT gated on Heading-1 sections** (the
  existing `_read_sections`/`_read_section_prose` primitives only see content under recognized H1s; a
  heading-less BRD would make the Section 9 cross-check vacuous). Handle grammar (stable ids):
  `para:N` (prose blocks are inventoried as grouped block-ranges, the accounting unit for Section 9,
  so the completeness check is sectional, not brittle per-paragraph), `table:N`, `image:N`,
  `embed:<name>`, `sibling:<name>`.
- **prose + tables as text**, every table's cells as **exact strings** (`cell.text.strip()`). Before
  building any table row-dict, the exploder **disambiguates blank/duplicate header cells** (index-suffix,
  mirroring the collision rule below) or fail-closes that table to `needs_human` -- never a plain
  `dict(zip(header,row))` that would silently drop columns from the oracle.
- **images -> jailed PNGs** (for vision); **embedded OLE objects + sibling CSV/xlsx -> jailed files**.
- **Sibling discovery is deterministic (resolves the chicken-and-egg):** the exploder inventories ALL
  regular files in the docx's own directory (the trusted base) as `sibling:<name>` handles,
  independent of prose. The normalizer then *selects* among inventoried handles; it never names a path
  the exploder did not inventory.
- **recorded CSV dialect per extracted/sibling CSV** (sniffed delimiter+quote, stored on the handle).
  A CSV whose dialect cannot be fixed deterministically is NOT rung-1 eligible.

**Write-path safety (fail-closed).** Zip member / OLE names are untrusted (separators, `..`, absolute
-- zip-slip):

- **reduce first, then validate** (`_safe_name` RAISES; it is a validator, not a reducer, and cannot
  be handed a raw `a/b/../c`): derive the bare basename with `PurePosixPath(member).name` and strip any
  backslash components, THEN validate that basename with `_safe_name`, THEN write only under a jailed
  output subdir resolved via `_jailed` (realpath + `is_relative_to`). Never write a raw-member path.
- **basename-collision policy**: distinct members reducing to one basename get a deterministic index
  suffix.
- **decompression bound (fail-closed)**: check `ZipInfo.file_size` BEFORE extracting; cap total
  bytes, per-entry size, and member/image/embedding counts, raising a `ConformanceError`-style report
  like the input `MAX_DOCX_BYTES` guard.
- **the extracted xlsx is a SECOND untrusted zip**: before openpyxl opens it (5.3.2), apply the same
  caps to the xlsx's OWN zip members and load `read_only` with an entity-expansion-safe parse; an xlsx
  exceeding the caps is hard-rejected (`needs_human`), never loaded unbounded.

**Read-path safety for SIBLING files (distinct from the write jail).** A sibling reference must resolve
INSIDE the trusted base = the docx's directory: reject any absolute path or `..`; `realpath` +
`is_relative_to(base)` BEFORE `open()` (a read-side mirror of `_jailed`). The write-jail on extracted
copies gives NO assurance about the source read.

Reuses the docx *primitives* (`_iter_block_items`, `_table_records`) but NOT the heading-gated readers.

### 5.2 The doc-normalizer (agent -- the one eyes-on component)

Sees raw data: native vision reads PNGs; the terminal reads text/data files. Model-agnostic (NO
`model:` key). Writes ONE artifact, **`normalizer_proposal.json`** (raw proposal; distinct from the
resolved `extract_doc.json`):

- **Bucket-1 intent** (fuzzy-safe), SAME shape as today so `doc-interpreter` and downstream are
  unchanged: `sources_schema` (`{name,type,nullable,key}`), `rules` (`{id,kind,description}`, kind in
  `join|schema_validate|filter|aggregate|sort|derive`; STTM sheets normalize here), `notes`,
  `extra_sections`, and an `output_keys` designation per output (intent; validated in 5.3.6).
- **the coverage map** -- one entry per inventory handle with a `disposition` (Section 9 schema).
- **located Bucket-2** -- per source/output, a **list of candidate inventory handles** (never a free
  path), each with an advisory **rung hint**. The validator DERIVES the authoritative rung from the
  resolved handle type (5.3.2), so the LLM cannot tag a screenshot as rung-2. The candidate list is a
  set of **alternatives** (for the file-vs-table precedence + consistency compare, Section 6), NOT
  partitions; a source whose sample is legitimately *split* across handles is out of scope and
  degrades to `smoke` (Section 17). The LLM authors row VALUES only for image/prose handles (rung 3a).
- **a low-confidence / could-not-interpret list**.

**Schema-provenance ladder** (schema may be absent): declared table -> STTM mapping -> inferred from
the exact data header -> inferred from prose (flagged) -> none (route to human).

Discipline: **locate, do not author** on rungs 1-2; author only on rung 3a. Fail-closed: low confidence
rather than fabrication.

### 5.3 The validator/merge (deterministic CLI tool)

Between the raw proposal and the final `extract_doc.json`. "The LLM proposes; the deterministic layer
disposes." A **deterministic CLI**: never calls a model. Inputs: `exploder_inventory.json`,
`normalizer_proposal.json`, and the jailed extracted files. On a shape error it emits a shape-error
artifact and returns a status; the *orchestrator* (5.4) owns the re-invoke loop.

1. **Assemble + shape-validate.** The shape predicate is enumerated (not just exemplified): required
   field shapes per Section 10 PLUS cross-field integrity -- every `rules` kind valid, every source
   has columns, `sample_input`/`sources_schema`/`expected_output` names mutually consistent, every
   located handle resolves. Each failure is classed `shape_error` (repair loop), `needs_human` (hard),
   or `soft`. A `shape_error` writes `normalizer_feedback.json` (schema mirrors the diagnostician's
   `feedback.json`: structural pointer + value-blind why/fix) and returns `status=shape_error`.
2. **Resolve + merge Bucket-2 EXACTLY; the validator supplies the bytes AND derives the rung:**
   - **Resolve** each candidate handle against the inventory; a non-member, a write-jail escape, or a
     sibling that fails the read-jail (5.1) -> `needs_human`.
   - **Derive the rung from the resolved handle TYPE** (LLM hint is advisory): CSV-with-dialect -> 1;
     Word table or round-trip-passing xlsx -> 2; image/prose -> 3a; round-trip-FAILING xlsx -> 3b. A
     hint the type can't honor (rung-1/2 on an image, rung-1 on an xlsx) -> `needs_human`, never coerced.
   - **Loss-free read:** rung-1 CSV read with the **exploder-recorded dialect** (never re-guessed),
     first row = header, each cell a `str`. **xlsx is never rung-1**: openpyxl returns TYPED cells and
     `str(1000.5) != "1,000.50"` -- the Section-2 corruption, deterministically. Read xlsx as each
     cell's **displayed text** (apply `number_format`; never `str(cell.value)`); the **round-trip
     assertion** (5.3.2a) decides rung-2 vs rung-3b. rung-2 table = the exploder's exact cell-strings.
     rung-3a = LLM-transcribed rows (`transcribed`); rung-3b = validator-read xlsx displayed-text that
     failed round-trip (`transcribed_unverified`). Assert every emitted cell is a `str`.
   - **(2a) The round-trip assertion (defined, with a safe default):** for each cell, render displayed
     text under `number_format`, then re-parse that text under the same format/locale; accept rung-2
     only if the reparse reproduces `cell.value` with ZERO tolerance (enumerated for number, date, and
     precision cases), OR the cell format is text/General with no numeric/date coercion. **ANY unproven
     cell -> rung-3b.** "When unproven, demote" is an explicit invariant so an eager implementation
     cannot pass corruption as `verified`. (Empirical tuning against real STTM sheets is deferred,
     Section 16; the predicate's definition is not.)
3. **Role/content distinctness guard (deterministic).** A resolved handle binds to at most one role;
   AND, extended to **content** (not just handle identity): if a graded `expected_output`'s merged
   bytes exactly equal any materialized `sample_input` source's bytes (same header+rows), it is the
   degenerate before==after case -- do NOT grade that output at `verified`; degrade the job to `smoke`
   and surface it. (A passthrough oracle cannot distinguish a correct transform from a no-op, whether
   the duplication is one handle or two byte-identical ones.)
4. **Column reconciliation -- ORDER and NAME (positional-binding correct).** `FileInputDelimited`
   binds CSV columns to `sources_schema` **positionally** and ignores header text
   (`file_input_delimited.py:462-469`; a count mismatch does NOT error -- the engine silently
   truncates/pads for Talend parity, `:444-446`). Therefore: the validator MATERIALIZES each
   `sample_input` source's row-dict key order (hence CSV column order) to MATCH the emitted
   `sources_schema` order for that source (or reorders `sources_schema` to the file's order) -- a
   name-match found in a *different* order MUST trigger a reorder, never pass through. An
   unreconcilable name/count/order mismatch is a **hard blocker -> `needs_human`** (the guard lives in
   the validator; the engine provides no failure to lean on). Oracle-exactness constrains VALUES, not
   header strings, so renaming/reordering headers is permitted -- but explicit.
   - **Expected-output name-space (the harness diffs BY COLUMN NAME).** `run_and_validate` diffs golden
     vs actual by column name. Actual output columns are named in the flow's output name-space
     (derivable from `sources_schema` + rules); the golden header must match. So the validator emits
     `expected_output` row-dict keys (the golden CSV header) in that **flow output name-space** (or
     carries an explicit name-map and renames the golden header before the diff), NOT the raw
     expected-file header -- else a name-only diff can never match and `verified` never grades green.
5. **Name-normalization for filenames (with a collision rule).** Each source/output NAME becomes a
   filename and a FileOutput id; `materialize_golden._safe_name` RAISES on separators/`..`/absolute.
   The validator maps each name to a safe component with an explicit, reproducible function (fold
   illegal chars to `_`, collapse repeats, strip edges), applied CONSISTENTLY across `sources_schema`
   keys, `sample_input` keys, `expected_output` keys, `output_keys`, and `provenance` (a cross-artifact
   co-key). Distinct names colliding to one component -> deterministic index suffix (across the whole
   co-key set) OR `needs_human` -- never a silent collapse that drops/merges a flow.
6. **Verify `output_keys` (COMPOSITE).** After canonicalizing key column names onto the flow output
   name-space (5.3.4), accept a proposed key only if the **TUPLE of its columns is unique across the
   merged expected rows** (distinct-tuple count == row count -- a composite check, not the per-column
   `compute_derived_facts.unique`; extend that helper or add a tuple check). Otherwise fall to `[]`
   (bag/multiset -- the sound default) + `low_confidence`. `output_keys` is produced here, verified
   here, surfaced at the gate.
7. **Synthesize `conformance`.** Do NOT reuse the template REQUIRED_BLOCKS logic (a real BRD lacks
   those headings -> `ok=false` -> `doc-interpreter` halts on every BRD). Shape-validation success =>
   `conformance = {ok: true, missing_blocks: [], parse_errors: []}`. Completeness is carried SOLELY by
   `extraction.status` (Section 9); a shape-repair exhaustion routes to `needs_human` BEFORE
   `doc-interpreter`, so `conformance.ok` is always true when it runs.
8. **Enforce `tier`** deterministically (Section 7).
9. **Recompute `derived_facts` rung-aware.** Recompute from merged rows via `compute_derived_facts`,
   BUT for a rung-3 source do NOT emit `unique: true` / `max_group_size <= 1` (which would silently
   suppress `doc-interpreter`'s non-unique-lookup-key ambiguity); emit the conservative
   (ambiguity-raising) value so `doc-interpreter`'s existing logic fires. Provenance-aware, not uniform.

Trust boundary: **the LLM proposes intent (schema/rules/notes/output-keys) and data *locations*
(candidate handles + advisory rung hints), and supplies only rung-3a transcribed rows; the validator
supplies/blesses everything that grades -- the exact bytes (rungs 1-2), the DERIVED rung, the
role/column-binding, the tier, conformance, and derived_facts -- and rung-3 rows are admitted only as
`transcribed`, capped at `smoke` by the deterministic grading-boundary rule (Section 7).**

### 5.4 The orchestrator's role (step 0, real-BRD branch)

Owns the two loops the validator deliberately does not:

- **Bounded shape-repair loop:** on `status=shape_error`, re-invoke the normalizer with
  `normalizer_feedback.json`, up to **N = 3** (the diagnostician loop's budget), then `needs_human`.
  Each iteration the normalizer **overwrites** `normalizer_proposal.json`; the validator re-reads it --
  named-artifact discipline, no un-named state crosses the boundary.
- **Extraction gate** (Section 9): on `extraction.status = needs_human`, pause to the human; else proceed.

---

## 6. The oracle-data provenance ladder

The rung is **derived by the validator from the resolved handle type** (5.3.2). Both value-exactness
AND role/column-binding gate `verified`:

| Rung | Handle type it is derived from | Who supplies the bytes | Earns |
|---|---|---|---|
| 1 `exact-file` (**CSV only**) | attached/embedded/sibling CSV with a recorded dialect | validator (byte/text-exact read) | `verified` (subject to guards 5.3.3-5.3.4) |
| 2 `exact-table` | a clean Word table, OR an xlsx whose displayed-text read PASSES the round-trip assertion | validator (exact cell-strings) | `verified` (subject to 5.3.3-5.3.4) |
| 3a `transcribed` | image/prose handle | **LLM vision** | capped at `smoke`; `verified` only via the deferred human-promote channel (Section 7) |
| 3b `transcribed_unverified` | an xlsx that FAILS the round-trip assertion | validator (openpyxl displayed-text, unverified) | capped at `smoke`; same as 3a |
| 4 none | no sample/expected present | -- | `smoke` / `build` |

**Precedence + consistency.** The normalizer emits a *list* of candidate handles per source (5.2). The
validator derives each candidate's rung; if a source has both an exact file and an exact table,
precedence is **file wins**, AND it runs the consistency compare (defined in 5.3.3/Section 7:
order-independent equality of the canonicalized-header row-dict multiset, empty trailing rows dropped);
a mismatch on a graded oracle degrades that job to `smoke` (Section 7 has the matching term), else
`low_confidence`.

The LLM **locates** on rungs 1-2 and only **authors** values on rung 3a.

---

## 7. Tier enforcement (deterministic AT THE GRADING BOUNDARY)

Tier is computed in the validator, quantified over ALL sources and ALL graded outputs:

```
verified  iff  sample present
               AND >= 1 graded expected output exists
               AND EVERY materialized sample_input source is rung 1-2 exact
               AND EVERY graded expected_output is rung 1-2 exact
               AND the role/content-distinctness guard (5.3.3) holds
               AND every multi-candidate source/output passes the consistency compare (Sec 6)
smoke     iff  sample present but the above does not hold
build     iff  no parseable sample
```

**"graded expected_output" is pinned to the downstream definition:** exactly `materialize_golden`'s
graded set -- an output with `len(rows) > 0` (`materialize_golden.py:104`).

**The tier cap is enforced DETERMINISTICALLY at the grading boundary, not by the orchestrator LLM.**
The earlier draft had the validator merely write a `tier` string, leaving `--smoke`-vs-`--golden-dir`
to the orchestrator (an LLM) -- so the "lone guardrail" secretly rested on an LLM branch, and a rung-3
answer key still landed on disk as `graded:true`. Fixed: **`materialize_golden` becomes rung-aware**
(Section 11) -- for a rung-3 (3a/3b) output it sets `graded:false` and writes **no** `_expected.csv`.
Then no transcribed answer key ever exists on disk as gradable, and `run_and_validate` (unchanged --
it already skips `graded:false`, `run_and_validate.py:807`) cannot diff it regardless of which flag the
orchestrator picks. The Section-8 "blocked by degrading the tier" claim is now deterministically true.

**The human-promote clause is DROPPED from the formula built now.** Promotion of a rung-3 oracle to
`verified` is deferred (Section 8 knob; Section 13 builds only the degrade). When built it MUST use a
**human-only, LLM-unwritable channel** -- a separate human-authored file the orchestrator writes at the
extraction gate, NEVER a field in the LLM-authored `extract_doc.json`. Recorded as an explicit invariant.

The guarantee built now: **no rung-3 oracle can grade -- period** (values guaranteed exact for any
graded output). Role/column-mapping errors are caught by the deterministic guards (5.3.3-5.3.4) for the
degenerate/positional cases, and otherwise made **visible** (harness red, or the extended final-gate
presentation, 8.3), never silently graded green.

---

## 8. Gates and the involvement posture (lean-agentic)

**Posture (locked): lean agentic everywhere a mistake reveals itself.** Wrong join key, mis-mapped
table, over-confident schema -- these surface (harness red, or final-gate flags), so we run them
autonomously and let them fail loudly. The invisible failure (a fake `verified` off unverified values)
is blocked by the **deterministic grading-boundary cap** (Section 7), not a human stop. Role/column
errors are handled by **deterministic guards** (5.3.3-5.3.4) + visibility at the final gate (8.3), not
a mandatory happy-path confirmation.

### 8.1 The two gates

- **Extraction gate** (new, early -- Section 9): fail-closed but biased to autonomy -- pause ONLY on a
  hard deterministic blocker; soft items surface without stopping.
- **Final human gate** (existing): never auto-approve.

### 8.2 The policy object (knobs default permissive; tighten in one place)

| Decision point | Lean-agentic default | Knob to tighten later |
|---|---|---|
| extraction gate | block only on a hard blocker; surface soft | pause on any low-confidence |
| role/column mapping (rung 1-2) | deterministic guards only; mapping surfaces at final gate | require human mapping confirmation |
| rung 3 oracle | auto-`smoke` (deterministic cap); no human stop, no fake green | build the human-promote channel (Section 7) |
| final gate | unchanged decision, extended presentation (8.3) | (stays) |

### 8.3 Final-gate presentation is extended (additive, surface-not-block)

The orchestrator's Safety-net-3 presentation additively also shows, verbatim from `extract_doc.json`:
the **tier + per-source/per-output derived rung**, the **role-binding** (which handle became which
role), the **coverage-map disposition summary**, and the **low_confidence** list -- so a mis-mapping is
visible at the gate that already exists.

---

## 9. Extraction completeness: the inventory cross-check

Do not trust the LLM's self-report. The exploder inventories the FULL block stream (5.1); the
normalizer must account for **every inventory handle**. Coverage-map schema:

```
{ handle: <inventory id>,               # para:N | table:N | image:N | embed:<name> | sibling:<name>
  disposition: "extracted_to" | "irrelevant" | "could_not_interpret",
  refs: [ <ref> ]                        # required + non-empty when extracted_to
}
```

**Ref grammar (so the cross-check is deterministic):** schema field = `<source>.<column>`; rule = rule
id; source/output = the sanitized source/output name; `extra_sections` = its heading key. (`notes` is
referenced indirectly via the rule/field a note produced -- notes are not separately addressable.)

`accounted` is **content-checked**: a handle counts only if it has a disposition AND (for
`extracted_to`) its `refs` are non-empty and every ref **resolves** to an actually-emitted target --
otherwise the guard is trivially satisfiable. Prose accounting is **sectional** (per `para:N`
block-range), not per-paragraph, so the hard-blocker isn't brittle.

Predicate:
- **hard blocker (-> `needs_human`, pause):** any handle unaccounted; any source's data handle that
  fails to resolve/type; a column reconciliation hard-fail (5.3.4); shape-repair exhaustion; total
  parse failure.
- **shape_error (-> repair loop, 5.4):** an `extracted_to` with empty/unresolvable `refs`.
- **soft (surface, do not block):** `could_not_interpret` on a non-source part; a `low_confidence` from
  a consistency/reconciliation guard.

At the gate the orchestrator shows the coverage map, the unaccounted/unresolved parts, and the
low-confidence list, and asks for help; it proceeds only when the hard-blocker predicate is clear.

---

## 10. The `extract_doc.json` contract (unchanged shape + additive)

Same field SHAPES today's consumers read; new fields additive. Fields the validator
**overwrites/synthesizes** are marked (it recomputes them):

```
existing (same SHAPE as today):
  sources_schema, rules, sample_input (raw-string cells, column order = schema order),
  expected_output (raw-string cells, header in flow output name-space),
  output_keys (produced+verified here, 5.3.6), derived_facts (recomputed rung-aware, 5.3.9),
  conformance (synthesized {ok:true,...}, 5.3.7), notes, extra_sections, tier (computed, Sec 7)
added (normalizer path only; downstream ignores):
  provenance{ per source/output: validator-DERIVED rung + resolved inventory handle },
  coverage_map (Section 9), extraction{ status, unaccounted, unresolved, low_confidence },
  normalization{ model_id, ... }   (model_id reserved for the deferred cache)
```

Two other bus artifacts feed the front door only, never a downstream stage: `exploder_inventory.json`
(exploder -> validator) and `normalizer_proposal.json` (normalizer -> validator).
`materialize_golden` reads `sample_input`/`expected_output`/`output_keys`/`sources_schema`/`tier` AND
(newly) the per-output `provenance` rung (Section 11). `doc-interpreter` reads its existing fields.

---

## 11. What stays unchanged -- and the two small rung-aware exceptions

Unchanged (engine `src/` and the data-blind agents):

- `doc-interpreter`, `flow-designer`, `configurator`, `assembler`, `test-runner`, `diagnostician` --
  all data-blind, read only their existing artifacts.
- `run_and_validate.py` -- unchanged: it already skips `graded:false` outputs, which is exactly what
  the rung-aware `materialize_golden` produces for a rung-3 output.
- The engine (`src/`), and the author-to-template workflow + its 215 tests.

**One small, additive change to OUR tooling (not the engine):** `materialize_golden.py` becomes
**rung-aware** -- it reads the per-output `provenance` rung from `extract_doc.json` and, for a rung-3
(3a/3b) output, sets `graded:false` and writes NO `_expected.csv`. This is the deterministic
grading-boundary enforcement of Section 7 (a rung-3 answer key can never sit on disk as gradable). It
is additive (a rung-1/2 output is materialized exactly as today) and lives in `agents/tools/`, not
`src/`. The extract_doc.json CONTRACT and every data-blind agent stay untouched.

The orchestrator gains: the pre-branch `docx_purity` scan, the real-BRD step-0 branch (exploder ->
normalizer -> validator/merge), the shape-repair loop, the extraction gate, and the extended final-gate
presentation (8.3). New deterministic tools: `docx_purity`, the exploder, the validator/merge CLI.

---

## 12. Reproducibility and caching (DEFERRED -- build later)

- **Basic reproducibility is free:** the approved `extract_doc.json` lives on disk and is re-read
  deterministically; LLM non-determinism does not propagate past the front door.
- **Deferred:** explicit freeze-on-approval; cache on `hash(doc + siblings) + model_id`; fold a
  preflight-probe output hash into `model_id` if Copilot exposes only a coarse id; cache stores only
  approved outputs, repair loop bypasses it. `normalization.model_id` is emitted now for the key.

---

## 13. Testing posture (discovery phase)

Input distribution is unknown (many teams, no standard template). So:

- **Now: no test suite.** The LLM reasons maximally; we run on real BRDs and learn. Intent mistakes
  surface visibly.
- **The lone kept guardrail is code, not a test:** the deterministic grading-boundary cap
  (rung-aware `materialize_golden`) + the role/content-distinctness guard (5.3.3). Scoped honestly to
  VALUES (+ the degenerate/positional role cases); it keeps "extract everything" from a fake green that
  would poison discovery.
- **Later (post-standardization):** more docs go through the deterministic path and the exact rungs;
  tests + determinism grow additively (Section 14).

(Future test shape, documented not built: deterministic unit tests for `docx_purity`, the exploder, and
the validator/merge; invariant property-tests -- CSV round-trip exactness, xlsx round-trip-or-demote,
positional column-order, rung-3-never-graded at the manifest level, role/content-distinctness,
zip-slip/zip-bomb refusal; a golden-doc fixture library vs a mocked normalizer; an opt-in `@pytest.mark`
live-model probe. Deterministic modules then clear the 95% per-module floor.)

---

## 14. Phased tightening (now -> post-standardization)

- **Now:** LLM-maximal, exploratory; deterministic path is the default for template-pure docs.
- **As templates standardize:** more docs template-pure or carrying exact CSV/clean tables (rungs 1-2),
  so the deterministic surface grows and the rung-3 surface shrinks; tests + stricter gates (mapping
  confirmation, the human-promote channel) are added -- additive, no re-architecture.

---

## 15. Constraints carried forward (locked)

- **Model-agnostic:** NO `model:` key in any `.agent.md`.
- **ASCII-only** in code/logs/authored markdown (RHEL-clean).
- **don't-minimize-egress:** trusted enclave; the oracle-exactness rule (Section 2) stands regardless.
- **Engine changes are the engine team's** (`src/` out of scope; the rung-aware `materialize_golden`
  and the new tools are `agents/tools/`, ours).
- **Adversarial-review loops:** spec -> plan -> final, looped till clean; Opus everywhere; multi-lens
  fan-out Workflow.
- **superpowers workflow:** brainstorming -> writing-plans -> subagent-driven-development ->
  requesting-code-review.
- **VS Code 1.122 tool IDs:** valid = `read`, `edit`, `search/codebase`, `agent/runSubagent`,
  `execute/runInTerminal`, `execute/getTerminalOutput`. INVALID = `read/files`, `edit/files`,
  `run/terminal`, `runCommands`. Verify IDs live in Copilot.
- **CLIs create their parent dirs.**
- **Git:** never commit to `main`; branch `feature/real-brd-ingestion`; stage by name; confirm before push/PR.

---

## 16. Open items to confirm during the build

- The orchestrator invocation-flag surface for real-BRD mode (semantics pinned in 4.1; only the flag
  wiring remains).
- **Vision delivery of a disk PNG to an autonomous subagent** (exploder disk-PNG ->
  `agent/runSubagent` normalizer -> subagent reads PNG into vision, no human attaching). Load-bearing
  for rung-3a; re-probe before the normalizer-agent task is planned. Fallback if unavailable:
  rung-3a -> `needs_human`, never a silent drop. (The exploder task is unaffected and can proceed.)
- **Empirical tuning of the xlsx round-trip assertion** against real STTM sheets (number/date/precision
  cases). The predicate is DEFINED (5.3.2a); only its real-data confirmation is deferred; unproven
  cells demote to rung-3b.
- DLP against realistic data-like content.
- The stable model-id surface (deferred cache only).

---

## 17. Out of scope

- Reproducibility/caching (Section 12) -- deferred.
- A test suite (Section 13) -- discovery phase; only the grading-boundary cap + distinctness guard built.
- The human-promote channel (Section 7) -- deferred; must be LLM-unwritable when built.
- A source/output whose sample is legitimately **split across multiple handles** (concat) -- out of
  scope; degrades to `smoke` (the candidate list is alternatives, not partitions).
- Any change to `src/` (engine) or the data-blind agents; the only tooling change is the rung-aware
  `materialize_golden` (Section 11).
- The author-to-template workflow -- unchanged.
