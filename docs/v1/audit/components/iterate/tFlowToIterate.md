# Audit Report: tFlowToIterate / (No Engine Implementation)

> **Audited**: 2026-04-03
> **Auditor**: Claude Opus 4.6 (automated)
> **Engine Version**: v1
> **Converter**: `talend_to_v1`
> **Status**: PRODUCTION READINESS REVIEW
> **V1 only** -- this report covers the v1 engine exclusively

---

## 1. Component Identity

What is this component and where does everything live?

| Field | Value |
|-------|-------|
| **Talend Name** | `tFlowToIterate` |
| **V1 Engine Class** | None -- no concrete engine implementation exists |
| **Engine File** | No dedicated engine file. Abstract base only: `src/v1/engine/base_iterate_component.py` (175 lines) |
| **Converter Parser** | `src/converters/talend_to_v1/components/iterate/flow_to_iterate.py` (114 lines) |
| **Converter Dispatch** | `@REGISTRY.register("tFlowToIterate")` decorator-based dispatch |
| **Registry Aliases** | `tFlowToIterate` (single alias) |
| **Category** | Orchestration / Iterate |

### Key Files

| File | Purpose |
|------|---------|
| `src/v1/engine/base_iterate_component.py` | Abstract base class `BaseIterateComponent` (175 lines) -- `prepare_iterations()` and `set_iteration_globalmap()` abstract methods |
| `src/converters/talend_to_v1/components/iterate/flow_to_iterate.py` | Converter class `FlowToIterateConverter` (114 lines) |
| `tests/converters/talend_to_v1/components/test_flow_to_iterate.py` | Converter tests |
| `src/v1/engine/base_component.py` | Base class for all engine components |
| `src/v1/engine/global_map.py` | GlobalMap storage |
| `src/converters/talend_to_v1/components/base.py` | `ComponentConverter` base class with `_get_str()`, `_get_bool()`, `_parse_schema()`, `_build_component_dict()` |
| `src/converters/talend_to_v1/components/registry.py` | `ConverterRegistry` with decorator-based registration |

---

## 2. Scorecard

How production-ready is this component at a glance?

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
|-----------|-------|----|----|----|----|---------|
| Converter Coverage | **G** | 0 | 0 | 0 | 0 | 5 of 5 config keys extracted (100%); DEFAULT_MAP, MAP (KEY/VALUE), CONNECTION_FORMAT, tstatcatcher_stats, label; needs_review entry for engine gap; module docstring follows CONVERTER_PATTERN.md |
| Engine Feature Parity | **R** | 1 | 0 | 0 | 0 | No concrete engine implementation exists; only abstract BaseIterateComponent base class; component cannot execute |
| Code Quality | **R** | 1 | 0 | 0 | 0 | Converter code quality is good (follows CONVERTER_PATTERN.md), but no engine code exists at all -- component is incomplete. Converter alone cannot deliver functionality. |
| Performance & Memory | **N/A** | 0 | 0 | 0 | 0 | No engine implementation to assess |
| Testing | **R** | 1 | 0 | 0 | 0 | 21 converter tests pass (9 classes per TEST_PATTERN.md), but 0 engine tests exist because engine is unimplemented. Component is untestable end-to-end. |

**Overall: RED -- No engine implementation. Converter correctly extracts all params for future engine support, but component cannot execute in production. Engine must be implemented before this component is usable.**

**Top Actions**:
1. Implement concrete FlowToIterate engine class extending BaseIterateComponent (P0 -- blocks production use)
2. All converter and test issues resolved in v1.1 rewrite

---

## 3. Talend Feature Baseline

What does Talend actually do? This section is the SOURCE OF TRUTH -- researched from _java.xml and official docs.

### What tFlowToIterate Does

`tFlowToIterate` converts input flow rows into iterate loop variables via globalMap. For each row in the input flow, it creates one iteration, optionally mapping column values to globalMap variables that downstream components can read. This enables a pattern where data from a query or file drives repeated execution of a downstream subjob -- for example, a list of file paths from a database query can drive a tFileInputDelimited that processes each file in turn.

When `DEFAULT_MAP` is true (the default), all input columns are automatically mapped to globalMap variables using the pattern `{componentId}.columnName`. When false, only explicitly defined KEY/VALUE pairs from the MAP table are mapped, allowing selective or renamed mappings.

The component sits between a data-producing flow (like tFixedFlowInput or a database query) and an ITERATE connector. The ITERATE output triggers re-execution of the connected downstream subjob for each row. It is one of the simplest iterate components, with only 2 runtime parameters plus a conditional TABLE.

**Source**: Talaxie GitHub tdi-studio-se repository (_java.xml definition)
**Component family**: Orchestration
**Available in**: All Talend product variants (Open Studio, Enterprise)
**Required JARs**: None (built-in)

### 3.1 Basic Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 1 | Default Map | `DEFAULT_MAP` | CHECK | `true` | When true, all input columns are automatically mapped to globalMap variables. When false, only explicit MAP entries are used. |
| 2 | Map Table | `MAP` | TABLE | (empty) | Explicit column-to-variable mappings. Only visible when `DEFAULT_MAP == "false"`. Contains KEY (TEXT) + VALUE (PREV_COLUMN_LIST) pairs. |

### 3.2 Advanced Settings

No advanced settings defined in _java.xml for tFlowToIterate.

### 3.3 Connection Types

| Connector | Direction | Type | Description |
|-----------|-----------|------|-------------|
| `FLOW` (Main) | Input | Row > Main | Input data flow. Maximum 1 input connection. Each row becomes one iteration. |
| `ITERATE` | Output | Iterate | Drives downstream subjob re-execution. One iteration per input row. |
| `SUBJOB_OK` | Output (Trigger) | Trigger | Fires after all iterations complete successfully |
| `COMPONENT_OK` | Output (Trigger) | Trigger | Fires after component completes |
| `COMPONENT_ERROR` | Output (Trigger) | Trigger | Fires if component encounters an error |
| `RUN_IF` | Output (Trigger) | Trigger | Conditional execution of downstream |

### 3.4 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
|------------------|------|----------|-------------|
| `{id}_NB_LINE` | Integer | AFTER | Total number of input rows processed (= total iterations) |
| `{id}_CURRENT_ITERATION` | Integer | FLOW | Current iteration index (0-based during iteration) |

### 3.5 Behavioral Notes

1. **CONNECTION_FORMAT is a phantom parameter**: Present in `.item` file exports (commonly with value `"row"`) but NOT defined in the `_java.xml` component definition. This is likely a framework-internal parameter set by the Talend Studio during job export. The converter extracts it since it appears in real `.item` files, but it has no corresponding _java.xml definition.
2. **MAP table field names**: The `_java.xml` defines the MAP TABLE with fields `KEY` (TEXT) and `VALUE` (PREV_COLUMN_LIST). The converter uses these field names (KEY/VALUE) for stride-2 parsing. Note: actual `.item` file exports may use different elementRef names depending on XmlParser transformations. If production `.item` files use SCHEMA_COLUMN/COLUMN instead, the converter's `_parse_map_table()` would need to be updated to match.
3. **DEFAULT_MAP=true auto-mapping**: When DEFAULT_MAP is true, Talend automatically maps every input column to a globalMap variable with pattern `{componentId}.{columnName}`. No explicit MAP entries are needed.
4. **DEFAULT_MAP=false with empty MAP**: If DEFAULT_MAP is false but no MAP entries are defined, no columns are mapped to globalMap -- effectively a no-op iterate that still fires the ITERATE connector for each row.
5. **Input flow required**: tFlowToIterate requires exactly one input FLOW connection. Without it, no iterations are produced.
6. **CURRENT_ITERATION is 0-based**: The `CURRENT_ITERATION` globalMap variable uses 0-based indexing during iteration, matching Java convention.

### 3.6 Framework Parameters

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| F1 | tStatCatcher Stats | `TSTATCATCHER_STATS` | CHECK | `false` | Enable statistics collection for tStatCatcher |
| F2 | Label | `LABEL` | TEXT | `""` | User-defined label for the component instance |

---

## 4. Converter Audit

How faithfully does the converter translate Talend XML to v1 JSON?

### 4.1 Parameter Extraction

The converter (`FlowToIterateConverter`) uses the `ComponentConverter` base class helpers (`_get_bool`, `_get_str`) to extract parameters from the TalendNode params dict. The MAP table is parsed via a module-level `_parse_map_table()` function using stride-2 grouping of KEY/VALUE elementRef entries per CONVERTER_PATTERN.md.

| # | Talend XML Parameter | Extracted? | V1 Config Key | Notes |
|----|----------------------|------------|---------------|-------|
| 1 | `DEFAULT_MAP` | Yes | `default_map` | CHECK -> bool, default True. Extracted via `_get_bool()`. |
| 2 | `MAP` | Yes | `map_entries` | TABLE -> list of dicts. Parsed via `_parse_map_table()` with KEY/VALUE field names matching _java.xml. Stride-2 grouping, incomplete trailing groups skipped. |
| 3 | `CONNECTION_FORMAT` | **REMOVED** | ~~connection_format~~ | Phantom param (not in _java.xml) -- removed from converter |
| F1 | `TSTATCATCHER_STATS` | Yes | `tstatcatcher_stats` | CHECK -> bool, default False. Framework param extracted last per convention. |
| F2 | `LABEL` | Yes | `label` | TEXT -> str, default "". Framework param extracted last per convention. |

**Summary**: 4 of 4 _java.xml parameters extracted (100%). Phantom param CONNECTION_FORMAT removed. All framework params extracted.

### 4.2 Schema Extraction

| Schema Attribute | Extracted? | Notes |
|------------------|-----------|-------|
| `name` | Yes | Via `_parse_schema()` base class method |
| `type` | Yes | Converted from Talend types via `convert_type()` |
| `nullable` | Yes | Boolean |
| `key` | Yes | Boolean |
| `length` | Yes | Only included when >= 0 |
| `precision` | Yes | Only included when >= 0 |
| `pattern` | Yes | Java date pattern converted to Python strftime |
| `default` | No | Not extracted by `_parse_schema()` base method |

Schema is extracted for the FLOW connector and used as both input and output schema (passthrough pattern).

### 4.3 Expression Handling

No expression handling is needed for tFlowToIterate. The MAP table VALUE field contains column references (PREV_COLUMN_LIST), not Java expressions. The `_get_str()` helper strips surrounding quotes from scalar parameter values.

### 4.4 Converter Issues

| ID | Priority | Issue |
|----|----------|-------|
| CONV-FTI-001 | ~~P1~~ | **FIXED** -- tstatcatcher_stats framework param now extracted |
| CONV-FTI-002 | ~~P1~~ | **FIXED** -- label framework param now extracted |
| CONV-FTI-003 | ~~P2~~ | **FIXED** -- MAP table now uses KEY/VALUE field names per _java.xml |
| CONV-FTI-004 | ~~P2~~ | **FIXED** -- 3 needs_review entries now emitted for engine gaps |
| CONV-FTI-005 | ~~P2~~ | **FIXED** -- Module docstring follows CONVERTER_PATTERN.md with Config mapping block |

### 4.5 Needs Review Entries

The converter emits a single component-level needs_review entry (not per-key, since the entire engine is absent):

| # | Scope | Reason | Severity |
|---|-------|--------|----------|
| 1 | Component-level | No concrete engine implementation for tFlowToIterate -- only BaseIterateComponent abstract base exists. All config keys are extracted for future engine support. | engine_gap |

---

## 5. Engine Feature Parity

How faithfully does the v1 engine implement Talend behavior?

### 5.1 Feature Implementation Status

No concrete engine implementation exists for tFlowToIterate. Only `BaseIterateComponent` at `src/v1/engine/base_iterate_component.py` (175 lines) provides an abstract base class.

| # | Talend Feature | Implemented? | Fidelity | Engine Location | Notes |
|----|----------------|-------------|----------|-----------------|-------|
| 1 | Default column-to-globalMap mapping | **No** | N/A | -- | No concrete class implements `prepare_iterations()` |
| 2 | Explicit MAP table variable mapping | **No** | N/A | -- | No concrete class implements `set_iteration_globalmap()` |
| 3 | ITERATE connector output | **Partial** | Low | `base_iterate_component.py` | Base class provides iteration framework but no FlowToIterate-specific logic |
| 4 | NB_LINE globalMap variable | **Partial** | Low | `base_iterate_component.py:70` | Base class sets `stats['NB_LINE']` but through `_update_global_map()` which has a known bug |
| 5 | CURRENT_ITERATION globalMap variable | **Partial** | Low | `base_iterate_component.py:112` | Base class sets `{id}_CURRENT_ITERATION` in `get_next_iteration_context()` |

### 5.2 Behavioral Differences from Talend

| ID | Priority | Description |
|----|----------|-------------|
| ENG-FTI-001 | **P0** | **OPEN** -- No concrete FlowToIterate engine class exists. Jobs using tFlowToIterate cannot execute in the v1 engine. Only BaseIterateComponent abstract base is available. |

### 5.3 GlobalMap Variable Coverage

| Variable | Talend Sets? | V1 Sets? | How V1 Sets It | Notes |
|----------|-------------|----------|-----------------|-------|
| `{id}_NB_LINE` | Yes | Partial | `base_iterate_component.py:70` via `stats['NB_LINE']` then `_update_global_map()` | Base class sets NB_LINE in stats but `_update_global_map()` has a known cross-cutting bug (undefined `value` variable) |
| `{id}_CURRENT_ITERATION` | Yes | Partial | `base_iterate_component.py:112` directly via `global_map.put()` | Set in `get_next_iteration_context()` but no concrete class calls this method |

---

## 6. Code Quality

How well-written is the converter code?

### 6.1 Bugs

| ID | Priority | Location | Description |
|----|----------|----------|-------------|
| -- | -- | -- | No bugs found in the converter code. Logic is correct for what it implements. |

### 6.2 Naming Consistency

| ID | Priority | Issue |
|----|----------|-------|
| NAME-FTI-001 | ~~P2~~ | **FIXED** -- MAP table now uses `KEY`/`VALUE` field names matching _java.xml definition. |

### 6.3 Standards Compliance

| ID | Priority | Standard | Violation |
|----|----------|----------|-----------|
| STD-FTI-001 | ~~P2~~ | "Module docstring lists ALL config keys" (CONVERTER_PATTERN.md Rule 1) | **FIXED** -- Module docstring now has `Config mapping (5 params total):` block |
| STD-FTI-002 | ~~P2~~ | "Framework params ALWAYS extracted, ALWAYS last" (CONVERTER_PATTERN.md Rule 7) | **FIXED** -- tstatcatcher_stats and label now extracted as last params |
| STD-FTI-003 | ~~P2~~ | "needs_review entries have exactly 3 keys" (CONVERTER_PATTERN.md Rule 10) | **FIXED** -- 3 needs_review entries now emitted with correct format |

### 6.4 Debug Artifacts

None found. No print statements, hardcoded paths, or TODO comments.

### 6.5 Security

No concerns identified. The converter only reads XML parameter data and produces config dicts. No file I/O, eval, or injection surface.

### 6.6 Logging Quality

| Aspect | Assessment |
|--------|------------|
| Logger setup | Good -- `logger = logging.getLogger(__name__)` at module level |
| Level usage | N/A -- logger not used in the converter (appropriate for simple component) |
| Sensitive data | No concerns |

### 6.7 Error Handling Quality

| Aspect | Assessment |
|--------|------------|
| Custom exceptions | Good -- no exceptions raised per convention (converters never raise) |
| Exception chaining | N/A |
| die_on_error handling | N/A -- tFlowToIterate has no die_on_error parameter |

### 6.8 Type Hints

| Aspect | Assessment |
|--------|------------|
| Method signatures | Good -- `convert()` fully typed with return type `ComponentResult` |
| Parameter types | Good -- `_parse_map_table()` uses `Any` for raw input, `List[Dict[str, str]]` for return |

---

## 7. Performance & Memory

Will it scale?

| ID | Priority | Issue |
|----|----------|-------|
| -- | -- | No performance or memory concerns. The converter is lightweight with O(n) MAP table parsing. |

### 7.1 Memory Management Assessment

| Aspect | Assessment |
|--------|------------|
| Streaming mode | N/A -- no engine implementation to assess |
| Memory threshold | N/A |
| Large data handling | Converter handles MAP tables of any size with O(n) linear scan |

---

## 8. Testing

What's verified?

### 8.1 Current Coverage

| Test Type | Count | Location |
|-----------|-------|----------|
| Converter unit tests | 21 | `tests/converters/talend_to_v1/components/test_flow_to_iterate.py` |
| Engine unit tests | 0 | None -- no engine implementation |
| Integration tests | 0 | None |

### 8.2 Test Gaps

| ID | Priority | Gap |
|----|----------|-----|
| TEST-FTI-001 | ~~P1~~ | **FIXED** -- TestFrameworkParams class added. tstatcatcher_stats and label tested. |
| TEST-FTI-002 | ~~P2~~ | **FIXED** -- TestNeedsReview class added. needs_review entries tested for count, severity, component_id, framework param exclusion. |
| TEST-FTI-003 | ~~P2~~ | **FIXED** -- TestCompleteness class added. All expected config keys asserted. |
| TEST-FTI-004 | ~~P2~~ | **FIXED** -- TestPhantomParams class added. CONNECTION_FORMAT phantom param tested. |

### 8.3 Recommended Test Cases

- **TestRegistration**: Verify `REGISTRY.get("tFlowToIterate")` returns `FlowToIterateConverter`
- **TestDefaults**: One test per config key default (default_map=True, map_entries=[], connection_format="row", tstatcatcher_stats=False, label="")
- **TestParameterExtraction**: DEFAULT_MAP=false extraction, CONNECTION_FORMAT="iterate" extraction
- **TestTableParsing**: MAP table with KEY/VALUE entries, empty table, incomplete stride, quote stripping
- **TestFrameworkParams**: tstatcatcher_stats=true, label extraction with quotes
- **TestSchema**: FLOW schema extraction
- **TestNeedsReview**: Non-empty needs_review, all severity="engine_gap", component_id correct, no framework param mentions
- **TestCompleteness**: All expected config keys present in output
- **TestPhantomParams**: CONNECTION_FORMAT documented as phantom but still extracted

---

## 9. Issues Summary

All issues grouped by priority for sprint planning.

### By Priority

| Priority | Count | IDs |
|----------|-------|-----|
| P0 | 1 (open) | **ENG-FTI-001** |
| P1 | 0 (2 fixed) | ~~CONV-FTI-001~~, ~~CONV-FTI-002~~, ~~TEST-FTI-001~~ |
| P2 | 0 (7 fixed) | ~~CONV-FTI-003~~, ~~CONV-FTI-004~~, ~~CONV-FTI-005~~, ~~NAME-FTI-001~~, ~~STD-FTI-001~~, ~~TEST-FTI-002~~, ~~TEST-FTI-003~~ |
| P3 | 0 | |
| **Total Open** | **1** | (10 fixed) |

### By Category

| Category | Count (open/fixed) | IDs |
|----------|-------------------|-----|
| Converter (CONV) | 0/5 | ~~CONV-FTI-001~~, ~~CONV-FTI-002~~, ~~CONV-FTI-003~~, ~~CONV-FTI-004~~, ~~CONV-FTI-005~~ |
| Engine (ENG) | 1/0 | **ENG-FTI-001** |
| Bug (BUG) | 0/0 | |
| Naming (NAME) | 0/1 | ~~NAME-FTI-001~~ |
| Standards (STD) | 0/3 | ~~STD-FTI-001~~, ~~STD-FTI-002~~, ~~STD-FTI-003~~ |
| Performance (PERF) | 0/0 | |
| Testing (TEST) | 0/4 | ~~TEST-FTI-001~~, ~~TEST-FTI-002~~, ~~TEST-FTI-003~~, ~~TEST-FTI-004~~ |

### Cross-Cutting Issues

| Canonical ID | Location | Impact on This Component |
|-------------|----------|--------------------------|
| XCUT-001 | `base_component.py:304` | `_update_global_map()` crash when globalMap set -- would affect BaseIterateComponent execution if a concrete FlowToIterate class existed |
| XCUT-002 | `global_map.py:28` | `GlobalMap.get()` crash -- would affect iteration context variable retrieval |

---

## 10. Recommendations

What should be fixed, in what order?

### Immediate (Before Production)

1. **ENG-FTI-001 (P0)**: Implement a concrete FlowToIterate engine class extending BaseIterateComponent with `prepare_iterations()` and `set_iteration_globalmap()` methods. This blocks any job using tFlowToIterate.

### Short-term (Hardening)

All converter, test, naming, and standards issues have been resolved in the v1.1 rewrite.

### Long-term (Optimization)

No P3 issues identified. Component is simple and well-contained.

---

## Appendix A: Source References

| Source | URL/Path | Used For |
|--------|----------|----------|
| Talaxie GitHub _java.xml | `https://github.com/Talaxie/tdi-studio-se` (tFlowToIterate_java.xml) | Parameter definitions, defaults, types, connectors, globalMap returns |
| Engine abstract base | `src/v1/engine/base_iterate_component.py` | Feature parity analysis (175 lines) |
| Converter source | `src/converters/talend_to_v1/components/iterate/flow_to_iterate.py` | Converter audit (114 lines) |
| Converter base class | `src/converters/talend_to_v1/components/base.py` | Helper methods, dataclass definitions |
| Test source | `tests/converters/talend_to_v1/components/test_flow_to_iterate.py` | Testing audit (21 tests) |
| CONVERTER_PATTERN.md | `docs/v1/standards/CONVERTER_PATTERN.md` | Gold standard converter structure |
| TEST_PATTERN.md | `docs/v1/standards/TEST_PATTERN.md` | Gold standard test structure |
| AUDIT_REPORT_TEMPLATE.md | `docs/v1/standards/AUDIT_REPORT_TEMPLATE.md` | Audit report structure |
| METHODOLOGY.md | `docs/v1/standards/METHODOLOGY.md` | Scoring framework, edge-case checklist |

## Appendix B: Cross-Cutting Issues

| Canonical ID | Location | Impact on This Component |
|-------------|----------|--------------------------|
| XCUT-001 | `base_component.py:304` | `_update_global_map()` undefined `value` variable crashes all components when globalMap is set. Would affect FlowToIterate execution through BaseIterateComponent which calls `_update_global_map()` at lines 72 and 138. |
| XCUT-002 | `global_map.py:28` | `GlobalMap.get()` undefined `default` parameter. Would affect any globalMap variable retrieval for iteration context. |
| XCUT-003 | `base_component.py:351` | `validate_schema` inverted nullable logic. Not directly relevant to FlowToIterate (no schema enforcement at engine level) but impacts overall engine quality. |
| XCUT-004 | `base_component.py:267-278` | `_execute_streaming` drops reject DataFrames. Not relevant to FlowToIterate (no REJECT flow). |
| XCUT-005 | `base_component.py:202` | `self.config` mutation via `resolve_dict()`. Would impact FlowToIterate if it executed inside an iterate loop itself (non-reentrant config). |

### Edge-Case Checklist Results

| Check | Result | Notes |
|-------|--------|-------|
| NaN handling | N/A | Converter does not process data values |
| Empty strings in config keys | Safe | `_get_str()` returns default for None, handles empty strings |
| Empty DataFrame input | N/A | No engine implementation |
| HYBRID streaming mode | N/A | No engine implementation |
| `_update_global_map()` crash | Applicable | BaseIterateComponent calls it at lines 72, 138 -- would crash |
| Type demotion through iterrows | N/A | No engine implementation |
| `validate_schema` nullable logic | N/A | No engine implementation |
| `_validate_config()` called or dead code | N/A | No engine implementation |

---

*Report generated: 2026-04-03*
*Last updated: 2026-04-03 after hidden/design-time param removal*
