---
phase: manager-commits
reviewed: 2026-04-18T11:33:56Z
depth: deep
files_reviewed: 20
files_reviewed_list:
  - src/converters/talend_to_v1/components/context/context_load.py
  - src/converters/talend_to_v1/components/transform/filter_rows.py
  - src/v1/engine/base_component.py
  - src/v1/engine/components/aggregate/aggregate_row.py
  - src/v1/engine/components/context/context_load.py
  - src/v1/engine/components/file/file_input_delimited.py
  - src/v1/engine/components/file/file_output_delimited.py
  - src/v1/engine/components/transform/filter_rows.py
  - src/v1/java_bridge/java/pom.xml
  - src/v1/java_bridge/java/src/main/java/routines/DataOperation.java
  - src/v1/java_bridge/java/src/main/java/routines/Mathematical.java
  - src/v1/java_bridge/java/src/main/java/routines/Numeric.java
  - src/v1/java_bridge/java/src/main/java/routines/Relational.java
  - src/v1/java_bridge/java/src/main/java/routines/StringHandling.java
  - src/v1/java_bridge/java/src/main/java/routines/TalendDataGenerator.java
  - src/v1/java_bridge/java/src/main/java/routines/TalendDate.java
  - src/v1/java_bridge/java/src/main/java/routines/TalendString.java
  - src/v1/java_bridge/java/src/main/java/routines/TalendStringUtil.java
  - tests/v1/engine/components/file/test_file_input_delimited.py
  - tests/v1/engine/components/file/test_file_output_delimited.py
findings:
  critical: 9
  warning: 17
  info: 12
  total: 38
status: issues_found
---

# Manager Commits: Code Review Report

**Reviewed:** 2026-04-18T11:33:56Z
**Depth:** deep
**Files Reviewed:** 20
**Status:** issues_found

## Summary

The manager's commits introduce several load-bearing changes in `base_component.py` (schema-column ordering, output-schema validation on reject, string-length truncation, stats double-count guard), meaningful fixes to `file_input_delimited.py` / `file_output_delimited.py` (multi-char delimiter, empty-output-with-header, CSV quote-all), and a large Talend routines library addition. Most additions are structurally sound, but several systemic bugs affect correctness:

1. **BaseComponent now applies `validate_schema` to the reject DataFrame** — this will raise `DataValidationError` on non-nullable NULLs in the reject stream. Reject rows often contain the NULLs that caused them to be rejected in the first place. This will break reject flows across every component that uses a non-nullable `reject_schema`.
2. **`_apply_decimal_precision` assumes `precision` is an int** — `Decimal(10) ** -precision` crashes with `TypeError` if precision is a string (common in JSON config).
3. **`file_input_delimited` raises `DataValidationError` but the caller catches only `(ValueError, TypeError)`** — in three places this means the exception escapes the per-row/per-column conversion boundary and kills the whole component.
4. **Java routines library is packaged with Maven but depends on an external `org.example.recon_etl.code:routines` artifact via a Windows-absolute local repo path** — this will not resolve outside the original developer's machine; Maven build is broken on macOS/Linux.
5. **`aggregate_row` treats `list_object` and `union` the same as `list`**, silently producing a joined string instead of a Python list (for `list_object`) and without deduplication (for `union`). This diverges from Talend.
6. **Three security-relevant issues** in Java routines: `StringHandling.CHANGE` (regex from user config, no escape), `TalendDataGenerator` (insecure `RandomUtils.random()` for potentially-PII fake data), and `Numeric.random`/`Mathematical.RND` (non-SecureRandom). These are low-to-medium risk in the ETL context but worth flagging.
7. **Multi-char field delimiter path in `file_output_delimited` uses `_write_raw_mode`** but does NOT re-escape embedded delimiters or newlines even when `csv_option=True`. Output is ambiguous and cannot be round-tripped by `_read_standard_mode` (which requires single-char).

Performance issues are not in scope; several O(n^2) patterns (e.g., `LTRIM`/`RTRIM` substring-walk, `context_load` row-by-row loop) are noted as Info only.

---

## Critical Issues

### CR-01: `validate_schema` applied to reject DataFrame raises `DataValidationError` on expected NULLs

**File:** `src/v1/engine/base_component.py:683-696`
**Issue:** `_apply_output_schema_validation` now runs `validate_schema` against the `reject` DataFrame using `reject_schema`. `validate_schema` raises `DataValidationError` when any non-nullable column contains NaN (`base_component.py:737-740`). A reject row, by definition, is a row that failed validation — it often has NULLs exactly where the error happened (e.g. a bad int column is coerced to NaN). Applying the same non-nullable strictness to reject flows will turn every component that has a non-nullable `reject_schema` into a crash-on-first-reject bomb. In `file_input_delimited`, every reject row has `errorCode`/`errorMessage` appended plus the raw string fields as strings — if the `reject_schema` was derived from the typed `output_schema`, the reject flow will now crash.

**Fix:** Skip nullable-violation checks (and ideally skip type coercion) on the reject path, or force the reject schema to be all-nullable before applying:
```python
def _apply_output_schema_validation(self, result: dict) -> dict:
    output_schema = getattr(self, "output_schema", None)
    if output_schema:
        main_df = result.get("main")
        if main_df is not None and isinstance(main_df, pd.DataFrame) and not main_df.empty:
            result["main"] = self.validate_schema(main_df, output_schema)

    reject_schema = getattr(self, "reject_schema", None)
    if reject_schema:
        reject_df = result.get("reject")
        if reject_df is not None and isinstance(reject_df, pd.DataFrame) and not reject_df.empty:
            # Reject rows are failed data; relax nullability for validation-only
            relaxed = [{**col, "nullable": True} for col in reject_schema]
            result["reject"] = self.validate_schema(reject_df, relaxed)
    return result
```

### CR-02: `_apply_decimal_precision` crashes on string precision

**File:** `src/v1/engine/base_component.py:780`
**Issue:** `quantize_str = Decimal(10) ** -precision` requires `precision` to be an `int`. JSON-loaded configs frequently contain numeric schema fields as strings (`"precision": "4"`). When that happens, `-precision` raises `TypeError: bad operand type for unary -: 'str'` inside `validate_schema`, which is wrapped by `BaseComponent.execute()` into `ComponentExecutionError` — breaking every component with a Decimal column in its schema.

**Fix:** Coerce at the top of the function:
```python
@staticmethod
def _apply_decimal_precision(df, col_name, precision):
    from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
    try:
        precision = int(precision)
    except (TypeError, ValueError):
        logger.warning(f"Invalid precision {precision!r} for column {col_name!r}; skipping")
        return df
    quantize_str = Decimal(10) ** -precision
    ...
```

### CR-03: `DataValidationError` leaks through `(ValueError, TypeError)` catch in fast path

**File:** `src/v1/engine/components/file/file_input_delimited.py:605, 661`
**Issue:** `_fast_path_convert` catches `(ValueError, TypeError)` at line 605 when a vectorized conversion fails, intending to fall back to per-row conversion. Inside `_vectorized_convert` (line 661), unmapped bool values raise `DataValidationError`. `DataValidationError` extends `ETLError`, **not** `ValueError` (see `src/v1/engine/exceptions.py:19`). So the `except (ValueError, TypeError)` catch does NOT catch it — the error escapes to `BaseComponent.execute()`, which wraps it in `ComponentExecutionError`. The whole component dies instead of rejecting the bad rows. Same bug at lines 773 and 612 where `_convert_value` raises `DataValidationError` inside a `try/except (ValueError, TypeError)` block.

**Fix:** Either raise `ValueError` from `_vectorized_convert` / `_convert_value` (since these are per-row type errors, not structural validation errors), or expand every catch to `(ValueError, TypeError, DataValidationError)`. Preferred — raise `ValueError` since that is what `pd.to_numeric` raises and matches semantic intent:
```python
# line 661
raise ValueError("Unmapped bool values found")
# line 856
raise ValueError(f"Empty value for non-nullable column")
```

### CR-04: Maven repo path is a Windows absolute path — build broken on Linux/macOS

**File:** `src/v1/java_bridge/java/pom.xml:57-62`
**Issue:**
```xml
<repository>
    <id>talend-local</id>
    <url>file:///C:/Softwares/TOS_DI-20211109_1610-V8.0.1/.../repository</url>
</repository>
```
RHEL production and macOS developer machines have no `C:/Softwares/...`. Maven resolution of `org.example.recon_etl.code:routines:8.0.1` will fail, and the shade plugin will not produce `java-bridge-with-dependencies.jar`. This silently breaks the Java bridge on any non-Windows environment. The routines files that reference `routines.system.RandomUtils`, `routines.system.FastDateParser`, `routines.system.LocaleProvider`, `routines.system.TalendTimestampWithTZ` will not compile without this artifact.

**Fix:** Remove the platform-specific path and host the Talend `routines` artifact either (a) in an internal Nexus/Artifactory reachable from RHEL, (b) as a vendored JAR inside the repo with `<scope>system</scope>` + `<systemPath>${project.basedir}/libs/...</systemPath>`, or (c) copy the needed helper classes into the codebase and delete the dependency. Also remove the `<repositories>` block entirely once resolved — leaving machine-local file:// URLs in a checked-in POM will bite any new developer.

### CR-05: `aggregate_row` `list_object` returns joined string, not a list

**File:** `src/v1/engine/components/aggregate/aggregate_row.py:138-144`
**Issue:**
```python
if func_name in ("list", "list_object", "union"):
    ...
    return lambda x: list_delimiter.join(x.astype(str))
```
Talend semantics:
- `list` -> delimiter-joined string (this code matches).
- `list_object` -> **Object** (`java.util.List`), not a string. Downstream components that expect a list (e.g. `tNormalize`, `tJavaRow` scripts) break.
- `union` -> distinct union of values, deduplicated.

All three are currently collapsed into a delimited string. Talend parity is violated. The `logger.warning` for `union` acknowledges the gap but still returns wrong output silently.

**Fix:**
```python
if func_name == "list":
    return (lambda x: list_delimiter.join(x.dropna().astype(str))) if ignore_null \
        else (lambda x: list_delimiter.join(x.astype(str)))
if func_name == "list_object":
    return (lambda x: x.dropna().tolist()) if ignore_null else (lambda x: x.tolist())
if func_name == "union":
    # distinct + joined
    return (lambda x: list_delimiter.join(sorted(set(x.dropna().astype(str))))) if ignore_null \
        else (lambda x: list_delimiter.join(sorted(set(x.astype(str)))))
```

### CR-06: Multi-char field delimiter path in `_write_raw_mode` produces unambiguous-but-unreadable output

**File:** `src/v1/engine/components/file/file_output_delimited.py:316-324, 392-437`
**Issue:** When `field_sep` is longer than one character, `_write_file` routes to `_write_raw_mode`. Even when `csv_option=True`, this path only wraps each field in `text_enclosure` (`_enclose_field`) — it does **not** escape the multi-char delimiter if it happens to appear inside a field, nor does it escape embedded newlines. The written file cannot be round-tripped by the matching `_read_standard_mode` (pandas `read_csv` rejects multi-char `sep` with an error), and cannot be parsed by `_read_csv_mode` (csv.reader also rejects multi-char delimiters). So the output is write-only.

Additionally, when `csv_option=False` and `field_sep` is multi-char, fields containing the delimiter substring silently corrupt the row count. Example: `field_sep="||"`, value="a||b" produces output "a||b" which deserializes to 3 fields.

**Fix:** Either:
- Reject multi-char `field_sep` in `_validate_config` with a clear `ConfigurationError` (this matches Python csv module semantics and is honest about the limitation), OR
- When `csv_option=True`, always enclose fields AND escape any embedded `text_enclosure`/`field_sep`/newline, AND update `file_input_delimited` to accept the resulting file (currently it cannot). This is a substantial feature, not a drive-by fix.

### CR-07: `Numeric.INT` throws `NumberFormatException` on non-integer input — not Talend-compatible

**File:** `src/v1/java_bridge/java/src/main/java/routines/Mathematical.java:226-228`
**Issue:**
```java
public static int INT(String e) {
    return Integer.valueOf(e);
}
```
Talend's routines.Mathematical.INT accepts strings like `"100.5"` and returns `100` (truncation). `Integer.valueOf("100.5")` throws `NumberFormatException`. Any job converted from Talend that uses `Mathematical.INT("100.5")` will now crash where it previously worked. Similar issue in `NUM` (line 343-348) — matches `\\d+` only; rejects negative numbers, decimals, and anything Talend accepts.

**Fix:**
```java
public static int INT(String e) {
    if (e == null) return 0;
    return (int) Double.parseDouble(e.trim());
}
public static int NUM(String e) {
    if (e == null) return 0;
    try { Double.parseDouble(e); return 1; } catch (NumberFormatException ex) { return 0; }
}
```

### CR-08: `TalendDate.TO_DATE` / `parseDate` wrap `ParseException` in unchecked `RuntimeException`, crashing the bridge

**File:** `src/v1/java_bridge/java/src/main/java/routines/TalendDate.java:494-495, 958-960, 1043-1045`
**Issue:**
```java
throw new RuntimeException(pattern + " can't support the date!");
```
These bare `RuntimeException`s with shortened message text will:
1. Propagate into the Groovy bridge with no typed information, losing the original pattern and input value for debugging.
2. Because Groovy treats any `RuntimeException` as script-fatal, a single malformed date in one row kills the whole batch when used inside a tMap expression. Talend's parseDate behavior is well-documented to throw a `java.text.ParseException` (checked) that most Talend job code wraps in try/catch. Replacing it with an unchecked `RuntimeException` means existing error-handling try/catch blocks written against `ParseException` in user expressions are now dead code.

**Fix:** Either preserve the checked exception (change method signature to `throws ParseException`) or wrap with a typed runtime subclass AND include the input string in the message:
```java
throw new RuntimeException("parseDate failed for input '" + stringDate + "' with pattern '" + pattern + "': " + e.getMessage(), e);
```

### CR-09: `file_output_delimited` `validate_schema` mutates input DataFrame before passthrough

**File:** `src/v1/engine/components/file/file_output_delimited.py:160-161`
**Issue:**
```python
if input_data is not None and not input_data.empty and output_schema:
    input_data = self.validate_schema(input_data, output_schema)
```
`validate_schema` is designed for OUTPUT validation; here it is applied to INPUT before writing. It:
- Truncates strings against `output_schema.length` — fine for writing, but then the SAME reference is returned as `main` at line 206 (`return {"main": input_data, ...}`), so downstream components after the sink receive the TRUNCATED data, not the original. This is a silent data-mutation across component boundaries.
- Raises `DataValidationError` for non-nullable NULLs, turning a schema mismatch into a fatal error for a sink component. Talend tFileOutputDelimited writes data as-is and does not validate nullability at write time.

Additionally, `BaseComponent._apply_output_schema_validation` will then run `validate_schema` AGAIN on the `main` passthrough in Step 7c, double-truncating any strings at the length boundary (truncation is idempotent, so no data corruption, but it's wasted work).

**Fix:** Apply a write-only formatter (e.g. coerce strings only) instead of `validate_schema`, and pass the ORIGINAL untouched DataFrame through as `main`:
```python
# Validate input against output schema ONLY for local formatting; don't replace input_data
df_to_write = input_data
if input_data is not None and not input_data.empty and output_schema:
    df_to_write = self.validate_schema(input_data.copy(), output_schema)
# ... use df_to_write for writing ...
# at return:
return {"main": input_data, "reject": None}  # preserve original
```

---

## Warnings

### WR-01: `_enforce_schema_column_order` uses wrong default for datetime columns

**File:** `src/v1/engine/base_component.py:592-605, 636-649`
**Issue:** Missing datetime columns are filled with `pd.NA` (nullable) or `""` (non-nullable). Neither is a valid `datetime64[ns]` default. `pd.NA` coerces to `NaT` in modern pandas but relies on implicit dtype inference — `""` breaks any downstream `pd.to_datetime(..., errors="raise")`. Tracks documented gap **G-01**.

**Fix:** Branch on `col_type`:
```python
elif col_type == "datetime":
    main_df[col] = pd.NaT if nullable else pd.Timestamp(0)
```

### WR-02: `_enforce_schema_column_order` adds missing columns via scalar assignment, breaking dtype on empty DataFrames

**File:** `src/v1/engine/base_component.py:596-605`
**Issue:** `main_df[col] = pd.NA` on an otherwise-populated DataFrame produces an `object` column of NAs, not the typed column. For `int` type this means subsequent `_coerce_column_type` coerces via `pd.to_numeric(pd.NA...)` → `NaN` → `Int64Dtype()` if nullable, OR crashes on non-nullable. The scalar-assignment pattern also relies on broadcast — if `main_df.empty is False` (populated df with missing col), broadcast works; if `main_df.empty is True` the assignment silently does nothing and the column is missing entirely.

**Fix:** Use typed pd.Series construction or explicit dtype assignment:
```python
if nullable and col_type == "int":
    main_df[col] = pd.Series([pd.NA] * len(main_df), dtype="Int64")
elif nullable:
    main_df[col] = pd.NA  # object is OK
```

### WR-03: `_apply_output_schema_validation` early-exits on empty reject, skipping missing-column fill

**File:** `src/v1/engine/base_component.py:686, 693`
**Issue:** The guard `not main_df.empty` / `not reject_df.empty` means validation does not run at all when the DataFrame is empty. `_enforce_schema_column_order` has the same guard at line 571 (`main_df.empty`). So an empty result skips column-alignment AND schema validation — downstream components receive an unaligned empty DataFrame whose columns may not match the schema (breaks tMap lookups keyed on schema order).

**Fix:** Remove the `empty` guards — reindex and typing still apply cheaply to empty DataFrames:
```python
if main_df is not None and isinstance(main_df, pd.DataFrame):
    result["main"] = self.validate_schema(main_df, output_schema)
```

### WR-04: `file_input_delimited._fast_path_convert` silently drops rejected indices without resetting index

**File:** `src/v1/engine/components/file/file_input_delimited.py:625-628`
**Issue:**
```python
if bad_indices.any():
    result = result[good_mask].copy()
```
This keeps the original row-indices on `result`. On the NEXT column iteration, `for idx in result.index:` walks the surviving indices correctly — but downstream code that later uses positional access (`result.iloc`, `.reset_index(drop=True)`) will be confused because the gaps remain. Also, `good_mask` is rebuilt from scratch each column iteration, so a row rejected for column A is STILL evaluated for column B against stale `result.at[idx, ...]` if the index happens to survive column A's filtering — actually wait, after `result = result[good_mask]` reassigns, the bad indices ARE gone. But the `row_dict` appended to `reject_rows` uses `result.at[idx, c]` for OTHER columns still in `result`, which means a reject row may be missing columns that have not been checked yet.

**Fix:** Collect reject indices across all columns first, then filter once. Also reset_index at the end:
```python
bad_indices = set()
for col_def in self.output_schema:
    ...
    for idx in result.index:
        if idx in bad_indices: continue
        try: self._convert_value(...)
        except (ValueError, TypeError, DataValidationError):
            bad_indices.add(idx)
            # capture row_dict from original df
            reject_rows.append(...)
result = result.drop(index=bad_indices).reset_index(drop=True)
```

### WR-05: `file_input_delimited` `remove_empty_row` double-walks the DataFrame (uses axis=1 apply)

**File:** `src/v1/engine/components/file/file_input_delimited.py:218-228`
**Issue:**
```python
df = df.dropna(how="all")
mask = df.apply(lambda row: not all(str(v).strip() == "" for v in row), axis=1)
if not mask.empty:
    df = df[mask].reset_index(drop=True)
```
`df.apply(axis=1)` is a row-wise Python loop — intentional perf cost is noted, but the `dropna(how="all")` immediately before is redundant: since `dtype=str` + `keep_default_na=False` is used in `pd.read_csv`, NaN literally cannot appear — every "empty" cell is `""`. So `dropna(how="all")` is a no-op. The `mask` computation is the real check.

**Fix:** Drop the redundant `dropna` call and use a vectorized check:
```python
if remove_empty_row:
    all_empty = (df.astype(str).apply(lambda s: s.str.strip()) == "").all(axis=1)
    df = df[~all_empty].reset_index(drop=True)
```

### WR-06: `file_input_delimited._validate_and_convert` returns input df when `output_schema` is None — no type coercion

**File:** `src/v1/engine/components/file/file_input_delimited.py:558-560`
**Issue:** When no output schema is provided, the method returns `df, None` as-is. `df` at this point is all-string (because `pd.read_csv(..., dtype=str)` was used). Downstream components receive a string-typed int column. Without schema the component can't know types, but this is worth a warning log at least.

**Fix:** Emit a warning and/or infer types via `pd.to_numeric(errors='ignore')` as a best-effort:
```python
if not self.output_schema:
    logger.warning(f"[{self.id}] No output_schema; emitting all-string columns")
    return df, None
```

### WR-07: `filter_rows._compare` numeric-vs-string fallback logic has dead branch

**File:** `src/v1/engine/components/transform/filter_rows.py:130-139`
**Issue:**
```python
numeric_col = pd.to_numeric(col, errors="coerce")
...
if numeric_val is not None and numeric_col.notna().any():
    return _OPERATOR_MAP[operator](numeric_col, numeric_val)
# Fall back to string comparison
return _OPERATOR_MAP[operator](col.astype(str), str(value))
```
If `numeric_val is not None` but `numeric_col.notna().any() is False` (value parses as number but no column values do), we fall to string comparison — comparing a stringified numeric `value` against raw strings. For `operator="=="` and config `value="10"` against column ["ten", "eleven"], this returns False-False, which is semantically fine. But for `value="10.0"` vs column `["10", "20"]`, string comparison gives `["10.0" == "10"]` = False, even though numerically they match. The code ALREADY detected `value` is numeric and just failed to coerce the column — then retreats to string comparison inconsistently.

**Fix:** Mix of numeric and string in a column should compare numerically where possible; fall back only when the value itself isn't numeric:
```python
if numeric_val is not None:
    # Compare numerically; non-numeric col values become NaN -> False
    return _OPERATOR_MAP[operator](numeric_col, numeric_val)
return _OPERATOR_MAP[operator](col.astype(str), str(value))
```

### WR-08: `filter_rows._handle_advanced` uses `self.inputs` without guarding NoneType

**File:** `src/v1/engine/components/transform/filter_rows.py:366`
**Issue:** `self.inputs[0] if self.inputs else "row1"` — but `self.inputs` is set by the engine at `engine.py:120`. If `FilterRows` is executed standalone (tests, notebook, CI without full engine run), `self.inputs` is undefined, and `self.inputs[0]` raises `AttributeError` before `if self.inputs` can short-circuit. The truthiness check happens first but the attribute access still fails.

Actually re-reading: `self.inputs[0] if self.inputs else "row1"` — Python evaluates `self.inputs` first for the truthiness check, NOT `self.inputs[0]`. So `AttributeError` on `self.inputs`, not index error. Still broken when attribute is missing.

**Fix:**
```python
main_table_name = getattr(self, "inputs", None)
main_table_name = main_table_name[0] if main_table_name else "row1"
```

### WR-09: `aggregate_row` `median` with `use_financial_precision` silently falls back to float

**File:** `src/v1/engine/components/aggregate/aggregate_row.py:146-150`
**Issue:**
```python
if func_name == "median":
    if use_financial_precision:
        return lambda x: x.dropna().astype(float).median() ...
```
Documented as "Decimal median is complex" — true, but the behavior diverges from other aggregations. `use_financial_precision=True` was promised in the class docstring, and users may be relying on it for regulatory calculations. Silently downgrading to float is a **reproducibility bug**: rounding mode differs, and for large Decimal values (currency in cents) this changes results.

**Fix:** At minimum warn once per component:
```python
if use_financial_precision:
    logger.warning(f"[median] Decimal median not supported; using float median (precision loss may occur)")
    return lambda x: ...
```
Better — implement Decimal median using `statistics.median` on a list of Decimals.

### WR-10: `aggregate_row` `count` is always non-null count, ignores `ignore_null=False`

**File:** `src/v1/engine/components/aggregate/aggregate_row.py:125-127`
**Issue:**
```python
if func_name == "count":
    return "count"
```
pandas `"count"` aggregator counts only non-null values regardless of `ignore_null`. Talend `count` with `ignore_null=false` should count ALL rows including nulls (effectively `size`). The engine silently ignores `ignore_null` for count.

**Fix:**
```python
if func_name == "count":
    return "count" if ignore_null else "size"
```

### WR-11: `aggregate_row._grouped_aggregation` uses `sort=True`, which alphabetizes output but Talend preserves input order

**File:** `src/v1/engine/components/aggregate/aggregate_row.py:394`
**Issue:** `groupby(group_cols, sort=True)` sorts by group key lexicographically. Talend tAggregateRow preserves the order of first appearance of each group (i.e., `sort=False`) — this is observable in golden-file diffs between Talend and engine output.

**Fix:** Use `sort=False` for Talend parity:
```python
df.groupby(group_cols, sort=False).agg(**named_aggs).reset_index()
```

### WR-12: `context_load` row-by-row iteration with `.iloc[i]` is O(n) per lookup

**File:** `src/v1/engine/components/context/context_load.py:140-158`
**Issue:** Per-row `.iloc[i]` on the Series is O(n) in pandas' copy-on-write world (3.0+); the whole loop is O(n²) for small-to-medium row counts. Given a context-load flow is typically <1000 rows, this is rarely catastrophic, but the existing vectorized `.str.strip()` prep suggests the author intended vectorization. Tracks MEMORY `project_pandas3_installed.md`.

**Fix:** Iterate over zipped native lists:
```python
keys_list = keys.tolist()
vals_list = values.tolist()
types_list = types.tolist() if has_type else [None] * len(input_data)
for key, val, type_val in zip(keys_list, vals_list, types_list):
    ...
```

### WR-13: `context_load` type preservation policy: type column value is used even when empty string

**File:** `src/v1/engine/components/context/context_load.py:228`
**Issue:**
```python
if has_type_column and type_val is not None and not pd.isna(type_val):
    return str(type_val)
```
A type column containing `""` (empty string after `.fillna("")` upstream) would return `""` as the type, which then propagates to `ContextManager.set(key, val, "")`. Downstream type-based coercion may misbehave with empty type strings.

**Fix:**
```python
if has_type_column and type_val is not None and not pd.isna(type_val):
    type_str = str(type_val).strip()
    if type_str:
        return type_str
```

### WR-14: `StringHandling.LEN` returns -1 for null — diverges from Talend which returns 0

**File:** `src/v1/java_bridge/java/src/main/java/routines/StringHandling.java:248-250`
**Issue:**
```java
public static int LEN(String string) {
    return string == null ? -1 : string.length();
}
```
Talend routines.StringHandling.LEN returns `0` for null input. Downstream math like `LEN(col) > 5` on a null column under Talend evaluates `0 > 5` = false; under this engine it evaluates `-1 > 5` = false too — same result here, BUT any user code doing `LEN(x) >= 0` changes from true (Talend) to false (engine).

**Fix:** `return string == null ? 0 : string.length();`

### WR-15: `StringHandling.INSTR` uses `defaultStart` in length check before assigning from `start`

**File:** `src/v1/java_bridge/java/src/main/java/routines/StringHandling.java:592-598`
**Issue:**
```java
int defaultStart = 1;
...
if (isVacant(string) || isVacant(search_value)|| Math.abs(defaultStart) >= string.length()) {
    return null;
}
if (start != null && start != 0) {
    defaultStart = start;
}
```
The `Math.abs(defaultStart) >= string.length()` check runs against hardcoded `1`, NOT the user-supplied `start`. If the user passes `start=100` against a 10-char string, the check passes (1 < 10) and the function proceeds into an `IndexOutOfBoundsException` at `string.substring(defaultStart - 1)` line 618.

**Fix:** Move the start-initialization above the length guard:
```java
int defaultStart = 1;
if (start != null && start != 0) defaultStart = start;
if (isVacant(string) || isVacant(search_value) || Math.abs(defaultStart) >= string.length()) {
    return null;
}
```

### WR-16: `Numeric.convertImpliedDecimalFormat` uses deprecated `new Float(double)`

**File:** `src/v1/java_bridge/java/src/main/java/routines/Numeric.java:112`
**Issue:** `new Float(decimal.doubleValue())` — `Float(double)` constructor is deprecated since Java 9 and removed in later versions. Under Java 11 (project target), this emits a deprecation warning; under Java 17+ it is slated for removal.

**Fix:** `Float.valueOf((float) decimal.doubleValue())` or return `Double` instead (Talend parity check required).

### WR-17: Test `test_empty_input_header_uses_input_schema` puts schema in config but component never reads it

**File:** `tests/v1/engine/components/file/test_file_output_delimited.py:561-575`
**Issue:** The test sets `config["schema"] = {"input": [...], "output": []}`, but `FileOutputDelimited.__init__` (inherited from `BaseComponent`) never extracts `schema` from config — `input_schema`/`output_schema` are set by the engine at `engine.py:122`, which is not invoked in this direct-instantiation test. So `comp.input_schema` is never set, `_get_header_columns()` returns `[]`, and the assertion `"x" in lines[0]` will fail when the test is actually run.

**Fix:** Set attribute directly as the other tests in this class do (see line 526 `comp.output_schema = [...]`):
```python
comp.input_schema = [{"name": "x", "type": "int"}, {"name": "y", "type": "str"}]
```

---

## Info

### IN-01: `Mathematical.CHAR` uses `Character.forDigit(i, 10)` — wrong for ASCII conversion

**File:** `src/v1/java_bridge/java/src/main/java/routines/DataOperation.java:22-24`
**Issue:** Docstring says "Converts a numeric value to its ASCII character string equivalent" — example `CHAR(1)` should return... Talend actually returns ASCII character for that value (e.g. `CHAR(65)` -> `'A'`). `Character.forDigit(1, 10)` returns `'1'` (digit character for radix 10), not the ASCII char at code point 1. For `CHAR(65)`, `forDigit(65, 10)` returns `'\0'` (invalid for radix 10) — completely wrong.
**Fix:** `return (char) i;`

### IN-02: `Mathematical.main()` leftover test code in production routines

**File:** `src/v1/java_bridge/java/src/main/java/routines/Mathematical.java:310-312`
**Issue:** `public static void main(String[] args) { Mathematical.MOD(3, 2); }` serves no purpose in a routine library. Also increases the shaded JAR's surface area for `mainClass` misconfiguration.
**Fix:** Delete.

### IN-03: `TalendDate.test_*` methods are leftover manual tests

**File:** `src/v1/java_bridge/java/src/main/java/routines/TalendDate.java:1190-1346`
**Issue:** Over 150 lines of `test_formatDate`/`test_compareDate`/`test_isDate`/`test_getRandomDate` methods with `System.out.println` and hardcoded thread tests. These are production-unsafe (they spin up test threads on classload if called by framework reflection) and bloat the JAR.
**Fix:** Delete or move to an actual JUnit test class.

### IN-04: `TalendDataGenerator` uses `RandomUtils.random()` for generated data

**File:** `src/v1/java_bridge/java/src/main/java/routines/TalendDataGenerator.java:23, 40, 65, 83, 101, 116`
**Issue:** `RandomUtils.random()` (from the Talend `routines.system` dep) is typically a wrapper around `java.util.Random` — not `SecureRandom`. For generated PII-looking data (names, addresses) this is fine; worth noting only if this data is used for any security-sensitive purpose (tokens, etc.). **Not used for secrets** based on current function set, so Info only.

### IN-05: `TalendString.getAsciiRandomString` mixes `SecureRandom` + tight loop

**File:** `src/v1/java_bridge/java/src/main/java/routines/TalendString.java:76-91`
**Issue:** Uses `SecureRandom` (good) but runs a `while (cnt < length)` loop that rejects non-alphanumeric candidates. For the default ASCII printable range (`' '` to `'z'+1`, 91 chars), roughly 62/91 = 68% are alphanumeric — so loop avg iterations = 1.47x length. Fine for small lengths, but `new SecureRandom()` is allocated every call (expensive in a tight loop).
**Fix:** Use a shared `private static final SecureRandom RAND = new SecureRandom();`.

### IN-06: `TalendString.initMap()` uses raw `Vector` — ancient pattern

**File:** `src/v1/java_bridge/java/src/main/java/routines/TalendString.java:20, 162`
**Issue:** `Vector` is legacy (synchronized access is not needed here), raw types lose generic safety. Matches the Talend upstream style but creates javac warnings.
**Fix:** `private static final List<String> map = initMap();` with `ArrayList<String>`.

### IN-07: `StringHandling.TRIM` delegates to `String.trim()` which only strips ASCII ≤ U+0020

**File:** `src/v1/java_bridge/java/src/main/java/routines/StringHandling.java:318-320`
**Issue:** `String.trim()` removes only characters ≤ U+0020. Talend's Java 11+ routines may use `String.strip()` which handles Unicode whitespace (e.g. U+00A0 non-breaking space). For ETL data containing NBSP (common in web-scraped inputs), engine output differs from Talend.
**Fix:** Check Talend reference behavior; if it uses `strip()`, align.

### IN-08: `StringHandling.LTRIM(value, trim_set)` has O(n²) inner walk

**File:** `src/v1/java_bridge/java/src/main/java/routines/StringHandling.java:415-442`
**Issue:** The `do { for (char c : chars) { for (; value.indexOf(c, st) == st; st++); } } while (...)` loop re-scans from `st` each iteration, producing O(n²) in pathological cases (e.g., LTRIM(("a"*1000 + "b"), "a")). Out of scope per review rules (perf not v1) — noted for future.

### IN-09: `aggregate_row._decimal_std` uses `float(variance) ** 0.5` — loses Decimal precision

**File:** `src/v1/engine/components/aggregate/aggregate_row.py:99`
**Issue:** The whole point of `use_financial_precision` is to avoid float rounding. `Decimal(str(float(variance) ** 0.5))` converts Decimal → float → sqrt → Decimal, discarding the precision benefit. Acknowledged in the comment "Decimal sqrt via float conversion (sufficient precision for ETL)" but worth documenting as a known loss.
**Fix:** Use `Decimal.sqrt()` if available (Python 3.13+) or implement Newton's method for true Decimal sqrt.

### IN-10: `filter_rows._compare` string fallback with `"CONTAINS"` ignores already-string check

**File:** `src/v1/engine/components/transform/filter_rows.py:142`
**Issue:** `_OPERATOR_MAP["CONTAINS"]` already calls `col.astype(str).str.contains(...)`; wrapping in the final `return _OPERATOR_MAP[operator](col, value)` path causes no harm but the double `.astype(str)` is wasted work. Minor.

### IN-11: `context_load._emit_message` re-reads DISABLE_* flags from config on every call

**File:** `src/v1/engine/components/context/context_load.py:283-286`
**Issue:** `self.config.get(...)` called per message; for a context-load with hundreds of messages emitted (unusual but possible), this is redundant. Read once in `_process()` and pass along.

### IN-12: Missing docstring examples for edge cases in `file_output_delimited._write_raw_mode`

**File:** `src/v1/engine/components/file/file_output_delimited.py:392-437`
**Issue:** `_write_raw_mode` docstring does not mention the no-escape-of-multi-char-delimiter semantics (see CR-06). Any future reader of this method could easily write a bug expecting it to round-trip. Add a Talend-parity note.

---

## Evidence on Documented Gaps (docs/v1/BaseComponent-Info.md)

| Gap | Status | Evidence |
|-----|--------|----------|
| **G-01** (datetime defaults for missing cols) | **CONFIRMED as bug** | See WR-01. `_enforce_schema_column_order` lines 596-605 and 636-649 use `pd.NA` / `""` for datetime, never `pd.NaT`. |
| **G-02** (Decimal coercion) | **CONFIRMED** | `_coerce_column_type` at line 812 maps Decimal → "object", doing nothing. `_apply_decimal_precision` only runs when `precision` is set (line 757); columns without `precision` stay as strings. |
| **G-03** (float precision) | **CONFIRMED** | `validate_schema` line 756 scopes precision to Decimal only: `if precision is not None and col_type == "Decimal":` — float columns never get precision applied. |
| **G-04** (date_pattern not used) | **CONFIRMED for parsing** (`_coerce_column_type` line 816 uses `pd.to_datetime` with no `format=`); `_validate_date` in `file_input_delimited` DOES use pattern via `datetime.strptime` — component-local, not base-level. |
| **G-05** (die_on_error ignored in validation) | **CONFIRMED** | `validate_schema` line 737-740 raises `DataValidationError` unconditionally; no `self.die_on_error` check. |
| **G-06** (no input schema validation) | **CONFIRMED** | Only `output_schema` / `reject_schema` referenced (`_apply_output_schema_validation`). No `input_schema` validation anywhere in base class. |
| **G-07** (no schema default values) | **CONFIRMED** | `_enforce_schema_column_order` uses hardcoded defaults by type, never `col_def.get("default")`. |
| **G-08** (key attribute unused) | **CONFIRMED** | No reference to `col_def.get("key")` in base_component.py. |
| **G-09** (no error flow routing) | **CONFIRMED** | No error-link mechanism in base class; components that need it (e.g. `tDie`) raise `ComponentExecutionError` themselves. |
| **G-10** (streaming defeats schema validation) | **CONFIRMED** | `execute()` lines 172-181 concat chunks THEN run 7b/7c — full concatenated DataFrame in memory before schema enforcement. |
| **G-11** (NB_LINE multi-input) | **CONFIRMED** | `_count_input_rows` lines 472-478 sums all dict values into one number. |
| **G-12** (empty string vs null) | **CONFIRMED** | `_coerce_column_type` line 818 uses `pd.to_numeric(..., errors="coerce")` — turns "" into NaN for numeric cols with no signal difference. |

**Additional undocumented issues uncovered during this review:**
- **G-13 (new):** `_apply_output_schema_validation` on reject DataFrame breaks reject flows when reject_schema has non-nullable columns. See CR-01.
- **G-14 (new):** `_apply_decimal_precision` crashes on string precision values from JSON configs. See CR-02.
- **G-15 (new):** Stats double-count guard via `_stats_set_by_component` is cleared in `execute()` lifecycle but NOT in `reset()` (iterate re-execution) — iterate loops using `_update_stats` directly may under-count on second iteration. See `reset()` at line 848.

---

_Reviewed: 2026-04-18T11:33:56Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
