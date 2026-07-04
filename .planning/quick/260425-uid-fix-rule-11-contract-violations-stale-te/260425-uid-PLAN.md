---
quick_id: 260425-uid
description: Fix Rule 11 contract violations + stale tests + add manual-component authoring guide
date: 2026-04-25
status: ready
plan_count: 1
task_count: 9
---

# Quick Task 260425-uid: Rule 11 Cleanup + Manual Authoring Guide

## Background

Phase 7.1 verifier flagged 6 components still calling `self.validate_schema()` inside `_process()` (Rule 11 violation). 4 stale tests are also calibrated to the pre-7.1 double-counting bug. This is mechanical cleanup that 7.1 deferred because the components were out of audit scope. Plus a docs file to prevent recurrence from manual (non-GSD) contributors.

## Tasks

### Task 1: Remove `self.validate_schema()` in SortRow._process

**File:** `src/v1/engine/components/transform/sort_row.py`
**Action:** grep for `self.validate_schema` in the file; delete the call line(s) inside `_process()`. BaseComponent step 7c handles validation.
**Verify:** `python -m pytest tests/v1/engine/components/transform/test_sort_row.py -q` — no new failures (the existing `test_stats_updated` failure is fixed in Task 7).
**Commit:** `fix(rule-11): remove manual validate_schema in SortRow._process — base class handles it`

### Task 2: Remove `self.validate_schema()` in RowGenerator._process

**File:** `src/v1/engine/components/transform/row_generator.py`
**Action:** grep for `self.validate_schema`; delete both call lines (~174-175).
**Verify:** `python -m pytest tests/v1/engine/components/transform/test_row_generator.py -q`.
**Commit:** `fix(rule-11): remove manual validate_schema in RowGenerator._process — base class handles it`

### Task 3: Remove `self.validate_schema()` in ExtractXmlFields._process

**File:** `src/v1/engine/components/transform/extract_xml_fields.py`
**Action:** grep for `self.validate_schema`; delete both call lines (~267-269).
**Verify:** `python -m pytest tests/v1/engine/components/transform/test_extract_xml_fields.py -q`.
**Commit:** `fix(rule-11): remove manual validate_schema in ExtractXmlFields._process — base class handles it`

### Task 4: Remove `self.validate_schema()` in SwiftBlockFormatter._process

**File:** `src/v1/engine/components/transform/swift_block_formatter.py`
**Action:** grep for `self.validate_schema`; delete the call line (~606).
**Verify:** `python -m pytest tests/v1/engine/components/transform/test_swift_block_formatter.py -q` (if test file exists).
**Commit:** `fix(rule-11): remove manual validate_schema in SwiftBlockFormatter._process — base class handles it`

### Task 5: Remove `self.validate_schema()` in ExtractDelimitedFields._process

**File:** `src/v1/engine/components/transform/extract_delimited_fields.py`
**Action:** grep for `self.validate_schema`; delete the call line (~263).
**Verify:** `python -m pytest tests/v1/engine/components/transform/test_extract_delimited_fields.py -q` (if test file exists).
**Commit:** `fix(rule-11): remove manual validate_schema in ExtractDelimitedFields._process — base class handles it`

### Task 6: Remove `self.validate_schema()` in FileInputPositional._process

**File:** `src/v1/engine/components/file/file_input_positional.py`
**Action:** grep for `self.validate_schema`; delete the call line (~300).
**Verify:** `python -m pytest tests/v1/engine/components/file/test_file_input_positional.py -q` (if test file exists).
**Commit:** `fix(rule-11): remove manual validate_schema in FileInputPositional._process — base class handles it`

### Task 7: Update 4 stale test assertions (post-7.1 contract)

**Files:**
- `tests/v1/engine/components/transform/test_filter_columns.py` (2 tests)
- `tests/v1/engine/components/transform/test_sort_row.py` (1 test)
- `tests/v1/engine/components/transform/test_unite.py` (1 test)

**Action:**
- `test_filter_columns.py::TestEdgeCases::test_stats_updated`: change `== 4` → `== 2` (NB_LINE and NB_LINE_OK). Update inline comment that documents old "_update_stats called twice" math.
- `test_sort_row.py::TestEdgeCases::test_stats_updated`: change `== 8` → `== 4`. Update inline comment.
- `test_unite.py::TestEdgeCases::test_stats_updated`: change `== 6` → `== 3`. Update inline comment.
- `test_filter_columns.py::TestSchemaFiltering::test_schema_column_not_in_input`: change assertion from `== ["a", "b"]` to `== ["a", "b", "z"]`. Add: assert `result["main"]["z"]` is null-filled. Add: assert the warning was logged via `caplog`.

**Verify:** `python -m pytest tests/v1/engine/components/transform/test_filter_columns.py tests/v1/engine/components/transform/test_sort_row.py tests/v1/engine/components/transform/test_unite.py -v` — all pass.

**Commit:** `test(rule-11): update test assertions to match corrected BaseComponent stats and schema contract (post 07.1)`

### Task 8: Add docs/v1/standards/MANUAL_COMPONENT_AUTHORING.md

**File:** `docs/v1/standards/MANUAL_COMPONENT_AUTHORING.md` (new)
**Action:** Write a 200-300 line guide for contributors authoring components OUTSIDE the GSD workflow. Required sections:
- Why this doc exists (link to phase 7.1 lessons)
- Required reading (ENGINE_COMPONENT_PATTERN.md, ENGINE_TEST_PATTERN.md, converter CLAUDE.md)
- The 11 rules of BaseComponent subclassing — extracted from ENGINE_COMPONENT_PATTERN.md as imperatives. Rule 11 (no manual validate_schema in _process) gets a bold callout.
- Stats lifecycle (BaseComponent owns stats; show double-count anti-pattern)
- treat_empty_as_null per-column behavior (numeric/datetime/Decimal default True; str default False)
- die_on_error reject routing (SCHEMA_VIOLATION when die_on_error=False)
- Per-chunk streaming (auto-selection rules; what _process must NOT assume)
- Java/Groovy expressions (`{{java}}` markers, bridge sync timing)
- Talend-parity is non-negotiable (link to PROJECT.md core value)
- Test patterns (RED-before-GREEN, edge cases, real Java bridge not mocks)
- PR checklist (full suite ran? regression test added? no double-count? no manual validate_schema?)

**Verify:** File exists, formatted as Markdown, sections present.
**Commit:** `docs(standards): add manual component authoring guide to prevent contract violations from non-GSD contributors`

### Task 9: Final regression sweep + push

**Action:**
- Run full Python engine test suite: `python -m pytest tests/v1/engine/ -q`. Confirm 0 failures (or only the pre-existing converter failure noted in 7.1 verification).
- Run Java tests: `cd src/v1/java_bridge/java && mvn test -q && cd -`. Confirm BUILD SUCCESS.
- `git push origin feature/engine-restructure`

**Verify:** All tests green; push succeeds.
**Commit:** N/A (push only — no new commits)

## Must-Haves

- All 6 components no longer call `self.validate_schema()` inside `_process()` (grep returns empty)
- 4 previously-failing tests now pass with corrected assertions
- `docs/v1/standards/MANUAL_COMPONENT_AUTHORING.md` exists and is well-formed
- Full Python test suite passes (0 failures or only pre-existing converter failure)
- mvn test passes
- Branch pushed to origin
