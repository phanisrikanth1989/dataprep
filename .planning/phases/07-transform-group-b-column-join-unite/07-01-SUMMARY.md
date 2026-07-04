---
phase: 07-transform-group-b-column-join-unite
plan: 01
subsystem: engine/transform
tags: [tJoin, join, rewrite, reject-schema]
dependency_graph:
  requires: []
  provides: [join-component, reject-schema-init]
  affects: [engine-component-init]
tech_stack:
  added: []
  patterns: [sentinel-null-handling, single-pass-merge-indicator]
key_files:
  created: []
  modified:
    - src/v1/engine/components/transform/join.py
    - src/v1/engine/engine.py
decisions:
  - Sentinel-based null key handling chosen over NaN-propagation for SQL/Talend semantics compliance
  - Case-sensitive join is default (matching Talend tJoin); case_sensitive=False available as future-proof config
  - Single-pass merge with indicator replaces double-merge pattern for reject computation
metrics:
  duration_seconds: 333
  completed: "2026-04-15T11:05:39Z"
  tasks_completed: 1
  tasks_total: 1
---

# Phase 07 Plan 01: tJoin Engine Component Rewrite Summary

Full rewrite of tJoin engine component fixing 8 bugs (P0 case-insensitive join corruption, wrong null semantics, double merge for reject, UPPERCASE config key mismatches, missing INCLUDE_LOOKUP toggle, missing ERROR_MESSAGE globalMap, missing reject schema) plus reject_schema initialization in engine.py.

## Completed Tasks

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add reject_schema to engine.py + rewrite join.py | c17380d | src/v1/engine/engine.py, src/v1/engine/components/transform/join.py |

## Key Changes

### engine.py (Part A)
- Added `component.reject_schema = comp_config.get('schema', {}).get('reject', [])` to `_initialize_components()`, following the same pattern as `input_schema` and `output_schema`

### join.py (Part B - Full Rewrite)
- **Registration**: `@REGISTRY.register("Join", "tJoin")` decorator for auto-registration
- **Config keys**: Reads lowercase converter keys directly (`use_inner_join`, `join_key`, `use_lookup_cols`, `lookup_cols`) -- no UPPERCASE keys
- **Null handling**: `_NULL_SENTINEL` constant prevents null keys from matching (SQL/Talend semantics)
- **Single-pass merge**: Uses `pd.merge()` with `indicator=True` for both main and reject computation (eliminated double merge)
- **INCLUDE_LOOKUP toggle**: `use_lookup_cols` + `lookup_cols` config controls whether lookup columns appear in output
- **ERROR_MESSAGE**: Sets `{id}_ERROR_MESSAGE` in globalMap on errors and when rejects exist
- **Reject schema**: Populates `errorCode='JOIN_REJECT'` and `errorMessage='No matching lookup row'` columns per `reject_schema`
- **Error handling**: `die_on_error` controls fatal vs graceful degradation; `ConfigurationError`/`DataValidationError` pass through
- **No execute() override**: Follows BaseComponent template method pattern (Rule 4)
- **No print()**: Logger only (Rule 8)
- **No state on self**: All processing state local to `_process()` (Rule 10)

## Bugs Fixed

1. **P0 Case-insensitive join corruption**: Old code lowercased original data columns in-place; new code works on copies only and case_sensitive defaults to True (Talend default)
2. **Wrong null semantics**: Old code let null keys match; new code uses sentinel-based filtering
3. **Double merge for reject**: Old code ran two separate `pd.merge()` calls; new code uses single merge with indicator
4. **UPPERCASE config key mismatch**: Old code read `USE_INNER_JOIN`, `JOIN_KEY`, `CASE_SENSITIVE`, `DIE_ON_ERROR`, `OUTPUT_COLUMNS`; new code reads lowercase converter keys
5. **Missing INCLUDE_LOOKUP toggle**: Old code had no `use_lookup_cols` support; new code implements full toggle
6. **Missing ERROR_MESSAGE globalMap**: Old code never set `{id}_ERROR_MESSAGE`; new code sets it on errors and rejects
7. **Missing reject schema**: Old code relied on `self.schema` dict (never set by engine); new code uses `self.reject_schema` (now set by engine)
8. **_validate_config wrong signature**: Old code returned `List[str]`; new code raises `ConfigurationError` per BaseComponent ABC contract

## Deviations from Plan

None - plan executed exactly as written.

## Decisions Made

1. **Sentinel value for null keys**: Used `_NULL_SENTINEL = "__DATAPREP_NULL_SENTINEL__"` string constant, replaced before merge and restored after -- straightforward and debuggable
2. **Case-sensitive default**: Default `case_sensitive=True` matches Talend tJoin behavior; config key available for future use but converter does not output it (phantom param removed)
3. **Graceful degradation**: On non-fatal errors, returns empty main + full main as reject (matching old behavior that was correct)

## Verification Results

- Registration: `REGISTRY.get('Join')` and `REGISTRY.get('tJoin')` both return `Join` class
- engine.py: `reject_schema` initialization line present
- Smoke test: Left outer join with 3 main rows returns 3 output rows
- Null key test: Inner join with null keys returns only non-null matches (1 row)
- Inner join test: 3 main + 2 lookup = 2 matched + 1 rejected
- Reject schema test: errorCode/errorMessage columns populated correctly
- INCLUDE_LOOKUP test: Lookup columns appear in output when toggled
- ERROR_MESSAGE test: GlobalMap variable set on rejects

## Self-Check: PASSED

```
FOUND: src/v1/engine/components/transform/join.py
FOUND: src/v1/engine/engine.py
FOUND: c17380d
```
