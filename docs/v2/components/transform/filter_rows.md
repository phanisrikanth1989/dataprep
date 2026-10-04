# FilterRows

## Purpose

Filters rows based on a condition expression compiled by the v2 DSL. Equivalent of Talend **tFilterRow**. Rows matching the condition pass to the "main" output; optionally, rejected rows go to the "reject" output.

## When to Use

Use FilterRows when you need to:
- Filter a dataset by a boolean condition
- Split data into matching and non-matching subsets (reject output)
- Apply complex filter expressions using the v2 DSL (comparisons, functions, compound logic)

## Configuration

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `condition` | string | (required) | v2 DSL expression evaluating to boolean. Supports column refs, operators (`==`, `!=`, `<`, `<=`, `>`, `>=`), logical ops (`&&`, `\|\|`), and built-in functions. |
| `reject_output` | boolean | `false` | When `true`, rejected rows (not matching condition) are emitted on the `"reject"` output. Triggers engine barrier materialization (two outputs). |

## Example

Basic filter:
```json
{
    "id": "filter_active",
    "type": "filter_rows",
    "config": {
        "condition": "status == 'active' && amount > 100"
    }
}
```

With reject output:
```json
{
    "id": "split_by_amount",
    "type": "filter_rows",
    "config": {
        "condition": "amount > 1000",
        "reject_output": true
    }
}
```

## Supported Features

<!-- GENERATED: features -->
| Feature | Support | Note |
|---------|---------|------|
| `FilterRowsFeature.advanced_cond` | unsupported | Freeform Java expressions cannot run in Polars. Rewrite as a v2 expression using supported DSL functions. |
| `FilterRowsFeature.condition` | full | v2-native single expression string (superset of Talend CONDITIONS) |
| `FilterRowsFeature.conditions` | full | Stride-4 CONDITIONS table (INPUT_COLUMN, FUNCTION, OPERATOR, RVALUE) with all common FUNCTION pre-transforms compiled to v2 DSL |
| `FilterRowsFeature.label` | full | Component label for display/debugging |
| `FilterRowsFeature.logical_op` | full | AND/OR joining of multiple conditions, compiled to && / \|\| in v2 DSL |
| `FilterRowsFeature.reject_output` | full | Opt-in: emitted only when job wires a reject flow; triggers engine barrier materialization |
| `FilterRowsFeature.tstatcatcher_stats` | not_planned | tStatCatcher is a v1/Talend concept; use Python logging instead |
| `FilterRowsFeature.use_advanced` | unsupported | Freeform Java expressions cannot run in Polars. Rewrite as a v2 expression using supported DSL functions. |
<!-- /GENERATED: features -->

## Unsupported Features

| Feature | Status | Advice |
|---------|--------|--------|
| `use_advanced` | UNSUPPORTED | Freeform Java expressions cannot run in Polars. Rewrite as a v2 expression using the supported DSL functions (LOWER, UPPER, TRIM, LENGTH, ABS, CONTAINS, REGEX_MATCH, etc.). |
| `advanced_cond` | UNSUPPORTED | Same as `use_advanced` -- the expression text cannot be translated. Manual rewrite required. |
| `tstatcatcher_stats` | NOT_PLANNED | tStatCatcher is a v1/Talend concept; use Python logging instead. |

## v2-Native Capabilities

The expression-only interface gives v2-native users capabilities beyond Talend's structured CONDITIONS:

| Capability | Example | Description |
|------------|---------|-------------|
| Range checks | `amount >= 100 && amount <= 500` | Compound range conditions (Talend requires two separate CONDITIONS rows) |
| Set membership | `CONTAINS(category, 'premium')` | String containment check via DSL function |
| Chained functions | `LENGTH(TRIM(name)) > 0` | Nested function calls for multi-step transforms |
| Math in filters | `price * quantity > 10000` | Arithmetic expressions in conditions |
| Null checks | `ISNULL(email)` or `ISNOTNULL(phone)` | Explicit null handling via DSL functions |
| Regex filtering | `REGEX_MATCH(code, '^[A-Z]{3}')` | Pattern matching via REGEX_MATCH |

## Performance

<!-- GENERATED: benchmarks -->
_No benchmark baseline committed yet._
<!-- /GENERATED: benchmarks -->

FilterRows is a pure lazy transform when `reject_output` is `false` -- it composes into
the Polars query plan with zero materialization overhead. The v2 component adds only the
expression compilation and dictionary lookup cost on top of raw `pl.LazyFrame.filter()`.

When `reject_output` is `true`, two outputs are produced, triggering engine barrier
materialization. The reject-on benchmark pair measures this overhead separately.

## Talend Differences

| Aspect | Talend tFilterRow | v2 FilterRows |
|--------|-------------------|---------------|
| Condition format | Structured stride-4 table (INPUT_COLUMN, FUNCTION, OPERATOR, RVALUE) | Single v2 DSL expression string |
| FUNCTION pre-transforms | Applied per-condition (LOWER_CASE, UPPER_CASE, TRIM, etc.) | Compiled to DSL functions (LOWER, UPPER, TRIM, etc.) -- all common functions supported |
| LOGICAL_OP | AND / OR joining conditions | `&&` / `\|\|` in expression |
| Advanced mode | Freeform Java expression (`USE_ADVANCED`) | **UNSUPPORTED** -- rewrite as v2 expression |
| NULL semantics | Java null comparison returns `false` directly | Polars NULL comparison returns NULL (treated as `false` by `filter()`). Same end result for simple filters; compound expressions may differ due to intermediate null propagation |
| Reject output | Always available as REJECT connector | Opt-in via `reject_output: true` config |
| FUNCTION coverage | v1 converter flagged ALL FUNCTION values as engine gaps | **v2 clean upgrade**: all common FUNCTIONs compile to native Polars expressions via DSL |
| tStatCatcher | Supported via Talend framework | Not planned (use Python logging) |
