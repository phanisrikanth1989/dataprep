# Audit Report: tFixedFlowInput / FixedFlowInputComponent

> **Audited**: 2026-04-03
> **Auditor**: Claude Opus 4.6 (automated)
> **Engine Version**: v1
> **Converter**: `talend_to_v1`
> **Status**: ENGINE REWRITTEN — 2026-05-01 (see § Resolved Issues)
> **V1 only** -- this report contains zero references to v2/PyETL

---

## 1. Component Identity

| Field | Value |
| ------- | ------- |
| **Talend Name** | `tFixedFlowInput` |
| **V1 Engine Class** | `FixedFlowInputComponent` |
| **Engine File** | `src/v1/engine/components/file/fixed_flow_input.py` (268 lines, rewritten 2026-05-01) |
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
| Converter Coverage | **G** | 0 | 0 | 0 | 0 | 8 unique + 2 framework params extracted via _build_component_dict; 1 needs_review (die_on_error engine gap); intable/rows gaps resolved |
| Engine Feature Parity | **G** | 0 | 0 | 0 | 1 | All three modes correct; @REGISTRY.register added; NB_LINE fixed; intable key fixed; separator normalization complete |
| Code Quality | **G** | 0 | 0 | 0 | 1 | _validate_config raises ConfigurationError; eval() removed; bare excepts removed; import re at module level |
| Performance & Memory | **G** | 0 | 0 | 1 | 0 | _resolve_value still called per cell (PERF-FFI-001); acceptable for typical NB_ROWS |
| Testing | **G** | 0 | 0 | 0 | 0 | 56 converter + 34 engine unit tests across 8 classes |

**Overall:** GREEN -- Engine fully rewritten; all P0/P1 issues resolved

**Remaining actions**:

1. (P2) Consider vectorizing `_resolve_value()` for large NB_ROWS (PERF-FFI-001)

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

**Note**: DIE_ON_ERROR and CONNECTION_FORMAT are NOT in the `_java.xml` definition for tFixedFlowInput. They appear in some .item exports but are not declared component parameters.

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

**Phantom params removed**: `CONNECTION_FORMAT` (not in `_java.xml`), `DIE_ON_ERROR` (not in `_java.xml`).

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
| 1 | `die_on_error` | Engine reads `die_on_error` but DIE_ON_ERROR not in `_java.xml` -- engine hardcoded default applies | engine_gap |

**Resolved entries (2026-05-01)**:

- `intable` key mismatch: engine rewritten to read `intable` (not `intable_data`).
- `rows` key: engine no longer reads `rows`; single mode reads `values_config` list-of-dicts directly.

---

## 5. Engine Feature Parity

### 5.1 Feature Implementation Status

| # | Talend Feature | Implemented? | Fidelity | Engine Location | Notes |
| ---- | ---------------- | ------------- | ---------- | ----------------- | ------- |
| 1 | Single mode (VALUES) | **Yes** | High | `_build_single_mode_rows()` | list-of-dicts format; dict fallback supported |
| 2 | Inline Table mode | **Yes** | High | `_build_intable_rows()` | Reads `intable` key; stride grouping by ncols; nb_rows limit; no null-padding |
| 3 | Inline Content mode | **Yes** | High | `_build_inline_content_rows()` | All lines emitted; nb_rows ignored |
| 4 | NB_ROWS generation | **Yes** | High | `_process()` | Single/intable modes; ignored in inline content mode |
| 5 | Context variable resolution | **Yes** | High | `_resolve_value()` | Delegated to ContextManager.resolve_string() |
| 6 | Java expression resolution | **Yes** | Medium | Via BaseComponent.execute() | Resolves {{java}} markers |
| 7 | GlobalMap resolution | **Yes** | High | `_resolve_value()` | Regex-based, no eval(); returns raw globalMap value |
| 8 | Statistics tracking | **Yes** | High | `_process()` | `_update_stats(row_count, row_count, 0)` -- NB_LINE correct |
| 9 | Empty schema / nb_rows=0 | **Yes** | High | `_process()` | Returns empty DataFrame with correct schema columns |
| 10 | Separator normalization | **Yes** | High | `_build_inline_content_rows()` | `\\n`, `\\t`, `\\r`, and pipe char all normalized via `_ESCAPE_MAP` |

### 5.2 Behavioral Differences from Talend

| ID | Priority | Description |
| ---- | ---------- | ------------- |
| ENG-FFI-005 | **P3** | **No `{id}_ERROR_MESSAGE` in globalMap**: ConfigurationError propagates via engine but error message string not stored in globalMap for downstream error handlers. |

**Resolved (2026-05-01)**:

- ENG-FFI-001 (P0): `_update_stats(0, ...)` NB_LINE bug fixed → `_update_stats(row_count, row_count, 0)`.
- ENG-FFI-002 (P1): `eval()` removed; globalMap value returned directly without expression evaluation.
- ENG-FFI-003 (P1): `validate_schema()` handled by BaseComponent after `_process()` returns (Rule 11).
- ENG-FFI-004 (P1): Separator normalization complete via `_ESCAPE_MAP` dict (`\\n`, `\\t`, `\\r`, `\\|`).
- ENG-FFI-006 (P2): Field value `.strip()` removed; raw split value used as-is.
- ENG-FFI-007 (P2): `rows` fallback removed; engine reads `values_config` list-of-dicts directly.
- ENG-FFI-008 (P2): Intable mode no longer null-pads; emits only available data rows.

### 5.3 GlobalMap Variable Coverage

| Variable | Talend Sets? | V1 Sets? | How V1 Sets It | Notes |
| ---------- | ------------- | ---------- | ----------------- | ------- |
| `{id}_NB_LINE` | Yes | **Yes** | `_update_stats(row_count, ...)` | Fixed 2026-05-01 |
| `{id}_NB_LINE_OK` | Yes | **Yes** | `_update_stats(_, row_count, _)` | Correct |
| `{id}_NB_LINE_REJECT` | Yes (0) | **Yes** | `_update_stats(_, _, 0)` | Always 0 (correct) |
| `{id}_ERROR_MESSAGE` | Yes | **No** | -- | Not implemented (ENG-FFI-005 P3) |

---

## 6. Code Quality

### 6.1 Bugs

| ID | Priority | Location | Description |
| ---- | ---------- | ---------- | ------------- |
| -- | -- | -- | No open bugs. |

**Resolved (2026-05-01)**:

- BUG-FFI-003 (P1): `_update_stats(0, ...)` NB_LINE bug fixed.
- BUG-FFI-004 (P1): `_validate_config()` now raises `ConfigurationError` (not dead list-return).
- BUG-FFI-005 (P2): Bare `except:` clauses replaced with `except Exception:`.
- BUG-FFI-006 (P2): Negative integer coercion fixed via `re.fullmatch(r"-?\\d+", ...)`.
- BUG-FFI-007 / BUG-FFI-008 (P2): Java cast stripping and eval() completely removed.
- BUG-FFI-009 (P3): `import re` moved to module level.
- BUG-FFI-010 (P3): globalMap resolution returns raw value directly; no string manipulation.

### 6.2 Naming Consistency

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| -- | -- | No open naming issues. |

### 6.3 Standards Compliance

| ID | Priority | Standard | Status |
| ---- | ---------- | ---------- | ------- |
| STD-FFI-001 | -- | `_validate_config()` raises ConfigurationError | **Fixed** -- raises on non-int nb_rows |
| STD-FFI-002 | -- | `validate_schema()` called on output | **Handled by BaseComponent** (Rule 11) |

### 6.4 Architecture Compliance

| Rule | Status |
| ------ | ------- |
| Rule 4 (execute() not overridden) | **Pass** |
| Rule 2 (_validate_config raises, not returns) | **Pass** |
| Rule 9 (@REGISTRY.register present) | **Pass** -- both aliases registered |
| Rule 11 (validate_schema not called in `_process`) | **Pass** |
| Rule 12 (_validate_config structural only) | **Pass** -- Group B nb_rows check |

### 6.5 Security

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| SEC-FFI-002 | **P3** | Inline content row data logged at DEBUG level -- may contain sensitive data if DEBUG logging enabled. |

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
| Engine unit tests | 34 | `tests/v1/engine/components/file/test_fixed_flow_input.py` |
| Integration tests | 0 | None (covered by regression guard `test_converter_output_structure.py`) |

**Engine test classes** (34 tests, 100% pass):

| Class | Count | Focus |
| ------- | ------- | ------- |
| `TestRegistration` | 2 | Both registry aliases resolve to correct class |
| `TestNoExecuteOverride` | 1 | execute() not overridden (Rule 4) |
| `TestValidation` | 3 | string/negative nb_rows raise ConfigurationError; valid config runs |
| `TestSingleMode` | 7 | nb_rows=0/1/3; list-of-dicts format; dict fallback; missing cols; empty values_config |
| `TestIntableMode` | 5 | basic 2 rows; intable key (not intable_data); nb_rows limit; no null-padding; empty |
| `TestInlineContentMode` | 6 | basic parse; nb_rows ignored; `\\n`/`\\t`/`\\\|` normalization; empty content |
| `TestStats` | 4 | NB_LINE/NB_LINE_OK = rows_generated; NB_LINE_REJECT = 0; nb_rows=0 gives 0 |
| `TestEdgeCases` | 6 | None/df input ignored; empty schema; numeric coercion; negative int; no reject key |

### 8.2 Test Gaps

| ID | Priority | Gap |
| ---- | ---------- | ----- |
| -- | -- | No outstanding test gaps. |

---

## 9. Issues Summary

### By Priority (post-rewrite 2026-05-01)

| Priority | Count | IDs |
| ---------- | ------- | ----- |
| P0 | 0 | -- |
| P1 | 0 | -- |
| P2 | 1 | PERF-FFI-001 |
| P3 | 2 | ENG-FFI-005, SEC-FFI-002 |
| **Total** | **3** | |

### By Category

| Category | Count | IDs |
| ---------- | ------- | ----- |
| Engine (ENG) | 1 | ENG-FFI-005 |
| Performance (PERF) | 1 | PERF-FFI-001 |
| Security (SEC) | 1 | SEC-FFI-002 |

---

## 10. Recommendations

### Immediate (Before Production)

- No blocking issues. Component is production-ready for standard usage patterns.

### Short-term (Hardening)

- Add `{id}_ERROR_MESSAGE` to globalMap on ConfigurationError (P3, ENG-FFI-005)

### Long-term (Optimization)

- Vectorize `_resolve_value()` for large NB_ROWS (P2, PERF-FFI-001)

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

---

## Resolved Issues (2026-05-01 Engine Rewrite)

| ID | Was Priority | Resolution |
| ---- | ------------- | ----------- |
| ENG-FFI-001 | P0 | `_update_stats(row_count, row_count, 0)` -- NB_LINE now correct |
| BUG-FFI-003 | P1 | Same as ENG-FFI-001 |
| BUG-FFI-004 | P1 | `_validate_config()` now raises `ConfigurationError` for non-int `nb_rows` |
| SEC-FFI-001 | P1 | `eval()` removed; globalMap value returned directly; no string arithmetic |
| ENG-FFI-002 | P1 | Same as SEC-FFI-001 |
| ENG-FFI-003 | P1 | `validate_schema()` handled by BaseComponent post-`_process()` (Rule 11) |
| ENG-FFI-004 | P1 | Separator normalization: `_ESCAPE_MAP` covers `\\n`, `\\t`, `\\r`, `\\\|` |
| STD-FFI-001 | P1 | `_validate_config()` is now active and raises |
| BUG-FFI-005 | P2 | Bare `except:` replaced with `except Exception:` |
| BUG-FFI-006 | P2 | Negative int coercion fixed via `re.fullmatch(r"-?\\d+", ...)` |
| BUG-FFI-007/008 | P2 | Java cast stripping and `eval()` call completely removed |
| ENG-FFI-006 | P2 | `.strip()` on field values removed |
| ENG-FFI-007 | P2 | `rows` fallback removed; `values_config` list-of-dicts used directly |
| ENG-FFI-008 | P2 | Intable no longer null-pads beyond available data |
| TEST-FFI-001 | P2 | 34 engine unit tests added (8 classes, 100% pass) |
| BUG-FFI-009 | P3 | `import re` moved to module level |
| BUG-FFI-010 | P3 | globalMap resolution simplified; single-reference limitation not applicable |
| CONV-001 | engine_gap | `intable` key mismatch removed from needs_review (engine fixed) |
| CONV-002 | engine_gap | `rows` key needs_review removed (engine no longer uses `rows`) |
| STD-FFI-002 | P2 | BaseComponent handles `validate_schema()` automatically after `_process()` |
| NAME-FFI-001 | P2 | field_separator naming is consistent; no change required |

**Engine rewrite**: `@REGISTRY.register("FixedFlowInputComponent", "tFixedFlowInput")` added;
`_validate_config()` raises `ConfigurationError`; `_build_single_mode_rows()` / `_build_intable_rows()` /
`_build_inline_content_rows()` replace the original `_generate_*` methods; `_coerce_numeric()` module-level
helper replaces `eval()`. File: 268 lines (was 330). Tests: 34 engine + 56 converter.

*Report generated: 2026-04-03*
*Last updated: 2026-05-01 -- engine fully rewritten, all P0/P1 issues resolved*
