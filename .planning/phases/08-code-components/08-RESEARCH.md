# Phase 8: Code Components - Research

**Researched:** 2026-04-29
**Domain:** User-supplied code execution (Java/Groovy + Python) with Talend semantic parity
**Confidence:** HIGH on engine internals and BaseComponent contract; MEDIUM on Talend tJavaRow per-row failure semantics (verified Talaxie source explicitly has no REJECT/die-on-error parameters); HIGH on Python `exec` security limitations.

## Summary

Phase 8 rewrites four code-execution components (`tJava`, `tJavaRow`, `python_component`, `python_row_component`) cleanly to the post-7.1 BaseComponent contract + Rule 11/12 contract. CONTEXT.md locks 28 decisions; this research verifies them against Talaxie source, the existing JavaBridge protocol, and BaseComponent internals, and surfaces three load-bearing findings the planner must reconcile:

1. **Code-body fields (`python_code`, `java_code`, `imports`) are NEVER context-resolved.** `ContextManager.SKIP_RESOLUTION_KEYS` (ENG-18, `src/v1/engine/context_manager.py:37-41`) explicitly skips them. CONTEXT.md D-26 must be re-interpreted: user code reads context via the `context['VAR']` programmatic dict in the exec namespace, NOT via `${context.X}` substitution into the source text.
2. **Talend tJavaRow has no native REJECT flow.** Verified directly from Talaxie `tJavaRow_java.xml` — only `SCHEMA`, `CODE`, `IMPORT` parameters; no `DIE_ON_ERROR`. The `errorMessage`/`errorCode` REJECT semantics in CONTEXT.md (D-14..D-16) are a DataPrep-specific *enhancement*, not Talend parity. Document this explicitly.
3. **The existing Java bridge `executeJavaRow` is all-or-nothing.** It compiles once and loops, but on any per-row exception it `throw new RuntimeException(...)` and the whole call fails (`JavaBridge.java:243-246`). Per D-19 ("no protocol changes"), the Python engine cannot natively split a batch failure into per-row reject. **Recommendation:** the tJavaRow REJECT contract for v1 must be "batch-level" — when `die_on_error=False` and the bridge raises, the *entire input batch* is sent to reject with a single `errorMessage` describing the failed row. Per-row reject is deferred to a future BRDG-* phase. Alternative: re-run per single-row in a Python loop when `die_on_error=False` (slow, but row-accurate) — planner must choose.

**Primary recommendation:** Plan four file rewrites (one component per file) + one new mixin file (`_code_component_mixin.py`) + four test files. Wire `@REGISTRY.register(...)` decorators (currently missing on all four — verified). Honor Rule 12 strictly for `_validate_config`. Drop `os` / `sys` from the namespace as a deliberate breaking change. For tJavaRow REJECT, plan must explicitly choose batch-level OR per-single-row retry semantics.

## User Constraints (from CONTEXT.md)

### Locked Decisions (verbatim)

- **D-01:** Treat the four existing files as legacy partial implementations. Rule 1 applies: rewrite cleanly to BaseComponent + Rule 11/12 contract. Do not patch in place.
- **D-02:** Use `file_output_delimited.py` (post-7.1 + 260429-hc2) and `tFilterRow` as canonical reference shapes.
- **D-03:** Each component is its own file in `src/v1/engine/components/transform/`. No supercomponent abstraction beyond a shared mixin.
- **D-04:** `_validate_config` may only check key presence and container shape (Rule 12). All content checks belong in `_process` after Step 3 resolution.
- **D-05:** `_process` returns `main` (DataFrame for *Row variants, None for one-shot variants) and `reject` (DataFrame with `errorMessage`/`errorCode` columns for *Row variants).
- **D-06:** `execute()` lifecycle is inherited unchanged. Components override only `_validate_config` and `_process`.
- **D-07:** `imports` config key holds a Java import block as raw text. At `_process` time, prepend it to `java_code` with a newline separator before sending to the Java bridge.
- **D-08:** Same prepend pattern for tJava (job-level) and tJavaRow (per-row). For tJavaRow, prepended-imports `java_code` is compiled ONCE at first row, reused across the loop.
- **D-09:** Create `src/v1/engine/components/transform/_code_component_mixin.py` containing `CodeComponentMixin` with consolidated `_get_context_dict()`. All four components inherit from this mixin AND from `BaseComponent`.
- **D-10:** `_get_context_dict()` returns a dict view of `self.context_manager` keyed by variable name.
- **D-11:** Build the Python exec namespace explicitly. Allow: `pandas` (as `pd`), `numpy` (as `np`), `datetime`, `json`, `re`, `math`, `decimal.Decimal`, plus `context` dict, `globalMap` proxy, `input_row`/`output_row`. Disallow `os`, `sys`, `subprocess`, `__import__`, `open`, `exec`, `eval`, `compile`, raw `__builtins__`.
- **D-12:** Document as breaking change. No silent compatibility shim.
- **D-13:** Whitelist enforcement happens in `_process` (after context resolution), not `_validate_config`.
- **D-14:** Per-row error in tJavaRow / python_row_component routes the offending input row to `reject` with appended `errorMessage` (str) and `errorCode` (int, default 1).
- **D-15:** Job continues processing remaining rows unless `die_on_error=True`.
- **D-16:** Reject column names exactly: `errorMessage`, `errorCode` (camelCase).
- **D-17:** `python_row_component` compiles once via `compile(source, filename='<python_row_component:{component_id}>', mode='exec')` and reuses the compiled code object via `exec(compiled_code, exec_namespace)` per row.
- **D-18:** Exec namespace REBUILT per row; compiled code object SHARED.
- **D-19..D-21:** Java bridge protocol unchanged. Reuse existing `compile_script`/`execute_script`. Bidirectional sync via `_sync_to_java`/`_sync_from_java` (already done by `_call_java_with_sync`). `@pytest.mark.java` integration tests mandatory.
- **D-22..D-24:** Phase 7.2 test fixture pattern. Three-test-per-fix template. Java component test files include `@pytest.mark.java` tests.
- **D-25:** Code components inherit three-phase resolution from `BaseComponent.execute()`. Components do NOT add their own resolution layer.
- **D-26:** `java_code` and `python_code` may themselves contain `${context.X}` references that resolve to substring values. **[RESEARCH NOTE: this is incorrect — see Risks/Pitfalls #1; ContextManager.SKIP_RESOLUTION_KEYS prevents this. Planner must reconcile.]**
- **D-27:** `_process` raises `ConfigurationError` for resolved-value validation failures. Place these checks BEFORE any broad try/except in `_process`.
- **D-28:** Per-row exec failures inside the user's code raise `ComponentExecutionError` ONLY when `die_on_error=True`. Otherwise the row is rejected.

### Claude's Discretion

- Exact mixin method names beyond `_get_context_dict`
- Per-row error log message format (use `[{component_id}]` prefix, ASCII-only)
- Internal method ordering inside each rewritten file (follow `file_output_delimited.py` section-separator convention)
- Test data shapes for the 4 component test files

### Deferred Ideas (OUT OF SCOPE)

- R/Groovy/arbitrary-language code components
- In-process JVM (replacing subprocess JavaBridge)
- Sandboxing the Java side
- DSL or templating on top of code components
- Performance optimization beyond compiled-once-exec-per-row (PERF-02 is satisfied by D-17/D-18)

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| JAVA-01 | tJava `imports` prepend support | D-07/D-08; verified Talaxie tJava_java.xml has IMPORT as separate ADVANCED parameter. Concatenation with `\n` separator before bridge call is correct semantics (Talend places IMPORT at file/class header in generated Java, but bridge compiles via Groovy which accepts top-of-block imports). |
| JAVA-02 | Bidirectional context/globalMap sync | Already handled by `JavaBridge._call_java_with_sync` (`bridge.py:645-676`). Components MUST NOT duplicate sync logic. |
| JAVA-03 | Standardize as engine component blueprint | Rewrite per Rule 11/12; reference `file_output_delimited.py`. |
| JROW-01 | tJavaRow `imports` prepend | Same as JAVA-01. Java side `executeJavaRow` already compiles once (`JavaBridge.java:200-204`) — D-08 is satisfied by existing protocol. |
| JROW-02 | REJECT flow for per-row Java errors | **CRITICAL CONSTRAINT:** existing `executeJavaRow` is all-or-nothing (`JavaBridge.java:243-246`). Per D-19 protocol cannot change. Planner must choose batch-level reject vs per-single-row retry. See Risks/Pitfalls #2. |
| JROW-03 | Verify input_row/output_row access patterns | Java side: `RowWrapper` for both, exposed as Groovy `Binding` variables (`JavaBridge.java:221-228`). Python side mirror = dicts. |
| JROW-04 | Standardize structure | Same as JAVA-03. |
| PYCO-01 | Standardize python_component | Same as JAVA-03. |
| PYCO-02 | Remove `os`/`sys` from namespace | D-11. **HONESTY NOTE:** this is *defensive hygiene*, not a security sandbox — Python `exec` is fundamentally not sandboxable (see Risks/Pitfalls #5). |
| PYCO-03 | Consolidate `_get_context_dict()` into mixin | D-09. Verified existing duplicates: `python_component.py:116-133` and `python_row_component.py:132-149` are byte-identical except docstring comment. |
| PYRO-01 | Standardize python_row_component | Same as JAVA-03. |
| PYRO-02 | Compiled code execution | D-17/D-18. `compile(source, filename, 'exec')` returns reusable code object; can `exec(code_obj, ns)` repeatedly with different namespaces. Verified per Python docs. Estimated 5-30x speedup for 10K rows over per-row `compile+exec` (parser is the heavy step; depends on code size). |
| PYRO-03 | Verify REJECT flow for per-row errors | D-14/D-15. Existing `python_row_component.py:105-111` already does this — pattern is sound, just needs cleanup to match `tFilterRow` reject shape (camelCase `errorCode`, integer not string). |
| TEST-07 | Engine unit tests for Python components | D-22..D-24. Phase 7.2 test fixture pattern; three-test-per-fix where applicable. |
| PERF-02 | Compiled code execution for PythonRowComponent | Same as PYRO-02. PERF-02 is *satisfied by* PYRO-02 (single requirement, two IDs). |

## Standard Stack

### Core (already in project, no installs)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pandas | 3.0.1 (project memory) | DataFrame I/O for *Row variants | Project-wide standard; all engine components use it |
| numpy | (transitive via pandas) | Numeric helpers in user code | Project-wide standard; in `bridge.py` already |
| pyarrow | 15.0.2 | Bridge serialization | Phase 2 lock |
| py4j | 0.10.9.7 | JVM gateway | Phase 2 lock |
| Python stdlib `compile` | 3.12 (3.10+ required) | Compile-once for python_row_component | PYRO-02 |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `decimal.Decimal` | stdlib | Allowed in user namespace | When user code needs precise arithmetic |
| `datetime` | stdlib | Allowed in user namespace | User time/date logic |
| `json`, `re`, `math` | stdlib | Allowed in user namespace | Common utility access |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `compile()` + `exec()` per-row | `ast.parse()` + custom interpreter | Massive complexity gain, no security gain (see Risks #5). REJECT. |
| Restricted `__builtins__` dict | Empty `{}` builtins | Empty breaks `len`, `str`, `int`, `print` etc. — too restrictive. Whitelist instead. |
| Subprocess-isolated Python (à la openedx/codejail) | seccomp/Docker | OS-level isolation, true sandbox. Architectural change beyond Phase 8 scope. |
| `RestrictedPython` (PyPI) | Whitelist namespace | Adds AST-rewriting dependency for partial security; still bypassable; OOSS for Phase 8. |

### Installation

No new packages. All deps already in project per `pyproject.toml`.

**Version verification:** Not applicable — using stdlib + already-pinned deps. `python --version` confirmed 3.12 (matches CLAUDE.md "Python 3.10+").

## Architecture Patterns

### System Architecture Diagram

```
                         ETLEngine (engine.py)
                                |
                                v
                      _execute_component(comp_id)
                                |
                                v
                  Component.execute(input_data)   [BaseComponent template method, lines 204-260]
                                |
              +-----------------+------------------+
              |                                    |
              v                                    v
        Step 1: deepcopy            Step 2: _validate_config()
        _original_config            (Rule 12: keys + shape only)
        -> self.config                              |
              |                                     v
              |                       Step 3: _resolve_expressions()
              |                       - {{java}} markers via batch bridge call
              |                       - context vars via ContextManager.resolve_dict
              |                       - SKIPPED for python_code/java_code/imports
              +--------------------+
                                   |
                                   v
                            Step 4: read die_on_error
                                   |
                                   v
                            Step 5: _process(input_data)
                                   |
              +-------------+------+--------+--------+
              |             |              |         |
              v             v              v         v
          tJava        tJavaRow     pythonComponent  pythonRowComponent
              |             |              |         |
              v             v              v         v
      bridge.execute_   bridge.execute_  exec(src,  compile(src) ONCE, then
      one_time_         java_row()       ns)        for each row: rebuild ns
      expression()      [compile-once    [one-shot] + exec(code_obj, ns)
      [one-shot]        Java side]                  + populate output_row
              |             |              |         |
              +------+------+              +----+----+
                     |                          |
                     v                          v
              JavaBridge subprocess     CodeComponentMixin
              + bidirectional sync      + namespace whitelist
              (Phase 2/5.1 lock)        + reject collection
                     |                          |
                     +-----------+--------------+
                                 |
                                 v
                         result = {"main": df, "reject": df-or-None}
                                 |
                                 v
                       Step 7b: _enforce_schema_column_order
                       Step 7c: _apply_output_schema_validation
                       Step 8:  _update_stats_from_result + _update_global_map
```

### Recommended Project Structure

```
src/v1/engine/components/transform/
├── _code_component_mixin.py       [NEW] CodeComponentMixin._get_context_dict
├── java_component.py              [REWRITE] tJava
├── java_row_component.py          [REWRITE] tJavaRow
├── python_component.py            [REWRITE] python_component
├── python_row_component.py        [REWRITE] python_row_component
└── __init__.py                    [VERIFY] keep imports

tests/v1/engine/components/transform/
├── test_java_component.py         [NEW]
├── test_java_row_component.py     [NEW]
├── test_python_component.py       [NEW]
└── test_python_row_component.py   [NEW]
```

### Pattern 1: Rule 12-compliant `_validate_config`

```python
# Source: file_output_delimited.py:130-145 (canonical post-7.1 shape)
def _validate_config(self) -> None:
    """Validate component configuration.

    Note:
        All content checks (whitelist enforcement, code non-empty,
        imports type, output_schema shape per-element) are deferred
        to _process() after context-variable resolution. Per Rule 12
        (Phase 7.2), this method only checks key presence and
        container shape.
    """
    # tJavaRow / python_row_component example
    if not self.config.get("java_code"):  # presence only
        raise ConfigurationError(
            f"[{self.id}] Missing required config key 'java_code'"
        )
    output_schema = self.config.get("output_schema", {})
    if not isinstance(output_schema, (dict, list)):  # shape only
        raise ConfigurationError(
            f"[{self.id}] 'output_schema' must be a dict or list"
        )
```

### Pattern 2: Rule 12-compliant deferred check in `_process`

```python
# Source: send_mail.py post-7.2 (Phase 7.2 lesson: BEFORE broad try/except)
def _process(self, input_data: Optional[pd.DataFrame] = None) -> dict:
    # ---- Deferred content checks (Rule 12) -- BEFORE any try/except ----
    python_code = self.config.get("python_code", "")
    if not isinstance(python_code, str):
        raise ConfigurationError(
            f"[{self.id}] 'python_code' must be a string"
        )
    if not python_code.strip():
        raise ConfigurationError(
            f"[{self.id}] 'python_code' must be non-empty after resolution"
        )

    # ---- Main work (may have try/except inside) ----
    try:
        ...
    except Exception as e:
        raise ComponentExecutionError(self.id, str(e), cause=e) from e
```

### Pattern 3: Compile-once Python (PYRO-02 / D-17/D-18)

```python
# Compile ONCE at the start of _process (cheap dict construction per row)
filename = f"<python_row_component:{self.id}>"
try:
    compiled_code = compile(python_code, filename, "exec")
except SyntaxError as e:
    raise ConfigurationError(
        f"[{self.id}] python_code has syntax error: {e}"
    ) from e

output_rows: list[dict] = []
reject_rows: list[dict] = []
for idx, row in input_data.iterrows():
    input_row = row.to_dict()
    output_row: dict = {}
    namespace = self._build_exec_namespace(input_row, output_row)  # rebuilt per row
    try:
        exec(compiled_code, namespace)
        output_rows.append(output_row)
    except Exception as e:
        if self.die_on_error:
            raise ComponentExecutionError(
                self.id,
                f"row {idx}: {e}",
                cause=e,
            ) from e
        reject = dict(input_row)
        reject["errorMessage"] = str(e)
        reject["errorCode"] = 1
        reject_rows.append(reject)
```

### Pattern 4: Whitelist namespace builder (D-11)

```python
# Allowed bindings -- explicit dict, no implicit imports
import datetime as _datetime
import json as _json
import math as _math
import re as _re
from decimal import Decimal as _Decimal

import numpy as _np
import pandas as _pd

# Safe builtins subset -- explicit allow list
_SAFE_BUILTINS = {
    name: __builtins__[name] if isinstance(__builtins__, dict)
    else getattr(__builtins__, name)
    for name in (
        "abs", "all", "any", "bool", "dict", "enumerate", "filter", "float",
        "int", "isinstance", "len", "list", "map", "max", "min", "print",
        "range", "reversed", "round", "set", "sorted", "str", "sum", "tuple",
        "zip",
    )
}

def _build_exec_namespace(self, input_row=None, output_row=None) -> dict:
    ns = {
        "__builtins__": _SAFE_BUILTINS,
        "pd": _pd,
        "np": _np,
        "datetime": _datetime,
        "json": _json,
        "re": _re,
        "math": _math,
        "Decimal": _Decimal,
        "context": self._get_context_dict(),
        "globalMap": self.global_map,
    }
    if input_row is not None:
        ns["input_row"] = input_row
    if output_row is not None:
        ns["output_row"] = output_row
    # Add python routines if loaded (CONTEXT.md: keep existing semantics)
    routines = self.get_python_routines()
    if routines:
        ns["routines"] = routines
        # Phase 8 discretion: add routines flat as well? Existing partial does.
        # Recommendation: keep flat for backward compatibility with any
        # converted Talend job that uses bare routine names.
        ns.update(routines)
    return ns
```

### Anti-Patterns to Avoid

- **Calling `validate_schema()` inside `_process`** (Rule 11). BaseComponent step 7c handles it.
- **Reading config in `__init__`** (Rule 5). Config not yet resolved.
- **Overriding `execute()`** (Rule 4). Breaks lifecycle.
- **Mutating `self.config` inside `_process`** (Rule 10 — non-reentrant for iterate). Read into local vars.
- **Calling `_update_stats()` redundantly** when BaseComponent will auto-count from `result["main"]` + `result["reject"]`. Per `MANUAL_COMPONENT_AUTHORING.md` Stats Lifecycle: only call manually when "rows read" differs from `len(main) + len(reject)` (e.g. one-shot `tJava` may want `_update_stats(0, 0, 0)` since no rows pass through, but passthrough mode does pass input through unchanged — see Risks #6).
- **Putting deferred `ConfigurationError` raises INSIDE the broad `try/except`** in `_process` (Phase 7.2 send_mail lesson). They get re-wrapped as `ComponentExecutionError`. Place BEFORE.
- **Calling `_sync_to_java`/`_sync_from_java` directly from the component**. JavaBridge wraps every call in `_call_java_with_sync` (`bridge.py:645-676`). Components must NOT duplicate sync logic.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Java code execution | Custom subprocess + stdin pipe | Existing `JavaBridge` (Phase 2/5.1) | Hardened, Arrow-based, sync-managed |
| Java compile-once-exec-many | Manual `groovyShell.parse` cache | Existing `executeJavaRow` (already does it) | Java side already compiles once internally |
| Context/globalMap sync | Manual `set_context` + `_sync_from_java` calls | `_call_java_with_sync` wrapper | Bridge handles sync at every call site |
| Config resolution | Custom `${context.X}` substitution | `BaseComponent.execute()` Step 3 | Centralized; SKIP_RESOLUTION_KEYS protects code bodies |
| Reject column appending | Manual DataFrame concat with errorMessage column | Reuse pattern from `filter_rows.py:241-251` | Same column convention; tested pattern |
| Schema validation on output | Call `validate_schema()` in `_process` | BaseComponent step 7c does it | Rule 11 |
| Python sandbox | `RestrictedPython`, AST rewriting, ptrace | Whitelist namespace (defensive hygiene only) | True sandbox needs OS-level (seccomp/container) — out of scope |

**Key insight:** Three of the four components have ZERO new infrastructure to build — the bridge, lifecycle, and reject pattern all exist. Phase 8's value is *consolidation* + *cleanup* + *security hygiene*, not net-new capability. The one exception is Python compile-once (PYRO-02) which is genuinely new and trivial.

## Runtime State Inventory

Not a rename/refactor phase — Step 2.5 not required. The four engine class names stay the same; the registry decorators are added (currently absent — see Risks #4).

## Common Pitfalls

### Pitfall 1: code-body fields are NEVER context-resolved (CONTEXT.md D-26 contradicts ENG-18)
**What goes wrong:** Planner reads D-26 ("`java_code` and `python_code` may themselves contain `${context.X}` references that resolve to substring values") and writes test cases asserting that `python_code = "x = ${context.HOME}"` resolves to `"x = /usr/home"` before exec. It does not. `ContextManager.SKIP_RESOLUTION_KEYS` (verified at `src/v1/engine/context_manager.py:37-41`) explicitly excludes `python_code`, `java_code`, and `imports` from resolution. ENG-18 fixed a bug where resolution corrupted code bodies (escaped quotes, broke string literals, etc.).
**Why it happens:** D-26 in CONTEXT.md was written without checking against ENG-18.
**How to avoid:** Plan must clarify: code bodies pass through verbatim. User code accesses context via the programmatic `context['VAR_NAME']` dict in the exec namespace, NOT via string substitution into source. Other config fields (e.g. a hypothetical `output_schema` value, `imports` itself if treated separately) follow normal resolution.
**Warning signs:** Test fixture that puts `${context.X}` inside `python_code` and expects substitution.

### Pitfall 2: tJavaRow REJECT is bridge-protocol-limited (D-14 vs D-19)
**What goes wrong:** D-14 promises per-row REJECT semantics. The existing `executeJavaRow` (`JavaBridge.java:209-247`) wraps the per-row work in `try/catch` but `throw new RuntimeException("Error processing row " + i, e)` — the WHOLE batch fails on the first error. D-19 forbids protocol changes.
**Why it happens:** CONTEXT.md was written without auditing the Java-side behavior.
**How to avoid:** Planner must explicitly choose:
- **Option A (recommended for v1):** Batch-level reject — when bridge raises, route the *entire input batch* to reject with a single appended `errorMessage` column carrying the bridge error and the row index. Honest, simple, matches "Talend has no REJECT" reality. Deferred per-row reject to a future phase explicitly noting BRDG-* needs an `executeJavaRowWithReject` variant.
- **Option B:** Per-single-row retry — when bridge raises with `die_on_error=False`, the Python side splits the input into single-row batches and re-runs each through the bridge, collecting errors. Slow (one bridge call per failing-batch row) but row-accurate.
- **Option C:** Defer JROW-02 entirely from Phase 8, mark as known gap with a phase 8.x follow-up.
The plan and test files must reflect whichever choice. RECOMMENDATION: **Option A for v1**, document loudly, plan a follow-up.
**Warning signs:** Tests that assert "row 5 fails, rows 0-4 + 6-9 pass" for tJavaRow — those will require Option B or a Java-side change.

### Pitfall 3: Python `exec` namespace whitelist is NOT a security sandbox
**What goes wrong:** D-11/PYCO-02 frames the namespace whitelist as a security control. It is not. Multiple known bypass techniques (`().__class__.__bases__[0].__subclasses__()`, exception traceback frame access, `__builtins__` access via `__class__.__mro__`) defeat any pure-Python namespace restriction. Confirmed by Python community consensus and HackTricks reference.
**Why it happens:** Conflating "guard rails against accidental misuse by job authors" with "defence against adversarial code".
**How to avoid:** Frame D-11 honestly in code comments and the threat model:
> "The namespace whitelist is a hygienic guard against ACCIDENTAL misuse by job authors who reach for `os.system` or `subprocess` out of habit. It is NOT a sandbox against adversarial code. The trust boundary is `python_code` is owned by Citi internal job authors; if the threat model ever changes, replace exec with subprocess-isolated execution (e.g. `openedx/codejail` pattern, or seccomp+container)."
The whitelist is still worth doing — most accidental usage is `import os; os.system(...)` for shell calls — but document the limitation.
**Warning signs:** Plan or PR description that calls D-11 a "sandbox" without qualification.

### Pitfall 4: existing four files are not registered with `@REGISTRY.register`
**What goes wrong:** Verified via `grep -rn "REGISTRY.register" src/v1/engine/components/transform/` returning zero hits for the four code components (file_output_delimited.py:73 has it; java_component.py and siblings do not). They appear to be looked up via the LEGACY `COMPONENT_REGISTRY` static dict in `engine.py` rather than the decorator registry. This will cause `_validate_config` lookups via `REGISTRY.get("tJava")` in tests to return `None`.
**Why it happens:** These components were authored before the decorator registry existed.
**How to avoid:** Each rewritten file MUST add `@REGISTRY.register("ClassName", "tTalendName")`. For example:
```python
@REGISTRY.register("JavaComponent", "tJava")
class JavaComponent(BaseComponent): ...
```
Test classes named `TestRegistration` (per `MANUAL_COMPONENT_AUTHORING.md` PR Checklist) will catch missing decorators.
**Warning signs:** Test setup that imports the class directly but skips the registry — that hides the bug.

### Pitfall 5: `execute_one_time_expression` returns a single VALUE, not the whole tJava block result
**What goes wrong:** `JavaBridge.execute_one_time_expression(expression: str)` (`bridge.py:257-274`) is designed for *single Java expressions* (e.g. `globalMap.put("x", 5)` or `2 + 3`). The current `java_component.py:77` calls it with a multi-line `java_code` block that may contain multiple statements. Whether this works depends on Groovy's accept-multi-statement-as-script behavior — which it does — but the API contract is single-expression.
**Why it happens:** The existing code seems to accidentally rely on Groovy's tolerance.
**How to avoid:** Either (a) keep using `execute_one_time_expression` and document that it's actually a "one-time SCRIPT" because Groovy doesn't distinguish, or (b) add a second method on the bridge for multi-statement scripts and refactor. For Phase 8 (D-19 says no protocol changes), choice (a) is mandatory: keep the existing API call. Document in the rewritten `java_component.py` docstring that "execute_one_time_expression handles multi-statement Groovy scripts despite its name".
**Warning signs:** Any plan task that proposes adding a new bridge method "for clarity" — that violates D-19.

### Pitfall 6: tJava passthrough vs no-input — stats mismatch
**What goes wrong:** Existing `java_component.py:101-105` returns `{'main': input_data}` if input_data is provided (passthrough), `{'main': pd.DataFrame()}` if not. BaseComponent stats logic counts from `len(main)`. For a one-shot tJava called as a job-level init component (no input), NB_LINE = 0 — correct. For a tJava in the middle of a flow with input, NB_LINE = len(input) — also "correct" in a passthrough sense. But Talend tJava is conceptually a job-level component with no input — the current passthrough is a DataPrep enhancement.
**Why it happens:** The original author wanted tJava to be insertable mid-flow.
**How to avoid:** Document the passthrough behavior in the rewritten component's docstring. Tests must cover both cases. Don't change existing behavior — converted jobs may rely on it.
**Warning signs:** Plan that "simplifies" tJava to always return empty DataFrame — would break existing converted jobs.

### Pitfall 7: existing Java side already prepends imports automatically? Verify before rewriting
**What goes wrong:** `bridge.py:216-255` (`execute_java_row`) takes only `java_code` parameter — no separate `imports`. Java side compiles whatever it gets. The Phase 8 plan expects the Python side to prepend `imports + "\n" + java_code` per D-07/D-08. Verified this is correct: bridge has no `imports` parameter, so Python-side prepend is the only place.
**Why it happens:** Just verifying that D-07 is sound.
**How to avoid:** Confirm during executor coding: prepend at the Python component layer, send single `java_code` string to bridge. Same for `execute_one_time_expression` (tJava one-shot).

### Pitfall 8: BaseComponent test fixture trap (Phase 7.2 lesson)
**What goes wrong:** Tests calling `comp._validate_config()` or `comp._process()` directly without populating `comp.config` see an empty dict (because `__init__` only sets `_original_config`).
**Why it happens:** Lifecycle Step 1 (`self.config = copy.deepcopy(self._original_config)`) only runs inside `execute()`.
**How to avoid:** Use the Phase 7.2 fixture pattern verbatim: `comp.config = dict(config)` before any direct `_validate_config`/`_process` call. Document in test docstrings.

## Code Examples

### Reject column append (canonical from `filter_rows.py`)

```python
# Source: filter_rows.py:241-251
reject_df = input_data[~mask].copy()
if not reject_df.empty:
    reject_df["errorMessage"] = self._build_reject_error_message()  # str
# Note: filter_rows uses `errorMessage` only.
# Phase 8 D-14 adds `errorCode` (int, default 1) — same shape, two columns.
```

### Compile-once Python execution

```python
# Source: Python docs (https://docs.python.org/3/library/functions.html#compile)
# Verified: compiled code object is reusable across many exec() calls with different namespaces.
filename = f"<python_row_component:{self.id}>"
compiled_code = compile(source, filename, "exec")
for idx, row in df.iterrows():
    namespace = build_namespace(row)  # cheap dict construction
    exec(compiled_code, namespace)    # parse work amortized
```

### Java bridge call with sync (already implemented)

```python
# Source: src/v1/java_bridge/bridge.py:645-676 -- _call_java_with_sync
# Components do NOT call this directly; it's wrapped around every public bridge method.
# Just call bridge.execute_java_row(...) or bridge.execute_one_time_expression(...).
def _call(): return self.java_bridge.executeJavaRow(...)
result_bytes = self._call_java_with_sync(_call)  # sync_from_java in finally
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `validate_schema()` inside `_process` (pre-7.1) | BaseComponent step 7c handles it | Phase 7.1 | Rule 11 |
| Content checks in `_validate_config` (pre-7.2) | Deferred to `_process` | Phase 7.2 | Rule 12 |
| Pre-row `compile()` in tPythonRow (existing) | Compile-once in `_process` start (PYRO-02) | Phase 8 | 5-30x speedup |
| `os`/`sys` exposed in Python namespace (existing) | Removed (D-11) | Phase 8 | Breaking change for any in-tree user code that imports them |

**Deprecated/outdated:**
- Pre-Rule-11 `validate_schema()` in components — Phase 7.1 closed
- Pre-Rule-12 `_validate_config` content checks — Phase 7.2 closed
- `_get_context_dict` duplicated across components — Phase 8 (this) closes via mixin
- Missing `@REGISTRY.register` on the 4 code components — Phase 8 closes

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (3.10+) |
| Config file | `pyproject.toml` (pytest section) — verified by ENG-15 closed |
| Quick run command | `python -m pytest tests/v1/engine/components/transform/test_python_component.py -x -q` |
| Full suite command | `python -m pytest tests/v1/engine/ -q` |
| Java integration command | `python -m pytest tests/v1/engine/components/transform/ -m java -q` |

### Phase Requirements -> Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| JAVA-01 | imports prepended to java_code | unit | `pytest tests/v1/engine/components/transform/test_java_component.py::TestImports -x` | NEW |
| JAVA-01 | imports + java_code together compiled by bridge | integration | `pytest tests/v1/engine/components/transform/test_java_component.py -m java -x` | NEW |
| JAVA-02 | bidirectional context/globalMap sync | integration | `pytest test_java_component.py::TestSync -m java -x` | NEW |
| JAVA-03 | structure complies with Rule 11/12 | unit | `pytest test_java_component.py::TestRegistration test_java_component.py::TestValidation -x` | NEW |
| JROW-01 | imports prepended to java_code per row | unit + integration | `pytest test_java_row_component.py::TestImports -x` | NEW |
| JROW-02 | REJECT flow on per-row Java error (Option A: batch-level) | integration | `pytest test_java_row_component.py::TestRejectFlow -m java -x` | NEW |
| JROW-03 | input_row/output_row semantics | integration | `pytest test_java_row_component.py::TestRowSemantics -m java -x` | NEW |
| JROW-04 | structure complies | unit | `pytest test_java_row_component.py::TestRegistration test_java_row_component.py::TestValidation -x` | NEW |
| PYCO-01 | structure complies | unit | `pytest test_python_component.py::TestRegistration test_python_component.py::TestValidation -x` | NEW |
| PYCO-02 | os/sys disallowed; safe modules allowed | unit | `pytest test_python_component.py::TestNamespaceWhitelist -x` | NEW |
| PYCO-03 | mixin `_get_context_dict` returns same dict for both Python components | unit | `pytest test_python_component.py::TestContextMixin test_python_row_component.py::TestContextMixin -x` | NEW |
| PYRO-01 | structure complies | unit | `pytest test_python_row_component.py::TestRegistration test_python_row_component.py::TestValidation -x` | NEW |
| PYRO-02 | compile() called once, exec called N times | unit (with patch) | `pytest test_python_row_component.py::TestCompileOnce -x` | NEW |
| PYRO-03 | per-row error -> reject DataFrame with errorMessage/errorCode | unit | `pytest test_python_row_component.py::TestRejectFlow -x` | NEW |
| TEST-07 | overall coverage of Python components | unit | `pytest tests/v1/engine/components/transform/test_python*.py -q` | NEW |
| PERF-02 | (satisfied by PYRO-02 above) | unit | (same as PYRO-02) | NEW |

### Sampling Rate

- **Per task commit:** the directly-relevant `test_*.py` file (`-x` for fast fail)
- **Per wave merge:** `pytest tests/v1/engine/components/transform/test_{java,python}*.py -q`
- **Phase gate:** Full engine suite green before `/gsd-verify-work`. Java-marker tests gated on JAR present (`mvn package` once before run).

### Wave 0 Gaps

- [ ] `tests/v1/engine/components/transform/test_java_component.py` — covers JAVA-01..03
- [ ] `tests/v1/engine/components/transform/test_java_row_component.py` — covers JROW-01..04
- [ ] `tests/v1/engine/components/transform/test_python_component.py` — covers PYCO-01..03
- [ ] `tests/v1/engine/components/transform/test_python_row_component.py` — covers PYRO-01..03 + PERF-02
- [ ] No new conftest needed — existing `tests/v1/engine/conftest.py` (verified by 7.2 reuse) provides `GlobalMap`/`ContextManager` patterns
- [ ] No framework install needed — pytest already pinned

## Threat Model Notes

**Trust boundary:** `python_code`, `java_code`, `imports` are user-supplied source code. Trust assumption is that they are written by Citi internal Talend job authors converted from existing production `.item` files — not adversarial input. There is no public-facing API surface.

### Per-component threat surface

| Component | Attack Surface | STRIDE | Mitigation |
|-----------|---------------|--------|-----------|
| `tJava` | Arbitrary Java/Groovy code execution in the JVM subprocess; full FS/network access from JVM | T, I, D, E | JVM is an isolated subprocess with bidirectional Py4J channel; no JVM sandbox per CONTEXT.md "Sandboxing the Java side" deferred. Threat is bounded by the JVM subprocess having the same OS user as Python — no privilege boundary. Document this. |
| `tJavaRow` | Same as tJava + per-row data access from input DataFrame | T, I | Same as above. |
| `python_component` | Arbitrary Python code in-process; can mutate engine state, exfiltrate to FS/network | T, I, D, E | Whitelist namespace (D-11) is HYGIENIC ONLY. Real mitigation: trust boundary (job authors are internal) + code review of converted JSONs. |
| `python_row_component` | Same as python_component + per-row data | T, I | Same. Per-row REJECT flow makes denial-of-service via crashing rows infeasible (when `die_on_error=False`). |

### ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | No auth surface in batch ETL |
| V3 Session Management | no | No session |
| V4 Access Control | no | OS-user-level only |
| V5 Input Validation | yes | Rule 12 deferred checks; type validation in `_process`; `output_schema` enforcement via BaseComponent step 7c |
| V6 Cryptography | no | No crypto in code components (job-level secrets via context vars are V6 in their own components) |
| V7 Error Handling & Logging | yes | ASCII-only logs; `[{component_id}]` prefix; ConfigurationError vs ComponentExecutionError discipline |

### Known Threat Patterns for {python exec / java groovy}

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Adversarial code in `python_code` (e.g. `import os; os.system("rm -rf /")`) | T | Whitelist namespace blocks `os` (hygienic only); real mitigation = code review of converted JSON before deployment |
| Adversarial code in `python_code` using `().__class__.__mro__` to escape namespace | T | Cannot be mitigated in pure Python; documented limitation; threat = internal user, not adversarial — accepted |
| Adversarial code in `java_code` using `Runtime.getRuntime().exec(...)` | T | Cannot be mitigated without JVM sandbox; documented limitation; threat = internal user, accepted |
| Code that exhausts memory in a row loop (DoS) | D | Python: row-loop is bounded by input size; OOM kills the process cleanly. Java: same. No fix needed. |
| Logging credential-like content (e.g. `print(context['DB_PASSWORD'])`) in user code | I | Cannot prevent in user code. Accept. Document in component docstring: "user code can read context including secrets — review before commit." |

### Logging policy for code components

- ASCII-only per `feedback_ascii_logging`. RHEL log capture must be clean.
- `[{component_id}]` prefix on every log line per established pattern.
- Do NOT log the user's code body at INFO level — too noisy. DEBUG only. Justification: code bodies can be 100+ lines.
- Per-row error messages MUST include the row index and the original exception message but NOT the row's data values (PII risk). Example: `[{id}] row {idx}: {e.__class__.__name__}: {e}`.

## External Research

### Python `compile()` for compile-once-exec-many (PYRO-02)

- **Sources:** [Python docs, compile()](https://docs.python.org/3/library/functions.html#compile)
- **Confirmed:** `compile(source, filename, 'exec')` returns a code object that is reusable across many `exec(code_obj, namespace)` calls. The `filename` argument is used in tracebacks/error messages only — it does not affect execution. Convention: `<string>` or any `<...>` marker. Recommendation: use `<python_row_component:{component_id}>` so debugging row-failure stack traces shows the originating component.
- **Performance:** parser is the heavy step (5-30x slower than namespace dict construction depending on code size). For 10K rows of even 50-line user code, compile-once is dramatically faster. Indicative — depends on code complexity. No project benchmarks needed for Phase 8; the speedup is qualitatively obvious.

### Python `exec` namespace sandboxing limitations

- **Sources:** [HackTricks Python sandbox bypass](https://hacktricks.wiki/en/generic-methodologies-and-resources/python/bypass-python-sandboxes/index.html); [Andrew Healey "Running Untrusted Python Code"](https://healeycodes.com/running-untrusted-python-code); [openedx/codejail](https://github.com/openedx/codejail)
- **Confirmed:** Python's introspection features (`__subclasses__`, `__mro__`, exception traceback frame access) make pure-Python namespace restriction bypassable. The honest position: namespace whitelist is hygiene against accidental misuse, not security against adversarial code. For real isolation: subprocess + seccomp (Linux) or full container isolation. CONTEXT.md scope explicitly defers true sandboxing.

### Talend tJava / tJavaRow source

- **Sources:** [Talaxie tJava component dir](https://github.com/Talaxie/tdi-studio-se/tree/master/main/plugins/org.talend.designer.components.localprovider/components/tJava); [Talaxie tJavaRow_java.xml](https://raw.githubusercontent.com/Talaxie/tdi-studio-se/master/main/plugins/org.talend.designer.components.localprovider/components/tJavaRow/tJavaRow_java.xml); [Talaxie tJava_begin.javajet](https://raw.githubusercontent.com/Talaxie/tdi-studio-se/master/main/plugins/org.talend.designer.components.localprovider/components/tJava/tJava_begin.javajet); [Talaxie tJavaRow_main.javajet](https://raw.githubusercontent.com/Talaxie/tdi-studio-se/master/main/plugins/org.talend.designer.components.localprovider/components/tJavaRow/tJavaRow_main.javajet)
- **Confirmed:**
  - tJava is a one-shot component (`_begin.javajet`); CODE inserted directly with no try/catch wrapping; IMPORT is a separate ADVANCED parameter (FIELD=MEMO_IMPORT).
  - tJavaRow has only `SCHEMA` (REQUIRED), `CODE`, and `IMPORT` parameters. **No `DIE_ON_ERROR`. No reject flow.** The per-row CODE is inserted via `<%=code%>` substitution — no try/catch around it, exceptions propagate up the job.
  - Imports are placed at file/class header level by the Talend code generator; in our Groovy bridge, prepending to the script body works because Groovy accepts top-of-script imports.
- **Implication:** Phase 8's REJECT flow (D-14..D-16) is a DataPrep-specific *enhancement*, not parity. Document this explicitly. Talend job authors who used tJavaRow without REJECT will see no behavioral change as long as `die_on_error=True` (default).

### Talend tPythonRow / tPython

- **No Talaxie source** — these are NOT Talend-shipped components. They are DataPrep-specific Python equivalents to tJava/tJavaRow.
- **Implication:** Design intent is "mirror tJava/tJavaRow structure but in Python." CONTEXT.md D-22 makes this explicit. The DataPrep converter (`src/converters/talend_to_v1/components/transform/python_component.py` and `python_row_component.py`) registers `tPython` and `tPythonRow` as Talend-side aliases — these ARE Talend-shipped tPython/tPythonRow components, just not in Talaxie's standard set. The Talend tPython component does exist in some Talend distributions (Open Studio for Big Data) and operates like tJava but uses Python.

## Project Constraints (from CLAUDE.md)

- **ASCII-only logging** — no emojis or unicode in log messages. Per-row error messages must be ASCII.
- **Fix-source-no-fallbacks** — D-12 mandates breaking-change cleanup, no compatibility shim for `os`/`sys` removal.
- **Prefer rewrite over patch** — D-01 mandates clean rewrite, not patching the existing 4 files.
- **Talend feature parity non-negotiable** — for tJava/tJavaRow, parity means CODE+IMPORT semantics. REJECT flow is an enhancement, document it.
- **Real-bridge tests required for Java side** — D-21/`feedback_test_real_bridge`. `@pytest.mark.java` tests are MANDATORY for Java component tests.
- **Custom exception hierarchy** — `ConfigurationError`, `ComponentExecutionError`. No `RuntimeError`/`ValueError`/generic `Exception`.
- **Logger, not print** — every component uses `logging.getLogger(__name__)`.
- **Snake_case files, PascalCase classes, snake_case methods** — already conventional.

## Dependencies on prior phases

| Phase | Dependency | Status |
|-------|-----------|--------|
| Phase 1 (Engine Core) | ENG-09/21 config immutability; ENG-18 SKIP_RESOLUTION_KEYS for code bodies | Complete |
| Phase 2 (Java Bridge) | JavaBridge subprocess + bidirectional sync; `_call_java_with_sync` wrapper; Arrow serialization | Complete |
| Phase 5.1 (Java Bridge tMap fix) | `executeJavaRow` compile-once pattern; Arrow type extraction (`extractTypedValue`) | Complete |
| Phase 7.1 (Manager Audit + BaseComponent fixes) | Rule 11 (no `validate_schema` in `_process`); errorMessage/errorCode reject convention; canonical `file_output_delimited.py`/`filter_rows.py` reference shapes | Complete |
| Phase 7.2 (validate-config bug sweep) | Rule 12 codified; deferred-check pattern; test fixture pattern (`comp.config = dict(config)`); three-test pattern; KEEP rationale comments; pinned-baseline pytest gate | Complete |
| Phase 9 (Routines) | tContextLoad, routines — DOES NOT BLOCK Phase 8. The existing `python_routine_manager` API used by python components is stable. | Complete |

**No upstream blockers.** Phase 8 is unblocked.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `compile()` 5-30x speedup over per-row `exec(source, ns)` for 10K rows | PYRO-02 / Standard Stack | Low — qualitatively the parser dominates; quantitatively varies by code size. PERF-02 only requires "compile once, exec per row" — the speedup is the rationale, not the acceptance criterion. |
| A2 | Groovy accepts top-of-script imports (so prepended `imports` text works) | JAVA-01 / JROW-01 | Medium — bridge integration test will catch if it doesn't work. Easy to fix by using a different placement or a separate Java-side `setImports` call (out of D-19 scope). VERIFY in first integration test. |
| A3 | tJavaRow REJECT semantics — Option A (batch-level) is the right default for v1 | JROW-02 / Pitfall #2 | Medium-High — this is a semantic divergence from per-row that may surprise users. Planner must surface this explicitly to the user during plan-phase, NOT bury it in code comments. |
| A4 | The four existing components are NOT registered with `@REGISTRY.register` | Pitfall #4 | Low — verified by grep; if wrong, the rewrite still adds the decorators harmlessly. |
| A5 | DataPrep job authors are internal Citi staff, not adversarial | Threat Model | High if wrong — would require subprocess-isolated Python (out of scope). Verify with stakeholder. CLAUDE.md does say "1200+ production jobs" suggesting internal usage. |
| A6 | `python_code`/`java_code`/`imports` are NEVER context-resolved (per ENG-18) | Pitfall #1 | Low — verified directly from `context_manager.py:37-41`. |
| A7 | tPython / tPythonRow are not in Talaxie standard component set | External Research | Low — converter has them, so the Talend component definitely exists somewhere in the Talend ecosystem; we don't need Talaxie source to define our parity contract. We mirror tJava/tJavaRow structure per CONTEXT.md D-22. |

## Open Questions

1. **JROW-02 REJECT semantics: Option A vs Option B?**
   - What we know: existing bridge is all-or-nothing (Option A natural); Option B requires per-single-row retry loop in the Python component (slow but row-accurate).
   - What's unclear: which Talend-job pattern is more common? Are there tJavaRow uses in the 1200+ production jobs that depend on row-level rejection?
   - Recommendation: Go with Option A for v1 (batch-level reject), document explicitly with a `# FUTURE` marker for an Option B follow-up phase. Surface the choice to user during `/gsd-plan-phase` for confirmation.

2. **Should the rewritten components extend the existing partial implementations' "passthrough mode" for tJava/python_component (returning input_data unchanged when input is given)?**
   - What we know: existing code does this (java_component.py:101-105, python_component.py:106-108). Talend's tJava is conceptually a job-level init component — it doesn't have a flow input.
   - What's unclear: do any production jobs rely on this passthrough?
   - Recommendation: KEEP the passthrough behavior for backward compatibility. Document explicitly in component docstring as "DataPrep extension beyond Talend semantics."

3. **For Python `routines` namespace exposure (D-11 + Claude's discretion): flat `**routines` plus nested `routines` dict, or only nested?**
   - What we know: existing partial implementations expose BOTH flat and nested (`'routines': python_routines, **python_routines`).
   - What's unclear: is there a converter-side convention that user code refers to routines flat (`MyUtil.foo()`) or nested (`routines.MyUtil.foo()`)?
   - Recommendation: KEEP both for backward compat with any converted job's user code. Document.

4. **`output_schema` for python_row_component — is it required?**
   - What we know: existing component validates output_schema if provided, treats `None` as "no validation". Converter generates it from FLOW metadata.
   - What's unclear: should `output_schema=None` be allowed in the rewrite?
   - Recommendation: keep optional, document. BaseComponent step 7c only runs schema validation if `self.output_schema` is set.

5. **Should `imports` be a separate config key, or merged into `java_code` at converter time?**
   - What we know: converter emits `imports` separately (java_component.py:42). Engine prepends per D-07.
   - What's unclear: any reason to keep them separate vs merge at converter?
   - Recommendation: keep separate. Engine-side prepend per D-07 is the defined contract.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | All | yes | 3.12.12 (>=3.10) | none |
| pytest | All tests | yes (project pinned) | per pyproject.toml | none |
| Java JDK | tJava/tJavaRow integration tests | per project | 11+ | mock-only tests (D-21 forbids — must verify on Mac at minimum) |
| Maven | Java bridge JAR build | per project | 3.x | pre-built JAR if available |
| Java bridge JAR | tJava/tJavaRow integration tests | needs check | — | `mvn package` from `src/v1/java_bridge/java/` |
| pandas | All | yes | 3.0.1 | none |
| numpy | All (transitive) | yes | per project | none |
| pyarrow | bridge | yes | 15.0.2 | none |
| py4j | bridge | yes | 0.10.9.7 | none |

**Missing dependencies with no fallback:** none.

**Missing dependencies with fallback:** verify Java bridge JAR exists before integration tests run; if not, plan must include `mvn package` setup step in the test fixture or wave 0.

## Sources

### Primary (HIGH confidence)
- `src/v1/engine/base_component.py` lines 1-260, 320-440, 1340-1373 — VERIFIED template-method lifecycle, Steps 1-8 ordering, `_resolve_expressions`, `get_python_routines`
- `src/v1/engine/context_manager.py` lines 37-41 — VERIFIED `SKIP_RESOLUTION_KEYS = {python_code, java_code, imports}` (ENG-18)
- `src/v1/engine/components/transform/{java,java_row,python,python_row}_component.py` — full read of all four, line-cited in pitfalls
- `src/v1/engine/components/transform/file_output_delimited.py` (post-7.1 + 260429-hc2) — canonical reference shape
- `src/v1/engine/components/transform/filter_rows.py` lines 154-166, 241-251 — canonical REJECT shape
- `src/v1/engine/components/transform/__init__.py` — VERIFIED imports of 4 code components, NO @REGISTRY.register decorators on the components themselves
- `src/v1/engine/component_registry.py` — VERIFIED decorator registry pattern
- `src/v1/engine/java_bridge_manager.py` — VERIFIED bridge lifecycle
- `src/v1/java_bridge/bridge.py` lines 216-302, 645-694 — VERIFIED `execute_java_row`, `execute_one_time_expression`, `_call_java_with_sync`, `_sync_from_java`
- `src/v1/java_bridge/java/src/main/java/com/citi/gru/etl/JavaBridge.java` lines 173-260 — VERIFIED Java side `executeJavaRow` is all-or-nothing (compile-once + per-row throws on first error)
- `src/converters/talend_to_v1/components/transform/{java,java_row,python,python_row}_component.py` — VERIFIED converter side emits `java_code`/`python_code` + `imports` keys (with `engine_gap` needs_review entries flagging that engine doesn't read imports — Phase 8 closes this gap)
- `docs/v1/standards/MANUAL_COMPONENT_AUTHORING.md` — Rules 1-12, stats lifecycle, test patterns
- `.planning/phases/07.2-*/07.2-LEARNINGS.md` — 5 patterns, fixture, three-test, deferred-check
- `tests/v1/engine/components/control/test_send_mail.py` lines 1-90 — canonical Phase 7.2 test fixture pattern
- [Python docs compile()](https://docs.python.org/3/library/functions.html#compile)

### Secondary (MEDIUM confidence)
- [Talaxie tJava_begin.javajet](https://raw.githubusercontent.com/Talaxie/tdi-studio-se/master/main/plugins/org.talend.designer.components.localprovider/components/tJava/tJava_begin.javajet) — verified IMPORT separate parameter
- [Talaxie tJavaRow_java.xml](https://raw.githubusercontent.com/Talaxie/tdi-studio-se/master/main/plugins/org.talend.designer.components.localprovider/components/tJavaRow/tJavaRow_java.xml) — verified no DIE_ON_ERROR/REJECT
- [Talaxie tJavaRow_main.javajet](https://raw.githubusercontent.com/Talaxie/tdi-studio-se/master/main/plugins/org.talend.designer.components.localprovider/components/tJavaRow/tJavaRow_main.javajet) — verified per-row CODE substitution, no try/catch
- [Talaxie tJava component dir](https://github.com/Talaxie/tdi-studio-se/tree/master/main/plugins/org.talend.designer.components.localprovider/components/tJava) — file listing confirms `_begin.javajet` (one-shot)

### Tertiary (LOW confidence — flagged)
- [HackTricks Python sandbox bypass](https://hacktricks.wiki/en/generic-methodologies-and-resources/python/bypass-python-sandboxes/index.html) — community reference for known bypasses
- [Andrew Healey "Running Untrusted Python Code"](https://healeycodes.com/running-untrusted-python-code) — community blog post
- [openedx/codejail](https://github.com/openedx/codejail) — alternative real-sandbox approach (out of scope reference)

## Metadata

**Confidence breakdown:**
- BaseComponent contract / lifecycle / Rule 11/12 / fixture pattern: HIGH (direct file reads + Phase 7.1/7.2 LEARNINGS)
- Existing component partials, code paths, REGISTRY status: HIGH (full reads with line cites)
- JavaBridge protocol: HIGH (full read of bridge.py + JavaBridge.java for executeJavaRow)
- Talend tJava / tJavaRow XML / javajet semantics: MEDIUM-HIGH (Talaxie source confirmed; some sub-templates not fully accessible — but XML param list is canonical)
- tPython / tPythonRow semantics: MEDIUM (no Talaxie source; design intent inferred from CONTEXT.md D-22 + DataPrep converter)
- Python compile() / exec sandbox limitations: HIGH (Python docs + community consensus)
- Talend-side compile-once-vs-per-row in tJavaRow: HIGH (verified in JavaBridge.java)
- tJavaRow REJECT semantics in Talend: HIGH-NEGATIVE (verified absent from XML)
- Performance estimate for compile-once vs per-call: MEDIUM (qualitative, not benchmarked)

**Research date:** 2026-04-29
**Valid until:** 2026-05-29 (30 days; stable engine codebase + locked decisions; Talend XML doesn't change at this pace)
