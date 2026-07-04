# Component Implementation Guide

**Last Updated:** 2026-06-13

---

## Table of Contents

1. [Overview](#overview)
2. [When to Add a Component](#when-to-add-a-component)
3. [Component Types](#component-types)
4. [Step-by-Step: Adding an Engine Component](#step-by-step-adding-an-engine-component)
5. [BaseComponent Lifecycle](#basecomponent-lifecycle)
6. [Common Patterns](#common-patterns)
7. [Testing Your Component](#testing-your-component)
8. [Troubleshooting](#troubleshooting)

---

## Overview

This guide walks you through adding a new engine component to DataPrep. Engine components execute JSON job configurations and process data through pandas DataFrames.

**Key Concepts:**
- Components inherit from `BaseComponent` (standard) or `BaseIterateComponent` (loops)
- Must implement abstract `_process()` method
- Return dict with `main` (DataFrame), optional `reject`, `stats`
- Registered in `COMPONENT_REGISTRY` by name

---

## When to Add a Component

Add a new component when:
- A Talend component has no Python equivalent
- You need custom business logic
- Existing components don't support a feature

**Do NOT add if:**
- Similar component already exists (extend instead)
- Feature fits as configuration parameter
- Logic belongs in a helper/utility module

---

## Component Types

### 1. Standard Component (BaseComponent)

For components that process input data once:
- File I/O (read, write)
- Transformations (map, filter, sort)
- Aggregations (group, distinct)
- Context operations (load, pass)

**Example:** `FileInputDelimited`, `tFilter`, `AggregateRow`

### 2. Iterator Component (BaseIterateComponent)

For components with loops:
- File iteration (tFileList)
- Flow iteration (tFlowToIterate)
- Foreach loops (tForeach)

**Example:** `FileList`, `FlowToIterate`

### 3. Control Component (BaseComponent)

For flow control:
- Subjob execution
- Conditional logic
- Error handling
- Loop control

**Example:** `Subjob`, `Die`

---

## Step-by-Step: Adding an Engine Component

### **Step 1: Create the Component File**

Location: `src/v1/engine/components/{category}/{component_name}.py`

```python
from src.v1.engine.base_component import BaseComponent
from src.v1.engine.exceptions import ComponentExecutionError
import pandas as pd
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class MyComponent(BaseComponent):
    """
    Brief description of what this component does.
    
    Configuration:
        param1 (str): Description of param1
        param2 (int): Description of param2, default 100
        
    Input:
        Expects DataFrame with columns: col_a, col_b
        
    Output:
        main: Transformed DataFrame with new columns
        stats: Processing statistics
    """
    
    def __init__(self, component_id: str, config: Dict[str, Any]):
        """
        Initialize component.
        
        Args:
            component_id: Unique identifier from job config
            config: Component configuration dict
        """
        super().__init__(component_id, config)
        
        # Extract and validate config parameters
        self.param1 = self._get_str(config, "param1", "default_value")
        self.param2 = self._get_int(config, "param2", 100)
        
        logger.debug(f"[{self.id}] Initialized with param1={self.param1}, param2={self.param2}")
    
    def _process(self, input_data: Optional[pd.DataFrame]) -> Dict[str, Any]:
        """
        Process input data and return results.
        
        Args:
            input_data: Input DataFrame (may be None if no incoming connection)
            
        Returns:
            Dict with:
                'main': Processed DataFrame
                'reject': Rejected rows DataFrame (optional)
                'stats': Processing statistics dict
        """
        try:
            # Initialize output structures
            main_df = pd.DataFrame()
            reject_df = pd.DataFrame()
            stats = {
                'input_rows': 0,
                'output_rows': 0,
                'rejected_rows': 0
            }
            
            # Validate input
            if input_data is None:
                logger.warning(f"[{self.id}] No input data provided")
                return {'main': main_df, 'reject': reject_df, 'stats': stats}
            
            if len(input_data) == 0:
                logger.info(f"[{self.id}] Input is empty")
                return {'main': main_df, 'reject': reject_df, 'stats': stats}
            
            stats['input_rows'] = len(input_data)
            logger.info(f"[{self.id}] Processing {stats['input_rows']} rows")
            
            # YOUR PROCESSING LOGIC HERE
            # Example: simple transformation
            main_df = input_data.copy()
            main_df['new_column'] = main_df['col_a'].astype(str).str.upper()
            
            # Track stats
            stats['output_rows'] = len(main_df)
            stats['rejected_rows'] = len(reject_df)
            
            logger.info(f"[{self.id}] Completed: {stats['output_rows']} output, {stats['rejected_rows']} rejected")
            
            return {
                'main': main_df,
                'reject': reject_df,
                'stats': stats
            }
            
        except Exception as e:
            logger.error(f"[{self.id}] Processing failed: {str(e)}")
            raise ComponentExecutionError(
                component_id=self.id,
                message=f"Failed to process data: {str(e)}",
                cause=e
            )
```

### **Step 2: Register the Component**

Add to `src/v1/engine/components/component_registry.py`:

```python
COMPONENT_REGISTRY = {
    # ... existing entries ...
    
    # My Component category
    "MyComponent": "src.v1.engine.components.mycomponent:MyComponent",
    "tMyComponent": "src.v1.engine.components.mycomponent:MyComponent",  # Talend name alias
}
```

### **Step 3: Export in __init__.py**

Update `src/v1/engine/components/{category}/__init__.py`:

```python
from .my_component import MyComponent

__all__ = [
    "MyComponent",
    # ... other exports ...
]
```

### **Step 4: Create Unit Tests**

Location: `tests/v1/engine/components/{category}/test_my_component.py`

```python
import pytest
import pandas as pd
from src.v1.engine.components.mycomponent import MyComponent


class TestMyComponent:
    """Unit tests for MyComponent"""
    
    @pytest.fixture
    def sample_df(self):
        """Create sample input DataFrame"""
        return pd.DataFrame({
            'col_a': ['hello', 'world'],
            'col_b': [1, 2]
        })
    
    @pytest.fixture
    def component(self):
        """Create component instance"""
        config = {
            'param1': 'test_value',
            'param2': 50
        }
        return MyComponent('test_component', config)
    
    def test_basic_processing(self, component, sample_df):
        """Test basic data processing"""
        result = component._process(sample_df)
        
        assert 'main' in result
        assert 'stats' in result
        assert len(result['main']) == 2
        assert 'new_column' in result['main'].columns
    
    def test_empty_input(self, component):
        """Test handling of empty input"""
        empty_df = pd.DataFrame()
        result = component._process(empty_df)
        
        assert len(result['main']) == 0
        assert result['stats']['input_rows'] == 0
    
    def test_none_input(self, component):
        """Test handling of None input"""
        result = component._process(None)
        
        assert 'main' in result
        assert len(result['main']) == 0
    
    def test_stats_tracking(self, component, sample_df):
        """Test statistics are properly tracked"""
        result = component._process(sample_df)
        
        assert result['stats']['input_rows'] == 2
        assert result['stats']['output_rows'] == 2
        assert result['stats']['rejected_rows'] == 0
```

### **Step 5: Integration Test**

Location: `tests/v1/engine/fixtures/pipeline/` (create job config)

```json
{
  "name": "test_my_component",
  "description": "Integration test for MyComponent",
  "components": [
    {
      "id": "input",
      "type": "tFileInputDelimited",
      "config": {
        "file_path": "tests/fixtures/data/sample.csv",
        "delimiter": ","
      }
    },
    {
      "id": "my_comp",
      "type": "MyComponent",
      "config": {
        "param1": "value1",
        "param2": 100
      }
    },
    {
      "id": "output",
      "type": "tFileOutputDelimited",
      "config": {
        "file_path": "output.csv"
      }
    }
  ],
  "flows": [
    {"source": "input", "target": "my_comp", "name": "main"},
    {"source": "my_comp", "target": "output", "name": "main"}
  ]
}
```

---

## BaseComponent Lifecycle

Understanding the execution flow helps with debugging:

```
execute(input_data, context)
    |
    ├─ 1. Resolve {{java}} expressions (JavaBridgeManager)
    |
    ├─ 2. Resolve ${context.var} variables (ContextManager)
    |
    ├─ 3. Auto-select execution mode (BATCH/STREAMING/HYBRID)
    |
    ├─ 4. Call _process(input_data) [YOUR CODE]
    |     |
    |     └─ Returns: {'main': df, 'reject': df, 'stats': dict}
    |
    ├─ 5. Update global_map (NB_LINE, NB_LINE_OK, NB_LINE_REJECT)
    |
    └─ 6. Return execution result
```

### Key Methods You Can Use

| Method | Purpose |
|--------|---------|
| `self._get_str(config, key, default)` | Extract string param safely |
| `self._get_int(config, key, default)` | Extract int param safely |
| `self._get_bool(config, key, default)` | Extract bool param safely |
| `self._update_global_map()` | Set NB_LINE, NB_LINE_OK, NB_LINE_REJECT |
| `self._update_stats()` | Track component stats |
| `self.validate_schema()` | Validate input DataFrame schema |
| `logger.info(f"[{self.id}] message")` | Log with component ID prefix |

---

## Common Patterns

### Pattern 1: Filter Component

```python
def _process(self, input_data: Optional[pd.DataFrame]) -> Dict[str, Any]:
    main_df = pd.DataFrame()
    reject_df = pd.DataFrame()
    
    if input_data is None or len(input_data) == 0:
        return {'main': main_df, 'reject': reject_df, 'stats': {}}
    
    # Apply filter condition (stored in self.condition)
    mask = input_data.eval(self.condition)
    main_df = input_data[mask].copy()
    reject_df = input_data[~mask].copy()
    
    return {
        'main': main_df,
        'reject': reject_df,
        'stats': {
            'input_rows': len(input_data),
            'passed': len(main_df),
            'rejected': len(reject_df)
        }
    }
```

### Pattern 2: Aggregation Component

```python
def _process(self, input_data: Optional[pd.DataFrame]) -> Dict[str, Any]:
    if input_data is None or len(input_data) == 0:
        return {'main': pd.DataFrame(), 'stats': {}}
    
    # Group and aggregate
    grouped = input_data.groupby(self.group_by_cols, as_index=False)
    result_df = grouped.agg({
        col: self.agg_functions[col] 
        for col in self.agg_cols
    })
    
    return {
        'main': result_df,
        'stats': {
            'input_rows': len(input_data),
            'output_rows': len(result_df)
        }
    }
```

### Pattern 3: File Output Component

```python
def _process(self, input_data: Optional[pd.DataFrame]) -> Dict[str, Any]:
    if input_data is None or len(input_data) == 0:
        logger.warning(f"[{self.id}] No data to write")
        return {'main': input_data or pd.DataFrame(), 'stats': {'rows_written': 0}}
    
    try:
        # Write to file
        input_data.to_csv(self.file_path, index=False)
        
        logger.info(f"[{self.id}] Wrote {len(input_data)} rows to {self.file_path}")
        
        return {
            'main': input_data,
            'stats': {'rows_written': len(input_data)}
        }
    except Exception as e:
        logger.error(f"[{self.id}] Failed to write file: {str(e)}")
        raise FileOperationError(f"Cannot write to {self.file_path}: {str(e)}", cause=e)
```

### Pattern 4: Iterator Component

```python
from src.v1.engine.base_iterate_component import BaseIterateComponent

class MyIterator(BaseIterateComponent):
    def prepare_iterations(self):
        """Setup iterations before loop starts"""
        self.items = self._get_items()
        self.current_index = 0
        return self.items
    
    def has_next_iteration(self) -> bool:
        """Check if more iterations exist"""
        return self.current_index < len(self.items)
    
    def get_next_iteration_context(self) -> Dict[str, Any]:
        """Get context for next iteration"""
        item = self.items[self.current_index]
        self.current_index += 1
        return {'current_item': item}
    
    def finalize_iterations(self) -> None:
        """Cleanup after all iterations"""
        logger.info(f"[{self.id}] Completed {self.current_index} iterations")
    
    def _process(self, input_data):
        # This runs for each iteration
        return {'main': input_data}
```

---

## Testing Your Component

### Unit Test Checklist

- [ ] Basic processing with valid input
- [ ] Empty DataFrame handling
- [ ] None input handling
- [ ] Config parameter extraction
- [ ] Statistics tracking
- [ ] Error conditions
- [ ] Schema validation
- [ ] Column name edge cases
- [ ] Type conversions
- [ ] Large data handling

### Integration Test Checklist

- [ ] Full pipeline execution
- [ ] Multiple components chained
- [ ] Flow routing (main/reject)
- [ ] File I/O operations
- [ ] Context variables passed correctly
- [ ] GlobalMap updates
- [ ] End-to-end data integrity

### Run Coverage Gate

```bash
# Test your component
pytest tests/v1/engine/components/mycomponent/ -v

# Check coverage
pytest tests/v1/engine/components/mycomponent/ \
  --cov=src/v1/engine/components/mycomponent \
  --cov-report=term-missing

# Must be >= 95% line coverage
```

---

## Troubleshooting

### Component Not Found

**Error:** `KeyError: 'MyComponent' not in COMPONENT_REGISTRY`

**Fix:**
1. Verify entry in `component_registry.py`
2. Check spelling matches class name exactly
3. Restart Python/test process (imports cached)

### Empty Output DataFrame

**Causes:**
- Input validation filtering out all rows
- Logic error in processing
- Schema mismatch

**Debug:**
```python
logger.debug(f"[{self.id}] Input shape: {input_data.shape}")
logger.debug(f"[{self.id}] Columns: {list(input_data.columns)}")
logger.debug(f"[{self.id}] Output shape: {result_df.shape}")
```

### Config Parameter Not Found

**Error:** `KeyError: 'param_name' in config`

**Fix:**
Always use getter methods with defaults:
```python
# WRONG
self.param = config['param_name']

# RIGHT
self.param = self._get_str(config, 'param_name', 'default_value')
```

### Java Expression Not Resolving

**Error:** `{{java}}` markers appear in output

**Fix:**
1. Check Java bridge is enabled (`java_config.enabled=true`)
2. Verify JVM 11+ on PATH
3. Check bridge JAR exists at `src/v1/java_bridge/java/target/*.jar`
4. Look for bridge startup errors in logs

### Test Fails with Coverage Gate

**Error:** Coverage < 95%

**Fix:**
1. Check which lines lack coverage: `--cov-report=term-missing`
2. Add tests for edge cases
3. Remove dead code or refactor
4. Use `# pragma: no cover` only for unreachable code

---

## Checklist: Before Committing

- [ ] Component class created and inherits from BaseComponent
- [ ] Registered in component_registry.py (both camelCase and tXXX names)
- [ ] Exported in __init__.py with __all__
- [ ] Docstrings on class and _process() method
- [ ] Unit tests created (>= 95% coverage)
- [ ] Integration test created (if file I/O)
- [ ] Logging added with [component_id] prefix
- [ ] Error handling with ComponentExecutionError
- [ ] Config extraction with _get_* helpers (no direct dict access)
- [ ] Stats dictionary populated
- [ ] No pandas FutureWarnings
- [ ] No hardcoded paths (use config)
- [ ] No external dependencies added (use existing only)

---

## Next Steps

1. **Review existing components:** Look at similar component for patterns
2. **Start small:** Create minimal version, test it, expand
3. **Follow ABC:** Respect the BaseComponent contract
4. **Test thoroughly:** 95% coverage requirement is strict
5. **Document well:** Future maintainers will thank you
6. **Ask for review:** Get PR feedback before merging

For questions, see TROUBLESHOOTING.md or CONTRIBUTING.md.
