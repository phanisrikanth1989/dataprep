# Audit Report: tDenormalize / Denormalize

> **Audited**: 2026-04-04
> **Last Updated**: 2026-06-13 -- Phase 13.1 engine hardening (registry fix, merge flag, null-key rows, Rule 12, 41 engine tests)
> **Reconciled**: 2026-05-11
> **Auditor**: Claude Sonnet 4.6 (automated)
> **Engine Version**: v1
> **Converter**: `talend_to_v1`
> **Status**: PRODUCTION READINESS REVIEW
> **V1 only** -- this report contains zero references to v2/PyETL

---

## 1. Component Identity

| Field | Value |
| ------- | ------- |
| **Talend Name** | `tDenormalize` |
| **V1 Engine Class** | `Denormalize` |
| **Engine File** | `src/v1/engine/components/transform/denormalize.py` (238 lines) |
| **Converter Parser** | `src/converters/talend_to_v1/components/transform/denormalize.py` (131 lines) |
| **Converter Dispatch** | `@REGISTRY.register("tDenormalize")` decorator-based dispatch |
| **Registry Aliases** | `Denormalize`, `tDenormalize` |
| **Category** | Processing / Transform |

### Key Files

| File | Purpose |
| ------ | --------- |
| `src/v1/engine/components/transform/denormalize.py` | Engine implementation (238 lines) |
| `src/converters/talend_to_v1/components/transform/denormalize.py` | Converter class (131 lines) |
| `tests/converters/talend_to_v1/components/test_denormalize.py` | Converter tests (26 tests) |
| `src/v1/engine/base_component.py` | Base class |
| `src/v1/engine/global_map.py` | GlobalMap storage |

---

## 2. Scorecard

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
| ----------- | ------- | ---- | ---- | ---- | ---- | --------- |
| Converter Coverage | **G** | 0 | 0 | 0 | 0 | 1 TABLE + 2 framework params extracted (100%). 2 phantom params removed. 2 static + 1 conditional needs_review. |
| Engine Feature Parity | **G** | 0 | 0 | 1 | 1 | ~~ENG-DNR-001~~ FIXED (registry). ~~ENG-DNR-002~~ FIXED (merge flag). ~~ENG-DNR-003~~ FIXED (null-key rows). ENG-DNR-004 (engine delimiter default) P2 open. |
| Code Quality | **G** | 0 | 0 | 0 | 0 | Rule 12 violations fixed. _validate_config returns None. No double validation. No manual _update_stats. %-style logging. |
| Performance & Memory | **G** | 0 | 0 | 1 | 1 | groupby() materializes full copy; closure per column. No P0/P1 issues. |
| Testing | **G** | 0 | 0 | 0 | 0 | 26 converter tests (Green). 41 engine unit tests added (Green). ~~TEST-DNR-001~~ FIXED. |

**Overall:** GREEN -- All P0/P1 issues resolved; converter and engine are production-ready

**Remaining Actions**:

1. ENG-DNR-004 (P2): Engine delimiter default is "," but _java.xml says ";" (converter always emits explicit value, so only affects standalone use)
2. ENG-DNR-005 (P3): Document null_as_empty as engine-specific enhancement

---

## 3. Talend Feature Baseline

### What tDenormalize Does

tDenormalize consolidates multiple rows into single rows by concatenating values from specified columns using configurable delimiters. It groups rows by key columns (all columns NOT in the denormalize list) and joins the values of denormalize columns within each group using the specified delimiter character.

The component is the inverse of tNormalize -- where tNormalize splits delimited strings into multiple rows, tDenormalize merges multiple rows back into delimited strings. A typical use case is aggregating product lists per order: multiple rows of (order_id, product_name) become one row per order_id with a comma-separated product_name list.

**Source**: Talaxie GitHub tDenormalize_java.xml
**Component family**: Processing / Transform
**Available in**: Talend Open Studio, Talend Data Integration
**Required JARs**: None (built-in)

### 3.1 Basic Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
| --- | ----------- | ----------------- | ------ | --------- | ------------- |
| 1 | Denormalize Columns | `DENORMALIZE_COLUMNS` | TABLE (stride-3) | [] | Table of columns to denormalize, each with INPUT_COLUMN, DELIMITER, MERGE |
| 1a | - Input Column | `INPUT_COLUMN` | str (elementRef) | -- | Column name to concatenate |
| 1b | - Delimiter | `DELIMITER` | str (elementRef) | `";"` | Delimiter character for concatenation |
| 1c | - Merge | `MERGE` | bool (elementRef) | `false` | Whether to deduplicate values before concatenation |
| 2 | Note | `NOTE` | LABEL | `""` | Informational label (maps to LABEL framework param) |

### 3.2 Advanced Settings

None defined in _java.xml.

### 3.3 Connection Types

| Connector | Direction | Type | Description |
| ----------- | ----------- | ------ | ------------- |
| `FLOW` (Main) | Input | Row > Main | Input rows to denormalize |
| `FLOW` (Main) | Output | Row > Main | Denormalized output rows (one per key group) |
| `SUBJOB_OK` | Output (Trigger) | Trigger | Fires after successful completion |
| `SUBJOB_ERROR` | Output (Trigger) | Trigger | Fires on error |

### 3.4 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
| ------------------ | ------ | ---------- | ------------- |
| `{id}_NB_LINE` | Integer | After execution | Total rows processed |
| `{id}_NB_LINE_OK` | Integer | After execution | Rows successfully denormalized |
| `{id}_NB_LINE_REJECT` | Integer | After execution | Rows rejected (always 0) |

### 3.5 Behavioral Notes

1. **Delimiter default is semicolon** (";") per _java.xml DEFAULT, not comma. This differs from the engine default of ",".
2. **Merge flag** controls whether duplicate values within a group are deduplicated before concatenation. When merge=true, only unique values appear in the concatenated result.
3. **Key columns** are determined implicitly -- any column NOT in the DENORMALIZE_COLUMNS list is treated as a grouping key.
4. **Row ordering** within groups follows input order. The output row order follows group-first-appearance order.
5. **Null handling** is not configurable via _java.xml. The engine has a `null_as_empty` config key (default False), but this is not a Talend parameter.

---

## 4. Converter Audit

### 4.1 Parameter Extraction

The converter uses a module-level `_parse_denormalize_columns()` function for stride-3 TABLE parsing. Framework params are extracted last via base class helpers. Two phantom params (CONNECTION_FORMAT, NULL_AS_EMPTY) have been removed.

| # | Talend XML Parameter | Extracted? | V1 Config Key | Notes |
| ---- | ---------------------- | ------------ | --------------- | ------- |
| 1 | `DENORMALIZE_COLUMNS` | Yes | `denormalize_columns` | Stride-3 TABLE: INPUT_COLUMN, DELIMITER (default ";"), MERGE (default false) |
| 2 | `NOTE` | N/A | -- | LABEL-type param, informational only |
| 3 | `TSTATCATCHER_STATS` | Yes | `tstatcatcher_stats` | Framework param, default false |
| 4 | `LABEL` | Yes | `label` | Framework param, default "" |
| -- | ~~`CONNECTION_FORMAT`~~ | **REMOVED** | -- | Phantom: not in _java.xml |
| -- | ~~`NULL_AS_EMPTY`~~ | **REMOVED** | -- | Phantom: not in _java.xml (engine-only key) |

**Summary**: 1 of 1 unique parameters extracted (100%) + 2 framework params.

### 4.2 Schema Extraction

| Schema Attribute | Extracted? | Notes |
| ------------------ | ----------- | ------- |
| `name` | Yes | Via `_parse_schema()` |
| `type` | Yes | Talend type converted via `convert_type()` |
| `nullable` | Yes | |
| `key` | Yes | |
| `length` | Yes | When >= 0 |
| `precision` | Yes | When >= 0 |
| `pattern` | Yes | Java-to-Python date pattern conversion |
| `default` | No | Not extracted by base class |

**Schema direction**: Passthrough (input == output) -- transform component.

### 4.3 Expression Handling

No expression parameters. DELIMITER values are string literals. Context variable resolution is not needed at converter level (handled by engine at runtime).

### 4.4 Converter Issues

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| CONV-DNR-001 | ~~P1~~ | **FIXED** -- Dedicated converter now exists (DenormalizeConverter) |
| CONV-DNR-002 | ~~P1~~ | **FIXED** -- merge default corrected to False per _java.xml |
| CONV-DNR-003 | ~~P2~~ | **FIXED** -- Schema passthrough implemented (input == output) |
| CONV-DNR-004 | ~~P2~~ | **FIXED** -- DELIMITER default corrected from "," to ";" per _java.xml |
| CONV-DNR-005 | ~~P2~~ | **FIXED** -- Phantom CONNECTION_FORMAT removed (not in `_java.xml`) |
| CONV-DNR-006 | ~~P2~~ | **FIXED** -- Phantom NULL_AS_EMPTY removed (not in _java.xml) |

### 4.5 Needs Review Entries

| # | Config Key | Reason | Severity |
| --- | ----------- | -------- | ---------- |
| 1 | `delimiter` (engine default) | Engine uses default "," (line 181) but _java.xml DEFAULT is ";" -- converter emits explicit ";" so engine fallback is not reached | engine_gap |
| 2 | `null_as_empty` (engine-only) | Engine reads this key (default False) but it is not a _java.xml parameter | engine_gap |
| 3 | `merge` (conditional) | Engine does not read merge flag -- when merge=True, deduplication will not occur at runtime | engine_gap |

---

## 5. Engine Feature Parity

### 5.1 Feature Implementation Status

| # | Talend Feature | Implemented? | Fidelity | Engine Location | Notes |
| ---- | ---------------- | ------------- | ---------- | ----------------- | ------- |
| 1 | Column concatenation | **Yes** | High | `_process()` | groupby + agg with delimiter join |
| 2 | Per-column delimiter | **Yes** | High | `_process()` | Resolved from config, default "," |
| 3 | Merge (dedup) flag | **Yes** | High | `_process()` | ~~ENG-DNR-002 FIXED~~ -- `make_concat_func(delim, merge)` with first-seen-order dedup |
| 4 | Null handling | **Yes** | Medium | `_process()` | null_as_empty config controls behavior |
| 5 | Key column detection | **Yes** | High | `_process()` | All non-denormalize columns become keys |
| 6 | Schema passthrough | **Yes** | High | -- | Output matches input schema structure |
| 7 | Null-key row preservation | **Yes** | High | `_process()` | ~~ENG-DNR-003 FIXED~~ -- `groupby(dropna=False, sort=False)` |

### 5.2 Behavioral Differences from Talend

| ID | Priority | Description |
| ---- | ---------- | ------------- |
| ~~ENG-DNR-001~~ | ~~P0~~ | **FIXED** -- `@REGISTRY.register("Denormalize", "tDenormalize")` added; correct import path |
| ~~ENG-DNR-002~~ | ~~P1~~ | **FIXED** -- `make_concat_func(delim, merge)` closure implements dedup with first-seen order |
| ~~ENG-DNR-003~~ | ~~P1~~ | **FIXED** -- `groupby(dropna=False, sort=False)` preserves null-key rows as a separate group |
| ENG-DNR-004 | **P2** | **OPEN** -- Engine delimiter default is "," but _java.xml says ";". Converter always emits explicit value; engine standalone use would differ. |
| ENG-DNR-005 | **P3** | **OPEN** -- Engine `null_as_empty` option has no Talend equivalent. This is an engine-specific enhancement. |

### 5.3 GlobalMap Variable Coverage

| Variable | Talend Sets? | V1 Sets? | How V1 Sets It | Notes |
| ---------- | ------------- | ---------- | ----------------- | ------- |
| `{id}_NB_LINE` | Yes | Yes | Base class `_update_global_map()` | NB_LINE = input rows (transform pattern) |
| `{id}_NB_LINE_OK` | Yes | Yes | Base class `_update_global_map()` | NB_LINE_OK = output rows (grouped rows) |
| `{id}_NB_LINE_REJECT` | Yes | Yes | Base class `_update_global_map()` | Always 0 (no reject path) |

---

## 6. Code Quality

### 6.1 Bugs

| ID | Priority | Location | Description |
| ---- | ---------- | ---------- | ------------- |
| -- | -- | -- | None in converter code. Engine bugs listed in Section 5.2. |

### 6.2 Naming Consistency

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| -- | -- | No naming issues. Config keys follow snake_case convention. |

### 6.3 Standards Compliance

All standards met. Engine now follows Rule 12 (no bool/type checks in `_validate_config()`). No double validation. Base class handles stats lifecycle.

### 6.4 Debug Artifacts

None found.

### 6.5 Security

No concerns identified. No exec/eval, no path traversal, no user-supplied code execution.

### 6.6 Logging Quality

| Aspect | Assessment |
| -------- | ------------ |
| Logger setup | Correct: `logger = logging.getLogger(__name__)` at module level |
| Level usage | Engine uses appropriate levels (info/debug/warning/error) |
| Sensitive data | No sensitive data logged |

### 6.7 Error Handling Quality

| Aspect | Assessment |
| -------- | ------------ |
| Custom exceptions | Engine uses ConfigurationError, DataValidationError, ComponentExecutionError |
| Exception chaining | Correct: `raise ... from e` pattern |
| die_on_error handling | Not applicable (no die_on_error in _java.xml) |

### 6.8 Type Hints

| Aspect | Assessment |
| -------- | ------------ |
| Method signatures | Complete type hints on all methods |
| Parameter types | All parameters typed (converter and engine) |

---

## 7. Performance & Memory

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| PERF-DNR-001 | **P2** | groupby() materializes a full copy of the DataFrame. For very large datasets this doubles memory usage. |
| PERF-DNR-002 | **P3** | Closure creation per column in aggregation_dict. Minor overhead, not significant for typical use. |

### 7.1 Memory Management Assessment

| Aspect | Assessment |
| -------- | ------------ |
| Streaming mode | Not supported. Full DataFrame must fit in memory. |
| Memory threshold | ~2x input size during groupby operation |
| Large data handling | Works for typical ETL sizes. Very large datasets (>1GB) may cause memory pressure. |

---

## 8. Testing

### 8.1 Current Coverage

| Test Type | Count | Location |
| ----------- | ------- | ---------- |
| Converter unit tests | 26 | `tests/converters/talend_to_v1/components/test_denormalize.py` |
| Engine unit tests | 41 | `tests/v1/engine/components/transform/test_denormalize.py` |
| Integration tests | 0 | None (covered by regression guard) |

### 8.2 Test Gaps

None. ~~TEST-DNR-001 FIXED~~ -- 41 engine unit tests added.

### 8.3 Engine Test Classes

| Class | Tests | Coverage |
| ------- | ------- | --------- |
| TestRegistration | 4 | REGISTRY._components, both aliases (Denormalize + tDenormalize) |
| TestValidation | 5 | container shape checks, None return, raises ConfigurationError |
| TestDefaults | 3 | passthrough when no denorm_columns |
| TestMainFlow | 8 | groupby, concat, delimiter, multiple cols, missing cols |
| TestMergeFlag | 4 | merge=True dedup, first-seen order |
| TestNullHandling | 3 | null_as_empty True/False |
| TestKeyColumnDetection | 2 | multi-key, column order |
| TestNullKeyRows | 1 | dropna=False preserves null key rows |
| TestEdgeCases | 5 | None/empty input, single row, reject=None, numeric to string |
| TestGlobalMapVariables | 4 | NB_LINE=input_rows, NB_LINE_OK=output_rows, REJECT=0 |
| TestIterateReexecution | 2 | consistent results, accumulating stats (2+6=8) |

---

## 9. Issues Summary

### By Priority

| Priority | Count | IDs |
| ---------- | ------- | ----- |
| P0 | 0 | ~~ENG-DNR-001 FIXED~~ |
| P1 | 0 | ~~ENG-DNR-002 FIXED~~, ~~ENG-DNR-003 FIXED~~ |
| P2 | 2 | **ENG-DNR-004**, **PERF-DNR-001** |
| P3 | 2 | **ENG-DNR-005**, **PERF-DNR-002** |
| **Total open** | **4** | (was 9 open, 5 resolved this cycle) |

### By Category

| Category | Count | IDs |
| ---------- | ------- | ----- |
| Converter (CONV) | 0 | ~~All 6 CONV-DNR issues FIXED previously~~ |
| Engine (ENG) | 2 open | ENG-DNR-004, ENG-DNR-005 |
| Performance (PERF) | 2 open | PERF-DNR-001, PERF-DNR-002 |
| Testing (TEST) | 0 | ~~TEST-DNR-001 FIXED~~ |

### Fixed Previously

| ID | Phase | Fix Applied |
| ---- | ------- | ------------- |
| ENG-DNR-001 | Phase 13.1 | Added `@REGISTRY.register("Denormalize", "tDenormalize")` + REGISTRY import |
| ENG-DNR-002 | Phase 13.1 | Implemented `make_concat_func(delim, merge)` with first-seen-order dedup |
| ENG-DNR-003 | Phase 13.1 | `groupby(dropna=False, sort=False)` preserves null-key rows |
| Code quality | Phase 13.1 | `_validate_config()` returns None, raises ConfigurationError; no double validation; no manual `_update_stats()`; %-style logging |
| TEST-DNR-001 | Phase 13.1 | 41 engine unit tests added (11 test classes) |
| Coverage lift | Phase 14-05 | Quick-win coverage sweep -- `denormalize.py` raised to >= 95% floor [RESOLVED in Phase 14-05] |

### Cross-Cutting Issues

Standard base class bugs (XCUT-001 through XCUT-005) apply to the engine component. See Appendix B.

---

## 10. Recommendations

### Short-term (Hardening)

1. **ENG-DNR-004 (P2)**: Change engine delimiter default from "," to ";" to align with _java.xml (low impact since converter always emits explicit values)

### Long-term (Optimization)

1. **ENG-DNR-005 (P3)**: Document null_as_empty as engine-specific enhancement in component docstring
2. **PERF-DNR-002 (P3)**: Optimize closure creation in aggregation dict

---

## Appendix A: Source References

| Source | URL/Path | Used For |
| -------- | ---------- | ---------- |
| Talaxie GitHub _java.xml | `tDenormalize/tDenormalize_java.xml` | Parameter definitions, defaults |
| Engine source | `src/v1/engine/components/transform/denormalize.py` | Feature parity analysis |
| Converter source | `src/converters/talend_to_v1/components/transform/denormalize.py` | Converter audit |
| Test source | `tests/converters/talend_to_v1/components/test_denormalize.py` | Test coverage analysis |

## Appendix B: Cross-Cutting Issues

| Canonical ID | Location | Impact on This Component |
| ------------- | ---------- | -------------------------- |
| XCUT-001 | `base_component.py:304` | `_update_global_map()` crash when globalMap set |
| XCUT-002 | `global_map.py:28` | `GlobalMap.get()` broken signature |
| XCUT-003 | `base_component.py:174` | `replace_in_config` literal `[i]` bug |
| XCUT-004 | `base_component.py` | `validate_schema` inverted nullable logic |
| XCUT-005 | `base_component.py` | `self.config` mutation non-reentrant |

---

*Report generated: 2026-04-04*
*Last updated: 2026-05-11 -- Phase 15.1 reconciliation (Phase 13.1 fixes confirmed current; Phase 14-05 quick-win coverage lift noted)*
