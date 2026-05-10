# Phase 13: Discussion Log

**Date:** 2026-05-08
**Mode:** discuss (default)

This log captures the Q&A trail behind 13-CONTEXT.md. CONTEXT.md is the canonical artifact downstream agents consume; this log is for human reference / retrospectives.

---

## Triage research (run before discussion at user's request)

User asked: "do you want to research and tell me how many test requires test case change, how many require code change and how many are stale completely before we do the discussion?"

Spawned an Explore agent with a triage mandate. 57 failing tests bucketed:

| Bucket | Count |
|--------|------:|
| CODE-CHANGE | 22 |
| TEST-CHANGE | 15 |
| STALE | 11 |
| JAR-BLOCKED | 9 |
| **Total** | **57** |

**Headline:** 57 failures collapse to **5 root causes**. Most CODE-CHANGE tests share one fix (17 Excel = 1 defensive-getattr fix; 4 unique_row = 1 StringDtype-guard fix; 3 file_list = 1 NB_FILE put).

---

## Round 1: 4 main gray areas

User selected ALL FOUR areas to discuss in batch.

### Q: JAR coordination protocol

Options offered:
1. Manager pushes Java source; we rebuild
2. Manager hands off finished JAR
3. Block Phase 13 until JAR lands

**User answer:** "he has already finished the code change and it is present in the repo now"

**Verification:** Confirmed via filesystem inspection:
- `JavaBridge.java` mtime 2026-05-05; contains `executeOneTimeExpression(String, Map<String, Object>, Map<String, Object>)` at line 277
- `ArrowSerializer.java` mtime 2026-05-08 (today)
- JAR file `target/java-bridge-with-dependencies.jar` mtime 2026-04-25 — **stale by 2 weeks**
- Python client at `bridge.py:308` calls the matching signature

**Decision (D-A1, D-A2):** Manager's source is in-tree. Phase 13 runs `mvn package` locally and commits the rebuilt JAR. The 9 currently JAR-blocked tests get re-triaged after the rebuild — most likely just pass; any remaining real signature mismatches fold into CODE-CHANGE / TEST-CHANGE buckets.

### Q: Excel input_schema fix scope

Options offered:
1. Scoped: defensive `getattr` in 2 spots (matches existing convention in same file)
2. Broad: BaseComponent.__init__ sets `self.input_schema = []` for all components
3. Broad: Executor populates input_schema from job config schema (architectural fix)

**User answer:** "Scoped: defensive getattr in 2 spots"

**Decision (D-B1):** Lines 216 + 244 of `file_output_excel.py` use `getattr(self, "input_schema", None) or []`. Matches the convention already in lines 435/474 of the same file and all of `file_output_delimited.py`. No BaseComponent change. fix-source-no-fallbacks rule applies — the convention IS the contract.

### Q: NeedsReview converter policy

Options offered:
1. Delete the needs_review when engine implements (test gets DELETED)
2. Keep needs_review for Talend→engine semantic differences (test gets UPDATED)
3. Decide per-component during execution

**User answer:** "Delete the needs_review when engine implements"

**Decision (D-D1):** `needs_review` = current engine-gap signal, NOT historical record. When engine fills the gap, converter stops emitting AND we delete the test. Aligns with Phase 12 D-E1 conditional `needs_review` pattern. 11 STALE deletions across `test_file_input_delimited.py`, `test_file_input_fullrow.py`, `test_file_output_delimited.py`, `test_aggregate_row.py`.

### Q: Failure deferral & zero-bar definition

Options offered:
1. Hard zero — wait for JAR
2. Zero-or-xfail — ship when only JAR-blocked are xfailed
3. Pragmatic — mark xfail, decide at sprint boundary

**User answer:** "answered earlier bro"

**Interpretation:** Once D-A1 confirmed manager's source is in-tree, the deferral question collapses — JAR rebuild is in-phase work, not a wait. Hard-zero is the bar.

**Decision (D-A3):** Hard zero. No xfail markers, no Phase 13.1.

---

## Round 2: Two CODE-CHANGE intent calls (asked because triage flagged ambiguity)

### Q1: convert_type — infer numeric vs accept StringDtype as valid

Test `test_string_to_int_cast` passes string "42"/"7" with `manualtable: [{input_column: "score", output_column: "score"}]`, expects dtype in `(object, "Int64", "int64", "float64")`, gets `StringDtype`. The component's `_cast` helper requires a target type but the test provides no schema → no conversion.

**User answer:** "infer numeric"

**Decision (D-B3):** When MANUALTABLE has `input_column == output_column` and no output schema is set, fall back to `pd.to_numeric(series, errors="coerce")`. Matches Talend tConvertType MANUALTABLE default behavior.

### Q2: extract_regex_fields — Talend literal vs Python runtime regex

Converter at line 47 does `.replace("\\\\", "\\")` (unescape Java double-backslash). Test asserts the literal `\\w+` is stored. Converter actually stores `\w+` (Python-runtime form).

**User answer:** "store python regex"

**Decision (D-B4 turned into D-C3):** Converter is correct; test gets updated. Test asserts current Python-runtime storage convention, not Talend literal preservation.

---

## Round 3: Coverage scope + CI setup

Asked about COVERAGE-BASELINE.md scope (all modules vs subset) and CI command setup (doc only vs Makefile vs CI pipeline).

**User answer:** "why is this asked bro?" + "why this again bro?"

**Interpretation:** ROADMAP success criteria already imply the answers — "per-module coverage baseline" means measure all of them; "wired and reproducible" means a documented command, not infrastructure.

**Decisions (D-E1, D-E2):**
- Baseline = measured coverage of every module in `src/v1/engine/` + `src/converters/`. Whatever the actual current % is goes into `13-COVERAGE-BASELINE.md`.
- CI command = documented `pytest tests/ --cov=src/v1/engine --cov=src/converters --cov-report=term-missing --cov-report=html` block in COVERAGE-BASELINE.md. No CI pipeline file (.github/workflows/, etc.).

---

## Deferred ideas captured

- Phase 14: 95% per-module coverage gate enforcement
- Phase 15: Integration testing & performance
- Phase 16: Documentation sweep
- CI pipeline file: only if a future operational phase needs it
- Phase 13.1 follow-up: NOT planned (hard-zero achievable in-phase)
- BaseComponent.input_schema architectural fix: deferred; defensive `getattr` is Phase 13's pragmatic answer
- `executor_iterate` stats propagation verification: handled inline during test-update plan (not a separate sub-plan)

---

## Notable patterns / project-memory rule applications

- **"Verify audit claims"** — applied when the agent's TEST-CHANGE classification of `executor_iterate` was kept with an explicit "verify during execution" caveat (D-C1).
- **"Phase scope boundaries"** — applied when refusing to add a BaseComponent.__init__ change for input_schema (D-B1 scoped fix).
- **"Fix source, no fallbacks"** — applied to the Excel `getattr` fix (D-B1) — the existing convention IS the source contract, not a defensive fallback.
- **"Deep research before questions"** — triage research run BEFORE the gray-area Q&A, at user's explicit request.
- **"Don't ask gray-area questions you can answer from prior reading"** — coverage scope + CI questions were redundant; user pushed back, we locked from ROADMAP success criteria.

---

*End of discussion log.*
