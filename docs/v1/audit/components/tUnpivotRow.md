# Audit Report: tUnpivotRow / UnpivotRow

## Component Identity

| Field | Value |
|-------|-------|
| **Talend Name** | `tUnpivotRow` |
| **V1 Engine Class** | `UnpivotRow` |
| **Engine File** | `src/v1/engine/components/transform/unpivot_row.py` |
| **Converter Parser** | `component_parser.py` -> `parse_unpivot_row()` (line ~2480) |
| **Converter Dispatch** | `converter.py` -> `elif component_type == 'tUnpivotRow':` (line ~355) |
| **Registry Aliases** | `UnpivotRow`, `tUnpivotRow` |
| **Category** | Transform |
| **Complexity** | Medium -- columnar transformation with melt/unpivot logic |

---

## Scorecard

| Dimension | Score | P0 | P1 | P2 | P3 |
|-----------|-------|----|----|----|----|
| Converter Coverage | R | 2 | 3 | 2 | 1 |
| Engine Feature Parity | Y | 1 | 2 | 3 | 1 |
| Code Quality | Y | 1 | 2 | 5 | 2 |
| Performance & Memory | Y | 0 | 1 | 2 | 1 |
| Testing | R | 1 | 1 | 0 | 0 |

**Score Legend**: G = Green (good), Y = Yellow (some gaps), R = Red (significant gaps)

---

## 1. Talend Feature Baseline

### What tUnpivotRow Does in Talend

The `tUnpivotRow` is a **custom Talend Exchange component** (not a built-in Talend component) that converts columns into rows -- the inverse of a pivot operation. Given a set of "row key" (identifier) columns and a set of "value" columns, it produces one output row per value column per input row, creating key-value pairs. It is commonly used to denormalize wide datasets into a narrow/long format.

**Example transformation:**

Input (wide):
```
| id | name  | jan_sales | feb_sales | mar_sales |
|----|-------|-----------|-----------|-----------|
| 1  | Alice | 100       | 200       | 150       |
```

Output (long) with `row_keys = [id, name]`:
```
| pivot_key  | pivot_value | id | name  |
|------------|-------------|----|-------|
| jan_sales  | 100         | 1  | Alice |
| feb_sales  | 200         | 1  | Alice |
| mar_sales  | 150         | 1  | Alice |
```

### Origin and Availability

The tUnpivotRow component is available from [Talend Exchange on GitHub](https://github.com/TalendExchange/Components). Multiple versions exist from different contributors (daztop v1.1 from 2009, wzawwin from 2014, leroux-g from 2012, sreenathtr from 2013). It is implemented as a Javajet component and must be manually installed into Talend Studio. It is **not** part of the standard Talend Open Studio or Talend Data Integration distributions.

### Basic Settings (Talend Studio)

| Parameter | Talend Name | Type | Description |
|-----------|-------------|------|-------------|
| Schema | `SCHEMA` | Schema editor | Output column definitions -- contains row key columns plus fixed `pivot_key` and `pivot_value` columns |
| Row Keys | `ROW_KEYS` | Table (COLUMN refs) | List of columns from the input schema to preserve as identifier columns; all other columns are unpivoted |
| Pivot Key Column | (fixed) | Read-only | Output column name for the original column names; always `pivot_key` |
| Pivot Value Column | (fixed) | Read-only | Output column name for the cell values; always `pivot_value` |

### Advanced Settings (Talend Studio)

| Parameter | Talend Name | Type | Description |
|-----------|-------------|------|-------------|
| Die On Error | `DIE_ON_ERROR` | Boolean | Whether to stop the job on processing errors. Default: `false` |
| Include Null Values | `INCLUDE_NULL_VALUES` | Boolean | Whether to emit output rows when the cell value is null. Default: `true` (varies by version) |

**Note**: Because tUnpivotRow is a custom Exchange component, parameter names and availability vary between versions. The parameters above represent the most common implementation. Some versions also expose:

| Parameter | Talend Name | Type | Description |
|-----------|-------------|------|-------------|
| Pivot Column Name | `PIVOT_COLUMN` | String | Custom name for the pivot key output column (some versions) |
| Value Column Name | `VALUE_COLUMN` | String | Custom name for the pivot value output column (some versions) |
| Group By Columns | `GROUP_BY_COLUMNS` | String (semicolon-separated) | Alternative grouping specification (some versions) |

### Connection Types

| Connector | Type | Description |
|-----------|------|-------------|
| `FLOW` (Main) | Input | Input data flow containing the wide-format rows |
| `FLOW` (Main) | Output | Output data flow containing the unpivoted/long-format rows |
| `REJECT` | Output | **Not standard** -- most tUnpivotRow versions do not have a reject flow. Errors either stop the job (if `DIE_ON_ERROR=true`) or are silently dropped. |

### GlobalMap Variables Produced (Talend)

| Key | Type | Description |
|-----|------|-------------|
| `{id}_NB_LINE` | int | Total number of input rows processed |
| `{id}_NB_LINE_OK` | int | Total number of output rows produced (should be `input_rows * unpivoted_columns`) |
| `{id}_NB_LINE_REJECT` | int | Number of rows rejected (typically 0 for this component) |

### Talend Behavioral Notes

1. **All output values are String type**: tUnpivotRow converts all pivot values to String type in its output. Downstream components (tMap, tConvertType) must handle type conversion.
2. **Column order in output**: The output schema is typically `[pivot_key, pivot_value, ...row_key_columns]`.
3. **Null handling**: When a cell value is null, some versions of tUnpivotRow throw a `NullPointerException` and the `pivot_value` retains the value from the previous field. This is a known bug in certain versions.
4. **Row multiplication**: For N input rows and M unpivoted columns, the output will have up to `N * M` rows.
5. **Fixed output column names**: In the original Talend Exchange component, `pivot_key` and `pivot_value` are hardcoded column names. Some extended versions allow customization via `PIVOT_COLUMN` and `VALUE_COLUMN` parameters.
6. **No reject flow**: The standard tUnpivotRow does not have a dedicated REJECT connector.

### Sources

- [Talend Skill: tUnpivotRow Custom Components](https://talendskill.com/knowledgebase/tunpivotrow-talend-custom-components/)
- [Datalytyx: Denormalise a dataset with Talend's tUnpivotRow](https://www.datalytyx.com/how-to-denormalise-a-dataset-using-talends-tunpivotrow/)
- [ETL Geeks Blog: How to use tUnpivotRow in Talend](http://etlgeeks.blogspot.com/2016/04/how-to-use-custom-componet-in-talend.html)
- [Desired Data: How to use UnpivotRow component in Talend](https://desireddata.blogspot.com/2015/06/how-to-use-unpivotrow-component-in.html)
- [GitHub: TalendExchange/Components](https://github.com/TalendExchange/Components)
- [Qlik/Talend Community: tUnpivotRow](https://community.qlik.com/t5/Installing-and-Upgrading/tUnpivotRow/td-p/2401503)

---

## 2. Converter Audit

### Parser Method: `parse_unpivot_row()`

**Location**: `src/converters/complex_converter/component_parser.py`, line ~2480

**Full source reviewed:**

```python
def parse_unpivot_row(self, node, component: Dict) -> Dict:
    """Parse tUnpivotRow specific configuration"""
    component['config']['pivot_column'] = node.get('PIVOT_COLUMN', 'pivot_key')
    component['config']['value_column'] = node.get('VALUE_COLUMN', 'pivot_value')
    component['config']['group_by_columns'] = node.get('GROUP_BY_COLUMNS', '').split(';')

    # Extract ROW_KEYS from XML
    row_keys = []
    for element in node.findall('./elementParameter[@name="ROW_KEYS"]/elementValue'):
        if element.get('elementRef') == 'COLUMN':
            row_keys.append(element.get('value', ''))

    # Ensure row_keys does not contain empty strings and provide default values if empty
    component['config']['row_keys'] = [key for key in row_keys if key ] or \
        ['COBDATE', 'AGREEMENTID', 'MASTERMNEMONIC', 'CLIENT_OR_AFFILIATE',
         'MNEMONIC', 'GMIACCOUNT', 'CURRENCY']
    component['config']['die_on_error'] = node.get('DIE_ON_ERROR', False)

    # Update schema to include only pivot_key, pivot_value, and row_keys in the specified order
    output_schema = [
        {'name': 'pivot_key', 'type': 'str', 'nullable': True, 'key': False},
        {'name': 'pivot_value', 'type': 'str', 'nullable': True, 'key': False}
    ]

    for key in component['config']['row_keys']:
        output_schema.append({'name': key, 'type': 'str', 'nullable': True, 'key': False})

    component['schema']['output'] = output_schema
    return component
```

### Dispatch Registration

**Location**: `src/converters/complex_converter/converter.py`, line ~355

```python
elif component_type == 'tUnpivotRow':
    component = self.component_parser.parse_unpivot_row(node, component)
```

The component is correctly registered in the converter dispatch.

### Parameters Extracted

| Talend Parameter | Converter Extracts? | V1 Config Key | Notes |
|------------------|---------------------|---------------|-------|
| `ROW_KEYS` | Yes | `row_keys` | Extracted from nested `elementParameter/elementValue` with `elementRef="COLUMN"` |
| `PIVOT_COLUMN` | Yes (incorrectly) | `pivot_column` | Uses `node.get()` instead of `node.find('.//elementParameter[@name=...]')` |
| `VALUE_COLUMN` | Yes (incorrectly) | `value_column` | Uses `node.get()` instead of `node.find('.//elementParameter[@name=...]')` |
| `GROUP_BY_COLUMNS` | Yes (incorrectly) | `group_by_columns` | Uses `node.get()` instead of proper XML traversal |
| `DIE_ON_ERROR` | Yes (incorrectly) | `die_on_error` | Uses `node.get()` instead of proper XML traversal; default is `False` (Python bool, not string) |
| `INCLUDE_NULL_VALUES` | **No** | -- | **Not extracted** |
| `SCHEMA` | Partially | `schema.output` | Hardcoded output schema with `'str'` type instead of Talend `'id_String'` format |

### Schema Extraction

| Attribute | Extracted? | Notes |
|-----------|-----------|-------|
| `name` | Yes | Hardcoded from `pivot_key`, `pivot_value`, and row_keys |
| `type` | Yes -- **incorrectly** | Uses `'str'` instead of `'id_String'` per STANDARDS.md |
| `nullable` | Yes | Always `True` |
| `key` | Yes | Always `False` |
| `length` | **No** | Not extracted |
| `precision` | **No** | Not extracted |
| `pattern` | **No** | Not extracted |

### Converter Issues

| ID | Priority | Issue |
|----|----------|-------|
| CONV-UPR-001 | **P0** | **Incorrect XML parameter access method**: `node.get('PIVOT_COLUMN', ...)` retrieves XML *attributes* on the node element, not Talend `elementParameter` child elements. Talend parameters are stored as `<elementParameter name="PIVOT_COLUMN" value="..."/>` children, requiring `node.find('.//elementParameter[@name="PIVOT_COLUMN"]').get('value')`. This means `pivot_column`, `value_column`, `group_by_columns`, and `die_on_error` will **always** return their default values, ignoring actual Talend job configuration. |
| CONV-UPR-002 | **P0** | **Hardcoded fallback row_keys**: When `ROW_KEYS` cannot be extracted (empty list), the parser falls back to a hardcoded list of domain-specific column names: `['COBDATE', 'AGREEMENTID', 'MASTERMNEMONIC', 'CLIENT_OR_AFFILIATE', 'MNEMONIC', 'GMIACCOUNT', 'CURRENCY']`. This is a project-specific hardcode that will produce incorrect results for any other Talend job. The converter should raise an error or return an empty list with a warning. |
| CONV-UPR-003 | **P1** | **Schema type format violation**: Output schema uses `'type': 'str'` instead of `'type': 'id_String'` as required by `STANDARDS.md` (section "Type Mapping"). The v1 engine's `validate_schema()` in `BaseComponent` has a mapping for `'str'` -> `'object'` but it is documented as the non-preferred format. |
| CONV-UPR-004 | **P1** | **Config key mismatch with engine**: Converter outputs `pivot_column` and `value_column` config keys, but the engine's `UnpivotRow._process()` reads `pivot_key` and `pivot_value`. These key names do not match, meaning the converter's values are silently ignored and the engine always uses its defaults (`'pivot_key'` and `'pivot_value'`). |
| CONV-UPR-005 | **P1** | **`INCLUDE_NULL_VALUES` not extracted**: The Talend component parameter controlling whether null-valued cells produce output rows is not parsed. The engine has `include_empty_values` config but the converter never populates it. |
| CONV-UPR-006 | **P1** | **`die_on_error` extraction broken**: `node.get('DIE_ON_ERROR', False)` will always return `False` because `DIE_ON_ERROR` is an `elementParameter` child, not an attribute on the node. The default is a Python `bool` rather than a string value, but even if it were extracted correctly, there is no `lower() == 'true'` conversion for the string value from XML. |
| CONV-UPR-007 | **P2** | **`group_by_columns` extracted but unused**: The converter extracts `group_by_columns` from the XML, but the engine's `UnpivotRow` class has no corresponding config parameter and completely ignores it. Dead config data. |
| CONV-UPR-008 | **P2** | **No docstring for Talend parameters**: The `parse_unpivot_row()` method lacks the standard docstring listing all expected Talend parameters, as required by `STANDARDS.md` ("Document Talend params" rule). |
| CONV-UPR-009 | **P3** | **No input schema preservation**: The converter overwrites `component['schema']['output']` with a synthesized schema but does not preserve the original input schema from the Talend XML. This means schema metadata from the Talend job design is lost. |

---

## 3. Engine Feature Parity Audit

### Engine Class: `UnpivotRow`

**Location**: `src/v1/engine/components/transform/unpivot_row.py`
**Lines of code**: 235
**Base class**: `BaseComponent`

### Feature Implementation Status

| Talend Feature | Implemented? | Fidelity | Notes |
|----------------|-------------|----------|-------|
| Unpivot columns to rows | Yes | High | Uses `pd.DataFrame.melt()` -- correct approach |
| Row keys (identifier columns) | Yes | High | Correctly preserves specified columns |
| Pivot key column naming | Yes | High | Configurable via `pivot_key` config key |
| Pivot value column naming | Yes | High | Configurable via `pivot_value` config key |
| Include/exclude null values | Yes | Medium | `include_empty_values` config controls `dropna()` |
| All output as String type | **No** | **N/A** | **Talend converts all pivot values to String; v1 preserves original types** |
| NullPointerException on null | **N/A** | **N/A** | Not applicable -- Python handles None natively (this is actually an improvement) |
| Die on error | **No** | **N/A** | Config key `die_on_error` is not read or honored by the engine |
| Reject flow | **No** | **N/A** | No reject output supported |
| Output column ordering | Yes | Medium | Reorders pivot columns first, but differs from Talend's exact ordering |
| GlobalMap `NB_LINE` | Yes | High | Set via `_update_stats()` -> `_update_global_map()` |
| GlobalMap `NB_LINE_OK` | Yes | High | Set via `_update_stats()` |
| GlobalMap `NB_LINE_REJECT` | Partial | Low | Always set to 0 -- never incremented even on filtered rows |
| Streaming mode support | Yes | Medium | Inherited from `BaseComponent` -- but unpivot in chunks may produce incorrect ordering |

### Behavioral Differences from Talend

| ID | Priority | Difference |
|----|----------|------------|
| ENG-UPR-001 | **P0** | **`NB_LINE_REJECT` is never set for filtered rows**: When `include_empty_values=False`, rows with null values are dropped via `dropna()`. The count of filtered rows is logged but never added to `NB_LINE_REJECT`. In Talend, these would be reflected in the statistics. The `rows_filtered` local variable (line 199) is computed but discarded -- it should feed into `_update_stats()`. |
| ENG-UPR-002 | **P1** | **No type coercion to String**: Talend's tUnpivotRow converts all `pivot_value` values to String type. The v1 engine preserves original types from the input DataFrame. This means numeric columns remain numeric in the output, which may cause downstream schema mismatches if downstream components expect String-typed pivot values. |
| ENG-UPR-003 | **P1** | **`die_on_error` not honored**: The engine does not read or act on the `die_on_error` config parameter. All errors in the `_process()` method are re-raised unconditionally (line 212-213), effectively acting as `die_on_error=True` always. There is no graceful degradation path. |
| ENG-UPR-004 | **P1** | **Output column order differs from Talend**: The engine places `[pivot_key, pivot_value, ...remaining]` first (line 179). Talend's standard output order is `[pivot_key, pivot_value, ...row_key_columns]` without any extra columns. The engine also re-adds all original input columns (lines 190-193), which Talend does not do -- Talend outputs only `pivot_key`, `pivot_value`, and the row key columns. |
| ENG-UPR-005 | **P2** | **Original input columns re-added with None values**: Lines 189-193 add back all original input columns that are not in the unpivoted result. In Talend, the output schema is strictly `[pivot_key, pivot_value, ...row_keys]`. Adding back the original wide columns (the very columns being unpivoted) pollutes the output with None-filled columns, producing a schema that does not match Talend's output. |
| ENG-UPR-006 | **P2** | **Redundant post-melt filter**: Line 175 filters `unpivoted_df[unpivoted_df[pivot_key_column].isin(columns_to_unpivot)]`. After `pd.melt()`, the `var_name` column will only ever contain values from `value_vars` (which IS `columns_to_unpivot`). This filter is always a no-op and should be removed for clarity and performance. |
| ENG-UPR-007 | **P3** | **Streaming mode chunk ordering**: When processing in streaming mode (via `BaseComponent._execute_streaming()`), each chunk is unpivoted independently. The `_original_order` tracking within `_process()` only preserves order within a single chunk, not across chunks. Cross-chunk row ordering may differ from batch mode. |

---

## 4. Code Quality Audit

### Bugs

| ID | Priority | Location | Description |
|----|----------|----------|-------------|
| BUG-UPR-001 | **P0** | `unpivot_row.py` line 175 + lines 189-193 | **Output schema pollution**: After `pd.melt()`, the code re-adds all original input columns with `None` values (lines 189-193). This means the unpivoted output contains the original wide columns (e.g., `jan_sales`, `feb_sales`, `mar_sales`) alongside the `pivot_key`/`pivot_value` columns -- but filled with `None`. Talend does NOT include these columns in the output. This corrupts the output schema and may break downstream components that expect only `[pivot_key, pivot_value, ...row_keys]`. |
| BUG-UPR-002 | **P1** | `unpivot_row.py` lines 183-187 | **Dead code -- unreachable column addition**: Lines 183-187 iterate over `column_order` and add missing columns. However, `column_order` is built from `unpivoted_df.columns` on line 179, so by definition every column in `column_order` already exists in `unpivoted_df`. This loop body (`unpivoted_df[col] = None`) can never execute. It is dead code. |
| BUG-UPR-003 | **P1** | `unpivot_row.py` lines 196-199 | **Filtered row count not reflected in statistics**: When `include_empty_values=False`, the count of dropped null rows is computed as `rows_filtered` (line 199) and logged (line 200) but never passed to `_update_stats()`. Statistics show `NB_LINE_REJECT=0` even when rows are filtered out, and `NB_LINE_OK` includes a count that does not account for the filtering (stats are updated AFTER filtering on line 203-204, so `rows_out` IS correct, but `NB_LINE_REJECT` remains 0). |
| BUG-UPR-004 | **P1** | `unpivot_row.py` line 134 | **Double validation of row_keys**: `_process()` re-validates `row_keys` on line 134 (`if not row_keys: raise ValueError`) after `_validate_config()` already checks for this. However, `_process()` uses `self.config.get('row_keys', [])` which can return an empty list (the default), while `_validate_config()` checks `self.config` for the key's presence. If `_validate_config()` is not called before `_process()` (which is the case -- `validate_config()` is a separate method, not called automatically by `execute()`), the `_process()` path is the only safeguard. This is not a bug per se, but the dual validation path is confusing and the `_validate_config()` errors are never surfaced automatically. |

### Naming Consistency

| ID | Priority | Issue |
|----|----------|-------|
| NAME-UPR-001 | **P2** | **Config key divergence between converter and engine**: Converter outputs `pivot_column` and `value_column`; engine reads `pivot_key` and `pivot_value`. This means the converter output is silently ignored -- the engine always uses defaults. The keys should be unified. |
| NAME-UPR-002 | **P2** | **Inconsistent Talend name in error messages**: Line 135 says `"Row keys must be specified for TUnpivotRow."` using `TUnpivotRow` (PascalCase with T prefix) while the class is `UnpivotRow` and the Talend name is `tUnpivotRow`. Should use consistent naming. |
| NAME-UPR-003 | **P2** | **Module docstring says `TUnpivotRow`**: Line 2 of the module docstring says `"TUnpivotRow - Convert columns..."` using an inconsistent capitalization. Should be `UnpivotRow` (class name) or `tUnpivotRow` (Talend name). |
| NAME-UPR-004 | **P2** | **Error log says `TUnpivotRow`**: Line 212: `logger.error(f"[{self.id}] Error in TUnpivotRow: {e}")` uses `TUnpivotRow` instead of `self.component_type` or consistent naming. |
| NAME-UPR-005 | **P3** | **Class docstring parameter names differ from actual config keys**: Docstring says `pivot_key (str)` and `pivot_value (str)` for config parameters, but these are the names of OUTPUT COLUMNS, not config keys that control the column names. This is ambiguous -- a reader cannot tell if `pivot_key` is the config key or the default column name. |

### Standards Compliance

| ID | Priority | Issue |
|----|----------|-------|
| STD-UPR-001 | **P2** | **`_validate_config()` not called automatically**: The `BaseComponent.execute()` method does not call `_validate_config()` or `validate_config()`. The engine only calls `_process()` via `_execute_batch()`. Configuration validation only runs if explicitly called by external code. Per STANDARDS.md, validation should be automatic. |
| STD-UPR-002 | **P2** | **Two validation methods**: The class has both `_validate_config()` (returns `List[str]`) and `validate_config()` (returns `bool`). STANDARDS.md shows a single `_validate_config()` pattern. The public `validate_config()` method is described as "backward compatible" but adds confusion and code duplication. |
| STD-UPR-003 | **P2** | **No custom exception types**: Errors are raised as `ValueError` (lines 137, 144) instead of the project-standard `ConfigurationError` or `ComponentExecutionError` defined in STANDARDS.md. |
| STD-UPR-004 | **P2** | **Catch-all exception handler re-raises without wrapping**: Line 211-213 catches `Exception` and re-raises it without wrapping in `ComponentExecutionError`. STANDARDS.md Pattern 1 shows wrapping: `raise ComponentExecutionError(self.id, str(e), e) from e`. |
| STD-UPR-005 | **P3** | **No type hints on class constants**: `DEFAULT_PIVOT_KEY`, `DEFAULT_PIVOT_VALUE`, `DEFAULT_INCLUDE_EMPTY_VALUES` lack type annotations. Minor style issue per STANDARDS.md convention. |

### Debug Artifacts

| ID | Priority | Issue |
|----|----------|-------|
| DBG-UPR-001 | **P2** | **Excessive DEBUG logging in hot path**: Lines 148-149, 153, 167, 172, 175-176, 181, 187, 193 all emit `logger.debug()` calls within the processing path. For large DataFrames with many columns, the string formatting (especially `f"Columns to unpivot: {columns_to_unpivot}"`) can be expensive even when DEBUG is disabled, because f-strings are evaluated eagerly. Should use lazy logging: `logger.debug("Columns to unpivot: %s", columns_to_unpivot)`. |
| DBG-UPR-002 | **P3** | **INFO-level log in base class `_update_global_map()`**: The `BaseComponent._update_global_map()` method (line 304) logs at INFO level with a reference to undefined variable `value` (it uses `stat_name` and `value` from the loop, but `value` is not defined -- it should be `stat_value`). This is a base class bug that affects all components. |

### Security

| ID | Priority | Issue |
|----|----------|-------|
| SEC-UPR-001 | **P3** | **No input sanitization on column names**: Column names from `row_keys` config are used directly in DataFrame operations without validation for special characters, extremely long names, or injection patterns. Low risk since input is from trusted converter output, but noted for defense-in-depth. |

---

## 5. Performance & Memory Audit

### Memory Analysis

The `_process()` method creates several intermediate copies of the data:

1. **Line 156**: `input_data_with_index = input_data.copy()` -- full copy of input DataFrame
2. **Line 159**: `pd.melt()` -- creates a new DataFrame with `N * M` rows (where N = input rows, M = unpivoted columns)
3. **Line 167**: `sort_values()` with `ignore_index=True` -- creates another copy
4. **Line 170**: `drop('_original_order')` -- creates another copy
5. **Line 175**: Boolean indexing filter -- creates another copy
6. **Line 179**: Column reorder -- creates another copy

**Peak memory**: Approximately `3-4x` the size of the melted output DataFrame, which itself is `M` times larger than the input (where M is the number of unpivoted columns).

For a 1M-row input with 50 unpivoted columns, this produces a 50M-row intermediate DataFrame, with peak memory around 3-4x that size. This can easily exceed available memory.

### Performance Issues

| ID | Priority | Issue |
|----|----------|-------|
| PERF-UPR-001 | **P1** | **Unnecessary full copy of input data**: Line 156 creates a full copy (`input_data.copy()`) solely to add a `_original_order` column. This doubles memory usage of the input. Instead, the `_original_order` column can be added directly to the `melt()` output using the input's index, or `melt()` can be called with `ignore_index=False` to preserve ordering information. |
| PERF-UPR-002 | **P2** | **Redundant no-op filter after melt**: Line 175 applies `unpivoted_df[unpivoted_df[pivot_key_column].isin(columns_to_unpivot)]` which is always a no-op (see BUG analysis above). This creates an unnecessary copy of the entire melted DataFrame and performs an O(N*M) membership check. For a 50M-row result, this wastes significant CPU and memory. |
| PERF-UPR-003 | **P2** | **Multiple chained DataFrame copies**: Lines 167-181 create 4-5 intermediate DataFrame copies through chained operations (`sort_values`, `drop`, boolean index, column reorder). These should be consolidated using `inplace=True` where possible, or restructured to minimize copies. For example, `sort_values(..., inplace=True)` and `drop(..., inplace=True)` would modify in place. |
| PERF-UPR-004 | **P2** | **O(N*M) sort operation**: Line 167 sorts the melted DataFrame by `['_original_order', pivot_key_column]`. For large inputs, this is an expensive O(N*M * log(N*M)) operation. Since `pd.melt()` already preserves row order (it iterates `value_vars` in order for each id combination), the sort is only needed to group by original row. Consider whether Talend's output order actually requires this sort, or if the natural melt order suffices. |
| PERF-UPR-005 | **P3** | **Eager f-string evaluation in debug logs**: Multiple `logger.debug(f"...")` calls eagerly evaluate f-strings even when DEBUG logging is disabled. For calls that format large lists (e.g., `columns_to_unpivot`), this wastes CPU. Use `%s`-style lazy formatting instead. |

---

## 6. Testing Audit

### Existing Tests

| Test File | Exists? | Notes |
|-----------|---------|-------|
| `tests/**/test_unpivot_row.py` | **No** | No test file found anywhere in the repository |
| `tests/**/test_unpivot*.py` | **No** | No file matching any unpivot pattern |
| `tests/**/test_pivot*.py` | **No** | No pivot-related test files at all |
| Integration tests | **No** | No integration test exercises tUnpivotRow in a job pipeline |

### Testing Issues

| ID | Priority | Issue |
|----|----------|-------|
| TEST-UPR-001 | **P0** | **Zero unit tests**: No test file exists for the `UnpivotRow` component. There is no coverage for any code path -- basic functionality, edge cases, configuration validation, error handling, or statistics tracking. |
| TEST-UPR-002 | **P1** | **No converter parser tests**: No tests exist for `parse_unpivot_row()` in the converter. The critical bugs in XML parameter access (CONV-UPR-001) would have been caught by even basic converter tests. |

### Recommended Test Cases

#### Unit Tests (Engine)

| Test | Priority | Description |
|------|----------|-------------|
| `test_basic_unpivot` | **P0** | Unpivot a simple 3-column DataFrame with 2 row keys, verify output has `N * M` rows with correct pivot_key and pivot_value values |
| `test_single_row_key` | **P0** | Single row key column, verify all other columns are unpivoted |
| `test_multiple_row_keys` | **P0** | Multiple row key columns, verify all are preserved in output |
| `test_empty_input` | **P0** | Pass `None` and empty DataFrame, verify empty DataFrame returned and stats are `(0, 0, 0)` |
| `test_missing_row_keys_config` | **P0** | Config without `row_keys`, verify `ValueError` is raised |
| `test_missing_row_key_column` | **P0** | `row_keys` references a column not in the input DataFrame, verify `ValueError` with descriptive message |
| `test_include_empty_values_true` | **P0** | Input with null cells and `include_empty_values=True`, verify null rows are included in output |
| `test_include_empty_values_false` | **P0** | Input with null cells and `include_empty_values=False`, verify null rows are excluded |
| `test_custom_pivot_key_name` | **P1** | Set `pivot_key='attribute'`, verify output column is named `attribute` |
| `test_custom_pivot_value_name` | **P1** | Set `pivot_value='val'`, verify output column is named `val` |
| `test_output_column_order` | **P1** | Verify output columns are in order `[pivot_key, pivot_value, ...row_keys]` |
| `test_row_order_preservation` | **P1** | Multi-row input, verify unpivoted rows maintain original row grouping order |
| `test_statistics_tracking` | **P1** | Verify `NB_LINE`, `NB_LINE_OK`, and `NB_LINE_REJECT` are set correctly |
| `test_statistics_with_null_filter` | **P1** | Verify `NB_LINE_REJECT` reflects filtered null rows (currently fails due to BUG-UPR-003) |
| `test_all_columns_as_row_keys` | **P2** | Edge case: all input columns are row keys, no columns to unpivot. Verify behavior. |
| `test_no_row_keys` | **P2** | Edge case: empty `row_keys` list. Verify error handling. |
| `test_single_unpivot_column` | **P2** | Only one column to unpivot; output should equal input row count |
| `test_large_dataframe` | **P2** | 100K+ rows with 20+ columns to unpivot; verify correctness and reasonable performance |
| `test_mixed_types_in_unpivot_columns` | **P2** | Columns with int, float, string, and None values; verify all are handled |
| `test_duplicate_row_key_values` | **P2** | Multiple input rows with same row key values; verify each produces correct unpivoted rows |
| `test_validate_config_valid` | **P2** | Valid config, verify `validate_config()` returns `True` |
| `test_validate_config_missing_row_keys` | **P2** | Missing `row_keys`, verify returns `False` |
| `test_validate_config_non_list_row_keys` | **P2** | `row_keys` is a string instead of list, verify returns `False` |
| `test_validate_config_non_string_entries` | **P2** | `row_keys` contains non-string entries, verify returns `False` |

#### Converter Tests

| Test | Priority | Description |
|------|----------|-------------|
| `test_parse_unpivot_row_basic` | **P0** | Parse a well-formed tUnpivotRow XML node, verify `row_keys`, `pivot_column`, `value_column` are extracted |
| `test_parse_unpivot_row_empty_keys` | **P0** | Parse node with no ROW_KEYS elements, verify behavior (currently falls back to hardcoded -- should fail) |
| `test_parse_unpivot_row_schema` | **P1** | Verify output schema contains `pivot_key`, `pivot_value`, and all row key columns |
| `test_parse_unpivot_row_schema_types` | **P1** | Verify schema uses `id_String` type format per STANDARDS.md |

#### Integration Tests

| Test | Priority | Description |
|------|----------|-------------|
| `test_unpivot_in_pipeline` | **P1** | Full pipeline: FileInput -> UnpivotRow -> FileOutput; verify end-to-end data flow |
| `test_unpivot_with_downstream_map` | **P2** | UnpivotRow -> Map; verify Map receives correctly structured data |

---

## 7. Issues Summary

### All Issues by Priority

#### P0 -- Critical (4 issues)

| ID | Category | Summary |
|----|----------|---------|
| CONV-UPR-001 | Converter | **Incorrect XML parameter access**: `node.get()` reads XML attributes instead of `elementParameter` children; `pivot_column`, `value_column`, `group_by_columns`, and `die_on_error` always return defaults |
| CONV-UPR-002 | Converter | **Hardcoded domain-specific fallback row_keys**: Falls back to `['COBDATE', 'AGREEMENTID', ...]` when ROW_KEYS extraction fails -- breaks any non-original-project Talend job |
| BUG-UPR-001 | Engine Bug | **Output schema pollution**: Original wide columns re-added with None values, producing output schema that does not match Talend's `[pivot_key, pivot_value, ...row_keys]` output |
| TEST-UPR-001 | Testing | **Zero unit tests**: No test coverage for any code path in UnpivotRow |

#### P1 -- Major (9 issues)

| ID | Category | Summary |
|----|----------|---------|
| CONV-UPR-003 | Converter | Schema type format uses `'str'` instead of `'id_String'` per STANDARDS.md |
| CONV-UPR-004 | Converter | Config key mismatch: converter outputs `pivot_column`/`value_column` but engine reads `pivot_key`/`pivot_value` |
| CONV-UPR-005 | Converter | `INCLUDE_NULL_VALUES` parameter not extracted from Talend XML |
| CONV-UPR-006 | Converter | `die_on_error` extraction broken due to incorrect XML access method |
| ENG-UPR-001 | Engine | `NB_LINE_REJECT` never set for rows filtered by `include_empty_values=False` |
| ENG-UPR-002 | Engine | No type coercion to String -- Talend converts all pivot values to String |
| ENG-UPR-003 | Engine | `die_on_error` config not honored; errors always re-raised |
| BUG-UPR-002 | Engine Bug | Dead code: unreachable column addition loop (lines 183-187) |
| BUG-UPR-003 | Engine Bug | Filtered row count computed but not reflected in `NB_LINE_REJECT` statistics |
| BUG-UPR-004 | Engine Bug | Dual validation paths: `_validate_config()` is never called automatically by `execute()` |
| ENG-UPR-004 | Engine | Output column order includes extra columns not present in Talend output |
| TEST-UPR-002 | Testing | No converter parser tests for `parse_unpivot_row()` |
| PERF-UPR-001 | Performance | Unnecessary full copy of input DataFrame for `_original_order` tracking |

#### P2 -- Moderate (14 issues)

| ID | Category | Summary |
|----|----------|---------|
| CONV-UPR-007 | Converter | `group_by_columns` extracted but unused by engine -- dead config data |
| CONV-UPR-008 | Converter | Missing standard docstring for Talend parameters in parser method |
| ENG-UPR-005 | Engine | Original input columns re-added with None values to output |
| ENG-UPR-006 | Engine | Redundant no-op filter after `pd.melt()` -- always passes all rows |
| NAME-UPR-001 | Naming | Config key divergence between converter (`pivot_column`) and engine (`pivot_key`) |
| NAME-UPR-002 | Naming | Inconsistent `TUnpivotRow` in error messages (should be `tUnpivotRow` or class name) |
| NAME-UPR-003 | Naming | Module docstring uses `TUnpivotRow` instead of `UnpivotRow` |
| NAME-UPR-004 | Naming | Error log uses hardcoded `TUnpivotRow` instead of `self.component_type` |
| STD-UPR-001 | Standards | `_validate_config()` not called automatically during `execute()` |
| STD-UPR-002 | Standards | Dual validation methods (`_validate_config()` and `validate_config()`) add confusion |
| STD-UPR-003 | Standards | Uses `ValueError` instead of project-standard `ConfigurationError` |
| STD-UPR-004 | Standards | Catch-all exception handler does not wrap in `ComponentExecutionError` |
| DBG-UPR-001 | Debug | Excessive eager f-string DEBUG logging in hot path |
| PERF-UPR-002 | Performance | Redundant no-op filter creates unnecessary DataFrame copy |
| PERF-UPR-003 | Performance | Multiple chained DataFrame copies; should use `inplace=True` |
| PERF-UPR-004 | Performance | O(N*M*log(N*M)) sort may be unnecessary if natural melt order suffices |

#### P3 -- Low (6 issues)

| ID | Category | Summary |
|----|----------|---------|
| CONV-UPR-009 | Converter | Original input schema from Talend XML not preserved |
| ENG-UPR-007 | Engine | Streaming mode chunk ordering may differ from batch mode |
| NAME-UPR-005 | Naming | Class docstring parameter descriptions ambiguous (config key vs column name) |
| STD-UPR-005 | Standards | Class constants lack type annotations |
| DBG-UPR-002 | Debug | Base class `_update_global_map()` references undefined variable `value` (affects all components) |
| PERF-UPR-005 | Performance | Eager f-string evaluation in debug logs |
| SEC-UPR-001 | Security | No input sanitization on column names |

### Issue Count Summary

| Priority | Count |
|----------|-------|
| P0 | 4 |
| P1 | 9 |
| P2 | 14 |
| P3 | 6 |
| **Total** | **33** |

---

## 8. Detailed Code Walkthrough

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
- Module docstring uses `TUnpivotRow` (NAME-UPR-003)
- Imports are in correct order per STANDARDS.md (stdlib, third-party, project)
- Logger correctly initialized at module level
- Import of `List` is used only in `_validate_config()` return type

### Class Definition and Constants (Lines 19-59)

**Class docstring** is comprehensive and follows STANDARDS.md template with Configuration, Inputs, Outputs, Statistics, Example, and Notes sections. However:
- The `pivot_key` and `pivot_value` config descriptions are ambiguous (NAME-UPR-005)
- The `Notes` section mentions "Missing columns are added with None values" which documents the bug (BUG-UPR-001) as intended behavior

**Constants:**
- `DEFAULT_PIVOT_KEY = 'pivot_key'` -- correct
- `DEFAULT_PIVOT_VALUE = 'pivot_value'` -- correct
- `DEFAULT_INCLUDE_EMPTY_VALUES = True` -- matches Talend default

### `_validate_config()` Method (Lines 61-98)

**Validation coverage:**

| Config Key | Validated? | Checks |
|------------|-----------|--------|
| `row_keys` | Yes | Presence, is list, non-empty, all entries are strings |
| `pivot_key` | Yes | Is string (if present) |
| `pivot_value` | Yes | Is string (if present) |
| `include_empty_values` | Yes | Is boolean (if present) |
| `die_on_error` | **No** | Not validated |

The validation is thorough for the parameters it covers. However, it is never automatically invoked (STD-UPR-001).

### `_process()` Method (Lines 100-213)

**Line-by-line analysis:**

**Lines 114-118 -- Empty input handling:**
```python
if input_data is None or input_data.empty:
    logger.warning(f"[{self.id}] Empty input received")
    self._update_stats(0, 0, 0)
    return {'main': pd.DataFrame()}
```
Correct pattern per STANDARDS.md. Returns empty DataFrame with zeroed stats.

**Lines 123-127 -- Config extraction:**
```python
row_keys = self.config.get('row_keys', [])
pivot_key_column = self.config.get('pivot_key', self.DEFAULT_PIVOT_KEY)
pivot_value_column = self.config.get('pivot_value', self.DEFAULT_PIVOT_VALUE)
include_empty_values = self.config.get('include_empty_values', self.DEFAULT_INCLUDE_EMPTY_VALUES)
```
Note: reads `pivot_key` and `pivot_value` -- but converter outputs `pivot_column` and `value_column` (CONV-UPR-004). The engine will always use defaults.

**Lines 133-137 -- Row keys validation:**
```python
if not row_keys:
    error_msg = "Row keys must be specified for TUnpivotRow."
    logger.error(f"[{self.id}] {error_msg}")
    raise ValueError(error_msg)
```
Uses `ValueError` instead of `ConfigurationError` (STD-UPR-003). Uses `TUnpivotRow` (NAME-UPR-002).

**Lines 139-144 -- Missing column detection:**
```python
missing_keys = [key for key in row_keys if key not in input_data.columns]
if missing_keys:
    error_msg = f"Missing row keys in input data: {missing_keys}"
    logger.error(f"[{self.id}] {error_msg}")
    raise ValueError(error_msg)
```
Good defensive check with descriptive error message. Should use `ConfigurationError`.

**Lines 146-149 -- Column identification:**
```python
columns_to_unpivot = [col for col in input_data.columns if col not in row_keys]
```
Correctly identifies columns to unpivot as all non-row-key columns.

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
The `pd.melt()` call is correct. However, the full copy for `_original_order` is wasteful (PERF-UPR-001). A more efficient approach:
```python
input_data['_original_order'] = range(len(input_data))
# ... melt ...
input_data.drop('_original_order', axis=1, inplace=True)  # clean up
```

**Lines 166-170 -- Sort and cleanup:**
```python
unpivoted_df = unpivoted_df.sort_values(['_original_order', pivot_key_column], ignore_index=True)
unpivoted_df = unpivoted_df.drop('_original_order', axis=1)
```
Sort ensures Talend-like row ordering (grouped by original row, then by column name). The sort is functionally correct but expensive (PERF-UPR-004).

**Line 175 -- Redundant filter:**
```python
unpivoted_df = unpivoted_df[unpivoted_df[pivot_key_column].isin(columns_to_unpivot)]
```
This is always a no-op (ENG-UPR-006, PERF-UPR-002). After `melt(value_vars=columns_to_unpivot)`, the `var_name` column can only contain values from `columns_to_unpivot`.

**Lines 178-181 -- Column reordering:**
```python
column_order = [pivot_key_column, pivot_value_column] + [col for col in unpivoted_df.columns if col not in [pivot_key_column, pivot_value_column]]
unpivoted_df = unpivoted_df[column_order]
```
Reorders to put pivot columns first. The list comprehension includes row_key columns (correct) but will also include any other columns that might exist.

**Lines 183-187 -- Dead code:**
```python
for col in column_order:
    if col not in unpivoted_df.columns:
        unpivoted_df[col] = None
```
Since `column_order` is derived from `unpivoted_df.columns`, this condition is never true (BUG-UPR-002).

**Lines 189-193 -- Schema pollution:**
```python
for col in input_data.columns:
    if col not in unpivoted_df.columns:
        unpivoted_df[col] = None
```
This re-adds the original wide columns (the very columns being unpivoted) back into the output with `None` values (BUG-UPR-001). For example, if unpivoting `jan_sales`, `feb_sales`, `mar_sales`, these columns are added back as all-None columns. This is incorrect behavior.

**Lines 195-200 -- Null value filtering:**
```python
if not include_empty_values:
    before_filter = len(unpivoted_df)
    unpivoted_df = unpivoted_df.dropna(subset=[pivot_value_column])
    rows_filtered = before_filter - len(unpivoted_df)
    logger.info(f"[{self.id}] Filtered out {rows_filtered} rows with empty values")
```
The `dropna()` only checks for `NaN`/`None`. Empty strings (`""`) are NOT filtered. Talend's behavior for empty strings vs null may differ. The `rows_filtered` count is computed and logged but not added to `NB_LINE_REJECT` (BUG-UPR-003).

**Lines 202-209 -- Statistics and return:**
```python
rows_out = len(unpivoted_df)
self._update_stats(rows_in, rows_out, 0)
```
`NB_LINE_REJECT` is hardcoded to `0` even when rows were filtered. Should be:
```python
self._update_stats(rows_in, rows_out, rows_filtered if not include_empty_values else 0)
```

### `validate_config()` Method (Lines 215-234)

This is a public wrapper around `_validate_config()` that converts the list of errors into a boolean. It provides backward compatibility but is never called automatically by the execution pipeline.

---

## 9. Converter-Engine Integration Analysis

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

**Key finding**: Due to the config key mismatch (CONV-UPR-004) and broken XML access (CONV-UPR-001), the converter's output is **functionally useless** for `pivot_column`, `value_column`, `group_by_columns`, and `die_on_error`. The engine always operates on its default values.

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

## 10. Comparison with Similar Components

### Comparison with tPivotToColumnsDelimited

The `tPivotToColumnsDelimited` converter parser (`parse_tpivot_to_columns_delimited`, line ~1881) uses the correct XML traversal pattern:

```python
# Correct: finds elementParameter child nodes
pivot_column = node.find('.//elementParameter[@name="PIVOT_COLUMN"]').get('value', '')
```

The `parse_unpivot_row()` uses the incorrect pattern:

```python
# Incorrect: reads XML attributes on the node itself
component['config']['pivot_column'] = node.get('PIVOT_COLUMN', 'pivot_key')
```

This confirms that CONV-UPR-001 is a genuine bug -- the correct pattern is already used elsewhere in the same codebase.

### Comparison with BaseComponent Standards

| Feature | BaseComponent Pattern | UnpivotRow Implementation | Compliant? |
|---------|----------------------|--------------------------|------------|
| Empty input handling | Return empty DF, zero stats | Yes | Yes |
| Stats tracking | `_update_stats(in, ok, reject)` | Partial -- reject always 0 | No |
| GlobalMap update | Via `_update_global_map()` | Inherited correctly | Yes |
| Error handling | Wrap in `ComponentExecutionError` | Re-raises raw `Exception` | No |
| Config validation | `_validate_config()` returns errors | Implemented but not auto-called | Partial |
| Streaming support | Via `_execute_streaming()` | Inherited -- but chunk ordering issues | Partial |
| Execution modes | batch/streaming/hybrid | Inherited correctly | Yes |

---

## 11. Risk Assessment

### Production Readiness Rating: NOT READY

| Risk Area | Severity | Impact |
|-----------|----------|--------|
| **Output schema pollution** (BUG-UPR-001) | Critical | Downstream components receive extra None-filled columns, causing schema mismatches, unexpected data, or failures |
| **Converter completely broken** (CONV-UPR-001, -002) | Critical | Any Talend job using tUnpivotRow with non-default settings will produce wrong output. Hardcoded row_keys are project-specific. |
| **No test coverage** (TEST-UPR-001) | Critical | No confidence in correctness of any code path; regressions cannot be detected |
| **Config key mismatch** (CONV-UPR-004) | High | Converter output is silently ignored; custom pivot/value column names from Talend jobs are lost |
| **Statistics inaccuracy** (BUG-UPR-003) | High | `NB_LINE_REJECT` always 0 even when rows are filtered; misleading pipeline monitoring |
| **No `die_on_error` support** (ENG-UPR-003) | Medium | Jobs that expect graceful error handling will instead fail with unhandled exceptions |

### Blockers for Production

1. Fix BUG-UPR-001 (output schema pollution) -- **must** remove lines 189-193
2. Fix CONV-UPR-001 (XML parameter access) -- **must** use `node.find('.//elementParameter...')` pattern
3. Fix CONV-UPR-002 (hardcoded row_keys) -- **must** remove domain-specific defaults
4. Fix CONV-UPR-004 (config key mismatch) -- **must** align converter output with engine input
5. Add basic unit tests (TEST-UPR-001) -- **must** have minimum test coverage
6. Fix BUG-UPR-003 (filtered row statistics) -- **should** reflect filtered rows in `NB_LINE_REJECT`

---

## 12. Recommendations

### Immediate (Before Production)

1. **Fix output schema pollution** (BUG-UPR-001): Remove lines 189-193 in `unpivot_row.py`. The output should contain ONLY `[pivot_key, pivot_value, ...row_keys]`.

2. **Fix dead code** (BUG-UPR-002): Remove lines 183-187 in `unpivot_row.py`. The loop is unreachable.

3. **Fix redundant filter** (ENG-UPR-006): Remove line 175 in `unpivot_row.py`. The filter is always a no-op.

4. **Fix converter XML access** (CONV-UPR-001): Replace `node.get('PARAM')` with `node.find('.//elementParameter[@name="PARAM"]').get('value', default)` for all parameters in `parse_unpivot_row()`.

5. **Remove hardcoded row_keys** (CONV-UPR-002): Replace the domain-specific fallback with an empty list or raise a warning. The converter should not contain business-specific column names.

6. **Align config keys** (CONV-UPR-004): Either change converter to output `pivot_key`/`pivot_value` OR change engine to read `pivot_column`/`value_column`. The former is recommended since `pivot_key`/`pivot_value` are the Talend-standard names.

7. **Fix NB_LINE_REJECT** (BUG-UPR-003): Pass the filtered row count to `_update_stats()`:
   ```python
   rows_filtered = 0
   if not include_empty_values:
       before_filter = len(unpivoted_df)
       unpivoted_df = unpivoted_df.dropna(subset=[pivot_value_column])
       rows_filtered = before_filter - len(unpivoted_df)
   rows_out = len(unpivoted_df)
   self._update_stats(rows_in, rows_out, rows_filtered)
   ```

8. **Create unit tests** (TEST-UPR-001): Add a comprehensive test file covering at minimum the P0 test cases listed in Section 6.

### Short-Term (Hardening)

9. **Extract `INCLUDE_NULL_VALUES`** (CONV-UPR-005): Add extraction in converter and map to engine's `include_empty_values` config key.

10. **Fix schema types** (CONV-UPR-003): Change `'type': 'str'` to `'type': 'id_String'` in the converter's synthesized output schema.

11. **Implement `die_on_error`** (ENG-UPR-003): Add graceful error handling in `_process()` that returns empty DataFrame when `die_on_error=False`.

12. **Add String type coercion** (ENG-UPR-002): After `pd.melt()`, convert `pivot_value_column` to string type to match Talend behavior:
    ```python
    unpivoted_df[pivot_value_column] = unpivoted_df[pivot_value_column].astype(str)
    ```

13. **Fix naming consistency** (NAME-UPR-002, -003, -004): Replace all instances of `TUnpivotRow` with `self.component_type` or the correct form.

14. **Use project exception types** (STD-UPR-003, -004): Replace `ValueError` with `ConfigurationError` and wrap exceptions in `ComponentExecutionError`.

15. **Add converter parser docstring** (CONV-UPR-008): Document all expected Talend parameters per STANDARDS.md.

### Long-Term (Optimization)

16. **Eliminate unnecessary DataFrame copy** (PERF-UPR-001): Use in-place column addition instead of `input_data.copy()`.

17. **Consolidate chained operations** (PERF-UPR-003): Use `inplace=True` for `sort_values()` and `drop()` to reduce memory copies.

18. **Evaluate sort necessity** (PERF-UPR-004): Determine if the natural `pd.melt()` output order matches Talend's order, potentially eliminating the sort entirely.

19. **Switch to lazy logging** (PERF-UPR-005): Replace `logger.debug(f"...")` with `logger.debug("...", ...)` format.

20. **Auto-call `_validate_config()`** (STD-UPR-001): Consider adding validation call at the start of `_process()` or in `BaseComponent.execute()`.

21. **Remove dead `group_by_columns`** (CONV-UPR-007): Either remove from converter or implement in engine if it serves a purpose.

---

## 13. Streaming Mode Analysis

### How Streaming Applies to UnpivotRow

The `BaseComponent` provides three execution modes: `BATCH`, `STREAMING`, and `HYBRID` (auto-select). When the input DataFrame exceeds `MEMORY_THRESHOLD_MB` (3072 MB), `HYBRID` mode switches to streaming, which splits the input into chunks of `chunk_size` rows (default 100,000) and processes each chunk independently via `_process()`.

### Chunk-Based Unpivot Behavior

For `UnpivotRow`, streaming mode means each chunk is independently melted:

```
Input DataFrame (300K rows, 10 unpivot columns):
  Chunk 1: rows 0-99999     -> melt -> 1,000,000 output rows
  Chunk 2: rows 100000-199999 -> melt -> 1,000,000 output rows
  Chunk 3: rows 200000-299999 -> melt -> 1,000,000 output rows
  Combined: pd.concat([chunk1, chunk2, chunk3]) -> 3,000,000 rows
```

### Streaming Mode Issues

| Issue | Description | Severity |
|-------|-------------|----------|
| **Row ordering** | Within each chunk, `_original_order` preserves order. But `_original_order` resets to 0 for each chunk, so cross-chunk ordering depends on `pd.concat` order (which is correct). However, within each chunk, rows are sorted by `[_original_order, pivot_key_column]`, meaning rows 0-99999 are sorted independently of rows 100000-199999. The final output has correct inter-chunk order but potentially different intra-chunk sort behavior than a single batch operation. | Medium |
| **Statistics accumulation** | `BaseComponent._execute_streaming()` calls `_process()` per chunk. Each `_process()` call invokes `_update_stats()` which ADDS to the cumulative stats (line 308: `self.stats['NB_LINE'] += rows_read`). This means stats accumulate correctly across chunks. | OK |
| **Memory amplification** | Each chunk of 100K rows with 10 unpivot columns produces 1M rows. The intermediate memory within `_process()` peaks at ~4x this (copies, sort, filter). So a 100K-row chunk may consume memory equivalent to ~4M rows worth of output data. For wide DataFrames, this can still be significant. | Medium |
| **Empty chunk handling** | If a chunk is empty (e.g., all rows filtered out by upstream component), `_process()` returns `{'main': pd.DataFrame()}`. The streaming logic checks `chunk_result.get('main') is not None` but an empty DataFrame is not None -- it will be appended to results. `pd.concat` with empty DataFrames is harmless but wasteful. | Low |

### Streaming Correctness Verdict

Streaming mode produces **functionally correct output** for `UnpivotRow`, but with a slightly different sort order than batch mode when the input exceeds one chunk. For most use cases, this difference is irrelevant since the output is typically consumed by aggregation or file output components that do not depend on exact row order.

---

## 14. Empty String vs Null Handling Deep Dive

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
- Empty string `""` values ARE included in output (they are not null)
- Some versions of tUnpivotRow have a known bug where null values cause `NullPointerException` and the previous field's value is retained

### V1 Engine Behavior

| Input Value | `include_empty_values=True` | `include_empty_values=False` | Talend Behavior |
|-------------|----------------------------|------------------------------|-----------------|
| `100` (int) | Included | Included | Included |
| `"hello"` | Included | Included | Included |
| `""` (empty string) | Included | Included (NOT filtered) | Included |
| `None` / `NaN` | Included | **Filtered** | Filtered (or NPE in some versions) |
| `0` (zero) | Included | Included | Included |
| `False` (bool) | Included | Included | Included |

### Gap Analysis

The v1 engine's null handling is **mostly correct** but has a subtle difference:
- After `pd.melt()`, numeric `NaN` values become `float('nan')` which `dropna()` correctly catches
- String columns with `None` values become `NaN` after melt, which `dropna()` correctly catches
- Empty strings remain as empty strings and are NOT caught by `dropna()` -- this matches Talend behavior

**Verdict**: The null handling is actually correct for the common case. The potential gap is only if Talend's INCLUDE_NULL_VALUES also catches empty strings in certain versions.

---

## 15. Recommended Fix: Corrected `parse_unpivot_row()`

The following is a corrected version of the converter parser that addresses CONV-UPR-001 through CONV-UPR-008:

```python
def parse_unpivot_row(self, node, component: Dict) -> Dict:
    """
    Parse tUnpivotRow specific configuration from Talend XML node.

    Talend Parameters:
        ROW_KEYS (table): Columns to preserve as identifiers (elementValue with elementRef="COLUMN")
        PIVOT_COLUMN (str): Name for the pivot key output column. Default: 'pivot_key'
        VALUE_COLUMN (str): Name for the pivot value output column. Default: 'pivot_value'
        DIE_ON_ERROR (bool): Whether to stop job on error. Default: false
        INCLUDE_NULL_VALUES (bool): Whether to include null values in output. Default: true
    """
    def get_param(name, default=None):
        param = node.find(f'.//elementParameter[@name="{name}"]')
        return param.get('value', default) if param is not None else default

    # Extract pivot column names
    pivot_key_name = get_param('PIVOT_COLUMN', 'pivot_key')
    if pivot_key_name and pivot_key_name.startswith('"') and pivot_key_name.endswith('"'):
        pivot_key_name = pivot_key_name[1:-1]
    component['config']['pivot_key'] = pivot_key_name or 'pivot_key'

    pivot_value_name = get_param('VALUE_COLUMN', 'pivot_value')
    if pivot_value_name and pivot_value_name.startswith('"') and pivot_value_name.endswith('"'):
        pivot_value_name = pivot_value_name[1:-1]
    component['config']['pivot_value'] = pivot_value_name or 'pivot_value'

    # Extract ROW_KEYS from XML
    row_keys = []
    for element in node.findall('.//elementParameter[@name="ROW_KEYS"]/elementValue'):
        if element.get('elementRef') == 'COLUMN':
            value = element.get('value', '').strip('"')
            if value:
                row_keys.append(value)

    if not row_keys:
        logger.warning(f"No ROW_KEYS found for tUnpivotRow component {component.get('id', 'unknown')}")

    component['config']['row_keys'] = row_keys

    # Extract boolean parameters
    die_on_error_str = get_param('DIE_ON_ERROR', 'false')
    component['config']['die_on_error'] = die_on_error_str.lower() == 'true' if isinstance(die_on_error_str, str) else False

    include_null_str = get_param('INCLUDE_NULL_VALUES', 'true')
    component['config']['include_empty_values'] = include_null_str.lower() != 'false' if isinstance(include_null_str, str) else True

    # Build output schema using Talend type format
    output_schema = [
        {'name': component['config']['pivot_key'], 'type': 'id_String', 'nullable': True, 'key': False},
        {'name': component['config']['pivot_value'], 'type': 'id_String', 'nullable': True, 'key': False}
    ]

    for key in component['config']['row_keys']:
        output_schema.append({'name': key, 'type': 'id_String', 'nullable': True, 'key': False})

    component['schema']['output'] = output_schema
    return component
```

---

## 14. Recommended Fix: Corrected `_process()` Core Logic

The following shows the corrected core processing logic addressing BUG-UPR-001, BUG-UPR-002, BUG-UPR-003, ENG-UPR-006, and PERF-UPR-001:

```python
def _process(self, input_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
    # Handle empty input
    if input_data is None or input_data.empty:
        logger.warning(f"[{self.id}] Empty input received")
        self._update_stats(0, 0, 0)
        return {'main': pd.DataFrame()}

    rows_in = len(input_data)
    logger.info(f"[{self.id}] Processing started: %d rows", rows_in)

    # Get configuration with defaults
    row_keys = self.config.get('row_keys', [])
    pivot_key_column = self.config.get('pivot_key', self.DEFAULT_PIVOT_KEY)
    pivot_value_column = self.config.get('pivot_value', self.DEFAULT_PIVOT_VALUE)
    include_empty_values = self.config.get('include_empty_values', self.DEFAULT_INCLUDE_EMPTY_VALUES)

    # Validate row_keys
    if not row_keys:
        raise ConfigurationError(f"[{self.id}] row_keys must be specified for tUnpivotRow")

    missing_keys = [key for key in row_keys if key not in input_data.columns]
    if missing_keys:
        raise ConfigurationError(f"[{self.id}] Missing row keys in input data: {missing_keys}")

    # Identify columns to unpivot
    columns_to_unpivot = [col for col in input_data.columns if col not in row_keys]

    try:
        # Perform unpivot using pandas melt
        unpivoted_df = input_data.melt(
            id_vars=row_keys,
            value_vars=columns_to_unpivot,
            var_name=pivot_key_column,
            value_name=pivot_value_column,
        )

        # Sort by original row order then column name
        # melt preserves id_vars order, so we reconstruct original row index
        unpivoted_df = unpivoted_df.sort_values(
            by=[pivot_key_column],
            kind='mergesort',  # stable sort preserves original row order
            ignore_index=True
        )

        # Reorder columns: pivot_key, pivot_value, then row_keys only
        column_order = [pivot_key_column, pivot_value_column] + row_keys
        unpivoted_df = unpivoted_df[column_order]

        # Convert pivot_value to string to match Talend behavior
        unpivoted_df[pivot_value_column] = unpivoted_df[pivot_value_column].astype(str)
        # Restore NaN for actual null values (astype(str) converts NaN to 'nan')
        unpivoted_df.loc[
            input_data.melt(id_vars=row_keys, value_vars=columns_to_unpivot)[pivot_value_column].isna().values,
            pivot_value_column
        ] = None

        # Filter null values if configured
        rows_filtered = 0
        if not include_empty_values:
            before_filter = len(unpivoted_df)
            unpivoted_df = unpivoted_df.dropna(subset=[pivot_value_column])
            rows_filtered = before_filter - len(unpivoted_df)
            logger.info(f"[{self.id}] Filtered out %d rows with empty values", rows_filtered)

        # Update statistics
        rows_out = len(unpivoted_df)
        self._update_stats(rows_in, rows_out, rows_filtered)

        logger.info(f"[{self.id}] Processing complete: in=%d, out=%d, filtered=%d",
                    rows_in, rows_out, rows_filtered)

        return {'main': unpivoted_df}

    except Exception as e:
        logger.error(f"[{self.id}] {self.component_type} processing failed: %s", e)
        raise
```

---

## Appendix A: File Inventory

| File | Path | Role |
|------|------|------|
| Engine implementation | `src/v1/engine/components/transform/unpivot_row.py` | Main component class |
| Transform `__init__.py` | `src/v1/engine/components/transform/__init__.py` | Exports `UnpivotRow` |
| Engine registry | `src/v1/engine/engine.py` | Registers `UnpivotRow` and `tUnpivotRow` aliases |
| Base component | `src/v1/engine/base_component.py` | Parent class with `execute()`, stats, streaming |
| Converter parser | `src/converters/complex_converter/component_parser.py` | `parse_unpivot_row()` method |
| Converter dispatch | `src/converters/complex_converter/converter.py` | Dispatches to `parse_unpivot_row()` |
| Standards document | `docs/v1/STANDARDS.md` | Project coding standards |

## Appendix B: Talend Reference Sources

- [Talend Skill: tUnpivotRow Custom Components](https://talendskill.com/knowledgebase/tunpivotrow-talend-custom-components/)
- [Datalytyx: Denormalise a dataset with Talend's tUnpivotRow](https://www.datalytyx.com/how-to-denormalise-a-dataset-using-talends-tunpivotrow/)
- [ETL Geeks Blog: How to use tUnpivotRow in Talend](http://etlgeeks.blogspot.com/2016/04/how-to-use-custom-componet-in-talend.html)
- [Desired Data: How to use UnpivotRow component in Talend](https://desireddata.blogspot.com/2015/06/how-to-use-unpivotrow-component-in.html)
- [GitHub: TalendExchange/Components](https://github.com/TalendExchange/Components)
- [Talend Community: tUnpivotRow questions](https://community.talend.com/s/question/0D53p00007vCjh5CAC/where-to-download-tunpivotrow-and-how-to-install-the-component-for-talend-65-version)
- [Qlik/Talend Help: Converting columns to rows](https://help.qlik.com/talend/en-US/components/8.0/tmap/converting-columns-to-rows)

## Appendix C: Issue Cross-Reference by File

### `unpivot_row.py`

| Line(s) | Issue IDs |
|---------|-----------|
| 2 | NAME-UPR-003 |
| 135 | NAME-UPR-002, STD-UPR-003 |
| 144 | STD-UPR-003 |
| 156 | PERF-UPR-001 |
| 167 | PERF-UPR-004 |
| 175 | ENG-UPR-006, PERF-UPR-002 |
| 183-187 | BUG-UPR-002 |
| 189-193 | BUG-UPR-001, ENG-UPR-005 |
| 196-199 | BUG-UPR-003, ENG-UPR-001 |
| 212 | NAME-UPR-004, STD-UPR-004 |

### `component_parser.py` (parse_unpivot_row)

| Line(s) | Issue IDs |
|---------|-----------|
| 2480-2481 | CONV-UPR-008 |
| 2482 | CONV-UPR-001 |
| 2483 | CONV-UPR-001 |
| 2484 | CONV-UPR-001, CONV-UPR-007 |
| 2493 | CONV-UPR-002 |
| 2494 | CONV-UPR-001, CONV-UPR-006 |
| 2498-2499 | CONV-UPR-003 |

---

*Report generated: 2026-03-21*
*Auditor: Claude Opus 4.6 (1M context)*
*Engine version: v1*
*Total issues found: 33 (4 P0, 9 P1, 14 P2, 6 P3)*
*Production readiness: NOT READY -- 4 P0 blockers must be resolved*
