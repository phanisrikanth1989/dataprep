# Phase 6: Transform Group A -- Aggregation, Sort, Filter - Research

**Researched:** 2026-04-15
**Domain:** Engine transform components (tAggregateRow, tSortRow, tFilterRow) -- full rewrites with Talend feature parity
**Confidence:** HIGH

## Summary

Phase 6 rewrites the three most complex transform components from scratch: tAggregateRow, tSortRow, and tFilterRow. All three are well-understood: converter output configs are verified from real converted JSON samples, Talend behavior is documented in audit reports, and the Phase 4 rewrite pattern (ENGINE_COMPONENT_PATTERN.md) is established. The primary complexity is in tFilterRow (14+ operators + 8 FUNCTION pre-transforms + Java bridge advanced mode) and tAggregateRow (12 aggregation functions + ignore_null + Decimal precision + groupby column renaming).

Key finding: the converter currently performs a lossy mapping of `population_std_dev` to `std`, which means the engine receives `"std"` for both sample and population std dev. Per D-10, population_std_dev needs `ddof=0`. This requires either a converter fix (pass `"population_std_dev"` through) or the engine must infer from context -- the converter fix is cleaner and consistent with D-04 (engine reads converter keys directly).

**Primary recommendation:** Follow the Phase 4 rewrite pattern exactly -- `@REGISTRY.register()` decorator, `_validate_config()` raising `ConfigurationError`, `_process()` returning `{'main': df, 'reject': df_or_None}`, all config read inside `_process()`. One plan per component + one combined test plan.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Full rewrite from scratch for all three components. Not patching existing code. Conform to ENGINE_COMPONENT_PATTERN.md blueprint with `@REGISTRY.register()` decorators.
- **D-02:** All P0-P3 items addressed -- rewrites naturally handle P2/P3 items (debug prints, optimization) since we're writing fresh code.
- **D-03:** Plan structure: 1 plan per component (AggregateRow, SortRow, FilterRow) + 1 combined test plan.
- **D-04:** Config key alignment same as Phase 4 (D-04) -- engine reads converter keys directly. `groupbys` not `group_by`, `criteria` not `sort_columns`, `logical_op` not `logical_operator`, `advanced_cond` not `advanced_condition`.
- **D-05:** Replace eval() with operator-function map. Conditions are already structured dicts from converter (`column`, `function`, `operator`, `value`), so map each Talend operator to a pandas vectorized operation. No AST parsing needed.
- **D-06:** Implement all 14+ Talend operators: `==`, `!=`, `>`, `<`, `>=`, `<=`, `MATCHES` (regex), `CONTAINS`, `STARTS_WITH`, `ENDS_WITH`, `IS_NULL`, `IS_NOT_NULL`, `LENGTH_LT`, `LENGTH_GT`.
- **D-07:** Implement all 8 FUNCTION pre-transforms: LOWER, UPPER, LENGTH, TRIM, LTRIM, RTRIM, LEFT, RIGHT. Applied to column values before operator comparison.
- **D-08:** Advanced conditions ({{java}} marked) delegate to Java bridge, consistent with tMap approach.
- **D-09:** list_object maps to delimited string -- Talend list_object produces `"a,b,c"` string. Engine implements as concat with delimiter (Talend behavior).
- **D-10:** population_std_dev gets dedicated implementation with `series.std(ddof=0)`, not lossy mapping to sample std (ddof=1).
- **D-11:** ignore_null when false: use `skipna=False` in pandas aggregation. Null + any = null (Talend behavior).
- **D-12:** use_financial_precision: when true, convert numeric columns to Decimal before aggregation, preserve Decimal precision through output.
- **D-13:** Converter outputs `groupbys` (list of dicts with `output_column`, `input_column`) and `operations` (list of dicts with `output_column`, `function`, `input_column`, `ignore_null`). Engine reads these directly.
- **D-14:** Implement all 3 sort types from `criteria` list: `num` (cast to numeric before sort), `alpha` (string sort, case-sensitive), `date` (parse to datetime before sort).
- **D-15:** Simplify to pandas sort_values() for all sizes. Keep `external` flag as future hook but don't implement parquet chunking.
- **D-16:** Remove engine-only config keys (na_position, case_sensitive, chunk_size) that are not Talend params.
- **D-17:** Remove streaming sort mode. Sort inherently requires all data.
- **D-18:** Converter outputs `criteria` (list of dicts with `column`, `sort_type`, `order`). Engine reads this directly.
- **D-19:** Test location: `tests/v1/engine/components/aggregate/test_aggregate_row.py`, `tests/v1/engine/components/transform/test_sort_row.py`, `tests/v1/engine/components/transform/test_filter_rows.py`.
- **D-20:** Exhaustive coverage per requirement. Every AGGR/SORT/FROW requirement gets dedicated test cases.
- **D-21:** Tests use programmatic DataFrame creation (no fixture files needed for transform components).

### Claude's Discretion
- Internal method decomposition within each component
- Exact operator implementation details (regex engine, string comparison mechanics)
- How to handle edge cases not specified by Talend (empty DataFrames, missing columns)
- Decimal conversion strategy details for financial precision mode

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| AGGR-01 | Fix `_ensure_output_columns` else-branch that nulls computed aggregation columns (P0) | Full rewrite eliminates this -- output schema driven by `groupbys` + `operations` config, no _ensure_output_columns method needed |
| AGGR-02 | Fix output_column ignored in grouped mode (P1) | Rewrite uses `output_column` from each operation dict as the result column name directly |
| AGGR-03 | Implement ignore_null support for aggregation functions (P1) | pandas `skipna=False` propagates NaN per Talend behavior; groupby lambda approach verified |
| AGGR-04 | Implement missing aggregation functions (list_object, union, population_std_dev) (P1) | list -> delimiter.join(); population_std_dev -> ddof=0; union -> not Talend core, log warning |
| AGGR-05 | Fix per-operation merge creating O(n*ops) intermediate DataFrames (P2) | Single-pass groupby.agg() with named aggregations eliminates merge chain |
| AGGR-06 | Fix Decimal handling inconsistency in grouped mode (P2) | Decimal columns detected and handled via apply() with Python Decimal arithmetic |
| AGGR-07 | Implement financial precision toggle for numeric aggregations (P2) | `use_financial_precision` converts numeric columns to Decimal before aggregation |
| AGGR-08 | Fix column collision in grouped mode (P2) | Output columns from operations dict -- no collision with proper naming |
| AGGR-09 | Standardize component to engine component blueprint pattern (P3) | `@REGISTRY.register()`, `_validate_config()` -> `ConfigurationError`, no print() |
| SORT-01 | Implement sort type distinction (numeric vs alphabetic vs date) from criteria (P1) | pandas `sort_values(key=...)` parameter enables per-column type coercion before sort |
| SORT-02 | Fix external sort that loads all data (P1) | Removed -- D-15 simplifies to pandas sort_values() for all sizes |
| SORT-03 | Fix streaming mode that collects all data (P1) | Removed -- D-17 eliminates streaming sort mode |
| SORT-04 | Remove engine-only config keys not in Talend (P2) | D-16 removes na_position, case_sensitive, chunk_size |
| SORT-05 | Standardize component to engine component blueprint pattern (P3) | Same as AGGR-09 |
| FROW-01 | Replace eval() with safe expression evaluation (P0) | D-05: operator-function map with vectorized pandas operations |
| FROW-02 | Implement all 14+ Talend operators (P1) | Full operator map verified: 14 operators mapped to pandas vectorized ops |
| FROW-03 | Implement FUNCTION pre-transforms (P1) | 8 functions mapped to pandas str accessor methods |
| FROW-04 | Fix string coercion in condition evaluation (P1) | Type-aware comparison: numeric columns compared as numbers, strings as strings |
| FROW-05 | Fix `.toList()` case error (P0 crash) | Eliminated -- rewrite uses vectorized masks, no `.tolist()` call |
| FROW-06 | Replace row-by-row eval() with vectorized pandas operations (P2) | D-05/D-06: all conditions are vectorized pandas Series operations |
| FROW-07 | Remove debug print statements (P2) | Fresh code -- no print() statements, only logger |
| TEST-08 | Engine unit tests for transform components | D-19/D-20: exhaustive per-requirement test coverage |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- **Tech stack**: Python 3.10+, pandas, no framework changes
- **Compatibility**: Identical output to Talend for same input/config
- **No breaking changes**: Converter JSON format must remain compatible
- **Naming**: snake_case modules, PascalCase classes, `_` prefix private
- **Errors**: Custom exception hierarchy (ConfigurationError, DataValidationError, etc.)
- **Logging**: `logging.getLogger(__name__)`, no print(), `[{self.id}]` prefix, ASCII only
- **Docstrings**: Google-style with Args/Returns/Raises
- **Config access**: Read in `_process()`, not `__init__()` (Rule 5)
- **Registration**: `@REGISTRY.register("Name", "tName")` decorator (Rule 9)

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pandas | 3.0.1 | DataFrame operations, groupby, sort, filter | Already in use, runtime-verified [VERIFIED: python runtime] |
| python decimal | stdlib | Decimal precision for financial aggregations | Required for Talend BigDecimal parity [VERIFIED: stdlib] |
| re | stdlib | Regex for MATCHES operator | Standard for pattern matching [VERIFIED: stdlib] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| numpy | (bundled with pandas) | NaN handling, numeric operations | Implicit via pandas [VERIFIED: python runtime] |
| pytest | 9.0.2 | Test framework | All unit tests [VERIFIED: python runtime] |

No new dependencies required. All functionality is covered by pandas + stdlib.

## Architecture Patterns

### Component File Structure

Each rewritten component follows ENGINE_COMPONENT_PATTERN.md exactly:

```
src/v1/engine/components/
  aggregate/
    __init__.py              # import AggregateRow (update existing)
    aggregate_row.py         # REWRITE (543 lines -> ~250 lines)
  transform/
    __init__.py              # already imports FilterRows, SortRow
    filter_rows.py           # REWRITE (316 lines -> ~200 lines)
    sort_row.py              # REWRITE (397 lines -> ~100 lines)
```

### Pattern 1: Config Key Alignment (D-04)
**What:** Engine reads converter config keys directly -- no mapping layer.
**When to use:** All three components.

Converter output keys (verified from real JSON samples):

**AggregateRow config:**
```python
# Source: tests/talend_xml_samples/converted_jsons/Job_tAggregateRow_0.1.json
config = {
    "groupbys": [{"output_column": "department", "input_column": "department"}],
    "operations": [
        {"output_column": "total_qty", "function": "sum", "input_column": "quantity", "ignore_null": True},
        {"output_column": "avg_sale", "function": "avg", "input_column": "sale_amount", "ignore_null": True},
    ],
    "list_delimiter": ",",
    "use_financial_precision": True,
    "check_type_overflow": False,
    "check_ulp": False,
}
```

**FilterRows config:**
```python
# Source: tests/talend_xml_samples/converted_jsons/Job_tFilterRow_0.1.json
config = {
    "logical_op": "&&",         # NOT "logical_operator" -- D-04
    "use_advanced": False,
    "advanced_cond": "",        # NOT "advanced_condition" -- D-04
    "conditions": [
        {"column": "age", "function": "", "operator": ">=", "value": "25"},
    ],
}
```

**SortRow config:**
```python
# Source: tests/talend_xml_samples/converted_jsons/Job_tSortRow_0.1.json
config = {
    "criteria": [               # NOT "sort_columns" -- D-04
        {"column": "department", "sort_type": "alpha", "order": "asc"},
        {"column": "salary", "sort_type": "num", "order": "desc"},
    ],
    "external": False,          # Future hook, not implemented
}
```

### Pattern 2: Operator-Function Map for FilterRows (D-05)
**What:** Static dict mapping Talend operator strings to pandas vectorized operations. No eval(), no AST.
**When to use:** FilterRows simple conditions mode.

```python
# Verified operator list from audit report ENG-FR-002
# Source: docs/v1/audit/components/transform/tFilterRow.md line 202
_OPERATOR_MAP = {
    "==":           lambda col, val: col == val,
    "!=":           lambda col, val: col != val,
    ">":            lambda col, val: col > val,
    "<":            lambda col, val: col < val,
    ">=":           lambda col, val: col >= val,
    "<=":           lambda col, val: col <= val,
    "MATCHES":      lambda col, val: col.str.fullmatch(val, na=False),
    "CONTAINS":     lambda col, val: col.str.contains(val, regex=False, na=False),
    "NOT_CONTAINS": lambda col, val: ~col.str.contains(val, regex=False, na=False),
    "STARTS_WITH":  lambda col, val: col.str.startswith(val, na=False),
    "ENDS_WITH":    lambda col, val: col.str.endswith(val, na=False),
    "IS_NULL":      lambda col, val: col.isna(),
    "IS_NOT_NULL":  lambda col, val: col.notna(),
    "LENGTH_LT":    lambda col, val: col.str.len() < int(val),
    "LENGTH_GT":    lambda col, val: col.str.len() > int(val),
}
```
[VERIFIED: pandas str accessor methods tested in runtime -- fullmatch, contains, startswith, endswith, len all confirmed working]

### Pattern 3: FUNCTION Pre-Transforms for FilterRows (D-07)
**What:** Apply FUNCTION to column values before operator comparison.
**When to use:** When condition dict has non-empty `function` field.

```python
# 8 Talend FUNCTION pre-transforms
# Source: docs/v1/audit/components/transform/tFilterRow.md line 122
_FUNCTION_MAP = {
    "":       lambda col: col,                    # no-op (most common)
    "LOWER":  lambda col: col.astype(str).str.lower(),
    "UPPER":  lambda col: col.astype(str).str.upper(),
    "LENGTH": lambda col: col.astype(str).str.len(),
    "TRIM":   lambda col: col.astype(str).str.strip(),
    "LTRIM":  lambda col: col.astype(str).str.lstrip(),
    "RTRIM":  lambda col: col.astype(str).str.rstrip(),
    "LEFT":   None,  # LEFT(n) requires parsing arg from function string
    "RIGHT":  None,  # RIGHT(n) requires parsing arg from function string
}
```

Note: LEFT and RIGHT take an argument (e.g., `"LEFT(3)"`). The engine must parse the integer argument from the function string. [ASSUMED -- Talend UI uses LEFT/RIGHT with a parameter but the exact format in the `function` field needs verification against real XML samples]

### Pattern 4: Aggregation Single-Pass (D-13, AGGR-05)
**What:** Replace per-operation merge chain with single-pass groupby.
**When to use:** AggregateRow grouped mode.

```python
# Instead of N separate groupby().agg().merge() calls:
agg_dict = {}
for op in operations:
    input_col = op["input_column"]
    output_col = op["output_column"]
    func = op["function"]
    ignore_null = op.get("ignore_null", True)

    if func == "count":
        agg_dict[output_col] = pd.NamedAgg(column=input_col, aggfunc="count")
    elif func == "sum":
        agg_dict[output_col] = pd.NamedAgg(column=input_col, aggfunc="sum")
    # ... etc

result = df.groupby(group_cols).agg(**agg_dict).reset_index()
```
[VERIFIED: pandas 3.0.1 NamedAgg confirmed working with groupby]

### Pattern 5: Sort Type Coercion via key= (D-14, SORT-01)
**What:** Use pandas `sort_values(key=...)` to apply per-column type coercion.
**When to use:** SortRow with mixed sort types.

```python
# Verified in pandas 3.0.1 runtime
def _make_sort_key(sort_type: str):
    if sort_type == "num":
        return pd.to_numeric  # coerce to numeric before comparison
    elif sort_type == "date":
        return pd.to_datetime  # coerce to datetime before comparison
    else:  # "alpha" -- default string sort
        return None  # no key function = default str sort
```
[VERIFIED: pandas sort_values key= parameter tested with pd.to_numeric and pd.to_datetime]

### Anti-Patterns to Avoid
- **DO NOT use eval():** The old FilterRows used `eval()` for advanced conditions -- security risk. Use Java bridge for `{{java}}` expressions, operator map for simple conditions.
- **DO NOT store state on self:** All processing state must be local to `_process()` (Rule 10).
- **DO NOT read config in __init__:** Config is resolved between `_validate_config()` and `_process()` (Rule 5).
- **DO NOT override execute():** Template method lifecycle handles stats, config immutability, expression resolution (Rule 4).
- **DO NOT use print():** Use `logger` with `[{self.id}]` prefix (Rule 8).
- **DO NOT merge per-operation:** Single-pass groupby.agg() instead of N merges (AGGR-05).
- **DO NOT use string coercion for all comparisons:** The old FilterRows cast everything to string -- breaks numeric ordering ("9" > "10"). Use type-aware comparison.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Standard deviation with ddof | Custom math | `series.std(ddof=0)` or `series.std(ddof=1)` | pandas handles NaN, empty series, edge cases [VERIFIED: pandas runtime, but note Decimal columns need custom handling -- pandas .std() fails on Decimal] |
| Regex matching | Custom pattern engine | `pandas.Series.str.fullmatch()` | Handles NaN, vectorized, matches Java String.matches() semantics [VERIFIED: pandas runtime] |
| Sort type coercion | Pre-sort type conversion loop | `sort_values(key=pd.to_numeric)` | Single vectorized operation [VERIFIED: pandas runtime] |
| Delimited string concat | Python loop with join | `groupby().agg(lambda x: delimiter.join(x.astype(str)))` | Handles NaN, vectorized per group [VERIFIED: pandas runtime] |
| Null propagation in aggregation | Custom null tracking | `skipna=False` parameter on pandas agg functions | Matches Talend "null + any = null" behavior [VERIFIED: pandas runtime -- sum/mean with skipna=False returns NaN] |

**Key insight:** pandas 3.0.1 provides all the vectorized operations needed for every Talend operator and aggregation function. The only exception is Decimal column handling, where pure Python Decimal arithmetic is needed because pandas `.std()` / `.mean()` fail on Decimal dtype columns.

## Common Pitfalls

### Pitfall 1: Decimal Columns Break pandas Aggregation Functions
**What goes wrong:** `pandas.Series.std()`, `.mean()`, `.var()` raise TypeError on Series containing `decimal.Decimal` objects.
**Why it happens:** pandas delegates to numpy which cannot handle Python Decimal objects.
**How to avoid:** When `use_financial_precision` is True or column contains Decimal values, use pure Python aggregation via `apply()` with Decimal arithmetic. For std dev: compute manually (`sum((x - mean)^2) / n` for population, `/ (n-1)` for sample).
**Warning signs:** `TypeError: unsupported operand type(s) for -: 'float' and 'decimal.Decimal'`
[VERIFIED: reproduced in pandas 3.0.1 runtime -- `pd.Series([Decimal('1.5'), Decimal('2.5')]).std()` raises TypeError]

### Pitfall 2: Converter Maps population_std_dev to std (Lossy)
**What goes wrong:** The converter's `_FUNCTION_MAP` maps `population_std_dev` -> `std`. The engine receives `"std"` for both sample and population variants. Decision D-10 requires `ddof=0` for population std dev, but the engine has no way to distinguish them.
**Why it happens:** Converter was written before the engine could handle population_std_dev as a distinct function.
**How to avoid:** Fix the converter to pass through `"population_std_dev"` instead of mapping to `"std"`. The engine then handles both: `"std"` -> `ddof=1`, `"population_std_dev"` -> `ddof=0`. This is a small converter change that must be included in the AggregateRow plan.
**Warning signs:** All population_std_dev results will be wrong (ddof=1 instead of ddof=0) if this isn't fixed.

### Pitfall 3: String vs Numeric Comparison in FilterRows
**What goes wrong:** The old engine cast ALL columns to string before comparison. This makes `"9" > "10"` evaluate True (string comparison), breaking numeric ordering.
**Why it happens:** Simplistic `.astype(str)` approach that treats everything as text.
**How to avoid:** Type-aware comparison: for numeric operators (`>`, `<`, `>=`, `<=`), attempt `pd.to_numeric()` coercion on both column and value. Fall back to string only for string-specific operators (CONTAINS, STARTS_WITH, etc.).
**Warning signs:** Conditions like `salary > 1000` matching wrong rows.

### Pitfall 4: MATCHES Uses Full Match (Not Partial)
**What goes wrong:** Using `str.contains()` or `str.match()` instead of `str.fullmatch()` for the MATCHES operator.
**Why it happens:** Python's `re.match()` only anchors at start. Talend's MATCHES (Java `String.matches()`) requires full string match.
**How to avoid:** Use `pandas.Series.str.fullmatch()` which is equivalent to Java's `String.matches()`.
**Warning signs:** MATCHES filter accepting partial matches.
[VERIFIED: `str.fullmatch(r'[a-z]+\d+')` correctly rejects partial matches in pandas 3.0.1]

### Pitfall 5: groupby ignores ignore_null by Default
**What goes wrong:** pandas `groupby().sum()` uses `skipna=True` by default, which silently drops NaN from aggregation. When Talend's `ignore_null=False`, null + any value should produce null.
**Why it happens:** pandas default skipna=True is opposite of Talend's ignore_null=False behavior.
**How to avoid:** When `ignore_null=False`, use lambda aggregation with `skipna=False`: `groupby().agg(lambda x: x.sum(skipna=False))` returns NaN if any value is NaN.
**Warning signs:** Aggregation results showing numeric values instead of null when input has null values and ignore_null=False.
[VERIFIED: `pd.Series([1.0, None]).sum(skipna=False)` returns `nan` in pandas 3.0.1]

### Pitfall 6: logical_op Value is "&&" Not "AND"
**What goes wrong:** Engine checks for `"AND"` / `"OR"` but converter outputs `"&&"` / `"||"` (Java-style).
**Why it happens:** Converter preserves the Talend CLOSED_LIST value which uses Java-style operators.
**How to avoid:** Normalize at start of _process(): `{"&&": "AND", "||": "OR", "AND": "AND", "OR": "OR"}`.
**Warning signs:** Conditions always using AND regardless of config.
[VERIFIED: from real JSON sample -- `"logical_op": "&&"` in Job_tFilterRow_0.1.json]

### Pitfall 7: AggregateRow Output Schema Differs from Input Schema
**What goes wrong:** tAggregateRow's output schema has DIFFERENT columns than its input schema. The output contains groupby columns + operation output columns, NOT all input columns. The old code tried to add all input columns back, creating the _ensure_output_columns bug.
**Why it happens:** Misunderstanding of Talend behavior -- aggregation produces a NEW schema defined by groupbys + operations.
**How to avoid:** Output columns are ONLY: (a) `output_column` from each groupby entry, and (b) `output_column` from each operation entry. Do NOT carry forward input columns not in these lists.
**Warning signs:** Extra null columns in output, or columns from input appearing in aggregated output.
[VERIFIED: from real JSON -- input schema has 5 columns (department, product, sale_amount, quantity, sale_date) but output schema has 7 different columns (department, total_sales, num_transactions, avg_sale, min_sale, max_sale, total_quantity)]

## Code Examples

### AggregateRow Core Structure
```python
# Source: ENGINE_COMPONENT_PATTERN.md + Phase 4 FileInputDelimited reference
"""Engine component for AggregateRow (tAggregateRow).

Groups input rows and applies aggregation functions.

Config keys consumed (8 total):
  groupbys                (list[dict], default [])   -- group-by column mappings
  operations              (list[dict], default [])   -- aggregation operations
  list_delimiter          (str, default ",")          -- delimiter for list function
  use_financial_precision (bool, default True)        -- use Decimal arithmetic
  check_type_overflow     (bool, default False)       -- deferred
  check_ulp               (bool, default False)       -- deferred
  tstatcatcher_stats      (bool, default False)       -- framework
  label                   (str, default "")           -- framework
"""
import logging
from decimal import Decimal
from typing import Any, Optional

import pandas as pd

from ...base_component import BaseComponent
from ...component_registry import REGISTRY
from ...exceptions import ConfigurationError

logger = logging.getLogger(__name__)


@REGISTRY.register("AggregateRow", "tAggregateRow")
class AggregateRow(BaseComponent):
    """tAggregateRow engine implementation."""

    def _validate_config(self) -> None:
        ops = self.config.get("operations", [])
        if not isinstance(ops, list):
            raise ConfigurationError(
                f"[{self.id}] 'operations' must be a list"
            )

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> dict:
        if input_data is None or input_data.empty:
            return {"main": pd.DataFrame(), "reject": None}

        groupbys = self.config.get("groupbys", [])
        operations = self.config.get("operations", [])
        # ... aggregation logic ...
        return {"main": result_df, "reject": None}
```

### FilterRows Operator Map Pattern
```python
# Type-aware comparison helper
def _compare(col: pd.Series, operator: str, value: str, col_dtype) -> pd.Series:
    """Apply operator to column, with type-aware coercion."""
    if operator in ("IS_NULL", "IS_NOT_NULL"):
        return _OPERATOR_MAP[operator](col, value)

    # For numeric comparison operators, coerce both sides to numeric
    if operator in ("==", "!=", ">", "<", ">=", "<="):
        numeric_col = pd.to_numeric(col, errors="coerce")
        numeric_val = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
        if pd.notna(numeric_val) and numeric_col.notna().any():
            return _OPERATOR_MAP[operator](numeric_col, numeric_val)
        # Fall back to string comparison if not numeric
        return _OPERATOR_MAP[operator](col.astype(str), str(value))

    # String operators always use string values
    return _OPERATOR_MAP[operator](col.astype(str), str(value))
```

### SortRow Minimal Implementation
```python
@REGISTRY.register("SortRow", "tSortRow")
class SortRow(BaseComponent):
    """tSortRow engine implementation."""

    def _validate_config(self) -> None:
        criteria = self.config.get("criteria", [])
        if not criteria:
            raise ConfigurationError(
                f"[{self.id}] 'criteria' must be a non-empty list"
            )

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> dict:
        if input_data is None or input_data.empty:
            return {"main": pd.DataFrame(), "reject": None}

        criteria = self.config.get("criteria", [])
        columns = [c["column"] for c in criteria if c["column"] in input_data.columns]
        ascending = [c.get("order", "asc") == "asc" for c in criteria if c["column"] in input_data.columns]

        # Build key functions for type-based sorting
        sort_types = {c["column"]: c.get("sort_type", "alpha") for c in criteria}

        result = input_data.sort_values(
            by=columns,
            ascending=ascending,
            key=lambda col: self._apply_sort_type(col, sort_types.get(col.name, "alpha")),
            ignore_index=True,
            kind="stable",
            na_position="last",
        )
        return {"main": result, "reject": None}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `eval()` for filter conditions | Operator-function map with vectorized pandas | This phase (D-05) | Eliminates code injection risk, 100x+ faster |
| Per-operation groupby+merge chain | Single-pass `groupby().agg(**named_aggs)` | This phase (AGGR-05) | O(n*ops) -> O(n) for grouped aggregation |
| String coercion for all comparisons | Type-aware comparison (numeric/string/null) | This phase (FROW-04) | Correct numeric ordering |
| Streaming sort mode | Batch-only sort via `sort_values()` | This phase (D-17) | Simpler, correct (sort needs all data) |
| Engine-invented config keys | Read converter keys directly | Phase 4 (D-04), continued | No mapping layer needed |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | LEFT/RIGHT FUNCTION pre-transforms take a numeric argument as part of the function string (e.g., `"LEFT(3)"`) | Architecture Patterns - Pattern 3 | Implementation will need to parse the integer argument differently; LOW risk -- can be verified from Talend XML samples |
| A2 | Talend NOT_CONTAINS operator exists as a distinct CLOSED_LIST value | Architecture Patterns - Pattern 2 | If NOT_CONTAINS is not a Talend operator, remove from map; LOW risk -- does not affect architecture |
| A3 | ABS_VALUE is a FUNCTION pre-transform but is excluded from the 8 in D-07 scope | Phase Requirements | If ABS_VALUE is needed, add to FUNCTION_MAP; LOW risk -- simple addition |

## Open Questions

1. **population_std_dev Converter Fix Scope**
   - What we know: Converter maps `population_std_dev` -> `std` (lossy). D-10 requires `ddof=0` for population variant.
   - What's unclear: Should the converter be fixed in this phase (small 1-line change) or tracked separately?
   - Recommendation: Fix converter in the AggregateRow plan. It is a 1-line change in `_FUNCTION_MAP` (change `"population_std_dev": "std"` to `"population_std_dev": "population_std_dev"`) and removing the lossy-mapping warning. This keeps D-10 self-contained.

2. **ABS_VALUE Function Pre-Transform**
   - What we know: Audit mentions ABS_VALUE as a FUNCTION pre-transform. D-07 lists 8 functions (LOWER, UPPER, LENGTH, TRIM, LTRIM, RTRIM, LEFT, RIGHT). ABS_VALUE is not in D-07.
   - What's unclear: Is ABS_VALUE commonly used in production jobs?
   - Recommendation: Include ABS_VALUE in implementation (simple `pd.to_numeric(col).abs()`) since it's trivial and avoids a future gap.

3. **MATCH_REGEX_CS (Case-Sensitive Regex)**
   - What we know: Audit ENG-FR-002 mentions MATCH_REGEX and MATCH_REGEX_CS as separate operators.
   - What's unclear: Whether these are distinct from MATCHES or aliases.
   - Recommendation: Implement `MATCH_REGEX_CS` as fullmatch with case-sensitive flag (default). The basic MATCHES can be case-insensitive via `re.IGNORECASE` flag. Both are simple pandas `str.fullmatch()` calls with different flags.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 |
| Config file | None (uses pytest defaults) |
| Quick run command | `python -m pytest tests/v1/engine/components/aggregate/test_aggregate_row.py tests/v1/engine/components/transform/test_sort_row.py tests/v1/engine/components/transform/test_filter_rows.py -x -q` |
| Full suite command | `python -m pytest tests/v1/engine/ -x -q` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| AGGR-01 | Output columns correct (no nulling of computed columns) | unit | `python -m pytest tests/v1/engine/components/aggregate/test_aggregate_row.py -x -k "output_columns"` | Wave 0 |
| AGGR-02 | output_column used as result column name | unit | `python -m pytest tests/v1/engine/components/aggregate/test_aggregate_row.py -x -k "output_column_rename"` | Wave 0 |
| AGGR-03 | ignore_null=False propagates NaN | unit | `python -m pytest tests/v1/engine/components/aggregate/test_aggregate_row.py -x -k "ignore_null"` | Wave 0 |
| AGGR-04 | list, population_std_dev functions | unit | `python -m pytest tests/v1/engine/components/aggregate/test_aggregate_row.py -x -k "list or population"` | Wave 0 |
| AGGR-05 | Single-pass aggregation (no merge chain) | unit | `python -m pytest tests/v1/engine/components/aggregate/test_aggregate_row.py -x -k "multiple_operations"` | Wave 0 |
| AGGR-06 | Decimal handling in grouped mode | unit | `python -m pytest tests/v1/engine/components/aggregate/test_aggregate_row.py -x -k "decimal"` | Wave 0 |
| AGGR-07 | Financial precision toggle | unit | `python -m pytest tests/v1/engine/components/aggregate/test_aggregate_row.py -x -k "financial_precision"` | Wave 0 |
| AGGR-08 | No column collision | unit | `python -m pytest tests/v1/engine/components/aggregate/test_aggregate_row.py -x -k "column_collision"` | Wave 0 |
| AGGR-09 | Blueprint pattern (registry, validate, no print) | unit | `python -m pytest tests/v1/engine/components/aggregate/test_aggregate_row.py -x -k "registry or validate"` | Wave 0 |
| SORT-01 | Sort type distinction (num/alpha/date) | unit | `python -m pytest tests/v1/engine/components/transform/test_sort_row.py -x -k "sort_type"` | Wave 0 |
| SORT-02 | External sort removed (simplified) | unit | `python -m pytest tests/v1/engine/components/transform/test_sort_row.py -x -k "basic"` | Wave 0 |
| SORT-03 | Streaming removed (batch only) | unit | `python -m pytest tests/v1/engine/components/transform/test_sort_row.py -x -k "basic"` | Wave 0 |
| SORT-04 | No engine-only config keys | unit | `python -m pytest tests/v1/engine/components/transform/test_sort_row.py -x -k "config"` | Wave 0 |
| SORT-05 | Blueprint pattern | unit | `python -m pytest tests/v1/engine/components/transform/test_sort_row.py -x -k "registry or validate"` | Wave 0 |
| FROW-01 | No eval() -- operator-function map | unit | `python -m pytest tests/v1/engine/components/transform/test_filter_rows.py -x -k "operator"` | Wave 0 |
| FROW-02 | All 14+ operators | unit | `python -m pytest tests/v1/engine/components/transform/test_filter_rows.py -x -k "operator"` | Wave 0 |
| FROW-03 | FUNCTION pre-transforms | unit | `python -m pytest tests/v1/engine/components/transform/test_filter_rows.py -x -k "function"` | Wave 0 |
| FROW-04 | Type-aware comparison | unit | `python -m pytest tests/v1/engine/components/transform/test_filter_rows.py -x -k "type_aware or numeric"` | Wave 0 |
| FROW-05 | No .toList() crash | unit | `python -m pytest tests/v1/engine/components/transform/test_filter_rows.py -x -k "basic"` | Wave 0 |
| FROW-06 | Vectorized operations | unit | `python -m pytest tests/v1/engine/components/transform/test_filter_rows.py -x -k "basic"` | Wave 0 |
| FROW-07 | No print() statements | unit | `python -m pytest tests/v1/engine/components/transform/test_filter_rows.py -x -k "basic"` | Wave 0 |
| TEST-08 | Engine unit tests for transforms | unit | All of the above | Wave 0 |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/v1/engine/components/aggregate/ tests/v1/engine/components/transform/test_sort_row.py tests/v1/engine/components/transform/test_filter_rows.py -x -q`
- **Per wave merge:** `python -m pytest tests/v1/engine/ -x -q`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/v1/engine/components/aggregate/__init__.py` -- package init
- [ ] `tests/v1/engine/components/aggregate/test_aggregate_row.py` -- all AGGR-* test cases
- [ ] `tests/v1/engine/components/transform/test_sort_row.py` -- all SORT-* test cases
- [ ] `tests/v1/engine/components/transform/test_filter_rows.py` -- all FROW-* test cases

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | N/A |
| V3 Session Management | no | N/A |
| V4 Access Control | no | N/A |
| V5 Input Validation | yes | Operator-function map (no eval), ConfigurationError for invalid config |
| V6 Cryptography | no | N/A |

### Known Threat Patterns for Transform Components

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Code injection via eval() in FilterRows | Tampering | Replace eval() with operator-function map (D-05) -- CRITICAL fix |
| Arbitrary regex in MATCHES operator | Denial of Service | Use `re.fullmatch()` with no timeout -- regex DoS is LOW risk for batch ETL (not user-facing). Log warning for complex patterns. |
| Malformed config causing unexpected behavior | Tampering | `_validate_config()` raises ConfigurationError for invalid keys/values |

## Sources

### Primary (HIGH confidence)
- `src/converters/talend_to_v1/components/aggregate/aggregate_row.py` -- converter output config shape (8 params, groupbys/operations structure)
- `src/converters/talend_to_v1/components/transform/filter_rows.py` -- converter output config shape (4 params, conditions structure)
- `src/converters/talend_to_v1/components/transform/sort_row.py` -- converter output config shape (5 params, criteria structure)
- `tests/talend_xml_samples/converted_jsons/Job_tAggregateRow_0.1.json` -- real converted JSON (verified config keys: groupbys, operations, list_delimiter, use_financial_precision)
- `tests/talend_xml_samples/converted_jsons/Job_tFilterRow_0.1.json` -- real converted JSON (verified config keys: logical_op, conditions, use_advanced, advanced_cond)
- `tests/talend_xml_samples/converted_jsons/Job_tSortRow_0.1.json` -- real converted JSON (verified config keys: criteria, external)
- `docs/v1/standards/ENGINE_COMPONENT_PATTERN.md` -- component blueprint (Rules 1-12)
- `src/v1/engine/base_component.py` -- BaseComponent lifecycle (execute -> validate -> resolve -> process)
- `src/v1/engine/component_registry.py` -- REGISTRY decorator-based registration
- `docs/v1/audit/components/transform/tFilterRow.md` -- operator list, function list, behavioral notes
- `docs/v1/audit/components/aggregate/tAggregateRow.md` -- 12 aggregation functions, table structures, engine gaps

### Secondary (MEDIUM confidence)
- pandas 3.0.1 runtime verification -- Decimal.std() failure, skipna=False behavior, sort_values key=, str.fullmatch()
- [Talend tFilterRow Properties](https://help.qlik.com/talend/en-US/components/8.0/processing/tfilterrow-standard-properties) -- official docs confirming FUNCTION/OPERATOR/CONDITIONS structure

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- pandas 3.0.1 verified, all operations runtime-tested
- Architecture: HIGH -- ENGINE_COMPONENT_PATTERN.md blueprint + Phase 4 reference implementation (FileInputDelimited) confirmed
- Pitfalls: HIGH -- all pitfalls verified via runtime testing (Decimal failure, skipna behavior, fullmatch semantics)
- Config shapes: HIGH -- verified from real converted JSON samples and converter source code

**Research date:** 2026-04-15
**Valid until:** 2026-05-15 (stable domain -- pandas API, Talend component specs don't change frequently)
