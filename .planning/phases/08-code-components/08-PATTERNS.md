# Phase 8: Code Components - Pattern Map

**Mapped:** 2026-04-29
**Files analyzed:** 5 source + 5 test = 10 new/rewritten files
**Analogs found:** 10 / 10 (full coverage)

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/v1/engine/components/transform/_code_component_mixin.py` | mixin (helper) | none (pure dict view) | `src/v1/engine/components/file/file_output_delimited.py::_bool` (static helper pattern) + the legacy `_get_context_dict` body | role-match |
| `src/v1/engine/components/transform/java_component.py` | component (transform) | one-shot (no input loop, side-effect via Java bridge) | `src/v1/engine/components/file/file_output_delimited.py` (sink-style passthrough, no per-row work) | exact-shape |
| `src/v1/engine/components/transform/java_row_component.py` | component (transform) | per-row REJECT-flow with Java bridge | `src/v1/engine/components/transform/filter_rows.py` (REJECT-flow shape) + `_handle_advanced` Java-bridge call site | exact |
| `src/v1/engine/components/transform/python_component.py` | component (transform) | one-shot exec | `file_output_delimited.py` (one-shot/passthrough shape) | role-match |
| `src/v1/engine/components/transform/python_row_component.py` | component (transform) | per-row REJECT-flow with compile-once exec | `filter_rows.py` (REJECT-flow + main/reject split) | exact |
| `tests/v1/engine/components/transform/test_java_component.py` | test | one-shot pass-through | `tests/v1/engine/components/file/test_file_output_delimited.py` (passthrough sink test shape) | role-match |
| `tests/v1/engine/components/transform/test_java_row_component.py` | test | per-row REJECT | `tests/v1/engine/components/transform/test_filter_rows.py` (TestRejectFlow shape) | exact |
| `tests/v1/engine/components/transform/test_python_component.py` | test | one-shot | `tests/v1/engine/components/file/test_file_output_delimited.py` | role-match |
| `tests/v1/engine/components/transform/test_python_row_component.py` | test | per-row REJECT | `tests/v1/engine/components/transform/test_filter_rows.py` | exact |
| `tests/v1/engine/components/transform/test_code_component_mixin.py` | test | unit (no DataFrame) | none direct; lightweight pytest module | role-match |

---

## Shared Patterns (apply to all 4 component rewrites)

### S1. Module-level docstring listing all config keys (canonical from `file_output_delimited.py:1-41`)

Every rewritten module MUST open with a triple-quoted docstring listing every config key consumed, with `(type, default)` plus a one-line description. Excerpt to model:

```python
"""Engine component for FileOutputDelimited (tFileOutputDelimited).

Writes DataFrame data to delimited text files with configurable formatting,
encoding, and output options. Sink component -- receives input data and writes
to disk. Returns original input DataFrame as 'main' (passthrough contract).

Config keys consumed (25 total):
  filepath            (str, required)        -- output file path
  fieldseparator      (str, default ";")     -- field delimiter character
  ...
"""
```

For Phase 8 components: list `java_code` / `python_code`, `imports`, `output_schema`, `die_on_error`, plus the shared framework keys (`tstatcatcher_stats`, `label`).

### S2. Imports block + module-level logger (canonical from `file_output_delimited.py:42-54`)

```python
import csv
import logging
import os
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from ...base_component import BaseComponent
from ...component_registry import REGISTRY
from ...exceptions import ConfigurationError, FileOperationError

logger = logging.getLogger(__name__)
```

Phase 8 should:
- Use **3-dot relative import** for `BaseComponent`, `REGISTRY`, exceptions: `from ...base_component import BaseComponent`
- Mixin lives in same package: `from ._code_component_mixin import CodeComponentMixin`
- Module logger via `logging.getLogger(__name__)` -- NEVER use `print()` (Rule 8).

### S3. `@REGISTRY.register(...)` with both V1 + Talend names (Rule 9, see `filter_rows.py:154`)

```python
@REGISTRY.register("FilterRows", "FilterRow", "tFilterRow", "tFilterRows")
class FilterRows(BaseComponent):
```

Phase 8 mappings:
- `@REGISTRY.register("JavaComponent", "tJava")`
- `@REGISTRY.register("JavaRowComponent", "tJavaRow")`
- `@REGISTRY.register("PythonComponent", "tPython", "tPythonComponent")`  -- check converter for the canonical Talend alias
- `@REGISTRY.register("PythonRowComponent", "tPythonRow")`

NOTE: the legacy partial files have NO `@REGISTRY.register` decorator -- registration was wired manually in `engine.py:COMPONENT_REGISTRY`. The rewrite MUST add the decorator (Rule 9) AND the new module must be imported from `src/v1/engine/components/transform/__init__.py` to activate the decorator on import.

### S4. Section separator convention (canonical from `file_output_delimited.py:104-128`)

```python
    # ------------------------------------------------------------------
    # Bool helper (ENG-WR-11)
    # ------------------------------------------------------------------

    @staticmethod
    def _bool(v: Any) -> bool:
        ...

    # ------------------------------------------------------------------
    # Configuration Validation
    # ------------------------------------------------------------------

    def _validate_config(self) -> None:
        ...
```

Use 66-dash rules between logical groups. Suggested ordering for Phase 8 components:
1. Static helpers (e.g. `_bool`)
2. Configuration Validation (`_validate_config`)
3. Core Processing (`_process`)
4. Namespace Construction (Python variants only -- `_build_exec_namespace`)
5. Per-row execution helper (Row variants only -- `_run_one_row`)
6. Module-level helpers (below class)

### S5. Rule 12 minimal `_validate_config` (canonical from `file_output_delimited.py:130-145`)

```python
def _validate_config(self) -> None:
    """Validate component configuration.

    Raises:
        ConfigurationError: If filepath is missing.

    Note:
        Multi-character fieldseparator validation is intentionally deferred
        to _process() after context variable resolution.  Validating here
        would incorrectly measure unresolved context references such as
        ``context.OP_DELIMITER`` as multi-character strings.
    """
    if not self.config.get("filepath"):
        raise ConfigurationError(
            f"[{self.id}] Missing required config key 'filepath'"
        )
```

Phase 8 components:
- Check key presence ONLY: `if not self.config.get("java_code"): raise ConfigurationError(...)`.
- Check container shape ONLY: `if not isinstance(self.config.get("imports", ""), str): raise ConfigurationError(...)`.
- DEFER all of: namespace whitelist enforcement, regex parse of imports block, `python_code` syntax check, output_schema content validation. These belong in `_process` (D-04, D-13, D-27).
- Always include `f"[{self.id}] ..."` prefix (Rule 7).

### S6. Custom exceptions, never bare `ValueError`/`RuntimeError` (Rule 7, contrast legacy)

Legacy `java_component.py:50` uses `raise ValueError(f"Component {self.id}: 'java_code' is required")`.
Legacy `java_component.py:54` uses `raise RuntimeError(...)`.

Rewrite MUST replace with:
- `ConfigurationError` (missing/invalid config) -- D-27
- `ComponentExecutionError` (per-row failure with `die_on_error=True`) -- D-28
- `ExpressionError` for Java-bridge call failures (parity with `filter_rows.py:454-457`)

Excerpt from `filter_rows.py:454-457` (model for Java-bridge error wrapping):

```python
except Exception as e:
    raise ExpressionError(
        f"[{self.id}] Error in Java expression at advanced_cond: {e}"
    ) from e
```

### S7. REJECT flow column convention (canonical from `filter_rows.py:244-252` + D-14/D-16)

```python
# Talend's tFilterRow REJECT flow has an extra `errorMessage` column
# holding the failed condition expression. Match that behaviour so
# downstream components (and the converter's REJECT schema) line up.
if not reject_df.empty:
    reject_df["errorMessage"] = self._build_reject_error_message()
```

Phase 8 *Row variants MUST:
- Use exact column names `errorMessage` (str) and `errorCode` (int default `1`).
- Append both columns to the rejected input row (`row.to_dict()` then `errorMessage`/`errorCode`).
- NOT use `error_message` / `error` / `PYTHON_ERROR` (legacy `python_row_component.py:109-110` violates this with `errorCode='PYTHON_ERROR'` -- a string, not int 1).
- Return `{"main": main_df, "reject": reject_df if not reject_df.empty else None}` (the `if not empty else None` shape comes from `filter_rows.py:262-265`).

### S8. Stats lifecycle -- DO NOT call `_update_stats` manually (Rule 10 + post-7.1 contract)

Both `filter_rows.py` and `file_output_delimited.py` rely on `BaseComponent._update_stats_from_result` to compute `NB_LINE / NB_LINE_OK / NB_LINE_REJECT` from `result["main"]` and `result["reject"]` lengths.

The legacy partial files all call `self._update_stats(...)` manually (e.g. `python_row_component.py:118-122`, `java_row_component.py:88-91`, `java_component.py:102`). This is the pre-7.1 double-count anti-pattern. **Remove all manual `_update_stats` calls in the rewrites** -- let BaseComponent compute from the result dict.

### S9. Three-phase config resolution is automatic (D-25)

Components MUST NOT add their own context resolution. By the time `_process` runs, `self.config` is fully resolved (BaseComponent step 3). For `java_code` / `python_code` / `imports` strings: `BaseComponent._resolve_expressions` already supports `SKIP_RESOLUTION_KEYS` for code bodies AND substring `${context.X}` resolution for non-skipped fields (D-26 documents this nuance).

---

## Pattern Assignments

### File 1. `src/v1/engine/components/transform/_code_component_mixin.py` (NEW mixin)

**Closest analog:** `file_output_delimited.py::_bool` (static helper pattern) + legacy `python_component.py:116-133` `_get_context_dict` body (the working logic to consolidate).

**File structure to follow:**
```python
"""Mixin providing shared helpers for code-execution components.

Used by JavaComponent, JavaRowComponent, PythonComponent, PythonRowComponent.
Inherited via multiple inheritance: ``class JavaComponent(CodeComponentMixin, BaseComponent)``.

Phase 8 D-09: consolidates the four near-duplicate ``_get_context_dict`` methods
that previously lived in each code component.
"""
from typing import Any

# (no other imports -- this module is dependency-free)


class CodeComponentMixin:
    """Shared helpers for code-execution components.

    NOT a BaseComponent subclass. Provides instance methods that read
    ``self.context_manager`` (set by BaseComponent.__init__).
    """

    def _get_context_dict(self) -> dict[str, Any]:
        """Return a flat dict view of context variables.

        Walks ``self.context_manager.get_all()`` and flattens both the
        nested ({Default: {var: {value: V, type: T}}}) and flat
        ({var: V}) shapes that ContextManager may produce. Suitable for
        injection as ``context`` into a user code exec namespace.
        """
        context_dict: dict[str, Any] = {}
        if self.context_manager:
            context_all = self.context_manager.get_all()
            for context_name, context_vars in context_all.items():
                if isinstance(context_vars, dict):
                    for var_name, var_info in context_vars.items():
                        if isinstance(var_info, dict) and "value" in var_info:
                            context_dict[var_name] = var_info["value"]
                        else:
                            context_dict[var_name] = var_info
                elif context_vars is not None:
                    context_dict[context_name] = context_vars
        return context_dict
```

**Source for the body:** lifted verbatim from `python_component.py:116-133` (the working logic). Both legacy `python_component.py` and `python_row_component.py` ship identical bodies; deduplicate by extraction.

**Pattern to follow:**
- Module-level docstring documenting purpose, consumers, and Phase 8 D-09 anchor.
- No registry decorator (it's not a component).
- No subclass of BaseComponent (mixin only).
- File name prefixed `_` matching the package convention -- no other module-level helpers in `transform/` use the underscore prefix yet, but it's idiomatic for "package-private" Python files.

**What NOT to copy:**
- Do NOT add a `__init__` -- the mixin must be cooperative-multiple-inheritance friendly.
- Do NOT introduce class state or other helpers in this first cut. Add more methods only if a second helper surfaces during executor planning (D-09 wording: "and any other shared helper that surfaces during planning").

**Mixin usage pattern (cite in plans for the 4 components):**
```python
class JavaComponent(CodeComponentMixin, BaseComponent):  # mixin first per D-09
    ...
```

---

### File 2. `src/v1/engine/components/transform/java_component.py` (REWRITE -- one-shot tJava)

**Closest analog:** `file_output_delimited.py` (overall shape: minimal `_validate_config`, side-effect-only `_process`, returns input passthrough as `main`).

**Imports pattern** (model from `file_output_delimited.py:42-54`, adapted):
```python
import logging
from typing import Any, Optional

import pandas as pd

from ...base_component import BaseComponent
from ...component_registry import REGISTRY
from ...exceptions import ComponentExecutionError, ConfigurationError, ExpressionError
from ._code_component_mixin import CodeComponentMixin

logger = logging.getLogger(__name__)
```

**Class declaration** (Rule 9, mixin-first per D-09):
```python
@REGISTRY.register("JavaComponent", "tJava")
class JavaComponent(CodeComponentMixin, BaseComponent):
    """tJava engine implementation -- one-shot Java/Groovy code execution.

    Executes user-supplied Java code ONCE per job invocation (not per row).
    Code has access to ``context`` and ``globalMap`` proxies. Bidirectional
    sync handled by JavaBridgeManager (D-19, D-20).

    Config keys:
        java_code (str, required): Java/Groovy source.
        imports   (str, default ""): Java import block prepended to java_code (D-07).
    """
```

**`_validate_config`** (Rule 12 minimalism, model `file_output_delimited.py:130-145`):
```python
def _validate_config(self) -> None:
    """Validate component configuration.

    Raises:
        ConfigurationError: If java_code is missing or not a string.

    Note:
        imports content shape (Java syntax validity) deferred to _process;
        the Java bridge surfaces compile errors with full diagnostics.
    """
    if not self.config.get("java_code"):
        raise ConfigurationError(
            f"[{self.id}] Missing required config key 'java_code'"
        )
    imports = self.config.get("imports", "")
    if imports and not isinstance(imports, str):
        raise ConfigurationError(
            f"[{self.id}] 'imports' must be a string"
        )
```

**`_process` shape** (passthrough, model `file_output_delimited.py:151-289` for return shape; bridge call from legacy `java_component.py:62-93`):

Key contract points:
- Read `java_code` and `imports` from `self.config` (already resolved per S9).
- Prepend `imports` per D-07: `if imports: java_code = imports + "\n" + java_code`.
- Acquire bridge via `self.java_bridge` (set by engine, NOT via `self.context_manager.get_java_bridge()` -- the legacy approach).
- If `self.java_bridge is None`: raise `ComponentExecutionError` (or `ExpressionError`) with a message that includes `self.id` (D-27).
- Bidirectional sync is handled by `JavaBridgeManager` per D-20 -- DO NOT duplicate the manual sync loops from legacy `java_component.py:65-93`.
- Call `self.java_bridge.execute_one_time_expression(java_code)` (existing protocol).
- Return `{"main": input_data, "reject": None}` (passthrough shape; matches `file_output_delimited.py:289`).
- DO NOT call `self._update_stats(...)` (S8).

**What NOT to copy from legacy `java_component.py`:**
- Lines 50, 54: `raise ValueError`, `raise RuntimeError` -- replace per S6.
- Lines 65-93: manual context+globalMap sync loops -- delete per D-20 (JavaBridgeManager owns sync).
- Line 81: `java_bridge._sync_from_java()` direct call -- handled by manager.
- Line 102: `self._update_stats(...)` -- delete per S8.
- The bare-string docstring style (lines 1-9, 19-41) -- replace with the canonical config-keys-table docstring per S1.

---

### File 3. `src/v1/engine/components/transform/java_row_component.py` (REWRITE -- per-row tJavaRow with REJECT)

**Closest analog:** `filter_rows.py` (REJECT flow shape, especially `_process` lines 216-265 and `_handle_advanced` lines 377-457 for Java-bridge dispatch).

**Imports** (per S2 + S6):
```python
import logging
from typing import Any, Optional

import pandas as pd

from ...base_component import BaseComponent
from ...component_registry import REGISTRY
from ...exceptions import ComponentExecutionError, ConfigurationError, ExpressionError
from ._code_component_mixin import CodeComponentMixin

logger = logging.getLogger(__name__)
```

**Class declaration:**
```python
@REGISTRY.register("JavaRowComponent", "tJavaRow")
class JavaRowComponent(CodeComponentMixin, BaseComponent):
    """tJavaRow engine implementation -- per-row Java/Groovy execution.

    Executes user-supplied Java code ONCE per input row. Per-row failures
    route the offending row to the reject flow with errorMessage/errorCode
    columns (D-14, D-16). When die_on_error=True, raises
    ComponentExecutionError on first failure (D-15, D-28).

    Config keys:
        java_code     (str, required): Java/Groovy source executed per row.
        imports       (str, default ""): Java import block prepended once (D-08).
        output_schema (dict|list, optional): output column types.
    """
```

**`_validate_config`** -- same shape as `JavaComponent._validate_config`. ADD `output_schema` shape check IF the converter contract requires presence (defer to converter audit during planning).

**`_process` shape** (REJECT-flow, model from `filter_rows.py:216-265`):

```python
def _process(self, input_data: Optional[pd.DataFrame] = None) -> dict:
    """Execute Java code on each row; route per-row failures to reject."""
    if input_data is None or input_data.empty:
        return {"main": input_data, "reject": None}

    java_code = self.config.get("java_code", "")
    imports = self.config.get("imports", "")
    output_schema = self.config.get("output_schema", {})

    if imports:
        java_code = imports + "\n" + java_code  # D-07

    if not self.java_bridge:
        raise ComponentExecutionError(
            self.id,
            "Java execution requested but no Java bridge available",
        )

    # D-08 + Phase 5.1 compiled-script reuse:
    # bridge compiles `java_code` once and reuses it across rows.
    try:
        result_df = self.java_bridge.execute_java_row(
            df=input_data,
            java_code=java_code,
            output_schema=output_schema,
        )
    except Exception as e:
        # Per-row error handling depends on bridge protocol -- for one-shot
        # (entire batch) failure, wrap in ExpressionError and let
        # die_on_error semantics apply at higher levels (cf. filter_rows.py:454).
        raise ExpressionError(
            f"[{self.id}] Java execution failed: {e}"
        ) from e

    # If bridge returns per-row outcomes (success / error pair), split here
    # into main_df + reject_df with errorMessage/errorCode columns (D-14, D-16).
    # Skeleton:
    main_df = result_df  # or result_df["main"] depending on bridge contract
    reject_df = None     # populate from result_df["reject"] if surfaced

    return {
        "main": main_df,
        "reject": reject_df if reject_df is not None and not reject_df.empty else None,
    }
```

NOTE for the planner: the exact bridge protocol for surfacing per-row errors needs verification during planning. If the bridge does not yet surface per-row errors, the `reject` flow may need a per-row Python-side iteration (similar to `python_row_component.py` legacy lines 70-111) using `execute_script` per row -- BUT this contradicts D-08's "compile once, reuse across loop" performance contract. Resolve this in the planning phase by reading `src/v1/engine/java_bridge_manager.py` and `src/v1/java_bridge/bridge.py`.

**Java-bridge dispatch pattern** (reference `filter_rows.py:422-457`):
```python
try:
    results = self.java_bridge.execute_tmap_preprocessing(
        df,
        {"_filter": expression},
        main_table_name=main_table_name,
        schema=schema,
    )
    ...
except Exception as e:
    raise ExpressionError(
        f"[{self.id}] Error in Java expression at advanced_cond: {e}"
    ) from e
```

The `try/except` wrapping with `raise ... from e` and `f"[{self.id}] ..."` prefix is the canonical pattern.

**What NOT to copy from legacy `java_row_component.py`:**
- Lines 50, 53, 61: `raise ValueError`/`RuntimeError` -- replace per S6.
- Lines 71-78: manual sync loops -- delete per D-20.
- Lines 88-91: manual `_update_stats` -- delete per S8.
- The output_schema enforcement does NOT belong in `_validate_config` if it can hold context vars (D-04). Defer.
- Missing REJECT flow entirely (legacy never produces a `reject` key) -- the rewrite MUST add it per D-14.

---

### File 4. `src/v1/engine/components/transform/python_component.py` (REWRITE -- one-shot tPython)

**Closest analog:** `file_output_delimited.py` for shape; legacy `python_component.py:69-101` for the namespace skeleton (which the rewrite hardens per D-11).

**Imports:**
```python
import datetime
import decimal
import json as _json_module
import logging
import math
import re as _re_module
from typing import Any, Optional

import numpy as np
import pandas as pd

from ...base_component import BaseComponent
from ...component_registry import REGISTRY
from ...exceptions import ComponentExecutionError, ConfigurationError
from ._code_component_mixin import CodeComponentMixin

logger = logging.getLogger(__name__)

# Whitelist of safe builtins for the user exec namespace (D-11).
_SAFE_BUILTINS = {
    name: __builtins__[name] if isinstance(__builtins__, dict) else getattr(__builtins__, name)
    for name in (
        "abs", "all", "any", "bool", "dict", "enumerate", "filter", "float",
        "frozenset", "int", "isinstance", "len", "list", "map", "max", "min",
        "print", "range", "repr", "round", "set", "sorted", "str", "sum",
        "tuple", "type", "zip",
    )
}

# Whitelist of safe imports surfaced into the namespace (D-11).
_SAFE_NAMESPACE_GLOBALS = {
    "pd": pd,
    "np": np,
    "datetime": datetime,
    "json": _json_module,
    "re": _re_module,
    "math": math,
    "Decimal": decimal.Decimal,
}
```

**Class declaration:**
```python
@REGISTRY.register("PythonComponent", "tPython", "tPythonComponent")
class PythonComponent(CodeComponentMixin, BaseComponent):
    """tPython engine implementation -- one-shot Python code execution.

    Executes user-supplied Python code ONCE per job invocation. Namespace
    is constructed per D-11 (curated whitelist of safe builtins and
    standard-library modules). os/sys/subprocess/eval/exec/__import__/open
    are intentionally NOT exposed (D-11). Existing user code that imports
    these names will fail with NameError -- this is a Phase 8 breaking
    change (D-12).

    Config keys:
        python_code (str, required): Python source executed once.
    """
```

**`_process` skeleton (D-11/D-13 -- whitelist enforcement at exec time, not validate time):**

```python
def _process(self, input_data: Optional[pd.DataFrame] = None) -> dict:
    python_code = self.config.get("python_code", "")
    # D-27: content check inside _process, BEFORE any broad try/except
    if not isinstance(python_code, str) or not python_code:
        raise ConfigurationError(
            f"[{self.id}] 'python_code' must be a non-empty string"
        )

    namespace = self._build_exec_namespace(input_data=None)
    try:
        exec(python_code, namespace)
    except Exception as e:
        raise ComponentExecutionError(
            self.id, f"Python code execution failed: {e}", cause=e,
        ) from e

    # Passthrough contract -- input flows through unchanged.
    return {"main": input_data, "reject": None}

def _build_exec_namespace(self, input_data: Optional[pd.DataFrame]) -> dict:
    """Build a namespace dict for exec() per D-11.

    Note:
        __builtins__ is a TIGHT dict containing only the names in
        _SAFE_BUILTINS. os, sys, subprocess, open, eval, exec, compile,
        and __import__ are intentionally absent (D-11, D-12).
    """
    return {
        "__builtins__": dict(_SAFE_BUILTINS),
        **_SAFE_NAMESPACE_GLOBALS,
        "context": self._get_context_dict(),     # from mixin (D-09)
        "globalMap": self.global_map,
        "routines": self.get_python_routines(),  # BaseComponent helper
    }
```

**What NOT to copy from legacy `python_component.py`:**
- Lines 60-61: `raise ValueError(...)` -- replace with `ConfigurationError` (S6).
- Lines 73-90: namespace construction inlined in `_process` -- extract into `_build_exec_namespace` for testability.
- Lines 93-98: `import os`, `import sys`, then `namespace['os'] = os` -- DELETE per D-11/D-12. This is the breaking change.
- Lines 78-79: `**python_routines` (routines spread directly into top-level namespace) -- preserve only the `routines` dict key (matches Talend's `Numeric.toString` style of access via `routines.Numeric.toString`); flat-spread is a security smell.
- Line 116-133: duplicate `_get_context_dict` -- inherited from mixin per D-09, so DELETE the duplicate.

---

### File 5. `src/v1/engine/components/transform/python_row_component.py` (REWRITE -- per-row Python with REJECT + compile-once)

**Closest analog:** `filter_rows.py` for REJECT flow shape; legacy `python_row_component.py:43-130` for the per-row loop body (rebuild around `compile()` + `exec()` per D-17/D-18).

**Imports:** same set as `python_component.py` (above).

**Class:**
```python
@REGISTRY.register("PythonRowComponent", "tPythonRow")
class PythonRowComponent(CodeComponentMixin, BaseComponent):
    """tPythonRow engine implementation -- per-row Python execution.

    Compiles user code ONCE (D-17) and reuses the compiled code object
    across every input row (D-18). Per-row failures route the offending
    input row to the reject flow with errorMessage/errorCode columns
    (D-14, D-16). When die_on_error=True, raises ComponentExecutionError
    on first per-row failure (D-15, D-28).

    Config keys:
        python_code   (str, required): Python source executed per row.
        output_schema (dict, optional): output column types.
    """
```

**`_process` shape (REJECT-flow + compile-once, model `filter_rows.py:216-265`):**

```python
def _process(self, input_data: Optional[pd.DataFrame] = None) -> dict:
    if input_data is None or input_data.empty:
        return {"main": input_data, "reject": None}

    python_code = self.config.get("python_code", "")
    if not isinstance(python_code, str) or not python_code:
        raise ConfigurationError(
            f"[{self.id}] 'python_code' must be a non-empty string"
        )

    # D-17: compile once, reuse across rows.
    try:
        compiled = compile(
            python_code,
            filename=f"<python_row_component:{self.id}>",
            mode="exec",
        )
    except SyntaxError as e:
        raise ConfigurationError(
            f"[{self.id}] Syntax error in python_code: {e}"
        ) from e

    output_rows = []
    reject_rows = []
    context_dict = self._get_context_dict()       # mixin, called once
    routines = self.get_python_routines()         # BaseComponent helper

    for idx, row in input_data.iterrows():
        input_row = row.to_dict()
        output_row: dict = {}
        # D-18: namespace REBUILT per row (cheap dict construction);
        # COMPILED CODE is shared.
        namespace = self._build_row_namespace(
            input_row=input_row,
            output_row=output_row,
            context_dict=context_dict,
            routines=routines,
        )
        try:
            exec(compiled, namespace)
        except Exception as e:
            if self.die_on_error:
                raise ComponentExecutionError(
                    self.id,
                    f"Python error at row index {idx}: {e}",
                    cause=e,
                ) from e
            # D-14/D-16 reject row shape:
            reject_row = dict(input_row)
            reject_row["errorMessage"] = str(e)
            reject_row["errorCode"] = 1
            reject_rows.append(reject_row)
            continue
        output_rows.append(namespace["output_row"])

    main_df = pd.DataFrame(output_rows) if output_rows else pd.DataFrame()
    reject_df = pd.DataFrame(reject_rows) if reject_rows else None

    return {"main": main_df, "reject": reject_df}
```

**REJECT-shape pattern reference** (from `filter_rows.py:241-265`):
```python
main_df = input_data[mask].copy()
reject_df = input_data[~mask].copy()

if not reject_df.empty:
    reject_df["errorMessage"] = self._build_reject_error_message()

return {
    "main": main_df,
    "reject": reject_df if not reject_df.empty else None,
}
```

Phase 8 mirrors the `if not empty else None` shape exactly.

**What NOT to copy from legacy `python_row_component.py`:**
- Lines 54-55: `raise ValueError` -- replace with `ConfigurationError` (S6).
- Lines 109-110: `errorCode='PYTHON_ERROR'` (string!) -- WRONG per D-16. MUST be `errorCode=1` (int).
- Lines 86-91: `pd`/`len`/`str`/etc. spread directly with no `__builtins__` lockdown -- harden per D-11.
- Lines 118-122: manual `_update_stats(...)` -- delete per S8.
- Lines 132-149: duplicate `_get_context_dict` -- inherit from mixin (D-09), delete.
- Lines 151-200: bespoke `_validate_output_row` with type coercion -- DELETE entirely. Output schema validation is BaseComponent step 7c (Rule 11). The legacy code violates Rule 11.
- The body re-compiles `python_code` per row implicitly via `exec(python_code, namespace)` (line 94) -- the rewrite MUST `compile()` once outside the loop (D-17).

---

### File 6. `tests/v1/engine/components/transform/test_java_component.py` (NEW)

**Closest analog:** `tests/v1/engine/components/file/test_file_output_delimited.py` (passthrough sink test shape).

**Required test classes** (per `MANUAL_COMPONENT_AUTHORING.md` table at line 402):
- `TestRegistration` -- both V1 and Talend alias resolve.
- `TestValidation` -- `_validate_config` error paths (missing java_code, non-string imports).
- `TestExecution` (`@pytest.mark.java` per D-21, D-24) -- happy path with real bridge; one-shot side effects observable via `globalMap`.
- `TestImportsPrepend` -- `imports` prepended to `java_code` before bridge call (D-07/D-08).
- `TestEdgeCases` -- None/empty input passthrough; bridge unavailable raises `ComponentExecutionError`.
- `TestStats` -- post-7.1 contract; `NB_LINE` matches input row count, no double-count.

**Fixture pattern** (model `test_filter_rows.py:31-43`):
```python
_DEFAULT_CONFIG = {
    "component_type": "JavaComponent",
    "java_code": "globalMap.put(\"hello\", \"world\");",
    "imports": "",
}

def _make_component(config=None, global_map=None):
    gm = global_map if global_map is not None else GlobalMap()
    cm = ContextManager()
    return JavaComponent(
        component_id="tJava_1",
        config=config or dict(_DEFAULT_CONFIG),
        global_map=gm,
        context_manager=cm,
    )
```

**Java-bridge marker** (per D-21, D-24):
```python
@pytest.mark.java
class TestExecution:
    """Integration tests requiring a running Java bridge JAR.

    Run: pytest tests/v1/engine/components/transform/test_java_component.py -m java
    """
    def test_one_shot_globalmap_write(self, java_bridge_fixture):
        ...
```

**What NOT to copy from existing legacy partials:** there are no Phase-7.1-conformant legacy tests for these components -- write fresh.

---

### File 7. `tests/v1/engine/components/transform/test_java_row_component.py` (NEW)

**Closest analog:** `tests/v1/engine/components/transform/test_filter_rows.py`, especially `TestRejectFlow` (lines 519-547) and `TestRejectMessage` (lines 875-901).

**Required test classes:**
- `TestRegistration`
- `TestValidation`
- `TestRowExecution` (`@pytest.mark.java`) -- happy path per row.
- `TestRejectFlow` -- per-row failure routes to reject; `errorMessage`/`errorCode` columns present (D-14/D-16); `errorCode == 1` (int); `reject is None` when no failures.
- `TestDieOnError` -- `die_on_error=True` raises `ComponentExecutionError` on first failure (D-15, D-28).
- `TestImportsPrepend` -- imports prepended once and compiled once across all rows (D-08).
- `TestEdgeCases` -- empty input passthrough; bridge unavailable.

**TestRejectFlow shape** (model `test_filter_rows.py:520-547`):
```python
def test_reject_contains_failing_rows(self):
    df = pd.DataFrame({"a": [1, 2, 3]})
    config = dict(_DEFAULT_CONFIG)
    config["java_code"] = "if (input_row.get(\"a\") == 2) throw new RuntimeException(\"boom\");"
    comp = _make_component(config=config)
    result = comp.execute(df)
    assert result["reject"] is not None
    assert len(result["reject"]) == 1
    assert int(result["reject"]["errorCode"].iloc[0]) == 1
    assert "boom" in result["reject"]["errorMessage"].iloc[0]

def test_reject_none_when_all_pass(self):
    ...
```

---

### File 8. `tests/v1/engine/components/transform/test_python_component.py` (NEW)

**Closest analog:** `test_file_output_delimited.py` for one-shot/passthrough shape.

**Required test classes:**
- `TestRegistration`
- `TestValidation` -- missing `python_code` raises `ConfigurationError`; non-string raises.
- `TestExecution` -- happy path; `globalMap.put` from user code visible after execute; `context` keys readable in user code.
- `TestNamespaceWhitelist` (D-11/D-12) -- user code referencing `os` raises `NameError` (or `ConfigurationError` per D-12 messaging) at exec time.
- `TestImports` -- whitelisted modules accessible: `pd`, `np`, `datetime`, `json`, `re`, `math`, `Decimal`.
- `TestEdgeCases` -- None/empty input passthrough; syntax error in `python_code` raises `ConfigurationError`.
- `TestStats` -- post-7.1 contract.

**Whitelist enforcement test:**
```python
def test_os_access_blocked(self):
    config = dict(_DEFAULT_CONFIG)
    config["python_code"] = "import os; globalMap.put(\"x\", os.getcwd())"
    comp = _make_component(config=config)
    with pytest.raises(ComponentExecutionError):
        comp.execute(None)
```

---

### File 9. `tests/v1/engine/components/transform/test_python_row_component.py` (NEW)

**Closest analog:** `test_filter_rows.py` (REJECT flow) + Phase 7.2 test fixture pattern.

**Required test classes:**
- `TestRegistration`
- `TestValidation`
- `TestRowExecution` -- `output_row` mutations land in `main`; per-row execution semantics; `input_row` reflects current row.
- `TestCompileOnce` (D-17/D-18) -- syntactic-error code raises `ConfigurationError` once before any iteration; verify `compile()` is called once via `unittest.mock.patch` on `builtins.compile`.
- `TestRejectFlow` -- per-row failure routes; `errorCode == 1`; `errorMessage` present.
- `TestDieOnError` -- `die_on_error=True` raises immediately.
- `TestNamespaceWhitelist` -- same as `test_python_component.py`.
- `TestEdgeCases` -- None/empty; output_schema validation handled by BaseComponent (Rule 11) NOT by component.

**TestCompileOnce skeleton:**
```python
def test_compile_called_once(self, monkeypatch):
    """D-17/D-18: compile() invoked exactly once across the row loop."""
    import builtins
    real_compile = builtins.compile
    calls = {"n": 0}
    def counting_compile(*args, **kw):
        calls["n"] += 1
        return real_compile(*args, **kw)
    monkeypatch.setattr(builtins, "compile", counting_compile)

    df = pd.DataFrame({"a": list(range(100))})
    config = dict(_DEFAULT_CONFIG)
    config["python_code"] = "output_row['a'] = input_row['a'] * 2"
    comp = _make_component(config=config)
    comp.execute(df)
    assert calls["n"] == 1, f"compile called {calls['n']} times, expected 1"
```

---

### File 10. `tests/v1/engine/components/transform/test_code_component_mixin.py` (NEW or fold into the 4 above)

**Closest analog:** none direct -- it's a unit test for a small helper class. Lightweight pytest module, no DataFrame fixtures.

**Required tests:**
- `_get_context_dict` returns `{}` when no context_manager.
- `_get_context_dict` flattens nested `{Default: {var: {value, type}}}` shape.
- `_get_context_dict` flattens flat `{var: value}` shape.
- `_get_context_dict` handles mixed shape per legacy logic.

**Decision (per D-09 latitude):** the planner may consolidate these into `test_python_component.py::TestContextDict` if a separate file is overkill. Folding-in is acceptable. Document the choice in the executor's commit message.

---

## Anti-Patterns the Rewrites MUST AVOID

Compiled from contrasts between legacy partials and the canonical 7.1 shape:

| # | Anti-pattern | Found in | Rule violated | Fix |
|---|---|---|---|---|
| AP-1 | `raise ValueError`/`raise RuntimeError` | all 4 legacy files | Rule 7 | Use `ConfigurationError` / `ComponentExecutionError` / `ExpressionError` |
| AP-2 | `print(...)` and `import os; namespace["os"] = os` | `python_component.py:93-98` | Rule 8 + D-11 | Use logger; remove os/sys exposure |
| AP-3 | Manual `_update_stats(...)` in `_process` | all 4 legacy files | Rule 10 + S8 | Delete -- BaseComponent auto-counts |
| AP-4 | Duplicate `_get_context_dict` per component | `python_component.py:116`, `python_row_component.py:132` | DRY + D-09 | Extract to `CodeComponentMixin` |
| AP-5 | `errorCode='PYTHON_ERROR'` (string) | `python_row_component.py:109` | D-16 | `errorCode=1` (int) |
| AP-6 | Re-`exec(python_code, ns)` inside loop | `python_row_component.py:94` | D-17/D-18 + PERF-02 | `compile()` once outside loop, `exec(compiled, ns)` inside |
| AP-7 | Custom `_validate_output_row` schema-coerce in component | `python_row_component.py:151-200` | Rule 11 | Delete; BaseComponent step 7c handles |
| AP-8 | Manual `java_bridge._sync_from_java()` calls | `java_component.py:81` | D-20 | Delete; JavaBridgeManager owns sync |
| AP-9 | Reading bridge via `context_manager.get_java_bridge()` | `java_component.py:59`, `java_row_component.py:66` | Engine wiring contract | Use `self.java_bridge` (set by engine) |
| AP-10 | Missing REJECT flow on `tJavaRow` | `java_row_component.py` (no reject logic) | D-14 + JROW-02 | Add reject DataFrame with errorMessage/errorCode |
| AP-11 | `_validate_config` missing entirely (relies on `_process` raise) | all 4 legacy files | Rule 2 + ENG-08 | Implement `_validate_config` per Rule 12 minimum |
| AP-12 | No `@REGISTRY.register(...)` decorator | all 4 legacy files | Rule 9 | Add decorator with both V1 and Talend names |

---

## Naming and Casing Conventions (per CLAUDE.md + MANUAL_COMPONENT_AUTHORING.md)

| Item | Convention | Phase 8 instance |
|------|-----------|------------------|
| File name | `snake_case.py` | `java_component.py`, `_code_component_mixin.py` |
| Class name | `PascalCase`, ends in `Component` for components | `JavaComponent`, `JavaRowComponent`, `PythonComponent`, `PythonRowComponent`, `CodeComponentMixin` |
| Test file | `test_<source>.py` | `test_java_component.py`, etc. |
| Method | `snake_case`; private prefixed `_` | `_validate_config`, `_process`, `_build_exec_namespace`, `_get_context_dict` |
| Module-level constants | `UPPER_SNAKE_CASE`; private `_UPPER_SNAKE_CASE` | `_SAFE_BUILTINS`, `_SAFE_NAMESPACE_GLOBALS` |
| Reject column names | exact camelCase per D-16 + Talend | `errorMessage`, `errorCode` |
| Logger | `logger = logging.getLogger(__name__)` at module level | as shown |
| Log prefix | `f"[{self.id}] ..."` (ASCII-only per project memory) | as shown -- NO emojis/unicode |
| Docstring style | triple double-quotes, Google-style for engine | as shown |

---

## No Analog Found

None. All 10 files have at least a role-match analog.

---

## Metadata

- **Analog search scope:** `src/v1/engine/components/file/`, `src/v1/engine/components/transform/`, `src/v1/engine/base_component.py`, `tests/v1/engine/components/transform/`, `tests/v1/engine/components/file/`
- **Files scanned (full read):** 11 (CONTEXT.md, file_output_delimited.py, filter_rows.py, java_component.py, java_row_component.py, python_component.py, python_row_component.py, base_component.py, MANUAL_COMPONENT_AUTHORING.md, test_filter_rows.py, test_file_output_delimited.py)
- **Pattern extraction date:** 2026-04-29
- **Phase:** 08-code-components
