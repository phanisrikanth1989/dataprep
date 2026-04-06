# Audit Report: tUniqRow / UniqueRow

> **Audited**: 2026-04-03
> **Auditor**: Claude Opus 4.6 (automated)
> **Engine Version**: v1
> **Converter**: `talend_to_v1`
> **Status**: PRODUCTION READINESS REVIEW
> **V1 only** — this report contains zero references to v2/PyETL

---

## 1. Component Identity

| Field | Value |
| ------- | ------- |
| **Talend Name** | `tUniqRow` (aliases: `tUniqueRow`, `tUnqRow`) |
| **V1 Engine Class** | `UniqueRow` |
| **Engine File** | `src/v1/engine/components/aggregate/unique_row.py` (289 lines) |
| **Converter Parser** | `src/converters/talend_to_v1/components/aggregate/unique_row.py` (197 lines) |
| **Converter Dispatch** | `@REGISTRY.register("tUniqueRow", "tUniqRow", "tUnqRow")` decorator-based dispatch |
| **Registry Aliases** | `tUniqueRow`, `tUniqRow`, `tUnqRow` (3 aliases) |
| **Category** | Aggregate / Data Quality |

### Key Files

| File | Purpose |
| ------ | --------- |
| `src/v1/engine/components/aggregate/unique_row.py` | Engine implementation (289 lines) |
| `src/converters/talend_to_v1/components/aggregate/unique_row.py` | Converter class |
| `tests/converters/talend_to_v1/components/test_unique_row.py` | Converter tests |
| `src/v1/engine/base_component.py` | Base class |
| `src/v1/engine/global_map.py` | GlobalMap storage |

---

## 2. Scorecard

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
| ----------- | ------- | ---- | ---- | ---- | ---- | --------- |
| Converter Coverage | **G** | 0 | 0 | 0 | 0 | 11 of 11 params extracted. UNIQUE_KEY TABLE parsed with stride-3. Per-column case sensitivity converted to global bool. 4 conditional needs_review entries for engine gaps. |
| Engine Feature Parity | **Y** | 0 | 3 | 2 | 1 | No per-column case sensitivity; no IS_VIRTUAL_COMPONENT disk mode; no BigDecimal hash normalization; UNIQUE/DUPLICATE flow routing via outputs list not named connectors |
| Code Quality | **Y** | 1 | 0 | 3 | 2 | `_update_global_map()` crash (cross-cutting P0); temp column collision risk; dead `_validate_config()`; naming inconsistencies |
| Performance & Memory | **Y** | 0 | 1 | 1 | 0 | Full DataFrame copy on every execution; no disk-based fallback for large datasets |
| Testing | **G** | 0 | 0 | 1 | 1 | 42 converter tests across 9 test classes per gold standard. No engine unit tests (P2). No integration tests (P3). |

Overall: YELLOW — Converter is Green (gold standard); Engine has significant feature gaps

**Top Actions:**

1. Fix `_update_global_map()` crash (cross-cutting P0)
2. Implement per-column case sensitivity in engine (P1)
3. Add IS_VIRTUAL_COMPONENT disk-based processing mode (P1)
4. Add BigDecimal hash/equals normalization in engine (P1)
5. Add engine unit tests

---

## 3. Talend Feature Baseline

### What tUniqRow Does

`tUniqRow` (also known as `tUniqueRow`) is a Data Quality component that compares entries in an input flow and separates them into unique records and duplicate records. It is an intermediary component requiring both an input flow and at least one output flow. It belongs to the **Data Quality** family.

The component has **two named output connectors**: `UNIQUE` (for first-seen records, displayed in green) and `DUPLICATE` (for subsequent occurrences of matching keys, displayed in orange dashed). This is a **critical distinction** from components like tFilterRow, which use `FLOW`/`REJECT` connectors. Deduplication is based on key columns specified in the UNIQUE_KEY table, with per-column case sensitivity control.

Advanced features include `ONLY_ONCE_EACH_DUPLICATED_KEY` (send each duplicate key only once to DUPLICATE output), `IS_VIRTUAL_COMPONENT` (disk-based processing for large datasets), and `CHANGE_HASH_AND_EQUALS_FOR_BIGDECIMAL` (normalize BigDecimal trailing zeros in hash/equals comparisons).

**Source**: [tUniqRow Standard properties (Talend 7.3)](https://help.talend.com/en-US/data-matching/7.3/tuniqrow-standard-properties), [tUniqRow Standard properties (Talend 8.0)](https://help.qlik.com/talend/en-US/data-matching/8.0/tuniqrow-standard-properties), [Component-specific settings (Job Script Reference Guide)](https://help.talend.com/en-US/job-script-reference-guide/7.3/component-specific-settings-for-tuniqrow), [Talaxie GitHub tdi-studio-se tUniqRow _java.xml](https://github.com/Talaxie/tdi-studio-se)
**Component family**: Data Quality (Processing)
**Available in**: All Talend products (Standard). Also available in Apache Spark Batch variant.
**Required JARs**: None (built-in)

### 3.1 Basic Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
| --- | ----------- | ----------------- | ------ | --------- | ------------- |
| 1 | Schema | `SCHEMA` | SCHEMA_TYPE | -- | Main schema definition. Shared between UNIQUE and DUPLICATE outputs. |
| 1b | Unique Schema | `SCHEMA_UNIQUE` | SCHEMA_TYPE | -- | Schema context for UNIQUE output connector. Mirrors main schema. |
| 1c | Duplicate Schema | `SCHEMA_DUPLICATE` | SCHEMA_TYPE | -- | Schema context for DUPLICATE output connector. Mirrors main schema. |
| 2 | Unique Key Table | `UNIQUE_KEY` | TABLE (stride-3: SCHEMA_COLUMN, KEY_ATTRIBUTE, CASE_SENSITIVE) | -- | Per-column deduplication settings. Each row specifies whether a column participates in key comparison and whether comparison is case-sensitive for that column. Only columns with `KEY_ATTRIBUTE="true"` participate in deduplication. |

#### UNIQUE_KEY Table Structure

The `UNIQUE_KEY` parameter is a table stored as groups of three `elementValue` entries in the Talend .item XML export:

| elementRef | Type | Description |
| ------------ | ------ | ------------- |
| `SCHEMA_COLUMN` | String | Column name from schema (quoted, e.g., `"firstName"`) |
| `KEY_ATTRIBUTE` | CHECK (`"true"`/`"false"`) | Whether this column participates in deduplication |
| `CASE_SENSITIVE` | CHECK (`"true"`/`"false"`) | Whether comparison is case-sensitive for this column |

**Note:** The _java.xml defines this TABLE with 2 items (KEY_ATTRIBUTE, CASE_SENSITIVE). The SCHEMA_COLUMN entry is added implicitly by the Talend framework for all TABLE params referencing schema columns. In .item file exports, the stride is 3.

### 3.2 Advanced Settings

| # | Parameter | Talend XML Name | Type | Default | Show If | Description |
| --- | ----------- | ----------------- | ------ | --------- | --------- | ------------- |
| A1 | Only Once Each Duplicated Key | `ONLY_ONCE_EACH_DUPLICATED_KEY` | CHECK | `false` | -- | When true, sends only the first duplicate for each key to DUPLICATE output (keeps "last" behavior). When false, sends all duplicates (keeps "first" behavior). |
| A2 | Is Virtual Component | `IS_VIRTUAL_COMPONENT` | CHECK | `false` | -- | Enables disk-based processing for large datasets. When true, intermediate data is written to disk instead of held in memory. |
| A3 | Buffer Size | `BUFFER_SIZE` | OPENED_LIST | `M` | `IS_VIRTUAL_COMPONENT == true` | Memory buffer size for disk-based mode. Items: `S` (Small), `M` (Medium), `B` (Big). |
| A4 | Temp Directory | `TEMP_DIRECTORY` | DIRECTORY | `""` | `IS_VIRTUAL_COMPONENT == true` | Directory for temporary files when disk-based mode is active. |
| A5 | Change Hash and Equals for BigDecimal | `CHANGE_HASH_AND_EQUALS_FOR_BIGDECIMAL` | CHECK | `false` | -- | Normalizes BigDecimal values before hash/equals comparison. Without this, `Decimal('1.0')` and `Decimal('1.00')` are treated as different values. |
| F1 | tStatCatcher Stats | `TSTATCATCHER_STATS` | CHECK | `false` | -- | Framework param: enable statistics collection |
| F2 | Label | `LABEL` | TEXT | `""` | -- | Framework param: display label |

### 3.3 Connection Types

| Connector | Direction | Type | Description |
| ----------- | ----------- | ------ | ------------- |
| `FLOW` (Main) | Input | Row > Main | Single input flow (max 1). All rows to be deduplicated. |
| `UNIQUE` | Output | Row > Main (green) | Unique rows (first occurrence per key group). Named connector, NOT `FLOW`. |
| `DUPLICATE` | Output | Row > Main (orange dashed) | Duplicate rows (subsequent occurrences per key group). Named connector, NOT `REJECT`. |
| `ITERATE` | Output | Iterate | For iterate-based processing |
| `SUBJOB_OK` | Output (Trigger) | Trigger | Fires when subjob completes successfully |
| `SUBJOB_ERROR` | Output (Trigger) | Trigger | Fires when subjob encounters an error |
| `COMPONENT_OK` | Output (Trigger) | Trigger | Fires when component completes successfully |
| `COMPONENT_ERROR` | Output (Trigger) | Trigger | Fires when component encounters an error |
| `RUN_IF` | Output (Trigger) | Trigger | Conditional execution trigger |

### 3.4 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
| ------------------ | ------ | ---------- | ------------- |
| `{id}_NB_UNIQUES` | Integer | After execution | Number of unique rows output |
| `{id}_NB_DUPLICATES` | Integer | After execution | Number of duplicate rows output |

### 3.5 Behavioral Notes

1. **UNIQUE/DUPLICATE connectors are NOT FLOW/REJECT.** This component uses named output connectors (`UNIQUE`, `DUPLICATE`) rather than the standard `FLOW`/`REJECT` pattern. The engine must route outputs by connector name, not by position.

2. **Per-column case sensitivity.** Each key column has its own CASE_SENSITIVE flag. A column with `CASE_SENSITIVE=false` converts values to lowercase before comparison. Mixed case settings (some columns case-sensitive, others not) is fully supported in Talend.

3. **ONLY_ONCE_EACH_DUPLICATED_KEY semantics.** When `true`, only the first duplicate for each key is sent to the DUPLICATE output. Subsequent duplicates with the same key are silently discarded. This effectively means "keep last" uniqueness behavior.

4. **CONNECTION_FORMAT phantom param.** This parameter appears in .item file exports but is NOT defined in the \_java.xml component definition. It is a framework-level parameter related to connection data format. Present in .item exports, absent from \_java.xml.

5. **IS_VIRTUAL_COMPONENT disk mode.** When enabled, the component uses disk-based storage for intermediate data, allowing processing of datasets larger than available memory. BUFFER_SIZE and TEMP_DIRECTORY are only relevant when this is enabled.

6. **BigDecimal hash normalization.** When `CHANGE_HASH_AND_EQUALS_FOR_BIGDECIMAL=true`, Java BigDecimal values are normalized (trailing zeros stripped) before hash/equals comparison, so `1.0` and `1.00` are treated as equal.

---

## 4. Converter Audit

### 4.1 Parameter Extraction

The converter (`UniqueRowConverter`) uses the `@REGISTRY.register("tUniqueRow", "tUniqRow", "tUnqRow")` decorator for dispatch. It extracts parameters using `_get_str()`, `_get_bool()`, and `_get_int()` helpers from the base class. The UNIQUE_KEY TABLE is parsed with a module-level `_parse_unique_key()` function using stride-3.

| # | Talend XML Parameter | Extracted? | V1 Config Key | Notes |
| ---- | ---------------------- | ------------ | --------------- | ------- |
| 1 | `SCHEMA` | Yes | (schema) | Via `_parse_schema()` |
| 2 | `UNIQUE_KEY` | Yes | `key_columns` | TABLE parsed with stride-3 (SCHEMA_COLUMN, KEY_ATTRIBUTE, CASE_SENSITIVE). Per-column case sensitivity collected. |
| 3 | `UNIQUE_KEY.CASE_SENSITIVE` | Yes | `case_sensitive` | Per-column values converted to global bool. Mixed values trigger needs_review. |
| 4 | `ONLY_ONCE_EACH_DUPLICATED_KEY` | Yes | `only_once_each_duplicated_key` | Bool, default false. Also derives `keep` (first/last). |
| 5 | `IS_VIRTUAL_COMPONENT` | Yes | `is_virtual_component` | Bool, default false |
| 6 | `BUFFER_SIZE` | Yes | `buffer_size` | Str, default "M" |
| 7 | `TEMP_DIRECTORY` | **REMOVED** | ~~temp_directory~~ | Hidden/design-time param -- removed from converter |
| 8 | `CHANGE_HASH_AND_EQUALS_FOR_BIGDECIMAL` | Yes | `change_hash_and_equals_for_bigdecimal` | Bool, default false. needs_review when true. |
| 9 | `CONNECTION_FORMAT` | **REMOVED** | ~~connection_format~~ | Phantom param (not in _java.xml) -- removed from converter |
| 10 | `TSTATCATCHER_STATS` | Yes | `tstatcatcher_stats` | Framework param, bool, default false |
| 11 | `LABEL` | Yes | `label` | Framework param, str, default "" |

**Summary**: 9 of 11 parameters extracted. 2 hidden/phantom params removed (TEMP_DIRECTORY, CONNECTION_FORMAT).

### 4.2 Schema Extraction

| Schema Attribute | Extracted? | Notes |
| ------------------ | ----------- | ------- |
| `name` | Yes | Via `_parse_schema()` |
| `type` | Yes | Converted via `convert_type()` |
| `nullable` | Yes | Direct extraction |
| `key` | Yes | Direct extraction |
| `length` | Yes | When >= 0 |
| `precision` | Yes | When >= 0 |
| `pattern` | Yes | Java-to-Python date pattern conversion |
| `default` | No | Not extracted by `_parse_schema()` |

### 4.3 Expression Handling

Context variables (`context.var`) and Java expressions (`{{java}}`) are handled by the `_get_str()` base class method, which strips surrounding quotes but does not perform expression resolution at conversion time. Expression resolution happens at engine runtime.

### 4.4 Converter Issues

None. All parameters correctly extracted per gold standard.

### 4.5 Needs Review Entries

The converter emits per-feature needs_review entries for specific engine gaps:

| # | Config Key | Reason | Severity |
| --- | ----------- | -------- | ---------- |
| 1 | `case_sensitive` | Engine uses global `case_sensitive` flag only; Talend supports per-column CASE_SENSITIVE. Mixed per-column values cannot be faithfully represented. | engine_gap |
| 2 | `change_hash_and_equals_for_bigdecimal` | Engine does not implement BigDecimal trailing zero normalization. Conditional: only emitted when enabled. | engine_gap |
| 3 | `is_virtual_component` | Engine does not implement disk-based processing mode (IS_VIRTUAL_COMPONENT). Always uses in-memory processing. | engine_gap |
| 4 | `only_once_each_duplicated_key` | Engine does not directly implement ONLY_ONCE_EACH_DUPLICATED_KEY semantics. Converter maps to keep=first/last as approximation. | engine_gap |

---

## 5. Engine Feature Parity

### 5.1 Feature Implementation Status

| # | Talend Feature | Implemented? | Fidelity | Engine Location | Notes |
| ---- | ---------------- | ------------- | ---------- | ----------------- | ------- |
| 1 | Deduplication by key columns | **Yes** | High | `_remove_duplicates()` line 190 | Uses `pd.DataFrame.duplicated()`. Falls back to all columns if key_columns empty. |
| 2 | Keep first/last | **Yes** | High | `_remove_duplicates()` line 249 | Uses pandas `keep` param ('first', 'last', False) |
| 3 | Global case sensitivity | **Yes** | Medium | `_remove_duplicates()` line 233 | Creates temp lowercase columns for string key columns. Only global flag, not per-column. |
| 4 | Per-column case sensitivity | **No** | N/A | -- | Engine only supports global `case_sensitive` bool. Talend supports per-column CASE_SENSITIVE. |
| 5 | UNIQUE output flow | **Partial** | Medium | `_process()` line 170 | Output as `main` and via `outputs` list index. Not named `UNIQUE` connector. |
| 6 | DUPLICATE output flow | **Partial** | Medium | `_process()` line 171 | Output as `reject` and via `outputs` list index. Not named `DUPLICATE` connector. |
| 7 | NB_UNIQUES stat | **Yes** | High | `_process()` line 162 | Written to globalMap as `{id}_NB_UNIQUES` |
| 8 | NB_DUPLICATES stat | **Yes** | High | `_process()` line 163 | Written to globalMap as `{id}_NB_DUPLICATES` |
| 9 | IS_VIRTUAL_COMPONENT (disk mode) | **No** | N/A | -- | Not implemented. Always in-memory. |
| 10 | BUFFER_SIZE | **No** | N/A | -- | Not implemented (depends on IS_VIRTUAL_COMPONENT) |
| 11 | TEMP_DIRECTORY | **No** | N/A | -- | Not implemented (depends on IS_VIRTUAL_COMPONENT) |
| 12 | CHANGE_HASH_AND_EQUALS_FOR_BIGDECIMAL | **No** | N/A | -- | Not implemented. Decimal('1.0') != Decimal('1.00') in hash. |
| 13 | ONLY_ONCE_EACH_DUPLICATED_KEY | **Partial** | Low | `_remove_duplicates()` line 249 | Approximated via keep='last', but does not suppress repeat duplicates in DUPLICATE output. |
| 14 | output_duplicates config | **Yes** | High | `_process()` line 139 | Engine-specific: controls whether duplicates are output at all. |
| 15 | is_reject_duplicate config | **Yes** | High | `_process()` line 140 | Engine-specific: controls whether duplicates are treated as rejects for stats. |

### 5.2 Behavioral Differences from Talend

| ID | Priority | Description |
| ---- | ---------- | ------------- |
| ENG-UNQ-001 | **P1** | **Per-column case sensitivity missing.** Engine uses a single global `case_sensitive` bool. Talend allows each key column to have independent CASE_SENSITIVE settings. Jobs with mixed per-column case sensitivity will produce incorrect deduplication results. |
| ENG-UNQ-002 | **P1** | **IS_VIRTUAL_COMPONENT disk mode not implemented.** Engine always loads full DataFrame into memory. Jobs with datasets exceeding available memory will fail with OOM errors where Talend would succeed using disk-based processing. |
| ENG-UNQ-003 | **P1** | **CHANGE_HASH_AND_EQUALS_FOR_BIGDECIMAL not implemented.** Engine uses Python's native Decimal comparison, where `Decimal('1.0') != Decimal('1.00')`. Talend normalizes trailing zeros when this is enabled. |
| ENG-UNQ-004 | **P2** | **UNIQUE/DUPLICATE flow routing via list index not name.** Engine routes unique rows to `main` and duplicates to `reject`, plus routes by index via `self.outputs` list. Talend uses named `UNIQUE`/`DUPLICATE` connectors. Works but fragile if output order changes. |
| ENG-UNQ-005 | **P2** | **ONLY_ONCE_EACH_DUPLICATED_KEY approximation.** Converter maps to `keep="last"` but engine does not actually suppress repeat duplicates in DUPLICATE output. The approximation only changes which duplicate is considered "unique" (first vs last seen). |
| ENG-UNQ-006 | **P3** | **output_duplicates and is_reject_duplicate are engine-specific.** These config keys do not correspond to Talend parameters. They add flexibility but diverge from Talend's model. |

### 5.3 GlobalMap Variable Coverage

| Variable | Talend Sets? | V1 Sets? | How V1 Sets It | Notes |
| ---------- | ------------- | ---------- | ----------------- | ------- |
| `{id}_NB_UNIQUES` | Yes | Yes | `global_map.put()` in `_process()` line 162 | Correct |
| `{id}_NB_DUPLICATES` | Yes | Yes | `global_map.put()` in `_process()` line 163 | Correct |
| `{id}_NB_LINE` | Yes | Yes | Via `_update_stats()` base class | Cross-cutting: crashes due to `_update_global_map()` bug |
| `{id}_NB_LINE_OK` | Yes | Yes | Via `_update_stats()` base class | Same cross-cutting issue |
| `{id}_NB_LINE_REJECT` | Yes | Partial | Via `_update_stats()` base class | Only counted when `is_reject_duplicate=True` |

---

## 6. Code Quality

### 6.1 Bugs

| ID | Priority | Location | Description |
| ---- | ---------- | ---------- | ------------- |
| BUG-UNQ-001 | **P0** | `base_component.py:304` | **CROSS-CUTTING:** `_update_global_map()` uses undefined `value` variable. Crashes ALL components when globalMap is set. Results lost, status stuck at RUNNING. |
| BUG-UNQ-002 | **P2** | `unique_row.py:238` | **Temp column collision risk.** Temporary columns use pattern `_temp_{col}`. If input data already has a column named `_temp_id`, it will be overwritten and dropped during cleanup. |

### 6.2 Naming Consistency

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| NAME-UNQ-001 | **P2** | Engine uses `main`/`reject` output names instead of `unique`/`duplicate` to match Talend's connector names. |
| NAME-UNQ-002 | **P3** | Engine config keys `output_duplicates` and `is_reject_duplicate` do not correspond to any Talend parameter. |

### 6.3 Standards Compliance

| ID | Priority | Standard | Violation |
| ---- | ---------- | ---------- | ----------- |
| STD-UNQ-001 | **P2** | "`_validate_config()` called or dead code" | `_validate_config()` defined (lines 74-105) but never called by the engine. Dead code. |

### 6.4 Debug Artifacts

None found. Engine uses logger consistently.

### 6.5 Security

No concerns identified. No `eval()`, `exec()`, or injection risks.

### 6.6 Logging Quality

| Aspect | Assessment |
| -------- | ------------ |
| Logger setup | Correct: `logger = logging.getLogger(__name__)` at module level |
| Level usage | Appropriate: `info` for start/complete, `warning` for empty input, `error` for failures |
| Sensitive data | No sensitive data in log messages |

### 6.7 Error Handling Quality

| Aspect | Assessment |
| -------- | ------------ |
| Custom exceptions | Uses `ComponentExecutionError` from engine exceptions module |
| Exception chaining | Yes: `raise ... from e` pattern used correctly |
| die_on_error handling | Not implemented (relies on engine-level error handling) |

### 6.8 Type Hints

| Aspect | Assessment |
| -------- | ------------ |
| Method signatures | Good: All public methods have return type annotations |
| Parameter types | Good: `Optional[pd.DataFrame]`, `List[str]`, `Dict[str, Any]` used consistently |

---

## 7. Performance & Memory

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| PERF-UNQ-001 | **P1** | **Full DataFrame copy.** `_remove_duplicates()` calls `input_data.copy()` on every invocation (line 229). For large DataFrames this doubles memory usage. |
| PERF-UNQ-002 | **P2** | **Double copy of output DataFrames.** Both `unique_df` and `duplicate_df` are created with `.copy()` from the already-copied DataFrame (lines 252-253). Three copies total. |
| PERF-UNQ-003 | **P3** | **No disk-based fallback.** IS_VIRTUAL_COMPONENT not implemented. Large datasets that exceed memory will OOM. |

### 7.1 Memory Management Assessment

| Aspect | Assessment |
| -------- | ------------ |
| Streaming mode | Not tested for HYBRID streaming. Stateless deduplication may work per-chunk but would produce incorrect results (duplicates across chunks missed). |
| Memory threshold | No memory threshold. Full DataFrame always loaded. |
| Large data handling | No disk-based fallback. Memory-bound by DataFrame size x3 (original + copy + output copies). |

---

## 8. Testing

### 8.1 Current Coverage

| Test Type | Count | Location |
| ----------- | ------- | ---------- |
| Converter unit tests | 42 | `tests/converters/talend_to_v1/components/test_unique_row.py` |
| Engine unit tests | 0 | None |
| Integration tests | 0 | None |

### 8.2 Test Gaps

| ID | Priority | Gap |
| ---- | ---------- | ----- |
| TEST-UNQ-001 | **P2** | No engine unit tests. `_remove_duplicates()` with various key column configs, case sensitivity, and empty inputs not tested. |
| TEST-UNQ-002 | **P3** | No integration tests verifying UNIQUE/DUPLICATE flow routing in a multi-component job. |

### 8.3 Recommended Test Cases

- Engine: Deduplication with single key column, keep=first
- Engine: Deduplication with multiple key columns, keep=last
- Engine: Case-insensitive deduplication with string columns
- Engine: Empty input DataFrame handling
- Engine: All columns as key when key_columns is empty
- Engine: GlobalMap NB_UNIQUES/NB_DUPLICATES correctness
- Integration: UNIQUE/DUPLICATE output flow routing to downstream components

---

## 9. Issues Summary

### By Priority

| Priority | Count | IDs |
| ---------- | ------- | ----- |
| P0 | 1 | **BUG-UNQ-001** (cross-cutting) |
| P1 | 4 | **ENG-UNQ-001**, **ENG-UNQ-002**, **ENG-UNQ-003**, **PERF-UNQ-001** |
| P2 | 7 | **ENG-UNQ-004**, **ENG-UNQ-005**, **BUG-UNQ-002**, **NAME-UNQ-001**, **STD-UNQ-001**, **PERF-UNQ-002**, **TEST-UNQ-001** |
| P3 | 4 | **ENG-UNQ-006**, **NAME-UNQ-002**, **PERF-UNQ-003**, **TEST-UNQ-002** |
| **Total** | **16** | |

### By Category

| Category | Count | IDs |
| ---------- | ------- | ----- |
| Engine (ENG) | 6 | ENG-UNQ-001 through ENG-UNQ-006 |
| Bug (BUG) | 2 | BUG-UNQ-001 (cross-cutting), BUG-UNQ-002 |
| Naming (NAME) | 2 | NAME-UNQ-001, NAME-UNQ-002 |
| Standards (STD) | 1 | STD-UNQ-001 |
| Performance (PERF) | 3 | PERF-UNQ-001 through PERF-UNQ-003 |
| Testing (TEST) | 2 | TEST-UNQ-001, TEST-UNQ-002 |
| Converter (CONV) | 0 | None |

### Cross-Cutting Issues

These issues are shared with all other engine components:

| Canonical ID | Location | Impact on This Component |
| ------------- | ---------- | -------------------------- |
| BUG-UNQ-001 | `base_component.py:304` | `_update_global_map()` crash when globalMap is set — NB_UNIQUES/NB_DUPLICATES custom stats may be lost |

---

## 10. Recommendations

### Immediate (Before Production)

1. **Fix `_update_global_map()` crash (BUG-UNQ-001, P0)** — Cross-cutting fix in base_component.py. Blocks all components.

### Short-term (Hardening)

1. **Implement per-column case sensitivity (ENG-UNQ-001, P1)** — Engine needs to support independent CASE_SENSITIVE per key column, not just global flag.
2. **Add IS_VIRTUAL_COMPONENT disk mode (ENG-UNQ-002, P1)** — Memory-bound processing limits dataset sizes.
3. **Add BigDecimal hash normalization (ENG-UNQ-003, P1)** — Needed for correct Decimal deduplication.
4. **Reduce DataFrame copies (PERF-UNQ-001, P1)** — Use views or in-place operations where possible.
5. **Fix UNIQUE/DUPLICATE connector naming (ENG-UNQ-004, NAME-UNQ-001, P2)** — Use named connectors matching Talend's UNIQUE/DUPLICATE.
6. **Add engine unit tests (TEST-UNQ-001, P2)** — Test deduplication logic directly.
7. **Avoid temp column collision (BUG-UNQ-002, P2)** — Use UUID-based temp column names.

### Long-term (Optimization)

1. **Add disk-based fallback (PERF-UNQ-003, P3)** — For datasets exceeding memory.
2. **Add integration tests (TEST-UNQ-002, P3)** — Multi-component flow routing.
3. **Remove engine-specific config keys (ENG-UNQ-006, NAME-UNQ-002, P3)** — Or document as engine extensions.

---

## Appendix A: Source References

| Source | URL/Path | Used For |
| -------- | ---------- | ---------- |
| Official Talend docs (7.3) | <https://help.talend.com/en-US/data-matching/7.3/tuniqrow-standard-properties> | Parameter definitions, defaults, behavioral docs |
| Official Talend docs (8.0) | <https://help.qlik.com/talend/en-US/data-matching/8.0/tuniqrow-standard-properties> | Updated parameter definitions |
| Talaxie GitHub _java.xml | <https://github.com/Talaxie/tdi-studio-se> (tUniqRow) | Component definition XML: params, types, defaults |
| Job Script Reference | <https://help.talend.com/en-US/job-script-reference-guide/7.3/component-specific-settings-for-tuniqrow> | UNIQUE_KEY table structure, usage examples |
| Engine source | `src/v1/engine/components/aggregate/unique_row.py` | Feature parity analysis (289 lines) |
| Converter source | `src/converters/talend_to_v1/components/aggregate/unique_row.py` | Converter audit |
| Base component | `src/v1/engine/base_component.py` | Cross-cutting bug analysis |

## Appendix B: Cross-Cutting Issues

| Canonical ID | Location | Impact on This Component |
| ------------- | ---------- | -------------------------- |
| XCUT-001 | `base_component.py:304` | `_update_global_map()` crash when globalMap set — affects NB_UNIQUES/NB_DUPLICATES stats |
| XCUT-002 | `global_map.py:28` | `GlobalMap.get()` undefined default — affects stat retrieval |
| XCUT-003 | `base_component.py:351` | `validate_schema` inverted nullable — nullable columns get `fillna(0)` |
| XCUT-004 | `base_component.py:267-278` | `_execute_streaming` drops rejects — DUPLICATE output lost in HYBRID mode |

---

*Report generated: 2026-04-03*
*Last updated: 2026-04-03 after hidden/design-time param removal*
