# UniqRow

## Purpose

Deduplicates rows based on key columns with per-column case sensitivity control. Equivalent of Talend **tUniqRow**. Unique rows go to the `"unique"` output; optionally, duplicate rows go to the `"duplicate"` output.

## When to Use

Use UniqRow when you need to:
- Deduplicate a dataset by one or more key columns
- Split data into unique and duplicate subsets (dual output)
- Need per-column case sensitivity (e.g., case-insensitive on name but case-sensitive on code)
- Want Polars-optimized dedup with `keep='any'` for maximum performance

## Configuration

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `key_columns` | list[dict] | (required) | List of `{"column": "name", "case_sensitive": true/false}` dicts. Columns with `case_sensitive: false` are lowercased via `str.to_lowercase()` before comparison. |
| `keep` | string | `"first"` | Which duplicate to keep: `"first"`, `"last"`, `"none"`, or `"any"` (v2-only). |
| `maintain_order` | boolean | `true` | Preserve input row order. Set `false` for streaming-eligible unstable dedup. |
| `duplicate_output` | boolean | `false` | When `true`, emit duplicate rows on the `"duplicate"` output. Triggers engine barrier materialization. |
| `only_once` | boolean | `false` | When `true` with `duplicate_output`, only the first duplicate per key group goes to duplicate output (others discarded). |

## Example

Basic dedup (single output):
```json
{
    "id": "dedup_customers",
    "type": "uniq_row",
    "config": {
        "key_columns": [
            {"column": "email", "case_sensitive": false}
        ]
    }
}
```

With duplicate output:
```json
{
    "id": "split_dupes",
    "type": "uniq_row",
    "config": {
        "key_columns": [
            {"column": "customer_id", "case_sensitive": true},
            {"column": "name", "case_sensitive": false}
        ],
        "duplicate_output": true,
        "only_once": true
    }
}
```

## Supported Features

<!-- GENERATED: features -->
| Feature | Support | Note |
|---------|---------|------|
| `UniqRowFeature.buffer_size` | unsupported | Accessory to IS_VIRTUAL_COMPONENT; not applicable in v2. |
| `UniqRowFeature.change_hash_bigdecimal` | not_planned | Polars Decimal dtype has limited trailing-zero normalization. No native support. |
| `UniqRowFeature.dedup` | full | Core deduplication based on key columns via Polars unique() |
| `UniqRowFeature.is_virtual_component` | unsupported | Disk-based processing has no Polars equivalent. Lazy evaluation + streaming is v2's answer to large data. |
| `UniqRowFeature.keep_any` | full | v2-only: keep='any' gives Polars optimizer freedom when caller does not need deterministic first-seen behavior |
| `UniqRowFeature.keep_modes` | full | Talend keep='first'/'last'/'none' mapped directly to Polars unique() keep parameter |
| `UniqRowFeature.label` | full | Component label for display/debugging |
| `UniqRowFeature.maintain_order` | full | Default True preserves input row order (Talend-compatible). Set False for streaming-eligible unstable dedup. |
| `UniqRowFeature.only_once_each_duplicated_key` | full | When enabled, only first duplicate per key emitted to duplicate output (group_by + head(1)) |
| `UniqRowFeature.per_column_case_sensitivity` | full | Each key column has independent case_sensitive flag; case-insensitive keys lowercased via str.to_lowercase() (vectorized Rust) |
| `UniqRowFeature.temp_directory` | unsupported | Accessory to IS_VIRTUAL_COMPONENT; not applicable in v2. |
| `UniqRowFeature.tstatcatcher_stats` | not_planned | tStatCatcher is a v1/Talend concept; use Python logging instead |
| `UniqRowFeature.unique_duplicate_outputs` | full | Dual named outputs: 'unique' (first-seen rows) and 'duplicate' (subsequent occurrences) |
<!-- /GENERATED: features -->

## Unsupported Features

| Feature | Status | Advice |
|---------|--------|--------|
| `is_virtual_component` | UNSUPPORTED | Disk-based processing has no Polars equivalent. Lazy evaluation + streaming is v2's answer to large data. Use `maintain_order=false` for streaming-eligible dedup on large datasets. |
| `buffer_size` | UNSUPPORTED | Accessory to `is_virtual_component`. Not applicable in v2 -- Polars manages memory natively. |
| `temp_directory` | UNSUPPORTED | Accessory to `is_virtual_component`. Not applicable in v2 -- no disk-spill mechanism needed with lazy evaluation. |
| `change_hash_bigdecimal` | NOT_PLANNED | Polars Decimal dtype has limited trailing-zero normalization. `Decimal('1.00')` and `Decimal('1.0')` may be treated as different values. No native support for BigDecimal hash/equals normalization. |
| `tstatcatcher_stats` | NOT_PLANNED | tStatCatcher is a v1/Talend concept. Use Python logging for observability in v2. |

## v2-Native Capabilities

UniqRow offers capabilities beyond Talend's tUniqRow:

| Capability | Example | Description |
|------------|---------|-------------|
| `keep='any'` | `{"keep": "any"}` | Gives Polars optimizer freedom when order among duplicates doesn't matter. Fastest dedup mode. |
| `maintain_order=false` | `{"maintain_order": false}` | Enables streaming engine execution. ~10-30% faster on large datasets at cost of non-deterministic row order. |
| Per-column case sensitivity | `[{"column": "name", "case_sensitive": false}]` | Each key column independently controlled. Talend supports this but v1 engine did not (engine gap ENG-UNQ-001). |
| Dual named outputs | `"unique"` / `"duplicate"` | Semantic output names matching Talend UNIQUE/DUPLICATE connectors (not generic main/reject). |

## Performance

<!-- GENERATED: benchmarks -->
_No benchmark baseline committed yet._
<!-- /GENERATED: benchmarks -->

UniqRow is a pure lazy transform when `duplicate_output` is `false` -- it composes into
the Polars query plan with zero materialization overhead. The v2 component adds only the
subset computation and dictionary lookup cost on top of raw `pl.LazyFrame.unique()`.

When `duplicate_output` is `true`, two outputs are produced via row-index + anti-join,
triggering engine barrier materialization. The benchmark pair measures this overhead
separately for both case-sensitive and case-insensitive paths.

The case-insensitive path adds `str.to_lowercase()` temporary columns -- a vectorized
Polars Rust operation, not a Python callback. The benchmark reference does the same
lowercase step so the comparison isolates v2 wrapper overhead only (per D-10).

## Talend Differences

| Aspect | Talend Behavior | v2 Behavior | Impact |
|--------|-----------------|-------------|--------|
| Output connectors | Named UNIQUE (green) and DUPLICATE (orange) connectors | Dict keys `"unique"` and `"duplicate"` | Same semantics, different mechanism |
| NULL handling | NULLs treated as equal in Java comparisons | Polars `null == null` is True in `unique()` | Same net result; Polars treats null as a discrete value, not SQL three-valued logic (per D-15) |
| Per-column case sensitivity | Per-column CASE_SENSITIVE flag in UNIQUE_KEY TABLE | Per-column `case_sensitive` in key_columns config | Fully supported (fixes v1 engine gap ENG-UNQ-001) |
| ONLY_ONCE_EACH_DUPLICATED_KEY | Sends only first dup per key to DUPLICATE | `only_once=True` suppresses repeated dupes via `unique(keep='first')` on duplicate frame | Equivalent behavior |
| IS_VIRTUAL_COMPONENT | Disk-based processing for large datasets | UNSUPPORTED -- use lazy evaluation + streaming | Polars lazy eval + streaming handles large data differently |
| BigDecimal hash normalization | Normalizes trailing zeros in BigDecimal | NOT_PLANNED -- Polars Decimal has limited support | May differ on edge cases with Decimal types |
| keep modes | First or Last (ONLY_ONCE controls) | first, last, none, any (v2 adds 'any' and 'none') | Superset |
| maintain_order | Implicit (Java insertion order) | Explicit `maintain_order=True` (default) | Same default; v2 lets user opt out for performance |
| Global stats | NB_UNIQUES, NB_DUPLICATES in GlobalMap | Not emitted (use Python logging) | Different observability mechanism |
