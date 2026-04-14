# Phase 5: tMap Component - Context

**Gathered:** 2026-04-15
**Status:** Ready for planning

<domain>
## Phase Boundary

Rewrite the tMap engine component from scratch with full Talend feature parity for join semantics, expression handling, reject routing, and all matching modes. tMap is the most complex component in the codebase (1164 lines) -- the rewrite preserves the sound hybrid architecture (pandas for bulk joins + Java bridge for expressions) but rebuilds within the BaseComponent lifecycle, fixes all 8 MAP requirements, and introduces smart join routing for cross-table expressions. Deep research into Talend's actual tMap execution via Talaxie GitHub `.javajet` source templates is required before planning.

**Phase 2/3 dependencies:** Java bridge (compile-once-execute-many pattern, tMap preprocessing/compiled APIs), Executor + OutputRouter (multi-input routing, named output flows), BaseComponent lifecycle (config immutability, stats, globalMap).

**Converter:** tMap converter (337 lines, Green status) stays as-is. No converter changes needed except potentially re-adding ENABLE_AUTO_CONVERT_TYPE for MAP-06.

</domain>

<decisions>
## Implementation Decisions

### Rewrite Approach
- **D-01:** Full rewrite from scratch. Not patching the existing 1164-line map.py. Conform to ENGINE_COMPONENT_PATTERN.md blueprint.
- **D-02:** Add `@REGISTRY.register('Map', 'tMap')` decorator per Phase 3 D-04.
- **D-03:** Preserve the hybrid architecture: pandas for bulk joins, Java bridge for expression evaluation. This approach is sound and performant.
- **D-04:** Preserve compile-once-execute-many Java bridge pattern for output evaluation (`compile_tmap_script()` + `execute_compiled_tmap_chunked()`).

### BaseComponent Lifecycle Integration (MAP-04)
- **D-05:** tMap does NOT override `execute()`. Uses BaseComponent lifecycle with targeted hook overrides. The whole point of MAP-04 is to stop bypassing the lifecycle -- overriding execute() again defeats that.
- **D-06:** Override `_resolve_expressions()` -- resolve context variables on scalar config fields only. Skip Java expression resolution entirely because tMap's expressions (output column mappings, filters, variables, join keys) reference row data and must be evaluated per-row inside `_process()`, not at config resolution time.
- **D-07:** Override `_update_stats_from_result()` -- tMap returns arbitrary named outputs (out1, reject1, etc.), not just main/reject. Must sum across all named output DataFrames.
- **D-08:** Override `_select_mode()` -- always return BATCH. tMap handles its own chunking internally via the Java bridge 50K chunk pattern.
- **D-09:** Implement `_validate_config()` (required by BaseComponent) and `_process()` as the core processing method.
- **D-10:** Benefits of hook approach: config immutability for free (deepcopy from _original_config), iterate support automatic (reset + config re-derivation), future lifecycle additions inherited.

### Join Semantics (Talend Parity -- Non-Negotiable)
- **D-11:** MAP-01 UNIQUE_MATCH uses first-row semantics (`drop_duplicates(keep='first')`). Current code incorrectly uses `keep='last'`.
- **D-12:** MAP-02 rejectInnerJoin outputs are distinct from generic reject outputs. Track per-lookup which main rows failed inner join. Use pandas merge indicator to identify unmatched rows per lookup.
- **D-13:** MAP-03 Null keys never match (SQL/Talend semantics). Pre-filter rows where ANY join key is null/NaN on both sides before pandas merge. Track null-key main rows for potential reject routing.
- **D-14:** All matching modes match Talend behavior exactly: UNIQUE_MATCH (first-row), FIRST_MATCH, LAST_MATCH, ALL_MATCHES (cartesian).

### Smart Join Routing (Cross-Table Expressions)
- **D-15:** Classify each lookup's join keys at processing time and route to the appropriate join strategy:
  - **Equality joins** (simple column ref like `row1.id`): pandas merge -- fast, O(n+m)
  - **Context-only joins** (like `context.region`): evaluate expression once, filter lookup, cross-join -- bounded by lookup size
  - **Cross-table joins** (references both sides like `StringHandling.MATCH(row1.name, lookup1.pattern)` or `row1.amount > lookup1.threshold`): chunked nested-loop evaluation via Java bridge -- O(n*m) comparisons but O(n*k) memory where k = average matches per row
- **D-16:** Cross-table joins are the critical design challenge. Research phase MUST investigate how Talend handles these via the `.javajet` code generation templates before implementation. Production job scan should identify which patterns actually appear.
- **D-17:** Size guard for cross-table and cartesian joins. Warn at configurable threshold, fail if product exceeds a hard limit. Prevents silent OOM.

### Chunking Strategy
- **D-18:** Preprocessing (join key evaluation, filter expressions) adds configurable threshold chunking. Only chunk if DataFrame exceeds threshold (e.g., 100K rows). Small datasets go through in one call for efficiency.
- **D-19:** Post-processing (compiled script output evaluation) preserves existing compile+chunk pattern via `execute_compiled_tmap_chunked()` with configurable chunk size.
- **D-20:** Chunk size configurable via config with sensible default (50K).

### Multi-Input/Output Routing
- **D-21:** `_process()` receives `Dict[flow_name, DataFrame]` from Phase 3 OutputRouter (e.g., `{"row1": DataFrame, "lookup1": DataFrame}`). OutputRouter already returns dict for multi-input components.
- **D-22:** `_process()` returns `Dict[output_name, DataFrame]` (e.g., `{"out1": DataFrame, "reject1": DataFrame}`). OutputRouter routes named outputs to downstream components.
- **D-23:** Converter already populates `component["inputs"]` and `component["outputs"]` lists -- ExecutionPlan uses these to wire OutputRouter.

### Feature Scope (All MAP-01 through MAP-08)
- **D-24:** MAP-05 catch output reject (activateCondensedTool) -- in scope. Captures expression evaluation errors into a separate output.
- **D-25:** MAP-06 auto type conversion (ENABLE_AUTO_CONVERT_TYPE) -- in scope. Converter currently removes this as hidden param; may need small converter update to re-add.
- **D-26:** MAP-07 {id}_NB_LINE globalMap variable -- in scope, handled via BaseComponent stats + _update_global_map().
- **D-27:** MAP-08 RELOAD_AT_EACH_ROW lookup mode -- in scope. Re-executes lookup per main row for parameterized lookups. Research must determine exact Talend behavior (re-query DB? re-filter cached table?).

### Thread Safety Fix (BUG-MAP-003)
- **D-28:** The compiled Java script uses `IntStream.parallel().forEach()` with a `HashMap` for variable storage (`Var.put(...)`) -- this is NOT thread-safe. Research must determine whether to: (a) use ConcurrentHashMap, (b) use per-thread variable maps, or (c) drop parallel execution. Talend's javajet templates will show how Talend handles this.

### Research Directive
- **D-29:** Deep research required before planning. The researcher MUST investigate all 10 topics:
  1. Cross-table join patterns in production .item samples
  2. Chained lookup patterns (Lookup2 references Lookup1)
  3. Variable dependency chains and evaluation order
  4. Thread safety in compiled scripts (parallel forEach + HashMap)
  5. Column name collision handling in Talend
  6. RELOAD_AT_EACH_ROW exact behavior from Talend source
  7. Expression error routing semantics (activateCondensedTool)
  8. Production .item scan for tMap usage patterns
  9. Memory/performance benchmarks for join strategies
  10. Talend Studio javajet templates for tMap internals

### Test Strategy
- **D-30:** Follows Phase 4 pattern: exhaustive tests per MAP requirement.
- **D-31:** Test location: `tests/v1/engine/components/transform/test_map.py`
- **D-32:** Multi-input test setup required: create main + lookup DataFrames, wrap in dict matching OutputRouter format.
- **D-33:** Java bridge can be mocked for unit tests (test join logic, routing, stats). Real bridge for integration tests marked with `@pytest.mark.java`.

### Claude's Discretion
- Internal method decomposition and helper design
- Exact preprocessing chunk threshold value
- How to structure the smart join classifier
- Column prefixing strategy (current `lookup_name.column` or alternative)
- Whether to use pandas merge indicator vs set-based difference for reject detection
- Compiled script generation details (parallel vs sequential, variable scoping)
- Test count target (estimated ~60-100 tests based on scope)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Talend Source (PRIMARY -- Behavior Reference)
- Talaxie GitHub: `Talaxie/tdi-studio-se` repository, path `main/plugins/org.talend.designer.components.localprovider/components/tMap/`
  - `tMap_java.xml` -- Parameter definitions, defaults, types, connectors
  - `tMap_begin.javajet` -- Code generated before component loop (lookup loading, join setup, matching mode implementation)
  - `tMap_main.javajet` -- Per-row execution (expression evaluation, cross-table matching, reject routing, variable evaluation order)
  - `tMap_end.javajet` -- Cleanup, stats, globalMap variable setting
- **This is the definitive source for all Talend behavioral questions.** More authoritative than docs. Research phase MUST fetch and analyze these files.

### Audit Report
- `docs/v1/audit/components/transform/tMap.md` -- Full audit: 26 issues (3 P0, 8 P1, 12 P2, 3 P3), feature parity analysis, behavioral differences, performance concerns, risk assessment

### Engine Component Pattern (Blueprint)
- `docs/v1/standards/ENGINE_COMPONENT_PATTERN.md` -- Gold standard pattern. tMap must conform.
- `docs/v1/standards/ENGINE_TEST_PATTERN.md` -- Test pattern for engine component tests.

### Current Engine Source (Rewrite Target)
- `src/v1/engine/components/transform/map.py` -- Current Map class (1164 lines, full rewrite)

### Converter Source (Config Key Reference -- No Changes)
- `src/converters/talend_to_v1/components/transform/map.py` -- MapConverter (337 lines, Green). Produces the config that the engine reads.

### Phase 1/2/3 Infrastructure (Build On)
- `src/v1/engine/base_component.py` -- Rewritten BaseComponent with lifecycle (validate -> snapshot -> resolve -> process -> stats)
- `src/v1/engine/component_registry.py` -- Decorator-based ComponentRegistry from Phase 3
- `src/v1/engine/output_router.py` -- Multi-input routing (get_input_data returns dict for multi-input), named output flow routing
- `src/v1/engine/executor.py` -- Executor._execute_component() passes input_data through, routes result
- `src/v1/engine/exceptions.py` -- Exception hierarchy (ConfigurationError, ComponentExecutionError, DataValidationError)
- `src/v1/java_bridge/bridge.py` -- Phase 2 rewritten bridge with tMap-specific APIs:
  - `execute_tmap_preprocessing()` -- batch expression evaluation on rows
  - `compile_tmap_script()` -- compile Groovy script once
  - `execute_compiled_tmap_chunked()` -- execute compiled script in chunks
  - All use `_call_java_with_sync()` for automatic context/globalMap sync

### Sample Converter Output
- `tests/talend_xml_samples/converted_jsons/` -- Real converter output for tMap jobs (scan for tMap usage patterns)

### Production .item Samples
- `tests/talend_xml_samples/` -- Talend XML samples. Research phase should scan for tMap components and analyze join patterns.

### Requirements
- `.planning/REQUIREMENTS.md` -- MAP-01 through MAP-08, TEST-03 mapped to Phase 5

### Prior Phase Context
- `.planning/phases/01-infrastructure-bug-fixes-project-setup/01-CONTEXT.md` -- D-08/D-09 (rewrite approach), D-13 (_validate_config abstract), D-14 (config snapshot for iterate)
- `.planning/phases/02-java-bridge-reliability/02-CONTEXT.md` -- D-04/D-05/D-06 (schema-driven serialization), D-12 (sync at every call site)
- `.planning/phases/03-execution-loop-restructure/03-CONTEXT.md` -- D-02/D-04 (decorator registry, each phase adds its own), D-01 (5-file split)
- `.planning/phases/04-file-i-o-components/04-CONTEXT.md` -- D-01 (full rewrite pattern), D-04 (read converter keys directly)

</canonical_refs>

<code_context>
## Existing Code Insights

### What Gets Rewritten
- `map.py` (1164 lines) -- overrides execute() entirely (bypasses lifecycle), manual context/globalMap sync (duplicates Phase 2 bridge), UNIQUE_MATCH uses keep='last' (wrong), no null key handling, fragile inner join reject detection (prev_df re-merge), no _validate_config(), no RELOAD_AT_EACH_ROW, no catch output reject, parallel forEach with non-thread-safe HashMap for variables, no preprocessing chunking

### What to Preserve (Architecture Concepts)
- Hybrid approach: pandas for bulk equality joins, Java bridge for expression evaluation. Sound architecture.
- Compile-once-execute-many pattern: generate Java script, compile via bridge, execute in parallel chunks. Performance-critical.
- Column prefixing with `lookup_name.column` to avoid collisions between main/lookup columns. May need refinement.
- Sequential lookup processing (Lookup2 can reference Lookup1's joined columns). Correct behavior.

### What Phase 2 Bridge Provides
- `execute_tmap_preprocessing()` -- batch evaluate expressions on DataFrame rows, returns numpy arrays per expression. Uses `_call_java_with_sync()`.
- `compile_tmap_script()` + `execute_compiled_tmap_chunked()` -- compile once, execute in 50K row chunks. No manual sync needed.
- Schema-driven Arrow serialization -- no data-inference issues.

### What Phase 3 Provides
- OutputRouter.get_input_data() returns Dict[flow_name, DataFrame] for multi-input components -- exactly what tMap needs.
- OutputRouter.route_outputs() maps named outputs to downstream flows.
- Executor passes input_data through and routes result back. No special handling needed for tMap.

### Established Patterns (From Prior Phases)
- BaseComponent lifecycle: validate -> snapshot -> resolve -> process -> stats (Phase 1)
- Decorator-based registry: `@REGISTRY.register()` triggered on import (Phase 3)
- Config immutability: _original_config deepcopied, config re-derived each execute() (Phase 1)
- Test pattern: tmp_path fixtures, exhaustive per-requirement coverage, @pytest.mark.java (Phase 2/4)

### Integration Points
- Registers in ComponentRegistry via `@REGISTRY.register('Map', 'tMap')` decorator
- Receives multi-input dict from OutputRouter, returns multi-output dict
- Uses Java bridge for expression evaluation (preprocessing + compiled output)
- Sets globalMap variables via BaseComponent._update_global_map()
- Uses ContextManager for context variable resolution (via BaseComponent lifecycle)

</code_context>

<specifics>
## Specific Ideas

- The Talaxie GitHub `.javajet` files are the definitive source for Talend behavior -- more authoritative than documentation. Research phase must fetch and analyze `tMap_begin.javajet`, `tMap_main.javajet`, `tMap_end.javajet`.
- Smart join routing (equality vs context-only vs cross-table) is the key architectural innovation over the current code. Research phase must determine how Talend handles cross-table expressions before implementation.
- BUG-MAP-003 (parallel forEach + HashMap) is a P0 correctness bug in the compiled script generation. The rewrite must fix this -- research should check Talend's threading model for tMap.
- MAP-06 (ENABLE_AUTO_CONVERT_TYPE) was removed from converter output as hidden/design-time param. May need small converter update to re-add it if research confirms it's needed for production jobs.
- Preprocessing chunking uses a configurable threshold (chunk only if DataFrame exceeds threshold). Avoids unnecessary overhead for small datasets.

</specifics>

<deferred>
## Deferred Ideas

- MAP-V2-02: Disk-based lookup caching (STORE_ON_DISK, ROWS_BUFFER_SIZE) -- v2 requirement
- MAP-V2-03: Parallel lookup loading (LKUP_PARALLELIZE) -- v2 requirement
- MAP-V2-04: Fuzzy matching (Levenshtein/Jaccard distance thresholds) -- v2 requirement
- MAP-V2-05: BigDecimal hash/equals for join keys -- v2 requirement
- activateGlobalMap on input/output tables -- low priority, deferred
- persistent lookup support -- low priority, deferred
- ALL_ROWS keyless cross-join matching mode -- P3, deferred

None -- discussion stayed within phase scope

</deferred>

---

*Phase: 05-tmap-component*
*Context gathered: 2026-04-15*
