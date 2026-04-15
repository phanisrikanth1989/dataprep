# Phase 9: tContextLoad & Routines - Research

**Researched:** 2026-04-15
**Domain:** Context variable loading, Java/Python routine management
**Confidence:** HIGH

## Summary

Phase 9 has two distinct work streams: (1) rewriting the tContextLoad engine component from scratch with full Talend feature parity, and (2) hardening and extending Java/Python routine loading. The tContextLoad rewrite is well-scoped -- the converter is Green (14/14 params, no changes needed), and the exact Talend validation logic has been verified from the Talaxie javajet source. The routine work is primarily integration hardening -- the Java bridge already loads routines via `Class.forName()` and exposes them in Groovy bindings, and PythonRoutineManager already loads `.py` files from a directory.

The tContextLoad rewrite follows the established ENGINE_COMPONENT_PATTERN.md blueprint used in Phases 4-7. The key challenge is implementing the three-phase validation model: during row processing, track which context keys were assigned vs newly created; after processing, compute unloaded keys by diffing context property names against processed keys; then emit messages at configured severity levels filtered by DISABLE_* flags. The routine work involves extending the JVM classpath for JAR auto-discovery and adding subdirectory scanning to PythonRoutineManager.

**Primary recommendation:** Rewrite tContextLoad as a single-wave deliverable with full validation policy support, then harden routine loading in a second wave. Both are independent and can be planned/executed in parallel.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Full rewrite from scratch. Not patching existing context_load.py (348 lines). The existing engine ignores 6 of 12 config keys, has NaN-to-string bugs (BUG-CL-002/003), and uses slow iterrows() instead of vectorized ops. Conform to ENGINE_COMPONENT_PATTERN.md blueprint per Phase 1 D-16.
- **D-02:** Add `@REGISTRY.register('ContextLoad', 'tContextLoad')` decorator per Phase 3 D-04 registry pattern.
- **D-03:** Flow-based input is the primary mode for explicit tContextLoad. The component receives a DataFrame with `key` and `value` columns from an upstream component (typically tFileInputDelimited). File-based loading (CONTEXTFILE, FORMAT, FIELDSEPARATOR, CSV_SEPARATOR, ERROR_IF_NOT_EXISTS) is a job-level implicit context load feature, separate from the tContextLoad component itself. The converter confirms this: implicit params are NOT in _java.xml but appear in .item exports.
- **D-04:** Use vectorized pandas operations instead of row-by-row iterrows(). For DataFrame input: `df.set_index('key')['value'].to_dict()` pattern for bulk context loading. Preserves performance for large context flows.
- **D-05:** Implement LOAD_NEW_VARIABLE validation: compare incoming flow keys against known context variable names (from ContextManager). For keys NOT in existing context, emit a message at the configured severity level (ERROR/WARNING/INFO).
- **D-06:** Implement NOT_LOAD_OLD_VARIABLE validation: compare existing context variable names against incoming flow keys. For context variables NOT present in the incoming flow, emit a message at the configured severity level.
- **D-07:** DISABLE_ERROR, DISABLE_WARNINGS, DISABLE_INFO flags suppress messages at their respective levels. DISABLE_WARNINGS defaults to true. DISABLE_INFO defaults to true. DISABLE_ERROR defaults to false.
- **D-08:** When die_on_error=true and a validation produces an ERROR-level message (that is not disabled), raise ComponentExecutionError to stop the job. When die_on_error=false, log the error and continue processing.
- **D-09:** On context variable reload, preserve type information. Use ContextManager.get_type() to retrieve the original type of existing variables. When the incoming flow includes a `type` column, use that. When not, check existing type from ContextManager. Only fall back to id_String when neither source provides type info.
- **D-10:** Java routines are already partially supported. This phase validates and hardens this existing path.
- **D-11:** Add JAR auto-discovery: scan a configured directory for .jar files and add them to the JVM classpath at bridge startup BEFORE calling loadRoutine().
- **D-12:** Routine class names in java_config.routines should be fully-qualified. Engine validates they load successfully or fails fast.
- **D-13:** PythonRoutineManager already exists and works for basic loading. Extend to support: (a) subdirectory scanning for organized routine packages, (b) making routines available as a namespace in python_component/python_row_component execution context.
- **D-14:** Python routines accessible via `routines.RoutineName.method()` pattern in Python expressions.
- **D-15:** Job configs declare required routines. Engine loads at startup, fails fast if any are missing. No runtime discovery.
- **D-16:** Converter enhancement to auto-populate routine lists from Talend .item files is deferred.

### Claude's Discretion
- Internal structure of tContextLoad rewrite (method decomposition, validation ordering)
- Exact vectorized pandas implementation for bulk context loading
- PythonRoutineManager internal refactoring for subdirectory support
- Error message formatting for validation messages
- Test organization and fixture design

### Deferred Ideas (OUT OF SCOPE)
- Converter enhancement to auto-populate routine lists from Talend .item file metadata -- future phase
- Implicit context load at job level (CONTEXTFILE, FORMAT, FIELDSEPARATOR params) -- separate from tContextLoad component, could be its own enhancement
- Java routine hot-reload during job execution -- not needed for Talend parity
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CTXL-01 | Implement DIE_ON_ERROR control -- honor flag instead of always raising | Talend javajet confirms: when `DIEONERROR=true` AND a validation message at ERROR level is not suppressed by DISABLE_ERROR, `throw new RuntimeException(msg)`. When false, log and continue. BaseComponent already reads `die_on_error` from config in step 4 of lifecycle. |
| CTXL-02 | Implement LOAD_NEW_VARIABLE policy (WARNING/ERROR/NO_WARNING) for keys not in job context | Talend tracks new keys in `newPropertyList` during row processing. In `_end`, iterates list and emits messages at configured severity, filtered by DISABLE_* flags. |
| CTXL-03 | Implement NOT_LOAD_OLD_VARIABLE policy (WARNING/ERROR/NO_WARNING) for context keys not in flow | Talend computes `noAssignList` in `_end` by diffing `context.propertyNames()` against `assignList + newPropertyList`. Emits messages for each unloaded key. |
| CTXL-04 | Verify context type preservation on reload | ContextManager.get_type() and .set(key, value, value_type) already support type storage. The component must check `type` column in DataFrame first, fall back to ContextManager.get_type(), then default to id_String. |
| ROUT-01 | Java routines -- make custom utility functions callable from Java expressions | JavaBridge.loadRoutine() + addRoutinesToBinding() already work. Need to extend classpath with routine JARs. |
| ROUT-02 | Python routines -- extend PythonRoutineManager for general-purpose routine loading | Add subdirectory scanning and namespace access pattern. |
| ROUT-03 | Routine discovery from job config -- auto-load routines referenced by jobs | JavaBridgeManager already loads from java_config.routines. PythonRoutineManager needs explicit routine list support. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pandas | 3.0.1 | DataFrame operations for context variable bulk loading | Already installed, project standard [VERIFIED: runtime check] |
| pytest | 9.0.2 | Test framework | Already installed, project standard [VERIFIED: runtime check] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Python stdlib `pathlib` | 3.12 | Directory scanning for routine discovery | PythonRoutineManager subdirectory support |
| Python stdlib `importlib` | 3.12 | Dynamic module loading for Python routines | Already used by PythonRoutineManager |

No new dependencies needed. All work uses existing libraries.

## Architecture Patterns

### tContextLoad Rewrite Structure

```
src/v1/engine/components/context/
  context_load.py     # Full rewrite (replaces existing 348-line file)
  __init__.py          # Already imports ContextLoad, no change needed
```

### Pattern 1: Three-Phase Validation Model (from Talaxie Javajet Source)

**What:** Talend's tContextLoad uses a begin-main-end pattern that translates to a three-phase validation model in the Python engine:

1. **Phase A (Setup):** Initialize tracking lists: `assigned_keys`, `new_keys`
2. **Phase B (Row Processing):** For each incoming key-value pair, check if key exists in `context_manager.context`. If exists, add to `assigned_keys`. If not, add to `new_keys`. Then unconditionally assign all values to context.
3. **Phase C (Post-Processing Validation):** Compute `unloaded_keys` = `set(context_manager.context.keys()) - set(assigned_keys) - set(new_keys)`. Emit validation messages for `new_keys` (per LOAD_NEW_VARIABLE) and `unloaded_keys` (per NOT_LOAD_OLD_VARIABLE), filtered by DISABLE_* flags.

**When to use:** This is the specific pattern for tContextLoad.

**Critical Talend behavior (verified from javajet source):** [CITED: github.com/Talaxie/tdi-studio-se tContextLoad_main.javajet]
- ALL incoming variables are assigned to context unconditionally, regardless of LOAD_NEW_VARIABLE setting
- LOAD_NEW_VARIABLE only controls the MESSAGE emitted for new variables, not whether they are loaded
- NOT_LOAD_OLD_VARIABLE only controls the MESSAGE emitted for context variables not present in the flow

```python
# Source: Verified from Talaxie tContextLoad_main.javajet and tContextLoad_end.javajet
def _process(self, input_data: Optional[pd.DataFrame] = None) -> dict:
    # Phase A: Initialize tracking
    assigned_keys: set[str] = set()
    new_keys: set[str] = set()
    existing_context_keys = set(self.context_manager.context.keys())

    # Phase B: Process rows (vectorized)
    if input_data is not None and not input_data.empty:
        kv_pairs = self._extract_key_value_pairs(input_data)
        for key, value, value_type in kv_pairs:
            if key in existing_context_keys:
                assigned_keys.add(key)
            else:
                new_keys.add(key)
            # ALWAYS assign -- policies only control messages
            self.context_manager.set(key, value, value_type)

    # Phase C: Post-processing validation
    unloaded_keys = existing_context_keys - assigned_keys - new_keys
    self._emit_validation_messages(new_keys, unloaded_keys)
    ...
```

### Pattern 2: Message Level Filtering

**What:** Validation messages have a severity level (ERROR/WARNING/INFO) set by the policy config, and three DISABLE flags that suppress messages at their respective levels.

```python
# Source: Verified from Talaxie tContextLoad_end.javajet
def _should_emit_message(self, level: str) -> bool:
    """Check if a message at the given level should be emitted."""
    if level == "ERROR" and self.config.get("disable_error", False):
        return False
    if level == "WARNING" and self.config.get("disable_warnings", True):
        return False
    if level == "INFO" and self.config.get("disable_info", True):
        return False
    return True

def _emit_validation_message(self, message: str, level: str) -> None:
    """Emit a validation message at the given level if not suppressed."""
    if not self._should_emit_message(level):
        return
    if level == "ERROR":
        logger.error(f"[{self.id}] {message}")
    elif level == "WARNING":
        logger.warning(f"[{self.id}] {message}")
    else:  # INFO
        logger.info(f"[{self.id}] {message}")
```

### Pattern 3: Vectorized Context Bulk Loading

**What:** Instead of iterrows(), use pandas vectorized operations for extracting key-value pairs from the DataFrame, then iterate only for the ContextManager.set() calls (which require individual key-value pairs).

```python
# Vectorized extraction, then iterate only for context writes
keys = input_data["key"].astype(str).str.strip()
values = input_data["value"]  # Keep original types, handle NaN
has_type_col = "type" in input_data.columns
types = input_data["type"] if has_type_col else None
```

**Why:** The vectorized extraction handles NaN safely (no `str(NaN)` -> `"nan"` bug). The context writes must still iterate because `ContextManager.set()` is per-variable, but the extraction is O(1) pandas operations. [ASSUMED]

### Pattern 4: JVM Classpath Extension for Routine JARs

**What:** Extend the `-cp` argument in `JavaBridge.start()` to include additional JAR files from a configured directory.

```python
# In bridge.py start() method, before building cmd:
classpath_entries = [jar_path]
if routine_jars_dir and os.path.isdir(routine_jars_dir):
    for jar_file in sorted(Path(routine_jars_dir).glob("*.jar")):
        classpath_entries.append(str(jar_file))
classpath = os.pathsep.join(classpath_entries)
cmd = ["java", ..., "-cp", classpath, "com.citi.gru.etl.JavaBridge"]
```

**Why:** `Class.forName()` in `loadRoutine()` only works if the class is on the JVM classpath. Currently only the main bridge JAR is on the classpath. [VERIFIED: bridge.py line 89 shows `-cp jar_path` with single JAR]

### Pattern 5: PythonRoutineManager Subdirectory Scanning

**What:** Extend `_load_routines()` to recursively scan subdirectories, treating each as a package namespace.

```python
# Current: only scans top-level *.py files
routine_files = list(routines_path.glob("*.py"))

# Extended: also scan subdirectories
for subdir in routines_path.iterdir():
    if subdir.is_dir() and not subdir.name.startswith('_'):
        for py_file in subdir.glob("*.py"):
            if not py_file.name.startswith('_'):
                # Load as subdir_name.ClassName
                ...
```

### Anti-Patterns to Avoid
- **iterrows() for DataFrame processing:** Causes NaN-to-string bugs (BUG-CL-002/003) and is O(n) with high constant factor. Use vectorized extraction then iterate only for ContextManager writes.
- **Storing processing state on self:** tContextLoad tracking lists (assigned_keys, new_keys) must be local to `_process()`, not instance attributes. Per Rule 10: components must work after reset().
- **Raising generic exceptions:** Use ComponentExecutionError (for die_on_error failures) and ConfigurationError (for bad config), never ValueError or RuntimeError.
- **Skipping _validate_config():** Even though tContextLoad has minimal config requirements, still validate policy enum values (ERROR/WARNING/INFO) in _validate_config().

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Type conversion for context variables | Custom type parsing | `ContextManager.set(key, value, value_type)` which calls `_convert_type()` | Already handles all 16 Talend type IDs with proper error handling |
| Config immutability/resolution | Custom snapshot/restore | BaseComponent lifecycle (steps 1-4 of execute()) | Handles deepcopy, expression resolution, die_on_error reading |
| Stats tracking | Custom NB_LINE tracking | BaseComponent `_update_stats_from_result()` + `_update_global_map()` | Automatic from returned dict keys |
| Component registration | Manual dict entry | `@REGISTRY.register()` decorator | Project standard since Phase 3 |
| Python module dynamic loading | Custom `exec()` / `__import__` | `importlib.util.spec_from_file_location` | Already used by PythonRoutineManager, handles edge cases |

## Common Pitfalls

### Pitfall 1: NaN Contamination in DataFrame Values
**What goes wrong:** `str(row['value'])` converts NaN to literal string `"nan"`, which gets stored as a context variable value. Downstream components then process `"nan"` as a valid string.
**Why it happens:** pandas NaN values are float, and `str(float('nan'))` returns `"nan"`.
**How to avoid:** Use `pd.isna(value)` check before conversion. Skip or use `None` for NaN values.
**Warning signs:** Context variable values showing as `"nan"` string in logs.

### Pitfall 2: Unconditional Assignment Misconception
**What goes wrong:** Implementing LOAD_NEW_VARIABLE as a gate that prevents loading new variables. In Talend, ALL variables are loaded unconditionally -- the policy only controls the message.
**Why it happens:** The parameter name "LOAD_NEW_VARIABLE" implies it controls loading, but it controls message severity.
**How to avoid:** Always assign all incoming key-value pairs to context. Apply validation messages AFTER all assignments.
**Warning signs:** Jobs that work in Talend failing because new context variables aren't being set.

### Pitfall 3: DISABLE_WARNINGS Defaults to True
**What goes wrong:** Setting `disable_warnings` default to `False`, causing unexpected warning messages that don't appear in Talend.
**Why it happens:** Counter-intuitive default -- Talend suppresses warnings by default.
**How to avoid:** Match converter defaults exactly: `disable_warnings=True`, `disable_info=True`, `disable_error=False`.
**Warning signs:** Extra warning messages in Python engine output that don't appear in Talend runs.

### Pitfall 4: die_on_error Interaction with BaseComponent
**What goes wrong:** Double error handling -- tContextLoad raises ComponentExecutionError for die_on_error, and BaseComponent also wraps exceptions.
**Why it happens:** BaseComponent step 4 reads `die_on_error` from config and wraps _process() errors. But tContextLoad needs to raise ONLY when die_on_error=true AND an ERROR-level validation message is not disabled.
**How to avoid:** Use BaseComponent's built-in die_on_error mechanism. When die_on_error=true, raise ComponentExecutionError from within _process(). When false, just log. BaseComponent will let the exception propagate since it already read die_on_error=true.
**Warning signs:** Errors being swallowed when they should propagate, or exceptions when they should be logged.

### Pitfall 5: JVM Classpath is Set at Startup
**What goes wrong:** Trying to add JARs to classpath after JVM has started.
**Why it happens:** Java's standard ClassLoader doesn't support dynamic classpath extension (URLClassLoader was deprecated for this in Java 9+).
**How to avoid:** All routine JARs must be on the classpath BEFORE JVM starts. The Python `bridge.py` must assemble the full classpath in the `start()` method.
**Warning signs:** `ClassNotFoundException` when calling `loadRoutine()` despite JAR file existing.

### Pitfall 6: Python Routine Namespace Collision
**What goes wrong:** Two routines in different subdirectories with the same class name overwrite each other.
**Why it happens:** PythonRoutineManager uses `_to_class_name()` to convert filenames, and stores by class name only.
**How to avoid:** Use fully-qualified names for subdirectory routines (e.g., `system.TalendString` not just `TalendString`), or detect collisions and warn.
**Warning signs:** Wrong routine being called, missing methods on routine objects.

## Code Examples

### Example 1: Complete tContextLoad _validate_config()

```python
# Source: Derived from ENGINE_COMPONENT_PATTERN.md + converter output analysis
def _validate_config(self) -> None:
    """Validate tContextLoad configuration."""
    # Validate policy enum values
    valid_levels = {"ERROR", "WARNING", "INFO"}

    load_new = self.config.get("load_new_variable", "WARNING")
    if load_new not in valid_levels:
        raise ConfigurationError(
            f"[{self.id}] Invalid load_new_variable '{load_new}'. "
            f"Must be one of: {valid_levels}"
        )

    not_load_old = self.config.get("not_load_old_variable", "WARNING")
    if not_load_old not in valid_levels:
        raise ConfigurationError(
            f"[{self.id}] Invalid not_load_old_variable '{not_load_old}'. "
            f"Must be one of: {valid_levels}"
        )
```

### Example 2: Vectorized Key-Value Extraction with NaN Safety

```python
# Source: D-04 decision + BUG-CL-002/003 fix approach
def _extract_context_data(self, df: pd.DataFrame) -> list[tuple[str, Any, str | None]]:
    """Extract (key, value, type) triples from input DataFrame.

    Returns:
        List of (key, value, value_type) tuples. NaN values are converted to None.
    """
    if "key" not in df.columns or "value" not in df.columns:
        raise DataValidationError(
            f"[{self.id}] Input DataFrame must have 'key' and 'value' columns, "
            f"got: {list(df.columns)}"
        )

    keys = df["key"].astype(str).str.strip()
    values = df["value"]
    has_type = "type" in df.columns
    types = df["type"] if has_type else pd.Series([None] * len(df), dtype=object)

    result = []
    for i in range(len(df)):
        key = keys.iloc[i]
        val = values.iloc[i]
        if pd.isna(val):
            val = None
        typ = types.iloc[i] if has_type and not pd.isna(types.iloc[i]) else None
        result.append((key, val, typ))
    return result
```

### Example 3: GlobalMap Variables per Talend Convention

```python
# Source: Verified from Talaxie tContextLoad_end.javajet
if self.global_map:
    self.global_map.put(f"{self.id}_NB_LINE", loaded_count)
    # Talend also sets these for validation diagnostics:
    new_keys_str = ",".join(sorted(new_keys)) if new_keys else ""
    unloaded_keys_str = ",".join(sorted(unloaded_keys)) if unloaded_keys else ""
    self.global_map.put(f"{self.id}_KEY_NOT_INCONTEXT", new_keys_str)
    self.global_map.put(f"{self.id}_KEY_NOT_LOADED", unloaded_keys_str)
```

### Example 4: JVM Classpath Extension in bridge.py

```python
# Source: D-11 decision + bridge.py analysis
def start(self, port=None, routine_jars=None):
    jar_path = self._find_jar_path()
    classpath_entries = [jar_path]

    # Add routine JAR files to classpath
    if routine_jars:
        for jar in routine_jars:
            if os.path.isfile(jar):
                classpath_entries.append(jar)
                logger.info("[OK] Added routine JAR to classpath: %s", jar)
            else:
                logger.warning("[WARN] Routine JAR not found: %s", jar)

    classpath = os.pathsep.join(classpath_entries)
    cmd = [
        "java", ...,
        "-cp", classpath,
        "com.citi.gru.etl.JavaBridge",
    ]
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Row-by-row iterrows() in context_load.py | Vectorized pandas extraction + per-key context writes | Phase 9 (this phase) | Eliminates NaN-to-string bugs, improves performance |
| Single JAR classpath for Java bridge | Multi-JAR classpath with routine JARs | Phase 9 (this phase) | Enables custom Java routine loading |
| Top-level-only Python routine scanning | Recursive subdirectory scanning | Phase 9 (this phase) | Supports organized routine packages |

**Deprecated/outdated:**
- The existing `context_load.py` (348 lines): Full rewrite per D-01. Old code has file-based loading that belongs at job level (D-03), NaN bugs, iterrows(), and ignores 6 config keys.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Vectorized pandas extraction for key-value pairs then individual ContextManager.set() calls is faster than iterrows() | Architecture Patterns (Pattern 3) | LOW -- the vectorized part handles string conversion/NaN checking; the per-key loop is unavoidable for ContextManager API |
| A2 | PythonRoutineManager subdirectory scanning should use flat namespace (subdir_name.ClassName) not nested | Architecture Patterns (Pattern 5) | LOW -- can adjust namespace scheme during implementation |
| A3 | The Talend `NO_WARNING` value in CLOSED_LIST maps to our policy having no message emission (the level string is absent from the DISABLE check since there's nothing to suppress) | Code Examples | MEDIUM -- if Talend actually uses `NO_WARNING` as a literal value rather than `INFO`, the implementation may need adjustment. The converter extracts `LOAD_NEW_VARIABLE` as-is from the Talend config. |

**Note on A3:** The CONTEXT.md decisions D-05/D-06 say the severity is a CLOSED_LIST with ERROR/WARNING/INFO. But the _java.xml reportedly uses `WARNING`, `ERROR`, and `NO_WARNING` as the CLOSED_LIST items. Verified from the converter: `load_new_variable = self._get_str(node, "LOAD_NEW_VARIABLE", default="WARNING")`. The converter does not transform the value, so it passes through as-is. If Talend uses `NO_WARNING`, we need to handle it as "emit no message" -- effectively the same as the DISABLE_* flag suppressing it. This is a LOW risk since the behavior is "do nothing" in that case.

## Open Questions

1. **NO_WARNING vs INFO in CLOSED_LIST**
   - What we know: Converter extracts LOAD_NEW_VARIABLE as a string. D-05/D-06 say the values are ERROR/WARNING/INFO. The Talend _java.xml may use `NO_WARNING` instead of `INFO`.
   - What's unclear: Whether any production job configs use `NO_WARNING` vs `INFO` vs `"NO_WARNING"` as the value.
   - Recommendation: Handle both -- treat `NO_WARNING` as "suppress all messages for this policy" (same effect as having messages disabled). The implementation should accept ERROR, WARNING, INFO, and NO_WARNING.

2. **NB_CONTEXT_LOADED vs NB_LINE**
   - What we know: The existing engine sets `{id}_NB_CONTEXT_LOADED`. The Talend javajet sets `{id}_NB_LINE`. The audit report says Talend behavior unknown for `NB_CONTEXT_LOADED`.
   - What's unclear: Whether downstream jobs reference `NB_CONTEXT_LOADED` in globalMap expressions.
   - Recommendation: Set BOTH. `NB_LINE` is the Talend-standard one (verified from javajet). `NB_CONTEXT_LOADED` is set by the old engine -- keep it for backward compatibility.

3. **routine_jars_dir config key name**
   - What we know: D-11 says "scan a configured directory (e.g., java_config.routines_dir or java_config.routine_jars)".
   - What's unclear: Exact config key name to use.
   - Recommendation: Use `java_config.routine_jars` as a list of paths (more explicit than a directory scan). Support both individual JAR paths and directory paths that get expanded to all .jar files within.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 |
| Config file | pyproject.toml |
| Quick run command | `python3 -m pytest tests/v1/engine/components/context/ -x -q` |
| Full suite command | `python3 -m pytest tests/v1/engine/ -x -q` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CTXL-01 | DIE_ON_ERROR flag honored | unit | `python3 -m pytest tests/v1/engine/components/context/test_context_load.py::TestDieOnError -x` | Wave 0 |
| CTXL-02 | LOAD_NEW_VARIABLE policy with ERROR/WARNING/INFO | unit | `python3 -m pytest tests/v1/engine/components/context/test_context_load.py::TestLoadNewVariable -x` | Wave 0 |
| CTXL-03 | NOT_LOAD_OLD_VARIABLE policy | unit | `python3 -m pytest tests/v1/engine/components/context/test_context_load.py::TestNotLoadOldVariable -x` | Wave 0 |
| CTXL-04 | Type preservation on context reload | unit | `python3 -m pytest tests/v1/engine/components/context/test_context_load.py::TestTypePreservation -x` | Wave 0 |
| ROUT-01 | Java routine loading and classpath extension | unit+integration | `python3 -m pytest tests/v1/engine/test_routine_loading.py::TestJavaRoutines -x` | Wave 0 |
| ROUT-02 | Python routine subdirectory scanning | unit | `python3 -m pytest tests/v1/engine/test_routine_loading.py::TestPythonRoutines -x` | Wave 0 |
| ROUT-03 | Routine auto-discovery from job config | unit | `python3 -m pytest tests/v1/engine/test_routine_loading.py::TestRoutineDiscovery -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `python3 -m pytest tests/v1/engine/components/context/ tests/v1/engine/test_routine_loading.py -x -q`
- **Per wave merge:** `python3 -m pytest tests/v1/engine/ -x -q`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/v1/engine/components/context/test_context_load.py` -- engine tests for tContextLoad (converter tests already exist at different path)
- [ ] `tests/v1/engine/test_routine_loading.py` -- tests for Java and Python routine loading enhancements
- [ ] `tests/v1/engine/components/context/__init__.py` -- package init for test directory

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | N/A |
| V3 Session Management | no | N/A |
| V4 Access Control | no | N/A |
| V5 Input Validation | yes | Validate policy enum values in _validate_config(); validate DataFrame column presence |
| V6 Cryptography | no | N/A |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Context variable injection via DataFrame keys | Tampering | Validate key names are strings, strip whitespace; ContextManager handles type safety |
| Python routine code injection | Elevation of Privilege | PythonRoutineManager loads only from configured directory; no dynamic path injection from job config values |
| Routine JAR path traversal | Tampering | Validate JAR paths are within configured routine directory; reject absolute paths or `..` traversal |
| print_operations logging sensitive values | Information Disclosure | Documented in audit -- matches Talend behavior. Add warning about password-type context variables in log output. |

## Sources

### Primary (HIGH confidence)
- `src/v1/engine/components/context/context_load.py` -- Current engine implementation (348 lines), read in full
- `src/converters/talend_to_v1/components/context/context_load.py` -- Converter (107 lines), read in full
- `src/v1/engine/context_manager.py` -- ContextManager with set/get/get_type/resolve, read in full
- `src/v1/engine/python_routine_manager.py` -- PythonRoutineManager (180 lines), read in full
- `src/v1/java_bridge/bridge.py` -- JavaBridge Python client, key sections read
- `src/v1/java_bridge/java/src/main/java/com/citi/gru/etl/JavaBridge.java` -- loadRoutine(), addRoutinesToBinding() verified
- `src/v1/engine/java_bridge_manager.py` -- JavaBridgeManager routine loading (lines 98-110), read in full
- `docs/v1/audit/components/context/tContextLoad.md` -- Full audit report, read in full
- `docs/v1/standards/ENGINE_COMPONENT_PATTERN.md` -- Component blueprint, read in full

### Secondary (MEDIUM confidence)
- Talaxie GitHub tContextLoad_begin.javajet -- Initialization: three tracking lists (assignList, newPropertyList, noAssignList) [CITED: github.com/Talaxie/tdi-studio-se]
- Talaxie GitHub tContextLoad_main.javajet -- Row processing: unconditional assignment, key categorization [CITED: github.com/Talaxie/tdi-studio-se]
- Talaxie GitHub tContextLoad_end.javajet -- Validation: noAssignList computation, DISABLE_* filtering, die_on_error throw [CITED: github.com/Talaxie/tdi-studio-se]

### Tertiary (LOW confidence)
- None -- all findings verified from source code or Talaxie javajet templates

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new libraries, all existing infrastructure
- Architecture: HIGH -- Talend behavior verified from javajet source, engine patterns established in Phases 4-7
- Pitfalls: HIGH -- all identified from actual bugs in existing code (BUG-CL-002/003) or verified Talend behavioral quirks

**Research date:** 2026-04-15
**Valid until:** 2026-05-15 (stable domain, no external dependency changes expected)
