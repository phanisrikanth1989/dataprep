# Phase 6: Transform Group A -- Aggregation, Sort, Filter - Context

**Gathered:** 2026-04-15
**Status:** Ready for planning

<domain>
## Phase Boundary

Rewrite tAggregateRow, tSortRow, and tFilterRow from scratch with full Talend feature parity, conforming to ENGINE_COMPONENT_PATTERN.md blueprint. All three components are rewritten to read converter config keys directly (no mapping layer). All P0-P3 requirements (AGGR-01 through AGGR-09, SORT-01 through SORT-05, FROW-01 through FROW-07) are addressed in the rewrites. Engine unit tests with exhaustive coverage per requirement.

**Focus:** Talend feature parity first. These are the 3 most complex transform components with the most bugs.

**Dependencies:** Phase 1 (BaseComponent lifecycle, GlobalMap, ContextManager), Phase 3 (execution loop, decorator-based ComponentRegistry, OutputRouter for REJECT flow).

</domain>

<decisions>
## Implementation Decisions

### Approach & Scope
- **D-01:** Full rewrite from scratch for all three components. Not patching existing code. Conform to ENGINE_COMPONENT_PATTERN.md blueprint with `@REGISTRY.register()` decorators.
- **D-02:** All P0-P3 items addressed -- rewrites naturally handle P2/P3 items (debug prints, optimization) since we're writing fresh code.
- **D-03:** Plan structure: 1 plan per component (AggregateRow, SortRow, FilterRow) + 1 combined test plan.
- **D-04:** Config key alignment same as Phase 4 (D-04) -- engine reads converter keys directly. `groupbys` not `group_by`, `criteria` not `sort_columns`, `logical_op` not `logical_operator`, `advanced_cond` not `advanced_condition`.

### tFilterRow Expression Engine
- **D-05:** Replace eval() with operator-function map. Conditions are already structured dicts from converter (`column`, `function`, `operator`, `value`), so map each Talend operator to a pandas vectorized operation. No AST parsing needed.
- **D-06:** Implement all 14+ Talend operators: `==`, `!=`, `>`, `<`, `>=`, `<=`, `MATCHES` (regex), `CONTAINS`, `STARTS_WITH`, `ENDS_WITH`, `IS_NULL`, `IS_NOT_NULL`, `LENGTH_LT`, `LENGTH_GT`.
- **D-07:** Implement all 8 FUNCTION pre-transforms: LOWER, UPPER, LENGTH, TRIM, LTRIM, RTRIM, LEFT, RIGHT. Applied to column values before operator comparison.
- **D-08:** Advanced conditions ({{java}} marked) delegate to Java bridge, consistent with tMap approach.

### tAggregateRow Completeness
- **D-09:** list_object maps to delimited string -- Talend list_object produces `"a,b,c"` string. Engine implements as concat with delimiter (Talend behavior).
- **D-10:** population_std_dev gets dedicated implementation with `series.std(ddof=0)`, not lossy mapping to sample std (ddof=1).
- **D-11:** ignore_null when false: use `skipna=False` in pandas aggregation. Null + any = null (Talend behavior).
- **D-12:** use_financial_precision: when true, convert numeric columns to Decimal before aggregation, preserve Decimal precision through output.
- **D-13:** Converter outputs `groupbys` (list of dicts with `output_column`, `input_column`) and `operations` (list of dicts with `output_column`, `function`, `input_column`, `ignore_null`). Engine reads these directly.

### tSortRow Implementation
- **D-14:** Implement all 3 sort types from `criteria` list: `num` (cast to numeric before sort), `alpha` (string sort, case-sensitive), `date` (parse to datetime before sort).
- **D-15:** Simplify to pandas sort_values() for all sizes. Keep `external` flag as future hook but don't implement parquet chunking. Pandas handles memory efficiently.
- **D-16:** Remove engine-only config keys (na_position, case_sensitive, chunk_size) that are not Talend params. Sort behavior determined by `criteria` entries only.
- **D-17:** Remove streaming sort mode. Sort inherently requires all data. Accept DataFrame in, return DataFrame out.
- **D-18:** Converter outputs `criteria` (list of dicts with `column`, `sort_type`, `order`). Engine reads this directly.

### Test Strategy
- **D-19:** Test location: `tests/v1/engine/components/aggregate/test_aggregate_row.py`, `tests/v1/engine/components/transform/test_sort_row.py`, `tests/v1/engine/components/transform/test_filter_rows.py`.
- **D-20:** Exhaustive coverage per requirement. Every AGGR/SORT/FROW requirement gets dedicated test cases.
- **D-21:** Tests use programmatic DataFrame creation (no fixture files needed for transform components).

### Claude's Discretion
- Internal method decomposition within each component
- Exact operator implementation details (regex engine, string comparison mechanics)
- How to handle edge cases not specified by Talend (empty DataFrames, missing columns)
- Decimal conversion strategy details for financial precision mode

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `BaseComponent` lifecycle from Phase 1 (base_component.py) -- template method pattern with execute() -> _process()
- `@REGISTRY.register()` decorator from Phase 3 for auto-registration
- `OutputRouter` from Phase 3 for REJECT flow routing
- `GlobalMap`, `ContextManager` for state management
- Phase 4 File I/O components as reference for rewrite patterns

### Established Patterns
- Engine components read converter config keys directly (Phase 4 D-04)
- `_process()` returns `{'main': DataFrame, 'reject': DataFrame}` with optional `'stats'`
- `_update_stats(rows_in, rows_out, rows_rejected)` for globalMap NB_LINE vars
- Config validation via `_validate_config()` returning list of error strings

### Integration Points
- Converter outputs: `AggregateRow` type with `groupbys`/`operations` config, `FilterRows` type with `conditions`/`logical_op`/`use_advanced`/`advanced_cond` config, `SortRow` type with `criteria`/`external` config
- COMPONENT_REGISTRY in engine.py maps type names to classes
- REJECT flow: FilterRows outputs reject DataFrame, routed by OutputRouter

### Current Component Sizes (to be rewritten)
- aggregate_row.py: 543 lines (heavy debug logging, config key mismatches, _ensure_output_columns bug)
- filter_rows.py: 315 lines (eval() security risk, print() debug, 6 operators only, .toList() crash)
- sort_row.py: 396 lines (no sort type distinction, broken external sort, streaming mode collects all data)

</code_context>

<specifics>
## Specific Ideas

No specific requirements beyond Talend feature parity. All implementation choices follow established Phase 4 patterns.

</specifics>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope.

</deferred>
