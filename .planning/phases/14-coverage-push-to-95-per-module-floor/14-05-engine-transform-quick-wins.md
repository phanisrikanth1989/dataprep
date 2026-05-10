---
phase: 14
plan: 05
slug: engine-transform-quick-wins
type: execute
wave: 1
depends_on: [14-01]
files_modified:
  - tests/v1/engine/components/transform/test_replace.py
  - tests/v1/engine/components/transform/test_python_row_component.py
  - tests/v1/engine/components/transform/test_pivot_to_columns_delimited.py
  - tests/v1/engine/components/transform/test_parse_record_set.py
  - tests/v1/engine/components/transform/test_row_generator.py
  - tests/v1/engine/components/transform/test_python_component.py
  - tests/v1/engine/components/transform/test_extract_positional_fields.py
  - tests/v1/engine/components/transform/test_extract_regex_fields.py
  - tests/v1/engine/components/transform/test_convert_type.py
  - tests/v1/engine/components/transform/test_extract_json_fields.py
  - tests/v1/engine/components/transform/test_extract_delimited_fields.py
  - tests/v1/engine/components/transform/test_filter_rows.py
autonomous: true
requirements: [TEST-11]
must_haves:
  truths:
    - "All 12 modules in scope reach >= 95% line coverage"
    - "Existing tests for these modules continue to pass"
    - "ETLError subclasses used in raises assertions"
  artifacts:
    - path: tests/v1/engine/components/transform/test_<module>.py
      provides: extension of existing per-module tests for missed-line clusters
  key_links:
    - from: each test file
      to: matching src/v1/engine/components/transform/<module>.py
      via: direct _process() unit tests with realistic-shape DataFrames (D-C1 pure-pandas)
---

<objective>
Lift 12 transform modules in the 80-94% baseline range to >= 95%. All targets are pure-pandas transforms with mature existing test files; the work is mechanical (extend existing tests with edge-case + error-branch coverage). Per D-C1, these are unit tests via direct `_process()` invocation -- no pipeline tests required (with the exception of `filter_rows.py` where pipeline tests are optional, see RESEARCH §Module Triage).
</objective>

<scope>
Modules and current baseline (RESEARCH §Module Triage transform table):

| Module | Cover | Miss | Effort |
|--------|------:|-----:|--------|
| replace.py | 94% | 6 | S |
| python_row_component.py | 93% | 4 | S |
| pivot_to_columns_delimited.py | 91% | 10 | S-M |
| parse_record_set.py | 89% | 7 | S |
| row_generator.py | 84% | 15 | M |
| python_component.py | 84% | 6 | S |
| extract_positional_fields.py | 87% | 14 | M |
| extract_regex_fields.py | 86% | 14 | M |
| convert_type.py | 86% | 15 | M |
| extract_json_fields.py | 86% | 18 | M |
| extract_delimited_fields.py | 83% | 18 | M |
| filter_rows.py | 80% | 32 | M |

For each: extend the matching `tests/v1/engine/components/transform/test_<module>.py` with edge-case + error-branch coverage targeting the missed-line clusters surfaced by `--cov-report=term-missing`. Use realistic-shape DataFrames with mixed dtypes (D-C4). Always assert specific `ETLError` subclasses (`ConfigurationError`, `DataValidationError`, `ComponentExecutionError`) -- never bare `Exception` (D-C4).

Specific branch hints from RESEARCH:
- `replace.py`: regex vs literal mode + replace-in-multiple-columns
- `python_row_component.py`: per-row error + REJECT flow edges
- `pivot_to_columns_delimited.py`: empty input + duplicate pivot keys
- `parse_record_set.py`: malformed record-set input
- `row_generator.py`: random vs sequential modes, type generators (date/decimal/string/int)
- `python_component.py`: D-11 secure namespace branches (no os/sys access)
- `extract_positional_fields.py`: padding + truncation edges
- `extract_regex_fields.py`: invalid regex -> `ConfigurationError`; Phase 13 already fixed regex storage convention
- `convert_type.py`: type-coercion error paths; Phase 13 BUG-CT-001 added MANUALTABLE numeric fallback
- `extract_json_fields.py`: JSONPath syntax errors, missing keys
- `extract_delimited_fields.py`: inconsistent column counts
- `filter_rows.py`: AST parser branches (FROW-01) + 14 operators (FROW-02) inventory; FUNCTION pre-transforms (LOWER/UPPER/LENGTH/TRIM/LTRIM/RTRIM/LEFT/RIGHT)
</scope>

<out_of_scope>
- Deep gaps `map.py`, `join.py`, `python_dataframe_component.py` (Plan 14-06).
- SWIFT modules (Plan 14-07).
- Already-at-95% transform modules (denormalize, filter_columns, java_component, memorize_rows, replicate, split_row, unite, unpivot_row, aggregate_sorted_row, normalize, sample_row, sort_row, log_row, schema_compliance_check, xml_map, extract_xml_fields, change_file_encoding, java_row_component).
- Pipeline tests (D-C1: pure-pandas transforms = unit-test only).
</out_of_scope>

<canonical_refs>
- `.planning/phases/14-coverage-push-to-95-per-module-floor/14-RESEARCH.md` §Module Triage transform section
- `.planning/REQUIREMENTS.md` (FROW-01..07, AGGR-related, etc. for behavior context)
- Each `src/v1/engine/components/transform/<module>.py` (the lift targets)
- Each existing `tests/v1/engine/components/transform/test_<module>.py` (extend, don't replace)
- `src/v1/engine/exceptions.py`
</canonical_refs>

<waves>

## Wave 1 -- Module-by-module test extensions (atomic; parallelizable)

Each task below: (1) inventory missed lines via `pytest --cov=<module> --cov-report=term-missing`, (2) add targeted tests for each missed cluster, (3) verify >= 95% for that module before moving on. Apply D-C5 (delete dead branch over pragma) when a missed line cannot be reached with realistic input -- document each deletion in plan summary.

### Task 14-05-001 -- Lift replace.py to 95%

- **Type:** test
- **Files:** `tests/v1/engine/components/transform/test_replace.py`
- **Verification:** `python -m pytest tests/v1/engine/components/transform/test_replace.py --cov=src/v1/engine/components/transform/replace --cov-report=term-missing -q`
- **Expected:** >= 95%; tests green.

### Task 14-05-002 -- Lift python_row_component.py to 95%

- **Type:** test
- **Files:** `tests/v1/engine/components/transform/test_python_row_component.py`
- **Verification:** `python -m pytest tests/v1/engine/components/transform/test_python_row_component.py --cov=src/v1/engine/components/transform/python_row_component --cov-report=term-missing -q`
- **Expected:** >= 95%.

### Task 14-05-003 -- Lift pivot_to_columns_delimited.py to 95%

- **Type:** test
- **Files:** `tests/v1/engine/components/transform/test_pivot_to_columns_delimited.py`
- **Verification:** `python -m pytest <test> --cov=src/v1/engine/components/transform/pivot_to_columns_delimited --cov-report=term-missing -q`
- **Expected:** >= 95%.

### Task 14-05-004 -- Lift parse_record_set.py to 95%

- **Type:** test
- **Files:** `tests/v1/engine/components/transform/test_parse_record_set.py`
- **Verification:** as above
- **Expected:** >= 95%.

### Task 14-05-005 -- Lift row_generator.py to 95%

- **Type:** test
- **Files:** `tests/v1/engine/components/transform/test_row_generator.py`
- **Verification:** as above
- **Expected:** >= 95%.

### Task 14-05-006 -- Lift python_component.py to 95% (D-11 secure namespace)

- **Type:** test
- **Files:** `tests/v1/engine/components/transform/test_python_component.py`
- **Verification:** as above
- **Expected:** >= 95%; verify `os` and `sys` are NOT in execution namespace.

### Task 14-05-007 -- Lift extract_positional_fields.py to 95%

- **Type:** test
- **Files:** `tests/v1/engine/components/transform/test_extract_positional_fields.py`
- **Verification:** as above
- **Expected:** >= 95%.

### Task 14-05-008 -- Lift extract_regex_fields.py to 95%

- **Type:** test
- **Files:** `tests/v1/engine/components/transform/test_extract_regex_fields.py`
- **Verification:** as above
- **Expected:** >= 95%; ConfigurationError on invalid regex.

### Task 14-05-009 -- Lift convert_type.py to 95%

- **Type:** test
- **Files:** `tests/v1/engine/components/transform/test_convert_type.py`
- **Verification:** as above
- **Expected:** >= 95%.

### Task 14-05-010 -- Lift extract_json_fields.py to 95%

- **Type:** test
- **Files:** `tests/v1/engine/components/transform/test_extract_json_fields.py`
- **Verification:** as above
- **Expected:** >= 95%.

### Task 14-05-011 -- Lift extract_delimited_fields.py to 95%

- **Type:** test
- **Files:** `tests/v1/engine/components/transform/test_extract_delimited_fields.py`
- **Verification:** as above
- **Expected:** >= 95%.

### Task 14-05-012 -- Lift filter_rows.py to 95%

- **Type:** test
- **Files:** `tests/v1/engine/components/transform/test_filter_rows.py`
- **Verification:** as above
- **Expected:** >= 95%; AST parser branches + all 14+ operators + FUNCTION pre-transforms covered.

### Task 14-05-013 -- Per-plan gate verification

- **Type:** infra (verify)
- **Description:**
    ```bash
    rm -f .coverage* && python -m pytest tests/v1/engine/components/transform/ -n auto \
      --cov=src/v1/engine/components/transform --cov-report=json:cov_14_05.json -q
    python scripts/check_per_module_coverage.py cov_14_05.json --floor 95
    ```
- **Files:** none persisted.
- **Expected:** PASS for the 12 modules listed above. Other transform modules (deep gaps, SWIFT) may still be below floor at this point -- expected.
- **Notes:** Use `--floor 95` only against the 12 specific files for this plan via grep filter, OR accept that other transform modules will still show as failing here (Plans 14-06, 14-07 close them).

</waves>

<verification_gate>

Plan 14-05 is GREEN when:
1. All 12 modules in scope >= 95% line coverage.
2. All extended tests pass under `-m "not oracle" -n auto -q`.
3. No new pragmas outside D-C3 allowlist.
4. ETLError subclasses in all `raises` assertions.
5. Per-module gate script reports PASS for the 12 modules (other transform deep gaps may still fail; closed by 14-06/14-07).

</verification_gate>

<commit_map>

One commit per module, plus optional bug-fix commits if surfaced. Atomic-per-fix per Phase 13 D-F2.

| # | Subject | Files |
|---|---------|-------|
| 1 | `test(14-05): COV-REP-001 lift transform/replace to 95% (regex/literal/multi-col branches)` | `tests/v1/engine/components/transform/test_replace.py` |
| 2 | `test(14-05): COV-PRC-001 lift transform/python_row_component to 95% (per-row error/REJECT edges)` | `tests/v1/engine/components/transform/test_python_row_component.py` |
| 3 | `test(14-05): COV-PVT-001 lift transform/pivot_to_columns_delimited to 95% (empty/duplicate-keys edges)` | `tests/v1/engine/components/transform/test_pivot_to_columns_delimited.py` |
| 4 | `test(14-05): COV-PRS-001 lift transform/parse_record_set to 95% (malformed input edges)` | `tests/v1/engine/components/transform/test_parse_record_set.py` |
| 5 | `test(14-05): COV-RGN-001 lift transform/row_generator to 95% (random/sequential + type generators)` | `tests/v1/engine/components/transform/test_row_generator.py` |
| 6 | `test(14-05): COV-PYC-001 lift transform/python_component to 95% (D-11 secure namespace branches)` | `tests/v1/engine/components/transform/test_python_component.py` |
| 7 | `test(14-05): COV-EPF-001 lift transform/extract_positional_fields to 95% (padding/truncation edges)` | `tests/v1/engine/components/transform/test_extract_positional_fields.py` |
| 8 | `test(14-05): COV-ERF-001 lift transform/extract_regex_fields to 95% (invalid regex -> ConfigurationError)` | `tests/v1/engine/components/transform/test_extract_regex_fields.py` |
| 9 | `test(14-05): COV-CVT-001 lift transform/convert_type to 95% (type-coercion error paths)` | `tests/v1/engine/components/transform/test_convert_type.py` |
| 10 | `test(14-05): COV-EJF-001 lift transform/extract_json_fields to 95% (JSONPath syntax errors / missing keys)` | `tests/v1/engine/components/transform/test_extract_json_fields.py` |
| 11 | `test(14-05): COV-EDF-001 lift transform/extract_delimited_fields to 95% (inconsistent column counts)` | `tests/v1/engine/components/transform/test_extract_delimited_fields.py` |
| 12 | `test(14-05): COV-FRW-001 lift transform/filter_rows to 95% (AST parser + 14 operators + FUNCTION pre-transforms)` | `tests/v1/engine/components/transform/test_filter_rows.py` |
| 13+ (conditional) | `fix(14-05): BUG-XXX-NN <description>` -- only if real bugs surface | matching `src/v1/engine/components/transform/*.py` |

(Total: 12 + optional bug commits.)

</commit_map>
