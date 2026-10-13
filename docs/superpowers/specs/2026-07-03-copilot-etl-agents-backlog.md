# Backlog: Copilot ETL Agents — deferred items

- **Date:** 2026-07-03
- **Branch:** `feature/copilot-etl-agents`
- **Companion to:** `2026-07-03-copilot-etl-agents-design.md`

Deferred per owner decision. **Section A** (engine changes) is delegated to the DataPrep engine team and is NOT on the agent-system critical path. **Section B** (agent-system follow-ups) folds into the implementation plan for this project. All items were surfaced by the adversarial review and verified against engine source; the specs below are the *corrected* versions.

---

## A. Engine changes (owner: engine team; deferred)

Each is additive, must clear the 95% per-module coverage gate, and must preserve Talend parity + the no-re-conversion constraint. Anchors verified against current source.

| # | Change | Corrected spec (do NOT implement the naive version) | Anchors |
|---|---|---|---|
| A1 | Raise on non-equality tMap join `operator` | Predicate is `raise if operator not in {"", "=", "=="}`. The converter emits `operator:""` by default, so `!= "="` would raise on **every existing converted job**. Only real inequality ops (`<,<=,>,>=,!=,STARTS_WITH,...`) raise. | `map_config.py:38,115`; `validate_config`; `map.py:106,113` (converter default) |
| A2 | Cartesian-size guard on equality joins | Guard **only the `ALL_MATCHES` branch**, estimating real per-key fan-out (groupby-count product), NOT `main_n*lookup_n`. UNIQUE/FIRST/LAST already dedup the lookup, so no explosion is possible there; the naive product-guard false-fails ordinary large recon joins incl. Phase A. | `map_joins.py:150-231,240-333` (equality paths, no guard); `:446-463` (dedup); `:546-559` (existing product guard — do not reuse as-is) |
| A3 | Injectable frozen clock + seed (test mode) | Hook `TalendDate.getCurrentDate` + `RandomUtils`; **also pin the subprocess JVM `-Duser.timezone`/`-Duser.language` to the Talend PROD values** (date *formatting* uses `TimeZone.getDefault()`/`Locale.getDefault()`), and enumerate ALL time/random routines (`getDate`, `getRandomDate`, `TalendString.getAsciiRandomString`'s `SecureRandom`), not just three. | `TalendDate.java:1149,125,1134`; `RandomUtils.java:49`; `TalendString.java:80` |
| A4 | Persist structured error records | Additively record `component_id + exception class + cause` into `execution_stats` (today only `str(e)`; the cause class is dropped). The cause chain is already walked two lines away for the tDie/exit_code path. | `executor.py:746-780` |
| A5 | Force `die_on_error=True` on allowlisted recon tMaps, + two coupled holes | (a) Re-raise the **RELOAD per-row** expression swallow so a bad row does not become a silent break; (b) the recon slice must **ban `catch_output_reject`** outputs on tMaps (it cancels the `die_on_error` raise and captures errors), and the oracle must treat that flow as errors-only, never breaks. | `map_joins.py:722-727` (RELOAD swallow); `map_compiled_script.py:405,511-514` (`has_error_tracking`); `map_config.py:69-78` (reject flavors) |
| A6 | Harden `python_dataframe` exec namespace (one of TWO unsandboxed exec paths) | `python_dataframe_component.py` runs a bare `exec(code, namespace)` where `namespace` never sets `__builtins__`, so Python auto-injects the FULL builtins = **UNSANDBOXED** -- unlike the whitelist-hardened `tPython`/`tPythonRow`/`PyMap`/`tJava*`, which install a tight `__builtins__` via `_code_component_mixin._build_safe_builtins`. Align `python_dataframe` with that mixin so LLM-authored `python_dataframe` code is hygienic. **`python_dataframe` is NOT the sole unsandboxed vector** -- `SwiftTransformer` is a second one (see A8); this item hardens `python_dataframe`, A8 hardens `SwiftTransformer`. (Relevant now that `python_dataframe` is UNBLOCKED for enrichment -- see `2026-07-03-enrichment-scope-correction.md`.) | `python_dataframe_component.py:98-119` (namespace dict + bare `exec`, no `__builtins__`); `_code_component_mixin.py:66` (`_build_safe_builtins`) |
| A7 | tConvertType per-row MANUALTABLE cast vs whole-column path (minor) | A per-row MANUALTABLE cast fails on a `StringDtype` column -- per-row assignment into a StringDtype cell rejects every row -- while the whole-column `pd.to_numeric` default path works. Reconcile the two paths so a MANUALTABLE cast behaves identically regardless of the column's incoming dtype. | `convert_type.py:167-192` (whole-column `to_numeric` default vs per-row loop) |
| A8 | Harden `SwiftTransformer` eval namespace (SECOND unsandboxed exec path) | `SwiftTransformer` eval()s each `python_expression` config field with an `eval_context` whose `__builtins__` explicitly includes `__import__` -> **arbitrary-import RCE** (`__import__('os').system(...)`). Remove `__import__` from that namespace / align it with `_code_component_mixin._build_safe_builtins()` (which deliberately OMITS `__import__`, `open`, `exec`). This is a SECOND unsandboxed vector alongside `python_dataframe` (A6), not a duplicate of it. Interim agent-side control: `surface_code_cells` already flags every `python_expression` cell as unsandboxed at the human gate. | `swift_transformer.py:722` (`__import__` inside the eval `__builtins__`), `:741` (`eval(expression, eval_context)`); `_code_component_mixin.py:66` (`_build_safe_builtins`, omits `__import__`) |
| A9 | Extend the harness output-path-jail to `SwiftTransformer.output_file` (minor) | The `run_and_validate` output-path jail covers `FileOutput*` sinks only; `SwiftTransformer.output_file` is a separate raw-path write (the component writes its transformed frame straight to that path) that escapes the jail. Extend the jail so this path is validated too. | `swift_transformer.py:440` (`output_file = self.config.get('output_file')`), `:442`/`:910` (`_write_output_file`) |
| A10 | OS-sandbox the RowGenerator/RunIf eval sinks (surfaced, not sandboxed) | RowGenerator `values[].array` and RunIf `condition` are eval'd in `{'__builtins__':{}}`-style namespaces that are object-graph-escapable (not real sandboxes); now SURFACED by surface_code_cells for human review; a true fix needs an OS sandbox (see A6/A8). Engine/infra. | `row_generator.py:33` (`_EVAL_GLOBALS`), `:145` (`eval`); `trigger_manager.py:40` (`_SAFE_GLOBALS`), `:360` (`eval`) |

Note: "duplicate-key break" is NOT an engine change — it is a pattern (`UniqueRow`/`AggregateRow` count -> route-to-break) built from existing components. It lives in the pattern library (design Section 11.3), not here.

Until A1-A5 land, the agent system gates the phases that depend on them (esp. Phase B tolerance and deterministic-run tests); Phases 0-2 scaffolding (roles, knowledge, harness on 1:1 data with a fixed clock supplied at the config level) do not block on them. A6-A9 are independent hygiene/parity fixes, not phase-gates: A6 (`python_dataframe`) and A8 (`SwiftTransformer`) are the TWO unsandboxed-exec-namespace hardens -- both matter now that code-bearing components are in play for enrichment, with `surface_code_cells` as the interim agent-side control that flags both at the human gate; A9 extends the harness output-path jail to `SwiftTransformer.output_file`; A7 is a minor `tConvertType` dtype-path reconcile.

---

## B. Agent-system design follow-ups (owner: this project; fold into the implementation plan)

- **Knowledge extractor:** only tMap has typed dataclasses (`map_config.py`); the other 10 allowlisted recon transforms read `self.config.get(...)` with partial docstrings and no key manifest. Build a **reflect/probe extractor** (import the module, reflect enum dicts like `filter_rows.py:32-48` `_OPERATOR_MAP`, probe `_validate_config` with candidate configs) OR ship a **hand-curated key manifest per recon component**, drift-checked against `_validate_config`. Even for tMap, **union the dataclass fields with the component's direct `self.config.get` reads** (`rows_buffer_size`/`output_chunk_size` are read but not dataclass fields — `map_component.py:45`).
- **Behavioral round-trip = regression tripwire only.** `BaseComponent` enforces no unknown/required-key contract (every read is `self.config.get(k, default)`), so the round-trip cannot observe accepted/ignored/required keys as a schema oracle. Use it as a coarse regression check on pinned golden configs; add `self.config.get` access tracing if real key-usage observation is needed.
- **Cache key must cover the intra-boundary repair loop.** Include prior-draft hash + the single targeted-error id + turn index (or bypass cache on repair turns, memoizing only accepted outputs). The 5-term outer key freezes the adaptive-repair loop on a cache hit. Show the **full validation-error set per repair turn** (or add a repair-regression guard) to avoid one-error-at-a-time oscillation.
- **Derived-facts residual:** the derived-facts approach assumes every value-literal the config needs (categorical domains, thresholds) is present in the **doc rule text**. If a rule needs a data-derived domain not in the doc, detect it up front and **route to human** rather than looping blind. Treat sample-derived uniqueness as **provisional** — only a **doc-declared** key constraint may suppress the duplicate-break flag.
- **Reference matcher grounding:** the mutation-row oracle-of-oracle is a second re-implementation; ground the boundary/tie-break/null expectations against **one real Talend run** (ties to the "obtain a real recon job" open item). Downgrade design Sec 8.2 "validate correctness" wording to match the Sec 15 honest ceiling.
- **`skipped` by set-difference** must subtract subjob-unreachable + `job_aborted` cascades, else any RunIf/OnComponentOk branch false-alarms as a "silently dropped component."
- **Keyless tolerance** (match on amount/date within tolerance, no shared ID) is real recon, not expressible as exact-join-plus-split, and not auto-flagged: add an ambiguity flag "tolerance rule with no exact key -> human," and/or admit guarded `FILTER_AS_MATCH` (`map_joins.py:571`) as a Phase-D pattern.
- **Tolerance pattern must pin `LEFT_OUTER_JOIN`** — under `INNER_JOIN`, join-misses divert to the separate `inner_join_reject` channel that bypasses the active script, so `is_reject` would miss them (`map_component.py:146-157,237-238`).
- **Golden coverage:** grow to one golden job **per shipped pattern** (Sec 11.3) as the library grows; run the model-capability preflight **N>=2**.
- **Opaque model id:** if the Copilot boundary exposes only a coarse model id, fold the preflight probe's **output hash** into `model_id` so a silent model swap invalidates cache + triggers freshness.

### B.1 General-ETL builder follow-ups (2026-07-07)

- **LLM doc-normalizer for arbitrary (non-template) requirement docs.** `extract_doc` today is a
  deterministic TEMPLATE parser: it fails **closed** (conformance gate rejects, exit 2) on any doc not
  authored to the exact template -- real STTM spreadsheets, prose BRDs, screenshots of sample data, etc.
  To ingest arbitrary existing docs, make the **schema + rules + notes** extraction LLM-driven, emitting
  a **shape-conforming `extract_doc.json`** -- so EVERY downstream stage AND `materialize_golden` stay
  unchanged (the contract is `extract_doc.json`; nothing cares how it was produced). **Hard constraint:**
  the LLM must NOT author `sample_input` / `expected_output` -- those become the input CSVs and the test
  oracle, and a paraphrased value (e.g. `"1,000.50"` -> `1000.5`) silently corrupts the grade with nothing
  downstream to catch it. Keep the sample/expected DATA **exact** (verbatim copy from an attached CSV/real
  table) **or human-verified**; the model may only *locate* it. Wrap the LLM in a thin **deterministic
  validator** (well-formedness + `tier` + `conformance`), and recompute `derived_facts` deterministically
  from the extracted rows (never LLM-invented uniqueness/null-rate). Accept the loss of run-to-run
  reproducibility. NOT needed for the author-to-template workflow; only for "ingest existing docs".
- **Harden `extract_doc.py`/other tool CLIs for missing parent dirs** -- DONE for `extract_doc --out`
  (creates its parent); audit the other `--out`/write CLIs for the same first-write-into-fresh-dir failure.
