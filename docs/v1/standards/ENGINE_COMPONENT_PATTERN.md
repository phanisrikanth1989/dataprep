# Gold Standard: Engine Component Pattern

> Reference: [best example component -- TBD until Phase 4]

Every engine component MUST follow this structure.

---

## File Structure

```python
"""Engine component for {ComponentName} ({tComponentName}).

{1-2 sentence description of what the component does.}

Config keys consumed ({N} total):
  {config_key_1}  ({type}, default {value}) -- {purpose}
  {config_key_2}  ({type}, default {value}) -- {purpose}
  ...
"""
import logging
from typing import Any, Optional

import pandas as pd

from ...base_component import BaseComponent
from ...component_registry import REGISTRY
from ...exceptions import ConfigurationError, DataValidationError, FileOperationError

logger = logging.getLogger(__name__)


@REGISTRY.register("{ComponentName}", "t{ComponentName}")
class {ComponentName}(BaseComponent):
    """{tComponentName} engine implementation.

    {1-2 sentence description.}

    Config keys:
        {config_key_1}: {description}
        {config_key_2}: {description}
    """

    # ------------------------------------------------------------------
    # Configuration Validation
    # ------------------------------------------------------------------

    def _validate_config(self) -> None:
        """Validate component configuration.

        Called before every execute(). ``self.config`` contains a fresh
        deepcopy of ``_original_config`` (context variables NOT yet resolved).
        Validate structural correctness: required keys, valid enum values, etc.

        Raises:
            ConfigurationError: If configuration is invalid.
        """
        # Required keys -- fail fast with descriptive messages
        if "required_key" not in self.config:
            raise ConfigurationError(
                f"[{self.id}] Missing required config key 'required_key'"
            )

        # Enum validation
        mode = self.config.get("mode", "default")
        valid_modes = {"mode_a", "mode_b", "mode_c"}
        if mode not in valid_modes:
            raise ConfigurationError(
                f"[{self.id}] Invalid mode '{mode}'. Must be one of: {valid_modes}"
            )

    # ------------------------------------------------------------------
    # Core Processing
    # ------------------------------------------------------------------

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> dict:
        """Process data. Return dict with 'main' and optionally 'reject'.

        Args:
            input_data: Input DataFrame from upstream component, or None
                for source components.

        Returns:
            dict with keys:
                - ``main``: output DataFrame (or None)
                - ``reject``: rejected rows DataFrame (or None)
                - any other named flow keys for multi-output components
        """
        # Read config values HERE (config is resolved by BaseComponent)
        file_path = self.config.get("file_path", "")
        delimiter = self.config.get("delimiter", ",")

        # ... processing logic ...

        # Set component-specific globalMap variables
        if self.global_map:
            self.global_map.put(f"{self.id}_FILENAME", file_path)

        return {"main": output_df, "reject": None}

    # ------------------------------------------------------------------
    # Static Helpers (private, prefixed with underscore)
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_encoding(encoding_str: str) -> str:
        """Convert Talend encoding string to Python encoding name.

        Args:
            encoding_str: Encoding string from config (e.g. 'ISO-8859-15').

        Returns:
            Python-compatible encoding name.
        """
        mapping = {"ISO-8859-15": "iso-8859-15", "UTF-8": "utf-8"}
        return mapping.get(encoding_str, encoding_str)
```

---

## Rules

### Rule 1: Extend BaseComponent (or BaseIterateComponent)

Every engine component class MUST extend `BaseComponent`. For iterate-producing components (tFileList, tFlowToIterate, tForeach), extend `BaseIterateComponent` instead.

```python
from ...base_component import BaseComponent

class FilterRows(BaseComponent):
    ...
```

### Rule 2: _validate_config() is Required

Every component MUST implement `_validate_config()`. Check ALL config keys the component depends on. Raise `ConfigurationError` with a descriptive message including the component id.

```python
def _validate_config(self) -> None:
    if "file_path" not in self.config:
        raise ConfigurationError(
            f"[{self.id}] Missing required config key 'file_path'"
        )
```

`_validate_config()` is called on an UNRESOLVED config (context variables not yet substituted). Validate structural correctness (key presence, enum values) -- not resolved values.

### Rule 3: _process() Returns Dict with 'main' Key

`_process()` MUST return a dict with at least a `'main'` key containing a `pd.DataFrame` or `None`. Optional: `'reject'` key for rejected rows, and any other named flow keys.

```python
def _process(self, input_data=None) -> dict:
    return {"main": output_df, "reject": reject_df}
```

For multi-output components (e.g., tMap with multiple outputs), use named flow keys:

```python
return {"main": primary_df, "reject": reject_df, "lookup_out": lookup_df}
```

### Rule 4: NEVER Override execute()

The `execute()` method in BaseComponent implements the Template Method lifecycle:

1. Fresh config from `_original_config` (deepcopy)
2. `_validate_config()` -- your validation hook
3. `_resolve_expressions()` -- Java markers + context variable resolution
4. Read `die_on_error` from resolved config
5. `_select_mode()` -- auto-select BATCH/STREAMING based on data size
6. `_execute_batch()` or `_execute_streaming()` -- calls `_process()`
7. `_update_stats_from_result()` + `_update_global_map()`

Override ONLY `_validate_config()` and `_process()`. The lifecycle handles config immutability (ENG-09), expression resolution (ENG-03), streaming chunking (ENG-07), stats, and error wrapping.

### Rule 5: Read Config in _process(), Not __init__()

Config values are resolved by BaseComponent between `_validate_config()` and `_process()`. Context variables (`${context.var}`) and Java expressions (`{{java}}...`) are NOT available until `_process()` is called.

```python
# WRONG -- config not resolved yet, values stale on re-execute
def __init__(self, component_id, config, global_map=None, context_manager=None):
    super().__init__(component_id, config, global_map, context_manager)
    self.file_path = config.get("file_path")  # WRONG

# CORRECT -- config is fresh and resolved at _process() time
def _process(self, input_data=None) -> dict:
    file_path = self.config.get("file_path", "")
    ...
```

### Rule 6: Use GlobalMap for Inter-Component Communication

Use `self.global_map.put()` to set component-specific variables. Use `self.global_map.get()` to read variables from upstream components. Stats (NB_LINE, NB_LINE_OK, NB_LINE_REJECT) are handled automatically by BaseComponent.

```python
def _process(self, input_data=None) -> dict:
    # Set component-specific variables
    if self.global_map:
        self.global_map.put(f"{self.id}_FILENAME", file_path)
        self.global_map.put(f"{self.id}_NB_LINE_INSERTED", inserted_count)

    # Read upstream variables
    if self.global_map:
        upstream_file = self.global_map.get("tFileInput_1_FILENAME")

    return {"main": df, "reject": None}
```

Always guard with `if self.global_map:` -- components must work without one (for testing).

### Rule 7: Use Custom Exceptions

Use the exception hierarchy from `src/v1/engine/exceptions.py`:

| Exception | When to use |
|-----------|-------------|
| `ConfigurationError` | Missing/invalid config keys, bad enum values |
| `DataValidationError` | Invalid data (schema mismatch, constraint violations) |
| `FileOperationError` | File not found, permission denied, encoding errors |
| `ComponentExecutionError` | Wrapped by BaseComponent -- do NOT raise directly |
| `ExpressionError` | Invalid expressions in filters/conditions |

NEVER raise generic `Exception`, `RuntimeError`, or `ValueError` from component code. Always use the specific exception type with a descriptive message including `self.id`.

### Rule 8: Use Logger, Not print()

Every module gets its own logger. Use `logger = logging.getLogger(__name__)` at module level. Prefix log messages with `[{self.id}]` for traceability.

```python
logger = logging.getLogger(__name__)

class MyComponent(BaseComponent):
    def _process(self, input_data=None) -> dict:
        logger.info(f"[{self.id}] Processing {len(input_data)} rows")
        logger.debug(f"[{self.id}] Config: {self.config}")
        logger.warning(f"[{self.id}] No input data, returning empty DataFrame")
        logger.error(f"[{self.id}] Failed to open file: {e}")
```

Log levels:
- **DEBUG**: Data details, config dumps, intermediate values
- **INFO**: Lifecycle events (start, complete, row counts)
- **WARNING**: Degraded operation (fallback behavior, missing optional config)
- **ERROR**: Failures (caught exceptions, before re-raising)

NEVER use `print()` in component code.

### Rule 9: Register via @REGISTRY.register() Decorator

Register the component using the decorator from `component_registry.py`. Pass both the V1 name (PascalCase) and the Talend alias (with `t` prefix):

```python
from ...component_registry import REGISTRY

@REGISTRY.register("FileInputDelimited", "tFileInputDelimited")
class FileInputDelimited(BaseComponent):
    ...
```

Both names map to the same class. Registration is triggered on import -- the component's package `__init__.py` must import the module to activate the decorator.

```python
# src/v1/engine/components/file/__init__.py
from .file_input_delimited import FileInputDelimited   # triggers @REGISTRY.register
from .file_output_delimited import FileOutputDelimited  # triggers @REGISTRY.register
```

The engine uses `REGISTRY.get(comp_type)` to look up component classes at runtime.

### Rule 10: Component MUST Work After reset()

Components are re-executed during iterate loops. The `reset()` method (inherited from BaseComponent) clears stats and status. Config is re-derived from `_original_config` at the next `execute()` call.

Do NOT store mutable processing state on `self` that persists across `execute()` calls. All processing state MUST be local to `_process()`.

```python
# WRONG -- state leaks between iterate re-executions
def _process(self, input_data=None) -> dict:
    if not hasattr(self, '_accumulated'):
        self._accumulated = []
    self._accumulated.append(input_data)  # Grows across iterations!
    ...

# CORRECT -- all state is local to _process()
def _process(self, input_data=None) -> dict:
    accumulated = []
    accumulated.append(input_data)
    ...
```

### Rule 11: Schema Validation

BaseComponent runs schema validation automatically in step 7c (`_apply_output_schema_validation`) AFTER `_process()` returns. Subclasses MUST NOT call `self.validate_schema(...)` inside `_process()`.

**Rule 11 addendum (Phase 7.1):**
Subclasses MUST NOT call self.validate_schema inside `_process()`. The base class
runs validation automatically in step 7c (`_apply_output_schema_validation`) AFTER
`_process` returns. Calling it inside `_process` double-validates and races with
`_enforce_schema_column_order`'s missing-column fill.

`validate_schema` handles:
- Type coercion (Talend types to pandas dtypes)
- Nullable constraint enforcement (raises `DataValidationError` if violated, or routes to reject if `die_on_error=False`)
- Nullable integer support (uses `pd.Int64Dtype()` for int columns with NaN)
- Decimal coercion to `Decimal` objects
- Float precision rounding
- Date pattern parsing (Java patterns + Talend default chain)
- `treat_empty_as_null` per-column semantics

The engine sets `self.output_schema` and `self.input_schema` on each component instance during initialization (from the job config's `schema.output` and `schema.input` arrays). Use these attributes directly -- do NOT dig into `self.config` for schema.

```python
def _process(self, input_data=None) -> dict:
    # ... produce output_df ...
    # DO NOT call self.validate_schema() here -- BaseComponent does it automatically
    return {"main": output_df, "reject": None}
```

Note: `self.output_schema` and `self.input_schema` are set by the engine's `_initialize_components()`, not by BaseComponent's `__init__`. They are `list[dict]` where each dict has keys: `name`, `type`, `nullable`, `key`, `length`, `precision`, `date_pattern`, `treat_empty_as_null`.

---

## Schema Attributes -> treat_empty_as_null

New per-column schema attribute (Phase 7.1 D-10).

Default value:
- `True` for: `int`, `float`, `bool`, `datetime`, `Decimal` columns
- `False` for: `str` columns

Effect:
- String columns: if `True`, `""` coerces to `pd.NA`; if `False` (default), `""` stays as `""`.
- Numeric/datetime/Decimal columns: if `True` (default), `""` coerces to NaN/NaT/NA;
  if `False`, raises `DataValidationError` when `""` is encountered.

Talend parity: Talend `tFileInputDelimited` reads `""` as `""` for string columns by default,
and as null/NaN for numeric/datetime/Decimal columns.

Schema example:
```json
{
  "name": "description",
  "type": "str",
  "nullable": true,
  "treat_empty_as_null": false
}
```

---

## die_on_error Semantics

Phase 7.1 D-11. When `die_on_error=False` (config key, default `True`), schema violations route to the
reject flow with:
- `errorCode = "SCHEMA_VIOLATION"`
- `errorMessage = "Column '<name>': <reason>"`

When `die_on_error=True` (default), schema violations raise `DataValidationError`.

Violation reasons:
- `"non-nullable column has null"` -- NULL in a non-nullable column
- `"type coercion failed: <value>"` -- value cannot be coerced to the declared type
- `"length exceeded: <actual> > <schema_length>"` -- string value exceeds declared length

Reserved column names: components MUST NOT add user columns named `errorMessage`
or `errorCode`. If such columns exist on input, they are renamed to `*_user` with a
warning before the engine attaches its own reject diagnostic columns.

### Rule 12: Module Docstring with Config Mapping

Every component module MUST have a docstring that lists ALL config keys it consumes, mapping from the JSON config key to its purpose, type, and default value. This is the single source of truth for what the component reads from config.

---

## Config Access Pattern

BaseComponent handles config lifecycle automatically:

1. **Construction**: `_original_config` = deepcopy of passed config (frozen, never mutated)
2. **Each execute()**: `self.config` = fresh deepcopy of `_original_config`
3. **_validate_config()**: Runs on unresolved config -- check structural correctness
4. **_resolve_expressions()**: Java markers + context variables resolved IN PLACE on `self.config`
5. **_process()**: Runs on fully resolved config -- read values here

```python
def _process(self, input_data=None) -> dict:
    # These values are fully resolved (context vars substituted, Java evaluated)
    file_path = self.config.get("file_path", "")
    encoding = self.config.get("encoding", "UTF-8")
    header_rows = self.config.get("header", 0)
    schema = self.config.get("schema", {})
    ...
```

---

## REJECT Flow Pattern

Components that filter or validate data should route rejected rows to a `'reject'` output:

```python
def _process(self, input_data=None) -> dict:
    if input_data is None or input_data.empty:
        return {"main": input_data, "reject": None}

    # Apply filter condition
    mask = input_data["status"] == "ACTIVE"
    good_rows = input_data[mask].copy()
    bad_rows = input_data[~mask].copy()

    return {
        "main": good_rows,
        "reject": bad_rows if not bad_rows.empty else None,
    }
```

BaseComponent stats are automatically updated from the returned dict:
- `NB_LINE` = len(main) + len(reject)
- `NB_LINE_OK` = len(main)
- `NB_LINE_REJECT` = len(reject)

---

## GlobalMap Variables Pattern

Components that set Talend-compatible globalMap variables:

```python
def _process(self, input_data=None) -> dict:
    file_path = self.config.get("file_path", "")

    # Read file, produce df ...

    # Set component-specific globalMap variables (Talend naming convention)
    if self.global_map:
        self.global_map.put(f"{self.id}_FILENAME", file_path)
        self.global_map.put(f"{self.id}_NB_LINE", len(df))

    return {"main": df, "reject": None}
```

Standard globalMap variable names per Talend convention:
- `{id}_FILENAME` -- file path for file components
- `{id}_NB_LINE` -- rows processed (also set automatically via stats)
- `{id}_NB_LINE_OK` -- rows passed (also set automatically via stats)
- `{id}_NB_LINE_REJECT` -- rows rejected (also set automatically via stats)
- `{id}_NB_LINE_INSERTED` -- rows inserted (DB output components)
- `{id}_NB_LINE_UPDATED` -- rows updated (DB output components)
- `{id}_NB_LINE_DELETED` -- rows deleted (DB output components)
- `{id}_CURRENT_FILE` -- current file path (iterate file components)
- `{id}_CURRENT_FILEPATH` -- current full file path (iterate file components)
- `{id}_CURRENT_FILEDIRECTORY` -- current directory (iterate file components)
- `{id}_ERROR_MESSAGE` -- last error message

---

## Anti-Patterns

### Do NOT override execute()

```python
# WRONG
class MyComponent(BaseComponent):
    def execute(self, input_data=None) -> dict:
        # Custom lifecycle -- BREAKS stats, config immutability, expression resolution
        ...
```

### Do NOT read config in __init__

```python
# WRONG -- values are stale on re-execute, context vars not resolved
def __init__(self, component_id, config, global_map=None, context_manager=None):
    super().__init__(component_id, config, global_map, context_manager)
    self.delimiter = config.get("delimiter", ",")
```

### Do NOT mutate _original_config

```python
# WRONG -- breaks iterate re-execution (ENG-09)
def _process(self, input_data=None) -> dict:
    self._original_config["processed"] = True
```

### Do NOT use print()

```python
# WRONG
def _process(self, input_data=None) -> dict:
    print(f"Processing {len(input_data)} rows")  # Use logger.info()
```

### Do NOT raise generic Exception

```python
# WRONG
raise Exception("File not found")
# CORRECT
raise FileOperationError(f"[{self.id}] File not found: {file_path}")
```

### Do NOT store processing state on self

```python
# WRONG -- leaks between iterate re-executions
def _process(self, input_data=None) -> dict:
    self.row_count += len(input_data)  # Accumulates across iterations!

# CORRECT -- local variable, reset each call
def _process(self, input_data=None) -> dict:
    row_count = len(input_data) if input_data is not None else 0
```

---

## Iterate Component Pattern

For components that produce iterations (tFileList, tFlowToIterate, tForeach), extend `BaseIterateComponent` instead of `BaseComponent`.

```python
"""Engine component for FileList (tFileList).

Iterates over files in a directory matching a pattern.

Config keys consumed (3 total):
  directory   (str)  -- directory to scan
  file_mask   (str)  -- glob pattern to match files
  recursive   (bool, default False) -- scan subdirectories
"""
import glob
import logging
import os
from typing import Any, Optional

import pandas as pd

from ...base_iterate_component import BaseIterateComponent
from ...exceptions import ConfigurationError, FileOperationError

logger = logging.getLogger(__name__)


class FileList(BaseIterateComponent):
    """tFileList engine implementation.

    Produces a list of file paths matching a glob pattern. Each file
    triggers re-execution of downstream subjob components.
    """

    def _validate_config(self) -> None:
        """Validate iterate component configuration."""
        if "directory" not in self.config:
            raise ConfigurationError(
                f"[{self.id}] Missing required config key 'directory'"
            )

    def prepare_iterations(self, input_data=None) -> list[Any]:
        """Scan directory and return list of matching file paths.

        Returns:
            List of file path strings.
        """
        directory = self.config.get("directory", ".")
        file_mask = self.config.get("file_mask", "*")
        recursive = self.config.get("recursive", False)

        pattern = os.path.join(directory, "**" if recursive else "", file_mask)
        files = sorted(glob.glob(pattern, recursive=recursive))

        logger.info(f"[{self.id}] Found {len(files)} files matching '{file_mask}'")
        return files

    def set_iteration_globalmap(self, item: Any) -> None:
        """Set globalMap variables for current file.

        Args:
            item: File path string from prepare_iterations().
        """
        if self.global_map:
            self.global_map.put(f"{self.id}_CURRENT_FILE", os.path.basename(item))
            self.global_map.put(f"{self.id}_CURRENT_FILEPATH", item)
            self.global_map.put(
                f"{self.id}_CURRENT_FILEDIRECTORY", os.path.dirname(item)
            )
```

### Iterate Lifecycle

1. `execute()` (inherited from BaseComponent) calls `_process()`
2. `_process()` (implemented by BaseIterateComponent) calls your `prepare_iterations()`
3. Engine iterate loop calls `has_next_iteration()` / `get_next_iteration_context()`
4. `get_next_iteration_context()` calls your `set_iteration_globalmap(item)` for each item
5. After all iterations, engine calls `finalize_iterations()`

### Iterate Abstract Methods

| Method | Required | Purpose |
|--------|----------|---------|
| `_validate_config()` | YES | Validate config keys (inherited from BaseComponent) |
| `prepare_iterations(input_data)` | YES | Return list of items to iterate over |
| `set_iteration_globalmap(item)` | YES | Set globalMap variables for one iteration |

### Iterate Component Rules

- Do NOT implement `_process()` -- BaseIterateComponent provides it
- `prepare_iterations()` returns a `list[Any]` -- each item is passed to `set_iteration_globalmap()`
- `set_iteration_globalmap()` sets globalMap variables using Talend naming conventions
- Reset is handled automatically -- `BaseIterateComponent.reset()` clears iteration state

---

## BaseComponent API Reference

### Constructor

```python
BaseComponent(
    component_id: str,     # Unique ID (e.g. "tFileInput_1")
    config: dict,          # Component config dict (deepcopied and frozen)
    global_map=None,       # GlobalMap instance (optional)
    context_manager=None,  # ContextManager instance (optional)
)
```

### Instance Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `self.id` | `str` | Component identifier |
| `self._original_config` | `dict` | Frozen config (deepcopy at construction) |
| `self.config` | `dict` | Working config (fresh copy each execute()) |
| `self.global_map` | `GlobalMap` | Stats and variable storage |
| `self.context_manager` | `ContextManager` | Variable resolution |
| `self.component_type` | `str` | Component type name |
| `self.status` | `ComponentStatus` | PENDING / RUNNING / SUCCESS / ERROR / SKIPPED |
| `self.stats` | `dict[str, int]` | NB_LINE, NB_LINE_OK, NB_LINE_REJECT |
| `self.execution_mode` | `ExecutionMode` | BATCH / STREAMING / HYBRID |
| `self.die_on_error` | `bool` | Whether errors are fatal (default True) |
| `self.output_schema` | `list[dict]` | Output schema columns (set by engine, not BaseComponent) |
| `self.input_schema` | `list[dict]` | Input schema columns (set by engine, not BaseComponent) |
| `self.java_bridge` | `JavaBridge` | Set by engine if Java is enabled |
| `self.python_routine_manager` | `PythonRoutineManager` | Set by engine if Python routines enabled |

### Methods Available to Subclasses

| Method | Purpose |
|--------|---------|
| `validate_schema(df, schema)` | Validate and coerce DataFrame types |
| `_update_stats(rows_read, rows_ok, rows_reject)` | Manual stats update (rarely needed) |
| `get_status()` | Get current ComponentStatus |
| `get_stats()` | Get copy of stats dict |
| `get_python_routines()` | Get loaded Python routines dict |
| `reset()` | Clear stats and status for iterate re-execution |

### Enums

```python
class ExecutionMode(Enum):
    BATCH = "batch"          # Process entire DataFrame at once
    STREAMING = "streaming"  # Process in chunks
    HYBRID = "hybrid"        # Auto-switch based on data size

class ComponentStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    ERROR = "error"
    SKIPPED = "skipped"
```

### Exception Hierarchy

```
ETLError
  +-- ConfigurationError       # Bad config keys, invalid enum values
  +-- DataValidationError      # Schema mismatch, constraint violations
  +-- ComponentExecutionError  # Wrapped by BaseComponent (do NOT raise directly)
  +-- FileOperationError       # File not found, permission denied
  +-- JavaBridgeError          # Java-Python bridge failures
  +-- ExpressionError          # Invalid filter/condition expressions
  +-- TriggerEvaluationError   # Trigger condition evaluation failures
  +-- SchemaError              # Schema-related issues
```
