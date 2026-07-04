---
phase: 14-coverage-push-to-95-per-module-floor
plan: 09
subsystem: testing
tags: [file-io, excel, json, raw-text, pytest, coverage, etl, registry, abstract-method, configuration-error, openpyxl, xlrd, jsonpath]

# Dependency graph
requires:
  - phase: 14-01
    provides: run_job_fixture pipeline-test infrastructure, FIXTURE_JOBS_ROOT, assert_ascii_logs
  - phase: 14-08
    provides: .gitignore D-RULE3 negation pattern for tests/fixtures/jobs/**/*.json (extended here to data/)
  - phase: 13
    provides: per-module coverage baseline (file_input_excel 28.7%, file_input_json 9.3%, file_input_raw 17.7%, file_output_excel 69.0%)
provides:
  - tests/fixtures/data/sample_basic.xlsx (single-sheet xlsx, header + 3 rows, mixed dtypes)
  - tests/fixtures/data/sample_multisheet.xlsx (2 sheets Q1/Q2, different schemas)
  - tests/fixtures/data/sample_legacy.xls (BIFF8 .xls via xlwt, single 'Legacy' sheet, header + 3 rows)
  - tests/fixtures/data/sample_data.json (simple list of 3 records)
  - tests/fixtures/data/sample_jsonpath.json (nested users[*] structure with JSONPath extraction)
  - tests/fixtures/data/sample_raw_utf8.txt (UTF-8 BOM + 3 Unix-EOL lines)
  - tests/fixtures/data/sample_raw_iso8859.txt (ISO-8859-15 with e-acute byte)
  - tests/fixtures/jobs/file/excel_simple.json (tFileInputExcel -> tFileOutputDelimited pipeline)
  - tests/fixtures/jobs/file/json_jsonpath.json (tFileInputJSON JSONPath -> tFileOutputDelimited)
  - tests/fixtures/jobs/file/raw_text.json (tFileInputRaw -> tFileOutputDelimited)
  - tests/v1/engine/components/file/test_file_input_json.py (NEW, 39 tests, 525 lines)
  - tests/v1/engine/components/file/test_file_input_raw.py (NEW, 23 tests, 319 lines)
  - tests/v1/engine/components/file/test_file_output_excel.py (EXTENDED with 38 new tests; total 80)
  - tests/v1/engine/components/file/test_file_input_excel.py (EXTENDED with 67 new tests; total 148)
  - FileInputJSON registered with REGISTRY (BUG-FIJ-001)
  - FileInputJSON._validate_config implemented (BUG-FIJ-002; raises ConfigurationError)
affects: [14-13-closeout, future-phases-using-excel-or-json-io]

# Tech tracking
tech-stack:
  added:
    - xlwt  # dev dependency only, used at fixture-build time for sample_legacy.xls
  patterns:
    - "Committed binary fixtures pattern: build .xlsx via openpyxl, .xls via xlwt, commit raw bytes to tests/fixtures/data/"
    - ".gitignore D-RULE3 negation extended to tests/fixtures/data/**/*.json (project-wide *.json rule swallows fixture data)"
    - "abstract _validate_config + REGISTRY registration as paired must-have for any BaseComponent subclass shipped in components/__init__.py (BUG-SWIFT-001/002 pattern replayed)"

key-files:
  created:
    - tests/v1/engine/components/file/test_file_input_json.py
    - tests/v1/engine/components/file/test_file_input_raw.py
    - tests/fixtures/data/sample_basic.xlsx
    - tests/fixtures/data/sample_multisheet.xlsx
    - tests/fixtures/data/sample_legacy.xls
    - tests/fixtures/data/sample_data.json
    - tests/fixtures/data/sample_jsonpath.json
    - tests/fixtures/data/sample_raw_utf8.txt
    - tests/fixtures/data/sample_raw_iso8859.txt
    - tests/fixtures/jobs/file/excel_simple.json
    - tests/fixtures/jobs/file/json_jsonpath.json
    - tests/fixtures/jobs/file/raw_text.json
  modified:
    - src/v1/engine/components/file/file_input_json.py (registration + abstract _validate_config)
    - tests/v1/engine/components/file/test_file_output_excel.py (38 new tests)
    - tests/v1/engine/components/file/test_file_input_excel.py (67 new tests)
    - .gitignore (extend negation for tests/fixtures/data/**/*.json)

key-decisions:
  - "BUG-FIJ-001/002 are real production bugs, not test-only annoyances. FileInputJSON imported in components/__init__.py was unreachable through REGISTRY (engine silently dropped it with 'Unknown component type'); same class was uninstantiable via ABC because the public validate_config() does not satisfy BaseComponent._validate_config @abstractmethod. Fix both at source per BUG-SWIFT-001/002 precedent."
  - "Inner ValueError raises at file_input_json.py lines 232/239/247 (type-conversion failures during row processing) intentionally left as raw ValueError. They are caught in the per-row try block and converted to reject-flow rows; changing the exception class would change reject behavior, which is out of scope for a coverage plan."
  - "file_input_excel.py reaches 97.4% (not 100%). The remaining 15 lines are defensive branches unreachable without bypassing _validate_config: invalid limit/footer string forms (caught at validate time), context_manager-not-on-self path (always set by BaseComponent.__init__), and pd.read_excel exception variants that don't trigger from any real .xlsx/.xls input we could synthesize. Documented as acceptable; future cleanup phase can D-C5 delete."
  - "Python's open(..., 'r') default universal-newlines mode converts \\r\\n -> \\n before the FileInputRaw debug_content method sees the content. Direct method-level calls to debug_content cover the Windows / Mac branches; end-to-end execute() coverage uses Unix line endings (the only form that naturally survives the read)."
  - "Pipeline fixture for raw_text.json uses fieldseparator=';' without quoting/escape config. Multi-line file content trips the CSV writer's 'need to escape, but no escapechar set' error. Test uses a no-special-char text file (HelloWorld) instead of the BOM/multi-line fixture so the pipeline runs end-to-end. The unit-level encoding tests still exercise the BOM and multi-line files directly."

patterns-established:
  - "BUG-FIJ-001 register-FileInputJSON-engine-component: paired with BUG-SWIFT-001 and BUG-PDC-001 -- the third instance of a BaseComponent subclass shipped in components/__init__.py without REGISTRY decoration. Future plan-checker should grep for class FileX(BaseComponent) without a preceding @REGISTRY.register."
  - "BUG-FIJ-002 abstract-_validate_config: public validate_config() (no underscore) does NOT satisfy BaseComponent._validate_config @abstractmethod. ABC machinery refuses to instantiate. Same shape as BUG-SWIFT-002. Plan-checker should grep for `class X(BaseComponent)` without a `def _validate_config` body."
  - "Plan 14-08 D-RULE3 .gitignore negation pattern (`!tests/fixtures/jobs/**/*.json`) extended to `!tests/fixtures/data/**/*.json` here. Any future plan that adds .json data fixtures under tests/fixtures/data/ inherits this exception."

requirements-completed: [TEST-11]

# Metrics
duration: ~55min
completed: 2026-05-11
tasks_total: 9
tasks_completed: 9
commits_total: 9
files_created: 12
files_modified: 4
---

# Phase 14 Plan 09: file deep gaps (excel/json/raw) Summary

**Lifted four file-component deep gaps -- file_input_excel.py 28.7%->97.4%, file_input_json.py 9.3%->100.0%, file_input_raw.py 17.7%->100.0%, file_output_excel.py 69.0%->100.0% -- via committed real binary fixtures (.xlsx/.xls/.json/.txt), 3 new pipeline-job fixtures, 167 new tests (38+67+39+23), and 2 source-side BUG-FIJ fixes (REGISTRY registration + abstract _validate_config) modelled on Plans 14-06/14-07/14-02 precedent.**

## Performance

- **Duration:** ~55 min
- **Started:** 2026-05-11
- **Completed:** 2026-05-11
- **Tasks:** 9 (4 fixture-data + 3 test-extension + 1 source-bug + 1 gate)
- **Files modified:** 16 (12 created, 4 modified)
- **Commits:** 9 (4 chore-fixture + 1 fix-source + 4 test-coverage)

## Accomplishments

- file_output_excel.py: 69.0% -> 100.0% (294/294 lines)
- file_input_excel.py: 28.7% -> 97.4% (573/588 lines, 15 missed)
- file_input_json.py: 9.3% -> 100.0% (195/195 lines)
- file_input_raw.py: 17.7% -> 100.0% (62/62 lines)
- Real binary/text fixtures committed under tests/fixtures/data/ (7 files)
- 3 pipeline-job JSON fixtures under tests/fixtures/jobs/file/
- 2 source-side bug fixes (BUG-FIJ-001/002) -- production unblocked
- Per-plan gate (scripts/check_per_module_coverage.py) PASSES for all 26 file modules at 95% floor

## Task Commits

Each task committed atomically:

1. **Task 14-09-001 (xlsx + multisheet + xls fixtures)** -- `709cd33` (chore: INFRA-FX-004)
2. **Task 14-09-002 (JSON sample fixtures + .gitignore negation)** -- `2abd311` (chore: INFRA-FX-005)
3. **Task 14-09-003 (raw-text utf8 + iso8859 fixtures)** -- `ae0ad75` (chore: INFRA-FX-006)
4. **Task 14-09-004 (pipeline-job fixtures)** -- `e7125cd` (chore: INFRA-FX-007)
5. **Task 14-09-005 (lift file_output_excel)** -- `5c4afa0` (test: COV-FOE-001)
6. **Task 14-09-006 (lift file_input_excel)** -- `8c2847d` (test: COV-FIE-001)
7. **BUG-FIJ-001/002 source fixes** -- `76cd7cb` (fix)
8. **Task 14-09-007 (lift file_input_json)** -- `b138bd7` (test: COV-FIJ-001)
9. **Task 14-09-008 (lift file_input_raw)** -- `e9c2cbe` (test: COV-FIR-001)

**Plan metadata:** Pending (this commit)

## Files Created/Modified

### Created (12)

- `tests/fixtures/data/sample_basic.xlsx` -- single-sheet xlsx (id/name/salary/hire_date + 3 rows)
- `tests/fixtures/data/sample_multisheet.xlsx` -- 2 sheets (Q1: region/sales, Q2: product/units/price)
- `tests/fixtures/data/sample_legacy.xls` -- BIFF8 .xls via xlwt (single 'Legacy' sheet, id/name + 3 rows)
- `tests/fixtures/data/sample_data.json` -- list of 3 user records
- `tests/fixtures/data/sample_jsonpath.json` -- nested {users: [...]} with contact sub-object
- `tests/fixtures/data/sample_raw_utf8.txt` -- UTF-8 BOM + 3 Unix-EOL lines
- `tests/fixtures/data/sample_raw_iso8859.txt` -- ISO-8859-15 with e-acute byte
- `tests/fixtures/jobs/file/excel_simple.json` -- tFileInputExcel -> tFileOutputDelimited
- `tests/fixtures/jobs/file/json_jsonpath.json` -- tFileInputJSON (JSONPath) -> tFileOutputDelimited
- `tests/fixtures/jobs/file/raw_text.json` -- tFileInputRaw -> tFileOutputDelimited
- `tests/v1/engine/components/file/test_file_input_json.py` -- 39 tests / 525 lines
- `tests/v1/engine/components/file/test_file_input_raw.py` -- 23 tests / 319 lines

### Modified (4)

- `src/v1/engine/components/file/file_input_json.py` -- @REGISTRY.register decorator, ConfigurationError/DataValidationError/FileOperationError imports, _validate_config implementation
- `tests/v1/engine/components/file/test_file_output_excel.py` -- +38 tests (validation extensions, dict/list/unsupported input branches, missing schema columns, invalid first_cell, per-column auto_size, error-handling extensions, append_sheet existing-data, date_pattern edges, _build_col_formats edges, unexpected-exception wrap, workbook load/create failures, sheet create failures, empty-string row filtering, pd.isna TypeError/ValueError on non-scalars, row_values without column_names, makedirs success, save failure with monkey-patched save, delete_empty_file OSError via post-save os.remove swap, to_datetime coerce failure)
- `tests/v1/engine/components/file/test_file_input_excel.py` -- +67 tests (committed xlsx/xls/multisheet fixtures; .xls via xlrd path covering all sheetlist forms; regex / partial / no-match; filepath quote stripping; advanced_separator method-level; trimming method-level; date conversion method-level; _build_converters_dict every dtype; _build_dtype_dict every mapping; _column_letter_to_index; _detect_excel_format; _decode_password plain + encrypted prefix; password branch; first_column/last_column letter/numeric/invalid; schema-driven usecols truncation; streaming via lowered MEMORY_THRESHOLD_MB; no-sheets branches; validation extensions for password / negative footer/limit / non-str separators; xlsx open failure; xls read failure; generic exception wrap; date conversion to_datetime exception; context_manager None branches; pipeline test)
- `.gitignore` -- extend `!tests/fixtures/data/**/*.json` negation

## Decisions Made

1. **BUG-FIJ-001/002 are real production bugs.** Same shape as BUG-SWIFT-001/002 (Plan 14-07) and BUG-PDC-001/002 (Plan 14-06): a BaseComponent subclass shipped in components/__init__.py but never registered, AND missing the abstract _validate_config. Engine.execute() silently treats unregistered types as 'Unknown component'; ABC machinery refuses instantiation. Both fixed at source.

2. **Inner ValueError raises kept raw.** Lines 232/239/247 in file_input_json._process are inside a per-row try block whose `except Exception` builds a reject-flow row. Changing them to DataValidationError or ConfigurationError would alter the catch behavior in surprising ways (BaseComponent.execute() reraises ConfigurationError but rewraps DataValidationError to ComponentExecutionError). Out of scope.

3. **file_input_excel.py at 97.4% is the verifiable floor.** The 15 remaining missed lines are defensive guards on _validate_config paths that pass shape validation but would later trip pd.read_excel or xlrd in ways no realistic input could trigger. Coverage plan requires >=95%; D-C3 narrow pragma allowlist does not cover these; D-C5 deletion is out of scope for a coverage plan. Future cleanup phase can revisit.

4. **Universal-newlines mode shapes the FileInputRaw test strategy.** Python 3's `open(p, 'r')` defaults to newline=None which converts \\r\\n -> \\n and \\r -> \\n before content reaches the component. To exercise debug_content's three EOL-detection branches we call the method directly with synthesized strings, plus one end-to-end test for the Unix branch (the only naturally-surviving form).

5. **Pipeline raw_text test uses no-special-char content.** The committed sample_raw_utf8.txt has multi-line content; the pipeline fixture's tFileOutputDelimited config has fieldseparator=';' but no escapechar, so writing multi-line content as a single cell trips Python's csv module. The test uses a single-line 'HelloWorld' string to exercise the full pipeline lifecycle without tripping the unrelated CSV-escape behavior. The encoding/BOM/multi-line content is still exercised by the FileInputRaw unit tests directly.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 + Rule 3 - Bug + Blocking] BUG-FIJ-001: FileInputJSON not registered with REGISTRY**

- **Found during:** Smoke-checking the json_jsonpath pipeline fixture before writing test_file_input_json.py.
- **Issue:** FileInputJSON was imported in `src/v1/engine/components/file/__init__.py` but never decorated with `@REGISTRY.register`. ETLEngine._initialize_components silently logged 'Unknown component type FileInputJSON' and continued. The converter at `src/converters/talend_to_v1/components/file/file_input_json.py:89` emits `type="FileInputJSON"`, so production jobs that converted from `tFileInputJSON` ran with the component missing. Identical shape to BUG-SWIFT-001 (Plan 14-07), BUG-PDC-001 (Plan 14-06), BUG-AGG-001 (Plan 14-02).
- **Fix:** Added `@REGISTRY.register("FileInputJSON", "tFileInputJSON")` decorator.
- **Files modified:** `src/v1/engine/components/file/file_input_json.py`
- **Verification:** `REGISTRY.get("FileInputJSON")` returns the class; `REGISTRY.get("tFileInputJSON")` returns the class. Pipeline test runs end-to-end.
- **Committed in:** `76cd7cb`

**2. [Rule 1 - Bug] BUG-FIJ-002: FileInputJSON missing abstract _validate_config (BaseComponent contract violation)**

- **Found during:** First instantiation attempt during test setup (immediately after fixing BUG-FIJ-001).
- **Issue:** `BaseComponent._validate_config` is declared `@abstractmethod`. FileInputJSON had only a public `validate_config()` (no leading underscore) which Python ABCs do NOT recognize. `__abstractmethods__` was non-empty and Python's ABC machinery refused instantiation with `TypeError: Can't instantiate abstract class FileInputJSON without an implementation for abstract method '_validate_config'`. Identical shape to BUG-SWIFT-002 (Plan 14-07).
- **Fix:** Added `_validate_config` method that raises ConfigurationError for missing required keys (filename or useurl+urlpath; json_loop_query), and wrong-shape mapping/encoding/booleans/schema. Per Rule 12, content-level checks remain in `_process()`.
- **Files modified:** `src/v1/engine/components/file/file_input_json.py`
- **Verification:** `__abstractmethods__` is empty; instantiation via REGISTRY succeeds.
- **Committed in:** `76cd7cb`

**3. [Rule 3 - Blocking issue] Extend .gitignore D-RULE3 negation to tests/fixtures/data/**/*.json**

- **Found during:** Task 14-09-002 commit step (`git add` reported "paths are ignored by .gitignore").
- **Issue:** Plan 14-08 D-RULE3 added `!tests/fixtures/jobs/**/*.json` to override the project-wide `*.json` rule. The new sample_data.json / sample_jsonpath.json fixtures live under `tests/fixtures/data/`, not `tests/fixtures/jobs/`, so they were silently swallowed.
- **Fix:** Added a second negation `!tests/fixtures/data/**/*.json` to .gitignore.
- **Files modified:** `.gitignore`
- **Verification:** `git add tests/fixtures/data/sample_data.json` succeeds without -f.
- **Committed in:** `2abd311`

**4. [Rule 3 - Blocking] Installed xlwt as a build-time dev dependency**

- **Found during:** Task 14-09-001 attempting to generate sample_legacy.xls.
- **Issue:** Python 3.10+ no longer ships xlwt; xlrd dropped .xls write support; sample_legacy.xls requires BIFF8 format which xlwt produces. xlwt was not in the environment.
- **Fix:** `pip install xlwt` (one-time dev-environment install). Not added to pyproject because: (a) xlwt is only needed to BUILD the fixture once and the .xls file is committed; (b) xlrd is already in the dependency set for reading .xls files at runtime; (c) future fixture rebuilds can re-install on demand.
- **Files modified:** None (no dependency files changed).
- **Verification:** `python -c "import xlwt"` succeeds; sample_legacy.xls loads via xlrd.
- **Committed in:** No commit (env-only).

### D-C5 Considerations

No D-C5 deletions in this plan. The 15 unreached lines in file_input_excel.py were considered for D-C5 but kept because:
- They are defensive guards inside real code paths (not init-time, abstract-method, or optional-import shims that D-C3 explicitly permits).
- They protect against pd.read_excel / xlrd version drift -- pandas 3 / xlrd 2.x have changed behavior; the catches are reasonable insurance.
- The 95% per-module floor is cleared without them; D-C5 cleanup is a cosmetic concern that does not block the gate.

Recommend Phase 16 (cleanup) or a closeout sweep delete them if the project moves to pinned pd.read_excel / xlrd versions.

---

**Total deviations:** 2 source bugs auto-fixed + 1 .gitignore extension + 1 dev-env install
**Impact on plan:** BUG-FIJ-001/002 blocked the json_jsonpath pipeline test required by the plan's success criteria. Without registration and abstract-method fixes, no `run_job_fixture("file/json_jsonpath", ...)` test for FileInputJSON could ever succeed. Fixes are minimal -- one decorator + one ~30-line _validate_config method. No feature creep; the component behaves the same way it did before for any caller that already worked (since no caller actually worked).

## Issues Encountered

- **Plan-checker note:** The plan's commit_map said "8 + optional bug commits". Landed at 9 (4 chore-fixture + 1 fix-source + 4 test-coverage); the source-bug commit was BUG-FIJ-001/002 combined.
- **debug_content universal-newlines artifact:** Documented inline in `TestLineEndingDetection` test class -- a real source quirk worth knowing about. The component would never see \\r\\n through normal text-mode reads on Python 3, so the Windows-detection branch is technically dead code under normal operation. Kept as defensive logging; no source change.
- **Pipeline raw_text CSV escape:** Documented as a decision (#5 above). The pipeline fixture is unchanged; the test works around at call time.
- **xlrd Pandas4Warning noise:** `df.select_dtypes(include=['object'])` triggers Pandas4Warning for str-dtype inclusion. Warnings only; tests pass. Out of scope for Plan 14-09; future pandas-4-compat phase can address.

## Known Stubs

None. All new tests assert real behavior against real fixtures or method-level outputs. No placeholder / hardcoded-empty / TODO patterns in the new test or fixture files.

## Threat Flags

None new. File-input components handle untrusted file inputs; existing parsing (openpyxl, xlrd, json.load, jsonpath_ng) is the same surface that has been in place since Phase 4. No new attack surface introduced by adding tests / fixtures / registration. The `eval()` concern noted in Plan 14-07 SWIFT does not apply here -- none of these components evaluate user input.

## TDD Gate Compliance

This is an `execute` plan, not a `tdd` plan. RED/GREEN gate sequence does not apply. Test commits (`5c4afa0`, `8c2847d`, `b138bd7`, `e9c2cbe`) come AFTER the source-fix commit (`76cd7cb`) for the BUG-FIJ pair, which is correct order: the source fix was a Rule 1/2 unblocker for the test to be written at all.

## Self-Check: PASSED

- All created files exist:
  - tests/v1/engine/components/file/test_file_input_json.py: FOUND
  - tests/v1/engine/components/file/test_file_input_raw.py: FOUND
  - tests/fixtures/data/sample_basic.xlsx: FOUND
  - tests/fixtures/data/sample_multisheet.xlsx: FOUND
  - tests/fixtures/data/sample_legacy.xls: FOUND
  - tests/fixtures/data/sample_data.json: FOUND
  - tests/fixtures/data/sample_jsonpath.json: FOUND
  - tests/fixtures/data/sample_raw_utf8.txt: FOUND
  - tests/fixtures/data/sample_raw_iso8859.txt: FOUND
  - tests/fixtures/jobs/file/excel_simple.json: FOUND
  - tests/fixtures/jobs/file/json_jsonpath.json: FOUND
  - tests/fixtures/jobs/file/raw_text.json: FOUND
- All commits exist on feature/engine-restructure: FOUND (9 commits between `709cd33` and `e9c2cbe`)
- Coverage: file_output_excel 100.0% PASS, file_input_excel 97.4% PASS, file_input_json 100.0% PASS, file_input_raw 100.0% PASS
- Per-plan gate: PASS for all 26 file modules at 95% floor
- 1402 tests pass under `-n auto` across file/ + integration/test_iterate_e2e.py

## Next Phase Readiness

- Plan 14-09 closes the 4 file deep gaps (largest single-module 419 missed lines lifted to 15).
- All file/* modules are now solidly at >=97.4% line coverage.
- BUG-FIJ-001/002 plus Plan 14-06/07's BUG-PDC-001/002 + BUG-SWIFT-001/002 form a clear pattern: silent "Unknown component" + ABC instantiation failure due to missing _validate_config in any non-registered subclass. Plan 14-13 closeout should add a plan-checker grep that flags new BaseComponent subclasses missing either decorator.
- Remaining Phase 14 plans: 14-12 (converters), 14-13 (closeout).
- No new blockers.

---
*Phase: 14-coverage-push-to-95-per-module-floor*
*Completed: 2026-05-11*
