---
phase: 08
plan: 01
subsystem: engine/components/transform
tags: [code-components, mixin, tjava, base-component, rule-11, rule-12]
requires:
  - .planning/phases/07.1-manager-audit-and-basecomponent-fixes/07.1-03-SUMMARY.md
  - .planning/phases/07.2-validate-config-bug-sweep-move-pre-resolution-content-checks/07.2-LEARNINGS.md
provides:
  - CodeComponentMixin (D-09 / PYCO-03)
  - module-level safe-namespace constants (_SAFE_BUILTIN_NAMES, _SAFE_NAMESPACE_GLOBALS, _build_safe_builtins) per D-11 / revision-1 Warning 7
  - JavaComponent rewritten to BaseComponent + Rule 11/12 contract (JAVA-01, JAVA-02, JAVA-03)
affects:
  - downstream Wave 2 plans (08-02 PythonComponent, 08-03 JavaRowComponent, 08-04 PythonRowComponent) inherit from CodeComponentMixin
tech-stack:
  added: []
  patterns:
    - "@REGISTRY.register decorator on JavaComponent (Rule 9) replacing legacy missing-decorator state"
    - "Mixin-first MRO: class X(CodeComponentMixin, BaseComponent) per D-09"
    - "Rule 12 minimal _validate_config (presence + container shape only) per Phase 7.2"
    - "ASCII-only logging at DEBUG level for code body (RESEARCH.md threat policy T-08-03)"
key-files:
  created:
    - src/v1/engine/components/transform/_code_component_mixin.py
    - tests/v1/engine/components/transform/test_code_component_mixin.py
    - tests/v1/engine/components/transform/test_java_component.py
  modified:
    - src/v1/engine/components/transform/java_component.py
    - src/v1/engine/components/transform/__init__.py
decisions:
  - "Module-level whitelist constants (D-11 / revision-1 Warning 7) -- not class attributes -- because they have no self-dependency and Java components do not need them; Python plans 02 and 04 will import them"
  - "Mixin has only _get_context_dict (Test 5 scope-creep guard) -- additional helpers will surface in Wave 2 if needed"
  - "Passthrough semantics for one-shot (D-29 revision 2): result['main'] returns input_data unchanged when provided, None when not -- documented as DataPrep data-flow equivalent of Talend tJava begin-block, NOT a Talend feature"
  - "ExpressionError used to wrap bridge raises in _process per PATTERNS.md S6; ComponentExecutionError reserved for missing-bridge gate per AP-9 fix"
metrics:
  duration: ~25min
  completed: 2026-04-29
---

# Phase 8 Plan 01: CodeComponentMixin + JavaComponent rewrite Summary

**One-liner:** Established the shared `CodeComponentMixin` (with module-level safe-namespace constants for D-11) and rewrote `java_component.py` cleanly to the post-7.1 `BaseComponent` + Rule 11/12 contract with `@REGISTRY.register("JavaComponent", "tJava")`, D-07 imports prepend, D-20 bridge-managed sync, and D-29 passthrough.

## Tasks Completed

| Task | Name | Commit | Files |
| ---- | ---- | ------ | ----- |
| 1 | Create `CodeComponentMixin` (D-09 / PYCO-03 / D-11 Warning 7) | 530a5cf | `src/v1/engine/components/transform/_code_component_mixin.py`, `tests/v1/engine/components/transform/test_code_component_mixin.py` |
| 2 | Rewrite `java_component.py` (JAVA-01, JAVA-02, JAVA-03) | 94c52bb | `src/v1/engine/components/transform/java_component.py`, `src/v1/engine/components/transform/__init__.py`, `tests/v1/engine/components/transform/test_java_component.py` |

## Test Results

- **`test_code_component_mixin.py`:** 16 cases (9 logical tests; Test 9 parametrizes 7 dangerous-name cases) -- all pass.
- **`test_java_component.py` unit subset (`-m "not java"`):** 12 cases -- all pass.
- **`test_java_component.py` java integration (`-m java`):** 2 cases defined; gated to Plan 05 (real-bridge fixture not yet wired).
- **Full transform regression sweep (`tests/v1/engine/components/transform/ -m "not java"`):** 444 passed, 2 deselected (the java-marker tests just added), 0 regressions.

## Done Criteria (per plan `<done>` blocks)

### Task 1
- [x] `_code_component_mixin.py` exists, 147 lines (>= 60).
- [x] `class CodeComponentMixin` count = 1.
- [x] `def _get_context_dict` count = 1.
- [x] `_SAFE_BUILTIN_NAMES` declared (4 grep hits incl. usage).
- [x] `_SAFE_NAMESPACE_GLOBALS` declared (2 grep hits).
- [x] `def _build_safe_builtins` count = 1.
- [x] 9 tests pass (16 cases incl. parametrize).

### Task 2
- [x] `@REGISTRY.register` count >= 1 (= 1) -- AP-12 fix.
- [x] `grep -E "raise ValueError|raise RuntimeError"` no match -- AP-1 fix.
- [x] `grep -c "self._update_stats"` = 0 -- AP-3 fix.
- [x] `grep -c "_sync_from_java"` = 0 -- AP-8 fix.
- [x] `grep -c "def _get_context_dict"` in java_component.py = 0 -- inherited from mixin (PYCO-03).
- [x] `grep -c "class JavaComponent(CodeComponentMixin, BaseComponent)"` = 1 -- D-09 mixin-first.
- [x] `self.java_bridge.execute_one_time_expression` call present (D-19 / D-20).
- [x] All non-java unit tests pass.
- [x] Java integration tests defined and properly marked (deferred to Plan 05).

## Truths Verified

- [x] JavaComponent extends `CodeComponentMixin + BaseComponent` and is registered under both `"JavaComponent"` and `"tJava"` via `@REGISTRY.register` (catches AP-1, AP-12). Verified via TestRegistration tests.
- [x] Submitting a tJava job config with `imports + java_code` causes the prepended block to be sent to the bridge via `execute_one_time_expression` (D-07/D-08, JAVA-01). Verified via TestImportsPrepend tests; real-bridge end-to-end gated to Plan 05 Test 13.
- [x] Bidirectional context/globalMap sync round-trip is wired through `JavaBridge._call_java_with_sync` (D-19 / D-20) -- the component does not duplicate the sync loops. Real-bridge round-trip verified by Test 12 once Plan 05 fixture lands.
- [x] `_get_context_dict` lives only in `CodeComponentMixin` (PYCO-03); the rewritten `java_component.py` carries zero copies (`grep -c` = 0). Wave 2 plans 02 / 04 will eliminate the remaining duplicates in `python_component.py` and `python_row_component.py`.
- [x] Python namespace whitelist constants (`_SAFE_BUILTIN_NAMES`, `_SAFE_NAMESPACE_GLOBALS`, `_build_safe_builtins`) live ONLY in `_code_component_mixin.py`. Wave 2 plans 02 / 04 will import them rather than redefining (revision-1 Warning 7).
- [x] `java_component.py` contains zero `raise ValueError`, zero `raise RuntimeError`, zero manual `self._update_stats(...)`, zero manual `_sync_from_java()` references (catches AP-1, AP-3, AP-8). Verified via final grep gate sweep.

## Artifact Verification

- `src/v1/engine/components/transform/_code_component_mixin.py`: 147 lines (>= 60 min); contains class + method + module-level constants/builder per the artifact contract.
- `src/v1/engine/components/transform/java_component.py`: 181 lines (replaces 109-line legacy partial); contains `@REGISTRY.register` + Rule 11/12 contract + imports prepend + no manual stats/sync.
- `src/v1/engine/components/transform/__init__.py`: contains both `from .java_component import JavaComponent` (already present) and the newly-added `from ._code_component_mixin import CodeComponentMixin  # noqa: F401` line.

## Key Links Verified

- `src/v1/engine/components/transform/java_component.py` -> `src/v1/java_bridge/bridge.py::execute_one_time_expression` via `self.java_bridge.execute_one_time_expression(java_code)` -- pattern present (1 hit).
- `src/v1/engine/components/transform/java_component.py` -> `src/v1/engine/components/transform/_code_component_mixin.py::CodeComponentMixin` via `class JavaComponent(CodeComponentMixin, BaseComponent)` -- pattern present (1 hit).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Test assertion case-mismatch on bridge-missing error message**
- **Found during:** Task 2, first test run after writing test file.
- **Issue:** Test 8 (`test_no_java_bridge_raises_component_execution_error`) asserted `"no Java bridge" in str(ei.value).lower()` -- mixed-case substring against a lowercased haystack always fails.
- **Fix:** Lowercased the substring literal to `"no java bridge"`.
- **Files modified:** `tests/v1/engine/components/transform/test_java_component.py`.
- **Commit:** Folded into 94c52bb (Task 2 commit -- single hunk fix before commit).

**2. [Rule 2 - Critical functionality] Docstring rewording to satisfy negative grep gates**
- **Found during:** Task 2, post-write grep gate sweep.
- **Issue:** Initial docstring text in `java_component.py` mentioned the bare-string anti-pattern names (`raise ValueError`, `self._update_stats(...)`, `_sync_from_java`) as part of the documented "anti-patterns avoided" list. The plan's `<done>` grep gates require these literal strings to have ZERO occurrences in the file -- including in comments / docstrings -- so that future audits (and Phase 8's grep-based negative checks) reliably catch reintroductions.
- **Fix:** Reworded the documentation to refer to the patterns descriptively without the literal names (e.g. "the sync machinery directly", "stats helper directly", "built-in generic exceptions"). Documentation intent preserved; gates now pass.
- **Files modified:** `src/v1/engine/components/transform/java_component.py`.
- **Commit:** Folded into 94c52bb (Task 2 commit -- pre-commit cleanup).

**3. [Rule 1 - Bug] Lifted `comp.config = dict(config)` populate into `_make_component`**
- **Found during:** Task 2, fixture authoring per Phase 7.2 D-22.
- **Issue:** `BaseComponent.__init__` only sets `_original_config`; `comp.config` is empty until `execute()` Step 1 runs. Direct calls to `_validate_config` / `_process` from unit tests would see `self.config == {}` and fail spuriously.
- **Fix:** Followed the Phase 7.2 D-22 fixture pattern -- helper now does both `JavaComponent(...)` and `comp.config = dict(config)`. Tests can call `_validate_config` / `_process` directly without going through `execute()`.
- **Files modified:** `tests/v1/engine/components/transform/test_java_component.py`.
- **Commit:** Authored correctly from the start; documenting here for traceability with the Phase 7.2 carry-forward pattern.

No architectural deviations (Rule 4) -- the plan was followed verbatim. No CLAUDE.md-driven adjustments beyond the ASCII-only logging policy already enforced by the plan / project memory.

## Threat Surface Scan

No new threat surface introduced beyond what the plan already enumerated in `<threat_model>` (T-08-01..04). No new endpoints, no schema changes, no auth paths. The rewritten `java_component.py` consumes the existing JavaBridge surface unchanged. T-08-03 (information disclosure via logs) actively mitigated -- the new code logs the java_code SIZE only, never the body, and only at DEBUG level.

## Self-Check: PASSED

- File `src/v1/engine/components/transform/_code_component_mixin.py` -- FOUND.
- File `tests/v1/engine/components/transform/test_code_component_mixin.py` -- FOUND.
- File `src/v1/engine/components/transform/java_component.py` -- FOUND (rewritten).
- File `tests/v1/engine/components/transform/test_java_component.py` -- FOUND.
- File `src/v1/engine/components/transform/__init__.py` -- FOUND (modified).
- Commit 530a5cf -- FOUND in `git log`.
- Commit 94c52bb -- FOUND in `git log`.
