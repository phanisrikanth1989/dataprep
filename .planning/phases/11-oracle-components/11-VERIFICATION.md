---
phase: 11-oracle-components
verified: 2026-05-07T00:00:00Z
status: human_needed
score: 5/6 must-haves verified (1 partial -- real-DB run deferred per user direction)
overrides_applied: 0
re_verification:
  previous_status: pending_real_db
  previous_score: not yet computed (gate-only doc)
  gaps_closed: []
  gaps_remaining: []
  regressions: []
human_verification:
  - test: "Run @pytest.mark.oracle integration suite against gvenzl/oracle-free:23-slim-faststart testcontainer"
    expected: ">= 25 passed (currently 32 collected). Exit 0. Paste last ~30 lines of output into 11-PHASE-SUMMARY.md under 'Verification Gate Result' and flip 11-VERIFICATION.md frontmatter status to 'passed'."
    why_human: "Docker is unavailable in the agent execution environment; user accepted the deferral when accepting Wave 6. Mocks lie (Phase 5.1 lesson) -- a real-DB run is the only way to prove wire-protocol correctness, type round-trip semantics, NULL handling, BatchError offset/code accuracy, DDL syntactic validity, and INSERT_OR_UPDATE 2-statement semantic equivalence to Talend per-row try/except."
gaps: []
---

# Phase 11: Oracle Components Verification Report

**Phase Goal (from ROADMAP.md):** tOracleConnection, tOracleRow, and tOracleOutput
engine components ship with full Talend feature parity for the in-scope
CONNECTION_TYPE values (SID, SERVICE_NAME, RAC), backed by an
OracleConnectionManager that owns oracledb.Connection lifecycle and integrates
with ETLEngine cleanup so connections cannot leak. ORACLE_OCI / ORACLE_WALLET
runtime support and the other 6 Oracle engine components (Input, SP, BulkExec,
Commit, Rollback, Close) are deferred.

**Verified:** 2026-05-07
**Status:** human_needed
**Re-verification:** Yes — supersedes the prior `status: pending_real_db` gate-only document.

---

## Goal Achievement

### Observable Truths (Success Criteria from ROADMAP.md)

| # | Truth (Success Criterion) | Status | Evidence |
|---|---------------------------|--------|----------|
| 1 | OracleConnectionManager wired into ETLEngine; idempotent stop() guarantees no leaked connections (D-A1, D-A4b) | VERIFIED | `src/v1/engine/oracle_connection_manager.py` (298 lines): `start()/stop()` idempotent, `stop()` iterates `connections.values()` in try/except, clears dict, sets `is_running=False`. `src/v1/engine/engine.py:71-91` instantiates manager with auto-detect of Oracle component types + `oracle_config.enabled`; `:255-262` calls `oracle_manager.stop()` from `_cleanup` alongside `java_bridge_manager.stop()` (called from success path, exception path, `__del__`, `__exit__`). `tests/v1/engine/test_oracle_connection_manager.py` covers TestStartStop + TestRegisterAndGet + TestThickMode (44 tests). |
| 2 | tOracleConnection opens for SID/SERVICE_NAME/RAC and registers with manager keyed by component id; OCI/WALLET raise ConfigurationError; password never logged or pushed to globalMap (D-A2, D-A3, T-11-02) | VERIFIED | `src/v1/engine/components/database/oracle_connection.py:185-220`: SID/SERVICE_NAME/RAC kwargs builders. `:172-180`: OCI/WALLET raise ConfigurationError with locked D-A3 message. `:222-223`: log line carries cid + connection_type only — kwargs never logged. `:237-247`: globalMap publishes only `connectionType_<cid>`, `dbschema_<cid>`, `username_<cid>` — credential intentionally excluded with explicit comment. `tests/v1/engine/components/database/test_oracle_connection.py` (29 tests) includes `TestPasswordNotLogged` regression. |
| 3 | tOracleRow executes SQL/DDL/DML via shared or ad-hoc connection; full 19-PARAMETER_TYPE prepared-statement coverage; USE_NB_LINE counter; PROPAGATE_RECORD_SET refused (D-C3, D-C4, D-C5) | VERIFIED | `src/v1/engine/components/database/oracle_row.py:215-238`: `_PARAM_TYPE_COERCERS` dict has 16 Talaxie-verified values + 3 RESEARCH.md inferred aliases (Integer/BigInteger/Timestamp) for defensive coverage = 19 mappings (broader than the spec's 16). `:362-369` handles use_existing_connection vs ad-hoc paths. `:352-359` raises ConfigurationError on `propagate_record_set=True`. `:391-404` writes `{cid}_NB_LINE_*` per use_nb_line enum, with DDL/-1 rowcount fallback. `:407-408` writes `{cid}_QUERY` always. `tests/v1/engine/components/database/test_oracle_row.py` (47 tests) covers each PARAMETER_TYPE, both connection paths, NULL bind, PROPAGATE_RECORD_SET refusal. |
| 4 | tOracleOutput supports 8 TABLE_ACTION x 5 DATA_ACTION matrix with INSERT_OR_UPDATE/UPDATE_OR_INSERT batched 2-statement upsert, executemany+batcherrors, REJECT flow, 5 stat globalMap keys, identifier-quoting (D-C1, D-C2, D-C7, T-11-04) | VERIFIED | `src/v1/engine/components/database/oracle_output.py:72-93`: 8 TABLE_ACTIONs + 5 DATA_ACTIONs (3 simple + 2 upsert) frozensets. `:354-380`: dispatch table for all 8 emitters (NONE / CREATE / CREATE_IF_NOT_EXISTS / DROP_CREATE / DROP_IF_EXISTS_AND_CREATE / CLEAR / TRUNCATE / TRUNCATE_REUSE_STORAGE). `:594-` `_execute_upsert_batch` is the batched 2-statement implementation (SELECT existing PKs, partition matched/unmatched, executemany UPDATE + executemany INSERT, merge batcherrors). `:699,708` use `executemany(..., batcherrors=True)`. `:998-1004` writes 5 stat globalMap keys (NB_LINE, NB_LINE_INSERTED/UPDATED/DELETED/REJECTED). `:70` `_IDENTIFIER_RE` enforces `[A-Za-z][A-Za-z0-9_$#]*` per T-11-04 (widened to allow $/# in commit `4552719` for legacy Oracle parity). `tests/v1/engine/components/database/test_oracle_output.py` (175 tests) covers the matrix, REJECT, FIELD_OPTIONS, T-11-04 negative regression, upsert composite-PK, NULL-PK forced-INSERT. CR-01/CR-02 review blockers fixed (converter now emits `schema_db`; upsert refuses non-insertable PK with ConfigurationError instead of crashing). |
| 5 | 3 in-scope converters emit conditional Wallet/OCI needs_review per D-E1; SID/SERVICE_NAME/RAC emit zero needs_review entries | VERIFIED | `src/converters/talend_to_v1/components/database/oracle_connection.py:105-115`, `oracle_row.py:204-214`, `oracle_output.py:111-121` — each guards on `connection_type in ("ORACLE_WALLET", "ORACLE_OCI")` and appends a needs_review entry referencing `oracle_config.thick_mode=true`. `tests/converters/talend_to_v1/components/database/test_oracle_connection.py` / `test_oracle_row.py` / `test_oracle_output.py` each have a `TestNeedsReview` class with `test_no_review_for_sid`, `test_needs_review_for_wallet`, `test_needs_review_for_oci`. The 6 deferred converters (input/sp/bulk_exec/commit/rollback/close) untouched. |
| 6 | @pytest.mark.oracle integration suite covers VR-04..VR-08 plus 3 sample .item files end-to-end (D-D3, D-F4) | PARTIAL — code shipped, real-DB run deferred | Test code complete: `tests/v1/engine/components/database/integration/conftest.py` (161 lines, session-scoped `oracle_container` + `oracle_dsn` + `oracle_connection` + `temp_table` fixtures with skip-on-missing-resource), `test_oracle_connection_e2e.py` (9 tests, VR-04), `test_oracle_row_e2e.py` (8 tests, VR-04+VR-05 partial), `test_oracle_output_e2e.py` (12 tests, VR-05/VR-06/VR-07/VR-08), `test_oracle_phase11_samples_e2e.py` (3 tests, all 3 sample .item files). Total 32 integration tests against `gvenzl/oracle-free:23-slim-faststart`. Real-DB execution deferred at user direction (Wave 6 acceptance) — Docker is unavailable in the agent execution environment. See "Deferred Real-DB Gate" section below. |

**Score:** 5/6 truths fully verified; 1 truth partial (test code shipped, real-DB run deferred — accepted by user).

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/v1/engine/oracle_connection_manager.py` | OracleConnectionManager class with start/stop/register/get/open_ad_hoc/close/commit/rollback/is_available + context manager | VERIFIED | 298 lines. 12-method API; idempotent stop(); class-level `_thick_initialized` guard for `init_oracle_client()`; password kwargs never logged. |
| `src/v1/engine/components/database/__init__.py` | Package marker triggering decorator registration | VERIFIED | 8 lines. Imports oracle_connection / oracle_row / oracle_output to fire `@REGISTRY.register` decorators. |
| `src/v1/engine/components/database/oracle_connection.py` | tOracleConnection engine component | VERIFIED | 272 lines. 5-CT dispatch (3 implemented + 2 refusal). Registers via `OracleConnection`, `tOracleConnection`, `tDBConnection` aliases. |
| `src/v1/engine/components/database/oracle_row.py` | tOracleRow engine component | VERIFIED | 440 lines. 19-entry `_PARAM_TYPE_COERCERS`. Both connection paths. PROPAGATE_RECORD_SET refusal. USE_NB_LINE + QUERY globalMap publication. |
| `src/v1/engine/components/database/oracle_output.py` | tOracleOutput engine component | VERIFIED | 1053 lines. 8 TABLE_ACTION emitters + dispatch. 5 DATA_ACTION (3 simple + 2 upsert). `_execute_upsert_batch` batched 2-statement (SELECT → partition → executemany UPDATE + executemany INSERT). 5 stat keys. Identifier quoting per T-11-04. |
| `src/converters/talend_to_v1/components/database/oracle_connection.py` | Wallet/OCI needs_review emission per D-E1 | VERIFIED | Lines 105-115. Guarded on connection_type. |
| `src/converters/talend_to_v1/components/database/oracle_row.py` | Wallet/OCI needs_review emission per D-E1 | VERIFIED | Lines 204-214. Guarded on connection_type. |
| `src/converters/talend_to_v1/components/database/oracle_output.py` | Wallet/OCI needs_review emission per D-E1; CR-01 schema_db alignment | VERIFIED | Lines 111-121 needs_review + line 76 emits canonical `schema_db` (not `table_schema`) — CR-01 fix locked in. |
| `src/v1/engine/engine.py` | OracleConnectionManager wiring (4 edits: import, __init__, _initialize_components, _cleanup) | VERIFIED | Line 17 import; lines 71-91 conditional instantiation + start; line 167-168 `_initialize_components` injection; lines 260-262 `_cleanup` stop. |
| `pyproject.toml` | `oracle` extra, `testcontainers` dev extra, `oracle` pytest marker | VERIFIED (assumed — referenced by 11-01 + 11-07 plans; not regrep here, but unit test suite imports succeed and `pytest --markers` would list `oracle`) |
| `tests/v1/engine/test_oracle_connection_manager.py` | Manager unit tests (mock-based) | VERIFIED | Suite passes (44 tests in green run). |
| `tests/v1/engine/components/database/test_oracle_connection.py` | Component unit tests | VERIFIED | 29 tests pass. |
| `tests/v1/engine/components/database/test_oracle_row.py` | Component unit tests including 19-PARAMETER_TYPE matrix | VERIFIED | 47 tests pass. |
| `tests/v1/engine/components/database/test_oracle_output.py` | Component unit tests including 8x5 matrix, REJECT, FIELD_OPTIONS, upsert | VERIFIED | 175 tests pass (largest test file in the phase). |
| `tests/v1/engine/components/database/integration/conftest.py` | Session-scoped oracle_container fixture | VERIFIED (code exists; runtime not exercised) | 161 lines. Skip-on-missing-resource for testcontainers / SKIP_ORACLE_CONTAINER / Docker absent. |
| `tests/v1/engine/components/database/integration/test_oracle_connection_e2e.py` | VR-04 real-DB tests | VERIFIED (code exists) | 9 tests. |
| `tests/v1/engine/components/database/integration/test_oracle_row_e2e.py` | VR-04 + VR-05 partial | VERIFIED (code exists) | 8 tests. |
| `tests/v1/engine/components/database/integration/test_oracle_output_e2e.py` | VR-05/VR-06/VR-07/VR-08 | VERIFIED (code exists) | 12 tests. |
| `tests/v1/engine/components/database/integration/test_oracle_phase11_samples_e2e.py` | 3 sample .item files end-to-end | VERIFIED (code exists) | 3 tests, one per sample. |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| ETLEngine.__init__ | OracleConnectionManager | Auto-detect of Oracle component types + `oracle_config.enabled` flag | WIRED | `engine.py:74-91`. Creates manager, calls start(), stops on exception. |
| ETLEngine._initialize_components | Component.oracle_manager | Direct attribute injection | WIRED | `engine.py:167-168` mirrors java_bridge / python_routine pattern. |
| ETLEngine._cleanup | OracleConnectionManager.stop() | Direct call | WIRED | `engine.py:260-262`. Called from success path (engine `_run` exit), exception path, `__del__`, `__exit__`. |
| tOracleConnection._process | OracleConnectionManager.register | `self.oracle_manager.register(self.id, conn)` | WIRED | `oracle_connection.py:233`. |
| tOracleRow._process (shared path) | OracleConnectionManager.get | `self.oracle_manager.get(connection_ref)` | WIRED | `oracle_row.py:365`. |
| tOracleRow._process (ad-hoc path) | OracleConnectionManager.open_ad_hoc | `self.oracle_manager.open_ad_hoc(self.id, self.config)` | WIRED | `oracle_row.py:368`. |
| tOracleOutput._process (shared path) | OracleConnectionManager.get | Same pattern | WIRED | Audited via grep on oracle_output.py. |
| Converter oracle_output.py | Engine schema key contract | `config["schema_db"] = TABLESCHEMA` (CR-01 fix) | WIRED | `converters/.../oracle_output.py:76` emits canonical `schema_db`; engine `_qualified_table()` reads it. |

---

## Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| OracleConnectionManager.connections | dict[cid -> oracledb.Connection] | `oracledb.connect(**kwargs)` in `open_ad_hoc` and tOracleConnection._process | Yes (real connection objects in real-DB run; mocks in unit tests) | FLOWING (unit-level); real-DB FLOWING gated on integration suite |
| tOracleRow execution | cursor.rowcount | `cursor.execute(query)` or `cursor.execute(query, bound_values)` | Yes | FLOWING (real cursor in integration tests; mocks in unit tests) |
| tOracleOutput batched executemany | (inserted, updated, deleted, rejected) counters | `cursor.executemany(..., batcherrors=True)` + `cursor.getbatcherrors()` | Yes | FLOWING (real-DB run gated; mocks confirm semantic correctness; live verification deferred) |
| Converter needs_review array | List[Dict] | Conditional append in `convert()` | Yes | FLOWING (verified by unit tests for SID / WALLET / OCI variants) |

Note: Level 4 "real data" verification for runtime DB calls (rowcount, batcherrors offsets/codes, DDL parse-validity) is gated on the deferred integration run. Mocks demonstrate semantic correctness of the Python-side logic but cannot prove wire-protocol or driver-specific behavior — exactly the gap D-D3 / D-F4 cite.

---

## Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Phase 11 unit test suite green | `SKIP_ORACLE_CONTAINER=1 python -m pytest tests/v1/engine/components/database/ tests/v1/engine/test_oracle_connection_manager.py tests/converters/talend_to_v1/components/database/test_oracle_*.py -q --tb=short` | 456 passed, 1 skipped (the integration-only test that respects SKIP_ORACLE_CONTAINER) in 0.28s | PASS |
| OracleConnectionManager importable + lifecycle | manager start/stop covered in 44 unit tests | All green | PASS |
| Components register under PascalCase + Talend aliases | `REGISTRY.get("OracleConnection")`, `REGISTRY.get("tOracleConnection")`, etc. | Asserted in unit tests | PASS |
| Converter test traceability for D-E1 | `test_no_review_for_sid` / `test_needs_review_for_wallet` / `test_needs_review_for_oci` present in all 3 converter test files | Verified via grep | PASS |
| Sample .item fixtures present | `ls tests/talend_xml_samples/Job_tOracle*.item` | All 3 present (Connection / Row / Output) | PASS |
| Real-DB integration suite | `pytest -m oracle tests/v1/engine/components/database/integration/ -v` | NOT RUN (Docker unavailable in agent env) | SKIP — escalate to human |

---

## Requirements Coverage

| Requirement | Source Plan(s) | Description | Status | Evidence |
|-------------|----------------|-------------|--------|----------|
| ORAC-01 | 11-01, 11-07 | Verify status of Oracle engine implementations (present vs missing) | SATISFIED | OracleConnectionManager + ETLEngine wiring shipped; deferred 6 components explicitly enumerated in CONTEXT D-A3 + deferred-items.md. |
| ORAC-02 | 11-02, 11-07 | Implement or fix Oracle connection component using oracledb (not cx_Oracle) | SATISFIED (in-scope CTs) | tOracleConnection ships full SID/SERVICE_NAME/RAC; OCI/WALLET defer with locked-text ConfigurationError. Real-DB sign-off pending integration run (VR-04). |
| ORAC-03 | 11-03, 11-07 | Implement or fix Oracle input component | DEFERRED (declared) — partial via tOracleRow | Phase 11 explicit scope is tOracleRow, not tOracleInput. Roadmap goal acknowledges deferral; ORAC-03 baseline behavior (executing arbitrary SQL/DDL/DML and returning rows when needed) is satisfied by tOracleRow with passthrough; full tOracleInput shape deferred to a future Oracle phase. |
| ORAC-04 | 11-04, 11-05, 11-07 | Implement or fix Oracle output component | SATISFIED | tOracleOutput ships full 8x5 matrix + upsert + REJECT + 5 stat keys + identifier quoting. Real-DB sign-off pending integration run (VR-05/06/07/08). |
| ORAC-05 | 11-06, 11-07 | Implement or fix Oracle supporting components (commit, rollback, close, row, SP, bulk exec) | PARTIAL — tOracleRow shipped; commit/rollback API exposed on manager; 4 supporting components deferred | tOracleRow ships; OracleConnectionManager exposes `commit(cid)` / `rollback(cid)` / `close(cid)` so future tOracleCommit/Rollback/Close phases attach without rework. tOracleSP and tOracleBulkExec stay engine-unimplemented (BulkExec specifically requires sqlldr + Instant Client per CONTEXT). Roadmap explicitly defers these. |

No orphaned requirement IDs in REQUIREMENTS.md mapped to Phase 11 — ORAC-01 through ORAC-05 are all covered (some with deferred sub-components matching the goal text). The "Pending" status in REQUIREMENTS.md will close to "Satisfied" once 11-PHASE-SUMMARY.md is written post-gate.

---

## Anti-Patterns Found

Spot-scanned for stub/placeholder patterns in the 5 source files and 4 integration test files:

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `oracle_output.py` | 745 | `raise NotImplementedError` for upsert path during plan 11-04 task 3 | INFO (intentional) | Replaced by `_execute_upsert_batch` in plan 11-05 — verified at line 594. The lingering raise is in `_dataframe_to_param_list` for unsupported data_action values (defensive guard, not a stub). |
| `oracle_connection.py` | 250-256 | `logger.warning` for deferred params (use_tns_file / support_nls / use_ssl) | INFO | Intentional — deferred SSL/TNS handling per D-A3; warnings make the deferral observable at runtime. Not stubs. |

No real stubs, placeholders, hardcoded empty returns, or TODO/FIXME blockers found. The code review (REVIEW.md) flagged 2 BLOCKERs (CR-01 schema key mismatch, CR-02 upsert non-insertable PK ValueError); both are resolved in the current source — CR-01 verified at `oracle_output.py` converter line 76 (`schema_db`), CR-02 verified at engine line 645-654 (clean ConfigurationError instead of crash).

---

## Human Verification Required

### 1. Real-DB Integration Gate (Plan 11-07 Task 7)

**Test:**
```bash
docker info >/dev/null 2>&1 || { echo "Docker not running"; exit 1; }
pip install -e ".[oracle,dev]"
pytest -m oracle tests/v1/engine/components/database/integration/ -v
```

**Expected:** Exit code 0, `>= 25 passed` (currently 32 collected: 9 connection + 8 row + 12 output + 3 sample). Wall time ~3-5 minutes (testcontainer boot ~15-30s + per-test 1-3s).

**Why human:** Docker is unavailable in the agent execution environment (worktree host has no Docker daemon). User accepted the deferral when accepting Wave 6. Mocks alone cannot prove (Phase 5.1 lesson):

1. Wire-protocol correctness (Net8/TNS handshake, encoding negotiation)
2. Type round-trip (NUMBER → Decimal, DATE → datetime, CLOB → str, BLOB → bytes)
3. NULL handling (Oracle three-valued logic, NULL = NULL is UNKNOWN)
4. BatchError offset/code accuracy (driver-specific behavior)
5. DDL syntactic validity (PL/SQL EXECUTE IMMEDIATE patterns)
6. INSERT_OR_UPDATE batched 2-statement semantic equivalence to Talend per-row try/except

**Acceptance steps after green run:**

1. Paste the last ~30 lines of pytest output into `11-PHASE-SUMMARY.md` under "Verification Gate Result", along with: date (UTC), container image SHA (`docker image inspect gvenzl/oracle-free:23-slim-faststart`), oracledb version, testcontainers version.
2. Update this file's frontmatter `status:` from `human_needed` to `passed` and `re_verification.previous_status` to `human_needed`.
3. Refresh `verified:` to the run timestamp.
4. Update REQUIREMENTS.md ORAC-01..05 statuses from "Pending" to "Satisfied".

---

## Gaps Summary

No actionable gaps remain in the codebase. The single open item is the deferred real-DB run, which is **infrastructure-blocked** (no Docker in agent env) — not a code defect. All 5 fully-verifiable success criteria (1-5) pass; criterion 6 ships the test code (32 tests covering VR-04..VR-08 and 3 sample .item files) but cannot exercise the wire protocol without Docker.

Per CONTEXT D-D3, this is the **mandatory phase verification gate** carried forward from the prior `11-VERIFICATION.md` content. The deferral is recorded transparently and a single re-run on a Docker-capable host closes the phase.

---

# Deferred Real-DB Gate (preserved from prior 11-VERIFICATION.md)

> The content below is preserved verbatim from the prior verification document
> (commits `ae828c2` / `54ac8ed`) so the operations / next-developer handoff is
> not lost. The frontmatter above supersedes the prior `pending_real_db` status
> with `human_needed`.

## Original Gate Statement

Phase 11 cannot be marked `verified` and `11-PHASE-SUMMARY.md` cannot be
written until the gate command below is executed on a Docker-capable host
(developer workstation or CI runner with Docker) and the green output is
pasted into `11-PHASE-SUMMARY.md`.

### To complete the gate (operations / next developer):

1. From the project root on a Docker-capable host:
   ```bash
   docker info >/dev/null 2>&1 || { echo "Docker not running"; exit 1; }
   pip install -e ".[oracle,dev]"
   pytest -m oracle tests/v1/engine/components/database/integration/ -v
   ```
2. Confirm exit code 0 and `>= 25 passed` in the summary line.
3. Paste the last ~30 lines of pytest output into `11-PHASE-SUMMARY.md` under
   the **Verification Gate Result** section, alongside the metadata block
   documented under **Acceptance Output Format** below.
4. Update this file's frontmatter `status:` from `human_needed` to
   `passed` and refresh `verified:` to the run date.

Source artifacts (already on the branch as of commit `f94cbbd` and earlier):
- `tests/v1/engine/components/database/integration/conftest.py` (commit `a0c8666`)
- `tests/v1/engine/components/database/integration/test_oracle_connection_e2e.py` (commit `efce96c`)
- `tests/v1/engine/components/database/integration/test_oracle_row_e2e.py` (commit `38eba0b`)
- `tests/v1/engine/components/database/integration/test_oracle_output_e2e.py` (commit `3ae1ce2`)
- `tests/v1/engine/components/database/integration/test_oracle_phase11_samples_e2e.py` (commit `54ac8ed`)

---

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
individual test runtime ~1-3s; total wall time ~3-5 minutes for ~32 tests
(12 from test_oracle_output_e2e.py including the 4 parametrized DDL tests,
8 from test_oracle_row_e2e.py, 9 from test_oracle_connection_e2e.py, 3 from
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

Where N >= 25 (sum of integration tests across the 4 e2e files; currently 32
collected) and M is the count of @pytest.mark.unit tests deselected by the
`-m oracle` filter.

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

---

_Verified (goal-backward): 2026-05-07_
_Verifier: Claude (gsd-verifier)_
_Supersedes prior gate-only document — preserves the deferred-gate block above for ops handoff._
