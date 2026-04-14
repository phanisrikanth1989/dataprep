# Phase 5: tMap Component - Research

**Researched:** 2026-04-15
**Domain:** Engine component rewrite -- multi-flow data mapping with joins, expressions, and reject routing
**Confidence:** HIGH

## Summary

tMap is the most complex component in the engine (1164 lines). This research investigated Talend's actual tMap behavior via the Talaxie GitHub javajet code generation templates, the AdvancedMemoryLookup Java source, official Talend documentation, the existing engine code, the converter output format, and the Phase 2/3 infrastructure APIs. The most critical finding is that **UNIQUE_MATCH uses LAST-row semantics (HashMap.put overwrites), not first-row** -- contradicting CONTEXT.md D-11. The existing engine code's `keep='last'` is actually correct Talend behavior. This must be surfaced to the user before planning proceeds.

The rewrite is architecturally straightforward: preserve the hybrid approach (pandas for bulk joins, Java bridge for expressions), integrate with BaseComponent lifecycle via targeted hook overrides (_resolve_expressions, _update_stats_from_result, _select_mode), and implement the 8 MAP requirements. The Phase 2 bridge provides the exact APIs needed (execute_tmap_preprocessing, compile_tmap_script, execute_compiled_tmap_chunked). The Phase 3 OutputRouter already returns Dict[flow_name, DataFrame] for multi-input components and routes named outputs to downstream flows.

**Primary recommendation:** Rewrite map.py from scratch conforming to ENGINE_COMPONENT_PATTERN.md, using BaseComponent lifecycle hooks (not execute() override), with pandas merge for equality joins, Java bridge preprocessing for complex join keys, and compiled script execution for output column evaluation. Fix the thread safety bug by removing parallel() from IntStream in the generated script.

<user_constraints>

## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Full rewrite from scratch. Not patching the existing 1164-line map.py. Conform to ENGINE_COMPONENT_PATTERN.md blueprint.
- **D-02:** Add `@REGISTRY.register('Map', 'tMap')` decorator per Phase 3 D-04.
- **D-03:** Preserve the hybrid architecture: pandas for bulk joins, Java bridge for expression evaluation.
- **D-04:** Preserve compile-once-execute-many Java bridge pattern for output evaluation.
- **D-05:** tMap does NOT override execute(). Uses BaseComponent lifecycle with targeted hook overrides.
- **D-06:** Override _resolve_expressions() -- resolve context on scalar fields only, skip Java expression resolution.
- **D-07:** Override _update_stats_from_result() -- sum across all named output DataFrames.
- **D-08:** Override _select_mode() -- always return BATCH.
- **D-09:** Implement _validate_config() and _process() as core processing method.
- **D-10:** Benefits of hook approach: config immutability for free, iterate support automatic, future lifecycle inherited.
- **D-11:** MAP-01 UNIQUE_MATCH uses first-row semantics (drop_duplicates(keep='first')). **[RESEARCH CONTRADICTS -- see Assumptions Log A1]**
- **D-12:** MAP-02 rejectInnerJoin outputs are distinct from generic reject outputs.
- **D-13:** MAP-03 Null keys never match (SQL/Talend semantics).
- **D-14:** All matching modes match Talend behavior exactly.
- **D-15:** Smart join routing: equality joins -> pandas merge, context-only -> evaluate+filter+cross, cross-table -> chunked nested-loop via Java bridge.
- **D-16:** Research must investigate how Talend handles cross-table expressions.
- **D-17:** Size guard for cross-table and cartesian joins.
- **D-18:** Preprocessing adds configurable threshold chunking.
- **D-19:** Post-processing preserves existing compile+chunk pattern.
- **D-20:** Chunk size configurable via config with default 50K.
- **D-21:** _process() receives Dict[flow_name, DataFrame] from OutputRouter.
- **D-22:** _process() returns Dict[output_name, DataFrame].
- **D-23:** Converter already populates inputs and outputs lists.
- **D-24:** MAP-05 catch output reject (activateCondensedTool) in scope.
- **D-25:** MAP-06 auto type conversion (ENABLE_AUTO_CONVERT_TYPE) in scope.
- **D-26:** MAP-07 {id}_NB_LINE globalMap variable in scope.
- **D-27:** MAP-08 RELOAD_AT_EACH_ROW lookup mode in scope.
- **D-28:** BUG-MAP-003 thread safety fix in scope.
- **D-29:** Deep research required on 10 topics before planning.
- **D-30 through D-33:** Test strategy follows Phase 4 pattern.

### Claude's Discretion
- Internal method decomposition and helper design
- Exact preprocessing chunk threshold value
- How to structure the smart join classifier
- Column prefixing strategy
- pandas merge indicator vs set-based difference for reject detection
- Compiled script generation details
- Test count target (estimated 60-100)

### Deferred Ideas (OUT OF SCOPE)
- MAP-V2-02: Disk-based lookup caching (STORE_ON_DISK, ROWS_BUFFER_SIZE)
- MAP-V2-03: Parallel lookup loading (LKUP_PARALLELIZE)
- MAP-V2-04: Fuzzy matching (Levenshtein/Jaccard)
- MAP-V2-05: BigDecimal hash/equals for join keys
- activateGlobalMap on input/output tables
- persistent lookup support
- ALL_ROWS keyless cross-join matching mode

</user_constraints>

<phase_requirements>

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| MAP-01 | Fix UNIQUE_MATCH semantics -- use first-row (Talend behavior) instead of keep='last' | **RESEARCH CONTRADICTS:** Talend AdvancedMemoryLookup uses HashMap.put (last wins). Official docs confirm UNIQUE_MATCH = last match. Current keep='last' is CORRECT. See Assumptions Log A1. |
| MAP-02 | Fix inner join reject routing -- differentiate rejectInnerJoin from generic reject | Talend uses `rejectedInnerJoin` boolean flag per row, set when inner join lookup returns no results. Distinct from output filter reject. See Architecture Patterns. |
| MAP-03 | Fix null join semantics -- pandas merge() matches NaN==NaN but Talend/SQL does not | Talend sets `hasCasePrimitiveKeyWithNull` flag and skips lookup entirely for null keys. Pre-filter approach confirmed correct. |
| MAP-04 | Refactor to use BaseComponent lifecycle instead of overriding execute() | BaseComponent provides _resolve_expressions, _update_stats_from_result, _select_mode as overridable hooks. See Architecture Patterns. |
| MAP-05 | Implement catch output reject (activateCondensedTool) | Talend wraps per-row evaluation in try-catch, routes error rows to outputs with activateCondensedTool=true. See javajet analysis. |
| MAP-06 | Implement auto type conversion for join columns (ENABLE_AUTO_CONVERT_TYPE) | Talend uses autoConverterMap with type-pair conversion functions. Converter currently strips this param -- small converter update needed. |
| MAP-07 | Implement {id}_NB_LINE globalMap variable | Handled via _update_global_map() from BaseComponent lifecycle. Override _update_stats_from_result to count across all outputs. |
| MAP-08 | Implement RELOAD_AT_EACH_ROW lookup mode | Talend re-executes lookup subprocess per main row, refreshing lookup HashMap from globalMap. See RELOAD analysis. |
| TEST-03 | Engine unit tests for tMap | Test infrastructure exists (conftest.py, GlobalMap, ContextManager). Follow ENGINE_TEST_PATTERN.md with tMap-specific test classes. |

</phase_requirements>

## Project Constraints (from CLAUDE.md)

- Python 3.10+ with `set[str]` syntax
- Must produce identical output to Talend for same input data and job configuration
- No breaking changes to converter JSON format
- Engine component must follow established pattern (ABC + registry + per-component)
- Java bridge uses Py4J + Arrow architecture
- ASCII-only logging (no emojis/unicode -- RHEL servers)
- Use `logging.getLogger(__name__)`, not print()
- Custom exception hierarchy from `src/v1/engine/exceptions.py`
- Google-style docstrings in engine modules
- snake_case for all functions/methods, PascalCase for classes
- No automated formatter, but 4-space indentation, generally under 120 chars

## Critical Research Findings (D-29 Topics)

### Topic 1: Cross-Table Join Patterns in Production .item Samples

**Finding:** The production sample `Job_tMap_0.1.item` uses simple equality joins only: `row1.country_code` joined to `lookup.country_code`. No cross-table expressions (e.g., `StringHandling.MATCH(row1.name, lookup1.pattern)`) were found in the available samples. [VERIFIED: codebase scan]

**Implication:** Cross-table joins are likely rare in the target 1200+ jobs. The smart join routing should prioritize equality joins (pandas merge path) for performance, with cross-table evaluation as a fallback. The cross-table path can be implemented but should log a warning when triggered.

### Topic 2: Chained Lookup Patterns (Lookup2 references Lookup1)

**Finding:** The existing engine code already handles chained lookups correctly -- lookups are processed sequentially, and each subsequent lookup can reference columns from previously joined lookups via the `joined_lookups` list passed to `_batch_evaluate_expressions`. The converter preserves lookup ordering (inputTables[1:] are parsed in document order). [VERIFIED: existing map.py lines 419-494, converter map.py lines 87-132]

**Implication:** The rewrite must preserve sequential lookup processing. Each lookup's join key expressions are evaluated against the current `joined_df` (which includes previous lookup columns). This is already sound architecture.

### Topic 3: Variable Dependency Chains and Evaluation Order

**Finding:** From javajet analysis: Variables are evaluated AFTER all lookups complete and BEFORE output expressions. Variable expressions CAN reference previously computed variables within the same Var scope (dependency chains are supported). The generated code creates a `Map<String, Object> Var` and evaluates entries sequentially, so `Var.put("var2", Var.get("var1") + 10)` works. [VERIFIED: tMap_main.inc.javajet WebFetch analysis]

**Implication:** The compiled script must evaluate variables in config order (which preserves XML document order from Talend). The current engine code already evaluates variables in order via the generated script. The rewrite must preserve this ordering.

### Topic 4: Thread Safety in Compiled Scripts (BUG-MAP-003)

**Finding:** The current compiled script uses `IntStream.range(0, rowCount).parallel().forEach()` with a shared `HashMap<String, Object> Var` for variable storage. This is NOT thread-safe -- HashMap is not concurrent-safe, and `Var.put()` from parallel threads can cause data corruption, lost updates, or ConcurrentModificationException. [VERIFIED: existing map.py lines 982-1008]

**Talend behavior:** Talend's generated code processes rows sequentially in a for-loop, NOT in parallel. The tMap_main.inc.javajet processes one main row at a time through a single-threaded iteration. There is no parallel execution. [VERIFIED: tMap_main.inc.javajet WebFetch analysis -- sequential row processing]

**Fix recommendation:** Remove `.parallel()` from the generated IntStream. Use sequential `.forEach()` instead. This matches Talend behavior and eliminates the race condition. The performance impact is negligible because the Java bridge already chunks at 50K rows, and sequential execution within a chunk is fast. If parallel execution is desired later, each parallel lane must have its own `Var` map instance (per-thread copies, not shared). [ASSUMED: performance impact assessment]

### Topic 5: Column Name Collision Handling in Talend

**Finding:** Talend generates unique struct classes for each input/output table (e.g., `row1Struct`, `lookup1Struct`). Each struct has its own field namespace -- there are no column name collisions because fields are always accessed via their table reference (e.g., `row1.id` vs `lookup1.id`). [VERIFIED: tMap_begin.inc.javajet and tMap_commons.skeleton WebFetch analysis]

**Current engine behavior:** The current code prefixes all lookup columns with `lookup_name.column` (e.g., `row2.country_code`). This prevents collisions but creates non-standard column names in the joined DataFrame. [VERIFIED: existing map.py lines 562-564, 691-693]

**Implication:** The prefixing approach is correct. The compiled script's RowWrapper already knows its table name and maps `row1.column` to the actual DataFrame column. The rewrite should continue prefixing lookup columns with `{lookup_name}.{column}` in the joined DataFrame.

### Topic 6: RELOAD_AT_EACH_ROW Exact Behavior

**Finding:** From javajet analysis: RELOAD_AT_EACH_ROW mode re-executes the lookup's upstream subprocess for EACH main row. The sequence is:
1. Before processing: lookup hash is null (not pre-loaded)
2. Per main row: populate globalMap with key-value expressions, invoke the lookup subprocess process, retrieve fresh lookup hash from globalMap
3. Lookup the current main row's key against this fresh hash
4. The subprocess typically executes a database query with parameterized conditions

CACHE_OR_RELOAD variant adds caching: if the same key values produce the same lookup, skip re-execution. [VERIFIED: tMap_main.inc.javajet WebFetch analysis, T_TM_M_354/T_TM_M_355]

**Implication for this engine:** The engine does not have a subprocess execution concept for lookups. RELOAD_AT_EACH_ROW in Talend assumes the lookup source is re-queryable (e.g., database). In the Python engine, lookups come from upstream DataFrame flows. The closest equivalent is: for each main row, re-filter the full lookup DataFrame using the current row's context/globalMap values (parameterized filter). This makes sense for lookups where the join expression references context variables that change per row (e.g., from a tFlowToIterate setting globalMap vars).

### Topic 7: Expression Error Routing (activateCondensedTool)

**Finding:** From javajet analysis: When `activateCondensedTool` (catch output reject) is true on an output table:
1. Per-row expression evaluation is wrapped in try-catch
2. On exception: the error row is NOT written to any normal output
3. Instead, the row data (from main/lookup columns that were available BEFORE the error) plus `errorMessage` and optional `errorStackTrace` fields are written to the catch output
4. Processing continues with the next row
5. This is distinct from inner join reject: catch output captures EXPRESSION errors, inner join reject captures UNMATCHED rows [VERIFIED: tMap_main.inc.javajet WebFetch analysis]

**Implication:** The compiled script already has partial error handling (die_on_error=false path routes to reject). The rewrite needs to distinguish:
- **Inner join reject output** (rejectInnerJoin=true): rows where inner join lookup found no match
- **Output filter reject** (reject=true, not rejectInnerJoin): rows that failed output expression filter
- **Catch output** (activateCondensedTool=true): rows where expression evaluation threw an exception

These are three different mechanisms that can coexist.

### Topic 8: Production .item Scan for tMap Usage Patterns

**Finding:** Scanning available test samples:
- `Job_tMap_0.1.item`: 1 main + 1 lookup, UNIQUE_MATCH, LOAD_ONCE, LEFT_OUTER_JOIN, simple equality join (row1.country_code), output filter (row1.salary > 60000), ternary expression in output column, multi-output (out, out2), activateCondensedTool=true on lookup
- Only 1 tMap sample available in the test corpus. [VERIFIED: codebase scan]

**Typical patterns from the sample:**
- Simple column reference join keys (`row1.country_code`)
- Java ternary expressions in output columns (`row1.salary >= 75000 ? "Senior" : "Junior"`)
- String concatenation in output columns (`row1.first_name + " " + row1.last_name`)
- Multi-output routing (some outputs filtered, others unfiltered)
- activateCondensedTool on lookup tables

### Topic 9: Memory/Performance Benchmarks for Join Strategies

**Finding:** The current engine uses pandas merge for joins (O(n+m) for hash join) and Java bridge compiled scripts with 50K row chunks for expression evaluation. [VERIFIED: existing map.py, bridge.py]

**Performance characteristics by join strategy:**
- **Equality join (pandas merge):** O(n+m) time, O(n+m) memory. Optimal for simple column-ref keys. [ASSUMED: standard pandas merge complexity]
- **Context-only join:** O(1) expression eval + O(m) filter + O(n*k) cross-join where k = filtered lookup size. Bounded by lookup size. [ASSUMED]
- **Cross-table join:** O(n*m) comparisons via Java bridge preprocessing. Memory is O(n*k) where k = avg matches per row. Must have size guard. [ASSUMED]
- **ALL_MATCHES (no dedup):** O(n*m) worst case for cartesian product. Size guard essential. [ASSUMED]

**Recommendation:** Use configurable thresholds: warn at 10M result rows, fail at 100M. These can be overridden per-job in config.

### Topic 10: Talend Studio javajet Templates for tMap Internals

**Finding:** The javajet template structure is:
- `tMap_begin.javajet` / `tMap_begin.inc.javajet`: Lookup table loading, data structure initialization (AdvancedMemoryLookup, SortableRow), struct class generation, variable table initialization
- `tMap_main.javajet` / `tMap_main.inc.javajet`: Per-row processing (lookup matching, variable evaluation, output routing, reject handling, error catching)
- `tMap_end.javajet` / `tMap_end.inc.javajet`: Cleanup (endGet on lookups, globalMap removal), logging stats
- `tMap_commons.skeleton`: Utility methods, type conversion, expression parsing, auto-convert support

**Key behavioral insights from javajet:**
1. Lookups use AdvancedMemoryLookup with HashMap -- UNIQUE_MATCH overwrites (last wins)
2. Null keys skip lookup entirely (hasCasePrimitiveKeyWithNull flag)
3. Variables evaluated after ALL lookups, in document order, can reference earlier variables
4. Per-row processing is SEQUENTIAL (no parallel execution in Talend)
5. rejectedInnerJoin is a per-row boolean flag, distinct from output filter rejection
6. activateCondensedTool catches expression exceptions and routes to error output
7. RELOAD_AT_EACH_ROW re-executes lookup subprocess per main row
8. Stats logged per output via count_* variables when Log4j enabled
9. No explicit NB_LINE globalMap variable set in tMap_end -- stats tracked via count logging
10. ENABLE_AUTO_CONVERT_TYPE uses autoConverterMap for type-pair conversions with date/string pattern support

[VERIFIED: tMap_begin.inc.javajet, tMap_main.inc.javajet, tMap_end.inc.javajet, tMap_commons.skeleton via WebFetch]

## Architecture Patterns

### Recommended File Structure

```
src/v1/engine/components/transform/
    map.py                          # Full rewrite (target: ~600-800 lines)

tests/v1/engine/components/transform/
    __init__.py
    test_map.py                     # Comprehensive tests (~60-100 tests)
```

### Pattern 1: BaseComponent Lifecycle Integration

**What:** tMap uses BaseComponent lifecycle but overrides three hooks to handle multi-flow semantics.

**Override 1: _resolve_expressions()**
```python
def _resolve_expressions(self) -> None:
    """Resolve context variables on scalar config fields only.

    tMap's expressions (output columns, filters, variables, join keys)
    reference row data and must be evaluated per-row in _process(),
    not at config resolution time. Only resolve context variables on
    top-level scalar config values (die_on_error, rows_buffer_size, etc.).
    """
    if self.context_manager:
        # Only resolve top-level scalar values, not nested inputs/outputs/variables
        for key in ("die_on_error", "rows_buffer_size", "label"):
            if key in self.config and isinstance(self.config[key], str):
                self.config[key] = self.context_manager.resolve_string(self.config[key])
```

**Override 2: _update_stats_from_result()**
```python
def _update_stats_from_result(self, result: dict) -> None:
    """Sum rows across ALL named output DataFrames."""
    total_rows = 0
    reject_rows = 0
    for key, value in result.items():
        if key == "stats":
            continue
        if isinstance(value, pd.DataFrame) and not value.empty:
            count = len(value)
            total_rows += count
            # Check if this output is a reject output
            output_config = self._get_output_config(key)
            if output_config and (output_config.get("is_reject") or output_config.get("inner_join_reject")):
                reject_rows += count
    self.stats["NB_LINE"] += total_rows
    self.stats["NB_LINE_OK"] += total_rows - reject_rows
    self.stats["NB_LINE_REJECT"] += reject_rows
```

**Override 3: _select_mode()**
```python
def _select_mode(self, input_data) -> ExecutionMode:
    """Always BATCH -- tMap handles its own chunking via Java bridge."""
    return ExecutionMode.BATCH
```
[VERIFIED: BaseComponent hooks at base_component.py lines 235, 360, 455]

### Pattern 2: Multi-Input/Output Data Flow

**What:** tMap receives Dict[flow_name, DataFrame] from OutputRouter and returns Dict[output_name, DataFrame].

**Input handling:**
```python
def _process(self, input_data=None) -> dict:
    # OutputRouter returns dict for multi-input components
    if isinstance(input_data, dict):
        inputs = input_data
    elif isinstance(input_data, pd.DataFrame):
        main_name = self.config["inputs"]["main"]["name"]
        inputs = {main_name: input_data}
    else:
        return self._create_empty_outputs()
    
    main_name = self.config["inputs"]["main"]["name"]
    main_df = inputs.get(main_name)
    # ... process lookups, variables, outputs ...
    return {"out1": out1_df, "reject1": reject1_df}
```
[VERIFIED: OutputRouter.get_input_data returns dict for multi-input at output_router.py:150-169]

### Pattern 3: Smart Join Routing (Classification)

**What:** Classify each lookup's join keys to route to the optimal join strategy.

```python
def _classify_join_type(self, join_keys: list[dict]) -> str:
    """Classify join keys into: equality, context_only, or cross_table."""
    for jk in join_keys:
        expr = self._strip_java_marker(jk["expression"])
        if self._is_simple_column_ref(expr):
            continue  # Equality join key
        if self._is_context_only_expression(expr):
            continue  # Context-only (will be single value after eval)
        return "cross_table"  # Has cross-table expression
    
    # If all keys are context-only
    if all(self._is_context_only_expression(
            self._strip_java_marker(jk["expression"])) for jk in join_keys):
        return "context_only"
    return "equality"
```

**Routing:**
- `equality`: pandas merge -- fast, O(n+m)
- `context_only`: evaluate context expressions once, filter lookup, cross-join
- `cross_table`: Java bridge preprocessing to evaluate join expressions per row, then merge on evaluated columns

### Pattern 4: Null Key Pre-Filter (MAP-03)

**What:** Pre-filter rows where ANY join key is null/NaN on both main and lookup sides before pandas merge.

```python
def _prefilter_null_keys(self, df: pd.DataFrame, key_columns: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split DataFrame into rows with all keys non-null vs any key null.
    
    Returns:
        (non_null_df, null_key_df) -- null_key_df goes to inner join reject if applicable.
    """
    null_mask = df[key_columns].isna().any(axis=1)
    return df[~null_mask].copy(), df[null_mask].copy()
```

This matches Talend behavior where null keys skip lookup entirely (`hasCasePrimitiveKeyWithNull` flag). [VERIFIED: tMap_main.inc.javajet]

### Pattern 5: Inner Join Reject Tracking (MAP-02)

**What:** Track per-lookup which main rows failed inner join, using pandas merge indicator.

```python
# Per lookup (inner join only):
result = main_df.merge(lookup_df, left_on=left_keys, right_on=right_keys,
                        how="left", indicator=True)
unmatched_mask = result["_merge"] == "left_only"
inner_join_rejects = result[unmatched_mask].drop(columns=["_merge"])
matched = result[~unmatched_mask].drop(columns=["_merge"])
```

Rows in inner_join_rejects are tracked separately. Outputs with `rejectInnerJoin=true` receive these rows. Outputs with `is_reject=true` but NOT `rejectInnerJoin` receive rows that pass joins but fail output expression filters. [VERIFIED: tMap_main.inc.javajet -- rejectedInnerJoin boolean distinct from output filter]

### Pattern 6: Compiled Script Generation (Thread-Safe)

**What:** Generate sequential (not parallel) Java/Groovy script for output evaluation.

**Fix for BUG-MAP-003:** Replace `IntStream.range(0, rowCount).parallel().forEach()` with `IntStream.range(0, rowCount).forEach()`.

Each iteration gets its own `Var` map as a local variable inside the forEach lambda. This is already correct in the current code (Var is declared inside the loop body), but parallel execution creates race conditions on the shared output arrays. Sequential execution eliminates this. The AtomicInteger counters can be replaced with simple int counters.

### Anti-Patterns to Avoid

- **Do NOT override execute():** Use lifecycle hooks instead. The current code's execute() override bypasses config immutability, stats tracking, and error wrapping.
- **Do NOT manually sync context/globalMap to Java bridge:** Phase 2's `_call_java_with_sync()` handles this automatically for preprocessing and compiled execution.
- **Do NOT use parallel forEach in compiled scripts:** Talend processes rows sequentially. Parallel execution introduces race conditions with no significant performance benefit at 50K chunk sizes.
- **Do NOT store processing state on self:** All state (joined_df, lookup results, inner_join_rejects) must be local to _process().
- **Do NOT assume UNIQUE_MATCH means first-row:** Talend's HashMap.put overwrites, making it last-row semantics.

## UNIQUE_MATCH Semantics Deep Dive

This is the most important finding of this research and contradicts CONTEXT.md D-11.

**Talend's AdvancedMemoryLookup implementation:**
- UNIQUE_MATCH uses `HashMap<V, V>` with `uniqueHash.put(value, value)` [VERIFIED: AdvancedMemoryLookup.java source via GitHub oVirt/ovirt-dwh mirror]
- HashMap.put() overwrites existing entries -- **last value inserted for a given key wins**
- Lookup data is loaded sequentially from upstream, so "last" means "last row in the lookup DataFrame with that key"

**Official Talend documentation:**
- "Unique match: If your primary row matches multiple rows in your look-up input, then only the **last matching row** will be output" [CITED: faihofu.blogspot.com/2019/08/talend-tos-tmap-join-configuration.html]
- FIRST_MATCH is explicitly defined as returning the first row, distinct from UNIQUE_MATCH [CITED: same source]

**Current engine code:** Uses `drop_duplicates(keep='last')` -- this is CORRECT Talend behavior.

**CONTEXT.md D-11 states:** "UNIQUE_MATCH uses first-row semantics (`drop_duplicates(keep='first')`). Current code incorrectly uses `keep='last'`." -- This is factually incorrect based on research.

**Recommendation:** Surface this finding to the user. The current code is correct. D-11 should be updated to `keep='last'` (or `keep='last'` should be preserved as-is since it already matches Talend).

## activateCondensedTool (Catch Output Reject) Design

From javajet analysis, the catch output reject mechanism works as follows:

1. **Configuration:** Each output table has an `activateCondensedTool` boolean (mapped to `catch_output_reject` in converter output)
2. **Runtime behavior:** Expression evaluation for all non-reject outputs is wrapped in try-catch
3. **On expression error:**
   - Row is NOT written to any normal output
   - Row data (from available main/lookup columns) is written to outputs with `catch_output_reject=true`
   - Additional fields `errorMessage` and `errorStackTrace` may be added
   - Processing continues with next row
4. **Distinction from other rejects:**
   - Inner join reject: lookup found no match (rejectedInnerJoin flag)
   - Output filter reject: row didn't pass output's expressionFilter
   - Catch output reject: expression evaluation threw an exception

**Implementation approach:** In the compiled script, wrap variable + non-reject output evaluation in an inner try-catch. On catch, route to catch output reject. This is already partially implemented in the current code (die_on_error=false path with errorCount/errorMap tracking).

## RELOAD_AT_EACH_ROW Implementation Design

**Talend behavior (from javajet):**
1. Lookup hash starts null
2. Per main row: execute lookup subprocess (e.g., DB query), rebuild lookup hash
3. Match current main row against fresh lookup

**Python engine equivalent (since lookups come from DataFrames, not re-queryable DB):**
- Store the full unfiltered lookup DataFrame
- For each main row: set globalMap variables from the row, re-evaluate the lookup filter expression, create a filtered lookup DataFrame, perform the join for this single row
- This is O(n*m) but matches the Talend semantics for parameterized lookups

**When this matters:** RELOAD_AT_EACH_ROW is used when the lookup filter references variables that change per row (e.g., `globalMap.get("current_region")`). Without reload, the filter is evaluated once with the initial variable values.

## ENABLE_AUTO_CONVERT_TYPE Design

**Talend behavior (from tMap_commons.skeleton):**
- When enabled, join key columns are automatically cast to compatible types before comparison
- Uses an `autoConverterMap` with type-pair conversion functions
- Common conversions: String<->Integer, String<->Date (with pattern), Integer<->Long
- Applied at join key evaluation time, not at data loading time

**Implementation approach:**
1. Converter update: re-add `enable_auto_convert_type` to converter output (currently stripped as hidden param)
2. Engine: when enabled, before merge, cast join key columns to compatible types using pandas astype()
3. Focus on common type mismatches: str->int, int->str, float->int

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Bulk equality joins | Custom hash-match loop | `pd.DataFrame.merge()` | Optimized C implementation, handles all join types |
| Expression evaluation | Python eval() or AST parser | Java bridge `execute_tmap_preprocessing()` | Talend expressions are Java/Groovy, not Python |
| Compiled batch execution | Custom per-row loop in Python | Java bridge `compile_tmap_script()` + `execute_compiled_tmap_chunked()` | Performance-critical, JVM handles compilation and hot-path optimization |
| Null key detection | Custom per-column null check | `df[key_cols].isna().any(axis=1)` | Vectorized pandas operation, handles all NA types |
| Config deepcopy/reset | Manual config management | BaseComponent lifecycle | Automatic deepcopy from _original_config per execute() |

## Common Pitfalls

### Pitfall 1: Expression Resolution Timing
**What goes wrong:** BaseComponent's default _resolve_expressions() scans ALL config for {{java}} markers and evaluates them as one-time expressions. tMap's expressions reference row data (row1.column, lookup1.column) which don't exist at config resolution time.
**Why it happens:** Default lifecycle assumes config expressions can be evaluated before _process().
**How to avoid:** Override _resolve_expressions() to skip Java marker resolution entirely. Only resolve context variables on scalar config fields.
**Warning signs:** Java bridge errors about undefined variables (row1, lookup1) during config resolution.

### Pitfall 2: pandas NaN==NaN Matching in Merge
**What goes wrong:** pandas merge treats NaN==NaN as a match (hash-based). Talend/SQL treats NULL != NULL.
**Why it happens:** pandas follow Python/numpy NaN equality semantics, not SQL semantics.
**How to avoid:** Pre-filter rows with null join keys BEFORE merge. Track null-key main rows for potential inner join reject routing.
**Warning signs:** Rows with null keys appearing in join results when they shouldn't.

### Pitfall 3: Column Name Collisions in Joined DataFrame
**What goes wrong:** If main and lookup have columns with the same name, pandas merge creates suffixed columns (e.g., `id_x`, `id_y`). The Java bridge RowWrapper can't find columns by their expected names.
**Why it happens:** pandas auto-suffixes duplicate column names in merge.
**How to avoid:** Prefix ALL lookup columns with `{lookup_name}.{column}` before merge. The RowWrapper already handles this mapping.
**Warning signs:** KeyError when RowWrapper tries to access columns by table.column pattern.

### Pitfall 4: Stats Counting for Multi-Output
**What goes wrong:** BaseComponent's default _update_stats_from_result() only counts "main" and "reject" keys. tMap returns arbitrary named outputs (out1, out2, reject1, etc.).
**Why it happens:** Default implementation assumes standard main/reject flow pattern.
**How to avoid:** Override _update_stats_from_result() to iterate all named outputs and sum counts.
**Warning signs:** NB_LINE showing 0 despite producing output rows.

### Pitfall 5: Config Mutation on Re-Execute
**What goes wrong:** If any processing state is stored on self or if config is mutated during _process(), iterate re-execution produces wrong results.
**Why it happens:** tMap processing is complex and tempting to store intermediate state.
**How to avoid:** All processing state must be local variables in _process(). Never modify self.config or self._original_config. BaseComponent provides fresh config deepcopy per execute().
**Warning signs:** Second execute() producing different results from first with same input.

### Pitfall 6: Thread Safety in Compiled Scripts
**What goes wrong:** Using IntStream.parallel().forEach() with shared HashMap for variables causes race conditions, lost updates, or ConcurrentModificationException.
**Why it happens:** Developer optimization attempt that violates thread safety constraints.
**How to avoid:** Use sequential forEach(). Talend processes rows sequentially. Performance impact is minimal within 50K-row chunks.
**Warning signs:** Intermittent wrong results, missing rows in output, ConcurrentModificationException.

## Code Examples

### Converter Output Format (Config Key Reference)

The converter produces this JSON structure that the engine must consume:

```python
# Source: tests/talend_xml_samples/converted_jsons/Job_tMap_0.1.json
config = {
    "inputs": {
        "main": {
            "name": "row1",           # Flow name from upstream
            "filter": "",             # {{java}} expression or empty
            "activate_filter": False,
            "matching_mode": "UNIQUE_MATCH",
            "lookup_mode": "LOAD_ONCE",
        },
        "lookups": [{
            "name": "row2",           # Flow name from upstream
            "matching_mode": "UNIQUE_MATCH",
            "lookup_mode": "LOAD_ONCE",
            "filter": "",
            "activate_filter": False,
            "join_keys": [{
                "lookup_column": "country_code",
                "expression": "{{java}}row1.country_code",
                "type": "str",
                "nullable": True,
                "operator": "=",
            }],
            "join_mode": "LEFT_OUTER_JOIN",  # or "INNER_JOIN"
        }],
    },
    "variables": [{
        "name": "var1",
        "expression": "{{java}}row1.name",
        "type": "str",
        "nullable": True,
    }],
    "outputs": [{
        "name": "out",
        "is_reject": False,
        "inner_join_reject": False,
        "filter": "{{java}}row1.salary > 60000",
        "activate_filter": True,
        "columns": [{
            "name": "full_name",
            "expression": "{{java}}row1.first_name + \" \" + row1.last_name",
            "type": "str",
            "nullable": True,
        }],
        "catch_output_reject": False,
    }],
    "die_on_error": True,
}
```
[VERIFIED: Job_tMap_0.1.json in tests/talend_xml_samples/converted_jsons/]

### Java Bridge API Usage

```python
# Source: src/v1/java_bridge/bridge.py lines 281-332, 401-453, 455-520
# Phase 2 rewritten APIs with automatic sync

# 1. Preprocessing: batch evaluate expressions on DataFrame rows
results = self.java_bridge.execute_tmap_preprocessing(
    df=joined_df,
    expressions={"join_key_0": "row1.id + lookup1.offset"},
    main_table_name="row1",
    lookup_table_names=["lookup1"],
    schema=schema_dict,  # Column name -> type string
)
# results: {"join_key_0": numpy_array_of_values}

# 2. Compile script once
self.java_bridge.compile_tmap_script(
    component_id=self.id,
    java_script=script_string,
    output_schemas={"out1": ["col1", "col2"]},
    output_types={"out1_col1": "id_String", "out1_col2": "id_Integer"},
    main_table_name="row1",
    lookup_names=["lookup1"],
)

# 3. Execute compiled script in chunks
output_dfs = self.java_bridge.execute_compiled_tmap_chunked(
    component_id=self.id,
    df=joined_df,
    chunk_size=50000,
    schema=schema_dict,
)
# output_dfs: {"out1": DataFrame, "out2": DataFrame}
```
[VERIFIED: bridge.py source]

### OutputRouter Multi-Input API

```python
# Source: src/v1/engine/output_router.py lines 150-169
# For components with multiple inputs, get_input_data returns dict
input_data = output_router.get_input_data("tMap_1")
# Returns: {"row1": DataFrame, "lookup1": DataFrame}
# For single-input: returns DataFrame directly

# After processing, route_outputs maps named outputs to downstream flows
output_router.route_outputs("tMap_1", {"out1": out1_df, "reject1": reject1_df})
```
[VERIFIED: output_router.py source]

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Override execute() entirely | BaseComponent lifecycle hooks | Phase 1 (ENG-08, ENG-09) | Config immutability, iterate support, stats tracking |
| Manual context/globalMap sync | _call_java_with_sync() auto-sync | Phase 2 (BRDG-03) | Eliminates sync bugs, bidirectional sync |
| Engine.COMPONENT_REGISTRY dict | @REGISTRY.register() decorator | Phase 3 (D-04) | Auto-registration on import |
| Engine._get_input_data() type-matching | OutputRouter.get_input_data() | Phase 3 (D-01) | Proper multi-input routing |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | **UNIQUE_MATCH uses LAST-row semantics (keep='last'), not first-row (keep='first')**. Research shows Talend's HashMap.put overwrites, and official docs confirm "last matching row". CONTEXT.md D-11 states the opposite. | UNIQUE_MATCH Deep Dive, MAP-01 | **HIGH** -- If D-11 is correct despite evidence, the engine will produce wrong join results for every UNIQUE_MATCH lookup. User must confirm. |
| A2 | Performance impact of removing .parallel() from compiled script is negligible at 50K chunk sizes. | Topic 4 (Thread Safety) | LOW -- If performance matters, sequential execution within 50K rows is still fast. Can benchmark later. |
| A3 | Cross-table join expressions are rare in production jobs. | Topic 1, 9 | MEDIUM -- If many production jobs use cross-table joins, the cross-table path needs better optimization than chunked nested-loop. |
| A4 | RELOAD_AT_EACH_ROW can be implemented as per-row re-filter of cached lookup DataFrame. | Topic 6 | MEDIUM -- If production jobs expect actual DB re-query, this approximation may not produce identical results. But since the engine gets lookups from DataFrames (not DB), re-filtering is the closest semantic match. |
| A5 | Standard pandas merge complexity is O(n+m) for hash join. | Topic 9 | LOW -- Well-established complexity for pandas merge on non-sorted data. |
| A6 | NB_LINE globalMap variable in tMap counts total output rows across all outputs (not input rows). | MAP-07 | MEDIUM -- The javajet shows per-output count_* counters but no explicit NB_LINE aggregation. May need to verify against actual Talend runtime. Current BaseComponent counts main+reject which may need override. |

## Open Questions

1. **UNIQUE_MATCH semantics (A1)**
   - What we know: Talend source code and docs say last-row. CONTEXT.md D-11 says first-row.
   - What's unclear: Whether D-11 was based on actual Talend testing or incorrect assumption.
   - Recommendation: Surface to user. Research evidence strongly supports keep='last'. If user insists on keep='first', document the decision as intentional deviation from Talend behavior.

2. **NB_LINE counting scope (A6)**
   - What we know: BaseComponent counts main + reject. tMap has arbitrary named outputs.
   - What's unclear: Whether Talend's tMap NB_LINE counts all output rows or just main rows.
   - Recommendation: Override _update_stats_from_result to count all output rows (safer -- matches what Talend's per-output counters sum to). Verify against actual Talend runtime if possible.

3. **ENABLE_AUTO_CONVERT_TYPE converter update**
   - What we know: Converter currently strips this as hidden param. Engine needs it.
   - What's unclear: Whether any production jobs actually use this parameter.
   - Recommendation: Small converter update to re-add it. The param exists in the sample .item file (`ENABLE_AUTO_CONVERT_TYPE value="false"`), so it's safe to extract.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (inferred from test_*.py naming, conftest.py present) |
| Config file | tests/v1/engine/conftest.py |
| Quick run command | `python -m pytest tests/v1/engine/components/transform/test_map.py -x -q` |
| Full suite command | `python -m pytest tests/v1/engine/ -x -q` |

### Phase Requirements to Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| MAP-01 | UNIQUE_MATCH semantics (last-row per research) | unit | `pytest tests/v1/engine/components/transform/test_map.py -k "unique_match" -x` | Wave 0 |
| MAP-02 | Inner join reject routing distinct from generic reject | unit | `pytest tests/v1/engine/components/transform/test_map.py -k "inner_join_reject" -x` | Wave 0 |
| MAP-03 | Null keys never match in joins | unit | `pytest tests/v1/engine/components/transform/test_map.py -k "null_key" -x` | Wave 0 |
| MAP-04 | Uses BaseComponent lifecycle (no execute override) | unit | `pytest tests/v1/engine/components/transform/test_map.py -k "lifecycle" -x` | Wave 0 |
| MAP-05 | activateCondensedTool catch output reject | unit | `pytest tests/v1/engine/components/transform/test_map.py -k "catch_output" -x` | Wave 0 |
| MAP-06 | ENABLE_AUTO_CONVERT_TYPE join column conversion | unit | `pytest tests/v1/engine/components/transform/test_map.py -k "auto_convert" -x` | Wave 0 |
| MAP-07 | {id}_NB_LINE globalMap variable | unit | `pytest tests/v1/engine/components/transform/test_map.py -k "nb_line" -x` | Wave 0 |
| MAP-08 | RELOAD_AT_EACH_ROW lookup mode | unit | `pytest tests/v1/engine/components/transform/test_map.py -k "reload" -x` | Wave 0 |
| TEST-03 | Comprehensive engine unit tests for tMap | unit | `pytest tests/v1/engine/components/transform/test_map.py -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/v1/engine/components/transform/test_map.py -x -q`
- **Per wave merge:** `python -m pytest tests/v1/engine/ -x -q`
- **Phase gate:** Full suite green before /gsd-verify-work

### Wave 0 Gaps
- [ ] `tests/v1/engine/components/transform/__init__.py` -- package init
- [ ] `tests/v1/engine/components/transform/test_map.py` -- all tMap tests (60-100 tests)

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | N/A -- batch ETL, no auth |
| V3 Session Management | no | N/A -- no sessions |
| V4 Access Control | no | N/A -- file-based, OS permissions |
| V5 Input Validation | yes | Config validation via _validate_config(); expression validation via Java bridge (sandboxed JVM) |
| V6 Cryptography | no | N/A -- no crypto operations |

### Known Threat Patterns for tMap

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Java expression injection via config | Tampering | Expressions come from converter (trusted .item files), not user input. Java bridge evaluates in sandboxed Groovy. |
| Cartesian join memory exhaustion | Denial of Service | Size guard: warn at configurable threshold, fail at hard limit |
| Unconstrained RELOAD_AT_EACH_ROW | Denial of Service | Each reload re-filters full lookup DataFrame. O(n*m) worst case. Log warning for large datasets. |

## Sources

### Primary (HIGH confidence)
- [Talaxie/tdi-studio-se tMap_begin.inc.javajet](https://raw.githubusercontent.com/Talaxie/tdi-studio-se/refs/heads/master/main/plugins/org.talend.designer.components.localprovider/components/tMap/tMap_begin.inc.javajet) -- Lookup loading, data structure initialization
- [Talaxie/tdi-studio-se tMap_main.inc.javajet](https://raw.githubusercontent.com/Talaxie/tdi-studio-se/refs/heads/master/main/plugins/org.talend.designer.components.localprovider/components/tMap/tMap_main.inc.javajet) -- Per-row processing, variable evaluation, reject routing
- [Talaxie/tdi-studio-se tMap_end.inc.javajet](https://raw.githubusercontent.com/Talaxie/tdi-studio-se/refs/heads/master/main/plugins/org.talend.designer.components.localprovider/components/tMap/tMap_end.inc.javajet) -- Cleanup, stats
- [Talaxie/tdi-studio-se tMap_java.xml](https://raw.githubusercontent.com/Talaxie/tdi-studio-se/refs/heads/master/main/plugins/org.talend.designer.components.localprovider/components/tMap/tMap_java.xml) -- Parameter definitions
- [AdvancedMemoryLookup.java (oVirt mirror)](https://github.com/oVirt/ovirt-dwh/blob/master/ovirt-engine-dwh/advancedPersistentLookupLib/src/main/java/org/talend/designer/components/lookup/memory/AdvancedMemoryLookup.java) -- UNIQUE_MATCH HashMap implementation
- Codebase: `src/v1/engine/components/transform/map.py` -- Current implementation (rewrite target)
- Codebase: `src/v1/engine/base_component.py` -- Lifecycle hooks
- Codebase: `src/v1/java_bridge/bridge.py` -- Phase 2 tMap APIs
- Codebase: `src/v1/engine/output_router.py` -- Multi-input/output routing
- Codebase: `src/converters/talend_to_v1/components/transform/map.py` -- Converter output format
- Codebase: `tests/talend_xml_samples/converted_jsons/Job_tMap_0.1.json` -- Sample converter output

### Secondary (MEDIUM confidence)
- [Talend tMap Match Models blog](https://faihofu.blogspot.com/2019/08/talend-tos-tmap-join-configuration.html) -- Confirms UNIQUE_MATCH = last matching row
- [Talend Components Help: Advanced mapping](https://help.qlik.com/talend/en-US/components/8.0/tmap/tmap-tfileinputdelimited-tfileoutputdelimited-tfileoutputdelimited-advanced-mapping-using-filters-explicit-joins-and-rejections-standard-component-this) -- Inner join reject and catch output reject behavior

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- Python/pandas/Java bridge are locked decisions, all APIs verified in codebase
- Architecture: HIGH -- BaseComponent lifecycle hooks verified, OutputRouter API verified, bridge APIs verified
- Join semantics: HIGH -- Verified against AdvancedMemoryLookup source and official docs
- UNIQUE_MATCH: HIGH -- Multiple sources agree (source code + docs), but conflicts with user decision D-11
- Pitfalls: HIGH -- Based on direct code analysis and javajet behavior analysis
- RELOAD_AT_EACH_ROW: MEDIUM -- javajet behavior clear, but engine approximation is an interpretation

**Research date:** 2026-04-15
**Valid until:** 2026-05-15 (stable domain -- Talend behavior unlikely to change)
