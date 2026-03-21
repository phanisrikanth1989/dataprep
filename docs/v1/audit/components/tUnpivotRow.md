# Audit Report: tUnpivotRow / UnpivotRow

> **Audited**: 2026-03-21
> **Auditor**: Claude Opus 4.6 (automated)
> **Engine Version**: v1
> **Converter**: `complex_converter`
> **Status**: PRODUCTION READINESS REVIEW

---

## 1. Component Identity

| Field | Value |
|-------|-------|
| **Talend Name** | `tUnpivotRow` |
| **V1 Engine Class** | `UnpivotRow` |
| **Engine File** | `src/v1/engine/components/transform/unpivot_row.py` (235 lines) |
| **Converter Parser** | `src/converters/complex_converter/component_parser.py` -> `parse_unpivot_row()` (lines 2480-2506) |
| **Converter Dispatch** | `src/converters/complex_converter/converter.py` -> `elif component_type == 'tUnpivotRow':` (line 355) |
| **Registry Aliases** | `UnpivotRow`, `tUnpivotRow` (registered in `src/v1/engine/engine.py` lines 156-157) |
| **Category** | Transform |

### Key Files

| File | Purpose |
|------|---------|
| `src/v1/engine/components/transform/unpivot_row.py` | Engine implementation (235 lines) |
| `src/converters/complex_converter/component_parser.py` (lines 2480-2506) | Parameter mapping from Talend XML to v1 JSON |
| `src/converters/complex_converter/converter.py` (line 355-356) | Dispatch -- dedicated `elif` branch for `tUnpivotRow` |
| `src/v1/engine/base_component.py` | Base class: `_update_stats()`, `_update_global_map()`, `validate_schema()`, `execute()` |
| `src/v1/engine/global_map.py` | GlobalMap storage for `{id}_NB_LINE` etc. |
| `src/v1/engine/exceptions.py` | Custom exception hierarchy (`ConfigurationError`, `ComponentExecutionError`, `DataValidationError`) |
| `src/v1/engine/components/transform/__init__.py` | Package exports -- exports `UnpivotRow` |
| `src/v1/engine/engine.py` | Registry -- maps `'UnpivotRow'` and `'tUnpivotRow'` to `UnpivotRow` class |

---

## 2. Scorecard

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
|-----------|-------|----|----|----|----|---------|
| Converter Coverage | **R** | 2 | 4 | 2 | 1 | Incorrect XML access method for all params except ROW_KEYS; hardcoded domain fallback; config key mismatch with engine; INCLUDE_NULL_VALUES not extracted |
| Engine Feature Parity | **Y** | 1 | 4 | 3 | 1 | Output schema pollution; no String coercion; no die_on_error; no reject flow; extra columns in output |
| Code Quality | **Y** | 1 | 5 | 8 | 2 | Dead code blocks; filtered rows not in stats; dual validation paths; ValueError instead of ConfigurationError; inconsistent naming; _original_order column collision; pivot_key/pivot_value name collision with row_keys; alphabetical sort breaks schema-order |
| Performance & Memory | **Y** | 0 | 1 | 4 | 1 | Unnecessary full copy; redundant no-op filter; chained DataFrame copies; expensive sort |
| Testing | **R** | 1 | 1 | 0 | 0 | Zero v1 unit tests; zero converter parser tests; zero integration tests |

**Overall: RED -- Not production-ready; 6 P0 blockers must be resolved**

### Score Key
- **R** (Red): Critical gaps blocking production use
- **Y** (Yellow): Significant gaps; usable for subset of jobs with known limitations
- **G** (Green): Production-ready with minor improvements recommended

---

## 3. Talend Feature Baseline

### What tUnpivotRow Does

`tUnpivotRow` is a **custom Talend Exchange component** (not a built-in Talend component) that converts columns into rows -- the inverse of a pivot operation. Given a set of "row key" (identifier) columns and a set of "value" columns, it produces one output row per value column per input row, creating key-value pairs. It is commonly used to denormalize wide datasets into a narrow/long format.

**Source**: [Talend Skill: tUnpivotRow](https://talendskill.com/knowledgebase/tunpivotrow-talend-custom-components/), [Datalytyx: Denormalise a dataset with tUnpivotRow](https://www.datalytyx.com/how-to-denormalise-a-dataset-using-talends-tunpivotrow/), [ETL Geeks Blog](http://etlgeeks.blogspot.com/2016/04/how-to-use-custom-componet-in-talend.html), [GitHub: TalendExchange/Components](https://github.com/TalendExchange/Components)

**Component family**: Transform (Custom Exchange)
**Available in**: Talend Open Studio, Talend Data Integration (requires manual installation from Talend Exchange)
**Required JARs**: None (Javajet component -- code is generated inline)

**Example transformation:**

Input (wide format):
```
| id | name  | jan_sales | feb_sales | mar_sales |
|----|-------|-----------|-----------|-----------|
| 1  | Alice | 100       | 200       | 150       |
| 2  | Bob   | 300       | null      | 250       |
```

Output (long format) with `row_keys = [id, name]`:
```
| pivot_key  | pivot_value | id | name  |
|------------|-------------|----|-------|
| jan_sales  | 100         | 1  | Alice |
| feb_sales  | 200         | 1  | Alice |
| mar_sales  | 150         | 1  | Alice |
| jan_sales  | 300         | 2  | Bob   |
| feb_sales  | null        | 2  | Bob   |
| mar_sales  | 250         | 2  | Bob   |
```

**Row multiplication formula**: For N input rows and M unpivoted columns, the output will have up to `N * M` rows.

### 3.1 Origin and Availability

The tUnpivotRow component is available from [Talend Exchange on GitHub](https://github.com/TalendExchange/Components). Multiple versions exist from different contributors (daztop v1.1 from 2009, wzawwin from 2014, leroux-g from 2012, sreenathtr from 2013). It is implemented as a Javajet component and must be manually installed into Talend Studio by downloading the zip file from Talend Exchange and copying it to the `custom_component` folder. It is **not** part of the standard Talend Open Studio or Talend Data Integration distributions.

**Installation steps** (from community documentation):
1. Download tUnpivotRow zip from exchange.talend.com or GitHub TalendExchange/Components
2. Unzip the folder
3. Copy the `tUnpivotRow` folder to the Talend Studio `custom_component` directory
4. In Talend Studio: Window -> Preferences -> Talend -> Component -> point to custom_component folder
5. Restart Talend Studio

### 3.2 Basic Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 1 | Schema | `SCHEMA` | Schema editor | -- | Output column definitions. Contains row key columns plus fixed `pivot_key` and `pivot_value` columns. The output schema is auto-generated based on ROW_KEYS selection. |
| 2 | Row Keys | `ROW_KEYS` | Table (COLUMN refs) | -- | **Mandatory**. List of columns from the input schema to preserve as identifier columns. All other columns are unpivoted into key-value pairs. Configured via the + button in the Row Keys area of the component settings. |
| 3 | Pivot Key Column | (fixed) | Read-only | `pivot_key` | Output column name for the original column names. This is a **hardcoded read-only** field in the standard Talend Exchange version. Some extended versions allow customization via `PIVOT_COLUMN` parameter. |
| 4 | Pivot Value Column | (fixed) | Read-only | `pivot_value` | Output column name for the cell values. This is a **hardcoded read-only** field in the standard version. Some extended versions allow customization via `VALUE_COLUMN` parameter. |

### 3.3 Advanced Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 5 | Die On Error | `DIE_ON_ERROR` | Boolean (CHECK) | `false` | Whether to stop the entire job on processing errors. When unchecked, errors are silently dropped. |
| 6 | Include Null Values | `INCLUDE_NULL_VALUES` | Boolean (CHECK) | `true` (varies by version) | Whether to emit output rows when the cell value is null. When false, null-valued cells do not produce output rows. |

**Note**: Because tUnpivotRow is a custom Exchange component, parameter names and availability vary between versions. The parameters above represent the most common implementation. Some versions also expose:

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 7 | Pivot Column Name | `PIVOT_COLUMN` | String | `pivot_key` | Custom name for the pivot key output column (extended versions only) |
| 8 | Value Column Name | `VALUE_COLUMN` | String | `pivot_value` | Custom name for the pivot value output column (extended versions only) |
| 9 | Group By Columns | `GROUP_BY_COLUMNS` | String (semicolon-separated) | -- | Alternative grouping specification (extended versions only) |
| 10 | tStatCatcher Statistics | `TSTATCATCHER_STATS` | Boolean (CHECK) | `false` | Capture processing metadata. Rarely used. |
| 11 | Label | `LABEL` | String | -- | Text label for the component in Talend Studio designer canvas. No runtime impact. |

### 3.4 Connection Types

| Connector | Direction | Type | Description |
|-----------|-----------|------|-------------|
| `FLOW` (Main) | Input | Row > Main | Input data flow containing the wide-format rows. All columns defined in the input schema must be present. |
| `FLOW` (Main) | Output | Row > Main | Output data flow containing the unpivoted/long-format rows. Schema is `[pivot_key, pivot_value, ...row_key_columns]`. Each input row produces M output rows (where M = number of unpivoted columns). |
| `REJECT` | Output | Row > Reject | **Not standard** -- most tUnpivotRow versions do NOT have a reject flow. Errors either stop the job (if `DIE_ON_ERROR=true`) or are silently dropped. |
| `SUBJOB_OK` | Output (Trigger) | Trigger | Fires when the entire subjob containing this component completes successfully. |
| `SUBJOB_ERROR` | Output (Trigger) | Trigger | Fires when the subjob containing this component fails with an error. |
| `COMPONENT_OK` | Output (Trigger) | Trigger | Fires when this specific component completes execution successfully. |
| `COMPONENT_ERROR` | Output (Trigger) | Trigger | Fires when this specific component fails with an error. |
| `RUN_IF` | Output (Trigger) | Trigger | Conditional trigger with a boolean expression. |

### 3.5 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
|------------------|------|----------|-------------|
| `{id}_NB_LINE` | Integer | After execution | Total number of input rows processed. |
| `{id}_NB_LINE_OK` | Integer | After execution | Total number of output rows produced. Should equal `input_rows * unpivoted_column_count` when all values are non-null and include_null_values=true. |
| `{id}_NB_LINE_REJECT` | Integer | After execution | Number of rows rejected. Typically 0 for this component since there is no reject flow. |
| `{id}_ERROR_MESSAGE` | String | On error | Last error message if any error occurred during execution. |

### 3.6 Behavioral Notes

1. **All output values are String type**: tUnpivotRow converts ALL pivot values to String type in its output, regardless of the original column type. This means numeric columns like `100` (Integer) become `"100"` (String) in `pivot_value`. Downstream components (tMap, tConvertType) must handle type conversion back to the desired types. This is a critical behavioral characteristic.

2. **Column order in output**: The output schema is strictly `[pivot_key, pivot_value, ...row_key_columns]`. No other columns appear in the output. The original "wide" columns (the ones being unpivoted) do NOT appear in the output schema.

3. **Null handling**: When a cell value is null, behavior varies by version:
   - Standard behavior: When `INCLUDE_NULL_VALUES=true`, null cells produce output rows with `pivot_value=null`. When false, null cells are skipped.
   - Known bug in some versions: Null values can cause a `NullPointerException` and the `pivot_value` retains the value from the previous field. This is documented in Talend community forums.
   - The v1 engine must handle both `NaN` and `None` correctly since pandas represents missing data differently from Java's null.

4. **Row multiplication**: For N input rows and M unpivoted columns, the output will have up to `N * M` rows. This can be a significant data amplification factor. A 100K-row input with 50 unpivoted columns produces 5M output rows.

5. **Fixed output column names**: In the original Talend Exchange component, `pivot_key` and `pivot_value` are hardcoded column names and are read-only in the component properties. Some extended versions allow customization via `PIVOT_COLUMN` and `VALUE_COLUMN` parameters.

6. **No reject flow**: The standard tUnpivotRow does NOT have a dedicated REJECT connector. This is different from most built-in Talend components which offer REJECT flows for error handling.

7. **Empty string vs null**: In Talend's Java runtime, empty string `""` and `null` are distinct values. Empty strings ARE included in output regardless of the INCLUDE_NULL_VALUES setting. Only Java `null` values are affected by this parameter.

8. **Input schema preservation**: The row key columns maintain their original types from the input schema. Only the `pivot_value` column is coerced to String.

9. **Order of unpivoted columns**: The `pivot_key` values appear in the same order as the columns appear in the input schema. For each input row, the unpivoted columns are iterated left-to-right, producing output rows in that same column order.

10. **NB_LINE semantics**: `NB_LINE` reflects the number of INPUT rows processed, not the number of output rows. `NB_LINE_OK` reflects the number of OUTPUT rows produced. This is important because the ratio `NB_LINE_OK / NB_LINE` equals the number of unpivoted columns (when no nulls are filtered).

---

## 4. Converter Audit

### 4.1 Parameter Extraction

The converter uses a **dedicated parser method** (`parse_unpivot_row()` in `component_parser.py` lines 2480-2506) with a dedicated `elif` branch in `converter.py` line 355. This is the correct approach per STANDARDS.md. However, the parser method itself has critical bugs in how it accesses XML parameters.

**Converter flow**:
1. `converter.py:_parse_component()` matches `component_type == 'tUnpivotRow'` (line 355)
2. Calls `self.component_parser.parse_unpivot_row(node, component)` (line 356)
3. `parse_unpivot_row()` attempts to extract parameters from the XML node
4. Returns component with populated `config` and `schema` dicts

| # | Talend XML Parameter | Extracted? | V1 Config Key | Converter Line | Notes |
|----|----------------------|------------|---------------|----------------|-------|
| 1 | `ROW_KEYS` | **Yes** | `row_keys` | 2487-2490 | Uses correct `node.findall('.//elementParameter[@name="ROW_KEYS"]/elementValue')` pattern. Filters by `elementRef='COLUMN'`. |
| 2 | `PIVOT_COLUMN` | **Yes (BROKEN)** | `pivot_column` | 2482 | **Uses `node.get()` instead of `node.find('.//elementParameter[...]')`.** Always returns default `'pivot_key'`. |
| 3 | `VALUE_COLUMN` | **Yes (BROKEN)** | `value_column` | 2483 | **Same incorrect `node.get()` pattern.** Always returns default `'pivot_value'`. |
| 4 | `GROUP_BY_COLUMNS` | **Yes (BROKEN)** | `group_by_columns` | 2484 | **Same incorrect `node.get()` pattern.** Always returns `['']` (empty string split). Engine does not read this key anyway. |
| 5 | `DIE_ON_ERROR` | **Yes (BROKEN)** | `die_on_error` | 2494 | **Same incorrect `node.get()` pattern.** Always returns `False` (the Python bool default). No string-to-bool conversion. |
| 6 | `INCLUDE_NULL_VALUES` | **No** | -- | -- | **Not extracted.** Engine has `include_empty_values` config but converter never populates it. |
| 7 | `SCHEMA` (input) | **No** | -- | -- | Input schema from Talend XML not preserved. |
| 8 | `SCHEMA` (output) | Partial | `schema.output` | 2497-2505 | Synthesized from config rather than extracted from XML. Uses `'str'` type instead of `'id_String'`. |
| 9 | `TSTATCATCHER_STATS` | **No** | -- | -- | Not extracted (low priority -- rarely used). |
| 10 | `LABEL` | **No** | -- | -- | Not extracted (cosmetic -- no runtime impact). |

**Summary**: 5 of 10 parameters have extraction code, but 4 of those 5 use the wrong XML access method and always return defaults. Effectively, only `ROW_KEYS` is correctly extracted (10% effective extraction rate).

### 4.2 Schema Extraction

The converter synthesizes an output schema rather than extracting it from the Talend XML:

```python
output_schema = [
    {'name': 'pivot_key', 'type': 'str', 'nullable': True, 'key': False},
    {'name': 'pivot_value', 'type': 'str', 'nullable': True, 'key': False}
]
for key in component['config']['row_keys']:
    output_schema.append({'name': key, 'type': 'str', 'nullable': True, 'key': False})
component['schema']['output'] = output_schema
```

| Schema Attribute | Extracted? | Notes |
|------------------|-----------|-------|
| `name` | Yes | Hardcoded from `pivot_key`, `pivot_value`, and row_keys |
| `type` | Yes -- **incorrectly** | Uses `'str'` instead of `'id_String'` per STANDARDS.md |
| `nullable` | Yes | Always `True` -- correct for unpivot output |
| `key` | Yes | Always `False` -- correct |
| `length` | **No** | Not extracted -- should be set for String columns |
| `precision` | **No** | Not extracted |
| `pattern` | **No** | Not extracted |
| `default` | **No** | Not extracted |

**Key observation**: The engine's `_process()` method never reads or applies the output schema. The engine derives its output structure entirely from the input DataFrame and config parameters. This means the converter's schema synthesis work is functionally unused at runtime -- it only serves as metadata for documentation or downstream tooling.

### 4.3 Expression Handling

The `parse_unpivot_row()` method does **not** handle context variables or Java expressions in any of its parameters. All parameters are extracted as literal values:

- `PIVOT_COLUMN`, `VALUE_COLUMN`: Treated as literal strings (no `context.` or `{{java}}` resolution)
- `ROW_KEYS`: Column references only -- no expression support needed (these are schema column names)
- `DIE_ON_ERROR`: Boolean flag -- no expression support needed

This is acceptable because tUnpivotRow parameters are typically static configuration values, not dynamic expressions. However, if a Talend job uses `context.pivotColumnName` as the PIVOT_COLUMN value, it will not be resolved.

### 4.4 Cross-Reference with tPivotToColumnsDelimited

The `tPivotToColumnsDelimited` converter parser (`parse_tpivot_to_columns_delimited`, line 1881) uses the **correct** XML traversal pattern:

```python
# Correct: finds elementParameter child nodes
pivot_column = node.find('.//elementParameter[@name="PIVOT_COLUMN"]').get('value', '')
```

The `parse_unpivot_row()` uses the **incorrect** pattern:

```python
# Incorrect: reads XML attributes on the node itself
component['config']['pivot_column'] = node.get('PIVOT_COLUMN', 'pivot_key')
```

This confirms that CONV-UPR-001 is a genuine bug -- the correct pattern is already used elsewhere in the same codebase by the same team.

### 4.5 Converter Issues

| ID | Priority | Issue |
|----|----------|-------|
| CONV-UPR-001 | **P0** | **Incorrect XML parameter access method**: `node.get('PIVOT_COLUMN', ...)` retrieves XML *attributes* on the node element, not Talend `elementParameter` child elements. Talend parameters are stored as `<elementParameter name="PIVOT_COLUMN" value="..."/>` children, requiring `node.find('.//elementParameter[@name="PIVOT_COLUMN"]').get('value')`. This means `pivot_column`, `value_column`, `group_by_columns`, and `die_on_error` will **always** return their default values, ignoring actual Talend job configuration. The correct pattern is used by `parse_tpivot_to_columns_delimited()` at line 1883. |
| CONV-UPR-002 | **P0** | **Hardcoded domain-specific fallback row_keys**: When `ROW_KEYS` extraction yields an empty list, the parser falls back to a hardcoded list of domain-specific column names: `['COBDATE', 'AGREEMENTID', 'MASTERMNEMONIC', 'CLIENT_OR_AFFILIATE', 'MNEMONIC', 'GMIACCOUNT', 'CURRENCY']` (line 2493). This is a project-specific hardcode from the original development context that will produce incorrect results for any other Talend job. The converter should raise an error or return an empty list with a warning. No other converter parser in the codebase has this pattern. |
| CONV-UPR-003 | **P1** | **Schema type format violation**: Output schema uses `'type': 'str'` instead of `'type': 'id_String'` as required by STANDARDS.md (section "Type Mapping"). The v1 engine's `validate_schema()` in `BaseComponent` has a mapping for `'str'` -> `'object'` but it is documented as the non-preferred format. All other converter parsers that synthesize schemas should use `id_String`. |
| CONV-UPR-004 | **P1** | **Config key mismatch with engine**: Converter outputs `pivot_column` and `value_column` config keys, but the engine's `UnpivotRow._process()` reads `pivot_key` and `pivot_value` (lines 125-126). These key names do not match, meaning the converter's values are silently ignored and the engine always uses its defaults (`'pivot_key'` and `'pivot_value'`). Even if CONV-UPR-001 were fixed, the custom column names would still be lost due to this key mismatch. |
| CONV-UPR-005 | **P1** | **`INCLUDE_NULL_VALUES` not extracted**: The Talend component parameter controlling whether null-valued cells produce output rows is not parsed at all. The engine has `include_empty_values` config key but the converter never populates it, so the engine always uses its default (`True`). Jobs that set `INCLUDE_NULL_VALUES=false` in Talend will behave differently in v1. |
| CONV-UPR-006 | **P1** | **`die_on_error` extraction broken in two ways**: (1) `node.get('DIE_ON_ERROR', False)` uses incorrect XML access (always returns the Python bool `False` default). (2) Even if the access were corrected, Talend XML stores boolean values as strings (`"true"` / `"false"`), but there is no `str.lower() == 'true'` conversion. The default is a Python `bool` rather than a string, causing type inconsistency. |
| CONV-UPR-007 | **P2** | **`group_by_columns` extracted but unused by engine**: The converter extracts `group_by_columns` from the XML (line 2484), but the engine's `UnpivotRow` class has no corresponding config parameter and completely ignores it. This is dead config data that wastes processing time and may confuse code readers. |
| CONV-UPR-008 | **P2** | **No docstring for Talend parameters**: The `parse_unpivot_row()` method has only a one-line docstring `"""Parse tUnpivotRow specific configuration"""` without listing the expected Talend parameters, their types, or defaults. Per STANDARDS.md ("Document Talend params" rule), parser methods should document all parameters. |
| CONV-UPR-009 | **P3** | **No input schema preservation**: The converter overwrites `component['schema']['output']` with a synthesized schema but does not extract or preserve the original input schema from the Talend XML `<metadata connector="FLOW">` node. This means schema metadata from the Talend job design is lost, making it impossible to detect schema drift between the original Talend design and the runtime input. |

---

## 5. Engine Feature Parity

### 5.1 Feature Implementation Status

| # | Talend Feature | Implemented? | Fidelity | Engine Location | Notes |
|----|----------------|-------------|----------|-----------------|-------|
| 1 | Unpivot columns to rows | **Yes** | High | `_process()` line 159 | Uses `pd.DataFrame.melt()` -- correct approach. Mathematically equivalent to Talend's column-to-row transformation. |
| 2 | Row keys (identifier columns) | **Yes** | High | `_process()` line 159 | Passed as `id_vars` to `pd.melt()`. Correctly preserves specified columns in output. |
| 3 | Pivot key column naming | **Yes** | High | `_process()` line 162 | Configurable via `pivot_key` config key. Default `'pivot_key'` matches Talend. |
| 4 | Pivot value column naming | **Yes** | High | `_process()` line 163 | Configurable via `pivot_value` config key. Default `'pivot_value'` matches Talend. |
| 5 | Include/exclude null values | **Yes** | Medium | `_process()` line 196-199 | `include_empty_values` config controls `dropna()` on pivot_value column. See Section 15 for edge cases. |
| 6 | All output as String type | **No** | **N/A** | -- | **Talend converts all pivot values to String; v1 preserves original types from the input DataFrame. This causes type mismatches with downstream components.** |
| 7 | NullPointerException on null | **N/A** | **N/A** | -- | Not applicable -- Python handles None natively. This is actually an improvement over Talend's buggy behavior in some versions. |
| 8 | Die on error | **No** | **N/A** | -- | Config key `die_on_error` is not read or honored by the engine. All errors are unconditionally re-raised (line 212-213), effectively acting as `die_on_error=True` always. |
| 9 | Reject flow | **No** | **N/A** | -- | No reject output supported. Matches Talend's standard tUnpivotRow (which also lacks reject). |
| 10 | Output column ordering | **Yes** | Medium | `_process()` line 179 | Reorders pivot columns first. But differs from Talend -- adds extra original columns back (BUG-UPR-001). |
| 11 | Empty input handling | **Yes** | High | `_process()` lines 115-118 | Returns empty DataFrame with zeroed stats. Correct pattern. |
| 12 | Row keys validation | **Yes** | High | `_process()` lines 134-144 | Validates non-empty row_keys and checks all keys exist in input DataFrame. |
| 13 | Row order preservation | **Yes** | High | `_process()` lines 155-170 | Uses `_original_order` tracking and sort to preserve input row grouping. |
| 14 | GlobalMap `NB_LINE` | **Yes** | High | via `_update_stats()` -> `_update_global_map()` | Set correctly via base class mechanism. |
| 15 | GlobalMap `NB_LINE_OK` | **Yes** | High | Same mechanism | Reflects actual output row count after all processing. |
| 16 | GlobalMap `NB_LINE_REJECT` | **Partial** | Low | Same mechanism | Always set to 0 -- never incremented even when rows are filtered by `include_empty_values=False`. |
| 17 | Streaming mode support | **Yes** | Medium | Inherited from `BaseComponent` | Chunked processing works but intra-chunk row ordering may differ from batch mode. |
| 18 | Context variable support | **Yes** | High | Via `BaseComponent.execute()` line 202 | `context_manager.resolve_dict()` called before `_process()` resolves `${context.var}` in config. |
| 19 | Java expression support | **Yes** | High | Via `BaseComponent.execute()` line 198 | `_resolve_java_expressions()` resolves `{{java}}` markers in config values. |
| 20 | `{id}_ERROR_MESSAGE` | **No** | **N/A** | -- | Not implemented. Error message not stored in globalMap on failure. |

### 5.2 Behavioral Differences from Talend

| ID | Priority | Description |
|----|----------|-------------|
| ENG-UPR-001 | **P0** | **Output schema pollution with None-filled original columns**: Lines 189-193 re-add ALL original input columns (including the very columns being unpivoted) back into the output with `None` values. For example, unpivoting `jan_sales`, `feb_sales`, `mar_sales` produces output with those columns still present but filled with `None`. Talend's output is strictly `[pivot_key, pivot_value, ...row_keys]` -- no extra columns. This corrupts the output schema and may break downstream components that expect the Talend-standard schema. |
| ENG-UPR-002 | **P1** | **No type coercion to String**: Talend's tUnpivotRow converts ALL `pivot_value` values to String type. The v1 engine preserves original types from the input DataFrame. This means numeric columns remain as `int64`/`float64` in the output, boolean columns remain as `bool`, etc. Downstream components that expect String-typed pivot values will receive incorrect types. The fix is a single line: `unpivoted_df[pivot_value_column] = unpivoted_df[pivot_value_column].astype(str)` after melt, with special handling for NaN values. |
| ENG-UPR-003 | **P1** | **`die_on_error` not honored**: The engine does not read or act on the `die_on_error` config parameter. All errors in the `_process()` method are re-raised unconditionally via the catch-all `except Exception as e: raise` block (lines 211-213). This effectively acts as `die_on_error=True` always. There is no graceful degradation path where errors produce an empty DataFrame or log a warning. |
| ENG-UPR-004 | **P1** | **`NB_LINE_REJECT` never reflects filtered rows**: When `include_empty_values=False`, rows with null values are dropped via `dropna()` (line 198). The count of filtered rows is computed as `rows_filtered` (line 199) and logged (line 200), but `_update_stats()` is called with `0` for the reject count (line 204). In Talend, filtered rows would be reflected in the statistics. |
| ENG-UPR-005 | **P2** | **Output column order includes extra columns not present in Talend output**: The column reordering logic (line 179) uses `[col for col in unpivoted_df.columns if col not in [pivot_key_column, pivot_value_column]]`, which includes row_key columns (correct) but also any other columns that happen to exist. Combined with BUG-UPR-001 (re-added original columns), this produces a schema wider than Talend's output. |
| ENG-UPR-006 | **P2** | **Redundant post-melt filter is always a no-op**: Line 175 filters `unpivoted_df[unpivoted_df[pivot_key_column].isin(columns_to_unpivot)]`. After `pd.melt(value_vars=columns_to_unpivot)`, the `var_name` column will ONLY ever contain values from `columns_to_unpivot`. This filter is always a no-op. It creates an unnecessary copy of the entire melted DataFrame and performs an O(N*M) membership check. |
| ENG-UPR-007 | **P2** | **`{id}_ERROR_MESSAGE` not set in globalMap**: When errors occur, the error message is not stored in globalMap for downstream reference. The `BaseComponent.execute()` catches exceptions (line 227-234) and sets `self.error_message = str(e)` but does not call `self.global_map.put(f"{self.id}_ERROR_MESSAGE", str(e))`. |
| ENG-UPR-008 | **P3** | **Streaming mode chunk ordering may differ from batch mode**: When processing in streaming mode via `BaseComponent._execute_streaming()`, each chunk is independently melted. The `_original_order` tracking within `_process()` only preserves order within a single chunk, not across chunks. The `_original_order` counter resets to `0` for each chunk, so intra-chunk sort produces `[0, 0, 0, 1, 1, 1, ...]` for each chunk independently, but the cross-chunk concatenation preserves inter-chunk order. |

### 5.3 GlobalMap Variable Coverage

| Variable | Talend Sets? | V1 Sets? | How V1 Sets It | Notes |
|----------|-------------|----------|-----------------|-------|
| `{id}_NB_LINE` | Yes | **Yes** | `_update_stats()` -> `_update_global_map()` -> `global_map.put_component_stat()` | Set to INPUT row count. Correct semantics. |
| `{id}_NB_LINE_OK` | Yes | **Yes** | Same mechanism | Set to OUTPUT row count. Correct semantics. |
| `{id}_NB_LINE_REJECT` | Yes | **Partial** | Same mechanism | Always 0, even when `include_empty_values=False` filters rows. Should reflect filtered count. |
| `{id}_ERROR_MESSAGE` | Yes | **No** | -- | Not implemented. Error stored in `self.error_message` but not pushed to globalMap. |
| `{id}_EXECUTION_TIME` | N/A (v1 only) | **Yes** | Base class | V1-specific, not in Talend. |

### 5.4 `_update_global_map()` Crash Analysis (Cross-Cutting)

The `BaseComponent._update_global_map()` method at line 304 of `base_component.py` contains a **cross-cutting bug** that affects ALL components, including `UnpivotRow`:

```python
def _update_global_map(self) -> None:
    """Update global map with component statistics"""
    if self.global_map:
        for stat_name, stat_value in self.stats.items():
            self.global_map.put_component_stat(self.id, stat_name, stat_value)
        # Log the statistics for debugging
        logger.info(f"Component {self.id}: Updated stats - NB_LINE:{self.stats['NB_LINE']} "
                     f"NB_LINE_OK:{self.stats['NB_LINE_OK']} NB_LINE_REJECT:{self.stats['NB_LINE_REJECT']} "
                     f"{stat_name}: {value}")
```

**Bug**: The log statement on line 304 references `{value}` which is undefined. The loop variable is named `stat_value`, not `value`. This causes a `NameError` at runtime whenever `global_map` is not `None`.

**Additionally**, `GlobalMap.get()` at line 28 of `global_map.py` references an undefined `default` parameter:

```python
def get(self, key: str) -> Optional[Any]:
    """Retrieve a value from the global map"""
    return self._map.get(key, default)
```

The method signature declares only `key: str` but the body calls `self._map.get(key, default)` where `default` is not defined. This causes a `NameError` on every `.get()` call. Furthermore, `get_component_stat()` on line 58 calls `self.get(key, default)` with two arguments, but `get()` only accepts one.

**Impact**: When `global_map` is provided to `UnpivotRow` (which is the normal production case), both `_update_global_map()` (called by `execute()` line 218 on success and line 231 on error) and any downstream `global_map.get()` calls will crash with `NameError`. This means:
1. Successful component execution will crash AFTER processing is complete but BEFORE the result is returned
2. Error handling will crash when trying to update stats, potentially masking the original error
3. Any downstream code that uses `global_map.get()` will crash

These are **cross-cutting P0 bugs** that affect every component in the v1 engine.

---

## 6. Code Quality

### 6.1 Bugs

| ID | Priority | Location | Description |
|----|----------|----------|-------------|
| BUG-UPR-001 | **P0** | `unpivot_row.py` lines 189-193 | **Output schema pollution**: After `pd.melt()`, the code re-adds ALL original input columns with `None` values. This means the unpivoted output contains the original wide columns (e.g., `jan_sales`, `feb_sales`, `mar_sales`) alongside `pivot_key`/`pivot_value` -- but filled with `None`. Talend does NOT include these columns in output. This corrupts the output schema and will break downstream components expecting only `[pivot_key, pivot_value, ...row_keys]`. The loop `for col in input_data.columns: if col not in unpivoted_df.columns: unpivoted_df[col] = None` is the direct cause. |
| BUG-UPR-002 | **P1** | `unpivot_row.py` lines 183-187 | **Dead code -- unreachable column addition**: Lines 183-187 iterate over `column_order` and add missing columns with `None`. However, `column_order` is built from `unpivoted_df.columns` on line 179, so by definition every column in `column_order` already exists in `unpivoted_df`. This loop body (`unpivoted_df[col] = None`) can never execute. It is dead code that adds complexity without function. |
| BUG-UPR-003 | **P1** | `unpivot_row.py` lines 196-204 | **Filtered row count not reflected in statistics**: When `include_empty_values=False`, the count of dropped null rows is computed as `rows_filtered` (line 199) and logged (line 200) but never passed to `_update_stats()`. The call on line 204 is `self._update_stats(rows_in, rows_out, 0)` -- hardcoding reject count to 0. Should be `self._update_stats(rows_in, rows_out, rows_filtered)` when `include_empty_values=False`. |
| BUG-UPR-004 | **P1** | `unpivot_row.py` line 134 & lines 61-98 | **Dual validation with `_validate_config()` never auto-called**: `_process()` re-validates `row_keys` on line 134 (`if not row_keys: raise ValueError`) after `_validate_config()` already checks for this. However, `_validate_config()` is never called automatically by `execute()` or `_process()`. The `validate_config()` public wrapper (lines 215-234) also exists but is also never auto-called. If external code does not explicitly call `validate_config()`, the more thorough `_validate_config()` checks (list type, non-empty, string entries, optional param types) are all bypassed. Only the minimal check in `_process()` runs. |
| BUG-UPR-005 | **P0** (Cross-Cutting) | `base_component.py` line 304 | **`_update_global_map()` references undefined variable `value`**: The log statement uses `{stat_name}: {value}` but the loop variable is `stat_value`. Causes `NameError` at runtime whenever `global_map` is not None. Affects ALL components. See Section 5.4 for full analysis. |
| BUG-UPR-006 | **P0** (Cross-Cutting) | `global_map.py` line 28 | **`GlobalMap.get()` references undefined `default` parameter**: Method signature is `def get(self, key: str) -> Optional[Any]` but body calls `self._map.get(key, default)` where `default` is not defined. Additionally, `get_component_stat()` (line 58) calls `self.get(key, default)` with two arguments but `get()` only accepts one. Both cause `NameError`. Affects ALL code using `global_map.get()`. |
| BUG-UPR-007 | **P1** | `unpivot_row.py` line 157 | **`_original_order` column name collision**: If the input DataFrame already contains a column named `_original_order`, line 157 silently overwrites it, corrupting the melt output. The overwritten column's original data is lost, and the melt operation uses the synthetic integer index instead of the original column values. No collision check is performed before assignment. Should use a guaranteed-unique sentinel name (e.g., `__unpivot_original_order_<uuid>`) or validate that the column does not already exist and raise `ConfigurationError` if it does. |
| BUG-UPR-008 | **P1** | `unpivot_row.py` lines 125-126, 162-163 | **`pivot_key_column`/`pivot_value_column` name collision with existing columns**: If the configured `pivot_key` column name (default `'pivot_key'`) matches an existing row_key column name, `pd.melt()` fails or produces duplicate columns. For example, if a row_key is named `'pivot_key'`, the `var_name='pivot_key'` parameter in `melt()` collides with the `id_vars` column of the same name, producing a DataFrame with duplicate column names. No collision check is performed between the pivot/value column names and the row_key names. |
| BUG-UPR-009 | **P2** | `unpivot_row.py` line 167 | **Sort by `pivot_key_column` changes column iteration order from schema-order to alphabetical**: The `sort_values(['_original_order', pivot_key_column])` on line 167 sorts the secondary key (`pivot_key_column`) alphabetically. This means unpivoted columns like `[jan_sales, feb_sales, mar_sales]` produce output rows in order `feb_sales, jan_sales, mar_sales` instead of Talend's schema-order `jan_sales, feb_sales, mar_sales`. Talend iterates columns left-to-right as they appear in the input schema; the alphabetical sort violates this ordering contract. Downstream consumers relying on column iteration order (e.g., positional indexing) will see incorrect data alignment. |

### 6.2 Naming Consistency

| ID | Priority | Issue |
|----|----------|-------|
| NAME-UPR-001 | **P2** | **Config key divergence between converter and engine**: Converter outputs `pivot_column` and `value_column`; engine reads `pivot_key` and `pivot_value`. The converter's values are silently ignored -- the engine always uses defaults. The keys should be unified. |
| NAME-UPR-002 | **P2** | **Inconsistent Talend name in error messages**: Line 135 says `"Row keys must be specified for TUnpivotRow."` using `TUnpivotRow` (PascalCase with T prefix). The class is `UnpivotRow` and the Talend name is `tUnpivotRow`. Should use `self.component_type` or consistent naming. |
| NAME-UPR-003 | **P2** | **Module docstring says `TUnpivotRow`**: Line 2 of the module docstring says `"TUnpivotRow - Convert columns..."` using an inconsistent capitalization. Should be `UnpivotRow` (class name) or `tUnpivotRow` (Talend name). |
| NAME-UPR-004 | **P2** | **Error log says `TUnpivotRow`**: Line 212: `logger.error(f"[{self.id}] Error in TUnpivotRow: {e}")` uses hardcoded `TUnpivotRow` instead of `self.component_type` or consistent naming. |
| NAME-UPR-005 | **P3** | **Class docstring parameter names ambiguous**: Docstring says `pivot_key (str)` and `pivot_value (str)` for config parameters, but these are also the names of OUTPUT COLUMNS. A reader cannot tell if `pivot_key` is the config key name or the default column name value. Should clarify: "pivot_key (str): Name for the output column containing original column names. Default: 'pivot_key'". |

### 6.3 Standards Compliance

| ID | Priority | Standard | Violation |
|----|----------|----------|-----------|
| STD-UPR-001 | **P2** | "`_validate_config()` should be called automatically" (STANDARDS.md) | `BaseComponent.execute()` does not call `_validate_config()` or `validate_config()`. Validation only runs if explicitly called by external code. Per STANDARDS.md, validation should be automatic during the execution lifecycle. |
| STD-UPR-002 | **P2** | "Single validation method pattern" (STANDARDS.md) | The class has both `_validate_config()` (returns `List[str]`) and `validate_config()` (returns `bool`). STANDARDS.md shows a single `_validate_config()` pattern. The public `validate_config()` method is described as "backward compatible" (line 225) but creates confusion and code duplication. |
| STD-UPR-003 | **P2** | "Use project exception types" (STANDARDS.md) | Errors are raised as `ValueError` (lines 137, 144) instead of the project-standard `ConfigurationError` (for config issues) or `ComponentExecutionError` (for runtime failures) defined in `src/v1/engine/exceptions.py`. |
| STD-UPR-004 | **P2** | "Wrap exceptions in ComponentExecutionError" (STANDARDS.md Pattern 1) | Line 211-213 catches `Exception` and re-raises it without wrapping in `ComponentExecutionError`. Should be: `raise ComponentExecutionError(self.id, str(e), e) from e`. |
| STD-UPR-005 | **P3** | "Type annotations on class constants" (STANDARDS.md convention) | `DEFAULT_PIVOT_KEY`, `DEFAULT_PIVOT_VALUE`, `DEFAULT_INCLUDE_EMPTY_VALUES` lack type annotations. Should be: `DEFAULT_PIVOT_KEY: str = 'pivot_key'`. |

### 6.4 Debug Artifacts

| ID | Priority | Issue |
|----|----------|-------|
| DBG-UPR-001 | **P2** | **Excessive eager f-string DEBUG logging in hot path**: Lines 129-131, 148-149, 153, 167, 172, 175-176, 181, 187, 193 all emit `logger.debug()` calls within the processing path. The f-strings are evaluated eagerly, meaning the string formatting runs even when DEBUG logging is disabled. For example, `f"[{self.id}] Columns to unpivot: {columns_to_unpivot}"` formats a potentially large list into a string even when the log level is INFO or above. Should use lazy `%s`-style formatting: `logger.debug("[%s] Columns to unpivot: %s", self.id, columns_to_unpivot)`. For large DataFrames with many columns, this has measurable CPU overhead. |
| DBG-UPR-002 | **P3** | **INFO-level log in base class `_update_global_map()`**: The `BaseComponent._update_global_map()` method (line 304) logs at INFO level. Statistics updates are an internal detail that should be logged at DEBUG level, not INFO. Every component execution produces this log line, which clutters production logs. |

### 6.5 Security

| ID | Priority | Issue |
|----|----------|-------|
| SEC-UPR-001 | **P3** | **No input sanitization on column names**: Column names from `row_keys` config are used directly in DataFrame operations (`input_data.columns`, `pd.melt()` `id_vars`, `isin()`) without validation for special characters, extremely long names (>255 chars), or injection patterns. Low risk since input is from trusted converter output and pandas handles arbitrary column names safely, but noted for defense-in-depth. |

### 6.6 Logging Quality

| Aspect | Assessment |
|--------|------------|
| Logger setup | Module-level `logger = logging.getLogger(__name__)` -- correct |
| Component ID prefix | All log messages use `[{self.id}]` prefix -- correct |
| Level usage | INFO for start/complete/filter milestones, DEBUG for details, WARNING for empty input, ERROR for failures -- correct |
| Start/complete logging | `_process()` logs start (line 121) and complete (line 206-207) with row counts -- correct |
| Sensitive data | No sensitive data logged -- correct |
| No print statements | No `print()` calls -- correct |
| Eager f-string issue | Uses `f"..."` format in debug logs instead of lazy `%s` format -- see DBG-UPR-001 |

### 6.7 Error Handling Quality

| Aspect | Assessment |
|--------|------------|
| Custom exceptions | Uses `ValueError` instead of project-standard `ConfigurationError`/`ComponentExecutionError` -- incorrect (STD-UPR-003) |
| Exception chaining | Does NOT use `raise ... from e` pattern -- re-raises bare `e` on line 213 |
| `die_on_error` handling | Not implemented -- all errors unconditionally re-raised (ENG-UPR-003) |
| No bare `except` | All except clauses specify `Exception` -- correct |
| Error messages | Include component ID and descriptive details -- correct |
| Graceful degradation | Only for empty input (returns empty DataFrame). No graceful path for processing errors. |

### 6.8 Type Hints

| Aspect | Assessment |
|--------|------------|
| Method signatures | All methods have return type hints -- correct |
| Parameter types | `_process()` has `Optional[pd.DataFrame]` and returns `Dict[str, Any]` -- correct |
| `_validate_config()` | Returns `List[str]` -- correct |
| `validate_config()` | Returns `bool` -- correct |
| Class constants | Missing type annotations (STD-UPR-005) |

---

## 7. Performance & Memory

### 7.1 Memory Analysis

The `_process()` method creates several intermediate copies of the data:

1. **Line 156**: `input_data_with_index = input_data.copy()` -- full copy of input DataFrame
2. **Line 159**: `pd.melt()` -- creates a new DataFrame with `N * M` rows (where N = input rows, M = unpivoted columns)
3. **Line 167**: `sort_values()` with `ignore_index=True` -- creates another copy
4. **Line 170**: `drop('_original_order')` -- creates another copy
5. **Line 175**: Boolean indexing filter -- creates another copy (no-op but still copies)
6. **Line 179**: Column reorder via `unpivoted_df[column_order]` -- creates another copy

**Peak memory formula**: Approximately `3-4x` the size of the melted output DataFrame, which itself is `M` times larger than the input (where M is the number of unpivoted columns).

**Concrete example**: For a 1M-row input with 50 unpivoted columns and 5 row key columns:
- Input DataFrame: ~1M rows * 55 columns * 8 bytes = ~440 MB
- Copy for _original_order: ~440 MB
- Melted DataFrame: 50M rows * 8 columns * 8 bytes = ~3.2 GB
- Sort produces another ~3.2 GB intermediate
- Peak memory: ~7+ GB

This easily exceeds available memory for large inputs with many unpivoted columns.

### 7.2 Performance Issues

| ID | Priority | Issue |
|----|----------|-------|
| PERF-UPR-001 | **P1** | **Unnecessary full copy of input data**: Line 156 creates a full copy (`input_data.copy()`) solely to add a `_original_order` column. This doubles memory usage of the input. Instead, the `_original_order` column can be added directly to the `melt()` output using the input's index, or `melt()` can be called with `ignore_index=False` to preserve ordering information. A more efficient approach: `input_data['_original_order'] = range(len(input_data))` (modify in place), then clean up after melt: `input_data.drop('_original_order', axis=1, inplace=True)`. |
| PERF-UPR-002 | **P2** | **Redundant no-op filter after melt**: Line 175 applies `unpivoted_df[unpivoted_df[pivot_key_column].isin(columns_to_unpivot)]` which is always a no-op (see ENG-UPR-006 analysis above). This creates an unnecessary copy of the entire melted DataFrame and performs an O(N*M) membership check against a set of M column names. For a 50M-row result, this wastes significant CPU and ~3.2 GB of memory for the copy. |
| PERF-UPR-003 | **P2** | **Multiple chained DataFrame copies**: Lines 167-181 create 4-5 intermediate DataFrame copies through chained operations (`sort_values`, `drop`, boolean index, column reorder). These should be consolidated using `inplace=True` where possible, or restructured to minimize copies. For example, `sort_values(..., inplace=True)` and `drop(..., inplace=True)` would modify in place, saving ~6 GB of intermediate memory for the example above. |
| PERF-UPR-004 | **P2** | **O(N*M*log(N*M)) sort operation**: Line 167 sorts the melted DataFrame by `['_original_order', pivot_key_column]`. For a 50M-row output, this is an expensive O(50M * log(50M)) ~= O(50M * 25) = O(1.25B) comparison operation. Since `pd.melt()` already preserves row order (it iterates `value_vars` in order for each id combination), the sort is only needed to group by original row. Consider whether the natural melt order suffices or if a cheaper groupby approach would work. |
| PERF-UPR-005 | **P3** | **Eager f-string evaluation in debug logs**: Multiple `logger.debug(f"...")` calls eagerly evaluate f-strings even when DEBUG logging is disabled. For calls that format large lists (e.g., `f"Columns to unpivot: {columns_to_unpivot}"` when there are 100+ columns), this wastes CPU. Use `%s`-style lazy formatting: `logger.debug("Columns to unpivot: %s", columns_to_unpivot)`. |

### 7.3 Memory Management Assessment

| Aspect | Assessment |
|--------|------------|
| Streaming mode | Inherited from `BaseComponent._execute_streaming()`. Chunks of `chunk_size` rows (default 100K) processed independently. Correct design for reducing peak memory. |
| Memory threshold | `MEMORY_THRESHOLD_MB = 3072` (3GB) inherited from `BaseComponent`. Reasonable default. |
| Data amplification | Unpivot amplifies data by factor M (unpivoted column count). A 3GB input with 10 columns to unpivot becomes 30GB output. HYBRID mode should account for this amplification factor, but currently only checks input size. |
| Copy management | Excessive intermediate copies (see PERF-UPR-003). 4-5 copies of the melted DataFrame created during processing. |

### 7.4 Streaming Mode Analysis

For `UnpivotRow`, streaming mode means each chunk is independently melted:

```
Input DataFrame (300K rows, 10 unpivot columns):
  Chunk 1: rows 0-99999       -> melt -> 1,000,000 output rows
  Chunk 2: rows 100000-199999 -> melt -> 1,000,000 output rows
  Chunk 3: rows 200000-299999 -> melt -> 1,000,000 output rows
  Combined: pd.concat([chunk1, chunk2, chunk3]) -> 3,000,000 rows
```

| Issue | Description | Severity |
|-------|-------------|----------|
| **Row ordering** | Within each chunk, `_original_order` preserves order. But `_original_order` resets to 0 for each chunk, so cross-chunk ordering depends on `pd.concat` order (which is correct). However, within each chunk, rows are sorted by `[_original_order, pivot_key_column]` independently. The final output has correct inter-chunk order but potentially different intra-chunk sort behavior than a single batch operation. | Medium |
| **Statistics accumulation** | `BaseComponent._execute_streaming()` calls `_process()` per chunk. Each `_process()` call invokes `_update_stats()` which ADDS to cumulative stats (line 308: `self.stats['NB_LINE'] += rows_read`). Stats accumulate correctly across chunks. | OK |
| **Memory amplification** | Each chunk of 100K rows with 10 unpivot columns produces 1M rows. The intermediate memory within `_process()` peaks at ~4x this (copies, sort, filter). So a 100K-row chunk may consume memory equivalent to ~4M rows of output data. For wide DataFrames, this can still be significant. | Medium |
| **Empty chunk handling** | If a chunk is empty (e.g., all rows filtered by upstream), `_process()` returns `{'main': pd.DataFrame()}`. The streaming logic checks `chunk_result.get('main') is not None` but an empty DataFrame is not None -- it will be appended to results. `pd.concat` with empty DataFrames is harmless but wasteful. | Low |

**Streaming Correctness Verdict**: Streaming mode produces **functionally correct output** for `UnpivotRow`, but with a slightly different sort order than batch mode when the input exceeds one chunk. For most use cases, this difference is irrelevant.

---

## 8. Testing

### 8.1 Current Coverage

| Test Type | Exists? | File | Notes |
|-----------|---------|------|-------|
| V1 engine unit tests | **No** | -- | Zero test files found for `UnpivotRow` v1 engine component |
| V1 engine integration tests | **No** | -- | No v1 engine integration tests found |
| Converter parser tests | **No** | -- | No tests for `parse_unpivot_row()` |

**Key finding**: The v1 engine has ZERO tests for this component. All 235 lines of v1 engine code and 27 lines of converter parser code are completely unverified by automated tests. The critical bugs in XML parameter access (CONV-UPR-001) and output schema pollution (BUG-UPR-001) would have been caught by even basic tests.

### 8.2 Testing Issues

| ID | Priority | Issue |
|----|----------|-------|
| TEST-UPR-001 | **P0** | **Zero unit tests**: No test file exists for the `UnpivotRow` component. There is no coverage for any code path -- basic functionality, edge cases, configuration validation, error handling, or statistics tracking. All 235 lines of engine code are unverified. |
| TEST-UPR-002 | **P1** | **No converter parser tests**: No tests exist for `parse_unpivot_row()` in the converter. The critical bugs in XML parameter access (CONV-UPR-001) and hardcoded fallback (CONV-UPR-002) would have been caught by even basic converter tests. |

### 8.3 Recommended Test Cases

#### P0 -- Must Have Before Production

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 1 | `test_basic_unpivot` | P0 | Unpivot a simple 3-column DataFrame with 2 row keys. Verify output has `N * M` rows with correct pivot_key and pivot_value values. Verify output schema is exactly `[pivot_key, pivot_value, ...row_keys]`. |
| 2 | `test_single_row_key` | P0 | Single row key column. Verify all other columns are unpivoted. |
| 3 | `test_multiple_row_keys` | P0 | Multiple row key columns. Verify all are preserved in output with correct values. |
| 4 | `test_empty_input_none` | P0 | Pass `None` as input. Verify empty DataFrame returned and stats are `(0, 0, 0)`. |
| 5 | `test_empty_input_dataframe` | P0 | Pass empty DataFrame as input. Verify empty DataFrame returned and stats are `(0, 0, 0)`. |
| 6 | `test_missing_row_keys_config` | P0 | Config without `row_keys`. Verify `ValueError` (or `ConfigurationError`) is raised with descriptive message. |
| 7 | `test_missing_row_key_column_in_data` | P0 | `row_keys` references a column not in the input DataFrame. Verify error with descriptive message listing missing columns. |
| 8 | `test_include_empty_values_true_with_nulls` | P0 | Input with null cells and `include_empty_values=True`. Verify null rows ARE included in output. |
| 9 | `test_include_empty_values_false_with_nulls` | P0 | Input with null cells and `include_empty_values=False`. Verify null rows are EXCLUDED from output. |

#### P1 -- Important

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 10 | `test_custom_pivot_key_name` | P1 | Set `pivot_key='attribute'`. Verify output column is named `attribute`. |
| 11 | `test_custom_pivot_value_name` | P1 | Set `pivot_value='val'`. Verify output column is named `val`. |
| 12 | `test_output_column_order_strict` | P1 | Verify output columns are EXACTLY `[pivot_key, pivot_value, ...row_keys]` with no extra columns. (Currently fails due to BUG-UPR-001.) |
| 13 | `test_row_order_preservation` | P1 | Multi-row input. Verify unpivoted rows maintain original row grouping order: all unpivoted values for row 1 come before all values for row 2. |
| 14 | `test_statistics_tracking` | P1 | Verify `NB_LINE` = input row count, `NB_LINE_OK` = output row count. |
| 15 | `test_statistics_with_null_filter` | P1 | Verify `NB_LINE_REJECT` reflects count of filtered null rows when `include_empty_values=False`. (Currently fails due to BUG-UPR-003.) |
| 16 | `test_validate_config_valid` | P1 | Valid config. Verify `validate_config()` returns `True`. |
| 17 | `test_string_type_coercion` | P1 | Numeric, boolean, and date columns. Verify all pivot_value entries are String type. (Currently fails due to ENG-UPR-002.) |
| 18 | `test_globalmap_integration` | P1 | Verify `{id}_NB_LINE` etc. are set in globalMap after execution. (Currently fails due to BUG-UPR-005.) |

#### P2 -- Hardening

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 19 | `test_all_columns_as_row_keys` | P2 | Edge case: all input columns are row keys, no columns to unpivot. Verify behavior (should produce empty or identity output). |
| 20 | `test_single_unpivot_column` | P2 | Only one column to unpivot. Output row count should equal input row count. |
| 21 | `test_large_dataframe` | P2 | 100K+ rows with 20+ columns to unpivot. Verify correctness and reasonable performance (<30 seconds). |
| 22 | `test_mixed_types_in_unpivot_columns` | P2 | Columns with int, float, string, and None values. Verify all are handled without error. |
| 23 | `test_duplicate_row_key_values` | P2 | Multiple input rows with same row key values. Verify each produces correct unpivoted rows. |
| 24 | `test_validate_config_missing_row_keys` | P2 | Missing `row_keys`. Verify `validate_config()` returns `False`. |
| 25 | `test_validate_config_non_list_row_keys` | P2 | `row_keys` is a string instead of list. Verify returns `False`. |
| 26 | `test_validate_config_non_string_entries` | P2 | `row_keys` contains non-string entries (int, None). Verify returns `False`. |
| 27 | `test_empty_string_values_not_filtered` | P2 | Input with empty string `""` cells and `include_empty_values=False`. Verify empty strings are NOT filtered (only NaN/None are). |
| 28 | `test_nan_vs_none_handling` | P2 | Input with both `float('nan')` and `None` values. Verify both are handled consistently by `dropna()`. |

#### Converter Tests

| # | Test | Priority | Description |
|----|------|----------|-------------|
| 29 | `test_parse_unpivot_row_basic` | P0 | Parse well-formed tUnpivotRow XML node. Verify `row_keys`, `pivot_key`, `pivot_value` extracted correctly. |
| 30 | `test_parse_unpivot_row_empty_keys` | P0 | Parse node with no ROW_KEYS elements. Verify error/warning (currently falls back to hardcoded domain list). |
| 31 | `test_parse_unpivot_row_schema` | P1 | Verify output schema contains `pivot_key`, `pivot_value`, and all row key columns with `id_String` type. |
| 32 | `test_parse_unpivot_row_xml_access` | P0 | Verify parameters are extracted from `elementParameter` children, not node attributes. |

#### Integration Tests

| # | Test | Priority | Description |
|----|------|----------|-------------|
| 33 | `test_unpivot_in_pipeline` | P1 | Full pipeline: FileInputDelimited -> UnpivotRow -> FileOutputDelimited. Verify end-to-end data flow. |
| 34 | `test_unpivot_with_downstream_map` | P2 | UnpivotRow -> Map. Verify Map receives correctly structured narrow data. |

---

## 9. Issues Summary

### P0 -- Critical

| ID | Category | Summary |
|----|----------|---------|
| CONV-UPR-001 | Converter | **Incorrect XML parameter access**: `node.get()` reads XML attributes instead of `elementParameter` children; `pivot_column`, `value_column`, `group_by_columns`, and `die_on_error` always return defaults. Correct pattern used by `parse_tpivot_to_columns_delimited()` at line 1883. |
| CONV-UPR-002 | Converter | **Hardcoded domain-specific fallback row_keys**: Falls back to `['COBDATE', 'AGREEMENTID', 'MASTERMNEMONIC', 'CLIENT_OR_AFFILIATE', 'MNEMONIC', 'GMIACCOUNT', 'CURRENCY']` when ROW_KEYS extraction fails. Breaks any non-original-project Talend job. |
| BUG-UPR-001 | Engine Bug | **Output schema pollution**: Original wide columns re-added with None values (lines 189-193), producing output schema that does not match Talend's `[pivot_key, pivot_value, ...row_keys]` output. Corrupts downstream processing. |
| BUG-UPR-005 | Bug (Cross-Cutting) | **`_update_global_map()` in `base_component.py:304` references undefined variable `value`** (should be `stat_value`). Will crash ALL components when `global_map` is set. |
| BUG-UPR-006 | Bug (Cross-Cutting) | **`GlobalMap.get()` in `global_map.py:28` references undefined parameter `default`**. Will crash on any `global_map.get()` call. `get_component_stat()` also passes two args to single-arg `get()`. |
| TEST-UPR-001 | Testing | **Zero unit tests**: No test file exists for any code path in UnpivotRow or its converter parser. All 262 lines are completely unverified. |

### P1 -- Major

| ID | Category | Summary |
|----|----------|---------|
| CONV-UPR-003 | Converter | Schema type format uses `'str'` instead of `'id_String'` per STANDARDS.md. |
| CONV-UPR-004 | Converter | Config key mismatch: converter outputs `pivot_column`/`value_column` but engine reads `pivot_key`/`pivot_value`. Custom names silently lost. |
| CONV-UPR-005 | Converter | `INCLUDE_NULL_VALUES` parameter not extracted from Talend XML. |
| CONV-UPR-006 | Converter | `die_on_error` extraction broken due to incorrect XML access method AND missing string-to-bool conversion. |
| ENG-UPR-002 | Engine | No type coercion to String -- Talend converts all pivot values to String; v1 preserves original types. |
| ENG-UPR-003 | Engine | `die_on_error` config not honored; errors always re-raised unconditionally. |
| ENG-UPR-004 | Engine | `NB_LINE_REJECT` never set for rows filtered by `include_empty_values=False`. |
| BUG-UPR-002 | Engine Bug | Dead code: unreachable column addition loop (lines 183-187). |
| BUG-UPR-003 | Engine Bug | Filtered row count computed (`rows_filtered`) but not reflected in `NB_LINE_REJECT` statistics. Hardcoded to 0. |
| BUG-UPR-004 | Engine Bug | Dual validation paths: `_validate_config()` is never called automatically by `execute()`. Comprehensive validation bypassed. |
| BUG-UPR-007 | Engine Bug | `_original_order` column name collision. If input already has `_original_order` column, line 157 silently overwrites it, corrupting melt output. |
| BUG-UPR-008 | Engine Bug | `pivot_key_column`/`pivot_value_column` name collision with existing columns. If default `pivot_key` matches a row_key name, melt fails or produces duplicate columns. |
| PERF-UPR-001 | Performance | Unnecessary full copy of input DataFrame (`input_data.copy()`) for `_original_order` tracking. Doubles input memory. |
| TEST-UPR-002 | Testing | No converter parser tests for `parse_unpivot_row()`. Critical XML access bugs undetected. |

### P2 -- Moderate

| ID | Category | Summary |
|----|----------|---------|
| CONV-UPR-007 | Converter | `group_by_columns` extracted but unused by engine -- dead config data. |
| CONV-UPR-008 | Converter | Missing standard docstring for Talend parameters in parser method. |
| ENG-UPR-005 | Engine | Output column order includes extra columns not present in Talend output. |
| ENG-UPR-006 | Engine | Redundant no-op filter after `pd.melt()` -- always passes all rows. |
| ENG-UPR-007 | Engine | `{id}_ERROR_MESSAGE` not set in globalMap on error. |
| BUG-UPR-009 | Engine Bug | Sort by `pivot_key_column` (line 167) changes column iteration order from schema-order to alphabetical. `[jan_sales, feb_sales, mar_sales]` produces `feb, jan, mar` instead of Talend's `jan, feb, mar`. |
| NAME-UPR-001 | Naming | Config key divergence between converter (`pivot_column`) and engine (`pivot_key`). |
| NAME-UPR-002 | Naming | Inconsistent `TUnpivotRow` in error messages (should be `tUnpivotRow` or class name). |
| NAME-UPR-003 | Naming | Module docstring uses `TUnpivotRow` instead of `UnpivotRow`. |
| NAME-UPR-004 | Naming | Error log uses hardcoded `TUnpivotRow` instead of `self.component_type`. |
| STD-UPR-001 | Standards | `_validate_config()` not called automatically during `execute()`. |
| STD-UPR-002 | Standards | Dual validation methods (`_validate_config()` and `validate_config()`) add confusion. |
| STD-UPR-003 | Standards | Uses `ValueError` instead of project-standard `ConfigurationError`. |
| STD-UPR-004 | Standards | Catch-all exception handler does not wrap in `ComponentExecutionError`. |
| DBG-UPR-001 | Debug | Excessive eager f-string DEBUG logging in hot path. |
| PERF-UPR-002 | Performance | Redundant no-op filter creates unnecessary DataFrame copy (~3.2 GB for 50M rows). |
| PERF-UPR-003 | Performance | Multiple chained DataFrame copies; should use `inplace=True`. |
| PERF-UPR-004 | Performance | O(N*M*log(N*M)) sort may be unnecessary if natural melt order suffices. |

### P3 -- Low

| ID | Category | Summary |
|----|----------|---------|
| CONV-UPR-009 | Converter | Original input schema from Talend XML not preserved. |
| ENG-UPR-008 | Engine | Streaming mode chunk ordering may differ from batch mode. |
| NAME-UPR-005 | Naming | Class docstring parameter descriptions ambiguous (config key vs column name). |
| STD-UPR-005 | Standards | Class constants lack type annotations. |
| DBG-UPR-002 | Debug | Base class `_update_global_map()` logs stats at INFO level; should be DEBUG. |
| PERF-UPR-005 | Performance | Eager f-string evaluation in debug logs. |
| SEC-UPR-001 | Security | No input sanitization on column names from config. |

### Issue Count Summary

| Priority | Count | Categories |
|----------|-------|------------|
| P0 | 6 | 2 converter, 1 engine bug, 2 cross-cutting bugs, 1 testing |
| P1 | 14 | 4 converter, 2 engine, 5 engine bugs, 1 performance, 1 testing |
| P2 | 18 | 2 converter, 3 engine, 1 engine bug, 4 naming, 4 standards, 1 debug, 3 performance |
| P3 | 7 | 1 converter, 1 engine, 1 naming, 1 standards, 1 debug, 1 performance, 1 security |
| **Total** | **45** | |

---

## 10. Recommendations

### Immediate (Before Production)

1. **Fix `_update_global_map()` bug** (BUG-UPR-005): Change `value` to `stat_value` on `base_component.py` line 304. Better yet, simplify the log line to avoid referencing loop variables after the loop: just log the three main stats explicitly. **Impact**: Fixes ALL components (cross-cutting). **Risk**: Very low (log message only).

2. **Fix `GlobalMap.get()` bug** (BUG-UPR-006): Add `default: Any = None` parameter to the `get()` method signature in `global_map.py` line 26. This fixes both direct calls and the two-argument call from `get_component_stat()` on line 58. **Impact**: Fixes ALL components and any code using `global_map.get()`. **Risk**: Very low (adds optional parameter with backward-compatible default).

3. **Fix output schema pollution** (BUG-UPR-001): Remove lines 189-193 in `unpivot_row.py`. The output should contain ONLY `[pivot_key, pivot_value, ...row_keys]`. The loop `for col in input_data.columns: if col not in unpivoted_df.columns: unpivoted_df[col] = None` re-adds the very columns being unpivoted. Delete these lines entirely.

4. **Fix dead code** (BUG-UPR-002): Remove lines 183-187 in `unpivot_row.py`. The loop iterating `column_order` and checking `if col not in unpivoted_df.columns` is unreachable since `column_order` is derived from `unpivoted_df.columns`.

5. **Fix redundant filter** (ENG-UPR-006): Remove line 175 in `unpivot_row.py`. The filter `unpivoted_df[unpivoted_df[pivot_key_column].isin(columns_to_unpivot)]` is always a no-op after `melt(value_vars=columns_to_unpivot)`.

6. **Fix converter XML access** (CONV-UPR-001): Replace `node.get('PARAM')` with `node.find('.//elementParameter[@name="PARAM"]').get('value', default)` for all parameters in `parse_unpivot_row()`. Use a helper function:
   ```python
   def get_param(name, default=None):
       param = node.find(f'.//elementParameter[@name="{name}"]')
       return param.get('value', default) if param is not None else default
   ```

7. **Remove hardcoded row_keys** (CONV-UPR-002): Replace the domain-specific fallback `['COBDATE', 'AGREEMENTID', ...]` with an empty list and a warning log. The converter should never contain business-specific column names:
   ```python
   component['config']['row_keys'] = [key for key in row_keys if key]
   if not component['config']['row_keys']:
       logger.warning(f"No ROW_KEYS found for tUnpivotRow {component.get('id', 'unknown')}")
   ```

8. **Align config keys** (CONV-UPR-004): Change converter to output `pivot_key` and `pivot_value` instead of `pivot_column` and `value_column`. The engine reads `pivot_key`/`pivot_value` which are the Talend-standard names.

9. **Fix NB_LINE_REJECT** (BUG-UPR-003): Pass the filtered row count to `_update_stats()`:
   ```python
   rows_filtered = 0
   if not include_empty_values:
       before_filter = len(unpivoted_df)
       unpivoted_df = unpivoted_df.dropna(subset=[pivot_value_column])
       rows_filtered = before_filter - len(unpivoted_df)
       logger.info(f"[{self.id}] Filtered out {rows_filtered} rows with empty values")
   rows_out = len(unpivoted_df)
   self._update_stats(rows_in, rows_out, rows_filtered)
   ```

10. **Create unit test suite** (TEST-UPR-001): Implement at minimum the 9 P0 test cases listed in Section 8.3. These cover: basic unpivot, single/multiple row keys, empty input (None and DataFrame), missing config, missing columns, and null handling.

### Short-Term (Hardening)

11. **Extract `INCLUDE_NULL_VALUES`** (CONV-UPR-005): Add extraction in converter using the corrected XML access pattern, and map to engine's `include_empty_values` config key:
    ```python
    include_null_str = get_param('INCLUDE_NULL_VALUES', 'true')
    component['config']['include_empty_values'] = include_null_str.lower() != 'false' if isinstance(include_null_str, str) else True
    ```

12. **Fix schema types** (CONV-UPR-003): Change `'type': 'str'` to `'type': 'id_String'` in the converter's synthesized output schema.

13. **Implement `die_on_error`** (ENG-UPR-003): Add graceful error handling in `_process()`:
    ```python
    except Exception as e:
        die_on_error = self.config.get('die_on_error', False)
        if die_on_error:
            raise ComponentExecutionError(self.id, str(e), e) from e
        else:
            logger.error(f"[{self.id}] {self.component_type}: {e}")
            self._update_stats(rows_in, 0, 0)
            return {'main': pd.DataFrame()}
    ```

14. **Add String type coercion** (ENG-UPR-002): After `pd.melt()`, convert `pivot_value_column` to string type to match Talend behavior:
    ```python
    # Convert pivot_value to string (Talend always outputs String)
    null_mask = unpivoted_df[pivot_value_column].isna()
    unpivoted_df[pivot_value_column] = unpivoted_df[pivot_value_column].astype(str)
    # Restore NaN for actual null values (astype(str) converts NaN to 'nan')
    unpivoted_df.loc[null_mask, pivot_value_column] = None
    ```

15. **Fix naming consistency** (NAME-UPR-002, -003, -004): Replace all instances of `TUnpivotRow` with `self.component_type` or the correct form `tUnpivotRow`:
    - Line 2: Change docstring to `"UnpivotRow - Convert columns into rows by unpivoting."`
    - Line 135: Change to `f"Row keys must be specified for {self.component_type}."`
    - Line 212: Change to `f"[{self.id}] {self.component_type} processing failed: {e}"`

16. **Use project exception types** (STD-UPR-003, -004): Replace `ValueError` with `ConfigurationError` on lines 137 and 144. Wrap catch-all exception in `ComponentExecutionError`:
    ```python
    from ...exceptions import ConfigurationError, ComponentExecutionError
    ```

17. **Add converter parser docstring** (CONV-UPR-008): Document all expected Talend parameters per STANDARDS.md.

### Long-Term (Optimization)

18. **Eliminate unnecessary DataFrame copy** (PERF-UPR-001): Use in-place column addition instead of `input_data.copy()`:
    ```python
    input_data['_original_order'] = range(len(input_data))
    unpivoted_df = input_data.melt(...)
    input_data.drop('_original_order', axis=1, inplace=True)  # clean up
    ```

19. **Consolidate chained operations** (PERF-UPR-003): Use `inplace=True` for `sort_values()` and `drop()`:
    ```python
    unpivoted_df.sort_values(['_original_order', pivot_key_column], inplace=True, ignore_index=True)
    unpivoted_df.drop('_original_order', axis=1, inplace=True)
    ```

20. **Evaluate sort necessity** (PERF-UPR-004): Determine if the natural `pd.melt()` output order matches Talend's order. `pd.melt()` already iterates id combinations in order for each value_var. If Talend outputs all unpivoted columns for row 1, then all for row 2, etc., the natural melt order with `id_vars` preserves this. The sort may be entirely unnecessary, saving O(N*M*log(N*M)) time.

21. **Switch to lazy logging** (PERF-UPR-005): Replace `logger.debug(f"...")` with `logger.debug("...", ...)` format throughout the class.

22. **Auto-call `_validate_config()`** (STD-UPR-001): Add validation call at the start of `_process()`:
    ```python
    errors = self._validate_config()
    if errors:
        error_msg = f"Configuration validation failed: {'; '.join(errors)}"
        raise ConfigurationError(error_msg)
    ```

23. **Remove dead `group_by_columns`** (CONV-UPR-007): Remove extraction from converter since the engine never reads it.

24. **Set `{id}_ERROR_MESSAGE` in globalMap** (ENG-UPR-007): In error handlers within `execute()`, call `self.global_map.put(f"{self.id}_ERROR_MESSAGE", str(e))`.

---

## 11. Detailed Code Walkthrough

This section provides a line-by-line analysis of the engine implementation for complete audit transparency.

### Module Header (Lines 1-16)

```python
"""
TUnpivotRow - Convert columns into rows by unpivoting.
Talend equivalent: tUnpivotRow
"""
import logging
import pandas as pd
from typing import Dict, Any, Optional, List
from ...base_component import BaseComponent

logger = logging.getLogger(__name__)
```

**Observations:**
- Module docstring uses `TUnpivotRow` (NAME-UPR-003) -- should be `UnpivotRow`
- Imports are in correct order per STANDARDS.md (stdlib, third-party, project)
- Logger correctly initialized at module level
- Import of `List` is used only in `_validate_config()` return type
- No import of `ConfigurationError` or `ComponentExecutionError` from exceptions module

### Class Definition and Constants (Lines 19-59)

**Class docstring** is comprehensive and follows STANDARDS.md template with Configuration, Inputs, Outputs, Statistics, Example, and Notes sections. However:
- The `pivot_key` and `pivot_value` config descriptions are ambiguous (NAME-UPR-005)
- The `Notes` section mentions "Missing columns are added with None values" which documents the bug (BUG-UPR-001) as intended behavior
- Statistics docstring says "NB_LINE_REJECT: Always 0 (no rows are rejected)" which is incorrect when `include_empty_values=False`

**Constants:**
- `DEFAULT_PIVOT_KEY = 'pivot_key'` -- correct, matches Talend default
- `DEFAULT_PIVOT_VALUE = 'pivot_value'` -- correct, matches Talend default
- `DEFAULT_INCLUDE_EMPTY_VALUES = True` -- matches Talend's default behavior

### `_validate_config()` Method (Lines 61-98)

**Validation coverage:**

| Config Key | Validated? | Checks |
|------------|-----------|--------|
| `row_keys` | Yes | Presence in config, isinstance list, non-empty, all entries are strings |
| `pivot_key` | Yes | isinstance string (if present) |
| `pivot_value` | Yes | isinstance string (if present) |
| `include_empty_values` | Yes | isinstance bool (if present) |
| `die_on_error` | **No** | Not validated |
| `group_by_columns` | **No** | Not validated (dead config anyway) |

The validation is thorough for the parameters it covers. However, it is **never automatically invoked** (STD-UPR-001). The `execute()` -> `_execute_batch()` -> `_process()` path never calls `_validate_config()`. Only the weaker inline check (`if not row_keys: raise ValueError`) in `_process()` runs automatically.

### `_process()` Method (Lines 100-213)

**Line-by-line analysis:**

**Lines 114-118 -- Empty input handling:**
```python
if input_data is None or input_data.empty:
    logger.warning(f"[{self.id}] Empty input received")
    self._update_stats(0, 0, 0)
    return {'main': pd.DataFrame()}
```
Correct pattern per STANDARDS.md. Returns empty DataFrame with zeroed stats. The `input_data.empty` check handles both empty DataFrames and zero-row DataFrames correctly.

**Lines 123-127 -- Config extraction:**
```python
row_keys = self.config.get('row_keys', [])
pivot_key_column = self.config.get('pivot_key', self.DEFAULT_PIVOT_KEY)
pivot_value_column = self.config.get('pivot_value', self.DEFAULT_PIVOT_VALUE)
include_empty_values = self.config.get('include_empty_values', self.DEFAULT_INCLUDE_EMPTY_VALUES)
```
Note: reads `pivot_key` and `pivot_value` config keys -- but converter outputs `pivot_column` and `value_column` (CONV-UPR-004). The engine will always use defaults because the converter's keys don't match.

**Lines 133-137 -- Row keys validation:**
```python
if not row_keys:
    error_msg = "Row keys must be specified for TUnpivotRow."
    logger.error(f"[{self.id}] {error_msg}")
    raise ValueError(error_msg)
```
Uses `ValueError` instead of `ConfigurationError` (STD-UPR-003). Uses `TUnpivotRow` naming (NAME-UPR-002).

**Lines 139-144 -- Missing column detection:**
```python
missing_keys = [key for key in row_keys if key not in input_data.columns]
if missing_keys:
    error_msg = f"Missing row keys in input data: {missing_keys}"
    logger.error(f"[{self.id}] {error_msg}")
    raise ValueError(error_msg)
```
Good defensive check with descriptive error message listing the specific missing columns. Should use `ConfigurationError`.

**Lines 146-149 -- Column identification:**
```python
columns_to_unpivot = [col for col in input_data.columns if col not in row_keys]
```
Correctly identifies columns to unpivot as all non-row-key columns. Preserves original column order from the input DataFrame.

**Lines 155-164 -- Core melt operation:**
```python
input_data_with_index = input_data.copy()
input_data_with_index['_original_order'] = range(len(input_data))
unpivoted_df = input_data_with_index.melt(
    id_vars=row_keys + ['_original_order'],
    value_vars=columns_to_unpivot,
    var_name=pivot_key_column,
    value_name=pivot_value_column,
)
```
The `pd.melt()` call is correct and is the standard pandas approach for unpivoting. However, the full copy for `_original_order` is wasteful (PERF-UPR-001). A more efficient approach would modify the input in place and clean up after.

**Lines 166-170 -- Sort and cleanup:**
```python
unpivoted_df = unpivoted_df.sort_values(['_original_order', pivot_key_column], ignore_index=True)
unpivoted_df = unpivoted_df.drop('_original_order', axis=1)
```
Sort ensures Talend-like row ordering (grouped by original row, then by column name alphabetically within each row). The sort is functionally correct but expensive for large outputs (PERF-UPR-004). `pd.melt()` naturally groups all value_vars for each id combination, so the primary sort key (`_original_order`) is already in order. The secondary sort key (`pivot_key_column`) adds alphabetical ordering within each row's unpivoted values, which may or may not match Talend's column iteration order.

**Line 175 -- Redundant filter:**
```python
unpivoted_df = unpivoted_df[unpivoted_df[pivot_key_column].isin(columns_to_unpivot)]
```
This is always a no-op (ENG-UPR-006, PERF-UPR-002). After `melt(value_vars=columns_to_unpivot)`, the `var_name` column can ONLY contain values from `columns_to_unpivot`. This line creates an unnecessary full copy of the DataFrame.

**Lines 178-181 -- Column reordering:**
```python
column_order = [pivot_key_column, pivot_value_column] + [col for col in unpivoted_df.columns if col not in [pivot_key_column, pivot_value_column]]
unpivoted_df = unpivoted_df[column_order]
```
Reorders to put pivot columns first. The list comprehension includes row_key columns (correct) but will also include any other columns that might exist. The Talend output is strictly `[pivot_key, pivot_value, ...row_keys]`, so the column order should be explicitly `[pivot_key_column, pivot_value_column] + row_keys`.

**Lines 183-187 -- Dead code:**
```python
for col in column_order:
    if col not in unpivoted_df.columns:
        unpivoted_df[col] = None
```
Since `column_order` is derived from `unpivoted_df.columns`, this condition is never true (BUG-UPR-002). This is unreachable dead code.

**Lines 189-193 -- Schema pollution (BUG-UPR-001):**
```python
for col in input_data.columns:
    if col not in unpivoted_df.columns:
        unpivoted_df[col] = None
```
This re-adds the original wide columns (the very columns being unpivoted) back into the output with `None` values. For example, if unpivoting `jan_sales`, `feb_sales`, `mar_sales`, these columns are added back as all-None columns. This is **incorrect behavior** -- Talend's output contains ONLY `[pivot_key, pivot_value, ...row_keys]`.

**Lines 195-200 -- Null value filtering:**
```python
if not include_empty_values:
    before_filter = len(unpivoted_df)
    unpivoted_df = unpivoted_df.dropna(subset=[pivot_value_column])
    rows_filtered = before_filter - len(unpivoted_df)
    logger.info(f"[{self.id}] Filtered out {rows_filtered} rows with empty values")
```
The `dropna()` only checks for `NaN`/`None`. Empty strings (`""`) are NOT filtered -- which actually matches Talend's behavior. The `rows_filtered` count is computed and logged but NOT added to `NB_LINE_REJECT` (BUG-UPR-003).

**Lines 202-209 -- Statistics and return:**
```python
rows_out = len(unpivoted_df)
self._update_stats(rows_in, rows_out, 0)
```
`NB_LINE_REJECT` is hardcoded to `0` even when rows were filtered. `rows_in` correctly captures the INPUT row count. `rows_out` correctly captures the OUTPUT row count after all processing.

**Lines 211-213 -- Exception handling:**
```python
except Exception as e:
    logger.error(f"[{self.id}] Error in TUnpivotRow: {e}")
    raise
```
Catches all exceptions and re-raises without wrapping. Uses `TUnpivotRow` naming (NAME-UPR-004). Does not wrap in `ComponentExecutionError` (STD-UPR-004). Does not check `die_on_error` (ENG-UPR-003).

### `validate_config()` Method (Lines 215-234)

This is a public wrapper around `_validate_config()` that converts the list of errors into a boolean. It provides backward compatibility but is never called automatically by the execution pipeline. The docstring explains this is for "backward compatibility" (line 225).

---

## 12. Converter-Engine Integration Analysis

### Data Flow: Talend XML -> Converter -> Engine

```
Talend XML                   Converter Output            Engine Reads
-----------                  ----------------            ------------
ROW_KEYS (elementParam)  --> row_keys (list)          -> row_keys (list)          OK (when extracted)
PIVOT_COLUMN (elemParam) --> pivot_column (string)    -> pivot_key (string)       MISMATCH (CONV-UPR-004)
VALUE_COLUMN (elemParam) --> value_column (string)    -> pivot_value (string)     MISMATCH (CONV-UPR-004)
GROUP_BY_COLUMNS         --> group_by_columns (list)  -> (not read)              DEAD DATA (CONV-UPR-007)
DIE_ON_ERROR             --> die_on_error (bool)      -> (not read)              IGNORED (ENG-UPR-003)
INCLUDE_NULL_VALUES      --> (not extracted)          -> include_empty_values     MISSING (CONV-UPR-005)
SCHEMA                   --> schema.output (list)     -> (not read by _process)  NOT USED
```

**Key finding**: Due to the config key mismatch (CONV-UPR-004) and broken XML access (CONV-UPR-001), the converter's output is **functionally useless** for `pivot_column`, `value_column`, `group_by_columns`, and `die_on_error`. The engine always operates on its default values. Only `row_keys` flows correctly from Talend XML to engine execution.

### Schema Flow

```
Talend XML Schema             Converter Output Schema        Engine Behavior
-----------------             ----------------------         ---------------
Input columns (from design)   Overwritten by synthesized     Not used by _process()
                              output schema with 'str' type  (engine derives output
                              instead of 'id_String'         from input DataFrame)
```

The converter synthesizes an output schema (CONV-UPR-003) but the engine's `_process()` never reads or applies it. The engine derives its output schema entirely from the input DataFrame's structure, which means the converter's schema work is also functionally unused.

---

## 13. Edge Case Analysis

### 13.1 NaN Handling

When the input DataFrame contains `NaN` values in columns being unpivoted:

| Input Type | After `pd.melt()` | After `dropna()` (include_empty=False) | Talend Behavior |
|-----------|-------------------|----------------------------------------|-----------------|
| `float('nan')` | Preserved as `NaN` | **Removed** | Removed (null in Java) |
| `np.nan` | Preserved as `NaN` | **Removed** | Removed (null in Java) |
| `None` (in object column) | Converted to `NaN` by melt | **Removed** | Removed (null in Java) |
| `pd.NA` (nullable int) | Converted to `NaN` by melt | **Removed** | Removed (null in Java) |

**Verdict**: NaN handling is correct. `pd.melt()` normalizes all missing value representations to `NaN`, and `dropna()` correctly removes them.

### 13.2 Empty String Handling

| Input Value | After `pd.melt()` | After `dropna()` (include_empty=False) | Talend Behavior |
|-------------|-------------------|----------------------------------------|-----------------|
| `""` (empty string) | Preserved as `""` | **NOT removed** (dropna ignores empty strings) | **NOT removed** (empty string is not null in Java) |
| `"   "` (whitespace) | Preserved as `"   "` | **NOT removed** | **NOT removed** |
| `"None"` (string) | Preserved as `"None"` | **NOT removed** | **NOT removed** |
| `"null"` (string) | Preserved as `"null"` | **NOT removed** | **NOT removed** |

**Verdict**: Empty string handling is correct. Empty strings are distinct from null in both Python/pandas and Java/Talend. The `dropna()` correctly does not filter them.

### 13.3 pd.melt() Behavior Deep Dive

`pd.DataFrame.melt()` is the core operation. Understanding its exact behavior is critical for verifying correctness:

1. **Column ordering**: `melt()` iterates `value_vars` in the order provided. Since `columns_to_unpivot = [col for col in input_data.columns if col not in row_keys]`, the order matches the input DataFrame's column order. This is consistent with Talend's left-to-right column iteration.

2. **Row grouping**: For each unique combination of `id_vars` values, `melt()` produces one row per `value_var`. The output naturally groups all values for each input row together, preserving the input row order.

3. **Type preservation**: `melt()` preserves the original column types in the `value_name` column. If unpivoting columns with mixed types (int and string), the resulting `pivot_value` column will have `object` dtype. This differs from Talend, which always produces String output (ENG-UPR-002).

4. **Index handling**: The `_original_order` column is added to track input row order. This is necessary because `melt()` resets the index. However, since `melt()` already preserves row order (iterating id combinations in order), the `_original_order` column is redundant for the primary grouping -- it only adds the ability to sort by original row AND column name simultaneously.

### 13.4 include_empty_values Edge Cases

| Scenario | `include_empty_values=True` | `include_empty_values=False` |
|----------|----------------------------|------------------------------|
| All values non-null | N*M output rows | N*M output rows (same) |
| All values null | N*M output rows (all with NaN pivot_value) | 0 output rows |
| Mixed: some null, some not | N*M output rows | (N*M - null_count) output rows |
| Single null column | N rows with NaN in output | N fewer rows in output |
| Zero (int 0) | Included | Included (0 is not NaN) |
| False (bool) | Included | Included (False is not NaN) |
| 0.0 (float) | Included | Included (0.0 is not NaN) |

### 13.5 Column Ordering Verification

**Expected Talend output order**: `[pivot_key, pivot_value, row_key_1, row_key_2, ...]`

**Actual v1 engine output order** (line 179):
```python
column_order = [pivot_key_column, pivot_value_column] + [col for col in unpivoted_df.columns if col not in [pivot_key_column, pivot_value_column]]
```

After BUG-UPR-001 (lines 189-193), the output also includes the original unpivoted columns with None values. So the actual order becomes:
```
[pivot_key, pivot_value, row_key_1, row_key_2, ..., original_col_1 (None), original_col_2 (None), ...]
```

This does NOT match Talend's output. After fixing BUG-UPR-001 by removing lines 189-193, the column order would correctly be:
```
[pivot_key, pivot_value, row_key_1, row_key_2, ...]
```

However, the list comprehension `[col for col in unpivoted_df.columns if col not in [...]]` relies on the DataFrame's column order after melt, which places `id_vars` (row keys) in their original order. This is correct.

### 13.6 row_keys Validation Edge Cases

| Scenario | Current Behavior | Expected Behavior |
|----------|-----------------|-------------------|
| `row_keys = []` (empty list) | `ValueError` raised (line 134-137) | Correct -- should error |
| `row_keys = None` (None) | `self.config.get('row_keys', [])` returns `None`; `if not row_keys` catches it | Correct -- should error |
| `row_keys` not in config | `self.config.get('row_keys', [])` returns `[]`; caught by `if not row_keys` | Correct -- should error |
| `row_keys = ['col1']` (single key) | Works correctly | Correct |
| `row_keys = ['nonexistent']` | `ValueError` raised with `missing_keys` list (lines 140-144) | Correct |
| `row_keys = ['col1', 'col1']` (duplicate) | Accepted -- no duplicate check. `pd.melt()` handles it (id_vars can have duplicates) | Ambiguous -- should warn |
| `row_keys` contains ALL columns | `columns_to_unpivot = []` (empty). `pd.melt()` with empty `value_vars` produces empty output. | Should warn user |
| `row_keys = [123]` (non-string) | `_validate_config()` would catch it, but is not auto-called. `_process()` proceeds; `123 not in input_data.columns` raises `ValueError` from missing_keys check. | Works but error message could be clearer |

### 13.7 HYBRID Streaming and _update_global_map Crash

When running in HYBRID mode with `global_map` provided:

1. `execute()` is called (BaseComponent, line 188)
2. Input data exceeds `MEMORY_THRESHOLD_MB` -> switches to STREAMING mode (line 206)
3. `_execute_streaming()` chunks the input and calls `_process()` per chunk
4. Each chunk successfully processes, `_update_stats()` accumulates correctly
5. After all chunks complete, `execute()` calls `_update_global_map()` (line 218)
6. **CRASH**: `_update_global_map()` references undefined `value` on line 304 -> `NameError`
7. The exception propagates to the `except` block in `execute()` (line 227)
8. `execute()` tries to call `_update_global_map()` AGAIN (line 231) -> **CRASH AGAIN**
9. The second `NameError` replaces the original error, and the original processing results are lost

**Impact**: Even though the unpivot processing completed successfully, the results are never returned because `_update_global_map()` crashes. This affects ALL components, not just UnpivotRow, but the impact is particularly severe for UnpivotRow because the data amplification (N*M rows) means significant processing time is wasted.

**Workaround**: Set `global_map=None` when instantiating components. This bypasses `_update_global_map()` entirely. However, this also disables all globalMap functionality including `{id}_NB_LINE` tracking.

---

## 14. Risk Assessment

### Production Readiness Rating: NOT READY

| Risk Area | Severity | Impact |
|-----------|----------|--------|
| **`_update_global_map()` crash** (BUG-UPR-005) | Critical | ALL components crash after processing when globalMap is provided. Results lost. Cross-cutting. |
| **`GlobalMap.get()` crash** (BUG-UPR-006) | Critical | ALL downstream globalMap.get() calls crash. Cross-cutting. |
| **Output schema pollution** (BUG-UPR-001) | Critical | Downstream components receive extra None-filled columns, causing schema mismatches, unexpected data, or failures. |
| **Converter completely broken** (CONV-UPR-001, -002) | Critical | Any Talend job using tUnpivotRow with non-default settings will produce wrong output. Hardcoded row_keys are project-specific. |
| **No test coverage** (TEST-UPR-001) | Critical | No confidence in correctness of any code path; regressions cannot be detected. |
| **Config key mismatch** (CONV-UPR-004) | High | Converter output silently ignored; custom pivot/value column names from Talend jobs are lost. |
| **Statistics inaccuracy** (BUG-UPR-003) | High | `NB_LINE_REJECT` always 0 even when rows are filtered; misleading pipeline monitoring. |
| **No `die_on_error` support** (ENG-UPR-003) | Medium | Jobs expecting graceful error handling will instead fail with unhandled exceptions. |
| **No String type coercion** (ENG-UPR-002) | Medium | Downstream components expecting String-typed pivot values receive mixed types. |

### Blockers for Production

1. **Fix BUG-UPR-005** -- `_update_global_map()` crash (cross-cutting)
2. **Fix BUG-UPR-006** -- `GlobalMap.get()` crash (cross-cutting)
3. **Fix BUG-UPR-001** -- output schema pollution (remove lines 189-193)
4. **Fix CONV-UPR-001** -- XML parameter access (use `node.find('.//elementParameter...')`)
5. **Fix CONV-UPR-002** -- hardcoded row_keys (remove domain-specific defaults)
6. **Fix CONV-UPR-004** -- config key mismatch (align converter output with engine input)
7. **Add basic unit tests** (TEST-UPR-001) -- minimum 9 P0 test cases

---

## 15. Empty String vs Null Handling Deep Dive

### The Problem

The `include_empty_values` config uses `dropna()` to filter null rows (line 198):

```python
unpivoted_df = unpivoted_df.dropna(subset=[pivot_value_column])
```

`dropna()` only removes rows where the value is `NaN` or `None`. It does NOT remove rows where the value is:
- Empty string `""`
- Whitespace-only string `"   "`
- The string `"None"` or `"null"`

### Talend Behavior

In Talend's tUnpivotRow:
- `null` Java values produce no output row (when INCLUDE_NULL_VALUES is false)
- Empty string `""` values ARE included in output (they are not null in Java)
- Some versions of tUnpivotRow have a known bug where null values cause `NullPointerException` and the previous field's value is retained
- Java's `null` is distinct from empty string `""` -- this maps to pandas' `NaN`/`None` vs `""`

### V1 Engine Behavior Matrix

| Input Value | pandas Type | `include_empty_values=True` | `include_empty_values=False` | Talend Behavior | Match? |
|-------------|-----------|----------------------------|------------------------------|-----------------|--------|
| `100` (int) | int64 | Included | Included | Included | Yes |
| `"hello"` (str) | object | Included | Included | Included | Yes |
| `""` (empty string) | object | Included | Included (NOT filtered) | Included | Yes |
| `"   "` (whitespace) | object | Included | Included (NOT filtered) | Included | Yes |
| `None` | NaN (after melt) | Included | **Filtered** | Filtered (or NPE in buggy versions) | Yes |
| `float('nan')` | float64 NaN | Included | **Filtered** | Filtered (Java null equivalent) | Yes |
| `np.nan` | float64 NaN | Included | **Filtered** | Filtered | Yes |
| `pd.NA` | pd.NA -> NaN | Included | **Filtered** | Filtered | Yes |
| `0` (zero) | int64 | Included | Included | Included | Yes |
| `False` (bool) | bool | Included | Included | Included | Yes |
| `0.0` (float zero) | float64 | Included | Included | Included | Yes |

### Gap Analysis

The v1 engine's null handling is **correct** for all common cases. The behavior matrix shows perfect alignment with Talend's expected behavior:
- True null/NaN values are correctly filtered when `include_empty_values=False`
- Empty strings, zeros, and other falsy-but-not-null values are correctly preserved
- The subtle difference between `None`, `NaN`, `np.nan`, and `pd.NA` is correctly normalized by `pd.melt()` into a consistent `NaN` that `dropna()` handles

**The only potential gap** is if a specific version of Talend's tUnpivotRow also treats empty strings as "empty values" to be filtered. Based on community documentation, this is NOT the standard behavior -- empty strings are not null in Java and should be preserved.

---

## 16. Recommended Fix: Corrected `parse_unpivot_row()`

The following is a corrected version of the converter parser that addresses CONV-UPR-001 through CONV-UPR-008:

```python
def parse_unpivot_row(self, node, component: Dict) -> Dict:
    """
    Parse tUnpivotRow specific configuration from Talend XML node.

    Talend Parameters:
        ROW_KEYS (table): Columns to preserve as identifiers
            (elementValue with elementRef="COLUMN")
        PIVOT_COLUMN (str): Name for the pivot key output column.
            Default: 'pivot_key'
        VALUE_COLUMN (str): Name for the pivot value output column.
            Default: 'pivot_value'
        DIE_ON_ERROR (bool): Whether to stop job on error.
            Default: false
        INCLUDE_NULL_VALUES (bool): Whether to include null values in output.
            Default: true

    Config Output Keys:
        pivot_key (str): Name for pivot key column (matches engine key)
        pivot_value (str): Name for pivot value column (matches engine key)
        row_keys (List[str]): Columns to preserve as identifiers
        die_on_error (bool): Whether to stop on error
        include_empty_values (bool): Whether to include null values
    """
    def get_param(name, default=None):
        """Helper to correctly extract elementParameter values from XML."""
        param = node.find(f'.//elementParameter[@name="{name}"]')
        return param.get('value', default) if param is not None else default

    # Extract pivot column names (using engine config key names)
    pivot_key_name = get_param('PIVOT_COLUMN', 'pivot_key')
    if pivot_key_name and pivot_key_name.startswith('"') and pivot_key_name.endswith('"'):
        pivot_key_name = pivot_key_name[1:-1]
    component['config']['pivot_key'] = pivot_key_name or 'pivot_key'

    pivot_value_name = get_param('VALUE_COLUMN', 'pivot_value')
    if pivot_value_name and pivot_value_name.startswith('"') and pivot_value_name.endswith('"'):
        pivot_value_name = pivot_value_name[1:-1]
    component['config']['pivot_value'] = pivot_value_name or 'pivot_value'

    # Extract ROW_KEYS from XML (this was already correct)
    row_keys = []
    for element in node.findall('.//elementParameter[@name="ROW_KEYS"]/elementValue'):
        if element.get('elementRef') == 'COLUMN':
            value = element.get('value', '').strip('"')
            if value:
                row_keys.append(value)

    if not row_keys:
        logger.warning(
            f"No ROW_KEYS found for tUnpivotRow component "
            f"{component.get('id', 'unknown')}"
        )

    component['config']['row_keys'] = row_keys  # No hardcoded fallback

    # Extract boolean parameters with proper string-to-bool conversion
    die_on_error_str = get_param('DIE_ON_ERROR', 'false')
    component['config']['die_on_error'] = (
        die_on_error_str.lower() == 'true'
        if isinstance(die_on_error_str, str) else False
    )

    include_null_str = get_param('INCLUDE_NULL_VALUES', 'true')
    component['config']['include_empty_values'] = (
        include_null_str.lower() != 'false'
        if isinstance(include_null_str, str) else True
    )

    # Build output schema using Talend type format (id_String)
    output_schema = [
        {'name': component['config']['pivot_key'], 'type': 'id_String',
         'nullable': True, 'key': False},
        {'name': component['config']['pivot_value'], 'type': 'id_String',
         'nullable': True, 'key': False}
    ]

    for key in component['config']['row_keys']:
        output_schema.append(
            {'name': key, 'type': 'id_String', 'nullable': True, 'key': False}
        )

    component['schema']['output'] = output_schema
    return component
```

**Changes from original**:
1. Uses `get_param()` helper with correct `node.find('.//elementParameter...')` pattern
2. Outputs `pivot_key`/`pivot_value` config keys matching engine expectations
3. Removes hardcoded domain-specific row_keys fallback
4. Adds string-to-bool conversion for `DIE_ON_ERROR`
5. Extracts `INCLUDE_NULL_VALUES` and maps to `include_empty_values`
6. Uses `id_String` type in schema instead of `str`
7. Removes dead `group_by_columns` extraction
8. Adds comprehensive docstring

---

## 17. Recommended Fix: Corrected `_process()` Core Logic

The following shows the corrected core processing logic addressing BUG-UPR-001, BUG-UPR-002, BUG-UPR-003, ENG-UPR-002, ENG-UPR-003, ENG-UPR-006, and PERF-UPR-001:

```python
def _process(self, input_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
    """
    Unpivot input data based on configuration.

    Args:
        input_data: Input DataFrame to unpivot (may be None or empty)

    Returns:
        Dictionary containing:
            - 'main': Unpivoted DataFrame with columns converted to rows

    Raises:
        ConfigurationError: If row_keys are missing or invalid
        ComponentExecutionError: If processing fails and die_on_error=True
    """
    # Handle empty input
    if input_data is None or input_data.empty:
        logger.warning("[%s] Empty input received", self.id)
        self._update_stats(0, 0, 0)
        return {'main': pd.DataFrame()}

    rows_in = len(input_data)
    logger.info("[%s] Processing started: %d rows", self.id, rows_in)

    # Get configuration with defaults
    row_keys = self.config.get('row_keys', [])
    pivot_key_column = self.config.get('pivot_key', self.DEFAULT_PIVOT_KEY)
    pivot_value_column = self.config.get('pivot_value', self.DEFAULT_PIVOT_VALUE)
    include_empty_values = self.config.get('include_empty_values',
                                           self.DEFAULT_INCLUDE_EMPTY_VALUES)
    die_on_error = self.config.get('die_on_error', False)

    # Validate row_keys
    if not row_keys:
        raise ConfigurationError(
            f"[{self.id}] row_keys must be specified for tUnpivotRow"
        )

    missing_keys = [key for key in row_keys if key not in input_data.columns]
    if missing_keys:
        raise ConfigurationError(
            f"[{self.id}] Missing row keys in input data: {missing_keys}"
        )

    # Identify columns to unpivot
    columns_to_unpivot = [col for col in input_data.columns if col not in row_keys]
    logger.debug("[%s] Row keys: %s, Columns to unpivot: %s",
                 self.id, row_keys, columns_to_unpivot)

    try:
        # Perform unpivot using pandas melt (no copy needed)
        unpivoted_df = input_data.melt(
            id_vars=row_keys,
            value_vars=columns_to_unpivot,
            var_name=pivot_key_column,
            value_name=pivot_value_column,
        )

        # Convert pivot_value to string to match Talend behavior
        null_mask = unpivoted_df[pivot_value_column].isna()
        unpivoted_df[pivot_value_column] = (
            unpivoted_df[pivot_value_column].astype(str)
        )
        unpivoted_df.loc[null_mask, pivot_value_column] = None

        # Reorder columns: pivot_key, pivot_value, then row_keys ONLY
        column_order = [pivot_key_column, pivot_value_column] + row_keys
        unpivoted_df = unpivoted_df[column_order]

        # Filter null values if configured
        rows_filtered = 0
        if not include_empty_values:
            before_filter = len(unpivoted_df)
            unpivoted_df = unpivoted_df.dropna(subset=[pivot_value_column])
            rows_filtered = before_filter - len(unpivoted_df)
            logger.info("[%s] Filtered %d rows with null values",
                        self.id, rows_filtered)

        # Update statistics with accurate reject count
        rows_out = len(unpivoted_df)
        self._update_stats(rows_in, rows_out, rows_filtered)

        logger.info("[%s] Complete: in=%d, out=%d, filtered=%d",
                    self.id, rows_in, rows_out, rows_filtered)

        return {'main': unpivoted_df}

    except ConfigurationError:
        raise  # Re-raise config errors as-is
    except Exception as e:
        if die_on_error:
            logger.error("[%s] %s failed: %s", self.id, self.component_type, e)
            raise ComponentExecutionError(self.id, str(e), e) from e
        else:
            logger.warning("[%s] %s error (continuing): %s",
                           self.id, self.component_type, e)
            self._update_stats(rows_in, 0, 0)
            return {'main': pd.DataFrame()}
```

**Changes from original**:
1. Removed full `input_data.copy()` -- uses `melt()` directly on input
2. Removed `_original_order` column tracking (melt preserves order natively)
3. Removed redundant no-op filter (line 175)
4. Removed dead code (lines 183-187)
5. Removed schema pollution (lines 189-193) -- output is strictly `[pivot_key, pivot_value, ...row_keys]`
6. Added String type coercion for `pivot_value` with null preservation
7. Added `rows_filtered` to `_update_stats()` reject count
8. Added `die_on_error` support with graceful degradation
9. Uses `ConfigurationError` instead of `ValueError`
10. Uses lazy `%s`-style logging instead of eager f-strings
11. Explicit column order: `[pivot_key_column, pivot_value_column] + row_keys`

---

## 18. Comparison with Similar Components

### Comparison with tPivotToColumnsDelimited

| Aspect | `tPivotToColumnsDelimited` | `tUnpivotRow` |
|--------|---------------------------|---------------|
| Operation | Rows to columns (pivot) | Columns to rows (unpivot) |
| Converter XML access | Correct (`node.find('.//elementParameter...')`) | **Incorrect** (`node.get()`) |
| Config key alignment | Aligned with engine | **Misaligned** (converter vs engine key names) |
| Output schema | Matches Talend | **Polluted** with extra None columns |
| Type coercion | N/A | **Missing** (should coerce to String) |

### Comparison with BaseComponent Standards

| Feature | BaseComponent Pattern | UnpivotRow Implementation | Compliant? |
|---------|----------------------|--------------------------|------------|
| Empty input handling | Return empty DF, zero stats | Yes | Yes |
| Stats tracking | `_update_stats(in, ok, reject)` | Partial -- reject always 0 | No |
| GlobalMap update | Via `_update_global_map()` | Inherited correctly | Yes |
| Error handling | Wrap in `ComponentExecutionError` | Re-raises raw `Exception` | No |
| Config validation | `_validate_config()` returns errors | Implemented but not auto-called | Partial |
| Streaming support | Via `_execute_streaming()` | Inherited -- chunk ordering issues | Partial |
| Execution modes | batch/streaming/hybrid | Inherited correctly | Yes |
| Exception types | `ConfigurationError`, `ComponentExecutionError` | Uses `ValueError` | No |

---

## Appendix A: File Inventory

| File | Path | Role |
|------|------|------|
| Engine implementation | `src/v1/engine/components/transform/unpivot_row.py` | Main component class (235 lines) |
| Transform `__init__.py` | `src/v1/engine/components/transform/__init__.py` | Exports `UnpivotRow` |
| Engine registry | `src/v1/engine/engine.py` | Registers `UnpivotRow` and `tUnpivotRow` aliases (lines 156-157) |
| Base component | `src/v1/engine/base_component.py` | Parent class with `execute()`, stats, streaming |
| Global map | `src/v1/engine/global_map.py` | GlobalMap storage with cross-cutting bugs |
| Exceptions | `src/v1/engine/exceptions.py` | `ConfigurationError`, `ComponentExecutionError`, etc. |
| Converter parser | `src/converters/complex_converter/component_parser.py` | `parse_unpivot_row()` method (lines 2480-2506) |
| Converter dispatch | `src/converters/complex_converter/converter.py` | Dispatches to `parse_unpivot_row()` (line 355-356) |

## Appendix B: Talend Reference Sources

- [Talend Skill: tUnpivotRow Custom Components](https://talendskill.com/knowledgebase/tunpivotrow-talend-custom-components/)
- [Datalytyx: Denormalise a dataset with Talend's tUnpivotRow](https://www.datalytyx.com/how-to-denormalise-a-dataset-using-talends-tunpivotrow/)
- [ETL Geeks Blog: How to use tUnpivotRow in Talend](http://etlgeeks.blogspot.com/2016/04/how-to-use-custom-componet-in-talend.html)
- [Desired Data: How to use UnpivotRow component in Talend](https://desireddata.blogspot.com/2015/06/how-to-use-unpivotrow-component-in.html)
- [GitHub: TalendExchange/Components](https://github.com/TalendExchange/Components)
- [Talend Community: tUnpivotRow](https://community.talend.com/s/question/0D53p00007vCjh5CAC/where-to-download-tunpivotrow-and-how-to-install-the-component-for-talend-65-version)
- [Qlik/Talend Help: Converting columns to rows](https://help.qlik.com/talend/en-US/components/8.0/tmap/converting-columns-to-rows)
- [Qlik Community: tUnpivotRow discussion](https://community.qlik.com/t5/Installing-and-Upgrading/tUnpivotRow/td-p/2401503)

## Appendix C: Issue Cross-Reference by File

### `unpivot_row.py`

| Line(s) | Issue IDs |
|---------|-----------|
| 2 | NAME-UPR-003 |
| 57-59 | STD-UPR-005 |
| 61-98 | STD-UPR-001, STD-UPR-002 |
| 134-137 | BUG-UPR-004, NAME-UPR-002, STD-UPR-003 |
| 139-144 | STD-UPR-003 |
| 148-149, 153, 167, 172, 175-176, 181, 187, 193 | DBG-UPR-001 |
| 156 | PERF-UPR-001 |
| 167 | PERF-UPR-004 |
| 175 | ENG-UPR-006, PERF-UPR-002 |
| 179 | ENG-UPR-005 |
| 183-187 | BUG-UPR-002 |
| 189-193 | BUG-UPR-001, ENG-UPR-001 |
| 196-199 | BUG-UPR-003, ENG-UPR-004 |
| 204 | BUG-UPR-003 |
| 212 | NAME-UPR-004, STD-UPR-004 |
| 215-234 | STD-UPR-002 |

### `component_parser.py` (parse_unpivot_row)

| Line(s) | Issue IDs |
|---------|-----------|
| 2480-2481 | CONV-UPR-008 |
| 2482 | CONV-UPR-001, CONV-UPR-004 |
| 2483 | CONV-UPR-001, CONV-UPR-004 |
| 2484 | CONV-UPR-001, CONV-UPR-007 |
| 2493 | CONV-UPR-002 |
| 2494 | CONV-UPR-001, CONV-UPR-006 |
| 2498-2499 | CONV-UPR-003 |

### `base_component.py` (Cross-Cutting)

| Line(s) | Issue IDs |
|---------|-----------|
| 304 | BUG-UPR-005, DBG-UPR-002 |

### `global_map.py` (Cross-Cutting)

| Line(s) | Issue IDs |
|---------|-----------|
| 26-28 | BUG-UPR-006 |
| 58 | BUG-UPR-006 |

## Appendix D: Complete Talend Parameter to V1 Config Key Reference

| Talend Parameter | V1 Config Key (Converter) | V1 Config Key (Engine) | Status | Priority to Fix |
|------------------|--------------------------|----------------------|--------|-----------------|
| `ROW_KEYS` | `row_keys` | `row_keys` | Mapped (correct XML access) | -- |
| `PIVOT_COLUMN` | `pivot_column` | `pivot_key` | **Mapped (broken XML access + key mismatch)** | P0 + P1 |
| `VALUE_COLUMN` | `value_column` | `pivot_value` | **Mapped (broken XML access + key mismatch)** | P0 + P1 |
| `GROUP_BY_COLUMNS` | `group_by_columns` | (not read) | **Mapped (broken) -> Dead data** | P2 (remove) |
| `DIE_ON_ERROR` | `die_on_error` | (not read) | **Mapped (broken) -> Ignored** | P0 + P1 |
| `INCLUDE_NULL_VALUES` | (not extracted) | `include_empty_values` | **Not Mapped** | P1 |
| `SCHEMA` | `schema.output` (synthesized) | (not read) | Partial -- synthesized, not extracted | P2 |
| `TSTATCATCHER_STATS` | -- | -- | Not needed (rarely used) | -- |
| `LABEL` | -- | -- | Not needed (cosmetic) | -- |

---

*Report generated: 2026-03-21*
*Auditor: Claude Opus 4.6 (1M context)*
*Engine version: v1*
*Total issues found: 45 (6 P0, 14 P1, 18 P2, 7 P3)*
*Production readiness: NOT READY -- 6 P0 blockers must be resolved*
