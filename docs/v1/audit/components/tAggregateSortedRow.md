# Audit Report: tAggregateSortedRow / AggregateSortedRow

## Component Identity

| Field | Value |
|-------|-------|
| **Talend Name** | `tAggregateSortedRow` |
| **V1 Engine Class** | `AggregateSortedRow` |
| **Engine File** | `src/v1/engine/components/transform/aggregate_sorted_row.py` |
| **Converter Parser** | `component_parser.py` -> `parse_t_aggregate_sorted_row()` (line ~2132) |
| **Converter Dispatch** | `converter.py` line ~339 |
| **Registry Aliases** | `TAggregateSortedRow`, `tAggregateSortedRow`, `AggregateSortedRow` |
| **Category** | Transform / Aggregation |
| **Complexity** | Medium-High -- sorted-input aggregation with multiple function support |
| **Talend Family** | Processing |
| **Issue ID Prefix** | `{CATEGORY}-ASR-{NUMBER}` |

---

## Scorecard

| Dimension | Score | P0 | P1 | P2 | P3 |
|-----------|-------|----|----|----|----|
| Converter Coverage | Y | 0 | 2 | 2 | 1 |
| Engine Feature Parity | R | 2 | 4 | 3 | 1 |
| Code Quality | Y | 1 | 3 | 4 | 2 |
| Performance & Memory | R | 1 | 1 | 2 | 0 |
| Testing | R | 1 | 1 | 0 | 0 |

**Legend**: R = Red (critical gaps), Y = Yellow (notable gaps), G = Green (production-ready)

---

## 1. Talend Feature Baseline

### What tAggregateSortedRow Does in Talend

The `tAggregateSortedRow` component belongs to the **Processing** family in Talend Studio.
It aggregates **pre-sorted** input data for output columns based on a configurable set of
grouping keys and aggregation operations. It is functionally similar to `tAggregateRow` but
with a critical architectural distinction: it is designed to work on data that has already
been sorted by the group-by columns (typically via an upstream `tSortRow`).

### Key Difference from tAggregateRow

The fundamental distinction between `tAggregateSortedRow` and `tAggregateRow` is their
memory model and processing strategy:

| Characteristic | tAggregateRow | tAggregateSortedRow |
|----------------|---------------|---------------------|
| **Input requirement** | Any order | Must be pre-sorted by group-by columns |
| **Memory model** | Buffers ALL data in memory (HashMap of groups) | Streaming / no buffer -- processes one group at a time |
| **Performance** | Slower for large datasets due to full buffering | Faster -- O(1) memory per group since groups arrive contiguously |
| **Result ordering** | Unordered (HashMap iteration) | Preserves sort order from input |
| **Row count property** | Not required | `ROW_COUNT` -- total input rows (used for progress/optimization) |
| **Use case** | Small-to-medium datasets, unsorted input | Large datasets where memory is a concern; always paired with tSortRow |
| **Failure mode** | None (handles any order) | Produces INCORRECT results if input is not sorted -- groups get split |

In production Talend jobs, the typical pattern is:

```
tSortRow (sort by group-by columns) --> tAggregateSortedRow (aggregate)
```

This pattern is preferred for large datasets because `tAggregateSortedRow` does not need
to hold the entire dataset in memory. It can emit aggregated rows as soon as it detects a
group boundary (i.e., when the group-by key values change between consecutive rows).

If input data is NOT sorted, `tAggregateSortedRow` will treat each contiguous run of
identical group keys as a separate group, producing duplicate/split group output rows
with partial aggregation results. This is a silent data-corruption scenario.

### Basic Settings (Talend Studio)

| Parameter | Talend Name | Type | Description |
|-----------|-------------|------|-------------|
| Schema | `SCHEMA` | Schema editor | Output column definitions with types |
| Group By | `GROUPBYS` | Table (INPUT_COLUMN) | List of columns to group by; rows with same values in these columns are aggregated together |
| Operations | `OPERATIONS` | Table (OUTPUT_COLUMN, INPUT_COLUMN, FUNCTION, IGNORE_NULL) | Aggregation operations to perform |
| Row Count | `ROW_COUNT` | Expression (Integer) | Total number of input rows -- used for progress tracking and optimization |

### Advanced Settings (Talend Studio)

| Parameter | Talend Name | Type | Description |
|-----------|-------------|------|-------------|
| Connection Format | `CONNECTION_FORMAT` | List | Connection format: `row` (default) |
| Die On Error | `DIE_ON_ERROR` | Boolean | Whether to stop the job on processing errors |

### Supported Aggregation Functions

| Function | Description | Null Handling |
|----------|-------------|---------------|
| `sum` | Sum of values | Ignores nulls (when IGNORE_NULL=true) |
| `count` | Count of rows | Counts all rows (or non-null if IGNORE_NULL) |
| `min` | Minimum value | Ignores nulls |
| `max` | Maximum value | Ignores nulls |
| `avg` | Average (mean) | Ignores nulls |
| `first` | First value in group | N/A |
| `last` | Last value in group | N/A |
| `list` | Collect values into Java List | Optionally ignores nulls |
| `count_distinct` | Count of unique values | Ignores nulls |
| `std_dev` | Standard deviation | Ignores nulls |
| `median` | Median value | Ignores nulls |

### IGNORE_NULL Behavior

When `IGNORE_NULL` is set to `true` for an operation in Talend:
- Null values in the input column are excluded from the aggregation computation
- For `count`, only non-null values are counted
- For `sum`, `avg`, `min`, `max`, nulls are excluded from calculation
- For `list`, null values are omitted from the collected list
- For `first`/`last`, the first/last non-null value is returned

When `IGNORE_NULL` is `false`:
- Nulls participate in the aggregation (may produce null results for some functions)

### Connection Types

| Connector | Type | Direction | Description |
|-----------|------|-----------|-------------|
| `FLOW` (Main) | Row | Input | Sorted input data flow -- MUST be sorted by group-by columns |
| `FLOW` (Main) | Row | Output | Aggregated output rows, one per unique group |
| `REJECT` | Row | Output | Rows that failed aggregation (with errorCode, errorMessage) |

### GlobalMap Variables Produced (Talend)

| Key | Type | Description |
|-----|------|-------------|
| `{id}_NB_LINE` | int | Total number of input rows processed |
| `{id}_NB_LINE_OK` | int | Number of successfully aggregated output rows |
| `{id}_NB_LINE_REJECT` | int | Number of rejected rows |

### Talend Behavioral Notes

1. **Pre-sorted input is MANDATORY**: If input is not sorted by group-by columns, the
   component produces incorrect results (split groups). Talend does NOT validate this
   at design time -- it is the developer's responsibility to ensure upstream sorting.

2. **Streaming semantics**: Internally, Talend's Java implementation processes rows one
   at a time, accumulating aggregation state. When it detects a change in the group-by
   key values (comparing current row to previous row), it emits the completed group and
   starts a new accumulator. This means it holds at most ONE group's data in memory.

3. **ROW_COUNT**: This property tells the component the total number of input rows. It
   is used for progress bar calculations and may be used for internal buffer sizing. It
   does NOT limit the number of rows processed.

4. **REJECT flow**: When connected, rows that cause errors during aggregation (e.g., type
   mismatches, overflow) are routed to the reject flow with `errorCode` and `errorMessage`
   columns appended. When not connected, errors either cause job failure (DIE_ON_ERROR=true)
   or are silently dropped.

5. **Empty group-by**: If no group-by columns are specified, the entire input is treated as
   one group, producing a single output row.

6. **Type preservation**: Talend preserves the output schema types. For example, if the
   output column is typed as `BigDecimal`, the aggregation result is cast to `BigDecimal`.

---

## 2. Converter Audit

### Parser Method: `parse_t_aggregate_sorted_row()`

**Location**: `src/converters/complex_converter/component_parser.py`, lines 2132-2199

The converter parser is dispatched from `converter.py` line ~339:
```python
elif component_type == 'tAggregateSortedRow':
    component = self.component_parser.parse_t_aggregate_sorted_row(node, component)
```

### Parameters Extracted

| Talend Parameter | Converter Extracts? | V1 Config Key | Notes |
|------------------|---------------------|---------------|-------|
| `GROUPBYS` (table) | Yes | `group_bys` | Extracts INPUT_COLUMN values from table rows |
| `OPERATIONS` (table) | Yes | `operations` | Groups every 4 elementValue entries; extracts OUTPUT_COLUMN, INPUT_COLUMN, FUNCTION, IGNORE_NULL |
| `ROW_COUNT` | Yes | `row_count` | Extracted but **not used** by engine |
| `CONNECTION_FORMAT` | Yes | `connection_format` | Extracted but **not used** by engine |
| `DIE_ON_ERROR` | **No** | -- | **Not extracted** -- other components extract this parameter |
| `SCHEMA` | Yes (partial) | `schema.output` | Extracts FLOW metadata: name, type, nullable, key, length, precision |

### Schema Extraction

| Attribute | Extracted? | Notes |
|-----------|-----------|-------|
| `name` | Yes | Column name from metadata |
| `type` | Yes | Raw Talend type (e.g., `id_String`) -- **not converted** to Python type |
| `nullable` | Yes | Boolean conversion |
| `key` | Yes | Boolean conversion |
| `length` | Yes | Integer conversion with default -1 |
| `precision` | Yes | Integer conversion with default -1 |
| `pattern` | **No** | Date pattern not extracted |
| `comment` | **No** | Column comment not extracted |
| `default` | **No** | Default value not extracted |

### Operations Parsing Analysis

The converter uses a fixed stride of 4 to group `elementValue` entries into operations:

```python
for i in range(0, len(elements), 4):
    op = {}
    for elem in elements[i:i+4]:
        ref = elem.get('elementRef')
        ...
```

**Risk**: This assumes Talend always emits exactly 4 `elementValue` entries per operation
(OUTPUT_COLUMN, INPUT_COLUMN, FUNCTION, IGNORE_NULL). If any future Talend version adds
or removes a field, or if optional fields are omitted, the stride-based parsing will
misalign all subsequent operations, producing silently wrong configurations.

### Converter Issues

| ID | Priority | Issue |
|----|----------|-------|
| CONV-ASR-001 | **P1** | `DIE_ON_ERROR` not extracted -- the engine's `die_on_error` config key will always be its default (`False`), meaning errors are silently swallowed even when the Talend job had `DIE_ON_ERROR=true`. Every other component parser in the codebase extracts this parameter. |
| CONV-ASR-002 | **P1** | Operations parsing uses hardcoded stride of 4 (`range(0, len(elements), 4)`). If any Talend version emits fewer or more elementValue entries per operation, all operations after the first will be misaligned. Should use a ref-based grouping strategy instead of positional stride. |
| CONV-ASR-003 | **P2** | Schema type not converted -- raw Talend types like `id_String`, `id_BigDecimal` are stored as-is. The engine does not appear to use the output schema for type coercion, so this is not immediately harmful, but it means the schema metadata is not usable for downstream validation. |
| CONV-ASR-004 | **P2** | `IGNORE_NULL` is extracted by the converter (`op['ignore_null']`) but the engine completely ignores it. The converter is doing extra work that has no downstream effect, and users who set IGNORE_NULL=false in Talend will not see the expected behavior. |
| CONV-ASR-005 | **P3** | Debug `print()` statements left in production code (lines 2178-2179). Should use `logger.debug()` instead of `print()`. |

---

## 3. Engine Feature Parity Audit

### Critical Architectural Finding: No Sorted-Input Optimization

**This is the most significant finding of this audit.**

The `AggregateSortedRow` engine class does NOT implement sorted-input streaming
aggregation. Instead, it uses `pandas.DataFrame.groupby()` which:

1. **Buffers all data in memory** (builds a hash-based grouping index)
2. **Does not require sorted input** (groupby works on any order)
3. **Does not detect or validate** that input is sorted
4. **Does not stream** -- it processes the entire DataFrame at once

This means `AggregateSortedRow` is functionally **identical** to `AggregateRow` in terms
of its processing model. The entire point of `tAggregateSortedRow` in Talend -- memory
efficiency through streaming aggregation of sorted data -- is completely absent.

**Evidence from source code** (`aggregate_sorted_row.py`):

- Line 150: `result_df = self._aggregate_grouped(input_data, group_bys, norm_ops)`
- Line 316: `grouped = df.groupby(valid_group_by, as_index=False).agg(agg_dict)`
- The word "sorted" only appears in docstrings and module comments, never in logic
- No pre-sort validation, no sort-order assertion, no streaming iteration
- No use of `row_count` or `connection_format` config values anywhere in processing logic

**Comparison with AggregateRow** (`src/v1/engine/components/aggregate/aggregate_row.py`):

Both classes use nearly identical approaches:
- Both inherit from `BaseComponent`
- Both use `pandas.groupby()` for aggregation
- Both support the same set of aggregation functions
- Both handle Decimal columns identically
- The primary differences are superficial: config key names (`group_bys` vs `group_by`),
  code organization style, and the presence of `_ensure_output_columns()` in AggregateRow

### Feature Implementation Status

| Talend Feature | Implemented? | Fidelity | Notes |
|----------------|-------------|----------|-------|
| Group-by aggregation | Yes | Medium | Works but uses hash-groupby, not sorted-streaming |
| Sum function | Yes | High | Includes Decimal precision handling |
| Count function | Yes | High | Supports count without input column |
| Min function | Yes | High | Via pandas min() |
| Max function | Yes | High | Via pandas max() |
| Avg/Mean function | Yes | High | Via pandas mean() |
| First function | Yes | Medium | Takes first value in group -- order depends on DataFrame order, not sort guarantee |
| Last function | Yes | Medium | Takes last value in group -- same order caveat |
| Count Distinct function | Yes | High | Via pandas nunique() |
| Std/StdDev function | Yes | High | Via pandas std() |
| Variance function | Yes | High | Via pandas var() |
| Median function | Yes | High | Via pandas median() |
| List function | Yes | High | Collects values into Python list |
| Concat/Concatenate function | Yes | High | Joins with configurable delimiter |
| **Pre-sorted input optimization** | **No** | **N/A** | **Core differentiator not implemented -- uses hash groupby like tAggregateRow** |
| **Sorted-input validation** | **No** | **N/A** | **No check that input is actually sorted by group-by columns** |
| **Streaming / O(1) memory per group** | **No** | **N/A** | **Entire DataFrame loaded into memory for groupby** |
| **IGNORE_NULL** | **No** | **N/A** | **Converter extracts it but engine ignores it entirely** |
| **ROW_COUNT usage** | **No** | **N/A** | **Extracted by converter, declared in docstring, never used in processing** |
| **CONNECTION_FORMAT usage** | **No** | **N/A** | **Extracted by converter, declared in docstring, never used** |
| **REJECT flow** | **No** | **N/A** | **No reject output -- errors either die or return original input** |
| **DIE_ON_ERROR** | Partial | Low | Engine checks `die_on_error` config but converter never sets it |
| **Empty group_bys (whole-table agg)** | Yes | High | Falls through to `_aggregate_all()` |
| **GlobalMap NB_LINE** | Yes | High | Via `_update_stats()` and base component |
| **GlobalMap NB_LINE_OK** | Yes | High | Set to output row count |
| **GlobalMap NB_LINE_REJECT** | Yes | High | Always 0 (no reject flow) |
| **Output column ordering** | Yes | Medium | Attempts to match input column order |
| **Non-operation columns set to null** | Yes | High | Columns not in group_by or operations are set to None |

### Behavioral Differences from Talend

| ID | Priority | Difference |
|----|----------|------------|
| ENG-ASR-001 | **P0** | **No sorted-input streaming aggregation**: The entire raison d'etre of tAggregateSortedRow is absent. The engine uses `pandas.groupby()` which buffers all data in memory via hash indexing. For large datasets (millions of rows), this defeats the purpose of choosing tAggregateSortedRow over tAggregateRow. A Talend job that uses tSortRow -> tAggregateSortedRow to handle a 10GB dataset will fail with OOM in the V1 engine. |
| ENG-ASR-002 | **P0** | **No sorted-input validation**: The engine does not verify that input data is sorted by the group-by columns. In Talend, unsorted input produces silently incorrect results (split groups). The engine's groupby approach "accidentally" handles unsorted input correctly, but this masks a configuration error -- if a user relies on this behavior, their job is non-portable back to Talend. |
| ENG-ASR-003 | **P1** | **IGNORE_NULL not implemented**: The converter extracts `ignore_null` per operation, but the engine never reads it. Pandas' default behavior is to ignore nulls for most aggregation functions (sum, mean, min, max), but this is not configurable. When a user explicitly sets `IGNORE_NULL=false` in Talend (meaning nulls should participate), the engine will still ignore nulls. |
| ENG-ASR-004 | **P1** | **No REJECT flow**: Talend's tAggregateSortedRow can route failed rows to a REJECT output with errorCode/errorMessage. The engine has no reject mechanism -- errors either raise an exception (if die_on_error) or silently return the original input data unchanged. |
| ENG-ASR-005 | **P1** | **ROW_COUNT ignored**: The engine declares `row_count` in its docstring and the converter extracts it, but it is never used in any processing logic. In Talend, this is used for progress tracking and may affect internal buffer sizing. |
| ENG-ASR-006 | **P1** | **First/Last semantics depend on DataFrame order**: In Talend, `first` and `last` operate on the sorted input stream, so they return the first/last value within the sorted group. In the engine, `pandas.groupby().first()`/`.last()` return the first/last non-NaN value in encounter order, which may differ if the DataFrame's internal row order does not match the expected sort order. |
| ENG-ASR-007 | **P2** | **Error handling returns original input**: When an exception occurs and `die_on_error=False`, the engine returns `{'main': input_data}` (line 186). This means downstream components receive the UN-AGGREGATED input, which is semantically wrong. Talend would produce no output or route to reject -- never pass through raw input as if aggregation succeeded. |
| ENG-ASR-008 | **P2** | **CONNECTION_FORMAT ignored**: Extracted by converter but never used. If the Talend job specifies a non-default connection format, the engine will not respect it. |
| ENG-ASR-009 | **P2** | **Config key inconsistency**: `AggregateSortedRow` uses `group_bys` (with underscore and plural) while `AggregateRow` uses `group_by` (singular). The `_validate_config()` also checks for `GROUPBYS` (all caps). This inconsistency creates confusion when manually constructing configs. |
| ENG-ASR-010 | **P3** | **Schema type metadata not used**: The converter extracts output schema with Talend types, but the engine never uses this schema for output type coercion. Numeric aggregation results may have different precision/scale than specified in the Talend schema. |

---

## 4. Code Quality Audit

### 4.1 Bugs

| ID | Priority | Location | Description |
|----|----------|----------|-------------|
| BUG-ASR-001 | **P0** | `aggregate_sorted_row.py` lines 117-121 | **Validation bypass in _process()**: `_validate_config()` checks for `group_bys` OR `GROUPBYS`, but `_process()` only reads `self.config.get('group_bys', [])` (line 117) and `self.config.get('operations', [])` (line 118). If the config uses the `GROUPBYS` key (all-caps, as the converter produces), `_process()` gets an empty list `[]`, then raises `ValueError("GROUPBYS configuration is required.")` at line 121. However, `_validate_config()` at line 77 also checks `self.config.get('GROUPBYS')` and would NOT flag this as an error. The result is that `_validate_config()` passes but `_process()` fails at runtime. The `_validate_config` method checks for BOTH key styles but `_process` only checks lowercase, creating a gap. |
| BUG-ASR-002 | **P1** | `aggregate_sorted_row.py` lines 120-121 | **Dead code / unreachable branch**: Line 120 checks `if not group_bys:` and raises ValueError. But if group_bys is empty, the docstring (line 68) says "Empty group_bys aggregates entire dataset into single row." Line 148 also has `if not group_bys: result_df = self._aggregate_all(...)` which is unreachable because line 121 raises before reaching it. The `_aggregate_all()` path for empty group_bys is dead code. |
| BUG-ASR-003 | **P1** | `aggregate_sorted_row.py` lines 256-263 | **Column name collision in agg_dict**: When the same input column is used in multiple operations (e.g., sum of `amount` AND count of `amount`), `agg_dict[input_col]` accumulates multiple functions. The pandas MultiIndex flattening logic (lines 319-344) attempts to map these back, but the `rename_dict` for the non-MultiIndex path (line 347) may clobber entries. If `amount` has both `sum` and `count`, `rename_dict` will have `amount_sum -> output1` and `amount_count -> output2`, but only if MultiIndex is NOT produced. The dual-path logic (MultiIndex vs flat) is fragile and undertested. |
| BUG-ASR-004 | **P1** | `aggregate_sorted_row.py` lines 258-260 | **Same input/output column name ambiguity**: When `input_col == output_col`, the code sets `rename_dict[input_col] = output_col` (a no-op rename). But if pandas produces a MultiIndex due to multiple aggregations on the same column, the MultiIndex path (line 319) takes over and the rename_dict is ignored. The comment says "FIX: Handle same input/output column names" but the fix only works for the single-aggregation case. |
| BUG-ASR-005 | **P2** | `aggregate_sorted_row.py` line 143 | **Default function 'sum' applied silently**: `function = op.get('function', 'sum').lower()` defaults to 'sum' if no function is specified. This is dangerous because a misconfigured operation (missing function key) will silently sum values instead of failing. The `_validate_config()` method does NOT check that each operation has a 'function' key. |

### 4.2 Duplicate / Near-Duplicate Code

| ID | Priority | Issue |
|----|----------|-------|
| DUP-ASR-001 | **P1** | **AggregateSortedRow is 95% identical to AggregateRow**: The `_apply_agg_function()` method is character-for-character identical between the two classes (compare lines 371-413 of aggregate_sorted_row.py with lines 364-407 of aggregate_row.py). The `_is_decimal_column()` method is also identical. The `_aggregate_all()` method differs only in parameter naming. The `_aggregate_grouped()` method has different implementations but achieves the same result. There should be a shared base class or mixin for common aggregation logic. |
| DUP-ASR-002 | **P2** | **Dual config key checking pattern**: The pattern of checking `self.config.get('key') or self.config.get('KEY')` appears in both `_validate_config()` and `_process()` but with different key sets. This should be normalized in one place (e.g., a `_normalize_config()` method called from `__init__`). |

### 4.3 Naming Consistency

| ID | Priority | Issue |
|----|----------|-------|
| NAME-ASR-001 | **P2** | Config key `group_bys` (plural with underscore) differs from `AggregateRow`'s `group_by` (singular). Talend's parameter is `GROUPBYS` (plural no underscore). Three different naming conventions for the same concept. |
| NAME-ASR-002 | **P2** | The converter maps the Talend component to class name `TAggregateSortedRow` (with leading T) in the component_parser.py name map (line 71), but the actual class is `AggregateSortedRow` (no T). The engine registry maps both `TAggregateSortedRow` and `tAggregateSortedRow` to the same class. The extra alias works but is confusing. |
| NAME-ASR-003 | **P2** | The class is registered in `src/v1/engine/components/transform/__init__.py` (transform package) but `AggregateRow` is in `src/v1/engine/components/aggregate/` (aggregate package). Two components that implement nearly identical logic live in different packages. |
| NAME-ASR-004 | **P3** | The module docstring says "Aggregates sorted rows" but the implementation does not require or leverage sorted rows. The docstring is misleading. |

### 4.4 Standards Compliance

| ID | Priority | Issue |
|----|----------|-------|
| STD-ASR-001 | **P2** | `_validate_config()` does not validate individual operation dictionaries. It checks that `operations` is a non-empty list but does not validate that each operation has required keys (`function`, `input_column`/`output_column`). Compare with `AggregateRow._validate_config()` which validates each operation's function against `SUPPORTED_FUNCTIONS` and checks for missing `input_column`. |
| STD-ASR-002 | **P2** | No `SUPPORTED_FUNCTIONS` class constant. `AggregateRow` defines `SUPPORTED_FUNCTIONS` as a class constant for validation and documentation. `AggregateSortedRow` has no such constant, relying on the ad-hoc `if/elif` chain in `_aggregate_grouped()` with an implicit default to sum for unknown functions (line 312). |
| STD-ASR-003 | **P2** | Missing class-level DEFAULT constants. `AggregateRow` defines `DEFAULT_OPERATIONS`, `DEFAULT_GROUP_BY`, `DEFAULT_DELIMITER`. `AggregateSortedRow` inlines defaults in method calls. |
| STD-ASR-004 | **P3** | Per `STANDARDS.md`, components should validate all config parameters in `_validate_config()`. The `row_count`, `connection_format`, and `die_on_error` parameters are not validated. |

### 4.5 Debug Artifacts

| ID | Priority | Issue |
|----|----------|-------|
| DBG-ASR-001 | **P1** | **print() statements in converter** (component_parser.py lines 2178-2179): `print(f"[parse_t_aggregate_sorted_row] Parsed group_bys: {group_bys}")` and `print(f"[parse_t_aggregate_sorted_row] Parsed operations: {operations}")`. These are raw `print()` calls, not logger calls. They will write to stdout in production, potentially corrupting structured log output. Every other converter parser method in the codebase uses either `logger.debug()` or no logging at all. |

### 4.6 Error Handling

| ID | Priority | Issue |
|----|----------|-------|
| ERR-ASR-001 | **P1** | **Silent error swallowing** (line 182-186): When an exception occurs and `die_on_error=False`, the component catches the exception, logs it, and returns `{'main': input_data}` -- the ORIGINAL un-aggregated data. Downstream components will receive raw input rows instead of aggregated output, likely causing data integrity issues. Should return an empty DataFrame or raise a specific error type. |
| ERR-ASR-002 | **P2** | **Inconsistent error behavior vs AggregateRow**: `AggregateRow._process()` always raises `ComponentExecutionError` on failure (line 204). `AggregateSortedRow._process()` conditionally raises or returns original data. Two components that should behave identically have different error contracts. |
| ERR-ASR-003 | **P2** | **No error context in exception**: Line 185 does `raise` (re-raises the caught exception) but does not wrap it in a `ComponentExecutionError` with the component ID. `AggregateRow` wraps exceptions: `raise ComponentExecutionError(self.id, f"Aggregation failed: {str(e)}", e)`. This means stack traces from `AggregateSortedRow` lack component identification. |

### 4.7 Security

| ID | Priority | Issue |
|----|----------|-------|
| SEC-ASR-001 | **P3** | No input sanitization -- column names from config are used directly in pandas operations. Not a concern if input is trusted (converter-generated), but noted for defense-in-depth. |

---

## 5. Performance & Memory Audit

### 5.1 Core Performance Issue: No Streaming Aggregation

The most critical performance issue is architectural: the component uses `pandas.groupby()`
which requires holding the entire input DataFrame in memory. This is the exact opposite of
what `tAggregateSortedRow` is designed for in Talend.

**Impact analysis**:

| Dataset Size | Talend tAggregateSortedRow | V1 AggregateSortedRow |
|-------------|---------------------------|----------------------|
| 100K rows | Fast, ~O(N) time, O(1) memory per group | Fast, O(N) time, O(N) memory |
| 1M rows | Fast, O(1) memory per group | Works but holds ~1M rows in memory |
| 10M rows | Fast, O(1) memory per group | May cause memory pressure (~2-5 GB) |
| 100M+ rows | Fast, O(1) memory per group | **OOM likely** -- cannot hold in memory |

For jobs that were specifically designed to use `tAggregateSortedRow` for its memory
efficiency (which is the ONLY reason to choose it over `tAggregateRow`), the V1 engine
provides no benefit.

### 5.2 Specific Performance Issues

| ID | Priority | Issue |
|----|----------|-------|
| PERF-ASR-001 | **P0** | **No streaming aggregation**: `pandas.groupby()` is a full-memory operation. The entire raison d'etre of tAggregateSortedRow (streaming, O(1) memory) is absent. For datasets that justified choosing tAggregateSortedRow in Talend (typically 10M+ rows), the V1 engine will consume excessive memory or OOM. |
| PERF-ASR-002 | **P1** | **Multiple groupby passes for custom aggregations**: The `_aggregate_grouped()` method performs one `groupby().agg()` for standard functions (line 316), then separate `groupby().apply()` calls for each custom aggregation (list, concat, decimal_sum, count-without-input). Each of these is a full pass over the data. For a configuration with 5 operations including 2 custom ones, that is 3 groupby passes total, each requiring O(N) time. |
| PERF-ASR-003 | **P2** | **Merge-based custom aggregation joining**: Custom aggregations (lines 354-368) compute results in a separate DataFrame and then merge back on group-by keys. Each merge is O(N*M) in the worst case. For K custom aggregations, this is K merge operations. Should accumulate all results and do a single merge, or use named aggregation. |
| PERF-ASR-004 | **P2** | **Column nullification loop** (lines 160-169): After aggregation, the code iterates over ALL original columns and sets non-required ones to `None`. For DataFrames with many columns (100+), this creates N new Series objects. Could use `df.loc[:, non_required_cols] = None` as a single operation. |

---

## 6. Testing Audit

### Existing Tests

There are **zero** unit tests or integration tests for `AggregateSortedRow` in the V1 test
suite. The `tests/` directory contains:

- `tests/v1/` -- only `test_java_integration.py` and `unit/test_bridge_arrow_schema.py`
- `tests/v2/component/test_aggregate_components.py` -- tests V2 aggregate components, NOT V1
- `tests/v2/integration/test_aggregate_pipeline.py` -- tests V2 pipeline, NOT V1

No file in the entire test suite references `AggregateSortedRow`, `aggregate_sorted_row`,
or `tAggregateSortedRow`.

### Testing Issues

| ID | Priority | Issue |
|----|----------|-------|
| TEST-ASR-001 | **P0** | **Zero unit tests** for `AggregateSortedRow`. No coverage of any aggregation function, no edge case testing, no error path testing. This is a component that performs data transformations -- incorrect aggregation silently corrupts data. |
| TEST-ASR-002 | **P1** | **No integration test** exercises this component in a V1 engine pipeline. No test verifies the converter -> engine -> execution path. |

### Recommended Test Cases

| Test | Priority | Description |
|------|----------|-------------|
| Basic grouped sum | P0 | Group by one column, sum another. Verify output row count and values. |
| Multiple operations | P0 | Group by one column, apply sum + count + avg on different columns. Verify all output columns. |
| Multiple group-by columns | P0 | Group by 2+ columns. Verify correct grouping. |
| Empty input | P0 | Pass None and empty DataFrame. Verify empty output and stats = 0. |
| No group-by (whole-table) | P0 | Empty group_bys list. Verify single output row with correct aggregation. |
| All aggregation functions | P0 | Test each function individually: sum, count, min, max, avg, first, last, count_distinct, std, var, median, list, concat. |
| Decimal precision | P1 | Sum Decimal columns. Verify precision is preserved (not float approximation). |
| Same input/output column name | P1 | Operations where input_column == output_column. Verify no column name collision. |
| Multiple operations on same column | P1 | Sum and count on the same input column. Verify both outputs are correct. |
| Missing input column | P1 | Reference a column that does not exist in input. Verify graceful handling. |
| die_on_error=true with bad data | P1 | Trigger an error with die_on_error=true. Verify exception raised. |
| die_on_error=false with bad data | P1 | Trigger an error with die_on_error=false. Verify behavior (currently returns input -- should be documented/tested). |
| GROUPBYS (uppercase) config key | P1 | Provide config with `GROUPBYS` key instead of `group_bys`. Verify it works (currently broken -- see BUG-ASR-001). |
| Null values in aggregation columns | P1 | Rows with null values in aggregated columns. Verify correct handling for each function. |
| Concat with custom delimiter | P2 | Concatenate function with non-default delimiter. Verify output string. |
| Large dataset (1M+ rows) | P2 | Performance and memory regression test. |
| Unsorted input | P2 | Verify that the engine produces correct results even with unsorted input (since it uses groupby). Document this as a known divergence from Talend. |
| Column ordering in output | P2 | Verify output columns match input column order with operation columns appended. |
| Non-required columns set to null | P2 | Verify columns not in group_by or operations are null in output. |
| Converter round-trip | P1 | Parse a Talend XML with tAggregateSortedRow, convert, execute. Verify end-to-end correctness. |

---

## 7. Issues Summary

### All Issues by Priority

#### P0 -- Critical (5 issues)

| ID | Category | Summary |
|----|----------|---------|
| ENG-ASR-001 | Feature Gap | No sorted-input streaming aggregation -- the core differentiator of tAggregateSortedRow is absent. Uses hash-based groupby identical to tAggregateRow. |
| ENG-ASR-002 | Feature Gap | No sorted-input validation -- does not verify input is sorted by group-by columns. |
| BUG-ASR-001 | Bug | Validation/processing config key mismatch -- `_validate_config()` accepts `GROUPBYS` but `_process()` only reads `group_bys`, causing runtime failure for converter-produced configs. |
| PERF-ASR-001 | Performance | No streaming aggregation -- pandas groupby requires O(N) memory, defeating the purpose of choosing tAggregateSortedRow for large datasets. |
| TEST-ASR-001 | Testing | Zero unit tests for any aggregation function or edge case. |

#### P1 -- Major (12 issues)

| ID | Category | Summary |
|----|----------|---------|
| CONV-ASR-001 | Converter | `DIE_ON_ERROR` not extracted from Talend XML. |
| CONV-ASR-002 | Converter | Operations parsing uses fragile hardcoded stride of 4. |
| ENG-ASR-003 | Feature Gap | `IGNORE_NULL` not implemented -- converter extracts it, engine ignores it. |
| ENG-ASR-004 | Feature Gap | No REJECT flow output. |
| ENG-ASR-005 | Feature Gap | `ROW_COUNT` extracted but never used. |
| ENG-ASR-006 | Feature Gap | First/Last semantics depend on DataFrame order, not guaranteed sort order. |
| BUG-ASR-002 | Bug | Dead code: `_aggregate_all()` unreachable for empty group_bys because ValueError is raised first. |
| BUG-ASR-003 | Bug | Column name collision risk when same input column has multiple operations. |
| BUG-ASR-004 | Bug | Same input/output column name handling only works for single-aggregation case. |
| DBG-ASR-001 | Debug | print() statements in converter production code. |
| ERR-ASR-001 | Error Handling | Silent error swallowing -- returns original un-aggregated input on failure. |
| DUP-ASR-001 | Duplication | 95% code duplication with AggregateRow -- should share a base class. |
| PERF-ASR-002 | Performance | Multiple groupby passes for custom aggregations. |
| TEST-ASR-002 | Testing | No integration tests in V1 pipeline. |

#### P2 -- Moderate (13 issues)

| ID | Category | Summary |
|----|----------|---------|
| CONV-ASR-003 | Converter | Schema types not converted from Talend format. |
| CONV-ASR-004 | Converter | IGNORE_NULL extracted by converter but ignored by engine. |
| ENG-ASR-007 | Feature Gap | Error handling returns original input instead of empty DataFrame. |
| ENG-ASR-008 | Feature Gap | CONNECTION_FORMAT ignored. |
| ENG-ASR-009 | Feature Gap | Config key naming inconsistency (`group_bys` vs `group_by` vs `GROUPBYS`). |
| BUG-ASR-005 | Bug | Missing function key silently defaults to sum. |
| DUP-ASR-002 | Duplication | Dual config key checking pattern repeated without normalization. |
| NAME-ASR-001 | Naming | Config key `group_bys` differs from AggregateRow's `group_by`. |
| NAME-ASR-002 | Naming | Converter maps to `TAggregateSortedRow` but class is `AggregateSortedRow`. |
| NAME-ASR-003 | Naming | Lives in `transform/` package while AggregateRow lives in `aggregate/` package. |
| STD-ASR-001 | Standards | _validate_config() does not validate individual operations. |
| STD-ASR-002 | Standards | No SUPPORTED_FUNCTIONS class constant. |
| STD-ASR-003 | Standards | No DEFAULT class constants. |
| ERR-ASR-002 | Error Handling | Inconsistent error behavior vs AggregateRow. |
| ERR-ASR-003 | Error Handling | No ComponentExecutionError wrapping. |
| PERF-ASR-003 | Performance | Merge-based custom aggregation joining adds overhead. |
| PERF-ASR-004 | Performance | Column nullification loop could be vectorized. |

#### P3 -- Low (4 issues)

| ID | Category | Summary |
|----|----------|---------|
| CONV-ASR-005 | Converter | Debug print() should be logger.debug(). |
| ENG-ASR-010 | Feature Gap | Schema type metadata not used for output coercion. |
| NAME-ASR-004 | Naming | Module docstring says "sorted" but implementation does not require/use sorting. |
| STD-ASR-004 | Standards | row_count, connection_format, die_on_error not validated in _validate_config(). |
| SEC-ASR-001 | Security | No input sanitization on column names. |

---

## 8. Detailed Code Walkthrough

### 8.1 Module Structure

```
aggregate_sorted_row.py (414 lines)
    |
    +-- Module docstring (lines 1-5)
    +-- Imports (lines 6-12)
    +-- Logger setup (line 14)
    +-- class AggregateSortedRow(BaseComponent) (lines 17-413)
        |
        +-- Class docstring (lines 18-70)
        +-- _validate_config() (lines 72-92)
        +-- _process() (lines 94-186)
        +-- _is_decimal_column() (lines 188-195)
        +-- _aggregate_all() (lines 197-217)
        +-- _aggregate_grouped() (lines 219-369)
        +-- _apply_agg_function() (lines 371-413)
```

### 8.2 _validate_config() Analysis (lines 72-92)

**Purpose**: Validates the component configuration before execution.

**What it checks**:
- `group_bys` OR `GROUPBYS` must exist and be a list
- `operations` OR `OPERATIONS` must exist, be a list, and be non-empty

**What it does NOT check**:
- Individual operation structure (no keys validation)
- `function` key existence or validity per operation
- `row_count` type/range
- `connection_format` valid values
- `die_on_error` type

**Discrepancy with _process()**:
- `_validate_config()` accepts `GROUPBYS` (uppercase) via `self.config.get('group_bys') or self.config.get('GROUPBYS')`
- `_process()` only reads `self.config.get('group_bys', [])` -- will get `[]` if config has `GROUPBYS`
- Then line 120 `if not group_bys:` triggers `raise ValueError("GROUPBYS configuration is required.")`
- This means a config that passes validation will fail at runtime

### 8.3 _process() Analysis (lines 94-186)

**Flow**:
1. Handle empty input (lines 106-109)
2. Get config (lines 117-118) -- **only lowercase keys**
3. Validate group_bys and operations exist (lines 120-123) -- **redundant with _validate_config but different**
4. Validate group_bys are all strings (lines 126-130)
5. Normalize operations (lines 133-144) -- supports both `input_column` and `column` keys
6. Dispatch to `_aggregate_all()` or `_aggregate_grouped()` (lines 147-150)
7. Add missing columns as null (lines 152-173)
8. Reorder columns (lines 172-173)
9. Update stats and return (lines 175-180)

**Issues in this flow**:
- Step 3 raises for empty group_bys, but step 6 has a dead branch handling empty group_bys
- Step 5's normalization creates a new list but does not validate completeness
- Step 7's column reordering uses a list comprehension that could produce duplicates if an operation output column matches an input column name

### 8.4 _aggregate_grouped() Analysis (lines 219-369)

**This is the most complex method and contains the most issues.**

The method uses a dual-path strategy:

**Path 1: Standard pandas aggregation** (lines 236-347)
- Builds an `agg_dict` mapping input columns to pandas aggregation functions
- Calls `df.groupby(valid_group_by, as_index=False).agg(agg_dict)`
- Handles MultiIndex column flattening (lines 319-347)
- Falls back to standard rename (line 347)

**Path 2: Custom aggregation** (lines 352-368)
- Handles decimal_sum, count-without-input, list, concat
- Each custom aggregation does a separate groupby + merge

**Specific issues in _aggregate_grouped()**:

1. **MultiIndex detection** (line 319): `any(isinstance(col, tuple) for col in grouped.columns)` -- this heuristic can fail if a column name is genuinely a tuple (unlikely but possible in pathological data).

2. **Operation function matching** (lines 328-330): The code iterates over `operations` to find a matching `input_column` and `function` for each MultiIndex tuple. If two operations have the same input_column and function (e.g., two sum operations on the same column with different output names), only the first match is used.

3. **Fallback column naming** (line 338): `'_'.join(str(c) for c in col if c)` -- if `c` is an empty string (which it can be for group-by columns in MultiIndex), this filter removes it, potentially creating ambiguous names.

4. **Avg->mean mapping** (lines 275-282): The converter stores the Talend function name (e.g., `avg`) but pandas uses `mean`. The code maps `avg` to `mean` for the aggregation dict, but then the MultiIndex tuple will contain `mean`, not `avg`. The operation matching at line 329 compares `op['function']` (which is `avg`) against `func_name` (which is `mean`). These will NOT match, causing the fallback naming to be used instead of the target output column name.

### 8.5 _apply_agg_function() Analysis (lines 371-413)

This method is used only by `_aggregate_all()` (whole-table aggregation with no groups).
It is NOT used by `_aggregate_grouped()`, which builds its own aggregation logic.

**Issues**:
- Line 413: Unknown functions default to `sum` with no warning. This is inconsistent with `_aggregate_grouped()` which logs a warning (line 312).
- The method duplicates function dispatch logic that also exists in `_aggregate_grouped()`.

---

## 9. Comparison: AggregateSortedRow vs AggregateRow

### Structural Comparison

| Aspect | AggregateSortedRow | AggregateRow |
|--------|-------------------|--------------|
| **Package** | `components/transform/` | `components/aggregate/` |
| **Config key for groups** | `group_bys` (also `GROUPBYS`) | `group_by` |
| **Config key for ops** | `operations` (also `OPERATIONS`) | `operations` |
| **SUPPORTED_FUNCTIONS constant** | No | Yes |
| **DEFAULT constants** | No | Yes (3 constants) |
| **_validate_config depth** | Shallow (list check only) | Deep (per-operation validation) |
| **Error handling** | Returns original input on failure | Raises ComponentExecutionError |
| **_aggregate_grouped approach** | pandas agg() + merge for custom | Individual groupby per operation + merge |
| **_apply_agg_function** | Identical implementation | Identical implementation |
| **_is_decimal_column** | Identical implementation | Identical implementation |
| **_ensure_output_columns** | Inline in _process() | Dedicated method with extensive logging |
| **Sorted input optimization** | None | N/A (not its purpose) |

### Key Observation

`AggregateSortedRow` appears to be a slightly earlier or alternative implementation of the
same aggregation logic as `AggregateRow`, placed in a different package with different
config key names. Neither component implements the streaming sorted-input optimization that
distinguishes `tAggregateSortedRow` from `tAggregateRow` in Talend.

The two classes should ideally:
1. Share a common `BaseAggregateComponent` with the duplicated methods
2. `AggregateSortedRow` should override `_aggregate_grouped()` with a true streaming
   implementation that iterates sorted rows and emits groups on key changes
3. `AggregateSortedRow` should validate that input is sorted and warn/fail if not

---

## 10. Recommendations

### Immediate -- Before Production (P0)

1. **Implement streaming sorted aggregation**: Replace `pandas.groupby()` in
   `AggregateSortedRow._aggregate_grouped()` with a row-by-row iterator that:
   - Reads rows sequentially
   - Compares each row's group-by values to the previous row
   - When group-by values change, emits the accumulated aggregation result
   - Starts a new accumulator for the new group
   - This achieves O(1) memory per group, matching Talend's behavior

2. **Add sorted-input validation**: Before processing, verify that the input DataFrame is
   sorted by the group-by columns. Options:
   - Assert: `assert df[group_bys].equals(df[group_bys].sort_values(group_bys))` (expensive)
   - Sample check: verify first/last/random rows are in order (cheaper)
   - Warning-only mode: log a warning if unsorted but still process correctly (safest)

3. **Fix BUG-ASR-001**: Normalize config keys in `_process()` to check both `group_bys`
   and `GROUPBYS`, or better yet, normalize once in a `_normalize_config()` method.

4. **Write core unit tests**: At minimum, test all 14 aggregation functions, empty input,
   multi-column group-by, and the BUG-ASR-001 scenario.

5. **Fix the dead code path**: Either remove the ValueError on empty group_bys (line 121)
   to allow whole-table aggregation, or update the docstring to reflect that group_bys
   is mandatory.

### Short-Term -- Hardening (P1)

6. **Extract DIE_ON_ERROR in converter**: Add `die_on_error` extraction to
   `parse_t_aggregate_sorted_row()`, following the pattern used by every other parser.

7. **Implement IGNORE_NULL**: Read the `ignore_null` flag from each operation and:
   - When true: use `.dropna()` before aggregation (current pandas default for most functions)
   - When false: include nulls in computation (use `skipna=False` for pandas aggregations)

8. **Fix error handling**: On failure with `die_on_error=False`, return an empty DataFrame
   (not the original input). Wrap exceptions in `ComponentExecutionError`.

9. **Remove print() statements**: Replace lines 2178-2179 in component_parser.py with
   `logger.debug()` calls.

10. **Refactor to share code with AggregateRow**: Create a `BaseAggregateComponent` with
    shared methods: `_apply_agg_function()`, `_is_decimal_column()`, `_aggregate_all()`.

11. **Fix avg/mean function name mismatch**: The MultiIndex column matching logic will fail
    for `avg` operations because Talend uses `avg` but pandas uses `mean`. Add a mapping
    dict for function name normalization.

12. **Add REJECT flow support**: Implement error row routing with `errorCode` and
    `errorMessage` columns, following the pattern used by other components.

### Medium-Term -- Robustness (P2)

13. **Unify config key naming**: Standardize on either `group_bys` or `group_by` across
    both aggregate components. Add a config normalization step.

14. **Move to aggregate/ package**: Relocate `AggregateSortedRow` from `components/transform/`
    to `components/aggregate/` alongside `AggregateRow` for organizational consistency.

15. **Add SUPPORTED_FUNCTIONS constant**: Define supported functions as a class constant
    and validate against it in `_validate_config()`.

16. **Improve _validate_config()**: Validate individual operation dictionaries, check for
    required keys, validate function names against SUPPORTED_FUNCTIONS.

17. **Fix operations stride parsing**: Replace the hardcoded stride-4 parsing in the
    converter with ref-based grouping that detects operation boundaries dynamically.

18. **Optimize multiple groupby passes**: Combine standard and custom aggregations into
    fewer passes where possible.

### Long-Term -- Optimization (P3)

19. **Implement true streaming mode**: For very large datasets, implement chunk-based
    processing that reads sorted input in chunks, maintaining aggregation state across
    chunk boundaries.

20. **Add ROW_COUNT usage**: Use `row_count` for progress reporting and memory
    pre-allocation optimization.

21. **Schema type coercion**: Use the output schema metadata to coerce aggregation
    results to the expected types (e.g., BigDecimal for financial columns).

---

## 11. Appendix A: Function-by-Function Parity Matrix

| Function | Talend | Engine `_aggregate_grouped()` | Engine `_apply_agg_function()` | Notes |
|----------|--------|-------------------------------|--------------------------------|-------|
| `sum` | Yes | Yes (pandas sum / decimal sum) | Yes (with Decimal handling) | Decimal path uses custom aggregation + merge |
| `count` | Yes | Yes (pandas count / size) | Yes | Without input_column uses size() |
| `count_distinct` | Yes | Yes (pandas nunique) | Yes | |
| `avg` / `mean` | Yes | Yes (pandas mean) | Yes | **BUG**: avg->mean mapping breaks MultiIndex naming |
| `min` | Yes | Yes (pandas min) | Yes | |
| `max` | Yes | Yes (pandas max) | Yes | |
| `first` | Yes | Yes (pandas first) | Yes | Semantics differ: Talend=sorted, Engine=encounter order |
| `last` | Yes | Yes (pandas last) | Yes | Same caveat as first |
| `list` | Yes | Yes (custom agg + merge) | Yes | |
| `concat`/`concatenate` | Yes | Yes (custom agg + merge) | Yes | Supports configurable delimiter |
| `std` / `stddev` | Yes | Yes (pandas std) | Yes | |
| `var` / `variance` | Yes | Yes (pandas var) | Yes | |
| `median` | Yes | Yes (pandas median) | Yes | |
| Unknown function | Error in Talend | **Defaults to sum** | **Defaults to sum** | Silent data corruption risk |

---

## 12. Appendix B: Configuration Key Cross-Reference

| Concept | Talend XML | Converter Output | Engine Config Key | Engine Reads? |
|---------|-----------|-----------------|-------------------|---------------|
| Group-by columns | `GROUPBYS` | `group_bys` | `group_bys` (or `GROUPBYS`) | Yes (lowercase only in _process) |
| Operations | `OPERATIONS` | `operations` | `operations` (or `OPERATIONS`) | Yes (lowercase only in _process) |
| Row count | `ROW_COUNT` | `row_count` | `row_count` | **No** |
| Connection format | `CONNECTION_FORMAT` | `connection_format` | `connection_format` | **No** |
| Die on error | `DIE_ON_ERROR` | **Not extracted** | `die_on_error` | Yes (always False) |
| Ignore null (per op) | `IGNORE_NULL` | `ignore_null` | `ignore_null` | **No** |
| Output schema | FLOW metadata | `schema.output` | `output_schema` | **No** |

---

## 13. Appendix C: Converter Code Listing with Annotations

```python
# component_parser.py lines 2132-2199

def parse_t_aggregate_sorted_row(self, node, component: Dict) -> Dict:
    """
    Parse tAggregateSortedRow component from Talend XML node.
    Extracts GROUPBYS and OPERATIONS tables and builds output schema.
    Maps to ETL-AGENT tAggregateSortedRow config format.
    """
    # Parse GROUPBYS
    group_bys = []
    for table in node.findall('.//elementParameter[@name="GROUPBYS"]'):
        for elem in table.findall('.//elementValue'):
            if elem.get('elementRef') == 'INPUT_COLUMN':
                group_bys.append(elem.get('value', ''))
    # NOTE: Only extracts INPUT_COLUMN refs, which is correct for GROUPBYS

    # Parse OPERATIONS (group every 4 consecutive elementValue as one op)
    operations = []
    for table in node.findall('.//elementParameter[@name="OPERATIONS"]'):
        elements = list(table.findall('.//elementValue'))
        for i in range(0, len(elements), 4):          # <-- FRAGILE: hardcoded stride
            op = {}
            for elem in elements[i:i+4]:
                ref = elem.get('elementRef')
                val = elem.get('value', '')
                if ref == 'OUTPUT_COLUMN':
                    op['output_column'] = val
                elif ref == 'INPUT_COLUMN':
                    op['input_column'] = val
                elif ref == 'FUNCTION':
                    op['function'] = val
                elif ref == 'IGNORE_NULL':
                    op['ignore_null'] = val.lower() == 'true'  # <-- Extracted but engine ignores
            if op:
                operations.append(op)

    # Parse ROW_COUNT
    row_count = None
    for param in node.findall('.//elementParameter[@name="ROW_COUNT"]'):
        row_count = param.get('value', None)           # <-- Extracted but engine ignores
        break

    # Parse CONNECTION_FORMAT
    connection_format = None
    for param in node.findall('.//elementParameter[@name="CONNECTION_FORMAT"]'):
        connection_format = param.get('value', None)   # <-- Extracted but engine ignores
        break

    # Log for debug
    print(f"[parse_t_aggregate_sorted_row] Parsed group_bys: {group_bys}")    # <-- PRINT in production!
    print(f"[parse_t_aggregate_sorted_row] Parsed operations: {operations}")   # <-- PRINT in production!

    # Build output schema from metadata
    output_schema = []
    for metadata in node.findall('.//metadata[@connector="FLOW"]'):
        for column in metadata.findall('.//column'):
            output_schema.append({
                'name': column.get('name', ''),
                'type': column.get('type', 'id_String'),  # <-- Raw Talend type, not converted
                'nullable': column.get('nullable', 'true').lower() == 'true',
                'key': column.get('key', 'false').lower() == 'true',
                'length': int(column.get('length', -1)),
                'precision': int(column.get('precision', -1))
            })

    # NOTE: DIE_ON_ERROR is NOT extracted here, unlike every other parser method

    component['config']['group_bys'] = group_bys
    component['config']['operations'] = operations
    component['config']['row_count'] = row_count
    component['config']['connection_format'] = connection_format
    component['schema']['output'] = output_schema
    return component
```

---

## 14. Appendix D: Engine Code Listing with Annotations

```python
# aggregate_sorted_row.py -- full class with inline annotations

class AggregateSortedRow(BaseComponent):
    # NOTE: No SUPPORTED_FUNCTIONS constant (unlike AggregateRow)
    # NOTE: No DEFAULT_* constants (unlike AggregateRow)

    def _validate_config(self) -> List[str]:
        errors = []
        # Checks BOTH group_bys and GROUPBYS
        group_bys = self.config.get('group_bys') or self.config.get('GROUPBYS')
        operations = self.config.get('operations') or self.config.get('OPERATIONS')
        # ... validates list types ...
        return errors

    def _process(self, input_data=None):
        # ... empty input handling ...

        # BUG: Only reads lowercase keys -- GROUPBYS config will produce empty list
        group_bys = self.config.get('group_bys', [])
        operations = self.config.get('operations', [])

        # BUG: Raises ValueError for empty group_bys, making _aggregate_all() dead code
        if not group_bys:
            raise ValueError("GROUPBYS configuration is required.")

        # ... normalize operations ...

        # CRITICAL: Uses pandas groupby -- NO sorted-input optimization
        if not group_bys:                                    # Dead code
            result_df = self._aggregate_all(input_data, norm_ops)
        else:
            result_df = self._aggregate_grouped(input_data, group_bys, norm_ops)

        # ... column nullification and reordering ...

        # BUG: On exception with die_on_error=False, returns original input
        except Exception as e:
            if self.config.get('die_on_error', False):
                raise
            return {'main': input_data}  # <-- Returns UN-AGGREGATED data!
```

---

## 15. Appendix E: Registry and Import Chain

```
Engine Registration (engine.py):
    'TAggregateSortedRow': AggregateSortedRow    (line 111)
    'tAggregateSortedRow': AggregateSortedRow    (line 112)

Import Chain:
    engine.py
        -> from .components.aggregate import AggregateSortedRow  (line 40)
            -> components/aggregate/__init__.py
                -> DOES NOT contain AggregateSortedRow!
                -> Only contains: AggregateRow, UniqueRow

    Actual import (from engine.py line 40):
        from .components.aggregate import AggregateSortedRow, Denormalize, Normalize, Replicate

    But components/aggregate/__init__.py only exports:
        AggregateRow, UniqueRow

    AggregateSortedRow is defined in:
        components/transform/aggregate_sorted_row.py
    And exported from:
        components/transform/__init__.py

    This means engine.py line 40 imports AggregateSortedRow from the
    aggregate package's __init__.py, which re-exports from transform.
    This is a fragile import chain -- the component lives in transform/
    but is imported as if it lives in aggregate/.
```

**Wait -- let me verify this more carefully.**

Looking at `engine.py` line 40:
```python
from .components.aggregate import AggregateSortedRow, Denormalize, Normalize, Replicate
```

But `components/aggregate/__init__.py` only exports `AggregateRow` and `UniqueRow`.

`AggregateSortedRow` is defined in `components/transform/aggregate_sorted_row.py` and
exported from `components/transform/__init__.py`.

This import should fail at runtime unless there is an additional import path. The fact
that the component works means either:
1. There is an additional import we have not found, OR
2. The `aggregate/__init__.py` has been modified to re-export from transform, OR
3. Python's import mechanism resolves this through a parent `__init__.py`

This needs investigation -- it may be a latent import error that only fails when the
component is actually instantiated.

| ID | Priority | Issue |
|----|----------|-------|
| IMP-ASR-001 | **P1** | `engine.py` imports `AggregateSortedRow` from `components.aggregate` but the class is defined in `components.transform`. The aggregate package `__init__.py` does not export it. This is either a broken import that fails at runtime or an undocumented re-export chain. |

---

## 16. Appendix F: Talend Reference Sources

The following sources were consulted for the Talend feature baseline in this audit:

- [tAggregateSortedRow Standard properties | Talend Components Help (v8.0)](https://help.talend.com/en-US/components/8.0/processing/taggregatesortedrow-standard-properties)
- [tAggregateSortedRow | Talend Components Help (v8.0)](https://help.talend.com/en-US/components/8.0/processing/taggregatesortedrow)
- [tAggregateSortedRow Standard properties | Talend Components Help (v7.3)](https://help.qlik.com/talend/en-US/components/7.3/processing/taggregatesortedrow-standard-properties)
- [tAggregateRow vs tAggregateSortedRow - Talend Tutorials](https://talended.wordpress.com/2017/03/28/taggregaterow-vs-taggregatesortedrow/)
- [Talend Aggregate Sorted Row - Tutorial Gateway](https://www.tutorialgateway.org/talend-aggregate-sorted-row/)
- [tAggregateRow and tAggregateSortedRow in Talend - Tech-Netting](https://tech-netting.blogspot.com/2016/03/taggregaterow-and-taggregatesortedrow.html)
- [Difference between tAggregateRow and tAggregateSortedRow - dwetl.com](http://dwetl.com/2015/03/25/difference-between-taggregaterow-and-taggregatesortedrow/)
- [When to use tAggregateRow and when to use tSortRow + tAggregateSortedRow - Qlik Community](https://community.qlik.com/t5/Design-and-Development/When-to-use-tAggregateRow-and-when-to-use-tSortRow/td-p/2277442)
- [Aggregating the sorted data | Talend Components Help (v7.3)](https://help.qlik.com/talend/en-US/components/7.3/processing/tsortrow-taggregatesortedrow-tlogrow-tfixedflowinput-aggregating-sorted-data-standard-component)
- [Sorting the input data | Talend Components Help (v8.0)](https://help.talend.com/r/en-US/8.0/processing/tsortrow-taggregatesortedrow-tlogrow-tfixedflowinput-sorting-input-data-standard-component)

---

## 17. Final Verdict

**Production Readiness: NOT READY**

The `AggregateSortedRow` component has a fundamental architectural gap: it does not
implement the sorted-input streaming aggregation that is the entire purpose of
`tAggregateSortedRow` in Talend. Instead, it is a near-duplicate of `AggregateRow`
with different config key names and slightly different code organization.

**For jobs that use `tAggregateSortedRow` with small-to-medium datasets**, the component
will produce correct results because `pandas.groupby()` handles any input order. However,
the memory characteristics will be worse than expected.

**For jobs that specifically chose `tAggregateSortedRow` for large dataset handling**
(which is the primary use case), the component will exhibit the same memory limitations
as `tAggregateRow`, potentially causing OOM failures that would not occur in Talend.

Additional concerns include: zero test coverage, a config key mismatch bug (BUG-ASR-001)
that will cause runtime failures for converter-produced configs, silent error swallowing
that returns un-aggregated data, and missing DIE_ON_ERROR extraction in the converter.

The component requires significant work before production use. At minimum:
1. Fix BUG-ASR-001 (config key mismatch)
2. Fix error handling (do not return original input on failure)
3. Add unit tests for core functionality
4. Extract DIE_ON_ERROR in converter
5. Document that streaming optimization is not yet implemented

For full Talend parity, implement streaming sorted aggregation.
