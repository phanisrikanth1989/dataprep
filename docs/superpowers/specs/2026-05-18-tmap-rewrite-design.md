# tMap Engine Component — Modular Rewrite Design

**Date:** 2026-05-18
**Author:** Brainstorming session (Aarun + Claude)
**Status:** Locked design, awaiting user review before implementation plan

---

## 1. Goal

Rewrite `src/v1/engine/components/transform/map.py` (currently 4292 lines in a single file with documented bugs, XFAIL'd test cases, and a history of regressions) as a small folder of focused modules. Preserve the existing converter JSON contract. Cover the features production jobs actually use; drop everything else. Fix the type-fidelity and Arrow-emission bugs at source.

**Why now:** Manager has been handing the developer (Aarun) a fresh list of tMap bugs each day for 4 days. The whack-a-mole pattern is a strong signal that the architecture is wrong, not just the individual bugs. The current 5-way join dispatch + dual-execution-path (Java-marker vs Python-eval) + defensive bounds-clamp + `__rejectMode__`-flag-dispatch in a single Groovy script produce interactions that current code paths don't reason about cleanly.

**Why a rewrite (not more patches):** The user's project memory `feedback_rewrite_over_patch` says: prefer clean rewrites over bug-by-bug patching for systemic issues. tMap is systemic.

---

## 2. Constraints (load-bearing)

From `CLAUDE.md` and this brainstorming session:

- **Tech stack fixed:** Python 3.10+, Java 11+, Py4J + Apache Arrow. No framework changes.
- **Talend parity is non-negotiable:** every test cell must match what a Talend job with the equivalent `.item` config produces.
- **Java bridge architecture is fixed:** Py4J + Arrow stays; no replacement.
- **No breaking changes to the JSON config format:** the converter's current output shape must continue to work without re-conversion. (Section 11 specifies the contract.)
- **No new dependencies:** all changes use existing Py4J / Arrow / pandas / numpy.
- **ASCII-only logging.** No emojis or unicode in any log line (`feedback_ascii_logging`).
- **Fix the source, no defensive fallbacks** (`feedback_fix_source_no_fallbacks`): when we identify a root cause (e.g. `set_context` str-coercion), we fix it at the source, not paper over it downstream.
- **Test the real Java bridge** (`feedback_test_real_bridge`): every behavioral test for compiled-script paths must use the `@pytest.mark.java` real-bridge fixture, not mocks.
- **Phase 14 coverage gate:** every new module must hit ≥95% per-module line coverage at the final commit.

---

## 3. Scope (locked)

**IN SCOPE — features the rewrite must support:**

| Area | Features |
|---|---|
| Inputs | 1 main + N lookups (1-10 reasonable) |
| Matching modes | UNIQUE_MATCH, FIRST_MATCH, LAST_MATCH, ALL_MATCHES |
| Lookup modes | LOAD_ONCE, RELOAD_AT_EACH_ROW |
| Join modes | LEFT_OUTER_JOIN, INNER_JOIN |
| Filters | main input filter, lookup filter, output filter |
| Join key patterns | Simple equality, Computed equality (main/prior refs), Filter-as-match (no equality key) |
| Variables | Sequential chained eval (Var.var2 sees Var.var1), can write to globalMap as side effect |
| Output expressions | Simple col copy, Java expressions, context/globalMap refs, routine calls, empty → null |
| Reject types | is_reject (output filter), inner_join_reject (lookup miss), catch_output_reject (expression errors) |
| Routines | StringHandling, TalendDate, Mathematical, custom project routines |
| Context/globalMap value types | id_String, id_Integer, id_Long, id_Date (date AND datetime), id_BigDecimal, id_Float, id_Double, id_Boolean — type fidelity preserved end-to-end |
| Error handling | die_on_error=true (default), die_on_error=false → route to catch_output_reject |
| Scale | Medium (chunking required; chunk size auto-tuned by row memory size) |
| ENABLE_AUTO_CONVERT_TYPE | str↔numeric, int↔float join-key coercion |

**OUT OF SCOPE — explicitly dropped:**

| Feature | Reason |
|---|---|
| CACHE_OR_RELOAD lookup mode | Not used in production |
| LKUP_PARALLELIZE | Talend-listed but not used in production |
| LEVENSHTEIN / JACCARD fuzzy match | Not used in production |
| CHANGE_HASH_AND_EQUALS_FOR_BIGDECIMAL | Not used in production |
| ROWS_BUFFER_SIZE disk-spilling | In-memory lookups sufficient at production scale |
| TEMPORARY_DATA_DIRECTORY | Commented out in Talaxie too; tied to disk-spill |
| Python-eval path (no-marker dispatch) | All production tMaps come from the converter with `{{java}}` markers. Single execution path = simpler. |
| Computed lookup-side join keys | Not expressible in Talend tMap UI (right-side of a join key is just a column picker) |
| Truly two-sided join keys | Same UI constraint; "two-sided matching" done via lookup filter, which we cover via Filter-as-match strategy |
| PyMap component | Separate component, not in this rewrite scope |
| FilterRows component | Separate component, not in this rewrite scope |
| `RowWrapper.java` changes | Untouched; works correctly |

---

## 4. Architecture — File Structure

```
src/v1/engine/components/transform/map/
├── __init__.py                    # re-exports Map for COMPONENT_REGISTRY
├── map_component.py               # ~200 LOC: Map(BaseComponent), _process orchestrator
├── map_config.py                  # ~200 LOC: config dataclasses + _validate_config
├── map_joins.py                   # ~350 LOC: 3 join strategies + RELOAD mode + dispatcher
├── map_compiled_script.py         # ~400 LOC: Groovy script generation (active + reject)
├── map_reject_routing.py          # ~250 LOC: post-bridge routing for 3 reject types
└── map_bridge_sync.py             # ~150 LOC: type-safe context+globalMap push
```

**Total: ~1550 LOC in 7 files** (vs current 4292 LOC in one file).

### Per-module responsibility (single responsibility principle)

**`__init__.py`** — re-exports `Map` so `COMPONENT_REGISTRY.register("Map", "tMap")` continues to work via existing import path `src.v1.engine.components.transform.map`.

**`map_component.py`** — the top-level `Map(BaseComponent)` class.
- Overrides: `_validate_config`, `_resolve_expressions` (scalar fields only), `_select_mode` (always BATCH), `_update_stats_from_result` (sum across all named outputs)
- `_process()` orchestrator (linear top-to-bottom; see Section 5)
- Does NO real work — delegates to other modules

**`map_config.py`** — config validation + dataclasses.
- `MapConfig`, `MainInputCfg`, `LookupCfg`, `JoinKeyCfg`, `VariableCfg`, `OutputCfg`, `ColumnCfg` dataclasses derived from the JSON shape in Section 11
- `validate_config(raw_config: dict) -> MapConfig` raises `ConfigurationError` on missing/invalid keys
- Hard-fails if any `{{java}}` marker present AND `java_bridge is None`

**`map_joins.py`** — lookup join execution + joined_df schema.
- `execute_lookup_join(joined_df, lookup_df, lookup_cfg, prior_lookups, java_bridge) -> (joined_df, inner_join_rejects)`
- `classify_join_strategy(join_keys, lookup_filter) -> JoinStrategy enum` (SIMPLE | COMPUTED | FILTER_AS_MATCH | RELOAD)
- Three strategy functions:
  - `_join_simple_equality(...)` — pandas merge directly
  - `_join_computed_equality(...)` — bridge-eval expression once, then pandas merge
  - `_join_filter_as_match(...)` — chunked cross-product + bridge-eval filter per chunk
- `_join_reload_per_row(...)` — separate dispatch for RELOAD_AT_EACH_ROW mode
- `compute_joined_df_schema(main_schema, consumed_lookups, variables, temp_join_key_cols) -> dict[str, str]` — single source of truth for joined_df column types (see Section 9)
- Helpers: `_apply_matching_mode`, `_prefix_lookup_columns`, `_prefilter_null_keys`, `_auto_convert_join_keys`, `_chunked_cross_product`

**`map_compiled_script.py`** — pure Groovy script generation.
- `build_active_script(config) -> str` — variables + all active output columns + is_reject filter routing + try/catch for catch_output_reject
- `build_reject_script(config) -> str` — inner_join_reject output column expressions only (no variables, no filters, no try/catch)
- Helpers: `_groovy_escape_expression` (in-string `$` escape), `_emit_variable_block`, `_emit_output_block`, `_emit_atomic_row_commit`
- Pure functions: take config, return string. No bridge calls, no state.

**`map_reject_routing.py`** — post-bridge DataFrame routing.
- `route_rejects(active_results, reject_results, errors_df, inner_join_reject_dfs, config) -> dict[str, pd.DataFrame]`
- Handles three reject types in order:
  - inner_join_reject ← merge `reject_results` + carry-over from `inner_join_reject_dfs` if reject script wasn't called
  - catch_output_reject ← combine `errors_df` rows + user-defined column values
  - is_reject ← already populated inside active script; just pass through
- Reserved-column policy (D-06): when user maps `errorMessage` / `errorStackTrace`, framework values win; otherwise emit only user-defined columns

**`map_bridge_sync.py`** — typed state push to bridge.
- `push_runtime_state_to_bridge(component, java_bridge) -> None`
- Writes directly to `java_bridge.context[k] = v` and `java_bridge.global_map[k] = v` (typed; no str-coerce)
- Type-aware: id_Float values wrapped via `gateway.jvm.java.lang.Float(v)` to avoid Py4J auto-Double; date/datetime flow through the existing registered Py4J converters
- The ONLY module that touches `java_bridge.context` / `.global_map` directly

### Dependency graph (no cycles)

```
map_component.py
    ├── map_config.py
    ├── map_joins.py
    │       └── map_bridge_sync.py (for bridge eval of computed keys / filter)
    ├── map_compiled_script.py (pure, no other map_ imports)
    ├── map_bridge_sync.py
    └── map_reject_routing.py
            └── map_bridge_sync.py (for reject script bridge calls)
```

`map_compiled_script.py` is pure — no dependencies on other map_ modules. `map_config.py` depends on nothing else in the package. `map_bridge_sync.py` depends on nothing else in the package. The other three orchestrate.

---

## 5. Data Flow

```
Map.execute(input_data)        [BaseComponent template method, unchanged]
   ↓
_validate_config()                                  [map_config.validate_config]
   - Raises ConfigurationError if java_bridge is None and any {{java}} marker present
   - Raises ConfigurationError on missing/invalid keys
   ↓
_resolve_expressions()                              [map_component.py override]
   - Only resolves context vars in scalar fields (die_on_error, label, etc.)
   - Skips parent's _resolve_java_expressions (row-level markers handled per-row)
   ↓
_select_mode() → BATCH                              [override, always BATCH]
   ↓
_process(input_data)                                [map_component.py]
   ↓
   ├─ parse_inputs(input_data) → {flow_name: DataFrame}
   │
   ├─ apply_main_filter(main_df, main_cfg)          [map_joins.apply_filter]
   │     - If filter has {{java}}, ONE bridge call via execute_tmap_preprocessing
   │       evaluating the filter expression across all main rows in batch (returns one
   │       boolean per row). Apply the mask. Not per-row bridge calls.
   │     - Returns filtered main_df
   │
   ├─ joined_df = main_df.copy()
   ├─ inner_join_reject_dfs: dict[lookup_name, DataFrame] = {}
   ├─ joined_lookup_names: list[str] = []
   │
   ├─ for lookup_cfg in lookups:                    [map_joins.execute_lookup_join]
   │     ├─ strategy = classify_join_strategy(lookup_cfg)
   │     │     - SIMPLE         if all join_keys are plain column refs
   │     │     - COMPUTED       if any join_key has an expression
   │     │     - FILTER_AS_MATCH if no join_keys but lookup has filter
   │     │     - RELOAD         if lookup_mode == RELOAD_AT_EACH_ROW (overrides above)
   │     ├─ joined_df, rejects = dispatch_to_strategy(strategy, ...)
   │     ├─ if rejects: inner_join_reject_dfs[lookup_cfg.name] = rejects
   │     └─ joined_lookup_names.append(lookup_cfg.name)
   │
   ├─ if joined_df.empty:
   │     return create_empty_outputs() with inner_join_rejects routed
   │
   ├─ joined_schema = compute_joined_df_schema(    [map_joins.compute_joined_df_schema]
   │     main_schema, consumed_lookups, variables, temp_join_key_cols)
   │     - Single source of truth for joined_df column types (Section 9)
   │     - Used by all subsequent bridge calls for Arrow serialization
   │     - Validates: every joined_df column has a declared type; raises ConfigurationError otherwise
   │
   ├─ active_script = build_active_script(config)   [map_compiled_script.build_active]
   │
   ├─ push_runtime_state_to_bridge(self, java_bridge)  [map_bridge_sync.push]
   │     - Writes typed context + globalMap to bridge dicts
   │
   ├─ active_raw_result = compile_and_execute(active_script, joined_df, chunk_size)
   │     - Returns {output_name: DataFrame} + "__errors__" DataFrame if die_on_error=false
   │
   ├─ reject_raw_result: dict = {}
   ├─ if has_inner_join_reject_outputs(config) and inner_join_reject_dfs:
   │     ├─ reject_source = build_reject_row_source(inner_join_reject_dfs, joined_df.columns)
   │     ├─ reject_script = build_reject_script(config)
   │     ├─ push_runtime_state_to_bridge(self, java_bridge)      # refresh after active pass
   │     └─ reject_raw_result = compile_and_execute(reject_script, reject_source, chunk_size)
   │
   └─ result = route_rejects(                       [map_reject_routing.route]
            active_raw_result,
            reject_raw_result,
            errors_df=active_raw_result.get("__errors__"),
            inner_join_reject_dfs=inner_join_reject_dfs,
            config=config,
       )
   ↓
return {output_name: DataFrame}                     [consumed by BaseComponent template
                                                     which then runs schema validation
                                                     and stat updates]
```

### Bridge call count

| Job shape | Compile calls | Execute calls |
|---|---|---|
| Simple (active outputs only) | 1 | 1 |
| With is_reject (output filter reject) | 1 | 1 (handled inline) |
| With catch_output_reject (expression errors) | 1 | 1 (handled inline via __errors__) |
| With inner_join_reject | 2 (active + reject scripts) | 2 |
| All three reject types | 2 | 2 |

Both scripts cached per `component_id` for re-execution (existing bridge cache).

---

## 6. Join Strategy Classification

```
classify_join_strategy(lookup_cfg) -> JoinStrategy:
    if lookup_cfg.lookup_mode == RELOAD_AT_EACH_ROW:
        return RELOAD

    join_keys = lookup_cfg.join_keys

    if not join_keys:
        if lookup_cfg.activate_filter and lookup_cfg.filter:
            return FILTER_AS_MATCH
        else:
            # Pure cartesian join (no keys, no filter) — rare but valid in Talend
            return FILTER_AS_MATCH  # treated as filter_expr=None cross-product

    # join_keys non-empty:
    if all(is_simple_column_ref(strip_marker(jk.expression)) for jk in join_keys):
        return SIMPLE
    else:
        return COMPUTED
```

### Strategy semantics

**SIMPLE** — pandas merge directly. Left keys = the column names from `jk.expression` (stripped of `{{java}}`). Right keys = `lookup_cfg.lookup_column`. Apply matching mode dedup to lookup first. O(n+m).

**COMPUTED** — batch-eval all `jk.expression` values via `execute_tmap_preprocessing(joined_df, expressions, ...)` ONCE; results become temporary columns on joined_df; then pandas merge with temp columns as left keys. Drop temp columns from result. O(n+m).

**FILTER_AS_MATCH** — chunked cross-product:
- Size guard: if joined_df rows × lookup rows ≥ 100M → raise ComponentExecutionError; ≥ 10M → log WARNING (preserves current `_check_size_guard` thresholds)
- For each chunk of joined_df (chunk size auto-tuned by row memory):
  - Cross-product chunk × full lookup → cross_chunk DataFrame
  - If `lookup_cfg.filter` set: ONE bridge call evaluating the filter expression across the entire cross_chunk in batch (returns one boolean per cross_chunk row); apply mask
  - If no filter (pure cartesian): keep all
- Concat surviving chunks
- O(n*m) total work, but memory-bounded by chunk and call-bounded to (n_chunks) bridge calls — not per-row

**RELOAD** — for each main row:
- If lookup_cfg.filter set: substitute main row values into filter expression, bridge-eval against full lookup, get matching subset
- Apply matching mode dedup
- For each candidate lookup row, evaluate join keys (simple equality assumed for RELOAD), find matches
- Combine main_row + matched_lookup_row (or NaN-padded for LEFT_OUTER unmatched)
- O(n*m); intentional — RELOAD is "row-by-row" by definition

### Inner-join reject handling per strategy

| Strategy | Reject collection |
|---|---|
| SIMPLE | pandas merge with `indicator=True`; rows with `_merge == 'left_only'` go to rejects (when join_mode = INNER_JOIN) |
| COMPUTED | Same as SIMPLE after the temp-key merge |
| FILTER_AS_MATCH | After cross-product survive, find main rows that survived at least once; the rest are rejects (when INNER_JOIN) |
| RELOAD | Tracked directly in the per-row loop; rejects are main rows where no candidate matched |

---

## 7. Compiled Script Structure

### Active script (always generated)

```groovy
import java.util.*;
import com.citi.gru.etl.RowWrapper;

// === Output buffers ===
Object[][] out1_data = new Object[rowCount][N1]
int out1_count = 0
// ... per active output ...
Object[][] reject_is_reject_data = new Object[rowCount][M]  // if any is_reject outputs
int reject_is_reject_count = 0

// Error tracking (only when die_on_error=false OR any catch_output_reject)
int errorCount = 0
Map<Integer, String> errorMap = new HashMap<>()
Map<Integer, String> stackTraceMap = new HashMap<>()  // NEW: real stack traces

// === Per-row loop (sequential or parallel — see Section 9) ===
for (int i = 0; i < rowCount; i++) {
    try {
        // Build row wrappers
        RowWrapper row1 = buildRowWrapper(inputRoot, i, "row1")
        RowWrapper row2 = buildRowWrapper(inputRoot, i, "row2")
        // ... per lookup ...

        // Inner try-catch for variables + outputs (only when die_on_error=false OR catch present)
        try {
            // Variables (sequential — later vars see earlier ones via Var.get)
            Map<String, Object> Var = new HashMap<>()
            Var.put("var1", <expr>)
            Var.put("var2", <expr referencing Var.var1 via Var.get("var1")>)
            // ...

            // Track whether row matched any active output (for is_reject routing)
            boolean matchedAny = false

            // For each ACTIVE (non-reject) output:
            //   Apply filter if present (return early if filtered)
            //   Pre-evaluate all column expressions into tempRow (atomic)
            //   Commit tempRow to output_data; set matchedAny = true
            {
                Object[] out1_tempRow = new Object[N1]
                if (<filter>) {
                    out1_tempRow[0] = <col0_expr>
                    out1_tempRow[1] = <col1_expr>
                    // ...
                    out1_data[out1_count++] = out1_tempRow
                    matchedAny = true
                }
            }

            // For each is_reject output: route filtered-out rows
            if (!matchedAny) {
                Object[] rej_tempRow = new Object[M]
                rej_tempRow[0] = <col0_expr>
                // ...
                reject_is_reject_data[reject_is_reject_count++] = rej_tempRow
            }
        } catch (Exception innerE) {
            String msg = innerE.getMessage() != null ? innerE.getMessage() : innerE.toString()
            // Capture stack trace as string (NEW — fixes empty errorStackTrace)
            java.io.StringWriter sw = new java.io.StringWriter()
            innerE.printStackTrace(new java.io.PrintWriter(sw))
            errorCount++
            errorMap.put(i, msg)
            stackTraceMap.put(i, sw.toString())
            // Row will route to catch_output_reject via __errors__ Arrow batch
        }
    } catch (Exception outerE) {
        // Hard failure at row-wrapper construction; propagate
        throw new RuntimeException("Error at row " + i + ": " + outerE.getMessage(), outerE)
    }
}

// === Return results map ===
Map<String, Map<String, Object>> results = new HashMap<>()
// Per active output: results.put(name, [data, count])
// Per is_reject output: results.put(name, [data, count])
// __errors__ emission (only when error tracking present):
Map<String, Object> errorInfo = new HashMap<>()
errorInfo.put("count", errorCount)
errorInfo.put("indices", new ArrayList<>(errorMap.keySet()))
errorInfo.put("messages", errorMap)
errorInfo.put("stackTraces", stackTraceMap)   // NEW: real stack traces, not empty strings
results.put("__errors__", errorInfo)

return results
```

### Reject script (only when inner_join_reject outputs configured)

Strictly smaller — no variables, no filters, no try/catch, no error map. Just:
- Per row of reject_source: build row wrappers, pre-evaluate columns for each inner_join_reject output, commit.
- Returns `{reject_output_name: [data, count]}`.

### Parallelism

**Sequential `for` loop** (not `IntStream.parallel().forEach()`):
- The variable evaluation chain (`Var.var2 = Var.var1 + ...`) is sequentially dependent within a row, but rows are independent.
- Parallelism would speed up large jobs but: Variables map is per-row (no race), output_data writes use AtomicInteger (no race), error map uses ConcurrentHashMap.
- **Decision: start sequential. Add parallel as a config flag (`parallel_execution`, default false) only if profiling shows it's needed.** The current code has parallel by default and it has caused subtle issues. Simpler-first.

---

## 8. Error Handling

### Three error layers

**Layer 1 — Configuration errors (job won't start)**
- Raised by `_validate_config` in `map_config.py`
- Examples: missing `inputs.main`, no outputs configured, `{{java}}` markers present but bridge unavailable
- Raises `ConfigurationError`; engine marks tMap as failed; job dies

**Layer 2 — Bridge errors (job died, no rows produced)**
- Raised by Java bridge during `compile_tmap_script` or `execute_compiled_tmap_chunked`
- Examples: Groovy compilation error (bad expression), JVM crash, Py4J connection lost
- Raises `ComponentExecutionError` (wrapped via existing `_call_java_with_sync`)
- Includes Java stderr in error message (existing behavior, kept)

**Layer 3 — Expression errors at row evaluation (per-row outcome)**
- Caught inside the active Groovy script
- Two sub-cases:
  - **die_on_error=true (default):** the script rethrows; the row's execution propagates an exception up; bridge call fails with `ComponentExecutionError`. Same blast radius as Layer 2.
  - **die_on_error=false:** caught in inner try/catch; row index + message + stack trace stored in errorMap/stackTraceMap; row routes to `catch_output_reject` outputs via the `__errors__` Arrow batch
- In both cases, schema validation (Layer 4) still applies to whatever rows did make it through

**Layer 4 — Schema validation (after _process)**
- Unchanged from current `BaseComponent._apply_output_schema_validation`
- die_on_error=true → raises DataValidationError on schema violations
- die_on_error=false → routes schema violators to the engine's reject mechanism (with `errorCode="SCHEMA_VIOLATION"`)

### Reject routing matrix

| Reject type | Trigger | Populated by | Routed by |
|---|---|---|---|
| `is_reject` | Output filter rejected the row | Active script (inline) | `map_reject_routing` passes through; columns evaluated in-script via atomic-row commit |
| `inner_join_reject` | INNER_JOIN lookup found no match | `map_joins` (per lookup, accumulated in `inner_join_reject_dfs`) | `map_reject_routing` builds `reject_source`, calls reject_script bridge, merges into final dict |
| `catch_output_reject` | Expression in active script threw | Active script via errorMap → `__errors__` Arrow | `map_reject_routing` reads `__errors__` DataFrame, joins back to joined_df by rowIndex, evaluates user catch column expressions, fills framework cols if mapped |

### Reserved column policy (D-06)

If a `catch_output_reject` output declares columns named `errorMessage` or `errorStackTrace`:
- Framework value WINS — `map_reject_routing` overwrites whatever the user expression evaluated to
- This matches Talaxie tMap_main.javajet L1925-1988 behavior

If those columns are NOT declared, the framework does not add them. The output frame contains only user-declared columns.

---

## 9. Java Bridge, Java-side Changes & Type Fidelity

### Principle: explicit types end-to-end across the Python/Java boundary

Three classes of state cross the boundary between Python and Java in a tMap execution:

1. **Context variables** (`bridge.context[key] = value`)
2. **globalMap entries** (`bridge.global_map[key] = value`)
3. **Row data** (DataFrames via Arrow IPC bytes — input frame, output frames, `__errors__` frame)

For all three, the **declared type is the source of truth.** No inference at the boundary, no string-coercion, no silent defaults.

### `src/v1/java_bridge/bridge.py` (Python client)

| Function | Change |
|---|---|
| `set_context(key, value)` | **Drop the `str(value)` coercion** at L859. Pass `value` as-is. (`fix_source_no_fallbacks`) |
| `set_global_map(key, value)` | Same. Drop str-coercion at L870. |
| `_sync_from_java()` | Unchanged. Already correct (reads `getContext()` / `getGlobalMap()` back into Python dicts) |
| `DatetimeConverter` / `DateConverter` | Unchanged. Already correct — the Py4J registration works |
| `execute_compiled_tmap_chunked` | Unchanged signature. The `__rejectMode__` flag wrap can be REMOVED (rewrite uses two separate compiled scripts instead of one with flag dispatch) |
| `_arrow_bytes_to_df` decimal-null-to-empty-string | **Revisit:** the current `""` substitution for Decimal nulls is questionable. Either keep with documented rationale or use `pd.NA`. Decided during implementation. |

### `src/v1/java_bridge/java/.../JavaBridge.java`

| Method | Change |
|---|---|
| `setContext(String key, String value)` | **Change signature to `(String key, Object value)`.** Drop String typing; accept any type. |
| `setGlobalMap(String key, String value)` | Same change. |
| `convertTMapOutputsToArrow` `__errors__` branch (L854-903) | **Populate `errorStackTrace` from real Throwable stack traces.** The current code emits the column with `""` because the Groovy script doesn't emit `stackTraces`. The new active script (Section 7) DOES emit `stackTraces` map. Java-side just reads it and serializes. |
| `executeCompiledTMap` / `executeCompiledTMapChunked` | Unchanged. The dual-invocation `__rejectMode__` dispatch is gone — Python side calls the appropriate script directly. |
| Other methods | Unchanged |

### `src/v1/engine/context_manager.py`

| Change | Reason |
|---|---|
| `_TYPE_CONVERTERS["id_Date"] = str` (L63) | **Change to `_TYPE_CONVERTERS["id_Date"] = _parse_talend_date`** (a new helper that returns `datetime.date` or `datetime.datetime` based on the value's format). Currently str-coerces dates and breaks every downstream type-aware path. |
| `_TYPE_CONVERTERS["id_BigDecimal"] = Decimal` | Unchanged (already correct) |
| `_TYPE_CONVERTERS["id_Float"]` vs `["id_Double"]` | Both stay as `float` (Python has no float32). Type fidelity to Java is the bridge's responsibility via `gateway.jvm.java.lang.Float(v)` wrapping in `map_bridge_sync.py`. |

### Data column type fidelity (rules)

Every column of every DataFrame that crosses the Python/Java boundary in a tMap execution carries an **explicitly declared type**. The type is sourced from:

| Column source | Type source |
|---|---|
| Main input columns | `schema_inputs_map[main_name]` (set by engine init from converter JSON) |
| Lookup input columns | `schema_inputs_map[lookup_name]` (per lookup) |
| Variable columns (`Var.*`) | `variable_cfg.type` from JSON config |
| Computed join-key temp columns (`__jk_*__`) | `join_key.type` from JSON config |
| Output columns | `output_cfg.columns[i].type` from JSON config |
| `__errors__` framework columns | Fixed: `rowIndex: int`, `errorMessage: str`, `errorStackTrace: str` |

**Computed schema for joined_df** is built by `map_joins.py` after all lookups process. Helper signature:

```python
def compute_joined_df_schema(
    main_schema: list[ColumnDef],
    consumed_lookups: list[tuple[str, list[ColumnDef]]],  # (name, schema) per joined lookup
    variables: list[VariableCfg],
    temp_join_key_cols: dict[str, str],  # temp_col_name -> type
) -> dict[str, str]
```

Returns `{col_name: type_str}` covering EVERY column expected in joined_df. Called once per `_process()` after all lookups join.

**Type→pyarrow mapping (used by `bridge.py:_df_to_arrow_bytes`):**

| Type string | pyarrow type | Java target |
|---|---|---|
| `"str"` | `pa.string()` | `java.lang.String` |
| `"int"` (int32) | `pa.int32()` | `java.lang.Integer` (`id_Integer`) |
| `"int"` (int64) | `pa.int64()` | `java.lang.Long` (`id_Long`) |
| `"float"` (float32) | `pa.float32()` | `java.lang.Float` (`id_Float`) |
| `"float"` (float64) | `pa.float64()` | `java.lang.Double` (`id_Double`) |
| `"bool"` | `pa.bool_()` | `java.lang.Boolean` |
| `"datetime"` | `pa.timestamp("ns")` | `java.util.Date` |
| `"Decimal"` | `pa.decimal128(precision, scale)` | `java.math.BigDecimal` |

Precision/scale for Decimal come from `column.precision` in the schema. Already supported via `bridge.py:build_arrow_schema` and `extract_precision_map` — kept as-is.

**Type-fidelity rules enforced in `bridge.py`:**

1. **Remove `_infer_schema_dict`** (`bridge.py:1122`) from the tMap call paths. It's a fallback that defaults to `"str"` for unrecognized dtypes. Callers MUST pass an explicit `schema` dict. (Function may remain for non-tMap callers if needed, but is not called from `execute_compiled_tmap_chunked` / `execute_tmap_preprocessing` paths.)

2. **Tighten `_reconcile_schema_to_df`** (`bridge.py:1043`) to **raise `ConfigurationError`** when a DataFrame column is missing from the schema. The current behavior — WARN and default to `"str"` — masks bugs (a column got into joined_df without a declared type means something upstream is wrong; we want to know).

3. **Remove `_infer_arrow_schema_dict` from map.py** (`map.py:155`). The new `map_joins.compute_joined_df_schema()` is the only producer. No sampling of object-dtype cells to guess types.

4. **int32 vs int64 distinction:** when type is `"int"`, the converter's source `id_Integer` (32-bit) vs `id_Long` (64-bit) must be carried as part of the type. Either widen the type strings (`"int32"`, `"int64"`) or add a parallel `column.subtype` field. Decided during implementation (see Open Q #6 below).

5. **float32 vs float64 distinction:** same story for `id_Float` vs `id_Double`. Same resolution.

### Java bridge JAR rebuild

After Java-side edits: `cd src/v1/java_bridge/java && mvn package` — required for the bug fixes to take effect at runtime. JAR is gitignored per Phase 13 convention; rebuild is part of the implementation plan acceptance check.

---

## 10. Migration & Rollback

### Backup of current code

Before any new file is written:
1. Rename `src/v1/engine/components/transform/map.py` → `src/v1/engine/components/transform/map_legacy.py`
2. The file stays in the repo (not gitignored). It remains importable as `from src.v1.engine.components.transform.map_legacy import Map as LegacyMap` for the diff harness (Section 12) and for emergency rollback.
3. After the rewrite is validated and merged, `map_legacy.py` can be deleted in a follow-up cleanup PR.

### Rollback path

If the rewrite fails in production:
1. Delete the `src/v1/engine/components/transform/map/` folder
2. Rename `map_legacy.py` back to `map.py`
3. `COMPONENT_REGISTRY` import path is `from .components.transform.map import Map` — same name resolves to either file
4. Single import swap; no JSON config changes needed

### Java-side rollback

If Java changes break the bridge:
- Revert `JavaBridge.java` to the previous commit
- Run `mvn package` to rebuild
- Python side (`bridge.py`) requires the matching JAR. No `try/except` API-detection fallback in `bridge.py` — that would be a defensive layer hiding misconfiguration (violates `fix_source_no_fallbacks`). Deployment process must rebuild the JAR whenever Python bridge code changes, and vice versa. If JAR and Python are out of sync, the bridge raises a clear error at startup.

---

## 11. JSON Config Contract (non-negotiable)

The rewrite consumes the exact JSON shape the converter currently emits. Verified shape from `tests/fixtures/jobs/transform/map_with_lookup.json` + `tests/talend_xml_samples/converted_jsons/Job_tMap_0.1.json`:

```json
{
  "component_type": "Map",
  "inputs": {
    "main": {
      "name": "row1",
      "filter": "",
      "activate_filter": false,
      "matching_mode": "UNIQUE_MATCH",
      "lookup_mode": "LOAD_ONCE"
    },
    "lookups": [{
      "name": "row2",
      "matching_mode": "UNIQUE_MATCH",
      "lookup_mode": "LOAD_ONCE",
      "filter": "",
      "activate_filter": false,
      "join_keys": [{
        "lookup_column": "key",
        "expression": "{{java}}row1.key",
        "type": "str",
        "nullable": true,
        "operator": "="
      }],
      "join_mode": "LEFT_OUTER_JOIN"
    }]
  },
  "variables": [{
    "name": "var1",
    "expression": "{{java}}row1.salary.toString()",
    "type": "str",
    "nullable": true
  }],
  "outputs": [{
    "name": "out_main",
    "is_reject": false,
    "inner_join_reject": false,
    "catch_output_reject": false,
    "filter": "",
    "activate_filter": false,
    "columns": [
      { "name": "id", "expression": "{{java}}row1.id", "type": "int", "nullable": true }
    ]
  }],
  "die_on_error": true,
  "rows_buffer_size": "2000000",
  "change_hash_and_equals_for_bigdecimal": true,
  "enable_auto_convert_type": false,
  "tstatcatcher_stats": false,
  "label": ""
}
```

Plus instance attributes set by `engine.py` during component init (continued):
- `self.schema_inputs_map` ← `component["schema"]["inputs"]` (per-flow input schemas, dict keyed by flow name)
- `self.output_schema` ← `component["schema"]["output"]`
- `self.reject_schema` ← derived schema when any reject output present

**Acceptance test for this constraint:** every JSON in `tests/fixtures/jobs/transform/` (05_3/*.json, 05_4/*.json, map_with_lookup.json, join_with_reject.json, plus converted/Job_tMap_0.1.json) must run through the new `Map` class **without modification**.

**Type declarations are non-negotiable parts of the contract.** Every `column` object in the JSON has a `type` field. Every `join_key` has a `type`. Every `variable` has a `type`. The rewrite treats those fields as authoritative — never infers, never falls back. If the converter ever emits a config with a missing type, that's a converter bug to fix at source (it's well-defined today; the converter always emits a type). See Section 9 for how those types flow through to the Java boundary.

---

## 12. Testing Strategy

### TDD: red → green → refactor per module

Each new module is built with tests first. The development sequence:

1. Write a failing test for one module's responsibility
2. Write the minimum code to pass
3. Refactor for clarity
4. Move to the next test

### Test corpus

**Reuse existing 17 test files** (no rename of test files, just update imports to new module paths):
- `tests/v1/engine/components/transform/test_map.py`
- `tests/v1/engine/components/transform/test_map_bridge.py`
- `tests/v1/engine/components/transform/test_map_05_3_e2e.py`
- `tests/v1/engine/components/transform/test_map_05_3_perf.py`
- `tests/v1/engine/components/transform/test_map_05_4_e2e.py`
- `tests/v1/engine/components/transform/test_map_groovy_safety.py`
- `tests/v1/engine/components/transform/test_map_integration.py`
- `tests/v1/engine/components/transform/test_map_method_size.py`
- `tests/v1/engine/components/transform/test_map_reject_inner_join.py`
- `tests/v1/engine/components/transform/test_map_reject_catch.py`
- `tests/v1/engine/components/transform/test_map_reject_filter.py`
- ... and the converter-side test files (unchanged)

These become the regression contract — the new code must pass all of them.

**Add new test files** per new module:
- `tests/v1/engine/components/transform/map/test_map_config.py`
- `tests/v1/engine/components/transform/map/test_map_joins.py`
- `tests/v1/engine/components/transform/map/test_map_compiled_script.py`
- `tests/v1/engine/components/transform/map/test_map_reject_routing.py`
- `tests/v1/engine/components/transform/map/test_map_bridge_sync.py`

Each new test file covers its module in isolation (e.g. `map_compiled_script.py` tests can run with no JVM since the module is pure — just `assert build_active_script(config) == expected_groovy_source`).

### Add NEW tests for the bugs the rewrite fixes

| Bug fixed | New test |
|---|---|
| id_Date in context loses type fidelity | `test_map_bridge.py::TestContextTypeFidelity::test_date_context_round_trips_as_java_date` |
| id_Float vs id_Double indistinguishable | `test_map_bridge.py::TestContextTypeFidelity::test_float_arrives_as_java_float` |
| `errorStackTrace` column always empty | `test_map_reject_catch.py::TestCatchOutputReject::test_error_stack_trace_populated` |
| Filter-reject compiled-path (4 retained xfails from 05.5) | `test_map_reject_filter.py::TestFilterRejectCompiled::*` — promote 4 xfails to active |
| `set_context` str-coercion | `test_bridge.py::TestSetContextTypeFidelity::test_*` (a few cells exercising every type) |

### Diff harness

A new script `scripts/diff_map_outputs.py`:
- Loads every JSON in `tests/fixtures/jobs/transform/` and any synthetic test cases
- Runs each through both `Map` (new) and `LegacyMap` (old, via `map_legacy.py`)
- Asserts output DataFrames are equal column-by-column, value-by-value, with appropriate tolerance for float comparisons
- Run as part of CI before merge; run manually before manager handover

### Coverage gate

- Each new module ≥95% per-module line coverage (Phase 14 floor)
- Run via the standard Phase 14 gate command from CLAUDE.md
- `map_legacy.py` excluded from coverage measurement (add to `pyproject.toml` omit list)

---

## 13. Acceptance Criteria

The rewrite is "done" when:

- [ ] All 7 new files exist with the responsibilities described in Section 4
- [ ] Old `map.py` renamed to `map_legacy.py`, still importable
- [ ] `COMPONENT_REGISTRY.register("Map", "tMap")` resolves to the new `Map` class
- [ ] All 17 existing test files pass against the new code (with updated import paths)
- [ ] All 7 new module-level test files pass
- [ ] The 5 new bug-fix tests pass
- [ ] The 4 retained xfails from Phase 05.5-08 are promoted to active and pass
- [ ] Diff harness passes for every fixture in `tests/fixtures/jobs/transform/`
- [ ] Phase 14 coverage gate passes (each new module ≥95% line coverage)
- [ ] `bridge.py` and `JavaBridge.java` changes applied (str-coercion dropped, Object signatures, real stack traces)
- [ ] `mvn package` rebuilt JAR exists at `src/v1/java_bridge/java/target/java-bridge-with-dependencies.jar`
- [ ] No emojis / unicode in any new log line
- [ ] No defensive fallbacks introduced (e.g. no `rowIndex` bounds-clamp; either Arrow corruption is impossible by construction OR it raises)
- [ ] Size guard preserved: FILTER_AS_MATCH cross-product warns at 10M rows, fails at 100M (matches current `_check_size_guard` thresholds)
- [ ] **Type fidelity end-to-end:** no schema inference in any tMap data-crossing path. `_infer_schema_dict` not called from tMap paths; `_infer_arrow_schema_dict` removed from `map.py`. `compute_joined_df_schema` is the single producer of joined_df column types.
- [ ] **Bridge schema validation strict:** `_reconcile_schema_to_df` raises `ConfigurationError` when a DataFrame column lacks a declared type (no WARN + default-to-str).
- [ ] **Type round-trip tests pass:** for each Talend type in scope (id_String, id_Integer, id_Long, id_Float, id_Double, id_Boolean, id_Date, id_BigDecimal), a row data column AND a context variable AND a globalMap entry of that type all arrive in Groovy as the correct Java type (verified via `instanceof` assertions in test Groovy expressions).
- [ ] CLAUDE.md updated if any new constraint emerges during implementation

---

## 14. Known Follow-Ups (NOT in this rewrite)

These are explicitly OUT OF SCOPE and tracked for future work:

- PyMap and FilterRows rewrites (same architectural bugs but separate components)
- BaseComponent's `_resolve_java_expressions` still uses `set_context` setter — once the setter is fixed at source (this rewrite), it inherits the fix
- Disk-spilling lookups for huge lookup tables (CACHE_OR_RELOAD / ROWS_BUFFER_SIZE) — defer until production needs it
- Fuzzy match join (LEVENSHTEIN / JACCARD) — defer until production needs it
- LKUP_PARALLELIZE — defer until production needs it
- `change_hash_and_equals_for_bigdecimal` — defer until a real Talend job uses BigDecimal join keys
- Performance profiling pass (parallel forEach vs sequential, chunk size tuning) — measure first, then optimize

---

## 15. Open Questions for Implementation

These are HOW questions (not WHAT) and will be answered during the implementation plan:

1. **Parallelism in active script:** start sequential for safety; add `parallel_execution` config flag if profiling shows it's needed. Default false.
2. **Chunk size auto-tuning:** the current code has `_compute_cross_chunk_size`; should the rewrite preserve that heuristic or use a fixed default?
3. **Decimal-null serialization:** the current `_arrow_bytes_to_df` substitutes empty string `""` for Decimal nulls. Either keep with explicit rationale or switch to `pd.NA` and trust downstream consumers.
4. **`reset()` for iterate re-execution:** the new Map class needs to be safe for re-execution under tIterate components. Verify that all per-call state is built fresh in `_process`.
5. **Custom routine class binding:** `addRoutinesToBinding` in Java is shared across all bridge methods. The rewrite inherits it. Confirm during implementation that loaded routines remain available across both the active and reject scripts.

6. **int32/int64 and float32/float64 distinction in type strings:** the engine's current 7-canonical-type vocabulary (`str / int / float / bool / datetime / Decimal / object`) loses Talend's `id_Integer` vs `id_Long` and `id_Float` vs `id_Double` distinction. Section 9 requires this distinction be preserved at the Java boundary. Two implementation options:
   - **(a) Widen type strings:** `"int32" / "int64" / "float32" / "float64"` alongside the others. Touches `_TYPE_MAPPING` and pyarrow type builders. Cleanest but expands the vocabulary across the codebase.
   - **(b) Parallel subtype field:** keep `"int" / "float"` as-is, add `column.subtype` (`"int32" / "int64" / ...`) consulted only at bridge crossings. Localised change, less codebase impact.
   - Decided during implementation; pick (b) if the wider type strings would require touching too many call sites outside tMap; pick (a) if the codebase is small enough to refactor cleanly.
