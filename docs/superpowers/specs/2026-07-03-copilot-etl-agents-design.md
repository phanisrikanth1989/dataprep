# Design Spec: Copilot Multi-Agent ETL Config Generator

- **Date:** 2026-07-03
- **Status:** DRAFT — pending adversarial review + user sign-off
- **Branch:** `feature/copilot-etl-agents`
- **Owner:** Recon team (A Arun)
- **Related:** `CLAUDE.md`, `docs/guides/AUTHORING_JOB_JSON.md`, `docs/JOB_CONFIGURATION_SCHEMA.md`, `src/router/ui_registry.json`, `docs/ai-prompts/*`

---

## 1. Goal & Constraints

### 1.1 Goal

A **dev-supervised, autonomous multi-agent system** that runs **entirely on the developer's laptop inside VS Code GitHub Copilot** and turns a **Word (`.docx`) requirements document** into a **validated DataPrep engine JSON job config**. It self-corrects through an **execution-based feedback loop** — generate config, run it through the real engine, diff actual output against the expected output in the doc, route failures back to the responsible upstream stage — looping automatically **3–5 times** before escalating to the developer, who gives final approval.

The system is a **new authoring front door** for jobs that have **no Talend `.item` source** (the existing converter already handles those). It produces the same JSON the engine consumes, so **Talend feature-parity remains the correctness bar**.

### 1.2 Success criteria

1. From a filled recon requirements doc, the system produces a job JSON that **runs on the engine and matches the doc's expected output** for the sample input, with **no human edits**, on a meaningful fraction of the first recon slice.
2. When it cannot, it **escalates with a precise, actionable diagnosis** (which stage, which rule/component, why) rather than a silent wrong answer.
3. It stays **correct as the engine evolves** — the knowledge it reasons from is derived from and re-verified against engine/converter source, not stale prose.

### 1.3 Non-goals

- Not a hosted service, web app, or anything running on a Citi server. **Local only.**
- Not a replacement for the Talend→JSON converter (that path stays for jobs with `.item` sources).
- Not database jobs, not non-file sources, in the first slice.
- Not fully unattended production authoring — a human approves the final JSON.

### 1.4 Hard constraints

| # | Constraint | Consequence |
|---|---|---|
| C1 | Runs **local** on the laptop inside VS Code; no hosted server; **no data egress** | MCP server is a local stdio subprocess; sample data never leaves the machine except via the user's existing Copilot model boundary (sampling) |
| C2 | Target **VS Code 1.106** (Nov 12 2025 build) | No native subagents (1.107+), no Agent Skills (1.107+). Orchestration = MCP + sampling |
| C3 | **Model-agnostic** | No dependency on any specific model brand; roles work with whatever the Copilot model is |
| C4 | Agent definition files live in **`.github/agents/`** | VS Code only auto-discovers custom agents there (or via `chat.modeFilesLocations`) |
| C5 | Knowledge grounded in **code-verified truth** | Everything except engine + converter code may be stale; knowledge pack is generated from source |
| C6 | Dependencies allowed from **Citi internal artifact repo** (`mcp` SDK, `python-docx`, …) | Primary design uses proper libraries; a zero-dependency stdlib path is a documented fallback only |
| C7 | First slice: **recon domain, files-only, transformation-rich** | Bounded component vocabulary; recon-shaped template + examples |
| C8 | ASCII-only logs; fix-at-source (no defensive fallbacks); Talend parity non-negotiable | Inherited from `CLAUDE.md` project rules |

### 1.5 Assumptions to confirm (non-blocking)

- **A1:** The `mcp` Python SDK and `python-docx` are installable from Citi's internal artifact repository. *If not, fall back to the stdlib implementations (Section 3.4).* — user will confirm.
- **A2:** MCP is enabled in the Citi Copilot (Tier-1 check **passed**), sampling is permitted, and the local server can be whitelisted if a registry policy is in force.
- **A3:** The DataPrep engine runs from the laptop terminal against local sample data (confirmed: engine runs via terminal today).

---

## 2. System Overview

### 2.1 End-to-end flow

```
 requirements.docx
        |
        v
  [extract_doc] (tool, deterministic)  ->  requirements.md (clean text + tables)
        |
        v
  Doc-Interpreter (role, LLM)          ->  requirement_spec.json
        |
        v
  Flow-Designer (role, LLM)            ->  flow_plan.json      --[optional human checkpoint]-->
        |
        v
  Configurator (role, LLM)             ->  job_draft.json
        |
        v
  Assembler (role, LLM + validator)    ->  job.json  (+ validation_report.json)
        |
        v
  Test-Runner (tool, deterministic)    ->  test_report.json   (runs engine, diffs vs expected)
        |
     pass? --------------------------- yes --> [human approval] --> DONE (job.json)
        | no
        v
  Diagnostician (role, LLM)            ->  feedback.json  (target stage + fix)
        |
        +--> orchestrator routes feedback to the named upstream stage; re-run from there
             (loop budget: 3-5 iterations, then escalate to human with the diagnosis)
```

### 2.2 The two-layer decoupling (the core architectural bet)

- **Durable core (mechanism-agnostic, ~80% of the value):** the role prompts, the code-verified **knowledge pack**, the **test/validate harness**, and the **artifact contracts**. Identical no matter how orchestration is wired.
- **Thin orchestration layer (platform-dependent):** how the roles are invoked and the loop is driven. On 1.106 this is an **MCP server** (Section 3). If the platform changes (1.107+ native subagents, or MCP disabled → handoffs), only this thin layer changes; the durable core is untouched.

This is what lets us build now on 1.106 and upgrade cleanly at the end-July VS Code bump.

---

## 3. Orchestration on VS Code 1.106

### 3.1 Mechanism: local MCP server + sampling

A single **local MCP server** (stdio transport — a child process VS Code launches; nothing listens on a network port, no data egress) exposes the pipeline as tools. It is registered in `.vscode/mcp.json`. A thin **kickoff custom agent** in `.github/agents/` starts a run and surfaces results in chat.

- **LLM roles** (Doc-Interpreter, Flow-Designer, Configurator, Assembler-reasoning, Diagnostician) are executed by the server via **MCP sampling** (`sampling/createMessage`) — the server asks VS Code to run a completion **on the user's Copilot model**. No external API key, model-agnostic. (Sampling is GA since VS Code 1.102; present in 1.106.)
- **Deterministic steps** (extract_doc, run_and_validate, static validation, knowledge-pack lookup, freshness check) are plain code in tools — no sampling needed.

### 3.2 Deterministic control loop (in code, not LLM-improvised)

The orchestration loop — sequencing, the 3–5 iteration budget, artifact read/write, feedback routing, human-gate handling — is **ordinary Python in the server**, not left to model improvisation. This is deliberate: a bank needs the control flow to be **deterministic, testable, and auditable**. The model's judgment is confined to well-scoped per-role sampling calls; the *orchestration* is code.

`iteration_log.md` records every step, artifact version, and routing decision for audit.

### 3.3 Approvals (human-in-the-loop by default)

VS Code prompts for: server start approval, tool-call approval (allow-listable), and the first **sampling** approval per server. Terminal execution (the engine run) also prompts unless auto-approve is configured. We assume **manual approval** is required and design the UX around it (batch approvals where possible).

### 3.4 Dependencies (primary + fallback)

- **Primary (per C6):** the official **`mcp` Python SDK** for the server; **`python-docx`** for `.docx` extraction; reuse the engine's existing env (pandas, lxml, openpyxl). Cleaner, more maintainable, standard.
- **Fallback (only if a library is absent from the internal repo):** stdlib-only implementations — JSON-RPC 2.0 over stdio for the server; `zipfile` + `xml.etree` for `.docx` (a `.docx` is zipped XML). Documented so we can revert per-component without redesign.

### 3.5 Kickoff agent (`.github/agents/etl-orchestrator.agent.md`)

A `target: vscode` custom agent that (a) lists the MCP server's tools + the terminal tool, (b) starts a pipeline run against a doc the user points at, (c) shows the per-iteration progress and the final `job.json` + `test_report.json`, and (d) asks for final approval. Model-agnostic (no pinned model).

### 3.6 Fallback orchestration (documented, not built first): handoffs

If MCP is ever disabled org-wide, the same roles become native custom agents in `.github/agents/` chained by **handoffs** — the developer clicks to advance/loop. Same roles, same knowledge pack, same harness; only the wiring differs. Recorded in `PLATFORM.md`.

---

## 4. Agent Roster & Artifact Contracts

### 4.1 Roles

| Role | Kind | Consumes | Produces | Responsibility |
|---|---|---|---|---|
| **Orchestrator** | code | all | `iteration_log.md` | Drive the loop, route feedback, enforce gates + budget |
| **Doc-Interpreter** | LLM | `requirements.md` + knowledge pack | `requirement_spec.json` | Extract schema, rules, sample in, expected out; flag ambiguities |
| **Flow-Designer** | LLM | `requirement_spec.json` + knowledge pack | `flow_plan.json` | Map rules → component graph (no config yet); rule→component coverage |
| **Configurator** | LLM | `flow_plan.json` + spec + knowledge pack | `job_draft.json` | Fill each component `config` + `schema` from code-verified specs |
| **Assembler** | LLM + code | `job_draft.json` | `job.json` + `validation_report.json` | Wire flows/triggers/subjobs/context; run static validator; fix reference/wiring issues |
| **Test-Runner** | code | `job.json` + sample/expected | `test_report.json` | Execute engine, diff actual vs expected, capture stats + classified error |
| **Diagnostician** | LLM | `test_report.json` + knowledge pack | `feedback.json` | Classify failure; name the responsible upstream role + concrete fix |
| **Knowledge-Maintainer** | LLM + code | engine/converter source | knowledge pack | Regenerate pack when stale (TTL or fingerprint) |

Roles are **pluggable**: adding one (e.g., a Context-Parameter-Extractor) = a role prompt in `agents/roles/`, an artifact in/out, and a slot in the orchestrator sequence.

### 4.2 Artifact contracts (the interfaces)

All artifacts live in `agents/work/<job_id>/` (gitignored). Every artifact carries `{ "schema_version": 1, "iteration": N }`.

**`requirement_spec.json`**
```jsonc
{
  "job_name": "recon_ledger_vs_statement",
  "domain": "recon",
  "inputs": [
    { "name": "ledger",   "file_hint": "ledger.csv",
      "schema": [ { "name": "txn_id", "type": "str", "nullable": false, "key": true }, ... ] },
    { "name": "statement","file_hint": "stmt.csv",  "schema": [ ... ] }
  ],
  "rules": [
    { "id": "R1", "kind": "match",     "description": "match ledger.txn_id to statement.ref_id",
      "details": { "left": "ledger.txn_id", "right": "statement.ref_id", "type": "exact" } },
    { "id": "R2", "kind": "tolerance", "description": "amounts equal within 0.01",
      "details": { "left": "ledger.amt", "right": "statement.amt", "abs_tol": 0.01 } },
    { "id": "R3", "kind": "aggregate", "description": "count + sum breaks by reason" }
  ],
  "outputs": [
    { "name": "matched", "schema": [ ... ] },
    { "name": "breaks",  "schema": [ ... ] },
    { "name": "summary", "schema": [ ... ] }
  ],
  "sample_input":    { "ledger": [ {row}, ... ], "statement": [ {row}, ... ] },
  "expected_output": { "matched": [ ... ], "breaks": [ ... ], "summary": [ ... ] },
  "ambiguities": [ { "rule_id": "R2", "question": "is tolerance absolute or percentage?" } ],
  "confidence": "high|medium|low"
}
```

**`flow_plan.json`**
```jsonc
{
  "components": [ { "id": "tFileInputDelimited_1", "type": "FileInputDelimited",
                    "purpose": "read ledger", "maps_to_rules": [] }, ... ],
  "flows":     [ { "name": "row1", "from": "...", "to": "...", "type": "flow" }, ... ],
  "triggers":  [ ... ],
  "subjobs":   { "subjob_1": [ ... ] },
  "rule_coverage": [ { "rule_id": "R1", "components": ["tMap_1"] }, ... ],
  "uncovered_rules": [],
  "open_questions": [ ]
}
```

**`job.json`** — the actual engine job config (per `docs/JOB_CONFIGURATION_SCHEMA.md` / code-verified schema). `job_draft.json` is the same shape pre-assembly/validation.

**`test_report.json`**
```jsonc
{
  "status": "pass|fail|error",
  "engine_status": "success|failed|error",
  "outputs": {
    "matched": { "expected_rows": 12, "actual_rows": 11,
                 "missing": [ {row} ], "unexpected": [ {row} ],
                 "column_diffs": [ { "row_key": "...", "column": "amt", "expected": 100.0, "actual": 100.01 } ] },
    "breaks":  { ... }, "summary": { ... }
  },
  "engine_stats": { "tMap_1": { "NB_LINE": 100, "NB_LINE_REJECT": 3 }, ... },
  "error": { "class": "DataValidationError", "component": "tMap_1",
             "message": "...", "cause": "..." },   // null on non-exception failures
  "iteration": 2
}
```

**`feedback.json`**
```jsonc
{
  "target_role": "configurator",         // configurator | flow_designer | doc_interpreter | assembler
  "severity": "blocking",
  "findings": [
    { "anchor": "tMap_1", "problem": "amount tolerance not applied; exact compare used",
      "evidence": "column_diffs on 'amt' off by 0.01", "suggested_fix": "apply abs_tol from R2 in the match expression" }
  ],
  "iteration": 2
}
```

---

## 5. Knowledge Pack & Self-Healing

### 5.1 Contents

- **Per-component config spec:** for every engine component — valid `config` keys, types, defaults, required-ness, conditional relationships, and the output/reject/schema conventions.
- **Job-schema rules:** top-level shape, flows vs triggers, subjob derivation, reject-as-flow, context/`java_config`.
- **The landmines** (code-verified): `die_on_error` dual defaults, tMap named-outputs + triple-name agreement, reject is a data flow not a trigger, top-level `subjobs` ignored, etc.

### 5.2 Source of truth: generated from code

`tools/gen_knowledge.py` derives the pack by parsing engine + converter **source** (Python `ast`): the `@REGISTRY.register(...)` decorators (valid type names/aliases), each component's `_validate_config` and `self.config.get(...)` reads (real keys + defaults), and the converter's Talend-param → JSON-key mappings. `src/router/ui_registry.json` is used as a **cross-check**, never as gospel (it can drift).

### 5.3 SKILL.md shape (forward-compatible)

Each knowledge module is authored as a **`SKILL.md`-style file** (name + description frontmatter + body + bundled reference data), placed under `.claude/skills/<name>/`. On 1.106 the roles consume them as plain context (loaded by the server / referenced from an instructions file). At **≥1.107** these same files light up as **native Agent Skills** with zero rewrite (Copilot reads `.claude/skills/`).

### 5.4 TTL + fingerprint self-healing

Each knowledge file carries frontmatter: `generated_at`, `ttl_days`, `source_fingerprint` (hash of the engine/converter files it was derived from). `tools/check_freshness.py` marks a module stale when **either** the TTL lapses **or** the fingerprint ≠ current code hash (code-change is the stronger trigger). The **Knowledge-Maintainer** regenerates stale modules from source and resets the stamp. The orchestrator runs the freshness check at the start of every pipeline run.

---

## 6. Test Harness & Feedback Routing

### 6.1 `tools/run_and_validate.py`

Deterministic CLI: `run_and_validate.py --job job.json --input <dir> --expected <dir> [--tolerance 0.01]`.
Steps: (1) run the engine on `job.json` against the sample input (imports `ETLEngine`, in-process); (2) capture per-output DataFrames + engine stats + any classified exception; (3) diff each actual output against the expected output — row presence (missing/unexpected keyed by the output's key columns), per-column value diffs with type-aware + optional numeric tolerance, row counts; (4) emit `test_report.json`. Exit code reflects pass/fail/error.

### 6.2 Error taxonomy → responsible stage

Reuses the exception-class table from `docs/ai-prompts/DEBUG_JOB_FAILURE.md` + a failure→stage map:

| Failure signal | Likely responsible stage |
|---|---|
| `ConfigurationError` / invalid config key | Configurator |
| `DataValidationError` / schema/type mismatch across a flow | Configurator (schema) or Assembler (wiring) |
| Wrong values / wrong aggregation / logic mismatch (diff, no exception) | Flow-Designer (wrong component/graph) or Configurator (wrong expression) |
| Reference/wiring error ("no flow named X") | Assembler |
| Requirement genuinely ambiguous / expected-output itself unclear | Doc-Interpreter (raise to human) |
| `JavaBridgeError` / `ExpressionError` | Configurator (expression) |

### 6.3 Loop control

- **Budget:** 3–5 automatic iterations (configurable). Each iteration re-runs **only from the responsible stage** forward (not the whole pipeline) using `feedback.json`.
- **Convergence guards:** stop early if two consecutive iterations produce an identical `job.json` (no progress) or an identical failure signature (oscillation); escalate with the diagnosis.
- **Human gates:** (a) *optional* checkpoint after Flow-Design (cheapest place to catch a misread — recommended on early/low-confidence runs); (b) *mandatory* final approval of `job.json` + `test_report.json`.

---

## 7. Repo Layout & Files

```
.github/agents/
    etl-orchestrator.agent.md      # kickoff custom agent (target: vscode)
    roles/                          # (fallback) per-role custom agents for handoffs mode
.vscode/mcp.json                    # registers the local MCP server
.claude/skills/<name>/SKILL.md      # knowledge modules (native skills at >=1.107)
agents/
    orchestrator/                   # MCP server + deterministic control loop
    roles/                          # role prompts (doc-interpreter, flow-designer, ...)
    knowledge/                      # generated pack (mirrors / sources .claude/skills)
    registry/                       # generated per-component config spec
    tools/                          # extract_doc.py, gen_knowledge.py,
                                    #   run_and_validate.py, check_freshness.py
    templates/                      # recon requirements-doc template + worked example
    work/                           # per-job scratch artifacts (gitignored)
    PLATFORM.md                     # version posture + upgrade playbook
    README.md
```

Note: agent *definitions* must sit in `.github/agents/` (C4); the *brains* (knowledge, tools, templates) sit in `agents/`. `.claude/skills/` holds the forward-compatible skill modules.

---

## 8. Recon First Slice

### 8.1 Scope

Recon, **files-only**, transformation-rich. Component vocabulary:

- **File in/out:** `FileInputDelimited`, `FileInputPositional`, `FileInputExcel`, `FileOutputDelimited`, `FileOutputPositional`, `FileOutputExcel`.
- **Transforms:** `Map` (tMap), `FilterRows`, `AggregateRow`, `Join` (tJoin), `SortRow`, `UniqueRow`, `ConvertType`, `Replace`, `Normalize`/`Denormalize`, `Unite`, `Replicate`.
- No database components, no non-file sources in this slice.

### 8.2 Recon requirements-doc template

A light `.docx` template (not too strict, not freeform) with four required blocks that survive text extraction (headings + tables):

1. **Inputs & schema** — one table per source (columns, types, key flags).
2. **Transformation / business rules** — prose, but each rule tagged with a stable id and a kind (match / tolerance / filter / aggregate / derive), recon-flavored (match keys, tolerances, break categories).
3. **Sample input** — a handful of rows per source (enough to exercise nulls, a break, a tolerance edge).
4. **Expected output** — matched / breaks / summary rows for that sample (the **test oracle**).

### 8.3 Representative recon pattern (strawman until a real job is supplied)

Two-source reconciliation: read source A + source B → normalize/convert types → match on key(s) with tolerance → split into **matched** and **breaks** (unmatched or out-of-tolerance, tagged with a break reason) → **summary** (counts + sums by reason) → write three files. To be refined against a real recon `.item`/JSON when available.

---

## 9. Platform Posture & Upgrade Playbook (`PLATFORM.md`)

- **Now:** VS Code 1.106, MCP + sampling, autonomous loop.
- **End-July VS Code update (unknown target version):**
  - **≥1.107:** native subagents (`chat.customAgentInSubagent.enabled`) and Agent Skills unlock. Optionally split roles into true custom-agent subagents; knowledge modules become native skills. No core rewrite.
  - **If MCP is ever disabled:** revert the thin orchestration layer to **handoffs** (Section 3.6).
- **Dependency posture:** libraries from the internal artifact repo are primary; stdlib fallbacks documented (Section 3.4).

---

## 10. Build Sequence / Phasing

- **Phase 0 — Deterministic core (no MCP yet).** `gen_knowledge.py` + knowledge pack; `run_and_validate.py`; `extract_doc.py`; `check_freshness.py`. Each verifiable standalone from the terminal. Prove the harness diffs a known-good and known-bad recon job correctly.
- **Phase 1 — MCP skeleton + one role.** Local MCP server (SDK) + the kickoff agent; one sampling-backed role (Configurator) end-to-end on a hand-made `flow_plan.json` for a trivial recon job. Proves sampling + tool-calls + terminal execution on the Citi laptop.
- **Phase 2 — Full loop.** All six roles + the deterministic control loop + feedback routing, on a hand-written recon `requirement_spec.json` (skip the doc for now). Loop converges on a real file-based recon job.
- **Phase 3 — Front door.** `extract_doc` + Doc-Interpreter + the recon template; run end-to-end from a `.docx`.
- **Phase 4 — Hardening.** More recon jobs, convergence guards, human checkpoints, `PLATFORM.md`, TTL maintenance in the loop.

Each phase is independently demoable and testable.

---

## Appendix A: Open items

- Confirm A1 (internal artifact repo has `mcp` + `python-docx`); if not, switch that component to the stdlib fallback.
- Obtain one real recon job (converted JSON or `.item`) to replace the strawman in Sections 4/8.
- Decide the exact `.docx` template layout with the recon team so extraction stays clean.
- Confirm whether the end-July VS Code update lands ≥1.107 (would change the orchestration upgrade path).

## Appendix B: Risks

- **R-1 (platform):** MCP disabled by policy after all → fall back to handoffs (loses full automation). Mitigated by decoupling.
- **R-2 (loop non-convergence):** LLM roles oscillate → convergence guards + human escalation with diagnosis.
- **R-3 (knowledge drift):** engine changes silently break generated configs → fingerprint/TTL self-healing.
- **R-4 (LLM invalid config):** Configurator invents keys → knowledge pack constrains + Assembler static-validates + engine execution is the hard gate.
- **R-5 (doc ambiguity / weak oracle):** thin or ambiguous expected output → Doc-Interpreter flags low confidence; human checkpoint.
- **R-6 (data governance):** sample data reaches the model via sampling → same trust boundary as normal Copilot use; document it explicitly for security review; keep samples minimal.
```
