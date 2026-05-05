---
phase: 10-iterate-support
plan: "05"
subsystem: converter
tags: [converter, iterate, parallel-extraction, dataclass, engine-gap]

# Dependency graph
requires:
  - phase: 10-01
    provides: BaseIterateComponent lifecycle rebuild (prerequisite for iterate support)
provides:
  - TalendConnection.params Dict[str, str] field capturing all elementParameter values beyond UNIQUE_NAME/CONDITION
  - _parse_connections populates params with all connection-level elementParameter name/value pairs
  - _parse_flows extracts ENABLE_PARALLEL (bool) and NUMBER_PARALLEL (int) from ITERATE-typed connections
  - engine_gap needs_review entry emitted when ENABLE_PARALLEL=true (D-J3 diagnostic)
  - 16 unit tests covering both real .item fixtures and synthesized ENABLE_PARALLEL=true mutation
affects:
  - 10-06
  - 10-07
  - 10-08
  - future parallel-execution phases (Phase 12+)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "TalendConnection.params: generic side-channel for connection-level XML attributes -- avoids new dedicated fields for each future connection property"
    - "_parse_flows returns (flows, needs_review_entries) tuple -- single return path for both data and diagnostics"
    - "engine_gap entry shape: {severity, component_id, message} -- consistent with existing needs_review entries from component converters"
    - "Mutation-based test pattern: read real .item fixture, str.replace(), write to tmp_path, convert -- avoids fragile in-memory XML construction"

key-files:
  created:
    - tests/converters/talend_to_v1/test_iterate_connection_extraction.py
  modified:
    - src/converters/talend_to_v1/components/base.py
    - src/converters/talend_to_v1/xml_parser.py
    - src/converters/talend_to_v1/converter.py
    - tests/converters/talend_to_v1/test_converter.py

key-decisions:
  - "TalendConnection.params stores all elementParameter values except UNIQUE_NAME and CONDITION as Dict[str, str] with _strip_quotes applied -- consistent with existing value handling"
  - "_parse_flows returns tuple (flows, needs_review_entries) rather than flows list -- required to surface engine_gap entries without class-level mutable state"
  - "engine_gap message text: 'Parallel iteration is configured (NUMBER_PARALLEL=N) but Phase 10 engine runs sequentially -- results correct but slower. Defer to Phase 12+ for parallel.' -- matches D-J3 intent"
  - "Use _needs_review key in convert_file result (consistent with existing convention) -- task 3 tests use result.get('_needs_review', [])"
  - "NUMBER_PARALLEL stored as int with try/except fallback to 0 -- defensive against non-numeric XML values (T-10-02 mitigation)"

patterns-established:
  - "Connection params side-channel: TalendConnection.params provides a generic dict for future connection-level XML attributes without requiring new dataclass fields each time"

requirements-completed: []

# Metrics
duration: 15min
completed: 2026-05-05
---

# Phase 10 Plan 05: ITERATE Connection Parallel Extraction Summary

**TalendConnection.params side-channel + _parse_flows ENABLE_PARALLEL/NUMBER_PARALLEL extraction with engine_gap needs_review entry for parallel iterate configurations**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-05-05T18:14:00Z
- **Completed:** 2026-05-05T18:29:22Z
- **Tasks:** 3
- **Files modified:** 4 (+ 1 created)

## Accomplishments
- Added generic `params: Dict[str, str]` field to `TalendConnection` dataclass capturing all elementParameter values beyond UNIQUE_NAME and CONDITION
- Updated `_parse_connections` in XmlParser to populate params dict from connection-level elementParameters
- Extended `_parse_flows` to extract `ENABLE_PARALLEL` (bool) and `NUMBER_PARALLEL` (int) from ITERATE-typed connection params and write them into flow dicts
- Implemented D-J3 engine_gap diagnostic: when ENABLE_PARALLEL=true, emits a needs_review entry warning that Phase 10 runs sequentially
- Created 16 unit tests: both real .item fixtures (Job_tFileList_0.1.item and Job_tFlowToIterate_0.1.item), mutation-based ENABLE_PARALLEL=true branch, non-iterate regression, and shape compatibility tests

## Task Commits

Each task was committed atomically:

1. **Task 1: Add params field to TalendConnection and populate in _parse_connections** - `e29b610` (feat)
2. **Task 2: Extend _parse_flows to extract ENABLE_PARALLEL/NUMBER_PARALLEL; emit engine_gap** - `08986e8` (feat)
3. **Task 3: Unit tests for extraction and needs_review entry** - `3993f5b` (test)

**Plan metadata:** committed with this SUMMARY.

## Files Created/Modified
- `src/converters/talend_to_v1/components/base.py` - Added `params: Dict[str, str] = field(default_factory=dict)` to TalendConnection
- `src/converters/talend_to_v1/xml_parser.py` - _parse_connections now populates conn.params with all non-UNIQUE_NAME/CONDITION elementParameter values
- `src/converters/talend_to_v1/converter.py` - _parse_flows returns tuple; ITERATE flows get enable_parallel/number_parallel; ENABLE_PARALLEL=true emits engine_gap entry
- `tests/converters/talend_to_v1/test_converter.py` - Updated TestFlowParsing tests to unpack (flows, needs_review) tuple
- `tests/converters/talend_to_v1/test_iterate_connection_extraction.py` - 16 new tests (created)

## Decisions Made
- `_parse_flows` signature changed from returning `List[Dict]` to returning `(List[Dict], List[Dict])` tuple. Existing `TestFlowParsing` tests in test_converter.py were calling `_parse_flows` directly with the old list return -- updated those tests as part of Task 2 (Rule 1 auto-fix: broken tests caused by signature change).
- Used `_needs_review` key (with underscore prefix) in the convert_file result, consistent with existing convention in converter.py. Task 3 tests use `result.get("_needs_review", [])` accordingly.
- `ENABLE_PARALLEL` stored as Python `bool` (not raw string) using `str(...).strip().lower() == "true"` comparison -- safe for both "true"/"false" string values from XML.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated TestFlowParsing tests to handle new tuple return**
- **Found during:** Task 2 (_parse_flows signature change)
- **Issue:** Four existing tests in test_converter.py called `TalendToV1Converter._parse_flows()` and used the result as a list. After changing return to `(flows, needs_review_entries)` tuple, `len(flows)` became 2 (the tuple length), breaking assertions.
- **Fix:** Updated all four TestFlowParsing test methods to unpack `flows, needs_review = TalendToV1Converter._parse_flows(connections)` and added `assert needs_review == []` for completeness.
- **Files modified:** tests/converters/talend_to_v1/test_converter.py
- **Verification:** `pytest tests/converters/talend_to_v1/test_converter.py` exits 0, 41 passed
- **Committed in:** `08986e8` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 broken test from signature change)
**Impact on plan:** Necessary correctness fix. No scope creep.

## Issues Encountered
- The acceptance criteria smoke test uses `p.parse_file(...)` but XmlParser has `p.parse(...)`. Used `parse()` in implementation and tests. The smoke test in the plan is illustrative and uses `parse_file` as a hypothetical -- actual implementation uses `parse`.

## Known Stubs
None -- all extraction is fully wired from XML to flow dict to needs_review.

## Threat Flags
None -- no new network endpoints, auth paths, or trust boundary changes. Converter reads from Talend project files (trusted source) and elementParameter values are stored as strings with no eval/exec.

## Self-Check

Verified after writing SUMMARY:

## Self-Check: PASSED

Files confirmed present:
- src/converters/talend_to_v1/components/base.py: FOUND (contains params: Dict[str, str])
- src/converters/talend_to_v1/xml_parser.py: FOUND (contains params[ep_name])
- src/converters/talend_to_v1/converter.py: FOUND (contains ENABLE_PARALLEL, engine_gap)
- tests/converters/talend_to_v1/test_iterate_connection_extraction.py: FOUND (16 tests)

Commits confirmed:
- e29b610: Task 1 -- TalendConnection.params + _parse_connections
- 08986e8: Task 2 -- _parse_flows extraction + engine_gap
- 3993f5b: Task 3 -- 16 unit tests

All 16 tests pass. No regressions in existing converter/xml_parser/base test suite (104 tests pass).

## Next Phase Readiness
- TalendConnection.params side-channel is available for any future connection-level attribute extraction (no new dataclass fields needed)
- ENABLE_PARALLEL/NUMBER_PARALLEL now visible in flow dicts -- Phase 12+ parallel execution can read these without re-parsing
- engine_gap entries surface silently-parallel jobs in audit reports before Phase 12 parallel support lands

---
*Phase: 10-iterate-support*
*Completed: 2026-05-05*
