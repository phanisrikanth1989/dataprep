# Testing Strategy & Patterns Guide

**Last Updated:** 2026-06-13

---

## Table of Contents

1. [Overview](#overview)
2. [Coverage Gate Requirements](#coverage-gate-requirements)
3. [Unit Testing Patterns](#unit-testing-patterns)
4. [Integration Testing Patterns](#integration-testing-patterns)
5. [Java Bridge Testing](#java-bridge-testing)
6. [Fixtures & Test Data](#fixtures--test-data)
7. [Mocking Strategies](#mocking-strategies)
8. [Common Test Failures](#common-test-failures)
9. [Performance Testing](#performance-testing)
10. [Test Checklists](#test-checklists)

---

## Overview

DataPrep enforces **95% per-module line coverage** as an immovable gate before production.

**Key Metrics:**
- 211 source files to cover
- 258 test files exist
- Coverage measured per-module (not global average)
- Branch coverage disabled (by design)
- Java bridge tests included in gate

**Test Categories:**
```
@pytest.mark.unit         # Fast, no I/O (< 1 second)
@pytest.mark.integration  # File I/O, full pipelines (1-10 seconds)
@pytest.mark.java         # Requires JVM 11+ (included in gate)
@pytest.mark.oracle       # Optional, excluded from gate
@pytest.mark.slow         # > 5 seconds
```

---

## Coverage Gate Requirements

### Running the Gate

```bash
# Exact gate command (from CLAUDE.md)
rm -f .coverage* && python -m pytest tests/ -m "not oracle" -n auto \
  --cov=src/v1/engine \
  --cov=src/converters \
  --cov-report=term-missing \
  --cov-report=html \
  --cov-report=json \
  && python scripts/check_per_module_coverage.py coverage.json --floor 95
```

**Expected Output:**
```
======================== 1850 passed in 45.23s =========================
PASS: all 181 in-scope modules at >= 95.0% line coverage
```

### What Gets Measured

**In-scope:**
```
src/v1/engine/          # Core engine
src/converters/         # Converter layer
(NOT src/converters/complex_converter/)
(NOT */__init__.py)
```

**Excluded from measurement:**
```
*/__init__.py           # Re-export only
__main__                # CLI entry points
@abstractmethod         # Interface markers
raise NotImplementedError
# pragma: no cover      # Manual exclusion (narrow allowlist)
```

### Handling Coverage Gaps

**Scenario: You have 89% coverage, need 95%**

```bash
# Step 1: Identify uncovered lines
pytest tests/ -m "not oracle" \
  --cov=src/v1/engine/components/file/file_input_delimited \
  --cov-report=term-missing

# Output shows:
# file_input_delimited.py  89.2%   34,45,67-70,89

# Step 2: Write tests for those lines
# Step 3: Run coverage again

# Step 4: If truly unreachable, mark with pragma
if __name__ == '__main__':  # pragma: no cover
    main()
```

---

## Unit Testing Patterns

### Pattern 1: Component Initialization Test

```python
import pytest
from src.v1.engine.components.file.file_input_delimited import FileInputDelimited


class TestFileInputDelimitedInit:
    """Test component initialization"""
    
    def test_init_with_defaults(self):
        """Test initialization with minimal config"""
        config = {
            'file_path': 'test.csv'
        }
        comp = FileInputDelimited('test_id', config)
        
        assert comp.id == 'test_id'
        assert comp.file_path == 'test.csv'
        assert comp.delimiter == ','  # default
    
    def test_init_with_custom_delimiter(self):
        """Test with custom configuration"""
        config = {
            'file_path': 'test.tsv',
            'delimiter': '\t'
        }
        comp = FileInputDelimited('test_id', config)
        
        assert comp.delimiter == '\t'
    
    def test_init_missing_required_param(self):
        """Test error when required param missing"""
        config = {}
        
        with pytest.raises(KeyError):
            FileInputDelimited('test_id', config)
    
    def test_init_invalid_param_type(self):
        """Test error on invalid parameter type"""
        config = {
            'file_path': 'test.csv',
            'encoding': 123  # Should be string
        }
        
        with pytest.raises((TypeError, ValueError)):
            FileInputDelimited('test_id', config)
```

### Pattern 2: Data Processing Test

```python
class TestFileInputDelimitedProcessing:
    """Test core processing logic"""
    
    @pytest.fixture
    def component(self):
        config = {'file_path': 'tests/fixtures/data/sample.csv'}
        return FileInputDelimited('test_id', config)
    
    @pytest.fixture
    def sample_file(self, tmp_path):
        """Create temporary test file"""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("col1,col2\n1,hello\n2,world\n")
        return str(csv_file)
    
    def test_process_valid_file(self, component, sample_file):
        """Test reading valid CSV file"""
        component.file_path = sample_file
        result = component._process(None)
        
        assert 'main' in result
        assert len(result['main']) == 2
        assert list(result['main'].columns) == ['col1', 'col2']
    
    def test_process_empty_file(self, component, sample_file):
        """Test reading empty file"""
        empty_file = sample_file
        with open(empty_file, 'w') as f:
            f.write('')  # Empty
        
        result = component._process(empty_file)
        
        assert 'main' in result
        assert len(result['main']) == 0
    
    def test_process_returns_required_keys(self, component, sample_file):
        """Test return dict has all required keys"""
        component.file_path = sample_file
        result = component._process(None)
        
        assert 'main' in result
        assert 'stats' in result
        assert isinstance(result['main'], pd.DataFrame)
        assert isinstance(result['stats'], dict)
    
    def test_stats_tracking(self, component, sample_file):
        """Test statistics are correctly tracked"""
        component.file_path = sample_file
        result = component._process(None)
        
        assert result['stats']['rows_read'] == 2
        assert result['stats']['encoding_used'] == 'utf-8'
```

### Pattern 3: Error Handling Test

```python
class TestFileInputDelimitedErrors:
    """Test error handling"""
    
    def test_process_missing_file(self):
        """Test error when file doesn't exist"""
        config = {'file_path': '/nonexistent/file.csv'}
        comp = FileInputDelimited('test_id', config)
        
        with pytest.raises(FileOperationError) as exc_info:
            comp._process(None)
        
        assert 'file_path' in str(exc_info.value).lower()
        assert 'not found' in str(exc_info.value).lower()
    
    def test_process_permission_denied(self, tmp_path):
        """Test error when file not readable"""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("col1,col2\n1,2\n")
        csv_file.chmod(0o000)  # Remove all permissions
        
        config = {'file_path': str(csv_file)}
        comp = FileInputDelimitedStub('test_id', config)
        
        try:
            with pytest.raises(FileOperationError):
                comp._process(None)
        finally:
            csv_file.chmod(0o644)  # Restore permissions
    
    def test_process_encoding_error(self, tmp_path):
        """Test error on encoding mismatch"""
        csv_file = tmp_path / "test.csv"
        csv_file.write_bytes(b'\xff\xfe')  # UTF-16 BOM
        
        config = {'file_path': str(csv_file), 'encoding': 'utf-8'}
        comp = FileInputDelimited('test_id', config)
        
        with pytest.raises(FileOperationError):
            comp._process(None)
```

### Pattern 4: Schema & Type Validation

```python
class TestComponentSchema:
    """Test schema handling"""
    
    def test_validate_input_schema(self):
        """Test input schema validation"""
        config = {
            'file_path': 'test.csv',
            'schema': [
                {'name': 'id', 'type': 'integer'},
                {'name': 'name', 'type': 'string'}
            ]
        }
        comp = FileInputDelimited('test_id', config)
        
        # Create matching DataFrame
        df = pd.DataFrame({
            'id': [1, 2, 3],
            'name': ['a', 'b', 'c']
        })
        
        # Should not raise
        comp.validate_schema(df)
    
    def test_validate_schema_mismatch(self):
        """Test error on schema mismatch"""
        config = {
            'file_path': 'test.csv',
            'schema': [
                {'name': 'id', 'type': 'integer'},
                {'name': 'name', 'type': 'string'}
            ]
        }
        comp = FileInputDelimited('test_id', config)
        
        # Create non-matching DataFrame
        df = pd.DataFrame({
            'id': [1, 2, 3],
            'email': ['a@b.com', 'c@d.com', 'e@f.com']  # Wrong column
        })
        
        with pytest.raises(SchemaError):
            comp.validate_schema(df)
```

---

## Integration Testing Patterns

### Pattern 1: Full Pipeline Execution

```python
import json
from src.v1.engine import ETLEngine


class TestFullPipeline:
    """Integration tests for complete pipelines"""
    
    @pytest.fixture
    def sample_csv(self, tmp_path):
        """Create test input file"""
        csv_file = tmp_path / "input.csv"
        csv_file.write_text("id,value\n1,100\n2,200\n3,300\n")
        return str(csv_file)
    
    @pytest.fixture
    def job_config(self, tmp_path, sample_csv):
        """Create job configuration"""
        output_file = tmp_path / "output.csv"
        return {
            "name": "test_pipeline",
            "components": [
                {
                    "id": "input",
                    "type": "tFileInputDelimited",
                    "config": {
                        "file_path": sample_csv,
                        "delimiter": ","
                    }
                },
                {
                    "id": "output",
                    "type": "tFileOutputDelimited",
                    "config": {
                        "file_path": str(output_file),
                        "delimiter": ","
                    }
                }
            ],
            "flows": [
                {
                    "source": "input",
                    "target": "output",
                    "name": "main"
                }
            ]
        }
    
    def test_simple_read_write_pipeline(self, job_config, tmp_path):
        """Test simple input -> output pipeline"""
        config_file = tmp_path / "job.json"
        with open(config_file, 'w') as f:
            json.dump(job_config, f)
        
        engine = ETLEngine()
        result = engine.run_job(str(config_file))
        
        assert result['status'] == 'SUCCESS'
        assert result['execution_stats']['total_components'] == 2
        assert result['execution_stats']['successful_components'] == 2
    
    def test_pipeline_with_filter(self, job_config, tmp_path):
        """Test pipeline with transformation component"""
        job_config['components'].insert(1, {
            "id": "filter",
            "type": "tFilter",
            "config": {
                "condition": "value > 150"
            }
        })
        
        job_config['flows'] = [
            {"source": "input", "target": "filter", "name": "main"},
            {"source": "filter", "target": "output", "name": "main"}
        ]
        
        config_file = tmp_path / "job.json"
        with open(config_file, 'w') as f:
            json.dump(job_config, f)
        
        engine = ETLEngine()
        result = engine.run_job(str(config_file))
        
        assert result['status'] == 'SUCCESS'
        # Should only output 2 rows (value > 150)
        assert result['execution_stats']['components']['output']['rows_processed'] == 2
```

### Pattern 2: End-to-End Data Integrity

```python
class TestDataIntegrity:
    """Test data is unchanged through pipeline"""
    
    def test_data_roundtrip(self, tmp_path):
        """Test data in == data out"""
        input_file = tmp_path / "input.csv"
        input_data = "id,name,value\n1,a,100\n2,b,200\n"
        input_file.write_text(input_data)
        
        output_file = tmp_path / "output.csv"
        
        config = {
            "components": [
                {
                    "id": "input",
                    "type": "tFileInputDelimited",
                    "config": {"file_path": str(input_file)}
                },
                {
                    "id": "output",
                    "type": "tFileOutputDelimited",
                    "config": {"file_path": str(output_file)}
                }
            ],
            "flows": [{"source": "input", "target": "output", "name": "main"}]
        }
        
        config_file = tmp_path / "job.json"
        with open(config_file, 'w') as f:
            json.dump(config, f)
        
        engine = ETLEngine()
        engine.run_job(str(config_file))
        
        # Read output and compare
        input_df = pd.read_csv(input_file)
        output_df = pd.read_csv(output_file)
        
        pd.testing.assert_frame_equal(input_df, output_df)
    
    def test_type_preservation(self, tmp_path):
        """Test data types preserved through pipeline"""
        input_file = tmp_path / "input.csv"
        input_file.write_text("id,value,price\n1,100,12.50\n2,200,25.00\n")
        
        config = {
            "components": [
                {
                    "id": "input",
                    "type": "tFileInputDelimited",
                    "config": {
                        "file_path": str(input_file),
                        "schema": [
                            {"name": "id", "type": "integer"},
                            {"name": "value", "type": "integer"},
                            {"name": "price", "type": "double"}
                        ]
                    }
                }
            ]
        }
        
        engine = ETLEngine()
        # Component execution would preserve types
        comp = engine._get_component('input', config['components'][0])
        result = comp._process(None)
        df = result['main']
        
        assert df['id'].dtype in [pd.Int64Dtype(), 'int64']
        assert df['value'].dtype in [pd.Int64Dtype(), 'int64']
        assert df['price'].dtype in ['float64', 'Float64Dtype']
```

---

## Java Bridge Testing

### Pattern 1: Java Expression Evaluation

```python
@pytest.mark.java
class TestJavaBridge:
    """Test Java expression execution (requires JVM)"""
    
    @pytest.fixture
    def bridge(self):
        """Initialize Java bridge"""
        from src.v1.engine.java_bridge_manager import JavaBridgeManager
        mgr = JavaBridgeManager()
        mgr.start()
        yield mgr
        mgr.stop()
    
    def test_simple_expression(self, bridge):
        """Test basic Java expression evaluation"""
        result = bridge.bridge.execute_expression(
            "'hello'.toUpperCase()",
            {}
        )
        assert result == 'HELLO'
    
    def test_expression_with_context(self, bridge):
        """Test expression accessing context variables"""
        context = {
            'name': 'world'
        }
        result = bridge.bridge.execute_expression(
            "'hello ' + name",
            context
        )
        assert result == 'hello world'
    
    def test_numeric_expression(self, bridge):
        """Test numeric operations"""
        context = {'value': 10}
        result = bridge.bridge.execute_expression(
            "value * 2 + 5",
            context
        )
        assert result == 25
    
    def test_null_handling(self, bridge):
        """Test null value handling"""
        context = {'value': None}
        result = bridge.bridge.execute_expression(
            "value == null ? 'null' : 'not null'",
            context
        )
        assert result == 'null'
    
    def test_expression_error(self, bridge):
        """Test error in Java expression"""
        with pytest.raises(Exception):  # JavaBridgeError
            bridge.bridge.execute_expression(
                "invalid java syntax }}}",
                {}
            )
```

### Pattern 2: tMap Testing

```python
@pytest.mark.java
class TestTMapExecution:
    """Test tMap component with Java bridge"""
    
    @pytest.fixture
    def sample_df(self):
        return pd.DataFrame({
            'first_name': ['John', 'Jane'],
            'last_name': ['Doe', 'Smith']
        })
    
    def test_tmap_field_concatenation(self, sample_df):
        """Test tMap concatenating fields"""
        config = {
            'mapping': {
                'full_name': "first_name + ' ' + last_name"
            },
            'java_expressions': True
        }
        
        from src.v1.engine.components.transform.map.tmap import TMap
        comp = TMap('test_map', config)
        result = comp._process(sample_df)
        
        output_df = result['main']
        assert 'full_name' in output_df.columns
        assert output_df['full_name'].iloc[0] == 'John Doe'
    
    def test_tmap_with_java_functions(self, sample_df):
        """Test tMap using Java string functions"""
        config = {
            'mapping': {
                'name_upper': "first_name.toUpperCase()"
            },
            'java_expressions': True
        }
        
        comp = TMap('test_map', config)
        result = comp._process(sample_df)
        
        output_df = result['main']
        assert output_df['name_upper'].iloc[0] == 'JOHN'
```

---

## Fixtures & Test Data

### Pattern 1: Shared Fixtures

```python
# tests/conftest.py
import pytest
import pandas as pd
import tempfile
from pathlib import Path


@pytest.fixture(scope='session')
def data_dir():
    """Path to test data directory"""
    return Path(__file__).parent / 'fixtures' / 'data'


@pytest.fixture
def sample_csv(data_dir):
    """Standard test CSV file"""
    return str(data_dir / 'sample.csv')


@pytest.fixture
def sample_df():
    """Standard test DataFrame"""
    return pd.DataFrame({
        'id': [1, 2, 3],
        'name': ['a', 'b', 'c'],
        'value': [100.5, 200.5, 300.5]
    })


@pytest.fixture
def empty_df():
    """Empty DataFrame"""
    return pd.DataFrame()


@pytest.fixture
def temp_csv(tmp_path):
    """Create temporary CSV file"""
    csv_file = tmp_path / "temp.csv"
    csv_file.write_text("col1,col2\n1,2\n3,4\n")
    return str(csv_file)


@pytest.fixture
def job_config_simple(tmp_path):
    """Minimal valid job config"""
    return {
        "name": "test_job",
        "components": [],
        "flows": []
    }
```

### Pattern 2: Test Data Organization

```
tests/fixtures/
├── data/                    # Raw data files
│   ├── sample.csv          # Standard test CSV
│   ├── large_file.csv      # Performance testing
│   ├── sample.xlsx         # Excel tests
│   ├── sample.json         # JSON tests
│   └── invalid/            # Malformed data
│       ├── encoding_error.csv
│       ├── missing_headers.csv
│       └── empty.csv
├── jobs/                    # Job configurations
│   ├── simple_pipeline.json
│   ├── with_filter.json
│   ├── with_java_bridge.json
│   └── complex_job.json
└── configs/                 # Component configs
    ├── file_input.json
    └── file_output.json
```

---

## Mocking Strategies

### Pattern 1: Mock File System

```python
from unittest.mock import Mock, patch, MagicMock


class TestFileInputWithMock:
    """Test file operations using mocks"""
    
    @patch('builtins.open', create=True)
    def test_read_with_mock_file(self, mock_open):
        """Test file reading with mocked file"""
        mock_open.return_value.__enter__.return_value.read.return_value = \
            "col1,col2\n1,2\n"
        
        # File operations would use mock
        # instead of real filesystem
    
    @patch('pandas.read_csv')
    def test_with_mocked_pandas(self, mock_read_csv):
        """Test with mocked pandas read"""
        mock_df = pd.DataFrame({'col': [1, 2, 3]})
        mock_read_csv.return_value = mock_df
        
        # Component would get mock DataFrame


@patch('src.v1.engine.java_bridge_manager.JavaBridgeManager')
def test_component_without_java_bridge(mock_bridge_mgr):
    """Test component logic without Java bridge"""
    mock_bridge_mgr.return_value.is_alive.return_value = False
    
    # Component would skip Java execution
```

### Pattern 2: Mock Java Bridge

```python
@pytest.mark.unit
class TestComponentWithoutJava:
    """Test component in pure Python mode"""
    
    @pytest.fixture
    def component_no_java(self):
        """Component with Java bridge disabled"""
        config = {
            'java_config': {'enabled': False}
        }
        # Component executes without JVM
        return SomeComponent('test_id', config)
    
    def test_python_fallback(self, component_no_java):
        """Test component works without Java"""
        input_df = pd.DataFrame({'value': [1, 2, 3]})
        result = component_no_java._process(input_df)
        
        # Should produce output without Java
        assert 'main' in result
        assert len(result['main']) > 0
```

---

## Common Test Failures

### Failure: "AttributeError: 'DataFrame' object has no attribute 'col'"

```python
# WRONG: Column doesn't exist
result = df.col

# RIGHT: Use bracket notation or .loc
result = df['col']
result = df.loc[:, 'col']
```

### Failure: "AssertionError: Lists differ"

```python
# For DataFrames, use pd.testing.assert_frame_equal
pd.testing.assert_frame_equal(df1, df2)

# For Series
pd.testing.assert_series_equal(s1, s2)

# For lists/values
assert result == expected or use assert_almost_equal for floats
```

### Failure: "PermissionError: Permission denied"

```python
# Ensure tmp_path fixture is used (auto-cleaned)
def test_something(tmp_path):
    file = tmp_path / "test.txt"
    # tmp_path always writable and cleaned up
```

### Failure: "Import errors in tests"

```bash
# Ensure PYTHONPATH includes project root
export PYTHONPATH=/path/to/recdataprep:$PYTHONPATH
pytest tests/

# Or run from project root
cd /path/to/recdataprep
pytest tests/
```

---

## Performance Testing

### Pattern: Benchmark Component

```python
@pytest.mark.slow
def test_component_performance(benchmark):
    """Benchmark component performance"""
    config = {'file_path': 'large_data.csv'}
    comp = FileInputDelimited('test_id', config)
    
    # Benchmark the processing
    result = benchmark(comp._process, None)
    
    # assertions about performance
    assert len(result['main']) > 1000000
    assert 'stats' in result
```

### Pattern: Memory Usage Test

```python
import tracemalloc


def test_memory_efficiency(sample_df):
    """Test memory usage stays reasonable"""
    tracemalloc.start()
    
    comp = MyComponent('test_id', {})
    result = comp._process(sample_df)
    
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    
    # Peak memory should be reasonable (< 1GB)
    assert peak < 1e9
```

---

## Test Checklists

### Unit Test Checklist

- [ ] Class initialization with defaults
- [ ] Class initialization with custom config
- [ ] Missing required parameters raise error
- [ ] Invalid parameter types raise error
- [ ] Basic data processing (happy path)
- [ ] Empty input handling
- [ ] None input handling
- [ ] Schema validation passes/fails correctly
- [ ] Error conditions raise appropriate exceptions
- [ ] Statistics are correctly tracked
- [ ] Logging includes component ID
- [ ] No FutureWarnings from pandas
- [ ] Coverage >= 95%

### Integration Test Checklist

- [ ] Simple pipeline (input → output)
- [ ] Pipeline with transformation
- [ ] Pipeline with multiple components chained
- [ ] Flow routing (main/reject)
- [ ] Data integrity (in == out)
- [ ] Type preservation through pipeline
- [ ] File I/O integration
- [ ] Context variables passed correctly
- [ ] GlobalMap updated correctly
- [ ] Error propagation works
- [ ] End-to-end execution succeeds
- [ ] Output files created correctly

### Java Bridge Test Checklist (if applicable)

- [ ] Simple Java expression evaluation
- [ ] Expression with context variables
- [ ] Numeric operations
- [ ] String operations
- [ ] Null handling
- [ ] Error in expression handled
- [ ] tMap field mapping works
- [ ] tMap with Java functions works
- [ ] Bridge starts/stops cleanly
- [ ] Multiple expressions batched

### Coverage Requirements Checklist

- [ ] All public methods tested
- [ ] All conditional branches tested
- [ ] Happy path tested
- [ ] Error paths tested
- [ ] Edge cases tested
- [ ] Empty input tested
- [ ] None input tested
- [ ] Large data tested (at least one case)
- [ ] Coverage >= 95% per module
- [ ] No manual `# pragma: no cover` abuses

---

## Running Tests Efficiently

```bash
# Run only unit tests (fast)
pytest tests/ -m unit -v

# Run specific component tests
pytest tests/v1/engine/components/file/ -v

# Run with coverage report
pytest tests/ -m "not oracle" --cov=src --cov-report=term-missing

# Run in parallel (faster)
pytest tests/ -m "not oracle" -n auto

# Run with full debug output
pytest tests/ -vv -s

# Run and stop on first failure
pytest tests/ -x

# Run specific test
pytest tests/v1/engine/components/file/test_file_input_delimited.py::TestClass::test_method
```

---

## Best Practices

1. **Use fixtures for setup/teardown** (tmp_path, sample_df, etc.)
2. **Test one thing per test** (specific behavior)
3. **Use descriptive test names** (test_X_when_Y_then_Z)
4. **Avoid test interdependencies** (each test should run standalone)
5. **Clean up resources** (files, temp dirs, connections)
6. **Test both success and failure paths**
7. **Use assertions with good messages** (assert X, "reason it failed")
8. **Keep tests fast** (< 1s for unit tests)
9. **Isolate external dependencies** (mock file I/O, network, etc.)
10. **Document complex test setups** (fixture docstrings)

