# FilterColumns

## Purpose

Selects or removes columns from the input data. Equivalent of Talend **tFilterColumns**.

## When to Use

Use FilterColumns when you need to:
- Select a subset of columns from a wide dataset
- Remove unwanted columns before writing output
- Rename columns during selection

## Configuration

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `columns` | list | (required) | Column names to keep/remove. Each element is a string or `{"name": "target", "source": "original"}` dict for renaming. |
| `mode` | string | `"keep"` | `"keep"` selects listed columns; `"remove"` drops them and keeps the rest. |

## Example

```json
{
    "id": "select_cols",
    "type": "filter_columns",
    "config": {
        "columns": ["id", "name", "amount"]
    }
}
```

Remove mode:
```json
{
    "id": "drop_temp",
    "type": "filter_columns",
    "config": {
        "columns": ["temp_col", "debug_col"],
        "mode": "remove"
    }
}
```

## Supported Features

<!-- GENERATED: features -->
| Feature | Support | Note |
|---------|---------|------|
| `FilterColumnsFeature.columns` | full | Column list with optional source->name rename mapping |
| `FilterColumnsFeature.label` | full | Component label for display/debugging |
| `FilterColumnsFeature.mode` | full | 'keep' (default) selects listed columns; 'remove' drops them |
| `FilterColumnsFeature.tstatcatcher_stats` | not_planned | tStatCatcher is a v1/Talend concept; use Python logging instead |
<!-- /GENERATED: features -->

## Unsupported Features

| Feature | Status | Advice |
|---------|--------|--------|
| `tstatcatcher_stats` | NOT_PLANNED | tStatCatcher is a v1/Talend concept; use Python logging instead |

## Performance

<!-- GENERATED: benchmarks -->
| Metric | v2 Component | Raw Polars | Ratio |
|--------|-------------|------------|-------|
| Median | 0.01 ms | 0.01 ms | 1.01x |
| Polars version | 1.38.1 | | |
| Runs | 5 | | |
<!-- /GENERATED: benchmarks -->

FilterColumns is a pure lazy transform -- it composes into the Polars query plan
with zero materialization overhead. The v2 component adds only the dictionary lookup
and expression-building cost on top of raw `pl.LazyFrame.select()`.

## Talend Differences

| Aspect | Talend tFilterColumns | v2 FilterColumns |
|--------|----------------------|------------------|
| Column selection | Schema defines passthrough | Explicit `columns` config list |
| Mode parameter | `REMOVE_OR_KEEP` closed list | `mode`: `"keep"` / `"remove"` |
| tStatCatcher | Supported via framework | Not planned (use Python logging) |
| Column rename | Not supported | Supported via `{"name": "new", "source": "old"}` |
