# Phase 11 Verification Gate

**Per CONTEXT.md D-D3 and D-F4 + Phase 5.1 mocks-lie lesson.**

Phase 11 is NOT verified until `pytest -m oracle` passes against a real
`gvenzl/oracle-free:23-slim-faststart` testcontainer at least once. Mocks of
`oracledb.Cursor` and `oracledb.Connection` cannot prove:

1. Wire-protocol correctness (Net8/TNS handshake, encoding negotiation)
2. Type round-trip (NUMBER -> Decimal, DATE -> datetime, CLOB -> str, BLOB -> bytes)
3. NULL handling (Oracle three-valued logic, NULL = NULL is UNKNOWN)
4. BatchError offset/code accuracy (driver-specific behavior)
5. DDL syntactic validity (PL/SQL EXECUTE IMMEDIATE patterns)
6. INSERT_OR_UPDATE batched 2-statement semantic equivalence to Talend
   per-row try/except

## Gate Command

```bash
# Prerequisites:
docker info >/dev/null 2>&1 || { echo "Docker not running"; exit 1; }
pip install -e ".[oracle,dev]"

# Full real-DB suite (includes container boot ~15-30s):
pytest -m oracle tests/v1/engine/components/database/integration/ -v
```

Expected: ALL tests pass. Container boot is ~15-30s on a typical dev box;
individual test runtime ~1-3s; total wall time ~3-5 minutes for ~25 tests
(15 from test_oracle_output_e2e.py including the 4 parametrized DDL tests,
8 from test_oracle_row_e2e.py, 7 from test_oracle_connection_e2e.py, 3 from
test_oracle_phase11_samples_e2e.py).

## Validation Requirement Coverage Map

| VR ID | Requirement | Test File | Test |
|-------|-------------|-----------|------|
| VR-01 | Manager lifecycle / leak-proof | tests/v1/engine/test_oracle_connection_manager.py | TestStartStop, TestRegisterAndGet (mock-based, plan 11-01) |
| VR-02 | Connection sharing via cid | tests/v1/engine/test_oracle_connection_manager.py + integration/test_oracle_connection_e2e.py | TestRegisterAndGet + TestComponentLevelE2E.test_register_and_get_round_trip |
| VR-03 | Driver mode (thin/thick) | tests/v1/engine/test_oracle_connection_manager.py | TestThickMode (mock-based; thick mode itself requires Instant Client and is deferred) |
| VR-04 | In-scope CONNECTION_TYPEs open | integration/test_oracle_connection_e2e.py | TestRealConnectionOpen.test_sid / test_service_name / test_rac |
| VR-05 | Type round-trip (6 type families) | integration/test_oracle_output_e2e.py + integration/test_oracle_row_e2e.py | TestTypeRoundTrip.* + TestPreparedStatementRoundTrip.* |
| VR-06 | REJECT batcherrors | integration/test_oracle_output_e2e.py | TestRejectBatcherrors.test_reject_on_unique_violation |
| VR-07 | INSERT_OR_UPDATE batched 2-statement | integration/test_oracle_output_e2e.py | TestUpsertBatched.test_insert_or_update_batched + test_update_or_insert_batched_prefers_update |
| VR-08 | DDL emission per CREATE-family | integration/test_oracle_output_e2e.py | TestDdlEmission.test_create_family_emits_valid_ddl (parametrized over 4 actions) |

## Acceptance Output Format

Paste the output of the gate command into `11-PHASE-SUMMARY.md` at phase close.
Required content:

```
Date: <YYYY-MM-DD HH:MM:SS UTC>
Container: gvenzl/oracle-free:23-slim-faststart
Image SHA: <docker image inspect output>
oracledb: <version>
testcontainers: <version>

============================= test session starts ==============================
...
===================== <N> passed, <M> deselected in <T>s =======================
```

Where N >= 25 (sum of integration tests across the 4 e2e files) and M is the
count of @pytest.mark.unit tests deselected by the `-m oracle` filter.

## CI Bypass

The integration suite is NOT run in default CI. To skip locally on a host
without Docker:

```bash
SKIP_ORACLE_CONTAINER=1 pytest -m oracle tests/v1/engine/components/database/integration/
```

All tests will pytest.skip() with a clear message. This bypass is for
developer-environment debugging only -- the phase verification gate
requires a green output that did NOT use this bypass.

## Why This Gate Exists

Phase 5.1 (Java bridge / tMap) shipped passing all unit tests; production then
hit four Java bridge bugs that mocks could not surface:

- Arrow type inference rounded BigDecimal to double precision
- buildRowWrapper closure leaked the previous batch's row context across
  per-row Java calls
- Arrow IPC schema/data column misalignment for variable-length string columns
- string-key globalMap entries failing Arrow Map type construction

The lesson: mocks of complex IO components do NOT validate semantic correctness.
The integration suite is the regression-prevention layer for plans 11-01..06.
Without a green real-DB run, Phase 11 cannot demonstrate Talend parity for the
production migration target of 1200+ jobs.

## Re-running After Code Changes

Any change to:
- `src/v1/engine/oracle_connection_manager.py`
- `src/v1/engine/components/database/oracle_connection.py`
- `src/v1/engine/components/database/oracle_row.py`
- `src/v1/engine/components/database/oracle_output.py`
- `src/converters/talend_to_v1/components/database/oracle_*.py`

requires re-running the gate command and updating `11-PHASE-SUMMARY.md` with
the new green output. The unit-test suite alone is insufficient.
