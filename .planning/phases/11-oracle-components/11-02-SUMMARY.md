---
phase: 11-oracle-components
plan: 02
subsystem: engine-components
tags: [engine, oracle, component, connection, security]

# Dependency graph
requires:
  - phase: 11-oracle-components
    plan: 01
    provides: "OracleConnectionManager.register(cid, conn) API; ETLEngine auto-detect + injection of oracle_manager into Oracle components"
  - phase: 03-engine-component-pattern
    provides: "BaseComponent + @REGISTRY.register decorator pattern; ConfigurationError exception hierarchy"
provides:
  - "OracleConnection engine component (~225 lines) with @REGISTRY.register triple-alias (OracleConnection / tOracleConnection / tDBConnection)"
  - "5-CT dispatch logic: ORACLE_SID / ORACLE_SERVICE_NAME / ORACLE_RAC succeed; ORACLE_OCI / ORACLE_WALLET raise ConfigurationError with locked D-A3 wording"
  - "T-11-02 mitigation: password never logged, never pushed to globalMap; verified by TestPasswordNotLogged regression suite"
  - "T-11-05 mitigation: OCI/Wallet error text contains no wallet path or auth detail; verified by TestProcessUnsupportedTypes"
  - "Talend-parity globalMap metadata strings (connectionType_<cid>, dbschema_<cid>, username_<cid>); credential intentionally absent"
  - "23 mock-based unit tests covering registration, validation, all 5 CT paths, AUTO_COMMIT, globalMap metadata, password-not-logged regression, manager wiring guard, port coercion"
affects: [11-03, 11-04, 11-05, 11-06, 11-07]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Phase 7.1 Rule 12 (D-F3): _validate_config does structural-only checks (enum + required keys); content checks (OCI/Wallet refusal, URL syntax) live in _process()"
    - "Manager-mediated lifecycle: live oracledb.Connection registers with OracleConnectionManager via self.oracle_manager.register(cid, conn); never enters globalMap"
    - "Triple-alias decorator @REGISTRY.register('OracleConnection', 'tOracleConnection', 'tDBConnection') so converter-emitted Talend names resolve to the same engine class"
    - "Lazy import of oracledb inside _process() keeps the [oracle] extra optional"
    - "Mock-based unit test pattern: patch.dict(sys.modules, {'oracledb': MagicMock()}) for lazy-imported drivers"

key-files:
  created:
    - "src/v1/engine/components/database/oracle_connection.py (235 lines, 1 class, 5-CT dispatch + manager.register + globalMap metadata)"
    - "tests/v1/engine/components/database/test_oracle_connection.py (316 lines, 23 tests, mock-based unit suite)"
  modified:
    - "src/v1/engine/components/database/__init__.py (now imports OracleConnection to trigger @REGISTRY.register at import time; was an empty placeholder from plan 11-01)"

key-decisions:
  - "Implementation file is exactly the plan's <action> block (verbatim). Module docstring, imports, _validate_config, and _process are unchanged from plan."
  - "_validate_config is structural-only per Rule 12 / D-F3. ORACLE_OCI passes _validate_config; the refusal lives in _process. Test TestValidateConfig.test_oci_passes_validate_config asserts this is intentional."
  - "T-11-02 enforcement: the kwargs dict (which holds the credential) is NEVER referenced in any logger call; only cid + connection_type appear in info messages. globalMap.put is invoked only with the 3 metadata strings. TestPasswordNotLogged.test_full_process_does_not_log_password and TestGlobalMapMetadata.test_never_writes_password_to_globalmap assert the regression."
  - "T-11-05 enforcement: ORACLE_OCI / ORACLE_WALLET refusal message contains only 'thick_mode' + 'Instant Client' + 'deferred items' wording. Cross-test TestPasswordNotLogged.test_password_not_in_oci_error_text also verifies the credential never leaks via the error text."
  - "Test deviation from plan: the plan's TestGlobalMapMetadata.test_never_writes_password_to_globalmap uses gm._data which does not exist on the GlobalMap class. Replaced with gm.get_all() (the canonical public accessor; GlobalMap stores its data in self._map internally). Behaviorally identical."

requirements-completed: [ORAC-02]

# Metrics
duration: ~12 min
completed: 2026-05-07
---

# Phase 11 Plan 02: OracleConnection Engine Component Summary

**OracleConnection engine component (~235 lines) with 5-CT dispatch, manager.register integration, T-11-02 / T-11-05 security mitigations, and 23 mock-based unit tests covering every behavior in the plan.**

## Performance

- **Duration:** ~12 min
- **Tasks:** 2 (component implementation + unit tests)
- **Files modified:** 3 (1 created in src, 1 modified in src, 1 created in tests)
- **Test count:** 23 new (all passing)

## Accomplishments

- `OracleConnection` class lives at `src/v1/engine/components/database/oracle_connection.py` with the canonical triple-alias decorator `@REGISTRY.register("OracleConnection", "tOracleConnection", "tDBConnection")` so converter-emitted Talend names resolve to the same engine class
- 5-CT dispatch in `_process()`:
  - `ORACLE_SID` -> `oracledb.connect(user, password, host, port=int, sid=dbname)`
  - `ORACLE_SERVICE_NAME` -> `oracledb.connect(user, password, host, port=int, service_name=dbname or local_service_name)`
  - `ORACLE_RAC` -> `oracledb.connect(user, password, dsn=rac_url.strip())` (raises if rac_url empty)
  - `ORACLE_OCI` / `ORACLE_WALLET` -> `ConfigurationError` with locked D-A3 wording (T-11-05 mitigation: no wallet path, no hostname, no auth detail leaked)
- `_validate_config` is structural-only per Phase 7.1 Rule 12 / D-F3: it checks `connection_type` is one of the 5 enum values and that `user` + `password` keys are present. Content checks (OCI/Wallet refusal, RAC URL syntax) live in `_process` after context resolution.
- `oracle_manager.register(self.id, conn)` is called immediately after `oracledb.connect()` succeeds (and after `auto_commit` honoring) so the live `Connection` lives in the manager keyed by component id, NEVER in globalMap (D-A1).
- globalMap publishes 3 Talend-parity metadata strings only: `connectionType_<cid>`, `dbschema_<cid>`, `username_<cid>`. Credential is NEVER pushed (T-11-02 mitigation).
- `AUTO_COMMIT=true` sets `conn.autocommit = True` immediately after connection open (D-A4).
- ASCII-only logging; `oracledb` import is deferred inside `_process` so the `[oracle]` extra remains optional for non-Oracle jobs.
- Deferred-feature parameters (`use_tns_file`, `support_nls`, `use_ssl`) emit a WARNING when `True`; non-default `encoding` emits an INFO that thin mode does not honor it.
- 23 mock-based unit tests in `tests/v1/engine/components/database/test_oracle_connection.py` cover every behavior in the plan; plan 11-01's 43-test manager suite still passes (no regression).

## Task Commits

Each task was committed atomically:

1. **Task 1: Add OracleConnection engine component (5-CT dispatch, manager registration, ASCII logging)** -- `f950f11` (feat)
2. **Task 2: Add OracleConnection unit tests (23 tests, T-11-02 password regression, D-A3 OCI/Wallet refusal)** -- `ad8160e` (test)

## Test Coverage Map

23 tests in `tests/v1/engine/components/database/test_oracle_connection.py`, all passing:

- **TestRegistration (1):** triple-alias resolves to OracleConnection class
- **TestValidateConfig (4):** invalid connection_type raises; missing user raises; missing password raises; ORACLE_OCI passes (content check, not structural -- Rule 12)
- **TestProcessOracleSid (3):** SID kwargs (user/password/host/port=int/sid); manager.register call site; orchestration return shape `{"main": None, "reject": None}`
- **TestProcessOracleServiceName (1):** service_name kwarg present; sid kwarg absent
- **TestProcessOracleRac (2):** dsn kwarg with stripped URL; empty rac_url raises ConfigurationError
- **TestProcessUnsupportedTypes (2):** ORACLE_OCI raises with D-A3 message text; ORACLE_WALLET raises with D-A3 message text
- **TestAutoCommit (2):** auto_commit=True sets conn.autocommit; default False leaves unchanged
- **TestGlobalMapMetadata (3):** writes connectionType_/dbschema_/username_; NEVER writes password; NEVER stores live Connection (D-A1)
- **TestPasswordNotLogged (2):** T-11-02 -- credential absent from caplog records during full _process flow; credential absent from OCI error text
- **TestManagerWiring (1):** _process raises ConfigurationError when oracle_manager=None
- **TestPortCoercion (2):** string "1521" coerced to int 1521; missing port defaults to 1521

## Verification (per <verification> block)

- [x] Registration smoke test: `python -c "from src.v1.engine.components import database; from src.v1.engine.component_registry import REGISTRY; assert REGISTRY.get('tOracleConnection') is not None"` -- OK
- [x] ASCII-only verification: both `oracle_connection.py` and `test_oracle_connection.py` round-trip through `.encode('ascii')` without error
- [x] T-11-02 negative regression: `grep -E "logger\.(info|error|warning|debug).*password" src/v1/engine/components/database/oracle_connection.py | grep -v '^#' | wc -l` == 0
- [x] No regression on plan 11-01: `pytest tests/v1/engine/test_oracle_connection_manager.py -x` -- 43 passed
- [x] Plan 11-02 tests pass: `pytest tests/v1/engine/components/database/test_oracle_connection.py -x` -- 23 passed

## Decisions Made

- **Verbatim implementation of the plan's `<action>` block.** Module docstring, imports, `_VALID_CONNECTION_TYPES` frozenset, `_validate_config`, and `_process` are exactly the plan's specification. Where the plan said "approximately 250 lines" the actual file is 235 lines because no logic was elided.
- **Phase 7.1 Rule 12 (D-F3) is enforced strictly.** `_validate_config` does NOT inspect `connection_type` for OCI/Wallet refusal -- only that the value is in the closed enum set. The refusal lives in `_process` with the locked D-A3 message text. The TestValidateConfig.test_oci_passes_validate_config test makes this contract explicit.
- **T-11-02 is enforced by code structure, not just discipline.** The kwargs dict (which holds the credential) is built as a local variable and passed into `oracledb.connect(**kwargs)` directly; it is NEVER referenced in any logger call. The only logger call site that fires after kwargs build is `logger.info("[%s] Opening Oracle connection (type=%s)", self.id, ct)` which prints exactly the cid + the connection_type literal.
- **T-11-05 is enforced via the locked D-A3 wording.** The OCI/Wallet refusal message text is `f"[{self.id}] CONNECTION_TYPE {ct!r} requires oracledb thick mode + Oracle Instant Client. Set oracle_config.thick_mode=true in job config and install Instant Client on the host. Tracked in deferred items."` -- it contains no wallet path, no hostname, no auth detail. The cross-test TestPasswordNotLogged.test_password_not_in_oci_error_text asserts the credential is also absent from this error text.
- **Test deviation from plan:** the plan's TestGlobalMapMetadata.test_never_writes_password_to_globalmap proposes `for key, value in gm.items() if hasattr(gm, "items") else gm._data.items()`. Neither attribute is a documented public surface on `GlobalMap` (it stores data in `self._map`). The test now uses `gm.get_all().items()` -- the canonical public accessor returning a copy of the internal map. Behaviorally identical, no T-11-02 coverage loss. Documented as a minor plan deviation.

## Deviations from Plan

### Out-of-scope but documented

**1. [Rule 1 - Bug] GlobalMap accessor in plan tests references nonexistent `_data` attribute**
- **Found during:** Task 2 (writing the tests)
- **Issue:** plan's `test_never_writes_password_to_globalmap` and `test_never_pushes_live_connection_to_globalmap` both reference `gm._data` and `gm._data.items()`. The actual `GlobalMap` class at `src/v1/engine/global_map.py:18` uses `self._map`, not `self._data`. The plan's `hasattr(gm, "items") else gm._data.items()` fallback is a no-op because `GlobalMap` does not implement `items()` either.
- **Fix:** replaced both occurrences with `gm.get_all().items()` -- the documented public accessor at `global_map.py:100` that returns a copy of the internal map. Same behavior, same coverage. Tests still assert (a) no key contains "password" (case-insensitive), (b) no value's str repr contains "secret_hunter2", (c) no value is the mock_conn live Connection, (d) no value is callable.
- **Files modified:** `tests/v1/engine/components/database/test_oracle_connection.py`
- **Commit:** ad8160e

No other deviations. Plan executed verbatim otherwise.

## Issues Encountered

None. All 23 tests passed on first run after the GlobalMap accessor fix above; no flakiness; no auth gates.

## Threat Flags

None. The threat surface introduced by this plan (the OCI/Wallet error path, the globalMap.put call sites, and the logger.info call site after kwargs build) is exactly what the plan's `<threat_model>` enumerates as `T-11-02` and `T-11-05`. Mitigations are in place and asserted by 7 distinct test cases (TestPasswordNotLogged x 2, TestGlobalMapMetadata x 3, TestProcessUnsupportedTypes x 2). No new surface introduced.

## Next Phase Readiness

- Plan 11-03 (`tOracleRow`) can now reference an upstream `tOracleConnection` via `use_existing_connection=true` + `connection=<cid>` and resolve the live Connection through `oracle_manager.get(cid)` -- the registration call site is in place at `oracle_connection.py:_process()`.
- Plan 11-04 (`tOracleOutput`) follows the same shape as plan 11-03 (use_existing_connection + connection=<cid>).
- Plan 11-05 (commit/rollback/close) was already wired in plan 11-01 via `oracle_manager.commit(cid)` / `rollback(cid)` / `close(cid)`; those methods now have a real upstream registration path through `OracleConnection._process` to look up against.
- Plan 11-06 (converter alignment) can confirm the converter emits `connection_type` / `host` / `port` / `dbname` / `user` / `password` / `schema_db` / `auto_commit` / `local_service_name` / `rac_url` keys exactly as the engine consumes them (the engine accepts the documented superset).
- Plan 11-07 (real-DB integration) can wire a live testcontainer Oracle into `OracleConnection._process` via `pytest.mark.oracle` -- the mock-based unit suite established here will not interfere because of `patch.dict(sys.modules, {"oracledb": MagicMock()})` scoping.

## Self-Check: PASSED

Verification (all checked):
- [x] FOUND: src/v1/engine/components/database/oracle_connection.py
- [x] FOUND: src/v1/engine/components/database/__init__.py (modified to import OracleConnection)
- [x] FOUND: tests/v1/engine/components/database/test_oracle_connection.py
- [x] FOUND commit f950f11 (Task 1: feat -- engine component)
- [x] FOUND commit ad8160e (Task 2: test -- 23 unit tests)
- [x] pytest tests/v1/engine/components/database/test_oracle_connection.py: 23 passed
- [x] pytest tests/v1/engine/test_oracle_connection_manager.py: 43 passed (no regression on plan 11-01)
- [x] Registration smoke test passes
- [x] ASCII-only verification: both files clean
- [x] T-11-02 negative grep: 0 password-logging call sites
- [x] T-11-05 negative grep: OCI error text contains thick_mode + Instant Client; no wallet path or hostname or auth detail
- [x] All Task 1 acceptance criteria met (10/10)
- [x] All Task 2 acceptance criteria met (6/6)
- [x] Plan-level success criteria met (7/7)

---
*Phase: 11-oracle-components*
*Completed: 2026-05-07*
