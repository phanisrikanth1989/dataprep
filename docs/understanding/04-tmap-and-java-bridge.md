# tMap Engine & Java/Groovy Bridge

This document is a deep dive into the two trickiest subsystems of DataPrep's V1
execution engine:

1. **The tMap engine** (`src/v1/engine/components/transform/map/`) -- the
   pure-Python orchestration that joins a main flow against lookups, generates
   chunked Groovy scripts for per-row Talend expression evaluation, and routes
   rows to multiple named outputs (including three reject flavours).
2. **The Java/Groovy bridge** (`src/v1/java_bridge/` + `src/v1/engine/java_bridge_manager.py`)
   -- the Py4J + Apache Arrow plumbing that runs legacy Talend Java/Groovy
   expressions against pandas DataFrames at runtime.

These two subsystems are intertwined: tMap is the bridge's single largest and
most demanding consumer, and almost every bridge design decision (Arrow
serialization, chunking, context/globalMap sync, the compile-once cache) exists
to make tMap correct and fast.

Audience: engineers extending this codebase and raising per-module test coverage
to the 95% floor. ASCII-only by project rule.

---

## 1. Why these two subsystems are coupled

Talend's tMap (and tJavaRow, tJava, output filters, RunIf conditions, etc.)
embed arbitrary Java/Groovy expressions that the converter cannot safely rewrite
to Python. The converter prefixes such expressions with a `{{java}}` marker and
defers them to the engine. At runtime the engine must:

- serialize a pandas DataFrame to something the JVM can read efficiently
  (Apache Arrow IPC byte buffers),
- run the original Talend expression (using the *real* vendored Talend routine
  library: `TalendDate`, `StringHandling`, `Mathematical`, etc.),
- deserialize the result back to pandas,
- keep `context` and `globalMap` (Talend's stateful variables) consistent across
  every call.

The tMap engine sits on top of all of this. It builds the joined frame in pure
pandas (the bridge does not join), then **generates** a Groovy script (it does
not interpret expressions itself) and hands that to the bridge for
compile-once / execute-many evaluation.

```
joined_df (pandas)  -->  Groovy source (map_compiled_script)
                          |
                          v
                    JavaBridge.compile_tmap_script  (parse + cache Script class)
                          |
                    JavaBridge.execute_compiled_tmap_chunked
                          |  Arrow IPC bytes per chunk
                          v
                    JVM: per-row Groovy over RowWrapper, vendored routines
                          |  Arrow IPC bytes per output (+ __errors__)
                          v
                    pandas output frames  -->  route_rejects  -->  result dict
```

---

## 2. tMap engine

### 2.1 Module map

| File | LOC | Responsibility |
| --- | --- | --- |
| `map/__init__.py` | 11 | Package entry; re-exports `Map`. Documents that `map_legacy.py` was removed (Phase 11) after a diff harness confirmed bit-for-bit parity. |
| `map/map_config.py` | 237 | Config dataclasses (`MapConfig`, `MainInputCfg`, `LookupCfg`, `JoinKeyCfg`, `VariableCfg`, `OutputCfg`, `ColumnCfg`) + `parse_config` + `validate_config` + `has_any_java_marker`. |
| `map/map_component.py` | 443 | `Map(BaseComponent)` orchestrator. Owns the 6-phase `_process` flow. |
| `map/map_joins.py` | 934 | Join strategy classifier + five join implementations + matching-mode dedup + null-key prefilter + dtype-preserving empty-lookup attach + `compute_joined_df_schema` + RELOAD row-ref substitution + size guards. |
| `map/map_compiled_script.py` | 621 | Pure Groovy source generator. Closure-chunked active and reject scripts; GString `$`-escaping; error tracking. |
| `map/map_bridge_sync.py` | 55 | The **only** module that writes `bridge.context` / `bridge.global_map` directly (bypassing setters). `id_Float` Java-wrapping. |
| `map/map_reject_routing.py` | 154 | Post-bridge routing of the 3 reject types into the final output dict. |

The package is a **modular rewrite** of the removed `map_legacy.py`. Each concern
lives in its own pure-function module; `map_component.py` is a thin orchestrator
that injects bridge-eval closures into the otherwise side-effect-free join/script
modules (this is what makes them unit-testable without a live JVM).

### 2.2 Config shape (`map_config.py`)

`parse_config(raw)` constructs typed dataclasses but does **no** semantic
validation; `validate_config(cfg, java_bridge_available)` does the checks. The
JSON shape mirrors what the converter emits
(`tests/fixtures/jobs/transform/map_with_lookup.json`).

Key dataclass fields:

- `MainInputCfg`: `name`, `filter`, `activate_filter`, `matching_mode`
  (default `UNIQUE_MATCH`), `lookup_mode` (default `LOAD_ONCE`).
- `LookupCfg`: `name`, `join_keys: list[JoinKeyCfg]`, `join_mode`
  (default `LEFT_OUTER_JOIN`), `matching_mode`, `lookup_mode`, `filter`,
  `activate_filter`.
- `JoinKeyCfg`: `lookup_column`, `expression` (the main-side expression, which
  may be a column ref or a `{{java}}`-marked Java expression), `type`,
  `operator` (default `=`).
- `OutputCfg`: `name`, `columns: list[ColumnCfg]`, plus the three reject flags
  `is_reject` / `inner_join_reject` / `catch_output_reject`, plus an optional
  output-level `filter`/`activate_filter`.
- `ColumnCfg`: `name`, `expression`, `type`, `nullable`, `length`, `precision`,
  `date_pattern`.

`validate_config` raises `ConfigurationError` for: missing main name, no
outputs, an output without a name or columns, a lookup without a name, a
join_key missing `lookup_column` or `expression`. Critically, if
`has_any_java_marker(cfg)` is true and no Java bridge is attached, it raises so
the job fails loudly instead of silently dropping expressions
(`map_config.py:231-236`).

### 2.3 The `Map` component lifecycle overrides

`Map` subclasses `BaseComponent` and is registered under both names:
`@REGISTRY.register("Map", "tMap")`. It overrides four lifecycle hooks
(`map_component.py`):

- **`_resolve_expressions`** -- *skips* the parent's per-row Java resolution.
  Row-level `{{java}}` markers reference per-row data that does not exist at
  config-resolution time; they are evaluated per row inside the compiled Groovy
  script. Only scalar config fields (`die_on_error`, `label`,
  `enable_auto_convert_type`, `rows_buffer_size`, `output_chunk_size`) get
  context-variable resolution here.
- **`_select_mode`** -- always returns `ExecutionMode.BATCH`. tMap does its own
  chunking via the bridge (`map_component.py:51-53`).
- **`_validate_config`** -- runs `parse_config` + `validate_config`, stashing the
  parsed config on `self._parsed_cfg`.
- **`_update_stats_from_result`** -- sums rows across **all** named outputs (not
  just `main`/`reject`); any output flagged `is_reject` / `inner_join_reject` /
  `catch_output_reject` counts toward `NB_LINE_REJECT`.

### 2.4 The 6-phase `_process` data flow

`Map._process` (`map_component.py:83-374`) is the heart of the engine. Inputs
arrive as either a `dict[flow_name -> DataFrame]` (multi-input) or a bare
DataFrame (treated as the main flow via `_parse_inputs`).

**Phase 1 -- main filter.** If `cfg.main.activate_filter`, the main filter is
evaluated against the main frame via `apply_filter` (which calls the bridge).
Empty result short-circuits to empty outputs.

**Phase 2 -- sequential lookup joins.** `joined_df` starts as a copy of the main
frame. Each lookup is processed in order:
- If the lookup frame is missing or empty, the code **short-circuits the strategy
  dispatch** and attaches typed-empty prefixed columns via
  `_attach_empty_lookup_columns`. This is a hard Talend-parity requirement: a
  missing lookup must **not** strip its columns from `joined_df`, because
  downstream filters and output expressions legitimately reference
  `row<N>.col`. For `INNER_JOIN` the main rows become rejects and `joined_df`
  is emptied; for `LEFT_OUTER` all main rows are preserved with null lookup
  columns (`map_component.py:126-168`).
- Otherwise `classify_join_strategy` picks a strategy and the matching
  `join_*` function is dispatched. Any rejected rows accumulate in
  `inner_join_reject_dfs` keyed by lookup name. The consumed lookup's schema is
  recorded so later expressions can reference earlier-joined lookups.

**Phase 3 -- joined schema.** `compute_joined_df_schema` composes the
`joined_df` column-type map from declared types only (main columns unprefixed,
lookup columns as `lookup_name.col`, variables as `Var.name`). This is the
**single source of truth** for Arrow serialization -- no inference, no fallback
to `str` (`map_joins.py:84-119`).

**Phase 4 -- active script.** `build_active_script(cfg)` generates Groovy;
`push_runtime_state_to_bridge` flushes context/globalMap; `compile_tmap_script`
parses + caches it under `f"{self.id}__active"`; `execute_compiled_tmap_chunked`
runs it over `joined_df` with `chunk_size=50000`. The special `__errors__`
frame (row-level capture for `catch_output_reject` and `die_on_error=False`) is
popped from the result (`map_component.py:252-323`).

**Phase 5 -- reject pass.** Only if any `inner_join_reject` output is configured
**and** there are actual reject rows. The accumulated `inner_join_reject_dfs` are
reindexed to `joined_df.columns` and concatenated into a reject row source, a
*separate* reject script is compiled under `f"{self.id}__reject"`, and run.

**Phase 6 -- route rejects.** `route_rejects` merges the active results, reject
results, the `__errors__` frame, and `joined_df` into the final
`dict[output_name -> DataFrame]`, always producing a frame for every configured
output.

After `_process` returns, `BaseComponent.execute` enforces output schema/column
order, coerces types, and updates `NB_LINE`/`OK`/`REJECT`.

### 2.5 Join strategy classification

`classify_join_strategy` (`map_joins.py:45-81`) selects one of five strategies
per lookup using a first-match decision order:

| Order | Condition | Strategy | Behaviour |
| --- | --- | --- | --- |
| 1 | `lookup_mode == "RELOAD_AT_EACH_ROW"` | `RELOAD` | Re-match the lookup for every main row; O(main x lookup) Python loop. |
| 2 | no join keys | `FILTER_AS_MATCH` | Chunked cross-product, optionally filtered by `lk.filter`. |
| 3 | every key expression is main-row-independent (refers only to `context.*` / `globalMap.*` / literals) | `CONSTANT_KEY` | Resolve all key values once via a single bridge call, pre-filter the lookup, broadcast. |
| 4 | every key is a `<known_input>.<col>` ref | `SIMPLE` | Direct pandas merge. |
| 5 | otherwise (at least one key is a computed expression) | `COMPUTED` | Batch-eval each key expression once across all rows, materialize temp columns, then merge. |

The classifier distinguishes a bona-fide `<table>.<col>` reference from a
Java-side accessor (`context.SOURCE`, `globalMap.X`) by checking whether the
table segment is `main_name` or a prior-lookup name
(`_is_known_input_col_ref`, `_is_main_row_independent`). Both helpers strip the
`{{java}}` marker and ignore tokens that fall inside double-quoted string
literals.

### 2.6 The five join implementations

All five live in `map_joins.py` and return `(merged_frame, inner_join_rejects_or_None)`.

- **`join_simple_equality`** -- applies matching-mode dedup to the lookup,
  prefixes lookup columns (`lookup_name.col`), then does a single
  `pd.merge(how="left", indicator=True)`. For `INNER_JOIN`, `left_only` rows
  become rejects. Null join keys are pre-split out via `_prefilter_null_keys`
  before the merge (null-never-matches) and re-added afterwards for
  `LEFT_OUTER`.
- **`join_computed_equality`** -- batch-evaluates each key expression on
  `joined_df` via the bridge (`bridge_eval_fn`), materializes the results as
  `__jk_main_<i>__` temp columns, merges on the temp columns, then drops them.
- **`join_constant_key`** -- evaluates every key once via
  `execute_batch_one_time_expressions`, checks for `{{ERROR}}` markers
  (raising `ComponentExecutionError` on failure), filters the lookup with
  pandas, dedups, and broadcasts via a cross-merge. Any null resolved value
  short-circuits to "no match" (Talend `HashMap.get(null)` semantics).
- **`join_filter_as_match`** -- chunked cross-product of `joined_df` x lookup; if
  a filter is set it is bridge-evaluated **once per chunk** (not per row) and
  the boolean mask applied. Chunk size is auto-tuned to bound peak intermediate
  memory at ~100M cells.
- **`join_reload_per_row`** -- nested `iterrows` loop; per main row it optionally
  substitutes that row's column values into the lookup filter
  (`_substitute_row_refs`), bridge-evaluates the substituted filter, and matches
  keys with Python `!=`. This is the per-row-reload semantic of
  `RELOAD_AT_EACH_ROW`.

#### Matching-mode dedup (`_apply_matching_mode`)

Mirrors Talend's `HashMap.put` semantics:

| `matching_mode` | pandas dedup | Rationale |
| --- | --- | --- |
| `UNIQUE_MATCH` | `keep="last"` | `HashMap.put` overwrites on duplicate key -> last write wins. |
| `LAST_MATCH` | `keep="last"` | Same as unique for dedup purposes. |
| `FIRST_MATCH` | `keep="first"` | First occurrence wins. |
| `ALL_MATCHES` | no dedup | Cartesian fan-out preserved. |

#### Size guards

`FILTER_AS_MATCH` and `CONSTANT_KEY` enforce a 10M-row **warn** threshold and a
100M-row **fail** threshold (`_check_cross_size_guard` raises
`ComponentExecutionError`). **`RELOAD` has no size guard** -- a large reload
lookup degrades silently and is a known performance cliff (one bridge round-trip
per main row when the reload lookup has an active filter).

### 2.7 `_attach_empty_lookup_columns`: Arrow dtype fidelity

`_attach_empty_lookup_columns` (`map_joins.py:478-520`) is a careful,
dtype-preserving null fill used on the empty-lookup branches:

| Source dtype | Fill | Why |
| --- | --- | --- |
| datetime | `pd.NaT` (same dtype) | preserves timestamp type |
| integer | `np.nan` as `float64` | mirrors pandas promoting int->float64 on a left merge against an empty int lookup |
| object (str / Decimal) | Python `None` | so Arrow serializes the *declared* type (e.g. `BigDecimal`=16 bytes), **not** float64 NaN (8 bytes), which would clash |
| float / bool | `np.nan` (same dtype) | dtype preserved |

This is exactly the kind of subtle Arrow-serialization parity detail that is
easy to get wrong, and it is the matching half of why
`compute_joined_df_schema` keeps declared types as the single source of truth.

> **Known gap.** The `SIMPLE`/`COMPUTED` `LEFT_OUTER` null-key path re-adds
> null-key main rows via `pd.concat` (`map_joins.py:224, 321`) *without* the
> dtype-preserving fill, so for those specific rows missing lookup columns
> become `float64` NaN rather than Python `None`. For object-typed
> (str/Decimal) lookup columns on null-key rows this is a latent dtype-fidelity
> mismatch -- and it only triggers on null-key rows, so it is easy to miss in
> tests. Whether it surfaces downstream depends on whether `BaseComponent`
> output-schema coercion masks it before the bridge re-serializes.

### 2.8 Compiled-script generation (`map_compiled_script.py`)

`build_active_script(cfg)` and `build_reject_script(cfg)` are **pure functions**:
`MapConfig` in, Groovy source string out, no bridge calls. The generated script
has a closure-chunked layout to stay under the **64KB JVM per-method bytecode
limit**:

- `_CHUNK_TARGET_CHARS = 8000` -- target emitted-source size per closure
  (matches Spark's JIT-inlining cutoff; ~8x headroom under 64KB).
- `_SINGLE_EXPR_HARD_CAP = 50000` -- a single column/variable/filter expression
  exceeding this raises `ConfigurationError` *before* the script reaches the
  bridge, with an actionable message ("split into a Var or reduce its size").

Variables and each output's columns are emitted as numbered Groovy closures
(`vars_chunk{N}`, `{out}_chunk{N}`, `{out}_reject_chunk{N}`) defined at the top
of `run()`; the row loop dispatches by `.call(...)`. Output filters below the
chunk threshold stay inline in the `if (...)` guard; larger filters are hoisted
to a `{out}_filter` closure.

The active script (`build_active_script`):
- imports `java.util.*` and `com.citi.gru.etl.RowWrapper`,
- classifies outputs into active / `is_reject` / `catch_output_reject`,
- enables error tracking (`errorMap`/`stackTraceMap` -> `__errors__`) when
  `die_on_error` is false **or** any `catch_output_reject` output exists,
- builds a `RowWrapper` per input per row via `buildRowWrapper`,
- for `is_reject` outputs, tracks a `matchedAny` boolean and routes unmatched
  rows to the reject output,
- wraps each row body in a try/catch that records the row index, message, and
  full stack trace into the `__errors__` structure.

The reject script (`build_reject_script`) is symmetric but reduced: no
variables, no filters, no `is_reject` routing, no try/catch -- it only emits the
`inner_join_reject` output columns over the reject row source.

#### `groovy_escape_expression`

`groovy_escape_expression` (`map_compiled_script.py:322-373`) is a hand-written,
security-relevant scanner that escapes `$` **only inside double-quoted string
literals** so Groovy's GString interpolation does not fire on Talend literals
like `"Total: $100"`. It consumes `\\` and `\"` as two-character units so the
closing quote cannot be mis-detected. Single-quoted strings are treated as
outside-string regions. (Note: `src/v1/engine/components/transform/java_component.py`
has a stale comment claiming this function handles backslashes/quotes/newlines;
it only handles `$`.)

### 2.9 Reject routing (`map_reject_routing.py`)

tMap has three reject flavours, each handled differently by `route_rejects`:

| Reject type | Populated by | Routing |
| --- | --- | --- |
| `is_reject` | the active script inline (`matchedAny == false`) | pass through from `active_results` |
| `inner_join_reject` | the **separate** reject-pass script over the join-phase reject rows | pass through from `reject_results` |
| `catch_output_reject` | `__errors__` row indices into `joined_df` | `_route_catch_output` selects failing rows, evaluates user column exprs, overlays framework `errorMessage`/`errorStackTrace` |

For `catch_output_reject`, the D-06 reserved-column policy is "framework wins":
if the user declared `errorMessage` or `errorStackTrace` columns, the
framework's captured values overwrite them.

> **MVP limitation.** `_route_catch_output` (`map_reject_routing.py:120-134`)
> evaluates user column expressions in pure Python with only trivial reference
> resolution (a bare column, or a 2-segment `row.col`). Any expression
> containing `(` or otherwise complex defaults to `None`. A catch output whose
> columns use Talend Java functions therefore silently emits nulls instead of
> computed values -- a parity gap that fails quietly (no error, no log).

### 2.10 Bridge state sync (`map_bridge_sync.py`)

`push_runtime_state_to_bridge` is the **only** place in the package that writes
`bridge.context` / `bridge.global_map` directly (rather than via setters), to
preserve Python value types end-to-end. It must be called immediately before any
bridge invocation that runs per-row Groovy.

It centralizes one subtle Py4J pitfall: Py4J's native protocol always sends a
Python `float` as a Java `Double`. For `id_Float`-typed context variables the
value is wrapped explicitly via `gateway.jvm.java.lang.Float(value)` so a Talend
`Float`-typed context variable keeps Java `Float` identity end-to-end
(`map_bridge_sync.py:41-46`). This is the single chokepoint for that bug.

### 2.11 tMap parity edge cases (summary)

- **Null join keys never match** (`HashMap.get(null)`), enforced by
  `_prefilter_null_keys` and the `CONSTANT_KEY` `has_null` short-circuit.
- **Missing/empty lookups do not strip columns**; `INNER` rejects all main rows,
  `LEFT_OUTER` preserves them with null lookup columns.
- **Output filters are honoured on reject rows** in `build_reject_script`
  (Talend evaluates the output's own filter before commit).
- **Reserved error columns are framework-wins** (D-06).
- **`output_chunk_size`** is resolved in `_resolve_expressions` but never flows
  into the two `execute_compiled_tmap_chunked` calls (both hardcode
  `chunk_size=50000`), so the override is effectively dead for tMap today.

---

## 3. Java/Groovy bridge

### 3.1 Module map

| File | LOC | Responsibility |
| --- | --- | --- |
| `src/v1/java_bridge/bridge.py` | 1587 | Python client: JVM lifecycle, Arrow (de)serialization, chunking with Base64-overflow halving, context/globalMap sync, Py4J date converters, JVM stdout/stderr drainers. |
| `src/v1/java_bridge/type_mapping.py` | 172 | Bridge-layer type system: 7 Python type strings -> Arrow types / Java type names; Arrow schema construction; Decimal precision/scale extraction. |
| `src/v1/engine/java_bridge_manager.py` | 167 | Per-job lifecycle wrapper: dynamic free-port allocation with TOCTOU retry, routine loading, library validation, context-manager protocol. |
| `java/.../JavaBridge.java` | 984 | Py4J entry point: `executeJavaRow`, one-time/batch expressions, tMap compile/execute, routine loading; holds the shared context/globalMap maps + compiled-script class cache. |
| `java/.../RowWrapper.java` | 133 | Groovy row accessor (`input_row.col` reads, `output_row.col=val` writes) with read-after-write semantics. |
| `java/.../ArrowSerializer.java` | 297 | Arrow vector creation/value-setting helpers; type coercion; Decimal scale alignment. |
| `java/.../routines/` | 3633 | Vendored Talend Open Studio 8.0.1 standard routine library (TalendDate, StringHandling, Mathematical, ...). |
| `java/pom.xml` | 169 | Maven build: Arrow 15.0.2, Groovy 3.0.21, Py4J 0.10.9.9, Java 11; shade plugin -> `java-bridge-with-dependencies.jar`. |

### 3.2 The 7-type type system (`type_mapping.py`)

The bridge accepts **only** seven Python type strings. Anything else raises
`ValueError` before serialization. The converter layer is responsible for
resolving Talend raw types down to these strings; the bridge never sees a raw
Talend type.

| Python type string | Arrow type | Java type name |
| --- | --- | --- |
| `str` | `pa.string()` | `String` |
| `int` | `pa.int64()` | `Long` |
| `float` | `pa.float64()` | `Double` |
| `bool` | `pa.bool_()` | `Boolean` |
| `datetime` | `pa.timestamp("ns")` | `Date` |
| `Decimal` | `pa.decimal128(38, 18)` | `BigDecimal` |
| `object` | `pa.string()` | `String` |

**Decimal precision/scale uses the inverted Talend convention**
(`extract_precision_map`): in the converter schema, `length` holds total digits
(precision) and `precision` holds decimal places (scale) -- the opposite of SQL's
usual naming. `build_arrow_schema` applies per-column `(precision, scale)`
overrides on the *input* path, falling back to `(38, 18)`.

> **Known output-side gap.** The Java `ArrowSerializer.createVectorForType`
> hardcodes the output `DecimalVector` to `decimal128(38, 18)`
> (`ArrowSerializer.java:183`) and `HALF_UP`-rounds output decimals to scale 18
> (`setScale(vectorScale, HALF_UP)`). The per-output precision/scale is **not**
> propagated to the output vector (unlike the input path). A Talend
> `Decimal(20,2)` output therefore round-trips at scale 18, not 2.

### 3.3 JVM lifecycle and reliability

#### `JavaBridgeManager` (per-job owner)

`JavaBridgeManager` (`java_bridge_manager.py`) owns one JVM per job. `start()`:
- allocates a free port by binding an ephemeral socket (`_find_free_port`),
- retries up to 3 times specifically on `"Address already in use"` to mitigate
  the TOCTOU race between releasing the probe socket and the JVM binding it,
  cleaning up a half-started bridge between attempts,
- syncs the Python log level to the JVM,
- validates required libraries (fails if any are missing),
- loads configured routines (fails on any load error).

`stop()` is idempotent. The class implements the context-manager protocol
(`__enter__`/`__exit__`) so JVM teardown is guaranteed even on failure.

#### `JavaBridge.start` (`bridge.py:176-329`)

- launches `java ... com.citi.gru.etl.JavaBridge` as a `subprocess.Popen` with
  the bridge JAR plus any routine JARs on the classpath,
- starts two daemon threads to drain JVM stdout/stderr into the Python logger
  (prevents pipe-buffer deadlock on verbose jobs),
- connects via Py4J with retry + exponential backoff (5 attempts starting at
  0.5s); a JVM that exits during startup surfaces its stderr in the error,
- registers two process-global Py4J input converters **once per Python
  process**: `DatetimeConverter` (registered first so the subclass match wins
  for `datetime.datetime`) and `DateConverter` (for `datetime.date`). Aware
  datetimes use UTC (`calendar.timegm`); naive datetimes use the host local
  timezone (`time.mktime`).

The JVM caps its Arrow `RootAllocator` at ~4 GB (`MAX_ALLOCATOR_BYTES`).

### 3.4 Arrow serialization (`_df_to_arrow_bytes`)

`_df_to_arrow_bytes` (`bridge.py:963+`) is schema-driven: Arrow types are always
built from explicit declared type strings, never inferred from data:

1. `_reconcile_schema_to_df` -- undeclared columns raise `ConfigurationError`;
   schema columns absent from the frame are pruned (strict).
2. `validate_schema_types` -- the 7-type guard.
3. `build_arrow_schema` -- applies per-column Decimal precision/scale.
4. Per-column coercion to the declared Arrow type (`str`/`object` -> str with
   null preservation; `int`/`float` -> `to_numeric`; `datetime` ->
   `to_datetime`; `Decimal` cells normalized to `decimal.Decimal`-or-`None`, with
   empty string `""` -> null so pyarrow can write a proper decimal null).
5. A single-batch Arrow IPC stream (`combine_chunks()` forces one batch).

On the Java side `ArrowStreamReader.loadNextBatch()` reads exactly one batch and
`extractTypedValue` converts each cell to a standard Java type
(`VarChar`->`String`, `BigInt`->`long`, `TimeStampNano`->`java.util.Date` at ms
resolution, `Decimal`->`BigDecimal`). On deserialization back to pandas,
decimal nulls are mapped to `""` so callers never see pandas `<NA>`.

### 3.5 Execution entry points

| Python method | Java method | Use |
| --- | --- | --- |
| `execute_java_row(df, java_code, output_schema, ...)` | `executeJavaRow` | tJavaRow per-row execution. |
| `execute_one_time_expression(expr)` | `executeOneTimeExpression` | single one-shot expression. |
| `execute_batch_one_time_expressions(dict)` | `executeBatchOneTimeExpressionsWithGlobalMap` | many one-shot expressions (used by tMap `CONSTANT_KEY`). |
| `execute_tmap_preprocessing(df, expressions, ...)` | `executeTMapPreprocessing` | batch-eval per-row expressions over a frame, returns `{expr_id: np.array}` (used by tMap join key/filter eval). |
| `compile_tmap_script(component_id, ...)` | `compileTMapScript` | parse + cache a tMap Script class. |
| `execute_compiled_tmap_chunked(component_id, df, ...)` | `executeCompiledTMap` | run a cached tMap script with chunking. |

### 3.6 Compile-once / execute-many (BRDG-06)

The JVM caches the compiled **Script class** (not an instance) keyed by
`component_id`, in a `ConcurrentHashMap` (`compiledScriptClasses`). Each
chunk/row gets a *fresh* Binding and a fresh Script instance via reflection. The
rationale (`JavaBridge.java`, `compileTMapScript`/`executeCompiledTMap`):

- no `synchronized(script)` bottleneck,
- no cross-row variable bleed (each row's Binding is isolated),
- compile cost (Groovy parse) is paid once per component, amortized across all
  rows.

`CachedTMapMeta` pairs the compiled class with its output schemas/types, main
table name, and lookup names.

Note: one-time and batch expressions do **not** share this cache -- each
`executeOneTimeExpression` / `executeBatchOneTimeExpressions` constructs a new
`GroovyShell` and recompiles, which is a repeated cost for expression-heavy jobs.

### 3.7 Chunking and Base64-overflow recovery

Py4J Base64-encodes `byte[]` arguments and stores the encoded length as a
*signed* 32-bit Java int. The raw Arrow payload is capped at
`_PY4J_BYTE_ARG_SAFE_LIMIT = ~1.5 GB` so that after Base64 expansion (~2.0 GB)
it stays below the 2 GB int limit and avoids
`java.lang.NegativeArraySizeException`.

`_execute_compiled_tmap_chunked_body` (`bridge.py:699-821`) handles this with a
FIFO `pending_ranges` deque and **bidirectional halve-and-retry**:

1. Build initial `(start, end)` ranges of `chunk_size` rows each.
2. **Pre-flight**: if a chunk's serialized Arrow payload exceeds the safe limit
   (and is more than 1 row), split the range in half and front-insert both
   halves (preserving row order); continue.
3. **Runtime**: if the Java call raises a `NegativeArraySizeException` /
   `py4j.Base64` error, halve and retry the same way.
4. A single row that still overflows re-raises the original error (unrecoverable).

Each output's chunk frames accumulate and are `pd.concat`-ed at the end. Output
decimal nulls are remapped to `""` per chunk.

### 3.8 Context / globalMap bidirectional sync

Every data execution method is wrapped by `_call_java_with_sync`
(`bridge.py:909-940`), which **always** runs `_sync_from_java()` in a `finally`
block -- even when the Java call raises -- so the Python mirrors of
`context`/`global_map` are refreshed after every call. Sync failures are logged
but never mask the original error or result.

- **Outbound (Python -> Java)**: each call passes `self.context` and a
  numeric-coerced copy of `self.global_map`. `_coerce_global_map_for_java`
  promotes numeric strings to `int`/`float` so Groovy casts like
  `(Integer) globalMap.get("k")` match Talend behaviour (config-loaded values
  like a tSetGlobalVar `"5000"` arrive as strings).
- **Inbound (Java -> Python)**: `_sync_from_java` reads `getContext()` /
  `getGlobalMap()` and `dict.update`s the Python mirrors.

#### The reject_mode scoped wrap

`execute_compiled_tmap_chunked(reject_mode=...)` pushes a `__rejectMode__` flag
into `context` before the call and restores the exact prior state afterward
(using the `_MISSING` sentinel to distinguish "key absent" from "key set to
None"), so the flag never leaks into unrelated bridge consumers.

### 3.9 Bridge parity gaps and reliability risks

These are the items most worth a test or a fix when extending the bridge:

- **Shared mutable state is not thread-safe.** `context`, `globalMap`, and
  `loadedRoutines` are plain `java.util.HashMap` mutated via `putAll`/`put` in
  every `execute_*` method. Only `compiledScriptClasses` is a
  `ConcurrentHashMap`. Today the Python client is single-threaded per bridge so
  calls are serialized; any future concurrent/parallel-chunk dispatch would hit
  unsynchronized shared maps.
- **Keys can never be deleted end-to-end.** `putAll` (Java) and `dict.update`
  (Python) are both additive; nothing removes a stale key from either side, so a
  context/globalMap key, once set, is resurrected on the next sync. The only
  explicit pop is the Python-side `reject_mode` wrap.
- **Decimal output scale loss** -- output decimals serialize at `(38, 18)`
  regardless of declared output precision (section 3.2).
- **Datetime fidelity** is lossy below milliseconds (`TimeStampNano` divided by
  1e6 into a `java.util.Date`) and tz-fragile (naive datetimes use host local
  time while the JVM runs at UTC).
- **Stray import**: `from attr import field` at `bridge.py:22` is unused.

---

## 4. Extension & testing guide

### 4.1 Where the unit-test seams are

The tMap join/script modules are **pure functions** with injected bridge-eval
closures, so they unit-test cleanly without a live JVM:

| Module | Test file | Highest-value assertions |
| --- | --- | --- |
| `map_config.py` | `tests/v1/engine/components/transform/map/test_map_config.py` | parse round-trip, validation raises |
| `map_joins.py` | `.../map/test_map_joins.py` | strategy classification; each `join_*` path; matching-mode dedup; null-key prefilter; empty-lookup dtype fill |
| `map_compiled_script.py` | `.../map/test_map_compiled_script.py`, `test_map_compiled_script_chunking.py` | closure chunking, hard-cap raise, GString `$`-escaping (`test_map_groovy_safety.py`) |
| `map_bridge_sync.py` | `.../map/test_map_bridge_sync.py` | `id_Float` wrapping |
| `map_reject_routing.py` | `.../map/test_map_reject_routing.py` | the 3 reject types |
| `map_component.py` | `.../map/test_map_component.py`, `test_type_fidelity.py` | orchestration; dtype/Arrow parity |

Integration / e2e (need a built JAR + live JVM):
`test_map_integration.py`, `test_map_bridge.py`, `test_map_05_3_e2e.py`,
`test_map_05_4_e2e.py`, the `test_map_reject_*` suite, and
`test_map_method_too_large_integration.py` (the 64KB chunking path).

Bridge Python tests live under `tests/v1/java_bridge/`
(`test_bridge_type_converters.py`, `test_bridge_strict_schema.py`,
`test_bridge_type_fidelity.py`, `test_stderr_drainer.py`) with a session-scoped
real-JVM fixture in `tests/v1/java_bridge/conftest.py` that **skips when the JAR
is unbuilt**. Project memory mandates a *real* JVM for bridge tests, not mocks;
any change touching `{{java}}` resolution should add `@pytest.mark.java`
live-bridge tests.

### 4.2 Coverage blind spots to close

- **tMap null-key `LEFT_OUTER` dtype gap** (section 2.7) for object/Decimal
  lookup columns specifically -- under-covered.
- **`catch_output_reject` complex-expression** path (section 2.9) -- the
  None-default for Java-function columns appears untested.
- **`RELOAD` performance / no size guard** -- behaviour on large reload lookups.
- **Bridge non-(38,18) Decimal output round-trip scale** -- no test asserts it.
- **Bridge naive-vs-aware datetime wall-clock round-trip** -- no parity test.
- **Concurrent bridge calls** -- no test exercises the shared HashMap risk.

### 4.3 Mental model for changes

- To change **join behaviour**, edit `map_joins.py`; the orchestrator and script
  generator should not need to change. Keep the `(merged_frame, rejects)`
  contract.
- To change **what Groovy is emitted**, edit `map_compiled_script.py` only; it is
  pure and must never call the bridge. Respect the 8KB chunk target / 50KB hard
  cap.
- To change **type serialization**, edit `type_mapping.py` (Python/Arrow side)
  and `ArrowSerializer.java` (JVM side) together -- they are two halves of one
  contract and a change to one without the other breaks round-trips.
- Any new bridge data method should be wrapped by `_call_java_with_sync` so
  context/globalMap stay consistent.
