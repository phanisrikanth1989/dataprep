# SortRow

## Purpose

Sorts rows by one or more columns with per-column direction and null positioning. Equivalent of Talend **tSortRow**. Single input (`"main"`), single output (`"main"`) -- not a barrier. The sort stays lazy via `LazyFrame.sort()` and the Polars optimizer decides when to materialize.

## When to Use

Use SortRow when you need to:
- Sort a dataset by one or more columns with explicit direction (ascending/descending)
- Control null positioning per column (nulls first or nulls last)
- Preserve input order for equal-valued rows (stable sort via `maintain_order`)
- Sort by multiple keys with mixed directions (e.g., category ascending, amount descending)

## Quick Start

```json
{
    "id": "sort_1",
    "type": "sort_row",
    "config": {
        "columns": [
            {"name": "date", "order": "desc"},
            {"name": "amount", "order": "asc", "nulls_last": true}
        ]
    }
}
```

## Configuration Reference

| Key | Type | Required | Default | Description |
|-----|------|----------|---------|-------------|
| `columns` | `list[dict]` | Yes | -- | Sort column definitions. Each dict has `name` (str, required), `order` (str, `"asc"` or `"desc"`, default `"asc"`), `nulls_last` (bool, overrides component-level default). See Column Entry Reference below. |
| `nulls_last` | `bool` | No | `false` | Default null positioning for all columns. When `true`, null values sort after non-null values. Per-column `nulls_last` overrides this value. |
| `maintain_order` | `bool` | No | `false` | Preserve input order for equal-valued rows (stable sort). **Performance impact:** enabling this prevents Polars from using parallel sorting algorithms and may disable streaming execution mode. Only use when row stability for equal keys is required. |

## Column Entry Reference

Each entry in the `columns` list is a dict with the following keys:

| Key | Type | Required | Default | Description |
|-----|------|----------|---------|-------------|
| `name` | `str` | Yes | -- | Column name to sort by. |
| `order` | `str` | No | `"asc"` | Sort direction: `"asc"` (ascending) or `"desc"` (descending). |
| `nulls_last` | `bool` | No | component `nulls_last` | Per-column null positioning override. When present, takes precedence over the component-level `nulls_last` default. |

## Behavior

- **Multi-column sort:** Columns are applied in order -- the first column is the primary sort key, subsequent columns are tiebreakers. This matches Talend's CRITERIA TABLE ordering.
- **Null handling:** Controlled by the `nulls_last` parameter (per-column or component-level). Per-column values override the component-level default when specified. When `nulls_last` is `false` (default), nulls sort before non-null values; when `true`, nulls sort after.
- **Lazy execution:** SortRow is **not** a barrier. `LazyFrame.sort()` stays lazy and composes into the Polars query plan. The Polars optimizer decides when to materialize.
- **Output:** Single `"main"` output with the same schema as input, rows reordered according to the sort criteria.
- **DataFrame coercion:** If a `pl.DataFrame` is passed as input, it is automatically converted to `pl.LazyFrame` before sorting.

## Supported Features

<!-- GENERATED: features -->
| Feature | Support | Note |
|---------|---------|------|
<!-- /GENERATED: features -->

## Unsupported Features

| Feature | Status | Advice |
|---------|--------|--------|
| `external` | NOT_PLANNED | JVM-specific memory management. Polars handles large dataset sorting natively via lazy execution and out-of-core processing. No manual external sort configuration needed. |
| `tempfile` | NOT_PLANNED | Only relevant with EXTERNAL=true. Polars handles large dataset sorting natively. |
| `createdir` | NOT_PLANNED | Only relevant with EXTERNAL=true. Polars handles large dataset sorting natively. |
| `external_sort_buffersize` | NOT_PLANNED | Only relevant with EXTERNAL=true. Polars handles large dataset sorting natively. |
| `sort_type` | NOT_PLANNED | Polars uses column dtype for comparison semantics (Int64 numerically, Utf8 lexicographically, Date chronologically). No equivalent needed. |
| `tstatcatcher_stats` | NOT_PLANNED | tStatCatcher is a v1/Talend concept. Use Python logging for observability in v2. |

## Talend Differences

### Sort Stability (GH #9916)

Polars sort is **unstable by default** (`maintain_order=false`). Equal-valued rows may be reordered arbitrarily for performance. Talend tSortRow sort is always stable -- equal-valued rows maintain their original input order.

When converting from Talend, the `talend_to_v2` converter emits `maintain_order: true` to preserve Talend's stable-sort behavior. v2-native users can leave `maintain_order: false` (the default) for better performance when stability among equal-keyed rows is not needed.

Reference: [Polars sort stability discussion](https://github.com/pola-rs/polars/issues/9916).

### Performance: Stable Sort and Streaming

> **Performance warning:** Setting `maintain_order=true` (stable sort) prevents Polars from using parallel sorting algorithms and may disable streaming execution mode. On large datasets, this can result in significantly higher memory usage and longer execution times compared to the default unstable sort (`maintain_order=false`). The `talend_to_v2` converter emits `maintain_order: true` by default for correctness; if your pipeline does not depend on the relative order of equal-keyed rows, consider setting `maintain_order: false` for better throughput.

This aligns with the project's "Performance first" value (PROJECT.md) -- users should understand the cost of stable sort before opting in.

### Sort Type (NUM/ALPHA/DATE)

Talend's CRITERIA TABLE has a `SORT` field that specifies the comparison data type (`NUM`, `ALPHA`, or `DATE`). Polars does not need this -- column dtype determines comparison semantics automatically:

| Talend SORT | Polars equivalent |
|-------------|-------------------|
| `NUM` | Int64/Float64 sorts numerically by nature |
| `ALPHA` | Utf8 sorts lexicographically by nature |
| `DATE` | Date/Datetime sorts chronologically by nature |

The `SORT` field is dropped during conversion. No v2 config equivalent exists.

### External Sort

Talend's `EXTERNAL` option enables disk-based sorting for large datasets that exceed JVM heap memory. Polars handles large dataset sorting natively via lazy execution and out-of-core processing -- no manual external sort configuration is needed. The related parameters (`TEMPFILE`, `CREATEDIR`, `EXTERNAL_SORT_BUFFERSIZE`) are all dropped during conversion with a warning.

### Null Positioning

Talend tSortRow has no native null-positioning control -- nulls are positioned according to Java's `Comparable` contract (nulls typically sort to the beginning or end depending on the comparator implementation). In v2, null positioning is explicitly controlled via the `nulls_last` parameter:

- **Component-level default:** `nulls_last: false` (nulls sort before non-null values)
- **Per-column override:** Each column entry can include its own `nulls_last` value, which takes precedence over the component-level default

The converter does not emit `nulls_last`, so the runtime default (`false`, nulls first) applies to converted jobs. Users can customize this in v2-native configs.

## Performance

<!-- GENERATED: benchmarks -->
<!-- /GENERATED: benchmarks -->

SortRow is a pure lazy transform -- it composes `LazyFrame.sort()` into the Polars query plan with zero materialization overhead. The v2 component adds only the parameter extraction and list-building cost on top of raw `pl.LazyFrame.sort()`.

When `maintain_order=false` (default), Polars can use parallel sorting algorithms and streaming execution for maximum throughput. Setting `maintain_order=true` forces a stable sort that serializes the operation.

## Examples

### Simple single-column sort

Sort customers by name in ascending order (default):

```json
{
    "name": "sort_by_name",
    "engine": "v2",
    "components": [
        {
            "id": "src",
            "type": "file_input_delimited",
            "config": {
                "path": "customers.csv",
                "delimiter": ";",
                "schema": [
                    {"name": "id", "type": "int"},
                    {"name": "name", "type": "string"}
                ]
            }
        },
        {
            "id": "sort",
            "type": "sort_row",
            "config": {
                "columns": [{"name": "name"}]
            }
        }
    ],
    "flows": [
        {"source": "src", "target": "sort", "output": "main", "input": "main"}
    ]
}
```

### Multi-column with mixed orders and null positioning

Sort transactions by category ascending, then amount descending, with nulls at the end:

```json
{
    "id": "sort_transactions",
    "type": "sort_row",
    "config": {
        "columns": [
            {"name": "category", "order": "asc"},
            {"name": "amount", "order": "desc", "nulls_last": true}
        ],
        "nulls_last": false
    }
}
```

In this example, `category` uses the component-level `nulls_last: false` (nulls first), while `amount` overrides it with `nulls_last: true` (nulls last).

### Stable sort for Talend-converted jobs

When converting from Talend, `maintain_order: true` preserves the original stable-sort semantics:

```json
{
    "id": "sort_stable",
    "type": "sort_row",
    "config": {
        "columns": [
            {"name": "department", "order": "asc"},
            {"name": "hire_date", "order": "desc"}
        ],
        "maintain_order": true
    }
}
```

> This is the config shape the `talend_to_v2` converter emits. If stability among equal-keyed rows is not important for your use case, remove `maintain_order` (or set it to `false`) for better performance.

## See Also

- [COMPONENT_STANDARD.md](../../COMPONENT_STANDARD.md) -- v2 component standard specification
- [Polars LazyFrame.sort()](https://docs.pola.rs/api/python/stable/reference/lazyframe/api/polars.LazyFrame.sort.html) -- Polars sort API reference
