# Troubleshooting & Debugging Guide

**Last Updated:** 2026-06-13

---

## Table of Contents

1. [Quick Diagnostics](#quick-diagnostics)
2. [Converter Issues](#converter-issues)
3. [Engine Execution Issues](#engine-execution-issues)
4. [Java Bridge Issues](#java-bridge-issues)
5. [Data & Schema Issues](#data--schema-issues)
6. [Expression Resolution Issues](#expression-resolution-issues)
7. [Performance Issues](#performance-issues)
8. [File I/O Issues](#file-io-issues)
9. [Context & GlobalMap Issues](#context--globalmap-issues)
10. [Testing & Coverage Issues](#testing--coverage-issues)

---

## Quick Diagnostics

### **Always Start Here**

Before diving into specific issues, gather diagnostic info:

```bash
# 1. Check Python version
python --version
# Expected: Python 3.12+

# 2. Check JVM (if using Java components)
java -version
# Expected: Java 11+

# 3. Check key files exist
ls src/v1/java_bridge/java/target/java-bridge-with-dependencies.jar
ls src/v1/engine/engine.py

# 4. Run a simple test
pytest tests/v1/engine/components/file/test_file_input_delimited.py -v -s

# 5. Check for import errors
python -c "from src.v1.engine import ETLEngine; print('OK')"

# 6. Check dependencies
python -c "import pandas; import pyarrow; import py4j; print('OK')"
```

### **Enable Debug Logging**

Add to your script before execution:

```python
import logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
)
```

This shows:
- Component initialization details
- Data flow at each step
- Java bridge communication
- Context resolution
- Expression evaluation

---

## Converter Issues

### Issue: "Unsupported Component" Placeholder in Output

**Symptom:**
```json
{
  "type": "_unsupported",
  "component_name": "tUnknownComponent"
}
```

**Causes:**
1. Converter doesn't have a handler for this Talend component
2. Component converter class not registered
3. Component name spelling mismatch

**Diagnosis:**
```bash
grep -r "tUnknownComponent" src/converters/talend_to_v1/components/
# If no match: component not implemented yet
```

**Solutions:**
1. **Check if converter exists:**
   ```bash
   find src/converters/talend_to_v1/components -name "*unknown*" -o -name "*UnknownComponent*"
   ```

2. **Check registration:**
   ```bash
   grep "tUnknownComponent" src/converters/talend_to_v1/components/*/registry.py
   ```

3. **If not implemented:**
   - Create new converter component (see COMPONENT_IMPLEMENTATION_GUIDE.md)
   - Mark in component_reference.md as "TODO"
   - Document current workaround in comments

### Issue: "Failed to Convert: Component has schema mismatch"

**Symptom:**
```
WARNING: Component 'map_1' has schema mismatch
Conversion needs review
```

**Causes:**
1. Talend schema definition doesn't match converter expectations
2. XML parser couldn't extract schema properly
3. Component has dynamic schema (columns determined at runtime)

**Diagnosis:**
```bash
# View the original XML
cat /path/to/job.item | grep -A 50 'map_1'

# Check what converter extracted
python -c "
from src.converters.talend_to_v1.xml_parser import XmlParser
parser = XmlParser('/path/to/job.item')
job = parser.parse()
comp = [c for c in job.components if c.name == 'map_1'][0]
print(comp.schema)
"
```

**Solutions:**
1. **Manually fix schema in output JSON:**
   ```json
   {
     "id": "map_1",
     "type": "tMap",
     "schema": [
       {"name": "col1", "type": "string"},
       {"name": "col2", "type": "integer"}
     ]
   }
   ```

2. **Use `needs_review` flag** to mark for manual verification

3. **Check converter logs** for warnings:
   ```bash
   python -m src.converters.talend_to_v1.converter job.item -v 2>&1 | grep -i "schema\|warning"
   ```

### Issue: "Expression could not be converted"

**Symptom:**
```
WARNING: Could not convert Java expression: 'complex.method()'
Marked with {{java}} for runtime evaluation
```

**Causes:**
1. Complex Java syntax not recognized by converter
2. Custom methods or classes
3. Talend-specific APIs

**Solutions:**
1. **Check if Java bridge can handle it:**
   ```python
   from src.v1.java_bridge.bridge import JavaBridge
   bridge = JavaBridge()
   bridge.start()
   result = bridge.execute_expression("complex.method()", {})
   bridge.stop()
   ```

2. **Simplify expression in Talend job** before converting

3. **Use Python custom code** instead of Java/Groovy

4. **Document in issue tracker** if commonly needed

---

## Engine Execution Issues

### Issue: "Component XYZ not found in registry"

**Symptom:**
```python
KeyError: 'XYZ' not in COMPONENT_REGISTRY
```

**Causes:**
1. Component not registered
2. Spelling mismatch (camelCase vs snake_case)
3. Talend name vs Python class name confusion

**Diagnosis:**
```bash
# List all registered components
python -c "
from src.v1.engine.component_registry import COMPONENT_REGISTRY
for name in sorted(COMPONENT_REGISTRY.keys()):
    print(name)
" | grep -i xyz
```

**Solutions:**
1. **Check component_registry.py:**
   ```python
   from src.v1.engine.component_registry import COMPONENT_REGISTRY
   print(COMPONENT_REGISTRY.get('tFileInputDelimited'))
   ```

2. **Verify spelling in job config:**
   ```bash
   # In JSON config
   "type": "tFileInputDelimited"  # Correct
   # NOT
   "type": "FileInputDelimited"   # May not be registered
   ```

3. **Register missing component:**
   ```python
   # In component_registry.py
   "MyComponent": "src.v1.engine.components.category.my_component:MyComponent",
   ```

### Issue: "Empty DataFrame produced by component"

**Symptom:**
```
Component 'filter_1' produced 0 output rows
No data passed to downstream components
```

**Causes:**
1. Input data filtered out entirely
2. Schema mismatch preventing processing
3. Component logic error
4. Upstream component produced no output

**Diagnosis:**
```python
# Enable debug logging
import logging
logging.getLogger('src.v1.engine').setLevel(logging.DEBUG)

# Add to job config to see intermediate data
"debug": true

# Check component output before/after
engine = ETLEngine()
result = engine.run_job('job.json')
print(result['execution_stats']['components']['filter_1'])
```

**Solutions:**
1. **Verify upstream data:**
   ```bash
   # Output upstream component to file
   # Check if data exists
   cat output_upstream.csv | head
   ```

2. **Check filter condition:**
   ```python
   # If using tFilter, verify condition works
   import pandas as pd
   df = pd.read_csv('input.csv')
   mask = df.eval('column > 100')  # Your condition
   print(f"Matched rows: {mask.sum()}")
   ```

3. **Enable component debug logging:**
   Update job config:
   ```json
   {
     "components": [{
       "id": "filter_1",
       "type": "tFilter",
       "config": {
         "condition": "column > 100",
         "debug": true
       }
     }]
   }
   ```

### Issue: "ComponentExecutionError: Component XYZ failed"

**Symptom:**
```
ComponentExecutionError: Component 'map_1' failed during execution
Cause: TypeError: unsupported operand type(s)
```

**Causes:**
1. Type mismatch (string vs number)
2. Null/None values not handled
3. Column doesn't exist
4. Invalid parameter value

**Diagnosis:**
```python
# Run with full traceback
import traceback
try:
    engine.run_job('job.json')
except Exception as e:
    traceback.print_exc()
    print(f"Component: {e.component_id if hasattr(e, 'component_id') else 'unknown'}")
    print(f"Cause: {e.cause if hasattr(e, 'cause') else str(e)}")
```

**Solutions:**
1. **Check input data types:**
   ```python
   df = pd.read_csv('input.csv')
   print(df.dtypes)
   # Fix: convert if needed
   # df['numeric_col'] = pd.to_numeric(df['numeric_col'], errors='coerce')
   ```

2. **Handle None/null values:**
   ```python
   df['col'].fillna(0, inplace=True)  # or appropriate default
   ```

3. **Verify column exists:**
   ```python
   assert 'expected_col' in df.columns, f"Missing column. Have: {list(df.columns)}"
   ```

4. **Check config parameters:**
   ```json
   {
     "id": "map_1",
     "type": "tMap",
     "config": {
       "column_name": "EXACT_NAME_IN_DATA",
       "max_rows": 1000
     }
   }
   ```

### Issue: "Die component triggered"

**Symptom:**
```
Execution terminated: Die component 'die_on_error_1' fired
Exit code: 1
Message: "Processing failed"
```

**Causes:**
1. Upstream component failed and `die_on_error=true`
2. Manual Die component triggered
3. Conditional flow logic led to Die

**Solutions:**
1. **Review upstream errors:**
   ```bash
   # Check execution_stats for failed components
   cat result.json | jq '.execution_stats.failed_components[]'
   ```

2. **Fix upstream component** or make `die_on_error=false`

3. **Review flow logic:**
   ```json
   {
     "triggers": [{
       "source": "map_1",
       "event": "OnComponentOk",
       "target": "die_1"
     }]
   }
   // This means die_1 fires if map_1 succeeds
   ```

---

## Java Bridge Issues

### Issue: "Java bridge failed to start"

**Symptom:**
```
JavaBridgeError: Failed to start Java bridge
Cannot bind to port, Java process not started
```

**Causes:**
1. JVM not installed or not on PATH
2. Port already in use
3. JAR file missing or corrupted
4. Java version < 11

**Diagnosis:**
```bash
# 1. Check Java
java -version
# Should output Java 11+

# 2. Check JAR exists
ls -la src/v1/java_bridge/java/target/java-bridge-with-dependencies.jar

# 3. Check port availability
netstat -an | grep 25333  # Default Py4J port

# 4. Check Java bridge logs
tail -f /tmp/java_bridge.log
```

**Solutions:**
1. **Install/Update Java:**
   ```bash
   # macOS
   brew install openjdk@11
   
   # Ubuntu
   sudo apt-get install openjdk-11-jdk
   
   # Windows
   choco install openjdk11
   ```

2. **Build Java bridge:**
   ```bash
   cd src/v1/java_bridge/java
   mvn clean package -DskipTests
   # Check: target/java-bridge-with-dependencies.jar exists
   ```

3. **Kill process using port:**
   ```bash
   lsof -i :25333
   kill -9 <PID>
   ```

4. **Force port change:**
   ```python
   from src.v1.engine.java_bridge_manager import JavaBridgeManager
   manager = JavaBridgeManager(port=25334)  # Use different port
   ```

### Issue: "{{java}} expressions not executing"

**Symptom:**
```
Java expressions marked as {{java}} but not evaluated
Output contains literal "{{java}}" strings
```

**Causes:**
1. Java bridge not enabled in job config
2. Bridge failed to start silently
3. Expression syntax error
4. Bridge communication timeout

**Diagnosis:**
```python
# Check if Java bridge started
from src.v1.engine.java_bridge_manager import JavaBridgeManager
manager = JavaBridgeManager()
print(f"Bridge alive: {manager.is_alive()}")

# Try manual expression
result = manager.bridge.execute_expression("'hello'.toUpperCase()", {})
print(result)
```

**Solutions:**
1. **Enable Java in job config:**
   ```json
   {
     "java_config": {
       "enabled": true
     }
   }
   ```

2. **Check bridge startup logs:**
   ```python
   import logging
   logging.getLogger('src.v1.engine.java_bridge_manager').setLevel(logging.DEBUG)
   ```

3. **Simplify expression:**
   ```groovy
   // WORKS
   'hello'.toUpperCase()
   
   // May fail
   complex.nested.method(arg1, arg2).filter(x > 5)
   ```

4. **Fallback to Python:**
   Convert Java expression to Python or use tJavaRow for complex logic

### Issue: "Arrow serialization error"

**Symptom:**
```
pyarrow.lib.ArrowException: Invalid DataFrame for serialization
Cannot serialize column with type <object>
```

**Causes:**
1. DataFrame contains mixed types (strings, numbers, objects)
2. Column contains complex Python objects
3. Arrow version mismatch
4. NaN/None handling issue

**Solutions:**
1. **Ensure clean types:**
   ```python
   df = df.astype({
       'col1': 'string',
       'col2': 'int64',
       'col3': 'float64'
   })
   ```

2. **Handle None/NaN:**
   ```python
   df = df.fillna('')  # or 0, depending on type
   ```

3. **Remove complex objects:**
   ```python
   # Instead of storing objects, serialize to JSON
   df['metadata'] = df['metadata'].apply(json.dumps)
   ```

4. **Check Arrow version:**
   ```bash
   python -c "import pyarrow; print(pyarrow.__version__)"
   # Expected: >= 15.0.2
   ```

---

## Data & Schema Issues

### Issue: "Schema validation failed"

**Symptom:**
```
SchemaError: Input DataFrame does not match expected schema
Expected columns: [id, name], Got: [id, name, extra]
```

**Causes:**
1. Upstream component produces unexpected columns
2. Component expects specific columns that don't exist
3. Column data types don't match schema definition

**Diagnosis:**
```python
# Check actual vs expected
import pandas as pd
df = pd.read_csv('input.csv')
print("Actual columns:", list(df.columns))
print("Actual dtypes:", dict(df.dtypes))

# Check component schema config
import json
with open('job.json') as f:
    job = json.load(f)
    comp = [c for c in job['components'] if c['id'] == 'my_comp'][0]
    print("Expected schema:", comp.get('schema', 'None specified'))
```

**Solutions:**
1. **Fix schema in component config:**
   ```json
   {
     "id": "my_comp",
     "type": "tMap",
     "schema": [
       {"name": "id", "type": "integer"},
       {"name": "name", "type": "string"},
       {"name": "extra", "type": "string"}
     ]
   }
   ```

2. **Add schema to upstream component:**
   ```json
   {
     "id": "file_input",
     "type": "tFileInputDelimited",
     "schema": [
       {"name": "id", "type": "integer", "precision": 10},
       {"name": "name", "type": "string", "length": 100}
     ]
   }
   ```

3. **Disable strict validation:**
   ```json
   {
     "id": "my_comp",
     "config": {
       "validate_schema": false
     }
   }
   ```

### Issue: "Data type conversion failed"

**Symptom:**
```
ValueError: Unable to parse string "2026-13-45" as datetime
```

**Causes:**
1. Invalid date/time format
2. Type mismatch (string to int conversion on non-numeric)
3. Null/None value in required field
4. Locale-specific formatting (e.g., European dates)

**Solutions:**
1. **Fix data source** to ensure valid values

2. **Handle conversion errors:**
   ```python
   # Before conversion, clean data
   df['date_col'] = pd.to_datetime(
       df['date_col'],
       format='%Y-%m-%d',
       errors='coerce'  # Invalid → NaT
   )
   ```

3. **Specify date format in config:**
   ```json
   {
     "id": "file_input",
     "type": "tFileInputDelimited",
     "config": {
       "date_format": "yyyy-MM-dd",
       "decimal_separator": ",",
       "thousands_separator": "."
     }
   }
   ```

### Issue: "Unexpected data types in output"

**Symptom:**
```
Expected int64, got object
Column should be string but contains bytes
```

**Solutions:**
1. **Force type conversion:**
   ```python
   df['col'] = df['col'].astype('int64')
   ```

2. **Check for non-printable characters:**
   ```python
   df['col'] = df['col'].str.replace(r'[\x00-\x1f\x7f-\x9f]', '', regex=True)
   ```

3. **Trim whitespace:**
   ```python
   df['col'] = df['col'].str.strip()
   ```

---

## Expression Resolution Issues

### Issue: "${context.var} not being replaced"

**Symptom:**
```
Input file: "${input_file}"
// Executes literally, not substituted
```

**Causes:**
1. Context variable not defined
2. Wrong variable name format
3. Context loading failed
4. Variable scope mismatch

**Diagnosis:**
```python
# Check loaded context
from src.v1.engine.context_manager import ContextManager
ctx_mgr = ContextManager()
print("Context vars:", ctx_mgr.context)

# Try to resolve
resolved = ctx_mgr.resolve_dict({"file": "${input_file}"})
print("Resolved:", resolved)
```

**Solutions:**
1. **Define context variable:**
   ```bash
   python src/v1/engine/engine.py job.json --context_param input_file=/path/to/file.csv
   ```

2. **Load from context file:**
   ```json
   {
     "context": {
       "file": "context.properties",
       "input_file": "default.csv"
     }
   }
   ```

3. **Fix variable name:**
   ```
   // CORRECT
   ${context.input_file}
   
   // WRONG
   ${input_file}           // Missing 'context.'
   ${context.InputFile}    // Wrong case
   ```

### Issue: "{{java}} marker appears in output"

**Symptom:**
```
Output contains: {{java:expression}}
Java code not executed
```

**Causes:**
1. Java bridge disabled or failed
2. Bridge couldn't parse expression
3. Expression evaluation timeout
4. Java error not logged

**Solutions:**
1. **Check bridge status:**
   ```python
   from src.v1.engine.java_bridge_manager import JavaBridgeManager
   mgr = JavaBridgeManager()
   print(f"Java enabled: {mgr.enabled}")
   print(f"Bridge alive: {mgr.bridge is not None and mgr.bridge.is_alive()}")
   ```

2. **Enable Java in config:**
   ```json
   {
     "java_config": {
       "enabled": true
     }
   }
   ```

3. **Simplify or convert expression:**
   Convert Java/Groovy to Python equivalent

4. **Check logs:**
   ```bash
   grep -i "java\|error\|exception" log_file.txt | head -20
   ```

---

## Performance Issues

### Issue: "Job runs slowly, memory usage high"

**Symptom:**
```
Processing takes hours
Memory usage climbs to 100%
```

**Causes:**
1. Batch mode processing entire large file at once
2. Inefficient pandas operations
3. Unused columns kept in memory
4. Excessive logging

**Solutions:**
1. **Switch to streaming mode:**
   ```json
   {
     "id": "component",
     "execution_mode": "STREAMING",
     "streaming_batch_size": 10000
   }
   ```

2. **Reduce memory footprint:**
   ```python
   # Load only needed columns
   df = pd.read_csv('file.csv', usecols=['col1', 'col2'])
   
   # Use appropriate dtypes
   df = pd.read_csv('file.csv', dtype={'id': 'int32', 'value': 'float32'})
   ```

3. **Reduce logging:**
   ```python
   logging.getLogger().setLevel(logging.WARNING)
   ```

4. **Check for inefficient operations:**
   ```python
   # SLOW: Multiple iterations
   for col in df.columns:
       df[col] = df[col].str.upper()
   
   # FAST: Vectorized
   df = df.applymap(str.upper) if isinstance(df.iloc[0, 0], str) else df
   ```

### Issue: "Java bridge slows down execution"

**Causes:**
1. Excessive {{java}} expressions (each = network call)
2. Large data serialization via Arrow
3. Java process startup overhead

**Solutions:**
1. **Batch Java operations:**
   ```groovy
   // SLOW: Called per row
   myFunction(col1, col2)
   
   // FAST: Called once for batch
   batchProcess(dataframe)
   ```

2. **Use Python for simple operations:**
   ```python
   # Instead of: "{{java:'hello'.toUpperCase()}}"
   # Use: Python equivalent in tJavaRow or custom component
   df['col'] = df['col'].str.upper()
   ```

3. **Disable Java if not needed:**
   ```json
   {"java_config": {"enabled": false}}
   ```

---

## File I/O Issues

### Issue: "File not found"

**Symptom:**
```
FileOperationError: Cannot open '/path/to/file.csv': No such file
```

**Causes:**
1. Path doesn't exist
2. Wrong working directory
3. Relative path issues
4. Permission denied

**Diagnosis:**
```bash
# Check if file exists
ls -la /path/to/file.csv

# Check working directory
pwd

# Check permissions
ls -ld /path/to/
```

**Solutions:**
1. **Use absolute paths:**
   ```json
   {
     "file_path": "/absolute/path/to/file.csv"
   }
   ```

2. **Use context variables for portability:**
   ```json
   {
     "file_path": "${context.input_dir}/file.csv"
   }
   ```
   ```bash
   python engine.py job.json --context_param input_dir=/data
   ```

3. **Create missing directories:**
   ```bash
   mkdir -p /path/to/directory
   ```

### Issue: "Permission denied writing file"

**Symptom:**
```
FileOperationError: Permission denied writing to output.csv
```

**Causes:**
1. No write permission on directory
2. File locked by another process
3. Read-only filesystem

**Solutions:**
```bash
# Check permissions
ls -l output.csv
# Add write permission
chmod 644 output.csv

# Check if file locked
lsof output.csv

# Kill process holding lock
kill -9 <PID>
```

### Issue: "Encoding errors reading file"

**Symptom:**
```
UnicodeDecodeError: 'utf-8' codec can't decode byte 0xff
```

**Causes:**
1. File has different encoding (UTF-16, Latin-1, etc.)
2. File has BOM (Byte Order Mark)
3. Corrupted file

**Solutions:**
1. **Specify encoding:**
   ```json
   {
     "id": "file_input",
     "type": "tFileInputDelimited",
     "config": {
       "encoding": "latin-1"  // or iso-8859-1, utf-16, etc.
     }
   }
   ```

2. **Detect encoding:**
   ```bash
   file -i input.csv
   chardet input.csv
   ```

3. **Fix file encoding:**
   ```bash
   iconv -f UTF-16 -t UTF-8 input.csv > output.csv
   ```

---

## Context & GlobalMap Issues

### Issue: "NB_LINE not updated"

**Symptom:**
```
GlobalMap['NB_LINE'] = 0
Expected: 1000 rows processed
```

**Causes:**
1. Component forgot to call `_update_global_map()`
2. Component is rejecting all rows
3. Input is empty

**Solutions:**
In your component's `_process()`:
```python
def _process(self, input_data):
    # ... processing ...
    
    # MUST call this
    self._update_global_map(
        nb_line=len(input_data),
        nb_line_ok=len(output_df),
        nb_line_reject=len(reject_df)
    )
    
    return {
        'main': output_df,
        'reject': reject_df,
        'stats': {...}
    }
```

### Issue: "Custom context variable lost between components"

**Symptom:**
```
Component A sets: context.my_var = "value"
Component B reads: context.my_var = null
```

**Causes:**
1. Variable not persisted to GlobalMap
2. Component B in different subjob
3. Scope issue

**Solutions:**
1. **Persist to GlobalMap:**
   ```python
   # In component A
   self.global_map['my_var'] = 'value'
   
   # In component B
   my_var = self.global_map.get('my_var')
   ```

2. **Check subjob boundaries:**
   ```json
   {
     "flows": [
       {
         "source": "comp_a",
         "target": "comp_b",
         "trigger": "OnComponentOk"
       }
     ]
   }
   ```

---

## Testing & Coverage Issues

### Issue: "Test fails: coverage < 95%"

**Symptom:**
```
FAIL: Component coverage 87.5% < 95.0%
```

**Diagnosis:**
```bash
pytest tests/my_test.py --cov=src --cov-report=term-missing
# Shows which lines lack coverage
```

**Solutions:**
1. **Add test for uncovered lines:**
   ```python
   def test_edge_case_handling(self):
       """Test handling of edge cases"""
       # ... test code ...
   ```

2. **Remove dead code:**
   ```python
   # If code is unreachable, delete it or refactor
   ```

3. **Mark unreachable code:**
   ```python
   if False:  # pragma: no cover
       never_reached()
   ```

### Issue: "Test import fails"

**Symptom:**
```
ImportError: cannot import name 'MyComponent'
```

**Causes:**
1. Component not exported in __init__.py
2. Wrong import path
3. Circular import

**Solutions:**
```python
# WRONG
from src.v1.engine.components.my_component import MyComponent

# RIGHT (check __init__.py)
from src.v1.engine.components.category import MyComponent

# Or direct
from src.v1.engine.components.category.my_component import MyComponent
```

### Issue: "Java tests skipped"

**Symptom:**
```
SKIPPED 5 tests (java marker)
```

**Causes:**
1. JVM not available
2. Tests not run with `-m java`

**Solutions:**
```bash
# Run ALL tests including Java
pytest -m "not oracle" -v

# Run ONLY Java tests
pytest -m java -v

# Check Java availability
java -version
```

---

## Still Stuck?

1. **Check project logs:**
   ```bash
   tail -f execution.log
   ```

2. **Add verbose output:**
   ```bash
   python -m src.converters.talend_to_v1.converter job.item output.json -v
   python src/v1/engine/engine.py job.json -v
   ```

3. **Enable full debug logging:**
   ```python
   logging.basicConfig(level=logging.DEBUG)
   ```

4. **Check similar issues:**
   Look at related working components and compare

5. **Minimal reproduction:**
   Create smallest possible test case that reproduces issue

6. **Ask for help:**
   File issue with logs, stack trace, and reproduction steps

---

## Common Error Messages Quick Reference

| Error | Likely Cause | Quick Fix |
|-------|--------------|-----------|
| `KeyError: 'component' not in COMPONENT_REGISTRY` | Not registered | Add to component_registry.py |
| `FileNotFoundError: input.csv` | Wrong path | Use absolute paths or context vars |
| `SchemaError: Column 'X' not found` | Column missing | Check upstream output or fix schema |
| `JavaBridgeError: Bridge not started` | JVM issues | Check Java 11+ and JAR file |
| `TypeError: unsupported operand types` | Type mismatch | Convert/coerce data types |
| `UnicodeDecodeError: utf-8 codec` | Wrong encoding | Specify encoding in file_input config |
| `ComponentExecutionError: Component failed` | Logic error | Enable debug logging, check inputs |
| `Coverage < 95%` | Untested code | Add test cases for uncovered lines |

