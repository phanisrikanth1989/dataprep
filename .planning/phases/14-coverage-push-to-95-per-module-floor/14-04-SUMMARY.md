---
phase: 14
plan: 04
subsystem: testing
tags: [coverage, oracle, mocked-oracledb, parameter-coercion, configuration-error-paths, ddl-emission]
status: complete
completed: 2026-05-10
duration_minutes: ~30
tasks_total: 3
tasks_completed: 3
commits_total: 2
requires:
  - phase: 14
    provides: "14-01 pipeline-test infrastructure (scripts/check_per_module_coverage.py, pyproject [tool.coverage])"
  - phase: 11
    provides: "oracle_output.py / oracle_row.py with the _make_mock_oracle_manager pattern"
provides:
  - "oracle_output.py 94.1% -> 99.5% line coverage (only optional-import shim 784-785 missed)"
  - "oracle_row.py 90.3% -> 100.0% line coverage"
  - "Per-module gate PASS for src/v1/engine/components/database/ (3/3 modules >= 95%)"
  - "Reference test patterns: oracledb DB_TYPE_* attribute lookup; PARAMETER_TYPE non-str-input edges; cleanup-raises-swallowed pattern"
affects:
  - "Future Oracle component plans (Input, SP, BulkExec, Commit, Rollback, Close): same _make_mock_oracle_manager + DB_TYPE_* import pattern"
  - "Plan 14-13 closeout: database subsystem locked at PASS"
tech_stack_added: []
tech_stack_patterns:
  - "Direct oracledb.DB_TYPE_* attribute lookup in tests (resilient to type-class identity changes across oracledb versions)"
  - "FakeDatabaseError stand-in for oracledb.DatabaseError in mid-batch error simulation"
  - "Scalar fetchall variant test for upsert (some drivers return raw scalars for single-column SELECTs)"
key_files_created: []
key_files_modified:
  - tests/v1/engine/components/database/test_oracle_output.py
  - tests/v1/engine/components/database/test_oracle_row.py
key-decisions:
  - "Did not pragma the optional `import oracledb` shim at oracle_output.py:784-785; coverage already at 99.5% so the floor is met without touching source"
  - "Did not modify any source files (no BUG-* surfaced); plan 11-04 / 11-03 contracts hold"
  - "Used direct oracledb attribute lookup for DB_TYPE_CLOB / DB_TYPE_TIMESTAMP / DB_TYPE_DATE / DB_TYPE_RAW / DB_TYPE_BLOB rather than identity assertions on patched constants -- more robust to future oracledb upgrades"
  - "Locked the FakeDatabaseError pattern as the canonical mock for mid-batch driver errors (oracledb.DatabaseError can't be raised directly without a real connection context)"
patterns-established:
  - "DB_TYPE_* attribute-lookup test pattern: import oracledb in the test; assert sizes[i] is oracledb.DB_TYPE_X. Resilient across oracledb versions."
  - "Cleanup-raises-swallowed assertion pattern: side_effect=RuntimeError on cursor.close / oracle_manager.close + caplog.WARNING capture + assert no re-raise."
  - "Scalar-row fetchall fallback test: drivers may return [val, val] vs [(val,), (val,)] -- our code wraps the scalar form into singleton tuples (line 665) and the test verifies upsert stats unchanged."
requirements_completed: [TEST-11]
metrics:
  duration_minutes: ~30
  oracle_output_pct_before: 94.1
  oracle_output_pct_after: 99.5
  oracle_row_pct_before: 90.3
  oracle_row_pct_after: 100.0
  oracle_connection_pct: 100.0
  per_module_gate: PASS
  modules_in_database_subsystem: 3
  tests_added_oracle_output: 24
  tests_added_oracle_row: 16
---

# Phase 14 Plan 04: Engine Database Subsystem Summary

**Lifted `oracle_output.py` 94.1% -> 99.5% and `oracle_row.py` 90.3% -> 100.0% line coverage via 40 new MagicMock-based tests covering rare TABLE_ACTION x DATA_ACTION corners, ConfigurationError branches, `_build_input_sizes` type-mapping branches, PARAMETER_TYPE coercion edges (datetime/date/time/bytes non-str inputs), USE_NB_LINE counter for valid 0-rowcount queries, mid-batch DatabaseError propagation, and cleanup-error-swallowing on cursor/manager close.** No source files modified -- contracts from Phase 11 plans 11-03 and 11-04 hold; no BUG-* surfaced.

## Performance

- **Duration:** ~30 min
- **Started:** 2026-05-10T17:13Z
- **Completed:** 2026-05-10T17:43Z
- **Tasks:** 3 of 3
- **Files modified:** 2

## Accomplishments

- `oracle_output.py` 94.1% -> 99.5% line coverage (24 new test methods)
- `oracle_row.py` 90.3% -> 100.0% line coverage (16 new test methods)
- Per-module gate PASS for `src/v1/engine/components/database/` (3/3 modules >= 95%; the third, `oracle_connection.py`, was already at 100% from Phase 11)
- Phase 11 testcontainer suite (`tests/v1/engine/components/database/integration/`) still gracefully skips at collection-time when `testcontainers` isn't installed -- opt-in via `-m oracle` is unaffected
- All Oracle interactions remain MagicMock per D-A6; zero live `oracledb` connections in unit tests

## Task Commits

1. **Task 14-04-001: Extend `test_oracle_output.py` for rare matrix corners + ConfigurationError branches** - `d54b5c1` (test)
2. **Task 14-04-002: Extend `test_oracle_row.py` for PARAMETER_TYPE + USE_NB_LINE + executemany error paths** - `43d0b54` (test)
3. **Task 14-04-003: Per-module gate verification** - no commit (verification-only; produced PASS line for database subsystem)

## Files Created/Modified

- `tests/v1/engine/components/database/test_oracle_output.py` - +353 LOC across 9 new test classes (`TestDdlTypeMappingByteAndBlob`, `TestEmptyInsertableUpdatable`, `TestUpsertScalarFetchallRow`, `TestBuildInputSizes`, `TestUseBatchSizeFalse`, `TestPreCommitAfterTableAction`, `TestCleanupSwallowsErrors`, `TestReservedWordIdentifierQuoting`)
- `tests/v1/engine/components/database/test_oracle_row.py` - +325 LOC across 6 new test classes (`TestParameterTypeCoercionDateEdges`, `TestUseNbLineWithZeroRows`, `TestExecuteMidBatchError`, `TestCleanupSwallowsErrors`, `TestPreparedStatementWithNullParameter`, `TestUseExistingConnectionVsAdHocBindShape`)

## Coverage Inventory (post-lift)

| Module | Before | After | Missing Lines (after) |
|--------|-------:|------:|-----------------------|
| `oracle_output.py` | 94.1% | 99.5% | `[784, 785]` -- optional `import oracledb` shim (D-C3 allowlist; not pragma'd because the 95% floor is already met) |
| `oracle_row.py` | 90.3% | 100.0% | -- |
| `oracle_connection.py` | 100.0% | 100.0% | -- |

Per-module gate command run: `python scripts/check_per_module_coverage.py cov_14_04.json --floor 95` -> `PASS: all 3 in-scope modules at >= 95.0% line coverage`.

## Specific Lines Lifted

### `oracle_output.py`

- **Line 156** `byte` schema type -> `NUMBER(3)` DDL (`TestDdlTypeMappingByteAndBlob.test_byte_maps_to_number_3`)
- **Line 426** INSERT with no insertable columns raises `ConfigurationError` (`TestEmptyInsertableUpdatable.test_insert_with_no_insertable_columns_raises`)
- **Line 451** UPDATE with no updatable columns raises `ConfigurationError` (`TestEmptyInsertableUpdatable.test_update_with_no_updatable_columns_raises`)
- **Line 504** `_build_pk_select_sql` with empty `pk_cols` raises `ConfigurationError` (`TestEmptyInsertableUpdatable.test_pk_select_empty_pk_raises`)
- **Line 665** Upsert SELECT scalar-row branch (`matched_keys.add((row,))`) (`TestUpsertScalarFetchallRow`)
- **Line 794** `_build_input_sizes` with unknown data_action returns `[]` (`TestBuildInputSizes.test_unknown_data_action_returns_empty`)
- **Lines 810-812** `str` len > 4000 / no length -> `oracledb.DB_TYPE_CLOB`; datetime -> `DB_TYPE_TIMESTAMP` or `DB_TYPE_DATE` per `use_timestamp_for_date_type` (`TestBuildInputSizes` cluster)
- **Lines 815-819** `bytes` short -> `DB_TYPE_RAW`, long -> `DB_TYPE_BLOB`
- **Line 821** unknown ctype falls back to `None` placeholder
- **Lines 910-912** `use_batch_size=False` treats whole DF as single batch; empty DF defensive `batch_size = 10000` fallback (`TestUseBatchSizeFalse`)
- **Line 919** Pre-DDL commit when `table_action != "NONE"` and `not autocommit` (`TestPreCommitAfterTableAction`)
- **Lines 1042-1043, 1047-1048** `cursor.close()` / `oracle_manager.close()` exceptions swallowed and logged WARNING (`TestCleanupSwallowsErrors`)

### `oracle_row.py`

- **Line 134** `_coerce_date(datetime)` -> `v.date()` (datetime input path, distinct from str/ISO)
- **Line 136** `_coerce_date(date)` -> identity returned
- **Line 139** `_coerce_date(int)` -> `ValueError`
- **Line 152** `_coerce_timestamp(datetime)` -> identity returned
- **Line 155** `_coerce_timestamp(int)` -> `ValueError`
- **Line 167** `_coerce_time(time)` -> identity returned
- **Line 170** `_coerce_time(int)` -> `ValueError`
- **Line 183** `_coerce_bytes(bytes)` -> identity returned (also exercised via `Blob` PARAMETER_TYPE)
- **Line 186** `_coerce_bytes(int)` -> `ValueError`
- **Lines 429-430** `cursor.close()` raise swallowed and logged WARNING (`TestCleanupSwallowsErrors.test_cursor_close_failure_logged_not_raised`)
- **Lines 434-435** `oracle_manager.close()` raise swallowed and logged WARNING (`TestCleanupSwallowsErrors.test_manager_close_failure_logged_not_raised`)

## Decisions Made

- **No source modifications.** Coverage gaps were genuine missing-test-cases rather than dead code. Each newly-covered branch is a real production code path (e.g., `byte` schema column -> NUMBER(3); cleanup raises must not mask original SQL exceptions; non-str datetime/date/time inputs to PARAMETER_TYPE coercers are valid Talend converter outputs). No BUG-* surfaced; no D-C5 dead-code deletions warranted.
- **No pragma added at `oracle_output.py:784-785`.** The optional `import oracledb` shim is in the D-C3 allowlist and could be tagged `# pragma: no cover`, but the per-module floor (95%) is already exceeded at 99.5%. Adding a pragma would be cosmetic; we leave the source untouched per "rewrite over patch" + minimum-source-change posture.
- **Direct `oracledb.DB_TYPE_*` attribute lookup in tests (not patched constants).** Future oracledb upgrades may re-identity their type classes; using the live attribute lookup makes the assertion compatible across versions while still verifying the correct constant is bound.
- **`FakeDatabaseError` for mid-batch error simulation.** Direct `oracledb.DatabaseError` instantiation isn't reliable without a real connection context; a stand-in subclass of `Exception` proves the propagation+cleanup contract without needing a live driver path.

## Deviations from Plan

None - plan executed exactly as written. Plan's commit_map called for "2-3 commits"; landed at 2 because no BUG-* surfaced. Task 14-04-003 was verification-only (per plan's "Files to create or modify: none persisted").

## Issues Encountered

- Initial `--cov=src/v1/engine/components/database/oracle_output` (filesystem path) and `--cov=src.v1.engine.components.database.oracle_output` (dotted module name) both failed: the former produced `module-not-imported` warnings (coverage didn't track it via pyproject's source list), and the latter triggered a `numpy ImportError: cannot load module more than once per process` collision with cached coverage state. **Resolution:** ran the full pyproject `[tool.coverage.run] source = [...]` set via plain `--cov` (no path), wrote JSON, and parsed with stdlib to extract the per-module rows. This matched Phase 14-01's gate-command pattern.

## Self-Check: PASSED

**Files verified to exist:**

```
$ [ -f tests/v1/engine/components/database/test_oracle_output.py ] && echo FOUND
FOUND
$ [ -f tests/v1/engine/components/database/test_oracle_row.py ] && echo FOUND
FOUND
```

**Commits verified to exist:**

```
$ git log --oneline | grep -E "d54b5c1|43d0b54"
43d0b54 test(14-04): COV-ORA-ROW-001 oracle_row PARAMETER_TYPE + USE_NB_LINE + executemany error paths via mocked oracledb
d54b5c1 test(14-04): COV-ORA-OUT-001 oracle_output rare matrix corners + ConfigurationError branches via mocked oracledb
```

**Verification gate (from PLAN.md):**

1. `oracle_output.py` >= 95% -- 99.5% PASS
2. `oracle_row.py` >= 95% -- 100.0% PASS
3. Tests pass under `-m "not oracle" -n auto -q` -- 219 passed, 1 skipped PASS
4. No real oracledb connection -- all interactions are MagicMock per D-A6 PASS
5. ETLError-subclass exceptions in all `raises` assertions (`ConfigurationError`, `DataValidationError`) -- PASS (the FakeDatabaseError test asserts a non-ETLError on the driver-error propagation path, which is the correct contract: tOracleRow lets driver exceptions bubble up unchanged so the engine's outer `_execute_component` handler sees them)
6. Per-module gate exits 0 for `database/` -- `PASS: all 3 in-scope modules at >= 95.0%` PASS

All six verification-gate criteria GREEN. Plan 14-04 complete.

## Next Phase Readiness

- Database subsystem locked at the 95% per-module floor (3/3 modules PASS)
- Oracle component test patterns documented in this Summary's Patterns Established section -- reusable for the deferred 6 Oracle components (Input, SP, BulkExec, Commit, Rollback, Close) when they ship in v2
- Plan 14-05 (next) will use the same `_make_mock_oracle_manager` + `_make_upsert_mock_manager` factories already in place for any further database additions
- No blockers; ready to advance to Plan 14-05

---
*Phase: 14-coverage-push-to-95-per-module-floor*
*Plan: 04 (engine-database)*
*Completed: 2026-05-10*
