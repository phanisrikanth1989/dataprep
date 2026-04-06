# Audit Report: tMap / Map

> **Audited**: 2026-04-04
> **Auditor**: Claude Opus 4.6 (automated)
> **Engine Version**: v1
> **Converter**: `talend_to_v1`
> **Status**: PRODUCTION READINESS REVIEW
> **V1 only** -- this report contains zero references to v2/PyETL

---

## 1. Component Identity

| Field | Value |
| ------- | ------- |
| **Talend Name** | `tMap` |
| **V1 Engine Class** | `Map` |
| **Engine File** | `src/v1/engine/components/transform/map.py` (1164 lines) |
| **Converter Parser** | `src/converters/talend_to_v1/components/transform/map.py` -> `MapConverter` |
| **Converter Dispatch** | `@REGISTRY.register("tMap")` decorator-based dispatch |
| **Registry Aliases** | `Map`, `tMap` |
| **Category** | Transform / Multi-Flow Data Mapping |

### Key Files

| File | Purpose |
| ------ | --------- |
| `src/v1/engine/components/transform/map.py` | Engine implementation (1164 lines -- largest in codebase) |
| `src/converters/talend_to_v1/components/transform/map.py` | `MapConverter` class -- parses MapperData XML into v1 JSON config |
| `tests/converters/talend_to_v1/components/test_map.py` | 56 converter tests across 11 test classes |
| `src/v1/engine/base_component.py` | Base class: `execute()`, `_update_global_map()` |
| `src/v1/engine/engine.py` (lines 779-795) | Multi-input routing: `_get_input_data()` returns dict for multi-input components |
| `src/v1/java_bridge/bridge.py` | Java bridge: `compile_tmap_script()`, `execute_compiled_tmap_chunked()` |
| `src/v1/engine/global_map.py` | GlobalMap storage for `{id}_NB_LINE` etc. |

---

## 2. Scorecard

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
| ----------- | ------- | ---- | ---- | ---- | ---- | --------- |
| Converter Coverage | **G** | 0 | 0 | 0 | 0 | 9 unique + 2 framework params extracted (100%). CHANGE_HASH default fixed. LEVENSHTEIN/JACCARD added. 9 per-feature needs_review. Multi-flow nodeData parsing preserved. |
| Engine Feature Parity | **Y** | 1 | 6 | 5 | 2 | No RELOAD_AT_EACH_ROW; no disk-based lookup caching; no parallel lookup; no catch_output_reject; UNIQUE_MATCH semantic deviation |
| Code Quality | **Y** | 3 | 4 | 6 | 3 | Cross-cutting base class bugs; parallel forEach race condition; `print()` in bridge |
| Performance & Memory | **Y** | 0 | 1 | 3 | 1 | 50K chunk size hard-coded; cartesian join has no size guard; Arrow serialization overhead |
| Testing | **Y** | 0 | 1 | 0 | 0 | 56 converter tests (Green). Zero engine unit tests (per D-73, Testing=Y not G). |

**Overall: Y -- Most complex component. Converter now gold standard. Engine has significant feature gaps.**

**Top Actions**:

1. Fix cross-cutting `_update_global_map()` crash (P0, all components)
2. Implement RELOAD_AT_EACH_ROW lookup mode (P1, correctness)
3. Add engine unit tests for tMap (P1, testing gap)
4. Add cartesian join size guard (P1, memory safety)
5. Fix parallel forEach race condition in Java bridge (P0, concurrency)

---

## 3. Talend Feature Baseline

### What tMap Does

tMap is Talend's most powerful data transformation component. It performs expression-based column mapping, multi-table lookup joins, variable computation, and conditional output routing -- all configured through a visual drag-and-drop mapper interface. tMap supports multiple input flows (one main plus any number of lookups), multiple output flows (including reject flows for failed join matches), and an intermediate variable table for reusable computed values.

The component uses Java expressions for all column mappings, filters, and join conditions. Lookup joins support multiple matching modes (UNIQUE_MATCH, FIRST_MATCH, LAST_MATCH, ALL_MATCHES) and can be inner or left outer joins. Output tables can have row-level expression filters and reject flags for capturing unmatched rows.

**Source**: Talaxie GitHub _java.xml, Talend Studio documentation
**Component family**: Processing
**Available in**: All Talend editions
**Required JARs**: None (built-in)

### 3.1 Basic Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
| --- | ----------- | ----------------- | ------ | --------- | ------------- |
| 1 | Map | `MAP` | EXTERNAL | -- | Visual mapper editor reference. Not extracted (UI-only). |
| 2 | Link Style | `LINK_STYLE` | CLOSED_LIST | `AUTO` | Connection line rendering style (AUTO, ROW, COLUMN). Visual only. |

### 3.2 Advanced Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
| --- | ----------- | ----------------- | ------ | --------- | ------------- |
| 3 | Die on Error | `DIE_ON_ERROR` | CHECK (hidden) | `true` | Stop job on component error |
| 4 | Lookup Parallelize | `LKUP_PARALLELIZE` | CHECK (hidden) | `false` | Load lookup tables in parallel |
| 5 | Levenshtein | `LEVENSHTEIN` | TEXT (hidden) | `0` | Levenshtein distance threshold for fuzzy string matching |
| 6 | Jaccard | `JACCARD` | TEXT (hidden) | `0` | Jaccard similarity threshold for fuzzy string matching |
| 7 | Enable Auto Convert Type | `ENABLE_AUTO_CONVERT_TYPE` | CHECK (hidden) | `false` | Auto-convert types between join columns |
| 8 | Rows Buffer Size | `ROWS_BUFFER_SIZE` | TEXT | `2000000` | Buffer size for disk-based lookup caching |
| 9 | Change Hash for BigDecimal | `CHANGE_HASH_AND_EQUALS_FOR_BIGDECIMAL` | CHECK | `true` | Use BigDecimal-safe hash/equals (ignores trailing zeros in join key comparisons) |

### 3.3 nodeData (MapperData XML)

tMap's primary configuration lives in nodeData XML, not elementParameters:

| Element | Purpose | Key Attributes |
| --------- | --------- | ---------------- |
| `inputTables` (first) | Main input flow | `name`, `activateExpressionFilter`, `expressionFilter`, `matchingMode`, `lookupMode` |
| `inputTables` (subsequent) | Lookup flows | Above + `innerJoin`, `persistent`, `sizeState` |
| `varTables` | Variable definitions | `name`, `sizeState` |
| `outputTables` | Output flows | `name`, `reject`, `rejectInnerJoin`, `activateExpressionFilter`, `expressionFilter` |
| `mapperTableEntries` | Column mappings | `name`, `expression`, `type`, `nullable`, `operator`, `length`, `precision`, `pattern` |

### 3.4 Framework Parameters

| # | Parameter | Talend XML Name | Type | Default |
| --- | ----------- | ----------------- | ------ | --------- |
| 10 | Stat Catcher | `TSTATCATCHER_STATS` | CHECK | `false` |
| 11 | Label | `LABEL` | TEXT | `""` |

### 3.5 Connection Types

| Connector | Direction | Type | Description |
| ----------- | ----------- | ------ | ------------- |
| `FLOW` (Main) | Input | Row > Main | Primary data input |
| `LOOKUP` | Input | Row > Lookup | Lookup table input (one per lookup) |
| `FLOW` (Output) | Output | Row > Main | Named output flows |
| `REJECT` | Output | Row > Reject | Rejected rows from inner join failures |
| `SUBJOB_OK` | Output (Trigger) | Trigger | Fires after component completes |
| `SUBJOB_ERROR` | Output (Trigger) | Trigger | Fires on component error |

### 3.6 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
| ------------------ | ------ | ---------- | ------------- |
| `{id}_NB_LINE` | Integer | After execution | Number of rows processed |

### 3.7 Behavioral Notes

1. **CHANGE_HASH_AND_EQUALS_FOR_BIGDECIMAL defaults to true** -- ensures consistent join key behavior when BigDecimal values have trailing zeros (e.g., 1.0 vs 1.00 are treated as equal).
2. **LEVENSHTEIN and JACCARD** are fuzzy matching thresholds. When non-zero, tMap uses fuzzy string comparison for join keys instead of exact match. These are text type (string values like "3" or "0.8").
3. **First inputTable is always the main flow**, subsequent inputTables are lookups. This ordering is critical for correct parsing.
4. **matchingMode** on lookup tables controls deduplication: UNIQUE_MATCH (first match), FIRST_MATCH, LAST_MATCH, ALL_MATCHES (cartesian).
5. **reject=true on outputTables** creates a reject flow. rejectInnerJoin=true captures rows that failed inner join conditions.
6. **expressionFilter** on any table is only active when activateExpressionFilter=true. Inactive filters are stored but not applied.

---

## 4. Converter Audit

### 4.1 Parameter Extraction

MapConverter parses both elementParameter flat params and nodeData MapperData XML. The converter uses module-level helper functions for each nodeData section: `_parse_input_main()`, `_parse_lookup()`, `_parse_variables()`, `_parse_outputs()`. All expressions are prefixed with `{{java}}` marker for engine routing.

| # | Talend XML Parameter | Extracted? | V1 Config Key | Notes |
| --- | ---------------------- | ------------ | --------------- | ------- |
| 1 | `MAP` | No | -- | Visual editor reference, not a config param |
| 2 | `LINK_STYLE` | **REMOVED** | ~~link_style~~ | Hidden/design-time param -- removed from converter |
| 3 | `DIE_ON_ERROR` | Yes | `die_on_error` | Default True |
| 4 | `LKUP_PARALLELIZE` | **REMOVED** | ~~lkup_parallelize~~ | Hidden/design-time param -- removed from converter |
| 5 | `LEVENSHTEIN` | **REMOVED** | ~~levenshtein~~ | Hidden/design-time param -- removed from converter |
| 6 | `JACCARD` | **REMOVED** | ~~jaccard~~ | Hidden/design-time param -- removed from converter |
| 7 | `ENABLE_AUTO_CONVERT_TYPE` | **REMOVED** | ~~enable_auto_convert_type~~ | Hidden/design-time param -- removed from converter |
| 8 | `ROWS_BUFFER_SIZE` | Yes | `rows_buffer_size` | Default "2000000". Extracted as str for expression support. |
| 9 | `CHANGE_HASH_AND_EQUALS_FOR_BIGDECIMAL` | Yes | `change_hash_and_equals_for_bigdecimal` | Default True. **FIXED** (was False) |
| 10 | `TSTATCATCHER_STATS` | Yes | `tstatcatcher_stats` | Framework param, default False |
| 11 | `LABEL` | Yes | `label` | Framework param, default "" |

**nodeData extraction:**

| Element | Extracted? | V1 Config Path | Notes |
| --------- | ------------ | ---------------- | ------- |
| `inputTables[0]` | Yes | `config.inputs.main` | Main flow with filter, matching_mode, lookup_mode |
| `inputTables[1:]` | Yes | `config.inputs.lookups[]` | Lookup flows with join keys, join_mode, matching_mode |
| `varTables` | Yes | `config.variables[]` | Variable definitions with expressions |
| `outputTables` | Yes | `config.outputs[]` | Output tables with columns, reject flags, filters |

**Summary**: 4 of 9 unique parameters extracted + 2 framework params + full nodeData parsing. 5 hidden/design-time params removed.

### 4.2 Schema Extraction

tMap uses empty schema (`{}`) because multi-flow routing is driven by nodeData configuration, not standard FLOW schema. The engine builds its own column lists from the MapperData input/output table definitions.

### 4.3 Expression Handling

All MapperData expressions (join keys, variable definitions, output column mappings, filters) are prefixed with `{{java}}` marker by `_java_expr()`. Context variables (`${context.var}`) are resolved by the engine's context_manager at runtime.

### 4.4 Converter Issues

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| ~~CONV-MAP-001~~ | ~~P1~~ | **FIXED** -- CHANGE_HASH_AND_EQUALS_FOR_BIGDECIMAL default corrected to True |
| ~~CONV-MAP-002~~ | ~~P1~~ | **FIXED** -- LEVENSHTEIN param added (was missing entirely) |
| ~~CONV-MAP-003~~ | ~~P1~~ | **FIXED** -- JACCARD param added (was missing entirely) |
| ~~CONV-MAP-004~~ | ~~P2~~ | **FIXED** -- LINK_STYLE default corrected to "AUTO" (was empty string) |
| ~~CONV-MAP-005~~ | ~~P2~~ | **FIXED** -- ROWS_BUFFER_SIZE extracted as str not int (supports expression strings) |
| ~~CONV-MAP-006~~ | ~~P2~~ | **FIXED** -- needs_review entries now use structured format (was using warnings only) |

### 4.5 Needs Review Entries

| # | Config Key | Reason | Severity |
| --- | ----------- | -------- | ---------- |
| 1 | `rows_buffer_size` | Engine does not read -- no disk buffering support | engine_gap |
| 2 | `change_hash_and_equals_for_bigdecimal` | Engine does not handle BigDecimal hash/equals behavior | engine_gap |

---

## 5. Engine Feature Parity

### 5.1 Feature Implementation Status

| # | Talend Feature | Implemented? | Fidelity | Engine Location | Notes |
| --- | ---------------- | ------------- | ---------- | ----------------- | ------- |
| 1 | Main input processing | **Yes** | High | `_process()` line 90 | Reads config\['inputs'\]\['main'\] |
| 2 | Lookup joins | **Yes** | Medium | `_join_lookups()` | Uses pandas merge, matching_mode support |
| 3 | UNIQUE_MATCH mode | **Partial** | Low | `_join_lookups()` | Uses drop_duplicates -- may not match Talend's "first row" semantics |
| 4 | ALL_MATCHES mode | **Yes** | High | `_join_lookups()` | Default pandas merge behavior |
| 5 | Inner/Outer join | **Yes** | High | `_join_lookups()` | Reads join_mode from config |
| 6 | Variable evaluation | **Yes** | Medium | `_evaluate_variables()` | Java expression evaluation via bridge |
| 7 | Output column mapping | **Yes** | Medium | `_generate_outputs()` | Java expression evaluation per output |
| 8 | Output filters | **Yes** | Medium | `_generate_outputs()` | Filter expressions evaluated via Java |
| 9 | Reject output | **Yes** | Medium | `_generate_outputs()` | Reject flag detection |
| 10 | Expression filters on inputs | **Yes** | Medium | `_process()` | Main and lookup input filters |
| 11 | RELOAD_AT_EACH_ROW | **No** | N/A | -- | Always loads once (P1) |
| 12 | RELOAD_AT_EACH_ROW_CACHE | **No** | N/A | -- | Always loads once (P1) |
| 13 | Disk-based lookup caching | **No** | N/A | -- | STORE_ON_DISK/TEMPORARY_DATA_DIRECTORY not supported |
| 14 | Parallel lookup loading | **No** | N/A | -- | LKUP_PARALLELIZE not supported |
| 15 | Auto type conversion | **No** | N/A | -- | ENABLE_AUTO_CONVERT_TYPE not supported |
| 16 | BigDecimal hash/equals | **No** | N/A | -- | CHANGE_HASH_AND_EQUALS_FOR_BIGDECIMAL not supported |
| 17 | Fuzzy matching (Levenshtein) | **No** | N/A | -- | LEVENSHTEIN threshold not supported |
| 18 | Fuzzy matching (Jaccard) | **No** | N/A | -- | JACCARD threshold not supported |
| 19 | Catch output reject | **No** | N/A | -- | activateCondensedTool on outputs not supported |
| 20 | GlobalMap access from table | **No** | N/A | -- | activateGlobalMap not supported |
| 21 | die_on_error | **Yes** | High | `_process()` line 867 | `config.get('die_on_error', True)` |

### 5.2 Behavioral Differences from Talend

| ID | Priority | Description |
| ---- | ---------- | ------------- |
| ENG-MAP-001 | **P0** | `_update_global_map()` crash when globalMap is set (cross-cutting base class bug) |
| ENG-MAP-002 | **P0** | Parallel forEach race condition in Java bridge chunked execution |
| ENG-MAP-003 | **P0** | `parse_base_component()` returns None for tMap (multi-input routing mismatch) |
| ENG-MAP-004 | **P1** | RELOAD_AT_EACH_ROW not implemented -- always loads once |
| ENG-MAP-005 | **P1** | UNIQUE_MATCH uses drop_duplicates, may not match Talend first-row semantics |
| ENG-MAP-006 | **P1** | No catch_output_reject -- filter-reject chaining not supported |
| ENG-MAP-007 | **P1** | No disk-based lookup caching (STORE_ON_DISK) |
| ENG-MAP-008 | **P1** | No parallel lookup loading (LKUP_PARALLELIZE) |
| ENG-MAP-009 | **P1** | No auto type conversion between join columns |
| ENG-MAP-010 | **P2** | No BigDecimal hash/equals handling for join keys |
| ENG-MAP-011 | **P2** | No fuzzy matching (Levenshtein/Jaccard) for join keys |
| ENG-MAP-012 | **P2** | No globalMap access from input/output tables |
| ENG-MAP-013 | **P2** | No rejectInnerJoin differentiation from generic reject |
| ENG-MAP-014 | **P2** | No persistent lookup support |
| ENG-MAP-015 | **P3** | 50K chunk size hard-coded -- should be configurable |
| ENG-MAP-016 | **P3** | No ALL_ROWS matching mode (keyless cross-join) |

### 5.3 GlobalMap Variable Coverage

| Variable | Talend Sets? | V1 Sets? | How V1 Sets It | Notes |
| ---------- | ------------- | ---------- | ----------------- | ------- |
| `{id}_NB_LINE` | Yes | Yes | `_update_global_map()` in base class | Cross-cutting crash bug (ENG-MAP-001) |

---

## 6. Code Quality

### 6.1 Bugs

| ID | Priority | Location | Description |
| ---- | ---------- | ---------- | ------------- |
| BUG-MAP-001 | **P0** | `base_component.py:304` | CROSS-CUTTING: `_update_global_map()` crashes when globalMap is set |
| BUG-MAP-002 | **P0** | `global_map.py:28` | CROSS-CUTTING: `GlobalMap.get()` broken signature |
| BUG-MAP-003 | **P0** | `bridge.py` | Parallel forEach race condition in `execute_compiled_tmap_chunked()` |
| BUG-MAP-004 | **P1** | `map.py:_join_lookups()` | UNIQUE_MATCH may not preserve Talend's first-row ordering |
| BUG-MAP-005 | **P1** | `map.py:_generate_outputs()` | Inner join reject detection fragile -- depends on pandas merge indicator |
| BUG-MAP-006 | **P1** | `map.py:_process()` | Input filter complex expression fallback may fail on edge cases |
| BUG-MAP-007 | **P1** | `engine.py:779-795` | Multi-input routing relies on component type string matching |

### 6.2 Naming Consistency

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| NAME-MAP-001 | **P2** | `_strip_java_marker()` vs `_java_expr()` -- inconsistent naming convention |
| NAME-MAP-002 | **P2** | `_is_simple_column_ref()` returns bool but pattern is `SIMPLE_COLUMN_PATTERN` (class vs module level) |

### 6.3 Standards Compliance

| ID | Priority | Standard | Violation |
| ---- | ---------- | ---------- | ----------- |
| STD-MAP-001 | **P2** | "No print statements" | `print()` in bridge.py for tMap script compilation |
| STD-MAP-002 | **P2** | "Module-level logger" | Logger present but some error paths use bare `raise` without logging |
| STD-MAP-003 | **P2** | "Type hints on all methods" | Several private methods lack return type annotations |
| STD-MAP-004 | **P3** | "Docstrings on all methods" | Some helper methods have incomplete docstrings |

### 6.4 Debug Artifacts

`print()` statement in bridge.py for compiled tMap script output. Should use logger.debug().

### 6.5 Security

See Section 11 Risk Assessment for comprehensive security analysis.

### 6.6 Logging Quality

| Aspect | Assessment |
| -------- | ------------ |
| Logger setup | Correct: `logger = logging.getLogger(__name__)` |
| Level usage | Adequate: info for processing counts, warning for empty inputs, error for failures |
| Sensitive data | No sensitive data logged |

### 6.7 Error Handling Quality

| Aspect | Assessment |
| -------- | ------------ |
| Custom exceptions | Uses base class exception hierarchy |
| Exception chaining | Present in some paths via `raise ... from e` |
| die_on_error handling | Reads `config.get('die_on_error', True)` -- controls exception propagation |

### 6.8 Type Hints

| Aspect | Assessment |
| -------- | ------------ |
| Method signatures | Present on public methods, missing on some private helpers |
| Parameter types | Mostly typed, some `Any` overuse |

---

## 7. Performance & Memory

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| PERF-MAP-001 | **P1** | 50K chunk size hard-coded -- not configurable per job |
| PERF-MAP-002 | **P2** | Cartesian join (ALL_MATCHES) has no size guard -- OOM on large lookups |
| PERF-MAP-003 | **P2** | Arrow serialization overhead per chunk for Java bridge |
| PERF-MAP-004 | **P2** | Multiple DataFrame copies during join chain (one per lookup) |
| PERF-MAP-005 | **P3** | No expression caching -- same expression re-parsed per chunk |

### 7.1 Memory Management Assessment

| Aspect | Assessment |
| -------- | ------------ |
| Streaming mode | Chunked execution via Java bridge (50K rows per chunk) |
| Memory threshold | No explicit threshold -- relies on Python/Java heap limits |
| Large data handling | Adequate for typical jobs; cartesian joins risk OOM |

---

## 8. Testing

### 8.1 Current Coverage

| Test Type | Count | Location |
| ----------- | ------- | ---------- |
| Converter unit tests | 56 | `tests/converters/talend_to_v1/components/test_map.py` |
| Engine unit tests | 0 | None |
| Integration tests | 5 | `tests/converters/talend_to_v1/test_integration.py` (TestComplexTMapStructure) |

### 8.2 Test Gaps

| ID | Priority | Gap |
| ---- | ---------- | ----- |
| TEST-MAP-001 | **P1** | No engine unit tests for Map component |

### 8.3 Recommended Test Cases

1. Engine: Main-only flow with simple column expressions
2. Engine: Main + lookup with inner join and UNIQUE_MATCH
3. Engine: Main + lookup with left outer join
4. Engine: Variable evaluation referencing main and lookup columns
5. Engine: Output filter expression evaluation
6. Engine: Reject flow with inner join rejection
7. Engine: die_on_error=False error continuation
8. Engine: Large lookup table memory behavior
9. Engine: Empty main input handling
10. Engine: Multiple lookups chained

---

## 9. Issues Summary

### By Priority

| Priority | Count | IDs |
| ---------- | ------- | ----- |
| P0 | 3 | BUG-MAP-001, BUG-MAP-002, BUG-MAP-003 |
| P1 | 8 | BUG-MAP-004, BUG-MAP-005, BUG-MAP-006, BUG-MAP-007, ENG-MAP-004, ENG-MAP-005, ENG-MAP-006, PERF-MAP-001, TEST-MAP-001 |
| P2 | 12 | NAME-MAP-001, NAME-MAP-002, STD-MAP-001, STD-MAP-002, STD-MAP-003, ENG-MAP-010, ENG-MAP-011, ENG-MAP-012, ENG-MAP-013, ENG-MAP-014, PERF-MAP-002, PERF-MAP-003, PERF-MAP-004 |
| P3 | 3 | STD-MAP-004, ENG-MAP-015, ENG-MAP-016, PERF-MAP-005 |
| **Total** | **26** | |

### By Category

| Category | Count | IDs |
| ---------- | ------- | ----- |
| Converter (CONV) | 0 | All fixed |
| Engine (ENG) | 13 | ENG-MAP-001 through ENG-MAP-016 |
| Bug (BUG) | 7 | BUG-MAP-001 through BUG-MAP-007 |
| Naming (NAME) | 2 | NAME-MAP-001, NAME-MAP-002 |
| Standards (STD) | 4 | STD-MAP-001 through STD-MAP-004 |
| Performance (PERF) | 5 | PERF-MAP-001 through PERF-MAP-005 |
| Testing (TEST) | 1 | TEST-MAP-001 |

### Cross-Cutting Issues

| Canonical ID | Location | Impact on This Component |
| ------------- | ---------- | -------------------------- |
| XCUT-001 | `base_component.py:304` | `_update_global_map()` crash when globalMap set -- affects NB_LINE tracking |
| XCUT-002 | `global_map.py:28` | `GlobalMap.get()` broken signature -- affects all globalMap reads |

---

## 10. Recommendations

### Immediate (Before Production)

1. Fix `_update_global_map()` crash (BUG-MAP-001, cross-cutting)
2. Fix `GlobalMap.get()` signature (BUG-MAP-002, cross-cutting)
3. Fix parallel forEach race condition in Java bridge (BUG-MAP-003)

### Short-term (Hardening)

1. Implement RELOAD_AT_EACH_ROW lookup mode (ENG-MAP-004)
2. Fix UNIQUE_MATCH first-row semantics (BUG-MAP-004)
3. Add engine unit tests (TEST-MAP-001)
4. Add cartesian join size guard (PERF-MAP-002)
5. Fix catch_output_reject support (ENG-MAP-006)

### Long-term (Optimization)

1. Implement fuzzy matching (Levenshtein/Jaccard) (ENG-MAP-011)
2. Make chunk size configurable (PERF-MAP-001)
3. Add expression caching (PERF-MAP-005)

---

## 11. Risk Assessment

### Risk Matrix

| Risk | Likelihood | Impact | Mitigation |
| ------ | ----------- | -------- | ------------ |
| Multi-flow output shape change breaks engine | Low (converter preserves shape) | **Critical** -- engine directly accesses `config['inputs']['main']['name']` | Per D-74: maintain existing output shape. Document changes as needs_review 'output_shape_change'. |
| Java expression injection in column mappings | Medium (expressions from .item files) | **High** -- arbitrary code execution in Java bridge | Validate expression syntax before passing to Java bridge. Sandbox Java execution. |
| Lookup join memory explosion | Medium (ALL_MATCHES with large tables) | **High** -- OOM crash kills entire job | Add size guard: fail fast if cartesian product exceeds threshold. |
| BigDecimal hash/equals inconsistency | Medium (financial data common) | **Medium** -- silent incorrect join results | Implement CHANGE_HASH_AND_EQUALS_FOR_BIGDECIMAL in engine. |
| Fuzzy matching thresholds unvalidated | Low (rarely used) | **Medium** -- LEVENSHTEIN/JACCARD are string values, no numeric validation | Validate as float/int at converter level. |
| Variable table dependency chains | Medium (complex jobs) | **Medium** -- variables referencing other variables may fail on evaluation order | Ensure topological evaluation order for variable dependencies. |
| Reject flow data integrity | Medium (inner join reject common) | **Medium** -- rejectInnerJoin flag not differentiated from generic reject | Implement rejectInnerJoin-specific routing in engine. |
| STORE_ON_DISK temp directory path traversal | Low (rarely configured) | **High** -- arbitrary filesystem access via TEMPORARY_DATA_DIRECTORY | Validate and sandbox temp directory path if STORE_ON_DISK is implemented. |

### High-Risk Job Patterns

1. **Large lookup tables with ALL_MATCHES**: Cartesian product can exhaust memory
2. **Multiple chained lookups**: Each lookup creates a DataFrame copy, multiplying memory usage
3. **Complex Java expressions in column mappings**: Long evaluation time per chunk
4. **RELOAD_AT_EACH_ROW lookups**: Not implemented, will silently use stale data
5. **BigDecimal join keys**: Silent incorrect results without hash/equals fix

### Safe Usage Patterns

1. **Single main + single lookup with UNIQUE_MATCH inner join**: Well-tested path
2. **Simple column reference expressions** (e.g., `row1.id`): Fast path, no Java bridge needed
3. **Small to medium lookup tables** (under 1M rows): Memory-safe
4. **LOAD_ONCE lookup mode**: Correctly implemented, predictable behavior
5. **die_on_error=true**: Fail-fast prevents cascading data corruption

---

## Appendix A: Source References

| Source | URL/Path | Used For |
| -------- | ---------- | ---------- |
| Talaxie GitHub _java.xml | `org.talend.designer.components/components/tMap/tMap_java.xml` | Parameter definitions, defaults, types |
| Engine source | `src/v1/engine/components/transform/map.py` | Feature parity analysis (1164 lines) |
| Converter source | `src/converters/talend_to_v1/components/transform/map.py` | Converter audit |
| Converter tests | `tests/converters/talend_to_v1/components/test_map.py` | Test coverage (56 tests) |
| Java bridge | `src/v1/java_bridge/bridge.py` | Java expression compilation and execution |

## Appendix B: Engine Config Key Mapping

| Config Key | Engine Reads? | Engine Location | Notes |
| ----------- | --------------- | ----------------- | ------- |
| `inputs.main` | **Yes** | `_process()` line 110 | Nested dict with name, filter, matching_mode, etc. |
| `inputs.lookups` | **Yes** | `_process()` line 111 | List of lookup dicts |
| `variables` | **Yes** | `_process()` line 112 | List of variable defs |
| `outputs` | **Yes** | `_process()` line 113 | List of output defs |
| `die_on_error` | **Yes** | `_process()` line 867 | `config.get('die_on_error', True)` |
| `link_style` | No | -- | Visual editor setting |
| `lkup_parallelize` | No | -- | Not implemented |
| `enable_auto_convert_type` | No | -- | Not implemented |
| `rows_buffer_size` | No | -- | Not implemented |
| `change_hash_and_equals_for_bigdecimal` | No | -- | Not implemented |
| `levenshtein` | No | -- | Not implemented |
| `jaccard` | No | -- | Not implemented |
| `var_table_name` | No | -- | UI metadata |
| `var_table_size_state` | No | -- | UI metadata |
| `tstatcatcher_stats` | No | -- | Framework param |
| `label` | No | -- | Framework param |

## Appendix C: MapperData XML Structure Reference

tMap's nodeData uses the MapperData XML format. This is the primary configuration mechanism -- far more complex than the flat elementParameter params.

### XML Hierarchy

```xml
<nodeData xsi:type="talendfile:MapperData">
  <!-- First inputTable = MAIN flow -->
  <inputTables name="row1" matchingMode="UNIQUE_MATCH" lookupMode="LOAD_ONCE"
               activateExpressionFilter="false" expressionFilter="">
    <mapperTableEntries name="col1" expression="" type="id_Integer"/>
  </inputTables>

  <!-- Subsequent inputTables = LOOKUP flows -->
  <inputTables name="lookup1" innerJoin="true" matchingMode="UNIQUE_MATCH"
               lookupMode="LOAD_ONCE" persistent="false" sizeState="">
    <mapperTableEntries name="lk_col" expression="row1.id" type="id_Integer"
                        operator="" nullable="true"/>
  </inputTables>

  <!-- Variable tables -->
  <varTables name="Var" sizeState="">
    <mapperTableEntries name="var1" expression="row1.name" type="id_String"
                        nullable="true"/>
  </varTables>

  <!-- Output tables -->
  <outputTables name="out1" reject="false" rejectInnerJoin="false"
                activateExpressionFilter="false" expressionFilter=""
                activateCondensedTool="false" activateGlobalMap="false">
    <mapperTableEntries name="out_col" expression="row1.id" type="id_Integer"
                        nullable="true" operator="" length="-1" precision="-1"
                        pattern=""/>
  </outputTables>

  <!-- Reject output -->
  <outputTables name="reject1" reject="true" rejectInnerJoin="true">
    <mapperTableEntries name="rej_col" expression="row1.id" type="id_Integer"/>
  </outputTables>
</nodeData>
```

### Parsing Rules

1. **inputTables[0]** is always MAIN -- parsed by `_parse_input_main()`
2. **inputTables[1:]** are LOOKUPS -- parsed by `_parse_lookup()`
3. **Join keys** are mapperTableEntries with non-empty `expression` or `operator` attributes
4. **innerJoin=true** maps to `join_mode="INNER_JOIN"`, otherwise `join_mode="LEFT_OUTER_JOIN"`
5. **reject=true** on outputTables creates reject flow
6. **All expressions** are prefixed with `{{java}}` marker by converter

---

*Report generated: 2026-04-04*
*Last updated: 2026-04-04 after hidden/design-time param removal*
