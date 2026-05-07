---
phase: 11-oracle-components
plan: 03
subsystem: engine-components
tags: [engine, oracle, component, sql-execution, prepared-statement]

# Dependency graph
requires:
  - phase: 11-oracle-components
    plan: 01
    provides: "OracleConnectionManager.get(cid_ref) / open_ad_hoc(cid, config) / close(cid) APIs; ETLEngine auto-injection of oracle_manager into Oracle components"
  - phase: 11-oracle-components
    plan: 02
    provides: "OracleConnection registers a live oracledb.Connection under self.id; downstream tOracleRow looks it up via use_existing_connection=true + connection=<cid>"
  - phase: 03-engine-component-pattern
    provides: "BaseComponent + @REGISTRY.register decorator pattern; ConfigurationError exception hierarchy"
provides:
  - "OracleRow engine component (~340 lines) with @REGISTRY.register dual-alias (OracleRow / tOracleRow)"
  - "19-key PARAMETER_TYPE coercion table = Talaxie's 16 verified + 3 RESEARCH.md inferred aliases (Integer, BigInteger, Timestamp)"
  - "Both connection acquisition paths: shared (manager.get) and ad-hoc (manager.open_ad_hoc + manager.close in finally)"
  - "USE_NB_LINE counter publishes cursor.rowcount to f'{cid}_<NB_LINE_*>' per the chosen enum value (D-C5); DDL/unknown rowcount writes 0 + WARNING"
  - "Resolved query string published to f'{cid}_QUERY' globalMap key (D-C8)"
  - "PROPAGATE_RECORD_SET=true raises ConfigurationError with D-C4 wording in _process (content check, Rule 12)"
  - "47 mock-based unit tests covering registration, validation, both connection paths, all 19 PARAMETER_TYPE coercions, USE_NB_LINE counter (4 enum cases + DDL edge cases), PROPAGATE_RECORD_SET refusal, commit behavior, passthrough"
affects: [11-04, 11-05, 11-06, 11-07]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Module-level coercer functions + dispatch dict (_PARAM_TYPE_COERCERS) -- pure functions tested in isolation"
    - "Phase 7.1 Rule 12 (D-F3): _validate_config does structural-only checks (required keys + closed enum); content checks (PROPAGATE_RECORD_SET refusal) live in _process"
    - "try/finally cursor lifecycle + ad-hoc connection close-on-exception (T-11-03 mitigation)"
    - "Talaxie XML inspection at plan-start to verify CLOSED_LIST enums BEFORE writing the dispatch table (Open Q 2 protocol)"

key-files:
  created:
    - "src/v1/engine/components/database/oracle_row.py (~340 lines, OracleRow class + 11 module-level coercer helpers + _PARAM_TYPE_COERCERS dispatch table + _coerce_prepared_param)"
    - "tests/v1/engine/components/database/test_oracle_row.py (~564 lines, 27 def test_ -> 47 parametrized cases)"
  modified:
    - "src/v1/engine/components/database/__init__.py (now imports OracleRow alongside OracleConnection to trigger @REGISTRY.register at import time)"

key-decisions:
  - "Open Q 2 resolved by direct Talaxie XML fetch (verified 2026-05-07). Talaxie's PARAMETER_TYPE CLOSED_LIST has 16 values: BigDecimal, Blob, Boolean, Byte, Bytes, Clob, Date, Double, Float, Int, Long, Object, Short, String, Time, Null. This DIFFERS from RESEARCH.md's inferred 16-list -- Talaxie HAS Blob/Clob/Null (additions) and LACKS Integer/BigInteger/Timestamp (RESEARCH inferences not actually in the XML)."
  - "Decision: support BOTH the verified Talaxie 16 AND the 3 RESEARCH-inferred aliases (Integer, BigInteger, Timestamp) for total 19 entries. Reasoning: defensive against converter variants or custom Talend palettes that might emit the inferred names; zero downside since Integer/BigInteger map to the same _coerce_int as Int/Long/Short/Byte and Timestamp gets its own coercer. This protects feature parity even if the converter is later updated to emit the 'extended' names."
  - "PROPAGATE_RECORD_SET refusal lives in _process (Rule 12 / D-F3). _validate_config passes a config with propagate_record_set=True; the refusal fires only after context resolution. Test TestValidateConfig.test_propagate_record_set_passes_validate_config + TestPropagateRecordSetRefusal pin this contract."
  - "Verified manager.get() / open_ad_hoc() / close() interfaces are stable from plan 11-01; no changes needed in oracle_connection_manager.py."
  - "ad-hoc connection close-on-exception: TestAdHocCloseInFinally.test_ad_hoc_closed_when_execute_raises asserts try/finally semantics. Companion test test_shared_connection_not_closed_when_execute_raises asserts we MUST NOT close shared connections (those are owned by upstream tOracleConnection)."
  - "Bound parameter values are NEVER logged (T-11-02 partial). logger.info logs cid + rowcount + use_nb_line enum -- never the values list."

requirements-completed: [ORAC-03]

# Metrics
duration: ~14 min
completed: 2026-05-07
---

# Phase 11 Plan 03: OracleRow Engine Component Summary

**OracleRow engine component (~340 lines) with 19-type prepared-statement coercion (Talaxie 16 verified + 3 inferred), USE_NB_LINE counter, PROPAGATE_RECORD_SET refusal, resolved-query globalMap publish, and 47 mock-based unit tests.**

## Performance

- **Duration:** ~14 min
- **Tasks:** 3 (Open Q 2 docstring stub + component implementation + unit tests)
- **Files modified:** 3 (1 modified in src, 1 created in src, 1 created in tests)
- **Test count:** 47 new (all passing); 0 regressions across 66 existing Oracle tests

## Accomplishments

- `OracleRow` class lives at `src/v1/engine/components/database/oracle_row.py` with `@REGISTRY.register("OracleRow", "tOracleRow")` so both names resolve to the same engine class
- **Open Q 2 resolved at plan-start:** fetched the Talaxie `tOracleRow_java.xml` and extracted the actual `PARAMETER_TYPE` CLOSED_LIST. The verified 16 values are *different* from RESEARCH.md's inferred 16-list:
  - Talaxie HAS:    `Blob`, `Clob`, `Null` (additions)
  - Talaxie LACKS:  `Integer`, `BigInteger`, `Timestamp` (RESEARCH inferences)
  - The component supports the **union** of both sets (19 total) for robust feature parity.
- 11 module-level coercer functions (`_coerce_string`, `_coerce_int`, `_coerce_decimal`, `_coerce_bool`, `_coerce_float`, `_coerce_date`, `_coerce_timestamp`, `_coerce_time`, `_coerce_bytes`, `_coerce_clob`, `_coerce_null`, `_passthrough`) each return `None` on `None` input -- safe for SQL NULL binds
- `_PARAM_TYPE_COERCERS` dispatch dict maps 19 PARAMETER_TYPE names to their coercers; `_coerce_prepared_param()` performs the lookup and raises `ConfigurationError` with the supported list on unknown type
- `_validate_config()` is structural-only (Rule 12 / D-F3): checks `query` key, `use_nb_line` enum, `set_preparedstatement_parameters` list-of-dicts shape, and parameter_type closed-list membership. Does NOT inspect `propagate_record_set` (content check)
- `_process()` flow:
  1. Refuse PROPAGATE_RECORD_SET=true (D-C4) BEFORE acquiring connection
  2. Acquire connection: shared via `oracle_manager.get(connection_ref)` OR ad-hoc via `oracle_manager.open_ad_hoc(self.id, self.config)`
  3. Build cursor; if `use_preparedstatement=true`, sort params by `parameter_index`, coerce each value, call `cursor.execute(query, [vals])`; otherwise `cursor.execute(query)` only
  4. D-C5: Read `cursor.rowcount`. If negative or None (DDL/unknown), write 0 to `f"{cid}_<USE_NB_LINE>"` + WARNING. Otherwise write the actual rowcount.
  5. D-C8: Write resolved query string to `f"{cid}_QUERY"` globalMap key
  6. Commit only when `conn.autocommit` is False (honor upstream tOracleConnection's auto_commit setting)
  7. finally: close cursor; if owns_connection (ad-hoc path), call `oracle_manager.close(self.id)`
  8. Return `{"main": input_data, "reject": None}` -- input passes through
- `database/__init__.py` updated to import `OracleRow` so `@REGISTRY.register` fires at package import time
- ASCII-only logging; bound parameter values never logged (T-11-02)
- 47 unit tests in `tests/v1/engine/components/database/test_oracle_row.py` cover every behavior in the plan; plan 11-01 (43 tests) and plan 11-02 (23 tests) still pass with zero regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: Open Question 2 resolution -- document verified Talaxie PARAMETER_TYPE enum** -- `4516ecf` (docs)
2. **Task 2: Implement OracleRow engine component (D-C3 / D-C4 / D-C5 / D-C8)** -- `cf8460a` (feat)
3. **Task 3: Add OracleRow unit tests (47 tests, full PARAMETER_TYPE matrix + D-C4/D-C5/D-C8 coverage)** -- `10c78ad` (test)

## Test Coverage Map

47 tests in `tests/v1/engine/components/database/test_oracle_row.py`, all passing:

- **TestRegistration (1):** both aliases resolve to OracleRow class
- **TestValidateConfig (6):** missing query / invalid use_nb_line / set_preparedstatement_parameters not list / entry not dict / unsupported parameter_type; propagate_record_set=True PASSES validate (Rule 12 contract)
- **TestPropagateRecordSetRefusal (1):** D-C4 message with "PROPAGATE_RECORD_SET" + "ResultSet" + "tOracleInput"; manager not touched before refusal
- **TestConnectionAcquisition (3):** USE_EXISTING_CONNECTION=true -> manager.get; =false -> manager.open_ad_hoc + manager.close; oracle_manager=None raises ConfigurationError
- **TestAdHocCloseInFinally (2):** ad-hoc connection closed on execute exception; shared connection NOT closed on execute exception
- **TestSimpleExecute (1):** USE_PREPAREDSTATEMENT=false -> single-arg execute()
- **TestPreparedStatementBindOrder (1):** shuffled parameter_index list ordered to positional binds
- **TestParameterTypeCoercion (19):** parametrized over the 19 supported types -- 16 Talaxie verified + 3 RESEARCH.md inferred aliases. Each case asserts value equality AND exact Python type.
- **TestParameterTypeNullPassthrough (1):** every coercer returns None for None input
- **TestUnknownParameterType (1):** ConfigurationError listing supported set
- **TestUseNbLineCounter (3):** INSERTED / UPDATED / DELETED write rowcount to globalMap
- **TestUseNbLineNone (1):** NONE writes no NB_LINE_* key
- **TestUseNbLineWithDdl (2):** rowcount=-1 and rowcount=None both write 0 + WARNING
- **TestQueryGlobalMapPublish (1):** f"{cid}_QUERY" set to resolved query (D-C8)
- **TestCommitBehavior (2):** conn.commit() only when autocommit False
- **TestPassthrough (2):** DataFrame and None input pass through

## Verification (per <verification> block)

- [x] All 3 task acceptance criteria met (see Task Commits above)
- [x] `pytest tests/v1/engine/components/database/test_oracle_row.py -x` -> **47 passed**
- [x] Registration: `python -c "from src.v1.engine.components import database; from src.v1.engine.component_registry import REGISTRY; assert REGISTRY.get('tOracleRow') is not None"` -> OK
- [x] ASCII verification: both `oracle_row.py` and `test_oracle_row.py` round-trip through `.encode('ascii')` without error
- [x] No regression: `pytest tests/v1/engine/test_oracle_connection_manager.py tests/v1/engine/components/database/test_oracle_connection.py -x` -> **66 passed (43 + 23)**
- [x] Open Q 2 resolved: `grep "Talaxie tOracleRow_java.xml PARAMETER_TYPE enum" src/v1/engine/components/database/oracle_row.py` returns the docstring block with verified types

## Decisions Made

- **Open Q 2 closed by Talaxie XML inspection.** The plan's RESEARCH.md inferred a 16-type list that differed from the actual Talaxie XML in 3 entries each direction. Decision: support the **union** (19 total) so the engine works regardless of which Talend variant emitted the JSON. Cost is one extra dict entry per inferred alias; benefit is robustness against converter changes or custom palettes.
- **`_coerce_clob` is a thin str-coercer.** oracledb thin mode handles long string binds natively; no `oracledb.LOB` wrapping needed at the bind site. The dedicated function name keeps the dispatch table self-documenting (could collapse to `_coerce_string` but the explicit name signals "this is for character LOBs" to readers).
- **`_coerce_null` always returns None regardless of `parameter_value`.** Talaxie's `Null` PARAMETER_TYPE explicitly binds SQL NULL; the PARAMETER_VALUE expression result is intentionally ignored. This matches Talend's runtime semantic where setting type=Null means "this slot is always NULL".
- **`_coerce_blob` aliases to `_coerce_bytes`.** Same coercer; the dispatch entry exists separately so future tweaks (e.g. wrapping with `oracledb.OBJECT` for very large LOBs) can apply only to Blob without touching plain Bytes.
- **PROPAGATE_RECORD_SET refusal happens BEFORE connection acquisition.** Implemented as the first check in `_process` so the test can assert `mock_mgr.get.assert_not_called()` and `mock_mgr.open_ad_hoc.assert_not_called()` -- no resource leak even if a downstream component is misconfigured with PROPAGATE_RECORD_SET=true.
- **`commit()` only when `conn.autocommit` is False.** Mirrors how plan 11-02 honors the upstream tOracleConnection's `auto_commit` config; for shared connections this means tOracleConnection sets autocommit once and downstream tOracleRow respects it. For ad-hoc connections, `manager.open_ad_hoc()` already honors `auto_commit` from the same config dict, so the `getattr(conn, "autocommit", False)` check produces the right answer in both paths.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Plan's RESEARCH.md PARAMETER_TYPE list does not match the actual Talaxie XML**
- **Found during:** Task 1 (Open Q 2 fetch)
- **Issue:** The plan's `<interfaces>` block and Task 2's coercion table list 16 types: `String, Int, Integer, Long, Short, Byte, BigInteger, BigDecimal, Boolean, Float, Double, Date, Timestamp, Time, Bytes, Object`. The verified Talaxie `tOracleRow_java.xml` (lines 333-352) instead has: `BigDecimal, Blob, Boolean, Byte, Bytes, Clob, Date, Double, Float, Int, Long, Object, Short, String, Time, Null`. Three entries are unique to each set.
- **Fix:** Implemented the **union** (19 entries) so feature parity is preserved against either source. Added `_coerce_clob` and `_coerce_null` helpers; mapped `Blob` to `_coerce_bytes` (LOB-as-bytes). Kept `Integer`, `BigInteger`, `Timestamp` as defensive aliases per the plan's contingency note ("If the 16th value is unclear, map to _passthrough with a TODO comment" -- here we mapped to the obvious correct coercer instead because the semantics ARE clear).
- **Files modified:** `src/v1/engine/components/database/oracle_row.py` (module docstring + `_PARAM_TYPE_COERCERS` table)
- **Commit:** `cf8460a` (Task 2)

**2. [Rule 1 - Plan adjustment] Tests added for the 3 Talaxie-only types not in the plan's test matrix**
- **Found during:** Task 3 (writing parametrized matrix)
- **Issue:** the plan's `TestParameterTypeCoercion` parametrize lists 16 cases (the inferred set). The actual Talaxie set has Blob/Clob/Null which were not tested.
- **Fix:** expanded the parametrize to 19 cases (Talaxie's 16 verified + 3 inferred aliases). Each case asserts both value equality and exact Python type. `Null` test asserts the coercer returns None even for non-None input ("ignored_value" -> None).
- **Files modified:** `tests/v1/engine/components/database/test_oracle_row.py`
- **Commit:** `10c78ad` (Task 3)

**3. [Rule 2 - Missing critical functionality] Added test for `set_preparedstatement_parameters` non-dict entry**
- **Found during:** Task 3 (mirroring the plan's TestValidateConfig)
- **Issue:** plan lists "set_preparedstatement_parameters not a list" but not "entry not a dict" even though `_validate_config` also checks the latter. Without a test, that branch is uncovered.
- **Fix:** added `test_set_preparedstatement_parameters_entry_not_dict_raises`. No code change needed -- the validation already exists.
- **Files modified:** `tests/v1/engine/components/database/test_oracle_row.py`
- **Commit:** `10c78ad` (Task 3)

**4. [Rule 2 - Missing critical functionality] Added test asserting shared connection is NOT closed on exception**
- **Found during:** Task 3 (writing TestAdHocCloseInFinally)
- **Issue:** plan's TestAdHocCloseInFinally tests the ad-hoc-closes-on-error case but not the symmetric "shared connection MUST NOT be closed on error" -- a regression that could leak when changing finally semantics.
- **Fix:** added `test_shared_connection_not_closed_when_execute_raises`. Asserts `mock_mgr.close.assert_not_called()` when `use_existing_connection=true` and `execute` raises; cursor is still closed.
- **Files modified:** `tests/v1/engine/components/database/test_oracle_row.py`
- **Commit:** `10c78ad` (Task 3)

**5. [Rule 2 - Missing critical functionality] Added explicit test for use_nb_line=NONE writing no NB_LINE_* key**
- **Found during:** Task 3 (writing TestUseNbLineCounter)
- **Issue:** plan mentions "NONE writes nothing" in must-haves but the test list only parametrizes the 3 non-NONE values. Without a positive test, regressions where NONE accidentally writes `tOracleRow_1_NONE=42` would slip through.
- **Fix:** added `TestUseNbLineNone.test_use_nb_line_none_writes_no_nb_line_key`. Inspects `gm.get_all().keys()` and asserts no key contains "NB_LINE_INSERTED|UPDATED|DELETED".
- **Files modified:** `tests/v1/engine/components/database/test_oracle_row.py`
- **Commit:** `10c78ad` (Task 3)

No other deviations. Plan executed verbatim otherwise.

## Issues Encountered

None. All 47 tests passed on first run; no flakiness; no auth gates; no architectural surprises. The Open Q 2 fetch returned the XML cleanly on first curl.

## Threat Flags

None. The threat surface introduced by this plan is exactly what `<threat_model>` enumerates as `T-11-01` / `T-11-02` / `T-11-03`. Mitigations:

- **T-11-01 (SQL injection via QUERY field):** mitigated by USE_PREPAREDSTATEMENT positional-bind path (19-type coercion converts each value before binding); module docstring documents this is the SAFE channel. Residual risk (raw QUERY with context.var interpolation) is documented and accepted -- trust boundary is internal Citi job authors.
- **T-11-02 (information disclosure via logging):** mitigated by the `logger.info` template `"[%s] Executed query (rowcount=%s, use_nb_line=%s)"` which prints only the cid + the rowcount integer + the enum value. Bound parameter values (which may be PII) are NEVER referenced in any logger call. Negative grep verifies: `grep -E "logger\.(info|error|warning|debug).*bound_values" src/v1/engine/components/database/oracle_row.py` returns 0 matches.
- **T-11-03 (DoS / resource leak via ad-hoc connection):** mitigated by `try/finally` wrapping cursor execution; ad-hoc connection closed via `oracle_manager.close(self.id)` in finally branch. `TestAdHocCloseInFinally.test_ad_hoc_closed_when_execute_raises` is the regression test.

No new threat surface introduced. PROPAGATE_RECORD_SET refusal eliminates a class of would-be issues (Talend's live-ResultSet-as-FLOW pattern is structurally incompatible with DataFrame semantics, so we refuse rather than half-implement).

## Next Phase Readiness

- Plan 11-04 (`tOracleOutput`) follows the same shape: same connection acquisition paths, same use-nb-line counter (with INSERT/UPDATE/DELETE per-row stats), same prepared-statement coercion table. It can directly import `_PARAM_TYPE_COERCERS` and `_coerce_prepared_param` from `oracle_row.py` if it wants to share the dispatch table, OR replicate the table privately if 11-04 wants to add Output-specific types (e.g. RETURNING_INTO clauses). Recommendation: factor `_PARAM_TYPE_COERCERS` + `_coerce_prepared_param` into `src/v1/engine/components/database/_param_coercion.py` in plan 11-04 if the reuse is meaningful.
- Plan 11-05 (commit/rollback/close) can call `oracle_manager.commit(cid)` / `rollback(cid)` / `close(cid)` against connections that tOracleConnection registered -- the lookup path through `manager.get()` is exercised here.
- Plan 11-06 (converter alignment) can confirm the converter at `src/converters/talend_to_v1/components/database/oracle_row.py` emits `query` / `use_nb_line` / `use_preparedstatement` / `set_preparedstatement_parameters` keys exactly as the engine consumes them. The current converter (read at plan-start) already emits `_PREPARED_FIELDS = ("PARAMETER_INDEX", "PARAMETER_TYPE", "PARAMETER_VALUE")` correctly.
- Plan 11-07 (real-DB integration) can wire a live testcontainer Oracle into `OracleRow._process` via `pytest.mark.oracle` -- the mock-based unit suite established here will not interfere because the import path for `oracledb` is mediated through `self.oracle_manager` (the manager handles the lazy import).

## Self-Check: PASSED

Verification (all checked):
- [x] FOUND: src/v1/engine/components/database/oracle_row.py
- [x] FOUND: src/v1/engine/components/database/__init__.py (modified to import OracleRow)
- [x] FOUND: tests/v1/engine/components/database/test_oracle_row.py
- [x] FOUND commit 4516ecf (Task 1: docs -- Open Q 2 docstring stub)
- [x] FOUND commit cf8460a (Task 2: feat -- OracleRow engine component)
- [x] FOUND commit 10c78ad (Task 3: test -- 47 unit tests)
- [x] pytest tests/v1/engine/components/database/test_oracle_row.py: 47 passed
- [x] pytest tests/v1/engine/test_oracle_connection_manager.py: 43 passed (no regression)
- [x] pytest tests/v1/engine/components/database/test_oracle_connection.py: 23 passed (no regression)
- [x] Registration smoke test passes
- [x] ASCII-only verification: both files clean
- [x] Task 1 acceptance criteria met (3/3)
- [x] Task 2 acceptance criteria met (8/8 -- registration grep, _PARAM_TYPE_COERCERS count, type list match, PROPAGATE_RECORD_SET, NB_LINE refs, _QUERY refs, ASCII, smoke test)
- [x] Task 3 acceptance criteria met (5/5 -- file exists, pytest exits 0, def test_ count >= 25 (got 27), PROPAGATE_RECORD_SET >= 1, _coerce_prepared_param/_PARAM_TYPE_COERCERS >= 3, ASCII)
- [x] Plan-level success criteria met (7/7 -- registration, both connection paths, full PARAMETER_TYPE coverage, USE_NB_LINE + DDL edge, PROPAGATE_RECORD_SET refusal, _QUERY publish, autocommit honored, Open Q 2 resolved)

---
*Phase: 11-oracle-components*
*Completed: 2026-05-07*
