# V2 Engine: Memory Management and Performance Tuning

This guide covers how the V2 PyETL engine manages memory, how barrier placement
affects peak memory usage, and practical tuning advice backed by real benchmark data.

Target audience: engineers running large-scale ETL jobs through the V2 engine.

---

## Table of Contents

1. [How Memory Works in V2](#how-memory-works-in-v2)
2. [Reference Counting Deep Dive](#reference-counting-deep-dive)
3. [Barrier Impact on Memory](#barrier-impact-on-memory)
4. [Benchmark Results](#benchmark-results)
5. [Performance Tuning Guide](#performance-tuning-guide)
6. [Polars Internals That Matter](#polars-internals-that-matter)
7. [Scaling Guidelines](#scaling-guidelines)
8. [When Things Break](#when-things-break)

---

## How Memory Works in V2

The V2 engine builds a pipeline of `pl.LazyFrame` operations. No data is loaded
into memory until something forces **materialization** (a `.collect()` call). The
key insight: a 15-component pipeline with zero barriers will build a single Polars
query plan that gets optimized and executed as one unit.

### The Lifecycle of Data

1. **Source components** call `pl.scan_csv()` (or `scan_parquet`, etc.). This
   returns a `LazyFrame` -- a query plan, not data. The file is not read yet.

2. **Transform components** (filter, map, select, sort, aggregate) append
   operations to the `LazyFrame`. Each `.filter()`, `.select()`, or `.join()`
   call adds a node to the query plan. Still no data in memory.

3. **Barrier components** call `.collect()`, which triggers Polars to execute
   the entire accumulated query plan. This is the moment data materializes in
   RAM. The result is a `DataFrame`, which the engine immediately re-wraps as
   a `LazyFrame` (via `.lazy()`) so downstream components continue in lazy mode.

4. **Sink components** (file output) are always barriers. They `.collect()` the
   final `LazyFrame` and write to disk.

The engine stores each component's output in an `ExecutionContext`. Once all
downstream consumers have read a component's output, reference counting frees it.

### What Forces Materialization

A component is a barrier when any of these is true:

| Condition | Why | Source |
|---|---|---|
| Component extends `SinkComponent` | Must write data to disk | `base.py` line 107: `is_barrier -> True` |
| Component extends `PythonComponent` | Python UDF needs a real DataFrame | `base.py` line 139: `is_barrier -> True` |
| Component produces multiple outputs | Engine must collect once and split | `engine.py` line 165: `len(result) > 1` |
| Filter with `reject_output: true` | Two outputs (main + reject) | `filter_component.py` line 49-54 |

Transform components (`TransformComponent`) are **not** barriers. Filter, Map,
Select, Sort, and Aggregate all operate lazily by default.

---

## Reference Counting Deep Dive

The engine uses reference counting to free component outputs as soon as they are
no longer needed. This is critical for long pipelines where intermediate outputs
would otherwise accumulate in memory.

### How It Works

**Step 1 -- DAG determines consumer counts.** When the engine starts, it builds a
DAG from the job configuration. Each node's reference count equals its number of
downstream consumers:

```
# src/v2/execution/dag.py, DAG.get_ref_counts()
def get_ref_counts(self) -> Dict[str, int]:
    return {
        node_id: len(node.downstream)
        for node_id, node in self.nodes.items()
    }
```

For a linear pipeline `A -> B -> C -> D`, reference counts are:
- A: 1 (consumed by B)
- B: 1 (consumed by C)
- C: 1 (consumed by D)
- D: 0 (sink, no downstream)

For a fan-out `A -> B, A -> C`, A's count is 2.

**Step 2 -- Engine initializes counts on the ExecutionContext.**

```
# src/v2/engine.py, PyETLEngine.execute()
ref_counts = self.dag.get_ref_counts()
for comp_id, count in ref_counts.items():
    context.set_ref_count(comp_id, count)
```

**Step 3 -- After each component executes, it decrements its upstream refs.**

```
# src/v2/engine.py, PyETLEngine._execute_component()
for upstream_id in dag_node.upstream:
    context.decrement_ref(upstream_id)
```

**Step 4 -- When a ref count hits zero, the output is deleted.**

```
# src/v2/execution/context.py, ExecutionContext.decrement_ref()
def decrement_ref(self, component_id: str) -> None:
    if component_id not in self._ref_counts:
        return
    self._ref_counts[component_id] -= 1
    if self._ref_counts[component_id] <= 0:
        if component_id in self._outputs:
            del self._outputs[component_id]
```

### Worked Example

Consider a pipeline with a fan-out:

```
read_orders (ref=2)
    |-> map_transform (ref=1) -> write_csv (ref=0)
    |-> aggregate_summary (ref=1) -> write_report (ref=0)
```

Execution order (topological): `read_orders`, `map_transform`, `aggregate_summary`,
`write_csv`, `write_report`.

1. `read_orders` executes. Output stored. Ref count = 2.
2. `map_transform` executes. Reads `read_orders` output. Decrements ref to 1.
   Output still alive (aggregate_summary has not run yet).
3. `aggregate_summary` executes. Reads `read_orders` output. Decrements ref to 0.
   **`read_orders` output is freed.**
4. `write_csv` executes. Reads `map_transform` output. Decrements ref to 0.
   **`map_transform` output is freed.**
5. `write_report` executes. Reads `aggregate_summary` output. Decrements ref to 0.
   **`aggregate_summary` output is freed.**

At no point are more than two component outputs alive simultaneously.

### Important Detail: LazyFrame Outputs Are Cheap

When a component is **not** a barrier, its output is a `LazyFrame` -- just a query
plan pointer. Storing it in the context costs almost zero memory. The ref counting
system matters most for **barrier outputs**, which are materialized `DataFrame`s
that have been re-wrapped as `LazyFrame` via `.lazy()`. Even though re-wrapping
is cheap (it wraps the underlying DataFrame), the materialized data stays in memory
until the ref count drops to zero and the context deletes it.

---

## Barrier Impact on Memory

This is the most counterintuitive concept in the engine: **more barriers can mean
less peak memory**.

### Why Fewer Barriers Use More Memory

With zero barriers (except the final sink), Polars builds one giant query plan.
When the sink calls `.collect()`, Polars executes the entire plan. Polars is smart
about streaming and predicate pushdown, but it still must hold intermediate join
results, grouped aggregations, and sorted data in memory simultaneously during
that single execution pass.

### Why More Barriers Use Less Memory

Each barrier calls `.collect()` on a smaller sub-plan. The result is stored,
ref-counted, and freed as soon as downstream components are done with it.
The maximum amount of data alive at any time is bounded by the largest single
materialization, not the entire dataset.

### The Tradeoff

| | Fewer Barriers | More Barriers |
|---|---|---|
| **Peak memory** | Higher (one large materialization) | Lower (many small materializations) |
| **Speed** | Faster (Polars optimizes the full plan) | Slower (optimization boundaries at each barrier) |
| **Predicate pushdown** | Full pipeline | Only within each segment between barriers |
| **Projection pushdown** | Full pipeline | Only within each segment |

The practical takeaway: **minimize barriers for speed, add barriers for memory
control**. The rest of this guide gives concrete numbers to help you decide.

---

## Benchmark Results

These numbers come from a real 15-component pipeline
(`tests/v2/integration/test_perf_barrier_scenarios.py`) that processes e-commerce
order data through 4 file inputs, 3 lookup joins, filters, aggregation, sort,
and a CSV output.

### Pipeline Structure

```
read_orders -----> map_cleanup -> filter_active -> map_product_enrich -> map_customer_enrich
read_products  --->                                  (lookup join)
read_customers --->                                                       (lookup join)
read_discounts --->                                  map_discount_enrich -> map_calculate
                                                        (lookup join)
                   filter_validate -> aggregate_summary -> sort_revenue -> select_final -> write_output
```

### Scenario Definitions

| Scenario | Barriers | Description |
|---|---|---|
| A | 1 (sink only) | All transforms are lazy native components. Single `.collect()` at the output sink. Maximum optimization. |
| B | 3 + sink = 4 | `filter_active`, `map_calculate`, and `filter_validate` are replaced with `python_code` components (which are always barriers). |
| C | 6 + sink = 7 | All of B, plus `map_cleanup`, `aggregate_summary`, and `sort_revenue` are also `python_code` barriers. |

All three scenarios produce **identical output** (verified by the equivalence test).

### 1M Rows (97 MB CSV files, 15-component pipeline with 3 lookup joins)

| Scenario | Barriers | Wall Time | Peak RAM (engine) |
|---|---|---|---|
| A -- Max Laziness | 1 | 92 ms | ~377 MB |
| B -- Moderate Barriers | 4 | 103 ms | ~159 MB |
| C -- Max Barriers | 7 | 105 ms | ~92 MB |

At 1M rows, all three scenarios complete in under 200 ms. The memory difference
is already dramatic: scenario C uses 4x less RAM than scenario A.

### 10M Rows (1 GB CSV files)

| Scenario | Barriers | Wall Time | Peak RAM (engine overhead) |
|---|---|---|---|
| A -- Max Laziness | 1 | 1.8 s | +2.8 GB |
| C -- Max Barriers | 7 | 1.5 s | +0.04 GB |

At 10M rows, scenario C actually runs **faster** than A because the system avoids
memory pressure. The engine overhead drops from 2.8 GB to 40 MB -- a 70x reduction.

### 100M Rows (10 GB CSV files, on 16 GB RAM machine)

| Scenario | Barriers | Wall Time | Notes |
|---|---|---|---|
| A -- Max Laziness | 1 | 55 s | Survived because Polars streaming optimizes internally, but RAM pressure is high |
| C -- Max Barriers | 7 | 107 s | Used minimal extra memory due to barrier chunking |

At 100M rows, scenario A is 2x faster but relies on the machine having enough RAM
for Polars to hold intermediate results. Scenario C is slower but predictable --
it will not OOM on a memory-constrained machine.

### Key Takeaway

For datasets under 1 GB, use fewer barriers -- speed dominates. For datasets
approaching or exceeding available RAM, add barriers to control memory.

---

## Performance Tuning Guide

### 1. Minimize Barriers for Speed (Default Strategy)

Use native V2 components whenever possible:

- `filter` instead of `python_code` with `input_df.filter(...)`.
- `map` with expressions instead of `python_code` with `input_df.with_columns(...)`.
- `aggregate` instead of `python_code` with `input_df.group_by(...)`.
- `sort` instead of `python_code` with `input_df.sort(...)`.

Every `python_code` or `python_dataframe` component is an automatic barrier.
Each barrier prevents Polars from optimizing across it.

### 2. Add Barriers for Memory Control on Large Datasets

When your dataset exceeds ~50% of available RAM, strategically introduce barriers.
The most effective placement:

- **After filters that significantly reduce row count.** A filter that drops 60%
  of rows means the barrier materializes only 40% of the data, and all downstream
  components work with the smaller dataset.
- **After the last join.** Join results are often the widest and most memory-hungry
  intermediate result. Materializing here frees the lookup tables.
- **Before aggregation.** If the group-by drastically reduces row count (e.g., from
  10M rows to 50 groups), the barrier after aggregation frees the pre-aggregation data.

To introduce a barrier without changing business logic, replace a native component
with its `python_code` equivalent:

```json
// Before (lazy)
{"id": "filter_active", "type": "filter", "config": {"condition": "status != 'CANCELLED'"}}

// After (barrier)
{"id": "filter_active", "type": "python_code", "config": {
    "code": "output_df = input_df.filter(pl.col('status') != 'CANCELLED')"
}}
```

### 3. Keep Lookup Tables Small Relative to Main Data

The map component performs joins lazily, but the joined result is wider (more
columns). If your lookup table is large, the join result balloons in memory when
eventually materialized.

Guidelines:
- Lookup tables should be <10% of the main data size.
- If a lookup table is large, filter it beforehand (separate pipeline or pre-step).
- Use `match_mode: "first"` or `match_mode: "last"` to deduplicate lookups before
  the join, preventing row multiplication.

### 4. Use Filters Early to Reduce Row Count Before Joins

Place filter components as early in the pipeline as possible:

```
// Good: filter before join
read_orders -> filter_active -> map_product_enrich (join)

// Bad: join before filter
read_orders -> map_product_enrich (join) -> filter_active
```

With the good ordering, Polars can push the filter predicate down to the scan,
reading fewer rows from disk. The join operates on a smaller dataset.

### 5. Avoid Unnecessary Python Components

Every `python_code` and `python_dataframe` component:
- Forces a `.collect()` (barrier).
- Breaks predicate and projection pushdown.
- Executes user code via `exec()`, which Polars cannot optimize.

Use Python components only when you need functionality that the expression DSL
and native components cannot provide (e.g., calling external APIs, complex
stateful logic, libraries not available through Polars expressions).

### 6. Prefer Parquet Over CSV for Large Files

`pl.scan_parquet()` supports predicate pushdown into the file format itself.
Polars can skip entire row groups that do not match filter conditions, reading
dramatically less data from disk. CSV does not support this -- Polars must read
every byte.

For files over 1 GB, converting to Parquet before processing can cut both I/O
time and memory by 50% or more.

### 7. Projection Pushdown: Only Select Columns You Need

If a downstream component only needs 5 of 20 columns, Polars can avoid reading
the other 15 from disk (with Parquet) or avoid allocating memory for them. This
works automatically within a lazy segment, but is broken by barriers. Place your
column selection (`select` component) before barriers when possible.

---

## Polars Internals That Matter

Understanding a few Polars internals explains why the V2 engine performs the way
it does.

### scan_csv Is Lazy

`pl.scan_csv("orders.csv")` does not read the file. It creates a `LazyFrame`
containing only the file path and schema. The file is read only when `.collect()`
is called (directly or by a barrier/sink). This is why the `FileInputDelimited`
source component (`src/v2/components/file/file_input_delimited.py`) has essentially
zero cost -- it just builds a scan plan.

### Query Plan Optimization

When `.collect()` is called on a `LazyFrame`, Polars runs an optimizer that:

1. **Predicate pushdown**: Moves filter conditions as close to the data source
   as possible. A filter after three joins can be pushed down to the initial scan.
2. **Projection pushdown**: Determines which columns are actually needed and
   avoids loading unused ones.
3. **Common subexpression elimination**: Detects duplicated computations and
   evaluates them once.
4. **Join ordering**: Optimizes the order of joins for performance.

Each barrier creates an optimization boundary. Polars can only optimize within
the lazy segment between barriers.

### Columnar Memory Layout

Polars stores data in Apache Arrow columnar format. This means:
- Each column is a contiguous memory buffer.
- Operations on single columns are cache-friendly.
- Adding or removing columns is cheap (pointer manipulation).
- Row-wise operations (like `python_row` components) are expensive because they
  cross column boundaries.

### Streaming Execution

For very large datasets, Polars can execute plans in streaming mode, processing
chunks of data rather than loading everything at once. This is why scenario A at
100M rows (10 GB) survives on a 16 GB machine even though the data theoretically
exceeds available RAM. However, streaming has limitations -- not all operations
support it, and complex joins may still require full materialization.

---

## Scaling Guidelines

Based on our benchmark data, here is what to expect at different scales.

### Small (< 1M rows / < 100 MB)

- Use scenario A (all lazy, minimize barriers).
- Wall time: sub-second.
- Memory: negligible.
- No tuning needed.

### Medium (1M - 10M rows / 100 MB - 1 GB)

- Start with scenario A.
- If memory usage is a concern (shared environment, containers with low limits),
  add 2-3 barriers after major filters and joins.
- Wall time: 1-5 seconds.
- Memory: 200 MB - 3 GB depending on barrier count.

### Large (10M - 100M rows / 1 - 10 GB)

- Use barriers aggressively (scenario C pattern).
- Place barriers after every filter that reduces data significantly.
- Use Parquet input format if possible.
- Wall time: 10s - 2 minutes.
- Memory: controlled by barrier placement. Can run in < 1 GB engine overhead
  with enough barriers.

### Very Large (> 100M rows / > 10 GB)

- Barriers are mandatory to avoid OOM.
- Consider splitting the job into multiple passes (iterate component).
- Pre-filter and pre-aggregate where possible.
- Use Parquet exclusively.
- Monitor with `resource.getrusage()` or `tracemalloc` (as the benchmark tests do).
- Wall time: minutes.
- Memory: depends entirely on barrier placement and data reduction ratios.

### Container / Kubernetes Considerations

When running in containers with memory limits:

- Set container memory to at least 2x the size of the largest single
  materialization (the biggest barrier segment).
- Add barriers so that no single `.collect()` call materializes more data than
  ~40% of the container memory limit.
- For a 4 GB container processing 2 GB of data with 3 joins, aim for 4-6 barriers
  to keep peak usage under 2 GB.

---

## When Things Break

### Out-of-Memory (OOM) During .collect()

**Symptom**: Process killed by OS or container runtime during execution of a
barrier or sink component.

**Cause**: The lazy segment before the barrier accumulates too many operations
(especially joins that multiply rows), and the single `.collect()` call tries to
materialize more data than available RAM.

**Fix**:
1. Identify the barrier component from the error traceback.
2. Add a barrier (python_code equivalent) midway through the lazy segment before it.
3. If the problem is a join that multiplies rows, check your join keys for
   duplicates. Use `match_mode: "first"` to prevent row multiplication.
4. Add an early filter to reduce row count before the join.

### Disk Space Exhaustion During Output

**Symptom**: `OSError` or `IOError` when writing output files.

**Cause**: Output CSV/Parquet files are large. A 100M row dataset with 20 columns
can produce a 10+ GB output file.

**Fix**:
1. Use Parquet output format (typically 3-5x smaller than CSV).
2. Filter or aggregate before the output to reduce row count.
3. Ensure sufficient disk space (at least 2x the expected output size to account
   for temporary files).

### Swap Thrashing

**Symptom**: Job runs but is extremely slow. System becomes unresponsive. Disk I/O
is constant.

**Cause**: Data exceeds physical RAM. The OS pages data to disk swap, and Polars
keeps accessing it, causing constant page faults.

**Fix**:
1. Add more barriers to reduce peak memory.
2. Reduce the dataset size with early filters.
3. Increase physical RAM or container memory limits.
4. As a diagnostic, run the job with `tracemalloc` enabled (as the benchmark tests
   do) to identify which component's materialization is the largest.

### Slow Performance Without OOM

**Symptom**: Job completes but takes much longer than expected.

**Cause**: Often too many barriers. Each barrier prevents Polars from optimizing
across it, and the overhead of `.collect()` + `.lazy()` re-wrapping adds up.

**Fix**:
1. Reduce barrier count. Replace `python_code` components with native equivalents.
2. Check for `python_row` components -- these iterate row-by-row and are orders
   of magnitude slower than vectorized operations.
3. Profile with the component stats in the execution result:
   ```python
   result = engine.execute()
   for comp_id, stats in result["components"].items():
       print(f"{comp_id}: {stats['duration_ms']:.1f}ms  barrier={stats.get('barrier')}")
   ```

### PythonCode Code Cache Growth

**Symptom**: Memory slowly grows across many job executions in a long-running process.

**Cause**: The `PythonCode` component has a class-level `_code_cache` dict that
stores compiled code objects. It clears at 100 entries, but in a long-running
service executing many different jobs, this can accumulate.

**Fix**: This is a known issue. For long-running services, restart the process
periodically, or clear the cache manually:
```python
from src.v2.components.python.python_code import PythonCode
PythonCode._code_cache.clear()
```

---

## Appendix: Source File Reference

| File | Relevance |
|---|---|
| `src/v2/execution/context.py` | `ExecutionContext` with `store_output()`, `decrement_ref()`, ref counting |
| `src/v2/engine.py` | `PyETLEngine._execute_component()` -- barrier detection, materialization, ref decrement loop |
| `src/v2/components/base.py` | `is_barrier` property on `SinkComponent` and `PythonComponent` |
| `src/v2/execution/dag.py` | `DAG.get_ref_counts()`, Kahn's topological sort |
| `src/v2/components/file/file_input_delimited.py` | `pl.scan_csv()` lazy source |
| `src/v2/components/file/file_output_delimited.py` | Sink barrier -- `.collect()` and write |
| `src/v2/components/python/python_code.py` | Python UDF barrier -- `.collect()` before `exec()` |
| `src/v2/components/transform/map_component.py` | Lookup joins, multiple outputs triggering barriers |
| `tests/v2/integration/test_perf_barrier_scenarios.py` | Benchmark test suite for all three scenarios |
