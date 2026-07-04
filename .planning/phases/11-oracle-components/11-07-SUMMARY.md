---
phase: 11-oracle-components
plan: 07
subsystem: testing
tags: [integration, oracle, testcontainers, gvenzl, pytest, verification-gate, D-D3, D-F4]
requires:
  - phase: 11-01
    provides: "OracleConnectionManager + @pytest.mark.oracle marker registration"
  - phase: 11-02
    provides: "OracleConnection engine component (SID/SERVICE_NAME/RAC open paths)"
  - phase: 11-03
    provides: "OracleRow engine component (prepared statements, USE_NB_LINE counter, DDL execution)"
  - phase: 11-04
    provides: "OracleOutput engine component (type round-trip, REJECT batcherrors, DDL emission)"
  - phase: 11-05
    provides: "OracleOutput batched 2-statement INSERT_OR_UPDATE / UPDATE_OR_INSERT upsert"
  - phase: 11-06
    provides: "Wallet/OCI conditional needs_review on the 3 in-scope Oracle converters"
provides:
  - "@pytest.mark.oracle integration test suite (~32 tests across 4 e2e files) exercising plans 11-01..06 against a real gvenzl/oracle-free:23-slim-faststart testcontainer"
  - "Session-scoped oracle_container conftest fixture with skip-on-missing-resource behavior (testcontainers not installed / SKIP_ORACLE_CONTAINER / Docker not running -> pytest.skip)"
  - "Phase 11 verification gate documentation (11-VERIFICATION.md) per D-D3 / D-F4: mocks lie -- one real-DB run is mandatory before Phase 11 is marked verified"
  - "Sample-driven E2E for the 3 Phase 11 .item fixtures (Job_tOracleConnection / Job_tOracleRow / Job_tOracleOutput) using the canonical Phase 10 pattern (convert_job + JSON mutation + ETLEngine)"
affects:
  - "Phase 11 close-out: 11-PHASE-SUMMARY.md cannot be written until the deferred gate run is green"
  - "Future Oracle plans (oracle_input, oracle_sp, oracle_bulk_exec, oracle_commit, oracle_rollback, oracle_close) inherit the integration directory + conftest pattern"
tech-stack:
  added:
    - "testcontainers-python (OracleDbContainer)"
    - "gvenzl/oracle-free:23-slim-faststart Docker image (Oracle-blessed FREE 23ai)"
  patterns:
    - "Session-scoped DB container + per-test temp_table fixture with PYTEST_T_<random> uniqueness + explicit DROP teardown (RESEARCH.md test isolation strategy)"
    - "Skip-on-missing-resource for optional integration deps (mirrors tests/integration/conftest.py:62-66)"
    - "Sample-driven E2E pattern: convert .item -> JSON -> _mutate_json_paths -> ETLEngine (mirror of tests/integration/test_iterate_e2e.py)"
    - "Phase verification gate as a checked-in document (11-VERIFICATION.md) -- not just a checklist in CONTEXT.md"
key-files:
  created:
    - "tests/v1/engine/components/database/integration/__init__.py"
    - "tests/v1/engine/components/database/integration/conftest.py"
    - "tests/v1/engine/components/database/integration/test_oracle_connection_e2e.py"
    - "tests/v1/engine/components/database/integration/test_oracle_row_e2e.py"
    - "tests/v1/engine/components/database/integration/test_oracle_output_e2e.py"
    - "tests/v1/engine/components/database/integration/test_oracle_phase11_samples_e2e.py"
    - ".planning/phases/11-oracle-components/11-VERIFICATION.md"
  modified: []
key-decisions:
  - "Deferred Task 7 (real-DB pytest run) because Docker is not available in the agent execution environment; gate documented in 11-VERIFICATION.md as PENDING REAL-DB RUN with the verbatim gate command and operations-handoff steps"
  - "11-PHASE-SUMMARY.md is intentionally NOT created in this plan -- it is reserved for the post-gate close-out and depends on the captured green pytest output"
  - "STATE.md / ROADMAP.md are intentionally NOT updated -- the per-user-direction deferral means Phase 11 status is unchanged from end-of-11-06"
  - "Test isolation: each test gets a unique PYTEST_T_<8 hex chars> table name with explicit DROP teardown (no container restart between tests) per RESEARCH.md"
  - "Coverage matrix (VR-04..08) baked into both the gate doc and the test docstrings so the regression-prevention claim is auditable"
patterns-established:
  - "Pattern 1: Phase verification gate as a checked-in markdown document with frontmatter status (pending_real_db / verified) -- machine-readable handoff to ops"
  - "Pattern 2: Skip-on-missing-resource at conftest module load (pytest.importorskip + Docker probe) so the unit suite runs unimpaired on Docker-less hosts"
  - "Pattern 3: Real-DB integration tests organized under tests/v1/engine/components/database/integration/ with @pytest.mark.oracle marker (deselected from default CI runs)"
requirements-completed: [ORAC-01, ORAC-02, ORAC-03, ORAC-04, ORAC-05]
duration: ~45 min (Tasks 1-6); Task 7 deferred
completed: 2026-05-07
---

# Phase 11 Plan 07: Oracle Integration Test Suite + Verification Gate Summary

**~32 @pytest.mark.oracle integration tests targeting gvenzl/oracle-free testcontainer + checked-in verification gate doc; Task 7 real-DB run deferred pending Docker-capable host.**

## Performance

- **Duration (Tasks 1-6):** ~45 min
- **Completed:** 2026-05-07
- **Tasks completed:** 6 of 7 (Task 7 deferred per user direction)
- **Files created:** 7 (6 under tests/v1/engine/components/database/integration/ + 1 verification gate doc)
- **Files modified:** 0
- **Test code shipped:** 1,581 lines (conftest 161, connection 273, row 357, output 621, samples 169, init 0)

## Accomplishments

- 4 end-to-end test files cover the full VR-04..08 matrix (in-scope CONNECTION_TYPE open, type round-trip, REJECT batcherrors, INSERT_OR_UPDATE batched 2-statement upsert, DDL emission for the 4 CREATE-family TABLE_ACTIONs)
- Sample-driven E2E for the 3 Phase 11 .item fixtures executes the full converter+engine pipeline (convert_job -> JSON mutation -> ETLEngine) against the testcontainer
- Session-scoped oracle_container fixture with skip-on-missing-resource: testcontainers not installed / SKIP_ORACLE_CONTAINER env / Docker not running each pytest.skip() with a clear reason -- the unit suite is unaffected on Docker-less hosts
- 11-VERIFICATION.md documents the phase gate (D-D3 / D-F4) as a checked-in document with frontmatter `status:` so the deferred state is machine-readable for the operations handoff

## Task Commits

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create integration test directory + conftest with oracle_container fixture | `a0c8666` | tests/.../integration/__init__.py, tests/.../integration/conftest.py |
| 2 | test_oracle_connection_e2e.py for VR-04 (SID / SERVICE_NAME / RAC open against real DB) | `efce96c` | tests/.../integration/test_oracle_connection_e2e.py |
| 3 | test_oracle_row_e2e.py for VR-04 + VR-05 partial (real cursor.rowcount, prepared-statement type round-trip subset, DDL exec) | `38eba0b` | tests/.../integration/test_oracle_row_e2e.py |
| 4 | test_oracle_output_e2e.py for VR-05 / VR-06 / VR-07 / VR-08 | `3ae1ce2` | tests/.../integration/test_oracle_output_e2e.py |
| 5 | test_oracle_phase11_samples_e2e.py converting + executing the 3 .item samples through ETLEngine | `54ac8ed` | tests/.../integration/test_oracle_phase11_samples_e2e.py |
| 6 | Document the phase verification gate in 11-VERIFICATION.md (D-D3, D-F4) | `f94cbbd` | .planning/phases/11-oracle-components/11-VERIFICATION.md |
| 7 | **DEFERRED** -- Run full @pytest.mark.oracle suite + paste green output | _pending real-DB run_ | _none -- gate command not executed_ |

**Verification gate deferral commit:** `ae828c2` (docs(11-07): mark Phase 11 verification gate as PENDING REAL-DB RUN)

## Task 7: DEFERRED -- Pending Real-DB Run on a Docker-Capable Host

The Task 7 `checkpoint:human-verify` gate was reached on 2026-05-07. Per user direction, the real-DB pytest run is **deferred** because Docker is unavailable in the current agent execution environment (the worktree host has no Docker daemon, and `testcontainers.OracleDbContainer.start()` requires a running daemon to pull and boot the gvenzl/oracle-free image).

The gate command is the verbatim command from the plan and from 11-VERIFICATION.md:

```bash
pytest -m oracle tests/v1/engine/components/database/integration/ -v
```

Prerequisites and expected output (per 11-VERIFICATION.md):

```bash
docker info >/dev/null 2>&1 || { echo "Docker not running"; exit 1; }
pip install -e ".[oracle,dev]"
pytest -m oracle tests/v1/engine/components/database/integration/ -v
```

Expected: ALL ~32 integration tests pass (after container boot ~15-30s; total wall time ~3-5 min). The breakdown:

- 9 tests in `test_oracle_connection_e2e.py` (VR-04)
- 8 tests in `test_oracle_row_e2e.py` (VR-04 + VR-05 partial)
- 12 tests in `test_oracle_output_e2e.py` (VR-05 / VR-06 / VR-07 / VR-08, including the parametrized DDL emission tests)
- 3 tests in `test_oracle_phase11_samples_e2e.py` (sample-driven E2E)

Phase 11 verification will return `human_needed` until this gate run is green. The operations handoff lives at the top of 11-VERIFICATION.md (see commit `ae828c2`); the file's frontmatter `status: pending_real_db` makes the deferral machine-readable.

## Files Created

| File | Lines | Purpose |
|------|------:|---------|
| `tests/v1/engine/components/database/integration/__init__.py` | 0 | Package marker |
| `tests/v1/engine/components/database/integration/conftest.py` | 161 | Session-scoped oracle_container + per-test oracle_dsn / oracle_connection / temp_table / job_config_oracle_overrides fixtures with skip-on-missing-resource |
| `tests/v1/engine/components/database/integration/test_oracle_connection_e2e.py` | 273 | VR-04: real connect for SID / SERVICE_NAME / RAC; OCI / WALLET refusal |
| `tests/v1/engine/components/database/integration/test_oracle_row_e2e.py` | 357 | VR-04 + VR-05 partial: prepared-statement type round-trip subset, real cursor.rowcount, USE_NB_LINE counter, PROPAGATE_RECORD_SET refusal |
| `tests/v1/engine/components/database/integration/test_oracle_output_e2e.py` | 621 | VR-05 (6 type families) + VR-06 (REJECT batcherrors) + VR-07 (INSERT_OR_UPDATE batched 2-statement) + VR-08 (4 CREATE-family TABLE_ACTIONs) + USE_TIMESTAMP_FOR_DATE_TYPE behavior (D-B1) |
| `tests/v1/engine/components/database/integration/test_oracle_phase11_samples_e2e.py` | 169 | Convert + execute Job_tOracleConnection / Job_tOracleRow / Job_tOracleOutput .item fixtures end-to-end |
| `.planning/phases/11-oracle-components/11-VERIFICATION.md` | 148 | Phase verification gate doc (D-D3, D-F4) with deferral block + frontmatter status |

## VR Coverage Matrix

| VR ID | Requirement | File | Test(s) |
|-------|-------------|------|---------|
| VR-04 | In-scope CONNECTION_TYPEs open | test_oracle_connection_e2e.py | TestRealConnectionOpen.test_sid / .test_service_name / .test_rac |
| VR-05 | Type round-trip (NUMBER / DATE / TIMESTAMP / VARCHAR2 / CLOB / BLOB) | test_oracle_output_e2e.py + test_oracle_row_e2e.py | TestTypeRoundTrip.* + TestPreparedStatementRoundTrip.* |
| VR-06 | REJECT batcherrors (ORA-00001) | test_oracle_output_e2e.py | TestRejectBatcherrors.test_reject_on_unique_violation |
| VR-07 | INSERT_OR_UPDATE batched 2-statement | test_oracle_output_e2e.py | TestUpsertBatched.test_insert_or_update_batched + .test_update_or_insert_batched_prefers_update |
| VR-08 | DDL emission for CREATE-family TABLE_ACTIONs | test_oracle_output_e2e.py | TestDdlEmission.test_create_family_emits_valid_ddl (parametrized over 4 actions) |

## Decisions Made

- **Defer Task 7 (real-DB pytest run) at user direction.** Docker is unavailable in the agent execution environment; the gate command, expected output, and 5 source-file commit references are persisted at the top of 11-VERIFICATION.md so any developer / ops engineer with a Docker-capable host can complete the gate.
- **Do not write 11-PHASE-SUMMARY.md.** That artifact requires the captured green pytest output and is reserved for post-gate close-out.
- **Do not update STATE.md or ROADMAP.md.** Phase 11 progress is unchanged from end-of-11-06 because plan 11-07 is partially complete (tasks 1-6 of 7).
- **Use frontmatter `status: pending_real_db` on 11-VERIFICATION.md** instead of an inline note. Frontmatter makes the deferred state machine-readable for any future automation that scans phase docs.

## Deviations from Plan

None during Tasks 1-6 -- the plan executed as written. Task 7 was deferred per user direction (not a deviation; it is a documented gate handoff).

## Issues Encountered

- **Task 7 blocker: Docker not available in agent execution environment.** Resolved by deferring the gate per user direction and persisting the run instructions in 11-VERIFICATION.md.

## User Setup Required

To complete the deferred gate, see the deferral block at the top of `11-VERIFICATION.md`. Summary:

1. On a Docker-capable host, run `pytest -m oracle tests/v1/engine/components/database/integration/ -v`.
2. Confirm exit code 0 and `>= 25 passed` (target ~32 with all collected).
3. Paste the last ~30 lines into `11-PHASE-SUMMARY.md` under "Verification Gate Result".
4. Flip `status: pending_real_db` -> `status: verified` in 11-VERIFICATION.md frontmatter.

## Next Phase Readiness

- Tasks 1-6 of plan 11-07 ship the regression-prevention layer for plans 11-01..06.
- Phase 11 will return `human_needed` from verification until the deferred gate is run green on a Docker-capable host.
- `11-PHASE-SUMMARY.md` is intentionally not created here; it consolidates the 7 plan summaries plus the captured gate output and is the post-gate close-out artifact.

## Self-Check: PASSED

All 7 created files exist on disk; all 6 task commits + the verification-deferral commit (`ae828c2`) are present in `git log`.

---
*Phase: 11-oracle-components*
*Plan: 07*
*Completed: 2026-05-07 (Tasks 1-6 of 7; Task 7 deferred)*
