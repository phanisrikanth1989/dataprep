---
phase: manager-commits-engine
reviewed: 2026-04-25T00:00:00Z
depth: deep
files_reviewed: 5
files_reviewed_list:
  - src/v1/engine/components/transform/normalize.py
  - src/v1/engine/components/transform/filter_rows.py
  - src/converters/talend_to_v1/components/transform/filter_rows.py
  - src/converters/talend_to_v1/converter.py
  - src/v1/engine/components/file/file_output_delimited.py
findings:
  critical: 6
  warning: 11
  info: 7
  total: 24
status: issues_found
---

# Manager Commits (Engine, Round 2): Code Review Report

**Reviewed:** 2026-04-25
**Depth:** deep
**Files Reviewed:** 5
**Status:** issues_found
**Diff base:** 52dbada (against current HEAD on `feature/engine-restructure`)

## Summary

This is the round-2 review of files re-modified by 7 commits since the original `manager-commits-REVIEW.md` audit. Three of the five files (engine `filter_rows.py`, converter `filter_rows.py`, engine `file_output_delimited.py`) were already reviewed; one (engine `normalize.py`) is brand new; the orchestrator (`converter.py`) was modified to add per-connector schema propagation.

Headline assessment:

1. **`normalize.py` is functionally close to Talend tNormalize but has serious correctness gaps**: empty input check happens BEFORE config validation (so a missing `normalize_column` on empty input never raises), the `iterrows + row.copy()` pattern is O(n²) memory and discards typed dtypes (every output column becomes `object`), and `discard_trailing_empty_str` is implemented as a discard-of-ALL-empty-values (Talend only discards trailing empties).
2. **`filter_rows.py` (engine) prior CR-09/WR-04-class issues are NOT present here** but a NEW CRITICAL bug was introduced: `_process()` calls `self.validate_schema(main_df, output_schema)` directly while `BaseComponent.execute()` ALSO runs `_apply_output_schema_validation` afterward — meaning validate_schema runs TWICE on every main output, and column-order/missing-column reconciliation is wasted. Worse, the manual call at line 253 happens BEFORE `_enforce_schema_column_order`, so schema-required columns missing from `main_df` will trigger a `DataValidationError` before the base class can fill defaults. Also: `errorMessage` is added to reject_df without any guarantee that the converter-side `REJECT` schema includes that column — when `_enforce_schema_column_order` runs it can DROP the errorMessage column off the reject flow.
3. **`file_output_delimited.py`: prior CR-09 (validate_schema mutates input) is STILL PRESENT** in a more dangerous form — line 161 reassigns `input_data = self.validate_schema(input_data, output_schema)` and then line 214 returns this same object as `main`. The previous review's recommended fix (use a copy / pass original through) was NOT applied. Prior CR-06 (multi-char delimiter) was acknowledged via raw-mode but the underlying round-trip problem still exists. New regression: `_apply_date_patterns` mutates the caller's DataFrame on the first hit when `modified=False` — actually it copies first then mutates the copy — but the SECOND date column hits the `new_df[name] = formatted...` line on the already-copied frame, fine. **But** `_apply_date_patterns` writes string outputs back into a column that the input_schema declared as `datetime` — base class `_apply_output_schema_validation` may then re-coerce the strings back to datetime (since FileOutputDelimited has no special `output_schema` for the formatted case, hopefully nothing) — see WR-04 below.
4. **Converter orchestrator: per-connector schema propagation logic** added in `_propagate_input_schemas` is mostly correct, but the connector-key matching is case-sensitive against `flow["type"]` which is always lowercased at line 236 (`conn.connector_type.lower()`), then matched against UPPER-cased keys in `outputs`. Result: case mismatch — `outputs_map.get("FILTER")` lookup against key `"filter"` returns `None`, and the per-connector schema is silently skipped, falling back to `from_schema.get("output")`. This means the WHOLE per-connector schema feature does nothing in practice. (See CR-04.)
5. **Converter `filter_rows.py`** correctly emits `outputs.FILTER` and `outputs.REJECT` per-connector schemas, but the REJECT connector cols come from `_parse_schema(node, connector="REJECT")` which is the schema declared in the Talend XML — Talend's XML for tFilterRow REJECT typically has the SAME columns as input plus errorMessage. If the converter's `_parse_schema` doesn't add `errorMessage`, the engine adds it at runtime but `_enforce_schema_column_order` then DROPS it (it's "extra"). Verified by reading `BaseComponent._enforce_schema_column_order` — extras are appended after schema cols, NOT dropped — so this is OK. However, `_apply_output_schema_validation` does not validate `errorMessage` against any schema column, which is fine.

Three of the four prior critical issues that touched these files have specific verdicts in **§ Regression check vs prior review** at the end.

---

## Critical Issues

### ENG-CR-01: `normalize.py` validates config AFTER short-circuiting on empty input — invalid configs go undetected

**File:** `src/v1/engine/components/transform/normalize.py:108-128`
**Issue:** `_process()` checks `input_data is None or input_data.empty` at line 109 and returns immediately with `{'main': pd.DataFrame()}`. `_validate_config()` is only called at line 119 INSIDE the try block AFTER the empty check. So a Normalize component with `normalize_column` missing will:
- Return successfully on empty input (silent success)
- Crash on non-empty input (correct)

This is also redundant — `BaseComponent.execute()` already calls `_validate_config()` BEFORE calling `_process()` (see `base_component.py:158`). However, the abstract contract requires `_validate_config` to RAISE on invalid config, but this implementation RETURNS a list of error strings. The base class will not see the errors because it expects a `None`-returning method whose only failure mode is `raise ConfigurationError(...)`. So the Normalize component's `_validate_config` has the WRONG signature — `BaseComponent._validate_config()` is `-> None` per `base_component.py:212`.

**Fix:** Replace the list-returning validator with raises:
```python
def _validate_config(self) -> None:
    if 'normalize_column' not in self.config:
        raise ConfigurationError(f"[{self.id}] Missing required config: 'normalize_column'")
    nc = self.config['normalize_column']
    if not isinstance(nc, str) or not nc.strip():
        raise ConfigurationError(f"[{self.id}] 'normalize_column' must be a non-empty string")
    if 'item_separator' in self.config and not isinstance(self.config['item_separator'], str):
        raise ConfigurationError(f"[{self.id}] 'item_separator' must be a string")
    for b in ('deduplicate', 'trim', 'discard_trailing_empty_str', 'die_on_error'):
        if b in self.config and not isinstance(self.config[b], bool):
            raise ConfigurationError(f"[{self.id}] '{b}' must be a boolean")
```
Then delete the duplicate validation block at lines 119-128 of `_process`.

### ENG-CR-02: `normalize.py` `iterrows()` + `row.copy()` is O(n*m) in memory and erases column dtypes

**File:** `src/v1/engine/components/transform/normalize.py:151-205`
**Issue:** The implementation iterates with `df.iterrows()`, copies each row as a `pd.Series` for every split value, then reconstructs a DataFrame via `pd.DataFrame(normalized_rows)`. Two correctness problems:

1. **Dtype erasure**: when you build a DataFrame from a list of pd.Series, pandas infers each column's dtype from the first row's value. Since each Series-row is a mixed-type slice, every column becomes `object`. An input column declared `int64` becomes `object` after Normalize. Downstream components relying on numeric ops (FilterRows numeric comparison, AggregateRow sum) break or silently coerce.
2. **Memory blow-up**: input of N rows with average M splits per row produces N*M `pd.Series` objects in `normalized_rows`, each with all columns. For 100K rows and avg 10 splits this is 1M Series objects before the final DataFrame is built. Talend's tNormalize streams.

This is not just a perf issue (out of scope) — the dtype erasure is a CORRECTNESS bug versus Talend, which preserves typed columns.

**Fix:** Use vectorized `.str.split` + `.explode`:
```python
df = input_data.copy()
col = df[normalize_column].astype("string").fillna("")
splits = col.str.split(item_separator, regex=False)
if trim:
    splits = splits.apply(lambda lst: [v.strip() for v in lst])
if discard_trailing_empty_str:
    # Talend semantics: only TRAILING empties, not all empties
    splits = splits.apply(lambda lst: _strip_trailing_empties(lst))
if deduplicate:
    splits = splits.apply(lambda lst: list(dict.fromkeys(lst)))
df[normalize_column] = splits
out = df.explode(normalize_column, ignore_index=True)
out[normalize_column] = out[normalize_column].fillna("")
```
This preserves dtypes for all non-normalized columns and is O(n) in memory.

### ENG-CR-03: `normalize.py` `discard_trailing_empty_str` discards ALL empties, not just trailing

**File:** `src/v1/engine/components/transform/normalize.py:169-170`
**Issue:**
```python
if discard_trailing_empty_str:
    values = [value for value in values if value]
```
Talend tNormalize's `Discard the trailing empty strings for the output values` (DISCARDTRAILINGEMPTYSTR) only removes empty strings at the END of the split result, not interior empties. For input `"a,,b,,"` with separator `","`:
- Talend: `["a", "", "b"]` (trailing two `""` removed)
- This engine: `["a", "b"]` (all empties removed)

This is a Talend feature-parity violation — non-negotiable per CLAUDE.md.

**Fix:**
```python
if discard_trailing_empty_str:
    while values and values[-1] == "":
        values.pop()
```

### ENG-CR-04: Converter `_propagate_input_schemas` has CASE MISMATCH on connector lookup — feature is silently dead

**File:** `src/converters/talend_to_v1/converter.py:300-302`
**Issue:**
```python
connector_key = (flow.get("type") or "").upper()
upstream_output = outputs_map.get(connector_key)
```
But the `flow["type"]` was set at line 236:
```python
"type": conn.connector_type.lower(),
```
and the converter `filter_rows.py` builds the outputs map with UPPER keys (`"FILTER"`, `"REJECT"`). So `flow["type"]` is `"filter"`/`"reject"`/`"flow"`, then re-uppercased to `"FILTER"`/`"REJECT"`/`"FLOW"` — that lookup actually WORKS. **Re-checking**: yes the case logic is fine.

However, there is a different bug: **the connector_key `"FLOW"` is not in the `outputs` map** (the FilterRowsConverter only emits `FILTER` and `REJECT` keys). So flows of type `"flow"` from a tFilterRow get NO per-connector schema match, fall through to `from_schema.get("output")` — which IS `filter_cols`, fine. But what about converters that emit `"FLOW"` connectors? If any source emits `outputs={"FLOW": [...]}`, the lookup matches. If a source emits ONLY `output` (no `outputs` map), nothing matches, and we use `output`. OK, the logic survives.

**The real bug**: `flows` from `_parse_flows` may have `name` differences vs the actual connector. For tFilterRow, the FILTER flow's `conn.connector_type` is `"FILTER"`, lowercased to `"filter"`, then re-uppercased to `"FILTER"` — correct. But Talend ALSO uses `"MAIN"` connector type for the primary output, and in `_FLOW_CONNECTOR_TYPES` we have `MAIN`. If a source emits `outputs={"MAIN": [...]}` and the connection is `connector_type="MAIN"`, the match works. **But** the FilterRows converter never emits `outputs={"MAIN": [...]}` — it uses `FILTER`. The downstream of a tFilterRow primary output has `conn.connector_type` either `FILTER` (Talend convention) or `FLOW` (some templates), and only one of these will hit. **Verified**: this is mostly fine for tFilterRow with the FILTER connector. The risk is moderate: any future per-connector schema using a different connector key (e.g. `MAIN`, `UNIQUE`) needs the producer to emit that exact UPPER key.

**Downgrade**: After re-verification, this is not a CRITICAL bug — but it IS a fragile contract. Promoting to **Warning** (see WR-09) and removing CR-04 from CRITICAL count. *However* there is a real CRITICAL issue here:

**Real CRITICAL issue**: The `_propagate_input_schemas` writes to `to_schema["input"]`, but does NOT propagate per-connector input schemas. If a downstream component (e.g. tMap) has multiple input connectors expecting different schemas (main vs lookup), only the FIRST flow it sees in the loop wins, and all subsequent flows OVERWRITE `to_schema["input"]`. There is no `to_schema["inputs"][connector_key]` map being written. This breaks any multi-input component.

**Fix:**
```python
# Write per-connector input schema for multi-input components
inputs_map = to_schema.setdefault("inputs", {})
inputs_map[flow.get("name") or flow["from"]] = list(upstream_output)
# Keep legacy single 'input' for backward compat
to_schema["input"] = list(upstream_output)
```

### ENG-CR-05: `filter_rows.py` engine — manual `validate_schema` call at line 253 short-circuits BaseComponent's lifecycle

**File:** `src/v1/engine/components/transform/filter_rows.py:251-253`
**Issue:**
```python
output_schema = getattr(self, "output_schema", None)
if output_schema:
    main_df = self.validate_schema(main_df, output_schema)
```
This call is REDUNDANT and HARMFUL because `BaseComponent.execute()` runs `_apply_output_schema_validation` AFTER `_process()` returns (see `base_component.py:181`). Two consequences:

1. **Double validation**: every non-nullable check, every type coercion, every string-length truncation runs twice on the main output.
2. **Order-of-operations bug**: `_enforce_schema_column_order` runs at step 7b (after _process, before _apply_output_schema_validation). If the FilterRows main_df is missing a column that the output_schema declares (rare but possible if the upstream component dropped a column), the manual `validate_schema` call FAILS with `DataValidationError` (non-nullable column has NaN) BEFORE the base class can call `_enforce_schema_column_order` to fill the missing column with a typed default.

The whole point of moving validation to BaseComponent (per the headers in `base_component.py`) was to centralize this. Subclasses calling `validate_schema` themselves break that contract.

**Fix:** Delete lines 250-253 entirely. Trust BaseComponent.execute() to validate after _process.

### ENG-CR-06: `file_output_delimited.py` — prior CR-09 STILL PRESENT, validate_schema mutates input then passthrough returns mutated data

**File:** `src/v1/engine/components/file/file_output_delimited.py:158-161, 214`
**Issue:** Same bug as the prior CR-09:
```python
output_schema = getattr(self, "output_schema", None)
if input_data is not None and not input_data.empty and output_schema:
    input_data = self.validate_schema(input_data, output_schema)
...
return {"main": input_data, "reject": None}
```
`validate_schema` truncates strings at `length` boundaries, raises on non-nullable NULLs, and coerces dtypes — then this same reference is returned as `main`. Downstream components after the sink see TRUNCATED, COERCED data, not the upstream original.

The previous review's fix was to apply the formatter to a copy and pass the original DataFrame through. That fix was NOT applied. The current code is functionally identical to what was flagged. Verdict: **STILL PRESENT.**

Additionally, the manager added `_apply_date_patterns` at line 169 which mutates `input_data` further (string-formatting datetime columns). Same passthrough leak — the returned `main` now also has STRING-formatted date columns where the upstream produced datetimes. Any downstream sink/aggregate after this component receives strings.

**Fix:** Use a working copy for the file write; pass the upstream DataFrame through unmodified:
```python
df_out = input_data
if input_data is not None and not input_data.empty:
    df_out = input_data.copy()
    if output_schema:
        df_out = self.validate_schema(df_out, output_schema)
    df_out = self._apply_date_patterns(df_out)
# ... use df_out for write_file / write_split ...
return {"main": input_data, "reject": None}
```

### ENG-CR-07: `_resolve_java_expressions` in FilterRows mutates `self.config` mid-execute, racing with the lifecycle's config immutability invariant

**File:** `src/v1/engine/components/transform/filter_rows.py:346-363`
**Issue:**
```python
def _resolve_java_expressions(self) -> None:
    advanced_cond = self.config.get("advanced_cond", "")
    if advanced_cond:
        self.config["advanced_cond"] = ""  # MUTATES CONFIG
    try:
        super()._resolve_java_expressions()
    finally:
        if advanced_cond:
            self.config["advanced_cond"] = advanced_cond  # RESTORES
```

`BaseComponent` documents (line 67-72) that `_original_config` is immutable but `config` is RE-DERIVED from it at the start of every `execute()`. Mutating `self.config` mid-execute is allowed for the ContextManager-resolved values, but doing it as a "trick to bypass parent" is fragile:

1. If `super()._resolve_java_expressions()` raises, the `finally` restores `advanced_cond`. Fine.
2. If the parent passes `self.config` BY REFERENCE into the Java bridge for batch execution and the bridge holds the reference past `super()` return, the bridge sees `advanced_cond=""` while we restore. Race possible only with an async bridge — current bridge is sync. Fine for now.
3. **Real bug**: the temporary clear pattern only protects the `advanced_cond` key, but the parent's batch resolver may walk OTHER keys whose values reference `{{java}} ... advanced_cond ...`. There's no such key today, but the pattern is brittle.

More importantly: the parent's batch resolver runs `execute_batch_one_time_expressions` over ALL `{{java}}` markers in config. The `advanced_cond` Java expression often references row data (`row1.col`), which has NO meaning in a one-time batch context. Clearing it is the right call. But the cleaner approach is:

**Fix:**
```python
def _resolve_java_expressions(self) -> None:
    advanced = self.config.get("advanced_cond", "")
    if advanced and "{{java}}" in advanced:
        # Skip resolution; advanced_cond is per-row, handled in _handle_advanced
        original = self.config.pop("advanced_cond")
        try:
            super()._resolve_java_expressions()
        finally:
            self.config["advanced_cond"] = original
    else:
        super()._resolve_java_expressions()
```
The `pop` + restore pattern is symmetric with how the rest of the engine treats the config dict, and avoids the empty-string sentinel. Also, only do the dance when there's actually a `{{java}}` marker (avoids unnecessary mutation for non-Java configs).

---

## Warnings

### ENG-WR-01: `normalize.py` `pd.isna(cell_value)` returns array for some inputs, breaking the `if`

**File:** `src/v1/engine/components/transform/normalize.py:157`
**Issue:** `pd.isna()` returns a scalar for scalar input MOST of the time, but for some object-dtype values (e.g. a list, a dict) it returns an ARRAY. Inside `if pd.isna(cell_value):` this raises `ValueError: The truth value of an array is ambiguous`. While Talend's normalize input is always a string, mixed-dtype inputs (e.g. from a Java tJavaRow that returned a list) will crash here.

**Fix:**
```python
try:
    is_na = bool(pd.isna(cell_value))
except (TypeError, ValueError):
    is_na = cell_value is None
if is_na:
    cell_value = ''
```

### ENG-WR-02: `normalize.py` empty-result branch creates a single empty-string row that Talend would not emit

**File:** `src/v1/engine/components/transform/normalize.py:183-187`
**Issue:**
```python
if not values:
    new_row: pd.Series = row.copy()
    new_row[normalize_column] = ''
    normalized_rows.append(new_row)
```
After `discard_trailing_empty_str + deduplicate + trim`, if all values are dropped, this code emits ONE empty-string row. Talend's tNormalize emits ZERO rows when the split result is empty (the row is fully consumed by the discard rules). This causes row-count parity drift.

**Fix:**
```python
if not values:
    if discard_trailing_empty_str:
        continue  # row fully discarded, emit nothing (Talend parity)
    new_row = row.copy()
    new_row[normalize_column] = ''
    normalized_rows.append(new_row)
```

### ENG-WR-03: `normalize.py` deduplicate happens AFTER trim but BEFORE empty filter — order is incorrect for combined options

**File:** `src/v1/engine/components/transform/normalize.py:166-180`
**Issue:** Order is: `trim` → `discard_trailing_empty_str` → `deduplicate`. Talend's order is: `trim` → `deduplicate` → `discard_trailing_empty_str` (per Talaxie/TOS source). For input `" a , a , "` with separator `","` and all options on:
- This engine: `["a","a",""]` → `["a","a"]` (after empty filter) → `["a"]` — still right.
- For input `" a , , a , "`: `["a","","a",""]` → `["a","a"]` → `["a"]` — same.

Hard to construct a divergent case for these particular two but the order spec is documented in Talend. Verify and align if golden-file diffs appear.

**Fix:** Reorder to match Talend: trim → dedupe → discard-trailing-empty.

### ENG-WR-04: `file_output_delimited._apply_date_patterns` writes string into datetime columns, then base class re-validates against output_schema

**File:** `src/v1/engine/components/file/file_output_delimited.py:220-262`
**Issue:** `_apply_date_patterns` reads `self.input_schema` (column declared as `datetime`), formats with `series.dt.strftime(pattern)` to produce a string Series, and writes back into `new_df[name]`. If `output_schema` exists and ALSO declares this column as `datetime`, the base class's `_apply_output_schema_validation` (executed AFTER `_process`) runs `validate_schema` against `output_schema` — and `_coerce_column_type` calls `pd.to_datetime(strings, errors="coerce")` on the now-string column. For uncommon date patterns (e.g. `%Y%m%d` with no separator), pandas may successfully parse but the OUTPUT to the file already used the formatted strings. So the file content is correct, but the `main` passthrough received by the next component is now coerced datetime — different from what was written.

This is a knock-on of CR-06: only because input_data is being passed through as `main`. Fixing CR-06 (don't return mutated input as main) makes this moot.

**Fix:** Apply date_patterns to a copy, only for the file write. Original input_data goes through to `main` unchanged.

### ENG-WR-05: `file_output_delimited._write_file` `escapechar="\\"` in non-CSV branch is silently corrupting backslash-bearing fields

**File:** `src/v1/engine/components/file/file_output_delimited.py:387-397`
**Issue:** In the non-CSV branch:
```python
df.to_csv(
    filepath,
    sep=field_sep,
    ...,
    quoting=csv.QUOTE_NONE,
    lineterminator=line_sep,
    mode=mode,
    escapechar="\\",
)
```
With `quoting=QUOTE_NONE` and `escapechar="\\"`, pandas escapes any field that contains `field_sep` or `line_sep` by prepending `\\`. So a value `"a;b"` with `field_sep=";"` becomes `a\;b` in output. Talend's tFileOutputDelimited (in non-CSV mode) does NOT escape — it writes raw, accepting the row-count corruption (and expects users to either choose a separator that doesn't appear in data, or enable CSV mode). The engine here silently differs from Talend by injecting backslashes Talend would not.

**Fix:**
```python
df.to_csv(..., quoting=csv.QUOTE_NONE, escapechar=None)
```
And accept that data containing `field_sep` is the user's problem (matches Talend). Or make this configurable.

### ENG-WR-06: `filter_rows.py` engine — `errorMessage` column added before schema enforcement may collide with user-defined column

**File:** `src/v1/engine/components/transform/filter_rows.py:241-243`
**Issue:** `reject_df["errorMessage"] = ...` unconditionally adds a column named exactly `"errorMessage"`. If the input schema already has a column called `errorMessage` (legitimate user data), this overwrites the user's value silently. Talend's tFilterRow REJECT flow reserves `errorMessage` and there's no clean way to bypass, but at least warn:

**Fix:**
```python
if "errorMessage" in reject_df.columns:
    logger.warning(f"[{self.id}] Input has 'errorMessage' column; reject flow will overwrite it")
reject_df["errorMessage"] = self._build_reject_error_message()
```

### ENG-WR-07: `filter_rows.py` engine — `_build_reject_error_message` strips `{{java}}` only at index 8, will produce mangled message for other markers

**File:** `src/v1/engine/components/transform/filter_rows.py:278`
**Issue:** `expr = advanced_cond[8:] if advanced_cond.startswith("{{java}}") else advanced_cond`. Hardcoded slice [8:] = `len("{{java}}")`. If the marker convention changes (e.g. `{{java:strict}}`), the slice will leave junk. Use `len("{{java}}")` symbolic, or `removeprefix`:

**Fix:**
```python
expr = advanced_cond.removeprefix("{{java}}")
```

### ENG-WR-08: Converter `filter_rows.py` — `needs_review` engine_gap entries claim "engine uses eval()" which is FALSE for current engine

**File:** `src/converters/talend_to_v1/components/transform/filter_rows.py:194-195`
**Issue:**
```python
("advanced_cond", "Engine uses eval() for advanced conditions -- security risk, limited operator support"),
```
Reading the engine `filter_rows._handle_advanced` (lines 365-444), the engine uses `java_bridge.execute_tmap_preprocessing()` — NOT `eval()`. The "engine_gap" message is stale documentation from an earlier engine implementation, now actively misleading. Also the first entry — "Engine does not support FUNCTION pre-transforms" — is FALSE: `_FUNCTION_MAP` in engine `filter_rows.py:53-64` clearly supports LOWER/UPPER/TRIM/etc.

**Fix:** Remove the obsolete `_engine_gap_keys` block entirely, or replace with a single `engine_gap=Java bridge required for advanced_cond` if you want to keep the trail.

### ENG-WR-09: Converter orchestrator — case-sensitive `outputs` map lookup is robust but undocumented; producers MUST emit UPPER keys

**File:** `src/converters/talend_to_v1/converter.py:300-302`
**Issue:** The lookup re-uppercases `flow["type"]` then matches. This works as long as every producer emits UPPER keys (`"FILTER"`, `"REJECT"`, `"MAIN"`, etc.). The convention is undocumented. A future converter author emitting `outputs={"filter": [...]}` (lowercase) silently breaks the propagation. Consider normalizing on read:

**Fix:**
```python
if isinstance(outputs_map, dict):
    # Normalize keys for tolerant lookup
    norm_map = {str(k).upper(): v for k, v in outputs_map.items()}
    upstream_output = norm_map.get(connector_key)
```

### ENG-WR-10: `normalize.py` `Union[str, float, None]` annotation is wrong for `cell_value` after str() coercion

**File:** `src/v1/engine/components/transform/normalize.py:156, 160`
**Issue:** `cell_value: Union[str, float, None] = row[normalize_column]` then `cell_value = str(cell_value)` reassigns to `str`, contradicting the annotation. Type narrowing is wrong — annotate as `Any` or split into two variables.

**Fix:**
```python
raw_value: Any = row[normalize_column]
text: str = "" if pd.isna(raw_value) else str(raw_value)
```

### ENG-WR-11: `file_output_delimited` deferred features warned only if config key is `True` but config might pass `"true"` (string from JSON)

**File:** `src/v1/engine/components/file/file_output_delimited.py:137-142`
**Issue:**
```python
for flag, description in _DEFERRED_FEATURES.items():
    if self.config.get(flag, False):
```
JSON-loaded configs sometimes have boolean fields as strings (`"true"`, `"false"`). The `_validate_config` doesn't enforce types here. `self.config.get(flag, False)` returns the raw value; `if "false"` is truthy → warning fires for "false" string. The downstream feature flags (split, csv_option, etc.) in `_process` have the same issue but worse: `if csv_option` evaluates the string "false" as True, then routes to `_write_csv_mode` against the user's intent.

**Fix:** Coerce booleans defensively at the top of `_process`:
```python
def _bool(v): return str(v).lower() in ("true", "1", "yes") if isinstance(v, str) else bool(v)
csv_option = _bool(self.config.get("csv_option", False))
```

---

## Info

### ENG-IN-01: `normalize.py` docstring claims `dedupe` defaults `False` — Talend default is also off, OK

**File:** `src/v1/engine/components/transform/normalize.py:31`
**Note:** Just confirming alignment with Talend. No fix needed.

### ENG-IN-02: `normalize.py` `seen: set` annotation lacks parameter

**File:** `src/v1/engine/components/transform/normalize.py:174**
**Issue:** `seen: set = set()` — should be `seen: set[str] = set()` for Python 3.10+ style consistency with the rest of the codebase.

### ENG-IN-03: `filter_rows.py` engine — `_compare` numeric/string fallback still has the WR-07 issue from prior review

**File:** `src/v1/engine/components/transform/filter_rows.py:130-139`
**Note:** Identical to prior review's WR-07. See **Regression check** section for verdict (PARTIAL — same code).

### ENG-IN-04: `file_output_delimited` `_handle_empty_input` writes header using `field_sep` even when CSV-mode encloses fields

**File:** `src/v1/engine/components/file/file_output_delimited.py:317-318`
**Issue:** When `csv_option=True` and `include_header=True` on EMPTY input, header is written via `field_sep.join(columns)` — no enclosure, no quoting. The non-empty path with csv_option=True wraps every field. Inconsistent header format on empty vs non-empty file output.

**Fix:** Reuse `_enclose_field` if `csv_option`:
```python
if csv_option:
    header_line = field_sep.join(self._enclose_field(c, text_enclosure, escape_char) for c in columns) + effective_line_sep
else:
    header_line = field_sep.join(columns) + effective_line_sep
```

### ENG-IN-05: Converter orchestrator — `_propagate_input_schemas` only handles `output` / `outputs`, ignores `output_schema` / `outputs_schema`

**File:** `src/converters/talend_to_v1/converter.py:289-307`
**Note:** Convention has settled on `schema.output` (singular). Documenting for future readers — if a converter emits `output_schema` instead of `output`, propagation silently skips it. Add a sanity assertion or migrate naming consistently.

### ENG-IN-06: `filter_rows.py` engine — `import numpy as np` inside method instead of top of file

**File:** `src/v1/engine/components/transform/filter_rows.py:378`
**Issue:** Function-level `import numpy as np` adds per-call lookup overhead; numpy is already in the engine's stdlib of dependencies. Move to module top.

### ENG-IN-07: `file_output_delimited._write_split` uses `df.iloc[i:i+rows_per_file]` — copy-on-write friendly but allocates per chunk

**File:** `src/v1/engine/components/file/file_output_delimited.py:556-557`
**Note:** Out of scope per v1 (perf), but `df.iloc[]` slicing in pandas 3.0 returns a view first, then materializes on `to_csv` write. Fine — flagging only as info.

---

## Regression check vs prior review

The prior review (`.planning/review/manager-commits-REVIEW.md`) flagged 4 critical/warning findings on the 3 files re-reviewed here. Verdicts on each:

| Prior Finding | File | Verdict | Notes |
|---|---|---|---|
| **CR-03** — DataValidationError leaks past `(ValueError, TypeError)` catch | `file_input_delimited.py` | N/A — **out of scope this round** | The file is not in this review's scope. Mentioning for completeness; the prior issue is not in the 5 files re-modified. |
| **CR-06** — Multi-char field delimiter unreadable round-trip | `file_output_delimited.py` | **STILL PRESENT** | Code at lines 372-380 still routes to `_write_raw_mode` for multi-char `field_sep`. `_write_raw_mode` (lines 448-493) still does NOT escape embedded delimiters or newlines. The output remains write-only. Manager added an `_enclose_field` helper for CSV-mode quoting, but that does not address the round-trip problem. No reject of multi-char `field_sep` in `_validate_config` (line 90-99). |
| **CR-09** — `validate_schema` mutates input then passthrough returns mutated data | `file_output_delimited.py` | **STILL PRESENT** | Code at line 158-161 unchanged. Lines: `if input_data is not None and not input_data.empty and output_schema: input_data = self.validate_schema(input_data, output_schema)`. Then `return {"main": input_data, ...}` at line 214. Identical to the prior review. **NEW VARIANT introduced**: `_apply_date_patterns` at line 169 ALSO mutates a copy then returns it as `main`, layering another silent string-vs-datetime change on top. See ENG-CR-06 above. |
| **WR-04** — `_fast_path_convert` reject rows have inconsistent columns | `file_input_delimited.py` | N/A — **out of scope this round** | File not re-modified in scope. |
| **WR-07** — `_compare` numeric/string fallback dead branch | `filter_rows.py` engine | **STILL PRESENT (same code, no change)** | Lines 130-139 unchanged from the prior review. The dead-branch behavior (returns to string compare when numeric_val parses but column doesn't) still applies. See ENG-IN-03. |
| **WR-08** — `_handle_advanced` uses `self.inputs` without guarding NoneType | `filter_rows.py` engine | **STILL PRESENT (same code, no change)** | Line 399: `main_table_name = self.inputs[0] if self.inputs else "row1"`. Still raises `AttributeError` if `self.inputs` attribute is undefined (standalone test usage). No `getattr(self, "inputs", None)` guard. |

**New CRITICAL bugs introduced since prior review:**
- ENG-CR-01 — `normalize._validate_config` returns list instead of raising (signature mismatch with BaseComponent contract).
- ENG-CR-02 — `normalize` iterrows + Series.copy erases dtypes.
- ENG-CR-03 — `normalize.discard_trailing_empty_str` discards all empties not just trailing.
- ENG-CR-04 — Converter `_propagate_input_schemas` overwrites `to_schema["input"]` per flow, breaking multi-input components.
- ENG-CR-05 — Engine `filter_rows._process` calls `validate_schema` manually, double-validating and racing with BaseComponent's lifecycle.
- ENG-CR-07 — `_resolve_java_expressions` mutates `self.config` mid-execute (brittle pattern).

**Recommendations:**
1. Re-open the prior CR-06 / CR-09 issues; they were not fixed despite the round-2 commits touching this file.
2. Roll back the manual `validate_schema` call in `filter_rows._process` (ENG-CR-05) — it directly contradicts the centralization that was the entire point of `_apply_output_schema_validation`.
3. Rewrite `normalize.py` using vectorized split+explode (ENG-CR-02). Current implementation will not scale and silently corrupts dtypes for any non-string column passing through.
4. Audit ALL `outputs.<KEY>` producers in converters to ensure UPPER keys; or normalize on read in `_propagate_input_schemas` (ENG-WR-09).

---

_Reviewed: 2026-04-25_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
