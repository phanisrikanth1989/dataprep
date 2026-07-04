# Phase 11: Oracle Components - Pattern Map

**Mapped:** 2026-05-07
**Files analyzed:** 22 (13 new + 9 modified)
**Analogs found:** 21 / 22 (testcontainers fixture has no analog -- new pattern)

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/v1/engine/oracle_connection_manager.py` | manager (lifecycle service) | resource pool / lifecycle | `src/v1/engine/java_bridge_manager.py` | exact (mirror) |
| `src/v1/engine/components/database/__init__.py` | package marker | n/a | `src/v1/engine/components/aggregate/__init__.py` | exact |
| `src/v1/engine/components/database/oracle_connection.py` | component (orchestration-only) | trigger / no FLOW | `src/v1/engine/components/file/file_exist.py` + `src/v1/engine/components/control/die.py` | role-match |
| `src/v1/engine/components/database/oracle_row.py` | component (transform / sink) | request-response (SQL exec) | `src/v1/engine/components/aggregate/aggregate_row.py` | role-match |
| `src/v1/engine/components/database/oracle_output.py` | component (sink + reject) | CRUD batch write + reject | `src/v1/engine/components/file/file_input_delimited.py` (REJECT pattern) + `aggregate_row.py` (process shape) | role-match |
| `tests/v1/engine/test_oracle_connection_manager.py` | test (manager unit) | mock-driven | `tests/v1/engine/test_routine_loading.py` + `tests/v1/engine/test_bridge.py` | exact |
| `tests/v1/engine/components/database/__init__.py` | test package marker | n/a | `tests/v1/engine/components/file/__init__.py` | exact |
| `tests/v1/engine/components/database/test_oracle_connection.py` | test (component unit) | mock `oracledb` | `tests/v1/engine/components/file/test_file_exist.py` | role-match |
| `tests/v1/engine/components/database/test_oracle_row.py` | test (component unit) | mock `oracledb.Cursor` | `tests/v1/engine/components/control/test_die.py` (TestRegistration / TestValidation shape) | role-match |
| `tests/v1/engine/components/database/test_oracle_output.py` | test (component unit) | mock `oracledb.Cursor` | `tests/v1/engine/components/file/test_file_exist.py` | role-match |
| `tests/v1/engine/components/database/integration/__init__.py` | test package marker | n/a | `tests/integration/__init__.py` | exact |
| `tests/v1/engine/components/database/integration/conftest.py` | test fixture (testcontainers) | external resource | **no analog** -- testcontainers is new to this codebase | none |
| `tests/v1/engine/components/database/integration/test_oracle_e2e.py` | test (e2e integration) | real Oracle + .item -> JSON -> ETLEngine | `tests/integration/test_iterate_e2e.py` | exact (structure) |
| `src/v1/engine/engine.py` | core (orchestrator) | wiring | (self) -- mirror existing `JavaBridgeManager` lines 41/47-54/139-140/231-233 | exact (in-place) |
| `src/v1/engine/component_registry.py` | core (registry) | n/a | (already supports `@REGISTRY.register` -- no edit needed if components self-register) | exact |
| `pyproject.toml` | config | n/a | (self) -- mirror existing `[project.optional-dependencies]` and `markers` table | exact |
| `src/converters/talend_to_v1/components/database/oracle_connection.py` (MOD) | converter | request-response | (self) -- adds 1 conditional `needs_review.append(...)` block to step 9 | exact |
| `src/converters/talend_to_v1/components/database/oracle_row.py` (MOD) | converter | request-response | (self) -- same pattern as oracle_connection D-E1 update | exact |
| `src/converters/talend_to_v1/components/database/oracle_output.py` (MOD) | converter | request-response | (self) -- same pattern as oracle_connection D-E1 update | exact |
| `tests/converters/talend_to_v1/components/database/test_oracle_connection.py` (MOD) | test | mock-free | (self) -- extend `TestNeedsReview` class | exact |
| `tests/converters/talend_to_v1/components/database/test_oracle_row.py` (MOD) | test | mock-free | (self) -- extend `TestNeedsReview` class | exact |
| `tests/converters/talend_to_v1/components/database/test_oracle_output.py` (MOD) | test | mock-free | (self) -- extend `TestNeedsReview` class | exact |

---

## Pattern Assignments

### `src/v1/engine/oracle_connection_manager.py` (NEW -- manager)

**Analog:** `src/v1/engine/java_bridge_manager.py` (167 lines total -- mirror it almost verbatim, substitute "java bridge" semantics for "oracle connection pool keyed by component id").

**Module header / imports** (lines 1-10):
```python
"""
Java Bridge Manager - Manages Java bridge lifecycle per job
"""
import logging
import socket
from typing import Optional, List

from .exceptions import JavaBridgeError

logger = logging.getLogger(__name__)
```
Mirror as: `"""Oracle Connection Manager - Manages oracledb.Connection lifecycle per job, keyed by component id."""` + `from .exceptions import ConfigurationError, ComponentExecutionError`. No socket import (no port allocation needed); add `from typing import Dict, Optional` and lazy `import oracledb` inside `start()` so the dep stays optional.

**Class skeleton with `__init__`** (lines 13-36):
```python
class JavaBridgeManager:
    """
    Manages Java bridge lifecycle for a single job.
    Each job gets its own Java process to ensure isolation.
    """

    def __init__(self, enable: bool = True, routines: Optional[List[str]] = None,
                 libraries: Optional[List[str]] = None, routine_jars: Optional[List[str]] = None):
        self.enable = enable
        self.bridge = None
        self.is_running = False
        self.port = None
        self.routines = routines or []
        self.libraries = libraries or []
        self.routine_jars = routine_jars or []
```
Mirror as:
```python
class OracleConnectionManager:
    """Manages oracledb.Connection lifecycle for a single job.

    Lives on ETLEngine alongside JavaBridgeManager / PythonRoutineManager.
    Connections are keyed by the registering component's id (e.g. "tOracleConnection_1").
    """
    def __init__(self, thick_mode: bool = False):
        self.thick_mode = thick_mode
        self.is_running = False
        self.connections: Dict[str, "oracledb.Connection"] = {}
        self._thick_initialized = False
```

**`start()` lifecycle method -- the lazy-import + idempotent init pattern** (lines 38-117):
```python
def start(self):
    """Start Java bridge with dynamic port allocation. ..."""
    if not self.enable:
        logger.info("Java execution disabled")
        return

    max_port_retries = 3
    last_error = None
    for attempt in range(1, max_port_retries + 1):
        try:
            ...
            from src.v1.java_bridge import JavaBridge
            self.bridge = JavaBridge()
            self.bridge.start(port=self.port, routine_jars=self.routine_jars)
            self.is_running = True
            break
        except Exception as e:
            ...
```
Mirror trimmed shape (no port retry needed; thick-mode init is the parallel concern):
```python
def start(self):
    if self.is_running:
        return  # Idempotent
    import oracledb
    oracledb.defaults.fetch_lobs = False  # D-B1 charset/LOB policy
    if self.thick_mode and not self._thick_initialized:
        oracledb.init_oracle_client()
        self._thick_initialized = True
        logger.info("[OK] Oracle thick mode initialized")
    self.is_running = True
    logger.info("[OK] OracleConnectionManager started (thick_mode=%s)", self.thick_mode)
```

**`stop()` -- idempotent close-all pattern** (lines 119-130):
```python
def stop(self):
    """Stop Java bridge and cleanup"""
    if self.bridge and self.is_running:
        try:
            self.bridge.stop()
            logger.info("[OK] Java bridge stopped (port %s)", self.port)
        except Exception as e:
            logger.error("[ERROR] Error stopping Java bridge: %s", e)
        finally:
            self.bridge = None
            self.is_running = False
            self.port = None
```
Mirror as iterate-over-`self.connections.values()` with per-connection try/except (D-A4b). Each bad close logged, never raised; clear dict in `finally`. Idempotent.

**`is_available()`, `__enter__`/`__exit__`, `__repr__`** (lines 136-166):
```python
def is_available(self) -> bool:
    return self.enable and self.is_running and self.bridge is not None

def __enter__(self):
    self.start()
    return self

def __exit__(self, exc_type, exc_val, exc_tb):
    self.stop()
    return False

def __repr__(self) -> str:
    status = "running" if self.is_running else "stopped"
    port_info = f"port={self.port}" if self.port else "no port"
    return f"JavaBridgeManager(status={status}, {port_info})"
```
Copy verbatim, adjust `__repr__` to `f"OracleConnectionManager(status={status}, connections={len(self.connections)})"`.

**Note on the `_find_free_port` private helper (lines 140-151):** No analog needed for Oracle (no socket binding). Skip; manager-side private helpers per Discretion are URL builders (`_build_sid_url`, `_build_service_name_url`, `_build_rac_url`) and `_open_ad_hoc(cid, config) -> Connection` / `register(cid, conn)` / `get(cid)` / `close(cid)` / `commit(cid)` / `rollback(cid)`.

**Structural note:** Mirror the public surface (`start`/`stop`/`is_available`/`__enter__`/`__exit__`/`__repr__`) so `ETLEngine._cleanup()` can wire it identically to `java_bridge_manager.stop()`. This is the single most important pattern for D-A4b.

---

### `src/v1/engine/components/database/__init__.py` (NEW -- package marker)

**Analog:** `src/v1/engine/components/aggregate/__init__.py` (lines 1-6):
```python
from .aggregate_row import AggregateRow
from .unique_row import UniqueRow

__all__ = [
    "AggregateRow", 
    "UniqueRow"]
```
Mirror as:
```python
from .oracle_connection import OracleConnection
from .oracle_row import OracleRow
from .oracle_output import OracleOutput

__all__ = ["OracleConnection", "OracleRow", "OracleOutput"]
```
**Also update** `src/v1/engine/components/__init__.py` (currently has `file/transform/aggregate/context/iterate` imports -- add `from . import database  # noqa: F401` so decorator registration triggers on engine import).

**Structural note:** Imports trigger `@REGISTRY.register` at import time -- exactly how `aggregate_row.py` etc. self-register.

---

### `src/v1/engine/components/database/oracle_connection.py` (NEW -- orchestration-only component, no FLOW)

**Analog A (orchestration shape):** `src/v1/engine/components/file/file_exist.py` -- no FLOW in/out, sets globalMap keys, returns `{"main": {<dict>}, "reject": None}`.

**Analog B (validation/process structure):** `src/v1/engine/components/control/die.py` -- raise patterns for `ConfigurationError` / `ComponentExecutionError`, `[{self.id}]` log prefix.

**Module docstring + Config Mapping format** (`die.py` lines 1-12):
```python
"""Engine component for Die (tDie).

Terminates job execution with a priority-rated error message and exit code.

Config keys consumed (6 total):
  message             (str, default "the end is near")   -- termination message
  code                (int | str, default "4")            -- error code
  priority            (int | str, default "5")            -- log level 1-6
  exit_jvm            (bool, default False)               -- accepted; not supported
  tstatcatcher_stats  (bool, default False)               -- framework param
  label               (str, default "")                   -- framework param
"""
```
Mirror as full Config Mapping for all 28 tOracleConnection params (matches `src/converters/talend_to_v1/components/database/oracle_connection.py` lines 6-34). Required by ENGINE_COMPONENT_PATTERN.md.

**Imports + REGISTRY decorator** (`file_exist.py` lines 20-32):
```python
import os
from typing import Any, Dict, Optional
import logging

from ...base_component import BaseComponent
from ...component_registry import REGISTRY
from ...exceptions import ConfigurationError

logger = logging.getLogger(__name__)


@REGISTRY.register("FileExistComponent", "FileExist", "tFileExist")
class FileExistComponent(BaseComponent):
```
Mirror as:
```python
@REGISTRY.register("OracleConnection", "tOracleConnection", "tDBConnection")
class OracleConnection(BaseComponent):
```
(Triple-alias matches converter dual-registration `tOracleConnection`/`tDBConnection` in `src/converters/talend_to_v1/components/database/oracle_connection.py:45`.)

**`_validate_config` (Rule 12 -- structural only)** (`die.py` lines 48-88):
```python
def _validate_config(self) -> None:
    """Raise ConfigurationError for invalid message, code, priority, or exit_code.

    Called on unresolved config. All numeric values may arrive as strings
    from the converter.
    """
    if "message" in self.config and self.config["message"] is not None:
        if not isinstance(self.config["message"], str):
            raise ConfigurationError(
                f"[{self.id}] Config 'message' must be a string"
            )
    if "code" in self.config:
        try:
            int(self.config["code"])
        except (ValueError, TypeError):
            raise ConfigurationError(
                f"[{self.id}] Config 'code' must be an integer; got '{self.config['code']}'"
            )
```
Mirror: only structural checks (`connection_type` in `{ORACLE_SID, ORACLE_SERVICE_NAME, ORACLE_OCI, ORACLE_RAC, ORACLE_WALLET}`; required keys present per `connection_type`). Do **NOT** validate URL syntax or resolved values here -- per D-F3 + Phase 7.1 Rule 12 those go in `_process()`.

**`_process` shape -- orchestration-only return** (`file_exist.py` lines 70-99):
```python
def _process(self, input_data: Optional[Any] = None) -> Dict[str, Any]:
    file_path = self._resolve_file_path()
    check_directory = self.config.get("check_directory", False)

    logger.info("[%s] File existence check started: %s", self.id, file_path)
    ...
    self._update_stats(rows_read=1, rows_ok=1, rows_reject=0)

    # Talend-parity globalMap variables.
    if self.global_map is not None:
        self.global_map.put(f"{self.id}_EXISTS", bool(file_exists))
        self.global_map.put(f"{self.id}_FILENAME", file_path)
    ...
    return {
        "main": {"file_exists": bool(file_exists), "file_path": file_path},
        "reject": None,
    }
```
Mirror: `_process` builds the URL, calls `self.oracle_manager.open_shared(self.id, self.config)`, sets Talend-parity metadata strings in `globalMap` (`f"connectionType_{self.id}"`, `f"dbschema_{self.id}"`, `f"username_{self.id}"`, `f"password_{self.id}"` per Talaxie `tOracleConnection_begin.javajet`), returns `{"main": {"connection_id": self.id}, "reject": None}`. **Live `oracledb.Connection` MUST NOT be put into globalMap** (D-A1).

**NotImplementedError pattern for OCI/Wallet** (`die.py` lines 127-132):
```python
error = ComponentExecutionError(
    self.id,
    f"Job terminated by tDie: {resolved_message} (exit code: {exit_code})",
)
error.exit_code = exit_code
raise error
```
Mirror with `NotImplementedError` (per D-A3 spec):
```python
raise NotImplementedError(
    f"[{self.id}] CONNECTION_TYPE {connection_type} requires oracledb thick mode + "
    f"Oracle Instant Client. Set oracle_config.thick_mode=true in job config and "
    f"install Instant Client on the host. Tracked in deferred items."
)
```

**Manager-injection requirement:** Component reads `self.oracle_manager` (set by `ETLEngine._initialize_components` mirror -- see engine.py edit below). Pattern is identical to `self.java_bridge` injection (`engine.py:140`).

---

### `src/v1/engine/components/database/oracle_row.py` (NEW -- request-response component, optional REJECT)

**Analog:** `src/v1/engine/components/aggregate/aggregate_row.py` (cleanest BaseComponent -> `_process` returns `{"main": ..., "reject": ...}` shape).

**Module docstring with full Config Mapping** (`aggregate_row.py` lines 1-14):
```python
"""Engine component for AggregateRow (tAggregateRow).

Groups input rows by specified columns and applies aggregation functions.

Config keys consumed (8 total):
  groupbys                (list[dict], default [])   -- group-by column mappings [{output_column, input_column}]
  operations              (list[dict], default [])   -- aggregation operations [{output_column, function, input_column, ignore_null}]
  list_delimiter          (str, default ",")          -- delimiter for list/list_object aggregation
  use_financial_precision (bool, default True)        -- use Decimal arithmetic for numeric aggregations
  ...
"""
```
Mirror with complete tOracleRow config keys: `query`, `use_existing_connection`, `connection`, `commit_every`, `use_preparedstatement`, `set_preparedstatement_parameters` (table), `use_nb_line`, `propagate_record_set`, `die_on_error`, plus connection params for ad-hoc mode, plus framework params.

**Imports + REGISTRY decorator** (`aggregate_row.py` lines 14-26):
```python
import logging
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

import numpy as np
import pandas as pd

from ...base_component import BaseComponent
from ...component_registry import REGISTRY
from ...exceptions import ConfigurationError

logger = logging.getLogger(__name__)
...

@REGISTRY.register("AggregateRow", "tAggregateRow")
class AggregateRow(BaseComponent):
```
Mirror as:
```python
@REGISTRY.register("OracleRow", "tOracleRow")
class OracleRow(BaseComponent):
```

**`_validate_config` -- structural only (Rule 12)** (`aggregate_row.py` lines 285-316):
```python
def _validate_config(self) -> None:
    operations = self.config.get("operations", [])
    if not isinstance(operations, list):
        raise ConfigurationError(
            f"[{self.id}] 'operations' must be a list, got {type(operations).__name__}"
        )
    for i, op in enumerate(operations):
        if not isinstance(op, dict):
            raise ConfigurationError(...)
        if "function" not in op:
            raise ConfigurationError(
                f"[{self.id}] Operation {i} missing required key 'function'"
            )
        ...
        if func not in _SUPPORTED_FUNCTIONS:
            raise ConfigurationError(
                f"[{self.id}] Operation {i} has unsupported function '{func}'. "
                f"Supported: {sorted(_SUPPORTED_FUNCTIONS)}"
            )
```
Mirror: only structural shape (`set_preparedstatement_parameters` is a list of dicts each with `parameter_index`/`parameter_type`/`parameter_value`; `use_nb_line` in `{NONE, NB_LINE_INSERTED, NB_LINE_UPDATED, NB_LINE_DELETED}`; allowed-set check on `parameter_type` 16-value table per D-C3). **Do NOT** parse SQL, validate URL, or check resolved values -- per D-F3.

**`_process` returning `{main, reject}`** (`aggregate_row.py` lines 321-331):
```python
def _process(self, input_data: Optional[pd.DataFrame] = None) -> dict:
    """Aggregate input data by group columns and operations.

    Returns:
        dict with 'main' (aggregated DataFrame) and 'reject' (None).
    """
    if input_data is None or input_data.empty:
        return {"main": pd.DataFrame(), "reject": None}

    groupbys = self.config.get("groupbys", [])
    operations = self.config.get("operations", [])
    ...
```
Mirror flow:
1. Read config keys
2. Acquire connection: `if use_existing_connection: conn = self.oracle_manager.get(self.config["connection"]); else: conn = self.oracle_manager.open_ad_hoc(self.id, self.config)`
3. Resolve `query` (BaseComponent has already done {{java}} + context resolution by the time `_process` runs -- see CONTEXT.md "Three-phase resolution")
4. Build prepared-statement bindings via the 16-type lookup table (D-C3)
5. `cursor.execute(...)` (or `executemany` for prepared-statement parameter list)
6. If `use_nb_line != "NONE"`: `self.global_map.put(f"{self.id}_<chosen>", cursor.rowcount)` (D-C5)
7. `self.global_map.put(f"{self.id}_QUERY", resolved_sql)` (D-C8)
8. Return `{"main": df_or_empty, "reject": None}` (no REJECT in tOracleRow per Talend semantics)

**PROPAGATE_RECORD_SET deferral pattern** (mirror `die.py` ConfigurationError raise):
```python
if self.config.get("propagate_record_set", False):
    raise ConfigurationError(
        f"[{self.id}] tOracleRow PROPAGATE_RECORD_SET emits a live ResultSet to a "
        f"downstream FLOW column; this Talend pattern doesn't translate cleanly to "
        f"DataFrame semantics. Tracked in deferred items -- rewrite as tOracleInput "
        f"-> downstream component when this is needed."
    )
```
This is a **content check** so it lives in `_process()`, **not** `_validate_config()` (Phase 7.1 Rule 12 / D-F3).

---

### `src/v1/engine/components/database/oracle_output.py` (NEW -- CRUD batch write with REJECT)

**Analog A (REJECT pattern):** `src/v1/engine/components/file/file_input_delimited.py` -- handles `{"main": ..., "reject": ...}` returns and `die_on_error` re-wrap.

**Analog B (`_process` per-step shape):** same `aggregate_row.py` pattern as oracle_row.

**`_process` reject + die_on_error pattern** (`file_input_delimited.py` lines 240-265):
```python
needs_row_validation = check_fields_num or check_date
main_df, reject_df = self._validate_and_convert(
    df=df,
    check_fields_num=check_fields_num,
    check_date=check_date,
    expected_col_count=expected_col_count,
    needs_row_validation=needs_row_validation,
)

# ---- 11. die_on_error boundary re-wrap (CR-03) ----
# Per-row coercion errors are now caught internally and accumulated into
# reject_df. When die_on_error=True, convert them to a typed
# DataValidationError so the engine's exception contract is preserved.
if die_on_error and reject_df is not None and len(reject_df) > 0:
    first_err = reject_df.iloc[0].get("errorMessage", "unknown") if hasattr(reject_df.iloc[0], "get") else str(reject_df.iloc[0])
    raise DataValidationError(
        f"[{self.id}] Schema/coercion failed for {len(reject_df)} row(s); "
        f"first error: {first_err}"
    )

return {"main": main_df, "reject": reject_df}
```
Mirror tOracleOutput `_process`:
1. Acquire connection (existing or ad-hoc, same as oracle_row)
2. TABLE_ACTION emitter dispatch -- one method per of the 8 actions (`_emit_create`, `_emit_create_if_not_exists`, `_emit_drop_create`, `_emit_drop_if_exists_and_create`, `_emit_clear`, `_emit_truncate`, `_emit_truncate_reuse_storage`, `NONE` no-op) per D-C1 + Discretion
3. DATA_ACTION SQL build per `INSERT`/`UPDATE`/`INSERT_OR_UPDATE`/`UPDATE_OR_INSERT`/`DELETE`. `INSERT_OR_UPDATE` / `UPDATE_OR_INSERT` use the 2-statement batched strategy (D-C2): `SELECT pk_cols WHERE pk IN (...)` -> partition matched/unmatched -> `executemany UPDATE`/`INSERT`
4. Bind via `cursor.setinputsizes()` per schema column type (D-B1)
5. `cursor.executemany(sql, rows, batcherrors=True)` (D-B2)
6. `for batch_err in cursor.getbatcherrors():` build reject row with schema `[errorCode (str), errorMessage (str), <input cols>]` (D-C7); `errorMessage = batch_err.message + " - Line: " + offset` (Talend parity)
7. Commit at `COMMIT_EVERY` cycle; trailing partial batch commits in `finalize()`
8. Set 5 globalMap stats keys per D-C8 (`{cid}_NB_LINE`, `{cid}_NB_LINE_INSERTED`, `{cid}_NB_LINE_UPDATED`, `{cid}_NB_LINE_DELETED`, `{cid}_NB_LINE_REJECTED`)
9. `die_on_error` re-wrap if rejects exist (mirror `file_input_delimited.py:253-258`)
10. `return {"main": pd.DataFrame(), "reject": reject_df}` (sink -> empty `main`)

**`@REGISTRY.register` line:**
```python
@REGISTRY.register("OracleOutput", "tOracleOutput")
class OracleOutput(BaseComponent):
```

**Structural note:** Module-level `_DEFERRED_FEATURES` dict pattern (`file_input_delimited.py:67-73`) is the canonical way to log warnings for deferred config flags -- use the same shape if any tOracleOutput flags are deferred (currently none in scope).

---

### `src/v1/engine/engine.py` (MODIFIED -- 4 in-place edits)

**Analog:** existing JavaBridgeManager wiring, lines 41/47-54/139-140/231-233 (verbatim template).

**Edit 1 -- Imports (after line 16):**
Existing (line 15-16):
```python
from .java_bridge_manager import JavaBridgeManager
from .python_routine_manager import PythonRoutineManager
```
Add immediately below:
```python
from .oracle_connection_manager import OracleConnectionManager
```

**Edit 2 -- Manager instantiation (after line 67, between `python_routine_manager` and `# Core services`):**
Existing template (lines 41-54):
```python
# Java bridge
self.java_bridge_manager = None
java_config = self.job_config.get('java_config', {})
if java_config.get('enabled', False):
    routines = java_config.get('routines', [])
    libraries = java_config.get('libraries', [])
    routine_jars = java_config.get('routine_jars', [])
    self.java_bridge_manager = JavaBridgeManager(
        enable=True, routines=routines, libraries=libraries, routine_jars=routine_jars
    )
    try:
        self.java_bridge_manager.start()
    except Exception:
        self.java_bridge_manager.stop()
        raise
```
Add after line 67 (auto-detect from component types, no `enabled` flag required per CONTEXT.md "Integration points"):
```python
# Oracle connection manager (auto-enabled if any Oracle component is in the job)
self.oracle_manager = None
oracle_types = {"OracleConnection", "tOracleConnection", "tDBConnection",
                "OracleRow", "tOracleRow", "OracleOutput", "tOracleOutput"}
has_oracle = any(c.get("type") in oracle_types for c in self.job_config.get("components", []))
if has_oracle:
    oracle_config = self.job_config.get("oracle_config", {})
    self.oracle_manager = OracleConnectionManager(
        thick_mode=oracle_config.get("thick_mode", False)
    )
    try:
        self.oracle_manager.start()
    except Exception:
        self.oracle_manager.stop()
        raise
```

**Edit 3 -- Component injection (after line 142, in `_initialize_components`):**
Existing template (lines 139-142):
```python
if self.java_bridge_manager:
    component.java_bridge = self.java_bridge_manager.bridge
if self.python_routine_manager:
    component.python_routine_manager = self.python_routine_manager
```
Add immediately below:
```python
if self.oracle_manager:
    component.oracle_manager = self.oracle_manager
```

**Edit 4 -- Cleanup (after line 233, in `_cleanup`):**
Existing template (lines 229-233):
```python
def _cleanup(self) -> None:
    """Cleanup resources including Java bridge."""
    if self.java_bridge_manager:
        logger.info("Shutting down Java bridge...")
        self.java_bridge_manager.stop()
```
Update to:
```python
def _cleanup(self) -> None:
    """Cleanup resources including Java bridge and Oracle connections."""
    if self.java_bridge_manager:
        logger.info("Shutting down Java bridge...")
        self.java_bridge_manager.stop()
    if self.oracle_manager:
        logger.info("Closing Oracle connections...")
        self.oracle_manager.stop()
```
This site is already called from success path (line 192), exception path (line 198), and `__del__` (line 241) -- no other changes needed. Connection leaks impossible per D-A4b.

---

### `src/v1/engine/component_registry.py` (NO CODE CHANGE)

The registry already supports decorator self-registration (`src/v1/engine/component_registry.py:29-55`). The Phase 11 components register themselves at import via `@REGISTRY.register("OracleConnection", "tOracleConnection", "tDBConnection")` etc. The only requirement is to add `from . import database  # noqa: F401` to `src/v1/engine/components/__init__.py` so import is triggered at engine startup (see `__init__.py` edit above). No registry-side edit.

---

### `pyproject.toml` (MODIFIED)

**Existing structure:**
```toml
[project.optional-dependencies]
java = ["pyarrow>=15.0,<24", "py4j>=0.10.9,<0.11"]
excel = ["openpyxl>=3.1,<4", "xlrd>=2.0,<3"]
xml = ["lxml>=4.9,<7"]
yaml = ["PyYAML>=6.0,<7"]
json = ["jsonpath-ng>=1.5,<2"]
api = ["fastapi>=0.111,<1", ...]
dev = ["pytest>=8.0,<10"]
all = ["dataprep[java,excel,xml,yaml,json,api]"]

[tool.pytest.ini_options]
testpaths = ["tests"]
markers = [
    "unit: Unit tests (fast, no I/O)",
    "integration: Integration tests (may require file I/O)",
    "java: Tests requiring Java bridge",
    "slow: Tests that take >5 seconds",
    "coverage: ...",
]
```
Add:
1. `oracle = ["oracledb>=2.5,<4"]` under `[project.optional-dependencies]`
2. `dev = ["pytest>=8.0,<10", "testcontainers>=4"]` (extend existing dev list, import-guarded inside conftest)
3. Update `all = ["dataprep[java,excel,xml,yaml,json,api,oracle]"]`
4. Add to `markers` list: `"oracle: Tests requiring an Oracle DB testcontainer (slow, opt-in)",`

**Structural note:** The `markers` list is the canonical pattern for new pytest markers (mirrors `java` marker added in Phase 5.1).

---

### Converter modifications (D-E1)

#### `src/converters/talend_to_v1/components/database/oracle_connection.py` (MODIFIED)

**Analog (self):** existing step 9 already has the `engine_gap` `needs_review.append(...)` pattern at lines 103-111:
```python
# ---- 9. Engine gap needs_review entries ----
needs_review.append({
    "issue": (
        "No concrete engine implementation for tOracleConnection. "
        "All config keys are extracted for future engine support."
    ),
    "component": node.component_id,
    "severity": "engine_gap",
})
```
**Replace** the `engine_gap` entry (engine now ships) with a conditional Wallet/OCI thick-mode entry:
```python
# ---- 9. Connection-type review entries (D-E1) ----
if config["connection_type"] in {"ORACLE_WALLET", "ORACLE_OCI"}:
    needs_review.append({
        "issue": (
            f"Connection type {config['connection_type']} requires "
            f"oracle_config.thick_mode=true in job config, plus Oracle "
            f"Instant Client on the host. Phase 11 raises "
            f"NotImplementedError until thick_mode is set."
        ),
        "component": node.component_id,
        "severity": "needs_review",
    })
```
**Same structural change** for `oracle_row.py` and `oracle_output.py` -- both currently emit a single `engine_gap` `needs_review.append(...)` block. The only delta is `severity: "needs_review"` (engine ships) vs the literal string above gated on `connection_type`.

#### `src/converters/talend_to_v1/components/database/oracle_row.py` (MODIFIED)

Same delta pattern as above. The converter file already extracts `connection_type`; mirror the `if connection_type in {ORACLE_WALLET, ORACLE_OCI}` guard around the `needs_review.append(...)` call.

#### `src/converters/talend_to_v1/components/database/oracle_output.py` (MODIFIED)

Same delta pattern as above.

---

### `tests/v1/engine/test_oracle_connection_manager.py` (NEW -- manager unit tests)

**Analog A (manager-style mock-based tests):** `tests/v1/engine/test_routine_loading.py` (lines 1-75) -- `_write_py_file` helper, `tmp_path` fixture, `@pytest.mark.unit` on every class.

**Analog B (mock import + start/stop pattern):** `tests/v1/engine/test_bridge.py:25-91`:
```python
def _create_bridge_with_mock():
    """Create a JavaBridge with mocked gateway and java_bridge, _started=True."""
    bridge = JavaBridge()
    mock_java_bridge = MagicMock()
    mock_java_bridge.getContext.return_value = {}
    mock_java_bridge.getGlobalMap.return_value = {}
    bridge.java_bridge = mock_java_bridge
    ...
    return bridge, mock_java_bridge

@pytest.mark.unit
class TestBridgeInit:
    def test_initial_state(self):
        bridge = JavaBridge()
        assert bridge.gateway is None
        ...

    @patch("src.v1.java_bridge.bridge.subprocess.Popen")
    @patch("src.v1.java_bridge.bridge.JavaGateway")
    def test_start_requires_port_or_default(self, mock_gateway_cls, mock_popen):
        ...
```
Mirror with `@patch("src.v1.engine.oracle_connection_manager.oracledb")` (lazy-imported inside `start()`). Test classes:
- `TestManagerInit` -- initial state (no connections, not running)
- `TestStartStop` -- idempotent start, idempotent stop, thick-mode init exactly once
- `TestRegisterAndGet` -- `manager.register(cid, mock_conn)`, `manager.get(cid)`, missing-cid raises
- `TestStopClosesAll` -- multiple registered connections all closed, one bad close doesn't block others (D-A4b)
- `TestThickMode` -- `init_oracle_client` called when `thick_mode=True`, not called when False
- `TestContextManager` -- `with OracleConnectionManager(): ...` pattern

---

### `tests/v1/engine/components/database/__init__.py` (NEW -- empty package marker)

Mirror `tests/v1/engine/components/file/__init__.py` (likely empty or single comment). Just `__init__.py` with no content needed.

---

### `tests/v1/engine/components/database/test_oracle_connection.py` (NEW -- engine component tests)

**Analog:** `tests/v1/engine/components/file/test_file_exist.py` (lines 1-80).

**Helper + fixtures pattern** (lines 10-19):
```python
def _make_component(config, global_map=None):
    gm = global_map if global_map is not None else GlobalMap()
    comp = FileExistComponent(
        component_id="tFileExist_1",
        config=config,
        global_map=gm,
        context_manager=ContextManager(),
    )
    comp.config = dict(config)
    return comp
```
Mirror as `_make_component(config, oracle_manager=None)` -- inject a `MagicMock` `oracle_manager` so component can call `self.oracle_manager.open_shared(...)`.

**TestRegistration class** (lines 22-28):
```python
@pytest.mark.unit
class TestRegistration:
    def test_registered_under_all_aliases(self):
        from src.v1.engine.component_registry import REGISTRY
        assert REGISTRY.get("FileExistComponent") is FileExistComponent
        assert REGISTRY.get("FileExist") is FileExistComponent
        assert REGISTRY.get("tFileExist") is FileExistComponent
```
Mirror with all 3 aliases: `OracleConnection`, `tOracleConnection`, `tDBConnection`.

**TestValidateConfig class** (lines 31-56) and **TestProcess** classes -- mirror shape exactly.

**Required additional class:** `TestNotImplementedConnectionTypes` -- assert `NotImplementedError` raised for `ORACLE_OCI` and `ORACLE_WALLET` per D-A3.

---

### `tests/v1/engine/components/database/test_oracle_row.py` and `test_oracle_output.py` (NEW)

**Analog:** `tests/v1/engine/components/control/test_die.py` (lines 1-100) -- the `TestRegistration` / `TestValidation` class layout matches what's needed; substitute `oracledb.Cursor` mocks for `_make_df()`. Include classes:
- `TestRegistration`
- `TestValidateConfig` (structural only)
- `TestProcess` (mock cursor, assert `executemany` called with expected SQL/binds)
- `TestUseExistingConnection` -- assert `oracle_manager.get(...)` called
- `TestAdHocConnection` -- assert `oracle_manager.open_ad_hoc(...)` called
- `TestRejectFlow` (oracle_output only) -- mock `cursor.getbatcherrors()` returns 2 BatchError objects, assert reject DataFrame schema = `[errorCode, errorMessage, <input cols>]` (D-C7)
- `TestUseNbLine` (oracle_row only) -- assert `globalMap[f"{cid}_NB_LINE_INSERTED"]` == `cursor.rowcount`
- `TestPropagateRecordSet` (oracle_row only) -- assert `ConfigurationError` per D-C4
- `TestStatsKeys` (oracle_output only) -- assert all 5 globalMap keys per D-C8
- `TestTableActions` (oracle_output only) -- one test per of the 8 TABLE_ACTION values, assert correct DDL emitted

---

### `tests/v1/engine/components/database/integration/__init__.py` (NEW -- empty package marker)

Mirror `tests/integration/__init__.py`. Empty file.

---

### `tests/v1/engine/components/database/integration/conftest.py` (NEW -- testcontainers fixture)

**No analog in this codebase.** This is a new pattern. Closest reference is `tests/integration/conftest.py` (java_bridge fixture, lines 1-86) -- shows the **structural pattern** of a session-scoped pytest fixture that gates an integration test on an external resource:

```python
@pytest.fixture(scope="session")
def java_bridge():
    """Skip if JAR is not built; otherwise yield the JAR path as a sentinel.
    ...
    """
    jar_path = _find_java_bridge_jar()
    if not jar_path.exists():
        pytest.skip(
            f"Java bridge JAR not found at {jar_path}. "
            f"Build with: cd src/v1/java_bridge/java && mvn package -q"
        )
    ...
    try:
        yield jar_path
    finally:
        if symlink_created:
            worktree_jar.unlink(missing_ok=True)
```
Mirror as `oracle_container` fixture using `testcontainers.oracle.OracleContainer`. Pattern shape:
```python
import pytest

try:
    from testcontainers.oracle import OracleContainer
    _HAS_TESTCONTAINERS = True
except ImportError:
    _HAS_TESTCONTAINERS = False

@pytest.fixture(scope="session")
def oracle_container():
    if not _HAS_TESTCONTAINERS:
        pytest.skip("testcontainers not installed; pip install -e '.[dev]'")
    with OracleContainer("gvenzl/oracle-free:23-slim") as oracle:
        yield oracle  # provides .get_connection_url() / host / port / user / pwd
```
Tests use `@pytest.mark.oracle` (the new marker registered in `pyproject.toml`) so they're opt-in via `pytest -m oracle`.

**Structural note:** Skip-on-missing-resource matches `tests/integration/conftest.py:62-66` java_bridge skip pattern verbatim.

---

### `tests/v1/engine/components/database/integration/test_oracle_e2e.py` (NEW -- end-to-end integration test)

**Analog:** `tests/integration/test_iterate_e2e.py` (lines 1-120).

**Module docstring + imports pattern** (lines 1-35):
```python
"""End-to-end integration tests for Phase 10 iterate support.

Uses real .item fixtures + real Java bridge (@pytest.mark.java).

Per Phase 5.1 lesson: mocks of the Java bridge gave false confidence for tMap;
every iterate-with-tMap-body test must use the real bridge.

Fixtures under test:
  - Job_tFileList_0.1.item:
      tFileList_1 -> (ITERATE) -> tFileInputDelimited_1 -> ...
"""
import json
import logging
from pathlib import Path
from typing import Any, Dict

import pytest

from src.converters.talend_to_v1.converter import convert_job
from src.v1.engine.engine import ETLEngine

SAMPLE_FILELIST = "tests/talend_xml_samples/Job_tFileList_0.1.item"
```
Mirror with the 3 Phase 11 sample paths:
```python
SAMPLE_CONNECTION = "tests/talend_xml_samples/Job_tOracleConnection_0.1.item"
SAMPLE_ROW = "tests/talend_xml_samples/Job_tOracleRow_0.1.item"
SAMPLE_OUTPUT = "tests/talend_xml_samples/Job_tOracleOutput_0.1.item"
```

**Helper -- mutate JSON to point at the testcontainer** (lines 47-71):
```python
def _mutate_json_paths(json_path: Path, mutations: Dict[str, Any]) -> None:
    """Load a job config JSON, apply component-config mutations, and save back.

    Args:
        json_path: Path to the JSON file to mutate in-place.
        mutations: Dict mapping component_id -> {config_key: new_value}.
    """
    with open(json_path, "r", encoding="utf-8") as f:
        config = json.load(f)
    for comp in config.get("components", []):
        comp_id = comp.get("id")
        if comp_id in mutations:
            for key, val in mutations[comp_id].items():
                comp.setdefault("config", {})[key] = val
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
```
Mirror exactly -- use it to inject `oracle_container.host` / `port` / `user` / `password` into the converter's JSON output before passing to `ETLEngine`.

**Test pattern -- convert .item -> mutate -> execute** (per `test_iterate_e2e.py` test bodies, lines ~140-200): mark with `@pytest.mark.oracle` (instead of `@pytest.mark.java`); request both `oracle_container` and `tmp_path` fixtures; call `convert_job(SAMPLE_CONNECTION, json_path)` then `_mutate_json_paths(...)` then `with ETLEngine(json_path) as engine: stats = engine.execute()`; assert on `stats["global_map"][f"tOracleOutput_1_NB_LINE_INSERTED"]` per D-C8.

**Structural note:** The `convert_job + _mutate_json_paths + ETLEngine context manager` flow is the canonical Phase-10/11 e2e pattern. No mocks at this level -- per Phase 5.1 lesson + D-D3.

---

### Converter test modifications

#### `tests/converters/talend_to_v1/components/database/test_oracle_connection.py` (MODIFIED -- extend `TestNeedsReview`)

**Analog (self):** existing `TestNeedsReview` class at lines 466-494:
```python
class TestNeedsReview:
    """Verify needs_review entries for engine gaps."""

    def test_needs_review_count(self):
        """Exactly 1 consolidated needs_review entry per D-27."""
        node = _make_node()
        result = _convert(node)
        assert len(result.needs_review) == 1

    def test_needs_review_is_engine_gap(self):
        """The needs_review entry has severity engine_gap."""
        node = _make_node()
        result = _convert(node)
        assert result.needs_review[0]["severity"] == "engine_gap"
```
Replace existing tests + add new tests:
```python
def test_no_needs_review_for_sid(self):
    """ORACLE_SID emits zero needs_review entries (engine ships it)."""
    node = _make_node(params={"CONNECTION_TYPE": '"ORACLE_SID"'})
    result = _convert(node)
    assert len(result.needs_review) == 0

def test_needs_review_for_wallet(self):
    """ORACLE_WALLET emits a thick-mode needs_review entry (D-E1)."""
    node = _make_node(params={"CONNECTION_TYPE": '"ORACLE_WALLET"'})
    result = _convert(node)
    assert len(result.needs_review) == 1
    assert "thick_mode" in result.needs_review[0]["issue"]

def test_needs_review_for_oci(self):
    """ORACLE_OCI emits a thick-mode needs_review entry (D-E1)."""
    node = _make_node(params={"CONNECTION_TYPE": '"ORACLE_OCI"'})
    result = _convert(node)
    assert len(result.needs_review) == 1
    assert "Instant Client" in result.needs_review[0]["issue"]
```

#### `tests/converters/talend_to_v1/components/database/test_oracle_row.py` (MODIFIED) and `test_oracle_output.py` (MODIFIED)

Same delta pattern -- extend `TestNeedsReview` class with the same 3 tests (`test_no_needs_review_for_sid` / `test_needs_review_for_wallet` / `test_needs_review_for_oci`).

---

## Shared Patterns

### Pattern 1: `@REGISTRY.register` decorator with PascalCase + Talend aliases

**Source:** `src/v1/engine/component_registry.py:29-55` + every component (e.g. `src/v1/engine/components/control/die.py:28`).
**Apply to:** all 3 new engine components (`oracle_connection.py`, `oracle_row.py`, `oracle_output.py`).
```python
@REGISTRY.register("Die", "tDie")
class Die(BaseComponent):
```
For Phase 11:
- `@REGISTRY.register("OracleConnection", "tOracleConnection", "tDBConnection")`
- `@REGISTRY.register("OracleRow", "tOracleRow")`
- `@REGISTRY.register("OracleOutput", "tOracleOutput")`

### Pattern 2: Module docstring with full Config Mapping

**Source:** `src/v1/engine/components/aggregate/aggregate_row.py:1-14`, `src/v1/engine/components/file/file_input_delimited.py:1-33`, `src/v1/engine/components/control/die.py:1-12`.
**Apply to:** all 3 new engine components. Required by ENGINE_COMPONENT_PATTERN.md (D-F2). Format:
```
"""Engine component for <Name> (t<Talend>).

<one-paragraph description>

Config keys consumed (N total):
  <key>  (<type>, default <val>)   -- <description>
  ...
"""
```

### Pattern 3: `[{self.id}]` log/error prefix (ASCII-only)

**Source:** every engine component (`die.py:107`, `aggregate_row.py:343`, `file_input_delimited.py:213`, etc.).
**Apply to:** all 3 new engine components and `OracleConnectionManager` for ASCII-only logging per project memory `feedback_ascii_logging.md`. No emojis, no unicode arrows. Format `f"[{self.id}] <message>"` (component side) or `"[OK]" / "[ERROR]" / "[WARN]"` (manager side, mirroring `java_bridge_manager.py:56,88,116,124`).

### Pattern 4: Phase 7.1 Rule 12 -- structural validation only in `_validate_config`

**Source:** `src/v1/engine/components/control/die.py:48-88`, `src/v1/engine/components/aggregate/aggregate_row.py:285-316`.
**Apply to:** all 3 new engine components. `_validate_config` runs **before** context resolution -- never validate URL syntax, SQL correctness, or any resolved value here. Content checks (PROPAGATE_RECORD_SET, NotImplementedError for OCI/Wallet, schema column type validity for DDL emission) belong in `_process()` per D-F3. Allowed checks: required-key-present, type-is-correct (`isinstance`), enum-membership in closed list (Phase 07.2 carve-out: see `context_load.py:74-80` precedent comment).

### Pattern 5: `_process` returning `{"main": ..., "reject": ...}` dict

**Source:** every BaseComponent subclass; canonical examples `aggregate_row.py:321-331` (no reject) and `file_input_delimited.py:265` (with reject).
**Apply to:** all 3 new engine components. `oracle_connection._process` returns `{"main": {<dict>}, "reject": None}` (orchestration). `oracle_row._process` returns `{"main": df_or_empty, "reject": None}`. `oracle_output._process` returns `{"main": pd.DataFrame(), "reject": reject_df}` (sink).

### Pattern 6: Manager injection via `_initialize_components`

**Source:** `src/v1/engine/engine.py:139-142`:
```python
if self.java_bridge_manager:
    component.java_bridge = self.java_bridge_manager.bridge
if self.python_routine_manager:
    component.python_routine_manager = self.python_routine_manager
```
**Apply to:** `engine.py` Edit 3. Components reference `self.oracle_manager` to call `.open_ad_hoc(self.id, self.config)`, `.get(connection_ref)`, `.close(self.id)`, `.commit(self.id)`, `.rollback(self.id)`.

### Pattern 7: `_cleanup` mirror call site

**Source:** `src/v1/engine/engine.py:229-233`:
```python
def _cleanup(self) -> None:
    """Cleanup resources including Java bridge."""
    if self.java_bridge_manager:
        logger.info("Shutting down Java bridge...")
        self.java_bridge_manager.stop()
```
**Apply to:** `engine.py` Edit 4. The site is already wired to success path (line 192), exception path (line 198), and `__del__` (line 241) -- one-line addition gives full leak protection (D-A4b).

### Pattern 8: `@pytest.mark.unit` on all unit-test classes

**Source:** every `tests/v1/engine/**/test_*.py` file (e.g. `test_die.py:45`, `test_file_exist.py:22`, `test_routine_loading.py:39`).
**Apply to:** all new unit-test files. `@pytest.mark.oracle` on the integration tests file only.

### Pattern 9: `tests/converters/.../test_*.py` test class layout

**Source:** `tests/converters/talend_to_v1/components/database/test_oracle_connection.py` (whole file).
**Apply to:** the 3 converter test extensions (D-E1). Existing classes (`TestRegistration`, `TestDefaults`, `TestParameterExtraction`, `TestFrameworkParams`, `TestSchema`, `TestNeedsReview`, `TestCompleteness`, `TestEdgeCases`) are the canonical layout -- only `TestNeedsReview` needs new tests for D-E1.

---

## No Analog Found

| File | Role | Data Flow | Reason | Recommendation |
|------|------|-----------|--------|----------------|
| `tests/v1/engine/components/database/integration/conftest.py` | test fixture (testcontainers) | external resource gate | testcontainers is new to this codebase; no Docker-based pytest fixtures exist | Use the **shape** of `tests/integration/conftest.py` (session-scoped fixture, `pytest.skip` on missing resource); use `testcontainers.oracle.OracleContainer("gvenzl/oracle-free:23-slim")` per D-D3. Document the new pattern in `docs/v1/standards/` if appropriate (Discretion). |

---

## Metadata

**Analog search scope:**
- `src/v1/engine/` (engine core + components/)
- `src/converters/talend_to_v1/components/database/` (existing oracle_*.py converters)
- `tests/v1/engine/` (unit tests)
- `tests/integration/` (e2e tests)
- `tests/converters/talend_to_v1/components/database/` (converter tests)
- `pyproject.toml` (config)

**Files scanned:** ~25 source files + ~10 test files

**Key patterns identified:**
1. All engine components self-register via `@REGISTRY.register("V1Name", "tTalendName"[, "talias"])` -- 3 of the new components follow this exactly.
2. Manager-style classes (`JavaBridgeManager`, `PythonRoutineManager`) follow a 5-method shape: `start() / stop() / is_available() / __enter__ + __exit__ / __repr__`. `OracleConnectionManager` mirrors this verbatim, swapping port-allocation logic for thick-mode init.
3. `ETLEngine` integration of any new manager is a 4-edit pattern (import / instantiate / inject onto components / cleanup) -- already exact templates exist.
4. `_validate_config` is structural-only (Rule 12); content checks live in `_process()`. Phase 11 components honor this for `PROPAGATE_RECORD_SET` and `NotImplementedError` for Wallet/OCI.
5. The `convert_job + _mutate_json_paths + ETLEngine` integration test pattern from `test_iterate_e2e.py` is the canonical e2e shape -- swap `@pytest.mark.java` for `@pytest.mark.oracle` and the `java_bridge` fixture for `oracle_container`.
6. ASCII-only logging is enforced via `[OK]/[ERROR]/[WARN]` prefixes (manager side) and `[{self.id}]` prefixes (component side) per project memory.

**Pattern extraction date:** 2026-05-07
