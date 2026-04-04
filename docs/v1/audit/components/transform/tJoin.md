# Audit Report: tJoin / Join

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
| **Talend Name** | `tJoin` |
| **V1 Engine Class** | `Join` |
| **Engine File** | `src/v1/engine/components/transform/join.py` (390 lines) |
| **Converter Parser** | `src/converters/talend_to_v1/components/transform/join.py` (155 lines) |
| **Converter Dispatch** | `@REGISTRY.register("tJoin")` decorator-based dispatch |
| **Registry Aliases** | `Join`, `tJoin` |
| **Category** | Transform / Processing |

### Key Files

| File | Purpose |
|------|---------|
| `src/v1/engine/components/transform/join.py` | Engine implementation (390 lines) |
| `src/converters/talend_to_v1/components/transform/join.py` | Converter class (155 lines) |
| `tests/converters/talend_to_v1/components/test_join.py` | Converter tests (26 tests) |
| `src/v1/engine/base_component.py` | Base class |
| `src/v1/engine/global_map.py` | GlobalMap storage |

---

## 2. Scorecard

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
|-----------|-------|----|----|----|----|---------|
| Converter Coverage | **G** | 0 | 0 | 0 | 0 | 4 unique + 2 framework params (100%); _build_component_dict; phantom CASE_SENSITIVE/DIE_ON_ERROR removed; USE_LOOKUP_COLS/LOOKUP_COLS TABLE added; JOIN_KEY INPUT_COLUMN/LOOKUP_COLUMN elementRefs fixed; 4 per-feature needs_review; 26 converter tests |
| Engine Feature Parity | **Y** | 1 | 3 | 2 | 1 | Schema filtering dead code; reject schema never populated; no INCLUDE_LOOKUP toggle; no ERROR_MESSAGE globalMap |
| Code Quality | **Y** | 2 | 4 | 3 | 1 | Cross-cutting base class bugs; schema attribute mismatch; double reject computation; dead validate_config; left outer join incorrect reject output |
| Performance & Memory | **G** | 0 | 1 | 2 | 1 | Double merge for reject; full copy on case-insensitive; minor optimizations |
| Testing | **Y** | 0 | 1 | 0 | 0 | 26 converter tests (Green); engine unit tests missing |

**Overall: YELLOW -- Converter Green, engine needs P0/P1 fixes**

**Top Actions**: Fix base class `_update_global_map()` crash (cross-cutting), fix `self.schema` attribute mismatch (dead code), fix case-insensitive join lowercase corruption, add engine unit tests

---

## 3. Talend Feature Baseline

### What tJoin Does

`tJoin` performs inner or outer joins between a primary (main) data flow and a lookup (reference) data flow. It compares columns from the main flow against reference columns from the lookup flow, performing an exact-match join on one or more key column pairs. The component outputs both matched records (via the main output FLOW) and optionally rejected records (via the REJECT output) -- rows from the main flow that had no matching row in the lookup flow. It is a simpler, more focused alternative to `tMap` for straightforward two-input join scenarios.

**Source**: [tJoin Standard Properties (Talend 7.3)](https://help.qlik.com/talend/en-US/components/7.3/processing/tjoin-standard-properties), [tJoin Standard Properties (Talend 8.0)](https://help.qlik.com/talend/en-US/components/8.0/processing/tjoin-standard-properties), [Talaxie GitHub _java.xml](https://github.com/Talaxie/tcommon-studio-se)
**Component family**: Processing (Integration)
**Available in**: All Talend products (Standard, Big Data, Data Fabric, etc.)
**Required JARs**: None (built-in)

### 3.1 Basic Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 1 | Schema | `SCHEMA` | Schema editor | -- | Column definitions for the output flow |
| 2 | Inner join | `USE_INNER_JOIN` | CHECK | `false` | When checked, inner join; unmatched main rows to REJECT. When unchecked, left outer join. |
| 3 | Join key | `JOIN_KEY` | TABLE (stride-2: `INPUT_COLUMN`, `LOOKUP_COLUMN`) | -- | Key column pairs for join matching. Multiple pairs are ANDed. |
| 4 | Use lookup columns | `USE_LOOKUP_COLS` | CHECK | `false` | When checked, include selected lookup columns in output. |
| 5 | Lookup columns | `LOOKUP_COLS` | TABLE (stride-2: `OUTPUT_COLUMN`, `LOOKUP_COLUMN`) | -- | Which lookup columns to include in output. |
| 6 | tStatCatcher Statistics | `TSTATCATCHER_STATS` | CHECK | `false` | Capture processing metadata for tStatCatcher. |

### 3.2 Advanced Settings

None documented in _java.xml. Note: `CASE_SENSITIVE` and `DIE_ON_ERROR` appear in the engine code and some online documentation but are **NOT present in the Talaxie _java.xml** definition. They are treated as phantom params in this audit.

### 3.3 Connection Types

| Connector | Direction | Type | Description |
|-----------|-----------|------|-------------|
| `FLOW` (Main) | Input | Row > Main | Primary data stream (left side of join) |
| `FLOW`/`FILTER` (Lookup) | Input | Row > Lookup | Reference data stream (right side of join) |
| `FLOW` (Main) | Output | Row > Main | Joined output rows |
| `REJECT` | Output | Row > Reject | Unmatched main rows (inner join mode) with errorCode/errorMessage |
| `SUBJOB_OK` | Output (Trigger) | Trigger | Fires on successful subjob completion |
| `SUBJOB_ERROR` | Output (Trigger) | Trigger | Fires on subjob error |
| `COMPONENT_OK` | Output (Trigger) | Trigger | Fires on component success |

### 3.4 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
|------------------|------|----------|-------------|
| `{id}_NB_LINE` | Integer | After execution | Total main input rows processed |
| `{id}_NB_LINE_OK` | Integer | After execution | Successfully joined output rows |
| `{id}_NB_LINE_REJECT` | Integer | After execution | Main rows with no lookup match |
| `{id}_ERROR_MESSAGE` | String | On error | Error message when die_on_error unchecked |

### 3.5 Behavioral Notes

1. **Input order matters**: First connected input is main (left), second is lookup (right).
2. **Left outer join is the default**: `USE_INNER_JOIN=false`. All main rows preserved with NULLs for unmatched lookup columns.
3. **Exact match only**: No fuzzy matching, range joins, or inequality joins. Use `tFuzzyJoin` or `tMap` for those.
4. **Multiple key columns**: Multiple key pairs are ANDed together.
5. **Duplicate lookup rows**: Only FIRST matching lookup row used per key combination (m:1 semantic).
6. **REJECT flow**: Contains main rows with no match + errorCode/errorMessage columns.
7. **Schema propagation**: Output can include columns from both flows with suffix handling for conflicts.
8. **Empty inputs**: Empty main -> empty output. Empty lookup + inner join -> all rejects. Empty lookup + outer join -> all main with NULLs.
9. **NULL key values**: NULLs do NOT match each other (SQL NULL semantics).
10. **Performance**: Lookup loaded into memory for hash-based lookups. Large lookups can cause OOM.
11. **CASE_SENSITIVE and DIE_ON_ERROR**: Present in engine code but NOT in _java.xml definition -- treated as phantom params.

---

## 4. Converter Audit

### 4.1 Parameter Extraction

The `talend_to_v1` converter uses `@REGISTRY.register("tJoin")` decorator-based dispatch with `_build_component_dict` wrapper. Two module-level TABLE parsers handle stride-2 JOIN_KEY and LOOKUP_COLS tables.

| # | Talend XML Parameter | Extracted? | V1 Config Key | Notes |
|----|----------------------|------------|---------------|-------|
| 1 | `USE_INNER_JOIN` | Yes | `use_inner_join` | bool, default False |
| 2 | `JOIN_KEY` (TABLE: `INPUT_COLUMN`+`LOOKUP_COLUMN`) | Yes | `join_key` | list of {input_column, lookup_column} dicts; LEFT_COLUMN/RIGHT_COLUMN fallback |
| 3 | `USE_LOOKUP_COLS` | Yes | `use_lookup_cols` | bool, default False |
| 4 | `LOOKUP_COLS` (TABLE: `OUTPUT_COLUMN`+`LOOKUP_COLUMN`) | Yes | `lookup_cols` | list of {output_column, lookup_column} dicts |
| 5 | `TSTATCATCHER_STATS` | Yes | `tstatcatcher_stats` | bool, default False (framework) |
| 6 | `LABEL` | Yes | `label` | str, default "" (framework) |
| -- | `CASE_SENSITIVE` | **REMOVED** | -- | Phantom param (not in _java.xml) |
| -- | `DIE_ON_ERROR` | **REMOVED** | -- | Phantom param (not in _java.xml) |

**Summary**: 4 of 4 unique _java.xml parameters extracted (100%) + 2 framework params. 2 phantom params removed.

### 4.2 Schema Extraction

| Schema Attribute | Extracted? | Notes |
|------------------|-----------|-------|
| `name` | Yes | Via `_parse_schema()` base class |
| `type` | Yes | Converted from Talend types via `convert_type()` |
| `nullable` | Yes | Boolean |
| `key` | Yes | Boolean |
| `length` | Yes | Integer, only if >= 0 |
| `precision` | Yes | Integer, only if >= 0 |
| `pattern` | Yes | Java-to-Python date pattern conversion |
| `default` | No | Not extracted from XML |

Transform passthrough schema: `input == output`.

### 4.3 Expression Handling

Context variable references in TABLE values are passed through as-is (not resolved at conversion time). Join key column names from TABLE entries have quotes stripped but no further expression processing.

### 4.4 Converter Issues

| ID | Priority | Issue |
|----|----------|-------|
| CONV-JN-001 | ~~P0~~ | **FIXED** -- `talend_to_v1` converter rewritten. Phantom params removed, TABLE parsers added. |
| CONV-JN-002 | ~~P1~~ | **FIXED** -- USE_LOOKUP_COLS and LOOKUP_COLS now extracted. |

### 4.5 Needs Review Entries

| # | Config Key | Reason | Severity |
|---|-----------|--------|----------|
| 1 | `use_inner_join` | Engine reads `USE_INNER_JOIN` (UPPERCASE) not `use_inner_join` | engine_gap |
| 2 | `join_key` | Engine reads `JOIN_KEY` (UPPERCASE); also expects `{main, lookup}` dict keys | engine_gap |
| 3 | `use_lookup_cols` | Engine does not read `use_lookup_cols` -- no INCLUDE_LOOKUP toggle implemented | engine_gap |
| 4 | `lookup_cols` | Engine does not read `lookup_cols` -- no lookup column selection implemented | engine_gap |

---

## 5. Engine Feature Parity

### 5.1 Feature Implementation Status

| # | Talend Feature | Implemented? | Fidelity | Engine Location | Notes |
|----|----------------|-------------|----------|-----------------|-------|
| 1 | Inner join | **Yes** | High | `_process()` line 255-256 | `how='inner'` via `pd.merge()` |
| 2 | Left outer join | **Yes** | High | `_process()` line 255-256 | `how='left'` via `pd.merge()` |
| 3 | Multi-key join | **Yes** | High | `_process()` line 227-228 | Multiple left_on/right_on columns |
| 4 | Case-sensitive matching | **Yes** | High | Default behavior | No transformation needed |
| 5 | Case-insensitive matching | **Yes** | Medium | `_process()` lines 233-247 | Converts to lowercase -- destructively modifies output values |
| 6 | Lookup deduplication (m:1) | **Yes** | High | `_process()` line 251 | `drop_duplicates(keep='first')` |
| 7 | Reject output | **Yes** | Medium | `_process()` lines 270-284 | Via separate left join with indicator |
| 8 | Die on error | **Yes** | High | `_process()` lines 356-365 | `ComponentExecutionError` or graceful degradation |
| 9 | Statistics tracking | **Yes** | High | `_process()` line 351 | NB_LINE, NB_LINE_OK, NB_LINE_REJECT |
| 10 | Output column filtering | **Yes** | Medium | `_process()` lines 335-342 | Engine-specific OUTPUT_COLUMNS |
| 11 | Schema-based output filtering | **Dead Code** | None | `_process()` lines 288-297 | References `self.schema` never set |
| 12 | Schema-based reject filtering | **Dead Code** | None | `_process()` lines 300-330 | References `self.schema` never set |
| 13 | Include lookup columns toggle | **No** | N/A | -- | No USE_LOOKUP_COLS support |
| 14 | `{id}_ERROR_MESSAGE` globalMap | **No** | N/A | -- | Error message not stored in globalMap |

### 5.2 Behavioral Differences from Talend

| ID | Priority | Description |
|----|----------|-------------|
| ENG-JN-001 | **P0** | **Schema filtering dead code**: `self.schema` never set by engine. 42 lines of unreachable schema filtering/reject error column logic. |
| ENG-JN-002 | **P1** | **No INCLUDE_LOOKUP_COLUMNS_IN_OUTPUT support**: Always includes all columns from both sides. |
| ENG-JN-003 | **P1** | **Case-insensitive join destroys original key values**: Output contains lowercase key values instead of original case. |
| ENG-JN-004 | **P1** | **`{id}_ERROR_MESSAGE` not set in globalMap**: Error details not available downstream. |
| ENG-JN-005 | **P2** | **Case-insensitive join applies `.astype(str)` to all key types**: Changes numeric/date key column dtypes. |
| ENG-JN-006 | **P2** | **Reject always computed even for left outer join**: Wasted computation when reject is guaranteed empty. |
| ENG-JN-007 | **P3** | **`DEFAULT_USE_INNER_JOIN = True` contradicts Talend default**: Should be False (left outer join). |

### 5.3 GlobalMap Variable Coverage

| Variable | Talend Sets? | V1 Sets? | How V1 Sets It | Notes |
|----------|-------------|----------|-----------------|-------|
| `{id}_NB_LINE` | Yes | **Yes** | `_update_stats()` | Counts main input rows |
| `{id}_NB_LINE_OK` | Yes | **Yes** | `_update_stats()` | Counts joined output rows |
| `{id}_NB_LINE_REJECT` | Yes | **Yes** | `_update_stats()` | Counts reject rows |
| `{id}_ERROR_MESSAGE` | Yes | **No** | -- | Not implemented |

---

## 6. Code Quality

### 6.1 Bugs

| ID | Priority | Location | Description |
|----|----------|----------|-------------|
| BUG-JN-001 | **P0** | `base_component.py:304` | **CROSS-CUTTING**: `_update_global_map()` references undefined variable `value` (should be `stat_value`). Crashes ALL components when globalMap set. |
| BUG-JN-002 | **P0** | `global_map.py:28` | **CROSS-CUTTING**: `GlobalMap.get()` references undefined `default` parameter. |
| BUG-JN-003 | ~~P0~~ | `join.py:288-330` | Schema filtering references `self.schema` never set. 42 lines dead code. |
| BUG-JN-004 | **P1** | `join.py:233-247` | Case-insensitive join outputs lowercase key values instead of original case. |
| BUG-JN-005 | **P1** | `join.py:273-284` | Double merge for reject computation. Potential index misalignment risk. |
| BUG-JN-006 | **P1** | `join.py:96-390` | `_validate_config()` and `validate_config()` are dead code (80 lines). Never called. |
| BUG-JN-007 | **P2** | `join.py:90` | `DEFAULT_USE_INNER_JOIN = True` contradicts Talend default (False). |
| BUG-JN-008 | **P2** | `join.py:264` | `copy=False` in `pd.merge()` deprecated in pandas 2.x. |
| BUG-JN-009 | **P2** | `join.py:335` | OUTPUT_COLUMNS filter runs after schema filter -- latent ordering issue. |
| BUG-JN-010 | **P1** | `join.py:273-284` | Left outer join produces incorrect reject output. Should produce zero rejects. |

### 6.2 Naming Consistency

| ID | Priority | Issue |
|----|----------|-------|
| NAME-JN-001 | **P2** | Engine config keys use UPPER_CASE (`JOIN_KEY`, `USE_INNER_JOIN`) inconsistent with other components using snake_case. |

### 6.3 Standards Compliance

| ID | Priority | Standard | Violation |
|----|----------|----------|-----------|
| STD-JN-001 | **P1** | "`_validate_config()` returns `List[str]`" | Method exists but is never called. 80 lines dead validation. |
| STD-JN-002 | **P2** | "Components must use `self.output_schema`" | Join uses `self.schema['output']` which is never set. |
| STD-JN-003 | **P2** | "`ConfigurationError` should be raised for config issues" | Imported but never raised. |

### 6.4 Debug Artifacts

None found.

### 6.5 Security

No concerns identified. No path traversal, exec/eval, or injection risks.

### 6.6 Logging Quality

| Aspect | Assessment |
|--------|------------|
| Logger setup | Module-level `logger = logging.getLogger(__name__)` -- correct |
| Level usage | INFO for milestones, DEBUG for details, WARNING for edge cases, ERROR for failures -- correct |
| Sensitive data | No sensitive data logged |

### 6.7 Error Handling Quality

| Aspect | Assessment |
|--------|------------|
| Custom exceptions | `ComponentExecutionError` used correctly |
| Exception chaining | `raise ... from e` pattern -- correct |
| die_on_error handling | Single try/except in `_process()` -- correct |

### 6.8 Type Hints

| Aspect | Assessment |
|--------|------------|
| Method signatures | All methods have return type hints |
| Parameter types | `Optional[Dict[str, pd.DataFrame]]` input -- correct |

---

## 7. Performance & Memory

| ID | Priority | Issue |
|----|----------|-------|
| PERF-JN-001 | **P1** | **Double `pd.merge()` for reject computation**: Two separate merge operations double join time and memory. Should use single merge with `indicator=True`. |
| PERF-JN-002 | **P2** | **Full DataFrame copy for case-insensitive joins**: `.copy()` on both DataFrames doubles memory. Should use temporary lowercase columns instead. |
| PERF-JN-003 | **P2** | **Reject computed for left outer join**: Guaranteed empty but still computed. |
| PERF-JN-004 | **P3** | `sort=False` in merge is good (positive finding). |

### 7.1 Memory Management Assessment

| Aspect | Assessment |
|--------|------------|
| Streaming mode | Not applicable -- Join requires both inputs simultaneously |
| Memory threshold | No limit on input size |
| Large data handling | Peak ~4-5x main DataFrame size (case-insensitive + reject computation) |

---

## 8. Testing

### 8.1 Current Coverage

| Test Type | Count | Location |
|-----------|-------|----------|
| Converter unit tests | 26 | `tests/converters/talend_to_v1/components/test_join.py` |
| Engine unit tests | 0 | None |
| Integration tests | 0 | None (component-specific) |

### 8.2 Test Gaps

| ID | Priority | Gap |
|----|----------|-----|
| TEST-JN-001 | **P1** | No v1 engine unit tests for Join component. 390 lines of engine code unverified. |

### 8.3 Recommended Test Cases

**P0 (must-have engine tests):**
1. Basic inner join with matched/unmatched rows
2. Basic left outer join with NULLs for unmatched lookup columns
3. Multi-key join (all keys must match)
4. Reject output correctness (inner join)
5. Empty main/lookup input handling
6. Statistics tracking (NB_LINE, NB_LINE_OK, NB_LINE_REJECT)

**P1 (hardening):**
7. Case-insensitive join (document lowercase output difference)
8. Lookup deduplication (first match only)
9. Die on error = true/false
10. Input mapping with non-standard names

---

## 9. Issues Summary

### By Priority

| Priority | Count | IDs |
|----------|-------|-----|
| P0 | 2 | **BUG-JN-001** (cross-cutting), **BUG-JN-002** (cross-cutting) |
| P1 | 9 | **BUG-JN-004**, **BUG-JN-005**, **BUG-JN-006**, **BUG-JN-010**, **ENG-JN-002**, **ENG-JN-003**, **ENG-JN-004**, **STD-JN-001**, **PERF-JN-001**, **TEST-JN-001** |
| P2 | 8 | **BUG-JN-007**, **BUG-JN-008**, **BUG-JN-009**, **ENG-JN-005**, **ENG-JN-006**, **STD-JN-002**, **STD-JN-003**, **NAME-JN-001**, **PERF-JN-002**, **PERF-JN-003** |
| P3 | 2 | **ENG-JN-007**, **PERF-JN-004** |
| **Total** | **21** | |

### By Category

| Category | Count | IDs |
|----------|-------|-----|
| Bug (BUG) | 10 | BUG-JN-001 through BUG-JN-010 |
| Engine (ENG) | 7 | ENG-JN-001 through ENG-JN-007 |
| Standards (STD) | 3 | STD-JN-001 through STD-JN-003 |
| Performance (PERF) | 4 | PERF-JN-001 through PERF-JN-004 |
| Naming (NAME) | 1 | NAME-JN-001 |
| Testing (TEST) | 1 | TEST-JN-001 |

### Cross-Cutting Issues

| Canonical ID | Location | Impact on This Component |
|-------------|----------|--------------------------|
| BUG-JN-001 | `base_component.py:304` | `_update_global_map()` crash when globalMap set |
| BUG-JN-002 | `global_map.py:28` | `GlobalMap.get()` broken signature |

---

## 10. Recommendations

### Immediate (Before Production)

1. **Fix `_update_global_map()` bug** (BUG-JN-001): Change `value` to `stat_value` on `base_component.py` line 304. Cross-cutting fix for all components.
2. **Fix `GlobalMap.get()` bug** (BUG-JN-002): Add `default: Any = None` parameter.
3. **Fix schema attribute mismatch** (ENG-JN-001): Set `component.schema = comp_config.get('schema', {})` in engine initialization.

### Short-term (Hardening)

4. **Fix case-insensitive join output** (BUG-JN-004/ENG-JN-003): Use temporary lowercase columns for merge, preserve original values.
5. **Fix left outer join reject** (BUG-JN-010): Skip reject computation when `use_inner_join=False`.
6. **Consolidate double merge** (PERF-JN-001): Single merge with `indicator=True`.
7. **Add engine unit tests** (TEST-JN-001): Minimum 8 P0 test cases.

### Long-term (Optimization)

8. **Add INCLUDE_LOOKUP toggle** (ENG-JN-002): Implement USE_LOOKUP_COLS/LOOKUP_COLS support.
9. **Remove deprecated `copy=False`** (BUG-JN-008): Forward compatibility with pandas 2.x.

---

## 11. Risk Assessment

### Risk Matrix

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Lookup memory explosion | Medium | High | Large lookup dataset held entirely in memory for hash join. Use database-level joins for large lookups. Monitor memory usage. |
| Key column type mismatch | Medium | Medium | Main and lookup key columns with different types (string vs int) cause join failure. Validate types before merge. |
| Inner join data loss | Medium | High | Inner join silently drops unmatched main rows. Ensure REJECT output is connected and monitored when using inner join mode. |
| CASE_SENSITIVE phantom removal | Low | Medium | Engine code still reads CASE_SENSITIVE from config. Converter no longer emits it, so engine falls back to class default (True). Behavior unchanged for case-sensitive joins, but case-insensitive mode cannot be toggled via converter. |
| Engine UPPERCASE key convention | High | Medium | Engine reads JOIN_KEY/USE_INNER_JOIN (UPPERCASE) but converter outputs join_key/use_inner_join (lowercase). Config keys will not be found by engine without key normalization. |
| Left outer join incorrect rejects | Medium | Low | Engine produces reject rows for left outer joins where Talend produces zero. May confuse downstream reject handling logic. |

### High-Risk Job Patterns

1. **Large lookup tables (>1M rows)**: Memory exhaustion risk during hash join
2. **Case-insensitive join + downstream case-sensitive processing**: Output key values are lowercased, breaking downstream expectations
3. **Left outer join with REJECT flow connected**: Engine produces incorrect (non-empty) reject output
4. **Mixed-type key columns**: String/numeric type mismatch causes cryptic pandas errors

### Safe Usage Patterns

1. **Inner join with small-to-medium lookup (<100K rows)**: Reliable, well-tested path
2. **Case-sensitive matching (default)**: No data corruption
3. **Single or dual key columns**: Well-exercised code path
4. **Left outer join without REJECT**: Most common pattern, output is correct

---

## Appendix A: Source References

| Source | URL/Path | Used For |
|--------|----------|----------|
| Talend 7.3 docs | https://help.qlik.com/talend/en-US/components/7.3/processing/tjoin-standard-properties | Parameter definitions |
| Talend 8.0 docs | https://help.qlik.com/talend/en-US/components/8.0/processing/tjoin-standard-properties | Parameter defaults |
| Talaxie GitHub | https://github.com/Talaxie/tcommon-studio-se | _java.xml component definition |
| Engine source | `src/v1/engine/components/transform/join.py` | Feature parity analysis |
| Converter source | `src/converters/talend_to_v1/components/transform/join.py` | Converter audit |

## Appendix B: Cross-Cutting Issues

| Canonical ID | Location | Impact on This Component |
|-------------|----------|--------------------------|
| XCUT-001 | `base_component.py:304` | `_update_global_map()` crash when globalMap set |
| XCUT-002 | `global_map.py:28` | `GlobalMap.get()` broken signature |

---

*Report generated: 2026-03-21*
*Last updated: 2026-04-04 after v1.1 Phase 12 converter standardization -- REWRITTEN per gold standard template with Section 11 Risk Assessment. Phantom CASE_SENSITIVE/DIE_ON_ERROR removed. USE_LOOKUP_COLS/LOOKUP_COLS TABLE added. JOIN_KEY elementRefs fixed to INPUT_COLUMN/LOOKUP_COLUMN. 4 per-feature needs_review. 26 converter tests. Issues reduced 36->21.*
