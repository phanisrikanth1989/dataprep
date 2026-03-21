# Audit Report: tDenormalize / Denormalize

> **Audited**: 2026-03-21
> **Auditor**: Claude Opus 4.6 (automated) -- GOLD STANDARD TEMPLATE
> **Engine Version**: v1
> **Converter**: `complex_converter`
> **Status**: PRODUCTION READINESS REVIEW

---

## 1. Component Identity

| Field | Value |
|-------|-------|
| **Talend Name** | `tDenormalize` |
| **V1 Engine Class** | `Denormalize` |
| **Engine File** | `src/v1/engine/components/transform/denormalize.py` (238 lines) |
| **Converter Parser** | `src/converters/complex_converter/component_parser.py` -> `parse_tdenormalize()` (lines 2738-2797) |
| **Converter Dispatch** | `src/converters/complex_converter/converter.py` -> `elif component_type == 'tDenormalize':` (lines 369-370) |
| **Registry Aliases** | `Denormalize`, `tDenormalize` (registered in `src/v1/engine/engine.py` lines 113-114) |
| **Category** | Processing / Transform |

### Key Files

| File | Purpose |
|------|---------|
| `src/v1/engine/components/transform/denormalize.py` | Engine implementation (238 lines) |
| `src/converters/complex_converter/component_parser.py` (lines 2738-2797) | Dedicated `parse_tdenormalize()` method for Talend XML to v1 JSON |
| `src/converters/complex_converter/converter.py` (lines 369-370) | Dispatch -- dedicated `elif` branch for `tDenormalize` |
| `src/v1/engine/components/transform/__init__.py` | Package export: `from .denormalize import Denormalize` |
| `src/v1/engine/engine.py` (lines 40, 113-114) | **BROKEN IMPORT**: Imports from `.components.aggregate` but class lives in `.components.transform` |
| `src/v1/engine/base_component.py` | Base class: `_update_stats()`, `_update_global_map()`, `validate_schema()`, `execute()` |
| `src/v1/engine/global_map.py` | GlobalMap storage for `{id}_NB_LINE` etc. |
| `src/v1/engine/exceptions.py` | Custom exception hierarchy (`ConfigurationError`, `DataValidationError`, `ComponentExecutionError`) |

---

## 2. Scorecard

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
|-----------|-------|----|----|----|----|---------|
| Converter Coverage | **Y** | 0 | 2 | 1 | 1 | 3 of 6 Talend params explicitly parsed; delimiter quote-stripping has edge cases; raw config bleeds through |
| Engine Feature Parity | **Y** | 1 | 4 | 2 | 1 | Broken import path; no "merge same value" filtering; groupby drops null-key rows; no REJECT flow; no order-change warning; multi-column denorm extends Talend semantics |
| Code Quality | **Y** | 2 | 1 | 3 | 1 | Cross-cutting base class bugs; groupby sort changes row order silently; null_as_empty includes empty strings in output (correct Talend behavior, documentation/clarity issue) |
| Performance & Memory | **G** | 0 | 0 | 1 | 1 | `groupby()` materializes full copy; closure creation per column |
| Testing | **R** | 1 | 1 | 0 | 0 | Zero v1 unit tests; zero v1 integration tests for this component |

**Overall: YELLOW -- Not production-ready without P0/P1 fixes**

### Score Key
- **R** (Red): Critical gaps blocking production use
- **Y** (Yellow): Significant gaps; usable for subset of jobs with known limitations
- **G** (Green): Production-ready with minor improvements recommended

---

## 3. Talend Feature Baseline

### What tDenormalize Does

`tDenormalize` is a Processing family component that denormalizes (flattens) an input data flow by combining multiple rows into single rows. It selects one or more columns whose values should be concatenated across rows sharing the same key, and produces one output row per unique key combination with the denormalized column values joined by a user-specified delimiter.

The component works by:
1. Identifying the column(s) to denormalize via the **To Denormalize** table
2. All remaining columns are treated as **implicit group-by keys**
3. Rows sharing the same key values are collapsed into a single output row
4. Values from the denormalized column(s) are concatenated using the configured delimiter
5. Optionally merging identical consecutive values to remove duplicates

**Source**: [tDenormalize Standard Properties (Talend 7.3)](https://help.qlik.com/talend/en-US/components/7.3/processing/tdenormalize-standard-properties), [tDenormalize Standard Properties (Talend 8.0)](https://help.qlik.com/talend/en-US/components/8.0/processing/tdenormalize-standard-properties), [Denormalizing on one column (scenario)](https://help.qlik.com/talend/en-US/components/7.3/processing/tdenormalize-tfileinputdelimited-tlogrow-tlogrow-denormalizing-on-one-column-standard-component-drop)

**Component family**: Processing (Integration)
**Available in**: All Talend products (Standard). Also available in MapReduce (deprecated), Spark Batch, Spark Streaming variants.

### 3.1 Basic Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 1 | Property Type | `PROPERTY_TYPE` | Built-In / Repository | Built-In | Whether config comes from metadata repository or is inline. Not needed at runtime. |
| 2 | Schema | `SCHEMA` | Schema editor | -- | Column definitions with types, lengths, patterns, nullable, key attributes. Defines the output structure. The schema must include both key columns and denormalize columns. |
| 3 | To Denormalize (Column) | `DENORMALIZE_COLUMNS` -> `INPUT_COLUMN` | Table (elementRef) | -- | **Mandatory**. Column name(s) to denormalize. Each row in the table specifies one column to collapse. All other columns become implicit group-by keys. In Talend Standard, only one column can be denormalized per component instance. |
| 4 | To Denormalize (Delimiter) | `DENORMALIZE_COLUMNS` -> `DELIMITER` | Table (elementRef) / String | `","` | Separator character(s) to join values. Specified in double quotes in the Talend UI (e.g., `","`). The XML stores this as either `&quot;,&quot;` (HTML-encoded) or `","` (raw). |
| 5 | To Denormalize (Merge same value) | `DENORMALIZE_COLUMNS` -> `MERGE` | Table (elementRef) / Boolean (CHECK) | `false` | When checked, removes duplicate consecutive values from the denormalized output. If the same value appears consecutively within a group, only one occurrence is kept. |

### 3.2 Advanced Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 6 | Null value as empty string | `NULL_AS_EMPTY` | Boolean (CHECK) | `false` | When checked, null values in the denormalized column are treated as empty strings during concatenation rather than being skipped. Only applies when the output column type is String. |
| 7 | tStatCatcher Statistics | `TSTATCATCHER_STATS` | Boolean (CHECK) | `false` | Capture processing metadata at component level for the tStatCatcher component. Unavailable in MapReduce version. |
| 8 | Label | `LABEL` | String | -- | Text label for the component in Talend Studio designer canvas. No runtime impact. |
| 9 | Connection Format | `CONNECTION_FORMAT` | String | `"row"` | Connection format type (usually "row" for standard flows). |

### 3.3 Connection Types

| Connector | Direction | Type | Description |
|-----------|-----------|------|-------------|
| `FLOW` (Main) | Input | Row > Main | Incoming row data to be denormalized. Component requires exactly one input flow. |
| `FLOW` (Main) | Output | Row > Main | Denormalized output rows. One row per unique key combination. Denormalized columns contain delimiter-separated concatenated values. |
| `SUBJOB_OK` | Output (Trigger) | Trigger | Fires when the entire subjob containing this component completes successfully. |
| `SUBJOB_ERROR` | Output (Trigger) | Trigger | Fires when the subjob containing this component fails with an error. |
| `COMPONENT_OK` | Output (Trigger) | Trigger | Fires when this specific component completes execution successfully. |
| `COMPONENT_ERROR` | Output (Trigger) | Trigger | Fires when this specific component fails with an error. |
| `RUN_IF` | Output (Trigger) | Trigger | Conditional trigger with a boolean expression. |

**Note**: tDenormalize does **not** have a REJECT output connector. All input rows are processed -- there is no rejection mechanism. Rows that cannot be denormalized (e.g., due to type issues) cause component-level errors rather than per-row rejection.

### 3.4 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
|------------------|------|----------|-------------|
| `{id}_NB_LINE` | Integer | After execution | Total number of rows transferred to the output (denormalized row count). This is an "After" scope variable, available only after the component completes. |
| `{id}_ERROR_MESSAGE` | String | On error | Error message generated by the component when an error occurs. Only populated when `DIE_ON_ERROR` is disabled. After scope. |

**Note on NB_LINE semantics**: For tDenormalize, `NB_LINE` represents the number of **output** rows (denormalized groups), not the number of input rows. This differs from input components where `NB_LINE` is the number of rows read. Talend documentation states: "the number of rows read by an input component or **transferred to an output component**."

### 3.5 Behavioral Notes

1. **Implicit group-by keys**: All columns NOT listed in the "To Denormalize" table are treated as implicit group-by keys. There is no explicit "group by" configuration. If columns A, B, C exist and B is denormalized, then A and C form the composite group key. Rows with identical (A, C) values are collapsed.

2. **Single column limitation**: Talend documentation explicitly states: "Beware as only one column can be denormalized" per tDenormalize instance. To denormalize multiple columns, multiple tDenormalize components must be chained. However, the "To Denormalize" table UI does allow adding multiple rows, creating ambiguity.

3. **Order change warning**: Official documentation warns: "This component may change the order in the incoming Java flow." The grouping operation does not preserve the original row order. Downstream components should not assume the output order matches input order.

4. **Non-denormalized column values**: For key columns, the value from the **first occurrence** within each group is retained. If a key column has different values across rows in the same group (which should not happen for a proper key), only the first value appears in the output.

5. **Merge same value behavior**: When "Merge same value" is checked, **strictly identical** consecutive values are deduplicated. The comparison is exact string equality. Values `"abc"` and `"ABC"` are NOT merged. Non-consecutive duplicates are NOT merged (e.g., `A,B,A` remains as-is because the second `A` is not consecutive to the first).

6. **Null handling**: By default, null values are skipped during concatenation. With `NULL_AS_EMPTY=true`, null values are converted to empty strings and included in the concatenated output. This means `A,null,B` becomes `A,B` (default) or `A,,B` (null_as_empty=true).

7. **Empty input**: An empty input flow produces no output rows. NB_LINE=0.

8. **Data type of denormalized column**: The output column type for the denormalized field is always String, regardless of the input column type. Numeric values are converted to their string representation before concatenation.

---

## 4. Converter Audit

### 4.1 Parameter Extraction

The converter uses a **dedicated parser method** (`parse_tdenormalize()` in `component_parser.py` lines 2738-2797). This is invoked after `parse_base_component()` has already populated `component['config']` with the raw parameter dump from `_map_component_parameters()`. Since tDenormalize has no dedicated mapping in `_map_component_parameters()`, it falls through to the `else` branch (line 384-386) which returns `config_raw` as-is.

**Converter flow**:
1. `converter.py:_parse_component()` calls `component_parser.parse_base_component(node)` (line 226)
2. `parse_base_component()` iterates all `elementParameter` nodes, builds `config_raw` dict (lines 433-458)
3. `_map_component_parameters('tDenormalize', config_raw)` hits the default `else` branch (line 384-386) and returns `config_raw` unchanged
4. Schema is extracted generically from `<metadata connector="FLOW">` nodes (lines 475-508)
5. Then `converter.py` line 370 calls `component_parser.parse_tdenormalize(node, component)`
6. `parse_tdenormalize()` adds `null_as_empty`, `connection_format`, and `denormalize_columns` to `component['config']`

**Important**: Because step 3 dumps all raw Talend parameters into `config`, and step 6 adds parsed parameters on top, the final `config` dict contains **both** raw XML parameters (like `PROPERTY_TYPE`, `LABEL`, `SCHEMA`, etc.) AND properly parsed parameters (`denormalize_columns`, `null_as_empty`, `connection_format`). The engine ignores the raw parameters (it reads only `denormalize_columns` and `null_as_empty`), so this is harmless but creates config bloat.

| # | Talend XML Parameter | Extracted? | V1 Config Key | Converter Line | Notes |
|----|----------------------|------------|---------------|----------------|-------|
| 1 | `DENORMALIZE_COLUMNS` (table) | **Yes** | `denormalize_columns` | 2754-2794 | Dedicated table parsing with elementRef-based field identification. Extracts `INPUT_COLUMN`, `DELIMITER`, `MERGE` per entry. |
| 2 | `NULL_AS_EMPTY` | **Yes** | `null_as_empty` | 2746-2747 | Boolean conversion from string. Default `false` matches Talend. |
| 3 | `CONNECTION_FORMAT` | **Yes** | `connection_format` | 2750-2751 | String extraction. Default `'row'`. |
| 4 | `SCHEMA` | Via base | (raw in config) | base 475-508 | Extracted generically by `parse_base_component()`. Type conversion applies. |
| 5 | `TSTATCATCHER_STATS` | Via base | (raw in config) | base 433-458 | Dumped as raw parameter. Not used by engine. |
| 6 | `LABEL` | Via base | (raw in config) | base 433-458 | Cosmetic. Not needed at runtime. |
| 7 | `PROPERTY_TYPE` | Via base | (raw in config) | base 433-458 | Not needed (always Built-In in converted jobs). |

**Summary**: 3 of 5 runtime-relevant parameters explicitly parsed. `DENORMALIZE_COLUMNS` table is the critical one and it is handled correctly. `NULL_AS_EMPTY` and `CONNECTION_FORMAT` are also extracted.

### 4.2 DENORMALIZE_COLUMNS Table Parsing Deep Dive

The `parse_tdenormalize()` method (lines 2754-2794) parses the `DENORMALIZE_COLUMNS` table parameter, which stores column configuration as triplets of `elementValue` nodes:

```python
# Groups elements by sets of 3 (INPUT_COLUMN, DELIMITER, MERGE)
for i in range(0, len(elements), 3):
    if i + 2 < len(elements):
        elem1 = elements[i]
        elem2 = elements[i + 1]
        elem3 = elements[i + 2]

        row_data = {}
        for elem in [elem1, elem2, elem3]:
            ref = elem.get('elementRef', '')
            value = elem.get('value', '')

            if ref == 'INPUT_COLUMN':
                row_data['input_column'] = value
            elif ref == 'DELIMITER':
                # clean delimiter: remove XML encoding and quotes
                if value.startswith('&quot;') and value.endswith('&quot;'):
                    value = value[6:-6]  # Remove &quot; from both ends
                elif value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]  # Remove quotes
                row_data['delimiter'] = value
            elif ref == 'MERGE':
                row_data['merge'] = value.lower() == 'true'
```

**Strengths**:
- Uses `elementRef` attribute to identify fields regardless of ordering within each triplet
- Handles both `&quot;` (HTML-encoded quotes) and bare `"` (raw quotes) around delimiter values
- Sets reasonable defaults: `delimiter=','`, `merge=True`

**Issues identified** (detailed in Section 4.4):
- The `&quot;` stripping removes exactly 6 characters from each end (`&quot;` = 6 chars), which is correct for a single `&quot;` wrapper. But if the delimiter value itself contains `&quot;` (e.g., a literal quote character as delimiter), the stripping will mangle it.
- The hard-coded group size of 3 assumes exactly 3 elementValue nodes per table row. If Talend adds a fourth field in a future version, or if a malformed XML has missing elements, the parsing breaks silently.
- The `i + 2 < len(elements)` guard means incomplete triplets (orphaned 1 or 2 elements at the end) are silently dropped.

### 4.3 Schema Extraction

Schema is extracted generically in `parse_base_component()` (lines 475-508 of `component_parser.py`).

| Schema Attribute | Extracted? | Notes |
|------------------|-----------|-------|
| `name` | Yes | Column name from `column.get('name')` |
| `type` | Yes | Converted via `ExpressionConverter.convert_type()` to Python types (`str`, `int`, etc.) -- **violates STANDARDS.md** which requires Talend format (`id_String`) |
| `nullable` | Yes | Boolean conversion from string `"true"/"false"` |
| `key` | Yes | Boolean conversion from string |
| `length` | Yes | Integer conversion, only if attribute present in XML |
| `precision` | Yes | Integer conversion, only if attribute present in XML |
| `pattern` (date) | Yes | Java date pattern converted to Python strftime |
| `default` | **No** | Column default value not extracted from XML |
| `comment` | **No** | Column comment not extracted (cosmetic) |
| `talendType` | **No** | Full Talend type string not preserved -- converted to Python type |

### 4.4 Converter Issues

| ID | Priority | Issue |
|----|----------|-------|
| CONV-DNR-001 | **P1** | **Delimiter `&quot;` stripping is fragile**: The converter checks `value.startswith('&quot;') and value.endswith('&quot;')` and strips 6 characters from each end (lines 2777-2778). This correctly handles the common case `&quot;,&quot;` -> `,`. However, if the delimiter is a literal quote character stored as `&quot;&quot;&quot;&quot;` (i.e., `"` wrapped in `"`), the stripping produces `&quot;` (6 chars stripped from each end of a 24-char string) instead of the intended `"`. Additionally, if the value contains only `&quot;` (exactly 6 characters), `value[6:-6]` produces an empty string, which may be the correct behavior for an empty delimiter but is ambiguous. The converter should decode XML entities first (`html.unescape()` or `xml.sax.saxutils.unescape()`), then strip surrounding quotes. |
| CONV-DNR-002 | **P1** | **`merge` flag extracted but default is `True` -- Talend default is `false`**: Line 2791 sets `'merge': row_data.get('merge', True)`, meaning if the `MERGE` elementValue is missing from the XML, the converter defaults to `True`. However, Talend's default for "Merge same value" is **unchecked** (false). This means XML files from Talend jobs where the user did not explicitly check "Merge same value" will be interpreted as merge=True in v1, altering behavior. |
| CONV-DNR-003 | **P2** | **Raw config bleed-through**: Because `_map_component_parameters()` has no dedicated mapping for `tDenormalize`, the default `else` branch (line 384-386) returns `config_raw` (all raw Talend XML parameters). These are dumped into `component['config']`, creating noise (e.g., `PROPERTY_TYPE`, `LABEL`, `SCHEMA`, `UNIQUE_NAME`, `TSTATCATCHER_STATS` all appear in config). The engine ignores them, but it increases JSON output size and may confuse debugging. |
| CONV-DNR-004 | **P3** | **Hard-coded triplet grouping is brittle**: The parser groups `elementValue` nodes in sets of 3 (line 2760: `for i in range(0, len(elements), 3)`). If Talend adds a fourth elementRef in a future version (e.g., a `SORT` option), or if XML is malformed, parsing silently produces wrong results. A more robust approach would group by detecting `INPUT_COLUMN` as the start of each row. |

---

## 5. Engine Feature Parity

### 5.1 Feature Implementation Status

| # | Talend Feature | Implemented? | Fidelity | Engine Location | Notes |
|----|----------------|-------------|----------|-----------------|-------|
| 1 | Denormalize single column | **Yes** | High | `_process()` lines 175-233 | Core groupby + agg with custom concat function |
| 2 | Implicit group-by key inference | **Yes** | High | Lines 164-165 | `key_columns = [col for col in input_data.columns if col not in denorm_col_names]` -- correct semantics |
| 3 | Delimiter-based concatenation | **Yes** | High | Lines 190-203 | Custom `make_concat_func()` closure creates delimiter-specific concat function |
| 4 | Context variable resolution in delimiter | **Yes** | High | Lines 183-185 | `context_manager.resolve_string(delimiter)` called before concatenation |
| 5 | Null handling (skip nulls) | **Yes** | High | Lines 197-199 | When `null_as_empty=false`, null values are filtered out before joining |
| 6 | Null as empty string | **Yes** | Medium | Lines 193-194 | When `null_as_empty=true`, nulls become `''`. However, empty strings ARE included in join, producing `A,,B` which matches Talend behavior. |
| 7 | Multiple denormalize columns | **Yes** | N/A | Lines 179-206 | **Extends beyond Talend**: V1 supports denormalizing multiple columns simultaneously. Talend Standard supports only one column per tDenormalize instance. This is a superset that does not break Talend jobs. |
| 8 | First-value for key columns | **Yes** | High | Lines 208-210 | `aggregation_dict[key_col] = 'first'` -- takes first value per group |
| 9 | Output column ordering | **Yes** | High | Lines 222-224 | `output_columns = key_columns + denorm_col_names` -- preserves key columns first, then denormalized columns. This may differ from Talend which preserves original column order. |
| 10 | Empty input handling | **Yes** | High | Lines 132-136 | Returns empty DataFrame with stats (0, 0, 0) |
| 11 | No denormalize columns (passthrough) | **Yes** | High | Lines 147-152 | Returns copy of input unchanged |
| 12 | Missing column validation | **Yes** | High | Lines 157-162 | Raises `DataValidationError` for columns not found in input |
| 13 | All-columns-denormalized guard | **Yes** | High | Lines 167-170 | Raises `DataValidationError` when no key columns remain |
| 14 | Statistics tracking (NB_LINE) | **Yes** | Medium | Lines 230-231 | `_update_stats(rows_in, rows_out, 0)` -- NB_LINE is input rows, NB_LINE_OK is output rows. See note on Talend semantics. |
| 15 | Config validation | **Yes** | High | Lines 64-99 | `_validate_config()` checks structure of denormalize_columns entries |
| 16 | **Merge same value** | **No** | N/A | -- | **The `merge` flag is extracted by converter but completely ignored by the engine.** The engine always concatenates all values, including duplicates. This is a functional gap for jobs that rely on deduplication. |
| 17 | **REJECT flow** | **No** | N/A | -- | **No reject output.** All errors either raise exceptions or return empty DataFrame. Not a gap per se for tDenormalize (which has no REJECT connector in Talend), but error granularity is limited. |
| 18 | **Row order preservation** | **No** | N/A | -- | **`groupby()` changes row order.** Talend warns about this, but v1 does not log any warning. Downstream components may be affected. |
| 19 | **`{id}_ERROR_MESSAGE` globalMap** | **No** | N/A | -- | Error message not stored in globalMap on failure. |

### 5.2 Behavioral Differences from Talend

| ID | Priority | Description |
|----|----------|-------------|
| ENG-DNR-001 | **P0** | **Broken import path blocks engine startup**: `engine.py` line 40 imports `Denormalize` from `.components.aggregate`, but the class is defined in `.components.transform`. The `aggregate/__init__.py` only exports `AggregateRow` and `UniqueRow`. This causes an `ImportError` at engine startup, preventing ANY job that loads the engine from running -- not just jobs using tDenormalize. The import should be `from .components.transform import AggregateSortedRow, Denormalize, Normalize, Replicate`. This is a **cross-cutting P0** because the engine cannot start at all. |
| ENG-DNR-002 | **P1** | **`merge` flag ignored**: The converter extracts `merge: true/false` for each denormalize column, but `_process()` never reads it. The engine always includes all values, including duplicates. For Talend jobs with "Merge same value" checked, duplicate values will appear in the output that should have been deduplicated. Example: input values `[A, A, B, A]` with merge=true should produce `A,B,A` (consecutive dedup) but v1 produces `A,A,B,A`. |
| ENG-DNR-003 | **P1** | **NB_LINE semantics differ**: The engine sets `NB_LINE = rows_in` (input row count) and `NB_LINE_OK = rows_out` (output/denormalized row count) on line 230. In Talend, `NB_LINE` for a non-input component means "the number of rows **transferred to an output component**", which is the output count. This means v1's `{id}_NB_LINE` is the input count, but Talend's `{id}_NB_LINE` would be the output count. Downstream components referencing `{id}_NB_LINE` will get the wrong value. |
| ENG-DNR-004 | **P1** | **Output column order may differ from Talend**: The engine forces `key_columns + denorm_col_names` ordering (line 223), placing all key columns first, then all denormalized columns. Talend preserves the original schema column order. If the schema defines columns as `[denorm_col, key_col1, key_col2]`, v1 reorders to `[key_col1, key_col2, denorm_col]`, which differs from Talend's `[denorm_col, key_col1, key_col2]`. This can break downstream components that access columns by index. |
| ENG-DNR-005 | **P2** | **`groupby()` sort behavior**: pandas `groupby()` sorts by key columns by default (unless `sort=False` is passed). This changes the row order even within the same group. Talend warns that tDenormalize "may change the order in the incoming Java flow," so order change is expected. However, the specific ordering (sorted by key vs. first-seen order) may differ between Talend and v1. |
| ENG-DNR-006 | **P2** | **No warning logged about row order change**: Talend explicitly warns users that tDenormalize may change row order. The v1 engine silently reorders without any warning in the log. A logger.warning() would help users diagnose order-dependent issues. |
| ENG-DNR-008 | **P1** | **`groupby()` silently drops rows with null key columns**: Lines 217 and 220 call `groupby()` without `dropna=False`. Pandas defaults to `dropna=True`, meaning rows where any key column is NaN/None are silently dropped from the output. Talend includes such rows. Causes silent data loss. |
| ENG-DNR-007 | **P3** | **`{id}_ERROR_MESSAGE` not set in globalMap**: When the component fails with `die_on_error=false` (not currently supported -- always dies on error), the error message should be stored in globalMap. Since tDenormalize has no `die_on_error` setting, this is low priority. |

### 5.3 GlobalMap Variable Coverage

| Variable | Talend Sets? | V1 Sets? | How V1 Sets It | Notes |
|----------|-------------|----------|-----------------|-------|
| `{id}_NB_LINE` | Yes (output rows) | **Yes** (input rows) | `_update_stats(rows_in, ...)` -> `_update_global_map()` -> `global_map.put_component_stat()` | **Semantic mismatch**: V1 stores input row count; Talend stores output row count |
| `{id}_NB_LINE_OK` | N/A | **Yes** | Same mechanism | Stores output row count. Ironically, THIS is the value Talend puts in NB_LINE. |
| `{id}_NB_LINE_REJECT` | N/A | **Yes** | Same mechanism | Always 0 (no reject mechanism in tDenormalize) |
| `{id}_ERROR_MESSAGE` | Yes (official) | **No** | -- | Not implemented |
| `{id}_EXECUTION_TIME` | N/A (v1 only) | **Yes** | Base class | V1-specific, not in Talend |

---

## 6. Code Quality

### 6.1 Bugs

| ID | Priority | Location | Description |
|----|----------|----------|-------------|
| BUG-DNR-001 | **P0** | `src/v1/engine/engine.py:40` | **Broken import path**: `from .components.aggregate import AggregateSortedRow, Denormalize, Normalize, Replicate` will raise `ImportError` because these classes are in `.components.transform`, not `.components.aggregate`. The `aggregate/__init__.py` only exports `AggregateRow` and `UniqueRow`. **CROSS-CUTTING**: This prevents the entire ETL engine from starting, blocking ALL jobs -- not just those using tDenormalize. Verified by attempting import: `ImportError: cannot import name 'Denormalize' from 'src.v1.engine.components.aggregate'`. (Note: the engine currently also fails on a prior import -- `FileInputXml` vs `FileInputXML` case mismatch in `file/__init__.py` -- meaning this bug may be masked in practice by the earlier failure.) |
| BUG-DNR-002 | **P0** | `src/v1/engine/base_component.py:304` | **`_update_global_map()` references undefined variable `value`**: The log statement uses `{stat_name}: {value}` but the loop variable is `stat_value`, not `value`. This causes `NameError` at runtime whenever `global_map` is not None. **CROSS-CUTTING**: Affects ALL components, including Denormalize. |
| BUG-DNR-003 | **P1** | `src/v1/engine/global_map.py:28` | **`GlobalMap.get()` references undefined `default` parameter**: The method signature is `def get(self, key: str) -> Optional[Any]`, but the body calls `self._map.get(key, default)`. The `default` parameter is not in the signature. Additionally, `get_component_stat()` on line 58 calls `self.get(key, default)` with two arguments, but `get()` only accepts one. **CROSS-CUTTING**: Affects all code using `global_map.get()`. |
| BUG-DNR-004 | **P2** | `src/v1/engine/components/transform/denormalize.py:193-199` | **`null_as_empty=true` includes empty strings in concatenation**: When `null_as_empty=true`, null values become `''` (empty string) and are included in the join. For input `['A', None, 'B']` with delimiter `,`, the output is `A,,B` (with empty field between delimiters). This actually matches correct Talend behavior. The comment on line 193 says "Convert nulls to empty strings" without clarifying that the empty strings are **included** in the output. This is a documentation/clarity issue, not a functional bug. |
| BUG-DNR-005 | **P2** | `src/v1/engine/components/transform/denormalize.py:214-220` | **`groupby` with `as_index=False` redundantly re-aggregates key columns**: Lines 209-210 add key columns to `aggregation_dict` with `'first'` aggregation. Lines 216-220 then call `groupby(key_columns, as_index=False).agg(aggregation_dict)`. The `as_index=False` already returns key columns as regular columns, and the `'first'` aggregation is redundant for columns that are in the `groupby` keys. While this produces correct results, it causes pandas to process key columns twice (once for grouping, once for aggregation), and may trigger a pandas `FutureWarning` about aggregating groupby columns. |
| BUG-DNR-006 | **P2** | `src/v1/engine/components/transform/denormalize.py:223-224` | **Output column order forced to keys-first**: `output_columns = key_columns + denorm_col_names` reorders columns so all keys come first. If the original schema has the denormalized column first (e.g., `[products, customer_id]`), the output will be `[customer_id, products]` instead. This differs from Talend which preserves original column order. |

### 6.2 Naming Consistency

| ID | Priority | Issue |
|----|----------|-------|
| NAME-DNR-001 | **P2** | **`denormalize_columns` config key uses underscore compound**: Consistent with other v1 components (e.g., `output_columns`, `sort_columns`). No issue. |
| NAME-DNR-002 | **P3** | **Engine class `Denormalize` vs Talend `tDenormalize`**: The `t` prefix removal is consistent with v1 naming convention. Registry correctly maps both names. No issue. |

### 6.3 Standards Compliance

| ID | Priority | Standard | Violation |
|----|----------|----------|-----------|
| STD-DNR-001 | **P2** | "Use Talend type format (`id_String`) in schemas" (STANDARDS.md) | Converter converts types to Python format (`str`, `int`) via `ExpressionConverter.convert_type()` instead of preserving Talend format (`id_String`, `id_Integer`). This is a cross-cutting issue shared with all components. |
| STD-DNR-002 | **P2** | "`_validate_config()` returns `List[str]`" (METHODOLOGY.md) | Method exists and IS called (line 126-130 of `_process()`). This is correct -- unlike many other v1 components where `_validate_config()` is dead code. However, validation is called at the start of every `_process()` invocation, meaning repeated calls on the same config wastefully re-validate. |
| STD-DNR-003 | **P3** | "No `print()` statements" (STANDARDS.md) | No print statements in `denormalize.py`. Correct. |

### 6.4 Debug Artifacts

| ID | Priority | Issue |
|----|----------|-------|
| DBG-DNR-001 | **P3** | No debug artifacts found. Code is clean. |

### 6.5 Security

| ID | Priority | Issue |
|----|----------|-------|
| SEC-DNR-001 | **P3** | **No input sanitization for delimiter**: The delimiter string is used directly in string `.join()` operations. If config comes from untrusted sources, a malicious delimiter could produce unexpected output. Not a concern for Talend-converted jobs where config is trusted. |

### 6.6 Logging Quality

The component has good logging throughout:

| Aspect | Assessment |
|--------|------------|
| Logger setup | Module-level `logger = logging.getLogger(__name__)` -- correct |
| Component ID prefix | All log messages use `[{self.id}]` prefix -- correct |
| Level usage | INFO for milestones (start/complete), DEBUG for config details and per-column delimiter, WARNING for empty input, ERROR for failures -- correct |
| Start/complete logging | `_process()` logs start (line 139); completion with counts (line 231) -- correct |
| Sensitive data | No sensitive data logged -- correct |
| No print statements | No `print()` calls -- correct |
| **Missing**: Order change warning | No warning about potential row order change, which Talend explicitly warns about |

### 6.7 Error Handling Quality

| Aspect | Assessment |
|--------|------------|
| Custom exceptions | Uses `ConfigurationError`, `DataValidationError`, `ComponentExecutionError` from `exceptions.py` -- correct |
| Exception chaining | Uses `raise ComponentExecutionError(..., e) from e` pattern (line 238) -- correct |
| Config validation | `_validate_config()` is called at start of `_process()` -- correct (unlike many other v1 components) |
| No bare `except` | Catch clause specifies `Exception` (line 235) -- correct |
| Error messages | Include component ID and error details -- correct |
| Graceful degradation | Empty input returns empty DataFrame -- correct. Missing columns raise `DataValidationError` -- correct. |

### 6.8 Type Hints

| Aspect | Assessment |
|--------|------------|
| Method signatures | `_validate_config() -> List[str]`, `_process(...) -> Dict[str, Any]` -- correct |
| Parameter types | `_process(input_data: Optional[pd.DataFrame])` -- correct |
| Class-level types | Uses `Dict`, `List`, `Optional`, `Any` from typing -- correct |
| Inner function types | `make_concat_func(delim)` lacks type hints -- minor |

---

## 7. Performance & Memory

| ID | Priority | Issue |
|----|----------|-------|
| PERF-DNR-001 | **P2** | **`groupby().agg()` materializes full copy**: The `groupby()` + `agg()` call on line 217-220 creates a complete copy of the grouped DataFrame in memory. For very large datasets with high cardinality keys (many groups), this is efficient. But for low cardinality keys (few groups, many rows per group), the concatenation of values into long strings consumes memory proportional to the total string length. No streaming/chunked mode is available. |
| PERF-DNR-002 | **P3** | **Closure creation per column**: `make_concat_func(delimiter)` creates a new function object per denormalize column (line 190). This is a minor overhead -- closure creation is O(1) and happens once per column, not per row. Not a real performance concern. |

### 7.1 Memory Management Assessment

| Aspect | Assessment |
|--------|------------|
| Streaming mode | **Not available**. Component always processes entire DataFrame in batch. No `MEMORY_THRESHOLD_MB` check. For very large input DataFrames, memory usage can spike during groupby+agg. |
| Input copy | No explicit `.copy()` of input -- `groupby()` operates on the input DataFrame directly. |
| Output copy | The `denormalized_df` is a new DataFrame created by `groupby().agg()`. No unnecessary copies. |
| String concatenation | `.join()` on list of strings is O(n) per group. Total across all groups is O(total values). Efficient. |
| Null filtering | List comprehension with filter (lines 197-199) creates temporary lists. Memory usage proportional to group size. |

### 7.2 Scalability Considerations

| Scenario | Assessment |
|----------|------------|
| Many groups, few rows per group | Efficient. `groupby()` handles this well. |
| Few groups, many rows per group | **Potential issue**: Each group produces a single string with ALL values concatenated. If a group has 1M rows, the output string could be very large. |
| Many columns | Low impact. Only denormalize columns get the custom agg function. Key columns use `'first'`. |
| Wide strings | Linear memory in total string length. No special handling. |

---

## 8. Testing

### 8.1 Current Coverage

| Test Type | Exists? | File | Notes |
|-----------|---------|------|-------|
| V1 engine unit tests | **No** | -- | Zero test files found for `Denormalize` v1 engine component |
| V1 engine integration tests | **No** | -- | No v1 engine integration tests found |
| Converter unit tests | **No** | -- | No tests for `parse_tdenormalize()` |

**Key finding**: The v1 engine has ZERO tests for this component. All 238 lines of v1 engine code and 60 lines of converter code are completely unverified.

### 8.2 Recommended Test Cases

#### P0 -- Must Have Before Production

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 1 | Basic single-column denormalize | P0 | Input: 4 rows with 2 key columns, 1 denormalize column. Verify grouping produces correct output with delimiter-separated values. |
| 2 | Empty input | P0 | Input: empty DataFrame. Verify returns empty DataFrame with stats (0, 0, 0). |
| 3 | Missing denormalize column | P0 | Input: DataFrame missing the configured denormalize column. Verify `DataValidationError` is raised with descriptive message. |
| 4 | Invalid config (no input_column) | P0 | Config: `denormalize_columns: [{"delimiter": ","}]`. Verify `ConfigurationError` is raised. |
| 5 | Single group (all rows same key) | P0 | Input: 5 rows all with same key. Verify single output row with all values concatenated. |
| 6 | Single row per group | P0 | Input: 3 rows each with unique key. Verify 3 output rows, each with a single (non-concatenated) value. |
| 7 | Statistics tracking | P0 | Verify `NB_LINE`, `NB_LINE_OK`, `NB_LINE_REJECT` set correctly in stats after execution. |

#### P1 -- Important

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 8 | Custom delimiter | P1 | Delimiter `"; "` (semicolon-space). Verify values joined with correct separator. |
| 9 | Null values with null_as_empty=false | P1 | Input includes None values. Verify nulls are excluded from concatenation. Output: `A,B` not `A,,B`. |
| 10 | Null values with null_as_empty=true | P1 | Input includes None values. Verify nulls become empty strings. Output: `A,,B`. |
| 11 | Merge same value (when implemented) | P1 | Input: `[A, A, B, A]` in a group with merge=true. Expected: `A,B,A` (consecutive dedup). Currently: `A,A,B,A` (no dedup). |
| 12 | Multiple key columns | P1 | Input: 3 key columns + 1 denormalize column. Verify composite key grouping works correctly. |
| 13 | Context variable in delimiter | P1 | Delimiter contains `${context.sep}`. Verify context_manager resolution. |
| 14 | No denormalize columns (passthrough) | P1 | Config: empty `denormalize_columns`. Verify input passed through unchanged. |
| 15 | GlobalMap integration | P1 | Verify `{id}_NB_LINE` etc. are set in globalMap after execution. |
| 16 | Output column ordering | P1 | Input with schema `[denorm_col, key_col]`. Verify output column order matches or document difference. |
| 17 | All columns denormalized (no keys) | P1 | All columns in denormalize_columns list. Verify `DataValidationError` raised. |

#### P2 -- Hardening

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 18 | Large group (10K values) | P2 | Single group with 10,000 rows. Verify concatenated string correctness and memory. |
| 19 | Mixed types in denormalize column | P2 | Column with int, float, string values. Verify all converted to string for concatenation. |
| 20 | Numeric column denormalization | P2 | Integer column. Verify numeric values converted to string (e.g., `1,2,3` not `1.0,2.0,3.0`). |
| 21 | Empty string values | P2 | Input with empty strings `""`. Verify empty strings are included in concatenation. |
| 22 | Whitespace in delimiter | P2 | Delimiter is `" | "`. Verify whitespace preserved. |
| 23 | Converter: &quot; delimiter | P2 | XML with `&quot;,&quot;` delimiter. Verify converter produces `,`. |
| 24 | Converter: bare quote delimiter | P2 | XML with `","` delimiter. Verify converter produces `,`. |
| 25 | Converter: merge=false XML | P2 | XML with MERGE value `false`. Verify converter produces `merge: false`. |
| 26 | Converter: missing MERGE element | P2 | XML with only 2 elementValues (INPUT_COLUMN, DELIMITER). Verify graceful handling. |

---

## 9. Issues Summary

### P0 -- Critical

| ID | Category | Summary |
|----|----------|---------|
| BUG-DNR-001 | Bug (Cross-Cutting) | **Broken import in `engine.py:40`**: `from .components.aggregate import ... Denormalize ...` will fail because `Denormalize` is in `.components.transform`, not `.components.aggregate`. Prevents engine from starting. Blocks ALL jobs. |
| BUG-DNR-002 | Bug (Cross-Cutting) | `_update_global_map()` in `base_component.py:304` references undefined variable `value` (should be `stat_value`). Will crash ALL components when `global_map` is set. |
| TEST-DNR-001 | Testing | Zero v1 unit tests for the Denormalize component. All 238 lines of engine code and 60 lines of converter code are unverified. |

### P1 -- Major

| ID | Category | Summary |
|----|----------|---------|
| CONV-DNR-001 | Converter | Delimiter `&quot;` stripping is fragile. Does not handle XML entity decoding properly. Literal quote delimiters will be mangled. |
| CONV-DNR-002 | Converter | Default `merge=True` contradicts Talend default of `false`. Jobs without explicit MERGE=true in XML will incorrectly have merge enabled in v1 config (though engine ignores it currently). |
| ENG-DNR-001 | Engine (Cross-Cutting) | **Broken import path** `engine.py:40`: `Denormalize` imported from `.components.aggregate` but lives in `.components.transform`. |
| ENG-DNR-002 | Engine | `merge` flag is extracted by converter but completely ignored by engine. Duplicate values are never removed. |
| ENG-DNR-003 | Engine | NB_LINE semantic mismatch: V1 stores input rows, Talend stores output rows. Downstream globalMap references get wrong value. |
| ENG-DNR-004 | Engine | Output column order forced to keys-first, differing from Talend's original-schema-order. |
| BUG-DNR-003 | Bug (Cross-Cutting) | `GlobalMap.get()` in `global_map.py:28` references undefined `default` parameter. Will crash on any `get()` call. |
| ENG-DNR-008 | Engine | `groupby()` silently drops rows with null key columns. Lines 217 and 220 call `groupby()` without `dropna=False`. Pandas defaults to `dropna=True`, meaning rows where any key column is NaN/None are silently dropped from the output. Talend includes such rows. Causes silent data loss. |
| TEST-DNR-002 | Testing | No integration test for Denormalize in a multi-step v1 job. |

### P2 -- Moderate

| ID | Category | Summary |
|----|----------|---------|
| BUG-DNR-004 | Bug | `null_as_empty=true` behavior (including empty strings in join) matches correct Talend behavior. Documentation/clarity issue, not a functional bug. |
| CONV-DNR-003 | Converter | Raw config bleed-through: all Talend XML parameters dumped into config alongside parsed values. |
| ENG-DNR-005 | Engine | `groupby()` sort changes row order. Behavior matches Talend warning but sort order may differ. |
| ENG-DNR-006 | Engine | No warning logged about row order change. Talend explicitly warns users; v1 is silent. |
| BUG-DNR-005 | Bug | `groupby` with `as_index=False` redundantly aggregates key columns with `'first'`. May trigger pandas `FutureWarning`. |
| BUG-DNR-006 | Bug | Output column order forced to keys-first instead of preserving original schema order. |
| STD-DNR-001 | Standards | Converter uses Python type format in schema instead of Talend type format. Cross-cutting. |
| STD-DNR-002 | Standards | `_validate_config()` called every `_process()` invocation -- wastefully re-validates unchanged config. |
| PERF-DNR-001 | Performance | `groupby().agg()` materializes full copy. No streaming/chunked mode for very large datasets. |

### P3 -- Low

| ID | Category | Summary |
|----|----------|---------|
| CONV-DNR-004 | Converter | Hard-coded triplet grouping for DENORMALIZE_COLUMNS table is brittle. |
| ENG-DNR-007 | Engine | `{id}_ERROR_MESSAGE` not set in globalMap on failure. |
| NAME-DNR-002 | Naming | Class name `Denormalize` vs Talend `tDenormalize` (intentional convention). |
| STD-DNR-003 | Standards | No print statements -- compliant. |
| SEC-DNR-001 | Security | No delimiter sanitization. Not a concern for Talend-converted jobs. |
| PERF-DNR-002 | Performance | Closure creation per column. Negligible overhead. |
| DBG-DNR-001 | Debug | No debug artifacts. Code is clean. |

### Issue Count Summary

| Priority | Count | Categories |
|----------|-------|------------|
| P0 | 3 | 2 bugs (cross-cutting), 1 testing |
| P1 | 9 | 2 converter, 5 engine, 1 bug (cross-cutting), 1 testing |
| P2 | 9 | 1 converter, 2 engine, 3 bugs, 2 standards, 1 performance |
| P3 | 7 | 1 converter, 1 engine, 1 naming, 1 standards, 1 security, 1 performance, 1 debug |
| **Total** | **28** | |

---

## 10. Recommendations

### Immediate (Before Production)

1. **Fix broken import path in `engine.py`** (BUG-DNR-001, ENG-DNR-001): Change line 40 from:
   ```python
   from .components.aggregate import AggregateSortedRow, Denormalize, Normalize, Replicate
   ```
   to:
   ```python
   from .components.transform import AggregateSortedRow, Denormalize, Normalize, Replicate
   ```
   **Impact**: Fixes engine startup for ALL jobs. **Risk**: Very low -- just correcting the import path.

2. **Fix `_update_global_map()` bug** (BUG-DNR-002): Change `value` to `stat_value` on `base_component.py` line 304, or remove the stale `{stat_name}: {value}` reference entirely. **Impact**: Fixes ALL components (cross-cutting). **Risk**: Very low (log message only).

3. **Fix `GlobalMap.get()` bug** (BUG-DNR-003): Add `default: Any = None` parameter to the `get()` method signature in `global_map.py` line 26. **Impact**: Fixes ALL components and any code using `global_map.get()`. **Risk**: Very low.

4. **Create unit test suite** (TEST-DNR-001): Implement at minimum the 7 P0 test cases listed in Section 8.2. These cover: basic denormalize, empty input, missing column, invalid config, single group, single row per group, and statistics tracking.

### Short-Term (Hardening)

5. **Implement `merge` same-value deduplication** (ENG-DNR-002): In `make_concat_func()`, after building the `values` list, if `merge=true` for that column, deduplicate consecutive values:
   ```python
   if merge:
       deduped = [values[0]]
       for v in values[1:]:
           if v != deduped[-1]:
               deduped.append(v)
       values = deduped
   ```
   **Impact**: Enables merge-same-value behavior matching Talend. **Risk**: Low.

6. **Fix NB_LINE semantics** (ENG-DNR-003): Change `_update_stats(rows_in, rows_out, 0)` on line 230 to `_update_stats(rows_out, rows_out, 0)`. For tDenormalize, `NB_LINE` should reflect the number of output rows transferred, matching Talend's "After" variable semantics.

7. **Fix converter `merge` default** (CONV-DNR-002): Change line 2791 from `'merge': row_data.get('merge', True)` to `'merge': row_data.get('merge', False)` to match Talend default.

8. **Preserve original column order** (ENG-DNR-004, BUG-DNR-006): Replace line 223:
   ```python
   output_columns = key_columns + denorm_col_names
   ```
   with:
   ```python
   output_columns = [col for col in input_data.columns]
   ```
   This preserves the original schema column ordering as Talend does.

9. **Fix converter delimiter parsing** (CONV-DNR-001): Replace the manual `&quot;` stripping with proper XML entity decoding:
   ```python
   import html
   value = html.unescape(value)
   if value.startswith('"') and value.endswith('"'):
       value = value[1:-1]
   ```
   This handles all XML entities correctly, not just `&quot;`.

10. **Add row order change warning** (ENG-DNR-006): Add after line 213:
    ```python
    logger.warning(f"[{self.id}] Groupby operation may change row order (consistent with Talend tDenormalize behavior)")
    ```

### Long-Term (Optimization)

11. **Remove redundant key column aggregation** (BUG-DNR-005): Remove lines 208-210 that add `'first'` aggregation for key columns. The `as_index=False` parameter on `groupby()` already includes key columns in the output. This avoids potential pandas `FutureWarning`.

12. **Add streaming/chunked mode** (PERF-DNR-001): For very large datasets, consider implementing a chunked denormalization that processes groups in batches. However, this is complex because all rows for a given group must be seen before the group can be output.

13. **Clean up raw config bleed** (CONV-DNR-003): Either add a dedicated mapping for tDenormalize in `_map_component_parameters()` that returns only the needed keys, or filter out raw parameters in `parse_tdenormalize()` before returning.

14. **Create integration test** (TEST-DNR-002): Build an end-to-end test exercising `tFileInputDelimited -> tDenormalize -> tFileOutputDelimited` in the v1 engine, verifying the full pipeline with context resolution and globalMap propagation.

---

## Appendix A: Converter Parser Code

```python
# component_parser.py lines 2738-2797
def parse_tdenormalize(self, node, component: Dict) -> Dict:
    """
    Parse tDenormalize specific configuration from Talend XML.
    Handles the DENORMALIZE_COLUMNS table parameter properly.
    """
    config = component['config']

    # Parse NULL_AS_EMPTY parameter
    null_as_empty_elem = node.find(".//elementParameter[@name='NULL_AS_EMPTY']")
    config['null_as_empty'] = null_as_empty_elem.get('value', 'false').lower() == 'true' if null_as_empty_elem is not None else False

    # Parse CONNECTION_FORMAT parameter
    connection_format_elem = node.find(".//elementParameter[@name='CONNECTION_FORMAT']")
    config['connection_format'] = connection_format_elem.get('value', 'row') if connection_format_elem is not None else 'row'

    # Parse DENORMALIZE_COLUMNS table parameter
    denormalize_columns = []
    for param in node.findall(".//elementParameter[@name='DENORMALIZE_COLUMNS']"):
        elements = param.findall('./elementValue')
        # Group elements by sets of 3 (INPUT_COLUMN, DELIMITER, MERGE)
        for i in range(0, len(elements), 3):
            if i + 2 < len(elements):
                elem1 = elements[i]
                elem2 = elements[i + 1]
                elem3 = elements[i + 2]

                row_data = {}
                for elem in [elem1, elem2, elem3]:
                    ref = elem.get('elementRef', '')
                    value = elem.get('value', '')

                    if ref == 'INPUT_COLUMN':
                        row_data['input_column'] = value
                    elif ref == 'DELIMITER':
                        if value.startswith('&quot;') and value.endswith('&quot;'):
                            value = value[6:-6]
                        elif value.startswith('"') and value.endswith('"'):
                            value = value[1:-1]
                        row_data['delimiter'] = value
                    elif ref == 'MERGE':
                        row_data['merge'] = value.lower() == 'true'

                if row_data.get('input_column'):
                    denormalize_columns.append({
                        'input_column': row_data.get('input_column', ''),
                        'delimiter': row_data.get('delimiter', ','),
                        'merge': row_data.get('merge', True)  # BUG: Default should be False
                    })

    config['denormalize_columns'] = denormalize_columns
    component['config'] = config
    return component
```

**Notes on this code**:
- Line 2777-2778: `&quot;` stripping removes exactly 6 characters per side. Works for `&quot;,&quot;` -> `,` but fails for nested `&quot;` (e.g., literal quote delimiter).
- Line 2779-2780: Bare quote stripping works correctly for standard `","` format.
- Line 2791: Default `merge=True` contradicts Talend default of `false`. Should be `False`.
- Line 2760: Hard-coded group size of 3 assumes exactly 3 elementValue nodes per table row.
- Line 2761: `i + 2 < len(elements)` guard silently drops incomplete triplets.

---

## Appendix B: Engine Class Structure

```
Denormalize (BaseComponent)
    Config Keys:
        denormalize_columns: List[Dict]   # [{input_column, delimiter, merge}]
        null_as_empty: bool               # Default: False
        connection_format: str            # Default: "row" (unused by engine)

    Methods:
        _validate_config() -> List[str]       # Validates denormalize_columns structure
        _process(input_data) -> Dict[str, Any] # Main entry point

    Internal Functions:
        make_concat_func(delim) -> Callable   # Creates closure for delimiter-specific concat
        concat_func(series) -> str            # Per-group value concatenation with null handling

    Stats:
        NB_LINE: int       # Input row count (should be output per Talend semantics)
        NB_LINE_OK: int    # Output row count
        NB_LINE_REJECT: int # Always 0

    Exceptions Raised:
        ConfigurationError        # Invalid config structure
        DataValidationError       # Missing columns, no key columns
        ComponentExecutionError   # Runtime groupby/agg failure
```

---

## Appendix C: Complete Talend Parameter to V1 Config Key Reference

| Talend Parameter | V1 Config Key | Status | Priority to Add |
|------------------|---------------|--------|-----------------|
| `DENORMALIZE_COLUMNS` -> `INPUT_COLUMN` | `denormalize_columns[].input_column` | Mapped | -- |
| `DENORMALIZE_COLUMNS` -> `DELIMITER` | `denormalize_columns[].delimiter` | Mapped | -- (fix entity decoding) |
| `DENORMALIZE_COLUMNS` -> `MERGE` | `denormalize_columns[].merge` | Mapped (wrong default) | -- (fix default to False) |
| `NULL_AS_EMPTY` | `null_as_empty` | Mapped | -- |
| `CONNECTION_FORMAT` | `connection_format` | Mapped | -- (unused by engine) |
| `SCHEMA` | `schema` | Via base parser | -- |
| `TSTATCATCHER_STATS` | (raw in config) | Not needed | -- (tStatCatcher rarely used) |
| `LABEL` | (raw in config) | Not needed | -- (cosmetic) |
| `PROPERTY_TYPE` | (raw in config) | Not needed | -- (always Built-In) |

---

## Appendix D: Denormalization Algorithm Analysis

### V1 Algorithm (pandas groupby)

```
Input:
  customer_id | product
  ------------|--------
  1           | apple
  1           | banana
  1           | apple
  2           | cherry

Config: denormalize_columns=[{input_column: "product", delimiter: ",", merge: false}]

Step 1: Identify keys = [customer_id], denorm = [product]
Step 2: groupby(customer_id, as_index=False).agg({
            product: concat_func(","),   # Custom lambda
            customer_id: 'first'         # Redundant for groupby key
        })
Step 3: concat_func for group 1: ["apple", "banana", "apple"] -> "apple,banana,apple"
        concat_func for group 2: ["cherry"] -> "cherry"
Step 4: Reorder columns to [customer_id, product]

Output:
  customer_id | product
  ------------|------------------
  1           | apple,banana,apple
  2           | cherry
```

### Talend Algorithm (with merge=true)

```
Same input, merge=true:

Step 3: Consecutive dedup: ["apple", "banana", "apple"] -> ["apple", "banana", "apple"]
        (Only consecutive duplicates removed, not all duplicates)

Output (same as without merge in this case):
  customer_id | product
  ------------|------------------
  1           | apple,banana,apple
  2           | cherry

But for input [apple, apple, banana, apple]:
  With merge=true:  "apple,banana,apple"  (consecutive "apple,apple" -> "apple")
  With merge=false: "apple,apple,banana,apple"
```

### V1 Gap: merge=true Not Implemented

The V1 engine always produces the merge=false output regardless of the merge flag value.

---

## Appendix E: Edge Case Analysis

### Edge Case 1: Empty input DataFrame

| Aspect | Detail |
|--------|--------|
| **Talend** | Returns 0 rows. NB_LINE=0. |
| **V1** | `_process()` line 132-136: Returns empty DataFrame. Stats (0, 0, 0). |
| **Verdict** | CORRECT |

### Edge Case 2: All rows have same key

| Aspect | Detail |
|--------|--------|
| **Talend** | Single output row with all values concatenated. |
| **V1** | `groupby()` produces single group. Concat produces single joined string. |
| **Verdict** | CORRECT |

### Edge Case 3: Each row has unique key

| Aspect | Detail |
|--------|--------|
| **Talend** | N output rows, each with a single (non-concatenated) value. NB_LINE=N. |
| **V1** | `groupby()` produces N groups, each with one value. No delimiter in output. |
| **Verdict** | CORRECT |

### Edge Case 4: Null values in denormalize column (null_as_empty=false)

| Aspect | Detail |
|--------|--------|
| **Talend** | Nulls are skipped. `A,null,B` -> `A,B`. |
| **V1** | Lines 197-199: Nulls filtered out with `[val for val in values if val is not None]`. Then joined. |
| **Verdict** | CORRECT |

### Edge Case 5: Null values in denormalize column (null_as_empty=true)

| Aspect | Detail |
|--------|--------|
| **Talend** | Nulls become empty strings. `A,null,B` -> `A,,B`. |
| **V1** | Lines 193-194: Nulls become `''`. All values (including empty strings) are joined. `A,,B`. |
| **Verdict** | CORRECT |

### Edge Case 6: All values null in a group (null_as_empty=false)

| Aspect | Detail |
|--------|--------|
| **Talend** | Output is empty string for the denormalized column. |
| **V1** | All values filtered out. `values = []`. `''.join([])` = `''`. |
| **Verdict** | CORRECT |

### Edge Case 7: Null values in key columns

| Aspect | Detail |
|--------|--------|
| **Talend** | Null key values form their own group (null == null for grouping). |
| **V1** | pandas `groupby()` by default **excludes** rows with NaN keys (`dropna=True`). These rows are silently dropped. |
| **Verdict** | **GAP** -- V1 drops rows with null keys. Talend groups them. Should use `groupby(..., dropna=False)`. |

### Edge Case 8: Denormalize column contains delimiter character

| Aspect | Detail |
|--------|--------|
| **Talend** | No escaping. If values contain the delimiter, the output is ambiguous. |
| **V1** | Same behavior -- `.join()` does not escape. |
| **Verdict** | CORRECT (both have same limitation) |

### Edge Case 9: Empty string delimiter

| Aspect | Detail |
|--------|--------|
| **Talend** | Values concatenated with no separator. `AB` from `[A, B]`. |
| **V1** | `''.join(['A', 'B'])` = `'AB'`. |
| **Verdict** | CORRECT |

### Edge Case 10: Multi-character delimiter

| Aspect | Detail |
|--------|--------|
| **Talend** | Supports multi-character delimiters. `" | "` produces `A | B | C`. |
| **V1** | `' | '.join(['A', 'B', 'C'])` = `'A | B | C'`. |
| **Verdict** | CORRECT |

### Edge Case 11: Multiple denormalize columns

| Aspect | Detail |
|--------|--------|
| **Talend** | Only supports one column per tDenormalize instance. |
| **V1** | Supports multiple columns simultaneously via the `denormalize_columns` list. |
| **Verdict** | **SUPERSET** -- V1 extends beyond Talend. Not a bug, but may produce unexpected results if someone manually adds multiple columns to a config that was converted from Talend. |

### Edge Case 12: Numeric values in denormalize column

| Aspect | Detail |
|--------|--------|
| **Talend** | Numeric values converted to string. Integer 42 -> "42". |
| **V1** | Line 194/197: `str(val)` converts numbers to strings. Integer 42 -> "42". Float 42.0 -> "42.0". |
| **Verdict** | **PARTIAL** -- Integer values produce "42" (correct), but float values produce "42.0" (may differ from Talend if Talend strips trailing ".0"). |

### Edge Case 13: Boolean values in denormalize column

| Aspect | Detail |
|--------|--------|
| **Talend** | Java boolean `true`/`false` (lowercase). |
| **V1** | Python `str(True)` = "True" (capitalized), `str(False)` = "False". |
| **Verdict** | **GAP** -- Python produces "True"/"False" while Talend produces "true"/"false". |

### Edge Case 14: Rows with null keys (groupby dropna)

| Aspect | Detail |
|--------|--------|
| **Talend** | Null keys form their own group. |
| **V1** | pandas `groupby()` default is `dropna=True`, which silently drops rows with NaN in key columns. |
| **Verdict** | **GAP** -- V1 loses rows with null keys. Should pass `dropna=False` to `groupby()`. |

---

## Appendix F: Cross-Cutting Issues

The following issues were discovered during this audit but affect the entire v1 engine, not just `Denormalize`:

| ID | Priority | Component | Issue |
|----|----------|-----------|-------|
| BUG-DNR-001 | **P0** | `engine.py:40` | Broken import: `Denormalize` imported from `.components.aggregate` but lives in `.components.transform`. Prevents engine startup for ALL jobs. |
| BUG-DNR-002 | **P0** | `base_component.py:304` | `_update_global_map()` references undefined `value` variable. Will crash ALL components when `global_map` is set. |
| BUG-DNR-003 | **P1** | `global_map.py:28` | `GlobalMap.get()` references undefined `default` parameter. Will crash on any `global_map.get()` call. |
| STD-DNR-001 | **P2** | `component_parser.py` | Schema types converted to Python format instead of Talend format. Affects all components. |

These should be tracked in a cross-cutting issues report as well.

---

## Appendix G: Implementation Fix Guides

### Fix Guide: BUG-DNR-001 -- Broken import path

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

**Explanation**: `Denormalize`, `AggregateSortedRow`, `Normalize`, and `Replicate` are all defined in the `transform` package (`src/v1/engine/components/transform/`), not the `aggregate` package. The `aggregate/__init__.py` only exports `AggregateRow` and `UniqueRow`.

**Impact**: Fixes engine startup for ALL jobs. **Risk**: Very low (correcting import path only).

---

### Fix Guide: BUG-DNR-002 -- `_update_global_map()` undefined variable

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

**Impact**: Fixes ALL components (cross-cutting). **Risk**: Very low (log message only).

---

### Fix Guide: BUG-DNR-003 -- `GlobalMap.get()` undefined default

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

**Impact**: Fixes ALL components and any code calling `global_map.get()`. **Risk**: Very low (adds optional parameter with backward-compatible default).

---

### Fix Guide: ENG-DNR-002 -- Implementing merge same value

**File**: `src/v1/engine/components/transform/denormalize.py`

In `_process()`, modify the loop that builds `aggregation_dict` to pass the `merge` flag to the closure:

```python
for col_config in denormalize_columns:
    col_name = col_config['input_column']
    delimiter = col_config.get('delimiter', ',')
    merge = col_config.get('merge', False)

    if self.context_manager:
        delimiter = self.context_manager.resolve_string(delimiter)

    def make_concat_func(delim, do_merge):
        def concat_func(series):
            if null_as_empty:
                values = [str(val) if pd.notnull(val) else '' for val in series]
            else:
                values = [str(val) if pd.notnull(val) else None for val in series]
                values = [val for val in values if val is not None]

            # Merge consecutive duplicates
            if do_merge and values:
                deduped = [values[0]]
                for v in values[1:]:
                    if v != deduped[-1]:
                        deduped.append(v)
                values = deduped

            result = delim.join(values) if values else ''
            return result
        return concat_func

    aggregation_dict[col_name] = make_concat_func(delimiter, merge)
```

**Impact**: Enables merge-same-value deduplication matching Talend behavior. **Risk**: Low (additive change, disabled by default).

---

### Fix Guide: ENG-DNR-004 -- Preserve original column order

**File**: `src/v1/engine/components/transform/denormalize.py`
**Line**: 223

**Current**:
```python
output_columns = key_columns + denorm_col_names
```

**Fix**:
```python
output_columns = [col for col in input_data.columns if col in key_columns or col in denorm_col_names]
```

**Explanation**: This preserves the original DataFrame column ordering instead of forcing keys first. Matches Talend's behavior of maintaining schema column order.

---

### Fix Guide: Edge Case 14 -- Null keys dropped by groupby

**File**: `src/v1/engine/components/transform/denormalize.py`
**Lines**: 216-220

**Current**:
```python
if len(key_columns) == 1:
    denormalized_df = input_data.groupby(key_columns[0], as_index=False).agg(aggregation_dict)
else:
    denormalized_df = input_data.groupby(key_columns, as_index=False).agg(aggregation_dict)
```

**Fix**:
```python
if len(key_columns) == 1:
    denormalized_df = input_data.groupby(key_columns[0], as_index=False, dropna=False).agg(aggregation_dict)
else:
    denormalized_df = input_data.groupby(key_columns, as_index=False, dropna=False).agg(aggregation_dict)
```

**Explanation**: Adding `dropna=False` ensures rows with null key values are grouped together (null == null) rather than being silently dropped. Matches Talend behavior.

---

## Appendix H: Risk Assessment for Production Migration

### High-Risk Scenarios

| Scenario | Risk Level | Affected Jobs | Mitigation |
|----------|-----------|---------------|------------|
| Engine startup failure (broken import) | **Critical** | ALL jobs | Fix import path in engine.py line 40 |
| Jobs using "Merge same value" | **High** | Jobs with merge=true on tDenormalize | Implement merge dedup in engine |
| Jobs referencing `{id}_NB_LINE` downstream | **High** | Jobs using globalMap NB_LINE from tDenormalize | Fix NB_LINE semantics to store output count |
| Jobs relying on column order | **Medium** | Jobs accessing columns by index after tDenormalize | Preserve original column order |
| Jobs with null key values | **Medium** | Jobs where key columns can be null | Add dropna=False to groupby |

### Low-Risk Scenarios

| Scenario | Risk Level | Notes |
|----------|-----------|-------|
| Jobs with single non-null key column | Low | Core functionality works correctly |
| Jobs with simple delimiters (comma, semicolon) | Low | Delimiter handling is solid |
| Jobs without merge same value | Low | Default behavior (no merge) works |
| Jobs with null_as_empty setting | Low | Both true/false cases handled correctly |

### Recommended Migration Strategy

1. **Phase 1**: Fix all P0 bugs (import path, base class bugs). Verify engine can start.
2. **Phase 2**: Audit each target job's Talend configuration. Check for merge=true, null keys, column order dependencies.
3. **Phase 3**: Implement P1 features required by target jobs (merge dedup, NB_LINE fix, column order).
4. **Phase 4**: Parallel-run migrated jobs against Talend originals. Compare output row-for-row.
5. **Phase 5**: Fix any differences found in parallel-run testing.

---

## Appendix I: Comparison with Related Components

| Feature | tDenormalize (V1) | tNormalize (V1) | tAggregateSortedRow (V1) |
|---------|-------------------|-----------------|--------------------------|
| Groupby keys | Implicit (all non-denorm cols) | N/A (splits rows) | Explicit key columns |
| Value handling | Concatenate with delimiter | Split on delimiter | Aggregate (sum, count, etc.) |
| Null handling | Skip or empty string | N/A | Varies by function |
| Merge same value | **Not implemented** | N/A | N/A |
| Column order | Forced keys-first | Preserves original | Varies |
| Streaming mode | No | No | No |
| REJECT flow | No | No | No |
| V1 Unit tests | **No** | **No** | **No** |
| Import path | **BROKEN** | **BROKEN** (same import line) | **BROKEN** (same import line) |

**Observation**: The broken import path on engine.py line 40 affects ALL four components imported from the wrong package: `AggregateSortedRow`, `Denormalize`, `Normalize`, and `Replicate`. This is a systemic issue, not component-specific.

---

## Appendix J: Talend tDenormalize XML Example

### Example XML for DENORMALIZE_COLUMNS table

```xml
<elementParameter field="TABLE" name="DENORMALIZE_COLUMNS" show="true">
    <elementValue elementRef="INPUT_COLUMN" value="product_name"/>
    <elementValue elementRef="DELIMITER" value="&quot;,&quot;"/>
    <elementValue elementRef="MERGE" value="false"/>
</elementParameter>
```

### Converter parsing result

```json
{
    "denormalize_columns": [
        {
            "input_column": "product_name",
            "delimiter": ",",
            "merge": false
        }
    ],
    "null_as_empty": false,
    "connection_format": "row"
}
```

### Example with multiple columns (V1 extension, not standard Talend)

```json
{
    "denormalize_columns": [
        {
            "input_column": "product_name",
            "delimiter": ",",
            "merge": false
        },
        {
            "input_column": "quantity",
            "delimiter": "; ",
            "merge": true
        }
    ],
    "null_as_empty": true
}
```

---

## Appendix K: Complete Engine Implementation Walkthrough

### `_validate_config()` (Lines 64-99)

Validates:
- `denormalize_columns` is a list (if provided)
- Each entry is a dict with string `input_column` and optional string `delimiter`
- `null_as_empty` is boolean

**Called**: Yes, at the start of `_process()` (line 126-130). Unlike many v1 components where `_validate_config()` is dead code, this component correctly invokes validation.

### `_process()` (Lines 101-238)

The main processing method:
1. Validate config (lines 126-130)
2. Handle empty input (lines 132-136)
3. Extract config values (lines 142-143)
4. Handle no-columns passthrough (lines 148-152)
5. Extract and validate column names (lines 155-162)
6. Infer key columns (lines 164-170)
7. Build aggregation functions per column (lines 177-206)
8. Execute groupby + agg (lines 213-220)
9. Reorder output columns (lines 222-224)
10. Update stats and return (lines 226-233)
11. Exception handler wraps in ComponentExecutionError (lines 235-238)

### `make_concat_func()` (Lines 190-204)

Closure factory creating delimiter-specific concatenation functions:
- `null_as_empty=true`: Nulls -> `''`, all values joined
- `null_as_empty=false`: Nulls filtered, non-null values joined
- Returns empty string `''` if no values remain after filtering

**Note**: The `merge` flag from config is NOT passed to this function. It is completely ignored.

### GroupBy Strategy (Lines 214-220)

Two code paths based on key column count:
- Single key: `groupby(key_columns[0], as_index=False)`
- Multiple keys: `groupby(key_columns, as_index=False)`

Both produce the same result -- the split is unnecessary since pandas handles single-element lists in `groupby()`. However, the single-key path avoids creating a MultiIndex, which is a minor optimization.

**Missing**: `dropna=False` parameter. Rows with null keys are silently dropped.

### Error Handling (Lines 235-238)

```python
except Exception as e:
    logger.error(f"[{self.id}] Denormalization failed: {e}")
    self._update_stats(rows_in, 0, rows_in)
    raise ComponentExecutionError(self.id, f"Denormalization failed: {e}", e) from e
```

On failure:
- Logs error with component ID
- Sets stats: NB_LINE=input, NB_LINE_OK=0, NB_LINE_REJECT=input (all input treated as rejected)
- Wraps in `ComponentExecutionError` with proper chaining (`from e`)

**Note**: There is no `die_on_error` flag -- the component always raises on error. This matches Talend behavior since tDenormalize does not have a `DIE_ON_ERROR` setting.

---

## Appendix L: Detailed Converter Flow Trace

### Step-by-Step Conversion of a tDenormalize Node

Given a Talend XML node like:

```xml
<node componentName="tDenormalize" componentVersion="0.102" offsetLabelX="0" offsetLabelY="0" posX="480" posY="256">
    <elementParameter field="TEXT" name="UNIQUE_NAME" value="tDenormalize_1"/>
    <elementParameter field="TEXT" name="LABEL" value="&quot;tDenormalize_1&quot;"/>
    <elementParameter field="CHECK" name="NULL_AS_EMPTY" value="true"/>
    <elementParameter field="CLOSED_LIST" name="CONNECTION_FORMAT" value="row"/>
    <elementParameter field="CHECK" name="TSTATCATCHER_STATS" value="false"/>
    <elementParameter field="TABLE" name="DENORMALIZE_COLUMNS" show="true">
        <elementValue elementRef="INPUT_COLUMN" value="city"/>
        <elementValue elementRef="DELIMITER" value="&quot;, &quot;"/>
        <elementValue elementRef="MERGE" value="true"/>
    </elementParameter>
    <metadata connector="FLOW" label="tDenormalize_1" name="tDenormalize_1">
        <column key="true" name="state" nullable="false" type="id_String"/>
        <column key="false" name="city" nullable="true" type="id_String"/>
    </metadata>
</node>
```

**Step 1: `parse_base_component()` (component_parser.py line 388)**

Creates the base component structure:
```json
{
    "id": "tDenormalize_1",
    "type": "Denormalize",
    "original_type": "tDenormalize",
    "position": {"x": 480, "y": 256},
    "config": {},
    "schema": {"input": [], "output": []},
    "inputs": [],
    "outputs": []
}
```

**Step 2: Generic parameter extraction (lines 433-458)**

Iterates all `elementParameter` nodes and builds `config_raw`:
```python
config_raw = {
    "LABEL": "tDenormalize_1",       # Quotes stripped by line 441-442
    "NULL_AS_EMPTY": True,            # Converted to bool by CHECK field handler (line 445-446)
    "CONNECTION_FORMAT": "row",
    "TSTATCATCHER_STATS": False       # Converted to bool
}
```

Note: `DENORMALIZE_COLUMNS` is a TABLE field type, so its `elementValue` children are NOT captured by the generic parameter loop (which only reads the `value` attribute of `elementParameter` nodes). Table parameters require dedicated parsing.

**Step 3: `_map_component_parameters('tDenormalize', config_raw)` (line 472)**

No dedicated mapping for `tDenormalize` -- falls through to the `else` branch (line 384-386):
```python
# Returns config_raw unchanged
component['config'] = config_raw
```

So `component['config']` now contains the raw parameters:
```json
{
    "LABEL": "tDenormalize_1",
    "NULL_AS_EMPTY": true,
    "CONNECTION_FORMAT": "row",
    "TSTATCATCHER_STATS": false
}
```

**Step 4: Schema extraction (lines 475-508)**

Parses `<metadata connector="FLOW">`:
```json
{
    "schema": {
        "input": [],
        "output": [
            {"name": "state", "type": "str", "nullable": false, "key": true},
            {"name": "city", "type": "str", "nullable": true, "key": false}
        ]
    }
}
```

**Step 5: `parse_tdenormalize(node, component)` (converter.py line 370)**

Runs the dedicated parser which adds:
- `null_as_empty`: Re-parses from XML (finds `true`). Overwrites the existing `True` in config. Redundant but harmless.
- `connection_format`: Re-parses from XML (finds `"row"`). Overwrites the existing `"row"`. Redundant.
- `denormalize_columns`: Parses the TABLE parameter (this is the new data):

```json
{
    "denormalize_columns": [
        {
            "input_column": "city",
            "delimiter": ", ",
            "merge": true
        }
    ]
}
```

The `&quot;, &quot;` delimiter is decoded: `value.startswith('&quot;')` matches, so `value[6:-6]` produces `", "` -> after further stripping, produces `, ` (comma-space).

Wait -- let us trace this more carefully:
- Original value: `&quot;, &quot;` (14 characters: `&quot;` + `, ` + `&quot;`)
- `value.startswith('&quot;')` -> True (starts with `&quot;`)
- `value.endswith('&quot;')` -> True (ends with `&quot;`)
- `value[6:-6]` -> `", "` becomes `, ` (14 - 6 - 6 = 2 characters: `, `)

Correct: delimiter is `, ` (comma-space).

**Final component config**:
```json
{
    "LABEL": "tDenormalize_1",
    "NULL_AS_EMPTY": true,
    "TSTATCATCHER_STATS": false,
    "null_as_empty": true,
    "connection_format": "row",
    "denormalize_columns": [
        {
            "input_column": "city",
            "delimiter": ", ",
            "merge": true
        }
    ]
}
```

Note the redundancy: `NULL_AS_EMPTY` (raw, boolean) and `null_as_empty` (parsed, boolean) coexist. The engine reads `null_as_empty` (lowercase with underscores) and ignores `NULL_AS_EMPTY`.

---

## Appendix M: Detailed Null Handling Matrix

### All Null Handling Scenarios

| Input Values | null_as_empty | Expected (Talend) | V1 Output | Match? |
|-------------|---------------|-------------------|-----------|--------|
| `["A", "B", "C"]` | false | `A,B,C` | `A,B,C` | Yes |
| `["A", "B", "C"]` | true | `A,B,C` | `A,B,C` | Yes |
| `["A", null, "C"]` | false | `A,C` | `A,C` | Yes |
| `["A", null, "C"]` | true | `A,,C` | `A,,C` | Yes |
| `[null, null, null]` | false | `` (empty) | `` (empty) | Yes |
| `[null, null, null]` | true | `,,` | `,,` | Yes |
| `[null, "A"]` | false | `A` | `A` | Yes |
| `[null, "A"]` | true | `,A` | `,A` | Yes |
| `["A", null]` | false | `A` | `A` | Yes |
| `["A", null]` | true | `A,` | `A,` | Yes |
| `[""]` | false | `` (empty) | `` (empty) | Yes |
| `[""]` | true | `` (empty) | `` (empty) | Yes |
| `[null]` | false | `` (empty) | `` (empty) | Yes |
| `[null]` | true | `` (empty) | `` (empty) | Yes |
| `["A", "", "C"]` | false | `A,,C` | `A,,C` | Yes |
| `["A", "", "C"]` | true | `A,,C` | `A,,C` | Yes |

**Key insight**: Empty strings (`""`) are ALWAYS included in concatenation, regardless of `null_as_empty`. Only `None`/`NaN` values are affected by the flag. This is correct behavior matching Talend.

---

## Appendix N: Merge Same Value Algorithm Specification

### Talend Behavior (Official)

The "Merge same value" checkbox removes **strictly identical consecutive** values. The comparison is:
- Case-sensitive (`"abc"` != `"ABC"`)
- Exact match (no trimming, no type coercion)
- **Consecutive only** -- non-adjacent duplicates are preserved

### Examples

| Input | merge=false | merge=true | Notes |
|-------|-------------|------------|-------|
| `[A, B, C]` | `A,B,C` | `A,B,C` | No duplicates |
| `[A, A, B]` | `A,A,B` | `A,B` | Consecutive `A,A` merged |
| `[A, B, A]` | `A,B,A` | `A,B,A` | Non-consecutive `A` not merged |
| `[A, A, A]` | `A,A,A` | `A` | All consecutive |
| `[A, A, B, B, A, A]` | `A,A,B,B,A,A` | `A,B,A` | Each run collapsed |
| `[A, a, A]` | `A,a,A` | `A,a,A` | Case-sensitive, no merge |
| `[, , A]` (empty strings) | `,,A` | `,A` | Empty strings are values too |
| `[null, null, A]` (null_as_empty=true) | `,,A` | `,A` | Nulls become empty, then merged |
| `[null, null, A]` (null_as_empty=false) | `A` | `A` | Nulls filtered first, no merge needed |

### V1 Gap

The v1 engine does not implement merge. All columns produce the merge=false output regardless of the flag value. The fix guide in Appendix G (Fix Guide: ENG-DNR-002) provides the implementation.

---

## Appendix O: GroupBy Behavior Deep Dive

### pandas groupby vs Talend grouping

| Behavior | Talend tDenormalize | V1 pandas groupby | Difference |
|----------|--------------------|--------------------|-----------|
| Sort by keys | Not documented; Java HashMap order | Yes (default `sort=True`) | V1 sorts keys; Talend order is implementation-dependent |
| Null key handling | Null keys form own group | Nulls dropped (`dropna=True` default) | **GAP**: V1 loses null-key rows |
| Key value for output | First occurrence | First occurrence (`'first'` agg) | Match |
| Concatenation order within group | Preserves input order within group | Preserves input order within group | Match |
| Empty groups | Not applicable (groups from data) | Not applicable | N/A |
| Column order | Preserves schema order | Forced keys-first | **GAP** |

### Recommended groupby Parameters

Current:
```python
input_data.groupby(key_columns, as_index=False).agg(aggregation_dict)
```

Recommended:
```python
input_data.groupby(key_columns, as_index=False, sort=False, dropna=False).agg(aggregation_dict)
```

- `sort=False`: Preserves first-seen key order instead of sorting. Better matches Talend's non-guaranteed-order behavior and improves performance.
- `dropna=False`: Includes rows with null keys. Matches Talend behavior.

### Impact of sort=False

| Key Values (order of appearance) | sort=True (current) | sort=False (recommended) |
|----------------------------------|---------------------|--------------------------|
| `[C, A, B, A, C]` | Output order: A, B, C | Output order: C, A, B |
| `[3, 1, 2]` | Output order: 1, 2, 3 | Output order: 3, 1, 2 |

Since Talend warns that row order may change, neither behavior is "wrong." However, `sort=False` is more performant (avoids sort step) and closer to Talend's HashMap-based grouping which produces arbitrary order.

---

## Appendix P: Comparison with Talend Generated Java Code

### Talend-generated tDenormalize Java pseudocode

```java
// Talend generates code similar to:
Map<String, List<String>> groups = new LinkedHashMap<>();

for (Row row : inputRows) {
    String key = row.getKeyColumns();  // Composite key
    String value = row.getDenormColumn();

    if (!groups.containsKey(key)) {
        groups.put(key, new ArrayList<>());
    }

    if (value == null && nullAsEmpty) {
        value = "";
    }

    if (value != null) {
        List<String> values = groups.get(key);
        if (mergeSameValue && !values.isEmpty()
            && values.get(values.size() - 1).equals(value)) {
            // Skip consecutive duplicate
        } else {
            values.add(value);
        }
    }
}

// Output
for (Map.Entry<String, List<String>> entry : groups.entrySet()) {
    outputRow.setKeyColumns(entry.getKey());
    outputRow.setDenormColumn(String.join(delimiter, entry.getValue()));
    output(outputRow);
}
```

### Key Observations

1. **LinkedHashMap**: Talend uses `LinkedHashMap`, which preserves insertion order. V1's `groupby(sort=True)` sorts alphabetically. Using `sort=False` would better match.

2. **Merge check at insertion time**: Talend checks for consecutive duplicates **at insertion time** (comparing with the last element in the list). This is O(1) per element. V1's proposed fix (post-collection dedup) is equivalent but processes the list after collection.

3. **Null handling at insertion time**: Talend converts null to empty string BEFORE checking if the value should be added. V1 does the same (null handling happens before join).

4. **Single-pass algorithm**: Talend processes rows in a single pass with a HashMap. V1 uses pandas `groupby()` which internally also uses a hash-based grouping. Performance should be comparable.

---

## Appendix Q: Test Data Generator

For quick manual testing, the following Python snippet creates test data covering key scenarios:

```python
import pandas as pd

# Basic test data
df = pd.DataFrame({
    'customer_id': [1, 1, 1, 2, 2, 3],
    'region': ['East', 'East', 'East', 'West', 'West', 'North'],
    'product': ['apple', 'banana', 'apple', 'cherry', None, 'date'],
    'quantity': [10, 20, 10, 30, 40, 50]
})

# Expected outputs:
# With delimiter="," null_as_empty=false merge=false:
#   customer_id=1, region=East, product="apple,banana,apple", quantity="10,20,10"
#   customer_id=2, region=West, product="cherry", quantity="30,40"
#   customer_id=3, region=North, product="date", quantity="50"
#
# With delimiter="," null_as_empty=true merge=false:
#   customer_id=2, region=West, product="cherry,", quantity="30,40"
#
# With delimiter="," null_as_empty=false merge=true:
#   customer_id=1, region=East, product="apple,banana,apple", quantity="10,20,10"
#   (merge only removes CONSECUTIVE dupes; "apple" at positions 0 and 2 are not consecutive)
#
# Edge case: null key
df_null_key = pd.DataFrame({
    'key': [1, None, None, 2],
    'value': ['A', 'B', 'C', 'D']
})
# Talend: key=1 -> "A", key=null -> "B,C", key=2 -> "D"
# V1 (current, dropna=True): key=1 -> "A", key=2 -> "D"  (null rows LOST)
```

This test data covers:
- Multiple groups with different sizes
- Null values in denormalize column
- Duplicate values (for merge testing)
- Null values in key columns (for dropna testing)
- Numeric values in denormalize column (type coercion testing)
