# Audit Report: tFixedFlowInput / FixedFlowInputComponent

> **Audited**: 2026-04-03
> **Auditor**: Claude Opus 4.6 (automated)
> **Engine Version**: v1
> **Converter**: `talend_to_v1`
> **Status**: PRODUCTION READINESS REVIEW
> **V1 only** -- this report contains zero references to v2/PyETL

---

## 1. Component Identity

| Field | Value |
| ------- | ------- |
| **Talend Name** | `tFixedFlowInput` |
| **V1 Engine Class** | `FixedFlowInputComponent` |
| **Engine File** | `src/v1/engine/components/file/fixed_flow_input.py` (330 lines) |
| **Converter Parser** | `src/converters/talend_to_v1/components/file/fixed_flow_input.py` (139 lines) |
| **Converter Dispatch** | `@REGISTRY.register("tFixedFlowInput")` decorator-based dispatch |
| **Registry Aliases** | `FixedFlowInputComponent`, `tFixedFlowInput` |
| **Category** | Misc / Input |

### Key Files

| File | Purpose |
| ------ | --------- |
| `src/v1/engine/components/file/fixed_flow_input.py` | Engine implementation (330 lines) |
| `src/converters/talend_to_v1/components/file/fixed_flow_input.py` | Converter class (139 lines) |
| `tests/converters/talend_to_v1/components/test_fixed_flow_input.py` | Converter tests (56 tests) |
| `src/v1/engine/base_component.py` | Base class |
| `src/v1/engine/global_map.py` | GlobalMap storage |

---

## 2. Scorecard

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
| ----------- | ------- | ---- | ---- | ---- | ---- | --------- |
| Converter Coverage | **G** | 0 | 0 | 0 | 0 | 8 unique + 2 framework params extracted via _build_component_dict; 3 needs_review for engine gaps; phantom params removed |
| Engine Feature Parity | **Y** | 1 | 5 | 3 | 0 | Three modes implemented; _update_stats NB_LINE bug; eval() in _resolve_value; validate_schema never called; separator normalization incomplete |
| Code Quality | **Y** | 2 | 2 | 4 | 2 | Cross-cutting base class bugs; dead _validate_config; eval() security risk; bare except clauses |
| Performance & Memory | **G** | 0 | 0 | 1 | 1 | Data generated in-memory (appropriate for fixed row component); minor optimization opportunities |
| Testing | **Y** | 0 | 0 | 1 | 0 | 56 converter tests across 12 classes; no engine unit tests |

**Overall: YELLOW -- Converter gold-standard; engine has P0/P1 behavioral bugs**

**Top Actions**:

1. Fix `_update_stats()` NB_LINE=0 bug (P0, ENG-FFI-001)
2. Fix `_update_global_map()` crash (P0, cross-cutting BUG-FFI-001)
3. Replace `eval()` with safe expression parsing (P1, SEC-FFI-001)
4. Call `_validate_config()` (P1, STD-FFI-001)
5. Add engine unit tests (P1, TEST-FFI-001)

---

## 3. Talend Feature Baseline

### What tFixedFlowInput Does

`tFixedFlowInput` generates a fixed number of rows of predefined data and feeds them into the data flow. It is commonly used for creating test data, providing constant lookup values, building SQL DDL statement lists, setting up context loading flows, and feeding fixed parameters into downstream components. The component does NOT read from a file or database -- it generates data purely from its configuration.

Three mutually exclusive modes are available: Single mode (VALUES table with one template row repeated NB_ROWS times), Inline Table mode (INTABLE with multiple distinct rows), and Inline Content mode (free-text delimited content parsed like a file).

**Source**: [Talaxie GitHub tFixedFlowInput_java.xml](https://github.com/nicmarti/Talaxie/blob/master/main/plugins/org.talend.designer.components.localprovider/components/tFixedFlowInput/tFixedFlowInput_java.xml), [Talend Help tFixedFlowInput Standard Properties](https://help.talend.com/r/en-US/7.3/tfixedflowinput/tfixedflowinput-standard-properties)
**Component family**: Misc (Miscellaneous / Input)
**Available in**: All Talend products (Standard)
**Required JARs**: None (pure in-memory generation)

### 3.1 Basic Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
| --- | ----------- | ----------------- | ------ | --------- | ------------- |
| 1 | Schema | `SCHEMA` | SCHEMA_TYPE | -- | Column definitions with types, lengths, patterns. Defines the output structure. |
| 2 | Number of Rows | `NB_ROWS` | TEXT | `1` | Total number of rows to generate. In Single mode, controls repetition. In Inline Content mode, typically ignored. |
| 3 | Use Single Table | `USE_SINGLEMODE` | RADIO | `true` | Default mode. Enables the VALUES table where each schema column gets a single value expression. |
| 4 | VALUES Table | `VALUES` | TABLE (SCHEMA_COLUMN, VALUE) | -- | Stride-2 table mapping each schema column to a value expression. Only visible when USE_SINGLEMODE=true. |
| 5 | Use Inline Table | `USE_INTABLE` | RADIO | `false` | Enables inline table editor where each UI row is one output row. |
| 6 | Inline Table | `INTABLE` | TABLE (per-column) | -- | Multi-row table with dynamic schema columns. Only visible when USE_INTABLE=true. |
| 7 | Use Inline Content | `USE_INLINECONTENT` | RADIO | `false` | Enables free-text area parsed as delimited file. |
| 8 | Row Separator | `ROWSEPARATOR` | TEXT | `"\\n"` | Row separator for inline content. Only visible when USE_INLINECONTENT=true. |
| 9 | Field Separator | `FIELDSEPARATOR` | TEXT | `";"` | Field separator for inline content. Only visible when USE_INLINECONTENT=true. |
| 10 | Inline Content | `INLINECONTENT` | MEMO | `""` | Free-text block of delimited data. Only visible when USE_INLINECONTENT=true. |

### 3.2 Advanced Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
| --- | ----------- | ----------------- | ------ | --------- | ------------- |
| 11 | tStatCatcher Statistics | `TSTATCATCHER_STATS` | CHECK | `false` | Framework param. Capture processing metadata for tStatCatcher. |
| 12 | Label | `LABEL` | TEXT | `""` | Framework param. Text label for the component in the Talend Studio designer. |

**Note**: DIE_ON_ERROR and CONNECTION_FORMAT are NOT in the _java.xml definition for tFixedFlowInput. They appear in some .item exports but are not declared component parameters.

### 3.3 Connection Types

| Connector | Direction | Type | Description |
| ----------- | ----------- | ------ | ------------- |
| `FLOW` (Main) | Output | Row > Main | Generated rows matching the output schema |
| `ITERATE` | Output | Iterate | For iterative processing with tFlowToIterate |
| `SUBJOB_OK` | Output (Trigger) | Trigger | Fires on successful subjob completion |
| `SUBJOB_ERROR` | Output (Trigger) | Trigger | Fires on subjob failure |
| `COMPONENT_OK` | Output (Trigger) | Trigger | Fires on component success |
| `COMPONENT_ERROR` | Output (Trigger) | Trigger | Fires on component failure |
| `RUN_IF` | Output (Trigger) | Trigger | Conditional trigger |

**Note**: No REJECT connection -- all data is predefined, no concept of malformed input.

### 3.4 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
| ------------------ | ------ | ---------- | ------------- |
| `{id}_NB_LINE` | Integer | After execution | Total rows generated |
| `{id}_NB_LINE_OK` | Integer | After execution | Rows successfully output (always equals NB_LINE) |
| `{id}_NB_LINE_REJECT` | Integer | After execution | Always 0 (no rejection mechanism) |
| `{id}_ERROR_MESSAGE` | String | On error | Last error message if error occurred |

### 3.5 Behavioral Notes

1. **Single mode (USE_SINGLEMODE=true)**: VALUES table defines one template row repeated NB_ROWS times. Each cell value is a Java expression evaluated per row.
2. **Inline Table mode (USE_INTABLE=true)**: Each table row is an independent record. NB_ROWS controls total rows; excess rows may be null-filled.
3. **Inline Content mode (USE_INLINECONTENT=true)**: Content parsed like a delimited file. NB_ROWS is typically ignored -- all content rows are processed. Context variables NOT supported in inline content.
4. **NB_ROWS=0**: Valid. Returns empty DataFrame with correct schema columns.
5. **No REJECT flow**: Unlike file input components, tFixedFlowInput has no malformed input concept.

---

## 4. Converter Audit

### 4.1 Parameter Extraction

The converter uses `FixedFlowInputConverter` in `src/converters/talend_to_v1/components/file/fixed_flow_input.py`, registered via `@REGISTRY.register("tFixedFlowInput")`. Uses `_build_component_dict` with `type_name="FixedFlowInputComponent"` per D-40/D-43.

| # | Talend XML Parameter | Extracted? | V1 Config Key | Notes |
| ---- | ---------------------- | ------------ | --------------- | ------- |
| 1 | `NB_ROWS` | Yes | `nb_rows` | int, default 1 via `_get_int()` |
| 2 | `USE_SINGLEMODE` | Yes | `use_singlemode` | bool/RADIO, default True via `_get_bool()` |
| 3 | `VALUES` | Yes | `values_config` | TABLE stride-2, module-level `_parse_values()` |
| 4 | `USE_INTABLE` | Yes | `use_intable` | bool/RADIO, default False via `_get_bool()` |
| 5 | `INTABLE` | Yes | `intable` | TABLE, module-level `_parse_intable()` |
| 6 | `USE_INLINECONTENT` | Yes | `use_inlinecontent` | bool/RADIO, default False via `_get_bool()` |
| 7 | `ROWSEPARATOR` | Yes | `row_separator` | str, default "\\n" via `_get_str()` |
| 8 | `FIELDSEPARATOR` | Yes | `field_separator` | str, default ";" via `_get_str()` |
| 9 | `INLINECONTENT` | Yes | `inline_content` | str, default "" via `_get_str()` |
| 10 | `SCHEMA` | Yes | (schema) | Extracted via `_parse_schema()`, placed at component level |
| 11 | `TSTATCATCHER_STATS` | Yes | `tstatcatcher_stats` | Framework, default False |
| 12 | `LABEL` | Yes | `label` | Framework, default "" |

**Phantom params removed**: `CONNECTION_FORMAT` (not in _java.xml), `DIE_ON_ERROR` (not in _java.xml).

**Summary**: 8 of 8 unique parameters extracted (100%) + 2 framework params. 0 missing.

### 4.2 Schema Extraction

| Schema Attribute | Extracted? | Notes |
| ------------------ | ----------- | ------- |
| `name` | Yes | Via `_parse_schema()` base class method |
| `type` | Yes | Converted via `convert_type()` |
| `nullable` | Yes | Boolean |
| `key` | Yes | Boolean |
| `length` | Yes | When >= 0 |
| `precision` | Yes | When >= 0 |
| `pattern` | Yes | Java-to-Python date pattern conversion |
| `default` | No | Not supported in base class |

### 4.3 Expression Handling

The rewritten converter does NOT handle context variables or Java expressions in VALUES at conversion time. Raw values are stored in `values_config` as-is (quotes stripped). Expression resolution is deferred to the engine runtime via `_resolve_value()`.

### 4.4 Converter Issues

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| -- | -- | No open converter issues. All phantom params removed. All _java.xml params extracted. |

### 4.5 Needs Review Entries

| # | Config Key | Reason | Severity |
| --- | ----------- | -------- | ---------- |
| 1 | `intable` | Engine reads `intable_data` but converter produces `intable` -- key name mismatch | engine_gap |
| 2 | `die_on_error` | Engine reads `die_on_error` but DIE_ON_ERROR not in _java.xml -- engine hardcoded default applies | engine_gap |
| 3 | `rows` | Engine reads `rows` for pre-generated data -- converter now provides raw config instead | engine_gap |

---

## 5. Engine Feature Parity

### 5.1 Feature Implementation Status

| # | Talend Feature | Implemented? | Fidelity | Engine Location | Notes |
| ---- | ---------------- | ------------- | ---------- | ----------------- | ------- |
| 1 | Single mode (VALUES) | **Yes** | High | `_generate_single_mode_rows()` L165 | Uses pre-parsed rows or values_config |
| 2 | Inline Table mode | **Partial** | Low | `_generate_intable_mode_rows()` L195 | Method exists but converter key mismatch (intable vs intable_data) |
| 3 | Inline Content mode | **Yes** | High | `_generate_inline_content_rows()` L217 | Splits content by separators |
| 4 | NB_ROWS generation | **Yes** | Medium | `_process()` L116 | Used in single/intable modes; ignored in inline content mode |
| 5 | Context variable resolution | **Yes** | Medium | `_resolve_value()` L268 | Handles ${context.var} and context.var |
| 6 | Java expression resolution | **Yes** | Medium | Via BaseComponent.execute() | Resolves {{java}} markers |
| 7 | GlobalMap resolution | **Yes** | Low | `_resolve_value()` L308 | Regex-based, uses eval() |
| 8 | Die on error | **Yes** | High | `_process()` L156 | Re-raises or returns empty DataFrame |
| 9 | Statistics tracking | **Partial** | Low | `_process()` L142 | NB_LINE is 0 instead of rows_generated |
| 10 | Empty schema handling | **Yes** | High | `_process()` L150 | Returns empty DataFrame with correct columns |
| 11 | Separator normalization | **Partial** | Medium | L232-234 | Only \\n and \\ | handled; \\t missing |
| 12 | validate_schema() | **No** | N/A | -- | Never called |

### 5.2 Behavioral Differences from Talend

| ID | Priority | Description |
| ---- | ---------- | ------------- |
| ENG-FFI-001 | **P0** | **`_update_stats()` passes 0 for NB_LINE**: L142 calls `self._update_stats(0, rows_generated, 0)`. NB_LINE is always 0. Should be `self._update_stats(rows_generated, rows_generated, 0)`. |
| ENG-FFI-002 | **P1** | **`_resolve_value()` uses `eval()` for globalMap expressions**: L321 calls `eval()` on partially user-controlled string. Security risk. |
| ENG-FFI-003 | **P1** | **`validate_schema()` never called**: Generated data types are whatever Python infers. |
| ENG-FFI-004 | **P1** | **Separator normalization incomplete**: Only `\\n` and `\\ | ` handled. `\\t` and other escapes not normalized. |
| ENG-FFI-005 | **P1** | **No `{id}_ERROR_MESSAGE` in globalMap**: Error messages not stored for downstream error handlers. |
| ENG-FFI-006 | **P2** | **Inline content strips field values unconditionally**: L256 calls `.strip()` on all values. Talend preserves whitespace. |
| ENG-FFI-007 | **P2** | **Single mode with `rows` ignores `nb_rows`**: When converter pre-generates rows, NB_ROWS is not respected. |
| ENG-FFI-008 | **P2** | **Intable mode null-fills beyond data**: Talend generally does not pad with null rows. |

### 5.3 GlobalMap Variable Coverage

| Variable | Talend Sets? | V1 Sets? | How V1 Sets It | Notes |
| ---------- | ------------- | ---------- | ----------------- | ------- |
| `{id}_NB_LINE` | Yes | **Bug** | `_update_stats(0, ...)` | Always 0 (ENG-FFI-001) |
| `{id}_NB_LINE_OK` | Yes | **Yes** | `_update_stats(_, rows_generated, _)` | Correct |
| `{id}_NB_LINE_REJECT` | Yes (0) | **Yes** | `_update_stats(_, _, 0)` | Always 0 (correct) |
| `{id}_ERROR_MESSAGE` | Yes | **No** | -- | Not implemented (ENG-FFI-005) |

---

## 6. Code Quality

### 6.1 Bugs

| ID | Priority | Location | Description |
| ---- | ---------- | ---------- | ------------- |
| BUG-FFI-001 | **P0** | `base_component.py:304` | **CROSS-CUTTING**: `_update_global_map()` references undefined variable `value` (should be `stat_value`). Causes NameError at runtime. |
| BUG-FFI-002 | **P0** | `global_map.py:28` | **CROSS-CUTTING**: `GlobalMap.get()` references undefined `default` parameter. Causes NameError. |
| BUG-FFI-003 | **P1** | `fixed_flow_input.py:142` | `_update_stats(0, rows_generated, 0)` sets NB_LINE to 0. |
| BUG-FFI-004 | **P1** | `fixed_flow_input.py:61-101` | `_validate_config()` is never called -- dead code. |
| BUG-FFI-005 | **P2** | `fixed_flow_input.py:286,322` | Bare `except:` clauses catch SystemExit and KeyboardInterrupt. |
| BUG-FFI-006 | **P2** | `fixed_flow_input.py:282-285` | Negative integers treated as floats (`'-5'.isdigit()` returns False). |
| BUG-FFI-007 | **P2** | `fixed_flow_input.py:318` | `replace(')', '')` destroys ALL closing parentheses in expressions. |
| BUG-FFI-008 | **P2** | `fixed_flow_input.py:318` | Only `((Integer)` cast type handled; other Java casts broken. |
| BUG-FFI-009 | **P3** | `fixed_flow_input.py:309` | `import re` inside function body instead of module-level. |
| BUG-FFI-010 | **P3** | `fixed_flow_input.py:310` | `re.search()` matches only first globalMap reference in multi-reference expressions. |

### 6.2 Naming Consistency

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| NAME-FFI-001 | **P2** | `field_separator` vs `delimiter` inconsistency across file components |

### 6.3 Standards Compliance

| ID | Priority | Standard | Violation |
| ---- | ---------- | ---------- | ----------- |
| STD-FFI-001 | **P1** | `_validate_config()` should be called at start of `_process()` | Never called -- dead code |
| STD-FFI-002 | **P2** | `validate_schema()` should be called on output DataFrame | Never called |

### 6.4 Debug Artifacts

Excessive INFO-level logging in `_generate_inline_content_rows()` (8 log statements that output raw data content). Should be DEBUG level.

### 6.5 Security

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| SEC-FFI-001 | **P1** | `eval()` call in `_resolve_value()` L321 on partially user-controlled string from globalMap. Should use `ast.literal_eval()` or safe expression evaluator. |
| SEC-FFI-002 | **P3** | Raw inline content logged at INFO level -- may contain sensitive data. |

### 6.6 Logging Quality

| Aspect | Assessment |
| -------- | ------------ |
| Logger setup | Correct: `logger = logging.getLogger(__name__)` |
| Level usage | Partially incorrect: many DEBUG-appropriate messages at INFO |
| Sensitive data | Risk: raw inline content logged at INFO |

### 6.7 Error Handling Quality

| Aspect | Assessment |
| -------- | ------------ |
| Custom exceptions | Not used (generic Exception re-raise) |
| die_on_error handling | Correct pattern: re-raises or returns empty DF |
| Bare except | Two bare `except:` clauses in `_resolve_value()` |

### 6.8 Type Hints

| Aspect | Assessment |
| -------- | ------------ |
| Method signatures | `_process()` return type correct |
| `_resolve_value()` | Return type missing |
| Parameter types | Partially typed (`List` should be `List[Dict]`) |

---

## 7. Performance & Memory

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| PERF-FFI-001 | **P2** | `_resolve_value()` called per cell, not vectorized. For 1000x10 schema, 10K calls with regex and eval(). |
| PERF-FFI-002 | **P3** | `import re` inside `_resolve_value()` on every call with globalMap reference. |

### 7.1 Memory Management Assessment

| Aspect | Assessment |
| -------- | ------------ |
| Streaming mode | Not applicable -- data generated in-memory |
| Memory threshold | Large NB_ROWS (millions) could consume significant memory |
| Large data handling | All rows generated as List[Dict] before DataFrame creation |

---

## 8. Testing

### 8.1 Current Coverage

| Test Type | Count | Location |
| ----------- | ------- | ---------- |
| Converter unit tests | 56 | `tests/converters/talend_to_v1/components/test_fixed_flow_input.py` |
| Engine unit tests | 0 | None |
| Integration tests | 0 | None (covered by regression guard `test_converter_output_structure.py`) |

### 8.2 Test Gaps

| ID | Priority | Gap |
| ---- | ---------- | ----- |
| TEST-FFI-001 | **P2** | No engine unit tests for FixedFlowInputComponent (330 lines of untested engine code) |

### 8.3 Recommended Test Cases

- Engine: Single mode with various NB_ROWS values (0, 1, 100)
- Engine: Inline content mode with custom separators
- Engine: die_on_error=True vs False behavior
- Engine: _resolve_value() with context variables and globalMap references
- Engine: Statistics tracking (NB_LINE correctness)

---

## 9. Issues Summary

### By Priority

| Priority | Count | IDs |
| ---------- | ------- | ----- |
| P0 | 2 | BUG-FFI-001, BUG-FFI-002 (cross-cutting) |
| P1 | 7 | BUG-FFI-003, BUG-FFI-004, ENG-FFI-002, ENG-FFI-003, ENG-FFI-004, ENG-FFI-005, SEC-FFI-001 |
| P2 | 8 | BUG-FFI-005, BUG-FFI-006, BUG-FFI-007, BUG-FFI-008, ENG-FFI-006, ENG-FFI-007, ENG-FFI-008, PERF-FFI-001 |
| P3 | 3 | BUG-FFI-009, BUG-FFI-010, SEC-FFI-002 |
| **Total** | **20** | |

### By Category

| Category | Count | IDs |
| ---------- | ------- | ----- |
| Converter (CONV) | 0 | -- |
| Engine (ENG) | 8 | ENG-FFI-001 through ENG-FFI-008 |
| Bug (BUG) | 10 | BUG-FFI-001 through BUG-FFI-010 |
| Naming (NAME) | 1 | NAME-FFI-001 |
| Standards (STD) | 2 | STD-FFI-001, STD-FFI-002 |
| Performance (PERF) | 1 | PERF-FFI-001 |
| Security (SEC) | 2 | SEC-FFI-001, SEC-FFI-002 |
| Testing (TEST) | 1 | TEST-FFI-001 |

### Cross-Cutting Issues

| Canonical ID | Location | Impact on This Component |
| ------------- | ---------- | -------------------------- |
| XCUT-001 | `base_component.py:304` | `_update_global_map()` crash (BUG-FFI-001) |
| XCUT-002 | `global_map.py:28` | `GlobalMap.get()` crash (BUG-FFI-002) |

---

## 10. Recommendations

### Immediate (Before Production)

- Fix `_update_stats()` NB_LINE=0 bug (P0, ENG-FFI-001)
- Fix cross-cutting base class bugs (P0, BUG-FFI-001/002)
- Replace `eval()` in `_resolve_value()` (P1, SEC-FFI-001)
- Call `_validate_config()` at start of `_process()` (P1, STD-FFI-001)
- Call `validate_schema()` on output DataFrame (P1, ENG-FFI-003)

### Short-term (Hardening)

- Fix separator normalization for \\t and other escapes (P1, ENG-FFI-004)
- Store `{id}_ERROR_MESSAGE` in globalMap on error (P1, ENG-FFI-005)
- Fix bare except clauses (P2, BUG-FFI-005)
- Fix negative integer coercion (P2, BUG-FFI-006)
- Add engine unit tests (P2, TEST-FFI-001)

### Long-term (Optimization)

- Vectorize `_resolve_value()` for large NB_ROWS (P2, PERF-FFI-001)
- Move `import re` to module level (P3, BUG-FFI-009)
- Reduce INFO logging verbosity (P3, SEC-FFI-002)

---

## 11. Risk Assessment

### Risk Matrix

| Risk | Likelihood | Impact | Mitigation |
| ------ | ----------- | -------- | ------------ |
| Data injection via eval() | Low | High | Replace eval() with ast.literal_eval() or safe expression evaluator |
| NB_LINE=0 breaks downstream NB_LINE checks | High | Medium | Fix _update_stats() first argument |
| Large NB_ROWS memory exhaustion | Low | High | Document max recommended NB_ROWS; consider streaming for >100K |
| Inline content with sensitive data in logs | Medium | Medium | Change log level from INFO to DEBUG for raw content |
| INTABLE mode config key mismatch | Medium | High | Engine reads `intable_data`, converter produces `intable` -- inline table mode silently broken |
| Separator escape sequences not normalized | Medium | Medium | \\t in FIELDSEPARATOR causes incorrect splitting |

### High-Risk Job Patterns

1. **Jobs using INTABLE mode**: Config key mismatch means intable data is never read by engine. Empty results.
2. **Jobs with globalMap expressions in VALUES**: eval() vulnerability and incomplete cast handling (only Integer supported).
3. **Jobs with NB_ROWS > 100K in single mode**: Memory pressure from List[Dict] materialization before DataFrame.
4. **Jobs checking {id}_NB_LINE downstream**: Always returns 0 due to _update_stats() bug.
5. **Jobs with \\t as field separator**: Literal "\\t" string used instead of tab character.

### Safe Usage Patterns

1. **Single mode with literal string values**: Most reliable path. VALUES with quoted string literals work correctly.
2. **Inline content with \\n row separator and ; field separator**: Default separators work correctly.
3. **NB_ROWS=1 (most common)**: Single row generation is fast and reliable.
4. **Static test data generation**: No context variables or globalMap references -- bypasses _resolve_value() entirely.

---

## Appendix A: Source References

| Source | URL/Path | Used For |
| -------- | ---------- | ---------- |
| Talaxie GitHub _java.xml | `<https://github.com/nicmarti/Talaxie/blob/master/main/plugins/org.talend.designer.components.localprovider/components/tFixedFlowInput/tFixedFlowInput_java.xml`> | Parameter definitions, defaults |
| Talend Help | `<https://help.talend.com/r/en-US/7.3/tfixedflowinput/tfixedflowinput-standard-properties`> | Behavioral documentation |
| Engine source | `src/v1/engine/components/file/fixed_flow_input.py` | Feature parity analysis |
| Converter source | `src/converters/talend_to_v1/components/file/fixed_flow_input.py` | Converter audit |
| Converter tests | `tests/converters/talend_to_v1/components/test_fixed_flow_input.py` | Test coverage analysis |

## Appendix B: Cross-Cutting Issues

| Canonical ID | Location | Impact on This Component |
| ------------- | ---------- | -------------------------- |
| XCUT-001 | `base_component.py:304` | `_update_global_map()` crash when globalMap set |
| XCUT-002 | `global_map.py:28` | `GlobalMap.get()` broken signature |

---

*Report generated: 2026-04-03*
*Last updated: 2026-04-03 after Phase 09-08 gold-standard rewrite*
