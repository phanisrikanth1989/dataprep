---
phase: 11
slug: oracle-components
status: planned
nyquist_compliant: true
wave_0_complete: false
created: 2026-05-07
last_updated: 2026-05-07
---

# Phase 11 -- Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Per CONTEXT.md D-D3, D-F4 + RESEARCH.md `## Validation Architecture` section.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x (already configured in `pyproject.toml`) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | `pytest tests/v1/engine/components/database/ tests/v1/engine/test_oracle_connection_manager.py -x` |
| **Full suite command** | `pytest tests/v1/engine/ tests/converters/talend_to_v1/components/database/ -x` |
| **Real-DB integration command** | `pytest -m oracle tests/v1/engine/components/database/integration/ -x` |
| **Estimated runtime** | ~30s for unit tests; ~3-5 min for `-m oracle` (testcontainer boot ~30-60s + tests) |

---

## Sampling Rate

- **After every task commit:** Run quick command (mock-default unit tests only -- fast feedback)
- **After every plan wave:** Run full suite (still mocks; `-m oracle` excluded)
- **Before `/gsd-verify-work`:** **MANDATORY** -- `pytest -m oracle` against `gvenzl/oracle-free` testcontainer must pass at least once. Per D-D3 Phase 5.1 "mocks lie" lesson -- mock-only verification cannot demonstrate Talend parity.
- **Max feedback latency:** 30s for unit-test sampling

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 11-01-T1 | 11-01 | 1 | ORAC-01 | -- | pyproject.toml has oracle extra, dev testcontainers, oracle pytest marker | unit | `pip install -e ".[oracle]" && pytest --markers 2>&1 \| grep oracle` | Wave 0 | pending |
| 11-01-T2 | 11-01 | 1 | ORAC-01 | T-11-02, T-11-03, T-11-05 | OracleConnectionManager class with 12-method API; idempotent stop; thick_mode guarded; PASS never logged | unit | `python -c "from src.v1.engine.oracle_connection_manager import OracleConnectionManager; m = OracleConnectionManager(); m.start(); m.stop()"` | Wave 0 | pending |
| 11-01-T3 | 11-01 | 1 | ORAC-01 | T-11-02 | ETLEngine wires oracle_manager (4 edits: import / __init__ / _initialize_components / _cleanup); TestPasswordNotLogged regression | unit | `pytest tests/v1/engine/test_oracle_connection_manager.py -x` | Wave 0 | pending |
| 11-02-T1 | 11-02 | 2 | ORAC-02 | T-11-02, T-11-05 | OracleConnection class with 5-CT dispatch; OCI/WALLET refusal; password never in logs/globalMap; auto_commit honored | unit | `python -c "from src.v1.engine.components import database; from src.v1.engine.component_registry import REGISTRY; assert REGISTRY.get('tOracleConnection') is not None"` | Wave 0 | pending |
| 11-02-T2 | 11-02 | 2 | ORAC-02 | T-11-02, T-11-05 | Unit tests cover 17 behaviors incl. TestPasswordNotLogged + TestProcessUnsupportedTypes | unit | `pytest tests/v1/engine/components/database/test_oracle_connection.py -x` | Wave 0 | pending |
| 11-03-T1 | 11-03 | 2 | ORAC-03 | -- | Open Q 2 resolved: PARAMETER_TYPE enum verified from Talaxie; documented in module docstring | unit | `grep -E "Talaxie tOracleRow_java.xml PARAMETER_TYPE enum" src/v1/engine/components/database/oracle_row.py` | Wave 0 | pending |
| 11-03-T2 | 11-03 | 2 | ORAC-03 | T-11-01 | OracleRow with full PARAMETER_TYPE coercion table; PROPAGATE_RECORD_SET refused; USE_NB_LINE counter; resolved QUERY published | unit | `python -c "from src.v1.engine.components import database; from src.v1.engine.component_registry import REGISTRY; assert REGISTRY.get('tOracleRow') is not None"` | Wave 0 | pending |
| 11-03-T3 | 11-03 | 2 | ORAC-03 | T-11-01 | Unit tests: registration / validation / both connection paths / 16 PARAMETER_TYPE coercions / USE_NB_LINE / PROPAGATE_RECORD_SET refusal | unit | `pytest tests/v1/engine/components/database/test_oracle_row.py -x` | Wave 0 | pending |
| 11-04-T1 | 11-04 | 2 | ORAC-04 | -- | Open Q 1, 3 resolved: Talaxie DDL conventions documented; CREATE_IF_NOT_EXISTS pattern locked | unit | `grep -E "Talaxie _tableActionForOutput.javajet" src/v1/engine/components/database/oracle_output.py` | Wave 0 | pending |
| 11-04-T2 | 11-04 | 2 | ORAC-04 | T-11-01, T-11-04 | OracleOutput with 8 TABLE_ACTIONs + INSERT/UPDATE/DELETE + REJECT flow + 5 stat keys + identifier quoting policy | unit | `python -c "from src.v1.engine.components import database; from src.v1.engine.component_registry import REGISTRY; assert REGISTRY.get('tOracleOutput') is not None"` | Wave 0 | pending |
| 11-04-T3 | 11-04 | 2 | ORAC-04 | T-11-01, T-11-04 | Unit tests: 30+ tests covering 8 TABLE_ACTIONs, 3 DATA_ACTIONs, REJECT flow, FIELD_OPTIONS, stat keys, die_on_error rewrap, T-11-04 negative regression | unit | `pytest tests/v1/engine/components/database/test_oracle_output.py -x` | Wave 0 | pending |
| 11-05-T1 | 11-05 | 3 | ORAC-04 | T-11-01 | _execute_upsert_batch replaces NotImplementedError stubs; SELECT-existing parameterized; NULL-PK forced INSERT | unit | `python -c "from src.v1.engine.components.database.oracle_output import OracleOutput; assert hasattr(OracleOutput, '_execute_upsert_batch')"` | Wave 0 | pending |
| 11-05-T2 | 11-05 | 3 | ORAC-04 | T-11-01 | Upsert unit tests: 5-row partition, single-PK / composite-PK, NULL-PK warning, reject merging, malicious-PK injection regression | unit | `pytest tests/v1/engine/components/database/test_oracle_output.py -x -k upsert` | Wave 0 | pending |
| 11-06-T1 | 11-06 | 2 | ORAC-05 | T-11-05 | 3 converters emit conditional Wallet/OCI needs_review; engine_gap entries removed; 6 deferred converters untouched | unit | `python -c "from src.converters.talend_to_v1.components.database.oracle_connection import OracleConnectionConverter; from src.converters.talend_to_v1.components.database.oracle_row import OracleRowConverter; from src.converters.talend_to_v1.components.database.oracle_output import OracleOutputConverter; print('OK')"` | Wave 0 | pending |
| 11-06-T2 | 11-06 | 2 | ORAC-05 | T-11-05 | Converter test files: TestNeedsReview class updated with no_review_for_sid / needs_review_for_wallet / needs_review_for_oci | unit | `pytest tests/converters/talend_to_v1/components/database/test_oracle_connection.py tests/converters/talend_to_v1/components/database/test_oracle_row.py tests/converters/talend_to_v1/components/database/test_oracle_output.py -x` | Wave 0 | pending |
| 11-07-T1 | 11-07 | 4 | ORAC-01..05 | -- | conftest.py with session-scoped oracle_container + per-test fixtures; skip-on-missing-resource | integration | `pytest tests/v1/engine/components/database/integration/conftest.py --collect-only` | Wave 0 | pending |
| 11-07-T2 | 11-07 | 4 | ORAC-02 | -- | VR-04 covered: SID / SERVICE_NAME / RAC each open against real DB | integration | `pytest -m oracle tests/v1/engine/components/database/integration/test_oracle_connection_e2e.py -x` | Wave 0 | pending |
| 11-07-T3 | 11-07 | 4 | ORAC-03 | T-11-01 | VR-04 + VR-05 partial: prepared-statement round-trip; DDL real execution; USE_NB_LINE against real cursor.rowcount | integration | `pytest -m oracle tests/v1/engine/components/database/integration/test_oracle_row_e2e.py -x` | Wave 0 | pending |
| 11-07-T4 | 11-07 | 4 | ORAC-04 | T-11-01, T-11-04 | VR-05/VR-06/VR-07/VR-08 covered: type round-trip, REJECT batcherrors, INSERT_OR_UPDATE, DDL emission per CREATE-family | integration | `pytest -m oracle tests/v1/engine/components/database/integration/test_oracle_output_e2e.py -x` | Wave 0 | pending |
| 11-07-T5 | 11-07 | 4 | ORAC-01..05 | -- | 3 sample .item files convert + execute end-to-end | integration | `pytest -m oracle tests/v1/engine/components/database/integration/test_oracle_phase11_samples_e2e.py -x` | Wave 0 | pending |
| 11-07-T6 | 11-07 | 4 | ORAC-01..05 | -- | 11-VERIFICATION.md documents phase gate per D-D3 / D-F4 | doc | `grep -c "pytest -m oracle" .planning/phases/11-oracle-components/11-VERIFICATION.md` | Wave 0 | pending |
| 11-07-T7 | 11-07 | 4 | ORAC-01..05 | -- | Phase verification gate: full @pytest.mark.oracle suite passes once against real testcontainer | integration (manual checkpoint) | `pytest -m oracle tests/v1/engine/components/database/integration/ -v` | Wave 0 | pending (checkpoint) |

*Status: pending / green / red / flaky*

---

## Validation Requirements (Nyquist Dimension 8)

Drawn from RESEARCH.md `## Validation Architecture` and CONTEXT.md D-* decisions:

1. **VR-01 -- Connection lifecycle (D-A4, D-A4b):** `OracleConnectionManager.stop()` is idempotent, closes all live connections, swallows per-connection close errors. Verified by unit tests with mock connections + integration test confirming no leaked sessions in v$session after `engine._cleanup()`.

2. **VR-02 -- Connection sharing (D-A1):** A second component referencing `tOracleConnection_1` via `USE_EXISTING_CONNECTION + CONNECTION` reuses the SAME live `oracledb.Connection` object (verified by `id()` equality). globalMap holds metadata strings only -- never the live connection.

3. **VR-03 -- Driver mode (D-A2):** Default thin mode does NOT call `oracledb.init_oracle_client()`. Setting `oracle_config.thick_mode=true` calls it exactly ONCE per process (class-level `_thick_initialized` guard). Switching mid-process raises a clear error.

4. **VR-04 -- Connection types in scope (D-A3):** `ORACLE_SID`, `ORACLE_SERVICE_NAME`, `ORACLE_RAC` produce successful `oracledb.connect()` calls against the testcontainer. `ORACLE_OCI` and `ORACLE_WALLET` raise `ConfigurationError` with the exact message specified in D-A3.

5. **VR-05 -- Type round-trip (D-B1):** A row written via tOracleOutput and read back via tOracleRow `SELECT *` round-trips losslessly for: NUMBER(p,s)->Decimal, DATE->datetime, TIMESTAMP->datetime, TIMESTAMP WITH TZ->tz-aware datetime, VARCHAR2->str, CLOB->str, BLOB->bytes. **REQUIRES @pytest.mark.oracle** -- mocks cannot prove wire-protocol parity (Phase 5.1 lesson).

6. **VR-06 -- Reject path with batcherrors (D-B2, D-C7):** With REJECT connection wired and `executemany(batcherrors=True)`, a batch containing 3 valid rows + 1 ORA-00001 (unique constraint) row produces: `NB_LINE_INSERTED=3`, `NB_LINE_REJECTED=1`, reject DataFrame contains the 4th row + correct `errorCode = "1"` + `errorMessage` ending in `" - Line: <offset>"` matching Talend format.

7. **VR-07 -- INSERT_OR_UPDATE batched 2-statement (D-C2):** With 5 input rows where 2 keys exist in target and 3 don't, the planner-emitted SQL produces `NB_LINE_UPDATED=2`, `NB_LINE_INSERTED=3`. Verified that exactly ONE `SELECT pk_cols WHERE pk IN (...)` query fires per batch (not per row), then exactly ONE `executemany UPDATE` and ONE `executemany INSERT`.

8. **VR-08 -- DDL emission (D-C1):** For each CREATE-family TABLE_ACTION (CREATE / CREATE_IF_NOT_EXISTS / DROP_CREATE / DROP_IF_EXISTS_AND_CREATE), the emitted DDL parses successfully against the testcontainer Oracle instance and produces a table whose columns match the engine schema column types per the type mapping table.

---

## Wave 0 Requirements

- [ ] `tests/v1/engine/test_oracle_connection_manager.py` -- stubs for VR-01, VR-02, VR-03 (mock-based unit tests) -- plan 11-01
- [ ] `tests/v1/engine/components/database/__init__.py` -- package marker -- plan 11-01
- [ ] `tests/v1/engine/components/database/test_oracle_connection.py` -- stubs for VR-04 (mock-based) -- plan 11-02
- [ ] `tests/v1/engine/components/database/test_oracle_row.py` -- stubs for VR-04 + 16-type matrix (mock-based) -- plan 11-03
- [ ] `tests/v1/engine/components/database/test_oracle_output.py` -- stubs for VR-06, VR-07, VR-08 (mock-based) -- plans 11-04 / 11-05
- [ ] `tests/v1/engine/components/database/integration/__init__.py` -- integration package marker -- plan 11-07
- [ ] `tests/v1/engine/components/database/integration/conftest.py` -- `oracle_container` fixture using `testcontainers` + `gvenzl/oracle-free:23-slim-faststart`; fixture is session-scoped; skip-emits if `testcontainers` not importable -- plan 11-07
- [ ] `tests/v1/engine/components/database/integration/test_oracle_connection_e2e.py` -- VR-04 -- plan 11-07
- [ ] `tests/v1/engine/components/database/integration/test_oracle_row_e2e.py` -- VR-04, VR-05 partial -- plan 11-07
- [ ] `tests/v1/engine/components/database/integration/test_oracle_output_e2e.py` -- VR-05, VR-06, VR-07, VR-08 -- plan 11-07
- [ ] `tests/v1/engine/components/database/integration/test_oracle_phase11_samples_e2e.py` -- 3 .item samples end-to-end -- plan 11-07
- [ ] `pyproject.toml` -- add `oracle = ["oracledb>=2.5,<4"]` extra, add `testcontainers>=4` to `dev` extra, register `oracle` pytest marker -- plan 11-01
- [ ] `.planning/phases/11-oracle-components/11-VERIFICATION.md` -- phase gate doc -- plan 11-07

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Wallet/OCI thick-mode end-to-end (out of Phase 11 scope) | ORAC-02 (deferred) | Requires Oracle Instant Client install on a host with wallet directory configured -- not reproducible in containers without bundled licensed Oracle Client | Document for the future phase that lifts Wallet/OCI |
| RHEL deployment validation | ORAC-02 | RHEL-specific filesystem and SELinux behavior cannot be reproduced in CI | Operations team manual run on a staging RHEL host |
| Phase verification gate (D-D3) | ORAC-01..05 | Requires Docker host capable of running gvenzl/oracle-free; not always available in default CI | Plan 11-07 Task 7 checkpoint -- developer pastes green `pytest -m oracle` output back to chat |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 30s for unit tests
- [ ] `@pytest.mark.oracle` real-DB suite passes against testcontainer at least once before phase verification (plan 11-07 Task 7 checkpoint)
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** plan-time approved 2026-05-07; phase verification gate pending plan 11-07 Task 7 execution
