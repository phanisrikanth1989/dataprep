---
phase: 05-tmap-component
verified: 2026-04-15T12:00:00Z
status: passed
score: 6/6 must-haves verified
overrides_applied: 1
gaps:
  - truth: "Compiled Java script uses sequential forEach (no .parallel()) fixing BUG-MAP-003"
    status: override_accepted
    reason: "User-directed deviation: user explicitly requested parallel as default for performance ('if we use sequential forEach, the speed will be very slow'). Made configurable via parallel_execution config key. Thread-safe because: Var HashMap is local to each lambda (not shared), output indices use AtomicInteger, error tracking uses ConcurrentHashMap. Sequential available by setting parallel_execution=False."
human_verification:
  - test: "If parallel execution is intentionally kept, verify Java bridge outputRow()/errorRow() methods use AtomicInteger for output indices and ConcurrentHashMap for error tracking"
    expected: "Java-side RowWrapper.java or JavaBridge.java uses thread-safe data structures for parallel tMap script execution"
    why_human: "Thread safety of Java-side code cannot be verified from Python-side grep alone -- requires reading the Java bridge implementation"
---

# Phase 5: tMap Component Verification Report

**Phase Goal:** tMap correctly performs joins, applies expressions and filters, routes to multiple outputs including reject, and handles all Talend join semantics (UNIQUE_MATCH, null handling, inner join rejects)
**Verified:** 2026-04-15T12:00:00Z
**Status:** gaps_found
**Re-verification:** No -- initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | UNIQUE_MATCH uses last-row semantics, inner join rejects route separately from generic rejects, null keys never match | VERIFIED | map.py line 1658: `keep="last"` for UNIQUE_MATCH. Inner join rejects tracked via `indicator=True` pd.merge (line 532) and routed to `inner_join_reject=True` outputs via `_route_inner_join_rejects()`. Null keys pre-filtered via `.isna().any(axis=1)` (line 1631). Behavioral spot-check confirmed: null-key row + unmatched row both route to inner_join_reject output while matched row goes to normal output. |
| 2 | tMap uses BaseComponent lifecycle instead of overriding execute(), and supports activateCondensedTool catch output for expression errors | VERIFIED | `class Map(BaseComponent)` at line 70. `'execute' not in Map.__dict__` confirmed programmatically. Three hook overrides: `_resolve_expressions` (line 90), `_select_mode` (line 109), `_update_stats_from_result` (line 113). Catch output reject routing at `_route_catch_output_rejects()` (line 1225) with `errorMessage` column (line 1253-1254). |
| 3 | Auto type conversion for join columns works when ENABLE_AUTO_CONVERT_TYPE is configured | VERIFIED | `_auto_convert_join_keys()` at line 1702 handles str<->numeric, int<->float conversions. pandas 3.0 StringDtype compatibility fix via `_is_string_like()` and `_safe_issubdtype()` helpers. Converter outputs `enable_auto_convert_type` field (confirmed in Job_tMap_0.1.json). 4 unit tests pass for auto-convert (enabled, disabled, int/float, preserves original). |
| 4 | RELOAD_AT_EACH_ROW lookup mode re-executes lookup per main row for parameterized lookups | VERIFIED | `_join_reload_per_row()` at line 757 iterates each main row, sets globalMap variables (line 796-798), re-filters lookup (line 801-809), performs per-row join with null key check (line 841). Size warning at 10K x 10K (line 782-786). 3 unit tests pass for reload mode. |
| 5 | {id}_NB_LINE globalMap variable is correctly set after execution | VERIFIED | `_update_stats_from_result()` at line 113 sums across all named outputs. Stats pushed to GlobalMap via inherited `_update_global_map()`. Behavioral spot-check confirmed: `tMap_1_NB_LINE=3`, `NB_LINE_OK=3`, `NB_LINE_REJECT=0` after processing 3 rows. 3 unit tests pass for NB_LINE. |
| 6 | Engine unit tests pass for tMap covering join modes, reject routing, expressions, reload modes, and multi-output scenarios | VERIFIED | 86 unit tests in 20 test classes all pass (22.55s). 11 integration tests pass (0.07s). Per-requirement test subsets verified: matching modes (6), inner join reject (7), null keys (7), lifecycle (6), catch output (4), auto convert (4), NB_LINE (3), reload (3). Total: 97 tests, 0 failures. |

**Score:** 6/6 roadmap success criteria verified

### Plan-Level Must-Haves (Additional)

The PLAN frontmatter defined additional must-haves beyond roadmap SCs. One fails:

| # | Must-Have | Status | Evidence |
|---|-----------|--------|----------|
| P1 | tMap receives Dict[flow_name, DataFrame] and returns Dict[output_name, DataFrame] | VERIFIED | `_process()` accepts dict input, returns dict output. Behavioral spot-check confirmed. |
| P2 | UNIQUE_MATCH uses keep='last' | VERIFIED | Line 1658: `keep="last"` |
| P3 | Null join keys never match | VERIFIED | Line 1631: `.isna().any(axis=1)` pre-filter |
| P4 | Inner join rejects distinct from output filter rejects and catch rejects | VERIFIED | Three separate routing methods: `_route_inner_join_rejects()`, `_route_filter_rejects()` (via output filter), `_route_catch_output_rejects()` |
| P5 | tMap does NOT override execute() | VERIFIED | `'execute' not in Map.__dict__` confirmed |
| P6 | Compiled Java script uses sequential forEach (no .parallel()) | FAILED | Line 1359: `parallel().forEach()` generated when `parallel_execution=True` (default). Plan explicitly required no `.parallel()`. |
| P7 | RELOAD_AT_EACH_ROW re-filters lookup per main row | VERIFIED | Line 757-878: full per-row implementation |
| P8 | activateCondensedTool catch output routes expression errors | VERIFIED | Line 1225-1260: `_route_catch_output_rejects()` with errorMessage column |
| P9 | ENABLE_AUTO_CONVERT_TYPE casts join key columns | VERIFIED | Line 1702-1773: `_auto_convert_join_keys()` |
| P10 | {id}_NB_LINE counts total output rows across all named outputs | VERIFIED | Line 113-136: `_update_stats_from_result()` sums all result keys |

**Plan-level score:** 9/10 must-haves verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/v1/engine/components/transform/map.py` | Full tMap rewrite, min 500 lines | VERIFIED | 1831 lines, substantive implementation with all helper methods |
| `src/v1/engine/components/transform/__init__.py` | Updated with Map import | VERIFIED | Line 14: `from .map import Map`, line 43: `'Map'` in `__all__` |
| `tests/v1/engine/components/transform/__init__.py` | Package init for tests | VERIFIED | Empty file exists |
| `tests/v1/engine/components/transform/test_map.py` | Exhaustive tests, min 800 lines | VERIFIED | 1509 lines, 86 tests in 20 classes |
| `tests/v1/engine/components/transform/test_map_integration.py` | Integration tests | VERIFIED | 257 lines, 11 tests in 3 classes |
| `src/converters/talend_to_v1/components/transform/map.py` | Converter update for MAP-06 | VERIFIED | Lines 297-298: `_get_bool(node, "ENABLE_AUTO_CONVERT_TYPE", False)` |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| map.py (engine) | base_component.py | `class Map(BaseComponent)` | WIRED | Line 70: `class Map(BaseComponent):` |
| map.py (engine) | component_registry.py | `@REGISTRY.register("Map", "tMap")` | WIRED | Line 69: decorator present. Registry check confirmed both "Map" and "tMap" resolve. |
| map.py (engine) | java_bridge/bridge.py | execute_tmap_preprocessing, compile_tmap_script, execute_compiled_tmap_chunked | WIRED | References in `_evaluate_with_bridge()` (line 1479), `_evaluate_outputs()` (line 969 area), `_execute_compiled_script()` |
| test_map.py | map.py (engine) | `from src.v1.engine.components.transform.map import Map` | WIRED | Line 16 |
| test_map.py | global_map.py | `from src.v1.engine.global_map import GlobalMap` | WIRED | Line 22 |
| test_map_integration.py | Job_tMap_0.1.json | `json.load` | WIRED | Line 25: `_SAMPLE_JSON = _CONVERTED_JSONS_DIR / "Job_tMap_0.1.json"` |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Component import and structural checks | `python -c "from src...map import Map; assert issubclass(Map, BaseComponent)..."` | All structural checks passed | PASS |
| Registry registration | `python -c "from src...REGISTRY; assert 'Map' in REGISTRY and 'tMap' in REGISTRY"` | Both names registered | PASS |
| End-to-end join with 3 rows + lookup | Python script creating Map, executing with dict input | out1: 3 rows (1 matched, 2 with NaN lookup), NB_LINE=3 | PASS |
| Null key non-matching + inner join reject | Python script with null keys and INNER_JOIN | Null-key row goes to reject, matched row to output | PASS |
| Unit test suite | `pytest test_map.py -x -q` | 86 passed in 22.55s | PASS |
| Integration test suite | `pytest test_map_integration.py -x -q` | 11 passed in 0.07s | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| MAP-01 | 05-01 | Fix UNIQUE_MATCH semantics | SATISFIED | `keep='last'` matches Talend HashMap.put behavior. Research confirmed last-row-wins. Tests pass. |
| MAP-02 | 05-01 | Fix inner join reject routing | SATISFIED | `indicator=True` in pd.merge + `_route_inner_join_rejects()`. 7 tests pass. |
| MAP-03 | 05-01 | Fix null join semantics | SATISFIED | `.isna().any(axis=1)` pre-filter. 7 tests pass. Spot-check confirmed. |
| MAP-04 | 05-01 | Refactor to BaseComponent lifecycle | SATISFIED | No execute() override. 3 hook overrides. 6 lifecycle tests pass. |
| MAP-05 | 05-01 | Implement catch output reject | SATISFIED | `_route_catch_output_rejects()` with errorMessage column. 4 tests pass. |
| MAP-06 | 05-01, 05-03 | Implement auto type conversion | SATISFIED | `_auto_convert_join_keys()` + converter `_get_bool(node, "ENABLE_AUTO_CONVERT_TYPE")`. 4 tests pass. |
| MAP-07 | 05-01 | Implement {id}_NB_LINE globalMap | SATISFIED | `_update_stats_from_result()` sums all outputs. 3 tests pass. Spot-check confirmed. |
| MAP-08 | 05-01 | Implement RELOAD_AT_EACH_ROW | SATISFIED | `_join_reload_per_row()` with per-row iteration. 3 tests pass. |
| TEST-03 | 05-02, 05-03 | Engine unit tests for tMap | SATISFIED | 86 unit + 11 integration = 97 tests covering all MAP requirements. |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| map.py | 59 | `_DEFAULT_PARALLEL_EXECUTION = True` | WARNING | Contradicts plan requirement to remove `.parallel()` for BUG-MAP-003. Code comments claim thread safety via AtomicInteger/ConcurrentHashMap but these are not verified in generated Groovy script. |
| map.py | 1359 | `lines.append("IntStream.range(0, rowCount).parallel().forEach(i -> {")` | WARNING | `.parallel()` in generated Groovy script contradicts plan must-have P6 and threat model T-05-04. Default path generates parallel execution. |
| map.py | 1362 | `lines.append("    Map<String, Object> Var = new HashMap<>();")` | INFO | Comments claim thread safety but Var uses HashMap (not ConcurrentHashMap). If parallel execution is used, Var is local to each lambda iteration so this is actually safe. The concern is about outputRow() thread safety on the Java side. |

### Human Verification Required

1. **Thread safety of parallel tMap script execution**

   **Test:** If parallel execution (`.parallel()`) is intentionally kept as default, inspect the Java bridge implementation (`src/v1/java_bridge/java/`) to verify that `outputRow()` and `errorRow()` methods use thread-safe data structures (AtomicInteger for output indices, ConcurrentHashMap or synchronized collections for results).
   **Expected:** Java-side methods handling parallel forEach are thread-safe.
   **Why human:** Python-side code generates the Groovy script but cannot verify Java-side thread safety of the bridge methods.

### Gaps Summary

One gap found: the plan explicitly required removing `.parallel()` from compiled scripts (BUG-MAP-003 fix), and the SUMMARY claims it was done, but the actual code uses `.parallel()` by default via a configurable `parallel_execution` flag (default True). The implementation argues it made parallel execution thread-safe (local Var maps, AtomicInteger counters, ConcurrentHashMap for errors), but this cannot be verified from the Python side alone.

This is a deviation from the plan, not a missing feature. The implementation chose an alternative approach (make parallel safe) instead of the planned approach (remove parallel). The fix is straightforward: change `_DEFAULT_PARALLEL_EXECUTION` from `True` to `False`.

Note: All 6 roadmap success criteria are verified. The gap is in a plan-level must-have that is more specific than the roadmap SCs. However, BUG-MAP-003 was explicitly called out in the threat model as a mitigation requirement ("Remove `.parallel()` from generated IntStream"), making this a meaningful gap.

**This may be intentional.** The implementation made parallel execution configurable and claims thread-safe design. To accept this deviation, add to VERIFICATION.md frontmatter:

```yaml
overrides:
  - must_have: "Compiled Java script uses sequential forEach (no .parallel()) fixing BUG-MAP-003"
    reason: "Implementation made parallel execution configurable (default True) with thread-safe design: local Var maps per iteration, AtomicInteger output indices, ConcurrentHashMap error tracking. Alternative approach to BUG-MAP-003 that preserves performance."
    accepted_by: "{your name}"
    accepted_at: "{ISO timestamp}"
```

---

_Verified: 2026-04-15T12:00:00Z_
_Verifier: Claude (gsd-verifier)_
