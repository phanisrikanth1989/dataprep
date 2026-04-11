# Audit Report: tJavaRow / JavaRowComponent

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
| **Talend Name** | `tJavaRow` |
| **V1 Engine Class** | `JavaRowComponent` |
| **Engine File** | `src/v1/engine/components/transform/java_row_component.py` (99 lines) |
| **Converter Parser** | `src/converters/talend_to_v1/components/transform/java_row_component.py` (80 lines) |
| **Converter Dispatch** | `@REGISTRY.register("tJavaRow")` decorator-based dispatch |
| **Registry Aliases** | `JavaRowComponent`, `tJavaRow` |
| **Category** | Transform / Custom Code (Java bridge) |

### Key Files

| File | Purpose |
| ------ | --------- |
| `src/v1/engine/components/transform/java_row_component.py` | Engine implementation (99 lines) -- thin orchestrator delegating to Java bridge |
| `src/converters/talend_to_v1/components/transform/java_row_component.py` | Converter class (80 lines) |
| `tests/converters/talend_to_v1/components/test_java_row_component.py` | Converter tests (22 tests) |
| `src/v1/engine/base_component.py` | Base class |
| `src/v1/engine/global_map.py` | GlobalMap storage |

---

## 2. Scorecard

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
| ----------- | ------- | ---- | ---- | ---- | ---- | --------- |
| Converter Coverage | **G** | 0 | 0 | 0 | 0 | 3 of 3 _java.xml params extracted (100%); phantom DIE_ON_ERROR removed; output_schema converter-generated for engine; 2 needs_review entries |
| Engine Feature Parity | **Y** | 2 | 5 | 4 | 2 | No REJECT flow; no die_on_error; synchronized parallel execution; no reverse context/globalMap sync |
| Code Quality | **G** | 0 | 0 | 1 | 0 | Gold standard converter; clean _build_component_dict usage; follows CONVERTER_PATTERN.md |
| Performance & Memory | **Y** | 1 | 2 | 2 | 1 | `synchronized(compiledScript)` serializes parallel row execution; no chunking; full Arrow copy |
| Testing | **Y** | 0 | 0 | 1 | 0 | 22 converter tests in 9 classes per TEST_PATTERN.md; no engine unit tests (D-89) |

**Overall: YELLOW -- Converter is Green, engine has significant gaps in error handling and parallel semantics**

**Top Actions**:

1. Implement REJECT flow in engine for die_on_error=false case
2. Fix synchronized bottleneck in JavaBridge parallel execution
3. Add reverse context/globalMap sync after Java execution
4. Add engine unit tests

---

## 3. Talend Feature Baseline

### What tJavaRow Does

`tJavaRow` is a custom code component in the Talend Custom Code family that executes user-written Java code on each row of a data flow. It functions as an in-line per-row transformer, accepting one input flow and producing one output flow. The component is conceptually similar to a 1-input/1-output `tMap` but with arbitrary Java logic instead of expression mappings. In Talend's generated code, the user's Java snippet is embedded directly inside a `while(hasNext)` loop that iterates over all incoming rows.

**Source**: [tJavaRow Standard Properties (Talend 8.0)](https://help.qlik.com/talend/en-US/components/8.0/java-custom-code/tjavarow-standard-properties), [Talaxie GitHub _java.xml](https://raw.githubusercontent.com/Talaxie/tdi-studio-se/refs/heads/master/main/plugins/org.talend.designer.components.localprovider/components/tJavaRow/tJavaRow_java.xml)
**Component family**: Custom Code (Java custom code)
**Available in**: All Talend products (Standard)
**Required JARs**: None (built-in)

### 3.1 Basic Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
| --- | ----------- | ----------------- | ------ | --------- | ------------- |
| 1 | Schema | `SCHEMA` | SCHEMA_TYPE | -- | Column definitions for input/output. Passthrough schema -- input equals output. |
| 2 | Code | `CODE` | MEMO_JAVA | (sample code) | Java code executed once per input row. Access to input_row, output_row, context, globalMap. XML-entity-encoded in .item files. |

### 3.2 Advanced Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
| --- | ----------- | ----------------- | ------ | --------- | ------------- |
| 3 | Import | `IMPORT` | MEMO_IMPORT | (comment) | Java import statements for external classes referenced in CODE. |

### 3.3 Connection Types

| Connector | Direction | Type | Description |
| ----------- | ----------- | ------ | ------------- |
| `FLOW` (Main) | Input | Row > Main | Incoming data flow. Each row accessible via `input_row` object. |
| `FLOW` (Main) | Output | Row > Main | Outgoing data flow. Each row written via `output_row` object. 1:1 row mapping. |
| `SUBJOB_OK` | Output (Trigger) | Trigger | Fires when subjob completes successfully. |
| `SUBJOB_ERROR` | Output (Trigger) | Trigger | Fires when subjob fails. |

### 3.4 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
| ------------------ | ------ | ---------- | ------------- |
| `{id}_NB_LINE` | Integer | After execution | Total number of rows processed. |

### 3.5 Behavioral Notes

1. **CODE is mandatory**: Talend requires at least one statement in the CODE field.
2. **IMPORT is optional**: Standard Java classes are available without imports.
3. **1:1 row mapping**: tJavaRow always produces exactly one output row per input row.
4. **Phantom DIE_ON_ERROR**: This parameter does NOT appear in the _java.xml definition. It exists in some .item exports but is not a true tJavaRow parameter.
5. **XML entity encoding**: CODE and IMPORT use `&#xD;&#xA;` for CR+LF, `&#xA;` for LF, `&#xD;` for CR.
6. **Per-row sequential processing**: Talend processes rows strictly sequentially within a single thread.

---

## 4. Converter Audit

### 4.1 Parameter Extraction

The converter uses `JavaRowComponentConverter` registered via `@REGISTRY.register("tJavaRow")`. It extracts CODE and IMPORT via `_get_param()` (MEMO type -- raw extraction per Pitfall 6) and builds output_schema from FLOW schema columns for engine compatibility.

| # | Talend XML Parameter | Extracted? | V1 Config Key | Default | needs_review? | Notes |
| ---- | ---------------------- | ------------ | --------------- | --------- | --------------- | ------- |
| 1 | `CODE` | **Yes** | `java_code` | `""` | No | Via `_get_param()` -- MEMO_JAVA type |
| 2 | `IMPORT` | **Yes** | `imports` | `""` | **Yes** | Via `_get_param()` -- MEMO_IMPORT type; engine does not read |
| 3 | `SCHEMA` | **Yes** | `output_schema` | `[]` | **Yes** | Converter-generated list of {name, type} dicts from schema columns |
| -- | `TSTATCATCHER_STATS` | **Yes** | `tstatcatcher_stats` | `False` | No | Framework param |
| -- | `LABEL` | **Yes** | `label` | `""` | No | Framework param |

**Phantom params REMOVED**: `DIE_ON_ERROR` (not in _java.xml -- was in previous converter)

**Summary**: 3 of 3 _java.xml parameters extracted (100%). 5 total config keys (3 unique + 2 framework).

### 4.2 Schema Extraction

| Schema Attribute | Extracted? | Notes |
| ------------------ | ----------- | ------- |
| `name` | Yes | Column name from FLOW schema |
| `type` | Yes | Converted via `convert_type()` |
| `nullable` | Yes | From SchemaColumn |
| `key` | Yes | From SchemaColumn |
| `length` | Yes | When >= 0 |
| `precision` | Yes | When >= 0 |
| `pattern` | Yes | Java-to-Python date pattern conversion |
| `default` | No | Not extracted by base class |

Schema is passthrough: input == output (transform component).

### 4.3 Expression Handling

CODE and IMPORT are stored as raw strings. No expression conversion is performed -- the Java code is passed through as-is for the Java bridge to execute.

### 4.4 Converter Issues

None. Converter follows gold standard pattern.

### 4.5 Needs Review Entries

| # | Config Key | Reason | Severity |
| --- | ----------- | -------- | ---------- |
| 1 | `imports` | Engine does not read 'imports' from config | engine_gap |
| 2 | `output_schema` | output_schema is converter-generated for engine compatibility, not from _java.xml | engine_gap |

---

## 5. Engine Feature Parity

### 5.1 Feature Implementation Status

| # | Talend Feature | Implemented? | Fidelity | Engine Location | Notes |
| ---- | ---------------- | ------------- | ---------- | ----------------- | ------- |
| 1 | Per-row Java code execution | **Yes** | Medium | `_process()` line 37 | Delegates to Java bridge; uses parallel execution (not sequential like Talend) |
| 2 | input_row / output_row access | **Yes** | Medium | Java bridge `RowWrapper` | Uses get()/set() methods + Groovy propertyMissing for dot notation |
| 3 | output_schema type mapping | **Yes** | Medium | `_process()` line 46 | Reads from config; used for Arrow serialization |
| 4 | imports prepended to code | **Yes** | High | `_process()` line 55 | Prepends imports to java_code string |
| 5 | REJECT flow | **No** | N/A | -- | Not implemented; exceptions propagate or crash |
| 6 | die_on_error toggle | **No** | N/A | -- | Engine does not read die_on_error config |
| 7 | context variable access | **Partial** | Medium | `_process()` line 73 | Forward sync only; changes in Java code not synced back |
| 8 | globalMap access | **Partial** | Medium | `_process()` line 77 | Forward sync only; changes not synced back |
| 9 | NB_LINE statistics | **Yes** | High | `_process()` line 88 | Via `_update_stats()` base class method |

### 5.2 Behavioral Differences from Talend

| ID | Priority | Description |
| ---- | ---------- | ------------- |
| ENG-JR-001 | **P0** | No REJECT flow -- error rows are lost instead of being routed to REJECT output |
| ENG-JR-002 | **P0** | Parallel execution via `IntStream.parallel()` breaks sequential semantics -- row order not guaranteed, shared state race conditions |
| ENG-JR-003 | **P1** | No die_on_error toggle -- engine always propagates exceptions |
| ENG-JR-004 | **P1** | No reverse context sync -- context changes in Java code not reflected in Python |
| ENG-JR-005 | **P1** | No reverse globalMap sync -- globalMap changes in Java code not reflected in Python |
| ENG-JR-006 | **P1** | RowWrapper get()/set() returns Object type -- requires explicit casting unlike Talend typed fields |
| ENG-JR-007 | **P1** | `synchronized(compiledScript)` serializes all parallel execution to a single thread |
| ENG-JR-008 | **P2** | No input validation for java_code or output_schema config keys |
| ENG-JR-009 | **P2** | Arrow serialization creates full copy of DataFrame for each invocation |
| ENG-JR-010 | **P2** | No support for Dynamic schema columns |
| ENG-JR-011 | **P2** | output_schema type mapping lossy for Long, Float, BigDecimal |
| ENG-JR-012 | **P3** | No support for tStatCatcher statistics collection |
| ENG-JR-013 | **P3** | No ERROR_MESSAGE globalMap variable on error |

### 5.3 GlobalMap Variable Coverage

| Variable | Talend Sets? | V1 Sets? | How V1 Sets It | Notes |
| ---------- | ------------- | ---------- | ----------------- | ------- |
| `{id}_NB_LINE` | Yes | Yes | `_update_stats()` line 88 | Rows processed count |
| `{id}_NB_LINE_OK` | Yes | No | -- | Not tracked separately |
| `{id}_NB_LINE_REJECT` | Yes | No | -- | No REJECT flow |
| `{id}_ERROR_MESSAGE` | Yes | No | -- | No error capture |

---

## 6. Code Quality

### 6.1 Bugs

None in converter code. Engine cross-cutting bugs apply (see Appendix B).

### 6.2 Naming Consistency

No naming issues found. Engine config keys match converter output.

### 6.3 Standards Compliance

Converter follows CONVERTER_PATTERN.md exactly:

- Module docstring with config mapping
- `@REGISTRY.register("tJavaRow")` decorator
- Parameter extraction order: core -> framework (last)
- `_build_component_dict` with `type_name="JavaRowComponent"`
- Per-feature needs_review with 3 keys (issue, component, severity)

No violations found.

### 6.4 Debug Artifacts

None found.

### 6.5 Security

Engine executes arbitrary Java/Groovy code via Java bridge. This is by design (tJavaRow is a code execution component). No additional security concerns beyond the inherent code execution risk.

### 6.6 Logging Quality

| Aspect | Assessment |
| -------- | ------------ |
| Logger setup | Correct: `logger = logging.getLogger(__name__)` in both converter and engine |
| Level usage | Engine uses info for success, error for failures -- appropriate |
| Sensitive data | f-string in engine logger includes component ID -- acceptable |

### 6.7 Error Handling Quality

| Aspect | Assessment |
| -------- | ------------ |
| Custom exceptions | Engine raises ValueError and RuntimeError directly -- no custom exceptions |
| Exception chaining | Engine uses bare `raise` in except block -- preserves chain |
| die_on_error handling | Not implemented in engine |

### 6.8 Type Hints

| Aspect | Assessment |
| -------- | ------------ |
| Method signatures | Engine: `_process(self, input_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]` -- correct |
| Parameter types | Converter: fully typed with `Dict[str, Any]`, `List[str]`, etc. |

---

## 7. Performance & Memory

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| PERF-JR-001 | **P0** | `synchronized(compiledScript)` in JavaBridge serializes all parallel row execution -- effectively single-threaded |
| PERF-JR-002 | **P1** | Full Arrow IPC copy of entire DataFrame per Java bridge invocation -- no chunking |
| PERF-JR-003 | **P1** | No streaming/chunked mode for large datasets |
| PERF-JR-004 | **P2** | Groovy compilation overhead per invocation (not cached across component executions) |
| PERF-JR-005 | **P2** | RowWrapper creates Object[] array per row -- additional allocation |
| PERF-JR-006 | **P3** | No JIT warmup optimization for frequently executed code paths |

### 7.1 Memory Management Assessment

| Aspect | Assessment |
| -------- | ------------ |
| Streaming mode | Not supported -- entire DataFrame loaded into memory |
| Memory threshold | No configurable threshold -- processes all rows at once |
| Large data handling | Full Arrow copy + parallel RowWrapper[] allocation = 2x+ memory usage |

---

## 8. Testing

### 8.1 Current Coverage

| Test Type | Count | Location |
| ----------- | ------- | ---------- |
| Converter unit tests | 22 | `tests/converters/talend_to_v1/components/test_java_row_component.py` |
| Engine unit tests | 0 | None |
| Integration tests | 2 | `tests/v1/test_java_integration.py` |

### 8.2 Test Gaps

| ID | Priority | Gap |
| ---- | ---------- | ----- |
| TEST-JR-001 | **P2** | No engine unit tests for JavaRowComponent._process() |

### 8.3 Recommended Test Cases

- Engine: Empty DataFrame input handling
- Engine: Missing java_code config raises ValueError
- Engine: Missing output_schema config raises ValueError
- Engine: Java bridge unavailable raises RuntimeError
- Engine: Large DataFrame performance benchmark
- Engine: Context/globalMap forward sync verification

---

## 9. Issues Summary

### By Priority

| Priority | Count | IDs |
| ---------- | ------- | ----- |
| P0 | 3 | ENG-JR-001, ENG-JR-002, PERF-JR-001 |
| P1 | 7 | ENG-JR-003, ENG-JR-004, ENG-JR-005, ENG-JR-006, ENG-JR-007, PERF-JR-002, PERF-JR-003 |
| P2 | 7 | ENG-JR-008, ENG-JR-009, ENG-JR-010, ENG-JR-011, PERF-JR-004, PERF-JR-005, TEST-JR-001 |
| P3 | 3 | ENG-JR-012, ENG-JR-013, PERF-JR-006 |
| **Total** | **20** | |

### By Category

| Category | Count | IDs |
| ---------- | ------- | ----- |
| Engine (ENG) | 13 | ENG-JR-001 through ENG-JR-013 |
| Performance (PERF) | 6 | PERF-JR-001 through PERF-JR-006 |
| Testing (TEST) | 1 | TEST-JR-001 |
| Converter (CONV) | 0 | -- |
| Bug (BUG) | 0 | -- |
| Naming (NAME) | 0 | -- |
| Standards (STD) | 0 | -- |

### Cross-Cutting Issues

Engine cross-cutting bugs from base_component.py apply to JavaRowComponent (see Appendix B).

---

## 10. Recommendations

### Immediate (Before Production)

1. **ENG-JR-001 (P0)**: Implement REJECT flow for error row routing
2. **ENG-JR-002 (P0)**: Fix parallel execution to preserve sequential row ordering
3. **PERF-JR-001 (P0)**: Remove synchronized bottleneck in JavaBridge

### Short-term (Hardening)

1. **ENG-JR-003 (P1)**: Implement die_on_error config toggle
2. **ENG-JR-004/005 (P1)**: Implement reverse context/globalMap sync
3. **PERF-JR-002/003 (P1)**: Add chunked processing for large DataFrames

### Long-term (Optimization)

1. **ENG-JR-012 (P3)**: Add tStatCatcher statistics support
2. **PERF-JR-006 (P3)**: Add JIT warmup for frequently executed code

---

## Appendix A: Source References

| Source | URL/Path | Used For |
| -------- | ---------- | ---------- |
| Talaxie GitHub _java.xml | `<https://raw.githubusercontent.com/Talaxie/tdi-studio-se/refs/heads/master/main/plugins/org.talend.designer.components.localprovider/components/tJavaRow/tJavaRow_java.xml`> | Parameter definitions, defaults |
| Official Talend docs | `<https://help.qlik.com/talend/en-US/components/8.0/java-custom-code/tjavarow-standard-properties`> | Feature baseline |
| Engine source | `src/v1/engine/components/transform/java_row_component.py` | Feature parity analysis |
| Converter source | `src/converters/talend_to_v1/components/transform/java_row_component.py` | Converter audit |
| Test source | `tests/converters/talend_to_v1/components/test_java_row_component.py` | Test coverage |

## Appendix B: Engine Config Key Mapping

| Config Key | _java.xml Param | Engine Reads? | Engine Location | Notes |
| ----------- | ---------------- | -------------- | ----------------- | ------- |
| `java_code` | CODE | **Yes** | `_process()` line 45 | Prepended with imports before execution |
| `imports` | IMPORT | **Yes** | `_process()` line 46 | Read but only used when non-empty |
| `output_schema` | -- (converter-generated) | **Yes** | `_process()` line 47 | Used for Arrow type mapping |
| `tstatcatcher_stats` | TSTATCATCHER_STATS | No | -- | Framework param, not used by engine |
| `label` | LABEL | No | -- | Framework param, not used by engine |

---

*Report generated: 2026-04-04*
*Last updated: 2026-04-04 after Phase 13 gold-standard rewrite -- phantom DIE_ON_ERROR removed, converter standardized*
