# Handoff: Real-BRD Ingestion (LLM Doc-Normalizer)

- **Date:** 2026-07-07
- **Branch:** `feature/real-brd-ingestion` (cut from `feature/copilot-etl-agents`, which holds the
  completed + demoed general-ETL builder, fully pushed).
- **Purpose:** start the "ingest a REAL BRD, not just a template doc" work fresh, with full context.
- **First action for the new session:** invoke `superpowers:brainstorming` to design the doc-normalizer
  (work the OPEN QUESTIONS below with the user), then `writing-plans`, then the subagent build with the
  adversarial-review loop. Do NOT write code before the design is brainstormed + user-approved.

---

## 1. TL;DR

The general-ETL pipeline builder is **DONE, pushed, and demoed** (manager was "super impressed"). It
ran **end-to-end in the real Citi VS Code Copilot, one-shot, on both a simple and a complex doc** — both
passed the harness first try, and the agent reported honestly. The manager's ONE ask: make it accept a
**real BRD** (arbitrary format), not just a doc authored to our exact template. That is this branch's
work, and it is already scoped as **backlog §B.1** (see `docs/superpowers/specs/2026-07-03-copilot-etl-agents-backlog.md`).

## 2. What the completed system does (context)

Pipeline (all on `feature/copilot-etl-agents`, pushed):

```
docx --> extract_doc (DETERMINISTIC template parser) --> extract_doc.json
     --> materialize_golden (deterministic: input CSVs + golden/ oracle)
     --> 6 LLM specialists via etl-orchestrator (#runSubagent):
         doc-interpreter -> flow-designer -> configurator -> assembler -> test-runner -> diagnostician
     --> 3-tier verification (verified|smoke|build) --> human gate (no auto-approve)
```

- **Proven live:** simple doc (2 sources, 1 join, 1 sort) AND complex doc (3 sources, 2 joins, filter,
  sort, 2 no-matches + 1 filtered row) both ran one-shot -> `passed: true`, correct output, agent's
  human-gate summary was accurate (every number traced to the files).
- **Design spec (completed):** `docs/superpowers/specs/2026-07-07-general-etl-pipeline-builder-design.md` (v3).
- **Testing guide:** `docs/AGENT_STEPWISE_TESTING_GUIDE.md` (single-step protocol; the orchestrator has a
  native testing mode).

## 3. The new requirement + THE load-bearing constraint

`extract_doc` today is a **deterministic TEMPLATE parser**: it fails **closed** (conformance gate, exit 2)
on any doc not authored to the exact template — real STTM spreadsheets, prose BRDs, screenshots of sample
data, Confluence, emails. To ingest arbitrary BRDs:

**Approach (agreed with the user):** an **LLM doc-normalizer** that extracts **schema + rules + notes**
(the *intent*) from a messy doc and emits a **shape-conforming `extract_doc.json`**. Because EVERY
downstream stage AND `materialize_golden` consume only `extract_doc.json` (the artifact-bus contract),
**nothing downstream changes** — the work is localized to the front door.

**HARD CONSTRAINT (do not violate):** `sample_input` / `expected_output` in `extract_doc.json` become the
**input CSVs and the test oracle**. If the LLM *paraphrases* a value (e.g. `"1,000.50"` -> `1000.5`, a
dropped trailing zero, a "fixed" typo), it **silently corrupts the grade** with nothing downstream to
catch it. So:
- The LLM extracts **intent** (schema, rules, notes) — fuzzy, safe-with-review.
- The **data** (sample/expected) stays **exact** — verbatim copy from an attached CSV/real table, **or
  human-verified**. The model may only *locate* it, never author it.
- Wrap the LLM in a **thin deterministic validator** (well-formedness + `tier` + `conformance`), and
  **recompute `derived_facts` deterministically** from the extracted rows (never LLM-invented).
- Accept the **loss of run-to-run reproducibility** (LLM varies; today's parser is deterministic).

This is the same "deterministic DATA / LLM INTENT" principle the whole system already rests on — the
LLM never touches the oracle.

## 4. `extract_doc.json` shape (the contract to conform to)

Two buckets:
- **Bucket 1 -> LLM-safe (intent + structure):** `sources_schema` (per source: `{name,type,nullable,key}`),
  `rules` (`{id,kind,description,...}`, kind in join/schema_validate/filter/aggregate/sort/derive),
  `notes` (verbatim prose), `extra_sections` (unrecognized sections; prose verbatim + tables as
  structural-facts-only), `derived_facts` (per-column `{n_distinct,null_rate,unique,max_group_size}` —
  the only load-bearing use is the non-unique-lookup-key ambiguity flag), `tier`, `conformance`.
- **Bucket 2 -> LOCAL oracle (never to the LLM as authorable):** `sample_input` (real rows -> input CSVs),
  `expected_output` (answer-key rows -> `<name>_expected.csv`), `output_keys` (composite key columns).

The normalizer must emit Bucket 1 from the LLM; Bucket 2 must be exact/verified.

## 5. What real BRDs actually look like (the challenge to brainstorm)

STTM (source-to-target mapping) spreadsheets in Excel; BRDs that are ~80% prose with a few embedded
tables + **screenshots** of sample data; Confluence pages; mapping columns with varying headers
("Source Field / Target Field / Transformation Logic"); sample data pasted as images or attached as
separate CSV/Excel. `extract_doc` handles NONE of these today.

## 6. OPEN DESIGN QUESTIONS (brainstorm these with the user)

1. **Convert-to-template vs extract-JSON-directly:** LLM produces a template-conforming `.docx` (then the
   existing deterministic `extract_doc` runs), OR the LLM emits `extract_doc.json` directly? (The latter
   skips a step but loses the deterministic table-copy for schema/sample.)
2. **How does the exact oracle DATA get in?** Real BRDs rarely have a clean Expected-Output table. Options:
   attached CSV the user points at; a human paste/verify step; or "no oracle -> smoke/build tier".
3. **No sample/expected in the BRD (common):** fall to `smoke`/`build` tier? Or prompt the human to supply
   sample data separately? (The 3-tier model already supports build-only.)
4. **Sample data as screenshots/images:** OCR? require it as an attachment? refuse + ask?
5. **The human-verify-the-oracle UX** — when/how does the human confirm the extracted answer key?
6. **STTM extraction:** multi-source mapping tables with arbitrary headers -> `sources_schema` + `rules`.
7. **Data exposure:** the extraction LLM now SEES all raw data (to extract it). Acceptable under
   *don't-minimize-egress* (trusted Citi enclave), but note the posture change vs today's data-blind flow.
8. **Where does it live?** a new `doc-normalizer` subagent (before/replacing `extract_doc`), a tool, or a
   hybrid (LLM + deterministic validator wrapper)?
9. **Fail-closed on low confidence:** if the LLM can't confidently extract, refuse / route to human —
   never fabricate (same discipline as the rest of the system).
10. **Reproducibility/caching** given LLM non-determinism.

## 7. Constraints + working style (carry forward — these are locked)

- **Model-agnostic:** NO `model:` key in any `.agent.md` (`validate_agents` enforces).
- **ASCII-only** in code/logs/authored markdown (RHEL-clean).
- **don't-minimize-egress:** trusted Citi enclave; real data may reach the Copilot. The oracle-exactness
  rule (Section 3) still stands regardless.
- **Engine changes = engine team** (`src/` is out of scope; backlog A6/A8/A10 are theirs).
- **Adversarial-review loops:** spec review -> plan review -> final whole-branch review, each **looped
  till clean** (0 Critical, no blocking Important). **Opus everywhere** (implementers AND reviewers). Use
  the multi-lens fan-out Workflow pattern used on the general-ETL build.
- **superpowers workflow:** `brainstorming` -> `writing-plans` -> `subagent-driven-development` ->
  `requesting-code-review`.
- **VS Code 1.122 tool IDs (learned the hard way in live testing):** valid = `read`, `edit`,
  `search/codebase`, `agent/runSubagent`, `execute/runInTerminal`, `execute/getTerminalOutput`. INVALID
  (do NOT use) = `read/files`, `edit/files`, `run/terminal`, `runCommands` (renamed). `validate_agents`
  checks tools-list STRUCTURE only, NOT live resolution -> always verify tool IDs in the live Copilot.
- **CLIs create their parent dirs** (`extract_doc --out` does; the orchestrator step-0 also `mkdir -p`s).
- **Git:** never commit to `main`; branch is `feature/real-brd-ingestion`; stage files by name; confirm
  before push/PR.

## 8. Key file pointers

- Backlog item: `docs/superpowers/specs/2026-07-03-copilot-etl-agents-backlog.md` (§B.1).
- Completed design: `docs/superpowers/specs/2026-07-07-general-etl-pipeline-builder-design.md`.
- The parser to augment/replace: `agents/tools/extract_doc.py` (+ `compute_derived_facts`, conformance).
- Deterministic materializer (downstream, unchanged): `agents/tools/materialize_golden.py`.
- Agents: `.github/agents/*.agent.md` (esp. `etl-orchestrator`, `doc-interpreter`).
- Skill: `.github/skills/dataprep-etl/`. Template: `agents/templates/etl_requirements_template.md`.
- Examples: `agents/examples/sample_etl_requirements*.docx` (+ generators).
- Tests: `tests/agents/` (215 passing on the base branch).

## 9. Recommended first moves for the fresh session

1. Confirm on branch `feature/real-brd-ingestion`; read this handoff + backlog §B.1.
2. `superpowers:brainstorming` — drive Section 6's open questions with the user; the biggest forks are
   (a) convert-to-template vs direct-JSON, and (b) how the exact oracle DATA is supplied/verified.
3. Write the spec, adversarial-review it (loop till clean), then plan + build + review — same loop that
   produced the general-ETL builder.
