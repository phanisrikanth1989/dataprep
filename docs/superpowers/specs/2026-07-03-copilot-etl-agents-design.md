# Design Spec: Copilot Multi-Agent ETL Config Generator

- **Date:** 2026-07-03
- **Version:** v2 (hardened after 6-lens adversarial review)
- **Status:** DRAFT — pending re-review + user sign-off
- **Branch:** `feature/copilot-etl-agents`
- **Owner:** Recon team (A Arun)
- **Related:** `CLAUDE.md`, `docs/guides/AUTHORING_JOB_JSON.md`, `src/router/ui_registry.json`, `docs/ai-prompts/*`

> **v1 -> v2:** v1 was reviewed by six adversarial lenses (platform, security, architecture, feedback-loop, LLM-reliability, recon-domain). Four returned "do not build as specified." The orchestration bets held; the oracle, rule model, security model, and LLM boundaries were redesigned. Section 15 is the findings-to-fix coverage matrix.

---

## 1. Goal & Constraints

### 1.1 Goal

A **dev-supervised, autonomous multi-agent system** that runs **locally on the developer's laptop inside VS Code GitHub Copilot** and turns a **Word (`.docx`) requirements document** into a **validated DataPrep engine JSON job config**. It self-corrects through an **execution-based feedback loop** — generate config, run it through the real engine **in a sandbox**, check output against a **multi-signal oracle**, route failures **deterministically** to the responsible stage — looping automatically up to **3–5 times** before escalating to a developer who gives **final approval**. Correctness bar: **Talend parity**.

### 1.2 Success criteria

1. From a filled recon requirements doc, the system produces a job JSON that (a) passes the **multi-signal oracle** (sample-equality **and** invariants **and** a held-out sample), not merely sample-equality, and (b) a human approves. "Sample matches expected" is **necessary, not sufficient** (recon review C1).
2. On failure, it escalates with a **precise, deterministically-routed** diagnosis, or returns the **best-scoring** attempt — never a confidently-wrong silent pass.
3. It stays correct as the engine evolves (fingerprint/TTL self-healing) **and** as the Copilot model changes (model-identity stamp + golden tests).

### 1.3 Non-goals

- Not a hosted service / server. **Local only.**
- Not the Talend->JSON converter (that path stays for `.item` sources).
- Not DB jobs, non-file sources, or **fuzzy/similarity matching** in the first slice (recon review — fuzzy is explicitly out; no engine component exists for it and the code-exec escape hatch is excluded for security).
- Not fully unattended production authoring — a human approves before first real use.

### 1.4 Hard constraints

| # | Constraint | Consequence |
|---|---|---|
| C1 | Runs **local**; no hosted server. **Sampling egresses prompt content to the Copilot model boundary** — so only **schema + rule text + synthetic/masked data** is ever sampled; **real sample/expected data stays local** to the deterministic oracle (never sampled). | See Sections 2, 7 |
| C2 | Target **VS Code 1.106**; design for clean upgrade at >=1.107 | No native subagents/skills; MCP + sampling |
| C3 | **Model-portable** (not "agnostic"): works with whatever model Copilot serves, but a **run of record pins a model** and stamps its identity. Reproducibility is scoped to *fixed model + fixed pack*. | See Sections 9, 4 |
| C4 | Agent defs in **`.github/agents/`** | Thin shims; brains in `agents/` |
| C5 | Knowledge grounded in **code-verified truth**, with `ui_registry.json` as primary shape source and **code as the drift-detector** | See Section 6 |
| C6 | Dependencies allowed from the **Citi internal artifact repo** (`mcp`, `python-docx`, `jsonschema`, `defusedxml`); stdlib fallback documented | See Section 4.4 |
| C7 | First slice: **recon, files-only**, and initially **one-sided exact/tolerance match + summary**; bidirectional/1:N/netting/waterfall are later phases | See Sections 10, 13 |
| C8 | **`job.json` is executable code, not inert config** (tMap runs Groovy; tPython\* runs `exec`). Treated under the Section 2 threat model. | See Section 2 |
| C9 | ASCII-only logs; fix-at-source; Talend parity | From `CLAUDE.md` |

### 1.5 Assumptions — now HARD gates, not soft assumptions (platform/security reviews)

- **A1 (Phase 1 gate):** Sampling works on the Citi build with a **real `createMessage` round-trip**, the **approval UX is one-time-per-server** (not per-request — if per-request, the autonomous premise fails and we redesign), and a **known-good model can be pinned** via `chat.mcp.serverSampling`. Verified by a preflight self-test before any pipeline work.
- **A2 (Phase 1 gate):** A local `.vscode/mcp.json` server is permitted under org MCP-registry policy, and sampling is not policy-blocked for this content.
- **A3 (security gate):** InfoSec sign-off that **synthetic/masked** sample data over sampling is in-scope for the enterprise no-retention/no-train terms. (We do not send real data — see C1.)
- **A4:** Internal artifact repo has `mcp`, `python-docx`, `jsonschema`, `defusedxml`; else stdlib fallback.

---

## 2. Threat Model & Security Posture (NEW — top priority)

**Assets:** the developer's laptop + its ambient credentials (SSO/Kerberos, `~/.ssh`, `~/.aws`, browser profiles), the corporate network the laptop sits on, and real recon (financial) data. **Adversary inputs:** an **untrusted `.docx`** (authored/emailed by others) and **LLM output** (which the `.docx` can steer via prompt injection). **The danger:** `job.json` is executable code — tMap cell expressions run **unsandboxed Groovy** (`bridge.py` -> `JavaBridge.java`, no `SecureASTCustomizer`/`SecurityManager`), `tPythonDataFrame` runs `exec()` with real builtins, and file components read/write arbitrary paths. So the raw pipeline is a clean **`.docx` -> LLM -> config -> execution -> RCE-as-developer** chain, firing **during** the autonomous loop, **before** any human gate.

**Controls (all mandatory):**

1. **Sandboxed, out-of-process execution.** The oracle runs each generated job in a **fresh child process** (not in-process), under: no network, a **filesystem jail** (input dir read-only; output only under `agents/work/<job>/out`; reject absolute paths, `..`, symlinks-escaping-jail, UNC/network paths), no inherited secrets/tokens, and CPU/wall/memory limits. This single control neutralizes RCE blast radius, file-exfiltration, and cross-iteration state leakage.
2. **Fail-closed component allowlist.** A pre-execution gate rejects any component `type` not on the recon slice allowlist (the engine itself is fail-*open* — `engine.py:186-193` warns-and-skips — so we cannot rely on it). **Code-bearing components** (tMap outputs/columns containing `{{java}}` free-form, `tPython*`, `tJava*`, `tPythonDataFrame`) are **blocked in the first slice**; tMap is allowed but its expressions are validated to a **safe subset** (no `System`/`Runtime`/`File`/`ProcessBuilder`/`Thread`/reflection/`.execute()`), and a `SecureASTCustomizer` denylist is added to the bridge as defense-in-depth.
3. **Data minimization.** LLM roles receive **schema + rule text + synthetic/masked sample rows** only. **Real** `sample_input`/`expected_output` are extracted **deterministically** (Section 7.1) and never leave the local oracle. This closes the egress hole *and* the LLM-transcription-corruption hole in one move.
4. **Human gate before first real use.** The mandatory human review shows the **component types**, any **code-bearing cells**, and the oracle summary — **un-batchable**, no auto-approve, and it never auto-collapses on a green report (a passing result must not suppress scrutiny).
5. **Prompt-injection defenses.** `extract_doc` delimits doc content as **data, not instructions**; the Configurator emits **typed params chosen from an allowlist**, never free-form code; expected-output and engine-error text are **never fed verbatim** back into an LLM prompt (kills second-order injection via `feedback.json`).
6. **Audit & secrets.** Each run records: `.docx` SHA-256, pack `source_fingerprint`, **model id+version**, prompts/responses, and final `job.json` hash into an **append-only** record. `agents/work/` is **encrypted-at-rest with a retention/secure-delete policy** — never "gitignore as a control." Every artifact is **secret-scanned** before write/sample; secrets never go in artifacts.
7. **Hardened parsers.** `.docx`/XML parsing uses `defusedxml`/`python-docx` with entity resolution off, DTD disabled, and decompression-ratio/size caps (billion-laughs / zip-bomb).

---

## 3. System Overview

### 3.1 End-to-end flow

```
 requirements.docx (UNTRUSTED)
        |
        v
  [extract_doc] (deterministic): requirements.md  +  deterministically-parsed tables:
        |                          - schema, rules  -> to LLM
        |                          - REAL sample_input / expected_output -> LOCAL ONLY (oracle)
        |                          - synthetic/masked sample rows -> to LLM
        |                          - template-conformance gate (4 blocks present + tables parsed)
        v
  Doc-Interpreter (LLM, synthetic data only)  -> requirement_spec.json   [validate+repair gate]
        v
  Flow-Designer (LLM)                         -> flow_plan.json          [validate+repair gate]  --[HARD checkpoint if confidence!=high]-->
        v
  Configurator (LLM)                          -> job_draft.json          [per-component config-key validator, BEFORE engine]
        v
  Assembler (LLM: wiring)                     -> job.json
  Validator (deterministic tool)              -> validation_report.json  (schema + reference + allowlist)
        v
  Oracle / Test-Runner (deterministic, SANDBOXED): run engine (fresh subprocess), read stats/reject/skipped,
     diff vs REAL expected (per-column tolerance), check invariants, held-out sample, mutation rows
        |                                     -> test_report.json
     pass(all signals)? -- yes --> [human review BEFORE first real use] --> DONE
        | no
        v
  Deterministic router (code): pick target stage from the INVARIANT that broke  (Diagnostician LLM writes only the human-readable suggestion)
        +--> re-run from target stage; invalidate stale downstream; freeze passing outputs; track best-so-far
             (budget 3-5; escalate best attempt with a routed diagnosis)
```

### 3.2 Two-layer decoupling (unchanged, still sound)

Durable core (roles, knowledge pack, oracle, artifact contracts, schemas) is mechanism-agnostic; only the thin orchestration layer (MCP) is platform-dependent. Upgrades cleanly to >=1.107 native subagents/skills.

---

## 4. Orchestration on VS Code 1.106

### 4.1 Mechanism (confirmed feasible by the platform lens)

A local **MCP server** (stdio) exposes the pipeline. **Verified:** a single MCP tool call can internally make **multiple nested `sampling/createMessage`** calls and **spawn subprocesses** — so the deterministic loop lives in server code, not LLM improvisation. Sampling uses the user's Copilot model, no external key.

### 4.2 Loop as a resumable server-side state machine

To avoid the "one multi-minute tool call with no timeout" hang (platform F1): the loop is a **state machine whose state persists to disk** after every stage. Each iteration is a **bounded** unit with a **wall-clock timeout** on each sampling call and each engine run; `notifications/progress` is emitted per stage; a hang is a first-class error that escalates. A killed/failed run **resumes from disk state**, not from scratch.

### 4.3 Execution is server-owned and sandboxed

The engine runs in a **fresh subprocess the server spawns** (Section 2 control 1) — **not** via the agent's terminal tool (v1 inconsistency, platform F4 fixed). The server's interpreter (with pandas/pyarrow/py4j + a reachable JVM) is set in `.vscode/mcp.json`.

### 4.4 Dependencies

Primary: `mcp`, `python-docx`, `jsonschema`, `defusedxml`. Stdlib fallback documented (JSON-RPC over stdio; `zipfile`+`defusedxml` for `.docx`). Per C6/A4.

### 4.5 Preflight (Phase-1 hard gate)

On first use the server runs a **sampling self-test** (one trivial `createMessage`), asserts the pinned model responds, and reports approval-UX behavior (A1). Fails fast with remediation if sampling is blocked/broken/per-request.

---

## 5. Agent Roster & Artifact Contracts

### 5.1 Roles

| Role | Kind | Produces | Note |
|---|---|---|---|
| Orchestrator | code | `iteration_log`, state | Deterministic loop + routing + gates |
| Doc-Interpreter | LLM | `requirement_spec.json` | Sees synthetic data only |
| Flow-Designer | LLM | `flow_plan.json` | Chooses components + recon pattern |
| Configurator | LLM | `job_draft.json` | Fills config; validated pre-engine |
| Assembler | LLM | `job.json` | **Wiring only** (flows/triggers/subjobs/context) |
| **Validator** | **code** | `validation_report.json` | **Split out of Assembler**: schema + reference + allowlist |
| Oracle/Test-Runner | code | `test_report.json` | Sandboxed run + multi-signal check |
| Diagnostician | LLM | `feedback.suggestion` | **Human-readable suggestion only; does NOT decide the stage** |
| Router | code | `feedback.target_role` | Deterministic, from the broken invariant |
| Knowledge-Maintainer | **code** | pack | **LLM-free** deterministic regeneration |

Every **LLM->artifact boundary** passes through a shared **parse -> strip-fences -> strict `json.loads` -> jsonschema-validate -> repair-retry(<=3) -> hard-fail** gate (LLM-reliability C2). Enums are normalized to closed sets at each boundary.

### 5.2 Rule model (expanded per recon review — the decisions that determine correctness)

`requirement_spec.rules[]` entries carry:
- `kind`: `match | tolerance | filter | aggregate | derive`
- `cardinality`: `1:1 | 1:N | N:M` (drives UNIQUE_MATCH vs ALL_MATCHES)
- `keys`: composite key columns per side
- `priority`/`order`: for **waterfall** (try key A; else key B) — ordered multi-pass, not AND-merged lookups
- `direction`/`unmatched_side`: `left_only | right_only | both` (drives the **two-pass** bidirectional-break pattern)
- `on_tolerance_fail`: `break_reason | nonmatch` (out-of-tolerance = tolerance-break vs non-match — different outputs + summary)
- `pre_group`/`net_on`: **netting** (aggregate before match)
- `break_code`: from a **controlled enum** (not free text)

The Doc-Interpreter **auto-flags ambiguity** (a match rule with a sibling tolerance rule but no `on_tolerance_fail`; a non-unique lookup key; a missing `direction`) -> forces the human checkpoint.

### 5.3 Contracts (fixed per architecture review)

- **`requirement_spec.json`**: adds required `outputs[].key` (composite) for diffing; `sample_input`/`expected_output` are **references/checksums** to the locally-held real rows (values not inlined into what's sampled); `max_sample_rows` cap.
- **`job_draft.json`** (Configurator) = `{components:[{id,type,config,schema}]}` **only**. **`job.json`** (Assembler) = draft **plus** `flows`/`triggers`/`subjobs`/`context`. ("Same shape" claim removed.) Flow keys are **`from`/`to`** (engine truth), not `source`/`target` (stale doc).
- **`test_report.json`**: structured signals — per-output `expected_rows/actual_rows/missing/unexpected/column_diffs`, per-component `status`/reject-flow/`skipped`, **invariant results**, held-out result, and a normalized **failure signature**. `error` is derived from **engine stats**, not a caught exception (Section 7.3).
- **`feedback.json`**: `target_role` (set by the **code router**), `findings[]` with `anchor` + rule-id, and the Diagnostician's `suggestion` (human-readable). Supports **multiple targets** (multi-root failures).
- Every artifact has a **formal JSON Schema** (Draft 2020-12) generated by `gen_knowledge.py`; role prompts use **strict-JSON exemplars** (never jsonc-with-comments — that would teach invalid output).
- Component **IDs are stable** across regenerations (deterministic id scheme) so feedback anchors / stats keys / prior approvals survive a stage re-run.

---

## 6. Knowledge Pack & Self-Healing (reworked)

### 6.1 Source of truth — inverted

`ui_registry.json` is **primary** for keys/types/defaults/required + **conditional `visibleWhen`** (ast cannot derive these — architecture review proved 4 components need 4 incompatible extraction strategies; 21+ dynamic-key sites). Code-scrape (registration decorators + `_validate_config` required-ness) is the **drift-detector**. **Conflict rule:** registry wins on shape; code wins on required-ness; any mismatch raises a **stale flag** (which *is* the self-healing signal — resolving the C5 "registry may be stale" tension).

### 6.2 Machine artifacts (LLM-free)

`gen_knowledge.py` deterministically emits: (a) a **JSON Schema per component `config`** (keys/types/required/enums) and per artifact; (b) a fixed **landmine registry** as machine facts — `die_on_error` dual defaults, tMap triple-name agreement, **`operator` is a no-op**, **`matching_mode` default drops duplicate matches**, reject-is-a-flow-not-a-trigger, flow `from`/`to`; (c) a **recon pattern library** (Section 10.3); (d) one **code-verified golden recon job**. Prose is template-filled from these facts. **No LLM** in generation (LLM-reliability C7, architecture #4).

### 6.3 One home, forward-compatible

Single store: `.claude/skills/<name>/SKILL.md` (+ generated reference-data files). Loaded as plain context on 1.106; native skills at >=1.107 (experimental). `agents/knowledge` / `agents/registry` as separate trees are **removed** (kills triplication drift, architecture #3).

### 6.4 Freshness — code AND model drift

Stale when TTL lapses **or** `source_fingerprint` != code hash **or** the **pinned model identity changes** (LLM-reliability H3). Regeneration is the deterministic `gen_knowledge.py`; a model change also forces the **golden-test suite** to re-run before the system is trusted.

---

## 7. The Oracle & Test Harness (redesigned — was the weakest part)

### 7.1 Deterministic oracle extraction

`extract_doc.py` parses the doc's Sample-Input and Expected-Output **tables directly** (python-docx cell walk) into typed rows, **checksums** them, and keeps them **local**. They are **never** routed through a sampling call (fixes LLM-transcription corruption C1 + egress F3 at once). A conformance gate fails fast if a block is missing, a table didn't parse, or it's an image-only table.

### 7.2 Multi-signal oracle (not sample-equality)

A config passes only if **all** hold:
1. **Sample-equality** vs the real expected rows, with **per-column tolerance from the rule spec** — exact by default; **columns governed by a tolerance rule are compared EXACTLY** against expected (so the test can't mask the very tolerance bug it encodes — LLM-reliability C5 / recon M); break `break_code` compared as an **exact enum** (free text is a non-compared annotation), plus a **predicate-consistency** check (each break row actually satisfies its code's predicate).
2. **Invariants** independent of the sample: row conservation (`matched + left_breaks == input_left`; symmetric for right), **sum reconciliation**, **no duplicate key in matched**, both-side break accounting, declared-key **uniqueness in expected**.
3. **Held-out sample** the loop never sees, checked once before human approval (guards overfitting — recon C1, LLM-reliability M1).
4. **Mutation rows** auto-injected (duplicate key, null key, one-sided-only, boundary tolerance) to exercise the edges a thin sample misses.

Diffs use **composite output keys** (multiset/bag comparison when no unique key); test-comparison **epsilon is separate** from business tolerance.

### 7.3 Reading engine failure signals (the taxonomy fix)

The engine **swallows exceptions** (`executor.py:746-780` -> stats dict; `engine.py:277-289` -> error dict; tDie does not propagate — feedback-loop C1). So the oracle reads: job `status`, per-component `status=="error"` + `error` string, **non-empty reject flows**, and **`skipped`** components — each a first-class failure signal with its own route. **Additive engine change (owned by this project):** persist a **structured error record** (`component_id`, exception class, `cause`) into `execution_stats` so routing has a real signal instead of `str(e)`.

### 7.4 Non-determinism quarantine

Freeze the clock (inject an **as-of date** context var), force **deterministic `tFileList` order** in test mode, **seed** randomness. **Run the engine twice**; any column that differs run-to-run is flagged **non-comparable** and excluded from the diff (else dates/order/random cause permanent false-fails — feedback-loop C3).

---

## 8. Feedback Loop & Convergence

- **Deterministic routing (code, not LLM):** the Router picks `target_role` from **the invariant that broke** — row-count/cardinality invariant -> Flow-Designer (graph/cardinality); value-only diff on conserved rows -> Configurator (expression); schema/reject/skipped -> Configurator(schema) or Assembler(wiring); unparseable/plain-exception -> human. The Diagnostician (LLM) writes only the human-readable *why/fix*, never the control decision (feedback-loop H2 / recon routing / LLM-reliability H2).
- **Escalation ladder + history:** the Router sees prior routings/outcomes; after N no-improvement re-runs of a stage it escalates **one stage upstream** (including re-opening a **confidently-wrong** `requirement_spec.json` -> Doc-Interpreter, not only "ambiguous").
- **Artifact invalidation:** re-running stage N may **invalidate/regenerate** stage N-1's artifact (fixes "stale upstream caps the fix" H2).
- **Multi-target:** `feedback` can carry several findings; independent roots fan out per iteration (multi-root convergence H3).
- **Per-output freeze:** already-passing outputs are frozen as **regression gates** so re-running a stage can't silently regress `matched` while fixing `breaks` (H5/M9).
- **Best-so-far:** track a **monotonic diff-distance**; escalate/return the **best** attempt, not the last (H5).
- **Convergence guards** operate on **canonicalized** artifacts (sorted keys, normalized expressions) and a **normalized failure signature** (class + component + rule-id + bucketed diff shape); detect **period-<=K cycles**, not just consecutive repeats.
- **Scoped re-runs:** a re-run's new artifact is diffed against the prior; changes **outside the targeted anchor** are rejected (prevents collateral regressions M4).

---

## 9. LLM Reliability & Determinism (NEW)

- **Per-boundary gate** (Section 5.1): strip -> strict parse -> jsonschema -> repair-retry -> hard-fail. Applied to **every** artifact, including `requirement_spec.json` (before it poisons downstream).
- **Per-component config-key validator** at the Configurator->`job_draft` boundary (before the expensive engine run): unknown keys, wrong types, out-of-enum values (e.g., `join_mode not in {LEFT_OUTER_JOIN, INNER_JOIN}`) are **hard errors** (fixes "shallow validator at the wrong boundary" LLM-reliability C4 — the existing `validator.py` only does 4 shallow checks).
- **Determinism substrate:** request `temperature:0` (best-effort hint), **cache** artifacts keyed by `hash(doc + pack_fingerprint + role_prompt + model_id)`, **canonicalize** every artifact, **golden-test** each role against frozen input/output pairs, **stamp model id+version** on every artifact. Reproducibility scoped to *fixed model + pack* (C3).
- **Context budget:** load **only** the per-component specs for components present in `flow_plan.json` (not the 283 KB registry); priority order where **schemas + landmines are never truncated**; cap sample rows; set `maxTokens`; **truncation is a hard error**, not silent loss (H4).
- **Mandatory low-confidence gate:** the human checkpoint fires when `confidence != high` **or** any independent signal (non-empty `ambiguities`/`uncovered_rules`, missing doc block, sample too thin to exercise a declared rule kind) — not the LLM's self-report alone (H5).

---

## 10. Recon First Slice + Pattern Library

### 10.1 Scope (phased)

Recon, files-only. **Phase A:** one-sided **exact-match** recon (matched + left-only breaks + summary). **Phase B:** **tolerance** (exact-join + post-split). **Phase C:** **bidirectional** breaks (two-pass). **Phase D:** **1:N/netting** (ALL_MATCHES + aggregate) and **waterfall** (ordered multi-pass). **Out of first slice:** fuzzy/similarity matching (no engine component; escape hatch excluded for security), DB.

### 10.2 Component vocabulary + footgun neutralization

Allowlist: `FileInput/Output{Delimited,Positional,Excel}`, **`Map` (tMap)**, `FilterRows`, `AggregateRow`, `SortRow`, `UniqueRow`, `ConvertType`, `Replace`, `Normalize`/`Denormalize`, `Unite`, `Replicate`. **tMap is THE recon matching primitive; `tJoin` is excluded from the recon slice** (can't do 1:N, one-sided reject only, and left-outer+reject **double-emits** — recon H). Footguns neutralized: **kill the `operator` field** in generated tMap JSON (any non-`=` is a silent no-op — engine raises on it as fix-at-source); **force `ALL_MATCHES`** when a lookup key is not schema-proven unique (default `UNIQUE_MATCH` silently drops duplicates).

### 10.3 Pattern library + golden job

The knowledge pack ships **named canonical recon patterns** (two-sided match, tolerance-as-exact-join-plus-split, netting, waterfall) and **one code-verified end-to-end golden recon job** (two-source: matched + both-side breaks + summary), re-verified against the engine. The Flow-Designer selects a pattern and the Configurator **few-shots from the golden job**, not from prose (recon L, LLM-reliability, architecture).

---

## 11. Repo Layout

```
.github/agents/etl-orchestrator.agent.md     # kickoff agent (target: vscode)
.vscode/mcp.json                              # local server + pinned interpreter
.claude/skills/<name>/SKILL.md                # single knowledge home (+ generated schemas/reference)
agents/
    orchestrator/        # MCP server + deterministic loop/router/state machine
    roles/               # role prompts (strict-JSON exemplars)
    tools/               # extract_doc, gen_knowledge, run_and_validate (sandbox), check_freshness, validate_artifact
    schemas/             # generated JSON Schemas (artifacts + per-component config)
    templates/           # recon .docx template + code-verified golden job
    work/                # per-job artifacts (encrypted-at-rest, retention policy; NOT a gitignore control)
    PLATFORM.md, README.md
```

---

## 12. Platform Posture & Upgrade Playbook (`PLATFORM.md`)

- Now: 1.106, MCP + sampling, resumable server-side loop.
- >=1.107 (possible end-July update): native subagents + skills unlock (experimental) — roles can split into true subagents; `.claude/skills` load natively. Minimal rework.
- If MCP/sampling disabled by policy: **handoffs** fallback (human-advanced; same roles/knowledge/oracle). Note: handoffs still sample the same (now synthetic) data.
- Cost: ~tens of sampling calls/job draw on Copilot quota; budget it.

---

## 13. Build Sequence

- **Phase 0 — Safety + determinism foundations (no LLM, no MCP).** `gen_knowledge.py` (registry-primary + schemas + landmine registry + drift-detector), the **sandboxed `run_and_validate.py`** with the multi-signal oracle + invariants + non-determinism quarantine, `extract_doc.py` (deterministic tables + conformance gate), the **structured-error engine change**, the per-component config-key validator, the golden recon job. All verifiable from the terminal. **This is where the disqualifying findings are closed.**
- **Phase 1 — MCP + sampling preflight (A1/A2/A3 gates).** Server skeleton + kickoff agent + sampling self-test + approval-UX verification + pinned model. One role (Configurator) end-to-end on a hand-made `flow_plan.json` for a Phase-A recon job.
- **Phase 2 — Full loop, Phase-A recon.** All roles + deterministic router + resumable state machine + per-boundary gates, converging on one-sided exact-match recon.
- **Phase 3 — Front door + tolerance (Phase B).** `.docx` -> Doc-Interpreter (synthetic-only) -> tolerance pattern.
- **Phase 4 — Bidirectional / 1:N / netting / waterfall (Phases C-D), hardening, audit, PLATFORM.md.**

---

## 14. Open Items & Residual Risks

- Confirm A1-A4 on the real Citi build (sampling round-trip, approval UX, model pin, org registry policy, artifact-repo libs).
- Obtain one real recon `.item`/JSON to validate the golden job + template against reality.
- Confirm the end-July VS Code target version (>=1.107 changes the upgrade path).
- Residual: the sandbox is defense-in-depth, not proof; code-bearing components stay human-gated. Reproducibility is bounded to a pinned model. The oracle is stronger but still ultimately bounded by the human-authored expected data (mitigated by invariants + held-out + mutation, not eliminated).

---

## 15. Findings-to-Fix Coverage (v1 review -> v2)

| Lens | Finding | v2 fix |
|---|---|---|
| Security | F1 RCE (tMap Groovy / tPython exec), in-process | Sec 2.1 sandbox out-of-process; 2.2 allowlist + code-bearing blocked; safe-subset + SecureAST |
| Security | F2 prompt-injection -> RCE chain | Sec 2.5 doc-as-data, typed-param allowlist, no error/expected text back to LLM |
| Security | F3 / platform C1 data egress ("no egress" false) | C1 reworded; Sec 2.3 + 7.1 synthetic-to-LLM, real data local |
| Security | F4 gate after danger; F5 file blast; F6 fail-open | Sec 2.4 gate before first use; 2.1 FS jail; 2.2 fail-closed allowlist |
| Security | F7 audit/model; F8 secrets; F9 parsers | Sec 2.6 audit+model id+encryption; 2.6 secret scan; 2.7 defusedxml |
| Feedback | C1 engine swallows exceptions | Sec 7.3 read stats/reject/skipped + structured-error engine change |
| Feedback | C2 weak oracle / C3 non-determinism | Sec 7.2 multi-signal + held-out + mutation; 7.4 quarantine + run-twice |
| Feedback | H1-H6 misroute/stale/multi-root/guards/die_on_error | Sec 8 deterministic router + ladder + invalidation + multi-target + freeze + best-so-far + canonical guards |
| Architecture | knowledge-from-ast unreliable; source inversion | Sec 6.1 registry-primary + code drift-detector |
| Architecture | triplication; Maintainer LLM; Assembler fused; contracts | Sec 6.3 one home; 6.2/5.1 LLM-free maintainer; 5.1 split Validator; 5.3 contracts fixed |
| LLM-rel | C1 LLM-transcribed oracle; C2 no structured output; C3 no schemas | Sec 7.1 deterministic extraction; 5.1 per-boundary gate; 6.2 formal schemas |
| LLM-rel | C4 shallow/late validation; C5 tolerance masks bug; C6 reproducibility | Sec 9 config-key validator; 7.2 exact-compare tolerance columns; 9 determinism substrate |
| LLM-rel | H1-H6, M2 (jsonc), M3 enums | Sec 8 canonical guards; 9 context budget + mandatory low-conf gate; 5.3 strict exemplars; 5.1 enum normalize |
| Recon | oracle overfit; operator no-op; bidirectional; tMap-vs-tJoin | Sec 7.2 invariants/held-out; 10.2 kill operator + tMap-only; 10.1/10.3 two-pass pattern |
| Recon | rule model thin; matching_mode; reason text; routing | Sec 5.2 expanded rule model; 10.2 force ALL_MATCHES; 7.2 reason enum; 8 invariant routing |
| Platform | control-loop feasible (confirmed); hang; model-dep; A2 gate; terminal | Sec 4.1 confirmed; 4.2 resumable state machine + timeouts; 4.5 preflight + pinned model; 1.5 hard gates; 4.3 subprocess |
```
