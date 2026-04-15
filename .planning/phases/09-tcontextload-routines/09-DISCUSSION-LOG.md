# Phase 9: tContextLoad & Routines - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md -- this log preserves the alternatives considered.

**Date:** 2026-04-15
**Phase:** 09-tcontextload-routines
**Mode:** auto
**Areas discussed:** tContextLoad Rewrite Approach, Variable Policy Behavior, DIE_ON_ERROR Behavior, Type Preservation, Java Routine Loading, Python Routine Loading, Routine Auto-Discovery

---

## tContextLoad Rewrite Approach

| Option | Description | Selected |
|--------|-------------|----------|
| Full rewrite from scratch | Consistent with Phase 5-7 pattern, existing code has 6 unimplemented keys and NaN bugs | [auto] |
| Patch existing code | Fix the 6 missing config keys and NaN bugs in current 348-line file | |

**User's choice:** [auto] Full rewrite from scratch (recommended default)
**Notes:** All prior phases (5, 6, 7) used full rewrites. Existing code ignores 6/12 config keys, has BUG-CL-002/003 NaN bugs, uses slow iterrows().

| Option | Description | Selected |
|--------|-------------|----------|
| Flow-based input only for tContextLoad | Matches converter: implicit params are job-level, not component-level | [auto] |
| Support both flow and file input in one component | More convenient but conflates two separate Talend features | |

**User's choice:** [auto] Flow-based input only (recommended default)
**Notes:** Converter explicitly documents that CONTEXTFILE/FORMAT/FIELDSEPARATOR are job-level params, not tContextLoad params.

## Variable Policy Behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Full Talend validation with severity levels | LOAD_NEW_VARIABLE/NOT_LOAD_OLD_VARIABLE emit at ERROR/WARNING/INFO level, suppressed by DISABLE_* flags | [auto] |
| Simple boolean validation | Just check and log, ignore severity levels | |

**User's choice:** [auto] Full Talend validation with severity levels (recommended default)
**Notes:** Talend uses CLOSED_LIST (ERROR/WARNING/INFO) not boolean. Must match exactly for feature parity.

## DIE_ON_ERROR Behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Standard die_on_error pattern | true=raise ComponentExecutionError, false=log and continue | [auto] |
| Always raise on validation errors | Simpler but not Talend-compatible | |

**User's choice:** [auto] Standard die_on_error pattern (recommended default)
**Notes:** Consistent with other components' die_on_error patterns.

## Java Routine Loading

| Option | Description | Selected |
|--------|-------------|----------|
| Harden existing path + add JAR auto-discovery | Validate existing loadRoutine works, add classpath JAR scanning | [auto] |
| Rewrite routine loading from scratch | Overkill -- existing bridge.load_routine and addRoutinesToBinding work | |

**User's choice:** [auto] Harden existing + JAR discovery (recommended default)
**Notes:** JavaBridge.java already has loadRoutine/addRoutinesToBinding infrastructure.

## Python Routine Loading

| Option | Description | Selected |
|--------|-------------|----------|
| Extend PythonRoutineManager | Add subdirectory support, namespace access in expressions | [auto] |
| Rewrite PythonRoutineManager | Current 180-line manager is functional, rewrite unnecessary | |

**User's choice:** [auto] Extend existing (recommended default)
**Notes:** PythonRoutineManager works for basic loading. Just needs subdirectory support and namespace integration.

## Routine Auto-Discovery

| Option | Description | Selected |
|--------|-------------|----------|
| Declare in job config, load at startup, fail fast | Parallel Java/Python pattern, clear contract | [auto] |
| Runtime discovery on first reference | More flexible but unpredictable, harder to debug | |

**User's choice:** [auto] Declare and load at startup (recommended default)
**Notes:** Matches existing java_config.routines pattern. All routines known and validated at startup.

## Claude's Discretion

- Internal tContextLoad method decomposition
- Vectorized pandas implementation details
- PythonRoutineManager refactoring internals
- Error message formatting
- Test organization

## Deferred Ideas

- Converter auto-population of routine lists from .item metadata
- Implicit context load at job level (separate from tContextLoad)
- Java routine hot-reload

---

*Log generated: 2026-04-15 (auto mode)*
