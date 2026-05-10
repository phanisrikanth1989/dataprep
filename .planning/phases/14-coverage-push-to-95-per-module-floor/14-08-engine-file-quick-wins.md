---
phase: 14
plan: 08
slug: engine-file-quick-wins
type: execute
wave: 1
depends_on: [14-01]
files_modified:
  - tests/v1/engine/components/file/test_file_list.py
  - tests/v1/engine/components/file/test_file_unarchive.py
  - tests/v1/engine/components/file/test_file_properties.py
  - tests/v1/engine/components/file/test_file_copy.py
  - tests/v1/engine/components/file/test_file_input_properties.py
  - tests/v1/engine/components/file/test_fixed_flow_input.py
  - tests/v1/engine/components/file/test_set_global_var.py
  - tests/v1/engine/components/file/test_file_input_delimited.py
  - tests/v1/engine/components/file/test_file_output_delimited.py
  - tests/v1/engine/components/file/test_file_output_positional.py
  - tests/v1/engine/components/file/test_file_input_positional.py
  - tests/v1/engine/components/file/test_file_touch.py
  - tests/fixtures/jobs/file/csv_with_header.json           # NEW pipeline fixture
  - tests/fixtures/jobs/file/csv_with_reject.json           # NEW pipeline fixture
  - tests/fixtures/jobs/file/csv_split_output.json          # NEW pipeline fixture
  - src/v1/engine/components/file/file_output_delimited.py  # D-C5 dead-code resolution at line 364
  - src/v1/engine/components/file/*.py                       # only if BUGs surface
autonomous: true
requirements: [TEST-11]
must_haves:
  truths:
    - "All 12 modules in scope reach >= 95% line coverage"
    - "The single existing pragma at file_output_delimited.py:364 is resolved (deleted, covered, or kept under D-C3 allowlist with explicit justification in plan summary)"
    - "Pipeline tests for file_input_delimited / file_output_delimited exist and pass"
    - "ETLError-subclass exceptions used in all raises assertions"
  artifacts:
    - path: tests/v1/engine/components/file/test_<module>.py
      provides: extension of existing per-module tests for missed-line clusters
    - path: tests/fixtures/jobs/file/csv_with_header.json
      provides: minimum 1-component pipeline fixture for tFileInputDelimited basic tests
    - path: tests/fixtures/jobs/file/csv_with_reject.json
      provides: 3-component pipeline fixture (input + output + reject) for CHECK_FIELDS_NUM behavior
    - path: tests/fixtures/jobs/file/csv_split_output.json
      provides: file-split (FOLD-04) pipeline fixture for tFileOutputDelimited
  key_links:
    - from: each test file
      to: matching src/v1/engine/components/file/<module>.py
      via: direct _process() unit tests + run_job_fixture pipeline tests for delimited modules
---

<objective>
Lift 12 file-component modules in the 81-94% range to >= 95%. Resolve the single existing `# pragma: no cover` at `src/v1/engine/components/file/file_output_delimited.py:364` per D-C5 decision tree (delete preferred, then cover, then allowlist). Pipeline tests required for `file_input_delimited.py` and `file_output_delimited.py` (D-C1 -- file I/O lifecycle / globalMap / reject-routing semantics matter); rest are unit-test only.
</objective>

<scope>
Modules + baseline (RESEARCH §Module Triage file table):

| Module | Cover | Miss | Effort | Test fit |
|--------|------:|-----:|--------|----------|
| file_list.py | 94% | 11 | S | unit + pipeline (set_global_var paired) |
| file_unarchive.py | 92% | 5 | S | unit |
| file_properties.py | 91% | 4 | S | unit |
| file_copy.py | 92% | 8 | S | unit |
| file_input_properties.py | 88% | 10 | M | unit |
| fixed_flow_input.py | 88% | 14 | M | unit |
| set_global_var.py | 89% | 7 | S | unit + pipeline |
| file_input_delimited.py | 86% | 53 | M-L | unit + pipeline |
| file_output_delimited.py | 83% | 46 | M-L | unit + pipeline; D-C5 pragma decision |
| file_output_positional.py | 83% | 44 | M-L | unit |
| file_input_positional.py | 81% | 33 | M | unit |
| file_touch.py | 83% | 9 | S | unit |

Branch hints from RESEARCH:
- `file_list.py`: glob/regex error branches; sort-order edge cases
- `file_unarchive.py`: unsupported archive type + permission errors
- `file_properties.py`: missing file / permission errors
- `file_copy.py`: overwrite-collision, source-missing, permission
- `file_input_properties.py`: invalid `.properties` syntax, encoding mismatches
- `fixed_flow_input.py`: multi-row + schema validation edges
- `set_global_var.py`: pipeline-test verifies vars flow downstream
- `file_input_delimited.py`: CSV-mode (RFC4180) edges via pipeline; encoding (ISO-8859-15) handling; CHECK_FIELDS_NUM reject
- `file_output_delimited.py`: file-split (FOLD-04), FILE_EXIST_EXCEPTION, multi-char delimiter; resolve pragma at line 364
- `file_output_positional.py`: column-width edge cases (truncation, padding)
- `file_input_positional.py`: date_pattern + thousands/decimal-separator branches
- `file_touch.py`: timestamp-clobber, create-vs-update branches
</scope>

<out_of_scope>
- Deep gaps `file_output_excel.py`, `file_input_excel.py`, `file_input_json.py`, `file_input_raw.py` (Plan 14-09).
- Already-at-95% file modules (`_xml_io.py`, `file_exist.py`, `file_delete.py`, `file_input_xml.py`, `file_output_advanced_xml.py`, `file_archive.py`, `file_row_count.py`, `file_input_fullrow.py`, `file_output_xml.py`).
</out_of_scope>

<canonical_refs>
- `.planning/phases/14-coverage-push-to-95-per-module-floor/14-RESEARCH.md` §Module Triage file section, §Pragma Policy & Enforcement (existing pragma audit), §Pipeline-Test Infrastructure
- `.planning/phases/14-coverage-push-to-95-per-module-floor/14-CONTEXT.md` D-C1, D-C2, D-C3, D-C5
- `src/v1/engine/components/file/*.py` (each lift target)
- existing `tests/v1/engine/components/file/test_<module>.py` (extend, don't replace)
- `src/v1/engine/exceptions.py` (FileOperationError, ConfigurationError, DataValidationError)
- `src/v1/engine/components/file/file_output_delimited.py:364` (the single existing pragma)
- `tests/conftest.py` (run_job_fixture)
</canonical_refs>

<waves>

## Wave 0 -- Pipeline-test fixtures for file delimited modules

### Task 14-08-001 -- Generate file/csv_with_header pipeline fixture

- **Type:** fixture
- **Description:** Convert a minimal `.item` (or hand-construct) -> `tests/fixtures/jobs/file/csv_with_header.json`. 1-component pipeline (just tFileInputDelimited, INCLUDEHEADER=true, semicolon-delimited, ISO-8859-15 encoding) -- placeholder filepath via mutations.
- **Files:** `tests/fixtures/jobs/file/csv_with_header.json`
- **Verification:** `python -c "import json; c=json.load(open('tests/fixtures/jobs/file/csv_with_header.json')); assert c['components'][0]['type'] in ('tFileInputDelimited','FileInputDelimited'); print('ok')"`
- **Expected:** `ok`.

### Task 14-08-002 -- Generate file/csv_with_reject pipeline fixture

- **Type:** fixture
- **Description:** 3-component pipeline: tFileInputDelimited (CHECK_FIELDS_NUM=true) -> tFileOutputDelimited (main) + REJECT flow -> tFileOutputDelimited (reject).
- **Files:** `tests/fixtures/jobs/file/csv_with_reject.json`
- **Verification:** `python -c "import json; c=json.load(open('tests/fixtures/jobs/file/csv_with_reject.json')); assert any('reject' in str(f).lower() for f in c.get('flows',[])); print('ok')"`
- **Expected:** `ok`.

### Task 14-08-003 -- Generate file/csv_split_output pipeline fixture

- **Type:** fixture
- **Description:** tFixedFlowInput (or simple input) -> tFileOutputDelimited (SPLIT=true, SPLIT_EVERY=2) -- exercises FOLD-04 file-split branch.
- **Files:** `tests/fixtures/jobs/file/csv_split_output.json`
- **Verification:** `python -c "import json; c=json.load(open('tests/fixtures/jobs/file/csv_split_output.json')); print('ok')"`
- **Expected:** `ok`.

## Wave 1 -- Per-module test extensions (12 atomic tasks)

For each task: inventory missed lines via `--cov-report=term-missing`, add targeted tests, verify >= 95% before commit. ETLError-subclass exceptions in all `raises`. Apply D-C5 (delete dead branch) when needed and document.

### Task 14-08-004 -- Lift file_list.py to 95% (unit; pipeline optional via set_global_var pairing)
- **Files:** `tests/v1/engine/components/file/test_file_list.py`
- **Verification:** `python -m pytest tests/v1/engine/components/file/test_file_list.py --cov=src/v1/engine/components/file/file_list --cov-report=term-missing -q`
- **Expected:** >= 95%.

### Task 14-08-005 -- Lift file_unarchive.py to 95%
- **Files:** `tests/v1/engine/components/file/test_file_unarchive.py`
- **Verification:** as above
- **Expected:** >= 95%.

### Task 14-08-006 -- Lift file_properties.py to 95%
- **Files:** `tests/v1/engine/components/file/test_file_properties.py`
- **Verification:** as above
- **Expected:** >= 95%.

### Task 14-08-007 -- Lift file_copy.py to 95%
- **Files:** `tests/v1/engine/components/file/test_file_copy.py`
- **Verification:** as above
- **Expected:** >= 95%.

### Task 14-08-008 -- Lift file_input_properties.py to 95%
- **Files:** `tests/v1/engine/components/file/test_file_input_properties.py`
- **Verification:** as above
- **Expected:** >= 95%.

### Task 14-08-009 -- Lift fixed_flow_input.py to 95%
- **Files:** `tests/v1/engine/components/file/test_fixed_flow_input.py`
- **Verification:** as above
- **Expected:** >= 95%.

### Task 14-08-010 -- Lift set_global_var.py to 95% (unit + optional pipeline)
- **Files:** `tests/v1/engine/components/file/test_set_global_var.py`
- **Description:** Add a pipeline test using `run_job_fixture` to verify variables set by tSetGlobalVar flow into a downstream component's config resolution.
- **Verification:** as above
- **Expected:** >= 95%.

### Task 14-08-011 -- Lift file_input_delimited.py to 95% (unit + pipeline)
- **Files:** `tests/v1/engine/components/file/test_file_input_delimited.py`
- **Description:** Unit tests for CSV-mode RFC4180 edges, ISO-8859-15 encoding, CHECK_FIELDS_NUM reject indices, TRIMSELECT per-column, THOUSANDS_SEPARATOR/DECIMAL_SEPARATOR. Pipeline tests via `run_job_fixture("file/csv_with_header", ...)` and `run_job_fixture("file/csv_with_reject", ...)` -- assert globalMap NB_LINE/NB_LINE_OK/NB_LINE_REJECT and reject-flow content per RESEARCH §Pattern 1 example.
- **Verification:** as above
- **Expected:** >= 95%.

### Task 14-08-012 -- Lift file_output_delimited.py to 95% + resolve pragma at line 364
- **Files:** `tests/v1/engine/components/file/test_file_output_delimited.py`, possibly `src/v1/engine/components/file/file_output_delimited.py`
- **Description:**
    1. Inventory missed lines.
    2. Cover file-split (FOLD-04), FILE_EXIST_EXCEPTION, multi-char delimiter, INCLUDEHEADER=False, append vs overwrite.
    3. Pipeline tests via `run_job_fixture("file/csv_split_output", ...)` to verify N output files generated when SPLIT_EVERY=2.
    4. **D-C5 decision** for the existing `# pragma: no cover` at `file_output_delimited.py:364`. Read the surrounding context: it's a catch-all `except Exception:` after typed exception handling. Per RESEARCH §A7 + D-C5: PREFER deletion (if the typed exception block above already catches everything reachable, the catch-all is dead). Apply in this order:
        - **First:** delete the catch-all + pragma. Run the test suite. If green, commit as `chore(14-08): STALE-FOD-001 delete unreachable catch-all per D-C5`.
        - **Else:** write a test that triggers the branch. Commit as `test(14-08): COV-FOD-NN cover catch-all branch in file_output_delimited`.
        - **Last:** if neither works, document why the pragma must remain (would require user override of D-C3) and surface in plan summary for closeout.
- **Verification:** `python -m pytest tests/v1/engine/components/file/test_file_output_delimited.py --cov=src/v1/engine/components/file/file_output_delimited --cov-report=term-missing -q`
- **Expected:** >= 95%; `grep -n "pragma: no cover" src/v1/engine/components/file/file_output_delimited.py` returns either empty (deleted) or only D-C3-allowlisted lines.

### Task 14-08-013 -- Lift file_output_positional.py to 95%
- **Files:** `tests/v1/engine/components/file/test_file_output_positional.py`
- **Verification:** `python -m pytest tests/v1/engine/components/file/test_file_output_positional.py --cov=src/v1/engine/components/file/file_output_positional --cov-report=term-missing -q`
- **Expected:** >= 95%.

### Task 14-08-014 -- Lift file_input_positional.py to 95%
- **Files:** `tests/v1/engine/components/file/test_file_input_positional.py`
- **Verification:** as above
- **Expected:** >= 95%.

### Task 14-08-015 -- Lift file_touch.py to 95%
- **Files:** `tests/v1/engine/components/file/test_file_touch.py`
- **Verification:** as above
- **Expected:** >= 95%.

### Task 14-08-016 -- Per-plan gate verification
- **Type:** infra (verify)
- **Description:**
    ```bash
    rm -f .coverage* && python -m pytest tests/v1/engine/components/file/ -m "not oracle" -n auto \
      --cov=src/v1/engine/components/file --cov-report=json:cov_14_08.json -q
    python scripts/check_per_module_coverage.py cov_14_08.json --floor 95
    ```
- **Expected:** PASS for the 12 modules in this plan; deep-gap file modules (excel/json/raw) may still fail (closed by Plan 14-09).
- **Notes:** Pragma audit:
    ```bash
    grep -rn "pragma: no cover" src/v1/engine/components/file/ \
      | grep -vE "(if __name__|abstractmethod|except ImportError)" \
      || echo "all file/ pragmas on D-C3 allowlist"
    ```
    Should print `all file/ pragmas on D-C3 allowlist` after task 14-08-012 closes the file_output_delimited:364 pragma.

</waves>

<verification_gate>

Plan 14-08 is GREEN when:
1. All 12 modules in scope >= 95% line coverage.
2. Pragma at `file_output_delimited.py:364` resolved (deleted, covered, or documented exception).
3. Pipeline tests for file_input_delimited and file_output_delimited pass via `run_job_fixture`.
4. ETLError subclasses in all `raises`.
5. `assert_ascii_logs` clean for any pipeline tests.
6. Per-module gate exits 0 for the 12 modules.
7. No new `# pragma: no cover` outside D-C3 allowlist anywhere in `src/v1/engine/components/file/`.

</verification_gate>

<commit_map>

| # | Subject | Files |
|---|---------|-------|
| 1 | `chore(14-08): INFRA-FX-001 add file/csv_with_header pipeline fixture` | `tests/fixtures/jobs/file/csv_with_header.json` |
| 2 | `chore(14-08): INFRA-FX-002 add file/csv_with_reject pipeline fixture` | `tests/fixtures/jobs/file/csv_with_reject.json` |
| 3 | `chore(14-08): INFRA-FX-003 add file/csv_split_output pipeline fixture` | `tests/fixtures/jobs/file/csv_split_output.json` |
| 4 | `test(14-08): COV-FL-001 lift file/file_list to 95% (glob/regex/sort branches)` | `tests/v1/engine/components/file/test_file_list.py` |
| 5 | `test(14-08): COV-FUA-001 lift file/file_unarchive to 95% (unsupported archive + perm errors)` | `tests/v1/engine/components/file/test_file_unarchive.py` |
| 6 | `test(14-08): COV-FP-001 lift file/file_properties to 95% (missing/perm errors)` | `tests/v1/engine/components/file/test_file_properties.py` |
| 7 | `test(14-08): COV-FCP-001 lift file/file_copy to 95% (overwrite/source-missing/perm)` | `tests/v1/engine/components/file/test_file_copy.py` |
| 8 | `test(14-08): COV-FIP-001 lift file/file_input_properties to 95% (syntax/encoding edges)` | `tests/v1/engine/components/file/test_file_input_properties.py` |
| 9 | `test(14-08): COV-FFI-001 lift file/fixed_flow_input to 95% (multi-row + schema-validation edges)` | `tests/v1/engine/components/file/test_fixed_flow_input.py` |
| 10 | `test(14-08): COV-SGV-001 lift file/set_global_var to 95% (unit + downstream-resolution pipeline)` | `tests/v1/engine/components/file/test_set_global_var.py` |
| 11 | `test(14-08): COV-FID-001 lift file/file_input_delimited to 95% (CSV mode + encoding + reject pipeline)` | `tests/v1/engine/components/file/test_file_input_delimited.py` |
| 12 | `chore(14-08): STALE-FOD-001 delete unreachable catch-all in file_output_delimited per D-C5` (or `test(14-08): COV-FOD-001 cover catch-all branch`) | `src/v1/engine/components/file/file_output_delimited.py` (and / or test file) |
| 13 | `test(14-08): COV-FOD-002 lift file/file_output_delimited to 95% (split + FILE_EXIST_EXCEPTION + multi-char delim pipeline)` | `tests/v1/engine/components/file/test_file_output_delimited.py` |
| 14 | `test(14-08): COV-FOP-001 lift file/file_output_positional to 95% (column-width edges)` | `tests/v1/engine/components/file/test_file_output_positional.py` |
| 15 | `test(14-08): COV-FIPo-001 lift file/file_input_positional to 95% (date_pattern + numeric separators)` | `tests/v1/engine/components/file/test_file_input_positional.py` |
| 16 | `test(14-08): COV-FT-001 lift file/file_touch to 95% (timestamp/create-vs-update)` | `tests/v1/engine/components/file/test_file_touch.py` |

(Total: 16 commits + optional bug commits.)

</commit_map>
