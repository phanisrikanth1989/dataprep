# Audit Report: tSplitRow / (No Engine Implementation)

> **Audited**: 2026-04-04
> **Auditor**: Claude Opus 4.6 (automated)
> **Engine Version**: v1
> **Converter**: `talend_to_v1`
> **Status**: PRODUCTION READINESS REVIEW
> **V1 only** -- this report covers the v1 engine exclusively

---

## 1. Component Identity

What is this component and where does everything live?

| Field | Value |
| ------- | ------- |
| **Talend Name** | `tSplitRow` |
| **V1 Engine Class** | None -- no engine implementation exists |
| **Engine File** | None |
| **Converter Parser** | `src/converters/talend_to_v1/components/transform/split_row.py` (121 lines) |
| **Converter Dispatch** | `@REGISTRY.register("tSplitRow")` decorator-based dispatch |
| **Registry Aliases** | `tSplitRow` (single alias) |
| **Category** | Transform / Split |

### Key Files

| File | Purpose |
| ------ | --------- |
| `src/converters/talend_to_v1/components/transform/split_row.py` | Converter class `SplitRowConverter` (121 lines) |
| `tests/converters/talend_to_v1/components/test_split_row.py` | Converter tests (24 tests across 10 classes) |
| `src/converters/talend_to_v1/components/base.py` | `ComponentConverter` base class with `_get_str()`, `_get_bool()`, `_parse_schema()`, `_build_component_dict()` |
| `src/converters/talend_to_v1/components/registry.py` | `ConverterRegistry` with decorator-based registration |

---

## 2. Scorecard

How production-ready is this component at a glance?

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
| ----------- | ------- | ---- | ---- | ---- | ---- | --------- |
| Converter Coverage | **G** | 0 | 0 | 0 | 0 | 1 of 1 unique config key extracted (100%); COL_MAPPING stride-2 TABLE (source_column, target_column); 1 phantom param (CONNECTION_FORMAT) removed; single consolidated needs_review; module docstring follows CONVERTER_PATTERN.md |
| Engine Feature Parity | **R** | 1 | 0 | 0 | 0 | No engine implementation exists at all; component cannot execute |
| Code Quality | **R** | 1 | 0 | 0 | 0 | Converter code quality is good (follows CONVERTER_PATTERN.md), but no engine code exists -- component is incomplete. Converter alone cannot deliver functionality. |
| Performance & Memory | **N/A** | 0 | 0 | 0 | 0 | No engine implementation to assess |
| Testing | **R** | 1 | 0 | 0 | 0 | 24 converter tests pass (10 classes per TEST_PATTERN.md), but 0 engine tests exist because engine is unimplemented. Component is untestable end-to-end. |

**Overall: RED -- No engine implementation. Converter correctly extracts all params for future engine support, but component cannot execute in production. Engine must be implemented before this component is usable.**

**Top Actions**:

1. Implement concrete SplitRow engine class (P0 -- blocks production use)
2. All converter and test issues resolved in v1.1 rewrite

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
| 1 | Column mapping split | **No** | N/A | N/A | No engine class exists |
| 2 | Multi-output routing | **No** | N/A | N/A | No engine class exists |

### 5.2 Behavioral Differences from Talend

| ID | Priority | Description |
| ---- | ---------- | ------------- |
| ENG-SPR-001 | **P0** | **OPEN** -- No engine implementation. tSplitRow converter output cannot be executed. Jobs containing tSplitRow will fail at runtime. |

### 5.3 GlobalMap Variable Coverage

| Variable | Talend Sets? | V1 Sets? | How V1 Sets It | Notes |
| ---------- | ------------- | ---------- | ----------------- | ------- |
| `{id}_NB_LINE` | Yes | No | N/A | No engine implementation |

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
| Level usage | N/A -- no engine code; converter has no log calls (appropriate for simple converter) |
| Sensitive data | No risk -- column names only |

### 6.7 Error Handling Quality

| Aspect | Assessment |
| -------- | ------------ |
| Custom exceptions | N/A -- no engine code |
| Exception chaining | N/A -- no engine code |
| die_on_error handling | N/A -- component has no DIE_ON_ERROR param |

### 6.8 Type Hints

| Aspect | Assessment |
| -------- | ------------ |
| Method signatures | Fully typed (`convert()`, `_parse_col_mapping()`) |
| Parameter types | All parameters typed with `Dict[str, Any]`, `List[Dict[str, str]]`, etc. |

---

## 7. Performance & Memory

Will it scale?

No engine implementation exists. Performance cannot be assessed.

### 7.1 Memory Management Assessment

| Aspect | Assessment |
| -------- | ------------ |
| Streaming mode | N/A -- no engine implementation |
| Memory threshold | N/A |
| Large data handling | N/A |

---

## 8. Testing

What's verified?

### 8.1 Current Coverage

| Test Type | Count | Location |
| ----------- | ------- | ---------- |
| Converter unit tests | 24 | `tests/converters/talend_to_v1/components/test_split_row.py` |
| Engine unit tests | 0 | None -- no engine implementation |
| Integration tests | 0 | None -- no engine implementation |

### 8.2 Test Gaps

| ID | Priority | Gap |
| ---- | ---------- | ----- |
| TEST-SPR-001 | **P0** | **OPEN** -- No engine tests (engine unimplemented). Component is untestable end-to-end. |

### 8.3 Recommended Test Cases

When engine is implemented:

- Happy path: single input row split to multiple outputs by column mapping
- Multiple mappings: verify each output receives correct columns
- Empty input: 0-row DataFrame with schema preserved
- Empty mapping: no column mappings defined -- behavior TBD
- Schema validation: output schemas match mapping definitions
- GlobalMap: `{id}_NB_LINE` set correctly after processing

---

## 9. Issues Summary

All issues grouped by priority for sprint planning.

### By Priority

| Priority | Count | IDs |
| ---------- | ------- | ----- |
| P0 | 3 | **ENG-SPR-001**, **TEST-SPR-001**, **CQ-SPR-001** |
| P1 | 0 | -- |
| P2 | 0 | -- |
| P3 | 0 | -- |
| **Total** | **3** | |

### By Category

| Category | Count | IDs |
| ---------- | ------- | ----- |
| Converter (CONV) | 0 | -- |
| Engine (ENG) | 1 | ENG-SPR-001 |
| Code Quality (CQ) | 1 | CQ-SPR-001 (no engine code) |
| Naming (NAME) | 0 | -- |
| Standards (STD) | 0 | -- |
| Performance (PERF) | 0 | -- |
| Testing (TEST) | 1 | TEST-SPR-001 |

### Cross-Cutting Issues

No cross-cutting issues apply -- no engine implementation exists, so base class bugs (globalMap crash, validate_schema, etc.) are not relevant.

---

## 10. Recommendations

What should be fixed, in what order?

### Immediate (Before Production)

1. **ENG-SPR-001 (P0)**: Implement `SplitRow` engine class that reads `col_mapping` from config and routes columns to output flows.
2. **TEST-SPR-001 (P0)**: Add engine unit tests once engine is implemented.
3. **CQ-SPR-001 (P0)**: Engine code quality will be assessed after implementation.

### Short-term (Hardening)

No additional items -- all issues are P0 (engine implementation).

### Long-term (Optimization)

No items -- component is simple enough that optimization is unlikely to be needed.

---

## Appendix A: Source References

| Source | URL/Path | Used For |
| -------- | ---------- | ---------- |
| Talaxie GitHub _java.xml | `<https://github.com/Talaxie/tdi-studio-se/blob/master/main/plugins/org.talend.designer.components.localprovider/components/tSplitRow/tSplitRow_java.xml`> | Parameter definitions, TABLE structure, defaults |
| Converter source | `src/converters/talend_to_v1/components/transform/split_row.py` | Converter audit |
| Test source | `tests/converters/talend_to_v1/components/test_split_row.py` | Test coverage analysis |
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
*Last updated: 2026-04-04 after Phase 11 standardization (v1.1)*
