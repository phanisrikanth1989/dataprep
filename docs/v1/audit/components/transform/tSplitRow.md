# Audit Report: tSplitRow / SplitRow

> **Audited**: 2026-04-04
> **Reconciled**: 2026-05-11
> **Auditor**: Claude Opus 4.6 (automated)
> **Engine Version**: v1
> **Converter**: `talend_to_v1`
> **Status**: PRODUCTION READY
> **V1 only** -- this report covers the v1 engine exclusively

---

## 1. Component Identity

What is this component and where does everything live?

| Field | Value |
| ------- | ------- |
| **Talend Name** | `tSplitRow` |
| **V1 Engine Class** | `SplitRow` (`src/v1/engine/components/transform/split_row.py`) |
| **Engine File** | `src/v1/engine/components/transform/split_row.py` |
| **Converter Parser** | `src/converters/talend_to_v1/components/transform/split_row.py` (121 lines) |
| **Converter Dispatch** | `@REGISTRY.register("tSplitRow")` decorator-based dispatch |
| **Registry Aliases** | `SplitRow`, `tSplitRow` |
| **Category** | Transform / Split |

### Key Files

| File | Purpose |
| ------ | --------- |
| `src/converters/talend_to_v1/components/transform/split_row.py` | Converter class `SplitRowConverter` (121 lines) |
| `tests/converters/talend_to_v1/components/test_split_row.py` | Converter tests (24 tests across 10 classes) |
| `src/v1/engine/components/transform/split_row.py` | Engine class `SplitRow` |
| `tests/v1/engine/components/transform/test_split_row.py` | Engine tests (28 tests, 6 classes) |
| `src/converters/talend_to_v1/components/base.py` | `ComponentConverter` base class with `_get_str()`, `_get_bool()`, `_parse_schema()`, `_build_component_dict()` |
| `src/converters/talend_to_v1/components/registry.py` | `ConverterRegistry` with decorator-based registration |

---

## 2. Scorecard

How production-ready is this component at a glance?

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
| ----------- | ------- | ---- | ---- | ---- | ---- | --------- |
| Converter Coverage | **G** | 0 | 0 | 0 | 0 | 1 of 1 unique config key extracted (100%); COL_MAPPING stride-2 TABLE (source_column, target_column); 1 phantom param (CONNECTION_FORMAT) removed; single consolidated needs_review; module docstring follows CONVERTER_PATTERN.md |
| Engine Feature Parity | **G** | 0 | 0 | 0 | 0 | `SplitRow` engine implemented; column selection, renaming, empty-mapping guard, and GlobalMap stats all functional |
| Code Quality | **G** | 0 | 0 | 0 | 0 | Follows MANUAL_COMPONENT_AUTHORING.md; Rules 11 and 12 compliant; no `eval/exec`; warns on missing source columns |
| Performance & Memory | **N/A** | 0 | 0 | 0 | 0 | Column projection -- no memory concerns |
| Testing | **G** | 0 | 0 | 0 | 0 | 28 engine tests (6 classes) + 24 converter tests all pass |

**Overall: GREEN -- Engine implemented, all tests pass. Converter and engine are both production-quality.**

**Top Actions**: None -- all issues resolved.

---

## 3. Talend Feature Baseline

What does Talend actually do? This section is the SOURCE OF TRUTH -- researched from _java.xml and official docs.

### What tSplitRow Does

tSplitRow splits incoming rows from a main input flow into multiple output flows based on column mapping definitions. Each column mapping specifies a source column from the input schema and a target column in an output schema, allowing data from a single input row to be distributed across multiple output connections.

This component is used in ETL jobs where a single data source needs to feed different downstream processing paths with different subsets of columns. It acts as a routing mechanism that directs specific columns to specific output flows.

**Source**: Talaxie GitHub `tSplitRow/tSplitRow_java.xml`
**Component family**: Transform
**Available in**: Talend Open Studio, Talend Data Integration
**Required JARs**: None (built-in)

### 3.1 Basic Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
| --- | ----------- | ----------------- | ------ | --------- | ------------- |
| 1 | Column Mapping | `COL_MAPPING` | TABLE (stride-2) | Empty | Maps source columns to target columns. Each entry has SOURCE_COLUMN and TARGET_COLUMN. Uses COLUMNS_BASED_ON_SCHEMA="true" in _java.xml but .item exports contain explicit elementRef entries. |
| -- | *Framework* | | | | |
| 2 | Stat Catcher | `TSTATCATCHER_STATS` | BOOLEAN | `false` | Enable statistics collection via tStatCatcher |
| 3 | Label | `LABEL` | TEXT | `""` | User-defined label for display in Talend Studio |

**Note**: The _java.xml defines COL_MAPPING with `COLUMNS_BASED_ON_SCHEMA="true"`, meaning Talend Studio auto-populates columns from the schema. However, when exported to .item files, the TABLE contains explicit SOURCE_COLUMN/TARGET_COLUMN elementRef entries. The converter parses the .item export format per project convention (.item is source of truth).

### 3.2 Advanced Settings

No advanced settings defined in _java.xml for tSplitRow.

### 3.3 Connection Types

| Connector | Direction | Type | Description |
| ----------- | ----------- | ------ | ------------- |
| `FLOW` (Main) | Input | Row > Main | Main input data flow |
| `FLOW` (Output) | Output | Row > Main | One or more output flows, each receiving mapped columns |
| `SUBJOB_OK` | Output (Trigger) | Trigger | Fires after successful completion |
| `SUBJOB_ERROR` | Output (Trigger) | Trigger | Fires on error |

### 3.4 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
| ------------------ | ------ | ---------- | ------------- |
| `{id}_NB_LINE` | Integer | After execution | Number of input rows processed |

### 3.5 Behavioral Notes

1. **COLUMNS_BASED_ON_SCHEMA**: The _java.xml sets this flag on COL_MAPPING, meaning the TABLE columns are derived from the connected schema in Talend Studio. The .item export materializes these as explicit SOURCE_COLUMN/TARGET_COLUMN pairs.
2. **CONNECTION_FORMAT is phantom**: This parameter does NOT exist in _java.xml. It was present in the old converter but has been removed as a phantom param.
3. **Simple component**: tSplitRow has no advanced settings, no conditional parameters, and only one TABLE parameter.

---

## 4. Converter Audit

How faithfully does the converter translate Talend XML to v1 JSON?

### 4.1 Parameter Extraction

The converter uses `SplitRowConverter` with `@REGISTRY.register("tSplitRow")`. It extracts the COL_MAPPING TABLE using a module-level `_parse_col_mapping()` stride-2 parser and framework params via base class helpers. Uses `_build_component_dict()` with `type_name="tSplitRow"` (no engine implementation exists).

| # | Talend XML Parameter | Extracted? | V1 Config Key | Notes |
| ---- | ---------------------- | ------------ | --------------- | ------- |
| 1 | `COL_MAPPING` | Yes | `col_mapping` | Stride-2 TABLE: SOURCE_COLUMN -> source_column, TARGET_COLUMN -> target_column. Returns list of dicts. |
| 2 | `TSTATCATCHER_STATS` | Yes | `tstatcatcher_stats` | Framework param, default False |
| 3 | `LABEL` | Yes | `label` | Framework param, default "" |
| -- | `CONNECTION_FORMAT` | **Removed** | -- | **Phantom param** -- not in _java.xml. Was in old converter, now removed. |

**Summary**: 1 of 1 unique parameters extracted (100%). 2 framework params always extracted. 1 phantom param removed.

### 4.2 Schema Extraction

| Schema Attribute | Extracted? | Notes |
| ------------------ | ----------- | ------- |
| `name` | Yes | Via `_parse_schema()` from base class |
| `type` | Yes | Via `convert_type()` -- Talend types to Python types |
| `nullable` | Yes | Boolean flag |
| `key` | Yes | Boolean flag |
| `length` | Yes | Included when >= 0 |
| `precision` | Yes | Included when >= 0 |
| `pattern` | Yes | Java-to-Python date pattern conversion |
| `default` | No | Not extracted by base class `_parse_schema()` |

Schema pattern: Transform passthrough -- `{"input": schema_cols, "output": schema_cols}`.

### 4.3 Expression Handling

The converter passes through raw parameter values. Context variable references (`context.var`) and Java expressions are preserved as-is in the config output for runtime resolution by the engine (when implemented).

### 4.4 Converter Issues

None -- converter follows gold standard CONVERTER_PATTERN.md with correct TABLE parsing, phantom removal, and consolidated needs_review.

### 4.5 Needs Review Entries

| # | Config Key | Reason | Severity |
| --- | ----------- | -------- | ---------- |
| 1 | (entire component) | No v1 engine implementation for tSplitRow -- entire component is unimplemented; converter output cannot be executed at runtime | engine_gap |

---

## 5. Engine Feature Parity

How faithfully does the v1 engine implement Talend behavior?

### 5.1 Feature Implementation Status

| # | Talend Feature | Implemented? | Fidelity | Engine Location | Notes |
| ---- | ---------------- | ------------- | ---------- | ----------------- | ------- |
| 1 | Column mapping split | **Yes** | Full | `SplitRow._process()` | Selects and renames columns per `col_mapping` |
| 2 | Multi-output routing | **Yes** | Full | `SplitRow._process()` | Outputs mapped columns to `main`; engine routes connections |

### 5.2 Behavioral Differences from Talend

No known behavioral differences.

| ID | Priority | Description |
| ---- | ---------- | ------------- |
| -- | -- | No differences identified |

### 5.3 GlobalMap Variable Coverage

| Variable | Talend Sets? | V1 Sets? | How V1 Sets It | Notes |
| ---------- | ------------- | ---------- | ----------------- | ------- |
| `{id}_NB_LINE` | Yes | Yes | `_update_stats(total, ok, 0)` in `_process()` | Verified by `TestGlobalMapVariables` |

---

## 6. Code Quality

How well-written is the engine code?

### 6.1 Bugs

No engine code exists. Converter code has no bugs identified.

### 6.2 Naming Consistency

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| -- | -- | No issues. Converter uses correct snake_case config keys per CONVERTER_PATTERN.md. |

### 6.3 Standards Compliance

Converter follows CONVERTER_PATTERN.md:

- Module docstring with config mapping table
- Module-level TABLE constants and parser function
- `_build_component_dict()` wrapper
- Framework params extracted last
- Single consolidated needs_review per D-27

### 6.4 Debug Artifacts

None found.

### 6.5 Security

No security concerns -- component performs column-level data routing with no external I/O, no eval/exec, no path operations.

### 6.6 Logging Quality

| Aspect | Assessment |
| -------- | ------------ |
| Logger setup | Module-level `logger = logging.getLogger(__name__)` -- correct |
| Level usage | `DEBUG` for empty-mapping guard; `WARNING` for missing source columns |
| Sensitive data | No risk -- column names only |

### 6.7 Error Handling Quality

| Aspect | Assessment |
| -------- | ------------ |
| Custom exceptions | `ConfigurationError` for missing/invalid `col_mapping` structure |
| Exception chaining | N/A -- validation is structural (Rule 12) |
| die_on_error handling | Handled via base class `execute()` |

### 6.8 Type Hints

| Aspect | Assessment |
| -------- | ------------ |
| Method signatures | Fully typed (`convert()`, `_parse_col_mapping()`) |
| Parameter types | All parameters typed with `Dict[str, Any]`, `List[Dict[str, str]]`, etc. |

---

## 7. Performance & Memory

Will it scale?

Simple column projection -- O(n) row copy. No memory concerns.

### 7.1 Memory Management Assessment

| Aspect | Assessment |
| -------- | ------------ |
| Streaming mode | Handled by base class |
| Memory threshold | N/A -- output is a column subset of input |
| Large data handling | Tested with 1000-row DataFrame (TestEdgeCases.test_large_input) |

---

## 8. Testing

What's verified?

### 8.1 Current Coverage

| Test Type | Count | Location |
| ----------- | ------- | ---------- |
| Converter unit tests | 24 | `tests/converters/talend_to_v1/components/test_split_row.py` |
| Engine unit tests | 28 | `tests/v1/engine/components/transform/test_split_row.py` |
| Integration tests | 0 | N/A |

### 8.2 Test Gaps

| ID | Priority | Gap |
| ---- | ---------- | ----- |
| -- | -- | No gaps -- all recommended test cases implemented |

### 8.3 Test Classes (Engine)

| Class | Tests | What's Verified |
| ------- | ------- | ----------------- |
| TestRegistration | 3 | V1 alias, Talend alias, BaseComponent inheritance |
| TestValidation | 5 | Missing col_mapping, not-a-list, entry-not-dict, missing source_column, missing target_column |
| TestMainFlow | 7 | Rename, drop unmapped, row count, values, identity mapping, column order, single column |
| TestEdgeCases | 7 | None input, empty DF, empty mapping, missing source, all missing, reject is None, large input |
| TestGlobalMapVariables | 4 | NB_LINE, NB_LINE_OK, NB_LINE_REJECT==0, no-globalmap |
| TestIterateReexecution | 2 | Reset consistency, config immutability |

---

## 9. Issues Summary

All issues grouped by priority for sprint planning.

### By Priority

| Priority | Count | IDs |
| ---------- | ------- | ----- |
| P0 | 0 | -- |
| P1 | 0 | -- |
| P2 | 0 | -- |
| P3 | 0 | -- |
| **Total** | **0** | |

### By Category

| Category | Count | IDs |
| ---------- | ------- | ----- |
| Converter (CONV) | 0 | -- |
| Engine (ENG) | 0 | -- |
| Code Quality (CQ) | 0 | -- |
| Naming (NAME) | 0 | -- |
| Standards (STD) | 0 | -- |
| Performance (PERF) | 0 | -- |
| Testing (TEST) | 0 | -- |

### Cross-Cutting Issues

None. Engine is implemented and verified against cross-cutting base class requirements (Rules 11 and 12 compliant).

---

## 10. Recommendations

What should be fixed, in what order?

### Immediate (Before Production)

No immediate actions -- component is production-ready.

### Short-term (Hardening)

No additional items.

### Long-term (Optimization)

No items -- component is simple enough that optimization is unlikely to be needed.

---

## Appendix A: Source References

| Source | URL/Path | Used For |
| -------- | ---------- | ---------- |
| Talaxie GitHub _java.xml | `<https://github.com/Talaxie/tdi-studio-se/blob/master/main/plugins/org.talend.designer.components.localprovider/components/tSplitRow/tSplitRow_java.xml`> | Parameter definitions, TABLE structure, defaults |
| Converter source | `src/converters/talend_to_v1/components/transform/split_row.py` | Converter audit |
| Engine source | `src/v1/engine/components/transform/split_row.py` | Engine audit |
| Test source (converter) | `tests/converters/talend_to_v1/components/test_split_row.py` | Converter test coverage |
| Test source (engine) | `tests/v1/engine/components/transform/test_split_row.py` | Engine test coverage |
| Base class | `src/converters/talend_to_v1/components/base.py` | Helper method reference |

## Appendix B: Converter Config Key Mapping

| Talend XML Parameter | Config Key | Type | Default | Extraction Method |
| ---------------------- | ------------ | ------ | --------- | ------------------- |
| `COL_MAPPING` | `col_mapping` | list of dicts | `[]` | `_parse_col_mapping()` stride-2 parser |
| `COL_MAPPING.SOURCE_COLUMN` | `source_column` | str | -- | elementRef in TABLE entry |
| `COL_MAPPING.TARGET_COLUMN` | `target_column` | str | -- | elementRef in TABLE entry |
| `TSTATCATCHER_STATS` | `tstatcatcher_stats` | bool | `False` | `_get_bool()` |
| `LABEL` | `label` | str | `""` | `_get_str()` |
| ~~`CONNECTION_FORMAT`~~ | ~~removed~~ | -- | -- | **Phantom param** -- not in _java.xml |

---

*Report generated: 2026-04-04*
*Last updated: 2026-05-11 -- reconciled (Phase 15.1-08)*
