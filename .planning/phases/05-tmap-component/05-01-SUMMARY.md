---
phase: 05-tmap-component
plan: 01
subsystem: engine
tags: [tmap, joins, pandas-merge, java-bridge, registry, base-component]

# Dependency graph
requires:
  - phase: 01-infrastructure-bug-fixes-project-setup
    provides: BaseComponent lifecycle with config immutability, validate/resolve/process hooks
  - phase: 02-java-bridge-reliability
    provides: Java bridge tMap APIs (preprocessing, compile, execute_chunked)
  - phase: 03-execution-loop-restructure
    provides: ComponentRegistry decorator pattern, OutputRouter multi-input/output routing
provides:
  - "Complete tMap engine component rewrite with full Talend feature parity"
  - "Smart join routing (equality/context_only/cross_table)"
  - "8 MAP requirements implemented (MAP-01 through MAP-08)"
  - "Thread-safe compiled script generation (sequential forEach)"
affects: [06-transform-components, 05-tmap-component-tests]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "BaseComponent lifecycle hook overrides for multi-flow components"
    - "Smart join routing classification (equality/context_only/cross_table)"
    - "Null key pre-filter before pandas merge for SQL/Talend semantics"
    - "Inner join reject tracking via pandas merge indicator"
    - "Sequential compiled script execution (no parallel forEach)"

key-files:
  created: []
  modified:
    - src/v1/engine/components/transform/map.py

key-decisions:
  - "UNIQUE_MATCH uses keep='last' (Talend HashMap.put overwrites, last row wins) -- research confirmed current code was correct"
  - "Three lifecycle hook overrides (_resolve_expressions, _select_mode, _update_stats_from_result) instead of execute() override"
  - "Size guard thresholds: warn at 10M result rows, fail at 100M for cartesian/cross-table joins"
  - "RELOAD_AT_EACH_ROW re-filters lookup per main row using current globalMap values"

patterns-established:
  - "Lifecycle hook override pattern: override _resolve_expressions to skip Java marker resolution for row-data expressions"
  - "Multi-output stats counting: override _update_stats_from_result to iterate all named outputs"
  - "Smart join routing: classify join keys at processing time, route to optimal join strategy"

requirements-completed: [MAP-01, MAP-02, MAP-03, MAP-04, MAP-05, MAP-06, MAP-07, MAP-08]

# Metrics
duration: 7min
completed: 2026-04-15
---

# Phase 5 Plan 1: tMap Engine Component Rewrite Summary

**Complete tMap engine component rewrite (1796 lines) with full Talend feature parity for joins, expressions, reject routing, matching modes, and BaseComponent lifecycle integration**

## Performance

- **Duration:** 7 min
- **Started:** 2026-04-14T22:29:39Z
- **Completed:** 2026-04-14T22:36:09Z
- **Tasks:** 2
- **Files modified:** 1

## Accomplishments
- Rewrote map.py from scratch conforming to ENGINE_COMPONENT_PATTERN.md with all 8 MAP requirements
- Integrated with BaseComponent lifecycle via 3 targeted hook overrides (no execute() override)
- Implemented smart join routing: equality joins via pandas merge, context-only via expression eval + cross-join, cross-table via Java bridge preprocessing
- Fixed BUG-MAP-003 thread safety by using sequential forEach in compiled scripts (no .parallel())
- Implemented null key pre-filter (MAP-03), inner join reject tracking (MAP-02), catch output reject routing (MAP-05), auto type conversion (MAP-06), RELOAD_AT_EACH_ROW per-row lookup (MAP-08)

## Task Commits

Each task was committed atomically:

1. **Task 1: Rewrite map.py from scratch with full Talend tMap feature parity** - `9ab8120` (feat)
2. **Task 2: Update transform __init__.py for registry-based Map import** - No changes needed; verified existing import and registry decoration work correctly with rewritten Map class

## Files Created/Modified
- `src/v1/engine/components/transform/map.py` - Complete rewrite of tMap engine component (1796 lines)

## Decisions Made
- UNIQUE_MATCH uses `keep='last'` -- research confirmed Talend's AdvancedMemoryLookup uses HashMap.put which overwrites (last row wins). The existing code was already correct despite CONTEXT.md D-11 stating otherwise.
- Override `_resolve_expressions()` to only resolve context variables on scalar config fields (die_on_error, rows_buffer_size, label, enable_auto_convert_type). Skip Java expression resolution because tMap expressions reference row data that does not exist at config resolution time.
- Override `_select_mode()` to always return BATCH. tMap handles its own chunking internally via the Java bridge compile-once-execute-many pattern.
- Override `_update_stats_from_result()` to sum rows across all named output DataFrames, distinguishing reject outputs from normal outputs.
- Size guard for cartesian/cross-table joins: warn at 10M result rows, fail at 100M. Prevents silent OOM.
- RELOAD_AT_EACH_ROW implemented as per-row lookup re-filter (re-evaluate lookup filter with current globalMap values), since Python engine lookups come from DataFrames not re-queryable databases.

## Deviations from Plan

None - plan executed exactly as written. Task 2 required no code changes as the existing __init__.py already correctly imported the Map class and had it in __all__.

## Issues Encountered

None

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Map component is ready for unit testing (Plan 05-02 or 05-03)
- Java bridge integration testing needs compiled JAR and running JVM
- All 8 MAP requirements are implemented, pending test verification

## Self-Check: PASSED

- FOUND: src/v1/engine/components/transform/map.py
- FOUND: .planning/phases/05-tmap-component/05-01-SUMMARY.md
- FOUND: commit 9ab8120

---
*Phase: 05-tmap-component*
*Completed: 2026-04-15*
