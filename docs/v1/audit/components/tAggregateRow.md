# Audit Report: tAggregateRow / AggregateRow

> **Audited**: 2026-03-21
> **Auditor**: Claude Opus 4.6 (automated)
> **Engine Version**: v1
> **Converter**: `complex_converter`
> **Status**: PRODUCTION READINESS REVIEW

---

## 1. Component Identity

| Field | Value |
|-------|-------|
| **Talend Name** | `tAggregateRow` |
| **V1 Engine Class** | `AggregateRow` |
| **Engine File** | `src/v1/engine/components/aggregate/aggregate_row.py` (544 lines) |
| **Converter Parser** | `src/converters/complex_converter/component_parser.py` -> `parse_aggregate()` (lines 683-742) |
| **Converter Dispatch** | `src/converters/complex_converter/converter.py` -> line 234 (`elif component_type == 'tAggregateRow'`) |
| **Registry Aliases** | `AggregateRow`, `tAggregateRow` (registered in `src/v1/engine/engine.py` lines 162-163) |
| **Category** | Processing / Aggregate |

### Key Files

| File | Purpose |
|------|---------|
| `src/v1/engine/components/aggregate/aggregate_row.py` | Engine implementation (544 lines) |
| `src/converters/complex_converter/component_parser.py` (lines 683-742) | Dedicated parser: `parse_aggregate()` -- extracts GROUPBYS, OPERATIONS, output schema |
| `src/converters/complex_converter/converter.py` (line 234) | Dispatch -- dedicated `elif component_type == 'tAggregateRow'` branch calls `parse_aggregate()` |
| `src/v1/engine/base_component.py` | Base class: `_update_stats()`, `_update_global_map()`, `validate_schema()`, `execute()` |
| `src/v1/engine/global_map.py` | GlobalMap storage for `{id}_NB_LINE` etc. |
| `src/v1/engine/components/aggregate/__init__.py` | Package exports: `AggregateRow`, `UniqueRow` |

---

## 2. Scorecard

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
|-----------|-------|----|----|----|----|---------|
| Converter Coverage | **Y** | 1 | 2 | 3 | 2 | GROUPBYS only extracts INPUT_COLUMN (misses OUTPUT_COLUMN mapping); OPERATIONS uses fragile fixed-offset grouping of 4; debug `print()` statements left in; `LIST_DELIMITER`, `USE_FINANCIAL_PRECISION`, `CHECK_TYPE_OVERFLOW`, `CHECK_ULP` not extracted |
| Engine Feature Parity | **Y** | 2 | 4 | 2 | 2 | `output_column` ignored in grouped mode (uses `input_column` instead); `_ensure_output_columns` `else` branch nulls all columns including group-by and aggregation results; `ignore_null` never used; no REJECT flow; no `list_object`, `union`, `population_std_dev` functions; no financial precision toggle |
| Code Quality | **Y** | 4 | 2 | 4 | 3 | Cross-cutting base class bugs; `_validate_config()` dead code; excessive diagnostic logging; `_ensure_output_columns` `else` branch nulls ALL columns including group-by and aggregation results; merge column collision for multiple operations on same input column; indentation anomaly at lines 450-451 |
| Performance & Memory | **G** | 0 | 1 | 2 | 1 | Per-operation merge creates O(n*ops) intermediate DataFrames; no Decimal handling in grouped aggregation; excessive diagnostic logging slows large datasets |
| Testing | **R** | 1 | 1 | 0 | 0 | Zero v1 unit tests; zero v1 integration tests for this component |

**Overall: YELLOW -- Not production-ready without P0/P1 fixes**

### Score Key
- **R** (Red): Critical gaps blocking production use
- **Y** (Yellow): Significant gaps; usable for subset of jobs with known limitations
- **G** (Green): Production-ready with minor improvements recommended

---

## 3. Talend Feature Baseline

### What tAggregateRow Does

`tAggregateRow` receives a data flow and aggregates it based on one or more columns. For each output line, it provides the aggregation key (group-by column values) and the relevant result of set operations (min, max, sum, count, etc.). It is the SQL `GROUP BY` equivalent in Talend Studio and is one of the most commonly used processing components in data integration jobs.

The component has two configuration tables:

1. **Group By table** -- defines which columns form the aggregation key (group key).
2. **Operations table** -- defines what calculations to perform on each group.

**Source**: [tAggregateRow Standard Properties (Talend 7.3)](https://help.qlik.com/talend/en-US/components/7.3/processing/taggregaterow-standard-properties), [Component-specific settings for tAggregateRow (Job Script Reference Guide 8.0)](https://help.qlik.com/talend/en-US/job-script-reference-guide/8.0/component-specific-settings-for-taggregaterow), [tAggregateRow Overview (Talend 8.0)](https://help.talend.com/en-US/components/8.0/processing/taggregaterow)

**Component family**: Processing
**Available in**: All Talend products (Standard). Also available in MapReduce (deprecated), Spark Batch, Spark Streaming variants.
**Required JARs**: None beyond the standard Talend runtime.

### 3.1 Basic Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 1 | Property Type | `PROPERTY_TYPE` | Built-In / Repository | Built-In | Whether config comes from metadata repository or is inline. Not needed at runtime. |
| 2 | Schema | `SCHEMA` | Schema editor | -- | Output column definitions with types, lengths, patterns, nullable, key attributes. Defines the output structure. The output schema MUST include group-by columns AND all operation output columns. |
| 3 | Group By | `GROUPBYS` | Table (OUTPUT_COLUMN, INPUT_COLUMN) | -- | Table defining which columns form the group key. Each row maps an output column to an input column. When output and input names differ, the output column receives the input column's values. If empty, all rows are aggregated into a single output row. |
| 4 | Operations | `OPERATIONS` | Table (OUTPUT_COLUMN, FUNCTION, INPUT_COLUMN, IGNORE_NULL) | -- | **Mandatory**. Table defining aggregation operations. Each row specifies: the output column name, the aggregation function, the input column to aggregate, and whether to ignore null values. Multiple operations can target different output columns from the same input column. |

### 3.2 Group By Table Structure

| Column | Purpose | Description |
|--------|---------|-------------|
| `OUTPUT_COLUMN` | Output field name | The column name in the output schema that will contain the group key value. Must exist in the output schema. |
| `INPUT_COLUMN` | Input field name | The column name from the input flow to use as group key. When different from `OUTPUT_COLUMN`, enables column renaming during aggregation. |

### 3.3 Operations Table Structure

| Column | Purpose | Description |
|--------|---------|-------------|
| `OUTPUT_COLUMN` | Output field name | The column name in the output schema that will receive the aggregated value. Must exist in the output schema. A single input column can be aggregated multiple ways into different output columns (e.g., `amount` -> `total_amount` via sum, `avg_amount` via avg). |
| `FUNCTION` | Aggregation function | The aggregation operation to perform. See section 3.4 for the complete list. |
| `INPUT_COLUMN` | Input field name | The column from the input flow whose values will be aggregated. Not required for `count` function (counts rows regardless of column). |
| `IGNORE_NULL` | Null handling | Boolean. When `true`, null values in the input column are excluded from the aggregation calculation. When `false` (default), nulls participate in calculations (e.g., a null in `sum` causes the result to be null in some contexts). Default: `false`. |

### 3.4 Supported Aggregation Functions

| # | Function (XML value) | Display Name | Description | Input Types | Output Type | Null Behavior (IGNORE_NULL=false) | Null Behavior (IGNORE_NULL=true) |
|---|----------------------|-------------|-------------|-------------|-------------|-----------------------------------|----------------------------------|
| 1 | `count` | count | Counts the number of rows in each group | Any | Integer | Counts all rows including those with null values | Counts only non-null values |
| 2 | `distinct` / `count_distinct` | count (distinct) | Counts the number of distinct (unique) values in each group | Any | Integer | Counts all distinct values including null as a value | Excludes null from distinct count |
| 3 | `min` | min | Returns the minimum value in each group | Numeric, String, Date | Same as input | Null propagates (result is null if any value is null) | Ignores nulls, returns min of non-null values |
| 4 | `max` | max | Returns the maximum value in each group | Numeric, String, Date | Same as input | Null propagates | Ignores nulls, returns max of non-null values |
| 5 | `avg` | avg | Calculates the arithmetic mean of values in each group | Numeric | Double/BigDecimal | Null propagates | Ignores nulls in both numerator and denominator |
| 6 | `sum` | sum | Calculates the total sum of values in each group | Numeric | Same as input (preserves BigDecimal) | Null propagates | Ignores nulls, sums non-null values only |
| 7 | `first` | first | Returns the first value encountered in each group | Any | Same as input | Returns first value even if null | Skips null values, returns first non-null |
| 8 | `last` | last | Returns the last value encountered in each group | Any | Same as input | Returns last value even if null | Skips null values, returns last non-null |
| 9 | `list` | list | Concatenates string representations of values in each group using a configurable delimiter | Any (toString) | String | Includes "null" string in list | Excludes null values from list |
| 10 | `list_object` | list (object) | Collects values into a Java List object (not string) | Any | List\<Object\> | Includes null in list | Excludes null from list |
| 11 | `std_dev` | standard deviation | Calculates the sample standard deviation of values | Numeric | Double | Null propagates | Ignores nulls |
| 12 | `population_std_dev` | population standard deviation | Calculates the population standard deviation of values | Numeric | Double | Null propagates | Ignores nulls |
| 13 | `union` | union (geometry) | Makes the union of a set of Geometry objects | Geometry | Geometry | N/A | N/A |

**Note on function XML names**: The Talend Job Script Reference Guide documents the FUNCTION values as: `count`, `distinct`, `min`, `max`, `avg`, `sum`, `first`, `last`, `list`, `list_object`, `std_dev`, `union`. The Talend Studio UI displays friendly names like "count (distinct)" and "standard deviation" but stores the short XML values listed above.

### 3.5 Advanced Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 5 | List Delimiter | `LIST_DELIMITER` | String | `","` | Separator used by the `list` function to concatenate values into a string. Only applies to operations using the `list` function. Default is comma. |
| 6 | Use Financial Precision | `USE_FINANCIAL_PRECISION` | Boolean (CHECK) | `true` | When enabled, uses `BigDecimal` for `sum` and `avg` operations to avoid floating-point precision errors. Heaps more memory and slower than unchecked. Critical for financial calculations. Default is `true`. |
| 7 | Check Type Overflow | `CHECK_TYPE_OVERFLOW` | Boolean (CHECK) | `false` | Validates that aggregated values do not exceed the type's range (e.g., Integer.MAX_VALUE for int sums). When enabled, throws an exception if overflow is detected. |
| 8 | Check ULP | `CHECK_ULP` | Boolean (CHECK) | `false` | Unit of Least Precision verification for Float/Double types. Detects precision loss during aggregation. |
| 9 | tStatCatcher Statistics | `TSTATCATCHER_STATS` | Boolean (CHECK) | `false` | Capture processing metadata at job and component levels for the tStatCatcher component. Rarely used. |
| 10 | Label | `LABEL` | String | -- | Text label for the component in the Talend Studio designer canvas. No runtime impact. |

### 3.6 Connection Types

| Connector | Direction | Type | Description |
|-----------|-----------|------|-------------|
| `FLOW` (Main) | Input | Row > Main | Input data flow to aggregate. Each row is a record from an upstream component. |
| `FLOW` (Main) | Output | Row > Main | Aggregated output rows. One row per unique combination of group-by column values. If no group-by columns, a single row is output. |
| `REJECT` | Output | Row > Reject | Rows that failed aggregation (e.g., type conversion errors during numeric aggregation). Includes ALL original schema columns plus `errorCode` (String) and `errorMessage` (String). Only active when connected and `DIE_ON_ERROR=false`. |
| `SUBJOB_OK` | Output (Trigger) | Trigger | Fires when the entire subjob containing this component completes successfully. |
| `SUBJOB_ERROR` | Output (Trigger) | Trigger | Fires when the subjob containing this component fails with an error. |
| `COMPONENT_OK` | Output (Trigger) | Trigger | Fires when this specific component completes execution successfully. |
| `COMPONENT_ERROR` | Output (Trigger) | Trigger | Fires when this specific component fails with an error. |
| `RUN_IF` | Output (Trigger) | Trigger | Conditional trigger with a boolean expression. |

### 3.7 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
|------------------|------|----------|-------------|
| `{id}_NB_LINE` | Integer | After execution | Total number of input rows processed (before aggregation). |
| `{id}_NB_LINE_OK` | Integer | After execution | Number of rows successfully output after aggregation. Equals the number of unique group key combinations (or 1 if no group-by). |
| `{id}_NB_LINE_REJECT` | Integer | After execution | Number of rows sent to the REJECT flow. Zero when no REJECT link is connected. |
| `{id}_ERROR_MESSAGE` | String | On error | Last error message if any error occurred during execution. Available via `(String)globalMap.get("{id}_ERROR_MESSAGE")`. |

### 3.8 Behavioral Notes

1. **Group By with empty table**: When no group-by columns are specified, ALL rows are aggregated into a single output row. This is equivalent to SQL `SELECT SUM(col) FROM table` (no GROUP BY clause).

2. **Output vs Input column naming in Group By**: The `OUTPUT_COLUMN` in the Group By table can differ from `INPUT_COLUMN`. This enables column renaming during aggregation. For example, `OUTPUT_COLUMN=customer_name, INPUT_COLUMN=cust_nm` renames the column in the output while using the input column values for grouping.

3. **Output vs Input column naming in Operations**: Similarly, `OUTPUT_COLUMN` in the Operations table specifies the destination column name, and `INPUT_COLUMN` specifies the source. This is how a single input column can produce multiple output columns: `INPUT_COLUMN=amount, OUTPUT_COLUMN=total_amount, FUNCTION=sum` and `INPUT_COLUMN=amount, OUTPUT_COLUMN=avg_amount, FUNCTION=avg`.

4. **IGNORE_NULL per operation**: Each operation has its own `IGNORE_NULL` flag. This means in the same component, one operation can ignore nulls while another includes them. This is critical for correct aggregation behavior.

5. **Financial precision (BigDecimal)**: When `USE_FINANCIAL_PRECISION=true` (the default), Talend uses Java's `BigDecimal` for `sum` and `avg` to avoid IEEE 754 floating-point rounding errors. This is essential for financial calculations where precision matters (e.g., currency amounts). The tradeoff is higher memory usage and slower execution.

6. **list function delimiter**: The `LIST_DELIMITER` setting controls how the `list` function concatenates values. Default is comma (`,`). This produces output like `"val1,val2,val3"`. The delimiter can be any string, including multi-character strings.

7. **count function without input column**: The `count` function does not require an `INPUT_COLUMN`. When no input column is specified, it counts the number of rows in each group (equivalent to SQL `COUNT(*)`). When an input column IS specified, it counts non-null values in that column (equivalent to SQL `COUNT(column)`).

8. **Multiple operations on the same input column**: Talend allows defining multiple operations that read from the same input column but write to different output columns with different functions. For example, you can compute `sum(amount)`, `avg(amount)`, `min(amount)`, and `max(amount)` simultaneously.

9. **Type preservation**: `min` and `max` preserve the input type (if input is Date, output is Date). `count` and `count_distinct` always return Integer. `sum` preserves BigDecimal when financial precision is enabled. `avg` returns Double (or BigDecimal with financial precision).

10. **Determinism of first/last**: `first` and `last` return values based on the order rows arrive at the component. If the upstream flow is not sorted, the results may be non-deterministic. For deterministic results, use `tSortRow` before `tAggregateRow`.

11. **BigDecimal in sum/avg**: When the input column type is `id_BigDecimal` or `USE_FINANCIAL_PRECISION=true`, Talend uses `BigDecimal.add()` for `sum` and `BigDecimal.divide()` for `avg`. Division uses `RoundingMode.HALF_UP` with the precision specified in the schema. This ensures no floating-point rounding errors in financial calculations.

12. **Error handling**: When `DIE_ON_ERROR=true`, any error during aggregation (e.g., type mismatch, overflow) causes the entire job to fail. When `false` and a REJECT link is connected, problematic rows are routed to REJECT. When `false` and no REJECT link, errors are logged and potentially cause data loss.

---

## 4. Converter Audit

### 4.1 Parameter Extraction

The converter uses a **dedicated parser method** (`parse_aggregate()` in `component_parser.py` lines 683-742), which is dispatched from `converter.py` line 234 via `elif component_type == 'tAggregateRow'`.

**Converter flow**:
1. `converter.py:_parse_component()` identifies component type as `tAggregateRow` (line 234)
2. Calls `self.component_parser.parse_aggregate(node, component)` (line 235)
3. `parse_aggregate()` extracts GROUPBYS table from `elementParameter[@name="GROUPBYS"]` nodes (lines 691-695)
4. Extracts OPERATIONS table from `elementParameter[@name="OPERATIONS"]` nodes using fixed-offset grouping of 4 elementValues (lines 698-717)
5. Extracts output schema from `metadata[@connector="FLOW"]` nodes (lines 724-734)
6. Stores results in `component['config']` as `group_by`, `operations`, and `output` (lines 739-741)

| # | Talend XML Parameter | Extracted? | V1 Config Key | Converter Line | Notes |
|----|----------------------|------------|---------------|----------------|-------|
| 1 | `GROUPBYS.INPUT_COLUMN` | Yes | `group_by` (list of strings) | 694-695 | Extracts INPUT_COLUMN from each elementValue with `elementRef='INPUT_COLUMN'` |
| 2 | `GROUPBYS.OUTPUT_COLUMN` | **No** | -- | -- | **Not extracted. Only INPUT_COLUMN is used for group_by. OUTPUT_COLUMN mapping is lost.** |
| 3 | `OPERATIONS.OUTPUT_COLUMN` | Yes | `operations[].output_column` | 708-709 | Extracted from elementValue with `elementRef='OUTPUT_COLUMN'` |
| 4 | `OPERATIONS.FUNCTION` | Yes | `operations[].function` | 712-713 | Extracted from elementValue with `elementRef='FUNCTION'` |
| 5 | `OPERATIONS.INPUT_COLUMN` | Yes | `operations[].input_column` | 710-711 | Extracted from elementValue with `elementRef='INPUT_COLUMN'` |
| 6 | `OPERATIONS.IGNORE_NULL` | Yes | `operations[].ignore_null` | 714-715 | Extracted and converted to boolean via `val.lower() == 'true'` |
| 7 | `LIST_DELIMITER` | **No** | -- | -- | **Not extracted. Engine defaults to comma, but Talend's per-component delimiter setting is lost.** |
| 8 | `USE_FINANCIAL_PRECISION` | **No** | -- | -- | **Not extracted. Engine has ad-hoc Decimal handling but no toggle for financial precision mode.** |
| 9 | `CHECK_TYPE_OVERFLOW` | **No** | -- | -- | **Not extracted. No type overflow checking in engine.** |
| 10 | `CHECK_ULP` | **No** | -- | -- | **Not extracted. No ULP checking in engine.** |
| 11 | `TSTATCATCHER_STATS` | **No** | -- | -- | Not extracted (low priority -- tStatCatcher rarely used) |
| 12 | `LABEL` | **No** | -- | -- | Not extracted (cosmetic -- no runtime impact) |
| 13 | `PROPERTY_TYPE` | No | -- | -- | Not needed (always Built-In in converted jobs) |
| 14 | `SCHEMA` | Yes | `output` (list of column defs) | 724-734 | Extracted from `metadata[@connector="FLOW"]` with name, type, nullable, key, length, precision |

**Summary**: 6 of 13 runtime-relevant parameters extracted (46%). 4 runtime-relevant parameters are missing (`GROUPBYS.OUTPUT_COLUMN`, `LIST_DELIMITER`, `USE_FINANCIAL_PRECISION`, `CHECK_TYPE_OVERFLOW`).

### 4.2 GROUPBYS Parsing Analysis

```python
# component_parser.py lines 691-695
for table in node.findall('.//elementParameter[@name="GROUPBYS"]'):
    for elem in table.findall('./elementValue'):
        if elem.get('elementRef') == 'INPUT_COLUMN':
            group_by.append(elem.get('value', ''))
```

**Issue**: Only `INPUT_COLUMN` is extracted. The `OUTPUT_COLUMN` is completely ignored. In Talend, when the Group By table has `OUTPUT_COLUMN=customer_name, INPUT_COLUMN=cust_nm`, the output column should be named `customer_name` while grouping by the input column `cust_nm`. The current converter discards the output column name, so if the output schema uses a different column name than the input, the engine will look for the wrong column during grouping.

**Impact**: Jobs where Group By OUTPUT_COLUMN differs from INPUT_COLUMN will produce incorrect grouping or runtime errors because the engine will try to group by the input column name, which may not exist in the output schema.

### 4.3 OPERATIONS Parsing Analysis

```python
# component_parser.py lines 698-717
for table in node.findall('.//elementParameter[@name="OPERATIONS"]'):
    elems = list(table.findall('.//elementValue'))
    # Each operation is a group of 4: OUTPUT_COLUMN, INPUT_COLUMN, FUNCTION, IGNORE_NULL
    for i in range(0, len(elems), 4):
        op = {}
        for j in range(4):
            if i + j < len(elems):
                ref = elems[i + j].get('elementRef')
                val = elems[i + j].get('value', '')
                if ref == 'OUTPUT_COLUMN':
                    op['output_column'] = val
                elif ref == 'INPUT_COLUMN':
                    op['input_column'] = val
                elif ref == 'FUNCTION':
                    op['function'] = val
                elif ref == 'IGNORE_NULL':
                    op['ignore_null'] = val.lower() == 'true'
        if op:
            operations.append(op)
```

**Critical Assumption**: The parser assumes each operation is defined by EXACTLY 4 consecutive `elementValue` elements in the order: `OUTPUT_COLUMN`, `INPUT_COLUMN`, `FUNCTION`, `IGNORE_NULL`. This is a **fragile fixed-offset grouping approach**.

**Problem 1 -- Order dependency**: The code iterates in groups of 4 (`for i in range(0, len(elems), 4)`) and within each group, it reads 4 elements sequentially. If the Talend XML ever emits the elementValues in a different order (e.g., FUNCTION before OUTPUT_COLUMN), the grouping would still work because the inner loop uses `elementRef` matching, not positional assignment. However, the GROUP BOUNDARY is position-based: elements 0-3 form operation 1, elements 4-7 form operation 2, etc. If Talend adds a 5th field per operation (e.g., `LIST_DELIMITER`), the grouping breaks completely.

**Problem 2 -- Missing field**: If any operation has fewer than 4 elementValues (e.g., `count` which may not have `INPUT_COLUMN` in some Talend versions), the boundary shifts by one and ALL subsequent operations are misaligned. For example, if operation 1 has 3 elements and operation 2 has 4, the parser would read elements [0,1,2,3] as operation 1 (stealing element 0 of operation 2) and [4,5,6,7] as operation 2 (which is actually operation 2 element 1 + operation 3 elements 0-2).

**Problem 3 -- No XML structure verification**: The parser does not validate that the extracted `op` dict contains all required fields (`output_column`, `function`, `input_column`). An incomplete operation (missing `function`) is silently appended to the operations list, which will later cause the engine to default to `sum`.

### 4.4 Schema Extraction

Schema is extracted from `metadata[@connector="FLOW"]` nodes (lines 724-734).

| Schema Attribute | Extracted? | Notes |
|------------------|-----------|-------|
| `name` | Yes | Column name from `column.get('name')` |
| `type` | Yes | Raw Talend type string (e.g., `id_String`, `id_Integer`) -- preserves original format |
| `nullable` | Yes | Boolean conversion from string `"true"/"false"` |
| `key` | Yes | Boolean conversion from string |
| `length` | Yes | Integer conversion with default -1 |
| `precision` | Yes | Integer conversion with default -1 |
| `pattern` | **No** | Date pattern not extracted |
| `default` | **No** | Column default value not extracted |
| `comment` | **No** | Column comment not extracted (cosmetic) |

**REJECT schema**: Not extracted. There is no search for `metadata[@connector="REJECT"]`.

### 4.5 Expression Handling

The `parse_aggregate()` method does NOT perform any expression handling (context variable resolution, Java expression marking) on the extracted values. Group-by column names and operation column names are treated as literal strings. This is correct for column names, which are not expressions in Talend. However, the `LIST_DELIMITER` (if it were extracted) could potentially contain a context variable reference, which would need resolution.

### 4.6 Function Name Mapping

The converter stores the Talend function name as-is from the XML. No mapping or normalization is performed. This means the engine receives the raw Talend function names:

| Talend XML Value | Converter Passes Through | Engine Expects | Match? |
|------------------|-------------------------|----------------|--------|
| `count` | `count` | `count` | Yes |
| `distinct` | `distinct` | `count_distinct` | **No** |
| `min` | `min` | `min` | Yes |
| `max` | `max` | `max` | Yes |
| `avg` | `avg` | `avg` or `mean` | Yes |
| `sum` | `sum` | `sum` | Yes |
| `first` | `first` | `first` | Yes |
| `last` | `last` | `last` | Yes |
| `list` | `list` | `list` | Yes |
| `list_object` | `list_object` | Not supported | **No** |
| `std_dev` | `std_dev` | `std` or `stddev` | **No** |
| `population_std_dev` | `population_std_dev` | Not supported | **No** |
| `union` | `union` | Not supported | **No** |

**Three function names are passed through but do not match the engine's expected names**: `distinct` (should be `count_distinct`), `std_dev` (should be `std` or `stddev`), `list_object` / `population_std_dev` / `union` (not supported at all). When the engine receives `distinct`, it falls through to the `else` clause in `_apply_agg_function()` and defaults to `sum`, which is silently incorrect.

### 4.7 Converter Issues

| ID | Priority | Issue |
|----|----------|-------|
| CONV-AGG-001 | **P0** | **Function name mismatch for `distinct`**: The Talend XML value `distinct` is passed through without mapping to `count_distinct`. The engine's `SUPPORTED_FUNCTIONS` list contains `count_distinct` but NOT `distinct`. When `distinct` reaches the engine, `_validate_config()` (if called) would flag it as unknown, and `_apply_agg_function()` defaults to `sum` -- silently producing a sum instead of a distinct count. This is a **data correctness** bug. |
| CONV-AGG-002 | **P1** | **Function name mismatch for `std_dev`**: The Talend XML value `std_dev` is passed through without mapping to `std` or `stddev`. The engine supports `std` and `stddev` but NOT `std_dev`. Same silent fallback to `sum` behavior as CONV-AGG-001. |
| CONV-AGG-003 | **P1** | **GROUPBYS.OUTPUT_COLUMN not extracted**: Only `INPUT_COLUMN` is extracted for group-by. The output column name is discarded. Jobs where group-by output column names differ from input column names will fail or produce wrong results. |
| CONV-AGG-004 | **P1** | **Debug `print()` statements left in production code**: Lines 720-721 and 737 contain `print()` statements: `print(f"[parse_aggregate] Parsed group_by columns: {group_by}")`, `print(f"[parse_aggregate] Parsed operations: {operations}")`, `print(f"[parse_aggregate] Parsed output schema: {output_schema}")`. These write to stdout, polluting console output in production and potentially leaking data details. Per STANDARDS.md, all logging MUST use the `logging` module, never `print()`. |
| CONV-AGG-005 | **P2** | **Fragile fixed-offset OPERATIONS grouping**: The parser groups elementValues in sets of 4 by position. If any operation has fewer or more than 4 fields, all subsequent operations are misaligned. A more robust approach would group by a known structure marker (e.g., detect the start of each operation by the `OUTPUT_COLUMN` elementRef). |
| CONV-AGG-006 | **P2** | **`LIST_DELIMITER` not extracted**: The per-component list delimiter setting is lost. Engine hardcodes `,` as the default delimiter. Jobs using a custom delimiter (e.g., `|` or `;`) for the `list` function will produce incorrect output. |
| CONV-AGG-007 | **P2** | **`USE_FINANCIAL_PRECISION` not extracted**: The financial precision toggle is lost. Engine has ad-hoc Decimal handling for `sum` in `_apply_agg_function()` but no explicit toggle. When `USE_FINANCIAL_PRECISION=false` in Talend (for performance), the engine still attempts Decimal conversion, wasting resources. |
| CONV-AGG-008 | **P2** | **No validation of extracted operation completeness**: Operations missing required fields (`function`, `input_column`) are silently appended. Should validate and warn. |
| CONV-AGG-009 | **P3** | **`CHECK_TYPE_OVERFLOW` not extracted**: No overflow checking available. Low priority -- rarely causes issues in practice. |
| CONV-AGG-010 | **P3** | **`CHECK_ULP` not extracted**: No ULP verification. Low priority -- rarely used. |

---

## 5. Engine Feature Parity

### 5.1 Feature Implementation Status

| # | Talend Feature | Implemented? | Fidelity | Engine Location | Notes |
|----|----------------|-------------|----------|-----------------|-------|
| 1 | Group-by aggregation | **Yes** | Medium | `_aggregate_grouped()` line 409 | Uses pandas `groupby()`. Group-by columns filtered to existing columns only. |
| 2 | No-group-by aggregation | **Yes** | High | `_aggregate_all()` line 206 | Aggregates entire DataFrame into single row. Correct behavior. |
| 3 | `sum` function | **Yes** | Medium | `_apply_agg_function()` line 376, `_aggregate_grouped()` line 458 | Two code paths: `_apply_agg_function()` for non-grouped (preserves Decimal); `_aggregate_grouped()` uses `pandas.groupby().sum()` (does NOT preserve Decimal). |
| 4 | `count` function | **Yes** | High | `_apply_agg_function()` line 387-388, `_aggregate_grouped()` line 462-469 | Supports both with and without input column. `count` without input uses `.size()`. |
| 5 | `count_distinct` function | **Yes** | High | `_apply_agg_function()` line 389-390, `_aggregate_grouped()` line 471-473 | Uses `nunique()`. Correct. |
| 6 | `avg`/`mean` function | **Yes** | Medium | `_apply_agg_function()` line 381-382, `_aggregate_grouped()` line 475-477 | Uses pandas `.mean()`. No Decimal precision -- returns float64. |
| 7 | `min` function | **Yes** | High | `_apply_agg_function()` line 383-384, `_aggregate_grouped()` line 479-481 | Uses pandas `.min()`. Preserves type. |
| 8 | `max` function | **Yes** | High | `_apply_agg_function()` line 385-386, `_aggregate_grouped()` line 483-485 | Uses pandas `.max()`. Preserves type. |
| 9 | `first` function | **Yes** | Medium | `_apply_agg_function()` line 391-392, `_aggregate_grouped()` line 499-501 | Uses `iloc[0]` for non-grouped; pandas `.first()` for grouped. **Note**: pandas `.first()` has different semantics than array index 0 -- it returns the first non-NaN value by default. |
| 10 | `last` function | **Yes** | Medium | `_apply_agg_function()` line 393-394, `_aggregate_grouped()` line 503-505 | Uses `iloc[-1]` for non-grouped; pandas `.last()` for grouped. Same `.last()` caveat as `first`. |
| 11 | `list` function | **Yes** | Medium | `_apply_agg_function()` line 401-402, `_aggregate_grouped()` line 507-509 | Non-grouped: returns Python list. Grouped: uses `apply(list)`. Returns list objects, not delimited strings. **Different from Talend which returns delimited string.** |
| 12 | `concat`/`concatenate` function | **Yes** | High | `_apply_agg_function()` line 403-405, `_aggregate_grouped()` line 511-516 | Uses configurable delimiter. Joins with `.astype(str)`. V1-only function (not in Talend). |
| 13 | `std`/`stddev` function | **Yes** | Medium | `_apply_agg_function()` line 395-396, `_aggregate_grouped()` line 487-489 | Uses pandas `.std()` which computes SAMPLE standard deviation (ddof=1). Matches Talend `std_dev` but NOT `population_std_dev`. |
| 14 | `var`/`variance` function | **Yes** | Medium | `_apply_agg_function()` line 397-398, `_aggregate_grouped()` line 491-493 | Uses pandas `.var()` (sample variance). V1-only function (not directly in Talend). |
| 15 | `median` function | **Yes** | High | `_apply_agg_function()` line 399-400, `_aggregate_grouped()` line 495-497 | Uses pandas `.median()`. V1-only function (not in standard Talend tAggregateRow). |
| 16 | Output column renaming | **Partial** | Low | `_aggregate_all()` line 221, `_aggregate_grouped()` line 440 | Non-grouped: uses `output_col` correctly. **Grouped: uses `input_col` as `target_col` for all operations, ignoring `output_col`**. See BUG-AGG-001. |
| 17 | `ignore_null` per operation | **No** | N/A | -- | **Converter extracts it but engine NEVER reads or uses `op.get('ignore_null')`. Completely ignored.** |
| 18 | Financial precision (BigDecimal) | **Partial** | Low | `_apply_agg_function()` line 377-379, `_is_decimal_column()` line 346 | Only in `_apply_agg_function()` for `sum` -- checks `isinstance(series.iloc[0], Decimal)` and uses Python `sum()`. **NOT applied in `_aggregate_grouped()`** where pandas `groupby().sum()` loses Decimal precision. Not applied to `avg` at all. |
| 19 | `list_object` function | **No** | N/A | -- | **Not implemented. No equivalent in SUPPORTED_FUNCTIONS.** |
| 20 | `population_std_dev` function | **No** | N/A | -- | **Not implemented. Would need `std(ddof=0)` instead of `std(ddof=1)`.** |
| 21 | `union` (geometry) function | **No** | N/A | -- | **Not implemented. Geometry operations not supported.** |
| 22 | `USE_FINANCIAL_PRECISION` toggle | **No** | N/A | -- | **No toggle. Ad-hoc Decimal detection only.** |
| 23 | `LIST_DELIMITER` configuration | **No** | N/A | -- | **Hardcoded to `,`. No per-component delimiter.** |
| 24 | `CHECK_TYPE_OVERFLOW` | **No** | N/A | -- | **No type overflow checking.** |
| 25 | `CHECK_ULP` | **No** | N/A | -- | **No ULP verification.** |
| 26 | **REJECT flow** | **No** | N/A | -- | **No reject output. All errors either die or return empty DF. Fundamental gap.** |
| 27 | **`{id}_ERROR_MESSAGE` globalMap** | **No** | N/A | -- | **Error message not stored in globalMap.** |
| 28 | Group-by column renaming (OUTPUT != INPUT) | **No** | N/A | -- | **Converter doesn't extract OUTPUT_COLUMN from GROUPBYS. Engine has no column renaming for group-by keys.** |

### 5.2 Behavioral Differences from Talend

| ID | Priority | Description |
|----|----------|-------------|
| ENG-AGG-001 | **P0** | **`output_column` ignored in grouped aggregation**: In `_aggregate_grouped()`, for ALL operations except `count` without input column, `target_col = input_col` (lines 460, 465, 473, 477, 481, 485, 489, 493, 497, 501, 505, 509, 516, 522). The `output_col` variable is computed on line 440 but never used as `target_col`. This means if a Talend job maps `INPUT_COLUMN=amount` to `OUTPUT_COLUMN=total_amount`, the engine produces a column named `amount` instead of `total_amount`. The output column name is completely wrong. In `_aggregate_all()` (line 221-225), `output_col` IS used correctly, so this bug only affects grouped aggregation. **Data correctness bug: downstream components expecting `total_amount` will find no data.** |
| ENG-AGG-002 | **P1** | **`ignore_null` completely ignored**: The converter extracts `ignore_null` from each operation (CONV line 714-715), but the engine NEVER reads this flag. Neither `_apply_agg_function()` nor `_aggregate_grouped()` checks `op.get('ignore_null')`. The behavior is determined entirely by pandas defaults: `sum()` ignores NaN by default (`skipna=True`), `count()` excludes NaN by default, `mean()` ignores NaN by default. This means the engine always behaves as if `IGNORE_NULL=true` for most functions, which differs from Talend's default of `IGNORE_NULL=false`. For functions like `min`/`max`, this difference can produce different results when nulls are present. |
| ENG-AGG-003 | **P1** | **No REJECT flow**: Talend routes rows that fail aggregation to a REJECT output. V1 either raises `ComponentExecutionError` (line 203-204) or returns empty DataFrame. There is no mechanism to capture and route problematic rows separately. |
| ENG-AGG-004 | **P1** | **Decimal precision lost in grouped aggregation**: `_aggregate_grouped()` uses `df.groupby(valid_group_by)[input_col].sum()` (line 458) which converts `Decimal` values to `float64` via pandas' native aggregation. The Decimal-preserving logic in `_apply_agg_function()` (line 377-379) is ONLY used in the non-grouped `_aggregate_all()` path. Financial calculations using grouped aggregation lose precision. |
| ENG-AGG-005 | **P1** | **`list` function returns Python list, not delimited string**: In Talend, the `list` function produces a delimited string (e.g., `"val1,val2,val3"`). In V1, `_aggregate_grouped()` line 508 uses `.apply(list)` which produces a Python list object `['val1', 'val2', 'val3']`. Downstream components expecting a string will fail or produce unexpected output. The V1-only `concat`/`concatenate` function does produce delimited strings, but a Talend job converted with `list` will get the wrong output type. |
| ENG-AGG-006 | **P0** | **`_ensure_output_columns` `else` branch nulls ALL columns already present in result_df -- including group-by and aggregation result columns (duplicate of BUG-AGG-005)**: The `else` branch at line 299 of `_ensure_output_columns()` nulls columns NOT in `meaningful_columns`, but there is NO `meaningful_columns` guard on this branch. Combined with BUG-AGG-001 (`output_column` ignored), this makes grouped aggregation produce all-None results. |
| ENG-AGG-007 | **P2** | **`first()` and `last()` semantic mismatch between grouped and non-grouped**: In `_aggregate_all()`, `first` uses `series.iloc[0]` (returns first value regardless of null status). In `_aggregate_grouped()`, `first` uses `pandas.groupby().first()` which returns the first NON-NULL value per group. These are different behaviors. If the first row in a group has a null value, `_aggregate_all()` returns null while `_aggregate_grouped()` skips it and returns the next non-null value. |
| ENG-AGG-008 | **P2** | **No `list_object` function**: Talend's `list_object` returns a Java `List<Object>`. No equivalent in V1. The `list` function returns Python list but with different semantics (converts to list of values, not list of typed objects). |
| ENG-AGG-009 | **P2** | **No `population_std_dev` function**: Talend supports population standard deviation (`ddof=0`). V1 only has sample standard deviation (`ddof=1` via pandas `.std()`). For datasets where population vs sample matters, this produces different results. |
| ENG-AGG-010 | **P3** | **No `union` (geometry) function**: Geometry operations not applicable for most data integration jobs. Very low priority. |
| ENG-AGG-011 | **P3** | **`var`/`variance` and `median` are V1 extensions**: These functions exist in V1 but not in standard Talend tAggregateRow. No issue per se, but creates a superset that may confuse users expecting Talend parity. |

### 5.3 GlobalMap Variable Coverage

| Variable | Talend Sets? | V1 Sets? | How V1 Sets It | Notes |
|----------|-------------|----------|-----------------|-------|
| `{id}_NB_LINE` | Yes | **Yes** | `_update_stats()` -> `_update_global_map()` -> `global_map.put_component_stat()` | Set correctly via base class mechanism. Represents input rows (before aggregation). |
| `{id}_NB_LINE_OK` | Yes | **Yes** | Same mechanism | Set to output row count (after aggregation). Correct. |
| `{id}_NB_LINE_REJECT` | Yes | **Partial** | Same mechanism | Always 0 since no reject flow exists. Even if aggregation partially fails, reject count is not updated. |
| `{id}_ERROR_MESSAGE` | Yes (official) | **No** | -- | Not implemented. Error messages are logged but not stored in globalMap. |
| `{id}_EXECUTION_TIME` | N/A (v1 only) | **Yes** | Base class | V1-specific, not in Talend. |

---

## 6. Code Quality

### 6.1 Bugs

| ID | Priority | Location | Description |
|----|----------|----------|-------------|
| BUG-AGG-001 | **P0** | `aggregate_row.py:440-522` | **`output_column` ignored in `_aggregate_grouped()`**: For ALL aggregation operations in grouped mode, `target_col` is set to `input_col` instead of `output_col`. Line 440 correctly computes `output_col = op.get('output_column', input_col)` but then never uses it as the target column. Lines 460, 465, 473, 477, 481, 485, 489, 493, 497, 501, 505, 509, 516, 522 all set `target_col = input_col`. The only exception is `count` without input column (line 469: `target_col = output_col`). This means column renaming (e.g., `amount` -> `total_amount`) works in `_aggregate_all()` but NOT in `_aggregate_grouped()`. Any job that uses both group-by AND output column renaming will produce wrong column names. **Severity: Data correctness bug -- downstream components will reference missing columns.** |
| BUG-AGG-002 | **P0** | `src/v1/engine/base_component.py:304` | **`_update_global_map()` references undefined variable `value`**: The log statement on line 304 uses `{stat_name}: {value}` but the loop variable is `stat_value`, not `value`. This causes `NameError` at runtime whenever `global_map` is not None. **CROSS-CUTTING**: This bug affects ALL components, not just AggregateRow, since `_update_global_map()` is called after every component execution (via `execute()` line 218). |
| BUG-AGG-003 | **P0** | `src/v1/engine/global_map.py:28` | **`GlobalMap.get()` references undefined `default` parameter**: The method signature is `def get(self, key: str) -> Optional[Any]` (line 26), but the body calls `self._map.get(key, default)` (line 28). The `default` parameter is not in the signature, causing `NameError` on every `.get()` call. Additionally, `get_component_stat()` on line 58 calls `self.get(key, default)` with two arguments, but `get()` only accepts one. **CROSS-CUTTING**: Affects all code using `global_map.get()`. |
| BUG-AGG-004 | **P1** | `aggregate_row.py:80-113` | **`_validate_config()` is never called**: The method exists with 33 lines of validation logic (checking `group_by` is list, `operations` is list, validating each operation's function name and input_column). However, it is never invoked by `__init__()`, `execute()`, or `_process()`. The base class `BaseComponent` does not call it either. All validation is dead code. Invalid configurations (unsupported function names, missing input_column) are not caught until they cause silent misbehavior deep in processing. |
| BUG-AGG-005 | **P0** | `aggregate_row.py:299-302` | **`_ensure_output_columns` `else` branch nulls ALL columns already present in result_df -- including group-by and aggregation result columns**: The `else` branch at line 299 fires for any column in `result_df.columns` that is NOT in `meaningful_columns` and sets it to `None`. There is NO `meaningful_columns` guard on this branch. Combined with BUG-AGG-001 (`output_column` ignored, so `target_col = input_col`), group-by columns and aggregation result columns can be nulled, making grouped aggregation produce all-None results. **Severity: Data corruption -- grouped aggregation silently produces empty/null output.** |
| BUG-AGG-006 | **P1** | `aggregate_row.py:391-394` | **`first()` and `last()` in `_apply_agg_function()` do not handle empty series safely**: `series.iloc[0]` and `series.iloc[-1]` are guarded by `if len(series) > 0` but do not handle the case where all values are NaN. If `ignore_null` were implemented, a filtered series could have length > 0 but all NaN values. Additionally, in grouped mode, `pandas.groupby().first()` returns the first non-NaN value, while `series.iloc[0]` returns the first value regardless of NaN status -- behavioral inconsistency. |
| BUG-AGG-007 | **P2** | `aggregate_row.py:407` | **Unknown function silently defaults to `sum`**: When `_apply_agg_function()` receives a function name not in the if/elif chain (line 406-407: `else: return series.sum()`), it silently defaults to sum. This is a data correctness hazard. An unknown function name (e.g., `distinct`, `std_dev`, `list_object`) will produce a sum instead of raising an error. Combined with the converter's function name mismatch (CONV-AGG-001, CONV-AGG-002), this means silently wrong results. |
| BUG-AGG-008 | **P2** | `aggregate_row.py:518-522` | **Unknown function in grouped mode also defaults to `sum`**: The `else` clause on line 518-522 of `_aggregate_grouped()` does the same silent fallback: `logger.warning(...)` then `df.groupby().sum()`. While it logs a warning (better than `_apply_agg_function()`), it still produces wrong results for truly unknown functions. |
| BUG-AGG-009 | **P0** | `aggregate_row.py:_aggregate_grouped()` | **Merge column collision for multiple operations on the same input column**: In `_aggregate_grouped()`, when two operations target the same `input_col` (e.g., `sum(amount)` and `avg(amount)`), the second merge creates `_x`/`_y` suffixed columns because `target_col = input_col` (BUG-AGG-001) and the column already exists from the first merge. Column names become unpredictable and downstream components cannot find expected columns. Common Talend pattern: multiple operations on the same column with different output names. |

### 6.2 Naming Consistency

| ID | Priority | Issue |
|----|----------|-------|
| NAME-AGG-001 | **P2** | **`group_by` (snake_case list) vs Talend `GROUPBYS` (plural)**: The V1 config key is `group_by` (singular list of column names) while Talend uses `GROUPBYS` (plural table structure with OUTPUT_COLUMN + INPUT_COLUMN pairs). The simplification loses the output-vs-input column distinction. |
| NAME-AGG-002 | **P2** | **`operations` (list of dicts) vs Talend `OPERATIONS` (table with 4 columns)**: Structurally similar but the V1 dict keys (`input_column`, `output_column`, `function`, `ignore_null`) use snake_case instead of Talend's UPPER_CASE. This is acceptable but should be documented in a mapping reference. |
| NAME-AGG-003 | **P3** | **V1 function name aliases (`avg`/`mean`, `std`/`stddev`, `concat`/`concatenate`)**: V1 supports multiple aliases for the same function. While convenient, this creates ambiguity -- which name is canonical? Talend uses single names (`avg`, `std_dev`). The alias set creates a superset that may confuse converters. |

### 6.3 Standards Compliance

| ID | Priority | Standard | Violation |
|----|----------|----------|-----------|
| STD-AGG-001 | **P1** | "`_validate_config()` must be called" (METHODOLOGY.md) | Method exists but is never called. Contract technically met (method returns `List[str]`) but functionally useless. Dead code. |
| STD-AGG-002 | **P2** | "No `print()` statements" (STANDARDS.md) | Three `print()` statements in `component_parser.py` lines 720, 721, 737 for the `parse_aggregate()` method. Should use `logger.debug()` or `logger.info()`. |
| STD-AGG-003 | **P2** | "Use Talend type format (`id_String`) in schemas" (STANDARDS.md) | Schema extraction preserves Talend type format (`id_String`) -- CORRECT. No violation here (unlike tFileInputDelimited which converts to Python types). |
| STD-AGG-004 | **P3** | "Component should set `{id}_ERROR_MESSAGE` in globalMap" (STANDARDS.md) | Error messages not stored in globalMap. Only logged via `logger.error()`. |
| STD-AGG-005 | **P3** | Indentation anomaly at lines 450-451 | Comment and `if` statement appear at different indentation level than preceding block. Functionally harmless but confusing for maintenance. |

### 6.4 Debug Artifacts

| ID | Priority | Issue |
|----|----------|-------|
| DBG-AGG-001 | **P1** | **`print()` statements in converter parser**: Lines 720-721 and 737 of `component_parser.py` contain `print()` calls in `parse_aggregate()`. These are debug artifacts that write directly to stdout: `print(f"[parse_aggregate] Parsed group_by columns: {group_by}")`, `print(f"[parse_aggregate] Parsed operations: {operations}")`, `print(f"[parse_aggregate] Parsed output schema: {output_schema}")`. In production, these pollute stdout and may leak sensitive column names or data structures. |
| DBG-AGG-002 | **P2** | **Excessive diagnostic logging in `_process()`**: Lines 141-158 contain verbose diagnostic logging specifically for sum operations: iterating all sum operations, logging data types, sample values, non-null counts, and even performing a test sum. This is development-time debugging code that should be removed or moved to DEBUG level. In production, this creates excessive log noise for every execution. |
| DBG-AGG-003 | **P2** | **Final verification logging in `_process()`**: Lines 175-184 perform "SUM OPERATIONS FINAL VERIFICATION" with banner-style logging (`===== SUM OPERATIONS FINAL VERIFICATION =====`). This is debug output that should be removed or conditional on a debug flag. |
| DBG-AGG-004 | **P2** | **Excessive logging in `_ensure_output_columns()`**: Lines 249-342 contain verbose logging for every column operation: "Ensuring output columns", "Expected operation output columns", column-by-column verification, "FINAL CHECK" for each operation. While some logging is appropriate, this level of verbosity is excessive for production use. |
| DBG-AGG-005 | **P3** | **Unicode checkmark characters in log messages**: Lines 278, 530 use `\u2713` (checkmark) and line 532 uses `\u2717` (cross) in log messages. These may not render correctly in all log sinks (e.g., ASCII-only log files, Windows consoles). Should use plain text like "OK" and "FAIL". |

### 6.5 Security

| ID | Priority | Issue |
|----|----------|-------|
| SEC-AGG-001 | **P3** | **`print()` statements leak column names and operation details**: The converter's `print()` calls (lines 720-721, 737) output column names, operation configurations, and schema details to stdout. If stdout is captured in logs, this leaks potentially sensitive schema information. |

### 6.6 Logging Quality

| Aspect | Assessment |
|--------|------------|
| Logger setup | Module-level `logger = logging.getLogger(__name__)` -- correct |
| Component ID prefix | All log messages use `[{self.id}]` prefix -- correct |
| Level usage | INFO for milestones and diagnostic details (over-used), WARNING for missing columns, ERROR for failures -- INFO level is too verbose; much should be DEBUG |
| Start/complete logging | `_process()` logs start (line 134), completion (line 194-197) -- correct |
| Sensitive data | `print()` statements output data sample values (line 150) and schema details -- problematic |
| No print statements | Converter has 3 `print()` calls -- violation |
| Diagnostic bloat | ~25 INFO-level log lines per execution in happy path -- excessive |

### 6.7 Error Handling Quality

| Aspect | Assessment |
|--------|------------|
| Custom exceptions | Uses `ComponentExecutionError` from `base_component.py` -- correct |
| Exception chaining | Uses `raise ComponentExecutionError(...) from e` pattern on line 204 -- correct |
| Empty input handling | Returns empty DataFrame with stats (0, 0, 0) on line 130-131 -- correct |
| Missing group-by columns | Filters to existing columns, warns, falls back to `_aggregate_all()` on line 427 -- correct |
| Missing input columns | Warns and skips operation on lines 451-453 -- reasonable but should track in reject count |
| No bare `except` | All except clauses specify `Exception` -- correct |
| Error messages | Include component ID and error details -- correct |
| Graceful degradation | On operation error, sets column to None (line 538) and continues -- reasonable |

### 6.8 Type Hints

| Aspect | Assessment |
|--------|------------|
| Method signatures | All methods have return type hints -- correct |
| Parameter types | `_process()`, `_aggregate_all()`, `_aggregate_grouped()` have parameter type hints -- correct |
| Complex types | Uses `Dict[str, Any]`, `Optional[pd.DataFrame]`, `List[Dict]`, `List[str]` -- correct |
| Missing hints | `_apply_agg_function()` parameter `op` typed as `Dict` (should be `Dict[str, Any]`) -- minor |

---

## 7. Performance & Memory

| ID | Priority | Issue |
|----|----------|-------|
| PERF-AGG-001 | **P1** | **Per-operation merge creates O(n*ops) intermediate DataFrames**: `_aggregate_grouped()` performs one `result_df.merge(agg_result, ...)` per operation (line 525). For 10 operations on a DataFrame with 1M groups, this creates 10 intermediate merge results. A more efficient approach is to build a single aggregation dictionary and use `df.groupby().agg(agg_dict)` which performs all aggregations in one pass. |
| PERF-AGG-002 | **P2** | **Decimal precision lost in grouped path -- no Decimal-preserving groupby**: `_aggregate_grouped()` uses `df.groupby()[col].sum()` which converts Decimal to float64. The `_apply_agg_function()` path preserves Decimal via `sum(series.dropna(), Decimal('0'))` but this path is only used in `_aggregate_all()`. To preserve Decimal in grouped mode, would need `df.groupby()[col].apply(lambda x: sum(x.dropna(), Decimal('0')))` which is slower but correct. |
| PERF-AGG-003 | **P2** | **`_ensure_output_columns()` performs expensive column operations**: The method iterates all input columns, performs merge operations for "meaningful" columns not in the result (lines 285-292), and reorders all columns (lines 305-327). For wide DataFrames (100+ columns), this is expensive. Much of this work is unnecessary if the aggregation is correctly producing the expected output columns. |
| PERF-AGG-004 | **P3** | **Diagnostic logging computes test sums**: Lines 154-158 in `_process()` perform a `series.sum()` test on each sum operation's input column BEFORE the actual aggregation. This doubles the computation for sum operations and serves no production purpose. |

### 7.1 Memory Management Assessment

| Aspect | Assessment |
|--------|------------|
| Streaming mode | Not specifically implemented for AggregateRow. Base class streaming is not applicable because aggregation requires all rows to be in memory for correct group-by results. This is architecturally correct -- aggregation is inherently a full-data operation. |
| Memory overhead | Per-operation merge (PERF-AGG-001) creates temporary DataFrames. With 10 operations, the peak memory usage is approximately 2x the base DataFrame size (current result + one merge result). |
| Large group count | With many unique group values, the result DataFrame approaches the input size. No special handling for high-cardinality group-by columns. |
| Intermediate results | `_aggregate_grouped()` builds result incrementally via merge. Each merge creates a new DataFrame. Previous intermediates are garbage-collected only when Python's GC runs. |

---

## 8. Testing

### 8.1 Current Coverage

| Test Type | Exists? | File | Notes |
|-----------|---------|------|-------|
| V1 engine unit tests | **No** | -- | Zero test files found for `AggregateRow` v1 engine component |
| V1 engine integration tests | **No** | -- | No v1 engine integration tests found |

**Key finding**: The v1 engine has ZERO tests for this component.

### 8.2 Recommended Test Cases

#### P0 -- Must Have Before Production

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 1 | Basic grouped sum | P0 | Group by one column, sum another. Verify correct sums per group. |
| 2 | Basic grouped count | P0 | Group by one column, count rows per group. Verify correct counts. |
| 3 | No group-by aggregation | P0 | Sum/count with empty group_by list. Verify single-row output. |
| 4 | Output column renaming | P0 | `input_column=amount, output_column=total_amount` with group-by. Verify output column is named `total_amount` (currently broken -- BUG-AGG-001). |
| 5 | Multiple operations same input | P0 | Two operations on same column: `sum(amount)->total, avg(amount)->average`. Verify both output columns correct. |
| 6 | Empty input DataFrame | P0 | Pass empty DataFrame. Verify returns empty DataFrame with stats (0, 0, 0). |
| 7 | Statistics tracking | P0 | Verify `NB_LINE` = input rows, `NB_LINE_OK` = output groups, `NB_LINE_REJECT` = 0. |
| 8 | Function name `distinct` from Talend | P0 | Pass function name `distinct` (Talend XML value). Verify it performs count_distinct, not sum (currently broken -- CONV-AGG-001). |

#### P1 -- Important

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 9 | Multi-column group-by | P1 | Group by two columns. Verify correct group combinations. |
| 10 | Decimal precision in sum | P1 | Input with Decimal values, group-by, sum. Verify Decimal precision preserved (currently broken in grouped mode -- ENG-AGG-004). |
| 11 | Null handling with ignore_null=true | P1 | Operations with `ignore_null: true`. Verify null values excluded. (Currently not implemented -- ENG-AGG-002). |
| 12 | Null handling with ignore_null=false | P1 | Operations with `ignore_null: false`. Verify null behavior matches Talend. |
| 13 | `first` and `last` functions | P1 | Verify correct first/last values per group, including null handling. |
| 14 | `list` function output type | P1 | Verify `list` produces delimited string (not Python list) matching Talend behavior. (Currently produces Python list -- ENG-AGG-005). |
| 15 | `count_distinct` function | P1 | Verify distinct count per group. Include null values in test data. |
| 16 | `std`/`stddev` function | P1 | Verify sample standard deviation matches expected value. |
| 17 | Function name `std_dev` from Talend | P1 | Pass function name `std_dev` (Talend XML value). Verify it performs stddev, not sum (currently broken -- CONV-AGG-002). |
| 18 | Missing input column | P1 | Operation references non-existent column. Verify warning logged and operation skipped gracefully. |
| 19 | Missing group-by column | P1 | Group-by references non-existent column. Verify falls back to aggregate-all. |
| 20 | Multiple group-by with some missing | P1 | Two group-by columns, one exists, one doesn't. Verify groups by existing column only. |
| 21 | GlobalMap integration | P1 | Verify `{id}_NB_LINE` etc. are set in globalMap after execution. |

#### P2 -- Hardening

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 22 | Large dataset performance | P2 | 1M rows, 5 group-by, 10 operations. Measure execution time. |
| 23 | High-cardinality group-by | P2 | 100K unique groups. Verify memory usage and correctness. |
| 24 | All supported functions | P2 | Test each of the 17 supported functions individually. |
| 25 | `concat` with custom delimiter | P2 | Verify custom delimiter is used correctly. |
| 26 | `median` function | P2 | Verify median calculation per group. |
| 27 | `var`/`variance` function | P2 | Verify variance calculation per group. |
| 28 | Mixed types in aggregation | P2 | Aggregate string columns with min/max, numeric with all functions. |
| 29 | Single-row input | P2 | Input with one row. Verify output is one row with correct values. |
| 30 | All-null column aggregation | P2 | Column with all null values. Verify correct behavior for each function. |

---

## 9. Issues Summary

### P0 -- Critical

| ID | Category | Summary |
|----|----------|---------|
| BUG-AGG-001 | Bug (Engine) | `output_column` ignored in `_aggregate_grouped()` -- all operations use `input_col` as target column name instead of `output_col`. Column renaming in grouped aggregation is completely broken. Downstream components expecting renamed columns will fail. |
| BUG-AGG-002 | Bug (Cross-Cutting) | `_update_global_map()` in `base_component.py:304` references undefined variable `value` (should be `stat_value`). Will crash ALL components when `global_map` is set. |
| BUG-AGG-003 | Bug (Cross-Cutting) | `GlobalMap.get()` in `global_map.py:28` references undefined parameter `default`. Will crash on any `global_map.get()` call. `get_component_stat()` also passes two args to single-arg `get()`. |
| CONV-AGG-001 | Converter | Function name `distinct` from Talend XML is not mapped to `count_distinct`. Engine silently falls back to `sum`, producing wrong results. |
| BUG-AGG-005 | Bug (Engine) | `_ensure_output_columns()` `else` branch at line 299 nulls ALL columns already present in result_df -- including group-by and aggregation result columns. No `meaningful_columns` guard on this branch. Combined with BUG-AGG-001 (output_column ignored), grouped aggregation produces all-None results. |
| ENG-AGG-006 | Engine | `_ensure_output_columns` `else` branch nulls ALL columns already present in result_df -- including group-by and aggregation result columns (duplicate of BUG-AGG-005). Combined with BUG-AGG-001, makes grouped aggregation produce all-None results. |
| BUG-AGG-009 | Bug (Engine) | Merge column collision for multiple operations on the same input column. In `_aggregate_grouped()`, when two operations target the same `input_col` (e.g., `sum(amount)` and `avg(amount)`), the second merge creates `_x`/`_y` suffixed columns because `target_col = input_col` (BUG-AGG-001) and the column already exists from the first merge. Column names become unpredictable and downstream components cannot find expected columns. Common Talend pattern: multiple operations on the same column with different output names. |
| TEST-AGG-001 | Testing | Zero v1 unit tests for AggregateRow. All 544 lines of v1 engine code are unverified. |

### P1 -- Major

| ID | Category | Summary |
|----|----------|---------|
| CONV-AGG-002 | Converter | Function name `std_dev` from Talend XML not mapped to `std`/`stddev`. Silent fallback to `sum`. |
| CONV-AGG-003 | Converter | GROUPBYS.OUTPUT_COLUMN not extracted -- group-by column renaming impossible. |
| CONV-AGG-004 | Converter | Debug `print()` statements in `parse_aggregate()` -- production code pollution and potential data leak. |
| ENG-AGG-002 | Engine | `ignore_null` per-operation flag completely ignored. Engine always uses pandas defaults (effectively IGNORE_NULL=true for most functions). |
| ENG-AGG-003 | Engine | No REJECT flow -- errors either crash or produce empty DataFrame. No row-level error routing. |
| ENG-AGG-004 | Engine | Decimal precision lost in grouped aggregation -- pandas `groupby().sum()` converts Decimal to float64. |
| ENG-AGG-005 | Engine | `list` function returns Python list object instead of delimited string (Talend returns delimited string). |
| BUG-AGG-004 | Bug | `_validate_config()` is dead code -- never called by any code path. 33 lines of unreachable validation. |
| BUG-AGG-006 | Bug | `first()`/`last()` semantic mismatch between grouped (non-NaN first/last via pandas) and non-grouped (true first/last via iloc) paths. |
| DBG-AGG-001 | Debug | `print()` statements in converter -- lines 720, 721, 737 of `component_parser.py`. |
| STD-AGG-001 | Standards | `_validate_config()` exists but never called -- dead validation code. |
| PERF-AGG-001 | Performance | Per-operation merge creates O(n*ops) intermediate DataFrames. Should use single-pass `groupby().agg()`. |
| TEST-AGG-002 | Testing | No integration test for AggregateRow in a multi-step v1 job. |

### P2 -- Moderate

| ID | Category | Summary |
|----|----------|---------|
| CONV-AGG-005 | Converter | Fragile fixed-offset OPERATIONS grouping -- assumes exactly 4 elementValues per operation. |
| CONV-AGG-006 | Converter | `LIST_DELIMITER` not extracted -- engine hardcodes comma delimiter. |
| CONV-AGG-007 | Converter | `USE_FINANCIAL_PRECISION` not extracted -- no financial precision toggle. |
| CONV-AGG-008 | Converter | No validation of extracted operation completeness -- incomplete ops silently appended. |
| ENG-AGG-007 | Engine | `first()`/`last()` semantic mismatch between grouped and non-grouped modes. |
| ENG-AGG-008 | Engine | No `list_object` function support. |
| ENG-AGG-009 | Engine | No `population_std_dev` function -- only sample std_dev available. |
| BUG-AGG-007 | Bug | Unknown function silently defaults to `sum` in `_apply_agg_function()`. |
| BUG-AGG-008 | Bug | Unknown function silently defaults to `sum` in `_aggregate_grouped()`. |
| NAME-AGG-001 | Naming | `group_by` (snake_case list) vs Talend `GROUPBYS` (plural table) -- loses output-vs-input distinction. |
| NAME-AGG-002 | Naming | `operations` dict key naming vs Talend UPPER_CASE. |
| STD-AGG-002 | Standards | `print()` statements in converter violate STANDARDS.md logging requirements. |
| DBG-AGG-002 | Debug | Excessive diagnostic logging for sum operations in `_process()`. |
| DBG-AGG-003 | Debug | "SUM OPERATIONS FINAL VERIFICATION" banner-style logging. |
| DBG-AGG-004 | Debug | Excessive per-column logging in `_ensure_output_columns()`. |
| PERF-AGG-002 | Performance | Decimal precision lost in grouped path -- no Decimal-preserving groupby. |
| PERF-AGG-003 | Performance | `_ensure_output_columns()` expensive for wide DataFrames. |

### P3 -- Low

| ID | Category | Summary |
|----|----------|---------|
| CONV-AGG-009 | Converter | `CHECK_TYPE_OVERFLOW` not extracted (rarely needed). |
| CONV-AGG-010 | Converter | `CHECK_ULP` not extracted (rarely used). |
| ENG-AGG-010 | Engine | No `union` (geometry) function. |
| ENG-AGG-011 | Engine | `var`/`variance` and `median` are V1 extensions not in Talend. |
| NAME-AGG-003 | Naming | Multiple function name aliases create ambiguity. |
| STD-AGG-003 | Standards | Schema type format preserved correctly (no violation). |
| STD-AGG-004 | Standards | `{id}_ERROR_MESSAGE` not set in globalMap. |
| SEC-AGG-001 | Security | `print()` statements leak column names and schema details. |
| DBG-AGG-005 | Debug | Unicode checkmark characters may not render in all log sinks. |
| PERF-AGG-004 | Performance | Diagnostic logging computes test sums before actual aggregation. |
| STD-AGG-005 | Standards | Indentation anomaly at lines 450-451. Comment and `if` statement appear at different indentation level than preceding block. Functionally harmless but confusing for maintenance. |

### Issue Count Summary

| Priority | Count | Categories |
|----------|-------|------------|
| P0 | 8 | 5 bugs (3 engine, 2 cross-cutting), 1 converter, 1 engine, 1 testing |
| P1 | 13 | 3 converter, 4 engine, 2 bugs, 1 debug, 1 standards, 1 performance, 1 testing |
| P2 | 17 | 4 converter, 3 engine, 2 bugs, 2 naming, 1 standards, 3 debug, 2 performance |
| P3 | 11 | 2 converter, 2 engine, 1 naming, 3 standards, 1 security, 1 debug, 1 performance |
| **Total** | **49** | |

---

## 10. Recommendations

### Immediate (Before Production)

1. **Fix `output_column` handling in `_aggregate_grouped()`** (BUG-AGG-001): Change all `target_col = input_col` assignments to `target_col = output_col`. After `df.groupby()[input_col].sum().reset_index()`, rename the result column from `input_col` to `output_col` before merging:
   ```python
   agg_result = df.groupby(valid_group_by)[input_col].sum().reset_index()
   if output_col != input_col:
       agg_result = agg_result.rename(columns={input_col: output_col})
   target_col = output_col
   ```
   This must be done for ALL 13 operation branches. **Impact**: Fixes column renaming for all grouped aggregations. **Risk**: Medium -- must verify all downstream column references still work.

2. **Fix `_update_global_map()` bug** (BUG-AGG-002): Change `value` to `stat_value` on `base_component.py` line 304, or remove the stale `{stat_name}: {value}` references entirely. **Impact**: Fixes ALL components (cross-cutting). **Risk**: Very low (log message only).

3. **Fix `GlobalMap.get()` bug** (BUG-AGG-003): Add `default: Any = None` parameter to the `get()` method signature in `global_map.py` line 26. **Impact**: Fixes ALL components and any code using `global_map.get()`. **Risk**: Very low (adds optional parameter with backward-compatible default).

4. **Add function name mapping in converter** (CONV-AGG-001, CONV-AGG-002): In `parse_aggregate()`, after extracting the function name, apply a mapping:
   ```python
   FUNCTION_MAP = {
       'distinct': 'count_distinct',
       'std_dev': 'std',
       'population_std_dev': 'population_std',  # or implement
   }
   function_name = FUNCTION_MAP.get(function_name, function_name)
   ```
   **Impact**: Fixes silent wrong results for `distinct` and `std_dev` functions. **Risk**: Low.

5. **Create unit test suite** (TEST-AGG-001): Implement at minimum the 8 P0 test cases listed in Section 8.2. These cover: basic grouped sum/count, no-group-by, output column renaming, multiple operations, empty input, statistics, and Talend function name `distinct`. **Impact**: Verifies core aggregation logic. **Risk**: None.

6. **Remove `print()` statements** (CONV-AGG-004, DBG-AGG-001): Replace the 3 `print()` calls in `parse_aggregate()` (lines 720, 721, 737) with `logger.debug()`:
   ```python
   logger.debug(f"[parse_aggregate] Parsed group_by columns: {group_by}")
   logger.debug(f"[parse_aggregate] Parsed operations: {operations}")
   logger.debug(f"[parse_aggregate] Parsed output schema: {output_schema}")
   ```
   **Impact**: Fixes STANDARDS.md violation and prevents production stdout pollution. **Risk**: Very low.

### Short-Term (Hardening)

7. **Implement `ignore_null` support** (ENG-AGG-002): In both `_apply_agg_function()` and `_aggregate_grouped()`, check `op.get('ignore_null', False)`:
   ```python
   ignore_null = op.get('ignore_null', False)
   if ignore_null:
       series = series.dropna()
   ```
   For grouped mode, use `.apply()` with the filter:
   ```python
   if ignore_null:
       agg_result = df.groupby(valid_group_by)[input_col].apply(
           lambda x: x.dropna().sum()
       ).reset_index()
   else:
       agg_result = df.groupby(valid_group_by)[input_col].sum().reset_index()
   ```
   **Impact**: Enables correct null handling per operation. **Risk**: Medium -- needs careful testing.

8. **Fix Decimal precision in grouped aggregation** (ENG-AGG-004): Replace `df.groupby()[col].sum()` with a Decimal-preserving path:
   ```python
   if self._is_decimal_column(df[input_col]):
       agg_result = df.groupby(valid_group_by)[input_col].apply(
           lambda x: sum(x.dropna(), Decimal('0'))
       ).reset_index()
   else:
       agg_result = df.groupby(valid_group_by)[input_col].sum().reset_index()
   ```
   **Impact**: Preserves financial precision in grouped sums. **Risk**: Low -- performance impact for large datasets.

9. **Fix `list` function to return delimited string** (ENG-AGG-005): Change the grouped `list` path from `apply(list)` to `apply(lambda x: delimiter.join(x.astype(str)))`:
   ```python
   elif function == 'list':
       delimiter = op.get('delimiter', self.DEFAULT_DELIMITER)
       agg_result = df.groupby(valid_group_by)[input_col].apply(
           lambda x: delimiter.join(x.astype(str))
       ).reset_index()
   ```
   **Impact**: Matches Talend behavior. **Risk**: Low -- changes output type from list to string.

10. **Wire up `_validate_config()`** (BUG-AGG-004, STD-AGG-001): Add call at beginning of `_process()`:
    ```python
    errors = self._validate_config()
    if errors:
        for err in errors:
            logger.error(f"[{self.id}] Config validation: {err}")
        raise ComponentExecutionError(self.id, f"Invalid config: {'; '.join(errors)}")
    ```
    **Impact**: Catches invalid configurations early. **Risk**: Low -- may surface previously hidden config issues.

11. **Extract GROUPBYS.OUTPUT_COLUMN in converter** (CONV-AGG-003): Modify `parse_aggregate()` to extract both OUTPUT_COLUMN and INPUT_COLUMN for GROUPBYS, storing as list of dicts:
    ```python
    group_by_mappings = []
    for table in node.findall('.//elementParameter[@name="GROUPBYS"]'):
        output_col = None
        input_col = None
        for elem in table.findall('./elementValue'):
            ref = elem.get('elementRef')
            val = elem.get('value', '')
            if ref == 'OUTPUT_COLUMN':
                output_col = val
            elif ref == 'INPUT_COLUMN':
                input_col = val
        if input_col:
            group_by_mappings.append({
                'output_column': output_col or input_col,
                'input_column': input_col
            })
    ```
    Then update engine to handle both list-of-strings (backward compatible) and list-of-dicts (new format) for `group_by`.

12. **Implement single-pass aggregation** (PERF-AGG-001): Replace the per-operation merge loop with a single `groupby().agg()` call:
    ```python
    agg_dict = {}
    rename_map = {}
    for op in operations:
        input_col = op.get('input_column')
        output_col = op.get('output_column', input_col)
        function = op.get('function', 'sum').lower()
        pandas_func = self._map_to_pandas_func(function)
        agg_dict[input_col] = agg_dict.get(input_col, [])
        agg_dict[input_col].append(pandas_func)
        rename_map[(input_col, pandas_func)] = output_col

    result = df.groupby(valid_group_by).agg(agg_dict)
    result.columns = [rename_map.get(col, col[0]) for col in result.columns]
    result = result.reset_index()
    ```
    **Impact**: Significant performance improvement for multi-operation aggregations. **Risk**: Medium -- needs careful column naming.

### Long-Term (Optimization)

13. **Implement REJECT flow** (ENG-AGG-003): Wrap each group's aggregation in try/except. Capture failed groups as reject rows with `errorCode` and `errorMessage`. Return `{'main': good_df, 'reject': reject_df}` from `_process()`.

14. **Add `list_object` support** (ENG-AGG-008): Implement as `apply(list)` (returns Python list objects). Differentiate from `list` which returns delimited string.

15. **Add `population_std_dev` support** (ENG-AGG-009): Implement as `std(ddof=0)` instead of `std(ddof=1)`.

16. **Set `{id}_ERROR_MESSAGE` in globalMap** (STD-AGG-004): In error handlers, call `self.global_map.put(f"{self.id}_ERROR_MESSAGE", str(e))`.

17. **Extract `LIST_DELIMITER` in converter** (CONV-AGG-006): Add extraction for `LIST_DELIMITER` parameter. Store in config as `list_delimiter`. Engine should use `op.get('delimiter', self.config.get('list_delimiter', self.DEFAULT_DELIMITER))`.

18. **Extract `USE_FINANCIAL_PRECISION` in converter** (CONV-AGG-007): Add extraction. Store as `use_financial_precision` boolean in config. Engine should only use Decimal path when this flag is true.

19. **Clean up diagnostic logging** (DBG-AGG-002, DBG-AGG-003, DBG-AGG-004): Move all diagnostic logging to DEBUG level. Remove banner-style formatting. Remove test-sum computation.

20. **Fix `_ensure_output_columns` destructive behavior** (BUG-AGG-005): Remove the `else` clause that sets non-operation columns to None (lines 300-302). Non-operation columns should either be excluded from the output entirely (Talend behavior) or left as-is.

---

## Appendix A: Converter Parser Code

```python
# component_parser.py lines 683-742
def parse_aggregate(self, node, component: Dict) -> Dict:
    """
    Parse tAggregateRow component from Talend XML node.
    Extracts GROUPBYS and OPERATIONS tables and builds output schema.
    Maps to ETL-AGENT AggregateRow config format.
    """

    # Parse GROUPBYS
    group_by = []
    for table in node.findall('.//elementParameter[@name="GROUPBYS"]'):
        for elem in table.findall('./elementValue'):
            if elem.get('elementRef') == 'INPUT_COLUMN':
                group_by.append(elem.get('value', ''))

    # Parse OPERATIONS
    operations = []
    for table in node.findall('.//elementParameter[@name="OPERATIONS"]'):
        elems = list(table.findall('.//elementValue'))
        # Each operation is a group of 4: OUTPUT_COLUMN, INPUT_COLUMN, FUNCTION, IGNORE_NULL
        for i in range(0, len(elems), 4):
            op = {}
            for j in range(4):
                if i + j < len(elems):
                    ref = elems[i + j].get('elementRef')
                    val = elems[i + j].get('value', '')
                    if ref == 'OUTPUT_COLUMN':
                        op['output_column'] = val
                    elif ref == 'INPUT_COLUMN':
                        op['input_column'] = val
                    elif ref == 'FUNCTION':
                        op['function'] = val
                    elif ref == 'IGNORE_NULL':
                        op['ignore_null'] = val.lower() == 'true'
            if op:
                operations.append(op)

    # --- DEBUG: Log group_by and operations parsing ---
    print(f"[parse_aggregate] Parsed group_by columns: {group_by}")
    print(f"[parse_aggregate] Parsed operations: {operations}")

    # Build output schema from metadata
    output_schema = []
    for metadata in node.findall('./metadata[@connector="FLOW"]'):
        for column in metadata.findall('./column'):
            output_schema.append({
                'name': column.get('name', ''),
                'type': column.get('type', 'id_String'),
                'nullable': column.get('nullable', 'true').lower() == 'true',
                'key': column.get('key', 'false').lower() == 'true',
                'length': int(column.get('length', -1)),
                'precision': int(column.get('precision', -1))
            })

    # --- DEBUG: Log output schema ---
    print(f"[parse_aggregate] Parsed output schema: {output_schema}")

    component['config']['group_by'] = group_by
    component['config']['operations'] = operations
    component['config']['output'] = output_schema
    return component
```

**Notes on this code**:
- Lines 691-695: GROUPBYS parsing only extracts `INPUT_COLUMN`, discarding `OUTPUT_COLUMN`. This means column renaming in the group-by key is lost.
- Lines 700-701: The comment "Each operation is a group of 4" documents the assumption, but doesn't validate it.
- Lines 702-717: Fixed-offset grouping. If element count is not divisible by 4, the last group may be incomplete. The `if i + j < len(elems)` guard prevents index errors but allows partial operations.
- Lines 720-721, 737: `print()` statements -- debug artifacts that must be removed.
- Lines 724-734: Schema extraction correctly preserves Talend type format (e.g., `id_String`).
- Line 739: `group_by` is stored as a flat list of column names, not as a list of `{output_column, input_column}` pairs.

---

## Appendix B: Engine Class Structure

```
AggregateRow (BaseComponent)
    Constants:
        DEFAULT_OPERATIONS = []
        DEFAULT_GROUP_BY = []
        DEFAULT_DELIMITER = ","
        SUPPORTED_FUNCTIONS = [
            'sum', 'count', 'count_distinct', 'avg', 'mean', 'min', 'max',
            'first', 'last', 'std', 'stddev', 'var', 'variance', 'median',
            'list', 'concat', 'concatenate'
        ]

    Methods:
        _validate_config() -> List[str]              # DEAD CODE -- never called
        _process(input_data) -> Dict[str, Any]       # Main entry point
        _aggregate_all(df, operations) -> DataFrame   # No group-by aggregation
        _aggregate_grouped(df, group_by, ops) -> DF   # Group-by aggregation
        _apply_agg_function(series, function, op)     # Single-series aggregation
        _is_decimal_column(series) -> bool            # Decimal type detection
        _ensure_output_columns(result, input, gb)     # Output column management
```

### Method Call Graph

```
execute()                         [base_component.py]
  -> _process(input_data)         [aggregate_row.py:115]
       -> _aggregate_all()        [if no group_by]
       |    -> _apply_agg_function()  [per operation]
       |
       -> _aggregate_grouped()    [if group_by present]
       |    -> [inline pandas groupby per operation]
       |    -> merge per operation
       |
       -> _ensure_output_columns() [always, after aggregation]
       -> _update_stats()          [base_component.py]
  -> _update_global_map()         [base_component.py -- has bug]
```

---

## Appendix C: Complete Talend Parameter to V1 Config Key Reference

| Talend Parameter | V1 Config Key | Status | Priority to Add |
|------------------|---------------|--------|-----------------|
| `GROUPBYS.INPUT_COLUMN` | `group_by` (list) | Mapped | -- |
| `GROUPBYS.OUTPUT_COLUMN` | -- | **Not Mapped** | P1 |
| `OPERATIONS.OUTPUT_COLUMN` | `operations[].output_column` | Mapped | -- |
| `OPERATIONS.FUNCTION` | `operations[].function` | Mapped (no name normalization) | P0 (add mapping) |
| `OPERATIONS.INPUT_COLUMN` | `operations[].input_column` | Mapped | -- |
| `OPERATIONS.IGNORE_NULL` | `operations[].ignore_null` | Mapped (converter) / **Ignored (engine)** | P1 (wire up in engine) |
| `LIST_DELIMITER` | -- | **Not Mapped** | P2 |
| `USE_FINANCIAL_PRECISION` | -- | **Not Mapped** | P2 |
| `CHECK_TYPE_OVERFLOW` | -- | **Not Mapped** | P3 |
| `CHECK_ULP` | -- | **Not Mapped** | P3 |
| `SCHEMA` | `output` (list of column defs) | Mapped | -- |
| `TSTATCATCHER_STATS` | -- | Not needed | -- (tStatCatcher rarely used) |
| `LABEL` | -- | Not needed | -- (cosmetic) |
| `PROPERTY_TYPE` | -- | Not needed | -- (always Built-In) |

---

## Appendix D: Function Name Mapping Reference

### Talend XML Values to V1 Engine Names

| Talend XML `FUNCTION` Value | V1 Engine Name(s) | Match? | Silent Fallback? | Fix |
|-----------------------------|-------------------|--------|-----------------|-----|
| `count` | `count` | Yes | No | -- |
| `distinct` | **Not matched** (expect `count_distinct`) | **No** | **Yes -- falls to `sum`** | Add mapping in converter |
| `min` | `min` | Yes | No | -- |
| `max` | `max` | Yes | No | -- |
| `avg` | `avg`, `mean` | Yes | No | -- |
| `sum` | `sum` | Yes | No | -- |
| `first` | `first` | Yes | No | -- |
| `last` | `last` | Yes | No | -- |
| `list` | `list` | Yes | No (but output type differs) | Fix output type |
| `list_object` | **Not supported** | **No** | **Yes -- falls to `sum`** | Implement or map |
| `std_dev` | **Not matched** (expect `std`, `stddev`) | **No** | **Yes -- falls to `sum`** | Add mapping in converter |
| `population_std_dev` | **Not supported** | **No** | **Yes -- falls to `sum`** | Implement with `ddof=0` |
| `union` | **Not supported** | **No** | **Yes -- falls to `sum`** | Low priority (geometry) |

### V1 Engine Extensions (Not in Talend)

| V1 Function Name | Description | Talend Equivalent |
|-------------------|-------------|-------------------|
| `mean` | Alias for `avg` | `avg` |
| `stddev` | Alias for `std` | `std_dev` |
| `var` / `variance` | Variance calculation | Not available |
| `median` | Median calculation | Not available (requires external routine) |
| `concat` / `concatenate` | Delimited string concatenation | `list` (with delimiter) |

---

## Appendix E: Detailed Code Analysis

### `_validate_config()` (Lines 80-113)

This method validates:
- `group_by` is a list (if present, defaults to `[]`)
- `operations` is a list (if present, defaults to `[]`)
- Each operation is a dictionary
- Each operation's `function` is in `SUPPORTED_FUNCTIONS`
- Non-count operations have `input_column`

**Not validated**: `output_column` presence, `ignore_null` type, `delimiter` type, column name existence in actual data.

**Critical**: This method is never called. Even if it were, it returns a list of error strings but no caller checks the list or raises exceptions.

### `_process()` (Lines 115-204)

The main processing method:
1. Handle empty/None input -- return empty DataFrame with stats (0, 0, 0)
2. Log input details (shape, columns)
3. **Diagnostic sum logging** (lines 141-158) -- logs data types, sample values, non-null counts, test sums for all sum operations
4. Get config: `group_by` and `operations`
5. Branch to `_aggregate_all()` (no group-by) or `_aggregate_grouped()` (with group-by)
6. **Final sum verification** (lines 175-184) -- banner-style logging for sum operation results
7. Call `_ensure_output_columns()` -- adds missing columns, reorders
8. Update stats and return
9. Catch-all exception handler raises `ComponentExecutionError`

**Observation**: Lines 141-184 contain ~40 lines of diagnostic code that serves no production purpose. This is development debugging that was not cleaned up.

### `_aggregate_all()` (Lines 206-230)

Non-grouped aggregation:
1. Iterates operations
2. For each operation, gets `input_col`, `output_col`, `function`
3. Calls `_apply_agg_function()` for each -- correctly uses `output_col` for result key
4. Returns single-row DataFrame

**Note**: This method correctly uses `output_col` for column naming, unlike `_aggregate_grouped()`.

### `_aggregate_grouped()` (Lines 409-543)

Grouped aggregation -- the most complex method:
1. Filter `group_by` columns to existing columns
2. Fall back to `_aggregate_all()` if no valid group-by columns
3. Create base result from unique group combinations: `df[valid_group_by].drop_duplicates()`
4. **Per-operation loop** (lines 437-539):
   a. Get `input_col`, `output_col`, `function`
   b. Skip if missing input column (non-count)
   c. Skip if input column not in DataFrame
   d. Branch on function name (13 branches)
   e. Each branch computes `agg_result` via `df.groupby().func().reset_index()`
   f. **ALL branches set `target_col = input_col`** (ignoring `output_col`) -- BUG-AGG-001
   g. Merge `agg_result` into `result_df` on group-by columns
5. Return completed result

**Critical bug**: Step 4f. The `output_col` variable is computed on line 440 but never assigned to `target_col` except for the `count` without-input-column case (line 469). All other operations produce columns named after the input column, not the output column.

**Performance concern**: Step 4g performs one merge per operation. For 10 operations, this is 10 merges. A single `groupby().agg()` call would be much more efficient.

### `_apply_agg_function()` (Lines 364-407)

Single-series aggregation for the non-grouped path:
- 12 if/elif branches covering all supported functions
- Decimal handling for `sum` only (lines 377-379)
- `list` returns `series.tolist()` (Python list, not string)
- `concat`/`concatenate` uses configurable delimiter with `.astype(str)`
- Unknown functions silently default to `sum` (line 407)

### `_is_decimal_column()` (Lines 346-362)

Checks if a series contains Decimal objects:
- Returns `False` for empty series
- Checks first non-null value for `isinstance(val, Decimal)`
- Used only in `_apply_agg_function()` for the `sum` path

### `_ensure_output_columns()` (Lines 232-344)

Ensures all expected columns are present in output and reorders them:
1. Compute `operation_output_columns` and `operation_input_columns` from config
2. Compute `meaningful_columns` = group-by + operation outputs + operation inputs
3. **Verify** operation columns exist in result (lines 269-278)
4. **Add missing input columns** (lines 281-302):
   - If column is in `meaningful_columns` and is an operation input: merge first values from grouped input
   - If column is NOT in `meaningful_columns`: **set to None** (destructive -- BUG-AGG-005)
5. **Reorder columns**: group-by first, then input columns (original order), then operation-only columns, then remaining
6. **Final verification**: log all operation columns and their values

**Observation**: This method is 112 lines long and contains extensive logging (18 log statements). It performs work that should largely be unnecessary if `_aggregate_grouped()` produced the correct output in the first place.

---

## Appendix F: Edge Case Analysis

### Edge Case 1: Empty input DataFrame

| Aspect | Detail |
|--------|--------|
| **Talend** | Returns 0 rows. NB_LINE=0, NB_LINE_OK=0. |
| **V1** | `_process()` line 128-131: Returns empty DataFrame with stats (0, 0, 0). |
| **Verdict** | CORRECT |

### Edge Case 2: No group-by columns specified

| Aspect | Detail |
|--------|--------|
| **Talend** | All rows aggregated into a single output row. |
| **V1** | `_process()` line 169-170: calls `_aggregate_all()` which returns single-row DataFrame. |
| **Verdict** | CORRECT |

### Edge Case 3: Group-by column not in input data

| Aspect | Detail |
|--------|--------|
| **Talend** | Error or empty result depending on configuration. |
| **V1** | `_aggregate_grouped()` line 423: filters to existing columns. If none valid, falls back to `_aggregate_all()` (line 427). Logs warning. |
| **Verdict** | ACCEPTABLE -- graceful degradation. Different from Talend error behavior but reasonable. |

### Edge Case 4: Operation input column not in input data

| Aspect | Detail |
|--------|--------|
| **Talend** | Error or null result depending on configuration and IGNORE_NULL. |
| **V1** | `_aggregate_grouped()` line 451-453: warns and skips operation. Column will be missing from result (added as None by `_ensure_output_columns()`). |
| **Verdict** | ACCEPTABLE -- graceful degradation with warning. |

### Edge Case 5: Output column name differs from input column name (grouped)

| Aspect | Detail |
|--------|--------|
| **Talend** | Output column gets the aggregated value with the specified output name. |
| **V1** | **BUG**: `_aggregate_grouped()` uses `target_col = input_col` for all operations. Output column name is ignored. Result column has the input column name instead of the output column name. |
| **Verdict** | **BROKEN** -- see BUG-AGG-001. |

### Edge Case 6: Output column name differs from input column name (non-grouped)

| Aspect | Detail |
|--------|--------|
| **Talend** | Output column gets the aggregated value with the specified output name. |
| **V1** | `_aggregate_all()` line 221: `output_col = op.get('output_column', input_col)`. Uses `output_col` as dict key on line 225. Correct. |
| **Verdict** | CORRECT |

### Edge Case 7: Null values in aggregation column with IGNORE_NULL=false

| Aspect | Detail |
|--------|--------|
| **Talend** | Null values participate in aggregation. For `sum`, null + 5 = null. For `count`, null values still counted (unless using count distinct). |
| **V1** | Engine ignores the `ignore_null` flag entirely. Pandas defaults apply: `sum()` skips NaN by default (`skipna=True`), so null + 5 = 5. This differs from Talend's IGNORE_NULL=false behavior where null propagates. |
| **Verdict** | **GAP** -- V1 always behaves as IGNORE_NULL=true. See ENG-AGG-002. |

### Edge Case 8: Null values in aggregation column with IGNORE_NULL=true

| Aspect | Detail |
|--------|--------|
| **Talend** | Null values excluded from aggregation. sum([5, null, 3]) = 8. |
| **V1** | Pandas defaults to skipna=True, so sum([5, NaN, 3]) = 8.0. Coincidentally matches Talend IGNORE_NULL=true behavior. |
| **Verdict** | CORRECT (by accident -- pandas defaults match IGNORE_NULL=true). |

### Edge Case 9: Decimal (BigDecimal) values in grouped sum

| Aspect | Detail |
|--------|--------|
| **Talend** | With USE_FINANCIAL_PRECISION=true (default), uses BigDecimal.add() for exact sum. |
| **V1** | `_aggregate_grouped()` line 458: `df.groupby()[col].sum()` -- pandas converts Decimal to float64, losing precision. The Decimal-preserving path in `_apply_agg_function()` (line 377-379) is only used in `_aggregate_all()`. |
| **Verdict** | **GAP** -- precision lost in grouped mode. See ENG-AGG-004. |

### Edge Case 10: Decimal values in non-grouped sum

| Aspect | Detail |
|--------|--------|
| **Talend** | Uses BigDecimal.add() for exact sum. |
| **V1** | `_apply_agg_function()` line 377-379: checks `isinstance(series.iloc[0], Decimal)` and uses `sum(series.dropna(), Decimal('0'))`. Preserves Decimal precision. |
| **Verdict** | CORRECT |

### Edge Case 11: `list` function output format

| Aspect | Detail |
|--------|--------|
| **Talend** | Returns delimited string: `"val1,val2,val3"`. Delimiter configurable via LIST_DELIMITER. |
| **V1** | Non-grouped: `_apply_agg_function()` returns `series.tolist()` -- Python list `['val1', 'val2', 'val3']`. Grouped: `df.groupby()[col].apply(list)` -- also Python list. |
| **Verdict** | **GAP** -- V1 returns Python list, Talend returns string. See ENG-AGG-005. |

### Edge Case 12: `count` without input column

| Aspect | Detail |
|--------|--------|
| **Talend** | Counts all rows per group (equivalent to COUNT(*)). |
| **V1** | Non-grouped: `_aggregate_all()` line 227-228: `result[output_col] = len(df)`. Correct. Grouped: `_aggregate_grouped()` line 467-469: `df.groupby().size().reset_index(name=output_col)`. Correct -- uses `output_col` for column name. |
| **Verdict** | CORRECT (and notably, this is the ONLY grouped operation that correctly uses `output_col`). |

### Edge Case 13: Multiple operations on same input column

| Aspect | Detail |
|--------|--------|
| **Talend** | Each operation produces a separate output column. `sum(amount)->total, avg(amount)->average` produces `total` and `average` columns. |
| **V1** | Non-grouped: Works correctly because `_aggregate_all()` uses `output_col` as dict key. Grouped: **BROKEN** because `target_col = input_col` for all operations. Both operations would try to create column `amount`, and the second merge would create `amount_x` and `amount_y` suffixes. |
| **Verdict** | **BROKEN in grouped mode** -- see BUG-AGG-001. Non-grouped mode is correct. |

### Edge Case 14: High-cardinality group-by (many unique groups)

| Aspect | Detail |
|--------|--------|
| **Talend** | Memory-intensive but handles via Java heap. |
| **V1** | Per-operation merge creates copies. With 100K groups and 10 operations, memory usage is approximately 10x the single-column result size. |
| **Verdict** | FUNCTIONAL but memory-intensive. See PERF-AGG-001. |

### Edge Case 15: `first`/`last` with null values in group

| Aspect | Detail |
|--------|--------|
| **Talend** | With IGNORE_NULL=false, `first` returns first value even if null. With IGNORE_NULL=true, returns first non-null. |
| **V1** | Non-grouped: `series.iloc[0]` returns first value regardless of null. Grouped: `pandas.groupby().first()` returns first NON-NULL value by default. |
| **Verdict** | **INCONSISTENT** -- non-grouped and grouped behave differently. Grouped path always behaves as IGNORE_NULL=true. See ENG-AGG-007. |

### Edge Case 16: Function name `distinct` from Talend XML

| Aspect | Detail |
|--------|--------|
| **Talend** | `distinct` in XML means count distinct. |
| **V1** | Engine receives `distinct`. Not in `SUPPORTED_FUNCTIONS`. `_validate_config()` would flag it (if called). `_apply_agg_function()` falls through all if/elif branches to `else: return series.sum()`. **Silently returns sum instead of count distinct.** |
| **Verdict** | **DATA CORRUPTION** -- see CONV-AGG-001. |

### Edge Case 17: Function name `std_dev` from Talend XML

| Aspect | Detail |
|--------|--------|
| **Talend** | `std_dev` in XML means sample standard deviation. |
| **V1** | Engine receives `std_dev`. Not in `SUPPORTED_FUNCTIONS` (engine expects `std` or `stddev`). Falls through to `sum`. **Silently returns sum instead of standard deviation.** |
| **Verdict** | **DATA CORRUPTION** -- see CONV-AGG-002. |

---

## Appendix G: Cross-Cutting Issues

The following issues were discovered during this audit but affect the entire v1 engine, not just `AggregateRow`:

| ID | Priority | Component | Issue |
|----|----------|-----------|-------|
| BUG-AGG-002 | **P0** | `base_component.py:304` | `_update_global_map()` references undefined `value` variable. Will crash ALL components when `global_map` is set. |
| BUG-AGG-003 | **P0** | `global_map.py:28` | `GlobalMap.get()` references undefined `default` parameter. Will crash on any `get()` call. `get_component_stat()` also passes two args to single-arg `get()`. |
| BUG-AGG-004 | **P1** | `base_component.py` | `_validate_config()` is defined in child components but never called. ALL components with validation logic have dead validation. |

These should be tracked in a cross-cutting issues report as well.

---

## Appendix H: Implementation Fix Guides

### Fix Guide: BUG-AGG-001 -- `output_column` ignored in grouped aggregation

**File**: `src/v1/engine/components/aggregate/aggregate_row.py`
**Lines**: 457-522 (all operation branches in `_aggregate_grouped()`)

**Current code (broken)** -- example for `sum`:
```python
if function == 'sum':
    agg_result = df.groupby(valid_group_by)[input_col].sum().reset_index()
    target_col = input_col  # <-- BUG: should be output_col
```

**Fix**:
```python
if function == 'sum':
    agg_result = df.groupby(valid_group_by)[input_col].sum().reset_index()
    if output_col != input_col:
        agg_result = agg_result.rename(columns={input_col: output_col})
    target_col = output_col
```

**Apply this pattern to ALL 13 operation branches** (sum, count, count_distinct, avg/mean, min, max, std/stddev, var/variance, median, first, last, list, concat/concatenate, and the default else clause).

**Impact**: Fixes column renaming for ALL grouped aggregation operations. **Risk**: Medium -- must verify downstream column references. Some jobs may have adapted to the broken behavior by using `input_column` as the expected output name.

**Test**: Create test with `input_column='amount', output_column='total_amount'`. Verify output DataFrame has column `total_amount`, not `amount`.

---

### Fix Guide: BUG-AGG-002 -- `_update_global_map()` undefined variable

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

**Impact**: Fixes ALL components (cross-cutting). **Risk**: Very low (log message only).

---

### Fix Guide: BUG-AGG-003 -- `GlobalMap.get()` undefined default

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

### Fix Guide: CONV-AGG-001 -- Function name mapping

**File**: `src/converters/complex_converter/component_parser.py`
**Location**: Inside `parse_aggregate()`, after line 713

**Add function name mapping after extraction**:
```python
# After extracting function name
if ref == 'FUNCTION':
    # Map Talend XML function names to V1 engine names
    TALEND_FUNCTION_MAP = {
        'distinct': 'count_distinct',
        'std_dev': 'std',
        'population_std_dev': 'population_std',
    }
    val = TALEND_FUNCTION_MAP.get(val, val)
    op['function'] = val
```

**Impact**: Fixes silent wrong results for `distinct` and `std_dev`. **Risk**: Low.

---

### Fix Guide: CONV-AGG-004 -- Replace print() with logger

**File**: `src/converters/complex_converter/component_parser.py`
**Lines**: 720-721, 737

**Current**:
```python
print(f"[parse_aggregate] Parsed group_by columns: {group_by}")
print(f"[parse_aggregate] Parsed operations: {operations}")
# ...
print(f"[parse_aggregate] Parsed output schema: {output_schema}")
```

**Fix**:
```python
logger.debug(f"[parse_aggregate] Parsed group_by columns: {group_by}")
logger.debug(f"[parse_aggregate] Parsed operations: {operations}")
# ...
logger.debug(f"[parse_aggregate] Parsed output schema: {output_schema}")
```

**Note**: Ensure `logger = logging.getLogger(__name__)` is defined at module level in `component_parser.py`. If not, add `import logging` and `logger = logging.getLogger(__name__)`.

---

### Fix Guide: ENG-AGG-002 -- Implement ignore_null

**File**: `src/v1/engine/components/aggregate/aggregate_row.py`

**Step 1**: In `_apply_agg_function()`, add null filtering:
```python
def _apply_agg_function(self, series: pd.Series, function: str, op: Dict) -> Any:
    ignore_null = op.get('ignore_null', False)
    if ignore_null:
        series = series.dropna()
    # ... rest of function unchanged
```

**Step 2**: In `_aggregate_grouped()`, add null filtering per operation:
```python
# Before each groupby operation
ignore_null = op.get('ignore_null', False)

if function == 'sum':
    if ignore_null:
        agg_result = df.groupby(valid_group_by)[input_col].apply(
            lambda x: x.dropna().sum()
        ).reset_index()
    else:
        # When IGNORE_NULL=false and any null exists, result should be null
        def sum_with_null(x):
            if x.isna().any():
                return None
            return x.sum()
        agg_result = df.groupby(valid_group_by)[input_col].apply(
            sum_with_null
        ).reset_index()
```

**Impact**: Enables correct per-operation null handling. **Risk**: Medium -- changes default behavior from "always ignore nulls" to "respect IGNORE_NULL flag."

---

### Fix Guide: ENG-AGG-005 -- Fix list function output type

**File**: `src/v1/engine/components/aggregate/aggregate_row.py`

**Non-grouped** (in `_apply_agg_function()`):
```python
elif function == 'list':
    delimiter = op.get('delimiter', self.DEFAULT_DELIMITER)
    return delimiter.join(series.astype(str))
```

**Grouped** (in `_aggregate_grouped()`):
```python
elif function == 'list':
    delimiter = op.get('delimiter', self.DEFAULT_DELIMITER)
    agg_result = df.groupby(valid_group_by)[input_col].apply(
        lambda x: delimiter.join(x.astype(str))
    ).reset_index()
    target_col = output_col  # Also fix BUG-AGG-001
```

**Impact**: Matches Talend behavior (delimited string output). **Risk**: Low -- changes output type.

---

## Appendix I: Comparison with Related V1 Aggregate Components

| Feature | tAggregateRow (V1) | tAggregateSortedRow (V1) |
|---------|---------------------|--------------------------|
| Group-by | Yes | Yes |
| Sum/Count/Avg/Min/Max | Yes | Yes |
| First/Last | Yes | Yes |
| Count Distinct | Yes | Yes |
| List (delimited) | Partial (returns Python list) | Unknown |
| Std Dev | Yes (sample only) | Yes |
| Ignore Null | Extracted but not used | Unknown |
| Output column renaming (grouped) | **Broken** | Unknown |
| Decimal precision (grouped) | **Lost** | Unknown |
| Financial precision toggle | **No** | No |
| REJECT flow | **No** | **No** |
| V1 Unit tests | **No** | **No** |
| Debug print() in converter | **Yes (3 statements)** | **Yes (2 statements)** |

**Observation**: The `output_column` bug (BUG-AGG-001), missing `ignore_null` implementation, debug `print()` statements, and lack of v1 unit tests appear to be systemic issues across aggregate components, not isolated to `tAggregateRow`. The converter's `parse_t_aggregate_sorted_row()` method (lines 2132-2179 of `component_parser.py`) also contains `print()` statements (lines 2178-2179).

---

## Appendix J: Risk Assessment for Production Migration

### High-Risk Scenarios

| Scenario | Risk Level | Affected Jobs | Mitigation |
|----------|-----------|---------------|------------|
| Jobs using output column renaming in operations | **Critical** | Any job where OUTPUT_COLUMN != INPUT_COLUMN in OPERATIONS table | Must fix BUG-AGG-001 before migrating |
| Jobs using `distinct` function | **Critical** | Any job with count_distinct operations | Must add function name mapping (CONV-AGG-001) |
| Jobs using `std_dev` function | **High** | Any job with standard deviation operations | Must add function name mapping (CONV-AGG-002) |
| Jobs relying on IGNORE_NULL=false | **High** | Jobs where null propagation matters | Must implement ignore_null (ENG-AGG-002) |
| Jobs with BigDecimal/financial precision in grouped sums | **High** | Financial calculations with group-by | Must fix Decimal handling (ENG-AGG-004) |
| Jobs using `list` function expecting string output | **High** | Jobs where list output is processed downstream as string | Must fix list output type (ENG-AGG-005) |
| Jobs using group-by with column renaming | **Medium** | Jobs where GROUPBYS OUTPUT_COLUMN != INPUT_COLUMN | Must extract GROUPBYS.OUTPUT_COLUMN (CONV-AGG-003) |
| Jobs using REJECT flow | **Medium** | Jobs with data quality checks on aggregation | Must implement REJECT flow (ENG-AGG-003) |
| Jobs using custom LIST_DELIMITER | **Medium** | Jobs with non-comma list delimiters | Must extract LIST_DELIMITER (CONV-AGG-006) |

### Low-Risk Scenarios

| Scenario | Risk Level | Notes |
|----------|-----------|-------|
| Jobs using simple sum/count/min/max with same column names | Low | Core functions work correctly when output_col == input_col |
| Jobs without group-by | Low | `_aggregate_all()` works correctly including column renaming |
| Jobs using `count` without input column | Low | Only grouped operation that correctly uses output_col |
| Jobs using `list_object` function | Low | Rare in practice |
| Jobs using `union` (geometry) | Very Low | Extremely rare |
| Jobs using CHECK_TYPE_OVERFLOW / CHECK_ULP | Very Low | Rarely enabled |

### Recommended Migration Strategy

1. **Phase 1**: Fix all P0 bugs (BUG-AGG-001, BUG-AGG-002, BUG-AGG-003, CONV-AGG-001). Add function name mapping in converter. These are blocking issues for ANY production use.
2. **Phase 2**: Audit each target job's Talend configuration. Identify which features are used: output column renaming, IGNORE_NULL, BigDecimal, list function, std_dev, distinct.
3. **Phase 3**: Implement P1 features required by target jobs (ignore_null, Decimal precision, list output format, REJECT flow).
4. **Phase 4**: Create unit tests covering at minimum the 8 P0 test cases and 13 P1 test cases.
5. **Phase 5**: Parallel-run migrated jobs against Talend originals. Compare output row-for-row, column-for-column, verifying column names, values, types, and row counts.
6. **Phase 6**: Fix any differences found in parallel-run testing.

---

## Appendix K: _aggregate_grouped() Target Column Assignment Analysis

This appendix documents the `target_col` assignment for each operation branch in `_aggregate_grouped()`, demonstrating the scope of BUG-AGG-001.

| Line | Function | `target_col` Assignment | Correct Value | Bug? |
|------|----------|------------------------|---------------|------|
| 460 | `sum` | `target_col = input_col` | `output_col` | **Yes** |
| 465 | `count` (with input) | `target_col = input_col` | `output_col` | **Yes** |
| 469 | `count` (without input) | `target_col = output_col` | `output_col` | No |
| 473 | `count_distinct` | `target_col = input_col` | `output_col` | **Yes** |
| 477 | `avg`/`mean` | `target_col = input_col` | `output_col` | **Yes** |
| 481 | `min` | `target_col = input_col` | `output_col` | **Yes** |
| 485 | `max` | `target_col = input_col` | `output_col` | **Yes** |
| 489 | `std`/`stddev` | `target_col = input_col` | `output_col` | **Yes** |
| 493 | `var`/`variance` | `target_col = input_col` | `output_col` | **Yes** |
| 497 | `median` | `target_col = input_col` | `output_col` | **Yes** |
| 501 | `first` | `target_col = input_col` | `output_col` | **Yes** |
| 505 | `last` | `target_col = input_col` | `output_col` | **Yes** |
| 509 | `list` | `target_col = input_col` | `output_col` | **Yes** |
| 516 | `concat`/`concatenate` | `target_col = input_col` | `output_col` | **Yes** |
| 522 | `else` (default sum) | `target_col = input_col` | `output_col` | **Yes** |

**Summary**: 14 out of 15 operation branches have the bug. Only `count` without input column (line 469) is correct.

---

## Appendix L: Supported Functions Comparison

### V1 SUPPORTED_FUNCTIONS List (aggregate_row.py line 74-78)

```python
SUPPORTED_FUNCTIONS = [
    'sum', 'count', 'count_distinct', 'avg', 'mean', 'min', 'max',
    'first', 'last', 'std', 'stddev', 'var', 'variance', 'median',
    'list', 'concat', 'concatenate'
]
```

**Total**: 17 function names (including aliases)

### Talend Documented Functions (from official docs)

```
count, distinct, min, max, avg, sum, first, last,
list, list_object, std_dev, population_std_dev, union
```

**Total**: 13 function names

### Coverage Matrix

| Category | Talend Functions | V1 Functions | Coverage |
|----------|-----------------|--------------|----------|
| Counting | `count`, `distinct` | `count`, `count_distinct` | 2/2 (name mismatch for `distinct`) |
| Aggregation | `sum`, `avg`, `min`, `max` | `sum`, `avg`/`mean`, `min`, `max` | 4/4 |
| Selection | `first`, `last` | `first`, `last` | 2/2 |
| Collection | `list`, `list_object` | `list`, `concat`/`concatenate` | 1/2 (`list_object` missing) |
| Statistics | `std_dev`, `population_std_dev` | `std`/`stddev`, `var`/`variance`, `median` | 1/2 (`population_std_dev` missing, V1 adds extras) |
| Geometry | `union` | -- | 0/1 |
| **Total** | **13** | **17** | **10/13 (77%)** with 3 name mismatches and 3 missing |

### Functions Missing from V1

| Function | Difficulty to Implement | Priority |
|----------|------------------------|----------|
| `list_object` | Low -- `apply(list)` returns Python list | P2 |
| `population_std_dev` | Low -- `std(ddof=0)` | P2 |
| `union` (geometry) | High -- requires geometry library | P3 |

### V1-Only Functions (Extensions)

| Function | Description | Risk |
|----------|-------------|------|
| `mean` | Alias for `avg` | None (convenience alias) |
| `stddev` | Alias for `std` | None (convenience alias) |
| `var`/`variance` | Variance calculation | None (useful extension) |
| `median` | Median calculation | None (useful extension) |
| `concat`/`concatenate` | String concatenation with delimiter | None (similar to `list` but returns string) |

---
