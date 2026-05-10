---
phase: 14
plan: 04
slug: engine-database
type: execute
wave: 1
depends_on: [14-01]
files_modified:
  - tests/v1/engine/components/database/test_oracle_output.py
  - tests/v1/engine/components/database/test_oracle_row.py
  - src/v1/engine/components/database/oracle_output.py  # only if BUG surfaces
  - src/v1/engine/components/database/oracle_row.py     # only if BUG surfaces
autonomous: true
requirements: [TEST-11]
must_haves:
  truths:
    - "src/v1/engine/components/database/oracle_output.py >= 95% line coverage"
    - "src/v1/engine/components/database/oracle_row.py >= 95% line coverage"
    - "All Oracle interactions are MagicMock; no real oracledb connection (D-A6)"
    - "Phase 11 testcontainer suite (-m oracle) is unaffected and remains opt-in"
  artifacts:
    - path: tests/v1/engine/components/database/test_oracle_output.py
      provides: extended coverage for rare TABLE_ACTION x DATA_ACTION corners and ConfigurationError branches
    - path: tests/v1/engine/components/database/test_oracle_row.py
      provides: extended coverage for PARAMETER_TYPE coercion edges, USE_NB_LINE counter, executemany error paths
  key_links:
    - from: test_oracle_output.py
      to: src/v1/engine/components/database/oracle_output.py
      via: _make_mock_oracle_manager(autocommit, batch_errors) helper
    - from: test_oracle_row.py
      to: src/v1/engine/components/database/oracle_row.py
      via: MagicMock Connection/Cursor pattern
---

<objective>
Lift `oracle_output.py` (94% -> 95%, 26 missed) and `oracle_row.py` (90% -> 95%, 13 missed). Mock `oracledb` at the boundary per D-A6 (Phase 11 testcontainer suite remains the real-DB verification path -- it stays opt-in via `-m oracle` and is excluded from the gate command). Mock pattern is established at `tests/v1/engine/components/database/test_oracle_output.py:64-77` (`_make_mock_oracle_manager`).
</objective>

<scope>
- MODIFIED: `tests/v1/engine/components/database/test_oracle_output.py` -- add tests for the rare DATA_ACTION x TABLE_ACTION corners (e.g., `INSERT_OR_UPDATE` on empty input, `UPDATE` with no key columns), `ConfigurationError` branches for missing required config, identifier-quoting edge cases, REJECT-flow with mixed valid/invalid rows via `mock_cursor.getbatcherrors`.
- MODIFIED: `tests/v1/engine/components/database/test_oracle_row.py` -- add tests for PARAMETER_TYPE coercion edges (less-common Oracle types: VARCHAR2, NUMBER, DATE, TIMESTAMP, CLOB, BLOB null/empty handling), `USE_NB_LINE=true` counter when 0 rows returned, `executemany` error paths (driver raises mid-batch), `PROPAGATE_RECORD_SET` refusal raises `ComponentExecutionError` with deferred-feature message.
- POSSIBLY MODIFIED: source files -- only if a real bug surfaces.
</scope>

<out_of_scope>
- `oracle_connection.py` (already at 95%).
- Real testcontainer integration (Phase 11 owns; opt-in via `-m oracle`; excluded from gate).
- `oracledb` dependency upgrade.
- The 6 deferred Oracle components (Input, SP, BulkExec, Commit, Rollback, Close) -- v2 territory.
</out_of_scope>

<canonical_refs>
- `.planning/phases/14-coverage-push-to-95-per-module-floor/14-RESEARCH.md` §Pattern 4 (oracledb boundary mock), §Module Triage database section
- `.planning/phases/14-coverage-push-to-95-per-module-floor/14-CONTEXT.md` D-A6
- `.planning/phases/11-oracle-components/11-04-PLAN.md` (DATA_ACTION x TABLE_ACTION matrix)
- `tests/v1/engine/components/database/test_oracle_output.py:64-77` (`_make_mock_oracle_manager` reference)
- `src/v1/engine/components/database/oracle_output.py` (lift target)
- `src/v1/engine/components/database/oracle_row.py` (lift target)
- `src/v1/engine/exceptions.py`
</canonical_refs>

<waves>

## Wave 1 -- Test extensions

### Task 14-04-001 -- Extend test_oracle_output.py for rare matrix corners + ConfigurationError branches

- **Type:** test
- **Description:**
    1. `pytest tests/v1/engine/components/database/test_oracle_output.py --cov=src/v1/engine/components/database/oracle_output --cov-report=term-missing -q` -- inventory missed lines.
    2. Reuse `_make_mock_oracle_manager(autocommit, batch_errors)` factory.
    3. Add tests: INSERT_OR_UPDATE on empty DataFrame (no SQL emitted), UPDATE without key columns (ConfigurationError), DELETE with empty input (no-op + stats), DROP_AND_CREATE_TABLE + skipped DDL when already exists, REJECT flow with batcherrors covering both unique-violation and check-constraint shapes, identifier quoting around reserved words (e.g., column named `"GROUP"`).
    4. All `pytest.raises` use `ConfigurationError` / `ComponentExecutionError` per D-C4.
- **Files to create or modify:** `tests/v1/engine/components/database/test_oracle_output.py`
- **Verification command:** `python -m pytest tests/v1/engine/components/database/test_oracle_output.py --cov=src/v1/engine/components/database/oracle_output --cov-report=term-missing -q`
- **Expected outcome:** Coverage >= 95% for `oracle_output.py`; tests green.

### Task 14-04-002 -- Extend test_oracle_row.py for PARAMETER_TYPE + USE_NB_LINE + executemany error paths

- **Type:** test
- **Description:**
    1. Inventory missed lines as above.
    2. Add tests: PARAMETER_TYPE coercion for VARCHAR2/NUMBER/DATE/TIMESTAMP/CLOB/BLOB nulls + non-null edges; USE_NB_LINE=true with 0 rows returned; executemany raising `oracledb.DatabaseError` mid-batch; PROPAGATE_RECORD_SET=true raising ComponentExecutionError with the deferred-feature message; USE_EXISTING_CONNECTION=true vs ad-hoc both paths.
- **Files to create or modify:** `tests/v1/engine/components/database/test_oracle_row.py`
- **Verification command:** `python -m pytest tests/v1/engine/components/database/test_oracle_row.py --cov=src/v1/engine/components/database/oracle_row --cov-report=term-missing -q`
- **Expected outcome:** Coverage >= 95% for `oracle_row.py`; tests green.

### Task 14-04-003 -- Per-module gate verification

- **Type:** infra (verify)
- **Description:**
    ```bash
    rm -f .coverage* && python -m pytest tests/v1/engine/components/database/ -m "not oracle" -n auto \
      --cov=src/v1/engine/components/database --cov-report=json:cov_14_04.json -q
    python scripts/check_per_module_coverage.py cov_14_04.json --floor 95
    ```
- **Files to create or modify:** none persisted.
- **Verification command:** above.
- **Expected outcome:** Exit 0; PASS for `oracle_connection.py`, `oracle_output.py`, `oracle_row.py`.

</waves>

<verification_gate>

Plan 14-04 is GREEN when:
1. `oracle_output.py` and `oracle_row.py` both >= 95%.
2. Tests pass under `-m "not oracle" -n auto -q`.
3. No real oracledb connection -- all mocked.
4. ETLError-subclass exceptions in all `raises` assertions.
5. Per-module gate exits 0 for `database/`.

</verification_gate>

<commit_map>

| # | Subject | Files |
|---|---------|-------|
| 1 | `test(14-04): COV-ORA-OUT-001 oracle_output rare matrix corners + ConfigurationError branches via mocked oracledb` | `tests/v1/engine/components/database/test_oracle_output.py` |
| 2 | `test(14-04): COV-ORA-ROW-001 oracle_row PARAMETER_TYPE + USE_NB_LINE + executemany error paths via mocked oracledb` | `tests/v1/engine/components/database/test_oracle_row.py` |
| 3 (conditional) | `fix(14-04): BUG-ORA-NN <description>` -- only if bug surfaces | `src/v1/engine/components/database/oracle_*.py` |

(Total: 2-3 commits.)

</commit_map>
