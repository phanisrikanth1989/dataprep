
## Phase 0 closeout — 2026-05-18

Phase 0 (foundational fixes) is complete. Six tasks landed:

- **0.1** Backup `map.py` -> `map_legacy.py`, stub the new `map/` package
- **0.2** Java side: `setContext`/`setGlobalMap` accept `Object`; `__errors__`
  Arrow reads `stackTraces` as `Map<Integer, String>`
- **0.3** JAR rebuilt with the new Java; smoke tests green
- **0.4** `bridge.py` drops `str(value)` coercion in setters; type-fidelity
  tests added; bonus DateConverter `JavaClass` fix (Py4J `GatewayClient`
  has no `.jvm` attr)
- **0.5** `context_manager.py` `id_Date` converter parses to date/datetime
  object; new tests added; xfail markers rebalanced for the new path
- **0.6** `bridge.py` `_reconcile_schema_to_df` raises `ConfigurationError`
  for any DataFrame column without a declared type

### Pre-flight baseline (recorded before Task 0.1)
- transform suite: 1933 passed, 1 skipped, 13 xfailed, 0 failed

### Post-Phase-0 baseline (recorded 2026-05-18)
- transform suite: 1935 passed, 1 skipped, 11 xfailed, 0 failed
- broader suite (excluding oracle/integration): 2 failed, 8298 passed, 4 skipped, 11 xfailed

### Known case-(a) failures to triage in Phase 8

These tests codify the old buggy behavior and must be updated or deleted
rather than reverted:

- `tests/v1/engine/test_context_manager.py::TestContextManagerTypeConversion::test_id_date_stays_string`
  Asserts `cm.get("val") == "2024-01-15"` (str). After Task 0.5, `id_Date`
  returns `datetime.datetime(2024, 1, 15, 0, 0)`. The test was codifying
  the str-coercion bug.

- `tests/v1/engine/test_context_manager.py::TestENG05Regression::test_date_stays_as_string`
  Asserts `result == "2024-01-15"` (str). Same root cause as above —
  `id_Date` now returns a datetime object, not a string.

### XFAIL marker rebalance (from Task 0.5)

See the section below. Net: +2 strict xfails (-2 promoted, +4 added).
Phase 8 triage will decide whether the 4 new ones repurpose or delete.

### Next phase

Phase 1 — map_bridge_sync.py. Start with Task 1.1
(push_runtime_state_to_bridge implementation + tests).

---

## Task 0.5 — test rebalance notes (2026-05-18)

Task 0.5 (`_TYPE_CONVERTERS['id_Date']` from `str` to `_parse_talend_date`)
required the following test marker rebalance:

- **Removed** `_XFAIL_DATE_CTX_STR_COERCION` xfail markers from the 2
  `test_type_cell[column-date_pydate-context]` and
  `[column-date_pydatetime-context]` cells. The bug they tracked is fixed.
- **Deleted** the now-dead `_XFAIL_DATE_CTX_STR_COERCION` constant.
- **Added** `_XFAIL_DATE_CTX_PARSEDATE_BIND` xfail markers to the 4
  `test_datetime_format_parse[context-*]` cells. These tests assume the
  legacy str-coerced id_Date behavior (`parseDate(String, String)` works).
  After Task 0.5, id_Date arrives in Groovy as `java.util.Date`, so
  `parseDate(String, Date)` raises MissingMethodException — the intended
  trade-off for Talend parity. Phase 8 triage will either delete or
  repurpose these 4 cells.

Net xfail count change: +4 - 2 = +2 strict xfails (4 context-* parsedate
cells xfailed, 2 context-column type-cell xfails promoted to active).
