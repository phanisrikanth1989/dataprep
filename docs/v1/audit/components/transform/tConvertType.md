# Audit Report: tConvertType

> **Audited**: 2026-04-04
> **Updated**: 2026-05-04 (implementation complete)
> **Reconciled**: 2026-05-11
> **Auditor**: Claude Sonnet 4.6 (automated)
> **Engine Version**: v1
> **Converter**: `talend_to_v1`
> **Status**: GREEN
> **V1 only** -- this report contains zero references to v2/PyETL

---

## 1. Component Identity

What is this component and where does everything live?

| Field | Value |
| ------- | ------- |
| **Talend Name** | `tConvertType` |
| **V1 Engine Class** | `ConvertType` |
| **Engine File** | `src/v1/engine/components/transform/convert_type.py` |
| **Converter Parser** | `src/converters/talend_to_v1/components/transform/convert_type.py` (118 lines) |
| **Converter Dispatch** | `@REGISTRY.register("tConvertType")` decorator-based dispatch |
| **Registry Aliases** | `ConvertType`, `tConvertType` (REGISTRY decorator) |
| **Category** | Transform / Type Conversion |

### Key Files

| File | Purpose |
| ------ | --------- |
| `src/v1/engine/components/transform/convert_type.py` | Engine implementation |
| `src/converters/talend_to_v1/components/transform/convert_type.py` | Converter class (118 lines) |
| `tests/converters/talend_to_v1/components/test_convert_type.py` | Converter tests (24 tests) |
| `tests/v1/engine/components/transform/test_convert_type.py` | Engine tests (24 tests) |

---

## 2. Scorecard

How production-ready is this component at a glance?

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
| ----------- | ------- | ---- | ---- | ---- | ---- | --------- |
| Converter Coverage | **G** | 0 | 0 | 0 | 0 | 4/4 unique params + 2 framework extracted; gold standard pattern |
| Engine Feature Parity | **G** | 0 | 0 | 0 | 0 | autocast, manualtable, emptytonull, dieonerror all implemented; REJECT flow routing; Talend type map |
| Code Quality | **G** | 0 | 0 | 0 | 0 | Clean converter; gold standard compliance; engine follows all 12 authoring rules |
| Performance & Memory | **G** | 0 | 0 | 0 | 1 | Per-row coercion loop; could be vectorized for large DataFrames |
| Testing | **G** | 0 | 0 | 0 | 0 | 24 engine tests: registration, validation, emptytonull, manualtable, autocast, reject routing, die-on-error, noop |

**Overall: GREEN** -- Engine implemented with full Talend feature parity: autocast, manualtable column coercion, emptytonull, dieonerror, REJECT flow routing.

**Implementation Notes (2026-05-04):**

- Created `src/v1/engine/components/transform/convert_type.py` (`ConvertType` class)
- `@REGISTRY.register("ConvertType", "tConvertType")` added
- Reads: `autocast` (bool), `emptytonull` (bool), `dieonerror` (bool), `manualtable` (list)
- `_TALEND_TO_PANDAS` dict maps Talend type names to pandas dtype strings
- `_coerce_series()` helper handles datetime, bool, int, float, string coercion
- `emptytonull=True`: replaces `""` with `pd.NA` on object columns before manual coercion
- `manualtable`: per-row coercion; failures tracked in `ok_mask`, routed to REJECT
- `autocast=True`: `pd.to_numeric(errors='coerce')` on non-manual columns (best-effort)
- `dieonerror=True`: raises `DataValidationError` instead of building REJECT flow
- Uses `getattr(self, "output_schema", None)` for runtime schema access (engine sets this)
- Returns `{"main": ok_df, "reject": reject_df}` with `error_code`/`error_message` columns
- Added to `src/v1/engine/components/transform/__init__.py`

---

## 3. Talend Feature Baseline

What does Talend actually do? This section is the SOURCE OF TRUTH -- researched from .item files, _java.xml, and official docs.

### What tConvertType Does

tConvertType converts column data types within a data flow. It supports two modes of operation: automatic type casting (AUTOCAST) where Talend infers the best type conversion, and manual type mapping (MANUALTABLE) where users explicitly define which columns should be converted to which types.

The component can also convert empty strings to null values (EMPTYTONULL). When used with DIEONERROR enabled, the component will terminate the job if a type conversion fails rather than continuing silently.

**Source**: Talaxie GitHub _java.xml
**Component family**: Cast / Type
**Available in**: All Talend products
**Required JARs**: None (built-in)

### 3.1 Basic Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
| --- | ----------- | ----------------- | ------ | --------- | ------------- |
| 1 | Schema | `IN_SCHEMA` | SCHEMA_TYPE | -- | Input schema definition |
| 2 | Auto Cast | `AUTOCAST` | CHECK | `false` | Enable automatic type casting |
| 3 | Manual Table | `MANUALTABLE` | TABLE | `[]` | Manual column-to-type mapping pairs |
| 3a | -- Input Column | `INPUT_COLUMN` | elementRef (str) | -- | Column name to convert |
| 3b | -- Output Column | `OUTPUT_COLUMN` | elementRef (str) | -- | Target type name |
| 4 | Empty to Null | `EMPTYTONULL` | CHECK | `false` | Convert empty strings to null |
| 5 | Die on Error | `DIEONERROR` | CHECK | `false` | Stop job on conversion error |
| 6 | Reject Schema | `SCHEMA_REJECT` | SCHEMA_TYPE | -- | Reject output with errorCode/errorMessage columns |

### 3.2 Advanced Settings

No advanced settings defined in _java.xml.

### 3.3 Connection Types

| Connector | Direction | Type | Description |
| ----------- | ----------- | ------ | ------------- |
| `FLOW` (Main) | Input/Output | Row > Main | Data flow with converted types |
| `REJECT` | Output | Row > Reject | Rows that failed type conversion |
| `SUBJOB_OK` | Output (Trigger) | Trigger | Fires on successful completion |
| `SUBJOB_ERROR` | Output (Trigger) | Trigger | Fires on failure |

### 3.4 GlobalMap Variables

No documented GlobalMap variables for tConvertType.

### 3.5 Behavioral Notes

1. **MANUALTABLE elementRef names**: The _java.xml defines `INPUT_COLUMN` and `OUTPUT_COLUMN` as the elementRef names for MANUALTABLE entries. No .item file evidence was found to contradict this, so _java.xml names are used in the converter. Historical converter code used `SCHEMA_COLUMN`/`CONVERT_TO` which may reflect an older .item format or a misidentification.
2. **DIEONERROR spelling**: The _java.xml parameter name is `DIEONERROR` (no underscore), consistent with other Talend components like tContextLoad.
3. **AUTOCAST vs MANUALTABLE interaction**: Both can be active simultaneously. AUTOCAST handles unmatched columns while MANUALTABLE provides explicit overrides.
4. **EMPTYTONULL**: Converts empty string values to null before type conversion occurs, which can affect conversion outcomes.

---

## 4. Converter Audit

How faithfully does the converter translate Talend XML to v1 JSON?

### 4.1 Parameter Extraction

The converter uses the gold standard pattern: `_build_component_dict()`, `_get_bool()`, `_get_str()` base class helpers, stride-2 TABLE parser for MANUALTABLE, and framework params last.

| # | Talend XML Parameter | Extracted? | V1 Config Key | Notes |
| ---- | ---------------------- | ------------ | --------------- | ------- |
| 1 | `AUTOCAST` | Yes | `autocast` | bool, default False |
| 2 | `MANUALTABLE` | Yes | `manualtable` | list of dicts, stride-2 TABLE |
| 2a | `INPUT_COLUMN` | Yes | `input_column` | str, elementRef in MANUALTABLE |
| 2b | `OUTPUT_COLUMN` | Yes | `output_column` | str, elementRef in MANUALTABLE |
| 3 | `EMPTYTONULL` | Yes | `emptytonull` | bool, default False |
| 4 | `DIEONERROR` | Yes | `dieonerror` | bool, default False |
| 5 | `TSTATCATCHER_STATS` | Yes | `tstatcatcher_stats` | bool, framework param |
| 6 | `LABEL` | Yes | `label` | str, framework param |

**Summary**: 4 of 4 unique parameters extracted (100%). Schema types (IN_SCHEMA, SCHEMA_REJECT) handled by framework.

### 4.2 Schema Extraction

| Schema Attribute | Extracted? | Notes |
| ------------------ | ----------- | ------- |
| `name` | Yes | Via `_parse_schema()` |
| `type` | Yes | Converted from Talend types via `convert_type()` |
| `nullable` | Yes | Direct extraction |
| `key` | Yes | Direct extraction |
| `length` | Yes | Included when >= 0 |
| `precision` | Yes | Included when >= 0 |
| `pattern` | Yes | Java-to-Python date pattern conversion |
| `default` | No | Not supported in base `_parse_schema()` |

Passthrough schema: input == output (transform component).

### 4.3 Expression Handling

No special expression handling needed. All parameters are simple types (CHECK booleans) or TABLE entries (string values).

### 4.4 Converter Issues

No issues found. Converter follows gold standard pattern.

### 4.5 Needs Review Entries

| # | Config Key | Reason | Severity |
| --- | ----------- | -------- | ---------- |
| 1 | (all keys) | No v1 engine implementation for tConvertType -- all config keys unread | engine_gap |

Single consolidated entry per D-27 (no engine exists).

---

## 5. Engine Feature Parity

How faithfully does the v1 engine implement Talend behavior?

### 5.1 Feature Implementation Status

Engine implemented 2026-05-04 (Phase 13-04 + post-BUG-CT-001 fix). All Talend features implemented.

| # | Talend Feature | Implemented? | Fidelity | Engine Location | Notes |
| ---- | ---------------- | ------------- | ---------- | ----------------- | ------- |
| 1 | Auto casting | **Yes** | High | `_process()` | `pd.to_numeric(errors='coerce')` on non-manual columns |
| 2 | Manual type mapping | **Yes** | High | `_process()` | `_coerce_series()` per MANUALTABLE entry; failures tracked in ok_mask |
| 3 | Empty to null conversion | **Yes** | High | `_process()` | `emptytonull=True` replaces `""` with `pd.NA` before coercion |
| 4 | Die on error | **Yes** | High | `_process()` | `dieonerror=True` raises DataValidationError |
| 5 | Reject flow | **Yes** | High | `_process()` | Returns `{"main": ok_df, "reject": reject_df}` with errorCode/errorMessage |

### 5.2 Behavioral Differences from Talend

| ID | Priority | Description |
| ---- | ---------- | ------------- |
| ~~BUG-CT-001~~ | ~~P1~~ | ~~MANUALTABLE numeric fallback -- in-place cast without target type fell back incorrectly~~ [RESOLVED in Phase 13-04, commit c246625 (BUG-CT-001)] |

### 5.3 GlobalMap Variable Coverage

| Variable | Talend Sets? | V1 Sets? | How V1 Sets It | Notes |
| ---------- | ------------- | ---------- | ----------------- | ------- |
| `{id}_NB_LINE` | Yes | Yes | Base class `_update_global_map()` | Total rows processed |
| `{id}_NB_LINE_OK` | Yes | Yes | Base class `_update_global_map()` | Rows successfully converted |
| `{id}_NB_LINE_REJECT` | Yes | Yes | Base class `_update_global_map()` | Rows routed to REJECT |

---

## 6. Code Quality

How well-written is the engine code?

### 6.1 Bugs

| ID | Priority | Location | Description |
| ---- | ---------- | ---------- | ------------- |
| ~~BUG-CT-001~~ | ~~P1~~ | `convert_type.py` | ~~MANUALTABLE numeric fallback incorrect for in-place cast without explicit target type~~ [RESOLVED in Phase 13-04, commit c246625 (BUG-CT-001)] |

### 6.2 Naming Consistency

Converter follows gold standard naming conventions. Config keys are snake_case.

### 6.3 Standards Compliance

Converter fully compliant with `docs/v1/patterns/CONVERTER_PATTERN.md`. Engine follows all 12 BaseComponent authoring rules.

### 6.4 Debug Artifacts

None found.

### 6.5 Security

No concerns identified.

### 6.6 Logging Quality

| Aspect | Assessment |
| -------- | ------------ |
| Logger setup | Module-level `logger = logging.getLogger(__name__)` -- correct |
| Level usage | N/A -- no logging calls needed for simple converter |
| Sensitive data | N/A |

### 6.7 Error Handling Quality

| Aspect | Assessment |
| -------- | ------------ |
| Custom exceptions | Engine uses DataValidationError on dieonerror=True; converter returns ComponentResult |
| Exception chaining | Engine uses `raise ... from e` pattern |
| die_on_error handling | Engine raises DataValidationError instead of building REJECT flow |

### 6.8 Type Hints

| Aspect | Assessment |
| -------- | ------------ |
| Method signatures | Full type hints on convert() and _parse_manualtable() |
| Parameter types | All parameters typed; return types specified |

---

## 7. Performance & Memory

Will it scale?

Converter is lightweight and does not process data. Engine uses per-row coercion loop for MANUALTABLE columns (P3 optimization opportunity).

### 7.1 Memory Management Assessment

| Aspect | Assessment |
| -------- | ------------ |
| Streaming mode | Not applicable -- simple column coercion operates on full DataFrame |
| Memory threshold | Low risk -- coercion is done in-place where possible |
| Large data handling | Per-row coercion loop (P3) -- vectorized approach possible for large DataFrames |

---

## 8. Testing

What's verified?

### 8.1 Current Coverage

| Test Type | Count | Location |
| ----------- | ------- | ---------- |
| Converter unit tests | 24 | `tests/converters/talend_to_v1/components/test_convert_type.py` |
| Engine unit tests | 24 | `tests/v1/engine/components/transform/test_convert_type.py` |
| Integration tests | 0 | None |

Phase 14-05 raised engine coverage to 95%+ floor (commit c246625 + `bfc9a87`-adjacent lift).

### 8.2 Test Gaps

~~TEST-CT-001~~ [RESOLVED in Phase 13-04, commit c246625 (BUG-CT-001)] -- engine tests added.

### 8.3 Test Classes (Engine)

- registration, validation, emptytonull, manualtable, autocast, reject routing, die-on-error, noop

---

## 9. Issues Summary

All issues grouped by priority for sprint planning.

### By Priority

| Priority | Count | IDs |
| ---------- | ------- | ----- |
| P0 | 0 | -- |
| P1 | 0 | ~~BUG-CT-001 RESOLVED Phase 13-04 c246625~~ |
| P2 | 0 | ~~TEST-CT-001 RESOLVED~~ |
| P3 | 1 | PERF-CT-001 (per-row coercion loop -- vectorization opportunity) |
| **Total open** | **1** | |

### By Category

| Category | Count | IDs |
| ---------- | ------- | ----- |
| Converter (CONV) | 0 | -- |
| Engine (ENG) | 0 | -- |
| Bug (BUG) | 0 | ~~BUG-CT-001 RESOLVED~~ |
| Naming (NAME) | 0 | -- |
| Standards (STD) | 0 | -- |
| Performance (PERF) | 1 | PERF-CT-001 |
| Testing (TEST) | 0 | ~~TEST-CT-001 RESOLVED~~ |

### Cross-Cutting Issues

Standard cross-cutting XCUT-001..XCUT-005 (base_component.py) -- see CROSS_CUTTING_ISSUES.md. All cross-cutting issues resolved by Phase 7.1/14 base class fixes.

---

## 10. Recommendations

What should be fixed, in what order?

### Immediate (Before Production)

None -- engine fully implemented; BUG-CT-001 resolved.

### Short-term (Hardening)

None open.

### Long-term (Optimization)

PERF-CT-001 (P3): Vectorize MANUALTABLE coercion for large DataFrames (currently per-row loop).

---

## Appendix A: Source References

| Source | URL/Path | Used For |
| -------- | ---------- | ---------- |
| Talaxie GitHub _java.xml | `tConvertType/tConvertType_java.xml` | Parameter definitions, defaults, elementRef names |
| Engine source | `src/v1/engine/components/transform/convert_type.py` | Engine audit |
| Converter source | `src/converters/talend_to_v1/components/transform/convert_type.py` | Converter audit |
| Converter tests | `tests/converters/talend_to_v1/components/test_convert_type.py` | Test coverage assessment |
| Engine tests | `tests/v1/engine/components/transform/test_convert_type.py` | Engine test coverage |

## Appendix B: Converter Config Key Mapping

| _java.xml Parameter | Config Key | Type | Default | Notes |
| --------------------- | ----------- | ------ | --------- | ------- |
| `AUTOCAST` | `autocast` | bool | `False` | CHECK type |
| `MANUALTABLE` | `manualtable` | list[dict] | `[]` | Stride-2 TABLE |
| `MANUALTABLE.INPUT_COLUMN` | `input_column` | str | -- | elementRef in TABLE |
| `MANUALTABLE.OUTPUT_COLUMN` | `output_column` | str | -- | elementRef in TABLE |
| `EMPTYTONULL` | `emptytonull` | bool | `False` | CHECK type |
| `DIEONERROR` | `dieonerror` | bool | `False` | CHECK type, no underscore |
| `TSTATCATCHER_STATS` | `tstatcatcher_stats` | bool | `False` | Framework param |
| `LABEL` | `label` | str | `""` | Framework param |

---

*Report generated: 2026-04-04*
*Last updated: 2026-05-11 -- Phase 15.1 reconciliation (BUG-CT-001 c246625 struck; Phase 14-05 lift noted; engine Section 5 updated)*
