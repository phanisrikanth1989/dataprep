---
phase: 11-oracle-components
reviewed: 2026-05-07T00:00:00Z
depth: standard
files_reviewed: 25
files_reviewed_list:
  - pyproject.toml
  - src/converters/talend_to_v1/components/database/oracle_connection.py
  - src/converters/talend_to_v1/components/database/oracle_output.py
  - src/converters/talend_to_v1/components/database/oracle_row.py
  - src/v1/engine/components/__init__.py
  - src/v1/engine/components/database/__init__.py
  - src/v1/engine/components/database/oracle_connection.py
  - src/v1/engine/components/database/oracle_output.py
  - src/v1/engine/components/database/oracle_row.py
  - src/v1/engine/engine.py
  - src/v1/engine/oracle_connection_manager.py
  - tests/converters/talend_to_v1/components/database/test_oracle_connection.py
  - tests/converters/talend_to_v1/components/database/test_oracle_output.py
  - tests/converters/talend_to_v1/components/database/test_oracle_row.py
  - tests/v1/engine/components/database/__init__.py
  - tests/v1/engine/components/database/integration/__init__.py
  - tests/v1/engine/components/database/integration/conftest.py
  - tests/v1/engine/components/database/integration/test_oracle_connection_e2e.py
  - tests/v1/engine/components/database/integration/test_oracle_output_e2e.py
  - tests/v1/engine/components/database/integration/test_oracle_phase11_samples_e2e.py
  - tests/v1/engine/components/database/integration/test_oracle_row_e2e.py
  - tests/v1/engine/components/database/test_oracle_connection.py
  - tests/v1/engine/components/database/test_oracle_output.py
  - tests/v1/engine/components/database/test_oracle_row.py
  - tests/v1/engine/test_oracle_connection_manager.py
findings:
  critical: 2
  warning: 8
  info: 5
  total: 15
status: issues_found
---

# Phase 11: Code Review Report

**Reviewed:** 2026-05-07
**Depth:** standard
**Files Reviewed:** 25
**Status:** issues_found

## Summary

Phase 11 introduces Oracle DB integration: three converters (tOracleConnection / tOracleRow / tOracleOutput), three engine components, an OracleConnectionManager, and integration plumbing in ETLEngine. Overall structure follows the project's ABC + registry pattern and the security posture (T-11-02 password hygiene, T-11-04 identifier quoting) is well thought through.

Two real correctness defects were found:

1. **BLOCKER: Schema key mismatch between converter and engine for tOracleOutput.** The converter emits `table_schema` (TABLESCHEMA Talend param), but the engine reads `schema_db` / `dbschema`. Result: every converted tOracleOutput job will silently lose its schema qualifier and emit unqualified `"EMP"` instead of `"HR"."EMP"`, which on multi-schema Oracle databases will write to the wrong table or fail with ORA-00942.
2. **BLOCKER: Upsert path raises ValueError when a PK column is excluded from the insertable set via FIELD_OPTIONS.** `_execute_upsert_batch` indexes PK columns into `insert_cols` (which honors FIELD_OPTIONS INSERTABLE), so any field_options config that marks a key as not insertable crashes with a confusing `ValueError: 'pk' is not in list` instead of a clean `ConfigurationError`.

Beyond those, several warnings around error masking, transaction semantics with `die_on_error`, parsing robustness, and a doc/code drift in `oracle_connection.py`.

## Critical Issues

### CR-01: Converter emits `table_schema` but engine reads `schema_db` (BLOCKER)

**File:** `src/converters/talend_to_v1/components/database/oracle_output.py:71` and `src/v1/engine/components/database/oracle_output.py:243`

**Issue:** The converter for tOracleOutput maps Talend's `TABLESCHEMA` XML param to `config["table_schema"]`:

```python
# converter
config["table_schema"] = self._get_str(node, "TABLESCHEMA", "")
```

The engine's `_qualified_table()` does NOT read `table_schema` — it reads `schema_db` (the key used by tOracleConnection / tOracleRow) with a `dbschema` fallback:

```python
# engine
schema = (self.config.get("schema_db") or self.config.get("dbschema") or "").strip()
```

Result: every converted tOracleOutput job loses its schema qualifier. The DDL/DML targets the unqualified table name, which under Oracle defaults to `<connecting_user>.<table>`. On any multi-schema Citi job (the common case), this writes to the wrong schema or fails ORA-00942 / ORA-00955. None of the unit tests catch this because they hand-build configs with `schema_db` set; the converter→engine wiring is never exercised by an end-to-end test in plan 11-07's mock-only suite.

**Fix:** Pick one. Recommended: align the converter with the other two Oracle converters and use `schema_db` (which is also what the engine docstring documents in `oracle_output.py` config-keys section: "schema_db" is listed). Update the docstring NOTE and rename the field:

```python
# src/converters/talend_to_v1/components/database/oracle_output.py:71
# WAS: config["table_schema"] = self._get_str(node, "TABLESCHEMA", "")
config["schema_db"] = self._get_str(node, "TABLESCHEMA", "")
```

Then update the converter docstring (lines 14, 34) and the converter test to expect `schema_db`. Alternatively, if the converter key is the contract, update `_qualified_table()` to also read `table_schema`. Whichever direction is chosen, add an integration test that runs a converted JSON through the engine against a temp_table with a non-default schema to lock the bug down.

### CR-02: Upsert with non-insertable PK raises `ValueError` instead of `ConfigurationError` (BLOCKER)

**File:** `src/v1/engine/components/database/oracle_output.py:543, 571, 667`

**Issue:** `_execute_upsert_batch` uses `insert_cols = self._insertable_columns()` as the column ordering for chunk tuples and PK lookups:

```python
# line 636
insert_cols = self._insertable_columns()
...
# line 640 (via _flatten_pk_binds)
pk_indices = [col_order.index(c) for c in pk_cols]   # line 543, 571
...
# line 667
update_indices_in_insert = [insert_cols.index(c) for c in update_col_order]
```

`_insertable_columns()` honors `field_options[*].insertable` — if a user marks a key column as `insertable=false` (a legitimate Talend FIELD_OPTIONS pattern, e.g. for sequence-populated PKs), the PK column is no longer in `insert_cols` and `insert_cols.index(pk_col)` raises an unhandled `ValueError: 'pk' is not in list`. Same root cause hits `_dataframe_to_param_list` (line 730–735): for upsert, it builds rows in `_insertable_columns()` order, dropping PK values that the SELECT/UPDATE need. The component should either (a) refuse the configuration with a clear `ConfigurationError`, or (b) override field_options for upsert and force PK columns into the chunk regardless.

**Fix:** Add an upfront validation in `_execute_upsert_batch` (or upstream in `_validate_config` once `data_action` is in the upsert set):

```python
def _execute_upsert_batch(self, cursor, chunk, chunk_df, prefer_update):
    pk_cols = self._key_columns()
    if not pk_cols:
        raise ConfigurationError(...)
    insert_cols = self._insertable_columns()
    missing = [c for c in pk_cols if c not in insert_cols]
    if missing:
        raise ConfigurationError(
            f"[{self.id}] upsert requires PK columns {missing!r} to also be "
            f"insertable; FIELD_OPTIONS marks them insertable=False"
        )
    ...
```

Alternatively, build a separate `upsert_cols = list(dict.fromkeys(insert_cols + pk_cols))` so PK is always included; this changes the SQL semantics, so the validation-and-refuse approach is safer.

## Warnings

### WR-01: `die_on_error` raises *after* successful rows are committed

**File:** `src/v1/engine/components/database/oracle_output.py:972-1000`

**Issue:** The chunk loop commits every `commit_every` rows (line 972-974) and again after the loop (line 976-977). The `die_on_error` check fires at line 994-1000, **after** all OK rows are already committed to the database. Talend's `tOracleOutput` with `die_on_error=true` is documented as job-aborting behavior; users will reasonably expect rollback semantics. With the current code, a job that processes 50,000 rows in chunks of 10,000, hits a bad row in chunk 4, dies — but chunks 1-3 (30,000 rows) are permanently in the table.

**Fix:** Either rollback the whole transaction on `die_on_error`, or document the partial-commit semantics explicitly. If rollback is preferred, gather batch errors into a fast-fail list, run `conn.rollback()`, then raise. If partial-commit is intentional Talend parity, add a clear comment + a test asserting the behavior so future readers don't trip on it.

```python
# Option: fail-fast inside the chunk loop, before commit cycle
if die_on_error and batch_errors:
    if owns_connection or table_action == "NONE":
        try:
            conn.rollback()
        except Exception:
            pass
    raise DataValidationError(...)
```

### WR-02: `OracleRow._process` `finally` block can mask the original exception

**File:** `src/v1/engine/components/database/oracle_row.py:420-423`

**Issue:**

```python
finally:
    cursor.close()
    if owns_connection:
        self.oracle_manager.close(self.id)
```

If `cursor.execute(...)` raises (e.g., ORA-00942), then `cursor.close()` itself raises (some drivers do on bad-state cursors), Python replaces the original SQL exception with the close-time exception. `oracle_output.py:1008-1018` already wraps cleanup in try/except for exactly this reason — apply the same pattern here. Same risk for `oracle_manager.close(self.id)`.

**Fix:**

```python
finally:
    try:
        cursor.close()
    except Exception:  # noqa: BLE001 -- cleanup must not mask original
        logger.warning("[%s] cursor.close() raised; ignoring", self.id)
    if owns_connection:
        try:
            self.oracle_manager.close(self.id)
        except Exception:  # noqa: BLE001
            logger.warning("[%s] oracle_manager.close() raised; ignoring", self.id)
```

### WR-03: `_parse_prepared_params` accepts incomplete rows silently

**File:** `src/converters/talend_to_v1/components/database/oracle_row.py:55-86`

**Issue:** The parser groups `raw` into windows of 3 elementRefs and only checks `if row:` (non-empty dict) before appending. If any group has fewer than 3 of the expected `PARAMETER_INDEX / PARAMETER_TYPE / PARAMETER_VALUE` `elementRef` keys (e.g., one entry has a typo or unexpected ref), `row` will be missing fields. Downstream `_coerce_prepared_param` will use defaults (`parameter_type` defaults to `"Object"`, `parameter_value` to `None`) and silently bind a wrong value or NULL. The current code defends against incomplete trailing groups (line 70-71) but not against malformed groups.

**Fix:** Verify that the resulting row has all three expected keys before accepting:

```python
if row.keys() >= {"parameter_index", "parameter_type", "parameter_value"}:
    result.append(row)
elif row:
    # Log a warning so silent data corruption is visible
    logger.warning("Incomplete prepared-param row at offset %d: %r", i, row)
```

Also accumulate to `warnings: List[str]` in the converter result so the post-conversion validator surfaces it.

### WR-04: Converter does not validate `parameter_index` is a positive integer

**File:** `src/converters/talend_to_v1/components/database/oracle_row.py:79`

**Issue:** `parameter_index` is taken straight from XML as a string (after stripping quotes). If a Talend job has a non-numeric `PARAMETER_INDEX` (typo, context expression), it will be propagated to the engine. The engine then runs:

```python
# src/v1/engine/components/database/oracle_row.py:381-383
ordered = sorted(params, key=lambda r: int(r.get("parameter_index", 0)))
```

`int("abc")` raises `ValueError` at runtime — far from the source of the bad data. The converter should at minimum surface a warning when `parameter_index` is non-numeric.

**Fix:** In the converter, `try: int(val.strip('"')); except ValueError: warnings.append(...)`.

### WR-05: Engine `oracle_connection.py` docstring says `tns_file_alias`, code path uses `tns_file`

**File:** `src/v1/engine/components/database/oracle_connection.py:38`

**Issue:** Module docstring lists `tns_file_alias` as a deferred config key, but the converter emits `tns_file` and the engine warning loop checks `use_tns_file`. Either rename the docstring entry or add the `tns_file` key explicitly. Trivial but misleading for downstream readers wiring up TNS-file support later.

**Fix:** Change the docstring line to `tns_file (str, default "") -- deferred`.

### WR-06: `OracleConnection._validate_config` does not validate `host`/`port`/`dbname` even though `_process` requires them

**File:** `src/v1/engine/components/database/oracle_connection.py:91-109, 144-163`

**Issue:** `_validate_config` only checks that `connection_type` is in the closed set and that `user`/`password` keys are *present* (not non-empty). At runtime, `_process` does `self.config["dbname"]` for SID (line 150) — if `dbname` is missing or empty, you get a `KeyError` for SID (no `.get`) or an `oracledb.connect` error for SERVICE_NAME (line 154 falls back to `local_service_name`). This makes errors surface as low-level driver errors rather than the engine's typed `ConfigurationError`. Not a security issue, but degrades operator UX.

**Fix:** Add a structural required-keys check per connection_type:

```python
def _validate_config(self) -> None:
    ...
    ct = self.config.get("connection_type", "ORACLE_SID")
    if ct == "ORACLE_SID":
        for k in ("host", "dbname"):
            if not self.config.get(k):
                raise ConfigurationError(f"[{self.id}] {ct} requires {k!r}")
    elif ct == "ORACLE_SERVICE_NAME":
        if not self.config.get("host"):
            raise ConfigurationError(f"[{self.id}] {ct} requires 'host'")
        if not self.config.get("dbname") and not self.config.get("local_service_name"):
            raise ConfigurationError(
                f"[{self.id}] {ct} requires 'dbname' or 'local_service_name'"
            )
```

(Phase 7.1 Rule 12 says structural-only — but absence-of-key checks are structural by that rule's spirit.)

### WR-07: `OracleConnectionManager.open_ad_hoc` silently overwrites validation order

**File:** `src/v1/engine/oracle_connection_manager.py:163-184`

**Issue:** The `cid in self.connections` precheck (line 163) raises `ValueError`, but the OCI/Wallet refusal (line 166) raises `ConfigurationError` *afterward*. Sequence is fine, but the `Unknown connection_type` branch (line 181-184) lists `ORACLE_OCI` and `ORACLE_WALLET` in its "must be one of" message even though those are explicitly refused above. If a typo lands in connection_type and the user reads the error, they see OCI/Wallet listed as valid options that they could try — which is misleading because they would then hit the refusal path.

**Fix:** Trim the OCI/Wallet entries from the error message in the `else` branch, or build the set programmatically:

```python
raise ConfigurationError(
    f"Unknown connection_type {ct!r}. Must be one of: "
    f"{{'ORACLE_SID','ORACLE_SERVICE_NAME','ORACLE_RAC'}} "
    f"(OCI/WALLET require thick mode + Instant Client; tracked in deferred items)"
)
```

### WR-08: Engine test `test_oracle_output.py:86` reads file via `open()` without `with`/encoding

**File:** `tests/v1/engine/components/database/test_oracle_output.py:86, 92, 102`

**Issue:**

```python
src = open(oracle_output.__file__).read()
```

No `with`, no `encoding` arg. Per project conventions in CLAUDE.md (`Missing 'with' for file operations` listed under Python checks). Resource leaks won't be visible in pytest but the pattern is non-conforming. Same in `test_oracle_row.py` and the converter test files if they follow the same idiom.

**Fix:**

```python
with open(oracle_output.__file__, encoding="utf-8") as f:
    src = f.read()
```

## Info

### IN-01: Empty `_emit_none(self, cursor)` returns `None` explicitly

**File:** `src/v1/engine/components/database/oracle_output.py:283-285`

**Issue:** `return None` after a docstring is redundant — the function returns None implicitly. Stylistic only.

**Fix:** Drop the `return None`.

### IN-02: `_DATA_ACTIONS_SIMPLE` defined but never read

**File:** `src/v1/engine/components/database/oracle_output.py:92`

**Issue:** `_DATA_ACTIONS_SIMPLE = frozenset({"INSERT","UPDATE","DELETE"})` is defined at module scope but never referenced — `_DATA_ACTIONS_UPSERT` is also unreferenced (the `is_upsert` check inlines the membership test at line 905-907). Dead code.

**Fix:** Remove both module-level frozensets, or replace the inline tuple checks with `data_action in _DATA_ACTIONS_UPSERT` for clarity.

### IN-03: Magic numbers for Oracle precision in `_column_to_oracle_type`

**File:** `src/v1/engine/components/database/oracle_output.py:149-180`

**Issue:** Hard-coded `NUMBER(10)`, `NUMBER(19)`, `VARCHAR2(... CHAR)`, `4000`, `2000`. They are documented in the docstring, but extracting to module constants (e.g. `_INT_PRECISION = 10`, `_VARCHAR2_MAX_BYTES = 4000`) would tighten test coverage and make the policy change in one place.

**Fix:** Optional — extract `_INT_PRECISION`, `_LONG_PRECISION`, `_VARCHAR2_INLINE_MAX`, `_RAW_INLINE_MAX` constants.

### IN-04: Engine `oracle_row.py` import of `Decimal` only used in the `_coerce_decimal` helper

**File:** `src/v1/engine/components/database/oracle_row.py:81`

**Issue:** `from decimal import Decimal` is at module scope and used in one place. Fine, but if the `oracle` extra is missing the consumer of this module shouldn't pay for `decimal` import. Trivial; `decimal` is stdlib so no real cost. Skip.

### IN-05: ETLEngine auto-detects Oracle components by component-type string match

**File:** `src/v1/engine/engine.py:74-83`

**Issue:** The hard-coded set `oracle_component_types = {"OracleConnection","tOracleConnection","tDBConnection","OracleRow","tOracleRow","OracleOutput","tOracleOutput"}` will silently fail if Phase 12 adds (say) `tOracleInput` and someone forgets to update this set. The OracleConnectionManager is then None and components hit the "OracleConnectionManager not wired" error path. Consider deriving the set from the registry or from class metadata so it's harder to drift.

**Fix:** Optional — expose a class attribute `_REQUIRES_ORACLE_MANAGER = True` on Oracle component classes and detect via REGISTRY introspection.

---

_Reviewed: 2026-05-07_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
