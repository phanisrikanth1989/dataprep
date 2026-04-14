# Coding Conventions

**Analysis Date:** 2026-04-14

## Naming Patterns

**Files:**
- Use `snake_case.py` for all Python modules: `filter_rows.py`, `file_input_delimited.py`, `aggregate_row.py`
- Test files: prefix with `test_` matching the source file name: `test_filter_rows.py`, `test_converter.py`
- Package init files: `__init__.py` in every directory to mark packages

**Functions/Methods:**
- Use `snake_case` for all functions and methods: `convert_file()`, `_parse_flows()`, `_get_input_data()`
- Private methods prefixed with single underscore: `_process()`, `_validate_config()`, `_execute_component()`
- Static helper methods prefixed with single underscore: `_get_str()`, `_get_bool()`, `_get_int()`, `_parse_schema()`
- Module-level private helpers prefixed with single underscore: `_safe_int()`, `_parse_conditions()`

**Variables:**
- Use `snake_case` for all variables: `component_id`, `flow_name`, `job_config`
- Constants use `UPPER_SNAKE_CASE`: `REGISTRY`, `COMPONENT_REGISTRY`, `DEFAULT_DELIMITER`, `MEMORY_THRESHOLD_MB`
- Private module-level constants prefixed with underscore: `_FLOW_CONNECTOR_TYPES`, `_JAVA_COMPONENT_TYPES`, `_DATE_TOKENS`, `_SKIP_FIELDS`

**Classes:**
- Use `PascalCase` for all classes: `TalendToV1Converter`, `ComponentConverter`, `FilterRowsConverter`, `ETLEngine`
- Dataclasses follow same pattern: `SchemaColumn`, `TalendNode`, `TalendConnection`, `ComponentResult`
- Enums use `PascalCase` with `UPPER_SNAKE_CASE` members: `ExecutionMode.BATCH`, `ComponentStatus.SUCCESS`
- Exception classes end with `Error`: `ETLError`, `ConfigurationError`, `FileOperationError`

**Types:**
- Use `PascalCase` for type aliases (rare -- mostly inline typing)
- Type hints follow standard `typing` module: `Dict[str, Any]`, `List[str]`, `Optional[int]`

## Code Style

**Formatting:**
- No automated formatter configured (no `.prettierrc`, `pyproject.toml`, `ruff.toml`, `.flake8` found)
- Indentation: 4 spaces (Python standard)
- Line length: no enforced limit, but lines generally stay under 120 characters
- String quotes: double quotes preferred for strings, single quotes used occasionally in engine code

**Linting:**
- No linter configuration detected
- `# noqa: F401` used for intentional unused imports (e.g., `src/converters/talend_to_v1/converter.py` line 23)
- `from __future__ import annotations` used consistently in converter module files

**Two Codebase Styles:**
The codebase has two distinct style zones:

1. **Converter module** (`src/converters/talend_to_v1/`): Cleaner, more modern Python
   - Uses `from __future__ import annotations`
   - Uses dataclasses extensively
   - Type hints on all function signatures
   - Docstrings with reStructuredText style
   - Consistent spacing around operators and comments
   - Section separators with `# ---` comment blocks

2. **Engine module** (`src/v1/engine/`): More informal style
   - f-strings with logging (anti-pattern, should use `%` formatting)
   - Mixed comment styles (some `#Comment` without space after `#`)
   - `print()` statements mixed with `logger` calls (debug artifacts)
   - Less consistent type hints
   - Google-style docstrings with `Args:` / `Returns:`

## Import Organization

**Order:**
1. Standard library imports (`json`, `logging`, `os`, `re`, `time`, `xml.etree.ElementTree`)
2. Third-party imports (`pandas as pd`, `pytest`)
3. Local/project imports (`from .components.base import ...`, `from ...base_component import BaseComponent`)

**Conventions:**
- Use `from __future__ import annotations` at the top of converter module files
- Relative imports within a package: `from ..type_mapping import convert_type`, `from ...base_component import BaseComponent`
- Absolute imports from project root in tests: `from src.converters.talend_to_v1.converter import TalendToV1Converter`
- `TYPE_CHECKING` guard for circular imports: see `src/converters/talend_to_v1/components/registry.py`

**Path Aliases:**
- None configured. All imports use full dotted paths from `src/`.

## Error Handling

**Converter Module Pattern:**
- Errors during component conversion are caught at the orchestrator level (`src/converters/talend_to_v1/converter.py` lines 97-107)
- Failed conversions produce an `_unsupported` placeholder instead of crashing
- Warnings accumulated as `List[str]` in `ComponentResult.warnings`
- Review items accumulated as `List[Dict[str, Any]]` in `ComponentResult.needs_review`

```python
# Pattern: Catch-and-placeholder at orchestrator level
try:
    converter_cls = REGISTRY.get(node.component_type)
    if converter_cls is not None:
        result = converter_cls().convert(node, job.connections, context)
    else:
        comp = self._unsupported(node)
except Exception as exc:
    logger.error("Converter error...", exc_info=True)
    comp = self._unsupported(node)
    warnings.append(f"Component '{node.component_id}' failed: {exc}")
```

**Engine Module Pattern:**
- Custom exception hierarchy rooted at `ETLError` (`src/v1/engine/exceptions.py`)
- Exceptions: `ConfigurationError`, `DataValidationError`, `ComponentExecutionError`, `FileOperationError`, `JavaBridgeError`, `ExpressionError`, `SchemaError`
- `ComponentExecutionError` includes `component_id` and `cause` attributes
- Components raise specific exceptions (`ConfigurationError`, `FileOperationError`) from `_process()`
- Engine catches exceptions in `_execute_component()` and tracks `failed_components`

```python
# Pattern: die_on_error conditional
if not filepath:
    if die_on_error:
        raise ConfigurationError(f"[{self.id}] 'filepath' is required")
    else:
        return {'main': pd.DataFrame()}
```

**Validation Pattern:**
- Post-conversion validation via `validate_config()` in `src/converters/talend_to_v1/validator.py`
- Uses `ValidationIssue` dataclass with `severity` ("error" / "warning" / "info")
- Returns `ValidationReport` with `valid: bool`, `issues: List[ValidationIssue]`, `summary: str`

## Logging

**Framework:** Python stdlib `logging`

**Patterns:**
- Each module gets its own logger: `logger = logging.getLogger(__name__)`
- Converter module uses `%`-style formatting with `logger.info()`: `logger.info("Parsed job '%s' with %d nodes", ...)`
- Engine module uses f-strings with `logger.info()`: `logger.info(f"Component {comp_id} completed")`
- Log levels:
  - `DEBUG`: Schema propagation, config details, chunk processing
  - `INFO`: Component conversion, job execution milestones, file reads
  - `WARNING`: Missing columns, unknown types, fallback behaviors
  - `ERROR`: Conversion failures, execution errors
- Engine has `logging.basicConfig(level=logging.INFO)` at module level in `src/v1/engine/engine.py`

**Use `%`-style for new code (converter style preferred):**
```python
logger.info("Parsed job '%s' with %d nodes", job.job_name, len(job.nodes))
```

## Comments

**When to Comment:**
- Section separators for logical groups within a class: `# ---- 1. Core parameters ----`
- ASCII art dividers between method groups: `# ------------------------------------------------------------------`
- Inline comments for non-obvious logic: `# Skip tLibraryLoad -- libraries are extracted separately`
- Config mapping headers at top of converter modules (docstring at file level)

**Docstrings:**
- Converter module: One-line or reStructuredText-style docstrings with `Parameters` / `Returns` sections
- Engine module: Google-style docstrings with `Args:` / `Returns:` / `Raises:` sections
- All classes and public methods should have docstrings
- Use triple double-quotes: `"""Docstring."""`

**Config Mapping Comment Block (converter pattern):**
```python
"""Converter for Talend tFilterRow component.

Config mapping (4 params + framework):
  LOGICAL_OP    -> logical_op    (str, CLOSED_LIST, default "AND")
  CONDITIONS    -> conditions    (list of dicts, stride-4 TABLE)
  ...
  --- framework ---
  TSTATCATCHER_STATS -> tstatcatcher_stats (bool, default False)
  LABEL              -> label              (str, default "")

Phantom params REMOVED: DIE_ON_ERROR (not in _java.xml)
"""
```

## Function Design

**Size:**
- Methods average 20-50 lines; larger methods (like `_process()`) can reach 100+ lines
- Static helper methods are preferred over free functions

**Parameters:**
- Use `self` methods for core logic, `@staticmethod` for pure utilities
- Node data passed as typed dataclass (`TalendNode`) not raw dicts
- Default parameter values provided via helper methods: `_get_str(node, "NAME", "default")`

**Return Values:**
- Converter `convert()` returns `ComponentResult` dataclass (component dict + warnings + needs_review)
- Engine `_process()` returns `Dict[str, Any]` with keys `'main'`, `'reject'`, `'stats'`
- Engine `execute()` returns execution statistics dict

## Module Design

**Exports:**
- `__init__.py` files import and re-export public classes
- `__all__` lists used in engine component packages: `src/v1/engine/components/transform/__init__.py`
- Converter components use decorator-based auto-registration (no `__all__` needed)

**Registration Patterns:**

Converter module uses decorator-based registry:
```python
@REGISTRY.register("tFilterRow")
@REGISTRY.register("tFilterRows")
class FilterRowsConverter(ComponentConverter):
    ...
```

Engine module uses explicit dict-based registry:
```python
COMPONENT_REGISTRY = {
    'FileInputDelimited': FileInputDelimited,
    'tFileInputDelimited': FileInputDelimited,
    ...
}
```

**Barrel Files:**
- `src/converters/talend_to_v1/components/__init__.py` imports all sub-packages to trigger auto-registration
- `src/v1/engine/components/transform/__init__.py` imports all component classes with `__all__`
- `src/v1/engine/__init__.py` exports only `ETLEngine`

## Dataclass Usage

Use `@dataclass` for structured data objects. Apply `field(default_factory=...)` for mutable defaults:

```python
@dataclass
class TalendNode:
    component_id: str
    component_type: str
    params: Dict[str, Any] = field(default_factory=dict)
    schema: Dict[str, List[SchemaColumn]] = field(default_factory=dict)
    position: Dict[str, int] = field(default_factory=lambda: {"x": 0, "y": 0})
    raw_xml: Optional[Element] = None
```

## Constants

Use `frozenset` for immutable constant sets:
```python
_FLOW_CONNECTOR_TYPES = frozenset({
    "FLOW", "MAIN", "REJECT", "FILTER",
    "UNIQUE", "DUPLICATE", "ITERATE",
})
```

Use plain `dict` for mapping constants:
```python
TALEND_TO_PYTHON = {
    "id_String": "str",
    "id_Integer": "int",
    ...
}
```

---

*Convention analysis: 2026-04-14*
