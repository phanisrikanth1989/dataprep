# Pitfalls Research

**Domain:** Talend ETL Migration Engine (Python/Py4J)
**Researched:** 2026-04-14
**Confidence:** HIGH (most findings verified against codebase + official docs + community sources)

## Critical Pitfalls

### Pitfall 1: Py4J Compiled Script Synchronization Bottleneck

**What goes wrong:**
The Java bridge executes Groovy scripts using `IntStream.range(0, rowCount).parallel().forEach()` for row processing, but the compiled script is shared and accessed through `synchronized(compiledScript)` (JavaBridge.java lines 138-141). This serializes all "parallel" row processing into effectively single-threaded execution while paying the overhead of thread coordination. Worse, under heavy load with many concurrent tMap/tJavaRow calls, the single compiled script becomes a contention point that can cause thread starvation and timeouts in the Py4J communication layer.

**Why it happens:**
Groovy's `Script` object is not thread-safe -- it holds mutable binding state. The developer chose `synchronized` as a quick fix for parallel execution, but this eliminates the parallelism benefit entirely. The real danger is that this bottleneck is invisible during small-scale testing and only manifests with production-scale data or when multiple components share the same bridge.

**How to avoid:**
- Per-thread script instances: clone or re-parse the script per thread (Groovy compilation is fast -- the 180x rows/sec benchmark in comments already accounts for compilation overhead).
- Use the compile-once/execute-many pattern (already partially implemented via `compiledScripts` cache in `CompiledTMapScript`) but ensure each thread gets its own Script instance with independent Binding.
- For tJavaRow, compile once outside the parallel loop and create per-thread copies.

**Warning signs:**
- tMap or tJavaRow components that process 100K+ rows take disproportionately longer than expected.
- JVM thread dumps showing many threads blocked on `synchronized(compiledScript)`.
- Py4J `Py4JNetworkError` timeouts during long-running expression evaluations.

**Phase to address:**
Java Bridge reliability phase. Fix before scaling to production workloads.

---

### Pitfall 2: Py4J Context/GlobalMap Synchronization Drift

**What goes wrong:**
The `JavaBridge` class maintains its own `self.context` and `self.global_map` Python dicts (bridge.py lines 24-25) that are separate from the engine's `ContextManager` and `GlobalMap`. Synchronization happens only at specific call points: `_resolve_java_expressions()` in `BaseComponent` syncs Python-to-Java before expression evaluation (base_component.py lines 133-144), and `_sync_from_java()` syncs Java-to-Python after `executeJavaRow` (bridge.py line 590). But critically:

1. `execute_tmap_compiled()` and `execute_compiled_tmap_chunked()` never call `_sync_from_java()` -- any globalMap changes made during tMap Java execution are lost.
2. `execute_batch_one_time_expressions()` never syncs back -- context changes made by one-time expressions are lost.
3. The `context` dict and `global_map` dict on the bridge accumulate stale values from previous component executions because they use `putAll()` / `update()` without clearing first.
4. During iterate loops, the bridge's context is never reset between iterations, so iteration N's globalMap variables leak into iteration N+1's Java execution.

**Why it happens:**
The bridge was designed as a stateless expression evaluator but evolved into a stateful context holder. Each new execution path (tMap compiled, batch expressions, chunked processing) was added without the sync discipline of the original `executeJavaRow` path.

**How to avoid:**
- Implement a single `_sync_context_to_java()` method called before EVERY Java bridge invocation, not just in `_resolve_java_expressions()`.
- Implement a single `_sync_from_java()` call after EVERY bridge method that could modify context/globalMap.
- Clear stale values before sync: `self.context.clear(); self.context.update(current_context)` instead of `self.context.update()`.
- Add a `reset_iteration_state()` method to the bridge called at iteration boundaries.

**Warning signs:**
- Context variables have unexpected values in components that execute after tMap or tJava components.
- GlobalMap statistics from one component appear in a subsequent component's Java execution context.
- Iterate loops produce incorrect results on the 2nd+ iteration but work correctly on the 1st.
- Job results differ when components are reordered (execution-order dependency on shared mutable state).

**Phase to address:**
Engine core infrastructure phase -- must be fixed before any component work, as every Java-using component depends on correct sync.

---

### Pitfall 3: Talend Null Semantics Divergence in Pandas Joins

**What goes wrong:**
Talend's join semantics specify that NULL does not match NULL in join keys (matching SQL behavior). However, pandas `merge()` treats NaN as a valid join key by default -- `NaN == NaN` produces a match. This means any tMap join where the join key column contains null/NaN values will produce spurious matches that Talend would not produce. For 1200+ migrated jobs, even a small percentage with null join keys will produce silently incorrect output.

Additionally, Talend's tMap supports only LEFT OUTER JOIN and INNER JOIN (not FULL OUTER JOIN). The engine's `_perform_lookups()` method (map.py line 480) checks `join_mode` and attempts inner join reject tracking, but the inner join reject detection uses a second `merge()` with `indicator=True` on the pre-join DataFrame -- this is fragile because column name collisions between main and lookup DataFrames cause `merge()` to fail silently or produce incorrect indicator values.

**Why it happens:**
Pandas was designed for data analysis, not ETL join semantics replication. The NaN-matches-NaN behavior is intentional in pandas. Developers who test with clean data (no nulls) never encounter this divergence.

**How to avoid:**
- For every `pd.merge()` call in the Map component, add sentinel value substitution: replace NaN in join key columns with a unique non-matching sentinel before merge, then restore NaN after.
- Alternatively, use `df.merge(...).pipe(lambda x: x[~(x[left_key].isna() & x[right_key].isna())])` to filter out null-null matches post-merge.
- For inner join reject detection, use `merge(indicator=True)` on the original merge call itself (not a separate call), and use `suffixes=` to prevent column name collisions.
- Build a test suite of Talend jobs with known null join keys and verify Python engine output matches Talend output exactly.

**Warning signs:**
- Row counts after joins are higher than expected (spurious null-null matches inflating results).
- Integration tests pass with clean test data but fail against production data containing nulls.
- Inner join reject counts differ from Talend's reject counts for the same job.

**Phase to address:**
tMap component hardening phase. This is a data correctness issue that must be validated with real production data.

---

### Pitfall 4: Iterate Loop State Leakage Across Iterations

**What goes wrong:**
The engine's iterate execution (engine.py `_execute_iterate_component()`, lines 622-764) re-executes downstream components per iteration by removing them from `self.executed_components` and re-running. However, several state leakage issues exist:

1. **Component internal state is not reset:** When a component like `FileOutputDelimited` runs in iteration 2, its `self.stats` still contains accumulated values from iteration 1. The `_update_stats()` method (base_component.py line 306) uses `+=`, so stats double-count.
2. **Data flows from previous iterations persist:** The cleanup loop (engine.py lines 709-717) only clears flows where `flow['from'] == executed_comp`. Flows from components NOT in the iteration set but consumed by iteration components are not cleared, potentially feeding stale data.
3. **Trigger manager state is partially cleared:** `self.trigger_manager.triggered_components.discard(executed_comp)` (line 711) clears the triggered set, but `self.trigger_manager.component_status` is not cleared. Components that check subjob status via `get_subjob_status()` may see stale "success" or "error" statuses from previous iterations.
4. **BaseComponent.config mutation:** The `resolve_dict()` call (base_component.py line 202) replaces `self.config` with resolved values. On the second iteration, context variables are already resolved, so `${context.var}` patterns are gone -- if context variables change between iterations (common with iterate patterns), the component uses iteration 1's resolved values.

**Why it happens:**
The iterate execution was bolted onto a single-execution engine design. Components were not designed for re-execution -- they assume `execute()` is called exactly once.

**How to avoid:**
- Add a `reset()` method to `BaseComponent` that clears stats, resets status to PENDING, and restores the original (unresolved) config. Store `self._original_config = copy.deepcopy(config)` in `__init__`.
- Clear all data flows for the iteration subjob at the start of each iteration, not just flows from executed components.
- Clear `component_status` in the trigger manager for all iteration components at the start of each iteration.
- Add an integration test that runs a 3-iteration job with changing context variables and verifies each iteration produces independent output.

**Warning signs:**
- Stats show NB_LINE values that are multiples of expected (e.g., 300 instead of 100 for a 3-iteration job).
- Output files from iterate loops contain data from previous iterations appended or mixed in.
- The second iteration of a loop produces different results than if the job ran with only that single iteration.
- Context-dependent file paths or filter expressions work on iteration 1 but use stale values on iteration 2+.

**Phase to address:**
Iterate support phase. Must be addressed before iterate components can be registered in the engine.

---

### Pitfall 5: GlobalMap.get() and _update_global_map() Crash Chain

**What goes wrong:**
Two bugs in the engine's core infrastructure create a crash chain that prevents ANY job from executing:

1. `GlobalMap.get()` (global_map.py line 28) references an undefined variable `default` -- every call raises `NameError`.
2. `_update_global_map()` (base_component.py line 304) references an undefined variable `value` in an f-string -- every component completion crashes.

These are documented P0 bugs in the cross-cutting issues report, but the pitfall extends beyond the bugs themselves: **because these crash on both the success AND error paths, they mask the real error**. When a component fails for a legitimate reason (bad data, missing file, etc.), the `_update_global_map()` crash replaces the original exception with a `NameError`, making debugging impossible.

**Why it happens:**
Zero engine-level tests exist. The engine has never been executed end-to-end in its current state. These are simple typos that any test would catch.

**How to avoid:**
- Fix both bugs immediately (5 minutes total).
- Add a "smoke test" that creates an engine with a minimal job config (one tRowGenerator + one tLogRow) and executes it. This single test would catch all import errors, GlobalMap errors, and _update_global_map errors.
- Establish a CI gate: no PR merges without the smoke test passing.

**Warning signs:**
- `NameError: name 'default' is not defined` in any globalMap access.
- `NameError: name 'value' is not defined` after any component execution.
- Real errors being masked by these NameErrors (you see the NameError instead of the actual problem).

**Phase to address:**
Phase 1 (engine core fixes). These are 2-minute fixes that unblock everything else.

---

### Pitfall 6: Context Variable Resolution Corrupts Java Code and File Paths

**What goes wrong:**
The `ContextManager.resolve_string()` method (context_manager.py lines 76-139) applies a bare `context.variable` regex pattern (`\bcontext\.(\w+)\b`) AFTER the `${context.variable}` pattern. This bare pattern matches:

1. Java code containing `context.getOutputDir()` -- replaces `context` with the context manager's value, corrupting the Java expression.
2. File paths like `/path/to/context.csv` -- replaces `context` with nothing (if no variable named "csv" exists) or with an unrelated value.
3. Log messages or comments containing the word "context."

The `resolve_dict()` method (context_manager.py lines 141-160) skips `java_code` and `imports` keys, but it does NOT skip:
- `python_code` keys -- Python component code containing `context.var` references is resolved prematurely, replacing valid Python attribute access with literal values.
- `filter` keys in tMap -- expressions like `row1.context_id > 0` where "context" appears as part of a column name could be corrupted.
- Nested config dicts -- only top-level key names are checked, so `{'settings': {'java_code': '...'}}` would NOT skip the inner java_code.

**Why it happens:**
The bare pattern was added as a convenience for users who write `context.var` instead of `${context.var}`, but it's too aggressive. The skip-list in `resolve_dict()` only covers top-level keys and only covers Java-specific keys.

**How to avoid:**
- Remove the bare `context.variable` pattern entirely. Require `${context.variable}` syntax everywhere. This is a breaking change but eliminates an entire class of bugs.
- If the bare pattern must stay, make it only match when `context.` appears at the start of the string or after whitespace/operators (not inside identifiers).
- Extend the skip-list to include `python_code`, `filter`, `expression`, and apply it recursively to nested dicts.
- Add `resolve_dict()` tests with Java code, Python code, file paths containing "context", and column names containing "context".

**Warning signs:**
- Java expressions fail with "variable not found" errors after context resolution.
- File operations fail on paths that contain the substring "context".
- Python component code produces unexpected results because variable references were replaced with literal values before execution.

**Phase to address:**
Engine core infrastructure phase. Must be fixed before component work because every component calls `resolve_dict()`.

---

### Pitfall 7: Arrow Serialization Type Mismatch Silent Data Corruption

**What goes wrong:**
The `_build_arrow_schema()` method (bridge.py lines 538-580) infers Arrow types by inspecting the first non-null value in each column. This creates several failure modes:

1. **Heterogeneous columns:** If the first non-null value is a string but subsequent values are Decimals (or vice versa), the entire column is serialized as the wrong type. Values that don't match the inferred type are silently coerced or corrupted during Arrow serialization.
2. **Empty columns after filtering:** After a tMap filter reduces a DataFrame, some columns may become all-null. The method falls back to `pa.string()` for these columns, which may not match the Java-side schema expectation.
3. **Decimal precision loss:** The `_infer_decimal_precision_scale()` method (lines 500-536) scans all values to find max precision/scale, but caps at (38, 18). If precision exceeds 38 (possible with very large BigDecimal values from Java), values are silently truncated.
4. **Date/datetime columns stored as object dtype:** When pandas reads dates as strings (common with CSV input), they have `object` dtype. The schema builder sees a string first value and creates a `pa.string()` field. Java code expecting a Date type receives a string, causing type cast failures.
5. **Boolean columns with null values:** pandas stores nullable booleans as `object` dtype. The first-value check may find a boolean, but subsequent null values in the Arrow column cause serialization issues.

**Why it happens:**
Arrow requires a homogeneous schema declaration upfront, but pandas DataFrames are dynamically typed per cell. The first-value inference is a heuristic that works for clean, uniform data but breaks on real-world ETL data with nulls, mixed types, and type coercion.

**How to avoid:**
- Use the output schema from the component config (Talend schema definitions specify exact types per column) to build the Arrow schema, rather than inferring from data.
- Add explicit type validation before Arrow serialization: check that all values in a column match the declared type, and coerce/reject mismatches.
- Add fallback handling for all-null columns: use the declared schema type, not a string default.
- Log a warning when inferred type differs from declared schema type.

**Warning signs:**
- `ArrowInvalid` exceptions during serialization mentioning type mismatches.
- Java bridge returning incorrect numeric values (precision loss, integer truncation).
- Components producing correct results with test data but incorrect results with production data containing nulls or mixed types.
- tMap expressions failing with ClassCastException on the Java side when they encounter unexpected types.

**Phase to address:**
Java Bridge reliability phase. Fix alongside Py4J bridge hardening.

---

### Pitfall 8: Execution Loop Stall on Unreachable Components

**What goes wrong:**
The engine's main execution loop (engine.py line 453) continues while `len(self.executed_components) < len(self.components)`. If any component is unreachable (no path from initial components through data flows or triggers), the loop stalls. The stall detection (lines 455-460) logs a warning and breaks, but this means the job reports "success" even though components were never executed. There is no distinction between "component skipped because trigger didn't fire" (legitimate) and "component unreachable due to misconfiguration" (error).

Additionally, the `_identify_subjobs()` method (lines 335-368) uses bidirectional graph traversal (`_find_connected_components`) -- it follows flows in both directions. This means a component with only an output flow to another component gets grouped into the same subjob, even if there's no logical dependency. This can cause subjob boundaries to be incorrect, making triggers fire at the wrong time.

**Why it happens:**
The engine was designed for well-formed jobs. Talend Studio prevents users from creating unreachable components through its GUI, but the JSON config consumed by the Python engine has no such validation. The bidirectional traversal was a pragmatic shortcut that works for simple linear jobs but breaks for complex DAGs.

**How to avoid:**
- Add a pre-execution validation pass that checks every component is reachable from at least one initial component through flows or triggers.
- Make the stall detection raise an error (or at least mark the job as "partial") instead of silently continuing.
- Change `_find_connected_components()` to only follow flows in the forward direction (from -> to) for subjob identification.
- Add explicit subjob_id to the JSON config (the converter already provides this) and trust it rather than auto-detecting.

**Warning signs:**
- Jobs complete "successfully" but produce fewer output rows than expected.
- Log shows "Execution stalled. Unexecuted components: ..." warnings.
- Components that should be triggered by OnSubjobOk never fire because subjob boundaries are incorrectly identified.

**Phase to address:**
Engine execution loop phase. Fix as part of the execution loop refactoring.

---

### Pitfall 9: OnSubjobOk Fires Prematurely (Per-Component Instead of Per-Subjob)

**What goes wrong:**
The trigger manager's `get_triggered_components()` method (trigger_manager.py lines 102-182) checks OnSubjobOk triggers every time ANY component in the subjob completes. It then calls `get_subjob_status()` to see if the entire subjob is "success." The problem: `get_subjob_status()` checks if ALL components in the subjob have status "success" -- but in the main execution loop, components are executed one at a time, and the trigger check happens after each component. If a subjob has 3 components (A -> B -> C) and A completes first, the trigger check for A already evaluates the subjob status. At this point B and C are still "pending," so the subjob status is "pending" and the trigger doesn't fire. This is correct. BUT -- if A is the ONLY component in the subjob (single-component subjobs are common), the trigger fires immediately, before downstream data flows from A have been stored.

The deeper issue: the trigger evaluation for OnSubjobOk runs on line 484 of engine.py, BEFORE the data flow storage on lines 568-585. So even for multi-component subjobs, triggers can fire before data is fully routed.

**Why it happens:**
The trigger evaluation happens in `_execute_component()` at the wrong point in the lifecycle. It should happen after data flow routing is complete, not during component execution.

**How to avoid:**
- Move trigger evaluation to AFTER data flow routing in the main execution loop (after `_execute_component` returns and data flows are stored).
- Ensure subjob completion is checked only when the last component in the subjob finishes, not on every component completion.
- Add integration tests with multi-component subjobs connected by OnSubjobOk triggers.

**Warning signs:**
- Downstream subjobs receive empty DataFrames despite upstream components processing data successfully.
- OnSubjobOk-triggered components execute but find no input data.
- Trigger order in logs shows triggers firing between component execution and data flow storage.

**Phase to address:**
Engine execution loop phase. This is an ordering bug in the execution lifecycle.

---

### Pitfall 10: Streaming Mode Silently Drops Reject Data

**What goes wrong:**
The `_execute_streaming()` method in `BaseComponent` (base_component.py lines 255-278) processes DataFrames in chunks and combines results. However, it only collects `chunk_result['main']` from each chunk -- it completely ignores `chunk_result.get('reject')`. For any component that produces reject output (tMap inner join rejects, tFilterRows rejected rows, tFileInputDelimited parse failures), streaming mode silently drops all rejected rows.

The streaming mode also returns only `{'main': combined}` without any other keys from the component's result dict (like named outputs from tMap). Components with multiple outputs lose all non-main outputs in streaming mode.

**Why it happens:**
The streaming implementation was built as a minimal proof-of-concept that only handles the simplest case (single input -> single output). Multi-output components and reject flows were not considered.

**How to avoid:**
- Extend `_execute_streaming()` to accumulate ALL result keys from each chunk, not just 'main'.
- For each unique key in chunk results, concatenate the DataFrames across chunks.
- Add an explicit test: run a tMap with inner join rejects in streaming mode and verify reject output is not empty.
- Consider whether streaming mode is even appropriate for this engine. Given that the MEMORY_THRESHOLD_MB is 3072 (3GB), and most production ETL jobs process less than this, streaming mode may never trigger. If it does trigger, the data loss is catastrophic. Better to fail loudly than drop data silently.

**Warning signs:**
- Jobs processing very large datasets (>3GB) produce fewer reject/error rows than expected.
- tMap components in streaming mode show 0 reject rows even with known unmatched lookup keys.
- NB_LINE_REJECT stats are suspiciously low for streaming-mode executions.

**Phase to address:**
Engine core infrastructure phase. Fix alongside other base_component.py issues.

---

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| `print()` instead of `logger` (79+ instances) | Quick debug output | Cannot control log levels in production; string formatting cost per row in tight loops; production noise obscures real errors | Never in production code. Replace all before production deployment. |
| `eval()`/`exec()` for expression evaluation (8+ sites) | Quick dynamic execution | Security risk (arbitrary code execution); no compile-once optimization; O(n) parse overhead per row | Acceptable for trusted job configs only. Add `compile()` pre-pass for per-row expressions. |
| `self.config` mutation via `resolve_dict()` | Simple context resolution | Non-reentrant: config is permanently modified after first execution. Iterate loops see already-resolved configs. | Never -- always resolve into a copy, keep original config immutable. |
| `synchronized(compiledScript)` for parallel execution | Prevents thread-safety crashes | Serializes all "parallel" work; scales worse than single-threaded for many rows | Never -- use per-thread script instances. |
| Inferring Arrow schema from first non-null value | Avoids requiring explicit schema | Silent data corruption on heterogeneous columns; wrong types for all-null columns | Only when no schema is available. Prefer declared schema from component config. |
| Hardcoded port 25333 as Py4J default | Simple configuration | Port conflicts when running multiple jobs concurrently | Acceptable only for single-job execution. Dynamic port allocation already exists in JavaBridgeManager. |

## Integration Gotchas

Common mistakes when connecting to external services.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Py4J Java Bridge | Not handling JVM process death gracefully. If the Java process crashes mid-execution (OOM, segfault), `Py4JNetworkError` is raised but the engine has no recovery path -- the job fails with an opaque network error. | Wrap all bridge calls in try/except for `Py4JNetworkError`. Implement health check (ping) before each bridge call. Consider JVM restart with `-Xmx` tuning for OOM cases. |
| Py4J Java Bridge | Accumulating Java object references without `detach()`. Every Java object accessed from Python creates a reference that prevents GC on the Java side. Long-running jobs with many tMap evaluations can exhaust JVM heap. | Call `gateway.detach(java_object)` after use, or rely on Python GC (which may not be timely). Monitor JVM heap usage. Set `-Xmx` appropriately. |
| Oracle Database | Components are commented out in engine registry and `src/v1/engine/components/database/` does not exist. Any job containing Oracle components will skip them silently (logged as "Unknown component type" warning). | Implement database components before enabling database jobs. Fail loudly (raise error) for unregistered component types instead of warning and skipping. |
| Arrow Serialization | Sending DataFrames with `Decimal` objects to Java. Python's `decimal.Decimal` must be explicitly mapped to Arrow `decimal128` with correct precision/scale. The bridge already handles this, but edge cases (NaN Decimal, Infinity, very large precision) are not handled. | Validate Decimal values before serialization. Reject Infinity/NaN Decimals. Cap precision at 38 (Arrow limit). |
| Context/GlobalMap Sync | Assuming Python context and Java context are in sync at all times. They are only synced at specific call points. A component modifying context in Python will not see the change reflected in Java until the next explicit sync. | Sync context explicitly before EVERY Java bridge call. Sync back after EVERY call that could modify context on the Java side. |

## Performance Traps

Patterns that work at small scale but fail as usage grows.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| `iterrows()` + `exec()` per row in PythonRowComponent | Execution time scales linearly with massive constant factor. 10K rows = seconds, 1M rows = hours. | Compile Python code once with `compile()`. Use `df.apply()` with the compiled function. For vectorizable operations, use pandas vectorized ops. | >50K rows |
| `eval()` per row in FilterRows | Expression string is parsed and compiled on every row. Apply with `axis=1` adds Python-level overhead per row. | `compile(expr)` once, then `eval(compiled_code, ...)` per row. Better: translate filter expressions to pandas query syntax. | >10K rows |
| Full DataFrame copy on every tMap lookup join | `joined_df = main_df.copy()` before each lookup, plus `prev_df = joined_df.copy()` for inner join reject detection. For N lookups, this creates 2N full copies. | Use in-place operations where safe. Only copy for inner join reject detection. Use `merge(indicator=True)` on the primary merge instead of a separate merge. | >500K rows with 3+ lookups |
| Re-scanning all components after each execution | The execution loop (engine.py line 496) iterates over ALL components after each component completes to find newly executable ones. For 50-component jobs, this is O(n^2) in components. | Build an adjacency list of dependencies. When a component completes, only check its direct dependents. | >30 components per job |
| Arrow serialization round-trip for simple expressions | Even `row1.column_name` (a simple column reference) goes through Arrow serialize -> Java evaluate -> Arrow deserialize if not caught by `SIMPLE_COLUMN_PATTERN`. | Expand the set of Python-evaluable patterns: arithmetic, string concatenation, null coalescing, type casts. Only send truly complex expressions to Java. | Every tMap execution |
| 3GB memory threshold for streaming switch | Streaming mode only activates at 3072 MB. A job processing a 2.5GB DataFrame stays in batch mode, consuming 5GB+ (input + intermediate copies). | Lower the threshold or make it configurable per job. Consider that DataFrames consume 2-10x the raw data size due to pandas overhead. | 1-3GB raw data size |

## Security Mistakes

Domain-specific security issues beyond general web security.

| Mistake | Risk | Prevention |
|---------|------|------------|
| `exec(python_code, namespace)` with `os` and `sys` in namespace | Arbitrary file system access, process control, and system information disclosure. A malicious job config could `os.system('rm -rf /')` or `os.environ['DB_PASSWORD']`. | Remove `os` and `sys` from the execution namespace. Create a whitelist of allowed modules. If untrusted configs are possible, use a sandboxed execution environment (e.g., RestrictedPython). |
| `eval(python_condition)` in TriggerManager for RunIf conditions | The Java-to-Python condition conversion (trigger_manager.py lines 196-234) is fragile: `!` to `not` replacement corrupts `!=` operators, and the resulting string is passed to `eval()`. A crafted RunIf condition could execute arbitrary Python. | Use `ast.literal_eval()` for simple value comparisons. For complex conditions, parse into an AST and evaluate safely. Fix the `!` replacement to only match standalone `!` (not `!=`). |
| SMTP passwords in job config JSON | Credentials stored in plain text in job config files. Could be committed to version control or exposed in logs. | Support environment variable references for sensitive config values (e.g., `${env.SMTP_PASSWORD}`). Never log config dicts that may contain passwords. |

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces.

- [ ] **tMap component:** Works for simple lookups but does not handle NULL join key semantics correctly (NULL should not match NULL per Talend behavior). Also missing: matching mode enforcement for FIRST_MATCH and LAST_MATCH (code references these but implementation may not filter duplicates correctly).
- [ ] **Iterate support:** `BaseIterateComponent` class exists and `_execute_iterate_component()` is coded in engine.py, but ZERO iterate components are registered in `COMPONENT_REGISTRY` (engine.py lines 159-160 are empty). The iterate execution path has never been tested.
- [ ] **Oracle database components:** Converter components exist at `src/converters/talend_to_v1/components/database/` with tests, but engine components do NOT exist (no `src/v1/engine/components/database/` directory). All database imports in engine.py are commented out.
- [ ] **Streaming mode:** Exists in `BaseComponent._execute_streaming()` but silently drops reject data and all non-main outputs. Any multi-output component in streaming mode produces data loss.
- [ ] **Error handling:** No custom exception hierarchy exists. All engine errors are generic `Exception` or `RuntimeError`. Error messages from different components are indistinguishable. The `Die` component has `exit_code` handling but no other component produces structured errors.
- [ ] **Engine import chain:** The engine.py file imports `AggregateSortedRow, Denormalize, Normalize, Replicate` from the wrong package (`aggregate` instead of `transform`). The entire engine module cannot be imported until this is fixed.
- [ ] **validate_schema nullable handling:** When `nullable=True`, the code fills NaN with 0 and casts to int64 (base_component.py line 352). This is backwards -- nullable=True should ALLOW nulls (use nullable integer dtype `Int64`), not fill them with 0.
- [ ] **RunIf condition evaluation:** The `!` to `not` string replacement (trigger_manager.py line 228) converts `!=` to ` not =` and `null` replacement converts `"annulled"` to `"anNoned"`. These corruption patterns break any RunIf condition containing these substrings.

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Null join key mismatches (Pitfall 3) | MEDIUM | Identify affected jobs by scanning for tMap joins where join key columns contain nulls. Re-run affected jobs after fixing null handling. Compare output row counts against Talend baseline. |
| Context sync drift (Pitfall 2) | HIGH | Audit all Java bridge call sites. Add sync before/after each call. Re-test all Java-using components. There may be production data already processed with wrong context values -- requires data reconciliation. |
| Iterate state leakage (Pitfall 4) | HIGH | Requires architectural fix (reset mechanism on BaseComponent). All iterate-dependent jobs (30% of 1200) must be re-validated after fix. Cannot be patched incrementally. |
| Arrow type corruption (Pitfall 7) | HIGH | Requires adding schema-driven Arrow serialization. All components using Java bridge must be re-tested with production-representative data including nulls and mixed types. |
| Streaming data loss (Pitfall 10) | LOW | Fix the streaming accumulation logic. Re-run any jobs that triggered streaming mode (>3GB data). Check for missing reject data. |
| Engine crash chain (Pitfall 5) | LOW | Two-line fix. All jobs become executable. No data recovery needed. |
| Context resolution corruption (Pitfall 6) | MEDIUM | Fix the bare pattern. Re-test components with Java code, Python code, and file paths containing "context." Re-run any jobs that produced incorrect output due to premature resolution. |

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Py4J script synchronization bottleneck | Java Bridge Reliability | Benchmark tMap with 100K+ rows; verify parallel execution actually parallelizes |
| Context/GlobalMap sync drift | Engine Core Infrastructure | Integration test: tJava modifies context, subsequent tMap reads it correctly |
| Null join semantics divergence | tMap Component Hardening | Test with null join keys; compare output against Talend baseline |
| Iterate state leakage | Iterate Support Implementation | 3-iteration test with changing context; verify independent iteration output |
| GlobalMap/update_global_map crash | Engine Core Infrastructure (first fix) | Smoke test: minimal job executes without NameError |
| Context resolution corruption | Engine Core Infrastructure | Test resolve_dict with java_code, python_code, file paths containing "context" |
| Arrow type mismatch corruption | Java Bridge Reliability | Test serialization with null columns, mixed types, Decimal edge cases |
| Execution loop stall | Engine Execution Loop Refactoring | Test with unreachable components; verify error raised, not silent stall |
| OnSubjobOk premature firing | Engine Execution Loop Refactoring | Multi-component subjob with OnSubjobOk; verify trigger fires after ALL components |
| Streaming reject data loss | Engine Core Infrastructure | tMap in streaming mode with inner join rejects; verify reject output non-empty |

## Sources

- [Py4J Advanced Topics -- Memory Management, Threading, Type Conversion](https://www.py4j.org/advanced_topics.html)
- [Py4J Changelog -- Memory leak fixes, ClientServer deadlock resolution](https://www.py4j.org/changelog.html)
- [Py4J Issue #275 -- Transport corruption from GC during communication](https://github.com/py4j/py4j/issues/275)
- [Py4J Issue #320 -- Java process lifecycle management](https://github.com/py4j/py4j/issues/320)
- [Py4J Issue #200 -- Reconnection after JVM restart](https://github.com/py4j/py4j/issues/200)
- [Talend Trigger Connections Documentation](https://help.qlik.com/talend/en-US/studio-user-guide/8.0-R2024-06/trigger-connections-for-job)
- [Talend tMap Inner Join Reject Behavior](https://community.talend.com/t5/Design-and-Development/tMap-Inner-Join-NULL-Rejected-Really-need-help/td-p/70969)
- [Talend Job Design Patterns -- OnSubjobOk vs OnComponentOk Memory Implications](https://www.talend.com/resources/talend-job-design-patterns-and-best-practices-part-1/)
- [Talend tFlowToIterate Properties](https://help.qlik.com/talend/en-US/components/7.3/orchestration/tflowtoiterate-standard-properties)
- [Pandas Scaling to Large Datasets -- Copy-on-Write, Chunking](https://pandas.pydata.org/docs/user_guide/scale.html)
- [Arrow Type System -- Decimal128 limits, Schema requirements](https://arrow.apache.org/docs/python/api/datatypes.html)
- [Databricks Community -- Talend Migration Best Practices](https://community.databricks.com/t5/data-engineering/migrating-talend-etl-jobs-to-databricks-best-practices-amp/td-p/135492)
- Internal: `docs/v1/audit/CROSS_CUTTING_ISSUES.md` -- 7 P0, 9 P1, 8 P2, 6 P3 cross-cutting bugs
- Internal: `docs/v1/audit/SUMMARY_SCORECARD.md` -- 928 issues across 86 components, 33 RED, 50 YELLOW, 3 GREEN
- Internal: `.planning/codebase/CONCERNS.md` -- Tech debt, known bugs, security considerations

---
*Pitfalls research for: Talend ETL Migration Engine (Python/Py4J)*
*Researched: 2026-04-14*
