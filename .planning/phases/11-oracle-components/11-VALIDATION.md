---
phase: 11
slug: oracle-components
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-07
---

# Phase 11 — Validation Strategy

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
| **Estimated runtime** | ~30s for unit tests; ~3–5 min for `-m oracle` (testcontainer boot ~30–60s + tests) |

---

## Sampling Rate

- **After every task commit:** Run quick command (mock-default unit tests only — fast feedback)
- **After every plan wave:** Run full suite (still mocks; `-m oracle` excluded)
- **Before `/gsd-verify-work`:** **MANDATORY** — `pytest -m oracle` against `gvenzl/oracle-free` testcontainer must pass at least once. Per D-D3 Phase 5.1 "mocks lie" lesson — mock-only verification cannot demonstrate Talend parity.
- **Max feedback latency:** 30s for unit-test sampling

---

## Per-Task Verification Map

> Populated by the planner during step 8. Each task gets a row with: Task ID, Plan, Wave, Requirement (ORAC-XX), Threat Ref (T-11-XX or "—"), Secure Behavior, Test Type, Automated Command, File Exists, Status.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| _to be filled by planner_ | | | | | | | | | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Validation Requirements (Nyquist Dimension 8)

Drawn from RESEARCH.md `## Validation Architecture` and CONTEXT.md D-* decisions:

1. **VR-01 — Connection lifecycle (D-A4, D-A4b):** `OracleConnectionManager.stop()` is idempotent, closes all live connections, swallows per-connection close errors. Verified by unit tests with mock connections + integration test confirming no leaked sessions in v$session after `engine._cleanup()`.

2. **VR-02 — Connection sharing (D-A1):** A second component referencing `tOracleConnection_1` via `USE_EXISTING_CONNECTION + CONNECTION` reuses the SAME live `oracledb.Connection` object (verified by `id()` equality). globalMap holds metadata strings only — never the live connection.

3. **VR-03 — Driver mode (D-A2):** Default thin mode does NOT call `oracledb.init_oracle_client()`. Setting `oracle_config.thick_mode=true` calls it exactly ONCE per process (class-level `_thick_initialized` guard). Switching mid-process raises a clear error.

4. **VR-04 — Connection types in scope (D-A3):** `ORACLE_SID`, `ORACLE_SERVICE_NAME`, `ORACLE_RAC` produce successful `oracledb.connect()` calls against the testcontainer. `ORACLE_OCI` and `ORACLE_WALLET` raise `NotImplementedError` with the exact message specified in D-A3.

5. **VR-05 — Type round-trip (D-B1):** A row written via tOracleOutput and read back via tOracleRow `SELECT *` round-trips losslessly for: NUMBER(p,s)→Decimal, DATE→datetime, TIMESTAMP→datetime, TIMESTAMP WITH TZ→tz-aware datetime, VARCHAR2→str, CLOB→str, BLOB→bytes. **REQUIRES @pytest.mark.oracle** — mocks cannot prove wire-protocol parity (Phase 5.1 lesson).

6. **VR-06 — Reject path with batcherrors (D-B2, D-C7):** With REJECT connection wired and `executemany(batcherrors=True)`, a batch containing 3 valid rows + 1 ORA-00001 (unique constraint) row produces: `NB_LINE_INSERTED=3`, `NB_LINE_REJECTED=1`, reject DataFrame contains the 4th row + correct `errorCode = "1"` + `errorMessage` ending in `" - Line: <offset>"` matching Talend format.

7. **VR-07 — INSERT_OR_UPDATE batched 2-statement (D-C2):** With 5 input rows where 2 keys exist in target and 3 don't, the planner-emitted SQL produces `NB_LINE_UPDATED=2`, `NB_LINE_INSERTED=3`. Verified that exactly ONE `SELECT pk_cols WHERE pk IN (...)` query fires per batch (not per row), then exactly ONE `executemany UPDATE` and ONE `executemany INSERT`.

8. **VR-08 — DDL emission (D-C1):** For each CREATE-family TABLE_ACTION (CREATE / CREATE_IF_NOT_EXISTS / DROP_CREATE / DROP_IF_EXISTS_AND_CREATE), the emitted DDL parses successfully against the testcontainer Oracle instance and produces a table whose columns match the engine schema column types per the type mapping table.

---

## Wave 0 Requirements

- [ ] `tests/v1/engine/test_oracle_connection_manager.py` — stubs for VR-01, VR-02, VR-03 (mock-based unit tests)
- [ ] `tests/v1/engine/components/database/__init__.py` — package marker
- [ ] `tests/v1/engine/components/database/test_oracle_connection.py` — stubs for VR-04 (mock-based)
- [ ] `tests/v1/engine/components/database/test_oracle_row.py` — stubs for VR-06 (mock-based)
- [ ] `tests/v1/engine/components/database/test_oracle_output.py` — stubs for VR-07, VR-08 (mock-based)
- [ ] `tests/v1/engine/components/database/integration/__init__.py` — integration package marker
- [ ] `tests/v1/engine/components/database/integration/conftest.py` — `oracle_container` fixture using `testcontainers` + `gvenzl/oracle-free:23-slim-faststart`; fixture is session-scoped; skip-emits if `testcontainers` not importable
- [ ] `tests/v1/engine/components/database/integration/test_oracle_e2e.py` — `@pytest.mark.oracle` E2E test stubs for VR-05 (type round-trip), plus the 3 `.item` sample-driven tests
- [ ] `pyproject.toml` — add `oracle = ["oracledb>=2.5,<4"]` extra, add `testcontainers>=4` to `dev` extra, register `oracle` pytest marker

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Wallet/OCI thick-mode end-to-end (out of Phase 11 scope) | ORAC-02 (deferred) | Requires Oracle Instant Client install on a host with wallet directory configured — not reproducible in containers without bundled licensed Oracle Client | Document for the future phase that lifts Wallet/OCI |
| RHEL deployment validation | ORAC-02 | RHEL-specific filesystem and SELinux behavior cannot be reproduced in CI | Operations team manual run on a staging RHEL host |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s for unit tests
- [ ] `@pytest.mark.oracle` real-DB suite passes against testcontainer at least once before phase verification
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
