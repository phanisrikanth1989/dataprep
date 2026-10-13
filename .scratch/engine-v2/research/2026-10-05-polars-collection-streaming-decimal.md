# Polars facts: collection, streaming, sinks, row counts, Decimal, errors, order (ticket 03)

Researched: 2026-10-05. Facts are stamped against the range this repo pins,
`polars>=1.38,<2.0` (`pyproject.toml`), read at its two ends: tag `py-1.38.0`
(released 2026-02-04) and tag `py-1.44.2` (released 2026-09-09; the installed
version and the latest 1.x). `py-2.0.0-rc.1` and `py-2.0.0-rc.2` exist as
pre-releases and are outside the pin. Sources: the Polars source and
docstrings at those two tags (the Python API reference at
docs.pola.rs/api/python/stable is generated from the docstrings), the user
guide sources at both tags (rendered at docs.pola.rs/user-guide), the official
GitHub release notes for every release from py-1.33.0 to py-2.0.0-rc.2,
statements by Polars members and collaborators in the pola-rs/polars tracker,
and Python's own `decimal` documentation. No blogs, no Stack Overflow, no AI
summaries.

Where the two ends of the pin differ, the first release carrying the change was
found by reading the same file at every release tag from py-1.38.0 to
py-1.44.2 ("tag scan" below).

Version stamps:
- `[1.38-1.44]` = read in the source or docs at both py-1.38.0 and py-1.44.2.
  Releases in between were not read one by one unless a change version is given.
- `[>=1.41.0]` and the like = first release that has it, from a tag scan or the
  release notes. `[1.44.2]` = checked at the top of the pin only.

Observations: lines marked **Observed** were observed on polars 1.44.2, the
installed version, with short scripts (Python 3.14.6, macOS 26.6 arm64, Apple
M4, 10 cores, 16 GB). An observation confirms or sharpens a source; where an
**Observed** line cites nothing else, the observation is the only evidence. All
observations are provisional for the RHEL target servers and for other
versions in the pin. The scripts lived in the system temp directory and are not
committed.

Shorthand for citations:
- `PATH@44#L10-L20` = https://github.com/pola-rs/polars/blob/py-1.44.2/PATH#L10-L20;
  `@38` = the same at tag py-1.38.0.
- File aliases: `LF` = py-polars/src/polars/lazyframe/frame.py;
  `DF` = py-polars/src/polars/dataframe/frame.py;
  `FN` = py-polars/src/polars/functions/lazy.py;
  `EAGER` = py-polars/src/polars/functions/eager.py;
  `EXPR` = py-polars/src/polars/expr/expr.py;
  `ENGINE` = py-polars/src/polars/lazyframe/engine.py;
  `LAZY` = crates/polars-lazy/src/frame/mod.rs;
  `MEMPLAN` = crates/polars-mem-engine/src/planner/lp.rs;
  `CACHE` = crates/polars-plan/src/plans/optimizer/cse/cache_states.rs;
  `LOWER` = crates/polars-stream/src/physical_plan/lower_ir.rs;
  `LOWERGB` = crates/polars-stream/src/physical_plan/lower_group_by.rs;
  `GRAPH` = crates/polars-stream/src/physical_plan/to_graph.rs;
  `PHYS` = crates/polars-stream/src/physical_plan/mod.rs;
  `DEC` = crates/polars-compute/src/decimal.rs;
  `DECOPS` = crates/polars-core/src/chunked_array/arithmetic/decimal.rs;
  `DECSER` = crates/polars-core/src/series/implementations/decimal.rs;
  `SCHEMA` = crates/polars-plan/src/plans/aexpr/schema.rs.
- `guide/PAGE Ln` = docs/source/user-guide/PAGE.md, rendered at
  https://docs.pola.rs/user-guide/PAGE/. The pages cited (lazy/execution,
  lazy/multiplexing, lazy/sources_sinks, lazy/optimizations, lazy/schemas,
  concepts/streaming) are byte-identical at py-1.38.0 and py-1.44.2 (diffed).
- `rel/TAG` = https://github.com/pola-rs/polars/releases/tag/TAG;
  `#N` = https://github.com/pola-rs/polars/issues/N (pull requests redirect).
- `pydecimal` = https://docs.python.org/3/library/decimal.html (Python 3.14).

Behaviour that changed inside the pin, in one place (details in the sections):

| First release | Change | Evidence |
|---|---|---|
| 1.39.0 (2026-03-12) | `Expr.truncate()` added; `product()` supports Decimal | tag scan of `EXPR`; rel/py-1.39.0 "Add Decimal support for product reduction (#26725)" |
| 1.40.0 (2026-04-18) | Plan-time dtype of `sum` over `Decimal(p, s)` becomes `Decimal(38, s)` | rel/py-1.40.0 "Widen decimal precision on sum aggregation (#27270)"; tag scan of `SCHEMA` |
| 1.41.0 (2026-05-22) | Streaming engine stabilized; runtime dtype of Decimal `sum` becomes `Decimal(38, s)`; `LazyFrame.execute()` added (unstable) | rel/py-1.41.0 "Stabilize streaming engine (#27497)", "Widen decimal precision on sum aggregation at runtime (#27579)"; tag scans of `LF`, `DECSER` |
| 1.42.0 (2026-06-24) | Spill to disk behind `POLARS_OOC_MEMORY_BUDGET_MB` | rel/py-1.42.0 "Add naive out-of-core spilling to Polars (#27998)" |
| 1.43.0 (2026-07-21) | `LazyFrame.profile()` deprecated; a shared sub-plan is kept when a branch filter cannot be pushed into it | `LF@44#L2035-L2039`; tag scan of `CACHE` (1.4) |
| 1.44.0 (2026-08-24) | Decimal `sum` raises on overflow; `sinked_paths_callback` public on `sink_parquet` and `sink_ipc`; per-method engine badges in the API reference; `group_by` docstring reworded | rel/py-1.44.0 "#28688", "#28814"; tag scans of `DECSER`, `LF` |

---

## Summary: the facts most likely to change a design decision

- Two `.collect()` calls on frames that share an upstream each re-run the whole upstream; `.cache()` does not carry across collects; only an already collected `df.lazy()` is not re-run (1.1, 1.2).
- `pl.collect_all` runs its frames as one plan, but sharing is the optimizer's choice: on 1.44.2 main + reject as `filter(c)` / `filter(~c)` on a shared scan read the source twice, and a computed flag column kept it to one read (1.4).
- With lazy file sinks, `pl.collect_all` shares the upstream only when called with `engine="streaming"`; its default engine ran the source once per sink (1.5, 3.3).
- `collect()` defaults to the in-memory engine across the pin and sinks default to streaming; streaming was "unstable" until 1.41.0 and becomes the default in 2.0, which is outside the pin (2.1, 2.2).
- Under streaming a full sort always materializes its input; group_by with median or `map_groups`, `unique(keep="last", maintain_order=True)` and joins with `validate=` fall back to in-memory per node (2.3, 2.4).
- No out-of-core for sort, group-by or join: spill to disk exists from 1.42.0 only behind an undocumented env var its author calls "highly unstable" (2.4).
- `write_csv` and `write_parquet` are thin wrappers over `sink_csv` and `sink_parquet` at both ends of the pin: same format options, and byte-identical CSV output observed (3.2).
- Sinks return `None`. `sink_csv` has no rows-written hook; `sink_parquet` and `sink_ipc` gained an unstable one in 1.44.0 (4.1).
- Counting in the sink's own pass works as `collect_all([sink(lazy=True), lf.select(pl.len())], engine="streaming")`, with no measurable extra cost observed; `lazy=True` is unstable (4.2, 4.3).
- A sink that fails part-way leaves a partial file at the target path (observed only); no atomicity guarantee was found (6.4).
- `pl.Decimal` is stable since 1.35.0: 128-bit, precision 1 to 38, fixed scale. `+ - * /` return `Decimal(38, max(scale))`; `*` and `/` round half-to-even to that scale, so `1.25 * 1.25 = 1.56` and `1 / 3 = 0.33` (5.3).
- Decimal `sum` changed inside the pin: dtype `Decimal(p, s)` at 1.38-1.39, `Decimal(38, s)` from 1.40/1.41, and overflow wrapped silently before 1.44.0; `mean` returns Float64; Decimal with a float gives Float64 (5.3, 5.4).
- Data errors (strict cast, CSV parse) surface only when the collect or sink runs; the exception is a message that names the column but not the file, row or component, and whether a strict cast raises depends on predicate pushdown (6.1 to 6.3).
- Row order: `group_by` and `unique` need `maintain_order=True`; a join without `maintain_order` kept left order on the in-memory engine but not on streaming; `pl.union` interleaves on streaming, `pl.concat` does not (7).
- The docs and 1.44.2 disagree in places: `sink_csv(engine="in-memory")` still runs on streaming, `round(mode="to_zero")` is rejected, `unique(maintain_order=True)` does stream, and the guide's schema-check example fails late (2.4, 3.1, 5.5, 6.1).

---

## 1. Collecting several outputs of one plan

### 1.1 A LazyFrame is a plan; every collect runs it again

- `[1.38-1.44]` guide/lazy/execution L42-L44: "Remember that `LazyFrame`s are
  query plans i.e. a promise on computation and is not guaranteed to cache
  common subplans. This means that every time you reuse it in separate
  downstream queries after it is defined, it is computed all over again."
- `[1.38-1.44]` guide/lazy/multiplexing L43-L52: a variable holding a LazyFrame
  "doesn't contain the materialized result ... it instead holds the query
  plan", so "every time we branch of this `LazyFrame` and call `collect` we
  re-evaluate" it.
- A frame made by `df.lazy()` from an already collected DataFrame holds that
  DataFrame as its source (`LOWER@44#L248-L258`: `IR::DataFrameScan` becomes an
  `InMemorySource { df }`), so collecting branches of it re-reads nothing.

**Observed** (1.44.2; the shared upstream is a `scan_csv` followed by a counting
Python `map_batches`, which also blocks predicate pushdown, see 1.4):

| What was run | Upstream ran, in-memory | Upstream ran, streaming |
|---|---|---|
| Two separate `.collect()` on two branches of one LazyFrame | 2 times | 2 times |
| `pl.collect_all([b1, b2])` | once | once |
| Two separate `.collect()`, with `.cache()` on the shared part | 2 times | 2 times |
| `pl.collect_all([b1, b2])` with `comm_subplan_elim=False` | 2 times | 2 times |
| One `.collect()` of `pl.concat([b1, b2])` | once | not run |
| Two `.collect()` on branches of `df.lazy()` (collected earlier) | 0 times | not run |

This is what `src/v2/engine.py` does today for a component with two outputs:
one `.collect()` per output, hence one full upstream run per output.

### 1.2 `LazyFrame.cache()` and cache nodes

- `[1.38-1.44]` Docstring, in full: "Cache the result once the execution of the
  physical plan hits this node. It is not recommended using this as the
  optimizer likely can do a better job." (`LF@44#L4469-L4476`,
  `LF@38#L4278-L4282`).
- `[1.44.2]` In-memory engine: a cached result lives in the per-query execution
  state, "kept in memory for the duration of the plan", and is dropped after its
  last reader (crates/polars-expr/src/state/execution_state.rs`@44#L108-L119`,
  `#L246-L280`). Every query builds a fresh state (`LAZY@44#L604`, `#L2454`).
  So a cache node is a whole materialized DataFrame, shared inside one collect
  and never across collects (confirmed by the third row of the table above).
- `[1.38-1.44]` Streaming engine: a cache node is lowered once and its consumers
  share the stream (`LOWER@44#L983-L992`, `LOWER@38#L964`); a stream with more
  than one consumer gets a multiplexer node (`PHYS@44#L814-L839`).
- An explicit `.cache()` can be removed by the optimizer; see 1.4.

### 1.3 `pl.collect_all`

- `[1.38-1.44]` Docstring: "Collect multiple LazyFrames at the same time. This
  can run all the computation graphs in parallel or combined. Common Subplan
  Elimination is applied on the combined plan, meaning that diverging queries
  will run only once." Returns "The collected DataFrames, returned in the same
  order as the input LazyFrames." (`FN@44#L2089-L2094`, `#L2189-L2192`;
  `FN@38#L2074-L2077`, `#L2162`).
- `[1.38-1.44]` guide/lazy/execution L76-L90: "It is very common that a query
  diverges at one point. In these cases it is recommended to use `collect_all`
  as they will ensure that diverging queries execute only once."
- `[1.38-1.44]` guide/lazy/multiplexing L68-L86: the combined queries "are
  shared under a single "SINK_MULTIPLE" evaluation and ... the optimizer has
  recognized that parts of the query come from the same subplan, indicated by
  the inserted "CACHE" nodes."
- `[1.38-1.44]` Implementation: the frames become one plan with a
  `SinkMultiple` root that is optimized once (`LAZY@44#L707-L723`,
  `LAZY@38#L706-L747`). **Observed**: `pl.explain_all([...])` (marked unstable,
  `FN@44#L2313-L2341`) prints `SINK_MULTIPLE` with one `CACHE[id: ...]` under
  both plans.
- `[1.38-1.44]` Default engine is in-memory: `"auto"` resolves to in-memory for
  `collect_all` (`LAZY@44#L636-L642`; `LAZY@38#L715-L718`, comment "Default
  engine for collect_all is InMemory"). There each shared sub-plan is executed
  once into a DataFrame before the plans run (crates/polars-mem-engine/src/
  executors/cache.rs`@44#L37-L43`, `#L60-L157`; `LAZY@38#L776-L785`).
- `[1.38-1.44]` The optimization behind it, as the guide lists it: "Common
  subplan elimination: Cache subtrees/file scans that are used by multiple
  subtrees in the query plan." It runs "1 time" (guide/lazy/optimizations L14).
  It is switched by the flag `comm_subplan_elim`: "Elide duplicate plans and
  caches their outputs." (py-polars/src/polars/lazyframe/
  opt_flags.py`@44#L220-L223`; the `QueryOptFlags` class is marked unstable,
  `#L25-L32`).
- `[1.38-1.44]` `collect_all(lazy=True)` (unstable) returns a LazyFrame instead
  of running: "This is only correct if all inputs sink to disk."
  (`FN@44#L2181-L2187`, `FN@38#L2151-L2153`).

### 1.4 Sharing is the optimizer's choice: branch filters can undo it

- `[1.38-1.44]` Source comment listing the cases after cache nodes are inserted
  and pushdown has run: "NO FILTERS: run predicate pd from the cache nodes";
  "There is a cache without predicates above the cache node -> run predicate
  form the cache nodes"; "The predicates above the cache nodes are all
  different -> remove the cache nodes" (`CACHE@44#L125-L128`,
  `CACHE@38#L117-L120`).
- `[>=1.43.0]` Refinement (tag scan of `CACHE`): "If a predicate refers to a
  column computed within the cached subplan, it cannot be pushed and removing
  the caches would lose the subplan sharing ... We therefore only remove the
  caches if _every_ filter above them is actually pushed" (`CACHE@44#L307-L317`).
  Before 1.43.0 the source removes the caches whenever the branch filters all
  differ. Not run on those versions.
- This matches the guide's wording "not guaranteed to cache common subplans"
  (1.1) rather than "will ensure that diverging queries execute only once" (1.3).

**Observed** (1.44.2, no Python function in the plan; source reads counted from
the streaming metrics log; identical on the default engine and on
`engine="streaming"`). "Main + reject" means `shared.filter(c)` and
`shared.filter(~c)` passed to `pl.collect_all`:

| Shape of the shared plan and its branches | `CACHE` refs in `explain_all` | CSV source read |
|---|---|---|
| Main + reject on `scan_csv().with_columns(...)`, with or without a filter before it | 0 | 2 times |
| Main + reject, with `.cache()` at the end of the shared part | 0 | 2 times |
| Main + reject, with `QueryOptFlags(predicate_pushdown=False)` | 0 | 2 times |
| Main + reject, shared part ends in `sort` | 0 | 2 times |
| Main + reject, shared part is a left join | 0 | 2 times |
| Two different filters on one shared plan | 0 | 2 times |
| Main + reject, shared part ends in `with_row_index` | 2 | once |
| Main + reject, shared part is a `group_by` result | 2 | once |
| Main + reject, shared part ends in `unique(keep="first", maintain_order=True)` | 2 | once |
| `shared.with_columns(ok=c)`, then `filter(ok)` and `filter(~ok)` | 2 | once |
| One branch filtered, the other an unfiltered `group_by` | 2 | once |
| Same rows, two different column selections | 2 | once |

### 1.5 `collect_all` with lazy file sinks: the default engine does not share

- `[1.38-1.44]` The in-memory planner hands every plan rooted at a file sink to
  the streaming executor, one build per root (`MEMPLAN@44#L415-L417`,
  `MEMPLAN@38#L291-L292`; crates/polars-stream/src/dispatch.rs`@44#L11-L41`).
  Each build lowers its own copy of the shared sub-plan.
- **Observed** (1.44.2): `pl.collect_all([lf.sink_csv(a, lazy=True),
  lf.sink_parquet(b, lazy=True)])` with the default engine or
  `engine="in-memory"` executed the CSV source twice, with no multiplexer.
  With `engine="streaming"` it executed the source once, through one
  multiplexer into two sink nodes. Same result with and without a Python
  function upstream. Not run on 1.38; the planner structure is the same there.

### 1.6 Cost of two DataFrame outputs

Measured in 4.3: for two filtered halves of one 15M-row plan, `collect_all`
was faster than two collects and used more peak memory, because the shared
part is held in addition to both outputs.

---

## 2. The streaming engine

### 2.1 Status across the pin

- `[1.38.0 to 1.40.1]` `collect(engine="streaming")`, `explain`, `show_graph`
  and `collect_async` call `issue_unstable_warning("streaming mode is
  considered unstable.")` (`LF@38#L1391-L1392`, `#L1542-L1543`, `#L2418-L2419`,
  `#L2551-L2552`; four call sites up to 1.40.1 by tag scan). The warning is
  only shown when `warn_unstable` is active
  (docs/source/development/versioning.md`@44#L59-L61`).
- `[>=1.41.0]` rel/py-1.41.0: "Stabilize streaming engine (#27497)". #27497 is
  by ritchie46 (member), merged 2026-05-04: "Well overdue." From 1.41.0 only
  `collect_async` still warns (tag scan; `ENGINE@44#L452-L453`).
- `[>=1.41.0]` Docstring: streaming "processes queries in batches, reducing
  memory pressure and often outperforming the in-memory engine. This will soon
  become the default engine of Polars." (`LF@44#L2471-L2474`).
- `[2.0, outside the pin]` `LazyFrame.profile` is deprecated since 1.43.0: "It
  was made for the older in-memory engine, but from version 2.0, Polars uses a
  streaming engine by default." (`LF@44#L2035-L2039`). #28274, by dsprenkels
  (collaborator): "From Polars 2.0 and onward, the streaming engine is the
  default engine for Polars." rel/py-2.0.0-rc.2 (pre-release, 2026-09-20): "The
  in-memory engine is no longer the default in the docstrings (#29137)".
- Tracking issue #20947 "Tracking issue for the new streaming engine", by
  coastalwhite (collaborator), open, last edited 2026-09-23: "From 1.31.1,
  Polars has a new streaming engine. In time, it will become the default
  engine ... All queries that run on the in-memory engine should run on the
  streaming engine (please file a bug otherwise), but certain operations might
  not have a native streaming implementation yet (in which case they will
  transparently fall back to the in-memory engine)."
- Versioning policy `[1.44.2]`: "The outcome of a query has changed due to
  changes to the query engine" is listed as a breaking change; "Bug fixes are
  not considered a breaking change"; "Functionality marked as unstable may
  change at any point without it being considered a breaking change."
  (docs/source/development/versioning.md`@44#L35-L76`).

### 2.2 How it is selected

- `[1.38-1.44]` `collect(engine=...)`; the default `"auto"` runs the in-memory
  engine. 1.44.2: `"auto"` uses the engine set by `Config.set_engine_affinity`
  or `POLARS_ENGINE_AFFINITY`, "falling back to "in-memory" if unset (this
  default may change in a future release)"; "If the selected engine cannot run
  the query, Polars falls back to the in-memory engine." (`LF@44#L2460-L2480`;
  1.38.0 wording `LF@38#L2286-L2293`).
- `[1.38-1.44]` guide/lazy/execution L39-L40: "With the default `collect` method
  Polars processes all of your data as one batch. This means that all the data
  has to fit into your available memory at the point of peak memory usage in
  your query." L46-L50: for larger-than-memory data "simply pass the
  `engine="streaming"` argument to `collect`".
- `[1.44.2]` `pl.Config.set_engine_affinity(engine)`: "The default execution
  engine Polars will attempt to use when calling `.collect()`. However, the
  query is not guaranteed to execute with the specified engine."
  (py-polars/src/polars/config.py`@44#L1569-L1582`). **Observed**: with
  `POLARS_ENGINE_AFFINITY=streaming` a plain `collect()` ran one streaming
  graph.
- `[1.38-1.44]` The old `streaming=True` argument: "the `streaming` parameter
  was deprecated in 1.25.0; use `engine` instead."
  (py-polars/src/polars/_utils/deprecation.py`@44#L80-L95`).
- `[1.38-1.44]` Sinks default to streaming: `"auto"` falls "back to
  "streaming" if unset" (`LF@44#L3920-L3940`; 1.38.0: "the query is run using
  the polars streaming engine", `LF@38#L3703-L3710`; Rust comment "Default
  engine for collect is InMemory, sink_* is Streaming", `LAZY@38#L643`).
- `[1.38-1.44]` The in-memory engine is not free of the streaming engine: its
  planner sends file scans, "partitionable" group-bys and file sinks to the
  streaming executor and materializes what comes back (`MEMPLAN@44#L357-L372`,
  `#L660-L661`; `MEMPLAN@38#L236-L242`, `#L396`, `#L535-L536`). **Observed**
  (1.44.2): a default `collect()` of `scan_csv -> filter -> group_by.agg(sum)`
  logged streaming nodes `multi-scan[csv]` and `group-by`, each ending in an
  `in-memory-sink`.

### 2.3 Which operations fall back to in-memory

- `[1.38-1.44]` guide/concepts/streaming L17-L20: "Some operations are
  inherently non-streaming, or are not implemented in a streaming manner (yet).
  In the latter case, Polars will fall back to the in-memory engine for those
  operations. A user doesn't have to know about this".
- `[1.38-1.44]` Fallback is per node, not per query. `InMemoryMap`: "Generic
  fallback for (as-of-yet) unsupported streaming mappings. Fully sinks all data
  to an in-memory data frame and uses the in-memory engine to perform the map."
  `InMemoryJoin`: "Fully sinks all data to in-memory data frames and uses the
  in-memory engine to perform the join." (`PHYS@44#L252-L255`, `#L515-L518`).
- `[1.38-1.44]` How to see it: `show_graph(plan_stage="physical",
  engine="streaming")`; "The legend shows how memory intensive the operation
  can be." (guide/concepts/streaming L22-L23; `LF@44#L1553-L1556`).
  `raw_output=True` returns the graph as text.
- `[>=1.44.0]` The API reference carries an engine badge per method (474
  docstrings at 1.44.2, none at 1.38.0; in `LF` they first appear at 1.44.0 by
  tag scan). At 1.44.2: `sort` is "in-memory, partially-distributed"
  (`LF@44#L1648`); `group_by` is "in-memory, partially-streaming,
  partially-distributed" (`LF@44#L5215`);
  `join` is "in-memory, streaming, partially-distributed" (`LF@44#L6216`);
  `unique`, `filter`, `select`, `with_columns`, `with_row_index`, `cache`,
  `cast`, `explode`, `unpivot`, `map_batches` are "in-memory, streaming,
  distributed"; the sinks are "streaming, distributed". Expressions badged
  in-memory only include `over`, `rank`, `is_unique`, `is_duplicated`,
  `is_last_distinct`, `quantile`, `rolling_*`, `shuffle`, `sample`, `reverse`,
  `arg_sort`, `pct_change`; `cum_sum` and friends, `Expr.sort`, `Expr.sort_by`
  and `median` are "partially-streaming". The badge directive defines no
  meaning for "partially" (py-polars/docs/source/_ext/engine_support.py`@44`).
- Tracking issue #20947 (state on 2026-09-23). Aggregates done: sum, mean,
  min/max, first/last, var/std, count, n_unique, mode; open: implode,
  median/quantile, `str.join`. Plan translation open: `.over()`, `.replace()`,
  `is_last_distinct`, `is_unique`, `is_duplicated`, `rank`, `arg_sort`,
  `sample`, `pct_change`, `fill_null(strategy=min/max/mean)`, `search_sorted`.

**Observed** (1.44.2): nodes in the streaming physical plan, read from
`show_graph(plan_stage="physical", engine="streaming", raw_output=True)`:

| Query on a `scan_csv` | Nodes |
|---|---|
| filter, select | `multi-scan[csv]` only (both pushed into the scan) |
| `sort` (with or without `maintain_order`) | `sort` |
| `sort(...).head(5)` | `bottom-k`, then `sort` |
| `group_by.agg(sum)`; `n_unique`, `first`, `last`, `len` | `group-by` |
| `group_by(maintain_order=True).agg(sum)` | `with-row-index`, `group-by`, `sort` |
| `group_by.agg(median)`; `agg(col.sort_by(...).first())`; `map_groups` | `in-memory-map` |
| inner, left, full join | `equi-join` |
| cross join; anti join | `cross-join`; `anti-join` |
| `unique()` | `group-by` |
| `unique(keep="first", maintain_order=True)` | `is-first-distinct`, `filter` |
| `unique(keep="last", maintain_order=True)` | `in-memory-map` |
| `pl.concat`; `pl.union` | `ordered-union`; `unordered-union` |
| `LazyFrame.map_batches(python_function)` | `in-memory-map` |
| `with_columns(sum().over(key))` | `group-by` and `equi-join` |

### 2.4 Sort, join, group-by and unique under streaming

- **Sort** `[1.38-1.44]`: the streaming sort node runs the in-memory engine's
  sort over its fully collected input (`GRAPH@44#L601-L636`,
  `GRAPH@38#L542-L577`; `LOWER@44#L508-L510`: the non-limiting case "dispatches
  to in-memory"). With a limit (`sort(...).head(n)`) a streaming top-k node
  runs first (`LOWER@44#L553-L576`). Docstring: with `maintain_order=True`
  "streaming is not possible and performance might be worse since this requires
  a stable search" (`LF@44#L1663-L1666`).
- **Group-by** `[1.38-1.44]`: a streaming hash group-by is used unless the
  query has `map_groups`, a dynamic or rolling group-by, or an aggregate that
  cannot be lowered; those go to `in-memory-map` (`LOWERGB@44#L719-L754`,
  `#L1197-L1320`, `#L40-L74`; `LOWERGB@38#L424-L431`). 1.44.2 streams dynamic
  and rolling group-bys that have no keys (`LOWERGB@44#L1211-L1259`).
  `maintain_order=True` is done in streaming by tagging rows with an index and
  sorting the groups afterwards (`LOWERGB@44#L756-L768`, `#L948-L963`;
  `LOWERGB@38#L448-L453`, `#L668-L670`). When the keys are known to be sorted a
  sorted group-by node is used (`LOWERGB@44#L1261-L1277`).
- Docstring drift for `group_by(maintain_order=...)`: 1.38.0 to 1.43.2 say
  "Setting this to `True` blocks the possibility to run on the streaming
  engine" (`LF@38#L5014-L5018`); from 1.44.0 it reads "blocks the possibility
  to run partitioned" (`LF@44#L5222-L5226`). The 1.38.0 source already streams
  it, as cited above.
- **Join** `[1.44.2]`: streaming nodes exist for equi joins (observed for
  inner, left and full), semi/anti, cross, as-of and range joins. A join falls
  back to `InMemoryJoin` when `validate=` needs checks or the match condition
  is not a pure equality outside a range join (`LOWER@44#L1193-L1204`,
  `#L1389-L1396`). `[1.38.0]`: only equi, semi/anti and cross joins stream;
  as-of and range joins fall back (`LOWER@38#L1058`, `#L1225`, `#L1240`).
  `[1.38-1.44]` A merge-join node is used instead when the planner knows both
  inputs are sorted on the key (`LOWER@44#L1151-L1154`, `#L1268-L1289`;
  `LOWER@38#L1095`). `[1.44.2]` The `build_side` argument: that side "will be
  likely be held in memory as a hash table" (`LF@44#L6313-L6337`, marked
  experimental; not in the 1.38.0 signature).
- **Unique** `[1.38-1.44]`: "We don't have a dedicated distinct operator (yet),
  lower to group by with an aggregate for each column."
  `unique(keep="last", maintain_order=True)` falls back: "the order-preserving
  groupby always orders by the first occurrence of the group so we can't lower
  this and have to fallback." (`LOWER@44#L1421-L1422`, `#L1515-L1517`;
  `LOWER@38#L1256`, `#L1264-L1266`). `[1.44.2]` also has a sorted-unique node
  for sorted keys and an `is_first_distinct` + filter path for
  `maintain_order=True` with `keep` "first" or "any" (`LOWER@44#L1451-L1513`).
- Docs versus source for `unique`: the docstring still says
  `maintain_order=True` "blocks the possibility to run on the streaming engine"
  (`LF@44#L8209-L8212`, `LF@38#L7776-L7779`), while the source and the observed
  plan run it on streaming nodes for every `keep` except "last".
- **Out-of-core**. Tracking issue #20947, section "Out-of-core": done
  "Multiplexers (#26774)"; open "Group-by", "Equi-join", "Sort". rel/py-1.42.0:
  "Add naive out-of-core spilling to Polars (#27998)"; that PR, by orlp
  (member): "this is all very early work and still highly unstable, likely with
  bugs and performance issues. To enable it, specify
  `POLARS_OOC_MEMORY_BUDGET_MB` ... not everything *can* be spilled to disk, so
  Polars can still go over this amount". `[1.44.2]` the budget defaults to
  unlimited (crates/polars-config/src/lib.rs`@44#L78-L79`), and the variable
  appears nowhere in the Python package or the user guide. `[1.38.0]` the
  crate that holds the spill code (`crates/polars-ooc`) does not exist.

### 2.5 Claims in `docs/v2/MEMORY_MANAGEMENT.md`, checked against the above

| Claim in that document | Status |
|---|---|
| "No data is loaded into memory until something forces materialization (a `.collect()` call)" | Agrees with the guide: a scan "will delay execution until the query is collected" (guide/lazy/sources_sinks L5-L9) |
| A barrier's DataFrame is re-wrapped with `.lazy()` so downstream stays lazy | Agrees with 1.1: branches of `df.lazy()` re-ran nothing |
| "Component produces multiple outputs: Engine must collect once and split" | Not what happens: `engine.py` collects once per output, and each collect re-runs the upstream (1.1) |
| Scenario A at 100M rows "Survived because Polars streaming optimizes internally"; "Polars can execute plans in streaming mode ... This is why scenario A ... survives" | Not supported as written. A default `collect()` is the in-memory engine and "all the data has to fit into your available memory" (2.2). `engine.py` passes `engine="streaming"` only when the job sets `streaming`. Scans and some group-bys do run through the streaming executor inside the in-memory engine, but their results are materialized in full (2.2) |
| "streaming has limitations -- not all operations support it, and complex joins may still require full materialization" | Agrees with 2.3 and 2.4 |
| "Each barrier creates an optimization boundary" | Agrees: a collected frame re-enters the plan as an in-memory source (1.1) |
| "more barriers can mean less peak memory", with the benchmark tables | Not established by any Polars source and not re-measured here |

---

## 3. Sinks

### 3.1 Streaming behaviour

- `[1.38-1.44]` Docstring of `sink_csv`: "Evaluate the query in streaming mode
  and write to a CSV file. This allows streaming results that are larger than
  RAM to be written to disk." `sink_parquet` says the same with "a Parquet
  file" (`LF@44#L3776-L3779`, `#L2838-L2841`; `LF@38#L3562-L3564`).
- `[1.38-1.44]` guide/lazy/sources_sinks L11-L15: "Sinks can execute a query and
  stream the results to storage ... you don't necessarily have to store all data
  in RAM, but can process data in batches."
- `[1.38-1.44]` Default engine for a sink is streaming (2.2). The docstring
  describes `engine="in-memory"` as "use the in-memory engine before writing"
  (`LF@44#L3929-L3930`), but the in-memory planner passes the whole plan under
  a file sink to the streaming executor (`MEMPLAN@44#L415-L417`,
  `MEMPLAN@38#L291-L292`). **Observed** (1.44.2): `sink_csv(path,
  engine="in-memory")` ran the same streaming nodes (`multi-scan[csv]`,
  `group-by`, `io-sink`) as the default.
- `[1.38-1.44]` `maintain_order=True` by default: "Maintain the order in which
  data is processed. Setting this to `False` will be slightly faster." The
  parameter is marked unstable (`LF@44#L3864-L3870`, `LF@38#L3647-L3653`).
- `[1.38-1.44]` `batch_size=1024` for CSV: "Number of rows that will be
  processed per thread." (`LF@44#L3820-L3821`).
- `[1.38-1.44]` A sink returns `None` (signature `-> LazyFrame | None`,
  `LF@44#L3743-L3775`). The docstring's "Returns: DataFrame" (`#L3950-L3952`)
  is wrong. **Observed**: `None`.
- `[1.38-1.44]` Target: `str | Path | IO[bytes] | IO[str] | PartitionBy`
  (`LF@44#L3745`). **Observed**: `sink_csv(open(p, "ab"),
  include_header=False)` appended to an existing file.
- `[1.38-1.44]` `mkdir=False` by default (unstable). **Observed**: a missing
  parent directory raises `FileNotFoundError`; `mkdir=True` creates it.
- `[1.38-1.44]` `sync_on_close` (unstable): `None` does not sync, `"data"`
  syncs contents, `"all"` syncs contents and metadata (`LF@44#L3898-L3907`).
- What is left on disk when a sink fails: see 6.4.

### 3.2 Option parity with `write_csv` and `write_parquet`

- `[1.38-1.44]` `DataFrame.write_csv` is implemented as
  `self.lazy().sink_csv(target, ..., engine="in-memory")`, and
  `DataFrame.write_parquet` as `self.lazy().sink_parquet(target, ...,
  engine="streaming")` unless `use_pyarrow=True` (`DF@44#L3238-L3266`,
  `#L4358-L4390`; `DF@38#L3218-L3222`, `#L4323-L4339`).
- `[1.38-1.44]` CSV, parameters on both with the same defaults: `include_bom`,
  `compression`, `compression_level`, `check_extension`, `include_header`,
  `separator`, `line_terminator`, `quote_char`, `batch_size`, `datetime_format`,
  `date_format`, `time_format`, `float_scientific`, `float_precision`,
  `decimal_comma`, `null_value`, `quote_style`, `storage_options`,
  `credential_provider`, `retries`. Only on `write_csv`: `file=None`, where
  `None` returns the CSV as a string (`DF@44#L3099-L3101`). Only on `sink_csv`:
  `path` (required), `maintain_order`, `sync_on_close`, `mkdir`, `lazy`,
  `engine`, `optimizations`. (Signatures read at both tags; compared with
  `inspect` on 1.44.2.)
- `[1.38-1.44]` Neither CSV signature has an append, encoding or escape
  character parameter.
- `[1.38-1.44]` Parquet, on both: `compression`, `compression_level`,
  `statistics`, `row_group_size`, `data_page_size`, `storage_options`,
  `credential_provider`, `retries`, `metadata`, `arrow_schema`, `mkdir`. Only
  on `write_parquet`: `use_pyarrow`, `pyarrow_options`, `partition_by`,
  `partition_chunk_size_bytes`. Only on `sink_parquet`: `maintain_order`,
  `sync_on_close`, `lazy`, `engine`, `optimizations`, and from 1.44.0
  `sinked_paths_callback`.
- **Observed** (1.44.2): for one frame with strings needing quotes, nulls,
  floats, dates, datetimes and a Decimal column, `write_csv`, `sink_csv` and
  `sink_csv(engine="in-memory")` wrote byte-identical files under nine option
  sets (defaults; separator, quote and null value; `quote_style` always,
  non_numeric and never; CRLF without header and with BOM; date and datetime
  formats; `float_precision`; `decimal_comma`).

### 3.3 Several sinks from one plan in one pass

- `[1.38-1.44]` guide/lazy/sources_sinks L41-L54: "Sinks can also multiplex.
  Meaning that we write to different sinks in a single query", with
  `q1 = lf.sink_parquet(.., lazy=True)`, `q2 = lf.sink_ipc(.., lazy=True)`,
  `pl.collect_all([q1, q2])`.
- `[1.38-1.44]` `lazy=True` on a sink: "Wait to start execution until `collect`
  is called." Marked unstable (`LF@44#L3914-L3919`, `LF@38#L3697-L3702`).
  **Observed**: it returns a LazyFrame, no file exists until it is collected,
  and the collect returns an empty frame of shape (0, 0).
- `[1.38-1.44]` In the streaming engine the plan is one graph: every sink is a
  node under a `SinkMultiple` root (`LOWER@44#L324-L338`, `LOWER@38#L305`) and
  a shared stream is fed through a multiplexer (`PHYS@44#L814-L839`).
- **Observed** (1.44.2), as in 1.5: a single source pass only with
  `pl.collect_all([...], engine="streaming")`. With the default engine both
  files were written correctly, from two source passes.
- **Observed**, 20M-row source, two CSV sinks of 15M rows each: one streaming
  `collect_all` took 1.48 / 1.91 / 2.31 s (min / median / max of 3) at 2.1 to
  2.4 GB peak RSS; two separate `sink_csv` calls took 3.57 / 5.25 / 6.63 s at
  1.4 GB. Both include operating-system write-back of well over a gigabyte of
  output and are noisy.
- `[1.44.2]` The multiplexer feeds each consumer through its own unbounded
  queue (crates/polars-stream/src/nodes/multiplexer.rs`@44#L10-L22`,
  `#L126-L142`). rel/py-1.40.0 lists "Lock-free memory manager with
  spill-to-disk and fully OOC multiplexer (#26774)"; spilling is subject to the
  env var in 2.4.

---

## 4. Row counts without a second pass

### 4.1 What a collect or a sink reports

- `collect()` returns a DataFrame; its `height` is the count.
- `[1.38-1.44]` A sink returns `None` (3.1). Nothing in its return value says
  how many rows were written. This is as-found finding 23.
- `[>=1.44.0]` `sink_parquet` and `sink_ipc` take `sinked_paths_callback`:
  "Callable that will be called with information on sinked paths." Marked
  unstable (`LF@44#L2984-L2989`; rel/py-1.44.0 "#28814"). It receives
  `SinkedPath(path, num_rows, num_bytes)` entries
  (py-polars/src/polars/io/partition.py`@44#L171-L187`). From 1.40.0 to 1.43.2
  it existed only as a private `_sinked_paths_callback` on `sink_parquet` (tag
  scan). `sink_csv` and `sink_ndjson` do not have it at 1.44.2. **Observed**:
  one entry with `num_rows=3334` for a 3334-row write.
- `[>=1.41.0]` `LazyFrame.execute()` (unstable) returns a `QueryResult` with
  `n_rows_total`, "Total rows that are outputted by the result"
  (`LF@44#L2244-L2260`; py-polars/src/polars/lazyframe/
  query_result.py`@44#L27-L30`). For the local engines it is a full collect
  followed by `df.height` (`ENGINE@44#L381-L383`).
- `[1.38-1.44]` `sink_batches(function)` and `collect_batches()` pass each batch
  to Python, where rows can be counted. Both are unstable and carry the warning
  "This method is much slower than native sinks. Only use it if you cannot
  implement your logic otherwise." (`LF@44#L4264-L4277`, `#L4342-L4358`;
  `LF@38#L4087-L4091`, `#L4162-L4166`).
- `[1.44.2]` The streaming engine can log per-node metrics, including
  `rows_received` and `rows_sent`, when `POLARS_LOG_METRICS=1` is set
  (crates/polars-stream/src/skeleton.rs`@44#L168-L176`, `#L205-L249`). The
  variable is not in the Python docs. **Observed**: the log printed node names
  and timings, with every row counter at 0.

### 4.2 Counting in the same pass as the sink

- Built from documented parts: `pl.collect_all([lf.sink_csv(path, lazy=True),
  lf.select(pl.len())], engine="streaming")`. The second result holds the
  count. `lazy=True` is unstable (3.3).
- **Observed** (1.44.2): the source was executed once on
  `engine="streaming"`, and the count equalled the rows in the file. On the
  default engine the source was executed twice (1.5).
- A count branch has no filter of its own, so the rule in 1.4 does not split
  it from the sink branch. **Observed**: two `CACHE` references in
  `explain_all`.

### 4.3 Measured cost

**Observed** (1.44.2; Apple M4, 10 cores, 16 GB; 20M-row, 988 MB CSV; plan
`scan_csv -> filter (keeps 15M rows) -> with_columns`; each case 3 times, each
in a fresh process, page cache warm). Peak RSS includes the memory-mapped
source file. Cases that write files include operating-system write-back. Read
the columns as indicative, not as a benchmark.

| Case | Seconds, min / median / max | Peak RSS, MB |
|---|---|---|
| `sink_csv` only (streaming) | 0.49 / 0.74 / 1.16 | 1350 to 1483 |
| `collect()` then `write_csv`, count from `df.height` (the engine today) | 1.04 / 1.41 / 1.91 | 2388 to 2559 |
| `collect(engine="streaming")` then `write_csv` | 0.86 / 0.91 / 0.97 | 2677 to 2687 |
| `collect_all([sink, len], engine="streaming")` | 0.51 / 0.53 / 0.55 | 1402 to 1439 |
| `collect_all([sink, len])`, default engine | 0.91 / 0.98 / 1.17 | 2530 to 2537 |
| `sink_csv`, then a separate `select(pl.len()).collect()` | 0.79 / 0.80 / 1.08 | 1455 to 1473 |
| `collect_all([half_a, half_b])` as DataFrames, default engine | 0.68 / 0.72 / 0.81 | 3245 to 4041 |
| `collect_all([half_a, half_b], engine="streaming")` | 0.63 / 0.66 / 0.67 | 3836 to 3961 |
| Two separate `.collect()` for the two halves (the engine today) | 0.84 / 0.86 / 0.86 | 2628 to 2815 |

Read against the first row: counting in the sink's own streaming pass added no
time or memory that this run could measure. Collecting first, or using the
default engine in `collect_all`, held about one more gigabyte, roughly the
15M-row frame.

---

## 5. Decimal

### 5.1 Status

- `[1.38-1.44]` `pl.Decimal` exists and carries no unstable warning: "Decimal
  128-bit type with an optional precision and non-negative scale."
  (py-polars/src/polars/datatypes/classes.py`@44#L448-L474`, `@38#L433-L459`).
  The comment in `src/v2/components/file/schema_types.py`, "Polars doesn't have
  Decimal", is out of date.
- Stabilized before the pin: rel/py-1.35.0 (2025-10-26) "Stabilize decimal
  (#25020)", by ritchie46 (member). Just before it, rel/py-1.34.0: "Use
  fixed-scale Decimals (#24542)", "Decimal <-> literal arithmetic supertype
  rules (#24594)".
- `[1.38-1.44]` The user guide gives no arithmetic rules of its own. Its type
  table says: "Use this if you need fine-grained control over the precision of
  your floats and the operations you make on them. See Python's
  `decimal.Decimal` for documentation on what a decimal data type is."
  (docs/source/user-guide/concepts/data-types-and-structures.md L200). The
  two types do not behave alike; see 5.8.
- `[1.38-1.44]` The arithmetic file `DECOPS` is identical at both tags, and
  `DEC` differs only in which integer-parsing calls `str_to_dec128` makes.
- `[1.38-1.44]` Still unstable: `Expr.str.to_decimal` (py-polars/src/polars/
  expr/string.py`@44#L334-L350`, `@38#L328-L340`).
- Coming in 2.0, outside the pin (rel/py-2.0.0-rc.2): "Coerce float literals to
  decimal instead of casting the column (#29395)"; "Consistent `Date` and
  `Decimal` means between the streaming and in-memory engines (#29359)".

### 5.2 Precision and scale

- `[1.38-1.44]` "precision: Maximum number of digits in each number. If set to
  `None` (default), the precision is set to 38 (the maximum supported by
  Polars). scale: Number of digits to the right of the decimal point in each
  number." `scale` defaults to 0 (classes.py, as above).
- `[1.38-1.44]` "precision must be between 1 and 38"; "scale must be less than
  or equal to precision" (`DEC@44#L35-L42`). A value fits precision `p` when
  its unscaled integer is strictly between `-10^p` and `10^p`
  (`DEC@44#L457-L461`).
- The scale is a property of the column, not of each value. **Observed**: a
  list `[Decimal("1.10"), Decimal("2.555")]` becomes `Decimal(38, 3)` holding
  `1.100` and `2.555`; `to_list()` returns Python `decimal.Decimal` objects.

### 5.3 Arithmetic

- `[1.38-1.44]` For `+`, `-`, `*`, `/` between two Decimal columns the result
  type is `Decimal(38, max(scale_left, scale_right))` (`DECOPS@44#L11-L15`,
  `#L73-L77`, `#L104-L108`; plan-time rule `SCHEMA@44#L578-L580`,
  `#L639-L641`, `#L699-L703`, `#L867-L869`; `SCHEMA@38#L563-L565`,
  `#L845-L847`). Both operands are first rescaled to that scale.
- `[1.38-1.44]` Multiplication: "Computes round(l * r / 10^s), rounding to
  nearest even." Division: "Computes round((l / r) * 10^s), rounding to nearest
  even." (`DEC@44#L523-L526`, `#L553-L564`). The product does not gain scale.
- `[1.38-1.44]` Division by zero raises `ComputeError: division by zero
  Decimal` (`DECOPS@44#L116-L118`). Overflow past 38 digits raises
  `ComputeError: overflow in decimal addition for ...`, and likewise for
  subtraction, multiplication and division (`DECOPS@44#L29-L31`, `#L91-L93`).
- `[1.38-1.44]` A null operand gives null (`DECOPS@44#L20-L22`).
- `[1.44.2]` Decimal divided by a float is planned as Float64
  (`SCHEMA@44#L871-L873`). rel/py-1.43.0 lists a fix, "Incorrect schema type for
  decimal <-> primitive division (#28373)"; the behaviour before 1.43.0 was not
  checked.

**Observed** (1.44.2), `a` and `b` both `Decimal(10, 2)`; every result dtype is
`Decimal(38, 2)`:

| a, b | Polars `a * b` | Python `a * b` | Polars `a / b` | Python `a / b` |
|---|---|---|---|---|
| 1.25, 1.25 | 1.56 | 1.5625 | 1.00 | 1 |
| 10.10, 3.00 | 30.30 | 30.3000 | 3.37 | 3.366666666666666666666666667 |
| 1.00, 3.00 | 3.00 | 3.0000 | 0.33 | 0.3333333333333333333333333333 |
| 0.50, 0.25 | 0.12 | 0.1250 | 2.00 | 2 |
| 0.50, 0.75 | 0.38 | 0.3750 | 0.67 | 0.6666666666666666666666666667 |

**Observed** (1.44.2), other operands and operators:
- `Decimal(10,2) + Decimal(12,4)` is `Decimal(38,4)`; `10.10 * 1.2345` gives
  `12.4684` (exact 12.46845, tie to even).
- Decimal with an Int64 column or an int literal stays Decimal: `10.10 * 3` is
  `30.30`, `10.10 / 3` is `3.37`, both `Decimal(38,2)`. As floats the same
  product is `30.299999999999997`, which is as-found finding 17.
- Decimal with a Float64 column or a float literal gives **Float64**.
- Decimal with `pl.lit(decimal.Decimal("0.125"))` gives `Decimal(38,3)`:
  `10.10 * 0.125` is `1.262`; Python gives `1.26250`.
- `//`, `%` and `**` raise `InvalidOperationError` ("floor_div operation not
  supported for dtype `decimal[10,2]`", and likewise `remainder`, `pow`).
  Negation and `abs` keep the dtype.
- Comparison works across scales and against floats: `1.10 == 1.1000` and
  `1.10 == 1.1` are true.

### 5.4 Aggregation

- `sum` changed inside the pin:
  - `[1.38.0 to 1.39.x]` result keeps the input type `Decimal(p, s)`
    (`DECSER@38#L432-L439`).
  - `[>=1.40.0]` plan-time type is `Decimal(38, s)` (`SCHEMA@44#L199-L200`;
    rel/py-1.40.0 "#27270").
  - `[>=1.41.0]` the runtime result is `Decimal(38, s)`, for whole-column and
    group-by sums (rel/py-1.41.0 "#27579"; tag scan of `DECSER`).
  - `[>=1.44.0]` overflow raises `ComputeError: overflow in decimal addition in
    sum` (`DECSER@44#L443-L458`). Before that, per the fix's author (#28688):
    "Series.sum() on Decimal summed the physical i128 values without validation
    ... returned a silently wrapped (negative) total".
- `[1.38-1.44]` `mean`, `median` and `std` of a Decimal column are Float64
  (crates/polars-plan/src/plans/aexpr/function_expr/schema.rs`@44#L574-L575`,
  `@38#L545-L546`). `min`, `max`, `first`, `last` keep the input type
  (`SCHEMA@44#L167-L172`).
- `[>=1.39.0]` `product` returns `Decimal(38, s)`, rounding to scale at every
  step and giving null on overflow (crates/polars-core/src/chunked_array/
  logical/decimal.rs`@44#L195-L214`).
- **Observed** (1.44.2) on 10.10, 20.20, 0.01, 0.02, null as `Decimal(10,2)`:
  `sum` 30.33 as `Decimal(38,2)`; `mean` 7.5825 as Float64; `min`, `max` as
  `Decimal(10,2)`; `cum_sum` as `Decimal(38,2)`; `product` 0.04. Sum of an
  empty Decimal column is 0.00. Group-by `sum` is `Decimal(38,2)` on both
  engines. The Float64 group mean of 10.10 and 20.20 printed
  `15.149999999999999` on the in-memory engine and `15.15` on streaming.

### 5.5 Rounding

- `[1.38-1.44]` Every scale reduction in the Decimal code rounds half to even:
  the helper "Returns round(x / 10^e) ... rounding to nearest even"
  (`DEC@44#L249-L266`) is used by rescale, which is a cast to a smaller scale
  (`DEC@44#L496-L509`), by multiplication, and by Decimal to integer
  (`DEC@44#L463-L466`). Division and string parsing round half to even too
  (`DEC@44#L587-L590`, `#L768-L777`).
- `[1.38-1.44]` `Expr.round(decimals=0, mode="half_to_even")`, with
  `"half_away_from_zero"` as the alternative (`EXPR@38#L1685-L1701`,
  `EXPR@44#L1945-L1979`). On a Decimal it keeps the dtype, so the scale does
  not shrink (crates/polars-ops/src/series/ops/round.rs`@44#L138-L180`).
- `[>=1.39.0]` `Expr.truncate(decimals)` truncates toward zero
  (`EXPR@44#L2068-L2085`; tag scan).
- Docs versus runtime `[1.44.2]`: the docstring and the type alias also list
  `mode="to_zero"` (`EXPR@44#L1975-L1979`; py-polars/src/polars/
  _typing.py`@44#L250`), but the Python binding accepts only the two older
  values (crates/polars-python/src/conversion/mod.rs`@44#L958-L970`).
  **Observed**: `round(2, mode="to_zero")` raises `ValueError`.

**Observed** (1.44.2), column `Decimal(10,3)`; `round`, `truncate`, `floor` and
`ceil` return `Decimal(10,3)`, the cast returns `Decimal(10,2)`:

| x | `round(2)` | `round(2, "half_away_from_zero")` | `truncate(2)` | `cast(Decimal(10,2))` | `floor()` |
|---|---|---|---|---|---|
| 0.125 | 0.120 | 0.130 | 0.120 | 0.12 | 0.000 |
| 0.135 | 0.140 | 0.140 | 0.130 | 0.14 | 0.000 |
| -0.125 | -0.120 | -0.130 | -0.120 | -0.12 | -1.000 |
| 1.005 | 1.000 | 1.010 | 1.000 | 1.00 | 1.000 |

Python's `quantize(Decimal("0.01"))` gives the same values as the cast column
under its default `ROUND_HALF_EVEN`, and the same as the third column under
`ROUND_HALF_UP`.

### 5.6 Casting from strings, floats and integers

- `[1.38-1.44]` String to Decimal: "no decimal separator is required (eg "500",
  "500.", and "500.0" are all accepted) ... Returns None if the number is not
  well-formed, or does not fit." An exponent (`e` or `E`) is parsed, and digits
  beyond the scale are rounded to even (`DEC@44#L662-L799`). Scientific
  notation arrived just before the pin: rel/py-1.37.0 "Allow scientific
  notation when parsing Decimals (#25711)".
- `[1.38-1.44]` `cast(pl.Decimal(p, s))` is strict by default and raises
  `InvalidOperationError`; `strict=False` gives null (6.3).
- `[1.38-1.44]` `Expr.str.to_decimal(*, scale)` returns `Decimal(38, scale)`;
  1.33.0 removed `inference_length` and made `scale` required
  (expr/string.py`@44#L334-L388`).
- `[1.38-1.44]` Float to Decimal multiplies by `10^s` and rounds ties to even,
  with a source note: "TODO: correctly rounded result. This rounds multiple
  times." (`DEC@44#L483-L494`).

**Observed** (1.44.2):
- `cast(pl.Decimal(10,2), strict=False)` from strings: `"1.005"` gives 1.00;
  `"2.675"` 2.68; `"1e3"` 1000.00; `"+3.10"` 3.10; `".5"` 0.50; `"5."` 5.00;
  `"-0.005"` 0.00; `"-0.006"` -0.01. Null for: `"abc"`, `""`, `" 1.5"`,
  `"1.5 "`, `"1,5"`, `"1_000"`, `"0x10"`, `"NaN"`, and `"12345678901.00"`
  (too wide for precision 10).
- `str.to_decimal(scale=2)` on `"abc"` returns null and raises nothing.
- Float64 to `Decimal(10,2)`: 2.675 gives 2.68; 1.005 gives 1.00;
  0.30000000000000004 gives 0.30. With `strict=False`, 1e20, NaN and inf give
  null.
- Decimal to Int64 rounds half to even: 2.50 gives 2, 3.50 gives 4, 1.99 gives
  2, -1.99 gives -2. Python `int()` truncates (3, 1, -1); Python `round()`
  matches Polars.
- Decimal to String keeps the scale ("2.50").

### 5.7 CSV read and write

- `[1.38-1.44]` CSV type inference never yields Decimal: a float-looking field
  is inferred as Float64 (crates/polars-io/src/csv/read/
  schema_inference.rs`@44#L339-L342`, `@38#L280-L283`). A Decimal column needs
  `schema` or `schema_overrides`.
- `[1.38-1.44]` Reading into a declared `Decimal(p, s)`: quotes are stripped,
  leading whitespace is skipped, an empty field is null, the rest goes through
  the string parser above. A field that fails is null under
  `ignore_errors=True`, otherwise an error (crates/polars-io/src/csv/read/
  builder.rs`@44#L396-L433`, `@38#L370-L426`). `decimal_comma=True` switches
  the separator (rel/py-1.34.0 "#24685").
- `[1.38-1.44]` Writing: the serializer writes every value with the column's
  full scale, unless the global zero-trimming setting is on, and honours
  `decimal_comma`. Whether a Decimal is quoted is decided from
  `decimal_comma`, a comma separator and a scale above 0, together with the
  quote style (crates/polars-io/src/csv/write/write_impl/
  serializer.rs`@44#L331-L342`, `#L598-L601`; file identical at py-1.38.0).
- **Observed** (1.44.2): reading `10.10`, `3.999`, empty, `"7"`, ` 2.5`, `1e2`,
  `-0.005` into `Decimal(10,2)` gives 10.10, 4.00, null, 7.00, 2.50, 100.00,
  0.00. A bad field raises `ComputeError: could not parse `abc` as dtype
  `decimal[10,2]` at column 'amt' (column number 2)`.
- **Observed**: `write_csv` writes `30.30`, `1.00` and an empty field for null.
  `float_precision` does not touch Decimal columns. `quote_style="non_numeric"`
  leaves them unquoted. With `decimal_comma=True` and a comma separator they
  come out as `"30,30"`.
- **Observed**: inside `pl.Config(trim_decimal_zeros=True)` the same
  `write_csv` writes `30.3` and `1`. That setting is documented as display
  formatting, "Strip trailing zeros from Decimal data type values"
  (config.py`@44#L1472-L1479`), and it changes file output. It is off by
  default.
- **Observed**: Parquet round-trips `Decimal(10,2)` unchanged.

### 5.8 Beside Python's `decimal.Decimal`

| Aspect | Polars `pl.Decimal` [1.38-1.44 unless stamped] | Python `decimal.Decimal` (pydecimal) |
|---|---|---|
| Precision | Fixed 128-bit; 1 to 38 digits per column | "a user alterable precision (defaulting to 28 places) which can be as large as needed" |
| Scale | Fixed per column, 0 to precision; every value shown at that scale | Per value: "a notion of significant places so that 1.30 + 1.20 is 2.50" |
| `+`, `-` result | `Decimal(38, max scale)`; raises past 38 digits | Exact, then rounded to context precision |
| `*` result | Scale stays `max scale`; rounded half to even | "uses all the figures in the multiplicands. For instance, 1.3 * 1.2 gives 1.56 while 1.30 * 1.20 gives 1.5600" |
| `/` result | Scale stays `max scale`; rounded half to even | Up to context precision: `Decimal(1) / Decimal(7)` is `0.1428571428571428571428571429` |
| Default rounding | Half to even, not configurable for arithmetic | `rounding=ROUND_HALF_EVEN` in the default context, configurable |
| Other modes | `round(mode="half_away_from_zero")`; `truncate()` from 1.39.0 | `ROUND_HALF_UP`: "Round to nearest with ties going away from zero."; `ROUND_DOWN`: "Round towards zero."; five more |
| Fixing the scale | `cast(pl.Decimal(p, s))` rounds half to even; `round()` keeps the scale | "The quantize() method rounds a number to a fixed exponent." |
| Division by zero | `ComputeError`, the query fails | `DivisionByZero` is trapped in the default context |
| Overflow | `ComputeError` past 38 digits; `sum` wrapped silently before 1.44.0 | `Overflow` is trapped; exponent range is +/-999999 |
| With a float | Float64 result in the pin; changes in 2.0 | `Decimal + float` raises `TypeError` (run on 3.14.6) |
| `//`, `%`, `**` | Not supported (1.44.2, observed) | Supported (run on 3.14.6) |
| `sum`, `mean` | `sum` is `Decimal(38, s)` from 1.41.0; `mean` is Float64 | `sum()` and `/` stay Decimal, under the context precision (run on 3.14.6: 30.33 and 15.15) |

Python's default context, printed by 3.14.6 and matching pydecimal:
`Context(prec=28, rounding=ROUND_HALF_EVEN, Emin=-999999, Emax=999999, ...,
traps=[InvalidOperation, DivisionByZero, Overflow])`. The Python cells in
quotation marks are from pydecimal; the others were run on Python 3.14.6.

**Observed** (1.44.2): a 38-digit value plus itself stays exact in Polars
(`246913578024691357802469135780.24691356`), where Python's default context
rounds to 28 digits (`2.469135780246913578024691358E+29`).

---

## 6. Errors in lazy plans

### 6.1 When errors surface

- `[1.38-1.44]` Building a plan reads no data and checks little. guide/lazy/
  schemas L17-L18: "Polars will check the schema before any data is processed.
  This check happens when you execute your lazy query." L39-L40: "Polars checks
  for any potential `InvalidOperationError` before the time-consuming step of
  actually processing the data in the pipeline."
- **Observed** (1.44.2): selecting an unknown column builds a plan without
  error; `collect_schema()` and `collect()` both raise `ColumnNotFoundError:
  unable to find column "nope"; valid columns: ["id", "grp", "amt"]`.
- **Observed** (1.44.2), with a counting function upstream to see whether data
  was touched before the error:

| Query | `collect_schema()` | `collect()` |
|---|---|---|
| String + Int | `InvalidOperationError`, no data read | same |
| `sum()` on a String column | `InvalidOperationError`, no data read | same |
| Join on keys of different dtypes | `SchemaError`, no data read | same |
| `filter` with a non-boolean predicate | `InvalidOperationError`, no data read | same |
| `round()` on a String column | passes | `InvalidOperationError` after the upstream ran |
| `str.len_bytes()` on an Int column | passes | `SchemaError` after the upstream ran |
| Strict cast, strict `str.to_date`, `str.to_integer` on bad data | passes | error after the upstream ran |

- The `round()` row is the guide's own example (guide/lazy/schemas L20-L27);
  on 1.44.2 it was raised during execution, not before it.
- **Observed**: `pl.scan_csv(path_that_does_not_exist)` returns a LazyFrame
  without complaint; `collect()` then raises the built-in `FileNotFoundError`,
  naming the path.
- Data-dependent errors (a value that will not cast, a CSV field that will not
  parse) can only surface while the collect or sink executes, wherever in the
  plan the cast or the scan sits. That is as-found finding 24.

### 6.2 What the exception identifies

- `[1.38-1.44]` Polars exceptions are subclasses of
  `polars.exceptions.PolarsError`. **Observed** (1.44.2): `ComputeError` and
  `InvalidOperationError` carry one string argument and no other attribute;
  there is no field for column, row, file or plan node.
- `[1.38-1.44]` Strict cast failure: `InvalidOperationError: conversion from
  `{from}` to `{to}` failed in column '{name}' for {n} out of {m} values:
  [up to 10 values]` (crates/polars-core/src/utils/series.rs`@44#L50-L94`,
  `@38#L81-L85`).
- **Observed** (1.44.2), one bad value in 300,000 rows: "conversion from `str`
  to `f64` failed in column 'amt' for 1 out of 2016 values: ["12x.50"]", the
  same text on both engines. The "out of" figure is the size of the batch being
  cast, not the row count. With `.alias("amount_num")` after the cast the
  message still says 'amt'.
- `[1.38-1.44]` CSV parse failure: `ComputeError: could not parse `{field}` as
  dtype `{dtype}` at column '{name}' (column number {n})`, then "The current
  offset in the file is {n} bytes." and a list of suggestions
  (crates/polars-io/src/csv/read/parser.rs`@44#L1165-L1190`,
  `@38#L1121-L1129`).
- **Observed** (1.44.2): the offset printed for a bad field on the last line of
  a 4.9 MB file was 38294, so it is not a position in the file. Scanning two
  files, the message did not name the file that held the bad field.
- `[1.44.2]` Errors found while resolving the plan append the plan: "Resolved
  plan until failure: ---> FAILED HERE RESOLVING {node} <---"
  (crates/polars-plan/src/plans/conversion/dsl_to_ir/mod.rs`@44#L96`).
  **Observed** for the unknown-column case.
- Nothing in any message names an engine component. That link has to be made
  by whoever built the plan.

### 6.3 What `strict=False` does

- `[1.38-1.44]` `Expr.cast(dtype, *, strict=True, wrap_numerical=False)`:
  "strict: Raise if cast is invalid on rows after predicates are pushed down.
  If `False`, invalid casts will produce null values. wrap_numerical: If True
  numeric casts wrap overflowing values instead of marking the cast as invalid."
  (`EXPR@44#L2197-L2202`, `EXPR@38#L1849-L1854`). `LazyFrame.cast(dtypes, *,
  strict=True)`: "Throw an error if a cast could not be done (for instance, due
  to an overflow)." (`LF@44#L4502-L4504`).
- **Observed** (1.44.2): `strict=False` turned the one bad value into one null
  on both engines. `str.to_date(fmt, strict=False)` also gives null.
- "After predicates are pushed down" is literal. **Observed**: a strict cast
  followed by a filter that removes the bad row succeeded with default
  optimizations (299,999 rows) and raised with
  `QueryOptFlags(predicate_pushdown=False)`.
- `[1.38-1.44]` The CSV counterpart is `scan_csv(ignore_errors=True)`: a field
  that fails to parse becomes null (crates/polars-io/src/csv/read/
  builder.rs`@44#L154-L161`, `#L423-L427`). **Observed**: one null, no error.
- Neither switch says which rows were nulled.

### 6.4 What is on disk after a failure (observed only)

No statement about partial output was found in the sink docstrings or the user
guide. **Observed** (1.44.2), plan with one uncastable value on the last of
300,000 lines:

| What ran | Exception | Target path afterwards |
|---|---|---|
| `sink_csv` (streaming) | `InvalidOperationError` | File exists: header only, 0 data rows |
| `collect()` then `write_csv` | `InvalidOperationError` | No file (the collect failed first) |
| `collect_all([good_sink, failing_sink])`, default engine | `InvalidOperationError` | Good file complete (300,000 rows); failing file has 4,516 rows |
| Same, `engine="streaming"` | `InvalidOperationError` | Good file complete; failing file has 12,871 rows |

---

## 7. Order

### 7.1 What the docs promise

- `[1.38-1.44]` guide/lazy/execution L42-L44: "If you define an operation on a
  `LazyFrame` that doesn't maintain row order (such as a `group_by`), then the
  order will also change every time it is run. To avoid this, use
  `maintain_order=True` arguments for such operations."
- `[1.38-1.44]` `group_by(maintain_order=False)`: "Ensure that the order of the
  groups is consistent with the input data. This is slower than a default group
  by." (`LF@44#L5222-L5224`, `LF@38#L5014-L5016`).
- `[1.38-1.44]` `unique(keep="any", maintain_order=False)`. `keep`: "'any': Does
  not give any guarantee of which row is kept. This allows more optimizations."
  `maintain_order`: "Keep the same order as the original DataFrame. This is
  more expensive to compute." (`LF@44#L8201-L8211`, `LF@38#L7768-L7778`).
- `[1.38-1.44]` `join(maintain_order=None)`, values `none`, `left`, `right`,
  `left_right`, `right_left`: "Do not rely on any observed ordering without
  explicitly setting this parameter, as your code may break in a future
  release. Not specifying any ordering can improve performance." For `none`,
  the default: "The ordering might differ across Polars versions or even
  between different runs." (`LF@44#L6293-L6312`, `LF@38#L6053-L6072`).
- `[1.38-1.44]` `sort(maintain_order=False)`: "Whether the order should be
  maintained if elements are equal." (`LF@44#L1663-L1664`,
  `LF@38#L1619-L1620`).
- `[1.38-1.44]` `pl.union`: "This function does not guarantee any specific
  ordering of rows in the result. If you need predictable row ordering, use
  `pl.concat()` instead." (`EAGER@44#L391-L393`, `EAGER@38#L326-L328`). In the
  code `pl.concat` asks for an ordered union and `pl.union` for an unordered
  one (`EAGER@44#L290-L295`, `#L603-L608`; `LOWER@44#L603-L607`).
- `[1.38-1.44]` Sinks, `sink_batches` and `collect_batches` default to
  `maintain_order=True` (3.1).
- `[1.38-1.44]` `top_k` and `bottom_k`: "The output is not guaranteed to be in
  any particular order, call `sort` after this function if you wish the output
  to be sorted." (`LF@44#L1855-L1857`, `LF@38#L1809-L1811`).
- `[1.44.2]` The optimizer may drop ordering nobody can see:
  `check_order_observe`, "Do not maintain order if the order would not be
  observed." (opt_flags.py`@44#L238-L241`; pass at
  crates/polars-plan/src/plans/optimizer/mod.rs`@44#L271-L296`). The same pass
  exists at 1.38.0 as `set_order`.
- No general statement was found that filter, select or with_columns keep row
  order on either engine; see "Could not establish".

### 7.2 Observed, per engine

**Observed** (1.44.2; 4M-row CSV scan with an ascending `id`, so results span
many batches). "Yes" means the property held on this run, not that it is
promised:

| Operation and check | In-memory | Streaming |
|---|---|---|
| `filter`, `with_columns`, `select`: rows stay in source order | yes | yes |
| `pl.concat([A, B])`: all of A, then all of B, each in order | yes | yes |
| `pl.union([A, B])`: same check | yes | **no** (interleaved) |
| `group_by` default: same key order on 3 runs | **no** | **no** |
| `group_by(maintain_order=True)`: keys in first-seen order | yes | yes |
| Values inside a group (`agg(pl.col(x))`) keep input order | yes | yes |
| `unique` default: same row order on 3 runs | **no** | **no** |
| `unique(keep="first", maintain_order=True)`: first-seen order, first row kept | yes | yes |
| `unique(keep="last", maintain_order=True)`: rows in input order | yes | yes |
| Left join, `maintain_order` not set: left order kept | yes | **no** |
| Inner join, `maintain_order` not set: left order kept | yes | **no** |
| Left join, `maintain_order="left"`: left order kept | yes | yes |
| `sort(key)`: ties keep input order | yes | yes |
| `sink_csv(maintain_order=True)`: file in source order | not run | yes |
| `sink_csv(maintain_order=False)`: file in source order | not run | yes |

The join rows are the practical difference between the engines: code that
leaned on left order without setting `maintain_order` passes on the in-memory
engine and breaks on streaming.

---

## Could not establish

- **Behaviour between the two ends of the pin.** Only 1.44.2 was run. Facts
  stamped `[1.38-1.44]` rest on reading both tags; where a change version is
  given it comes from a tag scan or the release notes, not from running that
  release. In particular the source-read claims that 1.38.0 to 1.42.x drop a
  shared sub-plan whenever branch filters differ (1.4), and that the default
  engine runs the source once per lazy sink on 1.38.0 (1.5), were not run.
- **A general row-order guarantee for the streaming engine.** The docs give
  per-operation `maintain_order` switches and nothing broader. That filter,
  select and with_columns kept order on streaming is observed only.
- **What a failed sink leaves behind, as a contract.** Partial files were
  observed (6.4); no source says whether that is intended, or whether a later
  release writes to a temporary name first.
- **How to read row counts from the streaming engine.** The per-node metrics
  exist in the source and the log printed zeros (4.1). No supported API was
  found for `sink_csv`.
- **The meaning of "partially-streaming"** in the 1.44 API badges (2.3).
- **Memory held by streaming group-by and join.** The tracking issue says
  out-of-core is not done for either; no source states a bound, and the build
  side of a join is only "likely" held in memory. Not measured here.
- **Whether `sort(maintain_order=False)` and `sink_csv(maintain_order=False)`
  can reorder in practice.** Both kept order on the runs above; the docs do not
  promise it.
- **Decimal division by an integer before 1.43.0**, given the schema fix in
  that release (5.3), and the state of `sum` on 1.40.x, where the plan-time
  type was widened one release before the runtime type (5.4).
- **Why the benchmark in `docs/v2/MEMORY_MANAGEMENT.md` behaved as it did.**
  Its numbers were not re-run; only its stated mechanism was checked (2.5).
- **Target servers.** Every observation is from one Mac. Timings and memory in
  4.3 in particular say nothing about RHEL hosts with other core counts, disks
  or file systems.
