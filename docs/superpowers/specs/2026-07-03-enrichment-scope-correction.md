# Scope Correction: Enrichment (not Reconciliation) + Full Component Set (decision record)

*Date: 2026-07-03. User-clarified. Supersedes the reconciliation domain model in the v3 design spec (`2026-07-03-copilot-etl-agents-design.md`) sections 5.2 (rule model), 8 (oracle framing), 11 (recon slice + Phases A-D), and control 1 of section 2 (code-injection block). The platform, knowledge, harness core, and extract layers are unaffected.*

## The correction
The ETL tool is for the recon team to do **DATA ENRICHMENT / PREPARATION** of source data, which then feeds **SmartStream TLM** where the **actual reconciliation** (matching/breaking/tolerance/netting) happens. TLM does the recon; this tool prepares the data for it.

The v3 spec assumed the ETL tool *performed* the reconciliation, so it built a full reconciliation domain model — rule kinds `match|tolerance`, `on_tolerance_fail`/`duplicate_disposition`/`direction`, a multi-signal oracle with a matched-vs-break tolerance partition, and a Phase A-D (match -> tolerance -> bidirectional -> netting/waterfall) roadmap. **That reconciliation layer is over-built and is dropped.** (Root cause: "recon" read as "reconciliation-in-the-tool"; the brainstorming should have asked "does this ETL do the recon or prepare data for the thing that does" — it didn't.)

## Enrichment model (the real one)
A job reads **source file(s) + lookup file(s)** -> **joins the lookups in to enrich/add columns** (tMap as a LEFT/lookup join, or another join path) -> **schema-validates** (type/format conformance; reject/route non-conforming rows if a job calls for it) -> **aggregates** -> **sorts** -> writes the **output that TLM ingests**. Pipelines vary job to job (no single fixed shape). The oracle just **diffs the produced output against the expected output** in the requirements doc; no match/break/tolerance logic in our tool.

## Direction (user)
- Agents **optimize for performance and resource**, and may use **ANY available engine component** to get the work done (the engine is a near-complete Talend replacement, not a recon-only tool). The pre-execution gate stays fail-closed only against *unregistered/unknown* types.
- **`python_dataframe` is UNBLOCKED** (it was in the v3 code-injection block). It runs LLM-authored pandas over the input DataFrame(s) — powerful for collapsing a multi-step transform into one vectorized node. Safe under the standing posture: trusted internal enclave + the **human gate reviews code-bearing cells** + the **oracle validates the actual output** (bad code -> wrong output -> fails the harness). Reversible if a stricter posture is ever needed. The human gate must explicitly surface any code cell.

## Bounded revision (concentrated in the domain layer; platform/tooling stand)
1. **doc-interpreter** rule model -> enrichment operations (join/lookup, schema-validate, filter, aggregate, sort, derive); drop match/tolerance/break/duplicate_disposition/direction.
2. **flow-designer** patterns -> flexible, perf-optimized enrichment pipelines over the FULL component set; tMap = the join primitive; reach for `python_dataframe` when it is the efficient move.
3. **configurator** -> validate curated components strictly; lean on the engine's own `_validate_config` + the oracle for uncurated ones.
4. **config-validator (`validate_config`)** -> **graceful degradation**: strict for a curated type; a soft advisory (NOT a hard fail) for a type with no curated schema, so any component works and correctness still falls to the engine + oracle.
5. **Golden job** -> recast from "match+reject" to a real enrichment shape (source+lookup -> join -> validate/convert -> aggregate -> sort -> output); more representative.
6. **Trim recon-only bits** -> `reference_matcher` (match/break oracle-of-oracle) and the "one-sided break / inner_join_reject" framing in the `dataprep-recon` skill; a LEFT-join enrichment keeps all source rows, no "breaks."
7. **Spec** sections 5.2/8/11 reframed reconciliation -> enrichment; the deferred **plan-3b** (tolerance/bidirectional/netting) is **dropped** (TLM's job).

## Unaffected (stands as built + review-clean)
Plan 4 platform (orchestrator + 6 specialists + audit + human gate + validate_agents); plan 2 knowledge layer (config schemas + `validate_config` core + landmines — engine-component facts, identical for enrichment; even tMap knowledge carries over since a lookup-enrichment is a join); plan 1 `extract_doc`; plan 3 harness core (`run_job_capture`/`diff_frames`/`check` — diff-output-vs-expected is exactly enrichment validation, component-agnostic).

## Status
Grounding the real `python_dataframe` config + the full component registry (which are curated vs not, perf characteristics) before writing agent instructions -- do NOT re-guess the way "recon" was guessed. Then execute the revision via opus SDD + end-of-plan adversarial review. Branch feature/copilot-etl-agents.
