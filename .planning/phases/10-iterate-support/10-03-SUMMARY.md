---
phase: 10-iterate-support
plan: "03"
subsystem: engine
tags: [engine, file, iterate, tFileList, pathlib, glob, regex, sort, globalmap]

# Dependency graph
requires:
  - phase: 10-01
    provides: BaseIterateComponent with 9-hook lifecycle, prepare_iterations(), set_iteration_globalmap() abstracts
  - phase: 10-02
    provides: Executor._execute_iterate_body() loop infrastructure

provides:
  - FileList engine component extending BaseIterateComponent (src/v1/engine/components/file/file_list.py)
  - FileListItem typed dataclass (path, name, parent, ext, index fields)
  - Registration via @REGISTRY.register("FileList", "tFileList")
  - 63 unit tests covering ITER-04, ITER-05, ITER-06, ITER-07, ITER-10 requirements

affects:
  - 10-07 (integration tests will use FileList end-to-end with tFileInputDelimited + tMap + tFileOutputDelimited)
  - 10-08 (tFileExist verify plan is separate; no interaction)
  - Engine executor (is_iterate_component=True flag already consumed by 10-02 executor)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "FileList extends BaseIterateComponent: implements prepare_iterations() + set_iteration_globalmap() + finalize()"
    - "fnmatch.translate -> re.compile for glob mode; re.compile(pattern) for regex mode; both use re.fullmatch for Java Pattern.matcher().matches() parity"
    - "_normalize_case_sensitive uses explicit isinstance(bool) guard before string check (prevents True==1 int collision)"
    - "FORMAT_FILEPATH_TO_SLASH applied in prepare_iterations before yielding FileListItem (not in globalMap setter)"
    - "D-G8 0-match: ComponentExecutionError message 'No file found in directory: <dir>' matches Talend RuntimeException"
    - "D-G9 bool/int collision: _CASE_SENSITIVE_TRUE/FALSE_STRINGS frozensets contain only strings; isinstance(bool) checked first"

key-files:
  created:
    - src/v1/engine/components/file/file_list.py
    - tests/v1/engine/components/file/test_file_list.py
  modified:
    - src/v1/engine/components/file/__init__.py

key-decisions:
  - "CURRENT_FILEEXTENSION uses path.suffix.lstrip('.') -- 'report.java' -> 'java' (no dot), matching Java lastIndexOf convention (Phase 10 research / Assumption A2)"
  - "FORMAT_FILEPATH_TO_SLASH applied in prepare_iterations() when building FileListItem, not in set_iteration_globalmap() -- single transformation point"
  - "0-match with missing directory treated as empty walk (not FileOperationError) -- ERROR=true produces ComponentExecutionError via the 0-match path regardless of cause"
  - "_normalize_case_sensitive is a @staticmethod taking component_id as first arg (not self) to enable use from _validate_config"
  - "_truthy() module-level helper normalises bool-like config values for INCLUDSUBDIR, GLOBEXPRESSIONS, ERROR, IFEXCLUDE, FORMAT_FILEPATH_TO_SLASH"

patterns-established:
  - "FileListItem dataclass pattern (D-A4): typed iteration items with all fields pre-computed before yielding"
  - "Iterate component stats via finalize(): NB_LINE = NB_LINE_OK = NB_FILE = total_iterations; NB_LINE_REJECT = 0"
  - "Test helper sets comp.config = dict(cfg) after construction (BaseComponent leaves config={} until execute())"

requirements-completed: [ITER-04, ITER-05, ITER-06, ITER-07, ITER-10]

# Metrics
duration: 6min
completed: 2026-05-05
---

# Phase 10 Plan 03: FileList Engine Component Summary

**tFileList engine component with 16 _java.xml params, 5 globalMap RETURN vars, glob/regex matching, 4 sort variants, ERROR=true/false parity -- 63 unit tests all passing**

## Performance

- **Duration:** 6 min
- **Started:** 2026-05-05T18:21:24Z
- **Completed:** 2026-05-05T18:27:00Z
- **Tasks:** 2 of 2
- **Files modified:** 3

## Accomplishments

- FileList component (tFileList engine) with full Talend production parity: 16 config keys, 5 RETURN globalMap variables, INCLUDSUBDIR recursive walk, glob vs regex modes, case-sensitivity, OR-wise multi-mask, EXCLUDEFILEMASK, 4 ORDER_BY variants + ASC/DESC, ERROR=true/false 0-match, FORMAT_FILEPATH_TO_SLASH
- Registered under both "FileList" and "tFileList" aliases via @REGISTRY.register -- satisfies ITER-10
- 63 unit tests across 14 classes: ITER-04 (walk), ITER-05 (5 globalMap vars), ITER-06 (INCLUDSUBDIR), ITER-07 (sort), ITER-10 (registration), ERROR=true/false, FORMAT_FILEPATH_TO_SLASH, CASE_SENSITIVE normalization, bool/int collision guard

## Task Commits

1. **Task 1: Implement FileList engine component** - `14d88bd` (feat)
2. **Task 2: Unit tests for FileList** - `ae36f21` (test)
3. **Plan metadata (SUMMARY)** - `[pending]` (docs)

## Files Created/Modified

- `src/v1/engine/components/file/file_list.py` -- FileList extends BaseIterateComponent; FileListItem dataclass; _validate_config, prepare_iterations, set_iteration_globalmap, finalize; static helpers _normalize_case_sensitive, _compile_mask, _match_path, _sort_paths, _apply_format_filepath_to_slash
- `src/v1/engine/components/file/__init__.py` -- Added `from .file_list import FileList` import and 'FileList' to __all__
- `tests/v1/engine/components/file/test_file_list.py` -- 63 tests across 14 test classes

## Decisions Made

- `CURRENT_FILEEXTENSION` via `path.suffix.lstrip('.')`: "report.java" -> "java", matching Java `lastIndexOf` convention
- Missing directory with ERROR=false treated as 0-match (log WARNING, empty iterator), not FileOperationError; ComponentExecutionError only on ERROR=true
- `_normalize_case_sensitive` uses `isinstance(bool)` first to prevent `True == 1` frozenset collision when checking string membership
- `FORMAT_FILEPATH_TO_SLASH` applied during `prepare_iterations()` when constructing FileListItem, so `set_iteration_globalmap` writes already-normalised values directly

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] ContextManager constructor call in tests used wrong kwarg**
- **Found during:** Task 2 (unit test execution)
- **Issue:** Test helper used `ContextManager(context_dict={})` but actual signature is `ContextManager(initial_context=None, ...)`
- **Fix:** Changed to `ContextManager()` (no-arg call, same effect)
- **Files modified:** tests/v1/engine/components/file/test_file_list.py
- **Verification:** All 63 tests pass after fix
- **Committed in:** ae36f21 (Task 2 commit)

**2. [Rule 1 - Bug] Test for invalid LIST_MODE had missing DIRECTORY key**
- **Found during:** Task 2 (unit test execution)
- **Issue:** `test_invalid_list_mode_raises` config lacked `DIRECTORY`, so ConfigurationError raised for wrong reason
- **Fix:** Added `"DIRECTORY": "/tmp/testdir"` to test config
- **Files modified:** tests/v1/engine/components/file/test_file_list.py
- **Verification:** Test correctly catches LIST_MODE ConfigurationError
- **Committed in:** ae36f21 (Task 2 commit)

**3. [Rule 2 - Missing Critical] Test helper sets comp.config after construction**
- **Found during:** Task 2 (unit test execution)
- **Issue:** BaseComponent leaves `self.config = {}` until `execute()` is called; direct calls to `_validate_config()` and `prepare_iterations()` in tests saw empty config
- **Fix:** Added `comp.config = dict(cfg)` in `_make_file_list()` helper, matching the pattern in `test_file_exist.py`
- **Files modified:** tests/v1/engine/components/file/test_file_list.py
- **Verification:** All validate_config and prepare_iterations tests now see correct config
- **Committed in:** ae36f21 (Task 2 commit)

---

**Total deviations:** 3 auto-fixed (2 Rule 1 bug, 1 Rule 2 missing critical)
**Impact on plan:** All auto-fixes in test code only; implementation code executed as planned. No scope creep.

## Issues Encountered

None - all implementation issues were minor test scaffolding errors resolved inline.

## Known Stubs

None. All 16 config params and 5 RETURN vars are fully wired.

## Threat Surface Scan

No new network endpoints or trust boundary surfaces introduced. FileList reads user-configured DIRECTORY from trusted JSON job config (converted from Talend .item). Threat model from plan (T-10-01 path traversal, T-10-02 glob DoS, T-10-03 directory enumeration) remains at LOW severity per plan analysis. No new surface found beyond what plan documented.

## Self-Check: PASSED

- src/v1/engine/components/file/file_list.py: FOUND
- src/v1/engine/components/file/__init__.py: FOUND (with FileList import)
- tests/v1/engine/components/file/test_file_list.py: FOUND
- .planning/phases/10-iterate-support/10-03-SUMMARY.md: FOUND
- Commit 14d88bd (feat): FOUND
- Commit ae36f21 (test): FOUND
- pytest tests/v1/engine/components/file/test_file_list.py: 63 passed

## Next Phase Readiness

- FileList is ready to be exercised by the 10-07 integration test plan (tFileList -> tFileInputDelimited -> tMap -> tFileOutputDelimited)
- Registered under both aliases -- Executor._execute_iterate_body() (10-02) will correctly branch on is_iterate_component=True
- finalize() sets all stats fields needed for post-loop trigger evaluation

---
*Phase: 10-iterate-support*
*Completed: 2026-05-05*
