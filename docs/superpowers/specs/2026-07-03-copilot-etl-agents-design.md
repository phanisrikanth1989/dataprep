# Design Spec: Copilot Multi-Agent ETL Config Generator

- **Date:** 2026-07-03
- **Version:** v3 (full autonomous system; hardened after two adversarial review rounds)
- **PLATFORM SUPERSEDED (2026-07-03):** Citi VS Code updated 1.106 -> 1.122. Per `2026-07-03-copilot-etl-agents-v1122-pivot.md`, the MCP-server + sampling orchestration and 1.106 platform posture (Sec 4, 13; constraint C1), the `.claude/skills` load surface + TTL freshness (C4, Sec 6.3), the resumable-subprocess execution model behind the engine-change staging / oracle harness / feedback loop (Sec 7-9), the repo layout (Sec 12), and the 1.106 data-egress framing (C2, Sec 2 control 4) are SUPERSEDED by the native subagents + Agent Skills design (free-agent loop; don't-minimize-egress). Still holding: the roster (role logic Sec 5.1 + contracts Sec 5.3), the curated-from-code knowledge (Sec 6.1-6.2), the feedback-loop shape (Sec 9, minus the retired tolerance routing), and the derived facts (Sec 10.4 -- now a convenience summary, no longer a security boundary). The oracle *framing* (Sec 8), the rule model (Sec 5.2), and the recon slice + Phases A-D (Sec 11) are governed by the DOMAIN banner below, not this one.
- **DOMAIN SUPERSEDED (2026-07-03):** the tool does data ENRICHMENT/prep, not reconciliation (SmartStream TLM reconciles). Per `2026-07-03-enrichment-scope-correction.md`, the rule model (Sec 5.2), the oracle framing (Sec 8), the recon slice + Phases A-D (Sec 11), and the code-injection component block (Sec 2 control 1 -- `python_dataframe` is now unblocked for enrichment) are SUPERSEDED. This DOMAIN correction governs the oracle / rule-model / recon-slice supersession; the PLATFORM banner above governs the 1.122 platform supersession. Both leave the role logic, the curated knowledge, the contracts, the extract layer, and the harness core intact.
- **Status:** DRAFT — pending final verification + user sign-off
- **Branch:** `feature/copilot-etl-agents`
- **Owner:** Recon team (A Arun)

> **Scope decision (user):** build the **full autonomous system**, not a narrow MVP. **Engine changes are authorized** ("everything in the code works and can be changed if needed"). The **only hard external constraint is VS Code 1.106**. Job execution is treated as the developer already treats it (run it directly, with human review) — a full OS sandbox is **optional later hardening**, not a build gate.
>
> **Review history:** v1 -> 6-lens adversarial review -> v2 -> 5-lens verification. All findings verified against engine source. Section 16 is the coverage matrix. This v3 closes the "remaining-blockers" by (a) making the authorized engine changes a first-class workstream, (b) sourcing knowledge from the engine's own typed structures (not the registry), and (c) re-proportioning security to the actual trusted-internal + human-review threat model.

---

## 1. Goal & Constraints

### 1.1 Goal

A **dev-supervised, fully autonomous multi-agent system** running **locally in VS Code GitHub Copilot** that turns a **Word (`.docx`) recon requirements doc** into a **validated DataPrep engine JSON job config**. It self-corrects via an **execution-based feedback loop** (generate -> run the real engine -> check a **multi-signal oracle** -> route failures **deterministically** to the responsible stage) up to **3-5 iterations**, then escalates to the developer for **final approval**. Correctness bar: **Talend parity**.

### 1.2 Hard constraints

| # | Constraint |
|---|---|
| C1 | **Only hard external constraint: VS Code 1.106.** Orchestration = MCP + sampling. Everything else in the DataPrep code may be changed as needed. |
| C2 | Runs **local**; no hosted server. Sampling egresses prompt content to the Copilot model boundary — so only **schema + rule text + derived structural facts + synthetic rows** are sampled; **real sample/expected data stays local** to the deterministic oracle. |
| C3 | **Model-portable across models that pass a capability preflight.** A run of record **pins a model** and stamps its identity. Reproducibility is memoization-scoped (Section 10). |
| C4 | Agent defs in **`.github/agents/`**; brains in `agents/`; knowledge in `.claude/skills/`. |
| C5 | Knowledge is **code-verified**: curated per-component schemas generated from the engine's typed structures + fixtures + a **live engine round-trip**, kept fresh by TTL + source-fingerprint. `ui_registry.json` is **UI metadata only** (it lacks tMap's config). |
| C6 | Dependencies from the Citi internal artifact repo (`mcp`, `python-docx`, `jsonschema`, `defusedxml`). |
| C7 | First domain: **recon, files-only**, phased (Section 11). |
| C8 | ASCII-only logs; fix-at-source; Talend parity (`CLAUDE.md`). |

### 1.3 Non-goals

Not the Talend->JSON converter; not DB/non-file sources or **fuzzy/similarity matching** in the first slice (no engine component exists; the code-exec escape hatch is out).

---

## 2. Threat Model & Security Posture (proportionate)

**Context (user's risk call):** requirements docs are authored by **trusted internal recon colleagues**, the developer **already runs the engine on this laptop**, and a **human reviews the config before first real use**. So the marginal risk of an LLM-authored-then-human-reviewed job over a hand-authored one is bounded, and the engine run needs no OS sandbox to be acceptable — it is the same act the dev performs today.

**Controls kept (cheap, good hygiene — no OS sandbox required):**
1. **Fail-closed component allowlist** at a pre-execution gate (the engine is fail-*open*: `engine.py:186-193` warns-and-skips unknown types). The recon slice allows file I/O + the transform set (Section 11.2); **code-injection components** (`tPython*`, `tJava*`, `tPythonDataFrame`, and free-form `{{java}}` tMap cells) are **blocked in the first slice**.
2. **Path jail (config-level):** every input/output path must resolve inside the job's `agents/work/<job>/` dir; reject absolute paths, `..`, symlink-escape, UNC/network paths.
3. **Human review before first real use:** un-batchable, shows component types + any code-bearing cells + the oracle summary; never auto-collapses on a green report; the reviewer signs off on **rules + keys**, not just pass/fail.
4. **Data minimization:** the LLM receives schema + rule text + **derived structural facts** (Section 10.4) + synthetic rows only; real sample/expected data stays local (Section 8.1). Repair/feedback prompts carry only **structural** error info (json-path + expected type/enum), never the offending value or engine-error/expected text verbatim (kills second-order injection).
5. **Hardened parsing:** `.docx`/XML via `python-docx`/`defusedxml` with entities off, DTD disabled, decompression caps.

**Documented residual (for security sign-off, NOT a build gate):** a crafted/careless requirements doc could steer the LLM to emit a job that does something unintended; the mitigation is the allowlist + human review + trusted authorship, not an OS sandbox. **Optional later hardening:** run the engine in a per-OS sandbox (`sandbox-exec`/`bwrap`/AppContainer) with an adversarial escape test — recommended before opening to less-trusted doc sources.

---

## 3. System Overview

```
 requirements.docx (trusted-internal)
   |
   v [extract_doc] deterministic: requirements.md + parsed tables
   |   - schema, rules            -> LLM
   |   - REAL sample/expected     -> LOCAL ONLY (oracle)
   |   - DERIVED structural facts (uniqueness, cardinality, null-rate, fan-out) computed from real rows -> LLM
   |   - synthetic rows           -> LLM
   |   - template-conformance gate (blocks present, tables parsed)
   v
 Doc-Interpreter (LLM)  -> requirement_spec.json   [validate+repair gate]
   v
 Flow-Designer (LLM)    -> flow_plan.json          [gate] --[HARD checkpoint if confidence!=high or ambiguity flags]-->
   v
 Configurator (LLM)     -> job_draft.json          [per-component config-key validator, BEFORE engine]
   v
 Assembler (LLM)        -> job.json ;  Validator (code) -> validation_report.json (schema+reference+allowlist)
   v
 Oracle/Test-Runner (deterministic): run engine (fresh subprocess, injected frozen clock/seed), read stats/reject/skipped,
    diff vs REAL expected (membership-exact tolerance), invariants (by cardinality), held-out, mutation rows -> test_report.json
   |
   pass(all signals)? -- yes --> [human review] --> DONE
   | no
   v
 Router (code): target = OWNER of the failing rule/field  (Diagnostician LLM writes only the value-blind human suggestion)
   +--> re-run target with sanitized feedback delta; invalidate stale downstream; freeze passing outputs (same data plane);
        budget 3-5; escalate BEST attempt (lexicographic score) with a routed diagnosis
```

Two-layer decoupling holds: durable core (roles, curated knowledge, oracle, contracts, engine changes) vs thin MCP orchestration; upgrades cleanly to >=1.107.

---

## 4. Orchestration on VS Code 1.106

Confirmed feasible by the platform lens: a single MCP tool call can make **multiple nested `sampling/createMessage`** calls and **spawn subprocesses** — so the deterministic loop lives in server code. The loop is a **resumable server-side state machine** (state persisted to disk after each stage; per-call wall-clock timeouts; `notifications/progress` per stage; a hang escalates; a killed run resumes from disk). The engine runs in a **fresh subprocess the server spawns** (with the engine's interpreter + JVM pinned in `.vscode/mcp.json`) — server-owned, not the agent's terminal tool. **Phase-1 preflight (hard gate):** a real `createMessage` self-test that verifies sampling works, reports the approval UX (one-time vs per-request), and pins a **capability-proven** model.

---

## 5. Agent Roster & Artifact Contracts

### 5.1 Roles

| Role | Kind | Produces | Note |
|---|---|---|---|
| Orchestrator | code | state, `iteration_log` | Deterministic loop, routing, gates, budget |
| Doc-Interpreter | LLM | `requirement_spec.json` | Schema+rules+derived-facts+synthetic in; no real values |
| Flow-Designer | LLM | `flow_plan.json` | Picks components + recon pattern |
| Configurator | LLM | `job_draft.json` | Fills config (components only) |
| Assembler | LLM | `job.json` | **Wiring only** (flows/triggers/subjobs/context) |
| **Validator** | **code** | `validation_report.json` | Schema + reference + allowlist + config-key check |
| Oracle/Test-Runner | code | `test_report.json` | Sandboxed-subprocess run + multi-signal check |
| Diagnostician | LLM | `feedback.suggestion` | **Value-blind**: rule-id + anchor + diff *shape* only; human-readable why |
| Router | code | `feedback.target_role` | **Deterministic, on the failing rule/field's OWNER** |
| Knowledge-Maintainer | **code** | curated schemas | **LLM-free** regeneration on staleness |

Every **LLM->artifact boundary** passes a shared gate: strip fences/prose -> strict `json.loads` -> jsonschema (formal schema) -> **adaptive repair-retry** (one targeted error per turn; budget scales with distinct-error count + wall clock, not a flat 3) -> hard-fail with a precise message. Enums are checked against a **small explicit synonym table** (case/whitespace fold only); anything outside is a **hard error** (no fuzzy nearest-enum). Component **IDs are deterministic/stable** across regenerations.

### 5.2 Rule model (recon-complete)

`requirement_spec.rules[]`: `kind (match|tolerance|filter|aggregate|derive)`, `cardinality (1:1|1:N|N:M)`, `keys` (composite per side), `priority/order` (waterfall), `direction/unmatched_side (left|right|both)`, `on_tolerance_fail (break_reason|nonmatch)`, `pre_group/net_on` (netting), **`duplicate_disposition`** (flag duplicate/multi-match as a break — the defining recon case), and `break_code` from a controlled enum **with an attached predicate** (for the predicate-consistency check). Doc-Interpreter **auto-flags** ambiguity (match+tolerance without `on_tolerance_fail`; non-unique lookup key per the derived facts; missing `direction`; duplicate-prone key) -> forces the human checkpoint.

### 5.3 Contracts (fixed)

- `requirement_spec.json`: adds `outputs[].key` (composite, required for diffing) and `derived_facts` (per-column uniqueness/null-rate/group fan-out, computed locally). `sample_input`/`expected_output` are **local references + checksums**, not inlined into sampled prompts. `max_sample_rows` cap.
- `job_draft.json` (Configurator) = `{components:[{id,type,config,schema}]}` **only**; `job.json` (Assembler) = draft + `flows`/`triggers`/`subjobs`/`context`. Flow keys are **`from`/`to`** (engine truth), not `source`/`target`.
- `test_report.json`: per-output `missing/unexpected/column_diffs`, per-component `status`/reject/`skipped`, **invariant results (by cardinality)**, held-out result, normalized failure signature. `error` derived from engine stats (Section 7).
- `feedback.json`: `target_role` set by the **code Router**; sanitized `findings` (rule-id + anchor + diff *shape*, no values); Diagnostician `suggestion` (human-readable). Supports **multiple targets**, topologically ordered (never regenerate a stage and its downstream consumer in the same pass).
- Every artifact + component `config` has a **formal JSON Schema (Draft 2020-12)** generated by `gen_knowledge.py`; role prompts use **strict-JSON exemplars** (never jsonc-with-comments).

---

## 6. Knowledge Pack (curated-from-code + TTL self-healing)

### 6.1 Source of truth — the engine's own typed structures, not the registry

The reviewers proved `ui_registry.json` **does not contain tMap's config** (4 scalar keys, 2 phantom; `matching_mode`/`join_keys`/`is_reject` = 0 hits) and carries Talend-field sub-key names for tFilterRows (`input_column`/`rvalue`) that differ from engine truth (`column`/`value`). So `gen_knowledge.py` builds **curated per-component config schemas** from:
1. the engine's **typed config structures** where they exist (tMap: the `map_config.py` dataclasses `MainInputCfg`/`LookupCfg`/`JoinKeyCfg`/`OutputCfg`), and the component `_validate_config` + docstrings elsewhere;
2. cross-checked against the repo **fixtures** (`tests/fixtures/jobs/**`); and
3. a **live engine round-trip** — feed a candidate config through the real engine and record accepted/required/ignored keys.

`ui_registry.json` is used only for **UI/connector metadata** and its **`visibleWhen` conditional relationships** (143 sites) — which feed conditional (context-aware) validation, one thing the registry *is* good for.

### 6.2 Machine artifacts (LLM-free)

Deterministic outputs: a **JSON Schema per component config** and per artifact (keys/types/required/enums/conditionals); a **landmine registry** anchored to specific code symbols + guard tests (die_on_error dual defaults, tMap triple-name, **operator no-op**, **matching_mode drops duplicates**, catch_output_reject is error-only, reject-is-a-flow, flow `from`/`to`); the **recon pattern library** (Section 11.3); and one **code-verified golden recon job**. Prose is template-filled from these facts — no LLM in generation.

### 6.3 One home + freshness (behavioral drift-detector)

Single load surface `.claude/skills/<name>/SKILL.md`; generated schemas/golden job under `agents/schemas`+`agents/templates` are **rendered into** the skill. Stale when TTL lapses **or** `source_fingerprint` != code hash **or** a **behavioral round-trip** (run the golden/candidate config through the engine, diff accepted/required keys) drifts **or** the pinned model identity changes. A drift flag **fails the build for that component**; regeneration is deterministic. This is exactly the TTL-managed live-docs mechanism — sourced from code, so it self-heals.

---

## 7. Engine Changes (DEFERRED to backlog — owned by the engine team)

Bounded, additive production-engine changes the agent system assumes will land. **Deferred and delegated per the owner's decision** — tracked with corrected, parity-safe predicates in `2026-07-03-copilot-etl-agents-backlog.md` **Section A** (and the non-engine follow-ups in **Section B**). They are NOT on the agent-system critical path: until they land, the phases that depend on them (esp. Phase B tolerance, deterministic-run tests) are gated, while Phases 0-2 scaffolding (roles, knowledge, harness on 1:1 data with a config-level fixed clock) proceed. Summary of the deferred set:

| Change | Why | Anchor |
|---|---|---|
| **Raise on non-`=` tMap join operator** | `operator` is parsed but read by no join path -> silently ignored; the LLM will emit `<=` for tolerance and it vanishes | `map_config.py` (`JoinKeyCfg.operator`); add to `validate_config` |
| **Port cartesian-size guard to equality joins** | equality `pd.merge` paths have no guard; forced `ALL_MATCHES` on non-unique keys can OOM | `map_joins.py` (`join_simple_equality`/`join_computed_equality`); guard exists only in constant/filter paths |
| **Injectable frozen clock + seed** | `TalendDate.getCurrentDate()` = `new Date()`, `RandomUtils` = `Math.random()` — unfreezable from Python; needed for deterministic tests | `TalendDate.java`, `RandomUtils.java` bridge hooks + a test-mode context |
| **Persist structured error records** | executor swallows exceptions to `{"status":"error","error":str(e)}`; the `.cause` class is dropped -> routing has no real signal | `executor.py:746-780`, `exceptions.py` |
| **Force `die_on_error=True` on allowlisted recon tMaps** | with `False`, expression errors are swallowed into the reject flow (below the executor catch) and mix with legitimate breaks | recon slice policy + `map_component.py` |
| **First-class duplicate/multi-match break** | duplicate reference rows are the defining recon case; UNIQUE_MATCH silently drops, ALL_MATCHES fans out — neither flags it | rule model + a canonical `UniqueRow`/`AggregateRow`-to-break pattern |

Each change gets unit + pipeline-fixture tests and a landmine guard test (6.2) so the knowledge pack stays truthful.

---

## 8. The Oracle & Test Harness

### 8.1 Deterministic extraction + local-only real data

`extract_doc.py` parses the Sample-Input/Expected-Output **tables directly** (python-docx), checksums them, keeps them **local**; never sampled. Fails fast if a block is missing / a table didn't parse / it's an image-only table.

### 8.2 Multi-signal oracle (pass requires ALL)

1. **Sample-equality** vs real expected, with **membership-exact** tolerance: the matched-vs-break **partition** is compared exactly against expected (so a wrong tolerance = wrong classification is caught and never masked); value columns compared with a **separate small test-epsilon** (never the business tolerance); `break_code` compared as an exact enum + **predicate-consistency** (each break row satisfies its code's predicate).
2. **Invariants parameterized by cardinality**: row conservation (`matched + left_breaks == input_left` for 1:1; adjusted for 1:N via fan-out facts), sum reconciliation, no-dup-key-in-matched (1:1), **both-side break accounting** for `direction=both`, declared-key uniqueness in expected. `left_breaks = UNION(join-miss, tolerance-fail-nonmatch)`.
3. **Held-out sample** (independently authored or engine-generated from the golden pattern — *not* a split of a thin doc sample) checked once before human approval; if the doc sample is too thin to both hold-out and exercise every rule kind, route to the human.
4. **Mutation rows** (duplicate/null key, one-sided, boundary tolerance) with expected outcomes computed by an **independent reference matcher** (the oracle-of-oracle) — so they validate *correctness*, not just invariants.

Diffs use **composite output keys** (multiset/bag comparison when no unique key; fail loudly if the declared key isn't unique in expected).

### 8.3 Reading engine failure signals

The engine swallows exceptions (`executor.py:746-780`; `engine.py:277-289`; tDie via `exit_code`). The oracle reads job `status`, per-component `status=="error"` + the **structured error record** (Section 7), and computes `skipped` by set-difference (unknown types are dropped with no stats entry). **Reject flows are mapped to their DECLARED recon output** and diffed as data (breaks) — reject non-emptiness is *not* treated as failure (business breaks are rejects). Because recon tMaps are forced `die_on_error=True` (Section 7), expression errors now propagate to the structured record instead of hiding in the reject channel.

### 8.4 Non-determinism handled at the source

Determinism is a property of the run, not a diff-time exclusion: the harness injects a **frozen clock + seed** into the engine (Section 7 change), forces a **single deterministic input file set** in the work dir (rather than rewriting `tFileList` order, which would test a different config than ships), and runs **N>=2** to detect residual jitter. A column that is non-deterministic **and business-relevant** is a **FAIL routed to Configurator**, never silently excluded. `TalendDate.getCurrentDate`/`Math.random`/`RandomUtils` are added to the blocked-expression set for the first slice.

---

## 9. Feedback Loop

- **Deterministic routing on the failing field's OWNER** (not the invariant's surface shape): a wrong **key/cardinality** -> the role that set it (Configurator, or Doc-Interpreter for the rule) — **not** Flow-Designer, which cannot fix a key; wrong **tolerance value** -> Configurator; a component **absent** from the graph -> Flow-Designer; **unknown/mistyped config key** -> Configurator; **dangling from/to / missing flow** -> Assembler; **filter-induced row-loss** (all-active-outputs miss) -> Configurator(filter); unclassifiable/plain-exception -> human. The Diagnostician writes only the value-blind *why/fix*.
- **Escalation ladder + history + sanitized delta:** the Router sees prior routings/outcomes; after N no-improvement re-runs it escalates one owner-stage upstream (incl. re-opening a confidently-wrong `requirement_spec`). Each re-run receives a **sanitized, typed feedback delta** that legitimately changes the artifact **and** the cache key (Section 10).
- **Artifact invalidation:** re-running stage N may regenerate stage N-1's artifact.
- **Per-output freeze on the same data plane** as correctness (held-out), exempting shifts the row-conservation invariant explains — so a strictly-better attempt is never rejected as a "regression."
- **Best-so-far, lexicographic:** rank by (invariant-clean > held-out-pass > sample-distance); escalate/return the best, not the last. Convergence guards operate on **canonicalized** artifacts + a normalized failure signature; detect period-<=K cycles.

---

## 10. LLM Reliability & Determinism

- **Per-boundary gate** (5.1): adaptive repair, one targeted error per turn, hard-fail with diagnosis. A **model-capability preflight** (golden-artifact round-trip) refuses a model that can't clear the boundary gates — converting a silent portability failure into an explicit "unsupported model" gate (reconciles C3).
- **Per-component config-key validator** at the Configurator boundary (before the engine): unknown keys, wrong types, out-of-enum, **and `visibleWhen`-conditional validity** (a key valid for positional but present in a delimited config is rejected). Recurses into **nested** structures (`inputs.lookups[].join_keys[].operator`). Accepts both registered type spellings (Talend `t`-prefixed and camelCase).
- **Determinism substrate (memoization-scoped):** `temperature:0` (best-effort hint); **cache keyed on `hash(all direct inputs incl. upstream-artifact hashes + feedback-delta hash + role_prompt + pack_fingerprint + model_id)`** (so an in-loop re-run with new feedback misses the cache and actually changes; a byte-identical replay hits); **canonicalize** every artifact; record each iteration's `(inputs_hash -> output)` so a whole trajectory replays. Reproducibility is stated honestly as "byte-identical-input replay," scoped to (model + pack + feedback-trace).
- **Golden tests assert oracle-PASS**, not output-equality (so a correct new model isn't failed by construction); equality snapshots reserved for the LLM-free tools. `result.model` recorded at fullest available granularity; unknown granularity => assume drift.
- **Context budget:** load only the per-component specs for components in `flow_plan.json`; schemas + landmines never truncated; cap sample rows; **preflight the model context limit + pre-count prompt tokens** (input truncation has no MCP signal) and check output `stopReason=="maxTokens"`; add a JSON continuation strategy for large drafts.

### 10.4 Derived structural facts (fixes masking + inference corruption together)

The correctness-critical inferences (uniqueness, cardinality, null-rate, group fan-out) that drive the `matching_mode`/duplicate footguns are **computed deterministically from the REAL local rows** and passed to the LLM as **facts** (e.g., "`ledger.txn_id`: unique; `statement.ref_id`: fan-out up to 3; `amt`: 0% null"), **never** as masked values. This closes both the egress hole and the "masking corrupts the uniqueness the LLM must judge" regression — the LLM judges structure from ground-truth facts, not from data whose structure was altered.

---

## 11. Recon Slice + Pattern Library

### 11.1 Phasing (full system, delivered in order)

A: one-sided **exact-match** (matched + left-breaks + summary) + **duplicate-key break**. B: **tolerance** (exact-join + post-split via `is_reject`, never `catch_output_reject`). C: **bidirectional** (two-pass A->B and B->A). D: **1:N / netting** (ALL_MATCHES + guarded merge + aggregate) and **waterfall** (ordered multi-pass). Out of first slice: fuzzy/similarity, DB.

### 11.2 Vocabulary + footgun neutralization

Allow: `FileInput/Output{Delimited,Positional,Excel}`, **`Map` (tMap, the recon primitive)**, `FilterRows`, `AggregateRow`, `SortRow`, `UniqueRow`, `ConvertType`, `Replace`, `Normalize`/`Denormalize`, `Unite`, `Replicate`. **`tJoin` excluded** from recon (can't do 1:N; one-sided reject; double-emits in left-outer+reject). Footguns neutralized via the Section 7 engine changes + the config-key validator (kill `operator`, guard the cartesian, force `ALL_MATCHES` only *with* the size guard, first-class duplicate break) and the landmine registry (`catch_output_reject` is error-only; tolerance/filter breaks use `is_reject`).

### 11.3 Pattern library + golden job

Named canonical patterns (two-sided match, tolerance-as-exact-join-plus-split, netting, waterfall, duplicate-break) and one **code-verified end-to-end golden recon job** (two-source: matched + both-side breaks + summary), re-verified against the engine each freshness cycle. The Configurator **few-shots from the golden job**, not prose.

---

## 12. Repo Layout

```
.github/agents/etl-orchestrator.agent.md
.vscode/mcp.json                              # server + pinned interpreter/JVM
.claude/skills/<name>/SKILL.md                # single knowledge load surface
agents/
  orchestrator/  roles/  tools/               # extract_doc, gen_knowledge, run_and_validate, check_freshness, validate_artifact, reference_matcher
  schemas/  templates/(golden job)  work/(encrypted-at-rest, retention policy)
  PLATFORM.md  README.md
```

---

## 13. Platform Posture

Now: 1.106, MCP + sampling, resumable loop. >=1.107 (possible end-July update): native subagents + skills unlock (experimental) — roles can split into true subagents, `.claude/skills` load natively, minimal rework. If MCP/sampling ever policy-disabled: handoffs fallback (same durable core). Cost: tens of sampling calls/job draw on Copilot quota — budget it.

---

## 14. Build Sequence

- **Phase 0 — Foundations (no LLM/MCP):** the Section 7 engine changes (each behind the coverage gate) + `gen_knowledge.py` (curated schemas from dataclasses/fixtures/round-trip + landmine registry + behavioral drift-detector) + `run_and_validate.py` (multi-signal oracle, invariants-by-cardinality, injected clock/seed, reference matcher) + `extract_doc.py` + the config-key validator + the golden recon job. Verifiable from the terminal.
- **Phase 1 — MCP + sampling preflight (hard gates):** server + kickoff agent + sampling self-test + approval-UX + capability-proven pinned model. One role end-to-end on a Phase-A job.
- **Phase 2 — Full loop, Phase A.** All roles + deterministic Router + resumable state machine + per-boundary gates.
- **Phase 3 — Front door + tolerance (Phase B).** `.docx` -> Doc-Interpreter (derived-facts) -> tolerance pattern.
- **Phase 4 — Bidirectional / 1:N / netting / waterfall (C-D); audit; PLATFORM.md; optional sandbox hardening.**

---

## 15. Open Items & Residual Risks

- Confirm on the Citi build: sampling round-trip + approval UX, a capability-proven pinnable model, org MCP-registry policy, artifact-repo libs, end-July VS Code target (>=1.107 changes the upgrade path).
- Obtain one real recon `.item`/JSON to validate the golden job + template.
- Residual: the oracle is ultimately bounded by the human-authored expected data (mitigated by invariants + independent held-out + reference-matcher mutation, not eliminated); reproducibility is memoization-scoped; the documented prompt-injection-via-doc residual (Section 2) is accepted under trusted-internal authorship + human review, with the OS sandbox as recommended later hardening.

---

## 16. v2-Verification -> v3 Coverage

| Lens | Blocker | v3 resolution |
|---|---|---|
| Security | S1 sandbox mechanism unspecified | Re-proportioned (Sec 2): trusted-internal + human-review; run-as-dev-does; sandbox = optional hardening + documented residual |
| Security | S2/S3 Groovy uncontainable; typed-param vs tMap expressions | Block code-injection components in slice; tMap expressions validated + `operator` killed; residual owned, not hand-waved |
| Security | S4 oracle bounded by doc author; S5 residual egress; S7 Diagnostician values | Sec 15 stated limitation + human reviews rules/keys; Sec 10.4 derived-facts (no real values sampled); Sec 5.1 Diagnostician value-blind |
| Feedback | 1 non-determinism quarantine masks bugs | Sec 8.4 injected clock/seed at source (engine change) + N-run + fail-not-exclude |
| Feedback | 2 routing misroutes to Flow-Designer | Sec 9 route on failing field's OWNER |
| Feedback | 3 die_on_error reject-channel ambiguity | Sec 7 force die_on_error=True + Sec 8.3 reject-as-declared-output |
| Feedback | 4 cache vs escalation; 5 freeze vs held-out; 6 mutation oracle | Sec 10 cache-key incl feedback delta; Sec 9 freeze on same plane; Sec 8.2 reference matcher |
| Architecture | registry lacks tMap config; drift can't heal | Sec 6.1 curated from dataclasses/fixtures/round-trip; registry=UI-only; behavioral drift-detector |
| LLM-rel | cache key; repair convergence; golden-by-equality; masking corrupts inference | Sec 10 full-input cache key; adaptive repair + capability preflight; oracle-PASS goldens; Sec 10.4 derived facts |
| Recon | operator no-op; duplicate disposition; cartesian guard; invariants 1:1; reject types | Sec 7 engine changes (operator raise, guard, duplicate break); Sec 8.2 invariants by cardinality; Sec 6.2/11 landmine + is_reject pattern |
| Platform | control-loop feasible; hang; model; execution | Sec 4 resumable state machine + preflight + subprocess; confirmed feasible |
```
