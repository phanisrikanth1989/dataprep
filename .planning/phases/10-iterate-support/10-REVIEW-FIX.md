---
phase: 10-iterate-support
fixed_at: 2026-05-05T00:00:00Z
review_path: .planning/phases/10-iterate-support/10-REVIEW.md
iteration: 1
findings_in_scope: 15
fixed: 6
already_fixed: 6
skipped: 3
status: partial
---

# Phase 10: Code Review Fix Report

**Fixed at:** 2026-05-05
**Source review:** `.planning/phases/10-iterate-support/10-REVIEW.md`
**Iteration:** 1

**Summary:**

- Findings in scope (Critical + Warning): 15
- Already fixed by gap-closure (Plans 10-09, 10-10, 10-11): 6 BLOCKERs
- Newly fixed in this run: 6 WARNINGs
- Skipped (architectural / out-of-scope audit): 3 WARNINGs

INFO findings (5) are out of scope per `fix_scope: critical_warning`.

---

## Already Fixed (Pre-existing Gap-Closure)

The 6 BLOCKER findings were resolved by Plans 10-09, 10-10, and 10-11 before this fixer ran. Each was re-verified against the current source before being marked.

### CR-01 (BLOCKER): Integration tests query wrong dict key

**File:** `tests/integration/test_iterate_e2e.py:160`, `:323`
**Resolution:** Plan 10-09 (commits `1610602`, `6332192`). Both call sites now use `result.get("_needs_review", [])`. A regression-guard test (`test_fatal_needs_review_gate_fires`) was added.

### CR-02 (BLOCKER): Executor bypasses public iteration API

**File:** `src/v1/engine/executor.py:346`
**Resolution:** Plan 10-10 (commit `bfe82f0`). `_execute_iterate_body` now drives the loop with `while iter_component.has_next_iteration()` + `iter_component.get_next_iteration_context()`; `current_iteration_index` advances correctly per iteration; the duplicate `set_iteration_globalmap` and `_CURRENT_ITERATION` writes were removed.

### CR-03 (BLOCKER): `on_iteration_error` (Hook 8) unreachable

**File:** `src/v1/engine/executor.py:365`, `src/v1/engine/base_iterate_component.py`
**Resolution:** Plan 10-10 (commit `33bee47`). The unreachable `except ComponentExecutionError` arm in the iterate driver was removed and `on_iteration_error` was deleted from `BaseIterateComponent`. The errors-as-statuses contract is now documented in the module docstring.

### CR-04 (BLOCKER): `_any_body_die_on_error` reads stale `execution_stats`

**File:** `src/v1/engine/executor.py:480`
**Resolution:** Plan 10-10 (commit `bfe82f0`). `_execute_iterate_body` now snapshots pre-iteration body status into `pre_iter_stats`, computes `iter_local_failed_bodies` as the per-iteration error diff, and passes it to `_any_body_die_on_error`, scoping the check to the current iteration only.

### CR-05 (BLOCKER): `_execute_subjob_plan` re-use across parent and body

**File:** `src/v1/engine/executor.py:226-305`
**Resolution:** Documentation/architecture concern only. Per `10-VERIFICATION.md`, this was reclassified as a non-defect (`ExecutionPlan._detect_nested_iterate` enforces depth=1 at plan time, so the dead branch cannot fire). Recorded as an architectural note for Phase 10.1 nested-iterate work; no code change required.

### CR-06 (BLOCKER): `_sort_paths` racy `path.stat()` in lambda

**File:** `src/v1/engine/components/file/file_list.py:339-354`, `:518-526`
**Resolution:** Plan 10-11 (commits `a532abc`, `22e6afc`). `_safe_stat_size` and `_safe_stat_mtime` static helpers wrap `p.stat()` in `try/except OSError`, returning sort-stable defaults (`0`, `0.0`) and logging an ASCII-only WARNING. `TestSortPathsRaceCondition` covers the TOCTOU race.

---

## Fixed Issues

### WR-01: Unsafe `execute()` re-entry on iterate components

**Files modified:** `src/v1/engine/base_iterate_component.py`
**Commit:** `73217f9`
**Applied fix:** `BaseIterateComponent.execute()` now rejects re-entry when `status == RUNNING` (concurrent / re-entrant call) or `status == SUCCESS` without an intervening `reset()`. Both paths raise `ConfigurationError` with a message pointing the caller at `reset()`. Stops silent re-walks of the directory (tFileList) and silent re-materialisation of `to_dict('records')` buffers (tFlowToIterate).

### WR-03: Document `_truthy` vs `_normalize_case_sensitive` divergence

**Files modified:** `src/v1/engine/components/file/file_list.py`
**Commit:** `34a6598`
**Applied fix:** Both helpers now carry WR-03 docstring notes explaining why they intentionally differ. `_normalize_case_sensitive` is strict (rejects `int 1`) because it controls regex compilation flags and ambiguous coercion would silently change pattern semantics. `_truthy` is lenient (accepts `int 1`) because it gates non-semantic flags. Both docstrings explicitly direct callers not to route `CASE_SENSITIVE` through `_truthy`.

### WR-04: Drop no-op reverse on `ORDER_BY_NOTHING + DESC`

**Files modified:** `src/v1/engine/components/file/file_list.py`
**Commit:** `20a71cc`
**Applied fix:** Removed the `list(reversed(paths))` allocation in the `ORDER_BY_NOTHING` branch. Talend itself does not reverse on `ORDER_BY_NOTHING + DESC`; reversing a non-deterministic sequence is meaningless and only wastes O(n). The branch now returns `paths` unchanged in both ASC and DESC variants.

### WR-05: Defense-in-depth assertion in iterate body driver

**Files modified:** `src/v1/engine/executor.py`
**Commit:** `a1a00ea`
**Applied fix:** Added `assert iter_component.status != ComponentStatus.ERROR` at the top of `_execute_iterate_body`. If a future code path bypasses the success gate in `_execute_subjob_plan` and reaches the body driver with the iterate component in `ERROR` state, the assertion now surfaces the bypass loudly instead of silently running zero iterations and reporting success.

### WR-06: Catch `ConfigurationError` mid-iterate-loop

**Files modified:** `src/v1/engine/executor.py`
**Commit:** `c27f531`
**Applied fix:** Wrapped `iter_component.get_next_iteration_context()` in a `try/except ConfigurationError` inside `_execute_iterate_body`. tFlowToIterate's `set_iteration_globalmap` raises `ConfigurationError` when `map_entries` references a column not present in a particular row; previously the exception propagated out of the iterate driver, bypassing iterate-end logging, NB_LINE stats, and reject-buffer routing. The handler now logs the failure (ASCII-only), records an error iteration, and surfaces the failure via the existing `_termination_error` / `_job_terminated` mechanism (the same path tDie uses), letting the cleanup code below the loop run before the error is reported.

### WR-07: Compile mask regexes once per directory walk

**Files modified:** `src/v1/engine/components/file/file_list.py`
**Commit:** `c7d2829`
**Applied fix:** `prepare_iterations` now compiles the inclusion mask list and the exclusion mask once before filtering, instead of going through `_match_path` (which recompiles per file). For directories with thousands of files this avoids `O(N_files * N_masks)` `re.compile` calls. `_match_path` is retained for any single-mask callers but is no longer used in the hot path.

---

## Skipped Issues

### WR-02: `_propagate_input_schemas` connector key alias chain

**File:** `src/converters/talend_to_v1/converter.py:341-347`
**Reason:** `skipped: requires cross-component audit and canonical-key registry definition (architectural)`
**Original issue:** Lookup uppercases `flow["type"]` and matches against the converter's `outputs` map. Components like tUniqRow may use `"OUTPUT"` while flow types are `"UNIQUE"` / `"DUPLICATE"`, so the lookup is silently brittle. The fix REVIEW.md proposes -- "document the canonical set of output connector keys and validate them at conversion time" -- requires (1) auditing every converter's `outputs` map, (2) defining a canonical alias chain, and (3) wiring validator support for it. That is a phase-12 / converter-cleanup deliverable, not a one-line fix; attempting it here would touch 80+ converters and is out of scope for review-fix.

### WR-08: `body_components_executed_by_iterate` not propagated to nested calls

**File:** `src/v1/engine/executor.py:222-266`
**Reason:** `skipped: dead code today; future-proofing tracked for Phase 10.1`
**Original issue:** The local `body_components_executed_by_iterate` set is not threaded into recursive `_execute_subjob_plan` calls. Phase 10's `ExecutionPlan._detect_nested_iterate` rejects nested iterate, so the recursion path is unreachable today. Promoting the set to instance state guarded by `_current_iterate_depth` is correct preparation for Phase 10.1 nested-iterate but the change requires a lifecycle test the current suite cannot exercise (no nested-iterate fixture). Deferred to Phase 10.1, where the test fixture and the set's semantics will be designed together.

### WR-09: `to_schema["input"]` last-write-wins for multi-input components

**File:** `src/converters/talend_to_v1/converter.py:368-370`
**Reason:** `skipped: requires audit of all multi-input engine components (tMap, tJoin, etc.) -- out of scope for Phase 10 review-fix`
**Original issue:** When a multi-input target consumes legacy `input_schema` (engine.py:131) instead of the per-flow `schema_inputs_map` (engine.py:138), it sees only the last flow's schema, silently corrupting validation. The REVIEW.md fix says "audit all multi-input engine components and either (a) enforce reading from `schema_inputs_map`, or (b) remove `input_schema` for multi-input cases." This is a multi-component audit (tMap, tJoin, tDenormalize, etc.) belonging to a dedicated converter-cleanup phase, not a one-touch fix. Phase 10 didn't introduce the issue and its iterate-specific propagation is already keyed correctly.

---

_Fixed: 2026-05-05_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
