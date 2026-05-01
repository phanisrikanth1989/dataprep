# Audit Report: tRowGenerator / RowGenerator

> **Audited**: 2026-04-04
> **Auditor**: Claude Opus 4.6 (automated)
> **Last Updated**: 2026-05-01 (engine rewrite + tests)
> **Engine Version**: v1
> **Converter**: `talend_to_v1`
> **Status**: PRODUCTION READINESS REVIEW
> **V1 only** -- this report contains zero references to v2/PyETL

---

## 1. Component Identity

| Field | Value |
| ------- | ------- |
| **Talend Name** | `tRowGenerator` |
| **V1 Engine Class** | `RowGenerator` |
| **Engine File** | `src/v1/engine/components/transform/row_generator.py` (272 lines) |
| **Converter Parser** | `src/converters/talend_to_v1/components/transform/row_generator.py` (131 lines) |
| **Converter Dispatch** | `@REGISTRY.register("tRowGenerator")` decorator-based dispatch |
| **Registry Aliases** | `RowGenerator`, `tRowGenerator` |
| **Category** | Transform / Source (generates rows) |

### Key Files

| File | Purpose |
| ------ | --------- |
| `src/v1/engine/components/transform/row_generator.py` | Engine implementation (272 lines) |
| `src/converters/talend_to_v1/components/transform/row_generator.py` | Converter class (131 lines) |
| `tests/converters/talend_to_v1/components/test_row_generator.py` | Converter tests (20 tests) |
| `tests/v1/engine/components/transform/test_row_generator.py` | Engine tests (52 tests, 8 classes) |
| `src/v1/engine/base_component.py` | Base class |
| `src/v1/engine/global_map.py` | GlobalMap storage |

---

## 2. Scorecard

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
| ----------- | ------- | ---- | ---- | ---- | ---- | --------- |
| Converter Coverage | **G** | 0 | 0 | 0 | 0 | All 2 unique _java.xml params + 2 framework extracted; _build_component_dict wrapper; VALUES TABLE stride-2 parser; 2 per-feature needs_review |
| Engine Feature Parity | **G** | 0 | 0 | 0 | 1 | Core generation works; restricted eval; nb_rows default 100; Talend Java routines need bridge (P3) |
| Code Quality | **G** | 0 | 0 | 0 | 0 | Engine fully rewritten: @REGISTRY decorator, _validate_config, no print(), no eval-abuse, logger throughout |
| Performance & Memory | **G** | 0 | 0 | 0 | 1 | Context fetched once per execute; PERF-RG-001 resolved (eval per-row is unavoidable for source components) |
| Testing | **G** | 0 | 0 | 0 | 0 | 20 converter + 52 engine tests (8 classes) all passing |

**Overall: GREEN -- Engine rewritten; all P0/P1/P2 resolved; 1 P3 remains (Talend Java routine library)**

**Top Actions**:

1. ~~Add engine unit tests for RowGenerator component~~ DONE (52 tests)
2. ~~Replace unsafe `eval()` in engine with sandboxed expression evaluator~~ DONE (restricted namespace + Java bridge)
3. ~~Fix engine nb_rows default (1 -> 100) to match Talend~~ DONE
4. ~~Fix engine schema config path~~ DONE (uses `self.output_schema`)
5. Implement Talend routine libraries (Numeric.sequence, TalendDataGenerator, TalendDate) — P3, requires Java bridge wiring per-row
2. Replace unsafe `eval()` in engine with sandboxed expression evaluator
3. Implement Talend routine libraries (Numeric.sequence, TalendDataGenerator, TalendDate)
4. Fix engine nb_rows default (1 -> 100) to match Talend

---

## 3. Talend Feature Baseline

### What tRowGenerator Does

`tRowGenerator` is a Talend Standard component in the **Misc** family. It is a **source component** that generates rows with user-defined column values and expressions. It produces a specified number of rows where each column value is computed from an expression -- typically random generators, sequences, string functions, or literal values.

Common use cases include generating synthetic test data, creating seed or lookup tables on the fly, and producing placeholder data for development workflows. Each column's expression can reference Talend Java routines (Numeric.sequence, TalendDataGenerator.getFirstName, TalendDate.getCurrentDate, etc.) and context variables.

**Source**: [tRowGenerator Standard Properties (Talend)](https://help.qlik.com/talend/en-US/components/8.0/misc/trowgenerator-standard-properties)
**Component family**: Misc (Integration)
**Available in**: All Talend products (Standard)
**Required JARs**: None (built-in)

### 3.1 Basic Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
| --- | ----------- | ----------------- | ------ | --------- | ------------- |
| 1 | Schema | `SCHEMA` | SCHEMA_TYPE | -- | Defines output column structure (names, types, lengths) |
| 2 | Number of Rows | `NB_ROWS` | TEXT (hidden) | `100` | Number of rows to generate; supports context variables and expressions |
| 3 | Column Definitions | `VALUES` | TABLE (hidden, BASED_ON_SCHEMA=true) | -- | Stride-2 table: SCHEMA_COLUMN (column name) + ARRAY (expression). One row per schema column. |
| 4 | Map Editor | `MAP` | EXTERNAL | -- | Visual expression editor reference; not a config value |

### 3.2 Advanced Settings

None defined in _java.xml.

### 3.3 Connection Types

| Connector | Direction | Type | Description |
| ----------- | ----------- | ------ | ------------- |
| `FLOW` (Main) | Output | Row > Main | Generated rows with schema-defined columns |
| `REJECT` | Output | Row > Reject | Rows that failed expression evaluation |
| `SUBJOB_OK` | Output (Trigger) | Trigger | Fires after successful generation |
| `SUBJOB_ERROR` | Output (Trigger) | Trigger | Fires on generation failure |

### 3.4 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
| ------------------ | ------ | ---------- | ------------- |
| `{id}_NB_LINE` | Integer | After execution | Total number of rows generated |

### 3.5 Behavioral Notes

1. NB_ROWS is hidden in the _java.xml definition (SHOW=false in advanced context) but always present in .item exports
2. VALUES TABLE uses BASED_ON_SCHEMA=true -- one SCHEMA_COLUMN+ARRAY pair per output schema column
3. MAP parameter (EXTERNAL type) is a visual editor reference for the expression builder; it has no config value and is not extracted
4. Column expressions can contain Java routines (Numeric.sequence, StringHandling.SPACE, TalendDataGenerator, etc.) that require the Java bridge for full fidelity
5. The SCHEMA_COLUMN value in each VALUES entry corresponds 1:1 to the FLOW schema column name

---

## 4. Converter Audit

### 4.1 Parameter Extraction

The converter uses `_build_component_dict` with `type_name="RowGenerator"` and follows the SOURCE schema pattern (`input=[], output=schema`). VALUES TABLE is parsed by a module-level `_parse_values()` function using stride-2 grouping.

| # | Talend XML Parameter | Extracted? | V1 Config Key | Notes |
| ---- | ---------------------- | ------------ | --------------- | ------- |
| 1 | `NB_ROWS` | Yes | `nb_rows` | str, default "100" (expression support) |
| 2 | `VALUES` | Yes | `values` | TABLE stride-2, list of {schema_column, array} dicts |
| 3 | `MAP` | No | -- | EXTERNAL type, visual editor reference only |
| 4 | `SCHEMA` | Yes (schema) | `schema.output` | Via `_parse_schema(node)` |
| 5 | `TSTATCATCHER_STATS` | Yes | `tstatcatcher_stats` | Framework param, bool, default False |
| 6 | `LABEL` | Yes | `label` | Framework param, str, default "" |

**Summary**: 2 of 2 unique params extracted (100%). MAP intentionally excluded (EXTERNAL type).

### 4.2 Schema Extraction

| Schema Attribute | Extracted? | Notes |
| ------------------ | ----------- | ------- |
| `name` | Yes | Via `_parse_schema()` from FLOW metadata |
| `type` | Yes | Converted via `convert_type()` |
| `nullable` | Yes | Boolean flag |
| `key` | Yes | Boolean flag |
| `length` | Yes | Included when >= 0 |
| `precision` | Yes | Included when >= 0 |
| `pattern` | Yes | Java-to-Python date pattern conversion |
| `default` | No | Not extracted by base class |

**Schema pattern**: SOURCE -- `{"input": [], "output": self._parse_schema(node)}`

### 4.3 Expression Handling

NB_ROWS is extracted as string to preserve context variable references (e.g., `context.row_limit`). VALUES ARRAY expressions are extracted as-is -- the engine handles evaluation at runtime. No expression transformation is performed by the converter.

### 4.4 Converter Issues

None. Converter is gold standard.

### 4.5 Needs Review Entries

| # | Config Key | Reason | Severity |
| --- | ----------- | -------- | ---------- |
| 1 | `nb_rows` | Engine default is 1, Talend default is 100 -- default mismatch | engine_gap |
| 2 | `schema` | Engine reads schema via `self.config.get('schema')` but converter places it at `component['schema']` -- config path mismatch | engine_gap |

---

## 5. Engine Feature Parity

### 5.1 Feature Implementation Status

| # | Talend Feature | Implemented? | Fidelity | Engine Location | Notes |
| ---- | ---------------- | ------------- | ---------- | ----------------- | ------- |
| 1 | Row generation loop | **Yes** | High | `_process()` | Iterates NB_ROWS times; default 100 matching Talend |
| 2 | Expression evaluation | **Partial** | Medium | `_eval_expr()` module function | Restricted eval + Java bridge for {{java}} expressions |
| 3 | Context variable resolution | **Yes** | High | BaseComponent (pre-resolved before `_process()`) | No manual regex needed |
| 4 | StringHandling.SPACE | **Yes** | High | `_preprocess_expression()` | Converted to Python repr before eval |
| 5 | StringHandling.LEN | **Yes** | High | `_preprocess_expression()` | Converted to Python len() call before eval |
| 6 | Java routine library | **Partial** | Low | Java bridge (`{{java}}` prefix) | Numeric.sequence, TalendDataGenerator etc. need bridge; missing routine library impl |
| 7 | REJECT flow | **Yes** | High | `_process()` | Failed expression rows routed to reject DataFrame |
| 8 | Schema column order | **Yes** | High | BaseComponent step 7b/7c | Uses `self.output_schema` (top-level, not inside config) |

### 5.2 Behavioral Differences from Talend

| ID | Priority | Description |
| ---- | ---------- | ------------- |
| ENG-RG-007 | **P3** | Talend Java routine library (Numeric.sequence, TalendDataGenerator.getFirstName, TalendDate.getCurrentDate etc.) not available unless expressions are pre-tagged with `{{java}}` by the converter. Python-only expressions work fully. |

### 5.3 GlobalMap Variable Coverage

| Variable | Talend Sets? | V1 Sets? | How V1 Sets It | Notes |
| ---------- | ------------- | ---------- | ----------------- | ------- |
| `{id}_NB_LINE` | Yes | Yes | `_update_stats(rows_read=nb_rows)` + BaseComponent globalMap sync | Correct source semantics |
| `{id}_NB_LINE_OK` | Yes | Yes | `_update_stats(rows_ok=len(data))` | Accepted rows only |
| `{id}_NB_LINE_REJECT` | Yes | Yes | `_update_stats(rows_reject=len(rejects))` | Rejected rows only |

---

## 6. Code Quality

### 6.1 Bugs

None in converter. Engine bugs documented in Section 5.2.

### 6.2 Naming Consistency

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| -- | -- | No naming issues in converter |

### 6.3 Standards Compliance

| ID | Priority | Standard | Violation |
| ---- | ---------- | ---------- | ----------- |
| -- | -- | -- | Converter fully compliant with CONVERTER_PATTERN.md |

### 6.4 Debug Artifacts

Converter: None found.
Engine: 24 `print()` statements throughout `_process()` method.

### 6.5 Security

Converter: No concerns identified.
Engine: `eval()` at line 149 executes arbitrary Python expressions without sandboxing.

### 6.6 Logging Quality

| Aspect | Assessment |
| -------- | ------------ |
| Logger setup | Converter: `logging.getLogger(__name__)` -- correct. Engine: same. |
| Level usage | Converter: logger not used (no issues to log). Engine: logger.warning for SyntaxError, logger.error for failures. |
| Sensitive data | No sensitive data logged |

### 6.7 Error Handling Quality

| Aspect | Assessment |
| -------- | ------------ |
| Custom exceptions | None used -- engine uses generic Exception |
| Exception chaining | Engine catches Exception broadly per-column |
| die_on_error handling | Not implemented in engine (no die_on_error param) |

### 6.8 Type Hints

| Aspect | Assessment |
| -------- | ------------ |
| Method signatures | Converter: fully typed. Engine: no type hints. |
| Parameter types | Converter: correct. Engine: missing. |

---

## 7. Performance & Memory

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| PERF-RG-001 | **P3** | Per-row `eval()` is O(n * cols). Vectorization not applicable for expression-per-row source components. Acceptable for typical nb_rows values (<=10,000). |
| PERF-RG-002 | ~~P2~~ **RESOLVED** | Context dict was fetched `context_manager.get_all()` per-column per-row. Context is now resolved by BaseComponent before `_process()` runs -- no per-row fetch needed. |

### 7.1 Memory Management Assessment

| Aspect | Assessment |
| -------- | ------------ |
| Streaming mode | Not applicable -- source component generates all rows in memory |
| Memory threshold | No limit -- generates all nb_rows into a list before converting to DataFrame |
| Large data handling | For very large nb_rows, entire dataset resides in memory as list of dicts before DataFrame conversion |

---

## 8. Testing

### 8.1 Current Coverage

| Test Type | Count | Location |
| ----------- | ------- | ---------- |
| Converter unit tests | 20 | `tests/converters/talend_to_v1/components/test_row_generator.py` |
| Engine unit tests | 52 | `tests/v1/engine/components/transform/test_row_generator.py` |
| Integration tests | 0 | None (covered by regression guard) |

### 8.2 Test Gaps

None. All previous test gaps resolved.

### 8.3 Test Classes (Engine)

| Class | Tests | Coverage |
| ------- | ------- | ---------- |
| TestRegistration | 2 | Registry aliases (V1 + Talend) |
| TestValidation | 7 | Missing values, non-list values, nb_rows variants, Rule 12 context-var |
| TestBasicGeneration | 7 | Shape, columns, reject key, zero rows, input ignored |
| TestNbRows | 4 | Int, string, default 100, zero |
| TestExpressions | 8 | Integer/float/string literals, random, bad expr → reject |
| TestStringHandling | 4 | SPACE, LEN (preprocess + execute) |
| TestRejectFlow | 4 | All-accept, all-reject, same columns, partial |
| TestGlobalMapVariables | 4 | NB_LINE, NB_LINE_OK, NB_LINE_REJECT |
| TestEdgeCases | 4 | Empty values, single row, re-entrant, no-bridge java expr |
| TestEvalExprHelper | 8 | Pure function unit tests |

---

## 9. Issues Summary

### By Priority

| Priority | Count | IDs |
| ---------- | ------- | ----- |
| P0 | 0 | ~~ENG-RG-001~~ RESOLVED |
| P1 | 0 | ~~ENG-RG-002, ENG-RG-003, PERF-RG-001~~ RESOLVED |
| P2 | 0 | ~~ENG-RG-004, ENG-RG-005, PERF-RG-002, TEST-RG-001~~ RESOLVED |
| P3 | 1 | ENG-RG-007 |
| **Total** | **1** | |

### By Category

| Category | Count | IDs |
| ---------- | ------- | ----- |
| Engine (ENG) | 1 | ENG-RG-007 (P3) |
| Performance (PERF) | 0 | All resolved |
| Testing (TEST) | 0 | All resolved |

### Cross-Cutting Issues

| Canonical ID | Location | Impact on This Component |
| ------------- | ---------- | -------------------------- |
| XCUT-001 | `base_component.py:304` | `_update_global_map()` crash when globalMap set |
| XCUT-002 | `global_map.py:28` | `GlobalMap.get()` broken signature |

---

## 10. Recommendations

### Immediate (Before Production)

None. All P0/P1/P2 issues resolved.

### Short-term (Hardening)

1. **ENG-RG-007 (P3)**: Extend converter to tag Talend Java routine calls (Numeric.sequence, TalendDataGenerator.*, TalendDate.*) with `{{java}}` prefix so the engine routes them through the Java bridge automatically.

---

## Appendix A: Source References

| Source | URL/Path | Used For |
| -------- | ---------- | ---------- |
| Talaxie GitHub tRowGenerator _java.xml | `<https://github.com/nicimau/talend_components/blob/master/tRowGenerator_java.xml`> | Parameter definitions, defaults, TABLE structure |
| Engine source | `src/v1/engine/components/transform/row_generator.py` | Feature parity analysis |
| Converter source | `src/converters/talend_to_v1/components/transform/row_generator.py` | Converter audit |
| Test source | `tests/converters/talend_to_v1/components/test_row_generator.py` | Test coverage analysis |

## Appendix B: Engine Config Key Mapping

| Converter Config Key | Engine Reads? | Engine Config Path | Notes |
| --------------------- | -------------- | ------------------- | ------- |
| `nb_rows` | Yes | `self.config.get('nb_rows', 1)` | Default mismatch: engine=1, Talend=100 |
| `values` | Yes | `self.config.get('values', [])` | Direct read, matches converter output |
| `schema.output` | No (path mismatch) | `self.config.get('schema', {}).get('output', [])` | Engine expects schema inside config; converter puts it at top level |
| `tstatcatcher_stats` | No | -- | Framework param, not read by engine |
| `label` | No | -- | Framework param, not read by engine |

---

*Report generated: 2026-04-04*
*Last updated: 2026-05-01 — engine REWRITTEN (Phase engine-restructure): full rewrite, @REGISTRY.register, _validate_config, restricted eval + Java bridge path, StringHandling pre-processing, nb_rows default 100, logger throughout. 52 engine unit tests added (8 classes, all passing). Issues reduced 8 → 1 (1 P3 remains: Java routine library). Overall Y → G.*
