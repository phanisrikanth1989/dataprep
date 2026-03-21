# V1 Engine Standards & Guidelines

Comprehensive standards for logging, error handling, naming conventions, and code structure in the v1 (Talend-compatible) engine.

## Table of Contents

1. [Overview](#overview)
2. [File & Module Organization](#file--module-organization)
3. [Naming Conventions](#naming-conventions)
4. [Logging Standards](#logging-standards)
5. [Error Handling](#error-handling)
6. [Component Structure](#component-structure)
7. [Documentation Standards](#documentation-standards)
8. [Checklist for New Components](#checklist-for-new-components)
9. [Converter Standards](#converter-standards)

---

## Overview

The v1 engine is designed for Talend job compatibility, supporting:
- Java routine execution via Py4J bridge
- Talend-style global variables and triggers
- Component statistics tracking (NB_LINE, NB_LINE_OK, etc.)
- Context variable resolution

All code changes should maintain backward compatibility with existing Talend job configurations.

---

## File & Module Organization

### Directory Structure

```
src/v1/
├── engine/
│   ├── engine.py                    # Main ETL orchestrator
│   ├── base_component.py            # Abstract base component
│   ├── base_iterate_component.py    # Base for iteration components
│   ├── context_manager.py           # Context variable management
│   ├── global_map.py                # Global variable storage
│   ├── trigger_manager.py           # Trigger execution (OnSubjobOk, etc.)
│   ├── java_bridge_manager.py       # Java bridge lifecycle
│   ├── python_routine_manager.py    # Python routine management
│   └── components/
│       ├── aggregate/               # Aggregation components
│       │   ├── __init__.py
│       │   ├── aggregate_row.py     # tAggregateRow
│       │   └── unique_row.py        # tUniqRow
│       ├── context/                 # Context components
│       │   ├── __init__.py
│       │   └── context_load.py      # tContextLoad
│       ├── control/                 # Control flow components
│       │   ├── __init__.py
│       │   ├── die.py               # tDie
│       │   └── warn.py              # tWarn
│       ├── database/                # Database components
│       │   ├── __init__.py
│       │   └── oracle_input.py      # tOracleInput
│       ├── file/                    # File I/O components
│       │   ├── __init__.py
│       │   ├── file_input_delimited.py
│       │   ├── file_input_excel.py
│       │   ├── file_input_positional.py
│       │   └── file_output_delimited.py
│       └── transform/               # Transform components
│           ├── __init__.py
│           ├── map.py               # tMap
│           ├── filter_rows.py       # tFilterRows
│           ├── filter_columns.py    # tFilterColumns
│           ├── sort_row.py          # tSortRow
│           ├── unite.py             # tUnite
│           ├── java_component.py    # tJava
│           ├── java_row_component.py
│           ├── python_component.py  # tPython
│           ├── python_row_component.py
│           └── python_dataframe_component.py
├── java_bridge/
│   ├── __init__.py
│   ├── bridge.py                    # Py4J bridge implementation
│   └── java/                        # Java source files
│       ├── pom.xml
│       └── src/main/java/
│           ├── com/citi/gru/etl/
│           │   ├── JavaBridge.java
│           │   └── RowWrapper.java
│           └── routines/            # Java routines
└── __init__.py
```

### File Naming Rules

| Category | Pattern | Example |
|----------|---------|---------|
| Component files | `snake_case.py` | `file_input_delimited.py` |
| Manager files | `*_manager.py` | `context_manager.py`, `trigger_manager.py` |
| Base classes | `base_*.py` | `base_component.py` |
| Bridge files | Descriptive | `bridge.py` |

### Class to File Mapping

| Talend Component | File Name | Class Name |
|------------------|-----------|------------|
| tFileInputDelimited | `file_input_delimited.py` | `FileInputDelimited` |
| tMap | `map.py` | `Map` |
| tFilterRows | `filter_rows.py` | `FilterRows` |
| tAggregateRow | `aggregate_row.py` | `AggregateRow` |
| tDie | `die.py` | `Die` |

**Rule**: File name is `snake_case` version of Talend component name (without `t` prefix).

---

## Naming Conventions

### Variables

| Category | Convention | Examples |
|----------|------------|----------|
| Local variables | `snake_case` | `input_data`, `row_count`, `output_schema` |
| Instance attributes | `snake_case` | `self.config`, `self.global_map` |
| Private methods | `_snake_case` | `_process()`, `_update_stats()` |
| Constants | `UPPER_SNAKE_CASE` | `MEMORY_THRESHOLD_MB`, `DEFAULT_ENCODING` |
| Class names | `PascalCase` | `FileInputDelimited`, `BaseComponent` |

### Standard Variable Names

Use these exact names for consistency across components:

```python
# Component identification
component_id      # NOT: comp_id, id, component_name
self.id           # Instance attribute for component ID

# Data handling
input_data        # Input DataFrame (singular)
input_dfs         # Multiple input DataFrames (dict)
result_df         # Result DataFrame
output_dfs        # Output dictionary {'main': df, 'reject': df}

# Configuration
config            # Component configuration dict
schema            # Schema definition list
column_name       # Single column name
column_names      # List of column names

# Statistics
rows_in           # Rows received
rows_out          # Rows output
rows_rejected     # Rows rejected
stats             # Statistics dictionary

# Context
context_vars      # Context variables dictionary
global_map        # Global map instance
context_manager   # Context manager instance
```

### Talend-Compatible Names

These names must be preserved for Talend compatibility:

```python
# Statistics keys (Talend standard)
'NB_LINE'           # Total rows processed
'NB_LINE_OK'        # Successful rows
'NB_LINE_REJECT'    # Rejected rows
'NB_LINE_INSERT'    # Inserted rows
'NB_LINE_UPDATE'    # Updated rows
'NB_LINE_DELETE'    # Deleted rows

# Type identifiers (Talend schema)
'id_String'
'id_Integer'
'id_Long'
'id_Float'
'id_Double'
'id_Boolean'
'id_Date'
'id_BigDecimal'

# Global map key pattern
f"{component_id}_NB_LINE"
f"{component_id}_NB_LINE_OK"
```

### Prefixes and Suffixes

| Prefix/Suffix | Usage | Example |
|---------------|-------|---------|
| `_` prefix | Private method/attribute | `_process()`, `_validate_config()` |
| `__` prefix | Name mangling (avoid) | Not recommended |
| `_df` suffix | DataFrame variable | `result_df`, `joined_df` |
| `_config` suffix | Configuration dict | `lookup_config`, `output_config` |
| `_manager` suffix | Manager classes | `ContextManager`, `TriggerManager` |
| `_temp_` prefix | Temporary columns | `_temp_join_key` |
| `_join_` prefix | Join-related columns | `_join_lookup_0` |

---

## Logging Standards

### Logger Setup

Every module must initialize a logger at module level:

```python
import logging

logger = logging.getLogger(__name__)
```

### Log Levels

| Level | Use Case | Example |
|-------|----------|---------|
| `DEBUG` | Detailed flow, variable values | Expression evaluation, join details |
| `INFO` | Key milestones, statistics | Component start/end, rows processed |
| `WARNING` | Recoverable issues | Missing optional column, empty lookup |
| `ERROR` | Failures requiring attention | Invalid config, file not found |
| `CRITICAL` | Fatal errors (rarely used) | System-level failures |

### Log Message Format

**Standard format for component logs:**

```python
# Pattern: [ComponentID] Action: Details
logger.info(f"[{self.id}] Processing started: {len(input_data)} rows")
logger.info(f"[{self.id}] Processing complete: {rows_out} rows output, {rows_rejected} rejected")
logger.warning(f"[{self.id}] Column not found: {column_name}, using default")
logger.error(f"[{self.id}] Processing failed: {str(e)}")
```

**Standard format for engine logs:**

```python
# Pattern: Action: Details
logger.info(f"Executing component: {component_id}")
logger.info(f"Job completed: {job_name} in {duration:.2f}s")
logger.error(f"Job failed: {str(e)}")
```

### Logging Examples by Category

**Component Lifecycle:**
```python
# Start
logger.info(f"[{self.id}] Processing started: {len(input_data)} rows")

# Progress (for long operations)
logger.debug(f"[{self.id}] Processed batch {batch_num}: {batch_rows} rows")

# Completion
logger.info(f"[{self.id}] Processing complete: "
            f"in={rows_in}, out={rows_out}, rejected={rows_rejected}")
```

**File Operations:**
```python
logger.info(f"[{self.id}] Reading file: {filepath}")
logger.info(f"[{self.id}] Read complete: {row_count} rows from {filepath}")
logger.warning(f"[{self.id}] File not found: {filepath}, returning empty result")
logger.error(f"[{self.id}] Failed to read file: {filepath}: {str(e)}")
```

**Data Transformations:**
```python
logger.debug(f"[{self.id}] Evaluating expression: {expression}")
logger.info(f"[{self.id}] Filter applied: {accepted} accepted, {rejected} rejected")
logger.info(f"[{self.id}] Aggregated {input_rows} rows into {output_rows} groups")
```

**Java Bridge:**
```python
logger.info(f"[{self.id}] Calling Java routine: {routine_name}")
logger.debug(f"[{self.id}] Java result: {result}")
logger.error(f"[{self.id}] Java execution failed: {str(e)}")
```

### What NOT to Log

```python
# DON'T: Use print statements
print(f"Processing {row_count} rows")  # BAD

# DON'T: Log sensitive data
logger.info(f"Password: {password}")  # BAD

# DON'T: Log entire DataFrames
logger.debug(f"Data: {df}")  # BAD - use df.shape or df.head()

# DON'T: Log without context
logger.error("Error occurred")  # BAD - no component ID or details
```

### Logging Configuration

Root logger should be configured once in engine.py:

```python
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
```

---

## Error Handling

### Exception Hierarchy

Define and use these custom exceptions (to be added to `src/v1/engine/exceptions.py`):

```python
class ETLError(Exception):
    """Base exception for all ETL errors."""
    pass


class ConfigurationError(ETLError):
    """Invalid or missing configuration."""
    pass


class DataValidationError(ETLError):
    """Data validation failure."""
    pass


class ComponentExecutionError(ETLError):
    """Component execution failure."""
    def __init__(self, component_id: str, message: str, cause: Exception = None):
        self.component_id = component_id
        self.cause = cause
        super().__init__(f"[{component_id}] {message}")


class FileOperationError(ETLError):
    """File read/write operation failure."""
    pass


class JavaBridgeError(ETLError):
    """Java bridge communication or execution failure."""
    pass


class ExpressionError(ETLError):
    """Expression parsing or evaluation failure."""
    pass


class SchemaError(ETLError):
    """Schema validation or mismatch error."""
    pass
```

### Error Handling Patterns

**Pattern 1: Component Processing with Graceful Degradation**

```python
def _process(self, input_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
    """Process input data."""
    die_on_error = self.config.get('die_on_error', True)

    try:
        # Validate input
        if input_data is None or input_data.empty:
            logger.warning(f"[{self.id}] Empty input received")
            self._update_stats(0, 0, 0)
            return {'main': pd.DataFrame()}

        rows_in = len(input_data)

        # Core processing logic
        result_df = self._do_processing(input_data)

        rows_out = len(result_df)
        self._update_stats(rows_in, rows_out, 0)
        logger.info(f"[{self.id}] Processing complete: "
                   f"in={rows_in}, out={rows_out}")

        return {'main': result_df}

    except FileNotFoundError as e:
        if die_on_error:
            logger.error(f"[{self.id}] File not found: {e}")
            raise FileOperationError(f"[{self.id}] {e}") from e
        else:
            logger.warning(f"[{self.id}] File not found: {e}, returning empty")
            self._update_stats(0, 0, 0)
            return {'main': pd.DataFrame()}

    except Exception as e:
        logger.error(f"[{self.id}] Processing failed: {e}")
        raise ComponentExecutionError(self.id, str(e), e) from e
```

**Pattern 2: Configuration Validation**

```python
def _validate_config(self) -> List[str]:
    """Validate component configuration.

    Returns:
        List of error messages (empty if valid)
    """
    errors = []

    # Required fields
    if 'path' not in self.config:
        errors.append("Missing required config: 'path'")

    if 'schema' not in self.config:
        errors.append("Missing required config: 'schema'")
    elif not isinstance(self.config['schema'], list):
        errors.append("Config 'schema' must be a list")
    elif len(self.config['schema']) == 0:
        errors.append("Config 'schema' cannot be empty")

    # Optional field validation
    if 'delimiter' in self.config:
        delimiter = self.config['delimiter']
        if not isinstance(delimiter, str) or len(delimiter) != 1:
            errors.append("Config 'delimiter' must be a single character")

    return errors
```

**Pattern 3: Java Bridge Error Handling**

```python
def _call_java_routine(self, routine_name: str, *args) -> Any:
    """Call a Java routine with error handling."""
    try:
        logger.debug(f"[{self.id}] Calling Java routine: {routine_name}")
        result = self.java_bridge.call_routine(routine_name, *args)
        logger.debug(f"[{self.id}] Java routine returned: {type(result)}")
        return result

    except Py4JNetworkError as e:
        logger.error(f"[{self.id}] Java bridge connection lost: {e}")
        raise JavaBridgeError(f"Connection to Java bridge lost: {e}") from e

    except Py4JJavaError as e:
        logger.error(f"[{self.id}] Java execution error: {e}")
        raise JavaBridgeError(f"Java routine '{routine_name}' failed: {e}") from e

    except Exception as e:
        logger.error(f"[{self.id}] Unexpected error calling Java: {e}")
        raise JavaBridgeError(f"Failed to call '{routine_name}': {e}") from e
```

### Error Message Guidelines

**Good Error Messages:**
```python
# Include context
raise ConfigurationError(
    f"[{self.id}] Invalid schema: column '{col_name}' has unknown type '{col_type}'. "
    f"Valid types: {', '.join(VALID_TYPES)}"
)

# Include what was expected vs actual
raise DataValidationError(
    f"[{self.id}] Schema mismatch: expected {len(expected_cols)} columns, "
    f"got {len(actual_cols)}. Missing: {missing_cols}"
)

# Include recovery suggestion
raise FileOperationError(
    f"[{self.id}] Cannot read file: {filepath}. "
    f"Check that file exists and has read permissions."
)
```

**Bad Error Messages:**
```python
raise Exception("Error")  # No context
raise RuntimeError(str(e))  # Just re-wrapping
raise ValueError("Invalid")  # No specifics
```

---

## Component Structure

### Standard Component Template

```python
"""
ComponentName - Brief description of what this component does.

Talend equivalent: tComponentName
"""
import logging
from typing import Any, Dict, List, Optional

import pandas as pd

from ..base_component import BaseComponent

logger = logging.getLogger(__name__)


class ComponentName(BaseComponent):
    """
    Detailed description of the component.

    Configuration:
        required_param (type): Description of required parameter
        optional_param (type): Description with default value. Default: X

    Inputs:
        main: Primary input DataFrame

    Outputs:
        main: Primary output DataFrame
        reject: Rejected rows (if applicable)

    Statistics:
        NB_LINE: Total rows processed
        NB_LINE_OK: Successful rows
        NB_LINE_REJECT: Rejected rows

    Example configuration:
        {
            "required_param": "value",
            "optional_param": 123
        }
    """

    # Class constants
    DEFAULT_VALUE = 100
    VALID_OPTIONS = ['option1', 'option2', 'option3']

    def _validate_config(self) -> List[str]:
        """Validate component configuration."""
        errors = []

        # Validate required fields
        if 'required_param' not in self.config:
            errors.append("Missing required config: 'required_param'")

        # Validate optional fields if present
        if 'optional_param' in self.config:
            value = self.config['optional_param']
            if not isinstance(value, int) or value < 0:
                errors.append("Config 'optional_param' must be a non-negative integer")

        return errors

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """
        Process input data.

        Args:
            input_data: Input DataFrame (may be None or empty)

        Returns:
            Dictionary with output DataFrames and optional stats
        """
        # Handle empty input
        if input_data is None or input_data.empty:
            logger.warning(f"[{self.id}] Empty input received")
            self._update_stats(0, 0, 0)
            return {'main': pd.DataFrame()}

        rows_in = len(input_data)
        logger.info(f"[{self.id}] Processing started: {rows_in} rows")

        try:
            # Get configuration with defaults
            optional_value = self.config.get('optional_param', self.DEFAULT_VALUE)

            # Core processing logic
            result_df = self._do_processing(input_data, optional_value)

            # Calculate statistics
            rows_out = len(result_df)
            rows_rejected = rows_in - rows_out

            # Update stats and log
            self._update_stats(rows_in, rows_out, rows_rejected)
            logger.info(f"[{self.id}] Processing complete: "
                       f"in={rows_in}, out={rows_out}, rejected={rows_rejected}")

            return {'main': result_df}

        except Exception as e:
            logger.error(f"[{self.id}] Processing failed: {e}")
            raise

    def _do_processing(self, df: pd.DataFrame, param: int) -> pd.DataFrame:
        """
        Internal processing logic.

        Args:
            df: Input DataFrame
            param: Processing parameter

        Returns:
            Processed DataFrame
        """
        # Implementation here
        return df
```

### Method Organization Order

1. **Class constants** (UPPER_SNAKE_CASE)
2. **`_validate_config()`** - Configuration validation
3. **`_process()`** - Main processing method (required)
4. **`execute()`** - Only if overriding base behavior
5. **Private helper methods** - `_do_*()`, `_parse_*()`, `_validate_*()`

### Import Order

```python
# 1. Standard library
import logging
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

# 2. Third-party
import pandas as pd
import numpy as np

# 3. Project imports (relative)
from ..base_component import BaseComponent
from ..global_map import GlobalMap
from ...java_bridge import JavaBridge

# 4. Logger initialization
logger = logging.getLogger(__name__)
```

---

## Documentation Standards

### Module Docstring

```python
"""
ComponentName - Brief one-line description.

Talend equivalent: tComponentName

This component does X by processing Y and outputting Z.
Supports features A, B, and C.
"""
```

### Class Docstring

```python
class ComponentName(BaseComponent):
    """
    Detailed description of the component's purpose and behavior.

    Configuration:
        param1 (str): Description. Required.
        param2 (int): Description. Default: 10
        param3 (bool): Description. Default: False

    Inputs:
        main: Description of main input
        lookup: Description of lookup input (if applicable)

    Outputs:
        main: Description of main output
        reject: Description of reject output (if applicable)

    Statistics:
        NB_LINE: Total rows processed
        NB_LINE_OK: Rows successfully processed
        NB_LINE_REJECT: Rows rejected

    Example:
        config = {
            "param1": "value",
            "param2": 20
        }
        component = ComponentName("comp_1", config)
        result = component.execute(input_df)

    Notes:
        - Special behavior note 1
        - Special behavior note 2
    """
```

### Method Docstring

```python
def _process(self, input_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
    """
    Process input data and produce output.

    Applies transformation X to the input DataFrame, filtering rows
    based on condition Y and computing column Z.

    Args:
        input_data: Input DataFrame. If None or empty, returns empty result.

    Returns:
        Dictionary containing:
            - 'main': Processed DataFrame with columns [a, b, c]
            - 'reject': Rejected rows (if reject_output enabled)
            - 'stats': Execution statistics

    Raises:
        ConfigurationError: If required configuration is missing
        DataValidationError: If input schema doesn't match expected

    Example:
        result = self._process(input_df)
        output_df = result['main']
    """
```

---

## Checklist for New Components

### Before Starting

- [ ] Identify Talend component equivalent
- [ ] Determine file location (which subdirectory)
- [ ] Review similar existing components for patterns
- [ ] List required and optional configuration parameters

### Implementation

- [ ] Create file with correct naming (`snake_case.py`)
- [ ] Add module docstring with Talend equivalent
- [ ] Import dependencies in correct order
- [ ] Initialize module-level logger
- [ ] Create class with `PascalCase` name
- [ ] Add comprehensive class docstring
- [ ] Implement `_validate_config()` for all required params
- [ ] Implement `_process()` with standard patterns:
  - [ ] Handle empty input gracefully
  - [ ] Log start with input row count
  - [ ] Get config values with defaults
  - [ ] Core processing in try-except
  - [ ] Update stats before return
  - [ ] Log completion with statistics
- [ ] Add helper methods with `_` prefix

### Logging & Errors

- [ ] Use `logger.info()` for start/complete messages
- [ ] Use `logger.debug()` for detailed flow
- [ ] Use `logger.warning()` for recoverable issues
- [ ] Use `logger.error()` for failures
- [ ] All log messages include `[{self.id}]` prefix
- [ ] Raise appropriate custom exceptions
- [ ] Error messages include context and suggestions

### Testing (separate file)

- [ ] Test with valid input
- [ ] Test with empty input
- [ ] Test with None input
- [ ] Test configuration validation
- [ ] Test error conditions
- [ ] Test statistics tracking

### Documentation

- [ ] Module docstring complete
- [ ] Class docstring with all sections
- [ ] Method docstrings for public methods
- [ ] Configuration parameters documented
- [ ] Example configuration provided

### Final Review

- [ ] All variable names follow conventions
- [ ] No `print()` statements
- [ ] No hardcoded magic values (use constants)
- [ ] Type hints on all methods
- [ ] Consistent with existing components

---

## Converter Standards

Standards for the Talend XML to JSON converter (`src/converters/complex_converter/`).

### File Organization

```
src/converters/complex_converter/
├── __init__.py                  # Package exports
├── converter.py                 # Main converter class (ComplexTalendConverter)
├── component_parser.py          # Component-specific parsing (ComponentParser)
└── expression_converter.py      # Expression conversion utilities (ExpressionConverter)
```

**Responsibilities:**

| File | Responsibility |
|------|---------------|
| `converter.py` | XML parsing, flow/trigger extraction, subjob detection, orchestration |
| `component_parser.py` | Component-specific config parsing, parameter mapping, schema extraction |
| `expression_converter.py` | Java→Python expression conversion, type mapping, Java detection |

### Naming Conventions

#### Talend Parameter Names → Python Config Keys

**CRITICAL**: Use consistent `snake_case` for all Python config keys. Never use `camelCase` or `UPPER_CASE` for output JSON.

| Talend XML Parameter | Python Config Key | Notes |
|----------------------|-------------------|-------|
| `FILENAME` | `filepath` | File path for input/output |
| `FIELDSEPARATOR` | `delimiter` | Field delimiter |
| `ROWSEPARATOR` | `row_separator` | Row separator |
| `HEADER` | `header_rows` | Number of header rows (int) |
| `FOOTER` | `footer_rows` | Number of footer rows (int) |
| `ENCODING` | `encoding` | File encoding |
| `TEXT_ENCLOSURE` | `text_enclosure` | Quote character |
| `ESCAPE_CHAR` | `escape_char` | Escape character |
| `INCLUDEHEADER` | `include_header` | Include header in output (bool) |
| `DIE_ON_ERROR` | `die_on_error` | Fail on error (bool) |
| `REMOVE_EMPTY_ROW` | `remove_empty_rows` | Remove empty rows (bool) |
| `TRIMALL` | `trim_all` | Trim all fields (bool) |
| `CASE_SENSITIVE` | `case_sensitive` | Case sensitivity (bool) |
| `UNIQUE_KEY` | `key_columns` | Key columns for uniqueness |
| `GROUPBYS` | `group_by` | Group by columns |
| `OPERATIONS` | `operations` | Aggregate operations |
| `CONDITIONS` | `conditions` | Filter conditions |
| `LOGICAL_OP` | `logical_operator` | Logical operator (AND/OR) |
| `CRITERIA` | `sort_columns` | Sort columns |

#### Type Mapping (Talend → Python)

**Standard type mapping** - use `ExpressionConverter.convert_type()`:

| Talend Type | Python Type | JSON Output |
|-------------|-------------|-------------|
| `id_String` | `str` | `"str"` |
| `id_Integer` | `int` | `"int"` |
| `id_Long` | `int` | `"int"` |
| `id_Float` | `float` | `"float"` |
| `id_Double` | `float` | `"float"` |
| `id_Boolean` | `bool` | `"bool"` |
| `id_Date` | `datetime` | `"datetime"` |
| `id_BigDecimal` | `Decimal` | `"Decimal"` |
| `id_Object` | `object` | `"object"` |
| `id_Character` | `str` | `"str"` |
| `id_Byte` | `int` | `"int"` |
| `id_Short` | `int` | `"int"` |

**In schema definitions**, use Talend type format (`id_String`, `id_Integer`, etc.):

```python
# CORRECT: Use Talend type format - v1 engine converts internally
column = {
    'name': col_name,
    'type': 'id_String'  # Talend type format
}

# INCORRECT: Don't use Python types in schema
column = {
    'name': col_name,
    'type': 'str'  # Wrong! Use id_String
}
```

The v1 engine maps these types internally (e.g., `id_String` → `object`, `id_Integer` → `Int64`).

#### Component Type Mapping

**Standard mapping** - defined in `ComponentParser.component_mapping`:

| Talend Component | Python Class Name | Notes |
|------------------|-------------------|-------|
| `tFileInputDelimited` | `FileInputDelimited` | Remove `t` prefix, PascalCase |
| `tFileOutputDelimited` | `FileOutputDelimited` | |
| `tMap` | `Map` | |
| `tFilterRow` | `FilterRows` | Note: Singular→Plural |
| `tFilterRows` | `FilterRows` | Handle both forms |
| `tFilterColumns` | `FilterColumns` | |
| `tAggregateRow` | `AggregateRow` | |
| `tUniqueRow` | `UniqueRow` | |
| `tSortRow` | `SortRow` | |
| `tUnite` | `Unite` | |
| `tJavaRow` | `JavaRowComponent` | Special: Add `Component` suffix |
| `tJava` | `JavaComponent` | Special: Add `Component` suffix |
| `tContextLoad` | `ContextLoad` | |
| `tWarn` | `Warn` | |
| `tDie` | `Die` | |

### JSON Output Structure

#### Standard Component Structure

Every component in the output JSON must have this structure:

```json
{
  "id": "unique_component_id",
  "type": "PythonClassName",
  "original_type": "tTalendName",
  "position": {"x": 100, "y": 200},
  "config": {
    "param1": "value1",
    "param2": 123
  },
  "schema": {
    "input": [...],
    "output": [...],
    "reject": [...]
  },
  "inputs": ["flow_name_1"],
  "outputs": ["flow_name_2"],
  "subjob_id": "subjob_1",
  "is_subjob_start": true
}
```

**Required fields:**
- `id` - Unique component identifier (from `UNIQUE_NAME` parameter)
- `type` - Mapped Python class name
- `original_type` - Original Talend component name (for debugging)
- `config` - Component-specific configuration
- `schema` - Input/output column schemas
- `inputs` - List of input flow names
- `outputs` - List of output flow names

#### Standard Flow Structure

```json
{
  "name": "flow_unique_name",
  "from": "source_component_id",
  "to": "target_component_id",
  "type": "flow"
}
```

**Flow types** (lowercase):
- `flow` - Standard data flow
- `main` - Main output flow
- `reject` - Reject output flow
- `filter` - Filter output flow
- `iterate` - Iteration flow

#### Standard Trigger Structure

```json
{
  "type": "OnSubjobOk",
  "from": "source_component_id",
  "to": "target_component_id",
  "condition": "optional_condition_expression"
}
```

**Trigger type mapping:**

| Talend Trigger | JSON Type |
|----------------|-----------|
| `SUBJOB_OK` | `OnSubjobOk` |
| `SUBJOB_ERROR` | `OnSubjobError` |
| `COMPONENT_OK` | `OnComponentOk` |
| `COMPONENT_ERROR` | `OnComponentError` |
| `RUN_IF` | `RunIf` |

### Expression Handling Standards

#### Java Expression Detection

Use `ExpressionConverter.detect_java_expression()` to identify expressions requiring Java execution:

**Patterns that trigger Java execution:**

| Pattern | Example | Why Java |
|---------|---------|----------|
| Routine calls | `routines.StringUtils.clean(x)` | Java routine |
| Static method calls | `ValidationUtils.validate(x)` | Java class |
| Method calls | `value.substring(0, 5)` | Java method |
| Unary operators | `!flag`, `++count` | Java syntax |
| Type casting | `(String)value` | Java cast |
| Ternary operator | `x > 0 ? "yes" : "no"` | Java ternary |
| GlobalMap access | `globalMap.get("key")` | Java GlobalMap |
| String concatenation | `"hello" + name` | Java concat |

**Patterns that DON'T trigger Java (handled by Python/ContextManager):**

| Pattern | Example | Why Not Java |
|---------|---------|--------------|
| Context reference | `${context.var}` | ContextManager handles |
| File paths | `/data/input.csv` | Literal path |
| URLs | `https://example.com` | Literal URL |
| Encodings | `UTF-8`, `ISO-8859-1` | Literal identifier |
| Negative numbers | `-5`, `-3.14` | Literal number |

#### Java Expression Marking

**CRITICAL**: All Java expressions must be prefixed with `{{java}}` marker:

```python
# CORRECT: Mark Java expressions
expression = "row1.name.toUpperCase()"
marked = f"{{{{java}}}}{expression}"  # "{{java}}row1.name.toUpperCase()"

# Use the helper method
from expression_converter import ExpressionConverter
marked = ExpressionConverter.mark_java_expression(expression)
```

**Where to apply marking:**

| Location | Apply Marking | Example |
|----------|---------------|---------|
| tMap column expressions | YES | `{{java}}row1.name` |
| tMap filter expressions | YES | `{{java}}row1.amount > 100` |
| tMap variable expressions | YES | `{{java}}row1.value * 2` |
| Filter conditions (RVALUE) | YES | `{{java}}context.threshold` |
| File paths | NO | `/data/file.csv` |
| Literal values | NO | `UTF-8`, `true`, `123` |

### Adding New Component Parsers

**CRITICAL**: Every component MUST have its own dedicated `parse_*` method. Do NOT use generic parameter mapping for "simple" components. This ensures:
- Consistent debugging experience across all 70-90 components
- Clear single place to look when a component has issues
- Easy to add component-specific logic later
- Self-documenting code structure

#### Step 1: Add Component Mapping

In `component_parser.py`, add to `component_mapping`:

```python
self.component_mapping = {
    # ... existing mappings ...
    'tNewComponent': 'NewComponent',  # Add new mapping
}
```

#### Step 2: Create Dedicated Parser Method

**Every component gets its own `parse_*` method** - no exceptions:

```python
def parse_new_component(self, node, component: Dict) -> Dict:
    """
    Parse tNewComponent specific configuration.

    Talend Parameters:
        PARAM_ONE (str): Description
        PARAM_TWO (int): Description, default 0
        FLAG (bool): Description, default False
        ITEMS (table): Nested items table
    """
    config = component['config']

    # === Simple parameters (from elementParameter) ===
    for param in node.findall('.//elementParameter'):
        name = param.get('name')
        value = param.get('value', '')
        field = param.get('field')

        # Strip quotes from string values
        if value.startswith('"') and value.endswith('"'):
            value = value[1:-1]

        if name == 'PARAM_ONE':
            config['param_one'] = value
        elif name == 'PARAM_TWO':
            config['param_two'] = int(value) if value.isdigit() else 0
        elif name == 'FLAG':
            config['flag'] = value.lower() == 'true' if field == 'CHECK' else False

    # === Nested table parameters ===
    items = []
    for param in node.findall('.//elementParameter[@name="ITEMS"]'):
        current_item = {}
        for item in param.findall('.//elementValue'):
            ref = item.get('elementRef')
            value = item.get('value', '')

            if ref == 'ITEM_NAME':
                # Save previous item if exists
                if 'name' in current_item:
                    items.append(current_item)
                    current_item = {}
                current_item['name'] = value
            elif ref == 'ITEM_VALUE':
                current_item['value'] = value

        # Don't forget the last item
        if 'name' in current_item:
            items.append(current_item)

    config['items'] = items

    return component
```

**Parameter parsing rules:**

1. **Always provide defaults** - Never let missing params cause KeyError
2. **Convert types explicitly** - Use `int()`, `bool()`, etc.
3. **Handle edge cases** - Check `.isdigit()` before `int()` conversion
4. **Strip quotes** - Remove surrounding quotes from string values
5. **Use snake_case** - All output keys must be snake_case
6. **Document Talend params** - List all expected Talend parameters in docstring

```python
# CORRECT: Safe integer conversion with default
config['count'] = int(value) if value.isdigit() else 0

# INCORRECT: Unsafe - will fail on empty string
config['count'] = int(value)
```

#### Step 3: Register Parser in Converter

In `converter.py`, add the parser call in `_parse_component()`:

```python
def _parse_component(self, node) -> Optional[Dict[str, Any]]:
    # ... existing code ...

    # Apply component-specific parsing
    if component_type == 'tMap':
        component = self.component_parser.parse_tmap(node, component)
    # ... existing cases ...
    elif component_type == 'tNewComponent':
        component = self.component_parser.parse_new_component(node, component)

    return component
```

### Method Organization Standards

#### In `converter.py`

```python
class ComplexTalendConverter:
    # 1. Constructor
    def __init__(self): ...

    # 2. Main public method
    def convert_file(self, filepath: str) -> Dict[str, Any]: ...

    # 3. Top-level parsing methods (called from convert_file)
    def _parse_context(self, root) -> Dict[str, Any]: ...
    def _parse_routines(self, root) -> List[str]: ...
    def _parse_libraries(self, root) -> List[str]: ...
    def _parse_component(self, node) -> Optional[Dict[str, Any]]: ...
    def _parse_flow(self, connection) -> Optional[Dict[str, Any]]: ...
    def _parse_trigger(self, connection) -> Optional[Dict[str, Any]]: ...

    # 4. Helper/utility methods
    def _update_component_connections(self, ...): ...
    def _detect_subjobs(self, ...): ...
    def _detect_java_requirement(self, ...): ...
    def _has_java_expressions(self, obj: Any) -> bool: ...

    # 5. Output method
    def save_json(self, job_config: Dict, output_path: str): ...
```

#### In `component_parser.py`

```python
class ComponentParser:
    # 1. Constructor with component_mapping
    def __init__(self): ...

    # 2. Base parser (extracts common fields: id, position, schema)
    def parse_base_component(self, node) -> Optional[Dict[str, Any]]: ...

    # 3. Component-specific parsers (EVERY component has one, alphabetical order)
    def parse_aggregate_row(self, node, component: Dict) -> Dict: ...
    def parse_context_load(self, node, component: Dict) -> Dict: ...
    def parse_die(self, node, component: Dict) -> Dict: ...
    def parse_file_input_delimited(self, node, component: Dict) -> Dict: ...
    def parse_file_input_excel(self, node, component: Dict) -> Dict: ...
    def parse_file_output_delimited(self, node, component: Dict) -> Dict: ...
    def parse_filter_columns(self, node, component: Dict) -> Dict: ...
    def parse_filter_rows(self, node, component: Dict) -> Dict: ...
    def parse_java(self, node, component: Dict) -> Dict: ...
    def parse_java_row(self, node, component: Dict) -> Dict: ...
    def parse_sort_row(self, node, component: Dict) -> Dict: ...
    def parse_tmap(self, node, component: Dict) -> Dict: ...
    def parse_unique_row(self, node, component: Dict) -> Dict: ...
    def parse_unite(self, node, component: Dict) -> Dict: ...
    def parse_warn(self, node, component: Dict) -> Dict: ...
    # ... add new components here in alphabetical order ...

    # 4. Helper methods (private)
    def _parse_table_parameter(self, node, param_name: str) -> List[Dict]: ...
    def _safe_int(self, value: str, default: int = 0) -> int: ...
    def _safe_bool(self, value: str, field: str) -> bool: ...
    def _strip_quotes(self, value: str) -> str: ...
```

**Note**: The deprecated `_map_component_parameters()` approach should be avoided. Each component must have its own `parse_*` method.

#### In `expression_converter.py`

```python
class ExpressionConverter:
    # All methods are @staticmethod (no instance state)

    # 1. Detection methods
    @staticmethod
    def detect_java_expression(value: str) -> bool: ...

    # 2. Transformation methods
    @staticmethod
    def mark_java_expression(value: str) -> str: ...

    @staticmethod
    def convert(expression: str) -> str: ...

    # 3. Type conversion
    @staticmethod
    def convert_type(talend_type: str) -> str: ...
```

### Checklist for New Converter Features

#### Adding a New Component

- [ ] Add to `component_mapping` dictionary in `component_parser.py`
- [ ] Create dedicated `parse_*` method (REQUIRED for ALL components)
  - [ ] Document all Talend parameters in docstring
  - [ ] Handle all simple parameters with safe conversions
  - [ ] Handle nested table parameters if applicable
  - [ ] Use snake_case for all output config keys
  - [ ] Use Talend type format (`id_String`) in schemas
- [ ] Register parser call in `converter.py._parse_component()`
- [ ] Test with sample Talend XML containing the component
- [ ] Verify JSON output matches expected structure
- [ ] Document any special handling in this standards file

#### Modifying Expression Handling

- [ ] Update `detect_java_expression()` if adding new patterns
- [ ] Update `convert()` if adding new Java→Python conversions
- [ ] Test with edge cases (paths, URLs, encodings)
- [ ] Ensure no false positives (literals marked as Java)
- [ ] Ensure no false negatives (Java expressions not marked)

#### Modifying Type Handling

- [ ] Update type mapping in `convert_type()`
- [ ] Update reverse mapping in `_python_type_to_java()` if needed
- [ ] Test with all Talend data types
- [ ] Verify schema output preserves original types where needed

### Common Mistakes to Avoid

```python
# WRONG: Using generic parameter mapping for components
def _map_component_parameters(self, component_type, config_raw):
    if component_type == 'tNewComponent':
        return {'param': config_raw.get('PARAM')}  # DON'T do this!

# CORRECT: Dedicated parse method for EVERY component
def parse_new_component(self, node, component):
    # Each component has its own method
    ...

# WRONG: Inconsistent case in output keys
config = {
    'fileName': value,      # camelCase - WRONG
    'FILEPATH': value,      # UPPER_CASE - WRONG
}

# CORRECT: Always snake_case
config = {
    'file_name': value,
    'filepath': value,
}

# WRONG: Not handling missing parameters
config['count'] = int(value)  # Will fail on empty string

# CORRECT: Safe conversion with default
config['count'] = int(value) if value.isdigit() else 0

# WRONG: Not marking Java expressions
expression = row1.value.toUpperCase()  # Will fail in Python

# CORRECT: Mark Java expressions
expression = "{{java}}row1.value.toUpperCase()"

# WRONG: Using Python types in schema
column = {'type': 'str'}  # Wrong format!

# CORRECT: Use Talend type format
column = {'type': 'id_String'}  # v1 engine converts internally

# WRONG: Not stripping quotes
value = param.get('value')  # Might be '"Hello"'

# CORRECT: Strip surrounding quotes
value = param.get('value', '')
if value.startswith('"') and value.endswith('"'):
    value = value[1:-1]
```
