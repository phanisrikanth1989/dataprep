---
status: awaiting_human_verify
trigger: "tMap compiled script mismatch - _build_compiled_script() generates wrong format for Java bridge"
created: 2026-04-15T00:00:00Z
updated: 2026-04-15T00:00:00Z
---

## Current Focus

hypothesis: CONFIRMED - Two bugs fixed in map.py (RowWrapper constructor + output_types format)
test: 100/100 tests pass
expecting: User verifies end-to-end with Java bridge running
next_action: Awaiting human verification

## Symptoms

expected: tMap processes complex Java expressions like `row1.first_name + " " + row1.last_name` and `row1.salary >= 75000 ? "Senior" : "Junior"` via the compiled Groovy script path, producing correct output DataFrames.
actual: The engine hangs at `execute_compiled_tmap_chunked` and never returns when processing a real Talend .item job (Job_tMap_0.1) with complex expressions. Simple column references (`row1.order_id`) work because they use the pandas equality join path, never touching the compiled script.
errors: No exception -- the Java bridge call hangs indefinitely. The Groovy script compiles (no compilation error) but execution never completes. The generated script uses `outputRow()` helper and a simplified format that doesn't match the bridge's expected format (pre-allocated Object[][] arrays, AtomicInteger counters, RowWrapper construction, Map return value).
reproduction: 1) Convert tests/talend_xml_samples/Job_tMap_0.1.item to JSON. 2) Create sample employees.csv + country_lookup.csv with matching schema. 3) Run through ETLEngine with java_config.enabled=True. 4) Engine hangs at tMap compiled script execution.
started: Phase 5 tMap rewrite generated new script format that doesn't match Phase 2 Java bridge contract.

## Eliminated

## Evidence

- timestamp: 2026-04-15T00:10:00Z
  checked: RowWrapper.java constructor signatures
  found: Only has no-arg constructor RowWrapper(). No 3-arg constructor (VectorSchemaRoot, int, String).
  implication: Generated script calls new RowWrapper(inputRoot, i, "row1") which does not exist -- runtime Groovy error.

- timestamp: 2026-04-15T00:12:00Z
  checked: JavaBridge.java buildTMapBinding() and convertTMapOutputsToArrow()
  found: buildTMapBinding injects inputRoot, rowCount, mainTableName, lookupNames into binding. convertTMapOutputsToArrow expects output_types keyed as "outputName_colName" -> python type string (e.g. "str", "int").
  implication: _build_output_schema() creates output_types["out"] = "normal" instead of output_types["out_full_name"] = "str" -- wrong format.

- timestamp: 2026-04-15T00:14:00Z
  checked: JavaBridge.java buildArrowRowWrapper() private method
  found: Builds RowWrapper by iterating inputRoot.getFieldVectors(), extracting values per row, storing under both prefixed and unprefixed names. This logic must be replicated inline in the generated script since buildArrowRowWrapper is private.
  implication: Script must manually build RowWrappers from Arrow field vectors.

- timestamp: 2026-04-15T00:16:00Z
  checked: _prefix_lookup_columns() in map.py
  found: Already uses str(col) on line 1773-1774. The fix for integer column names appears complete.
  implication: No additional fix needed for _prefix_lookup_columns.

## Resolution

root_cause: Three bugs in map.py: (1) _build_compiled_script() generates `new RowWrapper(inputRoot, i, "tableName")` but RowWrapper only has a no-arg constructor -- must build RowWrapper manually from Arrow field vectors. (2) _build_output_schema() creates output_types as {"outputName": "normal"} but Java bridge's convertTMapOutputsToArrow() expects {"outputName_colName": "pythonTypeStr"} -- wrong key format and wrong values. (3) The generated script needs to extract field vectors outside the loop for performance.
fix: Rewrite _build_compiled_script() to build RowWrappers inline from Arrow vectors (matching buildArrowRowWrapper logic). Rewrite _build_output_schema() to produce per-column type entries keyed as "outputName_colName" -> python type string.
verification: 100/100 tests pass (89 unit + 11 integration). 3 new regression tests added for RowWrapper construction, Arrow vector reading, and output_types format. 1 existing test updated (errorRow -> errorCount/errorMap assertion).
files_changed: [src/v1/engine/components/transform/map.py, tests/v1/engine/components/transform/test_map.py]
