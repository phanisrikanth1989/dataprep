# Audit Report: tFilterColumns / FilterColumns

> **Audited**: 2026-03-21
> **Auditor**: Claude Opus 4.6 (automated)
> **Engine Version**: v1
> **Converter**: `complex_converter`
> **Status**: PRODUCTION READINESS REVIEW

---

## 1. Component Identity

| Field | Value |
|-------|-------|
| **Talend Name** | `tFilterColumns` |
| **V1 Engine Class** | `FilterColumns` |
| **Engine File** | `src/v1/engine/components/transform/filter_columns.py` (205 lines) |
| **Converter Parser** | `src/converters/complex_converter/component_parser.py` -> `parse_filter_columns()` (lines 786-796) + `_map_component_parameters()` (lines 199-205) |
| **Converter Dispatch** | `src/converters/complex_converter/converter.py` -> dedicated `elif component_type == 'tFilterColumns'` branch (line 238-239) |
| **Registry Aliases** | `FilterColumns`, `tFilterColumns` (registered in `src/v1/engine/engine.py` lines 105-106) |
| **Category** | Transform / Processing |

### Key Files

| File | Purpose |
|------|---------|
| `src/v1/engine/components/transform/filter_columns.py` | Engine implementation (205 lines) |
| `src/converters/complex_converter/component_parser.py` (lines 786-796) | Dedicated `parse_filter_columns()` method extracts columns from FLOW metadata |
| `src/converters/complex_converter/component_parser.py` (lines 199-205) | Generic `_map_component_parameters()` fallback for `tFilterColumns` -- sets `columns`, `mode`, `keep_row_order` |
| `src/converters/complex_converter/converter.py` (lines 238-239) | Dispatch -- dedicated `elif` branch calls `parse_filter_columns()` AFTER generic base parsing |
| `src/v1/engine/base_component.py` | Base class: `_update_stats()`, `_update_global_map()`, `validate_schema()`, `execute()` |
| `src/v1/engine/global_map.py` | GlobalMap storage for `{id}_NB_LINE`, `{id}_NB_COLUMNS_IN`, `{id}_NB_COLUMNS_OUT` |
| `src/v1/engine/exceptions.py` | Custom exception hierarchy (`ComponentExecutionError`, `ConfigurationError`) |
| `src/v1/engine/components/transform/__init__.py` | Package exports (line 29, 58) |

---

## 2. Scorecard

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
|-----------|-------|----|----|----|----|---------|
| Converter Coverage | **Y** | 0 | 2 | 2 | 0 | Only output schema columns extracted; `mode` always defaults to `include`; no `LABEL`/`TSTATCATCHER_STATS` extraction (cosmetic); missing component_mapping entry |
| Engine Feature Parity | **Y** | 1 | 2 | 2 | 1 | Include/exclude modes implemented; column name mapping works; no column reordering based on output schema definition order; no new-column addition with defaults |
| Code Quality | **Y** | 2 | 7 | 3 | 2 | Cross-cutting base class bugs; mutable class default; dead `_validate_config()`; empty DF on empty input loses schema; duplicate column names in config/input cause corruption; invalid mode silently falls through; NB_COLUMNS_IN/OUT not set on early-return paths |
| Performance & Memory | **G** | 0 | 0 | 1 | 1 | `.copy()` on large DFs; streaming mode via base class works |
| Testing | **R** | 1 | 0 | 0 | 0 | Zero v1 unit tests; zero v1 integration tests |

**Overall: YELLOW -- Not production-ready without P0/P1 fixes**

### Score Key
- **R** (Red): Critical gaps blocking production use
- **Y** (Yellow): Significant gaps; usable for subset of jobs with known limitations
- **G** (Green): Production-ready with minor improvements recommended

---

## 3. Talend Feature Baseline

### What tFilterColumns Does

`tFilterColumns` is a Processing-family component that homogenizes schemas by reordering columns, removing unwanted columns, or adding new columns. It operates as an intermediate processor in a data pipeline, mapping input columns to output columns based on column names. The output schema defines which columns are retained and in what order. Any input columns not present in the output schema are dropped. Any output columns not present in the input are added with default/null values.

**Source**: [tFilterColumns Standard Properties (Talend 8.0)](https://help.qlik.com/talend/en-US/components/8.0/processing/tfiltercolumns-standard-properties), [Defining the column filter component (Job Script Reference Guide)](https://help.qlik.com/talend/en-US/job-script-reference-guide/8.0/defining-column-filter-component), [Notes about schema for tFilterColumns](https://help.qlik.com/talend/en-US/job-script-reference-guide/8.0/notes-about-schema-for-tfiltercolumns), [tFilterColumns 6.3](https://help.talend.com/reader/KxVIhxtXBBFymmkkWJ~O4Q/p0KmGBdlshiqi9PLGxX5Ng)

**Component family**: Processing (Integration)
**Available in**: All Talend products (Standard). Also available in MapReduce (deprecated), Spark Batch, Spark Streaming variants.
**Required JARs**: None (schema transformation only, no external dependencies).

### 3.1 Basic Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 1 | Property Type | `PROPERTY_TYPE` | Built-In / Repository | Built-In | Whether config comes from metadata repository or is inline. Not needed at runtime. |
| 2 | Schema | `SCHEMA` | Schema editor | -- | Output schema defining the column structure after filtering. Columns are defined with names, types, lengths, patterns, nullable, and key attributes. The output schema IS the filter specification -- columns present in the output schema are kept; columns absent are removed. |
| 3 | Sync columns | (UI action) | Button | -- | Retrieves schema from the previous component. Clicking "Sync columns" copies the upstream schema and allows the user to remove unwanted columns. |
| 4 | Label | `LABEL` | String | -- | Text label for the component in Talend Studio. No runtime impact. |

### 3.2 Advanced Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 5 | tStatCatcher Statistics | `TSTATCATCHER_STATS` | Boolean (CHECK) | `false` | Capture processing metadata at job and component levels for the tStatCatcher component. Rarely used. |

### 3.3 Connection Types

| Connector | Direction | Type | Description |
|-----------|-----------|------|-------------|
| `FLOW` (Main) | Input | Row > Main | Input data flow from upstream component. Required -- tFilterColumns cannot be a job starter. |
| `FLOW` (Main) | Output | Row > Main | Output data flow with filtered columns matching the output schema. |
| `SUBJOB_OK` | Output (Trigger) | Trigger | Fires when the entire subjob containing this component completes successfully. |
| `SUBJOB_ERROR` | Output (Trigger) | Trigger | Fires when the subjob containing this component fails with an error. |
| `COMPONENT_OK` | Output (Trigger) | Trigger | Fires when this specific component completes execution successfully. |
| `COMPONENT_ERROR` | Output (Trigger) | Trigger | Fires when this specific component fails with an error. |
| `RUN_IF` | Output (Trigger) | Trigger | Conditional trigger with a boolean expression. |

**Note**: tFilterColumns does NOT have a REJECT connection. All data either passes through (matching schema) or is lost (columns not in output schema). Unlike tFilterRow, there is no reject flow for tFilterColumns because it operates on column structure, not row values.

### 3.4 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
|------------------|------|----------|-------------|
| `{id}_NB_LINE` | Integer | After execution | Total number of rows processed (passed through). Since tFilterColumns does not filter rows, this equals the input row count. |
| `{id}_ERROR_MESSAGE` | String | On error | Last error message if an error occurred during execution. Only available when `Die on error` is unchecked (not applicable to this component as it has no die-on-error setting). |

**Note on NB_LINE**: For tFilterColumns, `NB_LINE` is the total row count because the component does not remove or reject any rows -- it only modifies the column structure. All input rows appear in the output with the modified schema.

**Note on column-count variables**: Talend does NOT natively set `{id}_NB_COLUMNS_IN` or `{id}_NB_COLUMNS_OUT` as globalMap variables. These are v1-specific custom statistics (see Section 5).

### 3.5 Behavioral Notes

1. **Schema-driven filtering**: tFilterColumns uses the output schema definition as the filter specification. There is no separate "columns to keep" or "columns to remove" parameter in Talend. The user defines the output schema (via Edit Schema / Sync Columns), and the component maps input columns to output columns by name. This is fundamentally different from how the v1 engine implements it (see Section 5).

2. **Column name matching**: The mapping between input and output columns is based on column names. If an output schema column name matches an input column name, the data flows through. If not, the column is added with null/default values. Column name matching is case-sensitive.

3. **Column reordering**: tFilterColumns can reorder columns. The output follows the order defined in the output schema, regardless of the input column order. If the output schema defines columns as `[city, name, age]` but the input has `[name, age, city]`, the output will follow the output schema order.

4. **Adding new columns**: If the output schema contains a column name that does not exist in the input, tFilterColumns adds it with null/default values based on the column type. This is a column augmentation feature.

5. **Type preservation**: Column types are preserved from the input. If the output schema specifies a different type for a column, implicit type conversion may occur (though this is unusual usage).

6. **Empty input handling**: If the upstream component produces zero rows, tFilterColumns produces zero rows with the output schema structure.

7. **Dynamic schema**: When dynamic schema is enabled, tFilterColumns can pass through all columns from the input without explicitly listing them in the schema.

8. **No REJECT flow**: Unlike tFilterRow, tFilterColumns has no REJECT output. It is a pure schema transformation component.

9. **Performance**: tFilterColumns is a very lightweight component in Talend. It performs no data transformation, only schema mapping. It adds negligible overhead to the job execution.

10. **Schema must match input by column name**: The official documentation states: "make sure that the schema columns you define in the addSchema {} function of this component match those of the input schema, if existing." If column names don't match, the data will be null for those columns.

---

## 4. Converter Audit

### 4.1 Parameter Extraction

The converter uses a **dual-path approach** for tFilterColumns:

**Path 1 -- Generic parameter extraction** (`parse_base_component()`, lines 420-472):
Since `tFilterColumns` is NOT in `components_with_dedicated_parsers` (line 421-425), it goes through the generic `elementParameter` extraction loop. This builds `config_raw` from XML attributes and then calls `_map_component_parameters('tFilterColumns', config_raw)` (line 472).

**Path 2 -- Dedicated parser** (`parse_filter_columns()`, lines 786-796):
After `parse_base_component()` returns, `converter.py` line 238-239 calls `component_parser.parse_filter_columns(node, component)`, which extracts column names from `<metadata connector="FLOW">` and OVERWRITES `component['config']['columns']`.

**Critical observation**: The `_map_component_parameters()` for `tFilterColumns` (lines 199-205) attempts to extract `COLUMNS`, `MODE`, and `KEEP_ROW_ORDER` from `config_raw`. However, Talend XML does NOT have `COLUMNS`, `MODE`, or `KEEP_ROW_ORDER` as `elementParameter` names for tFilterColumns. These parameters do not exist in Talend -- they are v1-specific inventions. The `config_raw.get()` calls will always return the defaults: `columns=[]`, `mode='include'`, `keep_row_order=True`. Then `parse_filter_columns()` overwrites `columns` with actual column names from FLOW metadata. But `mode` remains permanently set to `'include'`.

**Converter flow**:
1. `converter.py:_parse_component()` calls `component_parser.parse_base_component(node)`
2. `parse_base_component()` iterates all `elementParameter` nodes, builds `config_raw` dict
3. Calls `_map_component_parameters('tFilterColumns', config_raw)` -> returns `{columns: [], mode: 'include', keep_row_order: True}`
4. Back in `converter.py`, calls `parse_filter_columns(node, component)`
5. `parse_filter_columns()` extracts column names from `<metadata connector="FLOW">` section
6. Sets `component['config']['columns']` to the extracted column names (overwriting the empty list from step 3)
7. `mode` and `keep_row_order` remain at their defaults from step 3

| # | Talend XML Parameter | Extracted? | V1 Config Key | Converter Line | Notes |
|----|----------------------|------------|---------------|----------------|-------|
| 1 | `SCHEMA` (metadata/column names) | **Yes** | `columns` | 786-796 | Extracted from `<metadata connector="FLOW">/<column name="...">`. This IS the core Talend parameter -- the output schema defines which columns to keep. |
| 2 | `TSTATCATCHER_STATS` | **No** | -- | -- | Not extracted. Low priority -- rarely used. |
| 3 | `LABEL` | **No** | -- | -- | Not extracted. Cosmetic -- no runtime impact. |
| 4 | `PROPERTY_TYPE` | No | -- | -- | Not needed (always Built-In in converted jobs). |

**Summary**: 1 of 4 parameters extracted. However, the 1 extracted parameter (SCHEMA/columns) is the only runtime-relevant parameter, making functional coverage approximately 100% for the include-mode use case.

### 4.2 Schema Extraction

Schema is extracted in the dedicated `parse_filter_columns()` method (lines 786-796).

| Schema Attribute | Extracted? | Notes |
|------------------|-----------|-------|
| `name` | **Yes** | Column name from `column.get('name')` -- this is the primary filter specification |
| `type` | **No** | Column types are NOT extracted by `parse_filter_columns()` |
| `nullable` | **No** | Not extracted by dedicated parser |
| `key` | **No** | Not extracted by dedicated parser |
| `length` | **No** | Not extracted by dedicated parser |
| `precision` | **No** | Not extracted by dedicated parser |
| `pattern` | **No** | Not extracted by dedicated parser |
| `default` | **No** | Column default values not extracted -- prevents new-column addition with defaults |

**Critical gap**: The dedicated `parse_filter_columns()` method extracts ONLY column names. It does not extract column types, nullable flags, defaults, or any other schema attributes. The generic `parse_base_component()` does extract full schema info into `component['schema']` (lines 475-508), but the engine's `_process()` method only uses `component['config']['columns']` (the name list), not the full schema definition. This means column reordering works, column removal works, but column addition with typed defaults does NOT work.

### 4.3 Expression Handling

**Context variable handling**: Not applicable. tFilterColumns has no parameters that accept expressions or context variables. The column list comes from static schema definition.

**Java expression handling**: Not applicable. No string config values that could contain Java expressions.

### 4.4 Converter Issues

| ID | Priority | Issue |
|----|----------|-------|
| CONV-FC-001 | **P1** | **`mode` config key is a v1 invention with no Talend equivalent**: The `_map_component_parameters()` method (line 203) sets `mode` from `config_raw.get('MODE', 'include')`. Talend does NOT have a `MODE` parameter for tFilterColumns. Talend's behavior is always "keep columns defined in the output schema" (equivalent to "include" mode). The `mode='exclude'` option in the v1 engine is a v1 extension that has no Talend origin. While the default `'include'` is functionally correct, this creates confusion because the engine supports a feature (`exclude` mode) that the converter can never produce. |
| CONV-FC-002 | **P1** | **`keep_row_order` config key is a v1 invention with no Talend equivalent**: Same as above -- `config_raw.get('KEEP_ROW_ORDER', True)` (line 204) extracts a non-existent Talend parameter. The engine never uses this value (it is read on line 138 but never referenced in any logic). Dead config path from converter to engine. |
| CONV-FC-003 | **P2** | **Missing `component_mapping` entry for `tFilterColumns`**: The `component_mapping` dictionary (lines 50-103) does NOT contain an entry for `tFilterColumns`. This means `mapped_type` on line 404 falls through to `component_name` itself (`tFilterColumns`). The engine registry (engine.py lines 105-106) registers BOTH `FilterColumns` and `tFilterColumns`, so dispatch works. But the converter outputs `type: 'tFilterColumns'` instead of `type: 'FilterColumns'`, creating inconsistency with other components (e.g., `tFilterRow` maps to `FilterRows`, `tSortRow` maps to `SortRow`). |
| CONV-FC-004 | **P2** | **Output schema column types not extracted by dedicated parser**: `parse_filter_columns()` (lines 786-796) only extracts column names from `<metadata connector="FLOW">`. It does not extract types, nullable flags, or defaults. While the generic `parse_base_component()` does extract full schema into `component['schema']`, the engine's `_process()` only uses `config['columns']` (the name list). New columns added by the output schema with typed defaults cannot be reproduced. |

---

## 5. Engine Feature Parity

### 5.1 Feature Implementation Status

| # | Talend Feature | Implemented? | Fidelity | Engine Location | Notes |
|----|----------------|-------------|----------|-----------------|-------|
| 1 | Remove unwanted columns | **Yes** | High | `_process()` line 149-170 (include mode) | Uses list comprehension to identify columns to keep. Works correctly. |
| 2 | Column name matching | **Yes** | High | `_process()` line 154-155 | `if col in available_columns` -- correct case-sensitive matching. |
| 3 | Missing column warnings | **Yes** | High | `_process()` line 160-161 | Logs warning for columns specified in config but not found in input DataFrame. |
| 4 | Column reordering | **Yes** | High | `_process()` line 170 | `input_data[columns_to_keep].copy()` preserves the order from `columns` config, matching Talend behavior. |
| 5 | Exclude mode (remove specified) | **Yes** | N/A (v1 extension) | `_process()` line 172-183 | V1-specific feature. Talend tFilterColumns does not have an explicit "exclude" mode. |
| 6 | Empty input handling | **Yes** | Medium | `_process()` line 130-133 | Returns empty `pd.DataFrame()` -- see BUG-FC-003 for schema loss issue. |
| 7 | Row passthrough | **Yes** | High | `_process()` line 191 | `_update_stats(total_rows, total_rows, 0)` -- all rows pass through, matching Talend. |
| 8 | Custom column statistics | **Yes** | N/A (v1 extension) | `_process()` lines 194-197 | Stores `NB_COLUMNS_IN` and `NB_COLUMNS_OUT` in globalMap. Not a Talend feature. |
| 9 | Context variable support | **Yes** | High | Via `BaseComponent.execute()` line 202 | `context_manager.resolve_dict()` called before `_process()`. |
| 10 | Java expression support | **Yes** | High | Via `BaseComponent.execute()` line 198 | `_resolve_java_expressions()` resolves `{{java}}` markers (unlikely for this component). |
| 11 | Streaming / hybrid mode | **Yes** | Medium | Via `BaseComponent._execute_streaming()` line 255-278 | Inherited from base class. See Section 7 for limitations. |
| 12 | **Add new columns with defaults** | **No** | N/A | -- | **Talend can add columns not in the input by defining them in the output schema with typed defaults. V1 cannot do this -- only existing columns can be retained.** |
| 13 | **Column type casting** | **No** | N/A | -- | **If output schema defines a different type for a column, Talend may cast. V1 does not perform type casting on passthrough columns.** |
| 14 | `{id}_NB_LINE` globalMap | **Yes** | High | Via `_update_stats()` -> `_update_global_map()` | Set correctly via base class mechanism. |
| 15 | `{id}_ERROR_MESSAGE` globalMap | **No** | N/A | -- | Not implemented. |
| 16 | Dynamic schema | **No** | N/A | -- | No support for dynamic columns passthrough. |

### 5.2 Behavioral Differences from Talend

| ID | Priority | Description |
|----|----------|-------------|
| ENG-FC-001 | **P0** | **Schema-driven vs config-driven filtering**: Talend tFilterColumns operates by defining an output schema -- the schema IS the filter specification. The v1 engine operates by receiving a `columns` list in config and an `include`/`exclude` mode. While the converter bridges this gap (by extracting output schema column names into the `columns` config list), the conceptual model differs. The critical gap is that Talend can ADD columns (present in output schema but absent in input) with typed default values. V1 cannot -- it only selects from existing columns. If an output schema column is missing from input, v1 logs a warning and drops it (line 157-161). Talend would add it with null/default. |
| ENG-FC-002 | **P1** | **No column addition with defaults**: When Talend's output schema defines a column not present in the input, the column is added with null or the column's default value. V1 treats this as a "missing column" warning and excludes it entirely. Jobs that use tFilterColumns to augment the schema (add calculated/default columns) will produce DataFrames with fewer columns than expected. |
| ENG-FC-003 | **P1** | **`{id}_ERROR_MESSAGE` not set in globalMap**: When errors occur, the error message is not stored in globalMap for downstream reference. While tFilterColumns rarely errors, the base class pattern should set this consistently. |
| ENG-FC-004 | **P2** | **`exclude` mode has no Talend equivalent**: The engine supports `mode='exclude'` which inverts the column filter. Since the converter always produces `mode='include'` (the Talend-equivalent behavior), this is not a production issue. However, it creates a maintenance burden and potential confusion -- engineers may write v1 JSON using `exclude` mode expecting it to be convertible from Talend, but no Talend job can produce it. |
| ENG-FC-005 | **P2** | **Empty input returns schemaless DataFrame**: When `input_data` is None or empty (line 130-133), `_process()` returns `pd.DataFrame()` with no columns. Talend would return an empty DataFrame with the output schema columns defined. Downstream components expecting specific columns will fail. |
| ENG-FC-006 | **P3** | **No dynamic schema support**: Talend's dynamic schema feature allows unknown columns to pass through automatically. V1 requires an explicit column list. |

### 5.3 GlobalMap Variable Coverage

| Variable | Talend Sets? | V1 Sets? | How V1 Sets It | Notes |
|----------|-------------|----------|-----------------|-------|
| `{id}_NB_LINE` | Yes | **Yes** | `_update_stats()` -> `_update_global_map()` -> `global_map.put_component_stat()` | Set correctly. Equals input row count since no rows are filtered. |
| `{id}_NB_LINE_OK` | N/A (not standard for this component) | **Yes** | Same mechanism | V1 sets this; Talend does not document it for tFilterColumns. Always equals NB_LINE. |
| `{id}_NB_LINE_REJECT` | N/A (not standard for this component) | **Yes** | Same mechanism | V1 sets this; always 0 since no rows are rejected. Except in edge case where all columns are excluded and stats show `total_rows` as rejected (see BUG-FC-004). |
| `{id}_NB_COLUMNS_IN` | **No** (v1 custom) | **Yes** | `_process()` line 195 | V1-specific custom statistic. Number of input columns. |
| `{id}_NB_COLUMNS_OUT` | **No** (v1 custom) | **Yes** | `_process()` line 196 | V1-specific custom statistic. Number of output columns. |
| `{id}_ERROR_MESSAGE` | Yes (standard) | **No** | -- | Not implemented. |
| `{id}_EXECUTION_TIME` | N/A (v1 only) | **Yes** | Base class `execute()` line 217 | V1-specific, not in Talend. |

---

## 6. Code Quality

### 6.1 Bugs

| ID | Priority | Location | Description |
|----|----------|----------|-------------|
| BUG-FC-001 | **P0** | `src/v1/engine/base_component.py:304` | **`_update_global_map()` references undefined variable `value`**: The log statement on line 304 uses `{stat_name}: {value}` but the variable in the for loop (line 301) is named `stat_value`, not `value`. This causes `NameError` at runtime whenever `global_map` is not None. **CROSS-CUTTING**: This bug affects ALL components, not just FilterColumns, since `_update_global_map()` is called after every component execution (via `execute()` line 218 and line 231). Every successful or failed execution of FilterColumns with a globalMap will crash here. |
| BUG-FC-002 | **P0** | `src/v1/engine/global_map.py:28` | **`GlobalMap.get()` references undefined `default` parameter**: The method signature is `def get(self, key: str) -> Optional[Any]` (line 26), but the body calls `self._map.get(key, default)` (line 28). The `default` parameter is not in the signature, causing `NameError` on every `.get()` call. Additionally, `get_component_stat()` on line 58 calls `self.get(key, default)` with two arguments, but `get()` only accepts one. **CROSS-CUTTING**: Affects all code using `global_map.get()`. While FilterColumns uses `global_map.put()` directly (lines 195-196), which works, any downstream code calling `global_map.get()` to read those values will crash. |
| BUG-FC-003 | **P1** | `src/v1/engine/components/transform/filter_columns.py:130-133` | **Empty input returns schemaless DataFrame**: When `input_data is None or input_data.empty`, the method returns `pd.DataFrame()` with zero columns and zero rows. Downstream components expecting the output schema columns will fail with `KeyError`. Should return `pd.DataFrame(columns=columns)` where `columns` comes from `self.config.get('columns', [])`, preserving the expected output schema structure. |
| BUG-FC-004 | **P1** | `src/v1/engine/components/transform/filter_columns.py:165-166` | **Include mode with no valid columns sets NB_LINE_REJECT = total_rows**: When all specified columns are missing from input (e.g., schema mismatch), `_update_stats(total_rows, 0, total_rows)` marks ALL rows as rejected. But the rows are not malformed -- the column names simply don't match. Talend would produce a DataFrame with the specified columns filled with null/default, not reject all rows. The semantic meaning of "reject" is wrong here. |
| BUG-FC-005 | **P1** | `src/v1/engine/components/transform/filter_columns.py:177-180` | **Exclude mode with all columns excluded sets NB_LINE_REJECT = total_rows**: Same issue as BUG-FC-004. When all columns are excluded, `_update_stats(total_rows, 0, total_rows)` marks all rows as rejected. But the intent is to produce zero-column rows, not to reject data. Stats are semantically incorrect. |
| BUG-FC-006 | **P1** | `src/v1/engine/components/transform/filter_columns.py:71` | **Mutable class-level default `DEFAULT_COLUMNS = []`**: Class attribute `DEFAULT_COLUMNS` is a mutable list. While the current code uses `self.config.get('columns', self.DEFAULT_COLUMNS)` which returns the same list object for all instances, no code mutates `DEFAULT_COLUMNS` directly. However, if any code ever does `columns = self.DEFAULT_COLUMNS; columns.append(...)`, it would corrupt ALL instances. This is a Python anti-pattern. Should be `DEFAULT_COLUMNS = None` with `self.config.get('columns', [])` (fresh list each time) or a tuple `DEFAULT_COLUMNS = ()`. |
| BUG-FC-007 | **P2** | `src/v1/engine/components/transform/filter_columns.py:75-108` | **`_validate_config()` is never called**: The method contains 33 lines of validation logic (mode validation, columns type checking, keep_row_order type checking) but is never invoked by `__init__()`, `execute()`, or `_process()`. The base class `BaseComponent` does not call it either. All validation is dead code. Invalid configurations (e.g., `mode='invalid'`, `columns=123`) are not caught until they cause runtime errors in `_process()`. |
| BUG-FC-008 | **P1** | `src/v1/engine/components/transform/filter_columns.py:154-156, 170` | **Duplicate column names in config produce duplicated columns in output**: No deduplication is performed on the `columns` config list. `input_data[['name', 'age', 'name']].copy()` produces a DataFrame with the `'name'` column duplicated. Downstream components that assume unique column names will break on duplicate columns. |
| BUG-FC-009 | **P1** | `src/v1/engine/components/transform/filter_columns.py:172` | **Invalid mode values silently fall into exclude path**: The `else` branch at line 172 catches ALL non-`'include'` modes including typos like `'exlude'`. Should be `elif mode == 'exclude'` with an explicit error for unknown modes. |
| BUG-FC-010 | **P1** | `src/v1/engine/components/transform/filter_columns.py:133, 166, 180` | **NB_COLUMNS_IN/NB_COLUMNS_OUT never set on early-return paths**: Three code paths return before reaching `globalMap.put()` at lines 195-196: the empty-input early return (line 133), the include-mode no-valid-columns path (line 166), and the exclude-mode all-columns-excluded path (line 180). GlobalMap column count variables are left unset on these paths. |
| BUG-FC-011 | **P1** | `src/v1/engine/components/transform/filter_columns.py` | **Duplicate column names in INPUT DataFrame cause silent data corruption**: If the input DataFrame has duplicate column names, `input_data[columns_to_keep]` selects ALL columns with matching names, producing unexpected multi-column output and silent data corruption. |

### 6.2 Naming Consistency

| ID | Priority | Issue |
|----|----------|-------|
| NAME-FC-001 | **P2** | **`mode` and `keep_row_order` have no Talend equivalents**: These config keys are v1 inventions. Talend tFilterColumns has no `MODE` or `KEEP_ROW_ORDER` parameters. The converter's `_map_component_parameters()` (lines 199-205) creates these from non-existent XML parameters, always getting defaults. This creates the illusion of Talend parameter mapping where none exists. |
| NAME-FC-002 | **P3** | **Missing `component_mapping` entry**: The `component_mapping` dict in `component_parser.py` (lines 50-103) does not map `tFilterColumns` to `FilterColumns`. The component type in converted JSON is `tFilterColumns` instead of `FilterColumns`. Other transform components ARE mapped (e.g., `tFilterRow` -> `FilterRows`, `tSortRow` -> `SortRow`). |

### 6.3 Standards Compliance

| ID | Priority | Standard | Violation |
|----|----------|----------|-----------|
| STD-FC-001 | **P2** | "`_validate_config()` returns `List[str]`" (METHODOLOGY.md) | Method exists but is never called. Contract is technically met but functionally useless. Dead code. |
| STD-FC-002 | **P2** | "Every component parameter must trace to a Talend parameter" | `mode` and `keep_row_order` config keys have no Talend equivalent. They are v1 extensions that should be documented as such. |
| STD-FC-003 | **P3** | "No mutable class-level defaults" | `DEFAULT_COLUMNS = []` is a mutable list at class level. Should use `None` or tuple. |

### 6.4 Debug Artifacts

| ID | Priority | Issue |
|----|----------|-------|
| DBG-FC-001 | **P3** | **No debug artifacts in filter_columns.py**: Clean code -- no print statements, no TODO comments, no commented-out code. Good. |

### 6.5 Security

| ID | Priority | Issue |
|----|----------|-------|
| SEC-FC-001 | **P3** | **No security concerns**: FilterColumns operates on in-memory DataFrames only. No file I/O, no external connections, no expression evaluation. No attack surface. |

### 6.6 Logging Quality

The component has good logging quality, following STANDARDS.md patterns:

| Aspect | Assessment |
|--------|------------|
| Logger setup | Module-level `logger = logging.getLogger(__name__)` -- correct |
| Component ID prefix | All log messages use `[{self.id}]` prefix -- correct |
| Level usage | INFO for start/complete milestones, DEBUG for config/column details, WARNING for missing columns and empty input -- correct |
| Start/complete logging | `_process()` logs start (line 141) and completion (lines 186-188, 199) -- correct |
| Sensitive data | No sensitive data logged -- correct |
| No print statements | No `print()` calls -- correct |

### 6.7 Error Handling Quality

| Aspect | Assessment |
|--------|------------|
| Custom exceptions | Uses `ComponentExecutionError` from `exceptions.py` -- correct |
| Exception chaining | Uses `raise ComponentExecutionError(self.id, error_msg, e) from e` (line 205) -- correct |
| General try/except | Wraps entire processing logic in try/except (lines 144-205). Catches `Exception` -- correct, not too broad for a component processor. |
| No bare `except` | All except clauses specify `Exception` -- correct |
| Error messages | Include component ID and error details -- correct |
| Graceful degradation | Empty input returns empty DataFrame (not an error) -- correct design choice |

### 6.8 Type Hints

| Aspect | Assessment |
|--------|------------|
| Method signatures | `_validate_config() -> List[str]`, `_process(...) -> Dict[str, Any]` -- correct |
| Parameter types | `input_data: Optional[pd.DataFrame] = None` -- correct |
| Return types | `Dict[str, Any]` for `_process()`, `List[str]` for `_validate_config()` -- correct |
| Imports | `from typing import Any, Dict, List, Optional` -- all used, correct |

### 6.9 Thread Safety

| Aspect | Assessment |
|--------|------------|
| Shared mutable state | `DEFAULT_COLUMNS = []` is a mutable class-level list shared across all instances. If ever mutated, it affects all instances. Not currently mutated, but a latent risk. See BUG-FC-006. |
| Instance state | `self.config`, `self.stats`, `self.global_map` are instance-level. Safe for single-threaded execution. |
| GlobalMap thread safety | `GlobalMap` uses a plain dict with no locking. Concurrent writes from multiple components would cause race conditions. Not an issue in current single-threaded v1 engine, but would be if parallelism is added. |

### 6.10 validate_schema() Nullable Logic

The base class `validate_schema()` method (base_component.py lines 314-359) has an **inverted nullable condition** on line 351:

```python
if pandas_type == 'int64' and col_def.get('nullable', True):
    df[col_name] = df[col_name].fillna(0).astype('int64')
```

This reads: "if the column IS nullable, fill NaN with 0 and cast to non-nullable int64." The logic is inverted -- nullable columns should KEEP their NaN values (use nullable `Int64`), and non-nullable columns should fill NaN with 0. The condition should be `not col_def.get('nullable', True)` or the entire approach should use `Int64` (nullable) for nullable columns and `int64` (non-nullable) with `fillna(0)` for non-nullable columns.

**Impact on FilterColumns**: FilterColumns does NOT call `validate_schema()` directly in its `_process()` method. However, if downstream components or the engine pipeline calls `validate_schema()` on the FilterColumns output, this inverted condition would silently convert NaN to 0 in nullable integer columns, losing null information.

---

## 7. Performance & Memory

| ID | Priority | Issue |
|----|----------|-------|
| PERF-FC-001 | **P2** | **`.copy()` on potentially large DataFrames**: Lines 170 and 183 both call `input_data[columns_to_keep].copy()`. While `.copy()` is good practice to avoid SettingWithCopyWarning, for very large DataFrames (millions of rows, hundreds of columns) this doubles memory usage temporarily. For a passthrough transform component, a view might be acceptable if the caller guarantees no modification. However, `.copy()` is the safer default and matches pandas best practices. Minor optimization opportunity. |
| PERF-FC-002 | **P3** | **`list(input_data.columns)` creates unnecessary list**: Line 146 `available_columns = list(input_data.columns)` converts the pandas Index to a Python list. The subsequent `col in available_columns` checks (lines 155, 174, 175) would be O(n) per check on a list. Using `set(input_data.columns)` would make lookups O(1). For DataFrames with hundreds of columns, this is a minor optimization. |

### 7.1 Memory Management Assessment

| Aspect | Assessment |
|--------|------------|
| Streaming mode | Inherited from `BaseComponent._execute_streaming()` (lines 255-278). Works correctly for FilterColumns -- each chunk is filtered independently. Column filtering is stateless, so chunked processing is safe. |
| Memory threshold | `MEMORY_THRESHOLD_MB = 3072` (3GB) inherited from `BaseComponent`. Reasonable default for DataFrames. |
| Chunked processing | Via base class. FilterColumns processes each chunk identically. Results concatenated with `pd.concat(results, ignore_index=True)` (line 275). Correct behavior. |
| Copy overhead | `.copy()` on lines 170, 183 creates full copy of selected columns. For a 1GB DataFrame selecting 50% of columns, this uses 500MB additional memory temporarily. Acceptable for batch mode. |

### 7.2 Streaming Mode Behavior via Base Class

FilterColumns inherits HYBRID streaming mode from BaseComponent:

1. `execute()` calls `_auto_select_mode(input_data)` (line 206)
2. If input DataFrame memory > 3072 MB, switches to STREAMING
3. `_execute_streaming()` chunks the DataFrame and calls `_process()` per chunk
4. Each chunk is filtered independently (correct for column operations)
5. Results concatenated

**Potential issue**: When streaming mode is active, `_process()` is called per chunk. Each call executes `_update_stats(total_rows, total_rows, 0)` (line 191) which ACCUMULATES stats (`+=`). This is correct -- stats accumulate across chunks. However, `global_map.put(NB_COLUMNS_IN/OUT)` (lines 195-196) is called per chunk and OVERWRITES (not accumulates) the column counts. Since column counts are the same for every chunk, the final value is correct. No bug here.

**Edge case**: If streaming mode activates and the first chunk is empty (possible if input has very few rows and chunking creates empty trailing chunks), the empty-input early return (line 130-133) would fire, returning a schemaless DataFrame and setting stats to (0, 0, 0). Subsequent chunks would accumulate on top of this. The final stats would be correct (empty chunks contribute 0), but any intermediate globalMap column count writes from non-empty chunks would be correct.

---

## 8. Testing

### 8.1 Current Coverage

| Test Type | Exists? | File | Notes |
|-----------|---------|------|-------|
| V1 engine unit tests | **No** | -- | Zero test files found for `FilterColumns` v1 engine component |
| V1 engine integration tests | **No** | -- | No v1 engine integration tests found |
| Converter mapper tests | **Yes** | `tests/converters/v1_to_v2/test_component_mapper.py` (line 434) | Tests the component mapper for FilterColumns, NOT the v1 engine itself |

**Key finding**: The v1 engine has ZERO tests for this component. All 205 lines of v1 engine code are completely unverified. The only existing test is for the converter mapper (`TestFilterColumns` class at line 434), which verifies JSON translation, not v1 engine behavior.

### 8.2 Recommended Test Cases

#### P0 -- Must Have Before Production

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 1 | Basic include mode | P0 | DataFrame with 5 columns, include 3 -- verify only 3 columns in output, all rows preserved |
| 2 | Column reordering | P0 | Include columns in different order than input -- verify output follows config order |
| 3 | Missing columns in include | P0 | Include list has columns not in input -- verify warning logged, existing columns kept, missing columns excluded |
| 4 | Empty input DataFrame | P0 | Pass empty DataFrame -- verify empty output returned, stats (0, 0, 0) |
| 5 | None input | P0 | Pass None -- verify empty output returned, stats (0, 0, 0) |
| 6 | Statistics tracking | P0 | Verify `NB_LINE`, `NB_LINE_OK`, `NB_LINE_REJECT` are set correctly after execution (all rows pass through) |
| 7 | GlobalMap integration | P0 | Verify `{id}_NB_LINE`, `{id}_NB_COLUMNS_IN`, `{id}_NB_COLUMNS_OUT` are set in globalMap |

#### P1 -- Important

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 8 | Exclude mode basic | P1 | DataFrame with 5 columns, exclude 2 -- verify 3 columns remain |
| 9 | All columns excluded | P1 | Exclude all columns -- verify empty DataFrame returned, stats semantics |
| 10 | All columns included | P1 | Include all columns -- verify output matches input exactly |
| 11 | Duplicate column names in config | P1 | `columns: ["name", "name"]` -- verify no duplicated columns in output |
| 12 | Case-sensitive column names | P1 | Input has `Name` but config specifies `name` -- verify case sensitivity |
| 13 | Empty columns list | P1 | `columns: []` with include mode -- verify behavior (currently returns empty DF with all rows "rejected") |
| 14 | NaN values in filtered columns | P1 | DataFrame with NaN values -- verify NaN preserved through column filtering |
| 15 | Mixed dtypes preservation | P1 | Verify int, float, string, datetime column types are preserved through filtering |
| 16 | Single column DataFrame | P1 | Input has 1 column, include it -- verify single-column output works |

#### P2 -- Hardening

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 17 | Large DataFrame streaming | P2 | Verify hybrid mode activates streaming for DataFrame > memory threshold |
| 18 | Empty string column names | P2 | Column named `""` -- verify no crash |
| 19 | Special characters in column names | P2 | Column names with spaces, dots, brackets -- verify correct filtering |
| 20 | Concurrent FilterColumns instances | P2 | Two FilterColumns instances running -- verify no DEFAULT_COLUMNS contamination |
| 21 | Config with invalid mode | P2 | `mode: "invalid"` -- verify graceful error since `_validate_config()` is dead code |
| 22 | Config with non-list columns | P2 | `columns: "name"` (string instead of list) -- verify error handling |
| 23 | DataFrame with MultiIndex columns | P2 | Verify behavior with hierarchical column index |
| 24 | Empty string values vs NaN | P2 | Verify empty strings are preserved (not converted to NaN) through filtering |

---

## 9. Issues Summary

### P0 -- Critical

| ID | Category | Summary |
|----|----------|---------|
| BUG-FC-001 | Bug (Cross-Cutting) | `_update_global_map()` in `base_component.py:304` references undefined variable `value` (should be `stat_value`). Will crash ALL components when `global_map` is set. |
| BUG-FC-002 | Bug (Cross-Cutting) | `GlobalMap.get()` in `global_map.py:28` references undefined parameter `default`. Will crash on any `global_map.get()` call. `get_component_stat()` also passes two args to single-arg `get()`. |
| TEST-FC-001 | Testing | Zero v1 unit tests for the FilterColumns engine component. All 205 lines of v1 engine code are unverified. |

### P1 -- Major

| ID | Category | Summary |
|----|----------|---------|
| CONV-FC-001 | Converter | `mode` config key is a v1 invention with no Talend equivalent. `_map_component_parameters()` extracts non-existent `MODE` from XML, always getting `'include'` default. Creates confusion about Talend parity. |
| CONV-FC-002 | Converter | `keep_row_order` config key is a v1 invention with no Talend equivalent. Dead config path -- engine reads it (line 138) but never uses it. |
| ENG-FC-001 | Engine | **Schema-driven vs config-driven model mismatch**: Talend uses the output schema as the filter specification and can ADD columns. V1 uses a columns list and can only SELECT from existing columns. Column addition with typed defaults is not supported. |
| ENG-FC-002 | Engine | No column addition with defaults. Talend output schema columns not in input are added with null/defaults. V1 logs warning and drops them. |
| ENG-FC-003 | Engine | `{id}_ERROR_MESSAGE` not set in globalMap. |
| BUG-FC-003 | Bug | Empty input returns schemaless `pd.DataFrame()` -- downstream components expecting schema columns will fail. |
| BUG-FC-004 | Bug | Include mode with no valid columns marks all rows as rejected. Semantic misuse of NB_LINE_REJECT -- schema mismatch is not a row rejection. |
| BUG-FC-005 | Bug | Exclude mode with all columns excluded marks all rows as rejected. Same semantic issue as BUG-FC-004. |
| BUG-FC-006 | Bug | Mutable class-level `DEFAULT_COLUMNS = []`. Not currently mutated but a latent corruption risk if any code ever appends to it. Python anti-pattern. |
| BUG-FC-007 | Bug | `_validate_config()` is dead code -- never called. 33 lines of unreachable validation. Invalid configs not caught until runtime errors in `_process()`. |
| BUG-FC-008 | Bug | Duplicate column names in config produce duplicated columns in output (lines 154-156, 170). No deduplication. `input_data[['name', 'age', 'name']].copy()` produces DataFrame with `'name'` duplicated. Downstream components break on duplicate columns. |
| BUG-FC-009 | Bug | Invalid mode values silently fall into exclude path. `else` branch at line 172 catches ALL non-`'include'` modes including typos like `'exlude'`. Should be `elif mode == 'exclude'` with explicit error for unknown modes. |
| BUG-FC-010 | Bug | NB_COLUMNS_IN/NB_COLUMNS_OUT never set on early-return paths (lines 133, 166, 180). Three paths return before reaching `globalMap.put()` at lines 195-196. |
| BUG-FC-011 | Bug | Duplicate column names in INPUT DataFrame cause silent data corruption. `input_data[columns_to_keep]` selects ALL columns with matching names. |

### P2 -- Moderate

| ID | Category | Summary |
|----|----------|---------|
| CONV-FC-003 | Converter | Missing `component_mapping` entry for `tFilterColumns`. Converter outputs `type: 'tFilterColumns'` instead of `type: 'FilterColumns'`. Inconsistent with other transform components. |
| CONV-FC-004 | Converter | Output schema column types not extracted by dedicated parser. Only column names extracted. Prevents new-column addition with typed defaults. |
| ENG-FC-004 | Engine | `exclude` mode has no Talend equivalent. V1 extension creates maintenance burden and confusion. |
| ENG-FC-005 | Engine | Empty input returns schemaless DataFrame. Should preserve output column structure. |
| STD-FC-001 | Standards | `_validate_config()` exists but never called. Dead validation code. |
| STD-FC-002 | Standards | `mode` and `keep_row_order` config keys have no Talend equivalent. Should be documented as v1 extensions. |
| PERF-FC-001 | Performance | `.copy()` on potentially large DataFrames doubles memory temporarily. |
| NAME-FC-001 | Naming | `mode` and `keep_row_order` have no Talend equivalents. Config keys create illusion of Talend parameter mapping. |

### P3 -- Low

| ID | Category | Summary |
|----|----------|---------|
| ENG-FC-006 | Engine | No dynamic schema support. |
| STD-FC-003 | Standards | Mutable class-level `DEFAULT_COLUMNS = []`. Should use `None` or tuple. |
| NAME-FC-002 | Naming | Missing `component_mapping` entry makes type inconsistent (`tFilterColumns` instead of `FilterColumns`). |
| SEC-FC-001 | Security | No security concerns. Component operates on in-memory data only. |
| PERF-FC-002 | Performance | `list(input_data.columns)` could be `set()` for O(1) lookups. Minor for typical column counts. |
| DBG-FC-001 | Debug | No debug artifacts. Clean code. |

### Issue Count Summary

| Priority | Count | Categories |
|----------|-------|------------|
| P0 | 3 | 2 bugs (cross-cutting), 1 testing |
| P1 | 14 | 2 converter, 3 engine, 9 bugs |
| P2 | 8 | 2 converter, 2 engine, 1 standards, 1 naming, 1 performance, 1 standards |
| P3 | 6 | 1 engine, 1 standards, 1 naming, 1 security, 1 performance, 1 debug |
| **Total** | **31** | |

---

## 10. Recommendations

### Immediate (Before Production)

1. **Fix `_update_global_map()` bug** (BUG-FC-001): Change `value` to `stat_value` on `base_component.py` line 304. Better yet, remove the stale `{stat_name}: {value}` reference entirely and log just the three main stats. **Impact**: Fixes ALL components (cross-cutting). **Risk**: Very low (log message only).

2. **Fix `GlobalMap.get()` bug** (BUG-FC-002): Add `default: Any = None` parameter to the `get()` method signature in `global_map.py` line 26. This fixes both direct calls and the two-argument call from `get_component_stat()` on line 58. **Impact**: Fixes ALL components and any code using `global_map.get()`. **Risk**: Very low (adds optional parameter with backward-compatible default).

3. **Create unit test suite** (TEST-FC-001): Implement at minimum the 7 P0 test cases listed in Section 8.2. These cover: basic include mode, column reordering, missing columns, empty input, None input, statistics tracking, and globalMap integration. Without these, no v1 engine behavior is verified.

4. **Fix empty input to preserve schema** (BUG-FC-003): Change lines 130-133 from:
   ```python
   return {'main': pd.DataFrame()}
   ```
   to:
   ```python
   columns = self.config.get('columns', [])
   return {'main': pd.DataFrame(columns=columns)}
   ```
   This preserves the output schema structure for downstream components.

### Short-Term (Hardening)

5. **Fix NB_LINE_REJECT semantics** (BUG-FC-004, BUG-FC-005): When no valid columns remain (include mode) or all columns are excluded (exclude mode), use `_update_stats(total_rows, total_rows, 0)` instead of `_update_stats(total_rows, 0, total_rows)`. The rows are not rejected -- the column structure is empty. All rows technically passed through; they just have zero columns. Alternatively, log a WARNING-level message explaining the situation.

6. **Fix mutable class default** (BUG-FC-006): Change `DEFAULT_COLUMNS = []` to `DEFAULT_COLUMNS = None` on line 71. Update line 137 to: `columns = self.config.get('columns') or []` or `columns = self.config.get('columns', self.DEFAULT_COLUMNS) if self.DEFAULT_COLUMNS is not None else []`.

7. **Wire up `_validate_config()`** (BUG-FC-007): Add a call to `_validate_config()` at the beginning of `_process()`, checking the returned error list and raising `ConfigurationError` if errors found. Alternatively, add validation as a standard lifecycle step in `BaseComponent.execute()`.

8. **Implement column addition with defaults** (ENG-FC-001, ENG-FC-002): When a column in the `columns` config list is not found in the input DataFrame, instead of logging a warning and skipping it, add the column to the result DataFrame with `NaN` (or typed default if output schema provides defaults). This matches Talend's behavior where the output schema can augment the input schema.

9. **Add `component_mapping` entry** (CONV-FC-003): Add `'tFilterColumns': 'FilterColumns'` to the `component_mapping` dictionary in `component_parser.py` (around line 58). This ensures consistent type naming across all transform components.

10. **Set `{id}_ERROR_MESSAGE` in globalMap** (ENG-FC-003): In the except block of `_process()` (line 202-205), add: `if self.global_map: self.global_map.put(f"{self.id}_ERROR_MESSAGE", str(e))`.

### Long-Term (Optimization)

11. **Remove `_map_component_parameters()` path for tFilterColumns** (CONV-FC-001, CONV-FC-002): Add `tFilterColumns` to the `components_with_dedicated_parsers` list (line 421-425) in `parse_base_component()`. This prevents the generic extraction from setting phantom `mode` and `keep_row_order` config keys. The dedicated `parse_filter_columns()` should set `mode: 'include'` explicitly (since Talend behavior is always include-mode).

12. **Extract full schema in `parse_filter_columns()`** (CONV-FC-004): Extend the dedicated parser to extract column types, nullable flags, and defaults from the `<metadata connector="FLOW">` section. This enables column addition with typed defaults.

13. **Document `exclude` mode as v1 extension** (ENG-FC-004): Add documentation noting that `exclude` mode is a v1 extension not available in Talend. Converter will never produce it, but it can be used in hand-crafted v1 JSON.

14. **Optimize column lookup** (PERF-FC-002): Change `available_columns = list(input_data.columns)` to `available_columns_set = set(input_data.columns)` and use the set for `col in available_columns_set` lookups. Keep the list for order preservation where needed.

15. **Add dynamic schema support** (ENG-FC-006): Implement a `pass_all_columns: true` config option that forwards all input columns to output without filtering. Low priority -- only needed for Talend's dynamic schema feature.

---

## Appendix A: Converter Parameter Mapping Code

### Generic Mapper (`_map_component_parameters`, lines 199-205)

```python
# FilterColumns mapping
elif component_type == 'tFilterColumns':
    return {
        'columns': config_raw.get('COLUMNS', []),
        'mode': config_raw.get('MODE', 'include'),
        'keep_row_order': config_raw.get('KEEP_ROW_ORDER', True)
    }
```

**Notes on this code**:
- Line 202: `config_raw.get('COLUMNS', [])` -- Talend does NOT have a `COLUMNS` elementParameter. This will ALWAYS return `[]`. The actual columns are extracted by `parse_filter_columns()` afterwards, which overwrites this value.
- Line 203: `config_raw.get('MODE', 'include')` -- Talend does NOT have a `MODE` elementParameter. This will ALWAYS return `'include'`. No code ever sets it to `'exclude'` from Talend XML.
- Line 204: `config_raw.get('KEEP_ROW_ORDER', True)` -- Talend does NOT have a `KEEP_ROW_ORDER` elementParameter. This will ALWAYS return `True`. The engine reads this value on line 138 of `filter_columns.py` but never uses it in any logic.

### Dedicated Parser (`parse_filter_columns`, lines 786-796)

```python
def parse_filter_columns(self, node, component: Dict) -> Dict:
    """Parse tFilterColumns specific configuration"""
    columns = []
    # FIX: Extract columns from <metadata connector="FLOW"> section, not <elementParameter name="SCHEMA">
    for metadata in node.findall('.//metadata[@connector="FLOW"]'):
        for column in metadata.findall('./column'):
            col_name = column.get('name', '')
            if col_name:
                columns.append(col_name)
    component['config']['columns'] = columns
    return component
```

**Notes on this code**:
- The FIX comment on line 789 suggests this was a bug fix -- previously, columns were incorrectly extracted from the SCHEMA elementParameter instead of the FLOW metadata.
- The method ONLY sets `component['config']['columns']`. It does NOT set `mode`, `keep_row_order`, or any other config keys. These come from the generic mapper (always defaults).
- Column types, nullable flags, and defaults are NOT extracted. Only column names.
- The XPath `.//metadata[@connector="FLOW"]` correctly targets the output schema metadata section.

---

## Appendix B: Engine Class Structure

```
FilterColumns (BaseComponent)
    Constants:
        DEFAULT_MODE = 'include'
        DEFAULT_COLUMNS = []              # MUTABLE -- see BUG-FC-006
        DEFAULT_KEEP_ROW_ORDER = True
        VALID_MODES = ['include', 'exclude']

    Methods:
        _validate_config() -> List[str]   # DEAD CODE -- never called (BUG-FC-007)
        _process(input_data) -> Dict[str, Any]  # Main entry point

    Inherited from BaseComponent:
        execute(input_data) -> Dict[str, Any]     # Orchestrates mode selection, stats, globalMap
        _auto_select_mode(input_data) -> ExecutionMode  # HYBRID auto-switch
        _execute_batch(input_data) -> Dict[str, Any]    # Calls _process()
        _execute_streaming(input_data) -> Dict[str, Any]  # Chunks DF, calls _process() per chunk
        _create_chunks(df) -> Iterator[pd.DataFrame]    # Generator for streaming
        _update_stats(rows_read, rows_ok, rows_reject)  # Accumulates stats
        _update_global_map()                              # BUGGY -- see BUG-FC-001
        validate_schema(df, schema) -> pd.DataFrame       # Type coercion -- INVERTED nullable logic
        _resolve_java_expressions()                       # Resolves {{java}} markers
```

---

## Appendix C: Complete Talend Parameter to V1 Config Key Reference

| Talend Parameter | V1 Config Key | Status | Priority to Add |
|------------------|---------------|--------|-----------------|
| `SCHEMA` (output metadata columns) | `columns` | **Mapped** (via `parse_filter_columns()`) | -- |
| (No Talend equivalent) | `mode` | V1 Extension | Should be documented, not "mapped" |
| (No Talend equivalent) | `keep_row_order` | V1 Extension (dead code) | Should be removed or documented |
| `TSTATCATCHER_STATS` | -- | Not Mapped | -- (rarely used) |
| `LABEL` | -- | Not Mapped | -- (cosmetic) |
| `PROPERTY_TYPE` | -- | Not Mapped | -- (always Built-In) |

---

## Appendix D: Converter Dual-Path Flow Diagram

```
Talend XML (tFilterColumns node)
    |
    v
parse_base_component()
    |
    +-- NOT in components_with_dedicated_parsers
    |   (tFilterColumns is missing from the list)
    |
    +-- Generic elementParameter extraction (lines 432-458)
    |   Extracts: UNIQUE_NAME, LABEL, TSTATCATCHER_STATS, etc.
    |   (No COLUMNS, MODE, or KEEP_ROW_ORDER in Talend XML)
    |
    +-- _map_component_parameters('tFilterColumns', config_raw)
    |   Returns: {columns: [], mode: 'include', keep_row_order: True}
    |   (All defaults -- no Talend equivalents exist)
    |
    +-- Generic metadata schema extraction (lines 475-508)
    |   Sets: component['schema']['output'] = [{name, type, nullable, ...}]
    |
    v
converter.py:_parse_component() (line 238-239)
    |
    +-- elif component_type == 'tFilterColumns':
    |       parse_filter_columns(node, component)
    |
    v
parse_filter_columns()
    |
    +-- Extracts column names from <metadata connector="FLOW">
    +-- OVERWRITES component['config']['columns'] = ['col1', 'col2', ...]
    |
    v
Final config:
    {
        columns: ['col1', 'col2', ...],  # From parse_filter_columns()
        mode: 'include',                  # From _map_component_parameters() default
        keep_row_order: True              # From _map_component_parameters() default (DEAD)
    }
```

---

## Appendix E: Edge Case Analysis

### Edge Case 1: Empty input DataFrame

| Aspect | Detail |
|--------|--------|
| **Talend** | Returns 0 rows with output schema columns defined (empty DataFrame with correct structure). NB_LINE=0. |
| **V1** | Returns `pd.DataFrame()` with NO columns (line 133). Stats (0, 0, 0). |
| **Verdict** | **GAP** -- V1 loses schema structure. See BUG-FC-003. |

### Edge Case 2: None input

| Aspect | Detail |
|--------|--------|
| **Talend** | Not applicable -- Talend always provides a flow. |
| **V1** | Returns `pd.DataFrame()` with NO columns (line 133). Stats (0, 0, 0). |
| **Verdict** | ACCEPTABLE -- None input is a v1-specific edge case. |

### Edge Case 3: All specified columns missing from input

| Aspect | Detail |
|--------|--------|
| **Talend** | Adds all specified columns with null/default values. All rows pass through. |
| **V1** | Returns empty `pd.DataFrame()`. Stats: `(total_rows, 0, total_rows)` -- all rows "rejected". Logs warning. |
| **Verdict** | **GAP** -- V1 should add columns with NaN. See ENG-FC-002 and BUG-FC-004. |

### Edge Case 4: Input has extra columns not in include list

| Aspect | Detail |
|--------|--------|
| **Talend** | Extra columns silently dropped (not in output schema). |
| **V1** | Extra columns correctly dropped by `input_data[columns_to_keep]` (line 170). |
| **Verdict** | **CORRECT** |

### Edge Case 5: Column names with special characters (spaces, dots)

| Aspect | Detail |
|--------|--------|
| **Talend** | Column names can contain special characters. Matching is by exact name. |
| **V1** | pandas handles column names with special characters. `col in available_columns` is exact string match. |
| **Verdict** | **CORRECT** |

### Edge Case 6: NaN values in data

| Aspect | Detail |
|--------|--------|
| **Talend** | NaN/null values are preserved through column filtering. |
| **V1** | `input_data[columns_to_keep].copy()` preserves NaN values. No NaN manipulation in FilterColumns. |
| **Verdict** | **CORRECT** |

### Edge Case 7: Empty string values

| Aspect | Detail |
|--------|--------|
| **Talend** | Empty strings are preserved. Not confused with null. |
| **V1** | pandas preserves empty strings. `.copy()` does not modify values. |
| **Verdict** | **CORRECT** |

### Edge Case 8: DataFrame with 0 columns, N rows

| Aspect | Detail |
|--------|--------|
| **Talend** | Not a typical scenario -- all DataFrames have at least one column. |
| **V1** | `input_data.empty` returns `True` for 0-column DataFrame with rows. Early return with empty DF. |
| **Verdict** | ACCEPTABLE -- edge case unlikely in production. Note: `pd.DataFrame(index=range(5))` has 5 rows but 0 columns, and `.empty` returns `False` in newer pandas. Need to verify pandas version behavior. |

### Edge Case 9: Duplicate column names in include list

| Aspect | Detail |
|--------|--------|
| **Talend** | Output schema cannot have duplicate column names. |
| **V1** | `columns_to_keep` list may contain duplicates. `input_data[columns_to_keep]` with duplicate column names will create a DataFrame with duplicate columns, which can cause subtle bugs downstream. |
| **Verdict** | **GAP** -- V1 does not deduplicate. Should raise error or deduplicate. |

### Edge Case 10: Include mode with empty columns list

| Aspect | Detail |
|--------|--------|
| **Talend** | Not possible -- schema always has at least one column. |
| **V1** | `columns = []` -> `columns_to_keep = []` (empty) -> `not columns_to_keep` is True -> returns empty DF with `_update_stats(total_rows, 0, total_rows)`. All rows "rejected". |
| **Verdict** | ACCEPTABLE for edge case, but reject stats are semantically wrong. See BUG-FC-004. |

### Edge Case 11: Exclude mode with empty columns list

| Aspect | Detail |
|--------|--------|
| **Talend** | Not possible -- no explicit exclude mode in Talend. |
| **V1** | `columns = []` in exclude mode -> `columns_to_remove = []` -> `columns_to_keep = all columns` -> all columns pass through. |
| **Verdict** | **CORRECT** for v1 extension. |

### Edge Case 12: Very large number of columns (1000+)

| Aspect | Detail |
|--------|--------|
| **Talend** | Handles fine -- schema is static. |
| **V1** | `for col in columns` loop (line 154) iterates over config columns, checking `col in available_columns` (O(n) for list). For 1000 config columns and 1000 input columns, this is O(n^2). Could be O(n) with set. See PERF-FC-002. |
| **Verdict** | CORRECT but SLOW for extreme column counts. |

### Edge Case 13: Streaming mode with column filtering

| Aspect | Detail |
|--------|--------|
| **Talend** | Talend processes row-by-row, no chunking. |
| **V1** | Base class chunks DataFrame, calls `_process()` per chunk. Each chunk filtered identically. Final `pd.concat()` merges. Column structure consistent across chunks. |
| **Verdict** | **CORRECT** |

### Edge Case 14: Thread safety with shared DEFAULT_COLUMNS

| Aspect | Detail |
|--------|--------|
| **Talend** | Not applicable -- Java component instances are independent. |
| **V1** | `DEFAULT_COLUMNS = []` is a mutable class attribute. If two threads both create FilterColumns instances and one mutates `DEFAULT_COLUMNS`, the other is affected. Current code does not mutate it, but it is a latent risk. |
| **Verdict** | LATENT RISK. See BUG-FC-006. |

### Edge Case 15: _update_global_map() crash effect on component status

| Aspect | Detail |
|--------|--------|
| **Talend** | Not applicable -- Java component stats are set atomically. |
| **V1** | In `execute()` (base_component.py line 218), `_update_global_map()` is called BEFORE `self.status = ComponentStatus.SUCCESS` (line 220). If `_update_global_map()` crashes (BUG-FC-001), the exception propagates to the outer try/except (line 227), setting `self.status = ComponentStatus.ERROR` (line 228). The component result is never returned. The status NEVER reaches SUCCESS for ANY component when `global_map` is set. This is the single most critical cross-cutting bug. |
| **Verdict** | **CRITICAL GAP**. All components fail when globalMap is present. Status never reaches SUCCESS. |

---

## Appendix F: Cross-Cutting Issues

The following issues were discovered during this audit but affect the entire v1 engine, not just `FilterColumns`:

| ID | Priority | Component | Issue |
|----|----------|-----------|-------|
| BUG-FC-001 | **P0** | `base_component.py:304` | `_update_global_map()` references undefined `value` variable. Will crash ALL components. Status never reaches SUCCESS. |
| BUG-FC-002 | **P0** | `global_map.py:28` | `GlobalMap.get()` references undefined `default` parameter. Will crash on any `get()` call. |
| BUG-FC-007 | **P1** | `base_component.py` | `_validate_config()` is defined in child components but never called by base class. ALL components with validation logic have dead validation. |
| (validate_schema) | **P2** | `base_component.py:351` | `validate_schema()` nullable condition is inverted. Nullable columns get `fillna(0)` instead of non-nullable columns. |

These should be tracked in a cross-cutting issues report as well.

---

## Appendix G: Implementation Fix Guides

### Fix Guide: BUG-FC-001 -- `_update_global_map()` undefined variable

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

**Explanation**: `{value}` references an undefined variable (the loop variable is `stat_value`). The `{stat_name}` reference would show only the last loop iteration value, which is misleading. Best fix is to remove both stale references.

**Impact**: Fixes ALL components (cross-cutting). Unblocks ComponentStatus.SUCCESS. **Risk**: Very low (log message only).

---

### Fix Guide: BUG-FC-002 -- `GlobalMap.get()` undefined default

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

### Fix Guide: BUG-FC-003 -- Empty input schema preservation

**File**: `src/v1/engine/components/transform/filter_columns.py`
**Lines**: 130-133

**Current code**:
```python
if input_data is None or input_data.empty:
    logger.warning(f"[{self.id}] Empty input received")
    self._update_stats(0, 0, 0)
    return {'main': pd.DataFrame()}
```

**Fix**:
```python
if input_data is None or input_data.empty:
    logger.warning(f"[{self.id}] Empty input received")
    self._update_stats(0, 0, 0)
    columns = self.config.get('columns', [])
    return {'main': pd.DataFrame(columns=columns)}
```

**Explanation**: Preserves output schema structure (column names with zero rows) for downstream components that expect specific columns.

**Impact**: Fixes downstream `KeyError` when accessing columns on empty FilterColumns output. **Risk**: Low (only affects empty input path).

---

### Fix Guide: BUG-FC-006 -- Mutable class default

**File**: `src/v1/engine/components/transform/filter_columns.py`
**Line**: 71

**Current code**:
```python
DEFAULT_COLUMNS = []
```

**Fix option 1** (safest):
```python
DEFAULT_COLUMNS = ()  # Immutable tuple
```

**Fix option 2** (cleanest):
```python
# Remove DEFAULT_COLUMNS class attribute entirely
# In _process(), change line 137 to:
columns = self.config.get('columns', [])  # Fresh list each time
```

**Impact**: Eliminates latent shared-state corruption risk. **Risk**: Very low.

---

### Fix Guide: BUG-FC-007 -- Wire up `_validate_config()`

**File**: `src/v1/engine/components/transform/filter_columns.py`

**Add at the beginning of `_process()` (after line 129)**:
```python
# Validate configuration
errors = self._validate_config()
if errors:
    error_msg = f"Configuration validation failed: {'; '.join(errors)}"
    logger.error(f"[{self.id}] {error_msg}")
    raise ConfigurationError(error_msg)
```

**Impact**: Catches invalid configs early with clear error messages. **Risk**: Low (validation was already written, just not invoked).

---

### Fix Guide: ENG-FC-002 -- Column addition with defaults

**File**: `src/v1/engine/components/transform/filter_columns.py`

**In the include mode block (after line 170), add**:
```python
# Add missing columns with NaN (Talend behavior: output schema can augment input)
for col in missing_columns:
    result_df[col] = pd.NA
    logger.info(f"[{self.id}] Added missing column '{col}' with null values")
```

**And reorder to match output schema order**:
```python
# Reorder to match original column config order (include both existing and added)
result_df = result_df[columns]
```

**Impact**: Enables Talend-compatible column addition. **Risk**: Medium (changes behavior for jobs that previously got warnings for missing columns).

---

## Appendix H: Comparison with Other Transform Components

| Feature | tFilterColumns (V1) | tFilterRow (V1) | tMap (V1) | tSortRow (V1) |
|---------|---------------------|-----------------|-----------|---------------|
| Basic function | Column filtering | Row filtering | Row+column transform | Row sorting |
| Dedicated converter parser | Yes (`parse_filter_columns`) | Yes (`parse_filter_rows`) | Yes (`parse_tmap`) | Yes (`parse_sort_row`) |
| `component_mapping` entry | **No** | Yes (`FilterRows`) | Yes (`Map`) | Yes (`SortRow`) |
| `_validate_config()` called | **No** (dead code) | **No** (dead code) | N/A | **No** (dead code) |
| V1 unit tests | **No** | **No** | **No** | **No** |
| REJECT flow | N/A (no REJECT in Talend) | N/A (missing) | N/A (missing) | N/A (no REJECT) |
| GlobalMap NB_LINE | Yes | Yes | Yes | Yes |
| GlobalMap ERROR_MESSAGE | **No** | **No** | **No** | **No** |
| `_update_global_map()` bug | Yes (cross-cutting) | Yes (cross-cutting) | Yes (cross-cutting) | Yes (cross-cutting) |

**Observation**: The dead `_validate_config()`, missing `ERROR_MESSAGE` globalMap variable, missing unit tests, and `_update_global_map()` crash bug are systemic issues across ALL transform components. This suggests architectural omissions rather than component-specific oversights.

---

## Appendix I: Risk Assessment for Production Migration

### High-Risk Scenarios

| Scenario | Risk Level | Affected Jobs | Mitigation |
|----------|-----------|---------------|------------|
| Jobs using tFilterColumns to ADD columns | **High** | Jobs where output schema has columns not in input | Must implement column addition with defaults |
| Jobs relying on NB_LINE from globalMap | **Critical** | Any job accessing `tFilterColumns_1_NB_LINE` downstream | Must fix BUG-FC-001 (`_update_global_map()` crash) first |
| Jobs with empty input DataFrames | **Medium** | ETL jobs with conditional branches that may produce empty flows | Must fix BUG-FC-003 (schemaless empty output) |
| Jobs relying on column reordering | **Low** | Jobs where column order matters | V1 preserves config order -- should work correctly |

### Low-Risk Scenarios

| Scenario | Risk Level | Notes |
|----------|-----------|-------|
| Simple column removal | Low | Core use case works correctly |
| Jobs with stable input schemas | Low | No missing columns -> no addition needed |
| Jobs using tStatCatcher | Low | Not extracted, but rarely used |
| Column renaming | N/A | Not a feature of tFilterColumns (use tMap for renaming) |

### Recommended Migration Strategy

1. **Phase 1**: Fix all P0 bugs (cross-cutting `_update_global_map()` and `GlobalMap.get()`). Without these fixes, NO component can execute successfully with globalMap.
2. **Phase 2**: Create P0 unit tests. Verify basic include-mode column filtering works.
3. **Phase 3**: Audit each target job's tFilterColumns usage. Identify if any output schemas add columns not present in the input.
4. **Phase 4**: For jobs that add columns, implement ENG-FC-002 fix before migration.
5. **Phase 5**: Fix empty-input schema preservation (BUG-FC-003) if any jobs have conditional empty flows.
6. **Phase 6**: Parallel-run migrated jobs against Talend originals. Compare output column structure and row counts.

---

## Appendix J: Detailed `_process()` Code Walkthrough

### Lines 110-133: Method Signature and Empty Input Guard

```python
def _process(self, input_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
```

The method accepts an optional DataFrame. If `input_data` is None or empty, it returns an empty DataFrame with stats (0, 0, 0). **Issue**: Empty DataFrame has no schema (BUG-FC-003).

### Lines 135-142: Configuration Extraction

```python
mode = self.config.get('mode', self.DEFAULT_MODE)
columns = self.config.get('columns', self.DEFAULT_COLUMNS)
keep_row_order = self.config.get('keep_row_order', self.DEFAULT_KEEP_ROW_ORDER)
```

All three config values are read. `keep_row_order` is read but NEVER used -- dead variable. `mode` is always `'include'` from converter. `columns` is the list extracted by `parse_filter_columns()`.

### Lines 144-147: Available Column Detection

```python
available_columns = list(input_data.columns)
```

Converts pandas Index to list. Used for `in` checks. Should be `set()` for O(1) lookups (PERF-FC-002).

### Lines 149-170: Include Mode

Iterates over config `columns`, checks each against `available_columns`. Builds `columns_to_keep` (found) and `missing_columns` (not found). If no valid columns remain, returns empty DF with all rows "rejected" (BUG-FC-004). Otherwise, selects columns with `.copy()`.

### Lines 172-183: Exclude Mode

Builds `columns_to_remove` (in both config and input) and `columns_to_keep` (in input but not in config). If all columns excluded, returns empty DF with all rows "rejected" (BUG-FC-005).

### Lines 185-200: Statistics and GlobalMap

Updates stats with `(total_rows, total_rows, 0)` -- all rows pass through. Stores `NB_COLUMNS_IN` and `NB_COLUMNS_OUT` in globalMap (v1-specific).

### Lines 202-205: Error Handling

Catches all exceptions, wraps in `ComponentExecutionError` with component ID. Uses `raise ... from e` for proper chaining.

---

## Appendix K: validate_schema() Inverted Nullable Condition Detail

The base class `validate_schema()` method (base_component.py lines 340-359) contains this code:

```python
if pandas_type == 'int64' and col_def.get('nullable', True):
    df[col_name] = df[col_name].fillna(0).astype('int64')
```

**The condition is inverted.** Analysis:

| `nullable` value | Current behavior | Correct behavior |
|------------------|-----------------|-----------------|
| `True` (nullable column) | `fillna(0).astype('int64')` -- fills NaN with 0, loses nullability | Should KEEP NaN using nullable `Int64` dtype |
| `False` (non-nullable column) | No `fillna` -- NaN remains | Should `fillna(0).astype('int64')` -- fill NaN with 0 per Talend semantics |
| Not specified (default `True`) | Same as True -- fills NaN | Should KEEP NaN |

**Impact on FilterColumns**: FilterColumns does not call `validate_schema()` in its own `_process()`. However, if the engine pipeline or downstream components call it on FilterColumns output, nullable integer columns will silently lose their null values.

**Fix**: Change condition to `not col_def.get('nullable', True)`:
```python
if pandas_type == 'int64' and not col_def.get('nullable', True):
    df[col_name] = df[col_name].fillna(0).astype('int64')
```

---

## Appendix L: Type Demotion Risks

FilterColumns performs `.copy()` on column subsets. The pandas `.copy()` method preserves dtypes for standard dtypes (`int64`, `float64`, `object`, `datetime64[ns]`). However, there are edge cases:

| Dtype | Preserved by `.copy()`? | Risk |
|-------|------------------------|------|
| `int64` | Yes | No risk |
| `float64` | Yes | No risk |
| `object` (strings) | Yes | No risk |
| `datetime64[ns]` | Yes | No risk |
| `Int64` (nullable integer) | Yes | No risk |
| `category` | Yes | No risk |
| `Decimal` (via object) | Yes (stored as object) | No risk |
| Extension types (e.g., `ArrowDtype`) | **Depends** | May lose extension metadata in older pandas versions |

**Conclusion**: For standard Talend-compatible dtypes, FilterColumns `.copy()` preserves types correctly. No type demotion risk for production use cases.

---

## Appendix M: Comprehensive Test Implementation Guide

### Test Fixture Setup

The following test fixtures should be created in `tests/v1/unit/test_filter_columns.py`:

```python
import pytest
import pandas as pd
import numpy as np
from unittest.mock import MagicMock
from src.v1.engine.components.transform.filter_columns import FilterColumns
from src.v1.engine.global_map import GlobalMap
from src.v1.engine.exceptions import ComponentExecutionError, ConfigurationError


@pytest.fixture
def basic_df():
    """Standard 5-column DataFrame for testing"""
    return pd.DataFrame({
        'name': ['Alice', 'Bob', 'Charlie'],
        'age': [30, 25, 35],
        'city': ['NYC', 'LA', 'Chicago'],
        'email': ['a@x.com', 'b@x.com', 'c@x.com'],
        'temp_col': ['x', 'y', 'z']
    })


@pytest.fixture
def nan_df():
    """DataFrame with NaN values in various columns"""
    return pd.DataFrame({
        'name': ['Alice', None, 'Charlie'],
        'age': [30, np.nan, 35],
        'city': ['NYC', 'LA', None],
        'score': [1.5, np.nan, 3.7]
    })


@pytest.fixture
def typed_df():
    """DataFrame with multiple types for type preservation testing"""
    return pd.DataFrame({
        'id': pd.array([1, 2, 3], dtype='Int64'),
        'name': ['Alice', 'Bob', 'Charlie'],
        'score': [1.5, 2.7, 3.9],
        'active': [True, False, True],
        'created': pd.to_datetime(['2024-01-01', '2024-02-01', '2024-03-01'])
    })


@pytest.fixture
def empty_df():
    """Empty DataFrame with columns defined"""
    return pd.DataFrame(columns=['name', 'age', 'city'])


@pytest.fixture
def global_map():
    """Fresh GlobalMap instance"""
    return GlobalMap()
```

### P0 Test Cases (Must Have)

```python
class TestFilterColumnsP0:
    """Critical tests that must pass before production deployment"""

    def test_basic_include_mode(self, basic_df):
        """Test 1: Basic include mode -- keep 3 of 5 columns"""
        fc = FilterColumns('fc_1', {'mode': 'include', 'columns': ['name', 'age', 'city']})
        result = fc._process(basic_df)

        assert list(result['main'].columns) == ['name', 'age', 'city']
        assert len(result['main']) == 3
        assert 'email' not in result['main'].columns
        assert 'temp_col' not in result['main'].columns

    def test_column_reordering(self, basic_df):
        """Test 2: Output column order matches config order, not input order"""
        fc = FilterColumns('fc_2', {'mode': 'include', 'columns': ['city', 'name', 'age']})
        result = fc._process(basic_df)

        assert list(result['main'].columns) == ['city', 'name', 'age']

    def test_missing_columns_warning(self, basic_df):
        """Test 3: Missing columns logged as warnings, existing columns kept"""
        fc = FilterColumns('fc_3', {'mode': 'include', 'columns': ['name', 'nonexistent', 'age']})
        result = fc._process(basic_df)

        assert list(result['main'].columns) == ['name', 'age']
        assert len(result['main']) == 3

    def test_empty_dataframe_input(self, empty_df):
        """Test 4: Empty DataFrame returns empty output"""
        fc = FilterColumns('fc_4', {'mode': 'include', 'columns': ['name', 'age']})
        result = fc._process(empty_df)

        assert result['main'].empty
        assert fc.stats['NB_LINE'] == 0

    def test_none_input(self):
        """Test 5: None input returns empty output"""
        fc = FilterColumns('fc_5', {'mode': 'include', 'columns': ['name']})
        result = fc._process(None)

        assert result['main'].empty
        assert fc.stats['NB_LINE'] == 0

    def test_statistics_tracking(self, basic_df):
        """Test 6: Stats correctly reflect all rows passing through"""
        fc = FilterColumns('fc_6', {'mode': 'include', 'columns': ['name', 'age']})
        result = fc._process(basic_df)

        assert fc.stats['NB_LINE'] == 3
        assert fc.stats['NB_LINE_OK'] == 3
        assert fc.stats['NB_LINE_REJECT'] == 0

    def test_globalmap_integration(self, basic_df):
        """Test 7: GlobalMap receives NB_LINE and column stats"""
        gm = GlobalMap()
        fc = FilterColumns('fc_7', {'mode': 'include', 'columns': ['name', 'age']}, global_map=gm)
        result = fc._process(basic_df)

        # Note: _update_global_map() is called by execute(), not _process()
        # For direct _process() testing, check the stats dict
        assert fc.stats['NB_LINE'] == 3

        # If testing via execute() (requires BUG-FC-001 fix):
        # assert gm.get('fc_7_NB_LINE') == 3
```

### P1 Test Cases (Important)

```python
class TestFilterColumnsP1:
    """Important tests for feature completeness"""

    def test_exclude_mode_basic(self, basic_df):
        """Test 8: Exclude mode removes specified columns"""
        fc = FilterColumns('fc_8', {'mode': 'exclude', 'columns': ['temp_col', 'email']})
        result = fc._process(basic_df)

        assert 'temp_col' not in result['main'].columns
        assert 'email' not in result['main'].columns
        assert set(result['main'].columns) == {'name', 'age', 'city'}

    def test_all_columns_excluded(self, basic_df):
        """Test 9: Excluding all columns returns empty DF"""
        fc = FilterColumns('fc_9', {
            'mode': 'exclude',
            'columns': ['name', 'age', 'city', 'email', 'temp_col']
        })
        result = fc._process(basic_df)

        assert result['main'].empty

    def test_all_columns_included(self, basic_df):
        """Test 10: Including all columns returns full DataFrame"""
        fc = FilterColumns('fc_10', {
            'mode': 'include',
            'columns': ['name', 'age', 'city', 'email', 'temp_col']
        })
        result = fc._process(basic_df)

        assert list(result['main'].columns) == ['name', 'age', 'city', 'email', 'temp_col']
        assert len(result['main']) == 3

    def test_duplicate_column_names(self, basic_df):
        """Test 11: Duplicate column names in config"""
        fc = FilterColumns('fc_11', {'mode': 'include', 'columns': ['name', 'name']})
        result = fc._process(basic_df)

        # Current behavior: creates duplicate columns
        # Expected: should deduplicate
        assert len(result['main'].columns) <= 2

    def test_case_sensitivity(self, basic_df):
        """Test 12: Column matching is case-sensitive"""
        fc = FilterColumns('fc_12', {'mode': 'include', 'columns': ['Name', 'AGE']})
        result = fc._process(basic_df)

        # 'Name' != 'name', 'AGE' != 'age' -- both missing
        # Current behavior: returns empty DF with all rows "rejected"
        assert result['main'].empty or len(result['main'].columns) == 0

    def test_empty_columns_list_include(self, basic_df):
        """Test 13: Empty columns list in include mode"""
        fc = FilterColumns('fc_13', {'mode': 'include', 'columns': []})
        result = fc._process(basic_df)

        assert result['main'].empty

    def test_nan_values_preserved(self, nan_df):
        """Test 14: NaN values are preserved through filtering"""
        fc = FilterColumns('fc_14', {'mode': 'include', 'columns': ['name', 'age']})
        result = fc._process(nan_df)

        assert pd.isna(result['main']['name'].iloc[1])
        assert pd.isna(result['main']['age'].iloc[1])

    def test_dtype_preservation(self, typed_df):
        """Test 15: Column types are preserved through filtering"""
        fc = FilterColumns('fc_15', {'mode': 'include', 'columns': ['id', 'score', 'active']})
        result = fc._process(typed_df)

        assert result['main']['id'].dtype == pd.Int64Dtype()
        assert result['main']['score'].dtype == np.float64
        assert result['main']['active'].dtype == bool

    def test_single_column(self, basic_df):
        """Test 16: Single column DataFrame works correctly"""
        fc = FilterColumns('fc_16', {'mode': 'include', 'columns': ['name']})
        result = fc._process(basic_df)

        assert list(result['main'].columns) == ['name']
        assert len(result['main']) == 3
```

### P2 Test Cases (Hardening)

```python
class TestFilterColumnsP2:
    """Hardening tests for edge cases"""

    def test_special_chars_in_column_names(self):
        """Test 19: Column names with spaces, dots, brackets"""
        df = pd.DataFrame({
            'first name': ['Alice'],
            'age.years': [30],
            'address[0]': ['NYC']
        })
        fc = FilterColumns('fc_19', {
            'mode': 'include',
            'columns': ['first name', 'age.years']
        })
        result = fc._process(df)

        assert list(result['main'].columns) == ['first name', 'age.years']

    def test_empty_string_column_name(self):
        """Test 18: Column named empty string"""
        df = pd.DataFrame({'': ['value1'], 'name': ['Alice']})
        fc = FilterColumns('fc_18', {'mode': 'include', 'columns': ['']})
        result = fc._process(df)

        assert '' in result['main'].columns

    def test_invalid_mode_config(self):
        """Test 21: Invalid mode with dead _validate_config"""
        df = pd.DataFrame({'name': ['Alice']})
        fc = FilterColumns('fc_21', {'mode': 'invalid_mode', 'columns': ['name']})

        # Since _validate_config() is dead code, this falls through to else branch
        # mode == 'invalid_mode' is not 'include', so falls to else (exclude mode)
        result = fc._process(df)
        # Should this raise? Currently it silently uses exclude mode

    def test_non_list_columns_config(self):
        """Test 22: columns as string instead of list"""
        df = pd.DataFrame({'name': ['Alice'], 'age': [30]})
        fc = FilterColumns('fc_22', {'mode': 'include', 'columns': 'name'})

        # String 'name' is iterable -- iterates over characters 'n','a','m','e'
        # This is a subtle bug
        result = fc._process(df)

    def test_empty_string_values_preserved(self):
        """Test 24: Empty strings preserved, not converted to NaN"""
        df = pd.DataFrame({'name': ['Alice', '', 'Charlie'], 'age': [30, 25, 35]})
        fc = FilterColumns('fc_24', {'mode': 'include', 'columns': ['name']})
        result = fc._process(df)

        assert result['main']['name'].iloc[1] == ''
        assert not pd.isna(result['main']['name'].iloc[1])

    def test_exception_wrapping(self):
        """Test: Verify exceptions are wrapped in ComponentExecutionError"""
        # Create a mock input that will cause an error
        fc = FilterColumns('fc_err', {'mode': 'include', 'columns': ['name']})

        class BadDF:
            empty = False
            columns = property(lambda self: (_ for _ in ()).throw(RuntimeError("boom")))

        with pytest.raises(ComponentExecutionError):
            fc._process(BadDF())
```

---

## Appendix N: Converter-to-Engine Data Flow Trace

This appendix traces the complete data flow from a Talend XML `tFilterColumns` node through the converter and into the v1 engine.

### Step 1: Talend XML Input

```xml
<node componentName="tFilterColumns" componentVersion="0.101" offsetLabelX="0" offsetLabelY="0" posX="384" posY="256">
  <elementParameter field="TEXT" name="UNIQUE_NAME" value="tFilterColumns_1"/>
  <elementParameter field="TEXT" name="LABEL" value="filter_columns"/>
  <elementParameter field="CHECK" name="TSTATCATCHER_STATS" value="false"/>
  <metadata connector="FLOW" label="tFilterColumns_1" name="tFilterColumns_1">
    <column comment="" key="false" length="50" name="name" nullable="true" originalDbColumnName="name" pattern="" precision="0" sourceType="" type="id_String" usefulColumn="true"/>
    <column comment="" key="false" length="10" name="age" nullable="true" originalDbColumnName="age" pattern="" precision="0" sourceType="" type="id_Integer" usefulColumn="true"/>
    <column comment="" key="false" length="100" name="city" nullable="true" originalDbColumnName="city" pattern="" precision="0" sourceType="" type="id_String" usefulColumn="true"/>
  </metadata>
</node>
```

### Step 2: parse_base_component() Output

```python
{
    'id': 'tFilterColumns_1',
    'type': 'tFilterColumns',      # No component_mapping entry!
    'original_type': 'tFilterColumns',
    'position': {'x': 384, 'y': 256},
    'config': {
        'columns': [],             # COLUMNS not in Talend XML -> default []
        'mode': 'include',         # MODE not in Talend XML -> default 'include'
        'keep_row_order': True     # KEEP_ROW_ORDER not in Talend XML -> default True
    },
    'schema': {
        'input': [],
        'output': [
            {'name': 'name', 'type': 'str', 'nullable': True, 'key': False, 'length': 50},
            {'name': 'age', 'type': 'int', 'nullable': True, 'key': False, 'length': 10},
            {'name': 'city', 'type': 'str', 'nullable': True, 'key': False, 'length': 100}
        ]
    },
    'inputs': [],
    'outputs': []
}
```

### Step 3: parse_filter_columns() Output

```python
{
    'id': 'tFilterColumns_1',
    'type': 'tFilterColumns',
    'original_type': 'tFilterColumns',
    'position': {'x': 384, 'y': 256},
    'config': {
        'columns': ['name', 'age', 'city'],   # OVERWRITTEN by parse_filter_columns()
        'mode': 'include',                      # Unchanged from step 2
        'keep_row_order': True                  # Unchanged from step 2
    },
    'schema': {
        'input': [],
        'output': [
            {'name': 'name', 'type': 'str', 'nullable': True, 'key': False, 'length': 50},
            {'name': 'age', 'type': 'int', 'nullable': True, 'key': False, 'length': 10},
            {'name': 'city', 'type': 'str', 'nullable': True, 'key': False, 'length': 100}
        ]
    },
    'inputs': [],
    'outputs': []
}
```

### Step 4: Engine Instantiation

```python
# In engine.py, the component registry resolves:
registry['tFilterColumns'] = FilterColumns

# Component is instantiated with:
component = FilterColumns(
    component_id='tFilterColumns_1',
    config={
        'columns': ['name', 'age', 'city'],
        'mode': 'include',
        'keep_row_order': True
    },
    global_map=global_map_instance,
    context_manager=context_manager_instance
)
```

### Step 5: Engine Execution

```python
# execute() is called by the engine with input from upstream component:
result = component.execute(input_dataframe)

# Internally:
# 1. _resolve_java_expressions() -- no {{java}} markers, no-op
# 2. context_manager.resolve_dict() -- no ${context.} refs, no-op
# 3. _auto_select_mode() -> BATCH (unless DF > 3GB)
# 4. _execute_batch() -> _process(input_dataframe)
# 5. _process() filters columns:
#    - mode='include', columns=['name', 'age', 'city']
#    - result_df = input_dataframe[['name', 'age', 'city']].copy()
# 6. _update_stats(total_rows, total_rows, 0)
# 7. global_map.put(NB_COLUMNS_IN, ...) and global_map.put(NB_COLUMNS_OUT, ...)
# 8. Returns {'main': result_df}
# 9. Back in execute(): _update_global_map() -> CRASHES on BUG-FC-001
```

---

## Appendix O: Talend tFilterColumns vs V1 FilterColumns Feature Matrix

| Feature | Talend tFilterColumns | V1 FilterColumns | Match? |
|---------|----------------------|------------------|--------|
| Remove columns from flow | Yes (omit from output schema) | Yes (`include` mode) | Yes |
| Reorder columns | Yes (output schema order) | Yes (config list order) | Yes |
| Add new columns with null defaults | Yes (add to output schema) | **No** (missing columns warned and skipped) | **No** |
| Add new columns with typed defaults | Yes (schema defines type and default) | **No** | **No** |
| Exclude mode (remove specific columns) | No (always define what to keep) | Yes (v1 extension) | N/A |
| Column name matching | Case-sensitive by name | Case-sensitive by name | Yes |
| Row passthrough (no row filtering) | Yes (all rows pass through) | Yes (all rows pass through) | Yes |
| Preserve column types | Yes | Yes (`.copy()` preserves dtypes) | Yes |
| Preserve NaN/null values | Yes | Yes | Yes |
| Dynamic schema | Yes (pass all columns) | **No** | **No** |
| NB_LINE globalMap | Yes (after execution) | Yes (via base class) | Yes |
| ERROR_MESSAGE globalMap | Yes (on error) | **No** | **No** |
| REJECT flow | No (not applicable) | No | Yes (both absent) |
| tStatCatcher | Yes (optional) | No | N/A (rarely used) |
| Schema-driven configuration | Yes (output schema IS the config) | No (explicit column list in config) | **Conceptual difference** |
| Performance overhead | Negligible | Negligible (plus `.copy()` memory) | Close |

### Feature Parity Summary

- **Fully matched**: 8 features (remove, reorder, name matching, row passthrough, type preservation, NaN preservation, NB_LINE, no REJECT)
- **Missing in V1**: 4 features (add columns with defaults, add columns with typed defaults, dynamic schema, ERROR_MESSAGE)
- **V1 extensions**: 1 feature (exclude mode)
- **Conceptual difference**: 1 (schema-driven vs config-driven)

---

## Appendix P: Detailed Streaming Mode Analysis

### How Streaming Mode Activates for FilterColumns

```
execute(input_data: DataFrame)
    |
    +-- _auto_select_mode(input_data)
    |       |
    |       +-- isinstance(input_data, pd.DataFrame) -> True
    |       +-- memory_usage_mb = input_data.memory_usage(deep=True).sum() / (1024*1024)
    |       +-- if memory_usage_mb > 3072:  # 3 GB threshold
    |       |       return STREAMING
    |       +-- else:
    |               return BATCH
    |
    +-- if mode == STREAMING:
    |       _execute_streaming(input_data)
    |           |
    |           +-- _create_chunks(input_data)  # yields df.iloc[i:i+100000]
    |           +-- for chunk in chunks:
    |           |       chunk_result = _process(chunk)
    |           |       results.append(chunk_result['main'])
    |           +-- combined = pd.concat(results, ignore_index=True)
    |           +-- return {'main': combined}
    |
    +-- else:
            _execute_batch(input_data)
                |
                +-- return _process(input_data)
```

### Streaming Mode Correctness Analysis

| Aspect | Analysis | Verdict |
|--------|----------|---------|
| Column filtering per chunk | Each chunk filtered identically with same `columns` config. Output schemas consistent. | CORRECT |
| Stats accumulation | `_update_stats()` uses `+=` on `self.stats`. Multiple chunks accumulate correctly. | CORRECT |
| GlobalMap NB_COLUMNS_IN/OUT | Called per chunk via `global_map.put()`. Each chunk overwrites with same values. Final value correct. | CORRECT |
| Column order consistency | Each chunk uses `input_data[columns_to_keep]` with same `columns_to_keep`. Order consistent. | CORRECT |
| `pd.concat()` column alignment | All chunks have identical column structure. `pd.concat()` aligns correctly. | CORRECT |
| `ignore_index=True` | Resets row index. For FilterColumns (no row filtering), this is correct -- original index is not meaningful. | CORRECT |
| Empty chunk handling | If a chunk has 0 rows, `input_data.empty` returns True, triggering early return with `pd.DataFrame()`. This empty schemaless DF is appended to results. `pd.concat()` with empty DF + non-empty DF drops the empty one. | CORRECT (but schemaless empty DF is still BUG-FC-003) |
| Memory during concat | All chunk results are held in `results` list. For a 10 GB DataFrame chunked into 100 pieces, all 100 filtered chunks exist in memory simultaneously during `pd.concat()`. This doubles peak memory vs streaming benefit. | LIMITATION -- not a bug, but reduces streaming memory benefit |

### Streaming Mode Memory Timeline

For a 4 GB DataFrame with 50% of columns selected, chunk_size=100000 rows:

```
Time 0: Full 4 GB DataFrame in memory (from upstream component)
Time 1: Chunk 1 (40 MB) created, filtered to 20 MB result, appended to results list
Time 2: Chunk 2 (40 MB) created, filtered to 20 MB result, appended
...
Time N: Chunk N created, filtered, appended
Time N+1: pd.concat() -- all results in memory = 2 GB total
Time N+2: Original 4 GB DataFrame still in memory (held by caller)
Peak memory: ~6 GB (4 GB original + 2 GB concatenated result)
```

Without streaming (batch mode):
```
Peak memory: ~6 GB (4 GB original + 2 GB copy)
```

**Conclusion**: For FilterColumns specifically, streaming mode provides NO memory benefit because the full DataFrame is held by the caller and the full result is concatenated. Streaming is only beneficial for components that read from external sources (files, databases) where the full data never needs to be in memory at once.

---

## Appendix Q: Complete `_process()` Method Line-by-Line Annotation

```python
def _process(self, input_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
    """Filter columns based on configuration."""

    # Lines 130-133: Empty input guard
    # BUG-FC-003: Returns schemaless DataFrame -- should preserve column structure
    if input_data is None or input_data.empty:
        logger.warning(f"[{self.id}] Empty input received")
        self._update_stats(0, 0, 0)
        return {'main': pd.DataFrame()}

    # Lines 136-138: Config extraction
    # mode: always 'include' from converter (no Talend MODE param)
    # columns: list from parse_filter_columns() (FLOW metadata column names)
    # keep_row_order: always True (DEAD -- never used anywhere below)
    mode = self.config.get('mode', self.DEFAULT_MODE)
    columns = self.config.get('columns', self.DEFAULT_COLUMNS)  # BUG-FC-006: mutable default
    keep_row_order = self.config.get('keep_row_order', self.DEFAULT_KEEP_ROW_ORDER)

    total_rows = len(input_data)
    logger.info(f"[{self.id}] Processing started: {total_rows} rows, mode='{mode}'")
    logger.debug(f"[{self.id}] Configuration: columns={columns}, keep_row_order={keep_row_order}")

    try:
        # Line 146: Available column detection
        # PERF-FC-002: list() instead of set() makes lookups O(n)
        available_columns = list(input_data.columns)
        logger.debug(f"[{self.id}] Available columns: {available_columns}")

        if mode == 'include':
            # Lines 151-170: Include mode -- keep only specified columns
            columns_to_keep = []
            missing_columns = []

            for col in columns:
                if col in available_columns:  # O(n) lookup on list
                    columns_to_keep.append(col)
                else:
                    missing_columns.append(col)
                    # ENG-FC-002: Should ADD column with NaN instead of skipping

            if missing_columns:
                logger.warning(f"[{self.id}] Columns not found: {missing_columns}")

            if not columns_to_keep:
                # BUG-FC-004: All rows marked as "rejected" -- semantic misuse
                logger.warning(f"[{self.id}] No valid columns to keep, returning empty DataFrame")
                self._update_stats(total_rows, 0, total_rows)
                return {'main': pd.DataFrame()}

            logger.debug(f"[{self.id}] Include mode: keeping columns {columns_to_keep}")
            # PERF-FC-001: .copy() doubles memory for selected columns
            result_df = input_data[columns_to_keep].copy()

        else:  # exclude mode (v1 extension, never produced by converter)
            # Lines 174-183: Exclude mode -- remove specified columns
            columns_to_remove = [col for col in columns if col in available_columns]
            columns_to_keep = [col for col in available_columns if col not in columns]

            if not columns_to_keep:
                # BUG-FC-005: All rows marked as "rejected" -- semantic misuse
                logger.warning(f"[{self.id}] All columns excluded, returning empty DataFrame")
                self._update_stats(total_rows, 0, total_rows)
                return {'main': pd.DataFrame()}

            logger.debug(f"[{self.id}] Exclude mode: removing {columns_to_remove}, keeping {columns_to_keep}")
            result_df = input_data[columns_to_keep].copy()

        # Lines 186-199: Post-filtering stats and globalMap
        logger.info(f"[{self.id}] Column filtering complete: "
                    f"input={len(available_columns)} columns, "
                    f"output={len(result_df.columns)} columns")

        # All rows pass through -- no row filtering in tFilterColumns
        self._update_stats(total_rows, total_rows, 0)

        # V1-specific custom stats (not in Talend)
        if self.global_map:
            self.global_map.put(f"{self.id}_NB_COLUMNS_IN", len(available_columns))
            self.global_map.put(f"{self.id}_NB_COLUMNS_OUT", len(result_df.columns))
            logger.debug(f"[{self.id}] Updated global map with column statistics")

        logger.info(f"[{self.id}] Processing complete: {total_rows} rows processed")
        return {'main': result_df}

    except Exception as e:
        # Lines 202-205: Error wrapping
        # ENG-FC-003: Does not set {id}_ERROR_MESSAGE in globalMap
        error_msg = f"Error filtering columns: {str(e)}"
        logger.error(f"[{self.id}] {error_msg}")
        raise ComponentExecutionError(self.id, error_msg, e) from e
```

---

## Appendix R: Behavioral Note on `input_data.empty` with Edge-Case DataFrames

The guard on line 130 checks `input_data.empty`. The behavior of `pd.DataFrame.empty` varies:

| DataFrame | `.empty` value | Rows | Columns | FilterColumns behavior |
|-----------|---------------|------|---------|----------------------|
| `pd.DataFrame()` | True | 0 | 0 | Early return, empty DF |
| `pd.DataFrame(columns=['a','b'])` | True | 0 | 2 | Early return, loses schema (BUG-FC-003) |
| `pd.DataFrame({'a': []})` | True | 0 | 1 | Early return, loses schema |
| `pd.DataFrame({'a': [1]})` | False | 1 | 1 | Normal processing |
| `pd.DataFrame(index=range(5))` | **True** | 5 | 0 | Early return (correct -- no columns to filter) |
| `pd.DataFrame({'a': [None, None]})` | False | 2 | 1 | Normal processing (NaN rows are not "empty") |

**Key insight**: `pd.DataFrame.empty` returns True when there are 0 rows OR 0 columns. The 0-columns-with-rows case (row 5 in table) is correctly handled as empty. The 0-rows-with-columns case (rows 2-3) is where schema loss occurs.

---

## Appendix S: Component Status Lifecycle Analysis

The `ComponentStatus` enum defines five states: PENDING, RUNNING, SUCCESS, ERROR, SKIPPED.

For FilterColumns, the lifecycle is:

```
PENDING (initial, set in __init__)
    |
    v [execute() called]
RUNNING (set on line 192 of base_component.py)
    |
    v [_process() completes successfully]
    |
    +-- _update_global_map() called (line 218)
    |   |
    |   +-- BUG-FC-001: NameError on 'value' variable
    |   |   |
    |   |   v [exception propagates to execute() except block]
    |   |   ERROR (set on line 228)
    |   |   |
    |   |   +-- _update_global_map() called AGAIN (line 231) in except block
    |   |   |   |
    |   |   |   +-- BUG-FC-001 AGAIN: NameError
    |   |   |   +-- This second crash propagates out of execute()
    |   |   |   +-- Component is left in ERROR state
    |   |   v
    |   |   Exception propagates to engine
    |   |
    |   v [if BUG-FC-001 is fixed]
    |
    v [line 220]
SUCCESS
    |
    v [result returned with stats]
    {'main': result_df, 'stats': {...}}
```

**Critical finding**: Due to BUG-FC-001, the SUCCESS state is UNREACHABLE for any component when `global_map` is not None. The `_update_global_map()` call on line 218 always crashes before line 220 (`self.status = ComponentStatus.SUCCESS`). Furthermore, the error handler on line 231 calls `_update_global_map()` AGAIN, causing a SECOND crash. This means the error handler itself crashes, and the original result is lost.

**Double-crash sequence**:
1. `_process()` succeeds, returns result
2. `_update_global_map()` crashes with NameError (line 218)
3. Exception caught by except block (line 227)
4. `self.status = ComponentStatus.ERROR` set (line 228)
5. `_update_global_map()` called again (line 231) -- crashes AGAIN
6. Second NameError propagates uncaught
7. Engine receives NameError, not the original result
8. Job fails

**When `global_map` is None**: `_update_global_map()` returns immediately (line 300: `if self.global_map:`), so the bug does not trigger. SUCCESS status is reached. This explains why some tests might pass if they don't provide a globalMap.
