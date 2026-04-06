# Audit Report: tAggregateSortedRow / AggregateSortedRow

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
| **Talend Name** | `tAggregateSortedRow` |
| **V1 Engine Class** | `AggregateSortedRow` |
| **Engine File** | `src/v1/engine/components/transform/aggregate_sorted_row.py` (413 lines) |
| **Converter Parser** | `src/converters/talend_to_v1/components/transform/aggregate_sorted_row.py` (232 lines) |
| **Converter Dispatch** | `@REGISTRY.register("tAggregateSortedRow")` decorator-based dispatch |
| **Registry Aliases** | `AggregateSortedRow`, `tAggregateSortedRow` |
| **Category** | Transform / Aggregation |
| **Issue ID Prefix** | `{CATEGORY}-ASR-{NUMBER}` |

### Key Files

| File | Purpose |
| ------ | --------- |
| `src/v1/engine/components/transform/aggregate_sorted_row.py` | Engine implementation (413 lines) |
| `src/converters/talend_to_v1/components/transform/aggregate_sorted_row.py` | Converter class (232 lines) |
| `tests/converters/talend_to_v1/components/test_aggregate_sorted_row.py` | Converter tests (31 tests) |
| `src/v1/engine/base_component.py` | Base class |
| `src/v1/engine/global_map.py` | GlobalMap storage |

---

## 2. Scorecard

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
| ----------- | ------- | ---- | ---- | ---- | ---- | --------- |
| Converter Coverage | **G** | 0 | 0 | 0 | 0 | 3 unique + 2 framework params (100%); GROUPBYS stride-2, OPERATIONS stride-4 state-machine parser; function mapping (distinct->count_distinct, list_object->list); 1 static + 2 conditional needs_review |
| Engine Feature Parity | **Y** | 0 | 3 | 3 | 1 | No sorted-input streaming optimization; IGNORE_NULL not supported; group-by column renaming not supported; function mapping gaps (list_object, distinct handled at converter level) |
| Code Quality | **G** | 0 | 0 | 1 | 1 | Well-structured state-machine parser; comprehensive docstring; clean separation of TABLE parsing at module level; minor: 95% duplication with AggregateRow engine |
| Performance & Memory | **Y** | 0 | 1 | 1 | 0 | No streaming aggregation (O(N) memory vs Talend O(1) for sorted input); multiple groupby passes |
| Testing | **Y** | 0 | 0 | 1 | 0 | 31 converter tests across 9 classes; engine unit tests missing per D-89 |

**Overall: Y (Yellow) -- Converter is Gold standard. Engine has feature gaps (no sorted-stream optimization, no IGNORE_NULL) but core aggregation logic works correctly.**

**Top Actions**:

1. Add engine IGNORE_NULL support (per-operation null handling)
2. Optimize engine for sorted-input streaming (O(1) memory)
3. Add engine unit tests for aggregation edge cases

---

## 3. Talend Feature Baseline

### What tAggregateSortedRow Does

`tAggregateSortedRow` performs aggregation operations (sum, count, min, max, avg, etc.) on input data that is already sorted by the group-by columns. It is functionally equivalent to `tAggregateRow` but is optimized for pre-sorted input -- it can process data in a single pass with O(1) memory per group, emitting aggregated rows as each group boundary is crossed.

The component requires input data to be pre-sorted by the group-by columns (typically via `tSortRow` upstream). If input is not sorted, results will be incorrect -- groups may be split across non-contiguous rows, producing multiple partial aggregations instead of one complete aggregation per group.

Typical use cases include aggregating large sorted datasets where memory efficiency matters, computing running totals or group statistics on pre-sorted streams, and summarizing data after a sort operation.

**Source**: Talaxie GitHub _java.xml (primary), Talend documentation
**Component family**: Processing / Aggregation
**Available in**: Talend Open Studio, Talend Data Integration
**Required JARs**: None (built-in)

### 3.1 Basic Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
| --- | ----------- | ----------------- | ------ | --------- | ------------- |
| 1 | Schema | `SCHEMA` | SCHEMA | -- | Input/output schema definition (handled by framework) |
| 2 | Group-by columns | `GROUPBYS` | TABLE (stride-2) | [] | Columns to group by. Each row has OUTPUT_COLUMN (output name) and INPUT_COLUMN (source column name) |
| 3 | Operations | `OPERATIONS` | TABLE (stride-4) | [] | Aggregation operations. Each row has OUTPUT_COLUMN, INPUT_COLUMN, FUNCTION, and optional IGNORE_NULL |
| 4 | Row count | `ROW_COUNT` | TEXT | "" | Number of rows to process (expression-capable). Empty means process all rows |
| 5 | Note/Label | `LABEL` | TEXT | "" | User-defined label for the component |
| 6 | tStatCatcher | `TSTATCATCHER_STATS` | CHECK | false | Enable statistics collection |

### 3.2 Advanced Settings

None documented in _java.xml.

### 3.3 Connection Types

| Connector | Direction | Type | Description |
| ----------- | ----------- | ------ | ------------- |
| `FLOW` (Main) | Input | Row > Main | Pre-sorted input data |
| `FLOW` (Main) | Output | Row > Main | Aggregated output rows |
| `REJECT` | Output | Row > Reject | Rejected rows (not implemented in engine) |
| `SUBJOB_OK` | Output (Trigger) | Trigger | Fires after successful completion |
| `SUBJOB_ERROR` | Output (Trigger) | Trigger | Fires on error |

### 3.4 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
| ------------------ | ------ | ---------- | ------------- |
| `{id}_NB_LINE` | Integer | After execution | Total rows processed |
| `{id}_NB_LINE_OK` | Integer | After execution | Rows successfully aggregated |
| `{id}_NB_LINE_REJECT` | Integer | After execution | Rows rejected (always 0 in v1) |

### 3.5 Behavioral Notes

1. **Pre-sorted input required**: Unlike tAggregateRow, tAggregateSortedRow assumes input is sorted by group-by columns. Unsorted input produces incorrect results (split groups).
2. **ROW_COUNT is TEXT type**: Supports expressions (e.g., `context.limit`), not just integer literals. Empty string means process all rows.
3. **IGNORE_NULL is optional**: Not all OPERATIONS entries include IGNORE_NULL. The state-machine parser handles this gracefully.
4. **Function mapping**: `distinct` maps to `count_distinct`, `list_object` maps to `list` (with lossy-mapping warning).
5. **GROUPBYS OUTPUT_COLUMN renaming**: Talend supports different output and input column names in group-by. The v1 engine does not support this renaming.

---

## 4. Converter Audit

### 4.1 Parameter Extraction

The converter uses `@REGISTRY.register("tAggregateSortedRow")` for dispatch. GROUPBYS TABLE is parsed with stride-2 into list of `{output_column, input_column}` dicts. OPERATIONS TABLE uses a state-machine parser (flush-on-OUTPUT_COLUMN) for robustness with optional IGNORE_NULL. Function names are mapped via `_FUNCTION_MAP`. ROW_COUNT extracted as str (TEXT type). Phantom params DIE_ON_ERROR and CONNECTION_FORMAT excluded.

| # | Talend XML Parameter | Extracted? | V1 Config Key | Notes |
| ---- | ---------------------- | ------------ | --------------- | ------- |
| 1 | `GROUPBYS` | Yes | `groupbys` | TABLE stride-2 -> list of {output_column, input_column} dicts |
| 2 | `OPERATIONS` | Yes | `operations` | TABLE stride-4 state-machine -> list of {output_column, input_column, function, ignore_null} dicts |
| 3 | `ROW_COUNT` | Yes | `row_count` | TEXT type, _get_str, default "" |
| 4 | `TSTATCATCHER_STATS` | Yes | `tstatcatcher_stats` | bool, default False |
| 5 | `LABEL` | Yes | `label` | str, default "" |

**Summary**: 3 of 3 unique parameters extracted (100%), plus 2 framework params.

### 4.2 Schema Extraction

| Schema Attribute | Extracted? | Notes |
| ------------------ | ----------- | ------- |
| `name` | Yes | Via `_parse_schema()` |
| `type` | Yes | Converted via `convert_type()` |
| `nullable` | Yes | Direct extraction |
| `key` | Yes | Direct extraction |
| `length` | Yes | Only when >= 0 |
| `precision` | Yes | Only when >= 0 |
| `pattern` | Yes | Java-to-Python date pattern conversion |
| `default` | No | Not supported by base class |

### 4.3 Expression Handling

ROW_COUNT is extracted as a string to preserve expression references (e.g., `context.limit`). No other expression-capable parameters exist for this component.

### 4.4 Converter Issues

All converter issues have been resolved in the gold-standard rewrite:

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| CONV-ASR-001 | ~~P1~~ | **FIXED** -- Phantom DIE_ON_ERROR and CONNECTION_FORMAT removed |
| CONV-ASR-002 | ~~P1~~ | **FIXED** -- Function mapping: distinct->count_distinct, list_object->list |
| CONV-ASR-003 | ~~P2~~ | **FIXED** -- GROUPBYS parsed as stride-2 list of dicts (not flat list) |
| CONV-ASR-004 | ~~P2~~ | **FIXED** -- Uses _build_component_dict with type_name="AggregateSortedRow" |
| CONV-ASR-005 | ~~P2~~ | **FIXED** -- ROW_COUNT extracted as str (TEXT type) |

### 4.5 Needs Review Entries

| # | Config Key | Reason | Severity |
| --- | ----------- | -------- | ---------- |
| 1 | `row_count` | Engine does not read row_count config key -- processes all rows regardless | engine_gap |
| 2 | GROUPBYS renaming | Engine does not support group-by column renaming (conditional: only emitted when OUTPUT_COLUMN differs from INPUT_COLUMN) | engine_gap |
| 3 | `ignore_null` | Engine ignores per-operation ignore_null flag -- always uses pandas skipna=True (conditional: only emitted when ignore_null present in operations) | engine_gap |

---

## 5. Engine Feature Parity

### 5.1 Feature Implementation Status

| # | Talend Feature | Implemented? | Fidelity | Engine Location | Notes |
| ---- | ---------------- | ------------- | ---------- | ----------------- | ------- |
| 1 | Group-by aggregation | **Yes** | High | `_aggregate_grouped()` line 219 | Core groupby logic via pandas |
| 2 | Ungrouped aggregation | **Yes** | High | `_aggregate_all()` line 197 | Aggregates entire dataset when no group_bys |
| 3 | sum function | **Yes** | High | `_apply_agg_function()` line 383 | With Decimal precision support |
| 4 | count function | **Yes** | High | line 289 | Via pandas count |
| 5 | min/max functions | **Yes** | High | lines 389-391 | Direct pandas |
| 6 | avg function | **Yes** | Medium | line 278 | Maps to pandas mean |
| 7 | count_distinct function | **Yes** | High | line 293 | Maps to pandas nunique |
| 8 | first/last functions | **Yes** | Medium | line 299 | Via iloc[0]/iloc[-1] -- not identical to Talend streaming semantics |
| 9 | list function | **Yes** | High | line 308 | Via pandas apply(list) |
| 10 | concat/concatenate | **Yes** | High | line 310 | With configurable delimiter |
| 11 | IGNORE_NULL | **No** | N/A | -- | Engine always uses pandas default skipna=True |
| 12 | Sorted-input optimization | **No** | N/A | -- | Engine loads all data into memory regardless of sort order |
| 13 | REJECT flow | **No** | N/A | -- | No reject output support |
| 14 | row_count limit | **No** | N/A | -- | Engine processes all rows |
| 15 | Group-by renaming | **No** | N/A | -- | Engine reads group_bys as flat column name list |
| 16 | Decimal precision | **Partial** | Medium | line 251 | Decimal sum supported; avg/mean loses Decimal precision |

### 5.2 Behavioral Differences from Talend

| ID | Priority | Description |
| ---- | ---------- | ------------- |
| ENG-ASR-001 | **P1** | Engine does not support IGNORE_NULL flag -- always skips nulls via pandas default skipna=True. When ignore_null=false, Talend includes nulls in aggregation; engine incorrectly skips them. |
| ENG-ASR-002 | **P1** | No sorted-input streaming optimization. Talend processes sorted data in O(1) memory per group; engine loads entire dataset into memory (O(N)). |
| ENG-ASR-003 | **P1** | Engine does not support group-by column renaming -- reads group_bys as flat list of column names. OUTPUT_COLUMN different from INPUT_COLUMN silently ignored. |
| ENG-ASR-004 | **P2** | No REJECT flow support. Talend can route rejected rows; engine has no reject mechanism. |
| ENG-ASR-005 | **P2** | row_count config key not read. Engine processes all rows regardless of limit. |
| ENG-ASR-006 | **P2** | Decimal precision lost for avg/mean in ungrouped path -- converts to float64. |
| ENG-ASR-007 | **P3** | first/last semantics differ from Talend streaming: Talend emits first/last value seen in sorted stream; engine uses iloc[0]/iloc[-1] on grouped DataFrame which is functionally equivalent for sorted input but semantically different. |

### 5.3 GlobalMap Variable Coverage

| Variable | Talend Sets? | V1 Sets? | How V1 Sets It | Notes |
| ---------- | ------------- | ---------- | ----------------- | ------- |
| `{id}_NB_LINE` | Yes | Yes | `_update_stats()` line 111 | Total input rows |
| `{id}_NB_LINE_OK` | Yes | Yes | `_update_stats()` line 176 | Output rows |
| `{id}_NB_LINE_REJECT` | Yes | Yes | `_update_stats()` line 176 | Always 0 (no reject flow) |

---

## 6. Code Quality

### 6.1 Bugs

| ID | Priority | Location | Description |
| ---- | ---------- | ---------- | ------------- |
| BUG-ASR-001 | **P2** | `aggregate_sorted_row.py:129` | If group_bys list is empty (not None), engine raises ValueError("GROUPBYS configuration is required") even though Talend allows empty group_bys for whole-dataset aggregation |

### 6.2 Naming Consistency

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| NAME-ASR-001 | **P3** | Engine reads `group_bys` and `GROUPBYS` (dual key support), creating config key ambiguity |

### 6.3 Standards Compliance

No standards violations found.

### 6.4 Debug Artifacts

None found.

### 6.5 Security

No concerns identified. Component processes in-memory data without external I/O.

### 6.6 Logging Quality

| Aspect | Assessment |
| -------- | ------------ |
| Logger setup | Good -- module-level `logger = logging.getLogger(__name__)` |
| Level usage | Good -- info for start/complete, warning for edge cases, error for failures |
| Sensitive data | No concerns -- logs column names and counts only |

### 6.7 Error Handling Quality

| Aspect | Assessment |
| -------- | ------------ |
| Custom exceptions | None -- uses ValueError |
| Exception chaining | Not used |
| die_on_error handling | Good -- raises on error when True, returns raw input when False |

### 6.8 Type Hints

| Aspect | Assessment |
| -------- | ------------ |
| Method signatures | Good -- all methods typed |
| Parameter types | Good -- Dict, List, Optional used correctly |

---

## 7. Performance & Memory

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| PERF-ASR-001 | **P1** | No streaming aggregation: Talend tAggregateSortedRow processes sorted input in O(1) memory per group (streaming window); engine loads entire dataset into memory via pandas groupby. For large sorted datasets this defeats the purpose of using tAggregateSortedRow over tAggregateRow. |
| PERF-ASR-002 | **P2** | Multiple groupby passes: custom aggregations (list, concat, decimal_sum) each perform a separate groupby + merge operation. For N custom aggregations, this is O(N) groupby passes. |

### 7.1 Memory Management Assessment

| Aspect | Assessment |
| -------- | ------------ |
| Streaming mode | Not implemented -- engine does full-dataset pandas groupby |
| Memory threshold | No limit -- entire input held in memory |
| Large data handling | Potential OOM for large sorted datasets that Talend handles in O(1) memory |

---

## 8. Testing

### 8.1 Current Coverage

| Test Type | Count | Location |
| ----------- | ------- | ---------- |
| Converter unit tests | 31 | `tests/converters/talend_to_v1/components/test_aggregate_sorted_row.py` |
| Engine unit tests | 0 | None |
| Integration tests | 0 | None (covered by regression guard) |

### 8.2 Test Gaps

| ID | Priority | Gap |
| ---- | ---------- | ----- |
| TEST-ASR-001 | **P2** | No engine unit tests for aggregation logic, edge cases (empty input, single-row groups, all-null columns, unsorted input) |

### 8.3 Recommended Test Cases

1. Engine: empty DataFrame input (0 rows)
2. Engine: single-row groups (each row is its own group)
3. Engine: all-null column with various aggregation functions
4. Engine: unsorted input detection or degraded behavior documentation
5. Engine: Decimal precision for sum vs avg
6. Engine: count_distinct with null values
7. Engine: list function with mixed types
8. Engine: die_on_error=True vs False error paths
9. Engine: IGNORE_NULL=false behavior (currently broken)

---

## 9. Issues Summary

### By Priority

| Priority | Count | IDs |
| ---------- | ------- | ----- |
| P0 | 0 | -- |
| P1 | 3 | **ENG-ASR-001**, **ENG-ASR-002**, **ENG-ASR-003**, **PERF-ASR-001** |
| P2 | 5 | **ENG-ASR-004**, **ENG-ASR-005**, **ENG-ASR-006**, **BUG-ASR-001**, **PERF-ASR-002**, **TEST-ASR-001** |
| P3 | 2 | **ENG-ASR-007**, **NAME-ASR-001** |
| **Total** | **10** | |

### By Category

| Category | Count | IDs |
| ---------- | ------- | ----- |
| Converter (CONV) | 0 | All FIXED (5 resolved) |
| Engine (ENG) | 7 | ENG-ASR-001 through ENG-ASR-007 |
| Bug (BUG) | 1 | BUG-ASR-001 |
| Naming (NAME) | 1 | NAME-ASR-001 |
| Standards (STD) | 0 | -- |
| Performance (PERF) | 2 | PERF-ASR-001, PERF-ASR-002 |
| Testing (TEST) | 1 | TEST-ASR-001 |

### Cross-Cutting Issues

| Canonical ID | Location | Impact on This Component |
| ------------- | ---------- | -------------------------- |
| XCUT-001 | `base_component.py:304` | `_update_global_map()` crash when globalMap set |
| XCUT-002 | `base_component.py` | HYBRID streaming mode not supported (component is stateful) |

---

## 10. Recommendations

### Immediate (Before Production)

No P0 issues. Component is usable for typical aggregation workloads.

### Short-term (Hardening)

1. **ENG-ASR-001**: Implement per-operation IGNORE_NULL support (P1)
2. **ENG-ASR-002 / PERF-ASR-001**: Add sorted-input streaming aggregation for O(1) memory (P1)
3. **ENG-ASR-003**: Support group-by column renaming (OUTPUT_COLUMN != INPUT_COLUMN) (P1)
4. **ENG-ASR-004**: Add REJECT flow support (P2)
5. **ENG-ASR-005**: Read and enforce row_count limit (P2)
6. **TEST-ASR-001**: Add comprehensive engine unit tests (P2)

### Long-term (Optimization)

1. **ENG-ASR-007**: Align first/last semantics with Talend streaming model (P3)
2. **NAME-ASR-001**: Consolidate dual config key support to single key (P3)

---

## 11. Risk Assessment

### Risk Matrix

| Risk | Likelihood | Impact | Mitigation |
| ------ | ----------- | -------- | ------------ |
| **Incorrect results on unsorted input** | Medium | High | Engine does not validate input sort order. If upstream sort is missing or incorrect, groups will be split, producing multiple partial aggregations per logical group. Add sort-order validation or warning. |
| **Memory exhaustion on large sorted datasets** | Medium | High | Engine loads entire dataset into memory via pandas groupby, defeating the O(1) memory advantage of sorted-input aggregation. For datasets that exceed memory, use tAggregateRow or add streaming implementation. |
| **Silent data loss with IGNORE_NULL=false** | Low | High | When IGNORE_NULL=false, Talend includes null values in aggregation (e.g., sum includes null as 0). Engine always skips nulls (pandas skipna=True), silently producing different results. Affects financial calculations where null represents zero. |
| **Incorrect count_distinct with nulls** | Low | Medium | pandas nunique() excludes NaN by default. Talend count_distinct may include null as a distinct value depending on database behavior. |
| **Function mapping completeness** | Low | Medium | Converter maps distinct->count_distinct and list_object->list. Unknown functions pass through as-is. If engine encounters an unmapped function, it falls through to sum as default (line 413), silently producing incorrect results. |
| **Group-by renaming silently ignored** | Low | Medium | When GROUPBYS OUTPUT_COLUMN differs from INPUT_COLUMN, engine ignores the renaming. Output column names will not match Talend expectations. needs_review entry emitted by converter. |
| **Empty group-by with operations fails** | Low | Low | Engine raises ValueError for empty group_bys even though Talend supports whole-dataset aggregation with empty group-by list. Workaround: ensure at least one group-by column. |

### High-Risk Job Patterns

1. Jobs relying on IGNORE_NULL=false for null-inclusive aggregation (financial totals)
2. Jobs with large sorted datasets expecting O(1) memory consumption
3. Jobs using GROUP_BY column renaming (OUTPUT_COLUMN != INPUT_COLUMN)
4. Jobs without upstream tSortRow (unsorted input producing split groups)
5. Jobs using unknown/custom aggregate functions (silent fallback to sum)

### Safe Usage Patterns

1. Pre-sorted input with standard aggregate functions (sum, count, min, max, avg)
2. Small-to-medium datasets that fit in memory
3. Group-by columns with same output and input names
4. IGNORE_NULL=true (matches engine default behavior)
5. Standard functions only: sum, count, min, max, avg, first, last, list, count_distinct

---

## Appendix A: Source References

| Source | URL/Path | Used For |
| -------- | ---------- | ---------- |
| Talaxie GitHub _java.xml | `<https://github.com/nicco/talaxie/blob/master/main/plugins/org.talend.designer.components.localprovider/components/tAggregateSortedRow/tAggregateSortedRow_java.xml`> | Parameter definitions, defaults, TABLE structures |
| Engine source | `src/v1/engine/components/transform/aggregate_sorted_row.py` (413 lines) | Feature parity analysis, code quality review |
| Converter source | `src/converters/talend_to_v1/components/transform/aggregate_sorted_row.py` (232 lines) | Converter audit |
| Converter tests | `tests/converters/talend_to_v1/components/test_aggregate_sorted_row.py` (31 tests) | Test coverage analysis |
| Base class | `src/v1/engine/base_component.py` | Cross-cutting concerns |

## Appendix B: Engine Config Key Mapping

| Converter Config Key | Engine Reads | Match? | Notes |
| --------------------- | ------------- | -------- | ------- |
| `groupbys` (list of dicts) | `group_bys` (list of strings) | No | Converter outputs structured dicts with output_column/input_column; engine expects flat list of column name strings |
| `operations` (list of dicts) | `operations` (list of dicts) | Partial | Converter includes ignore_null; engine ignores it. Converter maps functions; engine reads function names directly. |
| `row_count` | Not read | No | Engine processes all rows regardless |
| `tstatcatcher_stats` | Not read by engine | No | Framework param for statistics collection |
| `label` | Not read by engine | No | Framework param for display |

---

*Report generated: 2026-04-04*
*Last updated: 2026-04-04 after gold-standard rewrite with Section 11 Risk Assessment*
