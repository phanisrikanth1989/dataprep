# Audit Report: tExtractRegexFields / ExtractRegexFields

> **Audited**: 2026-04-04
> **Last Updated**: 2026-04-05 (engine implementation created)
> **Reconciled**: 2026-05-11
> **Auditor**: Claude Sonnet 4.6 (automated)
> **Engine Version**: v1
> **Converter**: `talend_to_v1`
> **Status**: GREEN -- ENGINE IMPLEMENTATION COMPLETE
> **V1 only** -- this report covers the v1 engine exclusively

---

## 1. Component Identity

What is this component and where does everything live?

| Field | Value |
| ------- | ------- |
| **Talend Name** | `tExtractRegexFields` |
| **V1 Engine Class** | `ExtractRegexFields` |
| **Engine File** | `src/v1/engine/components/transform/extract_regex_fields.py` |
| **Converter Parser** | `src/converters/talend_to_v1/components/transform/extract_regex_fields.py` (80 lines) |
| **Converter Dispatch** | `@REGISTRY.register("tExtractRegexFields")` decorator-based dispatch |
| **Registry Aliases** | `ExtractRegexFields`, `tExtractRegexFields` |
| **Category** | Transform / Field Extraction |

### Key Files

| File | Purpose |
| ------ | --------- |
| `src/converters/talend_to_v1/components/transform/extract_regex_fields.py` | Converter class `ExtractRegexFieldsConverter` (80 lines) |
| `tests/converters/talend_to_v1/components/test_extract_regex_fields.py` | Converter tests (24 tests, 10 classes) |
| `src/converters/talend_to_v1/components/base.py` | `ComponentConverter` base class with `_get_str()`, `_get_bool()`, `_parse_schema()`, `_build_component_dict()` |
| `src/converters/talend_to_v1/components/registry.py` | `ConverterRegistry` with decorator-based registration |

---

## 2. Scorecard

How production-ready is this component at a glance?

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
| ----------- | ------- | ---- | ---- | ---- | ---- | --------- |
| Converter Coverage | **G** | 0 | 0 | 0 | 0 | 4 of 4 _java.xml unique params extracted (100%); phantom GROUP removed; FIELD and CHECK_FIELDS_NUM added; DIE_ON_ERROR default fixed to True; module docstring follows CONVERTER_PATTERN.md |
| Engine Feature Parity | **G** | 0 | 0 | 1 | 0 | New engine implementation: FIELD, REGEX, REJECT (NULL_SOURCE/NO_MATCH/FIELD_COUNT_MISMATCH), position-based group mapping |
| Code Quality | **G** | 0 | 0 | 0 | 0 | All 12 BaseComponent rules followed; %-style logging; no mutable state; proper null handling via pd.isna() |
| Performance & Memory | **Y** | 0 | 0 | 1 | 0 | iterrows() retained; no streaming |
| Testing | **G** | 0 | 0 | 0 | 0 | 24 converter tests + new engine unit test suite (TestRegistry/Validate/Empty/Main/Reject/Stats) |

**Overall: GREEN -- Engine implementation complete; all features implemented; production ready**

**Remaining items**:

1. Vectorized regex matching (P2 -- optimization for large datasets)

---

## 3. Talend Feature Baseline

What does Talend actually do? This section is the SOURCE OF TRUTH -- researched from _java.xml and official docs.

### What tExtractRegexFields Does

`tExtractRegexFields` extracts fields from a single input column by applying a regular expression with capture groups. Each capture group in the regex maps to a corresponding output column in the schema. The component reads from the specified source column (FIELD), applies the REGEX pattern, and populates output columns with the matched capture group values.

This is the regex counterpart of `tExtractDelimitedFields` (which splits by delimiter) and `tExtractPositionalFields` (which splits by fixed positions). All three share the same architectural pattern: select a source column, define an extraction rule, and populate schema-defined output columns with the extracted values.

**Source**: Talaxie GitHub tdi-studio-se repository (tExtractRegexFields_java.xml)
**Component family**: Processing / Field Extraction
**Available in**: All Talend product variants (Open Studio, Enterprise)
**Required JARs**: None (built-in)

### 3.1 Basic Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
| --- | ----------- | ----------------- | ------ | --------- | ------------- |
| 1 | Field | `FIELD` | PREV_COLUMN_LIST | (none) | Source column to apply the regex to. PREV_COLUMN_LIST type means it shows a dropdown of columns from the previous component's output schema. |
| 2 | Regex Help | `REGEX_HELP` | LABEL | (informational) | Display-only label showing regex syntax help in the UI. Not a configuration parameter -- not extracted. |
| 3 | Regex | `REGEX` | MEMO | (complex default) | Regular expression pattern with capture groups. MEMO type allows multi-line input. Each capture group maps to a schema output column. |
| 4 | Schema | `SCHEMA` | SCHEMA_TYPE | -- | Output schema definition |
| 5 | Reject Schema | `SCHEMA_REJECT` | SCHEMA_TYPE | -- | Schema for rejected rows (rows that don't match the regex) |

### 3.2 Advanced Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
| --- | ----------- | ----------------- | ------ | --------- | ------------- |
| 6 | Die on Error | `DIE_ON_ERROR` | CHECK | `true` | Whether to abort the job on extraction error. Default is `true` per _java.xml (not `false` as the old converter had). |
| 7 | Check Fields Num | `CHECK_FIELDS_NUM` | CHECK | `false` | Whether to verify that the number of capture groups matches the number of output schema columns. |

### 3.3 Framework Parameters

| # | Parameter | Talend XML Name | Type | Default | Description |
| --- | ----------- | ----------------- | ------ | --------- | ------------- |
| 8 | Stat Catcher | `TSTATCATCHER_STATS` | CHECK | `false` | Enable statistics collection for tStatCatcher |
| 9 | Label | `LABEL` | TEXT | `""` | User-defined label for the component instance |

### 3.4 Connection Types

| Connector | Direction | Type | Description |
| ----------- | ----------- | ------ | ------------- |
| `FLOW` (Main) | Input | Row > Main | Incoming data rows with the source column to extract from |
| `FLOW` (Main) | Output | Row > Main | Rows with extracted fields populated from regex capture groups |
| `REJECT` | Output | Row > Reject | Rows where the regex did not match (includes errorCode/errorMessage columns) |
| `SUBJOB_OK` | Output (Trigger) | Trigger | Fires after component completes successfully |
| `COMPONENT_OK` | Output (Trigger) | Trigger | Fires after component completes |
| `COMPONENT_ERROR` | Output (Trigger) | Trigger | Fires if component encounters an error |
| `RUN_IF` | Output (Trigger) | Trigger | Conditional execution of downstream |

### 3.5 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
| ------------------ | ------ | ---------- | ------------- |
| `{id}_NB_LINE` | Integer | After execution | Number of rows processed by the component |

### 3.6 Behavioral Notes

1. **Phantom GROUP parameter**: The old converter extracted a `GROUP` parameter that does NOT exist in the _java.xml definition. Regex "group" is a common concept, but tExtractRegexFields uses capture groups implicitly -- there is no configurable GROUP parameter in Talend. This phantom param was removed in the v1.1 rewrite.
2. **DIE_ON_ERROR default is True**: The _java.xml specifies `true` as the default for DIE_ON_ERROR (in the ADVANCED section). The old converter incorrectly used `false`.
3. **REGEX_HELP is a LABEL**: The `REGEX_HELP` parameter is of type LABEL (informational text displayed in the UI showing regex syntax help). It is not a configuration parameter and is not extracted by the converter.
4. **CHECK_FIELDS_NUM validation**: When enabled, Talend verifies at runtime that the number of capture groups in the regex matches the number of output schema columns. This prevents silent data misalignment.
5. **Schema passthrough**: Input and output schemas share the same FLOW schema. The component populates output columns from capture group matches.
6. **FIELD is PREV_COLUMN_LIST**: The FIELD parameter references a column from the previous component's output. It shows as a dropdown in the Talend UI.

---

## 4. Converter Audit

How faithfully does the converter translate Talend XML to v1 JSON?

### 4.1 Parameter Extraction

The `ExtractRegexFieldsConverter` class uses `_build_component_dict()` (per CONVERTER_PATTERN.md) with `type_name="tExtractRegexFields"` (per D-43, no-engine). Single consolidated `needs_review` entry per D-27 for the absent engine.

| # | Talend XML Parameter | Extracted? | V1 Config Key | Notes |
| ---- | ---------------------- | ------------ | --------------- | ------- |
| 1 | `FIELD` | Yes | `field` | `_get_str(node, "FIELD", "")` -- PREV_COLUMN_LIST type, default empty. **Added in v1.1 rewrite** (was missing). |
| 2 | `REGEX_HELP` | No (correct) | -- | LABEL param (informational text), not a configuration value |
| 3 | `REGEX` | Yes | `regex` | `_get_str(node, "REGEX", "")` -- MEMO type |
| 4 | `SCHEMA` | Yes | (schema) | Via `_parse_schema(node)` |
| 5 | `SCHEMA_REJECT` | No | -- | Reject schema not extracted in current pattern |
| 6 | `DIE_ON_ERROR` | Yes | `die_on_error` | `_get_bool(node, "DIE_ON_ERROR", True)` -- **default FIXED from False to True** per _java.xml |
| 7 | `CHECK_FIELDS_NUM` | Yes | `check_fields_num` | `_get_bool(node, "CHECK_FIELDS_NUM", False)` -- **Added in v1.1 rewrite** (was missing) |
| 8 | `TSTATCATCHER_STATS` | Yes | `tstatcatcher_stats` | Framework param, default `False` |
| 9 | `LABEL` | Yes | `label` | Framework param, default `""` |

**Phantom params removed**: `GROUP` was in the old converter but is NOT in _java.xml. Removed.

**Summary**: 4 of 4 unique _java.xml parameters extracted (100%). 2 framework params extracted. 0 phantom params remain.

### 4.2 Schema Extraction

| Schema Attribute | Extracted? | Notes |
| ------------------ | ----------- | ------- |
| `name` | Yes | Via `_parse_schema()` |
| `type` | Yes | Via `convert_type()` mapping |
| `nullable` | Yes | Direct from SchemaColumn |
| `key` | Yes | Direct from SchemaColumn |
| `length` | Yes | When >= 0 |
| `precision` | Yes | When >= 0 |
| `pattern` | Yes | Java-to-Python date pattern conversion |
| `default` | No | Not extracted by `_parse_schema()` |

Schema is passthrough: `{"input": schema_cols, "output": schema_cols}` -- both sides populated from FLOW connector.

### 4.3 Expression Handling

REGEX is a MEMO field, meaning it can contain complex regex patterns. FIELD is a PREV_COLUMN_LIST that references a previous column name. Both are passed through as string values. The converter does not attempt to evaluate or transform expression content.

### 4.4 Converter Issues

No open issues. Converter follows CONVERTER_PATTERN.md gold standard.

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| -- | -- | No issues found |

### 4.5 Needs Review Entries

Single consolidated needs_review entry per D-27 (no engine implementation):

| # | Config Key | Reason | Severity |
| --- | ----------- | -------- | ---------- |
| 1 | (component-level) | No v1 engine implementation exists for tExtractRegexFields. Converter output is syntactically valid but cannot execute at runtime. | engine_gap |

---

## 5. Engine Feature Parity

How faithfully does the v1 engine implement Talend behavior?

### 5.1 Feature Implementation Status

Engine implemented (post-2026-04-05 via Phase 8090e9e rewrite + `bad0dd0` unescape fix).

| # | Talend Feature | Implemented? | Fidelity | Engine Location | Notes |
| ---- | ---------------- | ------------- | ---------- | ----------------- | ------- |
| 1 | Regex field extraction | **Yes** | High | `_process()` | `re.search()` with capture groups |
| 2 | Capture group mapping | **Yes** | High | `_process()` | Position-based: group 1 -> first output column |
| 3 | Die on error handling | **Yes** | High | `_process()` | Raises ConfigurationError/DataValidationError |
| 4 | Check fields num validation | **Yes** | High | `_validate_config()` | Group count vs schema column count |
| 5 | Schema passthrough | **Yes** | High | BaseComponent | input == output schema |
| 6 | Reject flow | **Yes** | High | `_process()` | NULL_SOURCE, NO_MATCH, FIELD_COUNT_MISMATCH reason codes |

### 5.2 Behavioral Differences from Talend

| ID | Priority | Description |
| ---- | ---------- | ------------- |
| ~~ENG-ERF-001~~ | ~~P0~~ | ~~No engine implementation exists~~ [RESOLVED: ExtractRegexFields engine class implemented] |
| PERF-ERF-001 | **P2** | iterrows() retained -- not vectorized for regex matching |

### 5.3 GlobalMap Variable Coverage

| Variable | Talend Sets? | V1 Sets? | How V1 Sets It | Notes |
| ---------- | ------------- | ---------- | ----------------- | ------- |
| `{id}_NB_LINE` | Yes | Yes | Base class `_update_global_map()` | Total rows processed |
| `{id}_NB_LINE_OK` | Yes | Yes | Base class `_update_global_map()` | Rows successfully matched |
| `{id}_NB_LINE_REJECT` | Yes | Yes | Base class `_update_global_map()` | Rows routed to REJECT |

---

## 6. Code Quality

How well-written is the engine code?

### 6.1 Bugs

| ID | Priority | Location | Description |
| ---- | ---------- | ---------- | ------------- |
| ~~BUG-ERF-001~~ | ~~P0~~ | -- | ~~No engine code exists~~ [RESOLVED: engine class implemented] |
| (TEST-REGEX-001) | -- | `test_extract_regex_fields.py` | Phase 13-06 TEST-CHANGE: test_regex_custom updated to assert Python-unescaped regex storage (Java `\\\\` -> Python `\\`) [RESOLVED in Phase 13-06, commit aa44a46 (TEST-REGEX-001)] |

### 6.2 Naming Consistency

No issues found. Converter follows naming conventions (snake_case config keys, PascalCase class name).

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| -- | -- | No issues found |

### 6.3 Standards Compliance

Converter fully compliant with CONVERTER_PATTERN.md and TEST_PATTERN.md.

| ID | Priority | Standard | Violation |
| ---- | ---------- | ---------- | ----------- |
| -- | -- | -- | No violations found |

### 6.4 Debug Artifacts

None found.

### 6.5 Security

No concerns identified. The REGEX parameter contains a regular expression that would need validation at engine runtime (potential for ReDoS -- catastrophic backtracking with malicious patterns), but since no engine exists, this is not currently exploitable.

### 6.6 Logging Quality

| Aspect | Assessment |
| -------- | ------------ |
| Logger setup | Good -- `logger = logging.getLogger(__name__)` at module level |
| Level usage | N/A -- no logging calls needed in simple converter |
| Sensitive data | No sensitive data logged |

### 6.7 Error Handling Quality

| Aspect | Assessment |
| -------- | ------------ |
| Custom exceptions | N/A -- converter returns ComponentResult, does not raise |
| Exception chaining | N/A |
| die_on_error handling | N/A -- no engine implementation |

### 6.8 Type Hints

| Aspect | Assessment |
| -------- | ------------ |
| Method signatures | Complete -- all parameters and return types annotated |
| Parameter types | Correct -- matches base class signatures |

---

## 7. Performance & Memory

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| PERF-ERF-001 | **P2** | iterrows() retained -- regex matching is row-by-row; optimization opportunity for large DataFrames |

### 7.1 Memory Management Assessment

| Aspect | Assessment |
| -------- | ------------ |
| Streaming mode | Not supported -- full DataFrame in memory |
| Memory threshold | No limit |
| Large data handling | Per-row regex matching; no chunked mode |

---

## 8. Testing

What's verified?

### 8.1 Current Coverage

| Test Type | Count | Location |
| ----------- | ------- | ---------- |
| Converter unit tests | 24 | `tests/converters/talend_to_v1/components/test_extract_regex_fields.py` |
| Engine unit tests | 28 | `tests/v1/engine/components/transform/test_extract_regex_fields.py` |
| Integration tests | 0 | None |

Phase 14-05 raised engine coverage to >= 95% floor (commit `bf92a6b` -- COV-ERF-001 lift).
Phase 13-06 TEST-REGEX-001 updated test_regex_custom to assert Python-unescaped storage (commit `aa44a46`).

### 8.2 Test Gaps

~~TEST-ERF-001~~ [RESOLVED: engine tests added + Phase 14-05 coverage lift commit bf92a6b].

### 8.3 Test Classes (Converter)

| Class | Tests | What's Verified |
| ------- | ------- | ----------------- |
| TestRegistration | 1 | REGISTRY.get("tExtractRegexFields") is ExtractRegexFieldsConverter |
| TestDefaults | 6 | field="", regex="", die_on_error=True, check_fields_num=False, tstatcatcher_stats=False, label="" |
| TestParameterExtraction | 4 | field custom, regex custom, die_on_error=False, check_fields_num=True |
| TestFrameworkParams | 2 | tstatcatcher_stats=True, label extracted |
| TestSchema | 2 | Passthrough (input==output), columns populated |
| TestNeedsReview | 5 | Count==1, severity, no-engine message, component_id, no framework param entries |
| TestPhantomParams | 1 | GROUP NOT in config |
| TestCompleteness | 1 | All 6 expected config keys present (4 unique + 2 framework) |
| TestComponentStructure | 2 | type="tExtractRegexFields", original_type="tExtractRegexFields" |

### 8.4 Recommended Test Cases

When an engine is implemented, add:

1. Happy path: apply regex `"(\\d+)-(\\w+)"` to column with value `"123-abc"`, verify capture groups populate output columns
2. No match: regex doesn't match input value, verify reject flow
3. Check fields num: capture group count mismatch with output schema columns
4. Die on error true: extraction error causes job abort
5. Die on error false: extraction error produces warning, continues processing
6. Empty input: 0-row DataFrame
7. Null values in source column
8. Complex regex with nested groups
9. Schema passthrough verification: all columns preserved
10. GlobalMap variable `{id}_NB_LINE` set correctly

---

## 9. Issues Summary

All issues grouped by priority for sprint planning.

### By Priority

| Priority | Count | IDs |
| ---------- | ------- | ----- |
| P0 | 0 | -- (ENG-ERF-001 resolved; BUG-ERF-001 resolved; TEST-ERF-001 resolved) |
| P1 | 0 | -- |
| P2 | 1 | PERF-ERF-001 |
| P3 | 0 | -- |
| **Total** | **1** | |

### By Category

| Category | Count | IDs |
| ---------- | ------- | ----- |
| Converter (CONV) | 0 | -- |
| Engine (ENG) | 0 | -- (ENG-ERF-001 resolved) |
| Bug (BUG) | 0 | -- (BUG-ERF-001 resolved) |
| Naming (NAME) | 0 | -- |
| Standards (STD) | 0 | -- |
| Performance (PERF) | 1 | PERF-ERF-001 |
| Testing (TEST) | 0 | -- (TEST-ERF-001 resolved; TEST-REGEX-001 resolved) |

### Cross-Cutting Issues

No cross-cutting issues. Engine implementation follows base_component.py correctly.

---

## 10. Recommendations

What should be fixed, in what order?

### Immediate (Before Production)

None -- ENG-ERF-001, BUG-ERF-001, and TEST-ERF-001 are all resolved.

### Short-term (Hardening)

1. **Vectorize regex matching** (PERF-ERF-001, P2) -- replace iterrows() with vectorized `Series.str.extract()` for large DataFrame performance.

### Long-term (Optimization)

No long-term issues identified.

---

## Appendix A: Source References

| Source | URL/Path | Used For |
| -------- | ---------- | ---------- |
| Talaxie GitHub _java.xml | `<https://github.com/Talaxie/tdi-studio-se/blob/master/main/plugins/org.talend.designer.components.localprovider/components/tExtractRegexFields/tExtractRegexFields_java.xml`> | Parameter definitions, defaults, types |
| Converter source | `src/converters/talend_to_v1/components/transform/extract_regex_fields.py` | Converter audit |
| Test source | `tests/converters/talend_to_v1/components/test_extract_regex_fields.py` | Test coverage analysis |
| Pattern docs | `docs/v1/patterns/CONVERTER_PATTERN.md`, `docs/v1/patterns/TEST_PATTERN.md` | Standards compliance verification |
| Authoring guide | `docs/v1/patterns/MANUAL_COMPONENT_AUTHORING.md` | Component authoring rules (replaces legacy audit template) |

## Appendix B: Converter Config Key Mapping

| _java.xml Param | Config Key | Type | Default | Extracted | Notes |
| ----------------- | ----------- | ------ | --------- | ----------- | ------- |
| `FIELD` | `field` | str | `""` | Yes | PREV_COLUMN_LIST type. **Added in v1.1** (was missing). |
| `REGEX_HELP` | -- | -- | -- | No | LABEL param (display only) |
| `REGEX` | `regex` | str | `""` | Yes | MEMO type |
| `SCHEMA` | (schema) | -- | -- | Yes | Via `_parse_schema()` |
| `SCHEMA_REJECT` | -- | -- | -- | No | Reject schema type |
| `DIE_ON_ERROR` | `die_on_error` | bool | `True` | Yes | **Default FIXED** from False to True per _java.xml |
| `CHECK_FIELDS_NUM` | `check_fields_num` | bool | `False` | Yes | **Added in v1.1** (was missing) |
| `TSTATCATCHER_STATS` | `tstatcatcher_stats` | bool | `False` | Yes | Framework param |
| `LABEL` | `label` | str | `""` | Yes | Framework param |
| `GROUP` | -- | -- | -- | No | **PHANTOM** -- not in _java.xml, removed |

---

*Report generated: 2026-04-04*
*Last updated: 2026-05-11 -- Phase 15.1-05 reconciliation (engine gap resolved, Phase 13-06 + Phase 14-05 coverage noted, broken refs repaired)*
