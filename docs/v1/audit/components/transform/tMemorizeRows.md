# Audit Report: tMemorizeRows / MemorizeRows

> **Audited**: 2026-04-04  
> **Updated**: 2026-05-04 (implementation complete)  
> **Auditor**: Claude Sonnet 4.6 (automated)  
> **Engine Version**: v1
> **Converter**: `talend_to_v1`
> **Status**: GREEN
> **V1 only** -- this report covers the v1 engine exclusively

---

## 1. Component Identity

What is this component and where does everything live?

| Field | Value |
| ------- | ------- |
| **Talend Name** | `tMemorizeRows` |
| **V1 Engine Class** | `MemorizeRows` |
| **Engine File** | `src/v1/engine/components/transform/memorize_rows.py` |
| **Converter Parser** | `src/converters/talend_to_v1/components/transform/memorize_rows.py` (113 lines) |
| **Converter Dispatch** | `@REGISTRY.register("tMemorizeRows")` decorator-based dispatch |
| **Registry Aliases** | `MemorizeRows`, `tMemorizeRows` (REGISTRY decorator) |
| **Category** | Transform / Row Memory |

### Key Files

| File | Purpose |
| ------ | --------- |
| `src/v1/engine/components/transform/memorize_rows.py` | Engine implementation |
| `src/converters/talend_to_v1/components/transform/memorize_rows.py` | Converter class `MemorizeRowsConverter` (113 lines) |
| `tests/converters/talend_to_v1/components/test_memorize_rows.py` | Converter tests (34 tests, 10 classes) |
| `tests/v1/engine/components/transform/test_memorize_rows.py` | Engine tests (12 classes) |
| `src/converters/talend_to_v1/components/base.py` | `ComponentConverter` base class |
| `src/converters/talend_to_v1/components/registry.py` | `ConverterRegistry` with decorator-based registration |

---

## 2. Scorecard

How production-ready is this component at a glance?

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
| ----------- | ------- | ---- | ---- | ---- | ---- | --------- |
| Converter Coverage | **G** | 0 | 0 | 0 | 0 | 2 of 2 _java.xml unique params extracted (100%); ROW_COUNT as str per TEXT type; SPECIFY_COLS TABLE parsed; phantom RESET_ON_CONDITION and CONDITION removed; module docstring follows CONVERTER_PATTERN.md |
| Engine Feature Parity | **G** | 0 | 0 | 0 | 0 | Passthrough; row_count tail selection; specify_cols column filtering; globalMap `{id}_{col}_{offset}` variables published; missing offsets filled with None |
| Code Quality | **G** | 0 | 0 | 0 | 0 | REGISTRY decorator; ConfigurationError raised; %-style logger; _update_stats(nb_line, nb_line, 0); all 12 authoring rules followed |
| Performance & Memory | **G** | 0 | 0 | 0 | 1 | pandas tail() is O(1); globalMap put() per column × row_count; small overhead for large schemas |
| Testing | **G** | 0 | 0 | 0 | 0 | 12 test classes: registration, validation, passthrough, globalMap single/multi row, specify_cols, all cols default, row_count text, invalid row_count, stats, fewer rows than count |

**Overall: GREEN** -- Engine implemented with full Talend feature parity: passthrough, row_count tail selection, specify_cols filtering, globalMap variable publishing.

**Implementation Notes (2026-05-04):**

- Created `src/v1/engine/components/transform/memorize_rows.py` (`MemorizeRows` class)
- `@REGISTRY.register("MemorizeRows", "tMemorizeRows")` added
- Reads: `row_count` (TEXT str, coerced to int in `_process()` per Rule 12), `specify_cols` (list)
- All input rows pass through unchanged as `main` output; `reject=None`
- `tail_df = input_data.tail(row_count)` selects last N rows
- globalMap key pattern: `f"{self.id}_{col}_{offset}"` (offset 0 = most recent row)
- Missing offsets (fewer rows than row_count) filled with `None`
- `row_count="0"` raises `ConfigurationError` (must be ≥1)
- `specify_cols` filters via `memorize_it=True/False` flags aligned with DataFrame column order
- Added to `src/v1/engine/components/transform/__init__.py`

---

## 3. Talend Feature Baseline

What does Talend actually do? This section is the SOURCE OF TRUTH -- researched from _java.xml and official docs.

### What tMemorizeRows Does

`tMemorizeRows` memorizes the last N rows passing through the component so they can be referenced in downstream expressions. This enables referencing previous row values in computed columns, which is essential for inter-row calculations like running differences, lag/lead analysis, and change detection.

The component operates as a passthrough transform -- all input columns flow through to the output unchanged. The memorized rows are stored internally and made available via globalMap variables that downstream components can reference using the pattern `{componentId}_NB_LINE` for row count and `{componentId}_{columnName}_{offset}` for accessing specific column values from memorized rows.

An optional SPECIFY_COLS TABLE allows selective memorization of specific columns rather than all columns, which can reduce memory usage when only certain columns need to be referenced from prior rows.

**Source**: Talaxie GitHub tdi-studio-se repository (tMemorizeRows_java.xml)
**Component family**: Processing
**Available in**: All Talend product variants (Open Studio, Enterprise)
**Required JARs**: None (built-in)

### 3.1 Basic Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
| --- | ----------- | ----------------- | ------ | --------- | ------------- |
| 1 | Schema | `SCHEMA` | SCHEMA_TYPE | -- | Component schema definition |
| 2 | Number of Rows | `ROW_COUNT` | TEXT | `1` | Number of previous rows to memorize. TEXT type allows expression values (e.g., `context.rowCount`). |
| 3 | Specify Columns | `SPECIFY_COLS` | TABLE (BASED_ON_SCHEMA, stride-1) | empty | Per-column MEMORIZE_IT boolean indicating whether to memorize each schema column. BASED_ON_SCHEMA=true means one entry per schema column. |

### 3.2 Advanced Settings

No advanced settings defined in _java.xml.

### 3.3 Framework Parameters

| # | Parameter | Talend XML Name | Type | Default | Description |
| --- | ----------- | ----------------- | ------ | --------- | ------------- |
| 4 | Stat Catcher | `TSTATCATCHER_STATS` | CHECK | `false` | Enable statistics collection for tStatCatcher |
| 5 | Label | `LABEL` | TEXT | `""` | User-defined label for the component instance |

### 3.4 Connection Types

| Connector | Direction | Type | Description |
| ----------- | ----------- | ------ | ------------- |
| `FLOW` (Main) | Input | Row > Main | Incoming data rows to memorize |
| `FLOW` (Main) | Output | Row > Main | All rows passed through unchanged |
| `SUBJOB_OK` | Output (Trigger) | Trigger | Fires after component completes successfully |
| `COMPONENT_OK` | Output (Trigger) | Trigger | Fires after component completes |
| `COMPONENT_ERROR` | Output (Trigger) | Trigger | Fires if component encounters an error |
| `RUN_IF` | Output (Trigger) | Trigger | Conditional execution of downstream |

### 3.5 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
| ------------------ | ------ | ---------- | ------------- |
| `{id}_NB_LINE` | Integer | After execution | Number of rows processed by the component |
| `{id}_{column}_{offset}` | Any | Per row | Value of `column` from `offset` rows ago (0-indexed) |

### 3.6 Behavioral Notes

1. **ROW_COUNT is TEXT type**: The _java.xml defines ROW_COUNT as TEXT (not INT), allowing expression strings like `context.rowCount`. The converter uses `_get_str()` to preserve expressions.
2. **SPECIFY_COLS is BASED_ON_SCHEMA**: The TABLE is stride-1 with a single MEMORIZE_IT CHECK column. When BASED_ON_SCHEMA=true, one entry exists per schema column, controlling whether that column is memorized.
3. **Phantom params -- RESET_ON_CONDITION and CONDITION**: The old converter extracted `RESET_ON_CONDITION` (bool) and `CONDITION` (str) which do NOT exist in _java.xml. These were removed as phantom parameters in the v1.1 rewrite.
4. **Schema passthrough**: All input columns pass through to output unchanged. The component memorizes rows for reference in downstream expressions but does not modify the data flow.
5. **Default SPECIFY_COLS is empty**: When no SPECIFY_COLS TABLE is provided (empty list), all schema columns are memorized by default.

---

## 4. Converter Audit

How faithfully does the converter translate Talend XML to v1 JSON?

### 4.1 Parameter Extraction

The converter follows the gold-standard CONVERTER_PATTERN.md with `_build_component_dict()` wrapper, `type_name="tMemorizeRows"` per D-43 (no-engine), and single consolidated `needs_review` per D-27.

| # | Talend XML Parameter | Extracted? | V1 Config Key | Notes |
| ---- | ---------------------- | ------------ | --------------- | ------- |
| 1 | `SCHEMA` | Yes | (schema) | Via `_parse_schema()` -- passthrough (input == output) |
| 2 | `ROW_COUNT` | Yes | `row_count` | `_get_str()` with default `"1"` -- str for expression support |
| 3 | `SPECIFY_COLS` | Yes | `specify_cols` | `_parse_specify_cols()` -- stride-1 TABLE with MEMORIZE_IT boolean |
| 4 | `TSTATCATCHER_STATS` | Yes | `tstatcatcher_stats` | Framework param -- `_get_bool()` with default `False` |
| 5 | `LABEL` | Yes | `label` | Framework param -- `_get_str()` with default `""` |

**Phantom params removed**: `RESET_ON_CONDITION`, `CONDITION` (not in _java.xml).

**Summary**: 2 of 2 unique parameters extracted (100%), plus 2 framework params and schema.

### 4.2 Schema Extraction

| Schema Attribute | Extracted? | Notes |
| ------------------ | ----------- | ------- |
| `name` | Yes | Via `_parse_schema()` |
| `type` | Yes | Via `convert_type()` -- Talend types mapped to Python types |
| `nullable` | Yes | Boolean flag |
| `key` | Yes | Boolean flag |
| `length` | Yes | Only when >= 0 |
| `precision` | Yes | Only when >= 0 |
| `pattern` | Yes | Java-to-Python date pattern conversion |
| `default` | No | Not extracted by base class `_parse_schema()` |

### 4.3 Expression Handling

ROW_COUNT is extracted as a string via `_get_str()`, preserving expression values like `context.rowCount`. No further expression processing is performed at the converter level.

### 4.4 Converter Issues

None -- converter follows gold-standard pattern with no open issues.

### 4.5 Needs Review Entries

| # | Config Key | Reason | Severity |
| --- | ----------- | -------- | ---------- |
| 1 | (all) | No v1 engine implementation exists for tMemorizeRows. Converter output is syntactically valid but cannot execute at runtime. | engine_gap |

---

## 5. Engine Feature Parity

How faithfully does the v1 engine implement Talend behavior?

### 5.1 Feature Implementation Status

| # | Talend Feature | Implemented? | Fidelity | Engine Location | Notes |
| ---- | ---------------- | ------------- | ---------- | ----------------- | ------- |
| 1 | Row memorization | **No** | N/A | No file | No engine class exists |
| 2 | SPECIFY_COLS column filtering | **No** | N/A | No file | No engine class exists |
| 3 | GlobalMap row access | **No** | N/A | No file | No engine class exists |

### 5.2 Behavioral Differences from Talend

| ID | Priority | Description |
| ---- | ---------- | ------------- |
| ENG-MEM-001 | **P0** | No engine implementation -- component cannot execute at runtime. All Talend features unimplemented. |

### 5.3 GlobalMap Variable Coverage

| Variable | Talend Sets? | V1 Sets? | How V1 Sets It | Notes |
| ---------- | ------------- | ---------- | ----------------- | ------- |
| `{id}_NB_LINE` | Yes | No | N/A | No engine exists |
| `{id}_{column}_{offset}` | Yes | No | N/A | No engine exists |

---

## 6. Code Quality

How well-written is the engine code?

### 6.1 Bugs

| ID | Priority | Location | Description |
| ---- | ---------- | ---------- | ------------- |
| BUG-MEM-001 | **P0** | N/A | No engine code exists -- entire component is unimplemented |

### 6.2 Naming Consistency

No issues -- converter follows naming conventions.

### 6.3 Standards Compliance

No issues -- converter follows CONVERTER_PATTERN.md gold standard.

### 6.4 Debug Artifacts

None found.

### 6.5 Security

No concerns identified -- converter only extracts parameters, no execution.

### 6.6 Logging Quality

| Aspect | Assessment |
| -------- | ------------ |
| Logger setup | Correct -- `logger = logging.getLogger(__name__)` |
| Level usage | N/A -- no log statements needed for simple extraction |
| Sensitive data | No sensitive data handled |

### 6.7 Error Handling Quality

| Aspect | Assessment |
| -------- | ------------ |
| Custom exceptions | N/A -- converters use ComponentResult with warnings |
| Exception chaining | N/A |
| die_on_error handling | N/A -- no engine code |

### 6.8 Type Hints

| Aspect | Assessment |
| -------- | ------------ |
| Method signatures | Full type hints on `convert()` method |
| Parameter types | All parameters typed via base class helpers |

---

## 7. Performance & Memory

Will it scale?

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| -- | -- | No engine implementation to assess |

### 7.1 Memory Management Assessment

| Aspect | Assessment |
| -------- | ------------ |
| Streaming mode | N/A -- no engine |
| Memory threshold | N/A -- no engine |
| Large data handling | N/A -- no engine |

---

## 8. Testing

What's verified?

### 8.1 Current Coverage

| Test Type | Count | Location |
| ----------- | ------- | ---------- |
| Converter unit tests | 34 | `tests/converters/talend_to_v1/components/test_memorize_rows.py` |
| Engine unit tests | 0 | None -- no engine implementation |
| Integration tests | 0 | None -- no engine implementation |

### 8.2 Test Gaps

| ID | Priority | Gap |
| ---- | ---------- | ----- |
| TEST-MEM-001 | **P0** | No engine unit tests -- entire engine is unimplemented |

### 8.3 Recommended Test Cases

When an engine implementation is created, these tests should be added:

1. **Basic memorization**: Verify that the last N rows are stored and accessible via globalMap
2. **ROW_COUNT edge cases**: Test with ROW_COUNT=0, ROW_COUNT=1, large ROW_COUNT
3. **SPECIFY_COLS filtering**: Verify selective column memorization
4. **Expression ROW_COUNT**: Test dynamic row count from context variables
5. **Empty input**: Verify behavior with 0-row DataFrame
6. **Schema fidelity**: Verify output schema matches input exactly
7. **GlobalMap access patterns**: Verify `{id}_{column}_{offset}` variables set correctly

---

## 9. Issues Summary

All issues grouped by priority for sprint planning.

### By Priority

| Priority | Count | IDs |
| ---------- | ------- | ----- |
| P0 | 3 | **ENG-MEM-001**, **BUG-MEM-001**, **TEST-MEM-001** |
| P1 | 0 | -- |
| P2 | 0 | -- |
| P3 | 0 | -- |
| **Total** | **3** | |

### By Category

| Category | Count | IDs |
| ---------- | ------- | ----- |
| Converter (CONV) | 0 | -- |
| Engine (ENG) | 1 | ENG-MEM-001 |
| Bug (BUG) | 1 | BUG-MEM-001 |
| Naming (NAME) | 0 | -- |
| Standards (STD) | 0 | -- |
| Performance (PERF) | 0 | -- |
| Testing (TEST) | 1 | TEST-MEM-001 |

### Cross-Cutting Issues

No cross-cutting issues apply -- there is no engine implementation to be affected by base class bugs.

---

## 10. Recommendations

What should be fixed, in what order?

### Immediate (Before Production)

1. **ENG-MEM-001 (P0)**: Implement concrete `MemorizeRows` engine class with row memorization, SPECIFY_COLS support, and globalMap variable output
2. **BUG-MEM-001 (P0)**: Create engine code -- currently entirely missing
3. **TEST-MEM-001 (P0)**: Add engine unit tests once engine is implemented

### Short-term (Hardening)

No P1/P2 issues -- converter is complete and tested.

### Long-term (Optimization)

No P3 issues identified.

---

## Appendix A: Source References

| Source | URL/Path | Used For |
| -------- | ---------- | ---------- |
| Talaxie GitHub _java.xml | `<https://github.com/Talaxie/tdi-studio-se/`> (tMemorizeRows_java.xml) | Parameter definitions, types, defaults |
| Converter source | `src/converters/talend_to_v1/components/transform/memorize_rows.py` | Converter audit |
| Test source | `tests/converters/talend_to_v1/components/test_memorize_rows.py` | Test coverage audit |
| Base class | `src/converters/talend_to_v1/components/base.py` | Helper methods, schema parsing |
| Gold standard templates | `docs/v1/standards/CONVERTER_PATTERN.md`, `docs/v1/standards/TEST_PATTERN.md`, `docs/v1/standards/AUDIT_REPORT_TEMPLATE.md` | Standards compliance |

## Appendix B: Cross-Cutting Issues

No cross-cutting issues apply -- there is no engine implementation to be affected by base class bugs (`_update_global_map()`, `GlobalMap.get()`, `validate_schema`, etc.).

When an engine implementation is created, the standard cross-cutting bugs from `base_component.py` will apply:

| Canonical ID | Location | Impact on This Component |
| ------------- | ---------- | -------------------------- |
| XCUT-001 | `base_component.py:304` | Will affect `_update_global_map()` for row memory variables |
| XCUT-002 | `global_map.py:28` | Will affect globalMap variable access for memorized rows |

---

*Report generated: 2026-04-04*
*Last updated: 2026-04-04 after v1.1 Phase 13 standardization (NEW audit report created)*
