# Audit Report: tAggregateSortedRow / AggregateSortedRow

> **Audited**: 2026-03-21
> **Auditor**: Claude Opus 4.6 (automated) -- GOLD STANDARD TEMPLATE
> **Engine Version**: v1
> **Converter**: `complex_converter`
> **Status**: PRODUCTION READINESS REVIEW

---

## Component Identity

| Field | Value |
|-------|-------|
| **Talend Name** | `tAggregateSortedRow` |
| **V1 Engine Class** | `AggregateSortedRow` |
| **Engine File** | `src/v1/engine/components/transform/aggregate_sorted_row.py` (414 lines) |
| **Converter Parser** | `src/converters/complex_converter/component_parser.py` -> `parse_t_aggregate_sorted_row()` (lines 2132-2199) |
| **Converter Dispatch** | `src/converters/complex_converter/converter.py` -> dedicated `elif` branch (lines 339-340) |
| **Registry Aliases** | `TAggregateSortedRow`, `tAggregateSortedRow` (registered in `src/v1/engine/engine.py` lines 111-112) |
| **Category** | Transform / Aggregation |
| **Complexity** | Medium-High -- sorted-input aggregation with multiple function support |
| **Talend Family** | Processing |
| **Issue ID Prefix** | `{CATEGORY}-ASR-{NUMBER}` |

### Key Files

| File | Purpose |
|------|---------|
| `src/v1/engine/components/transform/aggregate_sorted_row.py` | Engine implementation (414 lines) |
| `src/converters/complex_converter/component_parser.py` (lines 2132-2199) | Parameter mapping from Talend XML to v1 JSON |
| `src/converters/complex_converter/converter.py` (lines 339-340) | Dispatch via dedicated `elif component_type == 'tAggregateSortedRow'` branch |
| `src/v1/engine/base_component.py` | Base class: `_update_stats()`, `_update_global_map()`, `validate_schema()`, `execute()` |
| `src/v1/engine/global_map.py` | GlobalMap storage for `{id}_NB_LINE` etc. |
| `src/v1/engine/components/aggregate/aggregate_row.py` | Sister component `AggregateRow` -- nearly identical implementation |
| `src/v1/engine/components/transform/__init__.py` | Package exports for `AggregateSortedRow` |
| `src/v1/engine/components/aggregate/__init__.py` | Package exports -- does NOT contain `AggregateSortedRow` despite engine.py importing from here |

---

## 2. Scorecard

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
|-----------|-------|----|----|----|----|---------|
| Converter Coverage | **Y** | 0 | 2 | 2 | 1 | 5 of 7 Talend params extracted; missing DIE_ON_ERROR; IGNORE_NULL extracted but engine ignores it; fragile stride-4 parsing |
| Engine Feature Parity | **R** | 2 | 6 | 4 | 1 | No sorted-input streaming; no IGNORE_NULL; no REJECT flow; avg/mean naming bug; first/last semantics differ; no input validation |
| Code Quality | **Y** | 1 | 7 | 9 | 3 | Config key mismatch bug; dead code paths; 95% duplication with AggregateRow; import chain issue; error handling returns raw input; stddev/variance aliases silently dropped; Decimal precision lost for avg/mean in ungrouped path; None output_column propagation |
| Performance & Memory | **R** | 1 | 1 | 2 | 0 | No streaming aggregation (O(N) memory vs Talend O(1)); multiple groupby passes; merge overhead |
| Testing | **R** | 1 | 1 | 0 | 0 | Zero v1 unit tests; zero v1 integration tests for this component |

**Overall: RED -- Not production-ready; requires P0 fixes before any production use**

### Score Key
- **R** (Red): Critical gaps blocking production use
- **Y** (Yellow): Significant gaps; usable for subset of jobs with known limitations
- **G** (Green): Production-ready with minor improvements recommended

---

## 3. Talend Feature Baseline

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

## 4. Converter Audit

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

## 5. Engine Feature Parity Audit

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
| Std/StdDev function | Partial | Medium | `std` works via pandas std(); **`stddev` alias silently dropped in grouped path** (BUG-ASR-010) |
| Variance function | Partial | Medium | `var` works via pandas var(); **`variance` alias silently dropped in grouped path** (BUG-ASR-010) |
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

## 6. Code Quality Audit

### 4.1 Bugs

| ID | Priority | Location | Description |
|----|----------|----------|-------------|
| BUG-ASR-001 | **P0** | `aggregate_sorted_row.py` lines 117-121 | **Validation bypass in _process()**: `_validate_config()` checks for `group_bys` OR `GROUPBYS`, but `_process()` only reads `self.config.get('group_bys', [])` (line 117) and `self.config.get('operations', [])` (line 118). If the config uses the `GROUPBYS` key (all-caps, as the converter produces), `_process()` gets an empty list `[]`, then raises `ValueError("GROUPBYS configuration is required.")` at line 121. However, `_validate_config()` at line 77 also checks `self.config.get('GROUPBYS')` and would NOT flag this as an error. The result is that `_validate_config()` passes but `_process()` fails at runtime. The `_validate_config` method checks for BOTH key styles but `_process` only checks lowercase, creating a gap. |
| BUG-ASR-002 | **P1** | `aggregate_sorted_row.py` lines 120-121 | **Dead code / unreachable branch**: Line 120 checks `if not group_bys:` and raises ValueError. But if group_bys is empty, the docstring (line 68) says "Empty group_bys aggregates entire dataset into single row." Line 148 also has `if not group_bys: result_df = self._aggregate_all(...)` which is unreachable because line 121 raises before reaching it. The `_aggregate_all()` path for empty group_bys is dead code. |
| BUG-ASR-003 | **P1** | `aggregate_sorted_row.py` lines 256-263 | **Column name collision in agg_dict**: When the same input column is used in multiple operations (e.g., sum of `amount` AND count of `amount`), `agg_dict[input_col]` accumulates multiple functions. The pandas MultiIndex flattening logic (lines 319-344) attempts to map these back, but the `rename_dict` for the non-MultiIndex path (line 347) may clobber entries. If `amount` has both `sum` and `count`, `rename_dict` will have `amount_sum -> output1` and `amount_count -> output2`, but only if MultiIndex is NOT produced. The dual-path logic (MultiIndex vs flat) is fragile and undertested. |
| BUG-ASR-004 | **P1** | `aggregate_sorted_row.py` lines 258-260 | **Same input/output column name ambiguity**: When `input_col == output_col`, the code sets `rename_dict[input_col] = output_col` (a no-op rename). But if pandas produces a MultiIndex due to multiple aggregations on the same column, the MultiIndex path (line 319) takes over and the rename_dict is ignored. The comment says "FIX: Handle same input/output column names" but the fix only works for the single-aggregation case. |
| BUG-ASR-005 | **P2** | `aggregate_sorted_row.py` line 143 | **Default function 'sum' applied silently**: `function = op.get('function', 'sum').lower()` defaults to 'sum' if no function is specified. This is dangerous because a misconfigured operation (missing function key) will silently sum values instead of failing. The `_validate_config()` method does NOT check that each operation has a 'function' key. |
| BUG-ASR-010 | **P1** | `aggregate_sorted_row.py` line 264 (`_aggregate_grouped()`) | **`stddev`/`variance` aliases silently dropped in `_aggregate_grouped()`**: Only `std`/`var` are handled in the function-mapping logic. The aliases `stddev` and `variance` fall through to the unknown-function else clause, producing no output column -- silent data loss. |
| BUG-ASR-011 | **P1** | `aggregate_sorted_row.py` line 388 (`_apply_agg_function()`) | **Decimal precision lost for avg/mean in ungrouped `_apply_agg_function()` path**: `series.mean()` converts Decimal to float64. The `sum` path has an explicit Decimal guard but `avg`/`mean` does not, causing silent precision loss for Decimal columns when no group-by columns are specified. |
| BUG-ASR-012 | **P2** | `aggregate_sorted_row.py` (`_aggregate_grouped()` / `_apply_agg_function()`) | **`None` output_column creates column literally named `None`**: When an operation has no `output_column`/`input_column`/`column` keys, `None` propagates through the aggregation logic and becomes the column name in the output DataFrame, creating a column literally named `None` instead of raising a validation error. |

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

## 7. Performance & Memory Audit

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

## 8. Testing Audit

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

## 9. Issues Summary

### All Issues by Priority

#### P0 -- Critical (5 issues)

| ID | Category | Summary |
|----|----------|---------|
| ENG-ASR-001 | Feature Gap | No sorted-input streaming aggregation -- the core differentiator of tAggregateSortedRow is absent. Uses hash-based groupby identical to tAggregateRow. |
| ENG-ASR-002 | Feature Gap | No sorted-input validation -- does not verify input is sorted by group-by columns. |
| BUG-ASR-001 | Bug | Validation/processing config key mismatch -- `_validate_config()` accepts `GROUPBYS` but `_process()` only reads `group_bys`, causing runtime failure for converter-produced configs. |
| PERF-ASR-001 | Performance | No streaming aggregation -- pandas groupby requires O(N) memory, defeating the purpose of choosing tAggregateSortedRow for large datasets. |
| TEST-ASR-001 | Testing | Zero unit tests for any aggregation function or edge case. |

#### P1 -- Major (16 issues)

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
| BUG-ASR-010 | Bug | `stddev`/`variance` aliases silently dropped in `_aggregate_grouped()` -- only `std`/`var` handled, aliases fall through producing no output column (silent data loss). |
| BUG-ASR-011 | Bug | Decimal precision lost for avg/mean in ungrouped `_apply_agg_function()` path -- `series.mean()` converts Decimal to float64, no Decimal guard unlike sum. |
| DUP-ASR-001 | Duplication | 95% code duplication with AggregateRow -- should share a base class. |
| PERF-ASR-002 | Performance | Multiple groupby passes for custom aggregations. |
| TEST-ASR-002 | Testing | No integration tests in V1 pipeline. |

#### P2 -- Moderate (18 issues)

| ID | Category | Summary |
|----|----------|---------|
| CONV-ASR-003 | Converter | Schema types not converted from Talend format. |
| CONV-ASR-004 | Converter | IGNORE_NULL extracted by converter but ignored by engine. |
| ENG-ASR-007 | Feature Gap | Error handling returns original input instead of empty DataFrame. |
| ENG-ASR-008 | Feature Gap | CONNECTION_FORMAT ignored. |
| ENG-ASR-009 | Feature Gap | Config key naming inconsistency (`group_bys` vs `group_by` vs `GROUPBYS`). |
| BUG-ASR-005 | Bug | Missing function key silently defaults to sum. |
| BUG-ASR-012 | Bug | `None` output_column creates column literally named `None` -- missing keys propagate `None` as column name instead of raising validation error. |
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

## 10. Detailed Code Walkthrough

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

## 11. Comparison: AggregateSortedRow vs AggregateRow

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

## 12. Recommendations

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

## 13. Appendix A: Function-by-Function Parity Matrix

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
| `std` / `stddev` | Yes | `std`: Yes (pandas std); **`stddev`: No** (alias silently dropped -- see BUG-ASR-010) | Yes | Grouped path only handles `std`; `stddev` alias falls through to unknown-function else clause |
| `var` / `variance` | Yes | `var`: Yes (pandas var); **`variance`: No** (alias silently dropped -- see BUG-ASR-010) | Yes | Grouped path only handles `var`; `variance` alias falls through to unknown-function else clause |
| `median` | Yes | Yes (pandas median) | Yes | |
| Unknown function | Error in Talend | **Defaults to sum** | **Defaults to sum** | Silent data corruption risk |

---

## 14. Appendix B: Configuration Key Cross-Reference

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

## 15. Appendix C: Converter Code Listing with Annotations

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

## 16. Appendix D: Engine Code Listing with Annotations

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

## 17. Appendix E: Registry and Import Chain

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

**CONFIRMED: Import chain is BROKEN.**

`engine.py` line 40:
```python
from .components.aggregate import AggregateSortedRow, Denormalize, Normalize, Replicate
```

But `components/aggregate/__init__.py` only exports `AggregateRow` and `UniqueRow`:
```python
from .aggregate_row import AggregateRow
from .unique_row import UniqueRow

__all__ = ["AggregateRow", "UniqueRow"]
```

`AggregateSortedRow` is defined in `components/transform/aggregate_sorted_row.py` and
exported from `components/transform/__init__.py`.

**Verification**: Running `python3 -c "from src.v1.engine.components.aggregate import
AggregateSortedRow"` produces an `ImportError`. The engine.py import line will fail at
module load time, preventing the ENTIRE engine from initializing. However, the actual
error that surfaces first is a different import error in `file/__init__.py` (case
sensitivity mismatch for `FileInputXml` vs `FileInputXML`), which may mask this issue.

This means the engine cannot currently be loaded as a Python module. The import chain
has multiple breakpoints.

| ID | Priority | Issue |
|----|----------|-------|
| IMP-ASR-001 | **P1** | `engine.py` imports `AggregateSortedRow` from `components.aggregate` but the class is defined in `components.transform`. The aggregate `__init__.py` does not export it. CONFIRMED broken -- `ImportError` at module load time. The engine cannot initialize. |

---

## 18. Appendix F: Logging Quality Assessment

| Aspect | Assessment |
|--------|------------|
| Logger setup | Module-level `logger = logging.getLogger(__name__)` -- correct |
| Component ID prefix | All log messages use `[{self.id}]` prefix -- correct |
| Level usage | INFO for milestones, WARNING for recoverable issues, ERROR for failures -- correct |
| Start/complete logging | `_process()` logs start (line 112) and completion (line 177) with row counts -- correct |
| Sensitive data | No sensitive data logged -- correct |
| No print statements | No `print()` calls in engine code -- correct (converter has print() -- see DBG-ASR-001) |
| Debug diagnostics | No excessive debug logging -- good for production. However, no DEBUG-level logging exists for detailed troubleshooting. The `AggregateRow` sister component has extensive DEBUG/INFO logging for each operation; `AggregateSortedRow` does not. |

### Error Handling Quality

| Aspect | Assessment |
|--------|------------|
| Custom exceptions | Does NOT use `ComponentExecutionError` from base -- inconsistent with `AggregateRow` |
| Exception chaining | Uses bare `raise` (re-raise) on line 185 -- loses component context |
| `die_on_error` handling | Conditional raise/return in single try/except block (lines 182-186) -- correct structure but returns wrong data on error |
| No bare `except` | All except clauses specify `Exception` -- correct |
| Error messages | Include component ID in log but not in exception -- partially correct |
| Graceful degradation | **BROKEN** -- returns original input DataFrame instead of empty DataFrame on failure |

### Type Hints

| Aspect | Assessment |
|--------|------------|
| Method signatures | All methods have return type hints -- correct |
| Parameter types | `_process()`, `_aggregate_all()`, `_aggregate_grouped()` all have parameter type hints -- correct |
| Complex types | Uses `Dict[str, Any]`, `Optional[pd.DataFrame]`, `List[Dict]`, `List[str]` -- correct |

---

## 19. Cross-Cutting Bugs (Shared Infrastructure)

These bugs live in shared base classes and affect ALL v1 engine components, including
`AggregateSortedRow`. They are documented here because they directly impact the
component's runtime behavior.

### 19.1 `_update_global_map()` Crash (base_component.py line 304)

**Location**: `src/v1/engine/base_component.py`, line 304

```python
def _update_global_map(self) -> None:
    """Update global map with component statistics"""
    if self.global_map:
        for stat_name, stat_value in self.stats.items():
            self.global_map.put_component_stat(self.id, stat_name, stat_value)
        # Log the statistics for debugging
        logger.info(f"Component {self.id}: Updated stats - NB_LINE:{self.stats['NB_LINE']} "
                     f"NB_LINE_OK:{self.stats['NB_LINE_OK']} NB_LINE_REJECT:{self.stats['NB_LINE_REJECT']} "
                     f"{stat_name}: {value}")  # <-- BUG: 'value' is undefined
```

**Bug**: The log statement on line 304 references `{value}` but the loop variable is
named `stat_value`, not `value`. This causes a `NameError` at runtime whenever
`self.global_map` is not None and the for-loop completes.

**Impact on AggregateSortedRow**: After `AggregateSortedRow._process()` completes,
`BaseComponent.execute()` calls `self._update_global_map()` (line 218). If a `GlobalMap`
instance is provided to the component (which is the normal production case), the method
will crash with `NameError: name 'value' is not defined`. This means:
1. Statistics are correctly stored in the GlobalMap (the `put_component_stat()` calls
   inside the for-loop succeed).
2. The crash occurs on the log statement AFTER the loop completes.
3. Because `stat_name` is still bound to the last loop variable, it will be defined.
   But `value` was never defined in this scope.
4. The `NameError` will propagate up through `execute()`, which catches `Exception` on
   line 224. The exception handler also calls `_update_global_map()` (line 231), creating
   a potential infinite recursion that terminates when the second `NameError` propagates
   out of the error handler.

| ID | Priority | Issue |
|----|----------|-------|
| XCUT-ASR-001 | **P0** | `_update_global_map()` references undefined variable `value` (should be `stat_value`). Will crash ALL components when `global_map` is set. Verified in `base_component.py` line 304. |

### 19.2 `GlobalMap.get()` Crash (global_map.py line 28)

**Location**: `src/v1/engine/global_map.py`, lines 26-28

```python
def get(self, key: str) -> Optional[Any]:
    """Retrieve a value from the global map"""
    return self._map.get(key, default)  # <-- BUG: 'default' is not a parameter
```

**Bug**: The method signature is `def get(self, key: str) -> Optional[Any]` but the body
calls `self._map.get(key, default)`. The parameter `default` does not exist in the method
signature, causing `NameError` on every call to `global_map.get()`.

**Compound bug**: `get_component_stat()` on line 58 calls `self.get(key, default)` passing
TWO arguments to a method that only accepts ONE positional argument (`key`). This causes
`TypeError: get() takes 2 positional arguments but 3 were given`.

**Impact on AggregateSortedRow**: Any downstream component or trigger that calls
`global_map.get()` or `global_map.get_component_stat()` to read statistics set by
`AggregateSortedRow` will crash. For example, reading `{id}_NB_LINE` via the convenience
method `get_nb_line()` -> `get_component_stat()` -> `get()` will fail.

| ID | Priority | Issue |
|----|----------|-------|
| XCUT-ASR-002 | **P0** | `GlobalMap.get()` references undefined `default` parameter. Will crash on any `.get()` call. `get_component_stat()` also passes wrong number of arguments. |

### 19.3 Impact Summary for AggregateSortedRow

The combination of XCUT-ASR-001 and XCUT-ASR-002 means that in any production
deployment where a `GlobalMap` is used:

1. `AggregateSortedRow` will complete its aggregation correctly.
2. `_update_stats()` will correctly update `self.stats`.
3. `_update_global_map()` will correctly store stats in the GlobalMap via `put_component_stat()`.
4. The crash occurs on the INFO log statement after the for-loop completes.
5. Any downstream code reading stats via `GlobalMap.get()` will also crash.

**Net effect**: The component's core aggregation logic works, but the statistics
infrastructure around it is broken. Any job that relies on globalMap for inter-component
communication or statistics tracking will fail.

---

## 20. Edge-Case Analysis

### Edge Case 1: NaN Values in Aggregation Columns

| Aspect | Detail |
|--------|--------|
| **Talend** | When `IGNORE_NULL=true` (default), null values are excluded from aggregation. When `IGNORE_NULL=false`, nulls participate and may produce null results. For `count`, `IGNORE_NULL=true` counts only non-null values; `IGNORE_NULL=false` counts all rows including nulls. |
| **V1 Engine** | Pandas' default behavior for most aggregation functions (`sum`, `mean`, `min`, `max`, `std`, `var`, `median`) is to skip NaN values (`skipna=True`). This matches Talend's `IGNORE_NULL=true` behavior. However, the engine provides NO mechanism to change this behavior for `IGNORE_NULL=false`. The `ignore_null` flag is extracted by the converter (line 2161) but never read by the engine. |
| **Specific behaviors**: | |
| `sum` with NaN | Pandas `sum(skipna=True)` returns the sum of non-NaN values (e.g., `[1, NaN, 3].sum() = 4`). Matches Talend IGNORE_NULL=true. With IGNORE_NULL=false, Talend returns null; pandas returns 4. |
| `count` with NaN | Pandas `count()` counts non-NaN values. Pandas `size()` counts all rows. Engine uses `count()` for named columns and `size()` for count-without-input. This partially matches Talend: count with IGNORE_NULL=true = count non-null = pandas count(). count with IGNORE_NULL=false = count all rows = pandas size(). But the engine always uses count() regardless of IGNORE_NULL. |
| `min`/`max` with NaN | Pandas `min(skipna=True)`/`max(skipna=True)` ignores NaN. Matches Talend IGNORE_NULL=true. With IGNORE_NULL=false, Talend returns null; pandas still returns the non-NaN min/max. |
| `avg`/`mean` with NaN | Pandas `mean(skipna=True)` ignores NaN. `[1, NaN, 3].mean() = 2.0`, not 1.333. Matches Talend IGNORE_NULL=true. |
| `first` with NaN | Engine uses `df.groupby().first()` which returns the first NON-NaN value (this is pandas' behavior). Talend `first` returns the literal first value (which may be null). **This is a semantic mismatch**: for sorted input `[NaN, 1, 2]`, Talend `first` returns NaN, pandas `first()` returns 1. |
| `last` with NaN | Same issue as `first`: pandas `last()` returns last non-NaN, Talend returns literal last value. |
| `list` with NaN | Engine uses `apply(list)` which includes NaN values in the list. Talend with IGNORE_NULL=true would exclude them. **Mismatch for IGNORE_NULL=true.** |
| `concat` with NaN | Engine uses `.astype(str)` which converts NaN to the string `"nan"`. Talend would either skip nulls (IGNORE_NULL=true) or include empty string (IGNORE_NULL=false). The string `"nan"` in concatenated output is almost certainly wrong. |
| **Verdict** | **PARTIAL -- matches Talend IGNORE_NULL=true for most functions, but `first`/`last` have semantic mismatch, `list` includes NaN when it should not, and `concat` produces "nan" strings.** |

| ID | Priority | Issue |
|----|----------|-------|
| EDGE-ASR-001 | **P1** | `first()`/`last()` use pandas skip-NaN semantics instead of Talend literal-position semantics. For sorted input `[NaN, 1, 2]`, pandas returns 1/2 but Talend returns NaN/2. |
| EDGE-ASR-002 | **P1** | `concat`/`concatenate` converts NaN to literal string `"nan"` via `.astype(str)`. Should either skip NaN (IGNORE_NULL=true) or use empty string (IGNORE_NULL=false). |
| EDGE-ASR-003 | **P2** | `list` aggregation includes NaN values. When IGNORE_NULL=true (Talend default), NaN should be excluded from the collected list. |

### Edge Case 2: Empty String Values in Aggregation Columns

| Aspect | Detail |
|--------|--------|
| **Talend** | Empty strings (`""`) are NOT null. They participate in all aggregations. `count` of `["", "a", ""]` = 3. `min` of `["", "a", "b"]` = `""` (empty string sorts before any character in Java). `concat` of `["", "a", ""]` with comma delimiter = `",a,"`. |
| **V1 Engine** | Pandas treats empty strings as valid values (not NaN). `count` correctly counts them. `min` correctly returns `""` (empty string compares as less-than in Python, matching Java behavior). `sum` of strings will concatenate them (pandas string sum), which differs from Talend numeric sum. `concat` via `delimiter.join(series.astype(str))` correctly includes empty strings. |
| **Verdict** | **CORRECT for most functions.** Empty strings are handled identically to Talend. The main risk is if empty strings are used in numeric aggregation columns, where Talend would fail with a type error and route to REJECT, while the engine would either produce NaN (if the column is numeric) or concatenate strings (if the column is object type). |

### Edge Case 3: Does It Actually Require Pre-Sorted Input?

| Aspect | Detail |
|--------|--------|
| **Talend** | YES, absolutely. `tAggregateSortedRow` processes rows sequentially, detecting group boundaries by comparing each row's group-by values to the previous row. If data is not sorted, non-contiguous occurrences of the same group key produce separate (duplicate) output groups with partial aggregation results. This is silent data corruption. |
| **V1 Engine** | NO. The engine uses `pandas.DataFrame.groupby()` which uses a hash-based grouping strategy. It correctly groups ALL rows with the same key regardless of input order. Unsorted input produces correct results. |
| **Consequence** | The engine "accidentally" handles a case that Talend cannot: unsorted input. This is both a benefit (no silent corruption from unsorted input) and a risk (jobs that appear to work in V1 may fail silently when ported back to Talend). It also means the engine gains NO performance benefit from sorted input -- it always does O(N) hash grouping regardless. |
| **Verdict** | **DIVERGENT -- not a bug per se, but a fundamental behavioral difference. The component is a copy of AggregateRow, not a true sorted-input streaming aggregator.** |

### Edge Case 4: HYBRID Streaming Mode

| Aspect | Detail |
|--------|--------|
| **Talend** | `tAggregateSortedRow` natively streams. It processes one row at a time, holding at most one group's accumulated state in memory. It does NOT batch or chunk. |
| **V1 Engine** | The engine has NO streaming or HYBRID mode for aggregation. The `BaseComponent` supports HYBRID mode for file I/O components (e.g., `FileInputDelimited` activates streaming for files > 3GB), but `AggregateSortedRow._process()` receives the full `input_data` DataFrame in a single call. There is no `_read_streaming()` or chunk-based processing path. |
| **Impact** | For the scenario `tFileInputDelimited (HYBRID) -> tSortRow -> tAggregateSortedRow`, the file input may stream in chunks, but once the sort component collects all chunks (sort requires full data), the aggregation component receives the complete DataFrame. Even if a hypothetical streaming aggregation were implemented, it could not activate until the sort is complete, so the actual memory benefit is limited by the sort step. |
| **Verdict** | **GAP -- no streaming mode exists. However, the practical impact is mitigated by the fact that the upstream `tSortRow` already requires full data in memory. The streaming gap only matters when input is ALREADY sorted (e.g., from a pre-sorted file or database ORDER BY query).** |

### Edge Case 5: Decimal Precision in Aggregation

| Aspect | Detail |
|--------|--------|
| **Talend** | `BigDecimal` columns maintain arbitrary precision through aggregation. `sum` uses `BigDecimal.add()`. `avg` uses `BigDecimal` division with configurable scale and rounding mode. `min`/`max` use `BigDecimal.compareTo()`. |
| **V1 Engine** | The engine has **special handling for Decimal in sum only**: `_is_decimal_column()` checks if a series contains `Decimal` objects, and if so, uses Python's `sum(series.dropna(), Decimal('0'))` instead of pandas `sum()`. This preserves exact Decimal precision for sum. However, for ALL OTHER FUNCTIONS (`mean`, `min`, `max`, `std`, `var`, `median`), the engine uses pandas' default numeric operations, which convert Decimals to float64 internally. This loses precision for values that exceed float64's 15-16 significant digits. |
| **Specific risks**: | |
| `sum` of Decimal | CORRECT -- uses Python `sum()` with Decimal accumulator (line 355, 385). Preserves arbitrary precision. |
| `avg`/`mean` of Decimal | **INCORRECT** -- pandas `mean()` converts to float64. A column with values `[Decimal('1.123456789012345678'), Decimal('2.987654321098765432')]` will lose digits beyond ~15th place. |
| `min`/`max` of Decimal | **RISKY** -- pandas comparison of Decimal objects may work correctly (Python's `Decimal.__lt__` is used), but the result is not guaranteed to remain a Decimal in the output DataFrame. Pandas may downcast to float64. |
| `count_distinct` of Decimal | CORRECT -- `nunique()` counts unique values, no arithmetic precision concern. |
| `list` of Decimal | CORRECT -- `apply(list)` preserves original objects. |
| `concat` of Decimal | CORRECT -- `.astype(str)` converts Decimal to its string representation, which is exact. |
| **Verdict** | **PARTIAL -- sum is correctly handled, but avg/mean loses precision for Decimal columns. min/max may also lose precision in the output.** |

| ID | Priority | Issue |
|----|----------|-------|
| EDGE-ASR-004 | **P1** | Decimal precision lost for `avg`/`mean` aggregation. Pandas converts to float64 internally, losing precision beyond ~15 significant digits. Only `sum` has explicit Decimal handling. |
| EDGE-ASR-005 | **P2** | Decimal values may be downcast to float64 for `min`/`max` operations in pandas groupby output. |

### Edge Case 6: `_update_global_map` Crash (Confirmed Cross-Cutting)

This is documented in Section 19.1 above but deserves explicit mention in the edge-case
checklist as it was specifically requested.

| Aspect | Detail |
|--------|--------|
| **Crash trigger** | Any execution where `self.global_map is not None` (i.e., production use). |
| **Root cause** | `base_component.py` line 304 uses undefined variable `value` instead of `stat_value`. |
| **AggregateSortedRow impact** | Component aggregation completes correctly. Stats are written to GlobalMap. Then the log statement crashes with `NameError`. This may be caught by the outer exception handler in `execute()`, but that handler also calls `_update_global_map()`, potentially causing a second crash. |
| **Verdict** | **P0 BUG -- confirmed cross-cutting, affects all components.** |

### Edge Case 7: Function Name Mapping (avg -> mean) Bug

| Aspect | Detail |
|--------|--------|
| **Scenario** | User configures an operation with `function: "avg"` in Talend (common for average). |
| **Converter output** | `{'function': 'avg', 'input_column': 'amount', 'output_column': 'avg_amount'}` |
| **Engine normalization** | Line 143: `function = op.get('function', 'sum').lower()` -> `'avg'` |
| **Engine agg_dict** | Line 278: `agg_dict[input_col].append('mean')` -- maps `avg` to pandas `mean` |
| **Pandas groupby result** | MultiIndex column: `('amount', 'mean')` |
| **MultiIndex matching** | Line 329: `op['function'] == func_name` -> `'avg' == 'mean'` -> `False` |
| **Fallback behavior** | Line 338: Column named `'amount_mean'` instead of `'avg_amount'` |
| **Downstream impact** | Output column name is `'amount_mean'` instead of the expected `'avg_amount'`. Any downstream component referencing `'avg_amount'` will fail with a column-not-found error. |
| **Same bug for**: | `count_distinct` -> `nunique`, `stddev` -> `std`, `variance` -> `var` |
| **Verdict** | **P1 BUG -- function name mapping breaks MultiIndex column naming for avg, count_distinct, and alias functions. Only affects the MultiIndex path (triggered when same input column has multiple aggregations).** |

| ID | Priority | Issue |
|----|----------|-------|
| EDGE-ASR-006 | **P1** | avg/mean, count_distinct/nunique, stddev/std, variance/var function name mapping breaks MultiIndex column naming. The `op['function']` stored by the normalizer retains the Talend name (e.g., `avg`) but pandas uses `mean` in its MultiIndex, causing the match at line 329 to fail and producing wrong output column names. |

### Edge Case 8: Population Standard Deviation vs Sample Standard Deviation

| Aspect | Detail |
|--------|--------|
| **Talend** | Supports three standard deviation variants: `standard deviation` (sample, N-1), `population standard deviation` (N), and `sample standard deviation` (N-1, same as standard deviation). |
| **V1 Engine** | Only supports `std` / `stddev` which maps to pandas `std()` with default `ddof=1` (sample standard deviation, N-1). There is NO support for population standard deviation (`ddof=0`). |
| **Impact** | Jobs using `population standard deviation` in Talend will produce incorrect results in V1 -- the values will be slightly different due to the N vs N-1 denominator. For small groups (e.g., 2-5 rows), the difference can be significant (up to 41% for a 2-row group). |
| **Verdict** | **GAP -- population standard deviation not supported. Produces silently incorrect results.** |

| ID | Priority | Issue |
|----|----------|-------|
| EDGE-ASR-007 | **P2** | Population standard deviation (`ddof=0`) not supported. Engine always uses sample standard deviation (`ddof=1`). Talend supports both variants. |

### Edge Case 9: Union (Geometry) Function

| Aspect | Detail |
|--------|--------|
| **Talend** | Supports `union (geometry)` aggregation function for spatial data types. |
| **V1 Engine** | Not supported. Not mentioned in code. Would require a spatial library (e.g., Shapely/GeoPandas). |
| **Verdict** | **GAP -- low priority unless spatial data jobs are in scope.** |

| ID | Priority | Issue |
|----|----------|-------|
| EDGE-ASR-008 | **P3** | `union (geometry)` aggregation function not supported. Requires spatial library. |

### Edge Case 10: List (Object) Function

| Aspect | Detail |
|--------|--------|
| **Talend** | Supports `list (object)` which collects values into a Java `ArrayList<Object>` preserving original types. Different from `list` which collects as strings. |
| **V1 Engine** | The `list` function uses `apply(list)` which preserves Python object types (not just strings). So the V1 `list` function is closer to Talend's `list (object)` than Talend's `list`. |
| **Verdict** | **ACCEPTABLE -- V1 `list` preserves original types, which is the more useful behavior.** |

### Edge Case 11: Single Group (All Rows Have Same Key)

| Aspect | Detail |
|--------|--------|
| **Talend** | Produces one output row. In sorted-streaming mode, this means the component accumulates the entire dataset before emitting (since the group key never changes until EOF). |
| **V1 Engine** | `groupby()` produces one group. Works correctly. No special-case behavior needed. |
| **Verdict** | **CORRECT** |

### Edge Case 12: All Null Group-By Column

| Aspect | Detail |
|--------|--------|
| **Talend** | Rows where the group-by column is null are grouped together (null == null for grouping purposes). |
| **V1 Engine** | Pandas `groupby()` by default DROPS rows where the group-by key is NaN (`dropna=True` is the pandas default). This means rows with null group-by values are silently excluded from all aggregation results. |
| **Verdict** | **BUG -- pandas groupby drops NaN keys by default. To match Talend, should pass `dropna=False` to `groupby()`.** |

| ID | Priority | Issue |
|----|----------|-------|
| EDGE-ASR-009 | **P1** | `groupby(valid_group_by, as_index=False)` uses pandas default `dropna=True`, silently dropping all rows where the group-by column is NaN/None. Talend groups null keys together. Should use `groupby(valid_group_by, as_index=False, dropna=False)`. |

### Edge Case 13: Very Large Number of Groups

| Aspect | Detail |
|--------|--------|
| **Talend** | With sorted-streaming, memory is O(1) per group regardless of group count. 1 million groups is fine. |
| **V1 Engine** | `pandas.groupby()` builds a hash index of all groups. Memory is O(G) where G is the number of unique groups. For 1M+ groups, this can be significant. Additionally, the result DataFrame has G rows, which is expected. |
| **Verdict** | **ACCEPTABLE for typical use cases. Performance degrades relative to Talend for very high group cardinality.** |

---

## 21. IGNORE_NULL Deep Dive

This section provides a comprehensive analysis of the `IGNORE_NULL` feature since it was
specifically called out in the edge-case checklist and represents a significant gap.

### 21.1 Talend Behavior

In Talend's `tAggregateSortedRow`, each operation in the OPERATIONS table has an
`IGNORE_NULL` checkbox (per-operation, not global). The default is `true`.

**When IGNORE_NULL = true (default)**:
- `sum([1, null, 3])` = 4 (nulls excluded)
- `count([1, null, 3])` = 2 (only non-null counted)
- `avg([1, null, 3])` = 2.0 (average of 1 and 3)
- `min([1, null, 3])` = 1 (nulls excluded)
- `max([1, null, 3])` = 3 (nulls excluded)
- `first([null, 1, 2])` = 1 (first non-null value)
- `last([1, 2, null])` = 2 (last non-null value)
- `list([1, null, 3])` = [1, 3] (nulls excluded)
- `concat([a, null, c], delimiter=',')` = "a,c" (nulls excluded)
- `count_distinct([1, null, 1, 3])` = 2 (distinct non-null values: 1, 3)

**When IGNORE_NULL = false**:
- `sum([1, null, 3])` = null (null poisons the result)
- `count([1, null, 3])` = 3 (all rows counted)
- `avg([1, null, 3])` = null (null poisons the result)
- `min([1, null, 3])` = null (null is "less than" any value in Java comparison)
- `max([1, null, 3])` = 3 (null is "less than" any value)
- `first([null, 1, 2])` = null (literal first value)
- `last([1, 2, null])` = null (literal last value)
- `list([1, null, 3])` = [1, null, 3] (nulls included)
- `concat([a, null, c], delimiter=',')` = "a,null,c" or "a,,c" (null represented)
- `count_distinct([1, null, 1, 3])` = 3 (null counts as a distinct value)

### 21.2 V1 Engine Behavior (Current)

The engine does NOT read the `ignore_null` flag. Its behavior is dictated by pandas defaults:

| Function | Pandas Default | Matches IGNORE_NULL=true? | Matches IGNORE_NULL=false? |
|----------|---------------|---------------------------|----------------------------|
| `sum` | `skipna=True` | Yes | **No** |
| `count` | Counts non-NaN | Yes | **No** (should count all) |
| `mean`/`avg` | `skipna=True` | Yes | **No** |
| `min` | `skipna=True` | Yes | **No** |
| `max` | `skipna=True` | Yes | **No** |
| `first` | First non-NaN | **No** (should be literal first) | **No** |
| `last` | Last non-NaN | **No** (should be literal last) | **No** |
| `nunique` | Excludes NaN | Yes | **No** (should count NaN) |
| `std` | `skipna=True` | Yes | **No** |
| `var` | `skipna=True` | Yes | **No** |
| `median` | `skipna=True` | Yes | **No** |
| `list` (apply) | Includes NaN | **No** (should exclude) | Yes |
| `concat` (apply) | NaN -> "nan" string | **No** (should exclude) | **No** (wrong representation) |

### 21.3 Implementation Recommendation

To implement IGNORE_NULL properly:

**For IGNORE_NULL=true** (default, mostly already working):
- Fix `first`/`last` to use `series.dropna().iloc[0]`/`series.dropna().iloc[-1]`
- Fix `list` to use `series.dropna().tolist()`
- Fix `concat` to use `series.dropna().astype(str)` before joining

**For IGNORE_NULL=false** (not yet supported):
- `sum`/`mean`/`min`/`max`/`std`/`var`/`median`: Use `skipna=False` parameter
- `count`: Use `len(series)` instead of `series.count()`
- `first`/`last`: Use `series.iloc[0]`/`series.iloc[-1]` (literal position)
- `nunique`: Include NaN as a distinct value: `series.nunique(dropna=False)`
- `list`: Use `series.tolist()` (includes NaN)
- `concat`: Replace NaN with empty string or "null" before joining

---

## 22. Appendix G: GlobalMap Variable Coverage

| Variable | Talend Sets? | V1 Sets? | How V1 Sets It | Notes |
|----------|-------------|----------|-----------------|-------|
| `{id}_NB_LINE` | Yes | **Yes** | `_update_stats(rows_in, ...)` -> `_update_global_map()` -> `global_map.put_component_stat()` | Set correctly, but `_update_global_map()` crashes after writing (XCUT-ASR-001) |
| `{id}_NB_LINE_OK` | Yes | **Yes** | Same mechanism | Always equals output row count (correct for aggregation -- no reject) |
| `{id}_NB_LINE_REJECT` | Yes | **Partial** | Same mechanism | Always 0 since no reject flow exists |
| `{id}_ERROR_MESSAGE` | Yes (official) | **No** | -- | Not implemented. Error messages are only logged, not stored in globalMap. |
| `{id}_EXECUTION_TIME` | N/A (v1 only) | **Yes** | Base class | V1-specific, not in Talend |

---

## 23. Appendix H: Issue Count Summary

### By Priority

| Priority | Count | Categories |
|----------|-------|------------|
| P0 | 5 | 2 feature gaps, 1 bug, 1 performance, 1 testing, + 2 cross-cutting |
| P1 | 18 | 2 converter, 6 engine feature gaps, 6 bugs, 1 debug, 1 error handling, 1 duplication, 1 performance, 1 testing, + 4 edge-case |
| P2 | 18 | 2 converter, 4 engine, 2 bugs, 2 duplication, 3 naming, 3 standards, 2 error handling, 2 performance, + 3 edge-case |
| P3 | 5 | 1 converter, 1 engine, 1 naming, 1 standards, 1 security, + 1 edge-case |
| **Total** | **46** | Plus 2 cross-cutting P0 issues shared with all components |

### By Category

| Category | Count | P0 | P1 | P2 | P3 |
|----------|-------|----|----|----|----|
| Cross-Cutting Bugs | 2 | 2 | 0 | 0 | 0 |
| Converter | 5 | 0 | 2 | 2 | 1 |
| Engine Feature Gaps | 13 | 2 | 6 | 4 | 1 |
| Bugs | 8 | 1 | 5 | 2 | 0 |
| Edge Cases | 9 | 0 | 4 | 3 | 2 |
| Performance | 4 | 1 | 1 | 2 | 0 |
| Testing | 2 | 1 | 1 | 0 | 0 |
| Code Quality (Naming/Standards/Debug/Error/Duplication/Security) | 13 | 0 | 3 | 7 | 3 |

### Full Issue Index (Alphabetical by ID)

| ID | Priority | Section | One-Line Summary |
|----|----------|---------|------------------|
| BUG-ASR-001 | P0 | 6.1 | Config key mismatch: `_validate_config()` accepts GROUPBYS but `_process()` only reads group_bys |
| BUG-ASR-002 | P1 | 6.1 | Dead code: `_aggregate_all()` unreachable for empty group_bys due to prior ValueError |
| BUG-ASR-003 | P1 | 6.1 | Column name collision when same input column has multiple aggregation operations |
| BUG-ASR-004 | P1 | 6.1 | Same input/output column name handling fails in MultiIndex case |
| BUG-ASR-005 | P2 | 6.1 | Missing function key silently defaults to sum instead of failing |
| BUG-ASR-010 | P1 | 6.1 | `stddev`/`variance` aliases silently dropped in `_aggregate_grouped()` -- only `std`/`var` handled, producing no output column (silent data loss) |
| BUG-ASR-011 | P1 | 6.1 | Decimal precision lost for avg/mean in ungrouped `_apply_agg_function()` path -- `series.mean()` converts Decimal to float64 |
| BUG-ASR-012 | P2 | 6.1 | `None` output_column creates column literally named `None` when operation lacks output_column/input_column/column keys |
| CONV-ASR-001 | P1 | 4 | DIE_ON_ERROR not extracted from Talend XML |
| CONV-ASR-002 | P1 | 4 | Operations parsing uses fragile hardcoded stride of 4 |
| CONV-ASR-003 | P2 | 4 | Schema types not converted from Talend format |
| CONV-ASR-004 | P2 | 4 | IGNORE_NULL extracted by converter but ignored by engine |
| CONV-ASR-005 | P3 | 4 | Debug print() should be logger.debug() |
| DBG-ASR-001 | P1 | 6.5 | print() statements in converter production code (lines 2178-2179) |
| DUP-ASR-001 | P1 | 6.2 | 95% code duplication with AggregateRow |
| DUP-ASR-002 | P2 | 6.2 | Dual config key checking pattern repeated without normalization |
| EDGE-ASR-001 | P1 | 20 | first()/last() use pandas skip-NaN instead of Talend literal-position semantics |
| EDGE-ASR-002 | P1 | 20 | concat converts NaN to literal string "nan" |
| EDGE-ASR-003 | P2 | 20 | list aggregation includes NaN when IGNORE_NULL=true should exclude them |
| EDGE-ASR-004 | P1 | 20 | Decimal precision lost for avg/mean aggregation (float64 conversion) |
| EDGE-ASR-005 | P2 | 20 | Decimal values may be downcast for min/max in groupby output |
| EDGE-ASR-006 | P1 | 20 | avg/mean, count_distinct/nunique function name mapping breaks MultiIndex naming |
| EDGE-ASR-007 | P2 | 20 | Population standard deviation (ddof=0) not supported |
| EDGE-ASR-008 | P3 | 20 | union (geometry) function not supported |
| EDGE-ASR-009 | P1 | 20 | groupby drops NaN keys by default (dropna=True), silently excluding null-keyed rows |
| ENG-ASR-001 | P0 | 5 | No sorted-input streaming aggregation |
| ENG-ASR-002 | P0 | 5 | No sorted-input validation |
| ENG-ASR-003 | P1 | 5 | IGNORE_NULL not implemented |
| ENG-ASR-004 | P1 | 5 | No REJECT flow output |
| ENG-ASR-005 | P1 | 5 | ROW_COUNT extracted but never used |
| ENG-ASR-006 | P1 | 5 | First/Last semantics depend on DataFrame order |
| ENG-ASR-007 | P2 | 5 | Error handling returns original un-aggregated input |
| ENG-ASR-008 | P2 | 5 | CONNECTION_FORMAT ignored |
| ENG-ASR-009 | P2 | 5 | Config key naming inconsistency (group_bys vs group_by vs GROUPBYS) |
| ENG-ASR-010 | P3 | 5 | Schema type metadata not used for output coercion |
| ERR-ASR-001 | P1 | 6.6 | Silent error swallowing returns original un-aggregated input |
| ERR-ASR-002 | P2 | 6.6 | Inconsistent error behavior vs AggregateRow |
| ERR-ASR-003 | P2 | 6.6 | No ComponentExecutionError wrapping |
| IMP-ASR-001 | P1 | 17 | engine.py imports AggregateSortedRow from components.aggregate but class is in components.transform |
| NAME-ASR-001 | P2 | 6.3 | Config key group_bys differs from AggregateRow's group_by |
| NAME-ASR-002 | P2 | 6.3 | Converter maps to TAggregateSortedRow but class is AggregateSortedRow |
| NAME-ASR-003 | P2 | 6.3 | Lives in transform/ package while AggregateRow lives in aggregate/ |
| NAME-ASR-004 | P3 | 6.3 | Module docstring says "sorted" but implementation does not use sorting |
| PERF-ASR-001 | P0 | 7 | No streaming aggregation (O(N) memory vs Talend O(1)) |
| PERF-ASR-002 | P1 | 7 | Multiple groupby passes for custom aggregations |
| PERF-ASR-003 | P2 | 7 | Merge-based custom aggregation joining adds overhead |
| PERF-ASR-004 | P2 | 7 | Column nullification loop could be vectorized |
| SEC-ASR-001 | P3 | 6.7 | No input sanitization on column names |
| STD-ASR-001 | P2 | 6.4 | _validate_config() does not validate individual operations |
| STD-ASR-002 | P2 | 6.4 | No SUPPORTED_FUNCTIONS class constant |
| STD-ASR-003 | P2 | 6.4 | No DEFAULT class constants |
| STD-ASR-004 | P3 | 6.4 | row_count, connection_format, die_on_error not validated |
| TEST-ASR-001 | P0 | 8 | Zero unit tests for any aggregation function |
| TEST-ASR-002 | P1 | 8 | No integration tests in V1 pipeline |
| XCUT-ASR-001 | P0 | 19 | _update_global_map() crashes: undefined variable 'value' (base_component.py:304) |
| XCUT-ASR-002 | P0 | 19 | GlobalMap.get() crashes: undefined parameter 'default' (global_map.py:28) |

---

## 24. Final Verdict

**Production Readiness: NOT READY (RED)**

### Blocking Issues (Must Fix Before Any Production Use)

The `AggregateSortedRow` component has **7 P0-level issues** (5 component-specific + 2
cross-cutting) that individually or collectively block production deployment:

1. **XCUT-ASR-001 + XCUT-ASR-002**: The cross-cutting `_update_global_map()` crash and
   `GlobalMap.get()` crash affect ALL components. Any job using globalMap (the normal case)
   will crash after aggregation completes. These must be fixed first.

2. **ENG-ASR-001 + PERF-ASR-001**: The core differentiator of `tAggregateSortedRow` --
   streaming, O(1)-memory aggregation of sorted data -- is completely absent. The engine
   uses `pandas.groupby()` which requires O(N) memory. Jobs that chose this component
   specifically for memory efficiency with large datasets will not receive the expected
   benefit, and may OOM on datasets that Talend handles easily.

3. **BUG-ASR-001**: The config key mismatch between `_validate_config()` (accepts
   `GROUPBYS`) and `_process()` (only reads `group_bys`) means converter-produced configs
   will fail at runtime with `ValueError("GROUPBYS configuration is required.")`.

4. **TEST-ASR-001**: Zero unit tests. All 414 lines of engine code are completely
   unverified. For a data transformation component, incorrect aggregation silently
   corrupts data.

### Architectural Assessment

The component is **not a true sorted-input aggregator**. It is a near-duplicate of
`AggregateRow` placed in a different package with different config key names. The two
classes share 95% of their code, with identical `_apply_agg_function()` and
`_is_decimal_column()` methods. Neither implements the streaming sorted-input optimization
that distinguishes `tAggregateSortedRow` from `tAggregateRow` in Talend.

### Conditional Usability

**For jobs with small-to-medium datasets (<1M rows)**: After fixing BUG-ASR-001 and the
cross-cutting bugs, the component will produce correct aggregation results for basic
functions (sum, count, min, max) because `pandas.groupby()` handles any input order.
The memory overhead is acceptable for datasets that fit in RAM.

**For jobs with large datasets (>10M rows)**: NOT USABLE. The component will exhibit
the same memory limitations as `tAggregateRow`, defeating the purpose of choosing
`tAggregateSortedRow`. OOM failures are likely for datasets that Talend handles via
streaming.

**For jobs using IGNORE_NULL=false**: NOT USABLE. The engine has no mechanism to change
pandas' default null-skipping behavior. Results will be silently incorrect for operations
where nulls should participate.

**For jobs using avg/mean on columns with multiple aggregations**: BUGGY. The avg->mean
function name mapping breaks MultiIndex column naming, producing wrong output column
names.

### Minimum Fix Checklist Before Production

1. Fix `_update_global_map()` crash (XCUT-ASR-001) -- change `value` to `stat_value`
2. Fix `GlobalMap.get()` crash (XCUT-ASR-002) -- add `default` parameter
3. Fix BUG-ASR-001 -- normalize config keys to lowercase in `_process()`
4. Fix error handling (ERR-ASR-001) -- return empty DataFrame, not original input
5. Fix `groupby(dropna=False)` (EDGE-ASR-009) -- include NaN-keyed rows
6. Extract DIE_ON_ERROR in converter (CONV-ASR-001)
7. Remove print() statements (DBG-ASR-001 / CONV-ASR-005)
8. Write P0 unit tests (TEST-ASR-001)
9. Document that streaming optimization is not yet implemented

### Full Talend Parity Roadmap

For complete feature parity with Talend's `tAggregateSortedRow`:
1. Implement streaming sorted aggregation with O(1) memory per group
2. Implement IGNORE_NULL per-operation flag
3. Add sorted-input validation (at minimum, log a warning)
4. Implement REJECT flow with errorCode/errorMessage columns
5. Fix avg/mean and other function name mapping bugs for MultiIndex
6. Add Decimal precision handling for avg/mean/min/max
7. Implement population standard deviation variant
8. Refactor to share base class with AggregateRow
9. Move from transform/ to aggregate/ package for consistency

---

## 25. Appendix I: Talend Reference Sources

The following sources were consulted for the Talend feature baseline in this audit:

- [tAggregateSortedRow Standard properties | Talend Components Help (v8.0)](https://help.talend.com/en-US/components/8.0/processing/taggregatesortedrow-standard-properties)
- [tAggregateSortedRow | Talend Components Help (v8.0)](https://help.qlik.com/talend/en-US/components/8.0/processing/taggregatesortedrow)
- [tAggregateSortedRow Standard properties | Talend Components Help (v7.3)](https://help.qlik.com/talend/en-US/components/7.3/processing/taggregatesortedrow-standard-properties)
- [tAggregateRow vs tAggregateSortedRow - Talend Tutorials](https://talended.wordpress.com/2017/03/28/taggregaterow-vs-taggregatesortedrow/)
- [Talend Aggregate Sorted Row - Tutorial Gateway](https://www.tutorialgateway.org/talend-aggregate-sorted-row/)
- [tAggregateRow and tAggregateSortedRow in Talend - Tech-Netting](https://tech-netting.blogspot.com/2016/03/taggregaterow-and-taggregatesortedrow.html)
- [Difference between tAggregateRow and tAggregateSortedRow - dwetl.com](http://dwetl.com/2015/03/25/difference-between-taggregaterow-and-taggregatesortedrow/)
- [When to use tAggregateRow and when to use tSortRow + tAggregateSortedRow - Qlik Community](https://community.qlik.com/t5/Design-and-Development/When-to-use-tAggregateRow-and-when-to-use-tSortRow/td-p/2277442)
- [Aggregating the sorted data | Talend Components Help (v7.3)](https://help.qlik.com/talend/en-US/components/7.3/processing/tsortrow-taggregatesortedrow-tlogrow-tfixedflowinput-aggregating-sorted-data-standard-component)
- [Sorting the input data | Talend Components Help (v8.0)](https://help.talend.com/r/en-US/8.0/processing/tsortrow-taggregatesortedrow-tlogrow-tfixedflowinput-sorting-input-data-standard-component)
- [Sorting and aggregating input data | Talend Components Help (v8.0)](https://help.qlik.com/talend/en-US/components/8.0/processing/tsortrow-taggregatesortedrow-tlogrow-tfixedflowinput-sorting-and-aggregating-input-data-standard-component-this)
