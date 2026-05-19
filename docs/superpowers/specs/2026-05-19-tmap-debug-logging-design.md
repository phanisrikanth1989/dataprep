# tMap debug logging — design

**Date:** 2026-05-19
**Branch:** `feature/engine-restructure`
**Scope:** Add observability to the tMap engine component. No behavior change.
**Predecessor work:** `2026-05-18-tmap-rewrite-design.md` (modular rewrite),
`2026-05-19-tmap-constant-key-design.md` (CONSTANT_KEY join strategy).

---

## 1. Problem

The tMap engine component is opaque when something goes wrong. The
manager's first production run of the CONSTANT_KEY fix routed every
row to `__errors__` (the Groovy script's inner-try/catch error
capture) and the engine logged nothing about it. The user could see
that the output was empty but had no way to discover:

- Which lookup was being joined when failures started
- What join strategy was selected for each lookup
- That `__errors__` was non-empty
- What exception each row hit (the Groovy stack traces are sitting in
  `errors_df["stackTraces"]` but are never logged)

The tMap package currently has exactly **two** log statements (both
`logger.warning` for cross-product size in `map_joins.py`). Nothing
in `map_component.py`, nothing in the compiled-script execution path,
nothing for join strategy decisions, nothing for `__errors__`.

This spec adds targeted INFO/WARNING/DEBUG logs so the next time a
job misbehaves, the user can see what happened from the standard log
stream — without enabling DEBUG, without attaching a debugger.

## 2. Goals

1. Make per-lookup join behavior visible at INFO level: which lookup,
   which strategy, which keys, row counts in/out, elapsed time.
2. Make `__errors__` visible at WARNING level whenever it's non-empty,
   with the first three error messages inline so the user sees the
   actual exception without enabling DEBUG.
3. Make main-flow filter, empty-lookup short-circuit, and script
   compile visible at INFO.
4. Expose full stack traces at DEBUG for the first three error rows.
5. Match the existing tMap logging style (`[%s]` bracket prefix with
   the component id, %-style format strings).

## 3. Non-goals

- No new logger configuration / no env-var gating. Standard Python
  logging config (e.g., `logging.basicConfig(level=logging.INFO)`)
  controls visibility.
- No per-row INFO/DEBUG logs (would flood the log stream for 1.5M-row
  jobs).
- No retroactive change to the two existing `map_joins.py` WARNINGs —
  they already follow the bracket + %-style pattern.
- No structured (JSON) logging — inconsistent with project style.
- No converter changes, no bridge changes, no JSON contract change.
- No fixture changes.

## 4. Logging style

All new log statements follow this shape, matching the existing
`map_joins.py` precedent extended with `self.id`:

```python
logger.<level>(
    "[%s] <message template with %s / %d / %.3f placeholders>",
    self.id, <arg1>, <arg2>, ...,
)
```

- `[%s]` first placeholder is always `self.id` (the tMap component id,
  e.g. `tMap_1`)
- %-style format strings, never f-strings (matches the existing
  `[tMap]` precedent and the executor-package convention)
- ASCII-only message bodies (no emojis, no unicode — RHEL log
  pipeline constraint per project convention)

Logger objects are module-level: `logger = logging.getLogger(__name__)`.
`map_component.py` does not currently have one — it must be added at
the top of the module.

## 5. Log surfaces — exact statements

### 5.1 Per-lookup join trace (INFO)

Two log lines per lookup: one just before the strategy dispatch, one
just after. The "before" line carries the full join configuration; the
"after" line carries the result row counts + elapsed wall time.

**Location:** `Map._process` in `map_component.py`, inside the
per-lookup loop currently spanning lines 112-157.

**Before-dispatch line:**

```python
logger.info(
    "[%s] lookup '%s' strategy=%s match=%s join=%s keys=[%s] "
    "main_rows=%d lookup_rows=%d filter_active=%s",
    self.id, lk.name, strategy.value, lk.matching_mode, lk.join_mode,
    ", ".join(f"{jk.lookup_column} <= {jk.expression}" for jk in lk.join_keys),
    len(joined_df), len(lookup_df), lk.activate_filter,
)
```

**After-dispatch line:**

```python
elapsed = time.perf_counter() - start
logger.info(
    "[%s] lookup '%s' joined: result_rows=%d rejects=%d elapsed=%.3fs",
    self.id, lk.name, len(joined_df),
    0 if rejects is None else len(rejects),
    elapsed,
)
```

The `start = time.perf_counter()` snapshot is taken immediately before
the strategy-dispatch `if`/`elif` chain. `time` must be imported at the
top of `map_component.py`.

**Example rendering:**

```
INFO:src.v1.engine.components.transform.map.map_component:[tMap_1] lookup 'row8' strategy=constant_key match=FIRST_MATCH join=LEFT_OUTER_JOIN keys=[name <= {{java}}context.SOURCE] main_rows=1500000 lookup_rows=42 filter_active=False
INFO:src.v1.engine.components.transform.map.map_component:[tMap_1] lookup 'row8' joined: result_rows=1500000 rejects=0 elapsed=0.123s
```

### 5.2 `__errors__` surfacing (WARNING + INFO + DEBUG)

**Location:** `Map._process` in `map_component.py`, immediately after
`errors_df = active_raw.pop("__errors__", None)` at line 201, **before**
the call to `route_rejects`.

**Three log statements, only emitted when `errors_df` carries non-zero
count:**

```python
if errors_df is not None:
    err_count = int(errors_df.get("count", 0))
    if err_count > 0:
        total_rows = len(joined_df)
        messages = errors_df.get("messages") or {}
        stack_traces = errors_df.get("stackTraces") or {}

        # Indices are dict keys; sort numerically and take first 3
        sorted_indices = sorted(messages.keys())[:3]
        samples = " | ".join(
            f"row {idx}: {messages[idx]}" for idx in sorted_indices
        )
        pct = (100.0 * err_count / total_rows) if total_rows else 0.0

        # WARNING -- always visible at default log levels
        logger.warning(
            "[%s] active script captured %d/%d rows in __errors__ "
            "(%.1f%%) -- first 3: %s",
            self.id, err_count, total_rows, pct, samples,
        )

        # INFO -- where the rows get routed
        catch_outputs = [o.name for o in cfg.outputs if o.catch_output_reject]
        if catch_outputs:
            logger.info(
                "[%s] __errors__ rows routed to catch_output_reject output(s): %s",
                self.id, ", ".join(catch_outputs),
            )
        else:
            logger.info(
                "[%s] __errors__ rows discarded "
                "(no catch_output_reject output configured)",
                self.id,
            )

        # DEBUG -- full stack traces for first 3
        for idx in sorted_indices:
            logger.debug(
                "[%s] stackTrace for row %d:\n%s",
                self.id, idx, stack_traces.get(idx, "<no stack>"),
            )
```

**Sample count is fixed at 3.** Bridge returns indices as int keys (per
the Arrow-emitted `Map<Integer, String>` -> Py4J -> Python dict
mapping). The sort is well-defined.

**Stack-trace fallback string** is `<no stack>` (ASCII) when an index
has a message but no stack trace -- guards against unexpected bridge
shapes.

### 5.3 Main filter row-count change (INFO)

**Location:** `Map._process` in `map_component.py`, around lines
97-104 where `cfg.main.filter` is applied. Add log immediately after the
filter is applied, only when `cfg.main.activate_filter and cfg.main.filter`
were both truthy.

```python
if cfg.main.activate_filter and cfg.main.filter:
    before_count = len(main_df)
    main_df = apply_filter(
        main_df, cfg.main.filter,
        self._bridge_eval_fn(), cfg.main.name, [],
    )
    logger.info(
        "[%s] main filter: %d -> %d rows (filter=%s)",
        self.id, before_count, len(main_df), cfg.main.filter,
    )
    if main_df.empty:
        return self._create_empty_outputs(cfg)
```

### 5.4 Empty/missing lookup short-circuit (INFO)

**Location:** `Map._process` in `map_component.py`, around lines
113-116 where the per-lookup loop short-circuits when `lookup_df is
None or lookup_df.empty`.

```python
for lk in cfg.lookups:
    lookup_df = inputs.get(lk.name)
    if lookup_df is None or lookup_df.empty:
        logger.info(
            "[%s] lookup '%s' skipped: %s",
            self.id, lk.name,
            "no input data" if lookup_df is None else "empty frame",
        )
        consumed_lookups.append((lk.name, self._lookup_schema(lk.name)))
        continue
```

### 5.5 Script compile (INFO)

**Location:** `Map._process` in `map_component.py`, immediately before
each `self.java_bridge.compile_tmap_script(...)` call. Two call sites:
one for the active script (around line 187), one for the reject script
(around line 222).

**Active script:**

```python
logger.info(
    "[%s] compiling active script (%d outputs)",
    self.id, sum(1 for o in cfg.outputs if not o.inner_join_reject),
)
self.java_bridge.compile_tmap_script(...)
```

**Reject script:**

```python
logger.info(
    "[%s] compiling reject script (%d outputs)",
    self.id, sum(1 for o in cfg.outputs if o.inner_join_reject),
)
self.java_bridge.compile_tmap_script(...)
```

## 6. Module-level changes

Top of `src/v1/engine/components/transform/map/map_component.py`:

```python
import logging
import time

logger = logging.getLogger(__name__)
```

`logging` is currently not imported; `time` is also not imported.

No other module-level changes.

## 7. Out of scope (deferred)

- **Per-row DEBUG/TRACE logs.** Too noisy for 1.5M-row jobs even at
  DEBUG. User explicitly said "if logging feels too much, I will move
  it to TRACE or DEBUG level later" -- a future move from INFO to a
  finer level is fine, but not on the first cut.
- **Strategy classification details.** The strategy enum value is
  already in the per-lookup log. The detailed *reason* (which helper
  rejected the expression) is debuggable from the classifier code; no
  log needed.
- **Bridge call logs.** `src/v1/java_bridge/bridge.py` already logs at
  DEBUG. Duplicating in `map_component.py` adds noise.
- **MethodTooLarge fix** (Script1.run > 65535 bytecode). Separate
  brainstorm and spec.
- **Performance instrumentation.** The `elapsed` field in §5.1 gives a
  rough wall-time per join. No richer profiling.

## 8. Test plan

Unit tests in `tests/v1/engine/components/transform/map/test_map_component.py`
using pytest's `caplog` fixture. All tests use the existing mock-bridge
pattern (no live JVM required).

**Required tests:**

1. `test_log_lookup_join_before_after` — assert two INFO log records
   fire per lookup join, with substrings:
   - Before: `"lookup 'row8' strategy="`, `"keys=["`, `"main_rows="`
   - After: `"lookup 'row8' joined: result_rows="`, `"elapsed="`

2. `test_log_lookup_skipped_when_lookup_df_none` — assert an INFO
   record with `"lookup 'row8' skipped: no input data"`.

3. `test_log_lookup_skipped_when_lookup_df_empty` — assert an INFO
   record with `"lookup 'row8' skipped: empty frame"`.

4. `test_log_main_filter_drops_rows` — config with `main.activate_filter=True`
   and a filter that drops half the rows. Assert INFO record:
   `"main filter: N -> M rows"`.

5. `test_log_compile_script_active` — assert INFO record:
   `"compiling active script (N outputs)"` per execute.

6. `test_log_compile_script_reject` — when any output has
   `inner_join_reject=True` AND there's a reject row source. Assert
   INFO record: `"compiling reject script (N outputs)"`.

7. `test_log_errors_warning_when_active_script_captures_errors` —
   craft a stub bridge that returns `__errors__` with count=2,
   messages={0: "msg0", 1: "msg1"}, stackTraces={...}. Assert
   WARNING record with substrings `"captured 2/N rows in __errors__"`,
   `"first 3: row 0: msg0 | row 1: msg1"`.

8. `test_log_errors_routing_with_catch_output` — when a
   `catch_output_reject=True` output is configured. Assert INFO
   record: `"routed to catch_output_reject output(s): rej"`.

9. `test_log_errors_routing_without_catch_output` — when no
   `catch_output_reject` output. Assert INFO record:
   `"discarded (no catch_output_reject output configured)"`.

10. `test_log_errors_debug_stack_traces` — set log level to DEBUG via
    `caplog.set_level(logging.DEBUG, logger=<name>)`. Assert one DEBUG
    record per captured-error index (capped at 3).

11. `test_no_error_log_when_errors_count_zero` — when `__errors__` is
    absent OR count=0, assert NO WARNING/INFO/DEBUG records for the
    `__errors__` surface (only the regular per-lookup logs fire).

Each test uses `caplog.set_level(logging.INFO, logger="src.v1.engine.components.transform.map.map_component")`
(or DEBUG for test 10) and asserts via `any(<substring> in r.message for r in caplog.records)`.

## 9. Backward compatibility

- No public API change.
- No JSON contract change.
- No log-format change for existing log statements (the two
  `map_joins.py` WARNINGs are untouched).
- Existing tests that don't inspect log output continue to pass.
- Coverage gate (95% per-module floor) must still pass. New code is in
  `map_component.py` which is currently 97.8% covered; the 11 new
  tests must keep that above 95%.

## 10. Files to touch

| File | Change |
|---|---|
| `src/v1/engine/components/transform/map/map_component.py` | Add `import logging`, `import time`, `logger = logging.getLogger(__name__)`; add ~8 log statements at the 5 surfaces described in §5 |
| `tests/v1/engine/components/transform/map/test_map_component.py` | Append 11 unit tests for the new log surfaces |

No converter changes. No bridge changes. No Java changes. No `.item`
or JSON fixture changes.
