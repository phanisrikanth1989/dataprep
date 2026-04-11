# Audit Report: tUnite / Unite

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
| **Talend Name** | `tUnite` |
| **V1 Engine Class** | `Unite` |
| **Engine File** | `src/v1/engine/components/transform/unite.py` (393 lines) |
| **Converter Parser** | `src/converters/talend_to_v1/components/transform/unite.py` (60 lines) |
| **Converter Dispatch** | `@REGISTRY.register("tUnite")` decorator-based dispatch |
| **Registry Aliases** | `Unite`, `tUnite` |
| **Category** | Transform / Processing |

### Key Files

| File | Purpose |
| ------ | --------- |
| `src/v1/engine/components/transform/unite.py` | Engine implementation (393 lines) |
| `src/converters/talend_to_v1/components/transform/unite.py` | Converter class (60 lines) |
| `tests/converters/talend_to_v1/components/test_unite.py` | Converter tests (18 tests) |
| `src/v1/engine/base_component.py` | Base class |
| `src/v1/engine/global_map.py` | GlobalMap storage |

---

## 2. Scorecard

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
| ----------- | ------- | ---- | ---- | ---- | ---- | --------- |
| Converter Coverage | **G** | 0 | 0 | 0 | 0 | 0 unique + 2 framework params extracted (100%); _build_component_dict; passthrough schema; 0 needs_review (engine defaults compatible) |
| Code Quality | **G** | 0 | 0 | 0 | 0 | Gold standard converter pattern; clean, minimal, well-documented module docstring with config mapping |
| Testing | **Y** | 0 | 0 | 1 | 0 | 18 converter tests across 7 test classes; no engine unit tests (TEST-UNI-001) |
| Overall | **Y** | 0 | 0 | 1 | 0 | Converter production-ready; engine unit tests needed for Green |

**Overall: YELLOW -- Converter is gold standard; engine unit tests needed for full Green**

**Top Actions**: Add engine unit tests for Unite component (TEST-UNI-001)

---

## 3. Talend Feature Baseline

### What tUnite Does

`tUnite` merges multiple input data flows into a single output data flow using UNION ALL semantics. It is one of the fundamental data integration components for combining rows from multiple upstream paths into one stream. Every input row from every connected input flow appears in the output, without deduplication or filtering.

The component is commonly used when data arrives from multiple sources (e.g., different files, database tables, or processing branches) and must be combined into a single stream for downstream processing. Deduplication, if needed, requires a separate `tUniqRow` component downstream.

**Source**: [tUnite Standard Properties (Talend 8.0)](https://help.qlik.com/talend/en-US/components/8.0/processing/tunite-standard-properties), [Talaxie GitHub _java.xml](https://raw.githubusercontent.com/Talaxie/tdi-studio-se/refs/heads/master/main/plugins/org.talend.designer.components.localprovider/components/tUnite/tUnite_java.xml)
**Component family**: Processing (Transform)
**Available in**: All Talend products (Standard)
**Required JARs**: None (built-in)

### 3.1 Basic Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
| --- | ----------- | ----------------- | ------ | --------- | ------------- |
| 1 | Schema | `SCHEMA` | Schema editor | -- | Propagated from first upstream connection via "Sync Columns". tUnite passes through the input schema identically to its output. All inputs must share the same schema. |
| 2 | Label | `LABEL` | String (TEXT) | `""` | Text label for the component in Talend Studio. No runtime impact. Framework param. |
| 3 | tStatCatcher Statistics | `TSTATCATCHER_STATS` | Boolean (CHECK) | `false` | Capture processing metadata for tStatCatcher. Framework param. |

**Key observation**: tUnite has **no user-configurable parameters** beyond SCHEMA and the two framework params. The _java.xml defines only `SCHEMA` (as SCHEMA_TYPE). There is no `mode`, `remove_duplicates`, `sort_output`, or `merge_columns` parameter in _java.xml -- those exist only in the v1 engine implementation.

### 3.2 Advanced Settings

None. tUnite has no advanced settings tab.

### 3.3 Connection Types

| Connector | Direction | Type | Description |
| ----------- | ----------- | ------ | ------------- |
| `Row (Main)` | Input | Row > Main | Multiple input data flows. All connected inputs are merged. |
| `Row (Main)` | Output | Row > Main | Single merged output flow containing all input rows. |
| `COMPONENT_OK` | Output (Trigger) | Trigger | Fires on successful completion |
| `COMPONENT_ERROR` | Output (Trigger) | Trigger | Fires on error |

### 3.4 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
| ------------------ | ------ | ---------- | ------------- |
| `{id}_NB_LINE` | Integer | After execution | Total rows processed across all inputs |
| `{id}_NB_LINE_OK` | Integer | After execution | Rows successfully merged to output |
| `{id}_NB_LINE_REJECT` | Integer | After execution | Rows rejected (always 0 for unite) |

### 3.5 Behavioral Notes

1. tUnite is a pure UNION ALL -- every input row appears in the output. No deduplication, no filtering, no transformation.
2. All input flows must have identical schemas. Talend Studio enforces this via "Sync Columns" propagation.
3. The order of rows in the output is determined by the order of input connections and the order of rows within each input.
4. There is no `mode`, `remove_duplicates`, `sort_output`, `merge_columns`, or `merge_how` parameter in the _java.xml definition -- these exist only in the v1 engine implementation as engine-specific extensions.

---

## 4. Converter Audit

### 4.1 Parameter Extraction

The converter uses `_build_component_dict` with `type_name="Unite"` and passthrough schema pattern. No unique parameters to extract beyond framework params.

| # | Talend XML Parameter | Extracted? | V1 Config Key | Notes |
| ---- | ---------------------- | ------------ | --------------- | ------- |
| 1 | `SCHEMA` | Yes | schema (passthrough) | `_parse_schema(node)` with input == output |
| 2 | `TSTATCATCHER_STATS` | Yes | `tstatcatcher_stats` | `_get_bool(node, ..., False)` -- framework param |
| 3 | `LABEL` | Yes | `label` | `_get_str(node, ..., "")` -- framework param |

**Summary**: 0 of 0 unique parameters extracted (N/A -- no unique params). 2 framework params extracted. 100% coverage.

### 4.2 Schema Extraction

| Schema Attribute | Extracted? | Notes |
| ------------------ | ----------- | ------- |
| `name` | Yes | Via `_parse_schema()` |
| `type` | Yes | Converted from Talend types via `convert_type()` |
| `nullable` | Yes | Boolean |
| `key` | Yes | Boolean |
| `length` | Yes | When >= 0 |
| `precision` | Yes | When >= 0 |
| `pattern` | Yes | Java-to-Python date pattern conversion |
| `default` | No | Not implemented in base class |

**Passthrough pattern**: `schema = {"input": schema_cols, "output": schema_cols}` -- input and output are identical references, establishing the transform passthrough pattern.

### 4.3 Expression Handling

Not applicable. tUnite has no expression-capable parameters.

### 4.4 Converter Issues

None. Converter is gold standard.

### 4.5 Needs Review Entries

None. Engine defaults (UNION mode, no dedup) match Talend UNION ALL behavior. Engine-specific features (mode, remove_duplicates, sort_output, merge_columns, merge_how, keep, sort_columns) are engine extensions that default to values compatible with Talend behavior. No needs_review entries required.

---

## 5. Engine Feature Parity

### 5.1 Feature Implementation Status

| # | Talend Feature | Implemented? | Fidelity | Engine Location | Notes |
| ---- | ---------------- | ------------- | ---------- | ----------------- | ------- |
| 1 | UNION ALL merge | **Yes** | High | `_process_batch()` line 220-223 | `pd.concat(dataframes, ignore_index=True, sort=False)` |
| 2 | Multiple input handling | **Yes** | High | `execute()` line 117-144 | Accepts dict of DataFrames |
| 3 | Schema passthrough | **Partial** | Medium | N/A | Engine does not validate that all inputs share the same schema |
| 4 | Error handling | **Yes** | Medium | `_process_batch()` line 308-310 | Generic exception handling |
| 5 | Statistics tracking | **Yes** | High | `_update_stats()` line 293 | NB_LINE, NB_LINE_OK, NB_LINE_REJECT |
| 6 | MERGE mode | **Extra** | N/A | `_process_batch()` line 226-271 | Engine-specific extension not in Talend |
| 7 | Remove duplicates | **Extra** | N/A | `_process_batch()` line 276-280 | Engine-specific extension not in Talend |
| 8 | Sort output | **Extra** | N/A | `_process_batch()` line 283-289 | Engine-specific extension not in Talend |
| 9 | Streaming mode | **Extra** | N/A | `_process_streaming()` line 312-361 | Engine-specific streaming support |

### 5.2 Behavioral Differences from Talend

| ID | Priority | Description |
| ---- | ---------- | ------------- |
| ENG-UNI-001 | **P2** | Engine reads `mode` (default 'UNION') which has no _java.xml equivalent. Default is safe (matches Talend). |
| ENG-UNI-002 | **P2** | Engine reads `remove_duplicates` (default False) which has no _java.xml equivalent. Default matches Talend (no dedup). |
| ENG-UNI-003 | **P2** | Engine reads `keep` (default 'first') which has no _java.xml equivalent. Only relevant when remove_duplicates=True. |
| ENG-UNI-004 | **P2** | Engine reads `sort_output` (default False) which has no _java.xml equivalent. Default preserves Talend row ordering. |
| ENG-UNI-005 | **P2** | Engine reads `sort_columns` (default []) which has no _java.xml equivalent. Only relevant when sort_output=True. |
| ENG-UNI-006 | **P2** | Engine reads `merge_columns` (default None) which has no _java.xml equivalent. Only relevant in MERGE mode. |
| ENG-UNI-007 | **P2** | Engine reads `merge_how` (default 'inner') which has no _java.xml equivalent. Only relevant in MERGE mode. |
| ENG-UNI-008 | **P2** | Engine has MERGE mode which is a fundamentally different operation from Talend's UNION ALL. No Talend equivalent. |

### 5.3 GlobalMap Variable Coverage

| Variable | Talend Sets? | V1 Sets? | How V1 Sets It | Notes |
| ---------- | ------------- | ---------- | ----------------- | ------- |
| `{id}_NB_LINE` | Yes | Yes | `_update_stats()` | Total input rows across all inputs |
| `{id}_NB_LINE_OK` | Yes | Yes | `_update_stats()` | Output rows |
| `{id}_NB_LINE_REJECT` | Yes | Yes | `_update_stats()` | Always 0 |
| `{id}_INPUT_COUNT` | No | Yes | globalMap.put() line 297 | Engine-specific: number of input streams |
| `{id}_MODE` | No | Yes | globalMap.put() line 298 | Engine-specific: combination mode used |
| `{id}_INPUT_ROWS` | No | Yes | globalMap.put() line 299 | Engine-specific: total input rows |
| `{id}_OUTPUT_ROWS` | No | Yes | globalMap.put() line 300 | Engine-specific: output row count |

---

## 6. Code Quality

### 6.1 Bugs

| ID | Priority | Location | Description |
| ---- | ---------- | ---------- | ------------- |
| BUG-UNI-001 | **P2** | `unite.py:54-57` | `_validate_config()` performs mode/merge validation but is never called by base class -- dead code |

### 6.2 Naming Consistency

No naming issues found in converter or engine.

### 6.3 Standards Compliance

| ID | Priority | Standard | Violation |
| ---- | ---------- | ---------- | ----------- |
| STD-UNI-001 | **P2** | "_validate_config() called or dead code" | `_validate_config()` defined but never called by base class |

### 6.4 Debug Artifacts

None found.

### 6.5 Security

No concerns identified. tUnite is a pure data merging component with no file I/O, network, or expression evaluation.

### 6.6 Logging Quality

| Aspect | Assessment |
| -------- | ------------ |
| Logger setup | Correct -- `logging.getLogger(__name__)` |
| Level usage | Appropriate -- info for start/complete, warning for empty input, debug for per-input counts |
| Sensitive data | No concerns -- only logs row counts and input names |

### 6.7 Error Handling Quality

| Aspect | Assessment |
| -------- | ------------ |
| Custom exceptions | Generic Exception re-raise in `_process_batch()` |
| Exception chaining | No -- bare `raise` without chaining |
| die_on_error handling | Not present -- engine always raises on error |

### 6.8 Type Hints

| Aspect | Assessment |
| -------- | ------------ |
| Method signatures | Complete -- return types and parameter types on all methods |
| Parameter types | Correct -- Optional[Any], Dict[str, Any], List[str] |

---

## 7. Performance & Memory

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| PERF-UNI-001 | **P2** | `pd.concat()` creates a full copy of all input data. For N inputs totaling M rows, peak memory is approximately 2x M rows (all inputs + concatenated result). No streaming option for UNION mode. |
| PERF-UNI-002 | **P3** | MERGE mode with no `merge_columns` falls back to common-column detection (set intersection per merge step), which is O(n_cols) per merge. Acceptable for typical use but not optimized. |

### 7.1 Memory Management Assessment

| Aspect | Assessment |
| -------- | ------------ |
| Streaming mode | Implemented for UNION only via generator (`_process_streaming()`). MERGE falls back to batch. |
| Memory threshold | No threshold -- loads all inputs into memory before concat |
| Large data handling | Memory-bound by sum of all input sizes. No chunked processing in batch mode. |

---

## 8. Testing

### 8.1 Current Coverage

| Test Type | Count | Location |
| ----------- | ------- | ---------- |
| Converter unit tests | 18 | `tests/converters/talend_to_v1/components/test_unite.py` |
| Engine unit tests | 0 | None |
| Integration tests | 0 | None (component-specific) |

### 8.2 Test Gaps

| ID | Priority | Gap |
| ---- | ---------- | ----- |
| TEST-UNI-001 | **P2** | No engine unit tests for Unite component |

### 8.3 Recommended Test Cases

- Engine: basic UNION of 2 DataFrames with identical schemas
- Engine: UNION with 3+ inputs
- Engine: empty DataFrame input (some inputs empty, some populated)
- Engine: MERGE mode with common columns
- Engine: MERGE mode with specified merge_columns
- Engine: remove_duplicates=True
- Engine: sort_output=True with valid sort_columns
- Engine: streaming mode UNION

---

## 9. Issues Summary

### By Priority

| Priority | Count | IDs |
| ---------- | ------- | ----- |
| P0 | 0 | -- |
| P1 | 0 | -- |
| P2 | 11 | ENG-UNI-001 through ENG-UNI-008, BUG-UNI-001, STD-UNI-001, PERF-UNI-001, TEST-UNI-001 |
| P3 | 1 | PERF-UNI-002 |
| **Total** | **12** | |

### By Category

| Category | Count | IDs |
| ---------- | ------- | ----- |
| Engine (ENG) | 8 | ENG-UNI-001 through ENG-UNI-008 |
| Bug (BUG) | 1 | BUG-UNI-001 |
| Standards (STD) | 1 | STD-UNI-001 |
| Performance (PERF) | 2 | PERF-UNI-001, PERF-UNI-002 |
| Testing (TEST) | 1 | TEST-UNI-001 |

### Cross-Cutting Issues

| Canonical ID | Location | Impact on This Component |
| ------------- | ---------- | -------------------------- |
| XCUT-001 | `base_component.py` | `_update_global_map()` crash when globalMap set |
| XCUT-002 | `base_component.py` | `_validate_config()` never called |

---

## 10. Recommendations

### Immediate (Before Production)

No P0 or P1 issues. Converter is production-ready.

### Short-term (Hardening)

- Add engine unit tests (TEST-UNI-001)
- Address dead `_validate_config()` code (cross-cutting with other components)

### Long-term (Optimization)

- Consider chunked concat for memory efficiency on large inputs (PERF-UNI-001)
- Document or restrict MERGE mode to prevent accidental use (ENG-UNI-008)

---

## 11. Risk Assessment

### Risk Matrix

| Risk | Likelihood | Impact | Mitigation |
| ------ | ----------- | -------- | ------------ |
| MERGE mode accidentally triggered via engine config | Low | High | Engine defaults to UNION mode. Converter never outputs `mode` key. Risk only if manual JSON editing sets mode=MERGE. |
| Schema mismatch across inputs | Medium | Medium | tUnite assumes all inputs have identical schemas. Engine uses `pd.concat(sort=False)` which produces NaN columns if schemas differ. No validation in converter or engine. Talend Studio prevents this via Sync Columns. |
| Streaming mode data ordering | Low | Low | Streaming mode only supports UNION. Generator yields chunks from each input sequentially. Row order may differ from batch mode if inputs are generators vs DataFrames. |
| Duplicate handling performance | Low | Medium | `remove_duplicates=False` is default (correct for UNION ALL). If accidentally set to True on large datasets, `drop_duplicates()` may be slow. Not a Talend param -- risk only from manual config. |
| Multiple globalMap puts on error | Low | Medium | If `_process_batch()` raises after partial processing, globalMap stats reflect partial state. No rollback mechanism. |

### High-Risk Job Patterns

- Manual JSON config that sets `mode` to `MERGE` -- fundamentally different behavior than Talend tUnite
- Inputs with mismatched schemas (different column names/types) -- produces NaN columns without error
- Very large inputs (millions of rows from many sources) in batch mode -- memory bound by sum of all inputs

### Safe Usage Patterns

- All inputs share identical schema (enforced at Talend design time)
- Default engine config (UNION mode, no dedup, no sort) -- matches Talend UNION ALL exactly
- Converter output (2 framework keys only) -- no risk of triggering engine-specific features

---

## Appendix A: Source References

| Source | URL/Path | Used For |
| -------- | ---------- | ---------- |
| Talend docs | [tUnite Standard Properties](https://help.qlik.com/talend/en-US/components/8.0/processing/tunite-standard-properties) | Parameter definitions |
| Talaxie GitHub _java.xml | [tUnite_java.xml](https://raw.githubusercontent.com/Talaxie/tdi-studio-se/refs/heads/master/main/plugins/org.talend.designer.components.localprovider/components/tUnite/tUnite_java.xml) | Component definition XML |
| Engine source | `src/v1/engine/components/transform/unite.py` | Feature parity analysis (393 lines) |
| Converter source | `src/converters/talend_to_v1/components/transform/unite.py` | Converter audit (60 lines) |

## Appendix B: Engine Config Key Mapping

| Engine Config Key | _java.xml Param | Default (Engine) | Default (_java.xml) | Status |
| ------------------- | ----------------- | ------------------ | --------------------- | -------- |
| `mode` | N/A | `'UNION'` | N/A | Engine-only key -- default matches Talend UNION ALL |
| `remove_duplicates` | N/A | `False` | N/A | Engine-only key -- default matches Talend (no dedup) |
| `keep` | N/A | `'first'` | N/A | Engine-only key -- only relevant if remove_duplicates=True |
| `sort_output` | N/A | `False` | N/A | Engine-only key -- default preserves row ordering |
| `sort_columns` | N/A | `[]` | N/A | Engine-only key -- only relevant if sort_output=True |
| `merge_columns` | N/A | `None` | N/A | Engine-only key -- only relevant in MERGE mode |
| `merge_how` | N/A | `'inner'` | N/A | Engine-only key -- only relevant in MERGE mode |
| `tstatcatcher_stats` | `TSTATCATCHER_STATS` | N/A | `false` | Framework param -- converter extracts correctly |
| `label` | `LABEL` | N/A | `""` | Framework param -- converter extracts correctly |

---

*Report generated: 2026-04-04*
*Last updated: 2026-04-04 after Phase 11 gold standard rewrite*
