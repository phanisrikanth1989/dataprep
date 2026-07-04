---
phase: 10-iterate-support
reviewed: 2026-05-05T00:00:00Z
depth: standard
files_reviewed: 32
files_reviewed_list:
  - pyproject.toml
  - src/converters/talend_to_v1/components/base.py
  - src/converters/talend_to_v1/components/file/file_input_delimited.py
  - src/converters/talend_to_v1/converter.py
  - src/converters/talend_to_v1/xml_parser.py
  - src/v1/engine/base_iterate_component.py
  - src/v1/engine/components/__init__.py
  - src/v1/engine/components/file/__init__.py
  - src/v1/engine/components/file/file_list.py
  - src/v1/engine/components/iterate/__init__.py
  - src/v1/engine/components/iterate/flow_to_iterate.py
  - src/v1/engine/engine.py
  - src/v1/engine/execution_plan.py
  - src/v1/engine/executor.py
  - src/v1/engine/iterate_logging.py
  - src/v1/engine/output_router.py
  - tests/converters/talend_to_v1/test_converter.py
  - tests/converters/talend_to_v1/test_iterate_connection_extraction.py
  - tests/integration/__init__.py
  - tests/integration/conftest.py
  - tests/integration/test_file_exist_e2e.py
  - tests/integration/test_iterate_e2e.py
  - tests/v1/engine/components/file/test_file_list.py
  - tests/v1/engine/components/iterate/__init__.py
  - tests/v1/engine/components/iterate/test_flow_to_iterate.py
  - tests/v1/engine/conftest.py
  - tests/v1/engine/test_base_component.py
  - tests/v1/engine/test_base_iterate_component.py
  - tests/v1/engine/test_execution_plan_iterate.py
  - tests/v1/engine/test_executor_iterate.py
  - tests/v1/engine/test_iterate_logging.py
  - tests/v1/engine/test_output_router_iterate.py
findings:
  critical: 6
  warning: 9
  info: 5
  total: 20
status: issues_found
---

# Phase 10: Code Review Report

**Reviewed:** 2026-05-05
**Depth:** standard
**Files Reviewed:** 32
**Status:** issues_found

## Summary

Phase 10 introduces iterate support (tFileList, tFlowToIterate) via a new `BaseIterateComponent`, a documented 9-hook lifecycle, an `Executor._execute_iterate_body` driver, `ExecutionPlan` body-subgraph BFS, `OutputRouter` REJECT-drain helpers, and ASCII-only iterate logging. The architecture is solid: ExecutionPlan owns the DAG, Executor owns orchestration, and components only own their iteration shape. Most edge cases (empty iterate, tDie inside body, die_on_error mid-loop, cross-subjob flow preservation) have explicit code paths and tests.

That said, the submission has substantial defects:

- **Two integration tests use the wrong dictionary key** (`"needs_review"` instead of `"_needs_review"`), so they cannot ever fail on conversion errors — silent test rot in the highest-value E2E suite.
- **The Executor bypasses the public `BaseIterateComponent` iteration API** (`has_next_iteration` / `get_next_iteration_context`) and iterates `iteration_iter` directly, leaving `current_iteration_index` permanently at 0 and skipping the canonical key-write path. The fact that an entire `get_next_iteration_context` method exists, is documented as the canonical write site for `_CURRENT_ITERATION`, has its own unit tests, and is never called by the production caller is a serious design split.
- **Per-iteration body errors raised inside `_execute_subjob_plan` are caught by `_execute_component` and converted to a string-status return value. The `except ComponentExecutionError` handler in `_execute_iterate_body` is therefore unreachable in practice**, so `Hook 8 (on_iteration_error)` never runs through the real call path. The unit tests that exercise it (`TestFailureSemantics`) work only because `_execute_component` catches inside its own try/except and `body_failed=True` is set via the `body_result == "error"` branch — `on_iteration_error` is never invoked. This is a contract bug.
- **`_any_body_die_on_error` looks at stale execution_stats**: by the time the iterate loop checks it, body components may have been reset (via `comp.reset()` further down the loop in non-failing branches), but on the failing-iteration branch the reset happens AFTER the check — fine — except the stats check uses `self.execution_stats[body_id].get("status")` which is set by `_execute_component`. After the first failed iteration this works; on a second iteration with different bodies failing, stale stats from the prior iteration can cause spurious die-on-error termination.
- **`_propagate_input_schemas` and `_parse_flows` ignore the connector type for some callers**: `_propagate_input_schemas` only looks up `outputs_map` by the flow's lowercase `type` (e.g., `flow`, `reject`), then uppercases it. But REJECT-typed flows for tFilterRow etc. should pull `outputs.REJECT`, and the converter writes `outputs` keyed by Talend connector strings (uppercase) — see WR-08.
- **Several bool/non-bool fragility issues** in `_truthy`, plus mutation-in-place anti-patterns where `list = sorted(list, ...)` is fine but `list = list(reversed(paths))` isn't documented (`paths` callsite is shared).

In total: 6 BLOCKER, 9 WARNING, 5 INFO findings below.

---

## Critical Issues

### CR-01 (BLOCKER): Integration tests query wrong dict key — cannot detect fatal conversion errors

**File:** `tests/integration/test_iterate_e2e.py:160` and `:323`

**Issue:**
The two tests `TestJobTFileListConversion.test_converts_without_errors` and `TestJobTFlowToIterateConversion.test_converts_without_errors` both do:
```python
fatal = [
    e for e in result.get("needs_review", [])      # <-- key bug
    if e.get("severity") in ("error", "fatal")
]
assert not fatal, ...
```

But `TalendToV1Converter.convert_file` writes the list under the key `_needs_review` (with leading underscore — see `src/converters/talend_to_v1/converter.py:172`):
```python
if needs_review:
    config["_needs_review"] = needs_review
```

The same test file even imports the same converter. The other suite, `tests/converters/talend_to_v1/test_iterate_connection_extraction.py:29`, correctly uses `result.get("_needs_review", [])`. So `result.get("needs_review", [])` here always returns `[]`, the `fatal` list is always empty, and these E2E "smoke check" assertions can NEVER fail regardless of what conversion produces. This silently negates the primary acceptance gate for the phase.

**Fix:**
```python
fatal = [
    e for e in result.get("_needs_review", [])
    if e.get("severity") in ("error", "fatal")
]
```

---

### CR-02 (BLOCKER): Executor bypasses public iteration API; `current_iteration_index` never advances

**File:** `src/v1/engine/executor.py:346` (and the entire `_execute_iterate_body` body loop)

**Issue:**
`BaseIterateComponent` documents two consumption methods explicitly tagged "used by Executor iterate loop":
- `has_next_iteration()` (line 275)
- `get_next_iteration_context()` (line 290)

These methods are responsible for (a) advancing `self.current_iteration_index`, (b) calling `set_iteration_globalmap(item)`, and (c) writing the canonical `f"{self.id}_CURRENT_ITERATION"` key (per ITER-11 / D-F7).

The Executor's `_execute_iterate_body` ignores all of this and iterates the raw iterator instead:
```python
for index, item in enumerate(iter_component.iteration_iter, start=1):
    ...
    self.global_map.put(f"{cid}_CURRENT_ITERATION", index)   # duplicating the key write
    iter_component.set_iteration_globalmap(item)             # duplicating the call
    ...
```

Consequences:
1. `iter_component.current_iteration_index` permanently remains 0 after `execute()` returns. Any downstream code reading it (e.g., a future tForeach that inherits the base class, or any consumer relying on it as a Talend-parity counter) sees the wrong value.
2. The "9-hook lifecycle" docstring's claim that `get_next_iteration_context` is the place where the key is written (and is the place the Executor calls) is now false — the Executor writes it directly. This contradicts the module docstring (line 31: "ITER-11 Fix (D-F7): get_next_iteration_context() writes f"{self.id}_CURRENT_ITERATION"...").
3. `has_next_iteration()` / `get_next_iteration_context()` are dead code in production but covered by `test_base_iterate_component.py::TestCurrentIterationKeyRename`, giving false coverage for the rename fix.

**Fix:** Either (a) rip out `has_next_iteration` / `get_next_iteration_context` and update the module docstring to reflect the executor-driven contract, OR (b) drive the Executor loop through them so the documented contract holds. Option (b) is cleaner and matches the unit tests:
```python
while iter_component.has_next_iteration():
    ctx = iter_component.get_next_iteration_context()
    if not ctx:
        break
    item, index = ctx["item"], ctx["index"]
    if iter_component.should_stop(item, index):
        break
    iter_component.before_iteration(item, index)
    # set_iteration_globalmap and key-write already done by get_next_iteration_context
    ...
```

---

### CR-03 (BLOCKER): `on_iteration_error` (Hook 8) is unreachable through the real Executor path

**File:** `src/v1/engine/executor.py:365-377`

**Issue:**
The iterate loop wraps `_execute_subjob_plan` in:
```python
try:
    body_result = self._execute_subjob_plan(body_plan)
    if body_result == "error":
        body_failed = True
except ComponentExecutionError as e:
    exit_code = getattr(e, "exit_code", None)
    if exit_code is not None:
        raise          # tDie path
    body_failed = True
    if not iter_component.on_iteration_error(item, index, e):
        raise
```

But `_execute_subjob_plan` does not raise `ComponentExecutionError` — `_execute_component` catches every exception in its own `except Exception` block (line 580-614) and returns the string `"error"`. The only `raise` path inside `_execute_component` is the tDie branch which does NOT re-raise (line 603: "Do NOT re-raise -- let execute_job handle via _job_terminated flag"). And `_execute_subjob_plan` itself never re-raises a caught error.

Result: the `except ComponentExecutionError` arm of the iterate body try/except is unreachable in production. `on_iteration_error` is consequently never called via the production code path. The unit test in `test_executor_iterate.py::TestFailureSemantics::test_die_on_error_false_continues` only proves that the loop continues — it does NOT prove `on_iteration_error` was invoked, because it never is.

Body components that want a custom error hook (the documented Hook 8 design) silently get nothing.

**Fix:** Either:
1. Have `_execute_iterate_body` check `body_result == "error"` and itself call `iter_component.on_iteration_error(item, index, exc)` — but `exc` is unavailable because `_execute_component` swallowed it. Must thread the original exception out of `_execute_component` (return tuple, or stash it on `self.execution_stats[body_id]["exception"]`).
2. Or, document this intentional "errors-as-statuses" design and remove the unreachable except arm + remove `on_iteration_error` from `BaseIterateComponent` since it cannot fire.

Add an explicit unit test that patches `iter_component.on_iteration_error` to `MagicMock()` and asserts the mock was called when a body fails.

---

### CR-04 (BLOCKER): `_any_body_die_on_error` reads `execution_stats` that may be from a prior iteration

**File:** `src/v1/engine/executor.py:480-498`

**Issue:**
```python
def _any_body_die_on_error(self, body_plan):
    for body_id in body_plan.component_ids:
        comp = self.components.get(body_id)
        ...
        comp_stats = self.execution_stats.get(body_id, {})
        if comp_stats.get("status") == "error" and ...:
            return True
    return False
```

This is called inside the iterate loop right after `body_failed=True`. The check reads `self.execution_stats[body_id]`, but `execution_stats` is only mutated by `_execute_component` and never cleared between iterations. If iteration N fails, `execution_stats[body_id]["status"] == "error"` is set. If iteration N+1 succeeds for that same body, `_execute_component` overwrites with the new success entry — fine. But if iteration N+1 has a *different* body component fail, the check loops over ALL body components and finds the OLD "error" status from iter N for the *previously failed* body, returning True even though the current iteration's failure is on a body with `die_on_error=False`. This causes spurious early termination of the iterate loop on legitimate `die_on_error=False` runs.

The test `TestFailureSemantics::test_die_on_error_false_continues` uses a single body component with `die_on_error=False` and only one failure, so this bug is not caught.

**Fix:** Track iteration-local failures explicitly inside the loop:
```python
iter_failed_bodies: list[str] = []
# ... if body_failed: collect bodies whose status changed to "error" THIS iteration
# Then check die_on_error only on iter_failed_bodies, not on stale stats.
```
Or clear `execution_stats` entries for body_ids before each iteration's body run.

---

### CR-05 (BLOCKER): `_execute_subjob_plan` skips iterate body re-execution when called for the body itself

**File:** `src/v1/engine/executor.py:226-305` together with `:311-478`

**Issue:**
`_execute_iterate_body` calls `_execute_subjob_plan(body_plan)` per iteration. `_execute_subjob_plan` then iterates `subjob_plan.component_ids` — but at line 226, for each `comp_id` it checks `if comp_id in self.components: ...` and at line 252 detects iterate components (`is_iterate_component=True`) and recursively calls `_execute_iterate_body` on them. Phase 10 forbids nested iterate (raised in `ExecutionPlan._detect_nested_iterate`), so this branch is dead — but the dead code path also adds `body_id`s to `body_components_executed_by_iterate` and to `executed_components` (line 264-266), which the OUTER iterate loop's reset/discard logic (line 432-436) tries to undo.

There is also a subtle re-entrancy issue: `_execute_subjob_plan` is invoked once for the parent subjob (which contains the iterate source) and once per iteration for the body subgraph. Both invocations iterate over `component_ids`. The body's parent subjob_plan also includes the iterate source itself, and the parent loop's `body_components_executed_by_iterate` set tries to skip components already executed by iterate-body-loop. But when this method is called recursively (with the body_plan), there's no parent context — the outer parent's `body_components_executed_by_iterate` is not propagated into the body run, so if a body subjob and parent subjob share components (which they shouldn't, but ExecutionPlan's BFS could include them), the same component may execute twice.

In practice, the body_plan is a strict subset of the parent subjob_plan, so an outer re-entry would re-execute components that were already added to `executed_components`. Line 235's `if comp_id not in self.components` check passes; line 240's `are_inputs_ready` may pass; then the component runs again. The unit tests don't exercise this because all iterate-source bodies are entirely contained.

**Fix:** Document explicitly that `_execute_subjob_plan` is single-purpose for either parent OR body and add an assertion that nested iterate doesn't reach the runtime branch (currently relies on ExecutionPlan precondition).

Less critical, but this is BLOCKER because the architecture re-uses one method for two different responsibilities, and the seam is fragile under future Phase 10.1 nested iterate work.

---

### CR-06 (BLOCKER): `prepare_iterations` of `FileList` triggers `path.resolve()` and `path.stat()` per yielded item without input validation

**File:** `src/v1/engine/components/file/file_list.py:339-354` and `:518-526`

**Issue:**
`_sort_paths` calls `p.stat().st_size` and `p.stat().st_mtime` inside the sort key lambda. If a file is deleted between `directory.iterdir()` and the sort (a race condition that is realistic on busy directories), `p.stat()` raises `FileNotFoundError` and the lambda crashes mid-sort. The defensive `if p.exists()` check inside the lambda is racy — the file may be deleted between `p.exists()` and `p.stat()`.

Worse, `p.resolve()` (line 341) follows symlinks and may raise `OSError` on broken symlinks; on some systems with `strict=True` (Python 3.10+ default for non-existent paths) the call raises `FileNotFoundError`.

Talend's behaviour on these races is to skip the file. The current implementation crashes the iterate loop with an unhandled exception inside `prepare_iterations` (which Executor wraps in `ComponentExecutionError`).

**Fix:** Wrap stat calls in try/except that returns a sort-stable default (and logs WARNING):
```python
def _safe_size(p):
    try:
        return p.stat().st_size
    except OSError:
        return 0
```
Same for `resolve()`.

---

## Warnings

### WR-01: `iteration_iter` re-iteration across `execute()` calls is unsafe

**File:** `src/v1/engine/base_iterate_component.py:157, 408`

**Issue:** `prepare_iterations` returns an Iterator (per D-A3, intentional). On `reset()`, `self.iteration_iter = iter(())` is set. But `execute()` does `self.iteration_iter = self.prepare_iterations(input_data)` — fine on first call. After reset+execute, the new iterator is fresh. However, if a caller invokes `execute()` twice without `reset()` (e.g., the engine outer subjob loop unintentionally hits the iterate component twice), the second call REPLACES `iteration_iter` with a new iterator built from the same `input_data` reference. This silently re-materialises the data, doubling memory pressure for tFlowToIterate's `to_dict('records')` and re-reading the directory for tFileList. There's no guard against double-execute.

**Fix:** Add a status check in `execute()` that raises if called when `status==RUNNING` or after a completed iteration without `reset()`.

---

### WR-02: `_propagate_input_schemas` connector lookup uses lowercase flow type but uppercase key normalisation

**File:** `src/converters/talend_to_v1/converter.py:341-347`

**Issue:**
```python
norm_map = {str(k).upper(): v for k, v in outputs_map.items()}
connector_key = (flow.get("type") or "").upper()
upstream_output = norm_map.get(connector_key)
```

`flow.get("type")` is set in `_parse_flows` (line 246) to `conn.connector_type.lower()` — so `flow["type"]` is always lowercase (e.g., `"flow"`, `"reject"`). After `.upper()` we get `"FLOW"`, `"REJECT"`. But the converter components store `outputs` keyed by `"FLOW"`, `"REJECT"`, etc. (Talend connector names) — match works.

However, the `tUniqRow` UNIQUE/DUPLICATE flow types in `_FLOW_TYPE_TO_RESULT_KEY` (output_router.py:22-29) map `"unique" -> "main"` and `"duplicate" -> "reject"`. After `.upper()`, the lookup looks for `"UNIQUE"` and `"DUPLICATE"` in the converter's `outputs` map — but tUniqRow converters typically use only `"OUTPUT"` and `"REJECT"` (or `"UNIQUE"` and `"DUPLICATE"` — varies). This is silently brittle. No test in the reviewed set covers a tUniqRow + schema propagation case.

**Fix:** Document the canonical set of output connector keys and validate them at conversion time, OR fall back through a known alias chain.

---

### WR-03: `_truthy` accepts integer 1/0 but `_normalize_case_sensitive` rejects them — inconsistency

**File:** `src/v1/engine/components/file/file_list.py:558-570` vs `:401-431`

**Issue:** `_truthy` returns `True` for `int(1)` (line 567 `return bool(value)`), so `INCLUDSUBDIR=1` is accepted as recursive. But `_normalize_case_sensitive` explicitly rejects integer 1 ("prevents bool/int collision"). The same Phase 10 component validates two boolean-like config values with two different rules. The unit test `test_integer_one_not_true` proves this divergence is intentional for CASE_SENSITIVE — but not documented for `_truthy`'s callers.

**Fix:** Either centralise to one truthy normaliser used by both, or document why CASE_SENSITIVE is special. As written, behaviour is inconsistent and confusing.

---

### WR-04: `_sort_paths` with `ORDER_BY_NOTHING` + DESC reverses an "unordered" sequence — test acknowledges this is a no-op but code still runs `list(reversed(paths))`

**File:** `src/v1/engine/components/file/file_list.py:507-512`

**Issue:** `list(reversed(paths))` allocates and copies the entire list for parity with no semantic meaning ("DESC reversal is a no-op for unordered sequences, but apply it anyway for consistency"). For 1200+ Talend jobs running this on directories with thousands of files, this is a wasted allocation. More importantly, "preserves OS-default order (non-deterministic)" + applying reverse() is a CONTRADICTION — non-deterministic-then-reversed is still non-deterministic, but now also dishonest about preserving OS order. Talend itself does NOT reverse on ORDER_BY_NOTHING+DESC — this is a Python addition not in scope.

**Fix:** Drop the reverse-on-NOTHING branch entirely. Update doc.

---

### WR-05: `_execute_iterate_body` does not handle `_validate_config` failure raised by `iter_component.execute()` — the call site is missing

**File:** `src/v1/engine/executor.py:250-261`

**Issue:** `_execute_subjob_plan` calls `_execute_component(comp_id)` for the iterate source first. `_execute_component` wraps `component.execute(input_data)` in try/except (line 552-614) and on exception returns `"error"` (line 614). If validation fails, `comp_result == "error"`, and the next branch checks `if comp_result == "success"` before entering iterate-body branch — so the body never runs. Good. BUT: `_execute_iterate_body` is also never called, so `iter_component.executed_components.add(cid)` (line 478) is also never run. The component IS marked executed via line 572 inside `_execute_component`'s success path — but only on success. On error, line 609 still adds to `executed_components`. So far OK.

The actual issue: `_execute_iterate_body` ASSUMES `iter_component.iteration_iter` was set up by a successful `execute()`. There's no guard. If `execute()` raised but the executor still entered the iterate branch (e.g., via a future code path that bypasses `_execute_component`), iterating `iter()` would yield nothing and the entire iterate would silently do zero iterations and report success. Defense-in-depth missing.

**Fix:** Add an assertion inside `_execute_iterate_body`:
```python
assert iter_component.status != ComponentStatus.ERROR, (
    f"[{cid}] Cannot run iterate body on errored component"
)
```

---

### WR-06: `flow_to_iterate.set_iteration_globalmap` raises ConfigurationError mid-iteration — non-recoverable mid-loop

**File:** `src/v1/engine/components/iterate/flow_to_iterate.py:210-214`

**Issue:** When `default_map=False` and `map_entries` references a column not in `item.row`, the method raises `ConfigurationError(...)`. But `_validate_config` explicitly does NOT check this (per Phase 7.1 Rule 12 / "structural-only"). So a user with a missing column gets the failure on the first iteration where the column is checked — but the iterate loop's `except ComponentExecutionError` arm only catches `ComponentExecutionError`, not `ConfigurationError`. The `ConfigurationError` will propagate out of `_execute_iterate_body` entirely, bypassing the `finally` block partially (the `finally` does run for `_current_iterate_depth` decrement, but the iterate-end log, NB_LINE stats, and reject-buffer routing are skipped).

This means: a missing column in map_entries kills the job AND leaves stats in an inconsistent state.

**Fix:** Either move this check into `_validate_config` (it's structural — the entries are config-time, the column comparison is per-row but the entries themselves are static), or treat it as a per-iteration data error and route to reject like other components do.

---

### WR-07: `FileList._compile_mask` recompiles the regex on every file in the directory

**File:** `src/v1/engine/components/file/file_list.py:454-479`

**Issue:** `_match_path` calls `_compile_mask` per-(file, mask) pair. For 1000 files and 5 masks, that's 5000 `re.compile` calls. The compiled patterns are reusable across files — they should be compiled once outside the file loop. This is a performance concern but the project memo says performance is out of v1 scope; flagged here only because for 1200+ jobs hitting a directory with 10000 files, this is observable lag. Demote if perf is truly out of scope.

**Fix:** Move compilation outside the per-file loop:
```python
compiled = [self._compile_mask(m, use_glob, case_sensitive) for m in masks]
raw_paths = [p for p in raw_paths if any(c.fullmatch(p.name) for c in compiled)]
```

---

### WR-08: `_execute_subjob_plan`'s `body_components_executed_by_iterate` set is not propagated to nested calls

**File:** `src/v1/engine/executor.py:222-266`

**Issue:** `body_components_executed_by_iterate` is local to the call. If `_execute_subjob_plan` is invoked recursively (Phase 10 prevents this for iterate, but not for general flows), components already iterated in the body of a parent call would re-execute. This is technically dead code today but a footgun for Phase 10.1 / nested iterate. Should be a thread-through parameter or instance state.

**Fix:** Promote to instance state guarded by stack depth, and clear on `_current_iterate_depth == 0`.

---

### WR-09: `_propagate_input_schemas` mutates `to_schema["input"]` when `inputs` map already covers it (last-write-wins) — undocumented for downstream consumers

**File:** `src/converters/talend_to_v1/converter.py:368-370`

**Issue:** Comment says "Last-write-wins is OK because (a) single-input targets only see one flow, (b) multi-input targets MUST read from inputs[flow_name] going forward." This is reasonable but the engine's `engine.py:131` reads:
```python
component.input_schema = comp_config.get('schema', {}).get('input', [])
```
And `schema_inputs_map` is read at line 138. There's no enforcement that multi-input components actually use `schema_inputs_map` — old code paths still happily read `input_schema`. If a multi-input component reads `input_schema`, it sees only the last flow's schema, silently corrupting validation.

**Fix:** Audit all multi-input engine components (tMap, tJoin, etc.) and either (a) enforce reading from `schema_inputs_map`, or (b) remove `input_schema` for multi-input cases. Phase 10 doesn't introduce this issue but the propagation logic is in scope; existing consumers should be flagged in CR-04 follow-up.

---

## Info

### IN-01: `__init__.py` for iterate components has 9 lines but only one component

**File:** `src/v1/engine/components/iterate/__init__.py`

**Issue:** Boilerplate-heavy; `__all__` lists only `FlowToIterate`. As Phase 10.1 adds more iterate components (tForeach, tLoop), update this file. No defect.

---

### IN-02: `tests/integration/__init__.py` is essentially empty

**File:** `tests/integration/__init__.py`

**Issue:** One-line docstring, no implementation. Harmless. Could remove unless required by pytest discovery.

---

### IN-03: `BaseIterateComponent.update_iteration_stats` is dead code

**File:** `src/v1/engine/base_iterate_component.py:332-344`

**Issue:** `update_iteration_stats` is documented as "Called by the Executor after each iteration completes" but the Executor (line 458-460 of executor.py) directly assigns to `iter_component.stats` keys — it never calls `update_iteration_stats`. The method is only exercised by `test_base_component.py::TestBaseIterateComponentReset::test_reset_clears_base_stats_too` which uses it as a stand-in to populate stats for the reset test.

**Fix:** Either call it from the Executor (preferred — matches docstring) or delete it.

---

### IN-04: Magic number `50` for `DEFAULT_LOG_PER_ITER_THRESHOLD`

**File:** `src/v1/engine/iterate_logging.py:19`

**Issue:** `DEFAULT_LOG_PER_ITER_THRESHOLD: int = 50` — no rationale comment. Why 50 and not 100 or 25? Document the choice or make it tunable per-component.

---

### IN-05: `pyproject.toml` `dataprep[all]` does NOT include the `dev` extra

**File:** `pyproject.toml:23`

**Issue:** `all = ["dataprep[java,excel,xml,yaml,json,api]"]` omits `dev` (pytest). A user running `pip install -e .[all]` then `pytest` will see ImportError. Either add `dev` to `all` or document.

---

_Reviewed: 2026-05-05_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
