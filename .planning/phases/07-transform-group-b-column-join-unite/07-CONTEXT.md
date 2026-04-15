# Phase 7: Transform Group B -- Column, Join, Unite - Context

**Gathered:** 2026-04-15
**Status:** Ready for planning

<domain>
## Phase Boundary

Rewrite tJoin from scratch with full Talend feature parity (8 bugs including P0 case-insensitive join corruption). Light rewrite of tFilterColumns (schema-based filtering, ~50 lines) and tUnite (UNION-only, ~50 lines) to remove non-Talend features. All three components conform to ENGINE_COMPONENT_PATTERN.md blueprint and read converter config keys directly. Engine unit tests for all three.

**Focus:** tJoin is the heavy lift (P0 corruption + config key mismatches). FilterColumns and Unite are light cleanup + test coverage.

**Dependencies:** Phase 1 (BaseComponent lifecycle), Phase 3 (execution loop, decorator-based ComponentRegistry, OutputRouter).

</domain>

<decisions>
## Implementation Decisions

### tJoin Approach
- **D-01:** Full rewrite from scratch. 8 bugs including P0 data corruption + config key mismatches = systemic issues. Phase 6 rewrite pattern.
- **D-02:** Read converter keys directly: `use_inner_join` (bool), `join_key` (list of `{input_column, lookup_column}` dicts), `use_lookup_cols` (bool), `lookup_cols` (list of `{output_column, lookup_column}` dicts).
- **D-03:** Null join semantics: pre-filter null keys before merge. Replace NaN with sentinel, merge, filter sentinel matches. Talend/SQL behavior: null != null.
- **D-04:** Case-insensitive join: create lowercase temp columns for matching, keep originals intact. Drop temp columns after merge. No data corruption.
- **D-05:** Implement INCLUDE_LOOKUP toggle (JOIN-04): when `use_lookup_cols=false`, exclude lookup-only columns from output. When true, include specified `lookup_cols`.
- **D-06:** Implement ERROR_MESSAGE globalMap variable (JOIN-05): `{id}_ERROR_MESSAGE` set on join errors.
- **D-07:** Fix reject output: reject = main rows with no lookup match. Compute correctly without double merge.
- **D-08:** Populate reject schema from `schema.reject` config, add errorCode/errorMessage columns.

### tFilterColumns Simplification
- **D-09:** Rewrite to schema-based filtering. Talend uses output schema as the column filter. Read `schema.output` column names and select those from input DataFrame. Remove `mode`, `columns`, `keep_row_order` config keys that aren't Talend params.
- **D-10:** ~50 lines replacing 205 lines. Trivial component: select columns from output schema, return filtered DataFrame.

### tUnite Simplification
- **D-11:** Simplify to UNION only. Talend tUnite only does concat. Remove MERGE mode, streaming mode, sort_output, remove_duplicates — none are Talend features.
- **D-12:** Use _process() only, remove custom execute() override. Engine passes dict of DataFrames. Follow BaseComponent pattern.
- **D-13:** ~50 lines replacing 393 lines. Collect all input DataFrames, pd.concat with ignore_index=True.

### Registration & Plan Structure
- **D-14:** @REGISTRY.register decorator for all three: Join/tJoin, FilterColumns/tFilterColumns, Unite/tUnite.
- **D-15:** 2 plans: Plan 01 = tJoin rewrite (heavy), Plan 02 = FilterColumns + Unite rewrites + all tests.

### Test Strategy
- **D-16:** Test location: `tests/v1/engine/components/transform/test_join.py`, `test_filter_columns.py`, `test_unite.py`.
- **D-17:** Phase 6 test patterns: programmatic DataFrame creation, _DEFAULT_CONFIG, _make_component helpers, @pytest.mark.unit.
- **D-18:** Exhaustive coverage per requirement. Every JOIN/FCOL/UNIT requirement gets dedicated test cases.

### Claude's Discretion
- Internal method decomposition within tJoin
- Exact sentinel value strategy for null key handling
- How to handle the input mapping (main/lookup identification from dict of DataFrames)
- Edge case behavior for empty lookup DataFrames

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- Phase 6 rewrite pattern (AggregateRow, SortRow, FilterRows) as reference
- BaseComponent lifecycle, @REGISTRY.register decorator, OutputRouter
- Phase 4 File I/O components as additional reference

### Established Patterns
- Engine reads converter config keys directly (Phase 4 D-04, Phase 6 D-04)
- `_process()` returns `{'main': DataFrame, 'reject': DataFrame}`
- `_update_stats(rows_in, rows_out, rows_rejected)` for globalMap vars
- Config validation via `_validate_config()` returning list of errors

### Integration Points
- Converter outputs: `Join` type with `use_inner_join`/`join_key`/`use_lookup_cols`/`lookup_cols`, `FilterColumns` type with schema only, `Unite` type with schema only
- Join receives multiple inputs as dict: `{'main': DataFrame, 'lookup': DataFrame}`
- Unite receives multiple inputs as dict: `{'input1': DataFrame, 'input2': DataFrame, ...}`

### Current Component Sizes (to be rewritten)
- join.py: 390 lines (P0 corruption, config mismatches, wrong null semantics, double merge)
- filter_columns.py: 205 lines (works but uses non-Talend config keys)
- unite.py: 393 lines (works but has MERGE/streaming modes not in Talend)

</code_context>

<specifics>
## Specific Ideas

No specific requirements beyond Talend feature parity. All implementation choices follow established Phase 4/6 patterns.

</specifics>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope.

</deferred>
