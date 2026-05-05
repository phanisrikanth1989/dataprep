---
phase: 10-iterate-support
verified: 2026-05-05T00:00:00Z
status: gaps_found
score: 3/5 must-haves verified
overrides_applied: 0
gaps:
  - truth: "Downstream subjobs re-execute per iteration item with components properly reset between iterations (EXEC-04, EXEC-05, EXEC-06) and the documented iterate API contract holds"
    status: failed
    reason: "CR-02: Executor iterates iter_component.iteration_iter directly via enumerate(), bypassing the documented has_next_iteration()/get_next_iteration_context() public API. current_iteration_index permanently stays 0 after execute() returns. The module docstring at base_iterate_component.py:30-31 states get_next_iteration_context() is the canonical place that writes _CURRENT_ITERATION -- but the executor never calls it. CR-03: The except ComponentExecutionError arm in _execute_iterate_body (executor.py:369-377) is unreachable because _execute_component (lines 580-614) catches ALL exceptions and returns the string 'error', never re-raising. on_iteration_error (Hook 8) therefore never fires through the production code path. CR-04: _any_body_die_on_error reads self.execution_stats which is never cleared between iterations. Stale 'error' status from iteration N can cause spurious die-on-error termination in iteration N+1 when a different body component fails."
    artifacts:
      - path: "src/v1/engine/executor.py"
        issue: "Line 346: direct iteration over iteration_iter bypasses has_next_iteration()/get_next_iteration_context() -- current_iteration_index never advances. Lines 369-377: except ComponentExecutionError arm is dead code because _execute_component (lines 580-614) swallows all exceptions and returns string 'error'. Lines 480-498: _any_body_die_on_error reads execution_stats that are never cleared between iterations, causing stale state."
      - path: "src/v1/engine/base_iterate_component.py"
        issue: "has_next_iteration() and get_next_iteration_context() methods (lines 275-326) are documented as 'used by Executor iterate loop' but are never called by the executor. current_iteration_index remains 0 after all iterations."
    missing:
      - "Either drive the executor loop via has_next_iteration()/get_next_iteration_context() to match the documented contract, OR remove those methods and update docstrings to reflect executor-driven iteration"
      - "Either wire on_iteration_error to actually fire (requires threading the exception out of _execute_component), OR remove Hook 8 and the unreachable except arm"
      - "Clear or scope execution_stats per iteration in _execute_iterate_body, or track iteration-local failures separately to prevent stale die_on_error decisions"

  - truth: "Integration tests can detect fatal conversion errors for tFileList and tFlowToIterate .item samples"
    status: failed
    reason: "CR-01: test_iterate_e2e.py lines 160 and 323 query result.get('needs_review', []) but the converter writes the list under '_needs_review' (with leading underscore, confirmed at converter.py:172). result.get('needs_review', []) always returns [], making fatal=[] always, so the primary E2E acceptance gate can never fail regardless of conversion output. The converter test in test_iterate_connection_extraction.py:29 correctly uses '_needs_review'."
    artifacts:
      - path: "tests/integration/test_iterate_e2e.py"
        issue: "Lines 160 and 323: result.get('needs_review', []) should be result.get('_needs_review', []) -- wrong key means fatal conversion errors are silently ignored"
    missing:
      - "Change 'needs_review' to '_needs_review' at lines 160 and 323 of tests/integration/test_iterate_e2e.py"

  - truth: "tFileList sort by FILESIZE or MODIFIEDDATE handles files deleted between directory walk and sort without crashing"
    status: failed
    reason: "CR-06: _sort_paths in file_list.py (lines 519 and 525) calls p.stat().st_size and p.stat().st_mtime inside a sort key lambda with an explicit p.exists() check, but the check is racy -- a file can be deleted between p.exists() and p.stat(). On Python 3.10+ strict=True, p.resolve() (called during item materialization) also raises FileNotFoundError on broken symlinks. Talend behavior on this race is to skip the file; the current implementation crashes the iterate loop."
    artifacts:
      - path: "src/v1/engine/components/file/file_list.py"
        issue: "Lines 519 and 525: racy p.exists()+p.stat() pattern in sort key lambda. The file can be deleted between exists check and stat call, raising FileNotFoundError and crashing the sort."
    missing:
      - "Wrap p.stat() calls in try/except OSError in the _sort_paths sort key lambda, returning a sort-stable default (e.g., 0 for size, 0.0 for mtime) on error and logging a WARNING"
---

# Phase 10: Iterate Support Verification Report

**Phase Goal:** The 30% of production jobs that use iterate patterns execute correctly -- tFlowToIterate converts rows to globalMap variables, tFileList/tFileExist iterate over files, and downstream subjobs re-execute per iteration item
**Verified:** 2026-05-05T00:00:00Z
**Status:** gaps_found
**Re-verification:** No -- initial verification

## Goal Achievement

### Observable Truths (from ROADMAP.md Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | tFlowToIterate converts each input row to globalMap variables in both DEFAULT_MAP and custom MAP modes, and sets {id}_CURRENT_ITERATE | VERIFIED | flow_to_iterate.py exists, set_iteration_globalmap writes per-row keys in both modes; 27 unit tests pass; ITER-01/02/03/11 covered |
| 2 | tFileList iterates over files matching a filemask with subdirectory inclusion and sort order options, setting all five globalMap variables | VERIFIED | file_list.py exists, set_iteration_globalmap writes all 5 RETURN vars; 63 unit tests pass; ITER-04/05/06/07 covered |
| 3 | tFileExist checks file existence and sets globalMap variables with correct config key handling | VERIFIED | file_exist.py GREEN per Phase 9 audit; integration tests confirm ITER-08/09; both file_name and file_path keys accepted |
| 4 | Downstream subjobs connected via iterate triggers re-execute once per iteration item, with components properly reset between iterations | FAILED | CR-02: executor bypasses has_next_iteration()/get_next_iteration_context() API, leaving current_iteration_index permanently at 0. CR-03: on_iteration_error (Hook 8) unreachable. CR-04: _any_body_die_on_error reads stale execution_stats from prior iterations |
| 5 | Engine unit tests pass for all three iterate components and the iterate execution loop | PARTIAL | 119 component tests pass; 39 executor/plan/router tests pass; but integration tests have a silent acceptance gate failure (CR-01: wrong dict key prevents detecting conversion errors) |

**Score:** 3/5 truths verified (Truth 4 FAILED, Truth 5 PARTIAL due to CR-01 silent test rot)

### Deferred Items

No items qualify for deferral. All three gaps are active defects in Phase 10 code, not future-phase work. Phases 11 and 12 do not address any of these issues.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/v1/engine/base_iterate_component.py` | 9-hook lifecycle, ITER-11 fix, iterator-based items | VERIFIED | 9 hooks present, _CURRENT_ITERATION used, iteration_iter replaces iteration_items, _iterate_depth field, execute() override |
| `src/v1/engine/executor.py` | _execute_iterate_body, _execute_subjob_plan refactor | VERIFIED (with defects) | Both methods exist; iterate loop runs per-item; but API bypass (CR-02) and unreachable hook (CR-03) and stale stats (CR-04) are defects in the implementation |
| `src/v1/engine/execution_plan.py` | _build_iterate_body_plan, _detect_nested_iterate, get_iterate_body_plan | VERIFIED | All 3 methods present; _ITERATE_TYPES constant defined; nested iterate detection works |
| `src/v1/engine/output_router.py` | drain_reject_flows, clear_partial_subjob_flows | VERIFIED | Both methods present and tested |
| `src/v1/engine/components/file/file_list.py` | FileList extending BaseIterateComponent | VERIFIED (with defect) | FileList present; 5 RETURN vars written; sort works but race condition (CR-06) in FILESIZE/MODIFIEDDATE sort keys |
| `src/v1/engine/components/iterate/flow_to_iterate.py` | FlowToIterate extending BaseIterateComponent | VERIFIED | FlowToIterate present; DEFAULT_MAP=true/false both work; pd.NA handling present |
| `src/v1/engine/iterate_logging.py` | ASCII-only logging infrastructure | VERIFIED | log_iterate_start, log_iterate_end present; DEFAULT_LOG_PER_ITER_THRESHOLD=50 |
| `src/v1/engine/components/__init__.py` | imports iterate package | VERIFIED | `from . import iterate` present |
| `src/v1/engine/components/file/__init__.py` | imports FileList | VERIFIED | `from .file_list import FileList` present |
| `src/v1/engine/components/iterate/__init__.py` | imports FlowToIterate | VERIFIED | `from .flow_to_iterate import FlowToIterate` present |
| `tests/v1/engine/test_base_iterate_component.py` | 29+ unit tests | VERIFIED | 29 tests pass |
| `tests/v1/engine/components/file/test_file_list.py` | 63+ unit tests | VERIFIED | 63 tests pass |
| `tests/v1/engine/components/iterate/test_flow_to_iterate.py` | 27+ unit tests | VERIFIED | 27 tests pass |
| `tests/v1/engine/test_executor_iterate.py` | 15+ executor iterate tests | VERIFIED | 15 tests pass |
| `tests/v1/engine/test_execution_plan_iterate.py` | 15+ plan tests | VERIFIED | 15 tests pass |
| `tests/v1/engine/test_output_router_iterate.py` | 9+ output router tests | VERIFIED | 9 tests pass |
| `tests/integration/test_iterate_e2e.py` | E2E integration tests | FAILED | 11 tests pass but 2 conversion-error assertions are silently broken (CR-01 wrong dict key) |
| `tests/integration/test_file_exist_e2e.py` | tFileExist integration tests | VERIFIED | 10 tests pass |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| BaseIterateComponent.execute() | prepare_iterations() | self.iteration_iter = self.prepare_iterations(input_data) | WIRED | base_iterate_component.py:157 |
| BaseIterateComponent.get_next_iteration_context() | GlobalMap.put | writes _CURRENT_ITERATION | WIRED but ORPHANED | Method exists but executor never calls it (CR-02) |
| Executor._execute_subjob_plan | Executor._execute_iterate_body | branch on is_iterate_component=True | WIRED | executor.py:255-261 |
| Executor._execute_iterate_body | OutputRouter.drain_reject_flows | drains per-iteration rejects | WIRED | executor.py:405 |
| FileList.set_iteration_globalmap | GlobalMap.put | writes 5 RETURN vars per file | WIRED | file_list.py:367-371 |
| FlowToIterate.set_iteration_globalmap | GlobalMap.put | writes per-row keys per DEFAULT_MAP mode | WIRED | flow_to_iterate.py lines confirm self.global_map.put calls |
| ExecutionPlan.__init__ | _build_iterate_body_plan | post-build step, _iterate_body_plans dict | WIRED | execution_plan.py:203-210 |
| components/__init__.py | iterate package | from . import iterate | WIRED | confirmed |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| FlowToIterate.set_iteration_globalmap | item.row (from to_dict('records')) | input_data DataFrame from upstream component | Yes -- df.to_dict('records') materializes real rows | FLOWING |
| FileList.set_iteration_globalmap | item (FileListItem from pathlib walk) | directory walk via iterdir/rglob | Yes -- real filesystem paths | FLOWING (with race condition in sort) |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| ITER-10: FileList registered in REGISTRY | python3 -c "from src.v1.engine.component_registry import REGISTRY; from src.v1.engine import components; assert REGISTRY.get('FileList') is not None" | OK | PASS |
| ITER-10: FlowToIterate registered in REGISTRY | python3 -c "...REGISTRY.get('FlowToIterate') is not None" | OK | PASS |
| All component unit tests pass | pytest tests/v1/engine/test_base_iterate_component.py tests/v1/engine/components/iterate/ tests/v1/engine/components/file/test_file_list.py | 119 passed | PASS |
| Executor/plan/router tests pass | pytest tests/v1/engine/test_executor_iterate.py tests/v1/engine/test_execution_plan_iterate.py tests/v1/engine/test_output_router_iterate.py | 39 passed | PASS |
| Integration tests pass | pytest tests/integration/ | 20 passed, 1 skipped | PASS (silent gate failure in conversion assertions -- CR-01) |
| Iterate connection extraction tests pass | pytest tests/converters/talend_to_v1/test_iterate_connection_extraction.py | 16 passed | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| EXEC-04 | 10-02 | Implement iterate execution -- _handle_iterate() per iteration item | VERIFIED | _execute_iterate_body exists and runs per item |
| EXEC-05 | 10-02 | Implement BaseComponent.reset() for state cleanup between iterations | VERIFIED | reset() called in loop at executor.py:432-436 |
| EXEC-06 | 10-02 | Config snapshot/restore for re-executed components | VERIFIED | copy.deepcopy(_original_config) at base_iterate_component.py:157-ish and base_component.py execute() |
| ITER-01 | 10-04 | tFlowToIterate converts each input row | VERIFIED | 27 tests pass; prepare_iterations returns iterator per row |
| ITER-02 | 10-04 | DEFAULT_MAP=true mode -- {flowName}.{col} keys | VERIFIED | set_iteration_globalmap writes {inputs[0]}.{col} |
| ITER-03 | 10-04 | DEFAULT_MAP=false mode -- custom map_entries | VERIFIED | set_iteration_globalmap writes user-defined keys verbatim |
| ITER-04 | 10-03 | tFileList walks directory matching filemask | VERIFIED | prepare_iterations uses iterdir/rglob; 63 tests |
| ITER-05 | 10-03 | tFileList sets 5 globalMap RETURN vars | VERIFIED | all 5 present in set_iteration_globalmap |
| ITER-06 | 10-03 | tFileList INCLUDSUBDIR support | VERIFIED | rglob used when INCLUDSUBDIR=true |
| ITER-07 | 10-03 | tFileList sort order options | VERIFIED | _sort_paths handles ORDER_BY_FILENAME/FILESIZE/MODIFIEDDATE |
| ITER-08 | 10-08 | tFileExist accepts file_name and file_path keys | VERIFIED | file_exist.py:47-48 checks both; integration tests confirm |
| ITER-09 | 10-08 | tFileExist sets {id}_EXISTS and {id}_FILENAME | VERIFIED | file_exist.py:88-89 writes both; integration tests confirm |
| ITER-10 | 10-03, 10-04 | All iterate components registered in COMPONENT_REGISTRY | VERIFIED | Registry confirmed via python3 import check |
| ITER-11 | 10-01 | {id}_CURRENT_ITERATION canonical key (not _CURRENT_ITERATE) | PARTIAL | base_iterate_component.py writes correct key in get_next_iteration_context(); executor.py:355 also writes correct key directly. The base method is orphaned (CR-02) but the key itself IS written correctly by the executor. |
| TEST-04 | 10-07 | Engine unit tests for iterate components | VERIFIED | 119+39+12+16 tests across all iterate test files pass |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| tests/integration/test_iterate_e2e.py | 160 | result.get("needs_review", []) wrong key (should be "_needs_review") | BLOCKER | Conversion error acceptance gate always passes silently |
| tests/integration/test_iterate_e2e.py | 323 | result.get("needs_review", []) wrong key (should be "_needs_review") | BLOCKER | Same |
| src/v1/engine/executor.py | 346 | `for index, item in enumerate(iter_component.iteration_iter, start=1)` bypasses documented public API | BLOCKER | current_iteration_index stays 0; API contract broken |
| src/v1/engine/executor.py | 369-377 | `except ComponentExecutionError` arm after `_execute_subjob_plan` call | BLOCKER | Dead code in production -- _execute_component never re-raises, so on_iteration_error never fires |
| src/v1/engine/executor.py | 480-498 | `_any_body_die_on_error` reads execution_stats without clearing between iterations | BLOCKER | Stale error status from prior iteration can cause spurious early termination |
| src/v1/engine/components/file/file_list.py | 519, 525 | p.exists() + p.stat() racy pattern in sort key lambda | BLOCKER | FileNotFoundError crash on busy directories during FILESIZE/MODIFIEDDATE sort |

### Human Verification Required

None -- all critical issues are programmatically verifiable.

## Gaps Summary

Three gaps block the phase goal:

**Gap 1 (CR-01, 1 file, 2 lines): Silent test rot in integration tests**
tests/integration/test_iterate_e2e.py at lines 160 and 323 query `result.get("needs_review", [])` but the converter writes `"_needs_review"` (leading underscore). The acceptance assertions that should detect fatal conversion errors always see an empty list and always pass. This silently voids the primary E2E smoke test for both tFileList and tFlowToIterate conversion.

**Gap 2 (CR-02 + CR-03 + CR-04, 1 file): Executor iterate loop has three correlated defects**
- CR-02: The executor bypasses the documented has_next_iteration()/get_next_iteration_context() public API, iterating the raw iterator directly. current_iteration_index never advances from 0. The BaseIterateComponent module docstring (lines 30-31) falsely states these methods are "used by Executor iterate loop."
- CR-03: on_iteration_error (Hook 8) is unreachable because _execute_component catches all exceptions and returns the string "error". The except ComponentExecutionError arm in _execute_iterate_body cannot fire through the production call path. Body components that want custom error handling silently get nothing.
- CR-04: _any_body_die_on_error reads execution_stats without scoping to the current iteration. A component that failed in iteration N with die_on_error=False can cause spurious early loop termination in iteration N+1 if a different body fails.

These three defects are correlated -- all stem from the Executor's iterate loop implementation not matching the designed contract.

**Gap 3 (CR-06, 1 file): FileList sort race condition**
_sort_paths calls p.stat() inside a sort key lambda after a p.exists() check. On busy directories a file deleted between exists() and stat() raises FileNotFoundError, crashing the iterate loop. Talend behavior is to skip deleted files. The fix is to wrap stat() in try/except OSError.

---

_Verified: 2026-05-05T00:00:00Z_
_Verifier: Claude (gsd-verifier)_
