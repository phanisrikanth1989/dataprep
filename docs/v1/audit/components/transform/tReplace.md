# Audit Report: tReplace / (No Engine Implementation)

> **Audited**: 2026-04-04
> **Auditor**: Claude Opus 4.6 (automated) -- GOLD STANDARD NEW
> **Engine Version**: v1
> **Converter**: `talend_to_v1`
> **Status**: PRODUCTION READINESS REVIEW
> **V1 only** -- this report contains zero references to v2/PyETL

---

## 1. Component Identity

What is this component and where does everything live?

| Field | Value |
| ------- | ------- |
| **Talend Name** | `tReplace` |
| **V1 Engine Class** | None -- no concrete engine implementation exists |
| **Engine File** | No dedicated engine file |
| **Converter Parser** | `src/converters/talend_to_v1/components/transform/replace.py` (202 lines) |
| **Converter Dispatch** | `@REGISTRY.register("tReplace")` decorator-based dispatch |
| **Registry Aliases** | `tReplace` (single alias) |
| **Category** | Processing / Transform |

### Key Files

| File | Purpose |
| ------ | --------- |
| `src/converters/talend_to_v1/components/transform/replace.py` | Converter class `ReplaceConverter` (202 lines) |
| `tests/converters/talend_to_v1/components/test_replace.py` | Converter tests (30 tests, 10 classes) |
| `src/converters/talend_to_v1/components/base.py` | `ComponentConverter` base class with `_get_str()`, `_get_bool()`, `_parse_schema()`, `_build_component_dict()` |
| `src/converters/talend_to_v1/components/registry.py` | `ConverterRegistry` with decorator-based registration |

---

## 2. Scorecard

How production-ready is this component at a glance?

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
| ----------- | ------- | ---- | ---- | ---- | ---- | --------- |
| Converter Coverage | **G** | 0 | 0 | 0 | 0 | 5 unique + 2 framework params extracted (100%); SUBSTITUTIONS stride-7 TABLE; ADVANCED_SUBST stride-4 TABLE; WHOLE_WORD default fixed True; phantom CONNECTION_FORMAT removed; single consolidated needs_review |
| Engine Feature Parity | **R** | 1 | 0 | 0 | 0 | No concrete engine implementation exists; component cannot execute |
| Code Quality | **R** | 1 | 0 | 0 | 0 | Converter code quality is good (follows CONVERTER_PATTERN.md), but no engine code exists -- component is incomplete |
| Performance & Memory | **N/A** | 0 | 0 | 0 | 0 | No engine implementation to assess |
| Testing | **R** | 1 | 0 | 0 | 0 | 30 converter tests pass (10 classes per TEST_PATTERN.md), but 0 engine tests exist because engine is unimplemented |

**Overall: RED -- No engine implementation. Converter correctly extracts all 7 params (5 unique + 2 framework) with both TABLE parsers and WHOLE_WORD default fix. Engine must be implemented before this component is usable.**

**Top Actions**:

1. Implement concrete Replace engine class (P0 -- blocks production use)
2. All converter and test issues resolved in v1.1 rewrite

---

## 3. Talend Feature Baseline

What does Talend actually do? This section is the SOURCE OF TRUTH -- researched from _java.xml and official docs.

### What tReplace Does

`tReplace` performs search-and-replace operations on column values in data flows. In simple mode, it uses a SUBSTITUTIONS table to define per-column search patterns and replacement strings, with options for whole-word matching, case sensitivity, and glob-style pattern matching. Each substitution row specifies an input column, a search pattern, a replacement string, and boolean flags controlling match behavior.

In advanced mode, the component uses an ADVANCED_SUBST table whose `SEARCH_COLUMN` and `REPLACE_COLUMN` entries are misleadingly-named parameters that hold a literal regex pattern (Java string expression) and a literal replacement string respectively. Despite the legacy XML tag names, they are NOT references to other columns in the schema -- the only real column reference per rule is `INPUT_COLUMN`. The same regex is applied uniformly to every row of the input column. (See "Primary Source Verification" at the end of this report for the Talaxie source citations.) The component processes all rows in the flow, applying substitutions to each row independently.

**Source**: Talaxie GitHub tdi-studio-se repository (tReplace_java.xml)
**Component family**: Processing / Transform
**Available in**: Talend Open Studio, Talend Data Integration
**Required JARs**: None (built-in)

### 3.1 Basic Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
| --- | ----------- | ----------------- | ------ | --------- | ------------- |
| 1 | Simple Mode | `SIMPLE_MODE` | CHECK | `true` | When true, use literal search/replace patterns from SUBSTITUTIONS table |
| 2 | Substitutions | `SUBSTITUTIONS` | TABLE (stride-7) | [] | Table of substitution rules for simple mode |
| 2a | - Input Column | `INPUT_COLUMN` | str (elementRef) | -- | Column name to apply substitution to |
| 2b | - Search Pattern | `SEARCH_PATTERN` | str (elementRef) | `"default"` | Pattern to search for |
| 2c | - Replace String | `REPLACE_STRING` | str (elementRef) | `"default"` | Replacement string |
| 2d | - Whole Word | `WHOLE_WORD` | bool (elementRef) | `true` | Match whole words only. **CRITICAL: default is true per _java.xml, was incorrectly false** |
| 2e | - Case Sensitive | `CASE_SENSITIVE` | bool (elementRef) | `false` | Whether matching is case-sensitive |
| 2f | - Use Glob | `USE_GLOB` | bool (elementRef) | `false` | Whether to use glob-style patterns |
| 2g | - Comment | `COMMENT` | str (elementRef) | `""` | User comment for this substitution rule |
| 3 | Strict Match | `STRICT_MATCH` | CHECK | `true` | When true, require exact pattern match. SHOW="false" (hidden by default) |

### 3.2 Advanced Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
| --- | ----------- | ----------------- | ------ | --------- | ------------- |
| 4 | Advanced Mode | `ADVANCED_MODE` | CHECK | `false` | When true, use regex-based search/replace from ADVANCED_SUBST table (literal regex pattern + literal replacement string applied uniformly to every row of the input column) |
| 5 | Advanced Substitutions | `ADVANCED_SUBST` | TABLE (stride-4) | [] | Table of regex-based substitution rules. Despite legacy XML tag names, only `INPUT_COLUMN` is a column reference -- `SEARCH_COLUMN` and `REPLACE_COLUMN` are literal Java string expressions (regex pattern + replacement). |
| 5a | - Input Column | `INPUT_COLUMN` | str (elementRef) | -- | DataFrame column the substitution applies to (this one IS a column reference) |
| 5b | - Pattern (legacy XML tag: SEARCH_COLUMN) | `SEARCH_COLUMN` | Java string expression evaluated to a regex | `"\\w+"` | Literal regex pattern. NOT a column reference despite the tag name. |
| 5c | - Replace (legacy XML tag: REPLACE_COLUMN) | `REPLACE_COLUMN` | Java string expression for replacement string | `"default"` | Literal replacement string. NOT a column reference despite the tag name. |
| 5d | - Comment | `COMMENT` | str (elementRef) | `""` | User comment for this substitution rule |

### 3.3 Connection Types

| Connector | Direction | Type | Description |
| ----------- | ----------- | ------ | ------------- |
| `FLOW` (Main) | Input | Row > Main | Data flow to apply replacements to |
| `FLOW` (Main) | Output | Row > Main | Data with replacements applied (same schema as input) |
| `SUBJOB_OK` | Output (Trigger) | Trigger | Fires when subjob completes successfully |
| `SUBJOB_ERROR` | Output (Trigger) | Trigger | Fires when subjob encounters an error |

### 3.4 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
| ------------------ | ------ | ---------- | ------------- |
| N/A | -- | -- | No globalMap variables documented for tReplace |

### 3.5 Behavioral Notes

1. **WHOLE_WORD default is true** per _java.xml -- the previous converter incorrectly defaulted to false, causing broader matches than intended
2. **STRICT_MATCH is hidden by default** (SHOW="false") -- rarely changed by users but defaults to true
3. **SIMPLE_MODE and ADVANCED_MODE** are independent booleans, not a RADIO group -- both can theoretically be true
4. **SUBSTITUTIONS stride-7** requires all 7 elementRef entries per row (INPUT_COLUMN, SEARCH_PATTERN, REPLACE_STRING, WHOLE_WORD, CASE_SENSITIVE, USE_GLOB, COMMENT)
5. **ADVANCED_SUBST stride-4** requires all 4 elementRef entries per row (INPUT_COLUMN, SEARCH_COLUMN, REPLACE_COLUMN, COMMENT)
6. **Phantom param removed**: CONNECTION_FORMAT was extracted by old converter but does not exist in _java.xml -- it was phantom

---

## 4. Converter Audit

How faithfully does the converter translate Talend XML to v1 JSON?

### 4.1 Parameter Extraction

The converter uses `@REGISTRY.register("tReplace")` decorator for dispatch and the `ReplaceConverter` class inheriting from `ComponentConverter`. It extracts 5 unique params plus 2 framework params using base class helpers. Two module-level TABLE parser functions (`_parse_substitutions` for stride-7, `_parse_advanced_subst` for stride-4) handle the TABLE parameters. Uses `_build_component_dict` with `type_name="tReplace"` per D-43 no-engine pattern.

| # | Talend XML Parameter | Extracted? | V1 Config Key | Notes |
| ---- | ---------------------- | ------------ | --------------- | ------- |
| 1 | `SIMPLE_MODE` | Yes | `simple_mode` | `_get_bool(node, "SIMPLE_MODE", True)` |
| 2 | `SUBSTITUTIONS` | Yes | `substitutions` | Stride-7 TABLE via `_parse_substitutions()`. WHOLE_WORD default True (CRITICAL FIX). |
| 3 | `STRICT_MATCH` | Yes | `strict_match` | `_get_bool(node, "STRICT_MATCH", True)`. Hidden param (SHOW=false). |
| 4 | `ADVANCED_MODE` | Yes | `advanced_mode` | `_get_bool(node, "ADVANCED_MODE", False)` |
| 5 | `ADVANCED_SUBST` | Yes | `advanced_subst` | Stride-4 TABLE via `_parse_advanced_subst()` |
| 6 | `TSTATCATCHER_STATS` | Yes | `tstatcatcher_stats` | Framework param, default False |
| 7 | `LABEL` | Yes | `label` | Framework param, default "" |
| -- | ~~`CONNECTION_FORMAT`~~ | **REMOVED** | -- | **Phantom param** -- not in _java.xml. Was extracted by old converter. |

**Summary**: 7 of 7 parameters extracted (100%). 1 phantom param removed.

### 4.2 Schema Extraction

| Schema Attribute | Extracted? | Notes |
| ------------------ | ----------- | ------- |
| `name` | Yes | Via `_parse_schema()` from FLOW connector |
| `type` | Yes | Via `convert_type()` for Talend-to-Python type mapping |
| `nullable` | Yes | From SchemaColumn |
| `key` | Yes | From SchemaColumn |
| `length` | Yes | When >= 0 |
| `precision` | Yes | When >= 0 |
| `pattern` | Yes | Java-to-Python date pattern conversion |
| `default` | No | Not extracted by base class `_parse_schema()` |

**Schema pattern**: Transform passthrough -- input and output schema are identical (replacements don't change column structure).

### 4.3 Expression Handling

The converter passes through string values as-is. Context variable references (`context.var`) and Java expressions within SUBSTITUTIONS TABLE values would be preserved in their original form for downstream resolution by the engine.

### 4.4 Converter Issues

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| -- | -- | No open converter issues. All resolved in v1.1 gold standard rewrite. |

### 4.5 Needs Review Entries

| # | Config Key | Reason | Severity |
| --- | ----------- | -------- | ---------- |
| 1 | (all) | No v1 engine implementation for tReplace -- single consolidated entry per D-27 | engine_gap |

---

## 5. Engine Feature Parity

How faithfully does the v1 engine implement Talend behavior?

### 5.1 Feature Implementation Status

| # | Talend Feature | Implemented? | Fidelity | Engine Location | Notes |
| ---- | ---------------- | ------------- | ---------- | ----------------- | ------- |
| 1 | Simple mode search-and-replace | **No** | N/A | No engine file | No engine implementation exists |
| 2 | Advanced mode regex-based replace (literal pattern applied uniformly to every row of the input column) | **No** | N/A | No engine file | No engine implementation exists |
| 3 | Whole word matching | **No** | N/A | No engine file | No engine implementation exists |
| 4 | Case sensitivity control | **No** | N/A | No engine file | No engine implementation exists |
| 5 | Glob pattern matching | **No** | N/A | No engine file | No engine implementation exists |

### 5.2 Behavioral Differences from Talend

| ID | Priority | Description |
| ---- | ---------- | ------------- |
| ENG-REP-001 | **P0** | No concrete engine implementation exists. tReplace cannot execute in v1 engine. |

### 5.3 GlobalMap Variable Coverage

| Variable | Talend Sets? | V1 Sets? | How V1 Sets It | Notes |
| ---------- | ------------- | ---------- | ----------------- | ------- |
| N/A | -- | -- | -- | No globalMap variables for tReplace; no engine exists |

---

## 6. Code Quality

How well-written is the engine code?

### 6.1 Bugs

| ID | Priority | Location | Description |
| ---- | ---------- | ---------- | ------------- |
| BUG-REP-001 | **P0** | No engine file | No engine code exists -- component is non-functional |

### 6.2 Naming Consistency

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| -- | -- | Converter follows snake_case convention for all config keys. No naming issues. |

### 6.3 Standards Compliance

| ID | Priority | Standard | Violation |
| ---- | ---------- | ---------- | ----------- |
| -- | -- | -- | Converter follows CONVERTER_PATTERN.md gold standard. No violations. |

### 6.4 Debug Artifacts

None found. Converter code is clean with no print statements, TODO comments, or debug artifacts.

### 6.5 Security

No concerns identified. The converter performs data extraction only and does not execute code or access external resources.

### 6.6 Logging Quality

| Aspect | Assessment |
| -------- | ------------ |
| Logger setup | Module-level `logger = logging.getLogger(__name__)` present |
| Level usage | N/A -- no engine code to assess |
| Sensitive data | No sensitive data exposure in converter |

### 6.7 Error Handling Quality

| Aspect | Assessment |
| -------- | ------------ |
| Custom exceptions | N/A -- no engine code; converter returns ComponentResult |
| Exception chaining | N/A -- no engine code |
| die_on_error handling | N/A -- no engine code |

### 6.8 Type Hints

| Aspect | Assessment |
| -------- | ------------ |
| Method signatures | Full type hints on convert(), parser functions, all parameters |
| Parameter types | `Dict[str, Any]`, `List[Dict[str, Any]]` throughout |

---

## 7. Performance & Memory

Will it scale?

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| -- | -- | No engine implementation to assess |

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
| Converter unit tests | 30 | `tests/converters/talend_to_v1/components/test_replace.py` |
| Engine unit tests | 0 | None -- no engine implementation |
| Integration tests | 0 | None -- no engine implementation |

### 8.2 Test Gaps

| ID | Priority | Gap |
| ---- | ---------- | ----- |
| TEST-REP-001 | **P0** | No engine unit tests -- engine is unimplemented |

### 8.3 Recommended Test Cases

When engine is implemented:

- Happy path: simple mode with single substitution
- Multiple substitutions on same column
- Whole word vs partial matching
- Case sensitivity on/off
- Glob pattern matching
- Advanced mode with regex-based replacement (literal pattern applied uniformly per input column)
- Empty substitutions table (no-op passthrough)
- Mixed simple + advanced mode
- Null/empty values in target columns
- Large datasets for performance validation

**Converter tests are comprehensive**: 30 tests across 10 test classes covering Registration, Defaults, SubstitutionsTable (stride-7 with all field defaults), AdvancedSubstTable (stride-4), ParameterExtraction, FrameworkParams, Schema, NeedsReview, PhantomParams (CONNECTION_FORMAT), Completeness, and ComponentStructure.

---

## 9. Issues Summary

All issues grouped by priority for sprint planning.

### By Priority

| Priority | Count | IDs |
| ---------- | ------- | ----- |
| P0 | 1 | **ENG-REP-001** (no engine) |
| P1 | 0 | -- |
| P2 | 0 | -- |
| P3 | 0 | -- |
| **Total** | **1** | |

### By Category

| Category | Count | IDs |
| ---------- | ------- | ----- |
| Converter (CONV) | 0 | -- |
| Engine (ENG) | 1 | ENG-REP-001 |
| Bug (BUG) | 0 | -- |
| Naming (NAME) | 0 | -- |
| Standards (STD) | 0 | -- |
| Performance (PERF) | 0 | -- |
| Testing (TEST) | 0 | -- |

### Cross-Cutting Issues

No cross-cutting issues apply -- no engine code exists to be affected by base class bugs.

---

## 10. Recommendations

What should be fixed, in what order?

### Immediate (Before Production)

1. **ENG-REP-001**: Implement concrete Replace engine class supporting simple mode search-and-replace with whole word, case sensitivity, and glob matching
2. Add engine unit tests once implementation exists

### Short-term (Hardening)

1. Implement advanced mode (regex-based search/replace -- literal pattern + replacement string applied uniformly to every row of the input column)
2. Add integration tests with realistic data flows

### Long-term (Optimization)

1. Optimize for large datasets with vectorized pandas string operations
2. Consider regex compilation caching for repeated patterns

---

## 11. Primary Source Verification

The advanced-mode behavior was verified against the upstream Talend (Talaxie) source on 2026-04-29:

- **`tReplace_java.xml`** declares the parameters with `FIELD="String"` (literal text input), not `FIELD="PREV_COLUMN_LIST"` (which is what the actual column-reference parameter `INPUT_COLUMN` uses):

  ```xml
  <ITEM NAME="SEARCH_COLUMN"  FIELD="String" VALUE="&quot;\\w+&quot;" />
  <ITEM NAME="REPLACE_COLUMN" FIELD="String" VALUE="&quot;default&quot;" />
  ```

  Source: https://github.com/Talaxie/tdi-studio-se/blob/master/main/plugins/org.talend.designer.components.localprovider/components/tReplace/tReplace_java.xml

- **`tReplace_messages.properties`** confirms the user-facing labels:

  - `ADVANCED_MODE.NAME=Advanced mode ( search with regexp pattern )`
  - `ADVANCED_SUBST.NAME=Regexp patterns`
  - `ADVANCED_SUBST.ITEM.SEARCH_COLUMN=Pattern`
  - `ADVANCED_SUBST.ITEM.REPLACE_COLUMN=Replace`

- **`tReplace_main.javajet`** generates Java that uses these as bareword string expressions, not as `row.*` accessors:

  ```java
  row.${INPUT_COLUMN} = StringUtils.replaceAll(row.${INPUT_COLUMN}, ${SEARCH_COLUMN}, ${REPLACE_COLUMN});
  ```

  The user-supplied `"\\w+"` lands in the generated Java as the literal string `"\\w+"` (which Java unescapes to the regex `\w+`).

Conclusion: the SEARCH_COLUMN / REPLACE_COLUMN tag names are a Talend naming artifact. They are regex pattern + replacement string, not column references. The engine implementation in `src/v1/engine/components/transform/replace.py::_apply_advanced_mode` matches this contract.

---

## Appendix A: Source References

| Source | URL/Path | Used For |
| -------- | ---------- | ---------- |
| Talaxie GitHub _java.xml | `<https://github.com/nicogbg/talaxie/blob/master/main/plugins/org.talend.designer.components.localprovider/components/tReplace/tReplace_java.xml`> | Parameter definitions, defaults, TABLE structures |
| Converter source | `src/converters/talend_to_v1/components/transform/replace.py` | Converter audit (202 lines) |
| Test source | `tests/converters/talend_to_v1/components/test_replace.py` | Test coverage analysis (30 tests) |
| Base class | `src/converters/talend_to_v1/components/base.py` | Helper methods, _build_component_dict |

## Appendix B: Converter Config Key Mapping

| # | Talend XML Name | Config Key | Type | Default | Parser |
| --- | ----------------- | ----------- | ------ | --------- | -------- |
| 1 | `SIMPLE_MODE` | `simple_mode` | bool | `True` | `_get_bool()` |
| 2 | `SUBSTITUTIONS` | `substitutions` | list[dict] | `[]` | `_parse_substitutions()` stride-7 |
| 2a | `INPUT_COLUMN` | `input_column` | str | -- | elementRef |
| 2b | `SEARCH_PATTERN` | `search_pattern` | str | `"default"` | elementRef, strip quotes |
| 2c | `REPLACE_STRING` | `replace_string` | str | `"default"` | elementRef, strip quotes |
| 2d | `WHOLE_WORD` | `whole_word` | bool | `True` | elementRef (**CRITICAL FIX: was False**) |
| 2e | `CASE_SENSITIVE` | `case_sensitive` | bool | `False` | elementRef |
| 2f | `USE_GLOB` | `use_glob` | bool | `False` | elementRef |
| 2g | `COMMENT` | `comment` | str | `""` | elementRef |
| 3 | `STRICT_MATCH` | `strict_match` | bool | `True` | `_get_bool()` |
| 4 | `ADVANCED_MODE` | `advanced_mode` | bool | `False` | `_get_bool()` |
| 5 | `ADVANCED_SUBST` | `advanced_subst` | list[dict] | `[]` | `_parse_advanced_subst()` stride-4 |
| 5a | `INPUT_COLUMN` | `input_column` | str (column ref) | -- | elementRef -- DataFrame column reference |
| 5b | `SEARCH_COLUMN` | `search_column` | str (literal regex pattern, NOT a column ref) | `"\\w+"` | elementRef -- Java string expression. Talaxie XML defines `FIELD="String"`. |
| 5c | `REPLACE_COLUMN` | `replace_column` | str (literal replacement string, NOT a column ref) | `"default"` | elementRef -- Java string expression. Talaxie XML defines `FIELD="String"`. |
| 5d | `COMMENT` | `comment` | str | `""` | elementRef |
| 6 | `TSTATCATCHER_STATS` | `tstatcatcher_stats` | bool | `False` | `_get_bool()` |
| 7 | `LABEL` | `label` | str | `""` | `_get_str()` |

---

*Report generated: 2026-04-04*
*Last updated: 2026-04-04 after v1.1 gold standard new creation*
