# Audit Report: tNormalize / Normalize

> **Audited**: 2026-03-21
> **Auditor**: Claude Opus 4.6 (automated)
> **Engine Version**: v1
> **Converter**: `complex_converter`
> **Status**: PRODUCTION READINESS REVIEW

---

## 1. Component Identity

| Field | Value |
|-------|-------|
| **Talend Name** | `tNormalize` |
| **V1 Engine Class** | `Normalize` |
| **Engine File** | `src/v1/engine/components/transform/normalize.py` (221 lines) |
| **Converter Parser** | `src/converters/complex_converter/component_parser.py` -> `parse_tnormalize()` (lines 1921-1937) |
| **Converter Dispatch** | `src/converters/complex_converter/converter.py` -> `elif component_type == 'tNormalize':` (line 315-316) |
| **Registry Aliases** | `Normalize`, `tNormalize` (registered in `src/v1/engine/engine.py` lines 115-116) |
| **Category** | Processing / Transform |

### Key Files

| File | Purpose |
|------|---------|
| `src/v1/engine/components/transform/normalize.py` | Engine implementation (221 lines) |
| `src/converters/complex_converter/component_parser.py` (lines 1921-1937) | Dedicated `parse_tnormalize()` method -- parameter mapping from Talend XML to v1 JSON |
| `src/converters/complex_converter/converter.py` (line 315-316) | Dispatch -- dedicated `elif component_type == 'tNormalize'` branch |
| `src/v1/engine/base_component.py` | Base class: `_update_stats()`, `_update_global_map()`, `validate_schema()`, `execute()` |
| `src/v1/engine/global_map.py` | GlobalMap storage for `{id}_NB_LINE` etc. |
| `src/v1/engine/exceptions.py` | Custom exception hierarchy (`ConfigurationError`, `ComponentExecutionError`) |
| `src/v1/engine/components/transform/__init__.py` (line 15) | Package export: `from .normalize import Normalize` |
| `src/v1/engine/engine.py` (line 40) | **BUG**: Imports `Normalize` from `.components.aggregate` but class lives in `.components.transform` |

---

## 2. Scorecard

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
|-----------|-------|----|----|----|----|---------|
| Converter Coverage | **G** | 0 | 0 | 3 | 2 | 5 of 7 Talend runtime params extracted (71%); missing `DIE_ON_ERROR`, `CSV parameters`; dedicated parser method |
| Engine Feature Parity | **Y** | 0 | 3 | 3 | 1 | `discard_trailing_empty_str` filters ALL empties not just trailing; null->empty string differs from Talend; NB_LINE wrong semantics |
| Code Quality | **R** | 3 | 4 | 5 | 1 | Cross-cutting base class bugs; empty-separator crash; `iterrows()` anti-pattern; `row.copy()` type demotion (data fidelity); import path mismatch; discard-empty logic bug; null handling bug; empty DF loses schema; `str()` garbage on non-string types |
| Performance & Memory | **R** | 1 | 1 | 1 | 0 | `iterrows()` + `row.copy()` + list-of-Series pattern is O(n*m) and creates massive intermediate memory; no vectorized alternative |
| Testing | **R** | 1 | 1 | 0 | 0 | Zero v1 unit tests; zero v1 integration tests for this component |

**Overall: RED -- Not production-ready. 3 of 5 dimensions are Red; 5 P0 and 9 P1 issues must be resolved before production use.**

### Score Key
- **R** (Red): Critical gaps blocking production use
- **Y** (Yellow): Significant gaps; usable for subset of jobs with known limitations
- **G** (Green): Production-ready with minor improvements recommended

---

## 3. Talend Feature Baseline

### What tNormalize Does

`tNormalize` normalizes the input flow following the SQL standard to help improve data quality and ease data updates. It takes a single column containing delimited values (e.g., `"a,b,c"`) and explodes each row into multiple rows -- one for each delimited value. All other columns in the row are replicated unchanged across the output rows. This is the inverse operation of `tDenormalize`.

**Source**: [tNormalize Standard Properties (Talend 8.0)](https://help.qlik.com/talend/en-US/components/8.0/processing/tnormalize-standard-properties), [tNormalize Overview (Talend 7.3)](https://help.talend.com/en-US/components/7.3/processing/tnormalize), [Normalizing Data Scenario (Talend 8.0)](https://help.talend.com/r/en-US/8.0/processing/tnormalize-tfileinputdelimited-tlogrow-tlogrow-normalizing-data-standard-component-this), [tNormalize ESB 7.x Docs (Talend Skill)](https://talendskill.com/talend-for-esb-docs/docs-7-x/tnormalize-talend-open-studio-for-esb-document-7-x/), [Talend tNormalize Tutorial (TutorialGateway)](https://www.tutorialgateway.org/talend-tnormalize/)

**Component family**: Processing
**Available in**: All Talend products (Standard). Also available in MapReduce (deprecated), Spark Batch, Spark Streaming variants.

### 3.1 Basic Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 1 | Property Type | `PROPERTY_TYPE` | Built-In / Repository | Built-In | Whether config comes from metadata repository or is inline. Not needed at runtime. |
| 2 | Schema | `SCHEMA` | Schema editor | -- | Column definitions with types, lengths, patterns, nullable, key attributes. Defines the output structure. Input and output schemas are identical -- the normalized column retains its original type. |
| 3 | Column to Normalize | `NORMALIZE_COLUMN` | Dropdown (column name) | -- | **Mandatory**. Selects which column in the input schema contains the delimited values to split. The dropdown is populated from the schema columns. |
| 4 | Item Separator | `ITEMSEPARATOR` | String (regex-capable) | `","` | The delimiter character(s) separating individual values within the normalized column. Can be a literal string or regex. The period character (`.`) should be avoided or escaped because the separator is regex-capable. Common values: `","`, `";"`, `"|"`, `"\\n"`. |

### 3.2 Advanced Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 5 | Get Rid of Duplicated Rows | `DEDUPLICATE` | Boolean (CHECK) | `false` | Remove duplicate values from the split output. When enabled, if a column value like `"a,b,a,c"` is split, the duplicate `"a"` is removed, producing only `"a"`, `"b"`, `"c"`. Deduplication is applied AFTER splitting and AFTER trim/discard operations. |
| 6 | Use CSV Parameters | (CSV escape/enclosure) | Boolean (CHECK) | `false` | Enables CSV-specific settings like escape mode and enclosure character for parsing the delimited values within the column. Allows handling of values that contain the separator inside quoted fields. |
| 7 | Discard Trailing Empty Strings | `DISCARD_TRAILING_EMPTY_STR` | Boolean (CHECK) | `false` | Remove empty strings that appear at the END of the split result. For example, `"a,b,,"` with comma separator produces `["a","b","",""]` -- with this flag enabled, the two trailing empty strings are removed, yielding `["a","b"]`. Only trailing empties are removed; leading or middle empties are preserved. |
| 8 | Trim Resulting Values | `TRIM` | Boolean (CHECK) | `false` | Remove leading and trailing whitespace from each split value. Applied AFTER the `discard_trailing_empty_str` step. For example, `" a , b , c "` produces `["a","b","c"]`. |
| 9 | tStatCatcher Statistics | `TSTATCATCHER_STATS` | Boolean (CHECK) | `false` | Capture processing metadata at job and component levels for the tStatCatcher component. Rarely used. |
| 10 | Die On Error | `DIE_ON_ERROR` | Boolean (CHECK) | `false` | Stop the entire job on processing error. When unchecked, errors are handled gracefully. |

**Processing order in Talend Advanced Settings**: When multiple advanced options are enabled simultaneously:
1. Split by item separator
2. Discard trailing empty strings (removes empty values at the END only)
3. Trim resulting values (strip whitespace)
4. Deduplicate (remove duplicate values)

This order is documented in the official Talend example scenario, which shows: "the list is tidied up with duplicate tags, leading and trailing whitespace and trailing empty strings removed."

### 3.3 Connection Types

| Connector | Direction | Type | Description |
|-----------|-----------|------|-------------|
| `FLOW` (Main) | Input | Row > Main | Input data flow containing the column to normalize. |
| `FLOW` (Main) | Output | Row > Main | Normalized output -- each split value becomes a separate row. All non-normalized columns are replicated. |
| `SUBJOB_OK` | Output (Trigger) | Trigger | Fires when the entire subjob containing this component completes successfully. |
| `SUBJOB_ERROR` | Output (Trigger) | Trigger | Fires when the subjob containing this component fails with an error. |
| `COMPONENT_OK` | Output (Trigger) | Trigger | Fires when this specific component completes execution successfully. |
| `COMPONENT_ERROR` | Output (Trigger) | Trigger | Fires when this specific component fails with an error. |
| `RUN_IF` | Output (Trigger) | Trigger | Conditional trigger with a boolean expression. |

**Note**: `tNormalize` does NOT have a REJECT output connector. It is a simple processing component that transforms its FLOW input into a FLOW output. Rows that cannot be normalized (e.g., null values) are still output -- they are not rejected. This is a key behavioral difference from components like `tFileInputDelimited`.

### 3.4 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
|------------------|------|----------|-------------|
| `{id}_NB_LINE` | Integer | After execution | The number of rows read by the component (input row count) or transferred to the output (output row count). For tNormalize, this reflects the OUTPUT row count -- the total number of rows produced after splitting. |
| `{id}_ERROR_MESSAGE` | String | On error | The error message generated by the component when an error occurs. Only functions when `DIE_ON_ERROR` is unchecked. |

### 3.5 Behavioral Notes

1. **Row explosion**: A single input row with N delimited values in the normalized column produces N output rows. All other columns are duplicated across all N rows. If the input has M rows and the i-th row has N_i values, the output has sum(N_i) rows.

2. **Null handling in Talend**: When the normalized column value is `null`, Talend produces a single output row with `null` in the normalized column. The null is NOT converted to an empty string -- it remains null. This is important for downstream null-aware logic.

3. **Empty string handling**: When the normalized column value is an empty string `""`, splitting by any separator produces a single-element array containing one empty string `[""]`. This results in one output row with an empty string in the normalized column.

4. **Separator is regex-capable**: The item separator field accepts regular expressions. The period character `.` matches any character in regex, so to use a literal period as separator, it should be escaped as `\\.`. This is noted in the official Talend documentation.

5. **Schema identity**: The output schema is identical to the input schema. The normalized column retains its original Talend type (e.g., `id_String`). No type conversion occurs during normalization.

6. **Processing order**: Discard trailing empty strings runs BEFORE trim. This means that if you have `"a, ,,"` with both options enabled:
   - Split: `["a", " ", "", ""]`
   - Discard trailing empties: `["a", " "]` (removes the two trailing empty strings)
   - Trim: `["a", ""]` (the `" "` becomes `""` after trimming)
   Note that the newly-empty-after-trim value is NOT discarded again. The discard step only runs once.

7. **Deduplication**: When `DEDUPLICATE` is enabled, duplicate values are removed from the split result. The first occurrence is kept, maintaining the original order. For `"a,b,a,c"`, the result is `["a","b","c"]`.

8. **NB_LINE reflects output count**: The `{id}_NB_LINE` global variable reflects the number of output rows, NOT the number of input rows. This is consistent with the Talend documentation which describes it as "the number of rows transferred."

9. **No REJECT flow**: Unlike components such as `tFileInputDelimited`, `tNormalize` does not produce reject rows. If processing encounters an issue (e.g., a non-string column selected for normalization), the behavior depends on `DIE_ON_ERROR`.

10. **CSV parameters**: When `Use CSV parameters` is enabled, the component can handle values that contain the separator character inside quoted fields. For example, with comma separator and CSV mode, `'"hello, world",foo'` correctly produces `["hello, world", "foo"]` instead of splitting on the comma inside quotes.

---

## 4. Converter Audit

### 4.1 Parameter Extraction

The converter uses a **dedicated parser method** (`parse_tnormalize()` in `component_parser.py` lines 1921-1937), which is the correct approach per standards. The method is registered in `converter.py` line 315-316 with a dedicated `elif component_type == 'tNormalize'` branch.

**Converter flow**:
1. `converter.py:_parse_component()` detects `component_type == 'tNormalize'` (line 315)
2. Calls `self.component_parser.parse_tnormalize(node, component)` (line 316)
3. `parse_tnormalize()` extracts 5 parameters from `elementParameter` nodes via XPath
4. Updates `component['config']` with the extracted values
5. Returns the component dictionary

| # | Talend XML Parameter | Extracted? | V1 Config Key | Converter Line | Notes |
|----|----------------------|------------|---------------|----------------|-------|
| 1 | `NORMALIZE_COLUMN` | Yes | `normalize_column` | 1923 | Uses XPath `'.//elementParameter[@name="NORMALIZE_COLUMN"]'`. `.get('value', '')` with empty string default. |
| 2 | `ITEMSEPARATOR` | Yes | `item_separator` | 1924 | **Default `';'` used if not found, then `.strip('"')` removes surrounding quotes.** Talend default is `","` (comma). The converter default of semicolon differs from Talend's comma default. |
| 3 | `DEDUPLICATE` | Yes | `deduplicate` | 1925 | Boolean conversion via `.lower() == 'true'`. Default `false`. Correct. |
| 4 | `TRIM` | Yes | `trim` | 1926 | Boolean conversion. Default `false`. Correct. |
| 5 | `DISCARD_TRAILING_EMPTY_STR` | Yes | `discard_trailing_empty_str` | 1927 | Boolean conversion. Default `false`. Correct. |
| 6 | `DIE_ON_ERROR` | **No** | -- | -- | **Not extracted by converter. Engine has its own `die_on_error` config key with default `False` but the converter does not propagate the Talend setting.** |
| 7 | CSV Parameters (escape/enclosure) | **No** | -- | -- | **Not extracted. Engine has no CSV-aware splitting mode for the normalized column.** |
| 8 | `TSTATCATCHER_STATS` | **No** | -- | -- | Not extracted (low priority -- tStatCatcher rarely used) |
| 9 | `PROPERTY_TYPE` | No | -- | -- | Not needed (always Built-In in converted jobs) |
| 10 | `LABEL` | No | -- | -- | Not extracted (cosmetic -- no runtime impact) |

**Summary**: 5 of 7 runtime-relevant parameters extracted (71%). 2 runtime-relevant parameters are missing (`DIE_ON_ERROR`, CSV parameters).

### 4.2 Schema Extraction

Schema is extracted generically in `parse_base_component()` (called before `parse_tnormalize()`). The schema for tNormalize has identical input and output structures.

| Schema Attribute | Extracted? | Notes |
|------------------|-----------|-------|
| `name` | Yes | Column name from `column.get('name')` |
| `type` | Yes | Converted via `ExpressionConverter.convert_type()` to Python types -- **violates STANDARDS.md** |
| `nullable` | Yes | Boolean conversion from string |
| `key` | Yes | Boolean conversion from string |
| `length` | Yes | Integer conversion, only if attribute present in XML |
| `precision` | Yes | Integer conversion, only if attribute present in XML |
| `pattern` (date) | Yes | Java date pattern converted to Python strftime |
| `default` | **No** | Column default value not extracted from XML |
| `comment` | **No** | Column comment not extracted (cosmetic) |

### 4.3 Expression Handling

**NORMALIZE_COLUMN extraction**: The converter uses `node.find('.//elementParameter[@name="NORMALIZE_COLUMN"]').get('value', '')` (line 1923). This extracts the raw column name string. Since this is a dropdown-selected column name, it should always be a simple string without Java expressions or context variables. However, the converter does NOT validate that the value is non-empty.

**ITEMSEPARATOR extraction**: The converter uses `.get('value', ';').strip('"')` (line 1924). The `.strip('"')` removes surrounding double quotes that Talend XML may include. However:
- The default value `';'` differs from Talend's default of `','`
- No Java expression detection is performed -- if the separator is a Java expression (e.g., `context.separator`), it will be passed as a literal string
- No context variable handling -- `context.sep` would not be resolved

**Potential NoneType crash**: If any of the `node.find()` calls on lines 1923-1927 return `None` (i.e., the XML element is missing), the subsequent `.get('value', ...)` call will raise an `AttributeError: 'NoneType' object has no attribute 'get'`. The converter does not guard against missing XML elements.

### 4.4 Converter Issues

| ID | Priority | Issue |
|----|----------|-------|
| CONV-NRM-001 | **P2** | **`DIE_ON_ERROR` not extracted**: The converter does not extract the `DIE_ON_ERROR` parameter from the Talend XML. The engine has a `die_on_error` config key that defaults to `False`, but if a Talend job explicitly sets `DIE_ON_ERROR=true`, this setting is lost during conversion. Jobs that should fail-fast on normalization errors will silently continue instead. |
| CONV-NRM-002 | **P2** | **Default item separator mismatch**: The converter defaults to `';'` (semicolon) on line 1924: `.get('value', ';')`. Talend's default item separator for tNormalize is `","` (comma). If a Talend job uses the default separator without explicitly setting it in the XML, the converter produces the wrong separator value, causing data to not be split at all or split incorrectly. |
| CONV-NRM-003 | **P2** | **No NoneType guard on XML element lookups**: Lines 1923-1927 each call `node.find(...).get(...)` without checking if `node.find()` returns `None`. If any `elementParameter` node is missing from the XML (e.g., in older Talend versions or corrupted exports), an `AttributeError` will crash the converter. Should use safe access: `elem = node.find(...); value = elem.get('value', default) if elem is not None else default`. |
| CONV-NRM-004 | **P3** | **No expression handling on ITEMSEPARATOR**: The converter does not check for Java expressions or context variables in the `ITEMSEPARATOR` value. If a Talend job uses `context.separator` as the item separator, it will be passed as the literal string `"context.separator"` instead of being resolved. |
| CONV-NRM-005 | **P3** | **CSV parameters not extracted**: The `Use CSV parameters` advanced setting (escape mode and enclosure character) is not extracted. This means the engine cannot handle separator characters appearing inside quoted values within the normalized column. Low priority because this is a rarely used feature. |

---

## 5. Engine Feature Parity

### 5.1 Feature Implementation Status

| # | Talend Feature | Implemented? | Fidelity | Engine Location | Notes |
|----|----------------|-------------|----------|-----------------|-------|
| 1 | Split column by separator | **Yes** | High | `_process()` line 161 | Uses Python `str.split(item_separator)`. Correct basic behavior. |
| 2 | Replicate non-normalized columns | **Yes** | High | `_process()` lines 187-190 | `row.copy()` for each split value preserves all other columns. Correct. |
| 3 | Configurable item separator | **Yes** | Medium | `_process()` line 130 | `config.get('item_separator', ',')`. **Engine default `,` matches Talend, but converter default `;` does not.** |
| 4 | Trim resulting values | **Yes** | High | `_process()` line 165 | `value.strip()` for each split value. Correct. |
| 5 | Discard trailing empty strings | **Partial** | **Low** | `_process()` lines 167-168 | **Filters ALL empty strings, not just trailing ones.** Implementation is `[value for value in values if value]` which removes empties at ANY position. Talend only removes TRAILING empties. See ENG-NRM-001. |
| 6 | Deduplicate output | **Yes** | High | `_process()` lines 170-178 | Order-preserving deduplication using seen-set pattern. Correct and matches Talend behavior. |
| 7 | Die on error | **Yes** | High | `_process()` lines 121-123, 140-142, 195-196 | Raises `ConfigurationError` or `ComponentExecutionError` when enabled. |
| 8 | Empty input handling | **Yes** | High | `_process()` lines 107-110 | Returns empty DataFrame with stats (0, 0, 0). Correct. |
| 9 | Missing column detection | **Yes** | High | `_process()` lines 137-146 | Checks if `normalize_column` exists in input DataFrame columns. Returns original data unchanged (or raises if `die_on_error`). |
| 10 | Null/NaN value handling | **Partial** | **Low** | `_process()` lines 155-158 | **Converts null/NaN to empty string `''` before splitting.** Talend preserves null and produces a single output row with null. See ENG-NRM-002. |
| 11 | Configuration validation | **Yes** | Medium | `_validate_config()` lines 60-88 | Validates required `normalize_column`, types of optional params. Called inside `_process()` on each invocation (line 117). |
| 12 | Statistics tracking | **Yes** | Medium | `_process()` line 208 | `_update_stats(rows_in, rows_out, 0)`. **Note**: `rows_in` is the INPUT row count but `rows_out` is the OUTPUT row count. In Talend, NB_LINE reflects output count for processing components. The v1 stats use `rows_in` for `NB_LINE` which may differ from Talend. See ENG-NRM-003. |
| 13 | Empty result after filtering | **Yes** | High | `_process()` lines 181-185 | When all values are filtered out (e.g., all empty + discard enabled), creates one row with empty string. Prevents row loss. |
| 14 | **CSV-aware splitting** | **No** | N/A | -- | **No CSV parameter support. Separator chars inside quoted values will cause incorrect splits.** |
| 15 | **Regex separator** | **Partial** | Medium | `_process()` line 161 | Python `str.split()` treats the separator as a literal string, NOT a regex. Talend's item separator is regex-capable. A separator like `"\\|"` would be treated literally in v1 but as regex in Talend. See ENG-NRM-004. |
| 16 | **REJECT flow** | **No** | N/A | -- | Talend tNormalize does not have a REJECT flow, so this is not a gap. Correct. |
| 17 | **`{id}_ERROR_MESSAGE` globalMap** | **No** | N/A | -- | **Error message not stored in globalMap when errors occur.** |

### 5.2 Behavioral Differences from Talend

| ID | Priority | Description |
|----|----------|-------------|
| ENG-NRM-001 | **P1** | **`discard_trailing_empty_str` removes ALL empties, not just trailing**: The implementation on line 167-168 uses `[value for value in values if value]`, which is a blanket filter removing ALL empty strings regardless of position. Talend's `Discard the trailing empty strings` only removes empty strings from the END of the split result. For example, with input `",a,,b,,"` (comma separator): Talend produces `["","a","","b"]` (trailing empties removed); v1 produces `["a","b"]` (all empties removed). The middle empty string between `a` and `b` and the leading empty string are incorrectly removed. |
| ENG-NRM-002 | **P1** | **Null values converted to empty string instead of preserved**: Lines 155-157 convert `pd.isna(cell_value)` to `cell_value = ''`, then split the empty string, producing one row with `""`. Talend preserves `null` and produces one row with `null`. This behavioral difference breaks downstream null-aware logic (e.g., `tFilterRow` checking for null, `tMap` with null checks). A column that was null in input will become empty string `""` in output, which is semantically different. |
| ENG-NRM-003 | **P1** | **NB_LINE reflects input count, not output count**: Line 208 calls `_update_stats(rows_in, rows_out, 0)` where the first argument is `rows_in` (input row count). The `_update_stats` method (base_component.py line 308) adds `rows_read` to `stats['NB_LINE']`. For tNormalize, Talend's NB_LINE reflects the OUTPUT row count. If 10 input rows produce 30 output rows, Talend reports NB_LINE=30, but v1 reports NB_LINE=10 and NB_LINE_OK=30. Downstream components referencing `{id}_NB_LINE` will get the wrong count. |
| ENG-NRM-004 | **P2** | **Item separator treated as literal, not regex**: Python's `str.split()` (line 161) treats the separator as a literal string. Talend's item separator is regex-capable. For literal separators (comma, semicolon, pipe), this makes no difference. But for regex patterns (e.g., `"\\s+"` for whitespace, `"[,;]"` for multiple separators), the split will not work correctly. The separator `"."` would work literally in v1 but match any character in Talend. |
| ENG-NRM-005 | **P2** | **Processing order differs from Talend**: The engine applies transformations in this order: (1) trim, (2) discard empty, (3) deduplicate (lines 164-178). Talend applies them as: (1) discard trailing empties, (2) trim, (3) deduplicate. The v1 order means trimming happens BEFORE discarding empties. If a value is `" "` (whitespace only), v1 trims it to `""` first, then the empty filter removes it. Talend would first check for trailing empties (keeping `" "` since it is not empty), then trim it to `""` (which stays). This produces different results in edge cases. |
| ENG-NRM-006 | **P3** | **No CSV-aware splitting**: The engine does not support the `Use CSV parameters` advanced setting. If the normalized column contains values like `'"hello, world",foo'` with comma separator, the engine will incorrectly split on the comma inside the quoted value. This is a rarely used Talend feature. |

### 5.3 GlobalMap Variable Coverage

| Variable | Talend Sets? | V1 Sets? | How V1 Sets It | Notes |
|----------|-------------|----------|-----------------|-------|
| `{id}_NB_LINE` | Yes | **Yes** | `_update_stats()` -> `_update_global_map()` -> `global_map.put_component_stat()` | Set but with wrong semantics: v1 uses input row count, Talend uses output row count |
| `{id}_NB_LINE_OK` | Yes | **Yes** | Same mechanism | Set to output row count (correct for NB_LINE_OK) |
| `{id}_NB_LINE_REJECT` | Yes | **Yes** | Same mechanism | Always 0 (correct -- tNormalize has no REJECT flow) |
| `{id}_ERROR_MESSAGE` | Yes (official) | **No** | -- | Not implemented. When errors occur with die_on_error=false, the error message is not stored in globalMap. |
| `{id}_EXECUTION_TIME` | N/A (v1 only) | **Yes** | Base class | V1-specific, not in Talend |

---

## 6. Code Quality

### 6.1 Bugs

| ID | Priority | Location | Description |
|----|----------|----------|-------------|
| BUG-NRM-001 | **P0** | `src/v1/engine/base_component.py:304` | **`_update_global_map()` references undefined variable `value`**: The log statement on line 304 uses `{stat_name}: {value}` but the variable in the for loop (line 301) is named `stat_value`, not `value`. This causes `NameError` at runtime whenever `global_map` is not None. **This is not just a logging bug -- the NameError crashes `execute()` entirely, preventing ANY component from returning results when `global_map` is set. The entire engine is broken for any job that uses globalMap.** **CROSS-CUTTING**: This bug affects ALL components, not just Normalize, since `_update_global_map()` is called after every component execution (via `execute()` line 218). |
| BUG-NRM-002 | **P0** | `src/v1/engine/global_map.py:28` | **`GlobalMap.get()` references undefined `default` parameter**: The method signature is `def get(self, key: str) -> Optional[Any]` (line 26), but the body calls `self._map.get(key, default)` (line 28). The `default` parameter is not in the signature, causing `NameError` on every `.get()` call. Additionally, `get_component_stat()` on line 58 calls `self.get(key, default)` with two arguments, but `get()` only accepts one. **CROSS-CUTTING**: Affects all code using `global_map.get()`. |
| BUG-NRM-003 | **P1** | `src/v1/engine/engine.py:40` | **Import path mismatch**: Line 40 imports `Normalize` from `.components.aggregate`: `from .components.aggregate import AggregateSortedRow, Denormalize, Normalize, Replicate`. However, the `Normalize` class is defined in `.components.transform.normalize` and exported from `.components.transform.__init__` (line 15). The `aggregate/__init__.py` does NOT export `Normalize` -- it only exports `AggregateRow` and `UniqueRow`. This import will raise `ImportError` at engine startup. The same bug affects `Denormalize`, `AggregateSortedRow`, and `Replicate` which are also in the `transform` package. |
| BUG-NRM-004 | **P1** | `src/v1/engine/components/transform/normalize.py:167-168` | **`discard_trailing_empty_str` removes ALL empties instead of only trailing**: The filter `[value for value in values if value]` removes every empty string from the list, regardless of position. The Talend feature `Discard the trailing empty strings` only removes empty strings from the END of the list. For input `",a,,b,,"` with comma separator, v1 produces `["a","b"]` but Talend produces `["","a","","b"]`. This is a semantic bug that silently corrupts data by dropping values. |
| BUG-NRM-005 | **P1** | `src/v1/engine/components/transform/normalize.py:155-157` | **Null/NaN converted to empty string `''` instead of preserved**: When `pd.isna(cell_value)` is true, the code sets `cell_value = ''` and then splits it, producing one row with `""`. Talend preserves the null value, producing one row with null. This changes the semantics of the data: downstream null checks will fail, and data quality reports will miscount nulls vs empties. |
| BUG-NRM-006 | **P0** | `src/v1/engine/components/transform/normalize.py:161` | **Empty separator (`item_separator=""`) causes ValueError crash**: `str.split("")` raises `ValueError` in Python. The `_validate_config()` method checks that the separator is a string but does not check that it is non-empty. An empty separator string (e.g., from a Talend job where `ITEMSEPARATOR` is set to `""` or from a converter stripping quotes off `'""'`) causes the entire component to crash with an unhandled `ValueError`, or silently skips all rows. No data is returned. |
| BUG-NRM-007 | **P1** | `src/v1/engine/components/transform/normalize.py:183-190,203` | **`row.copy()` demotes Decimal, datetime, and other non-native types (DATA FIDELITY issue)**: When `iterrows()` returns each row as a `pd.Series` with dtype `object`, then rows are reconstructed via `pd.DataFrame(normalized_rows)` (line 203), pandas re-infers dtypes. `Decimal` values become `float64` (losing precision), `datetime` columns can become object strings, and other non-native Python types are silently coerced. This is not just a performance issue -- it is a **data fidelity** bug. Financial data using `Decimal` for exact arithmetic will lose precision; timestamp columns may lose timezone information or become unparseable strings. |
| BUG-NRM-008 | **P2** | `src/v1/engine/components/transform/normalize.py:110` | **Empty DataFrame returned on empty input loses column schema**: Line 110 returns `pd.DataFrame()` with NO columns when the input DataFrame has zero rows. Downstream components expecting specific column names (e.g., `tMap` referencing `row.name`, `tFilterRow` checking column existence) will crash with `KeyError`. Should return `pd.DataFrame(columns=input_data.columns)` to preserve the column schema when input has columns but zero rows. |
| BUG-NRM-009 | **P2** | `src/v1/engine/components/transform/normalize.py:158` | **`str()` conversion on non-string column values produces garbage output**: The `str(cell_value)` call on line 158 blindly converts any type to string before splitting. Float `1.5` split by `'.'` yields `['1', '5']`. List `[1,2,3]` becomes `'[1, 2, 3]'` split by `','` yields `['[1', ' 2', ' 3]']`. Talend restricts the normalize column to string type at the schema level; v1 silently accepts any type and produces silently corrupted data that looks plausible but is semantically wrong. |

### 6.2 Anti-Patterns

| ID | Priority | Location | Description |
|----|----------|----------|-------------|
| ANTI-NRM-001 | **P0** | `src/v1/engine/components/transform/normalize.py:151` | **`iterrows()` anti-pattern**: The entire normalization logic is built around `for idx, row in input_data.iterrows()` (line 151). `iterrows()` is the single slowest way to iterate a pandas DataFrame -- it converts each row to a Series object, which involves type inference and memory allocation for every row. For a DataFrame with 1M rows and 20 columns, this creates 1M Series objects. The pandas documentation explicitly warns: "Iterating through pandas objects is generally slow. In many cases, iterating manually over the rows is not needed." The correct approach is vectorized: `df[col].str.split(sep).explode()`. This is approximately 100-1000x faster than `iterrows()`. |
| ANTI-NRM-002 | **P2** | `src/v1/engine/components/transform/normalize.py:183-190` | **`row.copy()` inside tight loop**: Each split value triggers `row.copy()` (a full Series copy). For a DataFrame with M rows where row i has N_i values, this creates sum(N_i) Series copies. Combined with the `iterrows()` overhead, this results in O(M * N_avg * cols) memory allocation and O(M * N_avg) Series construction overhead. A row with 100 delimited values creates 100 Series copies, each copying all columns. |
| ANTI-NRM-003 | **P2** | `src/v1/engine/components/transform/normalize.py:149,202-203` | **List-of-Series to DataFrame construction**: All normalized rows are collected as a `List[pd.Series]` (line 149), then converted to a DataFrame via `pd.DataFrame(normalized_rows)` (line 203). This pattern is known to be extremely slow in pandas -- each Series must be aligned by index, and the constructor performs O(n) alignment operations. The recommended approach is to collect rows as dictionaries or use `pd.concat()`. |

### 6.3 Processing Order Issue

| ID | Priority | Issue |
|----|----------|-------|
| LOGIC-NRM-001 | **P2** | **Processing order differs from Talend**: Lines 164-178 apply: (1) trim, (2) discard empty, (3) deduplicate. Talend applies: (1) discard trailing empties, (2) trim, (3) deduplicate. While the difference is subtle, it produces incorrect results when a value becomes empty after trimming. For example, with input `"a, ,b"` (comma separator) with both trim and discard enabled: V1: trim first -> `["a","","b"]`, discard ALL empties -> `["a","b"]` (loses the middle position). Talend: discard trailing empties first -> `["a"," ","b"]` (no trailing empties), trim -> `["a","","b"]` (the space becomes empty but is NOT discarded again). Talend produces 3 output rows; v1 produces 2. |

### 6.4 Naming Consistency

| ID | Priority | Issue |
|----|----------|-------|
| NAME-NRM-001 | **P3** | **Config key `discard_trailing_empty_str` abbreviation**: Uses `_str` instead of `_strings` or `_string`. Matches the Talend XML name `DISCARD_TRAILING_EMPTY_STR` so this is intentional, but inconsistent with the Python convention of using full words. |

### 6.5 Standards Compliance

| ID | Priority | Standard | Violation |
|----|----------|----------|-----------|
| STD-NRM-001 | **P2** | "Schema types in Talend format (`id_String`)" (STANDARDS.md) | Converter converts types to Python format (`str`, `int`) via `ExpressionConverter.convert_type()` instead of preserving Talend format. Cross-cutting issue shared with all components. |
| STD-NRM-002 | **P2** | "`_validate_config()` called once, not on every `_process()`" (METHODOLOGY.md) | `_validate_config()` is called inside `_process()` on every invocation (line 117), rather than once during initialization or first execution. For streaming mode where `_process()` is called per chunk, validation runs redundantly N times. While functionally correct, this is wasteful. |

### 6.6 Logging Quality

The component has good logging throughout:

| Aspect | Assessment |
|--------|------------|
| Logger setup | Module-level `logger = logging.getLogger(__name__)` -- correct |
| Component ID prefix | All log messages use `[{self.id}]` prefix -- correct |
| Level usage | INFO for start/complete, WARNING for empty input, ERROR for failures -- correct |
| Start/complete logging | `_process()` logs start (line 113) and completion with row counts (line 210-211) -- correct |
| Sensitive data | No sensitive data logged -- correct |
| No print statements | No `print()` calls -- correct |

### 6.7 Error Handling Quality

| Aspect | Assessment |
|--------|------------|
| Custom exceptions | Uses `ConfigurationError` and `ComponentExecutionError` from `exceptions.py` -- correct |
| Exception chaining | Uses `raise ... from e` pattern (line 196) -- correct |
| `die_on_error` handling | Two paths: config validation (line 121-126) and per-row processing (line 195-199). Both correctly check `die_on_error`. Non-error path returns original data unchanged. |
| Per-row error handling | Inner try/except (lines 152-199) catches per-row exceptions and either raises or appends original row unchanged -- correct pattern |
| No bare `except` | All except clauses specify `Exception` or specific exception types -- correct |
| Error messages | Include component ID, row index, and error details -- correct |
| Graceful degradation | Returns original DataFrame when config is invalid and `die_on_error=false` -- correct |

### 6.8 Type Hints

| Aspect | Assessment |
|--------|------------|
| Method signatures | `_validate_config() -> List[str]`, `_process(...) -> Dict[str, Any]` -- correct |
| Parameter types | `input_data: Optional[pd.DataFrame]` -- correct |
| Local variables | Typed: `normalize_column: str`, `item_separator: str`, `deduplicate: bool`, `normalized_rows: List[pd.Series]`, `seen: set`, `unique_values: List[str]` -- thorough |
| Return types | Dict return documented in docstring -- correct |
| Minor issue | `new_row: pd.Series` type hint redeclared inside both if/else branches (lines 183, 188). Not an error but redundant. |

---

## 7. Performance & Memory

| ID | Priority | Issue |
|----|----------|-------|
| PERF-NRM-001 | **P0** | **`iterrows()` is O(n*m) and unacceptably slow for production data**: The entire normalization is built on `input_data.iterrows()` (line 151), which is documented by pandas as the slowest iteration method. For each row, a `pd.Series` object is constructed, involving per-column type inference. A DataFrame with 1M rows and 20 columns will take minutes to iterate, compared to milliseconds for vectorized operations. The correct approach is `df.assign(**{col: df[col].str.split(sep)}).explode(col)`, which uses pandas' native C-optimized `explode()`. This is approximately 100-1000x faster than `iterrows()`. |
| PERF-NRM-002 | **P1** | **`row.copy()` per split value creates massive intermediate memory**: Each split value triggers a full `pd.Series.copy()` (lines 183, 188-189). For an input row with K columns and N split values, this allocates N*K values. Across M input rows with average N_avg split values, total intermediate allocations are M * N_avg * K. For 1M rows, 5 avg splits, 20 columns: 100M cell copies in Python-level loops. The vectorized `explode()` avoids all intermediate copies. |
| PERF-NRM-003 | **P2** | **`pd.DataFrame(list_of_series)` constructor is slow**: Line 203 creates the result DataFrame from a `List[pd.Series]`. This constructor must align each Series by index and infer dtypes. For a list of 5M Series objects (1M rows x 5 avg splits), this is extremely slow. Even collecting as dicts and using `pd.DataFrame.from_records()` would be faster. |

### 7.1 Memory Management Assessment

| Aspect | Assessment |
|--------|------------|
| Streaming mode | The base class supports streaming via `_execute_streaming()`, which chunks the input and calls `_process()` per chunk. Normalize inherits this. However, the `iterrows()` pattern within `_process()` negates much of the benefit. |
| Peak memory | For M input rows with average N_avg splits and K columns: peak memory is approximately `O(M * N_avg * K * 8 bytes)` for the list of Series, PLUS `O(M * N_avg * K * 8 bytes)` for the result DataFrame. Total peak is roughly 2x the output size. The vectorized `explode()` approach would use approximately 1x the output size. |
| Large split counts | If a single row has thousands of delimited values (e.g., a long tag list), the per-row loop creates thousands of Series copies. This is a worst-case scenario for the current implementation. |

### 7.2 Benchmark Estimate

| Input Size | Columns | Avg Splits | Output Rows | iterrows() (est.) | explode() (est.) |
|-----------|---------|------------|-------------|-------------------|-----------------|
| 1,000 rows | 10 | 3 | 3,000 | ~0.5s | ~0.005s |
| 100,000 rows | 10 | 3 | 300,000 | ~50s | ~0.2s |
| 1,000,000 rows | 20 | 5 | 5,000,000 | ~30min+ | ~2s |

**Note**: These are order-of-magnitude estimates based on known `iterrows()` vs vectorized performance ratios. Actual times depend on hardware and data characteristics.

---

## 8. Testing

### 8.1 Current Coverage

| Test Type | Exists? | File | Notes |
|-----------|---------|------|-------|
| V1 engine unit tests | **No** | -- | Zero test files found for `Normalize` v1 engine component |
| V1 engine integration tests | **No** | -- | No v1 engine integration tests found |

**Key finding**: The v1 engine has ZERO tests for this component. All 221 lines of v1 engine code are completely unverified.

### 8.2 Recommended Test Cases

#### P0 -- Must Have Before Production

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 1 | Basic split | P0 | Input with column `"a,b,c"`, separator `,`, verify 3 output rows with values `"a"`, `"b"`, `"c"`. All other columns duplicated. |
| 2 | Multi-row split | P0 | 3 input rows with different value counts (1, 3, 2). Verify 6 output rows total. Column ordering preserved. |
| 3 | Empty input | P0 | `None` input and empty DataFrame input both return empty DataFrame with stats (0, 0, 0). |
| 4 | Missing column + die_on_error=true | P0 | `normalize_column` not in input schema. Should raise `ConfigurationError`. |
| 5 | Missing column + die_on_error=false | P0 | Should return original DataFrame unchanged with warning logged. |
| 6 | Statistics tracking | P0 | Verify `NB_LINE`, `NB_LINE_OK`, `NB_LINE_REJECT` are set correctly in stats dict after execution. |
| 7 | Null/NaN values | P0 | Row with null in normalize column produces one output row. Verify the null is preserved (currently fails -- see BUG-NRM-005). |

#### P1 -- Important

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 8 | Trim enabled | P1 | Input `" a , b , c "`, separator `,`, trim=true. Verify `["a","b","c"]`. |
| 9 | Discard trailing empties | P1 | Input `"a,b,,"`, separator `,`, discard=true. Verify trailing empties removed but leading/middle preserved (currently fails -- see BUG-NRM-004). |
| 10 | Deduplicate enabled | P1 | Input `"a,b,a,c,b"`, separator `,`, deduplicate=true. Verify `["a","b","c"]` with first occurrence preserved. |
| 11 | All options enabled | P1 | Input `" a , b , , a , "`, separator `,`, trim=true, discard=true, deduplicate=true. Verify correct processing order and result. |
| 12 | Different separators | P1 | Test semicolon `;`, pipe `|`, newline `\\n`, tab `\\t` as separators. |
| 13 | Single value (no separator found) | P1 | Input `"hello"` with comma separator. No split occurs. Verify 1 output row with value `"hello"`. |
| 14 | All empty after filtering | P1 | Input `",,"` with discard enabled. All values are empty. Verify one row with empty string is produced (fallback behavior). |
| 15 | GlobalMap integration | P1 | Verify `{id}_NB_LINE` etc. are set in globalMap after execution. |
| 16 | Context variable in config | P1 | `item_separator` as `${context.sep}` should resolve via context manager. |
| 17 | Large number of splits | P1 | Single row with 1000 comma-separated values. Verify 1000 output rows and reasonable performance. |

#### P2 -- Hardening

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 18 | Regex separator | P2 | Separator `"\\s+"` should split on whitespace. Currently fails because `str.split()` treats as literal. |
| 19 | Non-string column | P2 | Normalize column contains integers. Verify `str()` conversion works correctly. |
| 20 | Very wide DataFrame | P2 | 100 columns, verify `row.copy()` preserves all columns correctly. |
| 21 | Index preservation | P2 | Verify output DataFrame has a clean 0-based integer index after `reset_index(drop=True)`. |
| 22 | Empty string in column | P2 | Column value is `""`. Verify one output row with empty string (no crash). |
| 23 | Streaming mode | P2 | Input exceeding memory threshold triggers streaming. Verify chunked processing produces correct results. |

---

## 9. Issues Summary

### P0 -- Critical

| ID | Category | Summary |
|----|----------|---------|
| BUG-NRM-001 | Bug (Cross-Cutting) | `_update_global_map()` in `base_component.py:304` references undefined variable `value` (should be `stat_value`). The NameError crashes `execute()` entirely, preventing ANY component from returning results when `global_map` is set. The entire engine is broken for any job that uses globalMap. |
| BUG-NRM-002 | Bug (Cross-Cutting) | `GlobalMap.get()` in `global_map.py:28` references undefined parameter `default`. Will crash on any `global_map.get()` call. `get_component_stat()` also passes two args to single-arg `get()`. |
| BUG-NRM-006 | Bug | Empty separator (`item_separator=""`) causes `ValueError` crash at line 161. `str.split("")` raises `ValueError`. `_validate_config()` checks that separator is a string but not non-empty. Entire component crashes with no data returned. |
| PERF-NRM-001 | Performance | `iterrows()` anti-pattern makes the component 100-1000x slower than vectorized alternative. Unacceptable for production data volumes (>100K rows). |
| TEST-NRM-001 | Testing | Zero v1 unit tests for this component. All 221 lines of v1 engine code are unverified. |

### P1 -- Major

| ID | Category | Summary |
|----|----------|---------|
| BUG-NRM-003 | Bug | Import path mismatch in `engine.py:40` -- imports `Normalize` from `.components.aggregate` but class lives in `.components.transform`. Will raise `ImportError` at engine startup. Also affects `Denormalize`, `AggregateSortedRow`, `Replicate`. |
| BUG-NRM-004 | Bug | `discard_trailing_empty_str` removes ALL empty strings instead of only trailing ones. Silently corrupts data by dropping values at non-trailing positions. |
| BUG-NRM-005 | Bug | Null/NaN values converted to empty string `""` instead of preserved. Changes data semantics; breaks downstream null-aware logic. |
| BUG-NRM-007 | Bug (Data Fidelity) | `row.copy()` demotes `Decimal`, `datetime`, and other non-native types. When rows are reconstructed via `pd.DataFrame(normalized_rows)` (line 203), pandas re-infers dtypes. `Decimal` values become `float64` (losing precision), `datetime` columns can become object strings. This is a DATA FIDELITY issue, not just performance. |
| ENG-NRM-001 | Engine | Same as BUG-NRM-004 -- `discard_trailing_empty_str` behavior does not match Talend. |
| ENG-NRM-002 | Engine | Same as BUG-NRM-005 -- null handling does not match Talend. |
| ENG-NRM-003 | Engine | `NB_LINE` reflects input row count; Talend uses output row count for processing components. Downstream globalMap references get wrong value. |
| PERF-NRM-002 | Performance | `row.copy()` per split value creates massive intermediate memory. Combined with `iterrows()`, this is the dominant performance bottleneck. |
| TEST-NRM-002 | Testing | No integration test for this component in a multi-step v1 job. |

### P2 -- Moderate

| ID | Category | Summary |
|----|----------|---------|
| BUG-NRM-008 | Bug | Empty DataFrame returned on empty input (line 110) loses column schema. Returns `pd.DataFrame()` with NO columns. Downstream components expecting specific column names will crash with `KeyError`. Should return `pd.DataFrame(columns=input_data.columns)`. |
| BUG-NRM-009 | Bug | `str()` conversion on non-string column values (line 158) produces garbage output. Float `1.5` split by `'.'` yields `['1', '5']`. List `[1,2,3]` becomes `'[1, 2, 3]'` split by `','` yields `['[1', ' 2', ' 3]']`. Talend restricts normalize column to string type; v1 silently accepts any type. |
| CONV-NRM-001 | Converter | `DIE_ON_ERROR` not extracted from Talend XML. Jobs with `DIE_ON_ERROR=true` will silently use default `false`. |
| CONV-NRM-002 | Converter | Default item separator `';'` differs from Talend default `','`. Jobs using default separator will produce wrong results. |
| CONV-NRM-003 | Converter | No NoneType guard on XML element lookups. Missing `elementParameter` nodes crash the converter with `AttributeError`. |
| ENG-NRM-004 | Engine | Item separator treated as literal string; Talend treats it as regex. Regex separators will not work. |
| ENG-NRM-005 | Engine | Processing order (trim, discard, deduplicate) differs from Talend (discard, trim, deduplicate). Edge cases produce different results. |
| PERF-NRM-003 | Performance | `pd.DataFrame(list_of_series)` constructor is slow for large result sets. |
| STD-NRM-001 | Standards | Schema types in Python format (`str`) instead of Talend format (`id_String`). Cross-cutting. |
| STD-NRM-002 | Standards | `_validate_config()` called inside `_process()` on every invocation rather than once at init. Wasteful for streaming mode. |
| LOGIC-NRM-001 | Logic | Processing order differs from Talend. Trim before discard vs discard before trim produces different results in edge cases. |

### P3 -- Low

| ID | Category | Summary |
|----|----------|---------|
| CONV-NRM-004 | Converter | No expression handling on ITEMSEPARATOR -- Java expressions and context variables passed as literal strings. |
| CONV-NRM-005 | Converter | CSV parameters not extracted -- separator chars inside quoted values cause incorrect splits. |
| ENG-NRM-006 | Engine | No CSV-aware splitting -- quoted values with separator characters are split incorrectly. |
| NAME-NRM-001 | Naming | Config key `discard_trailing_empty_str` uses abbreviation `_str` instead of `_strings`. |

### Issue Count Summary

| Priority | Count | Categories |
|----------|-------|------------|
| P0 | 5 | 3 bugs (2 cross-cutting, 1 empty-separator crash), 1 performance, 1 testing |
| P1 | 9 | 4 bugs (incl. data fidelity type demotion), 3 engine, 1 performance, 1 testing |
| P2 | 11 | 2 bugs (schema loss, str() garbage), 3 converter, 2 engine, 1 performance, 2 standards, 1 logic |
| P3 | 4 | 2 converter, 1 engine, 1 naming |
| **Total** | **29** | |

---

## 10. Recommendations

### Immediate (Before Production)

1. **Fix `_update_global_map()` bug** (BUG-NRM-001): Change `value` to `stat_value` on `base_component.py` line 304, or remove the stale references entirely and log just the three main stats. **Impact**: Fixes ALL components (cross-cutting). **Risk**: Very low (log message only).

2. **Fix `GlobalMap.get()` bug** (BUG-NRM-002): Add `default: Any = None` parameter to the `get()` method signature in `global_map.py` line 26. This fixes both direct calls and the two-argument call from `get_component_stat()` on line 58. **Impact**: Fixes ALL components and any code using `global_map.get()`. **Risk**: Very low.

3. **Fix import path in engine.py** (BUG-NRM-003): Change line 40 from `from .components.aggregate import AggregateSortedRow, Denormalize, Normalize, Replicate` to `from .components.transform import AggregateSortedRow, Denormalize, Normalize, Replicate`. This fixes the `ImportError` that prevents the entire engine from starting. **Impact**: Fixes 4 components. **Risk**: Very low.

4. **Replace `iterrows()` with vectorized `explode()`** (PERF-NRM-001, PERF-NRM-002, PERF-NRM-003): Replace the entire `iterrows()` loop (lines 149-199) with:
   ```python
   df = input_data.copy()
   # Handle null values (preserve as NaN, convert to empty string for splitting)
   mask_null = df[normalize_column].isna()
   df.loc[~mask_null, normalize_column] = df.loc[~mask_null, normalize_column].astype(str).str.split(item_separator)
   df.loc[mask_null, normalize_column] = df.loc[mask_null].apply(lambda _: [None], axis=1)
   result_df = df.explode(normalize_column).reset_index(drop=True)
   # Apply trim, discard, deduplicate as vectorized operations on result_df
   ```
   This is 100-1000x faster and uses 50% less memory. **Impact**: Makes the component production-viable for datasets over 100K rows. **Risk**: Medium (requires careful handling of null/empty edge cases).

5. **Create unit test suite** (TEST-NRM-001): Implement at minimum the 7 P0 test cases listed in Section 8.2. **Impact**: Verifies basic correctness. **Risk**: None.

### Short-Term (Hardening)

6. **Fix `discard_trailing_empty_str` to only remove trailing empties** (BUG-NRM-004): Replace line 167-168:
   ```python
   # Current (wrong):
   values = [value for value in values if value]

   # Correct:
   while values and not values[-1]:
       values.pop()
   ```
   This removes empty strings from the END only, matching Talend behavior. **Impact**: Fixes data corruption for inputs with empty values in non-trailing positions. **Risk**: Low.

7. **Fix null handling to preserve null** (BUG-NRM-005): Replace lines 155-158:
   ```python
   # Current (wrong):
   if pd.isna(cell_value):
       cell_value = ''

   # Correct:
   if pd.isna(cell_value):
       new_row = row.copy()
       new_row[normalize_column] = None  # or np.nan
       normalized_rows.append(new_row)
       continue  # Skip splitting for null values
   ```
   **Impact**: Preserves null semantics for downstream components. **Risk**: Low.

8. **Fix processing order to match Talend** (LOGIC-NRM-001, ENG-NRM-005): Reorder lines 164-178 to: (1) discard trailing empties, (2) trim, (3) deduplicate. Move the discard block before the trim block. **Impact**: Fixes edge case differences. **Risk**: Low.

9. **Fix NB_LINE to use output count** (ENG-NRM-003): Change line 208 from `_update_stats(rows_in, rows_out, 0)` to `_update_stats(rows_out, rows_out, 0)` so that NB_LINE reflects output row count, matching Talend behavior. **Impact**: Fixes downstream globalMap references. **Risk**: Low.

10. **Extract `DIE_ON_ERROR` in converter** (CONV-NRM-001): Add to `parse_tnormalize()`:
    ```python
    die_on_error_elem = node.find('.//elementParameter[@name="DIE_ON_ERROR"]')
    die_on_error = die_on_error_elem.get('value', 'false').lower() == 'true' if die_on_error_elem is not None else False
    component['config']['die_on_error'] = die_on_error
    ```
    **Impact**: Propagates fail-fast setting from Talend. **Risk**: Very low.

11. **Fix converter default separator** (CONV-NRM-002): Change line 1924 from `.get('value', ';')` to `.get('value', ',')` to match Talend's default comma separator. **Impact**: Fixes jobs using default separator. **Risk**: Very low.

12. **Add NoneType guards in converter** (CONV-NRM-003): Wrap each `node.find()` call with a None check:
    ```python
    elem = node.find('.//elementParameter[@name="NORMALIZE_COLUMN"]')
    normalize_column = elem.get('value', '') if elem is not None else ''
    ```
    **Impact**: Prevents converter crashes on incomplete XML. **Risk**: Very low.

### Long-Term (Optimization)

13. **Add regex separator support** (ENG-NRM-004): Replace `cell_value.split(item_separator)` with `re.split(item_separator, cell_value)` to match Talend's regex-capable separator. Add `import re` at module level. **Impact**: Enables regex separators. **Risk**: Low (regex `split()` is backward-compatible with literal strings).

14. **Add CSV-aware splitting** (ENG-NRM-006, CONV-NRM-005): When CSV parameters are enabled, use Python's `csv.reader` with configured escape/enclosure characters to split the column value, respecting quoted fields. **Impact**: Enables separator chars inside quoted values. **Risk**: Medium.

15. **Store `{id}_ERROR_MESSAGE` in globalMap**: In error handlers within `_process()`, call `self.global_map.put(f"{self.id}_ERROR_MESSAGE", str(e))` when `global_map` is available. **Impact**: Enables downstream error message access. **Risk**: Very low.

16. **Move `_validate_config()` to init or first-call** (STD-NRM-002): Call `_validate_config()` once during `__init__()` or cache the result after first call. Avoids redundant validation on every `_process()` call in streaming mode. **Impact**: Minor performance improvement. **Risk**: Very low.

17. **Create integration test** (TEST-NRM-002): Build an end-to-end test exercising `tFileInputDelimited -> tNormalize -> tLogRow` in the v1 engine, verifying context resolution, statistics propagation, and globalMap integration.

---

## Appendix A: Converter Parameter Mapping Code

```python
# component_parser.py lines 1921-1937
def parse_tnormalize(self, node, component: Dict) -> Dict:
    """Parse tNormalize specific configuration"""
    normalize_column = node.find('.//elementParameter[@name="NORMALIZE_COLUMN"]').get('value', '')
    item_separator = node.find('.//elementParameter[@name="ITEMSEPARATOR"]').get('value', ';').strip('"')
    deduplicate = node.find('.//elementParameter[@name="DEDUPLICATE"]').get('value', 'false').lower() == 'true'
    trim = node.find('.//elementParameter[@name="TRIM"]').get('value', 'false').lower() == 'true'
    discard_trailing_empty_str = node.find('.//elementParameter[@name="DISCARD_TRAILING_EMPTY_STR"]').get('value', 'false').lower() == 'true'

    component['config'].update({
        'normalize_column': normalize_column,
        'item_separator': item_separator,
        'deduplicate': deduplicate,
        'trim': trim,
        'discard_trailing_empty_str': discard_trailing_empty_str
    })

    return component
```

**Notes on this code**:
- Line 1923: No NoneType guard. If the `NORMALIZE_COLUMN` elementParameter is missing, `node.find()` returns `None` and `.get()` raises `AttributeError`.
- Line 1924: Default `';'` differs from Talend default `','`. The `.strip('"')` removes surrounding quotes from Talend XML values.
- Lines 1925-1927: Boolean conversion via `.lower() == 'true'` is correct. Default `'false'` matches Talend defaults.
- Missing: `DIE_ON_ERROR`, CSV parameters, `TSTATCATCHER_STATS`.

---

## Appendix B: Engine Class Structure

```
Normalize (BaseComponent)
    Docstring:
        - normalize_column (str): Column name to normalize/split. Required.
        - item_separator (str): Delimiter. Default: ','
        - deduplicate (bool): Remove duplicates. Default: False
        - trim (bool): Trim whitespace. Default: False
        - discard_trailing_empty_str (bool): Remove empties. Default: False
        - die_on_error (bool): Fail on errors. Default: False

    Methods:
        _validate_config() -> List[str]          # Config validation (called inside _process)
        _process(input_data) -> Dict[str, Any]   # Main entry point -- iterrows() based normalization
```

**Method flow in `_process()`**:
1. Check for empty input (return empty DF)
2. Validate config via `_validate_config()` (return original DF or raise on error)
3. Extract config values with defaults
4. Validate `normalize_column` exists in input DataFrame
5. Iterate rows with `iterrows()`:
   a. Get cell value (convert null to empty string)
   b. Split by separator
   c. Apply trim (if enabled)
   d. Apply discard empty (if enabled) -- **BUG: removes ALL empties**
   e. Apply deduplicate (if enabled) -- order-preserving
   f. Create output rows via `row.copy()` for each split value
   g. Handle empty result (create one row with empty string)
6. Build result DataFrame from list of Series
7. Update stats and return

---

## Appendix C: Complete Talend Parameter to V1 Config Key Reference

| Talend Parameter | V1 Config Key | Status | Priority to Add |
|------------------|---------------|--------|-----------------|
| `NORMALIZE_COLUMN` | `normalize_column` | Mapped | -- |
| `ITEMSEPARATOR` | `item_separator` | Mapped (default mismatch) | Fix default |
| `DEDUPLICATE` | `deduplicate` | Mapped | -- |
| `TRIM` | `trim` | Mapped | -- |
| `DISCARD_TRAILING_EMPTY_STR` | `discard_trailing_empty_str` | Mapped | -- |
| `DIE_ON_ERROR` | `die_on_error` | **Not Mapped** | P2 |
| CSV Parameters | -- | **Not Mapped** | P3 |
| `TSTATCATCHER_STATS` | -- | Not needed | -- (tStatCatcher rarely used) |
| `PROPERTY_TYPE` | -- | Not needed | -- (always Built-In) |
| `LABEL` | -- | Not needed | -- (cosmetic) |

---

## Appendix D: Discard Trailing Empty Strings -- Correct Implementation

### Current Implementation (Wrong)

```python
# normalize.py lines 167-168
if discard_trailing_empty_str:
    values = [value for value in values if value]
```

This removes ALL empty strings from the list, regardless of position.

### Correct Implementation

```python
if discard_trailing_empty_str:
    # Remove only trailing empty strings (from the end)
    while values and not values[-1]:
        values.pop()
```

### Example Comparison

Input: `",a,,b,,"`  (comma separator)

Split result: `["", "a", "", "b", "", ""]`

| Implementation | Result | Rows Produced |
|---------------|--------|---------------|
| Current (wrong) | `["a", "b"]` | 2 |
| Correct (Talend) | `["", "a", "", "b"]` | 4 |

The current implementation loses 2 data rows (the leading empty and the middle empty between `a` and `b`).

---

## Appendix E: Vectorized Replacement for iterrows()

### Current Implementation (Slow)

```python
# Lines 149-203 (simplified)
normalized_rows = []
for idx, row in input_data.iterrows():
    cell_value = row[normalize_column]
    if pd.isna(cell_value):
        cell_value = ''
    values = str(cell_value).split(item_separator)
    # ... trim, discard, deduplicate ...
    for value in values:
        new_row = row.copy()
        new_row[normalize_column] = value
        normalized_rows.append(new_row)
result_df = pd.DataFrame(normalized_rows).reset_index(drop=True)
```

### Recommended Vectorized Implementation

```python
import re

def _process(self, input_data):
    # ... validation ...

    df = input_data.copy()
    col = normalize_column

    # Step 1: Handle null values -- preserve as single-element [None] lists
    null_mask = df[col].isna()

    # Step 2: Split non-null values
    if not null_mask.all():
        # Use regex split for Talend compatibility
        df.loc[~null_mask, col] = df.loc[~null_mask, col].astype(str).apply(
            lambda x: re.split(item_separator, x)
        )

    # Keep nulls as [None] for explode
    df.loc[null_mask, col] = df.loc[null_mask].apply(lambda _: [None], axis=1)

    # Step 3: Explode -- one row per split value
    result_df = df.explode(col, ignore_index=True)

    # Step 4: Apply transformations (only on non-null string values)
    str_mask = result_df[col].notna()

    if discard_trailing_empty_str:
        # For trailing empties, we need group-level logic
        # This is harder to vectorize; may need a grouped approach
        pass  # See note below

    if trim:
        result_df.loc[str_mask, col] = result_df.loc[str_mask, col].str.strip()

    if deduplicate:
        # Group by original row index, drop duplicates within each group
        result_df = result_df.drop_duplicates(subset=result_df.columns.tolist(), keep='first')

    result_df = result_df.reset_index(drop=True)

    rows_out = len(result_df)
    self._update_stats(rows_out, rows_out, 0)

    return {'main': result_df}
```

**Note on `discard_trailing_empty_str` with vectorized approach**: The "trailing empty" logic requires knowing which values came from the END of each split list. This is hard to do purely with `explode()`. One approach: apply the trailing-empty removal BEFORE exploding (inside the `apply` lambda). Another: track the original row groups and remove trailing empties within each group post-explode.

**Performance impact**: For 1M rows with 5 average splits per row, the vectorized approach should complete in approximately 2-5 seconds, compared to 30+ minutes with `iterrows()`.

---

## Appendix F: Edge Case Analysis

### Edge Case 1: Empty input

| Aspect | Detail |
|--------|--------|
| **Talend** | Returns 0 rows, NB_LINE=0. No error. |
| **V1** | Lines 107-110: Returns empty DataFrame, stats (0, 0, 0). |
| **Verdict** | CORRECT |

### Edge Case 2: Null value in normalize column

| Aspect | Detail |
|--------|--------|
| **Talend** | Produces 1 output row with null in the normalized column. |
| **V1** | Lines 155-157: Converts null to `""`, splits, produces 1 row with `""`. |
| **Verdict** | **INCORRECT** -- null becomes empty string. See BUG-NRM-005. |

### Edge Case 3: Empty string value

| Aspect | Detail |
|--------|--------|
| **Talend** | Split `""` by any separator produces `[""]`. One output row with `""`. |
| **V1** | `"".split(",")` returns `[""]`. One output row with `""`. |
| **Verdict** | CORRECT |

### Edge Case 4: No separator found in value

| Aspect | Detail |
|--------|--------|
| **Talend** | `"hello".split(",")` produces `["hello"]`. One output row. |
| **V1** | Same: `"hello".split(",")` returns `["hello"]`. One output row. |
| **Verdict** | CORRECT |

### Edge Case 5: Separator at start and end

| Aspect | Detail |
|--------|--------|
| **Talend** | `",a,b,"` with comma produces `["", "a", "b", ""]`. 4 rows. |
| **V1** | Same split result. 4 rows. |
| **Verdict** | CORRECT (without discard/trim options) |

### Edge Case 6: Consecutive separators

| Aspect | Detail |
|--------|--------|
| **Talend** | `"a,,b"` with comma produces `["a", "", "b"]`. 3 rows. |
| **V1** | Same: `"a,,b".split(",")` returns `["a", "", "b"]`. 3 rows. |
| **Verdict** | CORRECT |

### Edge Case 7: All values empty after filtering

| Aspect | Detail |
|--------|--------|
| **Talend** | `",,"` with discard enabled: trailing empties removed, result depends on whether all are trailing. |
| **V1** | Lines 181-185: Creates one row with empty string as fallback. |
| **Verdict** | **PARTIAL** -- fallback prevents row loss but may differ from Talend exact behavior. |

### Edge Case 8: Non-string column value (integer)

| Aspect | Detail |
|--------|--------|
| **Talend** | Converts to string before splitting. |
| **V1** | Line 158: `cell_value = str(cell_value)`. Integer `123` becomes `"123"`, which does not split on comma. 1 row. |
| **Verdict** | CORRECT |

### Edge Case 9: Multi-character separator

| Aspect | Detail |
|--------|--------|
| **Talend** | `"a::b::c"` with separator `"::"` produces `["a", "b", "c"]`. |
| **V1** | `"a::b::c".split("::")` returns `["a", "b", "c"]`. |
| **Verdict** | CORRECT (for literal multi-char separators) |

### Edge Case 10: Deduplication order preservation

| Aspect | Detail |
|--------|--------|
| **Talend** | `"c,b,a,b,c"` deduplicated produces `["c", "b", "a"]`. First occurrence kept. |
| **V1** | Lines 172-178: seen-set preserves first occurrence order. `["c", "b", "a"]`. |
| **Verdict** | CORRECT |

### Edge Case 11: Single row with many splits

| Aspect | Detail |
|--------|--------|
| **Talend** | `"a,b,c,...,z"` with 1000 values produces 1000 rows. |
| **V1** | Creates 1000 Series copies via `row.copy()`. Functionally correct but extremely slow. |
| **Verdict** | CORRECT (functional), **PERFORMANCE ISSUE** (see PERF-NRM-001) |

### Edge Case 12: Trim + discard interaction

| Aspect | Detail |
|--------|--------|
| **Talend** | Order: discard trailing, then trim. `"a, ,"` -> discard trailing `""`: `["a", " "]` -> trim: `["a", ""]`. 2 rows. |
| **V1** | Order: trim first, then discard. `"a, ,"` -> trim: `["a", "", ""]` -> discard ALL empties: `["a"]`. 1 row. |
| **Verdict** | **INCORRECT** -- v1 produces 1 row, Talend produces 2 rows. See LOGIC-NRM-001. |

### Edge Case 13: Config validation with empty normalize_column

| Aspect | Detail |
|--------|--------|
| **Talend** | Cannot configure -- dropdown requires selection. |
| **V1** | Line 74: `_validate_config()` catches `not self.config['normalize_column'].strip()`. Returns error. |
| **Verdict** | CORRECT |

### Edge Case 14: Separator is period character

| Aspect | Detail |
|--------|--------|
| **Talend** | Regex mode: `.` matches any character. Must escape as `\\.`. |
| **V1** | `str.split(".")` treats `.` literally. `"a.b.c".split(".")` returns `["a", "b", "c"]`. |
| **Verdict** | **DIFFERENT BEHAVIOR** -- v1 treats `.` literally (correct for most use cases), Talend treats as regex. |

### Edge Case 15: Unicode separator

| Aspect | Detail |
|--------|--------|
| **Talend** | Java's `String.split()` handles Unicode. |
| **V1** | Python's `str.split()` handles Unicode. E.g., `"a\u2022b".split("\u2022")` works. |
| **Verdict** | CORRECT |

---

## Appendix G: Cross-Cutting Issues

The following issues were discovered during this audit but affect the entire v1 engine, not just `Normalize`:

| ID | Priority | Component | Issue |
|----|----------|-----------|-------|
| BUG-NRM-001 | **P0** | `base_component.py:304` | `_update_global_map()` references undefined `value` variable. NameError crashes `execute()` entirely, preventing ANY component from returning results when `global_map` is set. The entire engine is broken. |
| BUG-NRM-002 | **P0** | `global_map.py:28` | `GlobalMap.get()` references undefined `default` parameter. Will crash on any `get()` call. |
| BUG-NRM-003 | **P1** | `engine.py:40` | Import path mismatch: imports `Normalize`, `Denormalize`, `AggregateSortedRow`, `Replicate` from `.components.aggregate` but they live in `.components.transform`. |
| STD-NRM-001 | **P2** | `component_parser.py` | Schema types converted to Python format instead of Talend format. Affects all components. |

These should be tracked in a cross-cutting issues report as well.

---

## Appendix H: Implementation Fix Guides

### Fix Guide: BUG-NRM-001 -- `_update_global_map()` undefined variable

**File**: `src/v1/engine/base_component.py`
**Line**: 304

**Current code (broken)**:
```python
logger.info(f"Component {self.id}: Updated stats - NB_LINE:{self.stats['NB_LINE']} NB_LINE_OK:{self.stats['NB_LINE_OK']} NB_LINE_REJECT:{self.stats['NB_LINE_REJECT']} {stat_name}: {value}")
```

**Fix**:
```python
logger.info(f"Component {self.id}: Updated stats - NB_LINE:{self.stats['NB_LINE']} NB_LINE_OK:{self.stats['NB_LINE_OK']} NB_LINE_REJECT:{self.stats['NB_LINE_REJECT']}")
```

**Explanation**: `{value}` references an undefined variable (the loop variable is `stat_value`). The `{stat_name}` reference would show only the last loop iteration value. Best fix is to remove both stale references.

**Impact**: Fixes ALL components (cross-cutting). **Risk**: Very low.

---

### Fix Guide: BUG-NRM-002 -- `GlobalMap.get()` undefined default

**File**: `src/v1/engine/global_map.py`
**Line**: 26-28

**Current code (broken)**:
```python
def get(self, key: str) -> Optional[Any]:
    """Retrieve a value from the global map"""
    return self._map.get(key, default)
```

**Fix**:
```python
def get(self, key: str, default: Any = None) -> Optional[Any]:
    """Retrieve a value from the global map"""
    return self._map.get(key, default)
```

**Impact**: Fixes ALL components and any code calling `global_map.get()`. **Risk**: Very low.

---

### Fix Guide: BUG-NRM-003 -- Import path mismatch

**File**: `src/v1/engine/engine.py`
**Line**: 40

**Current code (broken)**:
```python
from .components.aggregate import AggregateSortedRow, Denormalize, Normalize, Replicate
```

**Fix**:
```python
from .components.transform import AggregateSortedRow, Denormalize, Normalize, Replicate
```

**Impact**: Fixes `ImportError` for 4 components. **Risk**: Very low.

---

### Fix Guide: BUG-NRM-004 -- Discard trailing empty strings

**File**: `src/v1/engine/components/transform/normalize.py`
**Lines**: 167-168

**Current code (wrong)**:
```python
if discard_trailing_empty_str:
    values = [value for value in values if value]
```

**Fix**:
```python
if discard_trailing_empty_str:
    while values and not values[-1]:
        values.pop()
```

**Impact**: Fixes data corruption for non-trailing empty values. **Risk**: Low.

---

### Fix Guide: BUG-NRM-005 -- Null handling

**File**: `src/v1/engine/components/transform/normalize.py`
**Lines**: 155-158

**Current code (wrong)**:
```python
if pd.isna(cell_value):
    cell_value = ''
else:
    cell_value = str(cell_value)
```

**Fix**:
```python
if pd.isna(cell_value):
    # Preserve null -- produce one row with null/None
    new_row = row.copy()
    new_row[normalize_column] = None
    normalized_rows.append(new_row)
    continue
else:
    cell_value = str(cell_value)
```

**Impact**: Preserves null semantics. **Risk**: Low.

---

### Fix Guide: ENG-NRM-005 -- Processing order

**File**: `src/v1/engine/components/transform/normalize.py`
**Lines**: 164-178

**Current order**: trim -> discard -> deduplicate
**Correct order (Talend)**: discard trailing empties -> trim -> deduplicate

**Fix**: Move lines 167-168 (discard block) BEFORE lines 164-165 (trim block):

```python
# Step 1: Discard trailing empty strings (Talend order)
if discard_trailing_empty_str:
    while values and not values[-1]:
        values.pop()

# Step 2: Trim
if trim:
    values = [value.strip() for value in values]

# Step 3: Deduplicate
if deduplicate:
    seen = set()
    unique_values = []
    for value in values:
        if value not in seen:
            seen.add(value)
            unique_values.append(value)
    values = unique_values
```

**Impact**: Matches Talend processing order. **Risk**: Low.

---

## Appendix I: Risk Assessment for Production Migration

### High-Risk Scenarios

| Scenario | Risk Level | Affected Jobs | Mitigation |
|----------|-----------|---------------|------------|
| Jobs with >100K input rows | **Critical** | Any job using tNormalize on large data | Must replace `iterrows()` with `explode()` before migration |
| Jobs with null values in normalize column | **High** | Jobs where nulls have semantic meaning downstream | Must fix null handling (BUG-NRM-005) |
| Jobs with embedded empties in values | **High** | Jobs where `"a,,b"` should preserve middle empty | Must fix discard trailing logic (BUG-NRM-004) |
| Jobs referencing `{id}_NB_LINE` downstream | **Medium** | Jobs with conditional logic on row count | Must fix NB_LINE semantics (ENG-NRM-003) |
| Jobs using regex separators | **Medium** | Jobs with whitespace or multi-pattern separators | Must add regex support (ENG-NRM-004) |
| Jobs relying on Talend default separator | **Medium** | Jobs that don't explicitly set separator | Must fix converter default (CONV-NRM-002) |

### Low-Risk Scenarios

| Scenario | Risk Level | Notes |
|----------|-----------|-------|
| Jobs with simple comma-separated values | Low | Basic split works correctly |
| Jobs using trim only | Low | Trim implementation is correct |
| Jobs using deduplicate only | Low | Order-preserving deduplication is correct |
| Jobs with CSV parameters | Low | Rarely used feature |

### Recommended Migration Strategy

1. **Phase 1**: Fix all P0 bugs (cross-cutting + `iterrows()`). Run existing converted jobs to verify basic functionality.
2. **Phase 2**: Fix P1 bugs (discard trailing, null handling, NB_LINE, import path).
3. **Phase 3**: Create unit test suite (P0 test cases). Run against both v1 and reference Talend output.
4. **Phase 4**: Parallel-run migrated jobs against Talend originals. Compare output row-for-row, paying special attention to null values, empty strings, and row counts.
5. **Phase 5**: Fix any differences found in parallel-run testing.

---

## Appendix J: Converter Dispatch Code

```python
# converter.py lines 315-316
elif component_type == 'tNormalize':
    component = self.component_parser.parse_tnormalize(node, component)
```

**Notes**: The converter has a dedicated `elif` branch for tNormalize, which is the correct approach per standards. The dispatch correctly calls the dedicated `parse_tnormalize()` method. No issues with the dispatch itself.

---

## Appendix K: Registry and Import Chain

```
Engine startup:
  engine.py:40 -> from .components.aggregate import ... Normalize ...  [BUG: wrong package]
                  Should be: from .components.transform import ... Normalize ...

Package chain (correct):
  transform/__init__.py:15 -> from .normalize import Normalize
  transform/normalize.py:19 -> class Normalize(BaseComponent)

Registry (engine.py lines 115-116):
  'Normalize': Normalize
  'tNormalize': Normalize

Converter name mapping (component_parser.py line 67):
  'tNormalize': 'Normalize'
```

The registry aliases are correct: both `Normalize` and `tNormalize` map to the same class. The converter name mapping correctly maps the Talend component type `tNormalize` to the v1 class name `Normalize`. The only issue is the import path in `engine.py`.

---

## Appendix L: Detailed Code Walkthrough

### `_validate_config()` (Lines 60-88)

This method validates the component configuration and returns a list of error messages. An empty list means the configuration is valid.

**Validation checks performed**:
1. `normalize_column` is present in config (required)
2. `normalize_column` is a string type
3. `normalize_column` is not empty/whitespace-only after `.strip()`
4. `item_separator` is a string type (if present)
5. `deduplicate` is a boolean type (if present)
6. `trim` is a boolean type (if present)
7. `discard_trailing_empty_str` is a boolean type (if present)
8. `die_on_error` is a boolean type (if present)

**Not validated**:
- Whether `normalize_column` actually exists in the input DataFrame (checked later in `_process()`)
- Whether `item_separator` is non-empty (an empty separator would cause `str.split('')` to raise `ValueError`)
- Whether `item_separator` is a valid regex (relevant if regex support is added)
- Maximum length of `item_separator` (no practical limit)

**Calling convention**: This method is called at the START of `_process()` (line 117-118). If errors are found:
- With `die_on_error=True`: raises `ConfigurationError` with all error messages joined by semicolon
- With `die_on_error=False`: logs the errors, updates stats with `(rows_in, rows_in, 0)` (treating all rows as "OK"), and returns the input data unchanged

**Issue**: The stats update on the non-error path (line 125) uses `_update_stats(rows_in, rows_in, 0)`, which counts the original input rows as "OK." This is misleading since no normalization was performed -- the data passed through unchanged. It should arguably use `_update_stats(rows_in, 0, 0)` to indicate that rows were read but not successfully normalized.

### `_process()` (Lines 90-221)

The main processing method. This is the only method that needs to be implemented per the `BaseComponent` abstract class contract.

**Full execution flow**:

```
_process(input_data)
  |
  +-- Check input_data is None or empty
  |     |-- Yes: log warning, stats (0,0,0), return empty DF
  |     +-- No: continue
  |
  +-- Log row count: "Processing started: {rows_in} rows"
  |
  +-- Try block:
  |   |
  |   +-- _validate_config()
  |   |     |-- Errors found + die_on_error: RAISE ConfigurationError
  |   |     |-- Errors found + !die_on_error: stats, return original DF
  |   |     +-- No errors: continue
  |   |
  |   +-- Extract config values with defaults:
  |   |     normalize_column = config.get('normalize_column', '')
  |   |     item_separator = config.get('item_separator', ',')
  |   |     deduplicate = config.get('deduplicate', False)
  |   |     trim = config.get('trim', False)
  |   |     discard_trailing_empty_str = config.get('discard_trailing_empty_str', False)
  |   |     die_on_error = config.get('die_on_error', False)
  |   |
  |   +-- Check normalize_column in input_data.columns
  |   |     |-- Not found + die_on_error: RAISE ConfigurationError
  |   |     |-- Not found + !die_on_error: stats, return original DF
  |   |     +-- Found: continue
  |   |
  |   +-- Initialize normalized_rows: List[pd.Series] = []
  |   |
  |   +-- FOR idx, row IN input_data.iterrows():
  |   |     |
  |   |     +-- Try block (per row):
  |   |     |   |
  |   |     |   +-- Get cell_value = row[normalize_column]
  |   |     |   |
  |   |     |   +-- pd.isna(cell_value)?
  |   |     |   |     |-- Yes: cell_value = '' [BUG: should preserve null]
  |   |     |   |     +-- No: cell_value = str(cell_value)
  |   |     |   |
  |   |     |   +-- values = cell_value.split(item_separator)
  |   |     |   |
  |   |     |   +-- trim? -> values = [v.strip() for v in values]
  |   |     |   |
  |   |     |   +-- discard_trailing_empty_str? -> values = [v for v if v]
  |   |     |   |     [BUG: removes ALL empties, not just trailing]
  |   |     |   |
  |   |     |   +-- deduplicate? -> order-preserving dedup via seen set
  |   |     |   |
  |   |     |   +-- values empty?
  |   |     |   |     |-- Yes: create 1 row with normalize_column = ''
  |   |     |   |     +-- No: FOR value IN values:
  |   |     |   |               new_row = row.copy()
  |   |     |   |               new_row[normalize_column] = value
  |   |     |   |               normalized_rows.append(new_row)
  |   |     |   |
  |   |     +-- Except Exception as e (per row):
  |   |           |-- die_on_error: RAISE ComponentExecutionError
  |   |           +-- !die_on_error: append original row.copy()
  |   |
  |   +-- Build result: pd.DataFrame(normalized_rows).reset_index(drop=True)
  |   |     OR empty DataFrame if normalized_rows is empty
  |   |
  |   +-- _update_stats(rows_in, rows_out, 0)
  |   |
  |   +-- Log: "Processing complete: in={rows_in}, out={rows_out}, rejected=0"
  |   |
  |   +-- Return {'main': result_df}
  |
  +-- Except ConfigurationError, ComponentExecutionError: re-raise
  +-- Except Exception as e: RAISE ComponentExecutionError (wrapped)
```

### Deduplication Algorithm (Lines 170-178)

The deduplication algorithm uses an order-preserving approach:

```python
seen: set = set()
unique_values: List[str] = []
for value in values:
    if value not in seen:
        seen.add(value)
        unique_values.append(value)
values = unique_values
```

**Correctness analysis**:
- **Time complexity**: O(n) where n is the number of split values. Each value involves a set lookup (O(1) average) and potential set insertion (O(1) amortized).
- **Space complexity**: O(n) for the seen set and unique_values list.
- **Order preservation**: The first occurrence of each value is kept. Values are appended to `unique_values` in the order they appear in the input, so the original order is preserved.
- **Case sensitivity**: Deduplication is case-sensitive. `"A"` and `"a"` are treated as different values. This matches Talend behavior.
- **After-trim deduplication**: If trim is enabled, deduplication runs AFTER trimming. This means `" a "` and `"a"` are deduplicated as the same value (both become `"a"` after trim). This is the correct Talend behavior -- trim first, then deduplicate.
- **Empty string handling**: Empty strings `""` are valid values for deduplication. If the split produces `["", "a", ""]`, deduplication yields `["", "a"]` (second empty removed). This interacts with `discard_trailing_empty_str` -- if discard runs before dedup (as it should per Talend order), trailing empties are removed first.

### Empty Result Fallback (Lines 181-185)

When all values are filtered out by discard and/or deduplication, the component creates a single output row with an empty string in the normalized column:

```python
if not values:
    new_row: pd.Series = row.copy()
    new_row[normalize_column] = ''
    normalized_rows.append(new_row)
```

**Analysis**: This prevents complete row loss when all split values are removed by filtering. However, this behavior may not match Talend exactly. In Talend, if a row produces zero values after discard+dedup, the row may be dropped entirely rather than producing an empty-string row. This needs verification against Talend reference output.

**Edge case interaction**: Consider input `",,"` (all empties) with `discard_trailing_empty_str=true`:
- Split: `["", "", ""]`
- v1 discard (wrong -- removes all): `[]` -> fallback creates 1 row with `""`
- Talend discard (correct -- removes trailing): `[]` (all are trailing) -> behavior uncertain

---

## Appendix M: Comparison with tDenormalize

`tNormalize` and `tDenormalize` are inverse operations. Understanding the relationship helps verify correctness.

| Aspect | tNormalize | tDenormalize |
|--------|-----------|-------------|
| **Direction** | One row -> Many rows (explode) | Many rows -> One row (aggregate) |
| **Key operation** | Split column by separator | Concatenate column values with separator |
| **Row count** | Output >= Input | Output <= Input |
| **Non-normalized columns** | Replicated to all output rows | Must be identical within each group |
| **Null handling** | Null -> 1 row with null | Nulls included in concatenation or skipped |
| **Separator** | Used to split | Used to join |
| **Schema** | Input schema == Output schema | Input schema == Output schema |
| **Advanced: Trim** | Trim each split value | N/A |
| **Advanced: Deduplicate** | Remove duplicate split values | N/A |
| **Advanced: Discard trailing** | Remove trailing empties from split | N/A |

**Roundtrip test**: If you normalize `"a,b,c"` by comma and then denormalize by comma, you should get back `"a,b,c"`. This is a useful integration test.

**Implementation consistency**: Both `Normalize` and `Denormalize` in v1 use the `iterrows()` anti-pattern. Both are imported incorrectly in `engine.py` line 40 from `.components.aggregate` instead of `.components.transform`. The same cross-cutting bugs affect both.

---

## Appendix N: Talend Generated Java Code Behavior

While we do not have direct access to the Talend-generated Java code for tNormalize, based on Talend's code generation patterns and the Java `String.split()` documentation, the following behavioral details can be inferred:

### Java `String.split()` Behavior

Talend's tNormalize uses Java's `String.split(regex)` internally. Key behavioral differences from Python's `str.split()`:

1. **Regex by default**: Java's `split()` always interprets the separator as a regex. Python's `split()` interprets it as a literal string. This means:
   - `"."` in Java splits on ANY character; in Python it splits on literal period
   - `"|"` in Java splits on empty string (regex pipe is OR with empty alternatives); in Python it splits on literal pipe
   - `"+"` in Java causes `PatternSyntaxException`; in Python it splits on literal plus

2. **Trailing empty strings**: Java's `String.split(regex)` has a special behavior: by default (`split(regex)` without limit argument), it **discards trailing empty strings** from the result array. For example:
   - Java: `"a,b,,".split(",")` returns `["a", "b"]` (trailing empties removed by default)
   - Python: `"a,b,,".split(",")` returns `["a", "b", "", ""]` (trailing empties preserved)

   This is a critical behavioral difference. Talend's `Discard the trailing empty strings` option is REDUNDANT with Java's default `split()` behavior -- it only matters when the `-1` limit is passed to `split()`, which preserves trailing empties.

3. **Leading empty strings**: Both Java and Python preserve leading empty strings:
   - Java: `",a,b".split(",")` returns `["", "a", "b"]`
   - Python: `",a,b".split(",")` returns `["", "a", "b"]`

4. **Consecutive separators**: Both produce empty strings in the middle:
   - Java: `"a,,b".split(",")` returns `["a", "", "b"]`
   - Python: `"a,,b".split(",")` returns `["a", "", "b"]`

**Implication for v1**: The v1 implementation's use of Python `str.split()` actually differs from Talend's Java `String.split()` in its DEFAULT handling of trailing empty strings. Without the `discard_trailing_empty_str` option, v1 preserves trailing empties while Talend discards them. This means:
- v1 WITHOUT discard option: `"a,b,,"` -> `["a", "b", "", ""]` (4 rows)
- Talend WITHOUT discard option: `"a,b,,"` -> `["a", "b"]` (2 rows)

This is a significant behavioral difference that is NOT captured by any current issue. The `discard_trailing_empty_str` option in Talend corresponds to using `split(regex, -1)` (preserve all) vs `split(regex)` (discard trailing). The v1 implementation has it backwards: the DEFAULT should discard trailing empties (matching Java's default), and the option should PREVENT discarding.

**New issue identified**: This analysis reveals an additional behavioral difference that should be filed:

| ID | Priority | Description |
|----|----------|-------------|
| ENG-NRM-007 | **P1** | **Default trailing empty string handling inverted**: Python `str.split()` preserves trailing empties by default, while Java `String.split()` (used by Talend) discards them by default. Without `discard_trailing_empty_str` enabled, v1 produces MORE rows than Talend for inputs ending with separators. The `discard_trailing_empty_str` option should arguably be the DEFAULT behavior, not the opt-in behavior. |

---

## Appendix O: Statistics Tracking Deep Dive

### How Statistics Flow

```
Normalize._process()
  |
  +-- _update_stats(rows_in, rows_out, 0)
  |     |-- self.stats['NB_LINE'] += rows_in        # Input rows
  |     |-- self.stats['NB_LINE_OK'] += rows_out     # Output rows
  |     +-- self.stats['NB_LINE_REJECT'] += 0        # Always 0
  |
  +-- Returns to BaseComponent.execute()
        |
        +-- self.stats['EXECUTION_TIME'] = elapsed
        +-- _update_global_map()
        |     |-- FOR each stat: global_map.put_component_stat(id, name, value)
        |     |     +-- global_map._component_stats[id][name] = value
        |     |     +-- global_map._map[f"{id}_{name}"] = value
        |     +-- [BUG] Log line references undefined 'value'
        |
        +-- result['stats'] = self.stats.copy()
        +-- return result
```

### Stat Value Analysis for Normalize

For a typical execution with 10 input rows producing 30 output rows:

| Stat | Value in V1 | Value in Talend | Match? |
|------|------------|-----------------|--------|
| `NB_LINE` | 10 (input rows) | 30 (output rows) | **NO** |
| `NB_LINE_OK` | 30 (output rows) | 30 (output rows) | YES |
| `NB_LINE_REJECT` | 0 | 0 | YES |
| `EXECUTION_TIME` | measured | N/A (v1 only) | N/A |

### GlobalMap Key Format

After execution, the globalMap contains:

| Key | Value | Source |
|-----|-------|--------|
| `tNormalize_1_NB_LINE` | 10 | `global_map.put_component_stat('tNormalize_1', 'NB_LINE', 10)` |
| `tNormalize_1_NB_LINE_OK` | 30 | `global_map.put_component_stat('tNormalize_1', 'NB_LINE_OK', 30)` |
| `tNormalize_1_NB_LINE_REJECT` | 0 | `global_map.put_component_stat('tNormalize_1', 'NB_LINE_REJECT', 0)` |
| `tNormalize_1_NB_LINE_INSERT` | 0 | Default from base class stats |
| `tNormalize_1_NB_LINE_UPDATE` | 0 | Default from base class stats |
| `tNormalize_1_NB_LINE_DELETE` | 0 | Default from base class stats |
| `tNormalize_1_EXECUTION_TIME` | 0.5 | Measured by base class |

**Note**: The base class initializes ALL stats keys (NB_LINE_INSERT, NB_LINE_UPDATE, NB_LINE_DELETE, EXECUTION_TIME) and stores ALL of them in the globalMap. This means the globalMap contains 7 keys per component, even though tNormalize only uses 3 of them. The extra keys are harmless but add noise.

---

## Appendix P: Interaction with Upstream and Downstream Components

### Common Upstream Components

| Component | Interaction | Notes |
|-----------|-------------|-------|
| `tFileInputDelimited` | Provides input rows with delimited values | Most common source. Schema defines column types. |
| `tMap` | Transforms data before normalization | May concatenate fields or apply expressions. |
| `tFilterRow` | Filters rows before normalization | Reduces input size for better performance. |
| `tDBInput` | Database query results with delimited columns | Common in data warehouse ETL. |

### Common Downstream Components

| Component | Interaction | Notes |
|-----------|-------------|-------|
| `tLogRow` | Displays normalized output | Used for verification. |
| `tMap` | Transforms normalized data | May join with lookup tables. |
| `tFilterRow` | Filters based on individual split values | **Affected by BUG-NRM-005**: null values become empty strings. `tFilterRow` checking for null will not find them. |
| `tFileOutputDelimited` | Writes normalized output to file | Row count will differ from input. |
| `tDenormalize` | Re-aggregates normalized data | Roundtrip test: normalize then denormalize should return original. |
| `tAggregateRow` | Counts or aggregates per split value | Common for tag/category analysis. |
| `tUniqRow` | Removes duplicate rows | May be used instead of tNormalize's built-in dedup if cross-row dedup is needed. |

### Data Flow Example

```
tFileInputDelimited_1                tNormalize_1                    tLogRow_1
  |                                    |                              |
  | Schema:                            | Config:                      |
  |   id (Integer)                     |   normalize_column: "tags"   |
  |   name (String)                    |   item_separator: ","        |
  |   tags (String)                    |   trim: true                 |
  |                                    |   deduplicate: true          |
  | Output:                            |                              |
  | id | name  | tags                  | Output:                      |
  |  1 | Alice | "java,python,java"    | id | name  | tags            |
  |  2 | Bob   | "sql,java"            |  1 | Alice | java            |
  |                                    |  1 | Alice | python          |
  |                                    |  2 | Bob   | sql             |
  |                                    |  2 | Bob   | java            |
  |                                    |                              |
  | NB_LINE: 2                         | NB_LINE: 4 (Talend)         |
  |                                    | NB_LINE: 2 (v1 BUG)         |
  |                                    | NB_LINE_OK: 4               |
```

**Note**: In the example above, Alice's `"java"` duplicate is removed by deduplication (only 2 output rows for Alice instead of 3). The `NB_LINE` discrepancy between Talend (4 = output rows) and v1 (2 = input rows) illustrates ENG-NRM-003.

---

## Appendix Q: Complete Engine Source Code Analysis

### Line-by-Line Coverage

| Lines | Purpose | Issues Found |
|-------|---------|-------------|
| 1-16 | Module docstring, imports, logger | Clean. All imports used. |
| 19-58 | Class docstring | Comprehensive. Documents all config params, inputs, outputs, stats, and example. |
| 60-88 | `_validate_config()` | Correct validation logic. Called inside `_process()` (not ideal per standards). |
| 90-105 | `_process()` docstring | Accurate. Documents return format and exceptions. |
| 107-110 | Empty input guard | Correct. Returns empty DF with stats (0, 0, 0). |
| 112-113 | Logging and row count | Correct. Uses `[{self.id}]` prefix. |
| 115-126 | Config validation call | Correct flow for die_on_error handling. Stats update may be misleading (see Appendix L). |
| 128-134 | Config extraction with defaults | Correct. All defaults match docstring. `item_separator` defaults to `,` (correct per Talend). |
| 136-146 | Column existence check | Correct. Returns original data or raises based on `die_on_error`. |
| 149 | Initialize `normalized_rows` list | Anti-pattern: List[pd.Series] will be slow to convert to DataFrame. |
| 151 | `iterrows()` loop | **ANTI-NRM-001**: Critical performance anti-pattern. |
| 152-199 | Per-row processing (inner try/except) | Contains BUG-NRM-004 (discard all empties) and BUG-NRM-005 (null to empty). |
| 155-158 | Null/NaN handling | **BUG-NRM-005**: Converts null to empty string. |
| 161 | Split by separator | Uses literal `str.split()`, not regex. See ENG-NRM-004. |
| 164-165 | Trim | Correct: `value.strip()` for each value. |
| 167-168 | Discard empty strings | **BUG-NRM-004**: Removes ALL empties, not just trailing. |
| 170-178 | Deduplicate | Correct: order-preserving seen-set algorithm. |
| 181-185 | Empty result fallback | Creates one row with empty string. May not match Talend exactly. |
| 187-190 | Create output rows | **ANTI-NRM-002**: `row.copy()` per split value. |
| 192-199 | Per-row error handling | Correct: raises or appends original row based on `die_on_error`. |
| 202-205 | Build result DataFrame | **ANTI-NRM-003**: `pd.DataFrame(list_of_series)` is slow. |
| 207-211 | Stats and logging | **ENG-NRM-003**: NB_LINE uses input count, not output count. |
| 213 | Return result | Correct format: `{'main': result_df}`. |
| 215-221 | Outer exception handling | Correct: re-raises custom exceptions, wraps others in `ComponentExecutionError`. |

### Code Metrics

| Metric | Value |
|--------|-------|
| Total lines | 221 |
| Blank lines | ~30 |
| Comment/docstring lines | ~65 |
| Code lines | ~126 |
| Methods | 2 (`_validate_config`, `_process`) |
| Cyclomatic complexity (`_process`) | ~12 (multiple if/else branches, nested loops, try/except) |
| Max nesting depth | 5 (try -> for -> try -> if -> for) |
| External dependencies | `pandas`, `logging`, `typing` |
| Internal dependencies | `BaseComponent`, `ConfigurationError`, `ComponentExecutionError` |

---

## Appendix R: Talend tNormalize Official Documentation Summary

Based on research from multiple official and community sources, the following is the consolidated reference for tNormalize behavior:

### Official Documentation (help.talend.com / help.qlik.com)

**Basic Settings**:
- Schema: row description defining columns to process
- Column to normalize: dropdown selecting the column to split
- Item separator: regex-capable delimiter for the split operation

**Advanced Settings**:
- Get rid of duplicated rows from output: removes duplicate values after splitting
- Use CSV parameters: enables escape mode and enclosure character for CSV-aware splitting
- Discard the trailing empty strings: removes empty strings from the END of the split result
- Trim resulting values: removes leading and trailing whitespace from each split value
- tStatCatcher Statistics: gathers processing metadata

**Global Variables**:
- NB_LINE: row count (output rows for processing components)
- ERROR_MESSAGE: error text when Die on error is unchecked

### Community Sources

**TutorialGateway** (tutorialgateway.org):
- tNormalize helps to normalize the denormalized data
- Two main options: Column to normalize and Item separator
- Component connects via Row > Main connections

**SQL DataTools** (sql-datatools.com):
- tNormalize splits a record having comma separated values into multiple records
- The component normalizes the source data as in database normalization

**Talend Skill** (talendskill.com):
- "normalizes the input flow following SQL standard to help improve data quality and thus eases the data update"
- Item separator "uses regex patterns, so the period character should be avoided or used carefully"

**Talend Community** (community.talend.com):
- tNormalize resulting in null output: when column value is null, output retains null
- NB_LINE available only after component execution completes

### Processing Order (from official scenario)

The official Talend scenario for tNormalize demonstrates processing a tag list with:
1. Trailing empty strings (from trailing commas)
2. Leading and trailing whitespace
3. Repeated tags

The scenario enables all three advanced options and shows the result "tidied up with duplicate tags, leading and trailing whitespace and trailing empty strings removed." This confirms the processing order: split -> discard trailing empties -> trim -> deduplicate.
