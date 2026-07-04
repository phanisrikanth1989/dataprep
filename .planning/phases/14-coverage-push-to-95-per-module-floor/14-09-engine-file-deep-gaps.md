---
phase: 14
plan: 09
slug: engine-file-deep-gaps
type: execute
wave: 2
depends_on: [14-01]
files_modified:
  - tests/v1/engine/components/file/test_file_output_excel.py
  - tests/v1/engine/components/file/test_file_input_excel.py
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
  - src/v1/engine/components/file/file_*_*.py  # only if BUGs surface
autonomous: true
requirements: [TEST-11]
must_haves:
  truths:
    - "src/v1/engine/components/file/file_output_excel.py >= 95% line coverage"
    - "src/v1/engine/components/file/file_input_excel.py >= 95% line coverage"
    - "src/v1/engine/components/file/file_input_json.py >= 95% line coverage"
    - "src/v1/engine/components/file/file_input_raw.py >= 95% line coverage"
    - "Real .xlsx, .xls, .json, .txt fixture files exist under tests/fixtures/data/ (not generated at test time -- committed)"
    - "Pipeline tests via run_job_fixture exercise full ETLEngine.execute() lifecycle for each deep-gap module"
  artifacts:
    - path: tests/fixtures/data/sample_*.xlsx, *.xls, *.json, *.txt
      provides: real binary/text fixture files for deep-gap file tests
    - path: tests/fixtures/jobs/file/excel_simple.json
      provides: pipeline fixture for tFileInputExcel + tFileOutputExcel basic flow
    - path: tests/fixtures/jobs/file/json_jsonpath.json
      provides: pipeline fixture for tFileInputJSON with JSONPath extraction
    - path: tests/fixtures/jobs/file/raw_text.json
      provides: pipeline fixture for tFileInputRaw single-field read
  key_links:
    - from: each test file
      to: matching src/v1/engine/components/file/<module>.py
      via: real fixture files + run_job_fixture pipeline tests
---

<objective>
Lift the four file-component deep gaps: `file_output_excel.py` (69%, 91 missed, 294 stmts), `file_input_excel.py` (29%, 419 missed, 588 stmts -- the largest single file gap), `file_input_json.py` (9%, 156 missed, 172 stmts), `file_input_raw.py` (15%, 51 missed, 60 stmts). Real binary/text fixture files committed under `tests/fixtures/data/` per D-A2 + RESEARCH §Module Triage. Pipeline tests via `run_job_fixture` for each deep-gap module per D-C1 (file I/O lifecycle / globalMap / encoding / format-branching matter).
</objective>

<scope>
- NEW fixture data files (binary committed):
    - `tests/fixtures/data/sample_basic.xlsx` -- single-sheet, header row, mixed dtypes (string/int/decimal/date)
    - `tests/fixtures/data/sample_multisheet.xlsx` -- two sheets with different schemas; exercises regex sheet-matching branch in `file_input_excel.py`
    - `tests/fixtures/data/sample_legacy.xls` -- BIFF8 .xls format via xlrd path; small file
    - `tests/fixtures/data/sample_data.json` -- simple JSON list of records
    - `tests/fixtures/data/sample_jsonpath.json` -- nested JSON requiring JSONPath extraction
    - `tests/fixtures/data/sample_raw_utf8.txt` -- short text file, UTF-8 BOM
    - `tests/fixtures/data/sample_raw_iso8859.txt` -- short text file, ISO-8859-15 with non-ASCII bytes (legitimate for the file's content -- ASCII-only rule applies to LOG output, not test data)
- NEW pipeline-job JSON fixtures:
    - `tests/fixtures/jobs/file/excel_simple.json` -- tFileInputExcel -> tFileOutputDelimited
    - `tests/fixtures/jobs/file/json_jsonpath.json` -- tFileInputJSON (JSONPath mode) -> tFileOutputDelimited
    - `tests/fixtures/jobs/file/raw_text.json` -- tFileInputRaw -> tFileOutputDelimited
- MODIFIED tests:
    - `tests/v1/engine/components/file/test_file_output_excel.py` -- cover advanced format branches (cell styles, formulas, multi-sheet write, sheet replace, header formatting) via openpyxl mock or real round-trip
    - `tests/v1/engine/components/file/test_file_input_excel.py` -- the deep-gap module (29%). Cover:
        - .xlsx via openpyxl path
        - .xls via xlrd path (legacy)
        - regex sheet-matching (multi-sheet workbook)
        - password-protected workbook (mock or skip via raise -> ConfigurationError)
        - ADVANCED_SEPARATOR for numeric columns
        - Date conversion (Excel date serial + datetime cells)
        - HEADER + FOOTER rows
        - Streaming vs batch (THRESHOLD branch)
        - die_on_error True/False
        - Pipeline test via `run_job_fixture("file/excel_simple", ...)`
    - `tests/v1/engine/components/file/test_file_input_json.py` -- the deepest gap (9%). Cover:
        - Simple list-of-objects mode
        - JSONPath query mode
        - Encoding variants (UTF-8 BOM, UTF-16)
        - URL read path (`urlopen`-based) -- mock `urlopen`
        - Date-parse + advanced separator branches
        - Malformed JSON -> DataValidationError
        - Pipeline test via `run_job_fixture("file/json_jsonpath", ...)`
    - `tests/v1/engine/components/file/test_file_input_raw.py` -- 15% module, small (60 stmts). Cover:
        - `as_string=True` (single-string single-row output)
        - `as_string=False` (one row per line)
        - Encoding variations (UTF-8, ISO-8859-15)
        - Missing file with `die_on_error=True` -> `FileOperationError`; `die_on_error=False` -> warning + empty output
        - Windows/Unix/Mac line-ending detection (debug_content branch)
        - Pipeline test via `run_job_fixture("file/raw_text", ...)`
- POSSIBLY MODIFIED: source files only if real bugs surface.
</scope>

<out_of_scope>
- file_output_xml / file_input_xml / file_output_advanced_xml (already at 95%+; Phase 12).
- file_archive (already at 95%+).
- Plan 14-08 file modules.
- Real password-protected .xlsx generation (use mock for that branch -- regulator-grade real samples not required per D-A5 spirit).
</out_of_scope>

<canonical_refs>
- `.planning/phases/14-coverage-push-to-95-per-module-floor/14-RESEARCH.md` §Module Triage file deep gaps; §Pipeline-Test Infrastructure
- `.planning/phases/14-coverage-push-to-95-per-module-floor/14-CONTEXT.md` D-A2, D-C1, D-C4
- `.planning/phases/13-test-stabilization-bridge-jar-rebuild/13-02-PLAN.md` (Phase 13 BUG-EXC-001 already fixed defensive read)
- `src/v1/engine/components/file/file_output_excel.py`, `file_input_excel.py`, `file_input_json.py`, `file_input_raw.py` (lift targets)
- `tests/v1/engine/components/file/test_file_output_excel.py` etc. (existing test scaffolding -- extend)
- `tests/conftest.py` (run_job_fixture)
- `src/v1/engine/exceptions.py`
</canonical_refs>

<waves>

## Wave 0 -- Real fixture-data files + pipeline-job JSON fixtures

### Task 14-09-001 -- Generate sample_basic.xlsx + sample_multisheet.xlsx (openpyxl) + sample_legacy.xls (xlrd-readable)

- **Type:** fixture (binary)
- **Description:** Generate at fixture-creation time using `openpyxl` for .xlsx and a tiny hand-rolled or pre-saved .xls. Fixtures committed -- not generated per-test-run.
    Script (one-shot, run by hand or as a fixture-build script under `tests/fixtures/data/_build_fixtures.py`):
    ```python
    from openpyxl import Workbook
    wb = Workbook(); ws = wb.active; ws.title = "Sheet1"
    ws.append(["id", "name", "salary", "hire_date"])
    ws.append([1, "Alice", 1000.50, "2024-01-15"])
    ws.append([2, "Bob", 2500.00, "2024-02-20"])
    wb.save("tests/fixtures/data/sample_basic.xlsx")
    ```
    Multisheet variant: 2 sheets ("Q1", "Q2") with different schemas. .xls: pre-existing tiny BIFF8 file (committed binary; if not available, synthesize via `xlwt` if installed, else hand-roll a 30-line sample).
- **Files:** `tests/fixtures/data/sample_basic.xlsx`, `tests/fixtures/data/sample_multisheet.xlsx`, `tests/fixtures/data/sample_legacy.xls`
- **Verification:** `python -c "from openpyxl import load_workbook; wb=load_workbook('tests/fixtures/data/sample_basic.xlsx'); assert wb['Sheet1'].max_row >= 3; print('ok-basic'); wb=load_workbook('tests/fixtures/data/sample_multisheet.xlsx'); assert len(wb.sheetnames) == 2; print('ok-multi'); import xlrd; wb=xlrd.open_workbook('tests/fixtures/data/sample_legacy.xls'); print('ok-xls')"`
- **Expected:** All three `ok-*` lines printed.

### Task 14-09-002 -- Generate sample_data.json + sample_jsonpath.json
- **Type:** fixture
- **Description:** Two JSON files: simple list of records + nested structure with JSONPath-extractable inner array.
- **Files:** `tests/fixtures/data/sample_data.json`, `tests/fixtures/data/sample_jsonpath.json`
- **Verification:** `python -c "import json; json.load(open('tests/fixtures/data/sample_data.json')); json.load(open('tests/fixtures/data/sample_jsonpath.json')); print('ok')"`
- **Expected:** `ok`.

### Task 14-09-003 -- Generate sample_raw_utf8.txt + sample_raw_iso8859.txt
- **Type:** fixture
- **Description:** Two raw text files. UTF-8 with BOM; ISO-8859-15 with non-ASCII bytes (e.g. e-acute) -- NOTE: ASCII-only rule applies to LOGS, not to test fixture data files (they exercise encoding branches by design).
- **Files:** `tests/fixtures/data/sample_raw_utf8.txt`, `tests/fixtures/data/sample_raw_iso8859.txt`
- **Verification:** `python -c "open('tests/fixtures/data/sample_raw_utf8.txt','rb').read(3)==b'\\xef\\xbb\\xbf' or print('utf8 has no BOM -- still ok'); open('tests/fixtures/data/sample_raw_iso8859.txt','rb').read(); print('ok')"`
- **Expected:** `ok`.

### Task 14-09-004 -- Generate pipeline-job JSON fixtures (excel_simple, json_jsonpath, raw_text)
- **Type:** fixture
- **Description:** 3 JSON job configs -- each a 2-component pipeline (input + output).
- **Files:** `tests/fixtures/jobs/file/excel_simple.json`, `tests/fixtures/jobs/file/json_jsonpath.json`, `tests/fixtures/jobs/file/raw_text.json`
- **Verification:** `python -c "import json; [json.load(open(f)) for f in ['tests/fixtures/jobs/file/excel_simple.json','tests/fixtures/jobs/file/json_jsonpath.json','tests/fixtures/jobs/file/raw_text.json']]; print('ok')"`
- **Expected:** `ok`.

## Wave 1 -- Test extensions per module

### Task 14-09-005 -- Lift file_output_excel.py to 95%
- **Files:** `tests/v1/engine/components/file/test_file_output_excel.py`
- **Description:** Cover advanced format branches (cell styles, formulas, multi-sheet, sheet replace, header formatting). Mock openpyxl where round-trip too costly; otherwise round-trip via tmp_path.
- **Verification:** `python -m pytest tests/v1/engine/components/file/test_file_output_excel.py --cov=src/v1/engine/components/file/file_output_excel --cov-report=term-missing -q`
- **Expected:** >= 95%.

### Task 14-09-006 -- Lift file_input_excel.py to 95% (deepest file gap, 588 stmts)
- **Files:** `tests/v1/engine/components/file/test_file_input_excel.py`
- **Description:** Cover .xlsx + .xls + multi-sheet regex matching + ADVANCED_SEPARATOR + date conversion (Excel serials) + HEADER/FOOTER rows + streaming/batch threshold + password (mock) + die_on_error. Pipeline test via `run_job_fixture("file/excel_simple", ...)` against committed sample fixture.
- **Verification:** `python -m pytest tests/v1/engine/components/file/test_file_input_excel.py --cov=src/v1/engine/components/file/file_input_excel --cov-report=term-missing -q`
- **Expected:** >= 95%; tests green.
- **Notes:** Largest single test extension in Phase 14 by missed-line count (419). Likely the test file grows from a small scaffold to ~30+ tests. Use `@pytest.mark.slow` for any test exceeding 5s.

### Task 14-09-007 -- Lift file_input_json.py to 95% (deepest gap percentage-wise, 9%)
- **Files:** `tests/v1/engine/components/file/test_file_input_json.py`
- **Description:** Cover simple list mode + JSONPath query + encoding variants + URL-read (mock urllib) + date-parse + malformed-JSON -> DataValidationError. Pipeline test via `run_job_fixture("file/json_jsonpath", ...)`.
- **Verification:** `python -m pytest tests/v1/engine/components/file/test_file_input_json.py --cov=src/v1/engine/components/file/file_input_json --cov-report=term-missing -q`
- **Expected:** >= 95%.

### Task 14-09-008 -- Lift file_input_raw.py to 95% (small file but deep gap, 60 stmts)
- **Files:** `tests/v1/engine/components/file/test_file_input_raw.py`
- **Description:** Cover as_string True/False + encoding variations + missing file (both die_on_error modes) + line-ending detection (Windows CRLF, Unix LF, Mac CR -- debug_content branch). Pipeline test via `run_job_fixture("file/raw_text", ...)`.
- **Verification:** `python -m pytest tests/v1/engine/components/file/test_file_input_raw.py --cov=src/v1/engine/components/file/file_input_raw --cov-report=term-missing -q`
- **Expected:** >= 95%.

### Task 14-09-009 -- Per-plan gate verification
- **Type:** infra (verify)
- **Description:**
    ```bash
    rm -f .coverage* && python -m pytest tests/v1/engine/components/file/ -m "not oracle" -n auto \
      --cov=src/v1/engine/components/file --cov-report=json:cov_14_09.json -q
    python scripts/check_per_module_coverage.py cov_14_09.json --floor 95
    ```
- **Expected:** PASS for all `src/v1/engine/components/file/*.py` modules (combined with Plan 14-08 closure of the quick-win + medium-gap file modules).

</waves>

<verification_gate>

Plan 14-09 is GREEN when:
1. All four deep-gap modules >= 95%.
2. All committed fixture files load successfully (`openpyxl`, `xlrd`, `json`, plain-text reads).
3. Pipeline tests pass via `run_job_fixture`.
4. ETLError subclasses in all `raises`.
5. `assert_ascii_logs` clean (test fixture data may be non-ASCII; LOGS must remain ASCII).
6. Per-module gate exits 0 for all 26 file modules (combined with 14-08).

</verification_gate>

<commit_map>

| # | Subject | Files |
|---|---------|-------|
| 1 | `chore(14-09): INFRA-FX-004 add Excel sample fixtures (xlsx + multisheet + xls)` | `tests/fixtures/data/sample_basic.xlsx`, `tests/fixtures/data/sample_multisheet.xlsx`, `tests/fixtures/data/sample_legacy.xls` |
| 2 | `chore(14-09): INFRA-FX-005 add JSON sample fixtures (simple + jsonpath)` | `tests/fixtures/data/sample_data.json`, `tests/fixtures/data/sample_jsonpath.json` |
| 3 | `chore(14-09): INFRA-FX-006 add raw-text sample fixtures (utf8 + iso8859)` | `tests/fixtures/data/sample_raw_*.txt` |
| 4 | `chore(14-09): INFRA-FX-007 add pipeline-job fixtures (excel/json/raw)` | `tests/fixtures/jobs/file/{excel_simple,json_jsonpath,raw_text}.json` |
| 5 | `test(14-09): COV-FOE-001 lift file/file_output_excel to 95% (cell styles + formulas + multi-sheet + header formatting)` | `tests/v1/engine/components/file/test_file_output_excel.py` |
| 6 | `test(14-09): COV-FIE-001 lift file/file_input_excel to 95% (.xlsx + .xls + regex sheet + ADVANCED_SEPARATOR + dates + streaming/batch + pipeline)` | `tests/v1/engine/components/file/test_file_input_excel.py` |
| 7 | `test(14-09): COV-FIJ-001 lift file/file_input_json to 95% (list + JSONPath + url + encoding + malformed + pipeline)` | `tests/v1/engine/components/file/test_file_input_json.py` |
| 8 | `test(14-09): COV-FIR-001 lift file/file_input_raw to 95% (as_string + encoding + line-endings + missing-file + pipeline)` | `tests/v1/engine/components/file/test_file_input_raw.py` |
| 9+ (conditional) | `fix(14-09): BUG-FX-NN <description>` -- only if bug surfaces | source files |

(Total: 8 + optional bug commits.)

</commit_map>
