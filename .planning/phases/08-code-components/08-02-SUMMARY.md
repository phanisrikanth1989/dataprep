---
phase: 08-code-components
plan: 02
subsystem: engine.components.transform
tags: [python_component, tPython, code-execution, namespace-whitelist, mixin]
requires:
  - .planning/phases/08-code-components/08-01-SUMMARY.md  # CodeComponentMixin + whitelist constants
provides:
  - "src/v1/engine/components/transform/python_component.py::PythonComponent"
  - "REGISTRY['PythonComponent']"
  - "REGISTRY['tPython']"
  - "REGISTRY['tPythonComponent']"
affects:
  - "tests/v1/engine/components/transform/test_python_component.py (new)"
tech-stack:
  added: []
  patterns:
    - "decorator-based REGISTRY registration (Rule 9)"
    - "mixin-first multiple inheritance for shared helpers (D-09)"
    - "module-level whitelist constants imported, not redefined (Warning 7)"
    - "Phase 7.2 D-22 fixture pattern for direct _process / _validate_config tests"
    - "deferred content checks before broad try/except (D-13 / D-27)"
key-files:
  created:
    - "tests/v1/engine/components/transform/test_python_component.py"
  modified:
    - "src/v1/engine/components/transform/python_component.py"
decisions:
  - "Implemented D-29 strictly: passthrough is default-and-only (no toggle); when input_data is provided, result['main'] is the same object (identity check confirmed by test)."
  - "Implemented D-11 whitelist by importing _SAFE_NAMESPACE_GLOBALS + _build_safe_builtins from _code_component_mixin (Warning 7); zero local redefinition."
  - "Kept the flat-spread of routines into the namespace alongside the nested 'routines' key (RESEARCH.md Open Question 3) for backward compatibility with converted Talend jobs."
  - "Wrapped user-code exceptions as ComponentExecutionError(self.id, msg, cause=e) so the engine's failure path captures both component_id and the original cause; tests assert 'NameError' / 'SyntaxError' is visible in str(exc)."
  - "Wrote a focused 21-test suite with no @pytest.mark.java marker -- PythonComponent never touches the Java bridge."
metrics:
  duration: "~25 minutes"
  completed: "2026-04-29"
  tasks_completed: 1
  tests_added: 21
  files_changed: 2
---

# Phase 8 Plan 02: PythonComponent Rewrite Summary

One-liner: rewrote one-shot tPython engine with the D-11 secure exec namespace
(no os/sys/subprocess/__import__/open/exec/eval/compile), mixin-inherited
context dict, and D-29 passthrough.

## Outcome

Plan 02 (Wave 2) is complete. The legacy 133-line `python_component.py`
has been replaced with a clean implementation that:

1. Registers under `PythonComponent`, `tPython`, and `tPythonComponent` via
   `@REGISTRY.register(...)` (AP-12 fix).
2. Inherits `_get_context_dict` from `CodeComponentMixin` (D-09 / AP-4 fix).
3. Builds the user exec namespace from the module-level whitelist constants
   imported from `_code_component_mixin` -- `_SAFE_NAMESPACE_GLOBALS` plus
   `_build_safe_builtins()` (Phase 8 revision-1 Warning 7 -- no local
   redefinition).
4. Defers `python_code` content checks (must be string / non-empty after
   strip) to `_process` BEFORE any broad try/except (D-13 / D-27), so a
   `ConfigurationError` is never re-wrapped as
   `ComponentExecutionError`.
5. Wraps user-code exceptions as
   `ComponentExecutionError(self.id, "...{ExceptionClass}: {msg}", cause=e)`
   so the original exception class is visible in `str(exc.value)` and the
   `__cause__` chain preserves the underlying error.
6. Implements D-29 passthrough as default-and-only: when `input_data` is
   provided, `result["main"]` is the same object reference; when
   `input_data` is `None`, `result["main"]` is `None`. `result["reject"]`
   is always `None` (one-shot variants have no reject flow).
7. Logs the code-block size at DEBUG only (RESEARCH.md logging policy --
   never INFO with body, ASCII-only).

A 21-test suite (`test_python_component.py`) covers:

- Registration (V1 name + both Talend aliases)
- `_validate_config` minimalism (Rule 12) -- presence + `${context.X}` literal pass-through
- Execution round-trip (`globalMap.put`, `context["VAR"]` read)
- D-11 whitelist enforcement -- 8 negative tests, one per blocked name
  (`os`, `sys`, `subprocess`, `__import__`, `open`, `exec`, `eval`, `compile`)
- D-11 whitelist allow -- `pd`, `np`, `datetime`, `json`, `re`, `math`, `Decimal` accessible
- D-29 passthrough (object-identity check on `input_data`)
- None-input no-op + user code still runs
- Syntax-error wrapping to `ComponentExecutionError`
- Stats lifecycle (AP-3) -- `_update_stats` is never invoked from `_process`
- Context mixin inheritance (AP-4) -- `_get_context_dict` is on the class
  via inheritance but NOT in `PythonComponent.__dict__`

## Verification

### Automated Tests

`python -m pytest tests/v1/engine/components/transform/test_python_component.py -x -q`

```
21 passed in 0.02s
```

Cross-plan sanity check (plan 01 + plan 02 unit tests):

`python -m pytest tests/v1/engine/components/transform/test_python_component.py tests/v1/engine/components/transform/test_code_component_mixin.py tests/v1/engine/components/transform/test_java_component.py -m "not java" -q`

```
49 passed, 2 deselected in 0.05s
```

### Grep Gates (from plan `<done>` block)

| Gate | Pattern | Expected | Actual |
|------|---------|----------|--------|
| AP-12 | `@REGISTRY.register` count | >= 1 | 1 |
| AP-2  | `^import os|^import sys` | no match | no match |
| AP-2  | `namespace\['os'\] = os` style injection | no match | no match |
| AP-1  | `raise ValueError|raise RuntimeError` | no match | no match |
| AP-4  | `def _get_context_dict` count | 0 | 0 |
| AP-3  | `self._update_stats` count | 0 | 0 |
| D-09  | `class PythonComponent(CodeComponentMixin, BaseComponent)` count | 1 | 1 |
| W7    | `^_SAFE_BUILTIN_NAMES` redefinition | 0 | 0 |
| W7    | `^_SAFE_NAMESPACE_GLOBALS` redefinition | 0 | 0 |
| W7    | `^def _build_safe_builtins` redefinition | 0 | 0 |
| W7    | `from ._code_component_mixin import` | >= 1 | 1 |
| W7    | `_SAFE_NAMESPACE_GLOBALS` reference (import + 2 uses) | >= 2 | 3 |
| W7    | `_build_safe_builtins` reference (import + 2 uses) | >= 2 | 3 |

All 13 gates pass.

## Deviations from Plan

None -- plan executed exactly as written.

One minor in-flight wording adjustment was made to the module docstring's
anti-pattern reference list (the prose example for AP-2 was rephrased
from `namespace['os'] = os` to "no direct injection of those modules
into the user namespace under their bare names") so the AP-2 grep gate
in the done-criteria block does not match an explanatory docstring. The
semantics of the doc are unchanged. This is housekeeping inside the
already-planned file and not a deviation in behavior.

## Authentication / Human-Action Gates

None -- plan was fully autonomous (no `checkpoint:*` task in plan body).

## Requirements Closed

- PYCO-01 (one-shot Python execution + passthrough + globalMap round-trip)
- PYCO-02 (D-11 secure namespace; D-12 breaking change documented)

PYCO-03 (mixin extraction) is closed by Plan 01; this plan only consumes
the mixin.

## Threat Mitigations Applied

- T-08-06 (accidental `os`/`sys`/`subprocess` use): D-11 whitelist
  removes the names from the user namespace; 8 negative tests verify
  each blocked name raises `NameError` -> `ComponentExecutionError`
  with the blocked name visible in the wrapper message.
- T-08-07 (information disclosure via logs): code-body size logged at
  DEBUG only with `[{self.id}]` prefix, ASCII-only -- consistent with
  the project's logging policy and `feedback_ascii_logging` memory.
- T-08-08 (code injection via `${context.X}`): handled upstream by
  `ContextManager.SKIP_RESOLUTION_KEYS`; the `python_code` field is
  never substring-substituted, so a literal `${context.VAR}` reaches
  exec verbatim and raises `NameError` (Test 4 documents this is
  intentional).

T-08-05 (E -- pure-Python sandbox bypass via `__subclasses__`/`__mro__`)
remains accepted per the threat register; the module docstring documents
this honestly.

## Files Touched

- Modified: `src/v1/engine/components/transform/python_component.py` (133L -> 244L; full rewrite)
- Created: `tests/v1/engine/components/transform/test_python_component.py` (21 tests, ~330L)

## Self-Check: PASSED

- File `src/v1/engine/components/transform/python_component.py` exists: FOUND
- File `tests/v1/engine/components/transform/test_python_component.py` exists: FOUND
- Commit `f2e8438`: FOUND in `git log --oneline`
- Test count: 21 collected, 21 passed
- All 13 grep gates pass
