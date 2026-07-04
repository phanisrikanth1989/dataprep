# 08 - Coverage & Tests (Phase 2 deliverable, Phase 3 work-list)

Audience: engineers about to do Phase 3 - stabilize the suite and raise per-module
coverage to the 95% floor, then add 2 new components.

This document synthesizes the Phase 2 diagnoses (a fleet of agents triaged the 159
failing tests and the 9 below-floor modules) into an actionable plan. It is paired
with `docs/understanding/07-findings-and-risks.md` (the risk register); cross-refs
to that doc use its IDs (e.g. H-B3, M-B10).

Branch this was measured on: `claude/peaceful-gates-f1e530`, with the Java bridge
jar built. All paths are repo-relative posix unless stated otherwise.

> Context that frames everything below: the engine package only just started
> importing again. Two import-blockers were fixed (see 07: H-B1 `engine.py`
> SyntaxError, H-B2 `trigger_manager.py` class-scoping). The 159 failures were
> previously MASKED by that import error, so they reflect the true state of the
> 28 recent WIP commits (pagination, Oracle/MSSQL, syncs). Some are real code
> bugs from those commits, some are tests never updated after an intentional
> behavior change, and a few are genuinely ambiguous and need a product decision.

---

## 1. Current state summary

> VERIFICATION CORRECTION (added after the synthesis pass): a few claims below
> were written by diagnosing agents that accidentally measured the MAIN checkout
> (`/Users/aarun/Workspace/Projects/citi/dataprep`) instead of this worktree -- the
> same path-confusion that twice misfiled docs into the main checkout. The
> authoritative, re-verified state of THIS worktree (`claude/peaceful-gates-f1e530`),
> measured from a fully clean state (cleared `__pycache__`, `.coverage*`, pytest
> cache), is: **159 failed, 8262 passed, 4 skipped - deterministic across two runs.**
> Corrections inline are marked [CORRECTED]. Net effect: the "really 53 failures /
> expression_converter already green / engine-misc mostly flaky" notes are WRONG for
> this worktree; the real Phase 3 failure count is 159.

### 1.1 The gate FAILS

Measured just now on this branch with the bridge jar built:

| Metric | Value |
|---|---|
| pytest | 159 failed, 8262 passed, 4 skipped |
| oracle-marked tests | excluded by the gate; 0 exist anyway |
| Per-module 95% floor | **FAIL** - 9 modules below floor |

### 1.2 The 9 below-floor modules

| Coverage | Module | Missing lines | Root nature |
|---|---|---|---|
| 18.5% | `src/v1/engine/components/file/file_input_xml.py` | 119 | blocked-by-failures (stale tests) |
| 61.7% | `src/v1/engine/components/database/oracle_output.py` | 158 | blocked-by-failures (code bugs + 1 decision) |
| 73.6% | `src/v1/engine/components/transform/xml_map.py` | 155 | blocked-by-failures (upstream) + net-new |
| 74.8% | `src/converters/talend_to_v1/components/transform/xml_map.py` | 82 | net-new tests |
| 82.8% | `src/v1/engine/components/transform/py_map.py` | 94 | net-new tests |
| 83.7% | `src/v1/engine/components/file/file_output_delimited.py` | 49 | blocked-by-failures (code bug + stale tests) |
| 83.8% | `src/v1/engine/components/transform/java_row_component.py` | 12 | net-new tests |
| 92.2% | `src/v1/engine/trigger_manager.py` | 14 | net-new tests |
| 94.8% | `src/converters/talend_to_v1/expression_converter.py` | 6 | STALE snapshot (already passes) |

> [CORRECTED] `expression_converter.py`: NOT stale and NOT green. Commit `9a054ef`
> IS an ancestor of HEAD, yet the 4 `TestDetectOperatorCarveouts` URL tests still
> FAIL in this worktree (`detect_java_expression("http://...")` returns False where
> the tests assert True - the URL carve-out short-circuits before the `//` comment
> rule). This is a real 4-test cluster needing classification in Phase 3 (likely a
> code regression in the carve-out control flow, lines 95-96 vs 129), not a no-op.

### 1.3 The 159 failing tests, grouped by cluster

| Cluster | Count | Owning module |
|---|---:|---|
| oracle_output | 77 | `database/oracle_output.py` |
| file_input_xml cluster | 42 | `file/file_input_xml.py` (+ xml coverage/e2e tests) |
| file_output cluster | 21 | `file/file_output_delimited.py`, `file_output_positional.py`, `file_input_delimited.py` |
| engine-misc | 7 | base_component / filter_rows / executor_iterate / fixed_flow / excel |
| db-input | 5 | `database/oracle_input.py`, `database/mssql_input.py` |
| expression_converter | 4 | `converters/.../expression_converter.py` |
| xml_map | 3 | converter `xml_map.py` + converter `map.py` + engine e2e |
| **Total** | **159** | |

[CORRECTED] An earlier triage note here claimed several counts were "inflated by
the import-blocker transition" (only 2 of 7 engine-misc reproduce, 4
expression_converter don't reproduce, real count ~53). That was measured against
the MAIN checkout. Re-verified from a fully clean state in THIS worktree, all 159
reproduce deterministically: the engine-misc failures (float precision, reject
flow, reject accumulation) and the 4 expression_converter failures are all real.
Size Phase 3 against 159, not 53.

---

## 2. THE PHASE 3 WORK-LIST (the centerpiece)

Three buckets, derived from the diagnoses' `fixTarget` classification:

- (a) Real code bugs to FIX (`fixTarget=code`)
- (b) Stale / not-updated TESTS to fix (`fixTarget=test`)
- (c) DECISIONS NEEDED (`fixTarget=decision_needed` / `classification=ambiguous`)

Recommended sequencing: do bucket (a) first (mostly unconditional, unblocks the
bulk of the floor), then bucket (b) in parallel, then resolve bucket (c) decisions
which gate the remaining tests. Within oracle_output specifically, the 3 code bugs
MUST be fixed before the quoting-policy decision can even be evaluated, because the
NameError/AttributeError pre-empt every assertion.

### 2.1 (a) Real code bugs to FIX (`fixTarget=code`)

| # | File:line | What's broken | Proposed fix | Conf | Tests unblocked |
|---|---|---|---|---|---:|
| C1 | `oracle_output.py:132` | `_quote_ident` references bare `IDENTIFIER_RE` (never defined); the constant is `_IDENTIFIER_RE` at line 71. `or` short-circuits so it is hit on every identifier path -> `NameError`. Incomplete rename in commit `bafc8e7`. (07: H-B3) | Change `IDENTIFIER_RE` -> `_IDENTIFIER_RE` at line 132; also fix the stale docstring ref at line 117. No test change. | high | ~62 |
| C2 | `oracle_output.py:252` (def) + 12 call sites (321,358,367,384,388,396,476,506,525,556,569,1081) | Method `_qualified_table` was renamed to public `qualified_table`, but the 12 internal callers and the 4 `TestQualifiedTableName` tests still call `self._qualified_table()` -> `AttributeError`. Same commit `bafc8e7`. (07: H-B4) | Lowest-risk: rename the def back to `_qualified_table` (private; nothing outside the module uses the public name, and tests assert `_qualified_table`). Alternatively keep `qualified_table` + update 12 call sites + add `_qualified_table = qualified_table` alias. | high | ~34 |
| C3 | `oracle_output.py:278,283,285,286` (body of `qualified_table`, lines 277-291) | Three further defects, reachable only after C1/C2: (1) `self._quote_ident(...)` calls a MODULE-level fn as a method -> `AttributeError`; (2) local `schema` is read at 283/285/286 but never assigned (the `schema = ...` line was deleted in the diff) -> `NameError`; (3) table source changed to `config.get('table') or config.get('dbschema')` so schema/table slots are conflated - FQN is semantically wrong. (07: H-B5) | Rewrite the body: `schema = (self.config.get('schema_db') or self.config.get('dbschema') or '').strip()`, `table = self.config['table'].strip()`, call module fn `_quote_ident(...)` (not `self.`), compose `f'{_quote_ident(schema)}.{_quote_ident(table)}'` when schema else `_quote_ident(table)`. Reconcile the `use_existing_connection` schema-suppression contradiction (see D1). | high | ~34 (overlaps C2) |
| C4 | `oracle_input.py:176,184` and `mssql_input.py:159` | `_apply_trim` guards strip with `df[col].dtype == object`. Under pandas 3.0.1 (in-pin: `>=2.0,<4`), `future.infer_string` defaults True, so str columns are `StringDtype`, not object. Guard is False, strip is skipped, values come back un-stripped. The project already handles this correctly at `py_map.py:1266`. | Broaden the guard in BOTH files to `df[col].dtype == object or pd.api.types.is_string_dtype(df[col].dtype)`. No test change. Also fix consistently (latent, not gated): `oracle_input._apply_no_null_values:207` and `convert_type.py:73`. | high | 5 |
| C5 | `file_output_delimited.py:342` (call) vs def at 574-588 | `_process()` calls `self._handle_empty_input(..., append=append)`; the body uses `append` (line 619) and documents it (607-611), but the `append` param was never added to the signature -> `TypeError` on every empty/None-input path. Uncommitted WIP in the worktree. | Add `append: bool = False,` to the signature (after `escape_char`, before `input_data`). No test change. | high | 14 |
| C6 | `file_input_delimited.py:75` (regex), applied at 248-252 | `_NON_PRINTABLE_RE = re.compile(r'[^\x20-\x7E\t\n\r]')` (commit `11a62f2`) negates ALL of ASCII-printable, so valid ISO-8859-15 / Latin-1 chars (e, i, a, Euro) get scrubbed to space - contradicts the scrubber's own docstring (targets only control bytes 0x00-0x1F, 0x7F-0x9F, U+FFFD). | Narrow to the codepoints the docstring names, e.g. `re.compile(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F-\x9F\uFFFD]')` (the trailing `\uFFFD` is the U+FFFD replacement char). Preserves Latin-1 data while still stripping the bytes that crash the Py4J wrap. Test is correct. (related: 07 M-B4 region) | high | 1 |

Bucket (a) total: clears ~117 of the 159 failures (C1-C3 overlap inside the 77
oracle tests; net oracle from code-only is ~60, the rest gated by D1).

> Worktree gotcha for C5: the diagnosing agent found that the MAIN checkout
> (`/Users/aarun/Workspace/Projects/citi/dataprep`) already has `file_output_delimited.py`
> FIXED (no `append` kwarg) - there the empty-input tests pass. Phase 3 must apply
> C5 in THIS WORKTREE; the main checkout is a red herring.

### 2.2 (b) Stale / not-updated TESTS to fix (`fixTarget=test`)

For each, the **canonical** (correct) behavior is the SOURCE, and the test lags.
Do NOT change the source for any of these.

| # | Test(s) | Canonical behavior (and why) | Fix | Conf | Tests |
|---|---|---|---|---|---:|
| T1 | `tests/v1/engine/components/file/test_file_input_xml.py`, `test_xml_coverage_gaps.py`, `test_xml_e2e.py` (42 tests) | Config key was renamed `filename` -> `filepath` in merge `4e8c0a0`. The engine (`file_input_xml.py:77,114`) AND the production converter (`file_input_xml.py` converter:103,135) AND sibling `file_input_delimited` all use `filepath`. Source is mutually consistent; only the tests still pass `filename`. (canonical = `filepath`) | Replace every `'filename': <v>` with `'filepath': <v>` in the 3 test files; change `match="filename"` -> `match="filepath"` at test_file_input_xml.py:128; ensure `test_missing_loop_query_raises` and `test_bool_typed_config_not_bool_raises` supply `filepath` so validation reaches the assertion they target. Optional: update engine docstring 44-47. | high | 42 |
| T2 | `tests/v1/engine/components/file/test_file_output_delimited.py:1498,1506,1517,1526` (4 tests) | The schema-iterating decimal formatter the tests describe was split out into `FileOutputDelimited._format_decimal_columns` (delimited.py:452-524). `_apply_decimal_precision` is now a `@staticmethod(df, col_name, precision)` (base_component.py:1132-1177) that quantizes ONE column. (canonical = `_format_decimal_columns`) | Repoint the 4 tests from `comp._apply_decimal_precision(df)` to `comp._format_decimal_columns(df)`. Assertions already match. Update stale docstring line-refs. | high | 4 |
| T3 | `tests/v1/engine/test_base_component.py::TestValidateSchemaLengthZero::test_positive_length_still_truncates` (1) | String-length truncation was intentionally REMOVED in commit `d1a4209` to match Talend (length is informational metadata, never enforced at runtime; base_component.py:931-933). | Change the test to assert values are UNCHANGED for positive length; update the class docstring to stop referencing the removed `v[:col_length]` guard. Do NOT re-add truncation. | high | 1 |
| T4 | `tests/v1/engine/components/file/test_fixed_flow_input.py::TestIntableMode::test_nb_rows_limits_output` (1) | `nb_rows` is intentionally ignored in intable mode (commit `d1a4209`; `_build_intable_rows` docstring at fixed_flow_input.py:169 says so). With a 2-entry-pair intable, output is 2 rows regardless of `nb_rows=1`. | Update the test to assert 2 rows / that nb_rows has no effect in intable mode. Do NOT re-introduce an nb_rows cap. | high | 1 |
| T5 | `tests/converters/talend_to_v1/components/transform/test_map.py::test_schema_empty` (test_map.py:306) (1) | tMap schema shape changed `{}` -> `{'inputs': {<flow>: [...]}}` in commit `07cd83a` to wire `schema.inputs` to `schema_inputs_map` so the Java bridge boundary check passes. Default node -> `{'inputs': {'row1': []}}`. | Update assertion to the new shape (`== {'inputs': {'row1': []}}` or `'inputs' in schema`); update docstring. Optional: add a positive populated-schema test. | high | 1 |
| T6 | `tests/converters/talend_to_v1/test_expression_converter.py::TestDetectOperatorCarveouts` (4 URL tests) | [CORRECTED] These FAIL in this worktree (verified). `detect_java_expression("http://...")` returns False; tests assert True. Commit `9a054ef` is in-branch but did not make them pass. NEEDS classification in Phase 3: determine whether `http://`/`//`/`ftp://` strings SHOULD be detected as Java (the `//` comment rule, tests say True) or not (carve-out short-circuits, code says False). Likely a real code regression in the carve-out vs comment-rule ordering (lines 95-96 vs 129). | NOT a no-op. Read the carve-out flow; classify code-vs-test; fix accordingly. | medium | 4 |

Bucket (b) total: 53 failing-snapshot entries, of which 49 are genuine stale-test
edits (T1-T5) and 4 (T6) are already green.

### 2.3 (c) DECISIONS NEEDED (`fixTarget=decision_needed` / ambiguous)

These BLOCK Phase 3 work and require a human/product answer before the affected
tests can be made canonical.

| # | Decision | Affected tests | Options | Recommendation |
|---|---|---:|---|---|
| D1 | **Oracle identifier-quoting policy.** Commit `bafc8e7` intentionally changed `_quote_ident` to emit BARE (unquoted) identifiers to fix ORA-00942 (lowercase config table vs uppercase on-disk). But ~17 tests assert QUOTED output, and `TestReservedWordIdentifierQuoting` (lines 1605/1617) documents that GROUP/ORDER columns MUST be double-quoted to be valid Oracle DDL. The new unquoted behavior REGRESSES reserved-word support. (07: H-S1) | ~17 | A) Revert to always-quote `f'"{name}"'`, keep all tests, solve ORA-00942 by case-normalizing config table names (`.upper()`). B) Keep unquoted, rewrite all ~17 assertions - but knowingly break reserved words (re-spec `TestReservedWordIdentifierQuoting`, flag to product). C) Hybrid: quote only reserved words / mixed-case names, leave plain uppercase bare - satisfies both, needs new tests. | C (hybrid) is likely best. Whichever is chosen, C1/C2/C3 (the 3 unconditional code bugs) MUST be fixed first; they are independent of D1. |
| D1b | **`use_existing_connection` schema suppression.** The refactor's new comment says schema should be suppressed in the FQN when `use_existing_connection=True`, but `TestQualifiedTableName` (lines 228-243) builds components with `use_existing_connection=True` and STILL expects the schema (`"HR"."EMP"`). Direct contradiction. | (subset of ~17) | Decide whether schema is suppressed under use_existing or always present; reconcile as part of the C3 rewrite. | Resolve together with D1 / C3; the tests currently encode "always present". |
| D2 | **Positional KEEP=ALL truncation.** Commit `11a62f2` appended an UNCONDITIONAL `series = series.str[:size]` at `file_output_positional.py:538`, which truncates `ABCDEFGH`->`ABCDE` and defeats KEEP=ALL. Contradicts the module's own contract (DEFAULT_KEEP='ALL', docstring "ALL (no truncation)" lines 73-74, no-op branch line 525). Talend tFileOutputPositional with KEEP=ALL allows overflow. | 2 | A) Make the clamp conditional: `if keep != 'ALL': series = series.str[:size]` - both tests pass, docstring stays true, fixed-width preserved for LEFT/MIDDLE/RIGHT. B) Keep absolute fixed-width, update 2 tests + docstring + DEFAULT_KEEP - but this diverges from Talend. | A. Lean toward conditional clamp; do NOT blindly update tests because the new behavior is itself questionable. |
| D3 | **Engine `xml_map` coverage remediation route.** Engine `xml_map.py` (73.6%) is under-covered only because its e2e driver (`test_xml_e2e.py::test_xml_map_e2e_per_row`) fails UPSTREAM on the `file_input_xml` `filepath` KeyError - 0 rows reach XMLMap. The module itself is healthy (65/65 unit tests pass). | 0 (coverage only) | A) Fix T1 (file_input_xml) and let the e2e exercise the per-row machinery end-to-end. B) Add isolated unit tests for `_compute_filter_mask`, `_evaluate_xml_multiloop`, `_evaluate_xml_for_row` with crafted lxml. | A is canonical (fix upstream). This is a process choice, not code-vs-test. |
| D-snap | [CORRECTED - RESOLVED] **Failure count verified = 159, not 53.** The "53 failed / 0 expression_converter" reading was the diagnosing agent measuring the MAIN checkout. A clean-state re-run in THIS worktree (cleared `__pycache__`/`.coverage*`/pytest cache) yields 159 failed / 8262 passed / 4 skipped, twice, deterministically. No decision needed - this row is closed. | 0 | n/a (resolved) | Phase 3 is sized against 159. |

> Latent code bugs flagged by the agents but OUT OF SCOPE for the gate (track in
> 07, do not let them bloat Phase 3): expression_converter `convert()` corrupts
> bare `!=` via a blanket `'!'->' not '` replace (07 M-B1); `mssql_input.py:89`
> mutates a shared connection's `timeout` without restoring it (07 M-B10);
> `file_input_json.py:105` emits `filename` not `filepath` (file-input config-key
> contract inconsistency). None affect the failing-test count or the floor.

---

## 3. Coverage-gap plan (per below-floor module)

"Blocked-by-failures" means coverage will JUMP once the relevant tests pass - no
net-new tests needed. "Net-new" means the failing tests already pass and the floor
gap is a genuine test-authoring gap.

| Module | Now | Blocked? | Why short / what fixes it | Net-new tests needed | Effort |
|---|---:|---|---|---|---|
| `file/file_input_xml.py` | 18.5% | YES | All 42 tests die at line 114/78 before any logic runs. The 119 missing lines are the entire `_process` body + helpers + reject path. Apply T1 (filename->filepath). | None to clear floor; recheck residual (likely only `except: pass` at 254-255) after. | small |
| `database/oracle_output.py` | 61.7% | YES | The 77 tests abort at the NameError/AttributeError. Missing lines map 1:1 onto DDL/DML/upsert bodies the tests drive. Apply C1+C2+C3, resolve D1. | None to clear floor; maybe 1-2 tiny tests for line 852 (CLOB) / 963 (pre-commit) after. | medium |
| engine `transform/xml_map.py` | 73.6% | YES (upstream) | Helpers + flat path covered by 65 passing unit tests; the XML-parse / filter / multiloop / per-row machinery (458-534, 536-651, 875-992, 998-1166, 1242-1399) only runs via the e2e that fails on the upstream `filepath` KeyError. Apply T1 (per D3-A). | Optional direct unit tests for `_compute_filter_mask`, `_evaluate_xml_multiloop`, `_evaluate_xml_for_row` with crafted lxml + fake bridge if covering independently. | medium |
| converter `transform/xml_map.py` | 74.8% | NO | Real net-new gap: `_build_expression_contexts_multi` + multi-loop XPath rewrite (430-504) and `_detect_looping_element` ATTRIBUT/nested branches (242-266, plus 300-303, 384/393, 629/640) lack targeted tests. | Helper tests for `_build_expression_contexts_multi` (deepest-loop field, ../-traversal field, no-loop early return) and `_detect_looping_element` (ATTRIBUT leaves, nested children). | small |
| `transform/py_map.py` | 82.8% | NO | Happy paths covered by 169 tests; ~20 branch/helper clusters skipped: filter paths (`_apply_filter_py` 542-565), reload (`_apply_reload_filter` 821-834), `_values_equal` 1306-1316, most of `_auto_convert_join_keys` 1271-1289, size-guard 1334/1340, plus many small validate/route/find-column branches. | ~20 targeted tests, mostly small configs driven through `_process` + a few direct helper calls. See diagnosis for the per-line list. | medium |
| `file/file_output_delimited.py` | 83.7% | YES | Dominant gap is the entire `_handle_empty_input` body (619-666) + empty branch in `_process` (345-349), all crashing at the line-342 `append` TypeError. Plus `_format_decimal_columns` inner branches (481-521) the 4 mis-pointed tests never reach. Apply C5 + T2. | Together clear ~45 of 49 lines. Lines 206/958/963 may need 1-2 small tests. | small |
| `transform/java_row_component.py` | 83.8% | NO | Recently-added paths untested: `chunk_size` validation (134-137, 141-142), output_schema list-normalization + None branch (203-209), `schema_inputs_map` -> input_schema_dict (227-230). No test sets any of these. | ~5-6 small tests reusing existing FakeBridge/java_bridge fixtures. See diagnosis. | small |
| `trigger_manager.py` | 92.2% | NO | `_to_python_scalar` numpy `.item()` path (63-66) never hit (tests store native Python). `_resolve_context_refs` closures (398-413) dead because NO test in the repo constructs `TriggerManager` with a `context_manager` arg. | ~4 tests: a numpy-scalar globalMap value; `TriggerManager(global_map=gm, context_manager=cm)` with `${context.X}`, bare `context.X`, and an undefined-var placeholder. | small |
| `converters/.../expression_converter.py` | (snapshot 94.8%) | NO | STALE snapshot. Current HEAD = 98.9% / 1 miss, 0 failures (fix `9a054ef`). The one residual miss (line 134) is DEAD CODE: the concat regex at 133 always short-circuits on `+` (an operator) earlier. | None. Mark line 134 `# pragma: no cover` (documented dead code). Re-measure (D-snap). | trivial |

Effort roll-up for the floor: oracle_output (medium, code+decision), file_input_xml
(small, mechanical), file_output_delimited (small, code+test), engine xml_map
(medium, upstream-gated + optional), converter xml_map (small, net-new), py_map
(medium, ~20 net-new), java_row (small, ~6 net-new), trigger_manager (small, ~4
net-new), expression_converter (trivial, pragma + re-measure).

> Two ABOVE-floor modules are also healed by bucket (a) and worth noting:
> `oracle_input.py` (97.9%, lines 177/185) and `mssql_input.py` (98.8%, line 160)
> reach ~100% once C4 lands - the trim lambda bodies start executing.

---

## 4. Test landscape / harness guide (durable)

All paths absolute under `/Users/aarun/Workspace/Projects/citi/dataprep/.claude/worktrees/peaceful-gates-f1e530`.

### 4.1 Conftest tree (6 files; pytest parent-walk, child does NOT shadow parent)

| Conftest | Provides | Notes / gotchas |
|---|---|---|
| `tests/conftest.py` (ROOT) | `PipelineResult` dataclass; `FIXTURE_JOBS_ROOT = tests/fixtures/jobs`; `run_job_fixture(name, mutations=None)` (copies a fixture JSON to tmp_path, applies `{component_id: {key: value}}` overrides, builds `ETLEngine`, executes, returns `PipelineResult`); `assert_ascii_logs` (fails teardown if any captured log byte is non-ASCII - RHEL ASCII-only rule). | Imports `src.v1.engine.engine.ETLEngine` at module top, so the ROOT conftest is itself sensitive to engine import-blockers; an engine import failure breaks collection of the ENTIRE `tests/` tree. (This is exactly what masked the 159 failures.) |
| `tests/v1/engine/conftest.py` | `StubComponent`, `IterateStubComponent`, `StubIterateItem`; `make_stub_component` / `make_job_config` / `make_iterate_job_config`; SESSION-SCOPED `java_bridge` fixture (one real JVM via `JavaBridgeManager()`, dynamic port, SIGTERM teardown). | JVM is shared across the whole session and NOT reset between tests (T-08-19): java tests that mutate globalMap/context must self-clean. |
| `tests/v1/engine/components/file/conftest.py` | SESSION-SCOPED `synthetic_60mb_xml` (generates a fresh ~60MB XML for streaming-path tests; asserts 55-65MB). | Never committed; generated per session. |
| `tests/v1/java_bridge/conftest.py` | Mirror of the engine `java_bridge` fixture. | So `java_bridge/` tests don't depend on a sibling dir. |
| `tests/integration/conftest.py` | `java_bridge` variant that yields the JAR PATH sentinel (does NOT start a JVM); `ETLEngine` starts its own manager when `java_config.enabled=True`. | Build-gate/skip only. |
| `tests/v1/engine/components/database/integration/conftest.py` (Oracle) | `pytest.importorskip('testcontainers')`; `oracle_container` (gvenzl/oracle-free:23, ~15-30s cold start), `oracle_dsn`/`oracle_connection`/`temp_table` (DROP...PURGE teardown), `job_config_oracle_overrides`. | Skips when testcontainers missing, `SKIP_ORACLE_CONTAINER` set, or Docker not running. |

### 4.2 Markers (`pyproject.toml [tool.pytest.ini_options].markers`)

| Marker | Meaning | Usage |
|---|---|---|
| `unit` | fast, no I/O | ~105 files |
| `integration` | file I/O | ~15 files |
| `java` | needs the bridge jar | ~30 files |
| `oracle` | needs Oracle testcontainer, opt-in, slow | ~13 files; EXCLUDED by the gate |
| `slow` | >5s | declared, 0 uses |
| `coverage` | **always-skipped documentation marker** | 1 use (`tests/integration/test_iterate_e2e.py::test_phase_10_files_covered_above_90_percent`), immediately `pytest.skip()`s - it documents intent, it does NOT enforce. Enforcement is the gate command. Do NOT tag real tests with it. |

`pyproject` `addopts = '-v --tb=short'`. Triage runs deliberately blank this with
`-o addopts=` for clean failure output without coverage-plugin noise.

### 4.3 Java-bridge jar requirement (critical in this worktree)

- Required at `src/v1/java_bridge/java/target/java-bridge-with-dependencies.jar`
  (gitignored build artifact). Build: `cd src/v1/java_bridge/java && mvn package -q`
  (needs JVM 11+ on PATH).
- WORKTREE GOTCHA: all four java conftests `_find_java_bridge_jar()` resolve the jar
  from the MAIN repo via `git rev-parse --git-common-dir` (target/ is gitignored and
  absent in the worktree), then SYMLINK the main-repo jar into the worktree's
  `target/` so `JavaBridge._find_jar_path` (relative to its own `__file__`) succeeds,
  and unlink on teardown.
- If the jar is ABSENT, java-fixture tests are `pytest.skip()`'d (NOT failed) - java
  coverage silently DROPS rather than turning red. The current gate state was
  measured WITH the jar built, so java tests actually ran.

### 4.4 How tests construct components (two patterns, both bypass `XmlParser`)

- **Engine component tests**: construct the v1 class directly -
  `Comp(component_id=..., config=cfg, global_map=GlobalMap(), context_manager=ContextManager())`,
  then call `comp._process(df)` directly (34 files do this).
  CONSTRUCTION FOOTGUN: tests must manually set `comp.config = dict(cfg)` (or deepcopy)
  AFTER construction. Normally `ETLEngine.execute()` populates `self.config` via a
  deepcopy of `_original_config`; calling `_process()` directly never runs that, so a
  test that forgets `comp.config = ...` sees an empty config. `make_stub_component()`
  does this for you; per-component `_make_component` helpers replicate it inline
  (reference: `_make_component(config=None, global_map=None)` in `test_convert_type.py`).
- **Converter tests**: build a `TalendNode` directly via a `_make_node(params=...,
  schema=..., component_id=..., component_type=...)` helper and feed it to the
  converter class; `SchemaColumn` models columns. Bypasses `XmlParser` entirely.
- **Full-pipeline tests**: either the root `run_job_fixture` (JSON fixture ->
  `ETLEngine`) or direct `ETLEngine(config_dict)` (13 files). `XmlParser` appears in
  only ~6 test files - the dominant convention is to feed pre-built dicts/nodes.

### 4.5 The per-module 95% gate (`scripts/check_per_module_coverage.py`)

- There is NO global `fail_under` (deliberately omitted) - a global average lets a
  100% module mask a 60% one. Enforcement is external.
- The script (stdlib-only, ASCII-only, 147 lines) reads
  `coverage.json['files'][path]['summary']['percent_covered']` per module, collects
  any below `--floor` (default 95.0), prints
  `FAIL: <K> module(s) below 95.0% ...` to stderr with
  `  <pct>%  <path>  (missing <n> lines)`, exits 1. Exit 0 = PASS, exit 2 = malformed
  report.
- `coverage.json` keys are repo-relative posix, e.g.
  `src/v1/engine/components/file/file_input_xml.py`. The current file has 198 file
  records (meta/files/totals top-level keys).
- Coverage scope (`[tool.coverage.run]`): `source=['src/v1/engine','src/converters']`;
  omits `__init__.py`, tests, `test_*.py`; `branch=false` (LINE coverage only);
  `parallel=true` (matches xdist shards). pragma allowlist is NARROW (only
  `if __name__ == .__main__.:`, `raise NotImplementedError`, `@abstractmethod`).
- GATE BLIND SPOT: the script only checks modules that APPEAR in `coverage.json`. A
  module never imported during the run is silently UN-gated - the file set is
  import-driven, not a filesystem enumeration. (CLAUDE.md still cites "181 in-scope
  modules"; current coverage.json has 198 - drift from the recent 28 WIP commits.)

### 4.6 The `.coverage` shard cleanup gotcha

`parallel=true` + xdist writes sharded `.coverage.*` files. Stale shards from an
interrupted/aborted prior run get COMBINED into the JSON and silently pollute the
report (inflate/skew numbers). The leading `rm -f .coverage*` in the gate command is
REQUIRED. Symptom (docs/guides/DEV_SETUP.md:221): unexpected coverage numbers -> you
have a stale `.coverage.*` shard; rm and re-run. Forgetting this is the most common
false coverage reading.

---

## 5. How to reproduce (exact commands)

Run from the worktree root.

Build the Java bridge jar (needed for accurate java coverage; skips otherwise):

```
cd src/v1/java_bridge/java && mvn package -q
```

Run the canonical coverage gate (CLAUDE.md "Coverage Gate"; also DEV_SETUP.md,
DEPLOYMENT.md, TESTING_STRATEGY.md). The leading `rm` is mandatory (4.6):

```
rm -f .coverage* && python -m pytest tests/ -m "not oracle" -n auto \
  --cov=src/v1/engine --cov=src/converters \
  --cov-report=term-missing --cov-report=html --cov-report=json \
&& python scripts/check_per_module_coverage.py coverage.json --floor 95
```

- `-m "not oracle"` excludes the opt-in Oracle testcontainer suite.
- `-m java` tests ARE measured, so JVM 11+ must be on PATH for full/accurate
  coverage; without the jar those tests skip and their target modules lose coverage.

Clean re-run before trusting a failure count (resolves the env-flaky 5 in
engine-misc and the stale expression_converter snapshot - D-snap):

```
rm -rf .pytest_cache && find . -name __pycache__ -type d -prune -exec rm -rf {} + \
  && rm -f .coverage* coverage.json
# then re-run the gate command above
```

Fast failure triage for a single area (drops `-v --tb=short` and coverage noise):

```
python -m pytest -o addopts= -p no:cacheprovider \
  tests/v1/engine/components/database/test_oracle_output.py
```

---

## 6. Cross-references

- `docs/understanding/07-findings-and-risks.md` - the risk register. Direct ties:
  - H-B1 / H-B2: the two import-blockers that masked these 159 failures (now fixed).
  - H-B3 / H-B4 / H-B5: the three oracle_output code bugs = C1 / C2 / C3 here.
  - H-S1: the oracle_output quoted-vs-unquoted test conflict = D1 here.
  - M-B1: expression_converter `!=` corruption (out-of-scope latent bug).
  - M-B10: mssql_input shared-connection timeout side-effect (out-of-scope hardening).
  - M-B4 region: file_input_delimited stride/scrubber issues (relates to C6).
- `docs/understanding/03-engine-components-catalog.md` - component-by-component
  reference for the file/transform/database components touched above.
- `docs/understanding/05-database-layer.md` - oracle_output / oracle_input /
  mssql_input behavior background for C1-C4 and D1.

---

## 7. Phase 3 quick-start checklist

1. Re-measure the gate from a CLEAN state (5) to get the true failure count (D-snap).
2. Fix bucket (a) code bugs C1-C6 (unconditional; unblocks ~117 failures + most floor).
3. Apply bucket (b) stale-test edits T1-T5 (T6 already green).
4. Get product answers on D1/D1b (oracle quoting) and D2 (positional KEEP=ALL);
   then make the ~17 oracle assertion tests and 2 positional tests canonical.
5. Add net-new coverage tests: py_map (~20), java_row (~6), trigger_manager (~4),
   converter xml_map (helper tests); pragma the one dead line in expression_converter.
6. Re-run the gate; confirm 0 failures and all in-scope modules >= 95%.
7. Only then add the 2 new components (tag tests `unit`/`integration`/`java`; set
   `comp.config` after direct construction; use `assert_ascii_logs` on log paths).
