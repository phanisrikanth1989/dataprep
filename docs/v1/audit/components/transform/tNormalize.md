# Audit Report: tNormalize / Normalize

> **Audited**: 2026-04-04
> **Auditor**: Claude Opus 4.6 (automated) -- GOLD STANDARD REWRITE
> **Engine Version**: v1
> **Converter**: `talend_to_v1`
> **Status**: PRODUCTION READINESS REVIEW
> **V1 only** -- this report contains zero references to v2/PyETL

---

## 1. Component Identity

| Field | Value |
|-------|-------|
| **Talend Name** | `tNormalize` |
| **V1 Engine Class** | `Normalize` |
| **Engine File** | `src/v1/engine/components/transform/normalize.py` (221 lines) |
| **Converter Parser** | `src/converters/talend_to_v1/components/transform/normalize.py` (95 lines) |
| **Converter Dispatch** | `@REGISTRY.register("tNormalize")` decorator-based dispatch |
| **Registry Aliases** | `Normalize`, `tNormalize` |
| **Category** | Processing / Transform |

### Key Files

| File | Purpose |
|------|---------|
| `src/v1/engine/components/transform/normalize.py` | Engine implementation (221 lines) |
| `src/converters/talend_to_v1/components/transform/normalize.py` | Converter class (95 lines) |
| `tests/converters/talend_to_v1/components/test_normalize.py` | Converter tests (30 tests) |
| `src/v1/engine/base_component.py` | Base class |
| `src/v1/engine/global_map.py` | GlobalMap storage |

---

## 2. Scorecard

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
|-----------|-------|----|----|----|----|---------|
| Converter Coverage | **G** | 0 | 0 | 0 | 0 | 9/9 _java.xml params extracted (100%). Phantom DIE_ON_ERROR removed. 3 per-feature needs_review. _build_component_dict wrapper. |
| Engine Feature Parity | **Y** | 0 | 3 | 2 | 1 | Engine does not read escape_char, text_enclosure, discard_trailing_empty_str. Engine uses item_separator key (converter emits itemseparator). |
| Code Quality | **G** | 0 | 0 | 1 | 0 | Clean gold standard converter, well-documented, per-feature needs_review |
| Performance & Memory | **R** | 1 | 1 | 0 | 0 | iterrows() + row.copy() anti-pattern is O(n*m), massive memory overhead |
| Testing | **Y** | 0 | 0 | 1 | 0 | 30 converter tests (Green); no engine unit tests (per D-89) |

**Overall: YELLOW -- Engine performance and feature gaps prevent Green; converter is gold standard**

**Top Actions**:
1. Replace iterrows() with vectorized pandas split (P0)
2. Add engine support for escape_char/text_enclosure CSV params (P1)
3. Fix engine key mismatch: item_separator vs itemseparator (P1)
4. Fix discard_trailing_empty_str to filter only trailing empties (P1)
5. Add engine unit tests

---

## 3. Talend Feature Baseline

### What tNormalize Does

tNormalize normalizes the input flow following the SQL standard to help improve data quality and ease data updates. It takes a single column containing delimited values (e.g., `"a,b,c"`) and explodes each row into multiple rows -- one for each delimited value. All other columns in the row are replicated unchanged across the output rows. This is the inverse operation of tDenormalize.

A typical use case is transforming a comma-separated tags column: a row with `tags="red,blue,green"` becomes three rows, each with one tag value, while all other columns remain identical.

**Source**: [tNormalize Standard Properties (Talend 8.0)](https://help.qlik.com/talend/en-US/components/8.0/processing/tnormalize-standard-properties), [Talaxie GitHub _java.xml](https://raw.githubusercontent.com/Talaxie/tdi-studio-se/refs/heads/master/main/plugins/org.talend.designer.components.localprovider/components/tNormalize/tNormalize_java.xml)
**Component family**: Processing / Transform
**Available in**: Talend Open Studio, Talend Data Integration, all Talend products (Standard)
**Required JARs**: None (built-in)

### 3.1 Basic Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 1 | Schema | `SCHEMA` | Schema editor | -- | Column definitions with types, lengths, patterns, nullable, key attributes. Input and output schemas are identical (passthrough). |
| 2 | Column to Normalize | `NORMALIZE_COLUMN` | PREV_COLUMN_LIST | -- | **Mandatory**. Selects which column contains the delimited values to split. Dropdown populated from schema columns. |
| 3 | Item Separator | `ITEMSEPARATOR` | TEXT | `","` | Delimiter character(s) separating individual values within the normalized column. Can be literal string or regex. |

### 3.2 Advanced Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 4 | Get Rid of Duplicated Rows | `DEDUPLICATE` | CHECK | `false` | Remove duplicate values from the split output. Applied AFTER splitting and AFTER trim/discard operations. |
| 5 | Use CSV Parameters | `CSV_OPTION` | CHECK | `false` | Enables CSV-specific escape mode and enclosure character for parsing values containing the separator inside quoted fields. |
| 6 | Escape Char | `ESCAPE_CHAR` | CLOSED_LIST | `ESCAPE_MODE_DOUBLED` | **Conditional on CSV_OPTION=true.** Values: `ESCAPE_MODE_DOUBLED`, `ESCAPE_MODE_BACKSLASH`. Controls how escape characters are interpreted in CSV mode. |
| 7 | Text Enclosure | `TEXT_ENCLOSURE` | TEXT | `"\""` | **Conditional on CSV_OPTION=true.** The character used to enclose text fields in CSV mode. Default is double-quote. |
| 8 | Discard Trailing Empty Strings | `DISCARD_TRAILING_EMPTY_STR` | CHECK | `false` | Remove empty strings appearing at the END of the split result. Only trailing empties are removed; leading/middle empties preserved. |
| 9 | Trim Resulting Values | `TRIM` | CHECK | `false` | Remove leading/trailing whitespace from each split value. |

### 3.3 Framework Parameters

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| F1 | tStatCatcher Statistics | `TSTATCATCHER_STATS` | CHECK | `false` | Capture processing metadata for tStatCatcher. |
| F2 | Label | `LABEL` | TEXT | `""` | User label for the component. |

### 3.4 Phantom Parameters (NOT in _java.xml)

| Parameter | Source | Status |
|-----------|--------|--------|
| `DIE_ON_ERROR` | Engine code only | **REMOVED from converter** -- not present in _java.xml |

### 3.5 Connection Types

| Connector | Direction | Type | Description |
|-----------|-----------|------|-------------|
| `FLOW` (Main) | Input | Row > Main | Primary input data with column to normalize |
| `FLOW` (Main) | Output | Row > Main | Normalized output with one row per split value |
| `SUBJOB_OK` | Output (Trigger) | Trigger | Fires after successful component execution |
| `SUBJOB_ERROR` | Output (Trigger) | Trigger | Fires on component error |

### 3.6 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
|------------------|------|----------|-------------|
| `{id}_NB_LINE` | Integer | After execution | Total rows processed |
| `{id}_NB_LINE_OK` | Integer | After execution | Rows successfully normalized |
| `{id}_NB_LINE_REJECT` | Integer | After execution | Rows rejected (always 0) |

### 3.7 Behavioral Notes

1. **Processing order**: Split -> discard trailing empties -> trim -> deduplicate
2. **Passthrough schema**: Input and output schemas are identical -- the normalized column retains its original type
3. **Regex-capable separator**: ITEMSEPARATOR is regex-capable; period (`.`) should be escaped
4. **CSV_OPTION gates ESCAPE_CHAR and TEXT_ENCLOSURE**: These params are only visible in Talend UI when CSV_OPTION is true, but converter always extracts them (Talend saves the values regardless)
5. **ESCAPE_CHAR is CLOSED_LIST**: Only two valid values -- ESCAPE_MODE_DOUBLED and ESCAPE_MODE_BACKSLASH

---

## 4. Converter Audit

### 4.1 Parameter Extraction

The converter uses `_build_component_dict` wrapper with `type_name="Normalize"` per gold standard. All 9 _java.xml parameters are extracted with correct defaults. Phantom DIE_ON_ERROR is excluded.

| # | Talend XML Parameter | Extracted? | V1 Config Key | Notes |
|----|----------------------|------------|---------------|-------|
| 1 | `NORMALIZE_COLUMN` | Yes | `normalize_column` | str, default "" |
| 2 | `ITEMSEPARATOR` | Yes | `itemseparator` | str, default "," |
| 3 | `DEDUPLICATE` | Yes | `deduplicate` | bool, default False |
| 4 | `CSV_OPTION` | Yes | `csv_option` | bool, default False |
| 5 | `ESCAPE_CHAR` | Yes | `escape_char` | str (CLOSED_LIST), default "ESCAPE_MODE_DOUBLED" |
| 6 | `TEXT_ENCLOSURE` | Yes | `text_enclosure` | str, default '"' |
| 7 | `DISCARD_TRAILING_EMPTY_STR` | Yes | `discard_trailing_empty_str` | bool, default False |
| 8 | `TRIM` | Yes | `trim` | bool, default False |
| 9 | `TSTATCATCHER_STATS` | Yes | `tstatcatcher_stats` | Framework, bool, default False |
| 10 | `LABEL` | Yes | `label` | Framework, str, default "" |
| -- | `DIE_ON_ERROR` | **No** | -- | **Phantom param removed** -- not in _java.xml |

**Summary**: 9 of 9 _java.xml parameters extracted (100%) + 2 framework params.

### 4.2 Schema Extraction

| Schema Attribute | Extracted? | Notes |
|------------------|-----------|-------|
| `name` | Yes | Via `_parse_schema()` |
| `type` | Yes | Converted from Talend types via `convert_type()` |
| `nullable` | Yes | |
| `key` | Yes | |
| `length` | Yes | When >= 0 |
| `precision` | Yes | When >= 0 |
| `pattern` | Yes | Java-to-Python date pattern conversion |
| `default` | No | Not extracted by base `_parse_schema()` |

Schema is **passthrough**: `{"input": schema_cols, "output": schema_cols}`.

### 4.3 Expression Handling

Context variables (`context.var`) and Java expressions are preserved as-is in string parameters (NORMALIZE_COLUMN, ITEMSEPARATOR, TEXT_ENCLOSURE). The converter does not interpret expressions -- they are passed through to the engine.

### 4.4 Converter Issues

None -- converter is gold standard.

### 4.5 Needs Review Entries

| # | Config Key | Reason | Severity |
|---|-----------|--------|----------|
| 1 | `escape_char` | Engine does not read CSV escape mode | engine_gap |
| 2 | `text_enclosure` | Engine does not read CSV text enclosure character | engine_gap |
| 3 | `discard_trailing_empty_str` | Engine filters ALL empty strings, not just trailing | engine_gap |

---

## 5. Engine Feature Parity

### 5.1 Feature Implementation Status

| # | Talend Feature | Implemented? | Fidelity | Engine Location | Notes |
|----|----------------|-------------|----------|-----------------|-------|
| 1 | Column splitting | **Yes** | High | `_process()` line 161 | Uses `str.split()` |
| 2 | Item separator | **Yes** | Medium | `_process()` line 133 | Reads `item_separator` key (converter emits `itemseparator`) |
| 3 | Deduplicate | **Yes** | High | `_process()` lines 173-179 | Order-preserving dedup |
| 4 | Trim | **Yes** | High | `_process()` lines 164-165 | Standard `str.strip()` |
| 5 | CSV option | **Partial** | Low | `_process()` line 134 | Reads flag but does not use escape/enclosure logic |
| 6 | Escape char | **No** | N/A | -- | Not read from config |
| 7 | Text enclosure | **No** | N/A | -- | Not read from config |
| 8 | Discard trailing empty str | **Partial** | Low | `_process()` lines 167-168 | Filters ALL empty strings, not just trailing |
| 9 | die_on_error | **Yes** | High | `_process()` lines 121-126, 140-143, 196 | Reads from config (but param is phantom in Talend) |

### 5.2 Behavioral Differences from Talend

| ID | Priority | Description |
|----|----------|-------------|
| ENG-NRM-001 | **P1** | Engine reads `item_separator` config key but converter emits `itemseparator` -- key name mismatch |
| ENG-NRM-002 | **P1** | Engine does not implement CSV escape/enclosure logic when `csv_option=true` |
| ENG-NRM-003 | **P1** | Engine `discard_trailing_empty_str` filters ALL empty strings, not just trailing ones |
| ENG-NRM-004 | **P2** | Engine reads `die_on_error` from config but this param is phantom (not in _java.xml) |
| ENG-NRM-005 | **P2** | Null values converted to empty string before split -- Talend may handle differently |
| ENG-NRM-006 | **P3** | Processing order: engine applies discard-empty before trim; Talend applies discard-trailing-empty before trim (same order but different scope for discard) |

### 5.3 GlobalMap Variable Coverage

| Variable | Talend Sets? | V1 Sets? | How V1 Sets It | Notes |
|----------|-------------|----------|-----------------|-------|
| `{id}_NB_LINE` | Yes | Yes | `_update_stats()` | V1 counts output rows; Talend counts input rows |
| `{id}_NB_LINE_OK` | Yes | Yes | `_update_stats()` | |
| `{id}_NB_LINE_REJECT` | Yes | Yes | `_update_stats()` | Always 0 |

---

## 6. Code Quality

### 6.1 Bugs

| ID | Priority | Location | Description |
|----|----------|----------|-------------|
| BUG-NRM-001 | **P0** | `normalize.py:161` | `str.split("")` raises ValueError if item_separator is empty string -- no empty-separator guard |
| BUG-NRM-002 | **P2** | `normalize.py:151-199` | `iterrows()` + `row.copy()` causes type demotion: Decimal->float64, datetime64->object. CROSS-CUTTING. |

### 6.2 Naming Consistency

| ID | Priority | Issue |
|----|----------|-------|
| NAME-NRM-001 | **P2** | Engine reads `item_separator` but _java.xml name is `ITEMSEPARATOR` -- converter correctly emits `itemseparator` per D-38 |

### 6.3 Standards Compliance

None -- engine follows project conventions.

### 6.4 Debug Artifacts

None found.

### 6.5 Security

No concerns identified. Component operates on in-memory data only.

### 6.6 Logging Quality

| Aspect | Assessment |
|--------|------------|
| Logger setup | Proper module-level `logging.getLogger(__name__)` |
| Level usage | info for start/complete, warning for empty input, error for failures |
| Sensitive data | No sensitive data logged |

### 6.7 Error Handling Quality

| Aspect | Assessment |
|--------|------------|
| Custom exceptions | Uses `ConfigurationError` and `ComponentExecutionError` |
| Exception chaining | Proper `raise ... from e` pattern |
| die_on_error handling | Correctly checks config flag before raising |

### 6.8 Type Hints

| Aspect | Assessment |
|--------|------------|
| Method signatures | Fully typed |
| Parameter types | Properly annotated with Optional, Union |

---

## 7. Performance & Memory

| ID | Priority | Issue |
|----|----------|-------|
| PERF-NRM-001 | **P0** | `iterrows()` + `row.copy()` + list-of-Series pattern is O(n*m) and creates massive intermediate memory. No vectorized alternative implemented. CROSS-CUTTING anti-pattern. |
| PERF-NRM-002 | **P1** | Each input row creates N copies (one per split value) via `row.copy()`. For 1M rows with average 5 values each, this creates 5M Series objects. |

### 7.1 Memory Management Assessment

| Aspect | Assessment |
|--------|------------|
| Streaming mode | Not implemented for normalize -- processes entire DataFrame at once |
| Memory threshold | No memory guard -- will OOM on large datasets with high fan-out |
| Large data handling | iterrows() anti-pattern makes this 100-1000x slower than vectorized approach |

---

## 8. Testing

### 8.1 Current Coverage

| Test Type | Count | Location |
|-----------|-------|----------|
| Converter unit tests | 30 | `tests/converters/talend_to_v1/components/test_normalize.py` |
| Engine unit tests | 0 | None |
| Integration tests | 0 | None (component-specific) |

### 8.2 Test Gaps

| ID | Priority | Gap |
|----|----------|-----|
| TEST-NRM-001 | **P2** | No engine unit tests for Normalize class (per D-89, Testing=Yellow) |

### 8.3 Recommended Test Cases

- Engine: empty string separator (triggers ValueError)
- Engine: null/NaN values in normalize column
- Engine: CSV_OPTION=true with quoted fields containing separator
- Engine: Large fan-out (1 row -> 1000+ rows) memory behavior
- Engine: Decimal/datetime type preservation through split

---

## 9. Issues Summary

### By Priority

| Priority | Count | IDs |
|----------|-------|-----|
| P0 | 1 | **BUG-NRM-001**, PERF-NRM-001 |
| P1 | 4 | **ENG-NRM-001**, **ENG-NRM-002**, **ENG-NRM-003**, **PERF-NRM-002** |
| P2 | 4 | **ENG-NRM-004**, **ENG-NRM-005**, **BUG-NRM-002**, **TEST-NRM-001** |
| P3 | 1 | **ENG-NRM-006** |
| **Total** | **10** | |

### By Category

| Category | Count | IDs |
|----------|-------|-----|
| Engine (ENG) | 6 | ENG-NRM-001 through ENG-NRM-006 |
| Bug (BUG) | 2 | BUG-NRM-001, BUG-NRM-002 |
| Performance (PERF) | 2 | PERF-NRM-001, PERF-NRM-002 |
| Testing (TEST) | 1 | TEST-NRM-001 |

### Cross-Cutting Issues

| Canonical ID | Location | Impact on This Component |
|-------------|----------|--------------------------|
| XCUT-001 | `base_component.py:304` | `_update_global_map()` crash when globalMap set |
| XCUT-002 | `normalize.py:151` | `iterrows()` anti-pattern (shared with tDenormalize, tSchemaComplianceCheck, etc.) |
| XCUT-003 | `normalize.py:183` | `row.copy()` type demotion through Series reconstruction |

---

## 10. Recommendations

### Immediate (Before Production)

1. **BUG-NRM-001 (P0)**: Add empty-separator guard before `str.split()`
2. **PERF-NRM-001 (P0)**: Replace `iterrows()` with vectorized `str.split()` + `explode()` pattern

### Short-term (Hardening)

3. **ENG-NRM-001 (P1)**: Align engine config key to `itemseparator` (or add converter alias)
4. **ENG-NRM-002 (P1)**: Implement CSV escape/enclosure logic when `csv_option=true`
5. **ENG-NRM-003 (P1)**: Fix discard logic to filter only TRAILING empty strings
6. **TEST-NRM-001 (P2)**: Add engine unit tests

### Long-term (Optimization)

7. **ENG-NRM-006 (P3)**: Verify processing order matches Talend exactly

---

## Appendix A: Source References

| Source | URL/Path | Used For |
|--------|----------|----------|
| Talaxie GitHub _java.xml | `https://raw.githubusercontent.com/Talaxie/tdi-studio-se/refs/heads/master/main/plugins/org.talend.designer.components.localprovider/components/tNormalize/tNormalize_java.xml` | Parameter definitions, defaults, field types |
| Talend 8.0 docs | `https://help.qlik.com/talend/en-US/components/8.0/processing/tnormalize-standard-properties` | Feature descriptions, behavioral notes |
| Engine source | `src/v1/engine/components/transform/normalize.py` | Feature parity analysis (221 lines) |
| Converter source | `src/converters/talend_to_v1/components/transform/normalize.py` | Converter audit (95 lines) |
| Converter tests | `tests/converters/talend_to_v1/components/test_normalize.py` | Test coverage (30 tests) |

## Appendix B: Engine Config Key Mapping

| Converter Config Key | Engine Config Key | Match? | Notes |
|---------------------|-------------------|--------|-------|
| `normalize_column` | `normalize_column` | Yes | Both use same key |
| `itemseparator` | `item_separator` | **No** | Engine uses underscore variant |
| `deduplicate` | `deduplicate` | Yes | |
| `csv_option` | `csv_option` | Yes | Engine reads but does not implement CSV logic |
| `escape_char` | -- | **No** | Engine does not read |
| `text_enclosure` | -- | **No** | Engine does not read |
| `discard_trailing_empty_str` | `discard_trailing_empty_str` | Yes | But engine behavior differs (all vs trailing) |
| `trim` | `trim` | Yes | |

---

*Report generated: 2026-04-04*
*Last updated: 2026-04-04 after gold standard rewrite (Phase 13)*
