# Audit Report: tFilterColumns / FilterColumns

> **Audited**: 2026-04-04
> **Auditor**: Claude Opus 4.6 (automated)
> **Engine Version**: v1
> **Converter**: `talend_to_v1`
> **Status**: PRODUCTION READINESS REVIEW
> **V1 only** -- this report contains zero references to v2/PyETL

---

## 1. Component Identity

| Field | Value |
|-------|-------|
| **Talend Name** | `tFilterColumns` |
| **V1 Engine Class** | `FilterColumns` |
| **Engine File** | `src/v1/engine/components/transform/filter_columns.py` (205 lines) |
| **Converter Parser** | `src/converters/talend_to_v1/components/transform/filter_columns.py` (68 lines) |
| **Converter Dispatch** | `@REGISTRY.register("tFilterColumns")` decorator-based dispatch |
| **Registry Aliases** | `FilterColumns`, `tFilterColumns` |
| **Category** | Transform / Processing |

### Key Files

| File | Purpose |
|------|---------|
| `src/v1/engine/components/transform/filter_columns.py` | Engine implementation (205 lines) |
| `src/converters/talend_to_v1/components/transform/filter_columns.py` | Converter class (68 lines) |
| `tests/converters/talend_to_v1/components/test_filter_columns.py` | Converter tests (23 tests) |
| `src/v1/engine/base_component.py` | Base class |
| `src/v1/engine/global_map.py` | GlobalMap storage |

---

## 2. Scorecard

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
|-----------|-------|----|----|----|----|---------|
| Converter Coverage | **G** | 0 | 0 | 0 | 0 | 0 unique + 2 framework params extracted (100%); _build_component_dict; passthrough schema; 2 per-feature needs_review for engine-only keys (mode, keep_row_order) |
| Code Quality | **G** | 0 | 0 | 0 | 0 | Gold standard converter pattern; clean, minimal, well-documented module docstring with config mapping |
| Testing | **Y** | 0 | 0 | 1 | 0 | 23 converter tests across 7 test classes; no engine unit tests (TEST-FC-001) |
| Overall | **Y** | 0 | 0 | 1 | 0 | Converter production-ready; engine unit tests needed for Green |

**Overall: YELLOW -- Converter is gold standard; engine unit tests needed for full Green**

**Top Actions**: Add engine unit tests for FilterColumns component (TEST-FC-001)

---

## 3. Talend Feature Baseline

### What tFilterColumns Does

`tFilterColumns` filters columns from the input data flow, passing only selected columns through to the output. In Talend Studio, the user configures which columns to keep by editing the output schema -- columns present in the output schema are kept, and columns absent are dropped. The component acts as a schema projection: it does not modify row data, only the column structure.

The component is commonly used to reduce a wide schema to only the columns needed downstream, to remove sensitive columns before writing to an output, or to reshape data between processing steps.

**Source**: [Talaxie GitHub _java.xml](https://raw.githubusercontent.com/Talaxie/tdi-studio-se/refs/heads/master/main/plugins/org.talend.designer.components.localprovider/components/tFilterColumns/tFilterColumns_java.xml)
**Component family**: Processing (Transform)
**Available in**: All Talend products (Standard)
**Required JARs**: None (built-in)

### 3.1 Basic Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 1 | Schema | `SCHEMA` | Schema editor | -- | Defines which columns pass through. The output FLOW schema determines the column list -- columns in this schema are kept, others are dropped. |
| 2 | Label | `LABEL` | String (TEXT) | `""` | Text label for the component in Talend Studio. No runtime impact. Framework param. |
| 3 | tStatCatcher Statistics | `TSTATCATCHER_STATS` | Boolean (CHECK) | `false` | Capture processing metadata for tStatCatcher. Framework param. |

**Key observation**: tFilterColumns has **no unique user-configurable parameters** beyond SCHEMA and the two framework params. The column list is entirely determined by the output FLOW schema, not by elementParameter entries. There is no `mode`, `columns`, or `keep_row_order` parameter in _java.xml -- these exist only in the v1 engine implementation.

### 3.2 Advanced Settings

None. tFilterColumns has no advanced settings tab.

### 3.3 Connection Types

| Connector | Direction | Type | Description |
|-----------|-----------|------|-------------|
| `Row (Main)` | Input | Row > Main | Input data flow with full column set |
| `Row (Main)` | Output | Row > Main | Output data flow with filtered column set (per output schema) |
| `COMPONENT_OK` | Output (Trigger) | Trigger | Fires on successful completion |
| `COMPONENT_ERROR` | Output (Trigger) | Trigger | Fires on error |

### 3.4 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
|------------------|------|----------|-------------|
| `{id}_NB_LINE` | Integer | After execution | Total rows processed |
| `{id}_NB_LINE_OK` | Integer | After execution | Rows successfully filtered |
| `{id}_NB_LINE_REJECT` | Integer | After execution | Rows rejected (always 0 for filter columns) |
| `{id}_NB_COLUMNS_IN` | Integer | After execution | Number of input columns (custom statistic) |
| `{id}_NB_COLUMNS_OUT` | Integer | After execution | Number of output columns (custom statistic) |

### 3.5 Behavioral Notes

1. tFilterColumns is a schema projection -- it modifies column structure but never modifies row data.
2. Column selection is determined by the output FLOW schema in Talend Studio, not by any component parameter.
3. There is no `mode`, `columns`, or `keep_row_order` parameter in the _java.xml definition -- these exist only in the v1 engine implementation.
4. Schema is configured via "Edit Schema" in Talend Studio -- the output schema defines the column filter.
5. The converter uses passthrough schema (input == output) because the FLOW schema available to the converter represents the post-filter column set. The pre-filter schema is not available in the .item XML.

---

## 4. Converter Audit

### 4.1 Parameter Extraction

The converter uses `_build_component_dict` with `type_name="FilterColumns"` and passthrough schema pattern. No unique parameters to extract beyond framework params.

| # | Talend XML Parameter | Extracted? | V1 Config Key | Notes |
|----|----------------------|------------|---------------|-------|
| 1 | `SCHEMA` | Yes | schema (passthrough) | `_parse_schema(node)` with input == output |
| 2 | `TSTATCATCHER_STATS` | Yes | `tstatcatcher_stats` | `_get_bool(node, ..., False)` -- framework param |
| 3 | `LABEL` | Yes | `label` | `_get_str(node, ..., "")` -- framework param |

**Summary**: 0 of 0 unique parameters extracted (N/A -- no unique params). 2 framework params extracted. 100% coverage.

### 4.2 Schema Extraction

| Schema Attribute | Extracted? | Notes |
|------------------|-----------|-------|
| `name` | Yes | Via `_parse_schema()` |
| `type` | Yes | Converted from Talend types via `convert_type()` |
| `nullable` | Yes | Boolean |
| `key` | Yes | Boolean |
| `length` | Yes | When >= 0 |
| `precision` | Yes | When >= 0 |
| `pattern` | Yes | Java-to-Python date pattern conversion |
| `default` | No | Not implemented in base class |

**Passthrough pattern**: `schema = {"input": schema_cols, "output": schema_cols}` -- input and output are identical references, establishing the transform passthrough pattern. The FLOW schema represents the filtered column set; the pre-filter schema is not available in _java.xml.

### 4.3 Expression Handling

Not applicable. tFilterColumns has no expression-capable parameters.

### 4.4 Converter Issues

None. Converter is gold standard.

### 4.5 Needs Review Entries

| # | Config Key | Reason | Severity |
|---|-----------|--------|----------|
| 1 | `mode` | Engine reads this key (default 'include') but it is not a _java.xml param. Converter does not output this key. | engine_gap |
| 2 | `keep_row_order` | Engine reads this key (default True) but it is not a _java.xml param. Converter does not output this key. | engine_gap |

---

## 5. Engine Feature Parity

### 5.1 Feature Implementation Status

| # | Talend Feature | Implemented? | Fidelity | Engine Location | Notes |
|----|----------------|-------------|----------|-----------------|-------|
| 1 | Column filtering (include mode) | **Yes** | High | `_process()` line 149-170 | Keeps specified columns, logs missing columns as warnings |
| 2 | Column filtering (exclude mode) | **Yes** | Medium | `_process()` line 172-183 | Removes specified columns -- no Talend equivalent mode parameter |
| 3 | Error handling | **Yes** | Medium | `_process()` line 202-205 | Catches exceptions, raises `ComponentExecutionError` |
| 4 | Statistics tracking | **Yes** | High | `_update_stats()` line 191 | NB_LINE, NB_LINE_OK, NB_LINE_REJECT |
| 5 | Custom column statistics | **Yes** | High | lines 194-197 | NB_COLUMNS_IN, NB_COLUMNS_OUT via globalMap |
| 6 | Config validation | **Partial** | Low | `_validate_config()` line 75-108 | Defined but never called (cross-cutting dead code) |

### 5.2 Behavioral Differences from Talend

| ID | Priority | Description |
|----|----------|-------------|
| ENG-FC-001 | **P2** | Engine reads `mode` (default 'include') with include/exclude semantics. Talend has no mode parameter -- column filtering is purely schema-driven. |
| ENG-FC-002 | **P2** | Engine reads `columns` (default []) as an explicit column name list. In Talend, columns are determined by the output schema, not a parameter. |
| ENG-FC-003 | **P2** | Engine reads `keep_row_order` (default True) which has no _java.xml equivalent. Currently not used in engine logic (documented but no-op). |
| ENG-FC-004 | **P2** | Engine returns empty DataFrame when no valid columns remain. Talend would fail schema validation at design time. |
| ENG-FC-005 | **P2** | Mutable class default: `DEFAULT_COLUMNS = []` at class level (line 71). If ever mutated, shared across instances. |
| ENG-FC-006 | **P2** | Empty DataFrame input returns `pd.DataFrame()` which loses column schema. Should preserve column structure. |

### 5.3 GlobalMap Variable Coverage

| Variable | Talend Sets? | V1 Sets? | How V1 Sets It | Notes |
|----------|-------------|----------|-----------------|-------|
| `{id}_NB_LINE` | Yes | Yes | `_update_stats()` | Total rows processed |
| `{id}_NB_LINE_OK` | Yes | Yes | `_update_stats()` | Successfully filtered rows |
| `{id}_NB_LINE_REJECT` | Yes | Yes | `_update_stats()` | Always 0 for filter columns |
| `{id}_NB_COLUMNS_IN` | Yes | Yes | `global_map.put()` line 195 | Input column count |
| `{id}_NB_COLUMNS_OUT` | Yes | Yes | `global_map.put()` line 196 | Output column count |

---

## 6. Code Quality

### 6.1 Bugs

| ID | Priority | Location | Description |
|----|----------|----------|-------------|
| BUG-FC-001 | **P2** | `filter_columns.py:71` | Mutable class default `DEFAULT_COLUMNS = []`. If ever appended to, shared across all instances. Should use `None` sentinel with `or []` in method. |
| BUG-FC-002 | **P2** | `filter_columns.py:131-133` | Empty input returns `pd.DataFrame()` which loses column schema. Should return DataFrame with correct columns but 0 rows. |
| BUG-FC-003 | **P2** | `filter_columns.py:164-166` | Include mode with no valid columns returns empty DataFrame and updates stats as 0 OK / total_rows REJECT, but this is misleading -- rows are not "rejected", columns are just missing. |

### 6.2 Naming Consistency

No naming issues found in converter or engine.

### 6.3 Standards Compliance

| ID | Priority | Standard | Violation |
|----|----------|----------|-----------|
| STD-FC-001 | **P2** | "_validate_config() called or dead code" | `_validate_config()` defined (lines 75-108) but never called by base class |

### 6.4 Debug Artifacts

None found.

### 6.5 Security

No concerns identified. tFilterColumns is a pure column projection with no file I/O, network, or expression evaluation.

### 6.6 Logging Quality

| Aspect | Assessment |
|--------|------------|
| Logger setup | Correct -- `logging.getLogger(__name__)` |
| Level usage | Appropriate -- info for start/complete, warning for missing columns and empty input, debug for configuration details |
| Sensitive data | No concerns -- logs column names and row counts only |

### 6.7 Error Handling Quality

| Aspect | Assessment |
|--------|------------|
| Custom exceptions | `ComponentExecutionError` raised on failure |
| Exception chaining | Yes -- `from e` used |
| die_on_error handling | Not applicable -- engine has no die_on_error for this component |

### 6.8 Type Hints

| Aspect | Assessment |
|--------|------------|
| Method signatures | Complete -- return types and parameter types |
| Parameter types | Correct -- Optional[pd.DataFrame], Dict[str, Any], List[str] |

---

## 7. Performance & Memory

| ID | Priority | Issue |
|----|----------|-------|
| PERF-FC-001 | **P3** | `.copy()` on result DataFrame (line 170, 183). For large DataFrames, creates full copy. Could use view for read-only downstream. |

### 7.1 Memory Management Assessment

| Aspect | Assessment |
|--------|------------|
| Streaming mode | Not implemented; relies on base class batch mode |
| Memory threshold | No threshold -- processes entire DataFrame at once |
| Large data handling | Memory-bound by input size (single copy) |

---

## 8. Testing

### 8.1 Current Coverage

| Test Type | Count | Location |
|-----------|-------|----------|
| Converter unit tests | 23 | `tests/converters/talend_to_v1/components/test_filter_columns.py` |
| Engine unit tests | 0 | None |
| Integration tests | 0 | None (component-specific) |

### 8.2 Test Gaps

| ID | Priority | Gap |
|----|----------|-----|
| TEST-FC-001 | **P2** | No engine unit tests for FilterColumns component |

### 8.3 Recommended Test Cases

- Engine: include mode with specified columns
- Engine: exclude mode with specified columns
- Engine: empty DataFrame input
- Engine: missing columns in include mode (warning behavior)
- Engine: all columns excluded (empty result)
- Engine: keep_row_order parameter (currently no-op)
- Engine: schema propagation verification
- Engine: NB_COLUMNS_IN / NB_COLUMNS_OUT globalMap variables

---

## 9. Issues Summary

### By Priority

| Priority | Count | IDs |
|----------|-------|-----|
| P0 | 0 | -- |
| P1 | 0 | -- |
| P2 | 10 | ENG-FC-001, ENG-FC-002, ENG-FC-003, ENG-FC-004, ENG-FC-005, ENG-FC-006, BUG-FC-001, BUG-FC-002, BUG-FC-003, STD-FC-001 |
| P3 | 1 | PERF-FC-001 |
| **Total** | **11** | (including TEST-FC-001 = **12**) |

### By Category

| Category | Count | IDs |
|----------|-------|-----|
| Engine (ENG) | 6 | ENG-FC-001, ENG-FC-002, ENG-FC-003, ENG-FC-004, ENG-FC-005, ENG-FC-006 |
| Bug (BUG) | 3 | BUG-FC-001, BUG-FC-002, BUG-FC-003 |
| Standards (STD) | 1 | STD-FC-001 |
| Performance (PERF) | 1 | PERF-FC-001 |
| Testing (TEST) | 1 | TEST-FC-001 |

### Cross-Cutting Issues

| Canonical ID | Location | Impact on This Component |
|-------------|----------|--------------------------|
| XCUT-001 | `base_component.py` | `_update_global_map()` crash when globalMap set |
| XCUT-002 | `base_component.py` | `_validate_config()` never called |

---

## 10. Recommendations

### Immediate (Before Production)

No P0 or P1 issues. Converter is production-ready.

### Short-term (Hardening)

- Add engine unit tests (TEST-FC-001)
- Fix mutable class default `DEFAULT_COLUMNS = []` (BUG-FC-001)
- Fix empty DataFrame losing column schema (BUG-FC-002)
- Address dead `_validate_config()` code (cross-cutting with other components)

### Long-term (Optimization)

- Consider view instead of `.copy()` for memory efficiency (PERF-FC-001)
- Remove artificial `mode` and `keep_row_order` engine parameters not in Talend (ENG-FC-001, ENG-FC-003)

---

## Appendix A: Source References

| Source | URL/Path | Used For |
|--------|----------|----------|
| Talaxie GitHub _java.xml | [tFilterColumns_java.xml](https://raw.githubusercontent.com/Talaxie/tdi-studio-se/refs/heads/master/main/plugins/org.talend.designer.components.localprovider/components/tFilterColumns/tFilterColumns_java.xml) | Component definition XML |
| Engine source | `src/v1/engine/components/transform/filter_columns.py` | Feature parity analysis |
| Converter source | `src/converters/talend_to_v1/components/transform/filter_columns.py` | Converter audit |

## Appendix B: Engine Config Key Mapping

| Engine Config Key | _java.xml Param | Default (Engine) | Default (_java.xml) | Status |
|-------------------|-----------------|------------------|---------------------|--------|
| `mode` | N/A | `'include'` | N/A | Engine-only key -- no _java.xml equivalent |
| `columns` | N/A (schema-driven) | `[]` | N/A | Engine reads column list; Talend uses FLOW schema |
| `keep_row_order` | N/A | `True` | N/A | Engine-only key -- no _java.xml equivalent, currently no-op |
| `tstatcatcher_stats` | `TSTATCATCHER_STATS` | N/A | `false` | Framework param -- converter extracts correctly |
| `label` | `LABEL` | N/A | `""` | Framework param -- converter extracts correctly |

---

*Report generated: 2026-04-04*
*Last updated: 2026-04-04 after Phase 11 gold standard rewrite*
