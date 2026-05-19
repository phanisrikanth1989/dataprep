# tMap CONSTANT_KEY join strategy — design

**Date:** 2026-05-19
**Branch:** `feature/engine-restructure`
**Scope:** Engine-side fix to the tMap `Map` component. No converter change. No
JSON contract change.
**Predecessor spec:** [`2026-05-18-tmap-rewrite-design.md`](2026-05-18-tmap-rewrite-design.md)
(the full tMap rewrite). This document amends Section 6 of that spec.

---

## 1. Problem

When a tMap lookup's join key has a left-side expression that references
**only** Talend context variables, the `globalMap`, literals, or routine
calls — i.e., **no main-flow or prior-lookup column reference** — the
current `Map` component crashes with `KeyError` at `pandas.merge` time.

Worked example (one lookup out of 7–8 in a real production job):

```json
{
  "name": "row8",
  "matching_mode": "FIRST_MATCH",
  "lookup_mode": "LOAD_ONCE",
  "join_keys": [{
    "lookup_column": "name",
    "expression": "{{java}}context.SOURCE",
    "type": "str",
    "nullable": true,
    "operator": "="
  }],
  "join_mode": "LEFT_OUTER_JOIN",
  "filter": "",
  "activate_filter": false
}
```

The intended semantics: for **every** main row, the value to match against
`row8.name` is the runtime value of `context.SOURCE` — a constant for the
entire batch. Talend uses this pattern routinely (environment-specific
config lookups, tenant resolution, "current run header" attachment, etc.).

### Failure path today

`classify_join_strategy` in `src/v1/engine/components/transform/map/map_joins.py:41-53`:

```python
if all(_is_simple_col_ref(_strip_marker(jk.expression)) for jk in lk.join_keys):
    return JoinStrategy.SIMPLE
```

`_strip_marker("{{java}}context.SOURCE")` → `"context.SOURCE"`. The regex
`^([a-zA-Z_]\w*)\.([a-zA-Z_]\w*)$` matches it (`context` looks like a table
name, `SOURCE` looks like a column name). The lookup is **misclassified as
SIMPLE**.

In `join_simple_equality` (map_joins.py:108-189) we then try to use
`"context.SOURCE"` (or bare `"SOURCE"`) as a left-merge column. Neither
exists in `joined_df`. `pd.merge` raises `KeyError: 'context.SOURCE'`.

### Scope of the bug

Any join key whose expression is of shape `<identifier>.<identifier>` and
references Java-side bindings rather than a row column will hit this:

- `{{java}}context.<ANY_VAR>` (every Talend context variable)
- `{{java}}globalMap.<KEY>` written without `.get(...)`
- Bare `context.SOURCE` (no marker) — same regex hit

Manager flagged this as part of a broader "failing miserably" report on
the tMap rewrite. This issue alone is the root cause of at least the
lookup-crash subset of that report.

### What we lost

The legacy `src/v1/engine/components/transform/map.py` (now deleted,
recoverable from `main` branch history) had `_is_context_only_expression`
+ `_perform_cartesian_join` (legacy lines 231-260, 517-557). It correctly
detected this case, evaluated the expression **once**, pre-filtered the
lookup, and cross-joined. **This regression was introduced by the rewrite
when the new classifier was authored without an equivalent path.** The
Phase 8 legacy-test triage deleted whichever tests would have caught it.

---

## 2. Goals

1. **Restore parity** with the legacy behavior for this pattern, which
   itself matches Talend's runtime output. Talend evaluates the
   expression per row (no optimization), but produces the same result set
   we'll produce via the optimized path — every main row sees the same
   matched lookup row (or null for unmatched).
2. **Avoid wasted per-row work.** For 1.5M main rows, the constant
   expression must be evaluated **once**, not 1.5M times — neither across
   the bridge nor inside the Groovy script.
3. **Keep the strategy boundaries disjoint.** New code lives alongside
   existing strategies in `map_joins.py`. No bolt-ons to FILTER_AS_MATCH
   or SIMPLE.

## 3. Non-goals

- No converter change. The JSON contract is unchanged.
- No new bridge method. We reuse `execute_batch_one_time_expressions`
  (see §6 for justification).
- No optimization for partial constant-ness (a lookup with *some*
  constant keys and *some* row-dependent keys still routes to COMPUTED).
- No reach into MethodTooLarge / script-splitting (separate phase).
- No changes to reject routing, output generation, type fidelity,
  variables, or any other tMap subsystem.

## 4. Approach overview

Add a new `JoinStrategy.CONSTANT_KEY` that activates when **every** join
key expression is main-row-independent. Execution path:

1. Evaluate all join key expressions in **one** batch bridge call.
2. Filter the lookup DataFrame in pandas using the resolved constants:
   `(lookup_df[k1] == v1) & (lookup_df[k2] == v2) & ...`.
3. Apply matching-mode dedup to the filtered lookup.
4. Apply the lookup's own `filter` (if `activate_filter=true`) to the
   filtered lookup.
5. Cross-join the filtered lookup onto every main row.
6. Honor `LEFT_OUTER_JOIN` vs `INNER_JOIN` rules for the empty-filtered
   case.

Total bridge crossings per CONSTANT_KEY lookup: **1**. Total Groovy
evaluations per join key: **1**.

## 5. Detection

### 5.1 Main-row-independence helper

New private helper in `map_joins.py`:

```python
def _is_main_row_independent(
    expr: str,
    main_name: str,
    prior_lookup_names: list[str],
) -> bool:
    """Return True if expr references no main / prior-lookup / Var column.

    Strips {{java}} marker. Scans for <table>.<col> references using the
    SAME quote-aware tokenizer pattern as _substitute_row_refs (so string
    literals containing "row1.foo" are not treated as references). A
    reference whose <table> is in {main_name, *prior_lookup_names, "Var"}
    counts as a main-row dependency.

    References to "context.*", "globalMap.*", routine calls, and bare
    identifiers do NOT count. Literals do not count.
    """
```

**Reuses** the existing `_ROW_REF_PATTERN` regex
(`map_joins.py:610-612`) and the quoted-range avoidance logic from
`_substitute_row_refs` (`map_joins.py:615-685`). No third
expression-parser introduced.

### 5.2 Classifier signature change

`classify_join_strategy(lk)` becomes:

```python
def classify_join_strategy(
    lk: LookupCfg,
    main_name: str,
    prior_lookup_names: list[str],
) -> JoinStrategy:
```

Decision tree (in order; first match wins):

1. `lk.lookup_mode == "RELOAD_AT_EACH_ROW"` → `RELOAD`
2. `not lk.join_keys` → `FILTER_AS_MATCH`
3. `all(_is_main_row_independent(jk.expression, ...) for jk in lk.join_keys)`
   → `CONSTANT_KEY` ← **new**
4. `all(not jk.expression.startswith(_JAVA_MARKER) and _is_simple_col_ref(jk.expression) for jk in lk.join_keys)`
   → `SIMPLE` ← **rule tightened**: marker presence now forbids SIMPLE
5. otherwise → `COMPUTED`

The rule-4 tightening is necessary as a **secondary fix**. Without it,
a `{{java}}row1.col` (marker over a real column ref) would route to
SIMPLE — the SIMPLE path then merges on a column named `"row1.col"`
which may or may not exist depending on whether main is named `row1`.
Treating the marker as a forcing flag for COMPUTED is the safer
contract: "if the converter marked it as Java, evaluate it through the
bridge." This is documented in section §9.2 of the predecessor spec.

### 5.3 Caller update

`Map._process` in `map_component.py:117` calls
`classify_join_strategy(lk)`. Update call site to pass `main_name` and
`prior_lookup_names`:

```python
strategy = classify_join_strategy(
    lk,
    main_name=cfg.main.name,
    prior_lookup_names=[n for n, _ in consumed_lookups],
)
```

## 6. Bridge API — reuse, don't add

Original plan (Q2 in the brainstorm) called for a dedicated
`execute_constant_expression` method on the bridge. On survey, the
existing `JavaBridge.execute_batch_one_time_expressions` already does
exactly this:

- Takes `expressions: dict[str, str]` (N expressions in one call)
- Returns `dict[str, Any]` of resolved values
- Pushes context + globalMap as part of the call
- Used by `base_component.py:389`, `xml_map.py:582`, `java_component.py`,
  `row_generator.py:122`. Covered by bridge integration tests.

**Decision change**: reuse `execute_batch_one_time_expressions`. No new
bridge method. Smaller surface, well-trodden code path, zero Java-side
change.

(Approval point for the user — this contradicts Q2 of the brainstorm.)

## 7. Execution

New function in `map_joins.py`:

```python
def join_constant_key(
    joined_df: pd.DataFrame,
    lookup_df: pd.DataFrame,
    lk: LookupCfg,
    main_name: str,
    prior_lookups: list[str],
    constant_eval_fn: Callable[[dict[str, str]], dict[str, Any]],
    lookup_filter_fn: Callable | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame | None]:
```

`constant_eval_fn` is injected by the orchestrator and wraps
`JavaBridge.execute_batch_one_time_expressions` with context+globalMap
sync (parallel to the existing `_bridge_eval_fn` closure pattern in
`map_component.py:286-301`).

`lookup_filter_fn` is optional — when the lookup has an `activate_filter`
filter expression, the orchestrator applies it to `lookup_df` **before**
passing it in (existing pattern at `map_component.py:125-132`). So this
parameter is reserved for future use and not required for the v1 of
this change.

### 7.1 Step-by-step

```
1. Strip {{java}} markers from each join key expression.
2. Build expressions dict: {"__ck_0__": expr0, "__ck_1__": expr1, ...}
3. results = constant_eval_fn(expressions)
   Single bridge call. Errors prefixed with "{{ERROR}}" by the bridge
   surface as ComponentExecutionError (same as legacy).
4. Build the pandas filter mask:
   mask = True
   for i, jk in enumerate(lk.join_keys):
       val = results[f"__ck_{i}__"]
       if val is None:
           mask = False     # null key never matches; short-circuit
           break
       mask &= (lookup_df[jk.lookup_column] == val)
   filtered = lookup_df[mask]
5. Apply matching mode dedup:
   filtered = _apply_matching_mode(filtered, key_cols, lk.matching_mode)
6. Prefix lookup columns: lk.name + "." + col
7. If filtered.empty:
   if lk.join_mode == "INNER_JOIN":
       return empty_with_schema, joined_df.copy()  # all main rows reject
   else:  # LEFT_OUTER_JOIN
       # Attach all-NaN lookup columns to every main row
       result = joined_df.copy()
       for col in prefixed_lookup_cols:
           result[col] = np.nan
       return result, None
8. Else (filtered has rows):
   # Cross-join main x filtered. For UNIQUE/FIRST/LAST_MATCH, filtered
   # has at most 1 row after dedup, so cross-join is broadcast.
   merged = pd.merge(joined_df, filtered_prefixed, how="cross")
   return merged, None
```

### 7.2 Behavioral notes

- **FIRST_MATCH on a constant key**: the lookup is filtered to rows
  matching the constant, then `_apply_matching_mode` keeps the first
  occurrence of each `lookup_column` value. For a single-key
  `name == "acme"` filter, that's one row at most. Every main row gets
  that one row attached.
- **ALL_MATCHES on a constant key**: the lookup is filtered (no dedup).
  Every main row gets every matching lookup row → `main_n * matched_n`
  result rows. Honors Talend semantics.
- **Multi-key constant join**: all keys are evaluated in the single
  batch call. Filter mask is the AND of per-key equality. Empty result
  follows the same LEFT_OUTER vs INNER rules.
- **Null evaluation result**: matches Talend's `HashMap.get(null)`
  silently-no-match. LEFT_OUTER fills nulls; INNER rejects all main.
- **Bridge error**: bridge returns `"{{ERROR}}..."` on a per-expression
  basis. We treat this the same way the rest of the engine does — raise
  `ComponentExecutionError` with `component_id` set. (`die_on_error` is
  honored by the engine layer, not here.)

### 7.3 Size guard

Worst-case row count: `main_n * matched_n`. For broadcast
(FIRST/UNIQUE/LAST_MATCH), `matched_n <= 1` → no growth. For
ALL_MATCHES with a permissive constant filter, growth is bounded by
the number of lookup rows matching the constant — typically small for
context-driven filters. We reuse the FILTER_AS_MATCH guard thresholds
(`_WARN_RESULT_ROWS = 10M`, `_FAIL_RESULT_ROWS = 100M`) for
consistency: WARN at 10M predicted output rows, raise
`ComponentExecutionError` at 100M.

## 8. Edge cases — explicit table

| Case | Behavior |
|---|---|
| All join keys reference `context.*` only | CONSTANT_KEY |
| Mix of `context.*` and `row1.col` keys | COMPUTED (any row dependency disables) |
| Single join key, expression `"literal_string"` | CONSTANT_KEY (no row refs) |
| Single join key, expression `5 + 5` | CONSTANT_KEY |
| Single join key, expression `Numeric.sequence("s1", 1, 1)` | CONSTANT_KEY (no row.col ref) |
| Single join key, expression bare `context.X` (no marker) | CONSTANT_KEY (same rules) |
| Lookup empty | LEFT_OUTER preserves main with null lookup cols; INNER rejects all main. (Existing pre-check at `map_component.py:113-116` short-circuits before strategy dispatch.) |
| Eval result null for any key | Short-circuit to empty filtered → LEFT_OUTER/INNER as above |
| Bridge call fails | `ComponentExecutionError` raised; engine handles per `die_on_error` |
| `activate_filter=true` on lookup | Orchestrator pre-filters `lookup_df` before calling `join_constant_key` (existing pattern) |
| `enable_auto_convert_type` | No new interaction. Pandas equality is used for the filter mask — same comparison semantics as the SIMPLE and COMPUTED strategies use today (no implicit type coercion across kinds, e.g. `int(123) != str("123")`). If a future ticket addresses cross-type coercion, it applies uniformly to all three strategies. |

## 9. Test plan

### 9.1 Unit tests (no bridge)

In `tests/v1/engine/components/transform/map/test_map_joins.py` (existing
file from rewrite). New tests:

- `test_classify_constant_key_pure_context_var` — single key
  `{{java}}context.SOURCE` → `CONSTANT_KEY`
- `test_classify_constant_key_bare_context_var` — bare `context.SOURCE`
  (no marker) → `CONSTANT_KEY`
- `test_classify_constant_key_globalmap_ref` — `{{java}}globalMap.X` →
  `CONSTANT_KEY`
- `test_classify_constant_key_literal` — `{{java}}"const_str"` →
  `CONSTANT_KEY`
- `test_classify_constant_key_mixed_keys_routes_to_computed` — one
  constant key + one `row1.col` key → `COMPUTED`
- `test_classify_marker_over_row_col_routes_to_computed` — secondary fix
  validation: `{{java}}row1.col` → `COMPUTED`, not `SIMPLE`
- `test_classify_main_row_dep_in_quoted_string_still_constant` — expr
  `"row1.foo"` (literal string containing what looks like a row ref) →
  `CONSTANT_KEY` (quote-awareness)
- `test_join_constant_key_left_outer_match` — broadcast happy path
- `test_join_constant_key_left_outer_no_match` — empty filtered →
  every main row preserved with nulls
- `test_join_constant_key_inner_no_match` — empty filtered → every
  main row in rejects
- `test_join_constant_key_first_match_dedup` — multi-row filtered lookup,
  FIRST_MATCH keeps first
- `test_join_constant_key_all_matches_cross` — multi-row filtered
  lookup, ALL_MATCHES produces main_n × matched_n
- `test_join_constant_key_multi_key_and` — two constant keys, AND filter
- `test_join_constant_key_null_eval_no_match` — bridge returns None →
  LEFT_OUTER nulls, INNER rejects
- `test_join_constant_key_size_guard` — synthetic large output triggers
  WARN at 10M, raises at 100M
- `test_join_constant_key_bridge_error_raises` — bridge returns
  `{{ERROR}}...` → `ComponentExecutionError`

### 9.2 Integration tests (live bridge, `@pytest.mark.java`)

In `tests/v1/engine/components/transform/map/test_map_integration.py`:

- `test_constant_key_context_source_end_to_end` — JSON config matching
  the worked example in §1 + a real context resolve via `ContextManager`
  + assertion on output row count and lookup-column values
- `test_constant_key_inner_join_no_match_rejects` — same shape, INNER
  join, context value doesn't match any lookup row → empty main output,
  inner_join_reject output gets all main rows
- `test_constant_key_one_bridge_call_only` — instrument bridge call
  count, assert exactly 1 call for the join (excluding script
  compile/exec)

### 9.3 Synthetic Talend `.item` regression fixture

User confirmed (Q3): no existing `.item` for this pattern. We'll
synthesize one for parity testing.

Create `tests/talend_xml_samples/Job_tMap_constant_key_lookup.item`
modeled on the existing `Job_tMap_*.item` fixtures, containing:
- One tFixedFlowInput as main (3 rows, columns `id` and `desc`)
- One tFixedFlowInput as lookup (6 rows, columns `name` and `info`)
- One tMap with the configuration from §1 (LOAD_ONCE, FIRST_MATCH,
  LEFT_OUTER, join key `lookup.name == context.SOURCE`)
- One tLogRow output
- A context variable `SOURCE` set to a value present in lookup rows

Run through `python -m src.converters.talend_to_v1.converter` to get
the canonical JSON, commit both the `.item` and the converted JSON
to `tests/talend_xml_samples/converted_jsons/Job_tMap_constant_key_lookup.json`.

Expected output is asserted programmatically inside the integration
test (no separate `.expected.csv` — that convention does not yet exist
in this repo, and one job's worth of expected rows is small enough to
inline as a `pd.DataFrame` literal next to the assertion).

### 9.4 Coverage gate impact

Coverage gate (95% per-module floor, `pyproject.toml [tool.coverage.run]`)
must continue to pass. `map_joins.py` line count grows by ~80 lines for
the new helper + new function. New tests must cover every branch of
`join_constant_key` and `_is_main_row_independent`.

## 10. Backward compatibility

- No JSON contract change.
- No bridge API change.
- No public Map / BaseComponent API change.
- Lookups previously misclassified as SIMPLE that crashed now route to
  CONSTANT_KEY and succeed. **This is a behavior change** — jobs that
  previously errored will now produce results. The results match the
  legacy `map.py` cartesian-prefilter behavior and Talend's per-row
  HashMap probe.
- The classifier signature gains two required parameters. There is only
  one caller (`Map._process`). External callers do not exist (`map_joins`
  is package-internal).

## 11. Out of scope (deferred)

- **MethodTooLarge** error reported separately. Lives in
  `map_compiled_script.py`. Own brainstorm, own spec, own plan.
- Optimization for partial constant-ness (some keys constant, some not).
  COMPUTED is correct, not slow enough to fix now.
- Caching of `_is_main_row_independent` results across multiple
  invocations on the same config — `_validate_config` is called once
  per execute, and classification is O(N_lookups × N_keys) regex scans.
  Not a hot path.

## 12. Open questions

None blocking. The Q2 deviation (reuse vs add bridge method) is the
only point requiring user confirmation; flagged in §6.

## 13. Files to touch (summary)

| File | Change |
|---|---|
| `src/v1/engine/components/transform/map/map_joins.py` | Add `_is_main_row_independent`, `JoinStrategy.CONSTANT_KEY`, `join_constant_key`; update `classify_join_strategy` signature + rule 4 marker tightening |
| `src/v1/engine/components/transform/map/map_component.py` | Update `classify_join_strategy` call site + new dispatch branch + wire `constant_eval_fn` closure |
| `tests/v1/engine/components/transform/map/test_map_joins.py` | New unit tests (§9.1) |
| `tests/v1/engine/components/transform/map/test_map_integration.py` | New integration tests (§9.2) |
| `tests/talend_xml_samples/Job_tMap_constant_key_lookup.item` | New synthesized `.item` |
| `tests/talend_xml_samples/converted_jsons/Job_tMap_constant_key_lookup.json` | Converted output from `.item` |

No converter change. No bridge change. No Java change.
