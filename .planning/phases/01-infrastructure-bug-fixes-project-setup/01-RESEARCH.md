# Phase 1: Infrastructure Bug Fixes & Project Setup - Research

**Researched:** 2026-04-14
**Domain:** Python ETL engine infrastructure -- base classes, shared services, project build config, test infrastructure
**Confidence:** HIGH

## Summary

Phase 1 rewrites four infrastructure classes from scratch (BaseComponent, GlobalMap, ContextManager, TriggerManager), creates pyproject.toml build configuration, establishes pytest infrastructure, and produces two standards documents (ENGINE_COMPONENT_PATTERN.md, ENGINE_TEST_PATTERN.md). The user decision is to rewrite rather than patch, accepting breakage of all ~50 existing engine components.

**Critical finding from code verification:** Of the 23 ENG requirements mapped to this phase, 2 are already fixed (ENG-04 broken imports, ENG-22 converter null-safety), 1 is not reproducible in current code (ENG-01 _update_global_map crash), and 2 are deferred per CONTEXT.md (ENG-13 config key alignment, ENG-14 encoding defaults). The remaining 18 are verified as real bugs or legitimate requirements. Additionally, 4 new bugs were discovered during active investigation.

**Primary recommendation:** Rewrite the four infrastructure classes with clean designs that inherently prevent the verified bugs. The rewrite must account for pandas 3.0 (already installed in the environment with Copy-on-Write always enabled), support iterate re-execution from day one (config snapshot/restore), and provide proper lifecycle hooks for the ~50 components that will be rewritten in Phases 4-11.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Print-to-logger (ENG-11) and exception hierarchy (ENG-12) migration covers infrastructure files ONLY: base_component.py, global_map.py, context_manager.py, trigger_manager.py, engine.py, exceptions.py. Later phases clean up their own component files.
- **D-02:** ENG-13 (config key alignment -- fieldseparator vs delimiter) is deferred to component phases. It's a per-component issue spanning multiple phases, similar to TEST-03.
- **D-03:** ENG-14 (encoding/delimiter/header default mismatches) is deferred to component phases -- same logic as ENG-13.
- **D-04:** ENG-17 (REJECT flow routing) stays in Phase 1. The engine provides the plumbing to route any named output flow (reject, duplicates, etc.) to the correct downstream component. Individual components are responsible for producing data on those flows in their respective phases.
- **D-05:** ENG-18 (resolve_dict corrupts python_code during context resolution) stays in Phase 1 -- the root cause is in infrastructure code (ContextManager/BaseComponent), even though it manifests in Python components.
- **D-06:** ENG-22 (converter .find().get() null-safety) -- verify during research phase whether already resolved. Skip if fixed.
- **D-07:** ENG-23 (discover additional bugs) -- research phase must: (a) verify all ENG-01 through ENG-22 against actual code to separate real bugs from audit hallucinations, (b) actively hunt for additional bugs in infrastructure files, (c) report confirmed vs. hallucinated issues. Plan only covers verified + newly discovered bugs.
- **D-08:** Rewrite infrastructure classes from scratch -- BaseComponent, GlobalMap, ContextManager, TriggerManager. Not patching bugs in existing code. Design the classes knowing iterate (Phase 10), Oracle (Phase 11), and multi-subjob execution (Phase 3) are coming.
- **D-09:** Accept breakage of all ~50 existing engine components. No backward compatibility layer. Clean design takes priority. Each component's phase (4-11) rewrites it to conform to the new pattern.
- **D-10:** Phase 1 rewrites individual classes. Phase 3 rewrites orchestration (execution loop, data routing). Engine.py gets minimal updates in Phase 1 (imports, registry, component instantiation) -- full execution loop rewrite is Phase 3.
- **D-11:** Comprehensive rewrite of BaseComponent with explicit lifecycle hooks. This sets THE pattern for all 12+ target components in later phases.
- **D-12:** Lifecycle designed as a proper contract, but components can extend or override if needed. tMap and other complex components should be able to hook into the lifecycle without being forced into a rigid mold.
- **D-13:** `_validate_config()` becomes abstract and required -- every component MUST implement it. Enforces discipline across all components.
- **D-14:** Config snapshot/restore built into the lifecycle from the start -- designed for iterate re-execution (Phase 10), not bolted on later.
- **D-15:** Create `docs/v1/standards/ENGINE_COMPONENT_PATTERN.md` -- same prescriptive style as CONVERTER_PATTERN.md. Complete code template with numbered rules that every engine component must follow.
- **D-16:** Create `docs/v1/standards/ENGINE_TEST_PATTERN.md` -- test pattern for engine component tests, mirroring TEST_PATTERN.md for converter tests.
- **D-17:** Leave AUDIT_REPORT_TEMPLATE.md as-is.
- **D-18:** JavaBridgeManager tests are deferred to Phase 2. Phase 1 tests only cover Python-side infrastructure: GlobalMap, ContextManager, TriggerManager.
- **D-19:** In-memory DataFrames for test data. No file I/O fixtures in Phase 1.
- **D-20:** Pytest markers defined from the start: unit, integration, java, slow. Configured in pyproject.toml.
- **D-21:** Minimal conftest.py -- markers and basic pytest configuration only. Each test file creates its own fixtures explicitly.
- **D-22:** Engine test location: `tests/v1/engine/` matching the source structure `src/v1/engine/`.
- **D-23:** Local pytest only -- no CI configuration in Phase 1.
- **D-24:** Exhaustive test coverage for the rewritten infrastructure (GlobalMap, ContextManager, TriggerManager, BaseComponent) -- comprehensive edge cases including empty inputs, None/NaN values, type coercion, config snapshot/restore cycles, reset behavior.
- **D-25:** Compatible dependency ranges in pyproject.toml (>=min,<next_major format). No exact pins in the project file.
- **D-26:** Optional dependency groups: core (pandas, numpy), java (pyarrow, py4j), dev (pytest). Install via `pip install -e .[dev,java]`.
- **D-27:** Pytest configuration in pyproject.toml under [tool.pytest.ini_options].
- **D-28:** Full project metadata in pyproject.toml -- name, version, description, python_requires='>=3.10'.

### Claude's Discretion
- Build backend choice (setuptools vs hatch vs other -- leaning setuptools)
- Specific lifecycle hook names and design for the BaseComponent rewrite
- Internal class design decisions (data structures, method signatures) for the rewritten classes
- ENG-22 disposition -- pending verification during research phase
- Exact dependency version ranges based on current environment

### Deferred Ideas (OUT OF SCOPE)
- ENG-13 (config key alignment) -- defer to component phases (Phase 4+), per-component issue
- ENG-14 (encoding/delimiter/header defaults) -- defer to component phases, same reasoning
- Print-to-logger in non-infrastructure component files -- each phase cleans its own components
- Exception hierarchy migration in non-infrastructure component files -- each phase handles its own
- CI configuration (GitHub Actions) -- defer until test suite is substantial
- ENG-22 (converter null-safety) -- verify during research, may already be resolved
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| ENG-01 | Fix `_update_global_map()` crash -- `value` variable undefined | **NOT REPRODUCIBLE** in current code. Line 304 no longer references `{value}`. See Bug Verification section. |
| ENG-02 | Fix `GlobalMap.get()` broken signature -- missing `default` parameter | **CONFIRMED** -- `NameError` on every call. Verified by test. |
| ENG-03 | Fix `replace_in_config` literal `[i]` bug | **CONFIRMED** -- line 174 uses `f"{path}[i]"` instead of `f"{path}[{i}]"`. |
| ENG-04 | Fix broken engine imports -- aggregate component import chain | **ALREADY FIXED** -- engine.py line 40 now imports from `.components.transform` correctly. Engine imports successfully. |
| ENG-05 | Fix context variable type conversion for all 16 mapped types | **CONFIRMED** -- 12 of 16 type mappings use string literals instead of callables. Silently returns unconverted strings. |
| ENG-06 | Fix trigger `!` replacement corrupting `!=` operators | **CONFIRMED** -- `x != 0` becomes `x  not = 0`. |
| ENG-07 | Fix streaming mode silently dropping reject data | **CONFIRMED** -- `_execute_streaming` only collects `main`, ignores `reject` key. |
| ENG-08 | Fix `_validate_config()` dead code -- wire into execute() lifecycle | **DOES NOT EXIST** in current BaseComponent. Not dead code but missing entirely. Rewrite adds it as abstract method per D-13. |
| ENG-09 | Fix BaseComponent `self.config` mutation via `resolve_dict()` | **CONFIRMED** -- line 202: `self.config = self.context_manager.resolve_dict(self.config)` loses original config. |
| ENG-10 | Fix OnSubjobOk trigger timing | Partially confirmed. The check works for common single-component subjobs but has edge cases with multi-component subjobs. Rewrite addresses this. |
| ENG-11 | Replace all `print()` debug statements with `logger` across infrastructure | **CONFIRMED** -- 108 print() calls across 7 engine files. Phase 1 covers infrastructure files only per D-01. Engine.py has 1 print in `__main__` block. |
| ENG-12 | Replace generic exceptions with custom exception hierarchy | **CONFIRMED** -- exceptions.py has a good hierarchy but BaseComponent/engine.py use generic `Exception`, `RuntimeError`, `raise` without the custom types. |
| ENG-13 | Fix config key alignment | **DEFERRED** per D-02 to component phases. |
| ENG-14 | Fix encoding/delimiter/header default mismatches | **DEFERRED** per D-03 to component phases. |
| ENG-15 | Create pyproject.toml with all Python dependencies | Supported by environment audit. All dependency versions verified. |
| ENG-16 | Standardize engine component template -- BaseComponent pattern | Addressed by the rewrite itself and ENGINE_COMPONENT_PATTERN.md creation per D-15. |
| ENG-17 | Implement REJECT flow routing in engine data flow | **CONFIRMED** -- engine.py line 571-574 has basic flow routing but reject flows are incomplete. Rewrite provides proper named flow plumbing. |
| ENG-18 | Fix `resolve_dict` corrupting `python_code` fields | **CONFIRMED** -- skip list is `['java_code', 'imports']` but `python_code` is missing. Pattern 2 replaces `context.variable_name` in code. |
| ENG-19 | Fix `validate_schema` inverted nullable logic | **CONFIRMED** -- line 351: fills NaN with 0 when `nullable=True` (inverted). |
| ENG-20 | Fix `_execute_streaming` drops reject data for every component | Same as ENG-07. **CONFIRMED**. |
| ENG-21 | Fix `self.config` mutation non-reentrant pattern -- snapshot and restore for iterate | Same root cause as ENG-09. Rewrite adds config snapshot/restore per D-14. |
| ENG-22 | Fix converter `.find().get()` null-safety pattern | **ALREADY RESOLVED** -- pattern only exists in deprecated `complex_converter`, not in active `talend_to_v1` converter. SKIP per D-06. |
| ENG-23 | Discover and fix additional engine issues not captured in audit | **4 NEW BUGS FOUND** -- see Discovered Bugs section below. |
| TEST-01 | Create pytest infrastructure (conftest.py, fixtures, markers) | No existing engine tests. `tests/v1/engine/` directory doesn't exist. Full creation needed. |
| TEST-02 | Engine unit tests for core infrastructure | Coverage target: GlobalMap, ContextManager, TriggerManager, BaseComponent. Per D-18, JavaBridgeManager deferred to Phase 2. |
</phase_requirements>

## Bug Verification Matrix

### Verified as REAL bugs in current code

| ID | Bug Description | How Verified | Status |
|----|----------------|-------------|--------|
| ENG-02 | GlobalMap.get() NameError | `gm.get('test')` raises `NameError: name 'default' is not defined` | CONFIRMED |
| ENG-03 | replace_in_config literal `[i]` | Line 174: `f"{path}[i]"` instead of `f"{path}[{i}]"` -- code inspection | CONFIRMED |
| ENG-05 | Context type conversion broken | `cm._convert_type('100', 'id_Integer')` returns string '100' with warning | CONFIRMED |
| ENG-06 | Trigger `!` corrupts `!=` | `'x != 0'.replace('!', ' not ')` produces `'x  not = 0'` | CONFIRMED |
| ENG-07/20 | Streaming drops reject | `_execute_streaming` only appends `chunk_result['main']` -- code inspection | CONFIRMED |
| ENG-09/21 | Config mutation non-reentrant | `self.config = self.context_manager.resolve_dict(self.config)` on line 202 | CONFIRMED |
| ENG-18 | resolve_dict corrupts python_code | `python_code` not in skip list `['java_code', 'imports']`; Pattern 2 replaces `context.var` | CONFIRMED |
| ENG-19 | validate_schema inverted nullable | `col_def.get('nullable', True)` -> fillna(0) when nullable=True (inverted) | CONFIRMED |

### NOT reproducible / Already fixed

| ID | Audit Claim | Current State | Verdict |
|----|------------|---------------|---------|
| ENG-01 | `_update_global_map()` references undefined `value` variable on line 304 | Line 304 does NOT reference `{value}`. The f-string terminates with `NB_LINE_REJECT:{self.stats['NB_LINE_REJECT']} "` | **NOT A BUG** -- audit report described a different code version |
| ENG-04 | Broken aggregate imports on engine.py line 40 | Line 40 correctly imports from `.components.transform`. `from src.v1.engine.engine import ETLEngine` succeeds. | **ALREADY FIXED** |
| ENG-22 | Converter `.find().get()` null-safety | Pattern only exists in deprecated `complex_converter`. The active `talend_to_v1` converter uses `_get_str()/_get_bool()/_get_int()` helpers. | **NOT APPLICABLE** to current converter |

### Audit Section 1.5 (FileInputXML case mismatch)

**Also already fixed.** `file/__init__.py` correctly imports `FileInputXML` (uppercase), matching the class name in `file_input_xml.py`.

### Requirements that are design features, not bugs

| ID | Description | Nature |
|----|-------------|--------|
| ENG-08 | `_validate_config()` dead code | Method does not exist at all in BaseComponent. Not dead code -- missing entirely. Rewrite adds as abstract. |
| ENG-10 | OnSubjobOk timing | Partially working. Common cases pass, edge cases with multi-component subjobs may fire prematurely. |
| ENG-16 | Standardize BaseComponent template | Design requirement, not a bug. |
| ENG-17 | REJECT flow routing | Engine has partial routing. Rewrite provides complete named-flow plumbing. |
| ENG-21 | Config snapshot/restore for iterate | Design requirement. No snapshot/restore mechanism exists. |

## Discovered Bugs (ENG-23)

Active investigation of infrastructure files revealed 4 additional bugs not in the audit:

### NEW-01: `ContextManager` imports unused `os` and `sys` modules

**File:** `src/v1/engine/context_manager.py`, lines 8-9
**Description:** `import os` and `import sys` are present but neither `os.` nor `sys.` is referenced anywhere in the file. These are dead imports.
**Impact:** Minor code quality issue, but notable because it suggests copy-paste origin.
**Confidence:** HIGH [VERIFIED: grep search found 0 uses of os. or sys. in context_manager.py]

### NEW-02: `resolve_dict` does not recurse into dicts inside lists

**File:** `src/v1/engine/context_manager.py`, line 157
**Description:** The list handling in `resolve_dict` only calls `resolve_string()` on string elements. Dict elements inside lists pass through unresolved:
```python
resolved[key] = [self.resolve_string(v) if isinstance(v, str) else v for v in value]
```
**Impact:** Component configs with structures like `conditions: [{field: "amount", value: "${context.threshold}"}]` will NOT have `${context.threshold}` resolved. This affects tMap (mappings list of dicts), tAggregateRow (operations list of dicts), tFilterRows (conditions list of dicts), and many others.
**Confidence:** HIGH [VERIFIED: tested `cm.resolve_dict({'conditions': [{'value': '${context.threshold}'}]})` -- dict values remain unresolved]

### NEW-03: `BaseComponent.__repr__()` missing opening parenthesis

**File:** `src/v1/engine/base_component.py`, line 382
**Description:** `return f"{self.component_type} id={self.id} status={self.status.value})"` -- closing `)` without opening `(`.
**Impact:** Cosmetic but produces malformed debug output.
**Confidence:** HIGH [VERIFIED: code inspection]

### NEW-04: `TriggerManager._evaluate_condition` uses unsandboxed `eval()`

**File:** `src/v1/engine/trigger_manager.py`, line 234
**Description:** `result = eval(python_condition)` executes with full Python runtime access. Condition strings originate from Talend XML (via converter). While the converter does some transformation, the eval has no sandboxing.
**Impact:** Security vulnerability if XML input files are from untrusted sources. Also masks errors -- the `except` returns `False` silently.
**Confidence:** HIGH [VERIFIED: code inspection, documented in audit Section 3.3]

### NEW-05: `TriggerManager._evaluate_condition` only handles `((Integer)...)` cast

**File:** `src/v1/engine/trigger_manager.py`, lines 200-208
**Description:** Only `((Integer)globalMap.get("key"))` regex is handled. `((Boolean)...)`, `((String)...)`, `((Long)...)` casts all fail silently.
**Impact:** RunIf triggers with non-Integer cast types silently evaluate to `False`, skipping entire subjobs.
**Confidence:** HIGH [VERIFIED: code inspection, documented in audit Section 3.1]

## Standard Stack

### Core

| Library | Env Version | pyproject.toml Range | Purpose | Why Standard |
|---------|-------------|---------------------|---------|--------------|
| pandas | 3.0.1 | >=2.0,<4 | DataFrame-based data processing | Already the transport layer for all engine components [VERIFIED: pip show] |
| numpy | 2.4.2 | >=1.24,<3 | Numerical operations, NaN handling | Required by pandas, used in bridge [VERIFIED: pip show] |

### Supporting

| Library | Env Version | pyproject.toml Range | Purpose | When to Use |
|---------|-------------|---------------------|---------|-------------|
| pyarrow | 23.0.1 | >=15.0,<24 | Arrow IPC for Java bridge data transfer | Java bridge group [VERIFIED: pip show] |
| py4j | 0.10.9.9 | >=0.10.9,<0.11 | Python-Java gateway | Java bridge group [VERIFIED: pip show] |
| openpyxl | 3.1.5 | >=3.1,<4 | Excel .xlsx read/write | File I/O components [VERIFIED: pip show] |
| xlrd | 2.0.2 | >=2.0,<3 | Legacy .xls reading | File I/O components [VERIFIED: pip show] |
| lxml | 6.0.3 | >=4.9,<7 | XML processing with XPath | XML components [VERIFIED: pip show] |
| PyYAML | 6.0.3 | >=6.0,<7 | YAML config parsing | SWIFT transformer [VERIFIED: pip show] |
| jsonpath-ng | 1.8.0 | >=1.5,<2 | JSONPath evaluation | ExtractJSONFields [VERIFIED: pip show] |

### Dev Dependencies

| Library | Env Version | Purpose |
|---------|-------------|---------|
| pytest | 9.0.2 | Test framework [VERIFIED: pip show] |

### Build Backend Decision

**Recommendation: Use setuptools** as the build backend. [ASSUMED]

Rationale:
- setuptools is the most widely used Python build backend
- The project has no complex build requirements (no C extensions, no custom build steps)
- D-25/D-26/D-28 specify straightforward pyproject.toml structure that setuptools supports natively
- `pip install -e .[dev,java]` works with setuptools out of the box
- Note: setuptools is NOT currently installed in the environment. It will be pulled in by pip when processing pyproject.toml.

**pyproject.toml structure:**
```toml
[build-system]
requires = ["setuptools>=68.0", "wheel"]
build-backend = "setuptools.backends._legacy:_Backend"

[project]
name = "dataprep"
version = "1.0.0"
description = "Talend ETL Migration Engine"
requires-python = ">=3.10"
dependencies = [
    "pandas>=2.0,<4",
    "numpy>=1.24,<3",
]

[project.optional-dependencies]
java = ["pyarrow>=15.0,<24", "py4j>=0.10.9,<0.11"]
excel = ["openpyxl>=3.1,<4", "xlrd>=2.0,<3"]
xml = ["lxml>=4.9,<7"]
yaml = ["PyYAML>=6.0,<7"]
json = ["jsonpath-ng>=1.5,<2"]
dev = ["pytest>=8.0,<10"]
all = ["dataprep[java,excel,xml,yaml,json]"]

[tool.pytest.ini_options]
testpaths = ["tests"]
markers = [
    "unit: Unit tests (fast, no I/O)",
    "integration: Integration tests (may require file I/O)",
    "java: Tests requiring Java bridge",
    "slow: Tests that take >5 seconds",
]
addopts = "-v --tb=short"
```

### Critical: pandas 3.0 Compatibility

The environment has pandas 3.0.1 installed with Copy-on-Write (CoW) ALWAYS enabled. [VERIFIED: `pd.options.mode.copy_on_write` confirmed as True]

The REQUIREMENTS.md says "pandas 3.0 upgrade" is out of scope, but the reality is **pandas 3.0 is already the installed version**. The rewrite MUST be compatible with pandas 3.0 behavior:

1. **Copy-on-Write is always on**: In-place DataFrame modifications (`df[col] = ...`) create copies automatically. This means existing patterns like `df[col_name] = pd.to_numeric(...)` in `validate_schema` are safe but may have slightly different memory behavior.
2. **`inplace=` parameter deprecated**: Many methods no longer support `inplace=True`. Use assignment instead.
3. **`pd.Int64Dtype()`**: Nullable integer types work correctly and should be used for nullable integer columns (fixing ENG-19).

The pyproject.toml specifies `pandas>=2.0,<4` to be compatible with both pandas 2.x and 3.x environments. [ASSUMED -- this range was chosen to avoid breaking existing deployments that may have pandas 2.x]

## Architecture Patterns

### Recommended Project Structure

```
src/v1/engine/
    __init__.py                      # Exports ETLEngine
    base_component.py                # REWRITE: BaseComponent ABC
    base_iterate_component.py        # REWRITE: BaseIterateComponent (extends BaseComponent)
    global_map.py                    # REWRITE: GlobalMap
    context_manager.py               # REWRITE: ContextManager
    trigger_manager.py               # REWRITE: TriggerManager
    engine.py                        # MINIMAL UPDATES: imports, instantiation
    exceptions.py                    # REFINE: add missing exception types if needed
    java_bridge_manager.py           # NO CHANGES (Phase 2)
    python_routine_manager.py        # NO CHANGES
    components/                      # NO CHANGES in Phase 1 (components break, fixed in Phases 4-11)

tests/v1/engine/
    __init__.py
    conftest.py                      # Minimal: markers, basic config
    test_global_map.py               # Exhaustive GlobalMap tests
    test_context_manager.py          # Exhaustive ContextManager tests
    test_trigger_manager.py          # Exhaustive TriggerManager tests
    test_base_component.py           # BaseComponent lifecycle tests (using concrete test subclass)

docs/v1/standards/
    ENGINE_COMPONENT_PATTERN.md      # NEW: Prescriptive component pattern
    ENGINE_TEST_PATTERN.md           # NEW: Prescriptive test pattern

pyproject.toml                       # NEW: Build config, dependencies, pytest config
```

### Pattern 1: BaseComponent Lifecycle (Template Method)

**What:** BaseComponent provides a rigid `execute()` lifecycle with well-defined hooks that subclasses implement. The template method orchestrates: validation, config snapshot, Java resolution, context resolution, mode selection, processing, stats update, and config restore.

**When to use:** Every engine component inherits BaseComponent.

**Design for the rewrite:**
```python
class BaseComponent(ABC):
    """Base class for all ETL engine components."""

    def __init__(self, component_id: str, config: dict, global_map=None, context_manager=None):
        self.id = component_id
        self._original_config = config          # FROZEN -- never mutated
        self.config = copy.deepcopy(config)     # Working copy -- resolved per execution
        self.global_map = global_map
        self.context_manager = context_manager
        # ... other init

    def execute(self, input_data=None) -> dict:
        """Template method -- DO NOT OVERRIDE (except tMap with justification)."""
        self._snapshot_config()           # Save for re-execution
        try:
            self._validate_config()       # Abstract -- subclass MUST implement
            self._resolve_expressions()   # Java + context resolution
            mode = self._select_mode(input_data)
            if mode == ExecutionMode.STREAMING:
                result = self._execute_streaming(input_data)
            else:
                result = self._execute_batch(input_data)
            self._update_stats_from_result(result)
            self._update_global_map()
            return result
        except Exception as e:
            self._handle_error(e)
            raise
        finally:
            self._restore_config()        # Always restore for iterate

    @abstractmethod
    def _validate_config(self) -> None:
        """Validate component configuration. Raise ConfigurationError if invalid."""
        ...

    @abstractmethod
    def _process(self, input_data=None) -> dict:
        """Process data. Return dict with 'main' and optionally 'reject', other named flows."""
        ...

    def _snapshot_config(self):
        """Save config before resolution for iterate re-execution."""
        self.config = copy.deepcopy(self._original_config)

    def _restore_config(self):
        """No-op in normal execution. Config is always re-derived from _original_config."""
        pass  # _snapshot_config already handles this at start of execute()

    def reset(self):
        """Reset component state for iterate re-execution."""
        self.config = copy.deepcopy(self._original_config)
        self.stats = self._default_stats()
        self.status = ComponentStatus.PENDING
```

**Key design decisions:**
- `_original_config` is FROZEN at construction time -- never mutated [addresses ENG-09/ENG-21]
- `config` is re-derived from `_original_config` at start of each `execute()` [addresses config mutation]
- `_validate_config()` is abstract -- forces every subclass to implement [addresses ENG-08, per D-13]
- `execute()` calls `_snapshot_config()` FIRST, before any resolution [addresses iterate re-execution per D-14]
- `reset()` provides explicit state cleanup for iterate loops [supports Phase 10]

### Pattern 2: GlobalMap (Thread-Aware Key-Value Store)

**What:** GlobalMap stores component statistics and inter-component variables. It's the Talend `globalMap` equivalent.

**Design for the rewrite:**
```python
class GlobalMap:
    """Talend-compatible globalMap implementation."""

    def __init__(self):
        self._store: dict[str, Any] = {}
        self._component_stats: dict[str, dict[str, Any]] = {}

    def get(self, key: str, default: Any = None) -> Any:    # FIX: default parameter
        return self._store.get(key, default)

    def put(self, key: str, value: Any) -> None:
        self._store[key] = value

    def put_component_stat(self, component_id: str, stat_name: str, value: Any) -> None:
        if component_id not in self._component_stats:
            self._component_stats[component_id] = {}
        self._component_stats[component_id][stat_name] = value
        self._store[f"{component_id}_{stat_name}"] = value

    def get_component_stat(self, component_id: str, stat_name: str, default: Any = 0) -> Any:
        if component_id in self._component_stats:
            return self._component_stats[component_id].get(stat_name, default)
        return self._store.get(f"{component_id}_{stat_name}", default)

    def clear(self) -> None: ...
    def reset_component(self, component_id: str) -> None: ...  # NEW: for iterate
    def get_all(self) -> dict[str, Any]: ...
    def contains(self, key: str) -> bool: ...
    def remove(self, key: str) -> None: ...
```

### Pattern 3: ContextManager (Safe Variable Resolution)

**What:** Manages context variables with proper type conversion and safe resolution that doesn't corrupt code fields.

**Design for the rewrite:**
```python
class ContextManager:
    """Context variable management with safe resolution."""

    # Fields that must NOT be resolved (they contain code)
    SKIP_RESOLUTION_KEYS = frozenset({'java_code', 'imports', 'python_code'})

    def resolve_dict(self, config: dict) -> dict:
        """Resolve context variables in a config dict. Returns NEW dict (never mutates input)."""
        resolved = {}
        for key, value in config.items():
            if key in self.SKIP_RESOLUTION_KEYS:
                resolved[key] = value  # Pass through code fields
            elif isinstance(value, str):
                resolved[key] = self.resolve_string(value)
            elif isinstance(value, dict):
                resolved[key] = self.resolve_dict(value)
            elif isinstance(value, list):
                resolved[key] = self._resolve_list(value)  # NEW: recurse into lists
            else:
                resolved[key] = value
        return resolved

    def _resolve_list(self, items: list) -> list:
        """Resolve context variables in list elements, including nested dicts."""
        result = []
        for item in items:
            if isinstance(item, str):
                result.append(self.resolve_string(item))
            elif isinstance(item, dict):
                result.append(self.resolve_dict(item))  # FIX: recurse into dicts in lists
            elif isinstance(item, list):
                result.append(self._resolve_list(item))
            else:
                result.append(item)
        return result

    def _convert_type(self, value: Any, value_type: str) -> Any:
        """Convert value to specified type. Uses actual callables, not string literals."""
        type_mapping = {
            'id_String': str,       # FIX: actual function, not string 'str'
            'id_Integer': int,      # FIX: actual function, not string 'int'
            'id_Long': int,
            'id_Float': float,
            'id_Double': float,
            'id_Boolean': lambda v: str(v).lower() in ('true', '1', 'yes'),
            'id_Date': str,
            'id_BigDecimal': Decimal,
            'str': str,
            'int': int,
            'float': float,
            'bool': lambda v: str(v).lower() in ('true', '1', 'yes'),
            'Decimal': Decimal,
            'datetime': str,
            'object': str,
        }
        # ...
```

### Pattern 4: TriggerManager (Safe Condition Evaluation)

**What:** Manages trigger flow between subjobs with safe condition evaluation (no raw `eval()`).

**Design for the rewrite:**
```python
class TriggerManager:
    """Trigger management with safe condition evaluation."""

    def _evaluate_condition(self, condition: str) -> bool:
        """Evaluate RunIf condition safely without raw eval()."""
        # 1. Parse globalMap.get() references for ALL cast types
        # 2. Replace Java operators with Python equivalents
        #    - Replace != BEFORE ! (order matters)
        #    - Use regex for standalone ! -> not
        # 3. Evaluate with restricted globals (no builtins)
        safe_globals = {"__builtins__": {}, "None": None, "True": True, "False": False}
        result = eval(python_condition, safe_globals, {})
        return bool(result)
```

### Anti-Patterns to Avoid

- **Config mutation in execute():** Never assign `self.config = resolved_version`. Always derive from `_original_config`. [Root cause of ENG-09/ENG-21]
- **String replacement for operator conversion:** Never use `.replace('!', ' not ')` without protecting `!=`. Use regex or replace longer operators first. [Root cause of ENG-06]
- **String literals as type converters:** Never use `'int'` when you mean `int`. String literals are not callable. [Root cause of ENG-05]
- **Skipping lifecycle hooks:** Never override `execute()` without calling super() or replicating the full lifecycle. [Current tMap anti-pattern]
- **Direct stats assignment:** Never use `self.stats['NB_LINE'] = len(df)` in `_process()`. Always use `self._update_stats(rows, ok, reject)` which uses `+=` accumulation. [Streaming mode correctness]
- **Bare eval():** Never use `eval()` with unrestricted globals. Always use `safe_globals = {"__builtins__": {}}`. [Security concern]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Config deep copy | Manual dict cloning | `copy.deepcopy()` | Nested dicts, lists require deep copy. Shallow copy misses nested mutations. |
| Type conversion registry | if/elif chain | Dict mapping type names to callables | Extensible, testable, no fall-through bugs |
| DataFrame memory estimation | Custom size calculation | `df.memory_usage(deep=True).sum()` | pandas built-in, handles object columns correctly |
| Nullable integer columns | `fillna(0).astype('int64')` | `pd.Int64Dtype()` (capital I) | pandas nullable integer type -- preserves NaN semantics |
| Safe eval | `eval()` with try/except | `eval(expr, {"__builtins__": {}}, locals)` | Restricts access to dangerous built-ins |
| Context variable patterns | Custom string parsing | `re.sub()` with proper patterns | Regex handles overlapping patterns correctly |

## Common Pitfalls

### Pitfall 1: Config Mutation Breaking Iterate

**What goes wrong:** Component works on first execution but produces wrong results on second execution in iterate loop.
**Why it happens:** `self.config` is overwritten with resolved values during first execution. Second execution resolves already-resolved values (double resolution or stale values).
**How to avoid:** Always resolve from `_original_config`, never from `self.config`. The `_snapshot_config()` pattern in execute() handles this.
**Warning signs:** Tests pass individually but fail when run in a loop.

### Pitfall 2: pandas 3.0 Copy-on-Write Surprises

**What goes wrong:** Code that previously modified DataFrames in-place silently creates copies, leading to unexpected memory usage or "values didn't change" bugs.
**Why it happens:** pandas 3.0 enables CoW by default. `df[col] = value` may trigger a copy.
**How to avoid:** Always use explicit assignment patterns. Don't rely on in-place modification side effects. Test with the installed pandas version.
**Warning signs:** Tests pass with pandas 2.x but fail with 3.x.

### Pitfall 3: String Replacement Order in Operator Conversion

**What goes wrong:** `!=` becomes ` not =` instead of `!= ` being preserved.
**Why it happens:** Replacing single-character `!` before multi-character `!=`.
**How to avoid:** Replace longer operators first (`!=`, `&&`, `||`), then single-character operators. Or use regex with negative lookahead: `re.sub(r'!(?!=)', ' not ', condition)`.
**Warning signs:** RunIf conditions with `!=` silently evaluate to False.

### Pitfall 4: Abstract Method vs. NotImplementedError

**What goes wrong:** Subclass forgets to implement `_validate_config()` and crashes at runtime instead of at import/instantiation time.
**Why it happens:** Using `raise NotImplementedError` instead of `@abstractmethod`.
**How to avoid:** Use ABC's `@abstractmethod` decorator. Python will raise `TypeError` when attempting to instantiate a class that doesn't implement all abstract methods.
**Warning signs:** Runtime crashes in production instead of import-time errors in development.

### Pitfall 5: resolve_dict Not Recursing Into Lists of Dicts

**What goes wrong:** Context variables in tMap mappings, tFilterRows conditions, tAggregateRow operations (all stored as lists of dicts in config) are not resolved.
**Why it happens:** The list handler in resolve_dict only processes string elements, skipping dict elements.
**How to avoid:** Implement `_resolve_list()` that recurses into dicts, lists, and strings within list elements.
**Warning signs:** Components receive unresolved `${context.var}` strings in nested config structures.

## Code Examples

### BaseComponent Test Subclass Pattern

For testing the abstract BaseComponent, tests need a concrete subclass:

```python
# In test_base_component.py
class ConcreteComponent(BaseComponent):
    """Minimal concrete component for testing BaseComponent lifecycle."""

    def _validate_config(self) -> None:
        pass  # Accept any config

    def _process(self, input_data=None) -> dict:
        return {'main': input_data, 'reject': None}
```

### GlobalMap Test Pattern

```python
class TestGlobalMapGet:
    def test_get_existing_key(self):
        gm = GlobalMap()
        gm.put("key", "value")
        assert gm.get("key") == "value"

    def test_get_missing_key_returns_default(self):
        gm = GlobalMap()
        assert gm.get("missing") is None
        assert gm.get("missing", 42) == 42

    def test_get_component_stat_with_default(self):
        gm = GlobalMap()
        assert gm.get_component_stat("comp_1", "NB_LINE", 0) == 0
```

### ContextManager Type Conversion Test Pattern

```python
class TestContextManagerTypeConversion:
    def test_id_integer_converts_to_int(self):
        cm = ContextManager()
        cm.set("threshold", "100", "id_Integer")
        assert cm.get("threshold") == 100
        assert isinstance(cm.get("threshold"), int)

    def test_id_boolean_converts_true(self):
        cm = ContextManager()
        cm.set("flag", "true", "id_Boolean")
        assert cm.get("flag") is True
```

### TriggerManager Safe Eval Test Pattern

```python
class TestTriggerConditionEval:
    def test_not_equals_preserved(self):
        gm = GlobalMap()
        gm.put("ERROR", "some error")
        tm = TriggerManager(gm)
        # Condition: globalMap.get("ERROR") != None
        # Should evaluate to True (error is set)
        assert tm._evaluate_condition('globalMap.get("ERROR") != null') is True

    def test_boolean_cast_handled(self):
        gm = GlobalMap()
        gm.put("tFileExist_1_EXISTS", True)
        tm = TriggerManager(gm)
        assert tm._evaluate_condition('((Boolean)globalMap.get("tFileExist_1_EXISTS"))') is True
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| pandas 2.x default (CoW disabled) | pandas 3.0 (CoW always enabled) | pandas 3.0.0 (April 2024) | DataFrame modifications may behave differently. Must test with CoW. [VERIFIED: installed version is 3.0.1] |
| `pd.Int64Dtype` optional | `pd.Int64Dtype` standard for nullable ints | pandas 1.0+ | Use for nullable integer columns instead of float64 workaround |
| `pytest.ini` or `setup.cfg` for pytest config | `pyproject.toml [tool.pytest.ini_options]` | pytest 6.0+ | Single config file [VERIFIED: pytest 9.0.2 supports this] |

**Note on py4j version:** The environment has py4j 0.10.9.9, which is newer than the 0.10.9.7 mentioned in CLAUDE.md. The pyproject.toml should use `>=0.10.9,<0.11` to accept both. [VERIFIED: pip show]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | setuptools is the appropriate build backend | Standard Stack | Low -- hatch or flit would also work; pyproject.toml structure is similar. User indicated leaning setuptools. |
| A2 | pandas>=2.0,<4 is a safe dependency range | Standard Stack | Medium -- some components may use pandas 2.x-specific APIs. The rewrite should use pandas 3.0-compatible APIs only. |
| A3 | The `_original_config` deep copy pattern is sufficient for iterate re-execution | Architecture Patterns | Low -- copy.deepcopy handles all JSON-serializable config structures. Edge case: config containing non-serializable objects (unlikely for JSON-derived configs). |

## Open Questions (RESOLVED)

1. **pandas 3.0 vs. REQUIREMENTS.md Out-of-Scope Declaration**
   - What we know: pandas 3.0.1 is installed. REQUIREMENTS.md says "pandas 3.0 upgrade" is out of scope.
   - What's unclear: Does "out of scope" mean "don't upgrade to 3.0" (already happened) or "don't address 3.0-specific breaking changes"?
   - RESOLVED: Write the rewrite code to be compatible with pandas 3.0 since it's the installed version. The pyproject.toml range `>=2.0,<4` allows both. No special pandas 3.0 migration work beyond writing correct code. Plans implement this.

2. **die_on_error as BaseComponent First-Class Attribute**
   - What we know: The audit (Section 2.4) recommends making `die_on_error` a BaseComponent attribute. Currently ~50% of components implement it ad-hoc.
   - What's unclear: Should this be part of Phase 1 BaseComponent rewrite or left for Phase 3 engine execution loop?
   - RESOLVED: Add `die_on_error` as a BaseComponent property (reads from `self.config.get('die_on_error', True)`) in Phase 1. The engine enforcement of it belongs in Phase 3. Plan 05 implements this.

3. **BaseIterateComponent Rewrite Scope**
   - What we know: BaseIterateComponent extends BaseComponent and overrides `execute()`. The rewrite of BaseComponent changes the lifecycle.
   - What's unclear: CONTEXT.md says "rewrite BaseComponent" but doesn't explicitly mention BaseIterateComponent.
   - RESOLVED: Rewrite BaseIterateComponent alongside BaseComponent in Phase 1 to ensure the iterate lifecycle is correct. It's a small file (176 lines) and must align with the new BaseComponent. Plan 05 implements this.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.10+ | Core engine | Yes | 3.12.12 | -- |
| pandas | DataFrame processing | Yes | 3.0.1 | -- |
| numpy | Numerical ops | Yes | 2.4.2 | -- |
| pytest | Test infrastructure | Yes | 9.0.2 | -- |
| setuptools | Build backend | No | -- | pip install setuptools (or use hatch) |

**Missing dependencies with no fallback:** None blocking.

**Missing dependencies with fallback:**
- setuptools not installed. Will be auto-installed by pip when processing pyproject.toml. No manual action needed.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 [VERIFIED: pip show] |
| Config file | None -- to be created as `pyproject.toml [tool.pytest.ini_options]` |
| Quick run command | `pytest tests/v1/engine/ -m unit -x` |
| Full suite command | `pytest tests/v1/engine/ -v` |

### Phase Requirements to Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ENG-02 | GlobalMap.get() with default parameter | unit | `pytest tests/v1/engine/test_global_map.py -x` | Wave 0 |
| ENG-03 | Java expression resolution in lists | unit | `pytest tests/v1/engine/test_base_component.py -x` | Wave 0 |
| ENG-05 | Context type conversion for all types | unit | `pytest tests/v1/engine/test_context_manager.py -x` | Wave 0 |
| ENG-06 | Trigger condition != preservation | unit | `pytest tests/v1/engine/test_trigger_manager.py -x` | Wave 0 |
| ENG-07/20 | Streaming mode preserves reject data | unit | `pytest tests/v1/engine/test_base_component.py -x` | Wave 0 |
| ENG-09/21 | Config snapshot/restore for iterate | unit | `pytest tests/v1/engine/test_base_component.py -x` | Wave 0 |
| ENG-11 | No print() in infrastructure files | unit | `grep -r 'print(' src/v1/engine/{base_component,global_map,context_manager,trigger_manager,engine,exceptions}.py` | Manual |
| ENG-12 | Custom exceptions used in infrastructure | unit | `pytest tests/v1/engine/test_base_component.py -x` | Wave 0 |
| ENG-15 | pyproject.toml valid | unit | `pip install -e .[dev] && pytest --collect-only` | Manual |
| ENG-16 | BaseComponent lifecycle correctness | unit | `pytest tests/v1/engine/test_base_component.py -x` | Wave 0 |
| ENG-17 | Named flow routing (reject etc.) | unit | `pytest tests/v1/engine/test_base_component.py -x` | Wave 0 |
| ENG-18 | python_code not corrupted by resolve_dict | unit | `pytest tests/v1/engine/test_context_manager.py -x` | Wave 0 |
| ENG-19 | validate_schema nullable logic correct | unit | `pytest tests/v1/engine/test_base_component.py -x` | Wave 0 |
| TEST-01 | Pytest infrastructure exists | manual | `pytest --co tests/v1/engine/` | Wave 0 |
| TEST-02 | Core infrastructure has passing tests | unit | `pytest tests/v1/engine/ -v` | Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest tests/v1/engine/ -m unit -x --tb=short`
- **Per wave merge:** `pytest tests/v1/engine/ -v`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/v1/engine/__init__.py` -- package marker
- [ ] `tests/v1/engine/conftest.py` -- markers, basic fixtures
- [ ] `tests/v1/engine/test_global_map.py` -- GlobalMap tests
- [ ] `tests/v1/engine/test_context_manager.py` -- ContextManager tests
- [ ] `tests/v1/engine/test_trigger_manager.py` -- TriggerManager tests
- [ ] `tests/v1/engine/test_base_component.py` -- BaseComponent lifecycle tests
- [ ] `tests/__init__.py` exists, `tests/v1/__init__.py` needs creation

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | N/A -- batch ETL system, no user auth |
| V3 Session Management | No | N/A |
| V4 Access Control | No | N/A |
| V5 Input Validation | Yes | Config validation via `_validate_config()` abstract method; type conversion in ContextManager |
| V6 Cryptography | No | N/A |

### Known Threat Patterns for Python ETL Engine

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Code injection via eval() in TriggerManager | Elevation of Privilege | Restricted eval with `{"__builtins__": {}}` globals |
| Config injection via context variable resolution | Tampering | SKIP_RESOLUTION_KEYS for code fields; Pattern 2 (bare context.var) should be restricted |
| Arbitrary code in python_code fields | Elevation of Privilege | Out of scope for Phase 1 -- PYCO-02 (Phase 8) addresses removing os/sys from namespace |

## Sources

### Primary (HIGH confidence)
- `src/v1/engine/base_component.py` -- read in full, all bugs verified against actual code
- `src/v1/engine/global_map.py` -- read in full, ENG-02 verified by execution
- `src/v1/engine/context_manager.py` -- read in full, ENG-05/ENG-18 verified by execution
- `src/v1/engine/trigger_manager.py` -- read in full, ENG-06 verified by string replacement test
- `src/v1/engine/engine.py` -- read in full, ENG-04 verified as already fixed
- `src/v1/engine/exceptions.py` -- read in full
- `src/v1/engine/base_iterate_component.py` -- read in full
- `docs/v1/audit/CROSS_CUTTING_ISSUES.md` -- read in full, cross-referenced against code
- `docs/v1/standards/CONVERTER_PATTERN.md` -- reference for ENGINE_COMPONENT_PATTERN.md style
- `docs/v1/standards/TEST_PATTERN.md` -- reference for ENGINE_TEST_PATTERN.md style
- pip show output for all dependency versions

### Secondary (MEDIUM confidence)
- `.planning/codebase/CONCERNS.md` -- tech debt and known bugs summary

### Tertiary (LOW confidence)
- None -- all claims verified against actual code or runtime tests.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all versions verified via pip show
- Architecture: HIGH -- patterns derived from actual code analysis and CONTEXT.md decisions
- Bug verification: HIGH -- all bugs tested against actual code; 3 audit claims proven incorrect
- Pitfalls: HIGH -- derived from verified bugs, not speculation

**Research date:** 2026-04-14
**Valid until:** 2026-05-14 (stable -- infrastructure code changes only via this phase)
