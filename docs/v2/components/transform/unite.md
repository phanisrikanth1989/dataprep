# Unite

## Purpose

Combines multiple input streams into one output using UNION ALL semantics. Equivalent of Talend **tUnite**. Every input row from every connected input appears in the output, preserving input order.

## When to Use

Use Unite when you need to:
- Merge rows from multiple processing branches into one stream
- Combine data from multiple sources before downstream processing
- Optionally deduplicate after union (mode: "distinct")
- Combine frames with different schemas using null-fill (align_schemas: true)

## Configuration

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `mode` | string | `"all"` | `"all"` keeps all rows (UNION ALL). `"distinct"` removes duplicates after union (v2-only). |
| `align_schemas` | boolean | `false` | When `true`, switches to `diagonal_relaxed` concat: columns are unioned, missing columns filled with null, types coerced. When `false` (default), all inputs must share identical schemas. |
| `inputs` | list | (all inputs) | Optional list of input names to include. By default, all connected inputs are unioned. v2-only feature. |

## Example

Basic union (two inputs):
```json
{
    "id": "merge_streams",
    "type": "unite",
    "config": {}
}
```

With deduplication:
```json
{
    "id": "merge_unique",
    "type": "unite",
    "config": {
        "mode": "distinct"
    }
}
```

Schema alignment (different column sets):
```json
{
    "id": "merge_relaxed",
    "type": "unite",
    "config": {
        "align_schemas": true
    }
}
```

## Supported Features

<!-- GENERATED: features -->
| Feature | Support | Note |
|---------|---------|------|
| `UniteFeature.align_schemas` | full | v2-only: switches to diagonal_relaxed concat for schema union + null-fill |
| `UniteFeature.inputs_selective` | full | v2-only: pick which named inputs to include in the union |
| `UniteFeature.label` | full | Component label for display/debugging |
| `UniteFeature.mode_distinct` | full | v2-only: remove duplicate rows after union via unique() |
| `UniteFeature.tstatcatcher_stats` | not_planned | tStatCatcher is a v1/Talend concept; use Python logging instead |
| `UniteFeature.unite` | full | Core UNION ALL semantics: all input rows combined into single output |
<!-- /GENERATED: features -->

## Unsupported Features

| Feature | Status | Advice |
|---------|--------|--------|
| `tstatcatcher_stats` | NOT_PLANNED | tStatCatcher is a v1/Talend concept; use Python logging instead. |

## v2-Native Capabilities

Unite offers capabilities beyond Talend's tUnite:

| Capability | Config | Description |
|------------|--------|-------------|
| Deduplication | `"mode": "distinct"` | Remove duplicate rows after union via Polars `unique()`. Talend requires a separate tUniqRow downstream. |
| Schema alignment | `"align_schemas": true` | Combine frames with different column sets. Missing columns filled with null, types coerced. Uses Polars `diagonal_relaxed` concat natively. |
| Selective inputs | `"inputs": ["orders", "returns"]` | Choose which connected inputs to include. Others are ignored. |

## Performance

<!-- GENERATED: benchmarks -->
_No benchmark baseline committed yet._
<!-- /GENERATED: benchmarks -->

Unite is a pure lazy transform -- `pl.concat()` composes into the Polars query plan with zero materialization overhead. The v2 component adds only the dictionary lookup and list-building cost on top of raw `pl.concat()`.

The default strict-vertical concat (`how="vertical"`) is the fastest path. The `align_schemas` opt-in (`how="diagonal_relaxed"`) adds schema-union overhead but is still a native Polars operation with no Python callbacks.

## Talend Differences

| Aspect | Talend tUnite | v2 Unite |
|--------|---------------|----------|
| Semantics | UNION ALL only | UNION ALL default; optional `"distinct"` mode for dedup |
| Schema handling | All inputs must share identical schema (enforced by Studio) | Default: strict match (`how="vertical"`, error on mismatch). Opt-in: `align_schemas: true` for column union + null-fill |
| Deduplication | Requires separate tUniqRow downstream | Built-in via `"mode": "distinct"` |
| Input selection | All connected flows always merged | Optional `"inputs"` list to pick specific inputs |
| Row ordering | Determined by connection order | Preserved by `pl.concat()` -- first frame's rows first, etc. |
| tStatCatcher | Supported via framework | Not planned (use Python logging) |
| Concat strategy | Java concatenation | Polars native `pl.concat()` -- lazy, vectorized, zero-copy when possible |
