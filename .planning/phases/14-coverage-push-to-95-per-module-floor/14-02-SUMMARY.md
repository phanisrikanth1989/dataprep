---
phase: 14
plan: 02
slug: engine-aggregate
subsystem: engine-aggregate
tags: [coverage-lift, aggregate-row, talend-parity, dead-code-deletion, bug-fix]
status: complete
completed: 2026-05-10
duration_minutes: ~35
tasks_total: 2
tasks_completed: 2
commits_total: 3
requires:
  - "14-01-SUMMARY.md (root tests/conftest.py + per-module floor script + pyproject coverage config)"
  - "13-COVERAGE-BASELINE.md (per-module floor reference -- aggregate_row baseline 79%)"
provides:
  - "src/v1/engine/components/aggregate/aggregate_row.py at 100% line coverage (199 stmts, 0 missed)"
  - "tests/v1/engine/components/aggregate/test_aggregate_row.py: 4 new test classes (TestDecimalHelpers, TestNullPropagationStringFunctions, TestFinancialPrecisionExtended, TestValidationExtended) -- 33 new tests"
  - "BUG-AGG-001 root-cause fix: list / list_object / union under ignore_null=False crashed on null-bearing input (silent regression since Phase 6)"
  - "Two D-C5 dead-code deletions: _build_agg_func unknown-function fallback (silent default-to-sum -> explicit ConfigurationError); _process column-ordering safety loop (unreachable)"
affects:
  - "src/v1/engine/components/aggregate/aggregate_row.py: stmts 203 -> 199 (4 dead lines removed); coverage 79% -> 100%"
  - "src/v1/engine/components/transform/aggregate_sorted_row.py: re-uses _build_agg_func; the stricter unknown-function contract (raise vs default) hardens it too -- _validate_config there already gates the same _SUPPORTED_FUNCTIONS set, so no behavior change for valid configs"
tech_stack_added: []
tech_stack_patterns:
  - "Direct unit testing of module-level helper functions (D-C1 pure-pandas pattern) -- _to_decimal, _decimal_mean, _decimal_std exposed for targeted edge-case testing without going through the full BaseComponent.execute() lifecycle"
  - "Talend-parity null token: pandas Series.fillna('null').astype(str) replicates Java's String.valueOf(null) == 'null' for list aggregator output"
  - "D-C5 dead-code-deletion as a quality lift mechanism (3 unreachable lines removed instead of 3 # pragma: no cover annotations)"
key_files_created: []
key_files_modified:
  - src/v1/engine/components/aggregate/aggregate_row.py
  - tests/v1/engine/components/aggregate/test_aggregate_row.py
decisions:
  - "BUG-AGG-001 fixed via fillna('null').astype(str) -- root-cause source fix at the lambdas, no defensive shim downstream (matches project memory 'fix source, no fallbacks')"
  - "Null token = 'null' (lowercase, Java parity) not 'nan' (pandas default) -- Talend tAggregateRow uses Java's ArrayList.toString() which writes 'null' for null elements"
  - "_build_agg_func unknown-function fallback removed (D-C5); replaced with explicit ConfigurationError so a future _validate_config regression surfaces immediately rather than silently producing wrong-aggregator output"
  - "_process column-ordering 'remaining columns' safety loop removed (D-C5) -- result columns are guaranteed by groupby + pd.NamedAgg construction; the prior 'shouldn't happen, but safety' comment was an honest admission of dead code"
  - "Test for the new _build_agg_func raise calls the helper directly (bypassing _validate_config) -- it is a regression contract guard, not coverage of an in-flow path"
metrics:
  duration_minutes: ~35
  baseline_pct: 79
  achieved_pct: 100
  stmts_before: 203
  stmts_after: 199
  missed_before: 43
  missed_after: 0
  new_tests: 33
  total_tests_in_file: 81
  bugs_fixed: 1
  dead_code_lines_deleted: 4
---

# Phase 14 Plan 02: Engine Aggregate Subsystem Coverage Lift Summary

**One-liner:** Lifted `src/v1/engine/components/aggregate/aggregate_row.py` from 79% to 100% line coverage by extending the existing test file with 33 new tests across 4 test classes (Decimal helpers / null-token list aggregators / financial-precision extended / validation extended), root-cause-fixing one real silent bug surfaced during test writing (BUG-AGG-001: list / list_object / union with ignore_null=False crashed on any null-bearing input because pandas `Series.astype(str)` does not coerce NaN to a string), and deleting two unreachable code paths under D-C5 (the `_build_agg_func` unknown-function silent-default-to-sum fallback and the `_process` column-ordering "remaining columns" safety loop).

## What Was Built

### Test additions (`tests/v1/engine/components/aggregate/test_aggregate_row.py`)

Four new test classes, 33 new tests total. All assertions use ETLError-subclass exceptions (D-C4); all DataFrames use realistic dtype mixes (Decimal object, object with np.nan, float64).

| Class | Lines covered (in source) | Tests | Notes |
|-------|---------------------------|-------|-------|
| `TestDecimalHelpers` | 45, 48-49, 72, 88, 96 | 11 | Direct unit tests of `_to_decimal` / `_decimal_mean` / `_decimal_std` edge paths (None/NaN, parse-error, empty series, mean=None propagation, n<=ddof). Pure helper functions = D-C1 unit-test natural fit. |
| `TestNullPropagationStringFunctions` | 144, 155, 165 | 3 | `ignore_null=False` branches of `list` / `list_object` / `union` with object-dtype + np.nan input. Asserts the BUG-AGG-001 fix: null is preserved as the literal `"null"` token. |
| `TestFinancialPrecisionExtended` | 192, 196, 200, 202-238 | 14 | Decimal-precision branches for `population_std_dev`, `variance`, `min`, `max` (skipna and not-skipna); plus NaN-propagation for `sum`, `avg`, `std`. Realistic Decimal-flavored DataFrames. |
| `TestValidationExtended` | 299, 303 + new 264-272 raise | 5 | `op` not a dict (line 299); missing `'function'` key (line 303); ETLError subclass invariant; direct call to `_build_agg_func` with unknown function name (regression guard for the D-C5 explicit-ConfigurationError replacing the silent fallback). |

Module-level helpers (`_to_decimal`, `_decimal_mean`, `_decimal_std`, `_build_agg_func`) imported alongside `AggregateRow` to enable direct unit tests of helper edge cases without the full `BaseComponent.execute()` lifecycle.

### Source changes (`src/v1/engine/components/aggregate/aggregate_row.py`)

#### BUG-AGG-001 fix (commit `2aebd30`)

Three lambdas changed -- `list` / `list_object` / `union` ignore_null=False branches:

```python
# Before (broken on null-bearing input):
return lambda x: list_delimiter.join(x.astype(str))

# After (Talend-parity null token):
return lambda x: list_delimiter.join(x.fillna("null").astype(str))
```

`pandas.Series.astype(str)` does NOT coerce NaN/None to a string -- it leaves them as floats, so `str.join()` raises `"sequence item N: expected str instance, float found"`. The `ignore_null=False` branches of `list` / `list_object` / `union` were therefore broken for any null-bearing input. The bug existed since Phase 6 (CR-05-bis) and was not surfaced by existing tests because all prior tests passed null-free input through these aggregators.

Root-cause fix at source: `fillna("null")` before `astype(str)`. The `"null"` token matches Java's `String.valueOf(null)` semantics (which is what Talend's `ArrayList.toString()` over a list with a null element produces -- `"[a, null, b]"`). No defensive shim downstream -- per project policy "fix source, no fallbacks".

#### D-C5 dead-code deletions (commit `c602719`)

1. **`_build_agg_func` unknown-function fallback** (was lines 257-259):
   - Was: `logger.warning(...) ; return lambda x: x.sum(skipna=skipna)`
   - Now: `raise ConfigurationError(f"Unsupported aggregation function ... validation gate has regressed")`
   - Unreachable because both `AggregateRow._validate_config` and `AggregateSortedRow._validate_config` (the only two callers) reject any `func` not in `_SUPPORTED_FUNCTIONS` before `_build_agg_func` is ever called. The silent-default-to-sum was a footgun: a future validation-gate regression would silently produce wrong-aggregator results. The explicit raise surfaces the contract violation immediately.

2. **`_process` column-ordering "remaining columns" safety loop** (was lines 384-387):
   - Was: `for col in result.columns: if col not in ordered_cols: ordered_cols.append(col)`
   - Now: removed entirely.
   - Unreachable because `result` is constructed entirely from `groupby(...).reset_index()` (which adds `group_output_cols`) and `pd.NamedAgg` (which adds `op_output_order`). Every column in `result.columns` is guaranteed to be in one of those two source lists. The prior `# shouldn't happen, but safety` comment was an honest admission the branch was dead.

Net statement count: 203 -> 199 (4 dead lines removed, 199 stmts now exercised at 100% coverage).

## Tasks Completed

| Task | Status | Commit |
|------|--------|--------|
| 14-02-001 (inventory missed lines + write extension tests) | done | covered by `2aebd30` (BUG fix) + `c602719` (D-C5 deletions) + `aa281e8` (tests) |
| 14-02-002 (verify per-module floor for this plan) | done | gate run: PASS (no commit -- cov_14_02.json is ephemeral, cleaned up) |

Total commits: **3** (`2aebd30`, `c602719`, `aa281e8`). Plan's commit_map estimated 1-2 commits; landed at 3 because:
- A real bug surfaced during test writing -> separate `fix` commit (BUG-AGG-001).
- D-C5 dead-code deletions warranted a separate `refactor` commit (different intent than `fix` per CLAUDE.md commit-type table).
- Test extensions in their own `test` commit per the plan's commit_map.

## Verification Evidence

```
$ python -m pytest tests/v1/engine/components/aggregate/test_aggregate_row.py \
    --cov=src/v1/engine/components/aggregate --cov-report=term-missing -q
... 81 passed in 0.33s
src/v1/engine/components/aggregate/aggregate_row.py     199      0  100.0%
```

```
$ rm -f .coverage cov_14_02.json
$ python -m pytest tests/v1/engine/components/aggregate/ -n auto \
    --cov=src/v1/engine/components/aggregate \
    --cov-report=json:cov_14_02.json -q
... 123 passed in 2.61s
$ python scripts/check_per_module_coverage.py cov_14_02.json --floor 95
PASS: all 2 in-scope modules at >= 95.0% line coverage
EXIT=0
```

```
$ python -m pytest tests/v1/engine/components/aggregate/ \
    tests/v1/engine/components/transform/test_aggregate_sorted_row.py -q
... 167 passed in 0.23s
```

(Sibling `aggregate_sorted_row.py` -- the only other consumer of `_build_agg_func` -- still passes after the D-C5 deletion of the silent fallback.)

## Verification Gate (from PLAN.md)

1. **`aggregate_row.py` reports >= 95% line coverage** -- ACHIEVED at **100%** (199/199 stmts).
2. **All tests in `test_aggregate_row.py` pass under `pytest -m "not oracle" -n auto -q`** -- 81 passed, 0 failed.
3. **No new `# pragma: no cover` outside D-C3 allowlist** -- VERIFIED (zero pragmas added; the two newly-uncovered lines were instead deleted under D-C5).
4. **All `pytest.raises` assertions use ETLError subclasses, never bare `Exception`** -- VERIFIED (TestValidationExtended uses `ConfigurationError`; existing classes use `ConfigurationError`).
5. **Per-module gate script exits 0 for `src/v1/engine/components/aggregate/`** -- VERIFIED (`PASS: all 2 in-scope modules at >= 95.0%`).

All five gate criteria GREEN. Plan 14-02 complete.

## Deviations from Plan

### [Rule 1 - Bug] BUG-AGG-001: list/list_object/union ignore_null=False crashed on null-bearing input

- **Found during:** Task 14-02-001 (writing `TestNullPropagationStringFunctions` tests for missed lines 144, 155, 165).
- **Issue:** First test run failed with `TypeError: '<' not supported between instances of 'str' and 'float'` (union) and `TypeError: sequence item N: expected str instance, float found` (list, list_object). Direct repro confirmed `pd.Series(['x', np.nan, 'y']).astype(str)` returns an object Series with the np.nan still as a float -- not stringified to `"nan"`. So `","join(...)` and `sorted(set(...))` both crash on any null-bearing input under `ignore_null=False`. The bug existed since Phase 6 (CR-05-bis) and was not surfaced by existing tests because no prior test passed null-bearing input through these three aggregators with `ignore_null=False`.
- **Fix:** Three lambdas updated to call `.fillna("null")` before `.astype(str)`. The `"null"` token matches Java's `String.valueOf(null)` -- which is exactly what Talend's `ArrayList.toString()` emits when the underlying list has null elements. No defensive shim downstream; root-cause fix at source per project policy.
- **Files modified:** `src/v1/engine/components/aggregate/aggregate_row.py` (3 lambdas, lines 144 / 155 / 165).
- **Commit:** `2aebd30`.

### [Rule 1 - Bug, D-C5] Dead-code deletions in `aggregate_row.py`

- **Found during:** Task 14-02-001 (after BUG-AGG-001 fix, two lines remained uncovered: 258-259 unknown-function fallback and 387 column-ordering safety).
- **Issue:** Both branches were unreachable in any in-flow code path:
  1. Lines 258-259 -- `_build_agg_func` unknown-function fallback: `_validate_config` (and `AggregateSortedRow._validate_config`) rejects any `func` not in `_SUPPORTED_FUNCTIONS` first. The fallback would silently default to `sum` and produce wrong-aggregator output if the validation gate ever regressed.
  2. Line 387 -- `_process` "remaining columns" safety loop: `result` is built entirely from `groupby(...).reset_index()` and `pd.NamedAgg`, so every column in `result.columns` is guaranteed to be in `group_output_cols + op_output_order`.
- **Fix:** Per Phase 14 D-C5 ("delete dead branch over pragma-or-fake-test") and project memory ("fix source, no fallbacks"), both branches deleted. The `_build_agg_func` fallback was replaced with an explicit `ConfigurationError` raise (so a future validation-gate regression surfaces immediately rather than silently); the column-ordering safety loop was removed entirely.
- **Files modified:** `src/v1/engine/components/aggregate/aggregate_row.py`.
- **Commit:** `c602719`.

### [Test design adjustment] StringDtype substituted with object-dtype + np.nan for list/union null tests

- **Found during:** Task 14-02-001 (initial null-token tests used `pd.array([..., None], dtype="string")` to honor D-C4's "realistic dtypes" call-out, but `pd.NA` does not sort against str under `sorted(set(...))` -- raises `TypeError: '<' not supported between instances of 'str' and 'NAType'`).
- **Resolution:** Object-dtype + `np.nan` is the natural Talend-parity shape for these aggregators -- Java treats null elements via `String.valueOf` which yields `"null"`, and `pandas.Series.fillna("null")` works on both object-dtype and float-dtype Series. The Decimal-precision tests still use realistic Decimal object dtype per D-C4. StringDtype is exercised by other plans in this phase where applicable.
- **Files modified:** `tests/v1/engine/components/aggregate/test_aggregate_row.py` (test fixtures only).
- **Commit:** `aa281e8`.

No other deviations. The plan's stated approach (extend the existing test file with edge-case tests, fix any bugs at source, delete dead code per D-C5) was followed exactly.

## Self-Check: PASSED

**Files verified to exist:**
- `tests/v1/engine/components/aggregate/test_aggregate_row.py` -- FOUND (81 tests, 4 new classes added)
- `src/v1/engine/components/aggregate/aggregate_row.py` -- FOUND (199 stmts, 0 missed at 100% coverage)

**Commits verified to exist (range d444ad0..HEAD):**
- `2aebd30` fix(14-02): BUG-AGG-001 list/list_object/union ignore_null=False crashed on null-bearing input -- FOUND
- `c602719` refactor(14-02): COV-AGG-002 D-C5 dead-code deletion in aggregate_row -- FOUND
- `aa281e8` test(14-02): COV-AGG-001 extend aggregate_row tests for Decimal helpers, null-token list/list_object/union, financial-precision min/max/variance/pop_std_dev, validation extensions -- FOUND

**Verification gate (from PLAN.md):**
1. aggregate_row.py >= 95% line coverage -- ACHIEVED 100% (199/199)
2. All tests pass -- 81 passed in test file; 167 passed across aggregate + aggregate_sorted_row siblings
3. No new pragmas -- VERIFIED (zero pragmas added; D-C5 deletions instead)
4. All raises use ETLError subclasses -- VERIFIED (ConfigurationError throughout)
5. Per-module gate exits 0 -- VERIFIED (PASS: all 2 in-scope modules)
6. ASCII-only logs -- VERIFIED (no emojis/unicode added)
7. No `inplace=True` -- VERIFIED (only `fillna("null")` chained, no in-place mutation)

All seven gate criteria GREEN. Plan 14-02 complete.
