
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
