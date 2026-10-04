# Component Development Guide

Complete guide for creating new components in the v2 engine, including naming conventions, coding standards, and best practices.

## Table of Contents

1. [Naming Conventions](#naming-conventions)
2. [File Structure](#file-structure)
3. [Component Architecture](#component-architecture)
4. [Creating a New Component](#creating-a-new-component)
5. [Configuration Standards](#configuration-standards)
6. [Testing Standards](#testing-standards)
7. [Documentation Standards](#documentation-standards)

---

## Naming Conventions

### File Names

| Type | Convention | Example |
|------|------------|---------|
| Component file | `{component_name}_component.py` or `{category}_{type}.py` | `map_component.py`, `file_input_delimited.py` |
| Test file | `test_{module_name}.py` | `test_transform_components.py` |
| Utility module | `{purpose}.py` | `schema_types.py` |

**Rules:**
- Use **snake_case** for all Python files
- Suffix component files with `_component.py` OR use descriptive names like `file_input_delimited.py`
- Group related components by category subdirectory

### Class Names

| Type | Convention | Example |
|------|------------|---------|
| Component class | `PascalCase` | `FileInputDelimited`, `Map`, `Filter` |
| Base class | `Base{Type}` or `{Type}Component` | `BaseComponent`, `SourceComponent` |
| Exception class | `{Description}Error` | `CompileError`, `ConfigError` |
| Enum class | `PascalCase` | `ComponentType`, `MatchMode`, `DataState` |

```python
# Good
class FileInputDelimited(SourceComponent):
class MatchMode(str, Enum):
class CompileError(Exception):

# Bad
class file_input_delimited(SourceComponent):  # Wrong: not PascalCase
class Match_Mode(str, Enum):                  # Wrong: underscore
class Compile_Err(Exception):                 # Wrong: abbreviated
```

### Variable Names

| Type | Convention | Example |
|------|------------|---------|
| Local variable | `snake_case` | `input_data`, `column_names` |
| Instance attribute | `snake_case` | `self.config`, `self._stats` |
| Private attribute | `_snake_case` | `self._compiled_code` |
| Constant | `UPPER_SNAKE_CASE` | `TYPE_MAPPING`, `DEFAULT_DELIMITER` |
| Class attribute | `snake_case` or `UPPER_SNAKE_CASE` | `spec`, `COMPONENT_TYPES` |

```python
# Good
TYPE_MAPPING = {...}           # Module-level constant
class MyComponent:
    spec = ComponentSpec(...)  # Class attribute

    def __init__(self):
        self.config = {}       # Public instance attribute
        self._cache = {}       # Private instance attribute

    def process(self):
        input_data = ...       # Local variable
        column_names = []      # Local variable

# Bad
typeMapping = {...}            # Wrong: camelCase
SPEC = ComponentSpec(...)      # Wrong: class attr should be lowercase
self.Config = {}               # Wrong: PascalCase
```

### Function & Method Names

| Type | Convention | Example |
|------|------------|---------|
| Public method | `snake_case` | `execute()`, `validate_config()` |
| Private method | `_snake_case` | `_apply_lookups()`, `_compile_node()` |
| Test function | `test_{description}` | `test_filter_basic()` |

```python
# Good
def validate_config(self) -> List[str]:
def _apply_match_mode(self, data, mode):
def test_map_with_lookup_basic():

# Bad
def ValidateConfig(self):      # Wrong: PascalCase
def applyMatchMode(self):      # Wrong: camelCase
def testMapBasic():            # Wrong: camelCase
```

### Config Parameter Names

| Type | Convention | Example |
|------|------------|---------|
| Config key | `snake_case` | `"header_rows"`, `"match_mode"` |
| Boolean config | `{verb}_{noun}` or descriptive | `"include_header"`, `"die_on_error"` |
| Path config | `{type}_path` or just `path` | `"path"`, `"output_path"` |

```json
{
    "path": "/data/input.csv",
    "delimiter": ",",
    "header_rows": 1,
    "include_header": true,
    "die_on_error": true,
    "match_mode": "first",
    "join_type": "left"
}
```

**Rules:**
- Always use `snake_case` for JSON config keys
- Use descriptive names (not abbreviated)
- Boolean keys should read naturally: `"include_header": true`

### Component Type Registry Names

| Convention | Example |
|------------|---------|
| `snake_case`, lowercase | `"file_input"`, `"file_input_delimited"` |
| Aliases for compatibility | `"file_input_csv"` → `FileInputDelimited` |

```python
COMPONENT_TYPES = {
    # Primary name
    'file_input_delimited': FileInputDelimited,
    # Aliases
    'file_input': FileInputDelimited,
    'file_input_csv': FileInputDelimited,
}
```

---

## File Structure

### Component Directory Layout

```
src/v2/components/
├── __init__.py                    # Export BaseComponent, ComponentOutput, etc.
├── base.py                        # Base classes and types
│
├── file/                          # File I/O components
│   ├── __init__.py
│   ├── schema_types.py            # Shared TYPE_MAPPING
│   ├── file_input_delimited.py    # CSV/TSV input
│   ├── file_input_excel.py        # Excel input
│   ├── file_output_delimited.py   # CSV/TSV output
│   └── file_output_parquet.py     # Parquet output
│
├── transform/                     # Transform components
│   ├── __init__.py
│   ├── map_component.py
│   ├── filter_component.py
│   ├── select_component.py
│   └── sort_component.py
│
├── aggregate/                     # Aggregation components
│   ├── __init__.py
│   ├── aggregate_component.py
│   └── unique_component.py
│
├── utility/                       # Utility components
│   ├── __init__.py
│   └── union_component.py
│
└── python/                        # Python code components
    ├── __init__.py
    ├── python_code.py
    ├── python_row.py
    └── python_dataframe.py
```

### Test Directory Layout

```
tests/v2/
├── conftest.py                    # Shared fixtures
├── __init__.py
│
├── unit/                          # Unit tests
│   ├── __init__.py
│   ├── test_expressions.py        # Tokenizer, parser, compiler
│   └── test_routines.py           # Routine manager tests
│
├── component/                     # Component tests
│   ├── __init__.py
│   ├── test_file_components.py    # FileInput/Output tests
│   ├── test_transform_components.py
│   ├── test_aggregate_components.py
│   └── test_python_components.py
│
└── integration/                   # Integration tests
    ├── __init__.py
    └── test_pipelines.py          # End-to-end pipeline tests
```

---

## Component Architecture

### Base Classes

```python
from v2.components.base import (
    BaseComponent,      # Abstract base for all components
    SourceComponent,    # Components that produce data (no inputs)
    SinkComponent,      # Components that consume data (no outputs)
    TransformComponent, # Components that transform data
)
```

### Component Types

```python
class ComponentType(Enum):
    SOURCE = "source"           # Produces data, no inputs
    SINK = "sink"               # Consumes data, no outputs
    STREAMING = "streaming"     # Row-by-row processing
    FULL_INPUT = "full_input"   # Needs all input (sort, aggregate)
    LOOKUP_JOIN = "lookup_join" # Needs lookup data first
```

### Component Specification

Every component must define a `spec`:

```python
class MyComponent(TransformComponent):
    spec = ComponentSpec(
        component_type=ComponentType.STREAMING,
        requires_full_input=False,
        supports_streaming=True,
        has_reject_output=False,
        input_names=["main"],
        output_names=["main"],
    )
```

---

## Creating a New Component

### Step 1: Create Component File

Create file in appropriate directory with proper naming:

```python
# src/v2/components/transform/limit_component.py
"""
Limit Component for v2 Engine.

Returns only the first N rows from input.
"""
import logging
from typing import Any, Dict, List, Union

import polars as pl

from ..base import (
    TransformComponent, ComponentSpec, ComponentType,
    ComponentOutput, ComponentStats, DataState
)

logger = logging.getLogger(__name__)
```

### Step 2: Define Class with Spec

```python
class Limit(TransformComponent):
    """
    Return only the first N rows from input.

    Config options:
        count: int - Maximum number of rows to return (required)

    Example config:
        {
            "count": 100
        }
    """

    spec = ComponentSpec(
        component_type=ComponentType.STREAMING,
        requires_full_input=False,
        supports_streaming=True,
        input_names=["main"],
        output_names=["main"],
    )
```

### Step 3: Implement validate_config()

```python
    def validate_config(self) -> List[str]:
        """Validate configuration."""
        errors = []

        # Check required fields
        if 'count' not in self.config:
            errors.append("Limit requires 'count' in config")
        elif not isinstance(self.config['count'], int):
            errors.append("Limit 'count' must be an integer")
        elif self.config['count'] < 0:
            errors.append("Limit 'count' must be non-negative")

        return errors
```

### Step 4: Implement execute()

```python
    def execute(
        self,
        inputs: Dict[str, Union[pl.LazyFrame, pl.DataFrame]],
    ) -> ComponentOutput:
        """Execute the limit operation."""
        # Get input data
        data = inputs.get("main")
        if data is None:
            raise ValueError(f"Limit {self.component_id}: Missing 'main' input")

        # Convert DataFrame to LazyFrame if needed
        if isinstance(data, pl.DataFrame):
            data = data.lazy()

        # Apply limit
        count = self.config['count']
        result = data.head(count)

        # Update statistics
        self._stats = ComponentStats(
            rows_in=0,  # Unknown until materialized
            rows_out=0,
        )

        logger.info(f"Limit {self.component_id}: Limited to {count} rows")

        return ComponentOutput(
            data={"main": result},
            stats=self._stats,
            state=DataState.LAZY,
        )
```

### Step 5: Export from Package

```python
# src/v2/components/transform/__init__.py
from .limit_component import Limit

__all__ = ['Map', 'Filter', 'Select', 'Sort', 'Limit']
```

### Step 6: Register in Engine

```python
# src/v2/engine.py
COMPONENT_TYPES: Dict[str, Type[BaseComponent]] = {
    # ... existing ...
    'limit': Limit,
    'head': Limit,  # Alias
}
```

### Step 7: Write Tests

```python
# tests/v2/component/test_transform_components.py
class TestLimit:
    """Test Limit component."""

    def test_limit_basic(self):
        """Test basic limit functionality."""
        component = Limit(
            component_id="limit_1",
            config={"count": 2},
        )

        df = pl.DataFrame({
            "id": [1, 2, 3, 4, 5],
            "name": ["a", "b", "c", "d", "e"],
        })

        result = component.execute({"main": df})
        output = result.data["main"].collect()

        assert len(output) == 2
        assert output["id"].to_list() == [1, 2]

    def test_limit_validation_missing_count(self):
        """Test validation catches missing count."""
        component = Limit(component_id="limit_1", config={})
        errors = component.validate_config()
        assert len(errors) == 1
        assert "count" in errors[0].lower()
```

---

## Configuration Standards

### Required vs Optional Config

```python
def validate_config(self) -> List[str]:
    errors = []

    # Required fields - raise error if missing
    if 'path' not in self.config:
        errors.append("FileInput requires 'path' in config")

    # Required with validation
    if 'schema' not in self.config:
        errors.append("FileInput requires 'schema' in config")
    elif not isinstance(self.config['schema'], list):
        errors.append("'schema' must be a list")

    return errors

def execute(self, inputs):
    # Optional fields - use defaults
    delimiter = self.config.get('delimiter', ',')
    header_rows = self.config.get('header_rows', 1)
    encoding = self.config.get('encoding', 'utf8')
```

### Config Key Naming

| Pattern | Use For | Example |
|---------|---------|---------|
| `{noun}` | Simple values | `"path"`, `"delimiter"` |
| `{noun}_{type}` | Type-specific | `"header_rows"`, `"column_names"` |
| `{verb}_{noun}` | Boolean flags | `"include_header"`, `"remove_empty_rows"` |
| `{noun}_on_{event}` | Error handling | `"die_on_error"` |

### Default Values

Document defaults in docstring and use sensible values:

```python
"""
Config options:
    delimiter: str - Field delimiter (default: ',')
    header_rows: int - Header rows to skip (default: 1)
    encoding: str - File encoding (default: 'utf8')
    include_header: bool - Write header row (default: True)
"""
```

---

## Testing Standards

### Test Class Naming

```python
class TestComponentName:
    """Test ComponentName component."""

class TestFeatureName:
    """Tests for feature name."""
```

### Test Method Naming

```python
def test_{component}_{scenario}():
def test_{component}_{scenario}_{expected_outcome}():
```

Examples:
```python
def test_filter_basic():
def test_filter_with_and_condition():
def test_filter_empty_result():
def test_filter_validation_missing_condition():
def test_map_match_mode_first():
def test_map_cartesian_join():
```

### Test Structure

```python
def test_component_scenario(self):
    """Clear description of what is being tested."""
    # Arrange - set up test data and component
    component = MyComponent(
        component_id="test_1",
        config={...},
    )

    input_df = pl.DataFrame({...})

    # Act - execute the component
    result = component.execute({"main": input_df})
    output = result.data["main"].collect()

    # Assert - verify results
    assert len(output) == expected_count
    assert output["column"].to_list() == expected_values
```

### Test Categories

1. **Basic functionality** - Happy path tests
2. **Edge cases** - Empty input, single row, large data
3. **Validation** - Missing config, invalid values
4. **Error handling** - Expected exceptions

```python
class TestFilter:
    # Basic functionality
    def test_filter_basic(self): ...
    def test_filter_with_string_comparison(self): ...

    # Edge cases
    def test_filter_empty_input(self): ...
    def test_filter_all_rows_match(self): ...
    def test_filter_no_rows_match(self): ...

    # Validation
    def test_filter_validation_missing_condition(self): ...
    def test_filter_validation_invalid_expression(self): ...

    # Multiple outputs
    def test_filter_with_reject_output(self): ...
```

---

## Documentation Standards

### Module Docstring

```python
"""
{ComponentName} Component for v2 Engine.

{Brief description of what the component does.}
"""
```

### Class Docstring

```python
class MyComponent(TransformComponent):
    """
    {One-line description}.

    {Detailed description if needed.}

    Config options:
        {option_name}: {type} - {description} (default: {value})
        {option_name}: {type} - {description} (required)

    Example config:
        {
            "option": "value"
        }
    """
```

### Method Docstring

```python
def execute(self, inputs: Dict[str, Union[pl.LazyFrame, pl.DataFrame]]) -> ComponentOutput:
    """Execute the component transformation.

    Args:
        inputs: Dictionary of input name to LazyFrame/DataFrame

    Returns:
        ComponentOutput with transformed data

    Raises:
        ValueError: If required input is missing
    """
```

---

## Component Checklist

When creating a new component, verify:

- [ ] File name follows convention: `{name}_component.py` or `{category}_{type}.py`
- [ ] Class name is PascalCase
- [ ] `spec` defined with correct `ComponentType`
- [ ] `input_names` and `output_names` set in spec
- [ ] `validate_config()` checks all required fields
- [ ] `execute()` (or `produce()`/`consume()`) implemented
- [ ] Handles both `DataFrame` and `LazyFrame` inputs
- [ ] Returns `LazyFrame` in output when possible
- [ ] Updates `ComponentStats` with row counts
- [ ] Logging added for debugging
- [ ] Exported from package `__init__.py`
- [ ] Registered via `@REGISTRY.register()` decorator
- [ ] Tests written for basic, edge cases, and validation
- [ ] Docstrings complete with config options
