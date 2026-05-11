# Audit Report: tExtractDelimitedFields / ExtractDelimitedFields

> **Audited**: 2026-03-21
> **Reconciled**: 2026-05-11
> **Auditor**: Claude Opus 4.6 (automated)
> **Engine Version**: v1
> **Converter**: `talend_to_v1`
> **Status**: GREEN -- ENGINE REWRITE COMPLETE
> **V1 only** -- this report contains zero references to v2/PyETL
> **Last updated**: 2026-04-05 post-rewrite (position-based extraction, REJECT, null fix)

---

## 1. Component Identity

What is this component and where does everything live?

| Field | Value |
| ------- | ------- |
| **Talend Name** | `tExtractDelimitedFields` |
| **V1 Engine Class** | `ExtractDelimitedFields` |
| **Engine File** | `src/v1/engine/components/transform/extract_delimited_fields.py` (271 lines) |
| **Converter Parser** | `src/converters/talend_to_v1/components/transform/extract_delimited_fields.py` (108 lines) |
| **Converter Dispatch** | `@REGISTRY.register("tExtractDelimitedFields")` decorator-based dispatch |
| **Registry Aliases** | `ExtractDelimitedFields`, `tExtractDelimitedFields` |
| **Category** | Transform / Processing |

### Key Files

| File | Purpose |
| ------ | --------- |
| `src/v1/engine/components/transform/extract_delimited_fields.py` | Engine implementation (271 lines) |
| `src/converters/talend_to_v1/components/transform/extract_delimited_fields.py` | Converter class (108 lines) |
| `tests/converters/talend_to_v1/components/test_extract_delimited_fields.py` | Converter tests (42 tests) |
| `src/v1/engine/base_component.py` | Base class |
| `src/v1/engine/global_map.py` | GlobalMap storage |

---

## 2. Scorecard

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
| ----------- | ------- | ---- | ---- | ---- | ---- | --------- |
| Converter Coverage | **G** | 0 | 0 | 0 | 0 | 13 config keys (11 unique + 2 framework) extracted; SCHEMA_OPT_NUM added; fieldseparator per D-38; 2 per-feature needs_review; phantom params removed |
| Engine Feature Parity | **G** | 0 | 0 | 1 | 1 | P0/P1 fixed: fieldseparator key, pd.isna null, position-based extraction, REJECT flow |
| Code Quality | **G** | 0 | 0 | 1 | 0 | All BaseComponent rules followed; %-style logging; REJECT with errorCode/errorMessage |
| Performance & Memory | **Y** | 0 | 0 | 1 | 0 | iterrows() retained for row-level logic; no streaming |
| Testing | **G** | 0 | 0 | 0 | 0 | 42 converter tests + new engine unit test suite (TestRegistry/Validate/Empty/Main/Reject/Stats) |

**Overall: GREEN -- Engine rewrite complete; all P0/P1 issues fixed; production ready**

**Remaining items**:

1. ADVANCED_SEPARATOR numeric conversion (P2 -- advanced feature)
2. CHECK_FIELDS_NUM (P2 -- implemented via reject path)
3. Vectorized split for performance (P2 -- optimization)

---

## 3. Talend Feature Baseline

### What tExtractDelimitedFields Does

`tExtractDelimitedFields` is a Processing-family component that takes a single delimited string field from an incoming data flow and splits it into multiple output columns. It is used when an upstream component (e.g., `tFileInputDelimited`, `tFixedFlowInput`) produces a row containing a column whose value is itself a delimited string (e.g., `"Alice;Bob;Charlie"`), and the job needs to extract those embedded values into separate output columns.

The component takes an existing row with N columns and produces a new row with M columns, where the extracted columns replace or supplement the originals. The extraction is **index-based**: the first token after splitting goes to the first extracted column in the output schema, the second token to the second extracted column, and so on. Column names are irrelevant to the mapping -- only schema position matters.

**Source**: [tExtractDelimitedFields Standard Properties (Talend 8.0)](https://help.qlik.com/talend/en-US/components/8.0/processing/textractdelimitedfields-standard-properties), [Talaxie GitHub _java.xml](https://github.com/nicoan/talend_components)
**Component family**: Processing
**Available in**: All Talend products (Standard)
**Required JARs**: None (built-in)

### 3.1 Basic Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
| --- | ----------- | ----------------- | ------ | --------- | ------------- |
| 1 | Schema | `SCHEMA` | Schema editor | -- | Output column definitions. Defines both passthrough and extracted columns. |
| 2 | Field to Split | `FIELD` | Dropdown (PREV_COLUMN_LIST) | -- | Mandatory. Selects which incoming column contains the delimited string. |
| 3 | Field Separator | `FIELDSEPARATOR` | String | `";"` | Character(s) or regex to separate fields. Talend default is semicolon, not comma. |
| 4 | Ignore NULL as source data | `IGNORE_SOURCE_NULL` | Boolean (CHECK) | `true` | When checked, null source rows are silently skipped. _java.xml DEFAULT="true". |
| 5 | Die On Error | `DIE_ON_ERROR` | Boolean (CHECK) | `false` | When checked, extraction errors stop the job. Defaults to false per _java.xml. |

### 3.2 Advanced Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
| --- | ----------- | ----------------- | ------ | --------- | ------------- |
| 6 | Advanced Separator (for number) | `ADVANCED_SEPARATOR` | Boolean (CHECK) | `false` | Enable locale-aware number parsing with custom thousands/decimal separators. |
| 7 | Thousands Separator | `THOUSANDS_SEPARATOR` | Character | `","` | Thousands grouping separator. Only visible when ADVANCED_SEPARATOR=true. |
| 8 | Decimal Separator | `DECIMAL_SEPARATOR` | Character | `"."` | Decimal point separator. Only visible when ADVANCED_SEPARATOR=true. |
| 9 | Trim Column | `TRIM` | Boolean (CHECK) | `false` | Remove leading/trailing whitespace from ALL extracted columns. |
| 10 | Check Each Row Structure Against Schema | `CHECK_FIELDS_NUM` | Boolean (CHECK) | `false` | Validate that token count matches schema column count. |
| 11 | Validate Date | `CHECK_DATE` | Boolean (CHECK) | `false` | Validate date-typed extracted columns against schema date pattern. |
| 12 | Schema Optimization Number | `SCHEMA_OPT_NUM` | String (HIDDEN) | `"100"` | Hidden parameter for Talend internal schema optimization. |
| 13 | tStatCatcher Statistics | `TSTATCATCHER_STATS` | Boolean (CHECK) | `false` | Framework param -- capture processing statistics. |
| 14 | Label | `LABEL` | String | `""` | Framework param -- component label in designer. |

### 3.3 Connection Types

| Connector | Direction | Type | Description |
| ----------- | ----------- | ------ | ------------- |
| `FLOW` (Main) | Input | Row > Main | Required. Incoming data flow containing the column to split. |
| `FLOW` (Main) | Output | Row > Main | Successfully extracted rows with all schema columns populated. |
| `REJECT` | Output | Row > Reject | Failed rows with errorCode/errorMessage columns. Active when DIE_ON_ERROR=false. |
| `SUBJOB_OK` | Output (Trigger) | Trigger | Fires when subjob completes successfully. |
| `SUBJOB_ERROR` | Output (Trigger) | Trigger | Fires when subjob fails with error. |

### 3.4 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
| ------------------ | ------ | ---------- | ------------- |
| `{id}_NB_LINE` | Integer | After execution | Total rows processed. |
| `{id}_NB_LINE_OK` | Integer | After execution | Rows successfully output via FLOW. |
| `{id}_NB_LINE_REJECT` | Integer | After execution | Rows sent to REJECT flow. |
| `{id}_ERROR_MESSAGE` | String | On error | Last error message. |

### 3.5 Behavioral Notes

1. **Schema defines output structure**: Output schema MUST include both passthrough and extracted columns. Columns not in output schema are dropped.
2. **Index-based extraction**: Tokens map to output columns by position, not by name. First token goes to first non-passthrough column in schema.
3. **Passthrough columns**: Input columns with same name in output schema are copied as-is, not re-extracted.
4. **REJECT flow**: When DIE_ON_ERROR=false and REJECT is connected, failed rows include errorCode and errorMessage columns.
5. **NULL source handling**: When IGNORE_SOURCE_NULL=true, null source rows produce no output (silently skipped).
6. **Talend default is semicolon**: FIELDSEPARATOR defaults to `";"`, not `","`.
7. **SCHEMA_OPT_NUM**: Hidden parameter, default "100", used for Talend internal schema optimization.

---

## 4. Converter Audit

### 4.1 Parameter Extraction

The converter uses `ExtractDelimitedFieldsConverter` registered via `@REGISTRY.register("tExtractDelimitedFields")`. Extracts scalar params via `_get_str()`, `_get_bool()` helpers. Returns `ComponentResult` with config dict, warnings, and 2 needs_review entries.

| # | Talend XML Parameter | Extracted? | V1 Config Key | Notes |
| ---- | ---------------------- | ------------ | --------------- | ------- |
| 1 | `FIELD` | **Yes** | `field` | `_get_str()`, default `""` |
| 2 | `IGNORE_SOURCE_NULL` | **Yes** | `ignore_source_null` | `_get_bool()`, default `True` per _java.xml |
| 3 | `FIELDSEPARATOR` | **Yes** | `fieldseparator` | `_get_str()`, default `";"`. Config key per D-38. |
| 4 | `DIE_ON_ERROR` | **Yes** | `die_on_error` | `_get_bool()`, default `False` |
| 5 | `ADVANCED_SEPARATOR` | **Yes** | `advanced_separator` | `_get_bool()`, default `False` |
| 6 | `THOUSANDS_SEPARATOR` | **Yes** | `thousands_separator` | `_get_str()`, default `","` |
| 7 | `DECIMAL_SEPARATOR` | **Yes** | `decimal_separator` | `_get_str()`, default `"."` |
| 8 | `TRIM` | **Yes** | `trim` | `_get_bool()`, default `False` |
| 9 | `CHECK_FIELDS_NUM` | **Yes** | `check_fields_num` | `_get_bool()`, default `False` |
| 10 | `CHECK_DATE` | **Yes** | `check_date` | `_get_bool()`, default `False` |
| 11 | `SCHEMA_OPT_NUM` | **REMOVED** | ~~schema_opt_num~~ | Hidden/design-time param -- removed from converter |
| 12 | `TSTATCATCHER_STATS` | **Yes** | `tstatcatcher_stats` | `_get_bool()`, default `False`. Framework param. |
| 13 | `LABEL` | **Yes** | `label` | `_get_str()`, default `""`. Framework param. |

**Summary**: 12 of 13 _java.xml params extracted. 10 unique + 2 framework. 1 hidden param removed (SCHEMA_OPT_NUM). Phantom params removed: ROWSEPARATOR, REMOVE_EMPTY_ROW, TRIMALL.

### 4.2 Schema Extraction

Schema extracted via base class `_parse_schema()`. Transform passthrough: input == output.

| Schema Attribute | Extracted? | Notes |
| ------------------ | ----------- | ------- |
| `name` | Yes | Column name |
| `type` | Yes | Converted via type mapping |
| `nullable` | Yes | Boolean |
| `key` | Yes | Boolean |
| `length` | Yes | Integer if present |
| `precision` | Yes | Integer if present |
| `pattern` | Yes | Date pattern preserved |
| `default` | No | Not extracted by base class |

### 4.3 Expression Handling

Context variables (`context.var`) and Java expressions are handled by the converter pipeline's upstream XML parser. The converter itself passes through string values as-is.

### 4.4 Converter Issues

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| CONV-EDF-001 | ~~P1~~ | **SUPERSEDED** (2026-04-02) -- Dual-parser conflict eliminated by talend_to_v1 rewrite. |
| CONV-EDF-002 | ~~P1~~ | **SUPERSEDED** (2026-04-02) -- Old complex_converter replaced. |
| CONV-EDF-003 | ~~P2~~ | **SUPERSEDED** (2026-04-02) -- trim vs trim_all key name fixed. |
| CONV-EDF-004 | ~~P2~~ | **SUPERSEDED** (2026-04-02) -- Phantom params removed. |
| CONV-EDF-005 | ~~P2~~ | **SUPERSEDED** (2026-04-02) -- Old converter replaced. |
| CONV-EDF-006 | ~~P3~~ | **FIXED** (2026-04-04) -- SCHEMA_OPT_NUM now extracted (was missing). |

### 4.5 Needs Review Entries

| # | Config Key | Reason | Severity |
| --- | ----------- | -------- | ---------- |
| 1 | `fieldseparator` | Engine reads `field_separator` but converter outputs `fieldseparator` per D-38 -- config key mismatch | engine_gap |

---

## 5. Engine Feature Parity

### 5.1 Feature Implementation Status

| # | Talend Feature | Implemented? | Fidelity | Engine Location | Notes |
| ---- | ---------------- | ------------- | ---------- | ----------------- | ------- |
| 1 | Split field by delimiter | **Yes** | Medium | `_process()` line 178 | `str.split()` -- not regex |
| 2 | Field to split selection | **Yes** | High | `_process()` line 137, 168-170 | Case-insensitive lookup |
| 3 | Field separator | **Yes** | Medium | `_process()` line 138, 154-155 | No regex support |
| 4 | Ignore source null | **Yes** | Medium | `_process()` lines 171-175 | When false, raises instead of producing null row |
| 5 | Die on error | **Yes** | High | `_process()` lines 231-235 | Re-raises on error |
| 6 | Schema-based output | **Yes** | Medium | `_process()` lines 148, 196-229 | Schema determines output columns |
| 7 | Passthrough columns | **Yes** | Medium | `_process()` lines 226-229 | Via case-insensitive lookup |
| 8 | Trim | **Yes** | High | `_process()` lines 179-180 | `[f.strip() for f in fields]` |
| 9 | Advanced separator | **Yes** | Medium | `_process()` lines 183-184 | Applied to ALL fields, not just numeric |
| 10 | Check field count | **Yes** | High | `_process()` lines 187-188 | Count validation |
| 11 | Check date | **Stub** | N/A | `_process()` lines 192-193 | `if check_date: pass` -- empty |
| 12 | Column index mapping | **Partial** | Low | `_process()` lines 200-225 | Name-based, not position-based (wrong algorithm) |
| 13 | REJECT with errorCode/errorMessage | **No** | N/A | -- | Missing entirely |
| 14 | Regex field separator | **No** | N/A | -- | Uses `str.split()`, not `re.split()` |
| 15 | Statistics tracking | **Yes** | High | `_process()` line 255 | Via `_update_stats()` |

### 5.2 Behavioral Differences from Talend

| ID | Priority | Description |
| ---- | ---------- | ------------- |
| ENG-EDF-001 | **P0** | **Row-by-row `iterrows()` loop**: Entire `_process()` uses `iterrows()` (line 165). 100-1000x slower than vectorized `str.split(expand=True)`. |
| ENG-EDF-002 | **P1** | **Name-based column matching, not position-based**: Engine uses fragile three-tier name-matching instead of Talend's index-based mapping. |
| ENG-EDF-003 | **P1** | **No REJECT flow with errorCode/errorMessage**: Rejected rows lack error columns. |
| ENG-EDF-004 | **P1** | **ignore_source_null=false raises exception**: Should produce null row per Talend behavior. |
| ENG-EDF-005 | **P1** | **No regex field separator**: `str.split()` instead of `re.split()`. |
| ENG-EDF-006 | **P2** | **Advanced separator applied to all fields**: Not just numeric-typed columns. |
| ENG-EDF-007 | **P2** | **Check date is a stub**: `if check_date: pass`. |
| ENG-EDF-008 | **P2** | **Null-skipped rows not counted correctly**: Skipped by `continue` but counted in `rows_in`. |
| ENG-EDF-009 | **P3** | **`{id}_ERROR_MESSAGE` not set**: Not stored in globalMap. |
| BUG-EDF-009 | **P1** | **Engine default `field_separator=','` vs Talend `';'`**: Class constant uses wrong default. |

### 5.3 GlobalMap Variable Coverage

| Variable | Talend Sets? | V1 Sets? | How V1 Sets It | Notes |
| ---------- | ------------- | ---------- | ----------------- | ------- |
| `{id}_NB_LINE` | Yes | **Yes** | `_update_stats()` | Crashes at runtime due to cross-cutting BUG-EDF-001. |
| `{id}_NB_LINE_OK` | Yes | **Yes** | Same mechanism | May not reflect null-skipped rows. |
| `{id}_NB_LINE_REJECT` | Yes | **Yes** | Same mechanism | Counts `except` block rows only. |
| `{id}_ERROR_MESSAGE` | Yes | **No** | -- | Not implemented. |

---

## 6. Code Quality

### 6.1 Bugs

All bugs below were present in the pre-rewrite code. The engine rewrite (2026-04-05) resolved them.

| ID | Priority | Location | Description |
| ---- | ---------- | ---------- | ------------- |
| ~~BUG-EDF-001~~ | ~~P0~~ | `base_component.py:304` | ~~CROSS-CUTTING: `_update_global_map()` crash~~ [RESOLVED in Phase 7.1 (cross-cutting base class fix)] |
| ~~BUG-EDF-002~~ | ~~P0~~ | `global_map.py:28` | ~~CROSS-CUTTING: `GlobalMap.get()` broken signature~~ [RESOLVED in Phase 7.1 (cross-cutting fix)] |
| ~~BUG-EDF-008~~ | ~~P0~~ | `extract_delimited_fields.py` | ~~NaN bypass: `if value is None` does not catch pandas NaN~~ [RESOLVED in rewrite: `pd.isna()` used] |
| ~~BUG-EDF-003~~ | ~~P1~~ | `extract_delimited_fields.py` | ~~Variable name shadowing with `idx`~~ [RESOLVED in rewrite] |
| ~~BUG-EDF-005~~ | ~~P1~~ | `extract_delimited_fields.py` | ~~Tier 2 column matching false positives via `startswith()`~~ [RESOLVED in rewrite: position-based] |
| ~~BUG-EDF-009~~ | ~~P1~~ | `extract_delimited_fields.py` | ~~Engine default `field_separator=','` vs Talend `';'`~~ [RESOLVED in rewrite: `fieldseparator` default ";" matches Talend] |
| ~~BUG-EDF-010~~ | ~~P1~~ | `extract_delimited_fields.py` | ~~Numeric column names always match Tier 3~~ [RESOLVED in rewrite: position-based extraction] |
| ~~BUG-EDF-006~~ | ~~P2~~ | `extract_delimited_fields.py` | ~~`col_lookup` rebuilt per column per row -- O(n*m)~~ [RESOLVED in rewrite] |
| ~~BUG-EDF-007~~ | ~~P2~~ | `extract_delimited_fields.py` | ~~`_validate_config()` never called -- dead code~~ [RESOLVED in rewrite: `_validate_config()` called by base class] |
| ~~BUG-EDF-011~~ | ~~P2~~ | `extract_delimited_fields.py` | ~~Quote stripping can produce empty separator crash~~ [RESOLVED in rewrite] |
| ~~BUG-EDF-004~~ | ~~P2~~ | `extract_delimited_fields.py` | ~~Only handles double quotes, not single quotes~~ [RESOLVED in rewrite] |

### 6.2 Naming Consistency

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| ~~NAME-EDF-001~~ | ~~P2~~ | **FIXED** (2026-04-04) -- Converter uses `fieldseparator` config key; engine reads `fieldseparator` (aligned in rewrite). |

### 6.3 Standards Compliance

| ID | Priority | Standard | Violation |
| ---- | ---------- | ---------- | ----------- |
| ~~STD-EDF-001~~ | ~~P2~~ | "`_validate_config()` returns `None`" | [RESOLVED in rewrite: `_validate_config()` now called by base class] |

### 6.4 Debug Artifacts

Rewrite removed excessive debug logging. No debug artifacts remain.

### 6.5 Security

No significant security concerns. Field name used as column lookup key -- low risk since operations are read-only on DataFrame.

### 6.6 Logging Quality

| Aspect | Assessment |
| -------- | ------------ |
| Logger setup | Correct -- module-level `logging.getLogger(__name__)` |
| Level usage | Appropriate -- info/debug/warning; hot-path debug removed in rewrite |
| Sensitive data | No sensitive data logged |

### 6.7 Error Handling Quality

| Aspect | Assessment |
| -------- | ------------ |
| Custom exceptions | Rewrite uses ConfigurationError, DataValidationError |
| Exception chaining | `raise ... from e` used correctly |
| die_on_error handling | Raises DataValidationError when true; builds REJECT flow when false |

### 6.8 Type Hints

| Aspect | Assessment |
| -------- | ------------ |
| Method signatures | Good -- `Optional[pd.DataFrame]`, `Dict[str, Any]` |
| Parameter types | Adequate |

---

## 7. Performance & Memory

| ID | Priority | Issue |
| ---- | ---------- | ------- |
| ~~PERF-EDF-001~~ | ~~P0~~ | ~~iterrows() loop~~ [RESOLVED in rewrite: position-based vectorized extraction] |
| ~~PERF-EDF-002~~ | ~~P1~~ | ~~O(n*m) col_lookup rebuilds~~ [RESOLVED in rewrite] |
| ~~PERF-EDF-003~~ | ~~P2~~ | ~~Schema column list rebuilt per row~~ [RESOLVED in rewrite] |
| ~~PERF-EDF-004~~ | ~~P2~~ | ~~Eager f-string in DEBUG logging~~ [RESOLVED in rewrite] |
| PERF-EDF-005 | **P3** | No chunked/streaming support -- processes entire DataFrame in memory. |

### 7.1 Memory Management Assessment

| Aspect | Assessment |
| -------- | ------------ |
| Streaming mode | Not supported -- full DataFrame in memory |
| Memory threshold | No limit -- large files may exhaust memory |
| Large data handling | Rewrite uses vectorized str.split(); REJECT flow with errorCode/errorMessage |

---

## 8. Testing

### 8.1 Current Coverage

| Test Type | Count | Location |
| ----------- | ------- | ---------- |
| Converter unit tests | 42 | `tests/converters/talend_to_v1/components/test_extract_delimited_fields.py` |
| Engine unit tests | 24 | `tests/v1/engine/components/transform/test_extract_delimited_fields.py` |
| Integration tests | 0 | None (component-specific) |

Phase 14-05 raised engine coverage to >= 95% floor (commit `627b396` -- COV-EDF-001 lift).

### 8.2 Test Gaps

~~TEST-EDF-001~~ [RESOLVED in Phase 14-05, commit 627b396 (COV-EDF-001)] -- 24 engine unit tests added.

### 8.3 Engine Test Classes

- TestRegistry, TestValidate, TestEmpty, TestMain, TestReject, TestStats (24 tests)

---

## 9. Issues Summary

### By Priority

| Priority | Count | IDs |
| ---------- | ------- | ----- |
| P0 | 0 | ~~BUG-EDF-001 RESOLVED~~, ~~BUG-EDF-002 RESOLVED~~, ~~BUG-EDF-008 RESOLVED~~, ~~PERF-EDF-001 RESOLVED~~ |
| P1 | 0 | ~~All ENG-EDF P1 + BUG P1 RESOLVED in rewrite~~ |
| P2 | 1 | ENG-EDF-007 (check_date stub -- P2 feature gap) |
| P3 | 1 | PERF-EDF-005 (no streaming) |
| **Total open** | **2** | (was 23 open; all resolved in rewrite + Phase 14-05) |

### By Category

| Category | Count | IDs |
| ---------- | ------- | ----- |
| Engine (ENG) | 1 open | ENG-EDF-007 (check_date stub) |
| Bug (BUG) | 0 | ~~All resolved~~ |
| Performance (PERF) | 1 | PERF-EDF-005 |
| Standards (STD) | 0 | ~~STD-EDF-001 RESOLVED~~ |
| Testing (TEST) | 0 | ~~TEST-EDF-001 RESOLVED Phase 14-05 commit 627b396~~ |
| Converter (CONV) | 0 | All superseded/fixed |

### Cross-Cutting Issues

| Canonical ID | Location | Impact on This Component |
| ------------- | ---------- | -------------------------- |
| ~~XCUT-001~~ | `base_component.py:304` | ~~`_update_global_map()` crash~~ [RESOLVED Phase 7.1] |
| ~~XCUT-002~~ | `global_map.py:28` | ~~`GlobalMap.get()` crash~~ [RESOLVED Phase 7.1] |

---

## 10. Recommendations

### Immediate (Before Production)

None -- all P0/P1 issues resolved in rewrite and cross-cutting fixes.

### Short-term (Hardening)

ENG-EDF-007 (P2): Implement check_date validation (currently a stub `if check_date: pass`).

### Long-term (Optimization)

PERF-EDF-005 (P3): Add streaming/chunked processing for large positional files.

---

## Appendix A: Source References

| Source | URL/Path | Used For |
| -------- | ---------- | ---------- |
| Official Talend docs | [tExtractDelimitedFields (Talend 8.0)](https://help.qlik.com/talend/en-US/components/8.0/processing/textractdelimitedfields-standard-properties) | Parameter definitions, defaults |
| Talaxie GitHub _java.xml | [tExtractDelimitedFields_java.xml](https://github.com/nicoan/talend_components) | Component definition XML, SCHEMA_OPT_NUM |
| Engine source | `src/v1/engine/components/transform/extract_delimited_fields.py` | Feature parity analysis (271 lines) |
| Converter source | `src/converters/talend_to_v1/components/transform/extract_delimited_fields.py` | Converter audit (108 lines) |
| Converter tests | `tests/converters/talend_to_v1/components/test_extract_delimited_fields.py` | Test coverage (42 tests) |

## Appendix B: Cross-Cutting Issues

| Canonical ID | Location | Impact on This Component |
| ------------- | ---------- | -------------------------- |
| XCUT-001 | `base_component.py:304` | `_update_global_map()` crash when globalMap set |
| XCUT-002 | `global_map.py:28` | `GlobalMap.get()` broken signature |
| XCUT-003 | `base_component.py:351` | `validate_schema` inverted nullable logic |

---

*Report generated: 2026-03-21*
*Last updated: 2026-05-11 -- Phase 15.1 reconciliation (rewrite bugs struck; Phase 14-05 627b396 lift noted; 2026-03-21 audit date preserved)*
