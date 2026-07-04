# What BaseComponent Currently Handles

*Last updated: 2026-05-11*

## 1. Template Method Lifecycle (execute(), ~8 steps)

| Step | What it does |
|------|-------------|
| 1 | Fresh config from `_original_config` via deepcopy (ENG-09/ENG-21) |
| 2 | `_validate_config()` -- abstract, every subclass must implement |
| 3 | `_resolve_expressions()` -- Java `{{java}}` markers + `${context.var}` resolution |
| 4 | Read `die_on_error` from resolved config |
| 5 | Capture `_input_row_count` for NB_LINE |
| 6 | `_select_mode()` -- auto BATCH/STREAMING based on 3GB threshold |
| 7 | `_execute_batch()` or `_execute_streaming()` -> delegates to `_process()` |
| 7b | `_enforce_schema_column_order()` -- reorder + add missing columns (main + reject) |
| 7c | `_apply_output_schema_validation()` -- type coercion, precision, length truncation (main + reject) |
| 8 | `_update_stats_from_result()` + `_update_global_map()` |

## 2. Config Immutability

- `_original_config` deepcopied at construction, never mutated
- `config` re-derived every `execute()` call -- safe for iterate loops

## 3. Execution Modes

- **BATCH:** full DataFrame in one `_process()` call
- **STREAMING:** chunks at configurable `chunk_size` (default 10,000), collects ALL named flows (ENG-07/ENG-20)
- **HYBRID:** auto-selects based on `memory_usage(deep=True)` vs `MEMORY_THRESHOLD_MB` (3GB)

## 4. Java Expression Resolution

- Recursive config scan for `{{java}}` markers
- Syncs context + globalMap to Java bridge before evaluation
- Batch `execute_batch_one_time_expressions` for efficiency
- Handles `{{ERROR}}` results from bridge

## 5. Schema Validation (validate_schema)

- Type coercion: str -> object, int -> int64, float -> float64, bool -> bool, datetime -> datetime64[ns], Decimal -> object
- Nullable enforcement (ENG-19): raises `DataValidationError` for non-nullable columns with nulls
- Nullable int: uses `pd.Int64Dtype()` for int columns with nulls
- Decimal precision: `ROUND_HALF_UP` via `_apply_decimal_precision`
- String length truncation: truncates values exceeding `col_length` (FIX-GAP-02)
- Applied to both main and reject DataFrames (FIX-GAP-03)

## 6. Column Ordering (_enforce_schema_column_order)

- Reorders DataFrame columns to match schema order
- Adds missing schema columns with type-appropriate defaults:
  - Nullable -> `pd.NA` (or `pd.NaT` for nullable datetime, post-G-01 fix)
  - Non-nullable str -> `""`
  - Non-nullable int/float/Decimal -> `0`
  - Non-nullable bool -> `False`
  - Non-nullable datetime -> `pd.Timestamp(0)` (post-G-01 fix)
- Applied to both main (`output_schema`) and reject (`reject_schema`) (FIX-GAP-04)

## 7. Stats Management

- `NB_LINE`, `NB_LINE_OK`, `NB_LINE_REJECT` counters
- Auto-computed from result dict (source components: output count; transforms: input count)
- Manual `_update_stats()` for component-managed stats (avoids double-counting via `_stats_set_by_component` flag)
- Pushed to GlobalMap via `_update_global_map()`

## 8. Other

- Status tracking: PENDING -> RUNNING -> SUCCESS/ERROR
- Reset for iteration: `reset()` clears stats, status, globalMap
- Python routine access: `get_python_routines()`
- Error wrapping: all non-`ConfigurationError` exceptions wrapped in `ComponentExecutionError(component_id, cause)`

---

# What It Doesn't Handle (Gaps)

Gap status legend:
- **FIXED Phase 7.1** -- gap closed; see `.planning/phases/07.1-base-component-class-improvements/07.1-PHASE-SUMMARY.md` and the `base_component.py` module docstring header.
- **OPEN** -- gap still present; tracked for a future phase.

| # | Gap | Impact |
|---|-----|--------|
| **G-01** | ~~**Datetime defaults for missing columns** -- `_enforce_schema_column_order` uses `pd.NA` for nullable datetime, `""` for non-nullable. Should use `pd.NaT` for nullable datetime and a sentinel for non-nullable.~~ **FIXED Phase 7.1** (WR-01/G-01: missing datetime columns now filled with `pd.NaT` (nullable) or `pd.Timestamp(0)` (non-nullable); see `base_component.py` docstring). | Wrong default type for datetime columns |
| **G-02** | ~~**Decimal coercion in `_coerce_column_type`** -- Decimal falls through to "object" (no-op). String values like "123.45" won't become `Decimal` objects until `_apply_decimal_precision` runs. If no `precision` attribute, they stay as strings forever.~~ **FIXED Phase 7.1** (G-02: Decimal columns without precision now coerced to Decimal objects in `_coerce_column_type`). | Missing Decimal conversion for columns without precision |
| **G-03** | ~~**Float precision** -- Only Decimal columns get precision applied. Talend also rounds float/double columns to their schema precision.~~ **FIXED Phase 7.1** (G-03: Float columns with declared precision now rounded to that precision). | Float values may have extra decimal places vs Talend output |
| **G-04** | ~~**date_pattern not used** -- Schema columns can have `date_pattern` (e.g. "yyyy-MM-dd"). `pd.to_datetime` uses default inference, not the specified pattern. Formatting on output is also not applied.~~ **FIXED Phase 7.1** (G-04: `date_pattern` attribute now used for datetime parsing; Talend default chain -> ISO 8601 -> inference). | Datetime parsing may fail or produce wrong results for non-standard formats |
| **G-05** | ~~**`die_on_error` not checked in schema validation** -- `validate_schema` raises `DataValidationError` for non-nullable nulls regardless of `die_on_error`. If `die_on_error=False`, it should log and continue (produce empty/default).~~ **FIXED Phase 7.1** (G-05/D-11: `die_on_error=False` now routes schema-violating rows to reject with `errorCode=SCHEMA_VIOLATION`). | Fatal error even when job config says to continue |
| **G-06** | **OPEN**: No input schema validation -- Only output/reject schemas validated. Input data accepted as-is. | Garbage-in passes silently, type mismatches detected late |
| **G-07** | **OPEN**: No schema default values -- Talend supports column-level `default` attribute. Not implemented. | Missing columns get generic defaults instead of schema-specified ones |
| **G-08** | **OPEN**: No `key` attribute enforcement -- Schema has `key: true/false` but never used for uniqueness checks or lookup optimization. | No key constraint validation |
| **G-09** | **OPEN**: No error flow routing -- Talend has error links that capture component errors and route them. No equivalent mechanism. | Errors either fail the component or get swallowed |
| **G-10** | ~~**Streaming defeats schema validation** -- Steps 7b/7c run AFTER chunks are concatenated, so the full DataFrame is in memory. Partially defeats streaming's memory goal.~~ **FIXED Phase 7.1** (G-10/D-12: `_execute_streaming` now runs schema validation per chunk, not after concatenation). | Memory spike for large datasets in streaming mode |
| **G-11** | **OPEN**: NB_LINE multi-input -- `_count_input_rows` sums all dict inputs into one number. Talend tracks NB_LINE per input link for multi-input components (e.g. tMap). | Stats differ from Talend for multi-input components |
| **G-12** | ~~**Empty string vs null** -- No explicit distinction. `pd.to_numeric("", errors="coerce")` -> NaN, masking intentional empty strings.~~ **FIXED Phase 7.1** (G-12/D-10: `treat_empty_as_null` per-column attribute now controls empty-string-to-null coercion; default `True` for numeric/datetime/Decimal, `False` for str). | Semantic data loss for string fields |
