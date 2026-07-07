# Step-by-Step Agent Testing Guide

A controlled, one-agent-at-a-time protocol for exercising the `etl-orchestrator`
and its six specialist subagents. The goal is **visibility over autonomy**: the
orchestrator fires exactly one stage, then **halts** so you can inspect the real
artifact that stage wrote before you authorize the next stage.

This is a *testing* override of the orchestrator's normal free-agent loop. In
production the orchestrator runs the whole chain autonomously; here we drive it
in single-step mode.

---

## 1. What we are testing

The pipeline turns an ETL requirements `.docx` into a runnable, harness-verified
`job.json`. It has three kinds of players:

| Player | Kind | Role |
|--------|------|------|
| `etl-orchestrator` | user-invocable | Drives the chain, keeps the audit log, stops at the human gate. Never edits artifacts, never judges correctness. |
| 6 specialists | subagent-only | Each reads its predecessor's artifact from disk and writes its own back. |
| Deterministic tools + harness | Python CLIs | `extract_doc`, `materialize_golden` (step 0); `validate_config`, `run_and_validate` (the PASS/FAIL oracle); `surface_code_cells`, `audit_log`. |

### The artifact bus

Every stage communicates through JSON files under `agents/work/<job>/` — **data
never travels through the orchestrator's prose**. This is exactly what makes
step-by-step inspection possible: after each halt, you open the file that stage
just wrote.

```
extract_doc.json        <- STEP 0  (deterministic, run by orchestrator)
requirement_spec.json   <- STAGE 1 doc-interpreter
flow_plan.json          <- STAGE 2 flow-designer
job_draft.json          <- STAGE 3 configurator
job.json                <- STAGE 4 assembler
test_report.json        <- STAGE 5 test-runner (the harness verdict)
feedback.json           <- STAGE 6 diagnostician (only on a FAILED report)
audit.jsonl             <- orchestrator's append-only audit trail
```

---

## 2. The stages in order

| # | Stage | Agent | Reads | Writes | What "good" looks like |
|---|-------|-------|-------|--------|------------------------|
| 0a | extract | *(tool)* `extract_doc` | `<docx>` | `extract_doc.json` | Exit 0; `conformance.ok == true`; a `tier` of `verified`. |
| 0b | materialize | *(tool)* `materialize_golden` | `extract_doc.json` | input CSVs + `golden/{*_expected.csv, manifest.json}` | Input CSV(s) at work-dir root; golden answer key under `golden/`. |
| 1 | interpret | `doc-interpreter` | `extract_doc.json` | `requirement_spec.json` | Normalized `rules` (join/sort/etc.), `outputs`, `notes`, `tier`, and an `ambiguities` list (ideally empty). |
| 2 | design | `flow-designer` | `requirement_spec.json` | `flow_plan.json` | A `pattern` line + ordered `components` using **registered** engine type names. |
| 3 | configure | `configurator` | `flow_plan.json` | `job_draft.json` | Per-component `config` + `schema`; every curated component validated clean. |
| 4 | assemble | `assembler` | `job_draft.json` (+ `flow_plan.json`, `requirement_spec.json`) | `job.json` | Envelope wired: `subjob_id`, `{input,output}` schema, typed `flows`, `inputs`/`outputs`. |
| 5 | test | `test-runner` | `job.json` (+ golden) | `test_report.json` | Harness `passed == true` (verified tier). |
| 6 | diagnose | `diagnostician` | `test_report.json` (FAILED only) | `feedback.json` | One `owner` stage + a value-blind `why`/`fix`. |

Between stage 4 and stage 5 the orchestrator runs a **pre-execution code review**
(`surface_code_cells`) and pauses if the job contains any code-bearing cell.

### Verification tiers

`extract_doc` computes a tier that changes how stage 5 behaves:

- **verified** — sample input **and** graded expected output both exist. Harness
  diffs against the golden and loops on `passed` (max 3 repair iterations). The
  sample doc is this tier.
- **smoke** — sample input but no graded expected. One `--smoke` run, no diff.
- **build** — no parseable sample input. `job.json` built but never executed.

---

## 3. The controlled testing protocol

We invoke the **orchestrator** — it fires the agents, and it is the only entry
point (the six specialists are `user-invocable: false`, so you cannot invoke them
directly; the orchestrator drives them via `#runSubagent`). The orchestrator has a
**native single-step / testing mode**: when your invocation asks for it, the
orchestrator runs exactly one stage, halts, and waits for your explicit "proceed"
before the next. So single-stepping is *supported behavior*, not a prompt-override
the agent might ignore mid-run.

### Invocation prompt template

Invoke the `etl-orchestrator` with a message like:

```
Run the ETL pipeline for:
  docx: agents/examples/sample_etl_requirements.docx
  job:  <JOB_SLUG>

TESTING MODE — SINGLE STEP:
- Execute STEP 0 (extract_doc + materialize_golden) only, then STOP.
- After each subsequent stage, run exactly ONE #runSubagent (or one tool step),
  append the audit line, print the path of the artifact it wrote, then STOP and
  wait for my explicit "proceed" before the next stage.
- Do NOT chain stages. Do NOT auto-repair on failure — if test-runner fails,
  run the diagnostician ONCE, show me feedback.json, then STOP.
- Keep all three safety nets (harness owns correctness, audit log, human gate).
```

### The loop you run

For each stage:

1. Tell the orchestrator to run the **next single stage**.
2. Orchestrator invokes one agent (or tool), writes one artifact, logs one audit
   line, then halts.
3. **You inspect** the artifact it named (open the JSON, run the checklist in
   §4).
4. If it looks right, reply `proceed`. If not, stop and debug that one stage.

Because each stage is isolated and its output is a file on disk, a failure is
attributable to exactly one agent — which is the whole point.

---

## 4. Per-stage inspection checklists

**What these checks catch (and what they don't):** stages 1–4 are *structural* — they
catch shape and wiring errors early, which is the whole point of per-stage attribution.
But **semantic** correctness (did the join actually produce the right rows? is the sort
order right?) only surfaces at the harness in stage 5. An all-green checklist at stages
1–4 means the artifact is well-formed, **not** that the final job is correct — so don't
over-trust an early green.

### Step 0 — extract + materialize (deterministic)

- `agents/work/<job>/extract_doc.json` exists; `conformance.ok == true`.
- `tier == "verified"` for the sample doc.
- `sources_schema`, `rules`, `output_keys`, `notes`, `derived_facts` populated.
- Input CSV(s) written to `agents/work/<job>/` root.
- `agents/work/<job>/golden/` has `manifest.json` + `<out>_expected.csv`.
- **Note:** this step touches the real data deterministically — no model runs
  here. If this is wrong, the fault is the tool or the docx, not an agent.

### Stage 1 — doc-interpreter → `requirement_spec.json`

- Each rule normalized to one op (`join | schema_validate | filter | aggregate |
  sort | derive`) with the right fields (a `join` has `keys`, `columns_added`,
  `cardinality`, `no_match`).
- `outputs` lists each Expected-Output name (structural only, no keys/graded).
- `notes` carried verbatim; note-derived rules tagged `source: "note"`.
- **`ambiguities`** — for the sample this should be empty (the note resolves
  `no_match` and case-sensitivity). A non-empty list is a real signal, not a
  bug: it means the interpreter refused to guess.
- **Data-blindness check:** no real `sample_input`/`expected_output` cell values
  should appear anywhere in the spec.

### Stage 2 — flow-designer → `flow_plan.json`

- A one-line `pattern` describing the pipeline shape.
- `components` is an ordered list of `{id, type, purpose}`.
- Every `type` is a **registered engine name** (e.g. `tJoin`, `SortRow`,
  `FileOutputDelimited`, `tPythonDataFrame`) — not prose shorthand like
  `python_dataframe`.
- No `config`, no `schema`, no flows at this stage.
- For the sample, expect the *shape*: a column-adding lookup join on
  `counterparty_code` + a `SortRow` on `txn_id` + `FileInputDelimited`×2 +
  `FileOutputDelimited`. **Which join node is a genuine design choice, not a fixed
  answer.** Because R1 *adds* a column (`counterparty_name`), the flow-designer will
  most likely pick `tMap`/`PyMap` — a bare `tJoin` adds no lookup columns unless
  `use_lookup_cols: true` (landmine `tjoin-needs-use-lookup-cols`, and the
  configurator explicitly prefers `tMap`/`PyMap` for column-adding lookups). Inspect
  what it chose; do **not** flag a valid `tMap`/`PyMap` (or a correctly-configured
  `tJoin`) as wrong just because it differs from a single expected node.

### Stage 3 — configurator → `job_draft.json`

- Shape is exactly `{"components": [{"id","type","config","schema"}]}` — no
  flows, no `inputs`/`outputs`, no `subjob_id`.
- Every curated component validated clean (`validate_config` → `"valid": true`).
- `schema.output` filled, `schema.input` left `[]` (assembler derives it).
- Landmine checks: `csv_option: true` + `text_enclosure: "\""` on the
  materialized FileInput/FileOutput; `execution_mode: "batch"` pinned on
  stateful nodes (`SortRow`, `AggregateRow`, `UniqueRow`, `tPythonDataFrame`);
  correct die-on-error key per component; `sort_type` on non-string sort keys.
- FileInput `filepath` is a bare `"<source-name>.csv"`.

### Stage 4 — assembler → `job.json`

- Every component has `subjob_id`; schema is `{input, output}` two-key objects.
- `flows` is a top-level list of `{name, type, from, to}` with `"type":"flow"`
  (or `"reject"`), never `"main"`.
- Each component's `inputs`/`outputs` reference **flow names**, not component ids.
- **Output-name contract:** each terminal FileOutput `id` equals its
  Expected-Output name (`result` for the sample).
- Graph is connected and acyclic; no dangling flows.
- `config` blocks are byte-for-byte identical to the draft (only FileOutput
  `id` may be renamed).

### Stage 5 — pre-exec review + test-runner → `test_report.json`

- `surface_code_cells` runs first, and what it surfaces depends on the join the
  flow-designer chose in Stage 2:
  - If it chose a bare `tJoin` + `SortRow` (no expression-bearing nodes), expect
    **no cells** surfaced and no pause.
  - If it chose `tMap`/`PyMap` for the column-adding lookup (the likely pick for
    R1), expect the `{{java}}` tMap expressions or the PyMap
    join/variable/output expressions to be **surfaced** and the pre-exec review
    to **pause for your approval** before test-runner runs. That pause is
    correct behavior, not a fault — approve the cells to continue.
- test-runner runs `run_and_validate --golden-dir ... --out test_report.json`.
- Inspect `test_report.json`: `passed` boolean, `engine` block, per-output
  `outputs` diffs, `reasons`. For the sample, expect `passed: true`.
- **Do not judge correctness yourself** — the harness `passed` flag is the
  verdict.

### Stage 6 — diagnostician → `feedback.json` (only if stage 5 failed)

- Runs only on a FAILED report.
- `owner` names exactly one stage (`doc-interpreter | flow-designer |
  configurator | assembler | human`).
- `signal` cites structural evidence (json-path + diff shape), `why`/`fix` are
  value-blind.
- In testing mode we **stop here** and inspect, rather than auto-re-running the
  owner stage.

---

## 5. Where to look after each halt

- **The artifact** the stage wrote — `agents/work/<job>/<artifact>.json`.
- **The audit trail** — `agents/work/<job>/audit.jsonl`; the last line records
  which subagent ran, on which artifact, and (for test-runner) the verdict.
- **The orchestrator's message** — it prints the artifact path and stops.

---

## 6. Manual fallback (bypassing the orchestrator)

If you ever want to run a single agent in total isolation (e.g. to re-test one
stage after a fix), the deterministic tools can be run straight from the
terminal — no Copilot needed:

```bash
# Step 0
python -m agents.tools.extract_doc agents/examples/sample_etl_requirements.docx \
  --out agents/work/<job>/extract_doc.json
python -m agents.tools.materialize_golden \
  --extract-doc agents/work/<job>/extract_doc.json \
  --work-dir agents/work/<job>

# Stage 3 per-component config check
python -m agents.tools.validate_config --type SortRow --config some_config.json

# Stage 5 harness
python -m agents.tools.run_and_validate \
  --job agents/work/<job>/job.json \
  --golden-dir agents/work/<job>/golden \
  --out agents/work/<job>/test_report.json
```

The five model-driven stages (doc-interpreter, flow-designer, configurator,
assembler, diagnostician) must be invoked as subagents — they reason, so they need a
model. But the **entire deterministic backbone runs from the terminal**: `extract_doc`
+ `materialize_golden` (step 0), `validate_config` (stage 3's per-component check), and
`run_and_validate` (stage 5's harness — the `test-runner` agent is just a thin wrapper
around this CLI). So you can **hand-author any intermediate JSON** (e.g. a `job.json`)
and run the harness on it directly to test a single model stage's output in isolation —
no Copilot needed.

---

## 7. Reset between runs

Each run writes to `agents/work/<job>/`. To start a stage fresh, delete or
rename that directory (or pick a new `<job>` slug) so stale artifacts don't mask
a stage's real output.
