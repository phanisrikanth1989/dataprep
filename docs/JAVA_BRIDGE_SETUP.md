# Java Bridge Setup & Troubleshooting Guide

**Last Updated:** 2026-06-13

---

## Table of Contents

1. [What is the Java Bridge](#what-is-the-java-bridge)
2. [System Requirements](#system-requirements)
3. [Installation & Setup](#installation--setup)
4. [Configuration](#configuration)
5. [Testing the Bridge](#testing-the-bridge)
6. [Troubleshooting](#troubleshooting)
7. [Advanced Configuration](#advanced-configuration)
8. [Performance Tuning](#performance-tuning)

---

## What is the Java Bridge

The Java bridge allows DataPrep engine (Python) to execute:
- **Talend Java/Groovy expressions** (`{{java}}` markers)
- **tMap transformations** (complex field mappings)
- **tJava components** (custom Java code)
- **tJavaRow components** (row-level Java processing)
- **Talend system functions** (TalendString, TalendDate, etc.)

**Architecture:**
```
Python Engine (Py4J Client)
        ↕ (network RPC + Arrow binary)
JVM Server Process (Groovy interpreter)
        ↕
User Java/Groovy code
```

**Technology Stack:**
- **Py4J** — Python-Java RPC communication
- **Apache Arrow** — Binary data serialization
- **Groovy 3.0.21** — Dynamic expression evaluation
- **JVM 11+** — Runtime environment

---

## System Requirements

### Required

| Component | Version | Check Command |
|-----------|---------|---------------|
| Java (JDK/JRE) | 11+ | `java -version` |
| Python | 3.12+ | `python --version` |
| Maven | 3.x | `mvn --version` |
| Git | (for cloning) | `git --version` |

### Optional but Recommended

- **Memory:** 4GB+ RAM (2GB minimum for JVM)
- **Disk:** 1GB+ free space (JAR + dependencies)
- **Network:** No firewall restrictions between ports 25333-25344

### Verify Java Installation

```bash
# Check Java is on PATH
java -version
# Output: openjdk version "11.0.X" or later

# Check JVM can start
java -XmxTest  # Quick validation
# If this fails, PATH not set correctly

# Find Java location
which java        # macOS/Linux
where java        # Windows PowerShell

# Add Java to PATH if needed (Windows)
set PATH=%PATH%;C:\Program Files\Java\openjdk-11\bin

# Add Java to PATH if needed (Linux/macOS)
export PATH="/usr/lib/jvm/java-11-openjdk/bin:$PATH"
```

---

## Installation & Setup

### Step 1: Verify Python Dependencies

```bash
# Install Python dependencies (if not already installed)
pip install py4j pyarrow

# Verify installation
python -c "import py4j; import pyarrow; print('OK')"
```

### Step 2: Build Java Bridge JAR

```bash
# Navigate to Java bridge directory
cd src/v1/java_bridge/java

# Build with Maven
mvn clean package -DskipTests

# Expected output:
# [INFO] BUILD SUCCESS
# [INFO] JAR file created: target/java-bridge-with-dependencies.jar

# Verify JAR exists
ls -la target/java-bridge-with-dependencies.jar
# Should show file size ~20-30 MB
```

**If build fails:**

```bash
# Check Maven installation
mvn --version

# Check Java compiler available
javac -version

# Try verbose build
mvn clean package -DskipTests -X 2>&1 | tail -50

# Common fixes:
# 1. Clear Maven cache
rm -rf ~/.m2/repository
mvn clean package

# 2. Update Maven
brew install maven  # macOS
sudo apt-get install maven  # Linux

# 3. Set JAVA_HOME
export JAVA_HOME=/path/to/java/11
```

### Step 3: Verify Bridge Starts

```bash
# Simple Python test
python -c "
from src.v1.engine.java_bridge_manager import JavaBridgeManager
mgr = JavaBridgeManager()
mgr.start()
print('Bridge started successfully')
result = mgr.bridge.execute_expression(\"'hello'.toUpperCase()\", {})
print(f'Test result: {result}')
mgr.stop()
"

# Expected output:
# Bridge started successfully
# Test result: HELLO
```

---

## Configuration

### Basic Configuration

In your job config JSON:

```json
{
  "name": "my_job",
  "java_config": {
    "enabled": true
  },
  "components": [
    {
      "id": "map_1",
      "type": "tMap",
      "config": {
        "mapping": {
          "full_name": "first_name + ' ' + last_name"
        }
      }
    }
  ]
}
```

### Advanced Configuration

```python
# In Python code
from src.v1.engine import ETLEngine

engine = ETLEngine(
    java_enabled=True,
    java_port=25333,                    # Default Py4J port
    java_bridge_timeout=30,             # Seconds to wait for bridge
    java_bridge_max_retries=3,          # Restart attempts
    java_batches_per_call=1000,         # Expressions per RPC call
)

result = engine.run_job('job.json')
```

### Job Config Java Section

```json
{
  "java_config": {
    "enabled": true,
    "jvm_heap_size": "2g",              // Min/max JVM heap
    "jvm_options": [                    // Additional JVM flags
      "-Dfile.encoding=UTF-8",
      "-XX:+UseG1GC"
    ],
    "bridge_port": 25333,               // Py4J server port
    "bridge_timeout": 30,               // Seconds
    "debug": false                      // Enable Java debug output
  }
}
```

---

## Testing the Bridge

### Quick Sanity Checks

```bash
# Test 1: Bridge starts
python -c "
from src.v1.engine.java_bridge_manager import JavaBridgeManager
mgr = JavaBridgeManager()
mgr.start()
print('PASS: Bridge started')
mgr.stop()
"

# Test 2: Simple expression
python -c "
from src.v1.engine.java_bridge_manager import JavaBridgeManager
mgr = JavaBridgeManager()
mgr.start()
result = mgr.bridge.execute_expression(\"1 + 2\", {})
assert result == 3
print('PASS: Basic math works')
mgr.stop()
"

# Test 3: String operations
python -c "
from src.v1.engine.java_bridge_manager import JavaBridgeManager
mgr = JavaBridgeManager()
mgr.start()
result = mgr.bridge.execute_expression(\"'Hello'.toLowerCase()\", {})
assert result == 'hello'
print('PASS: String operations work')
mgr.stop()
"

# Test 4: With context variables
python -c "
from src.v1.engine.java_bridge_manager import JavaBridgeManager
mgr = JavaBridgeManager()
mgr.start()
result = mgr.bridge.execute_expression(
    'name.toUpperCase()',
    {'name': 'john'}
)
assert result == 'JOHN'
print('PASS: Context variables work')
mgr.stop()
"
```

### Run Unit Tests

```bash
# Run Java bridge unit tests
pytest tests/v1/java_bridge/ -v

# Run with Java bridge required
pytest tests/v1/java_bridge/ -m java -v

# Expected: all tests pass
```

### Run Integration Tests

```bash
# Full engine tests (includes Java bridge)
pytest tests/v1/engine/components/transform/map/ -v

# Should include tMap tests
# Look for: test_tmap_*
```

---

## Troubleshooting

### Issue: "Bridge failed to start"

**Symptom:**
```
JavaBridgeError: Failed to start Java bridge
Cannot connect to JVM
```

**Diagnosis:**

```bash
# Step 1: Check Java is installed and on PATH
java -version
# If command not found, Java not installed or not on PATH

# Step 2: Check JAR file exists
ls -la src/v1/java_bridge/java/target/java-bridge-with-dependencies.jar
# If not found, JAR not built

# Step 3: Check port availability
netstat -an | grep 25333
lsof -i :25333
# If in use, port occupied by another process

# Step 4: Check Java can run
java -jar src/v1/java_bridge/java/target/java-bridge-with-dependencies.jar --help
# If fails, JAR is corrupted or incompatible
```

**Solutions:**

1. **Install Java:**
   ```bash
   # macOS
   brew install openjdk@11
   
   # Linux (Ubuntu)
   sudo apt-get install openjdk-11-jdk
   
   # Windows
   choco install openjdk11
   # OR download from adoptopenjdk.net
   ```

2. **Add Java to PATH:**
   ```bash
   # macOS/Linux - add to ~/.bashrc or ~/.zshrc
   export PATH="/usr/libexec/java_home -v 11:$PATH"
   
   # Windows PowerShell - permanent
   setx PATH "%PATH%;C:\Program Files\Java\openjdk-11\bin"
   
   # Verify
   java -version
   ```

3. **Build JAR:**
   ```bash
   cd src/v1/java_bridge/java
   mvn clean package -DskipTests
   ```

4. **Free port 25333:**
   ```bash
   # Find process using port
   lsof -i :25333
   
   # Kill it
   kill -9 <PID>
   
   # Or use different port
   # See "Advanced Configuration"
   ```

### Issue: "No Java bridge found"

**Symptom:**
```
FileNotFoundError: [Errno 2] No such file or directory:
  'src/v1/java_bridge/java/target/java-bridge-with-dependencies.jar'
```

**Solution:**

Build the Java bridge:

```bash
cd src/v1/java_bridge/java
mvn clean package -DskipTests

# Verify it exists
ls target/java-bridge-with-dependencies.jar
```

### Issue: "Java expressions return null or incorrect value"

**Symptom:**
```
Expression: 'test'.toUpperCase()
Expected: TEST
Got: null or 'test'
```

**Causes:**
1. Expression syntax error (Groovy, not Java)
2. Class/method doesn't exist
3. Type mismatch
4. Bridge communication error

**Diagnosis:**

```python
# Enable debug logging
import logging
logging.basicConfig(level=logging.DEBUG)
logging.getLogger('src.v1.engine.java_bridge_manager').setLevel(logging.DEBUG)

# Try expression
from src.v1.engine.java_bridge_manager import JavaBridgeManager
mgr = JavaBridgeManager()
mgr.start()

try:
    result = mgr.bridge.execute_expression("'test'.toUpperCase()", {})
    print(f"Result: {result}")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()

mgr.stop()
```

**Solutions:**

1. **Check Groovy syntax (not Java):**
   ```groovy
   // GROOVY (correct)
   'test'.toUpperCase()
   value ? 'yes' : 'no'
   list.collect { it * 2 }
   
   // NOT Java primitives like:
   String result = 'test'.toUpperCase();  // Syntax error
   ```

2. **Use correct method names:**
   ```groovy
   // String methods (case-sensitive)
   'hello'.length()      // OK
   'hello'.Length()      // Error
   'hello'.size()        // OK (also works)
   
   // Check Groovy/Java docs for available methods
   ```

3. **Handle type conversions:**
   ```groovy
   // Type coercion
   (10).toString()       // int to string
   '10'.toInteger()      // string to int
   3.14 as float         // cast to type
   ```

4. **Check context variable spelling:**
   ```groovy
   // CORRECT: exact variable name
   firstName.toUpperCase()
   
   // WRONG: typo
   firstname.toUpperCase()     // Error: undefined variable
   ```

### Issue: "Bridge timeout - expressions taking too long"

**Symptom:**
```
JavaBridgeError: Bridge call timed out after 30 seconds
```

**Causes:**
1. Expression very complex
2. JVM garbage collection pause
3. Network latency
4. Infinite loop in expression

**Solutions:**

1. **Increase timeout:**
   ```python
   engine = ETLEngine(java_bridge_timeout=60)  # 60 seconds
   ```

2. **Simplify expression:**
   ```groovy
   // COMPLEX (slow)
   data.collect { row ->
       row.fields.collect { f ->
           f.value.transform()
       }
   }
   
   // SIMPLER (faster)
   data.forEach { row ->
       process(row)
   }
   ```

3. **Check for infinite loops:**
   ```groovy
   // WRONG: infinite loop
   while (true) { x = x + 1 }
   
   // RIGHT: bounded loop
   (1..10).each { print it }
   ```

4. **Profile expression performance:**
   ```python
   import time
   start = time.time()
   result = mgr.bridge.execute_expression(expr, context)
   print(f"Execution took {time.time() - start:.2f} seconds")
   ```

### Issue: "Arrow serialization fails"

**Symptom:**
```
pyarrow.lib.ArrowException: Cannot serialize DataFrame
```

**Causes:**
1. DataFrame contains complex Python objects
2. Mixed/conflicting types in column
3. Non-serializable objects (functions, etc.)

**Solutions:**

```python
# Clean DataFrame before sending to Java
import pandas as pd

# 1. Remove complex objects
df = df.drop(columns=['function_col', 'object_col'])

# 2. Ensure consistent types per column
df['amount'] = pd.to_numeric(df['amount'], errors='coerce')
df['date'] = pd.to_datetime(df['date'])

# 3. Convert everything to basic types
df = df.astype({
    'id': 'int64',
    'name': 'string',
    'value': 'float64'
})

# 4. Handle None/NaN
df = df.fillna('')  # or 0, or appropriate default

# Now pass to Java bridge
```

### Issue: "Memory error - bridge runs out of memory"

**Symptom:**
```
OutOfMemoryError: Java heap space
```

**Causes:**
1. JVM heap too small (default 1GB)
2. Large DataFrame serialization
3. Memory leak in Java code

**Solutions:**

1. **Increase JVM heap:**
   ```json
   {
     "java_config": {
       "jvm_options": [
         "-Xmx4g"  // 4GB max heap
       ]
     }
   }
   ```

2. **Process in batches:**
   ```python
   # Instead of sending entire DataFrame
   # Send in chunks
   batch_size = 10000
   for i in range(0, len(df), batch_size):
       batch = df.iloc[i:i+batch_size]
       # Process batch via Java bridge
   ```

3. **Monitor memory usage:**
   ```bash
   # Watch JVM memory
   jps -l  # List Java processes
   jstat -gc -h3 <pid> 1000  # Monitor every 1 second
   ```

### Issue: "Bridge crashes mysteriously"

**Symptom:**
```
Py4J backend is dead. Trying to reconnect.
JavaBridgeError: Lost connection to Java bridge
```

**Causes:**
1. JVM process crashed (OOM, exception)
2. System killed process (ulimit exceeded)
3. Network interface failure

**Diagnosis:**

```bash
# Check if Java process running
jps -l

# Check system logs (Linux)
dmesg | tail -20
journalctl -n 50

# Check if OOM killed process
grep -i "out of memory" /var/log/messages

# Check ulimits
ulimit -a
```

**Solutions:**

1. **Enable auto-restart:**
   ```python
   mgr = JavaBridgeManager(auto_restart=True, max_restart_attempts=3)
   ```

2. **Increase system resource limits:**
   ```bash
   # Increase max processes
   ulimit -u 2048
   
   # Increase file descriptors
   ulimit -n 4096
   
   # Make permanent (Linux) - edit /etc/security/limits.conf
   ```

3. **Monitor JVM health:**
   ```python
   if not mgr.bridge.is_alive():
       print("Bridge dead, restarting...")
       mgr.restart()
   ```

---

## Advanced Configuration

### Custom Groovy Functions

Create custom functions in Java bridge:

```java
// src/v1/java_bridge/java/src/main/java/com/citi/gru/etl/CustomFunctions.java
public class CustomFunctions {
    public static String myFunction(String input) {
        return input.toUpperCase() + "_CUSTOM";
    }
}
```

Use in expressions:

```groovy
CustomFunctions.myFunction('hello')  // Returns: HELLO_CUSTOM
```

### Multiple Java Bridge Instances

For parallel processing:

```python
from src.v1.engine.java_bridge_manager import JavaBridgeManager

mgr1 = JavaBridgeManager(port=25333)
mgr2 = JavaBridgeManager(port=25334)
mgr3 = JavaBridgeManager(port=25335)

mgr1.start()
mgr2.start()
mgr3.start()

# Use in parallel...

mgr1.stop()
mgr2.stop()
mgr3.stop()
```

### Custom JVM Options

```json
{
  "java_config": {
    "jvm_options": [
      "-Xmx4g",                           // Heap size
      "-XX:+UseG1GC",                     // Garbage collector
      "-XX:MaxGCPauseMillis=200",        // GC pause time
      "-Dfile.encoding=UTF-8",            // File encoding
      "-Djava.net.preferIPv4Stack=true"  // Network preference
    ]
  }
}
```

---

## Performance Tuning

### Batch Optimization

```python
# Send multiple expressions in one RPC call
expressions = [
    "'hello'.toUpperCase()",
    "10 + 20",
    "'world'.length()"
]

# More efficient than individual calls
results = mgr.bridge.batch_execute(expressions)
```

### Connection Pooling

```python
# Reuse bridge connection
mgr = JavaBridgeManager()
mgr.start()

for batch in data_batches:
    result = mgr.bridge.process_batch(batch)

mgr.stop()
```

### Minimize Data Transfer

```groovy
// Process data in Java, return only results
// NOT: send entire DataFrame, transform in Python, send back

// Instead:
myDataFrame
    .collect { row -> transform(row) }
    .filter { it.isValid }
```

---

## Monitoring & Debugging

### Enable Bridge Logging

```python
import logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(name)s] %(message)s'
)

# Now all bridge communication logged
```

### Check Bridge Health

```python
mgr = JavaBridgeManager()
mgr.start()

print(f"Bridge alive: {mgr.bridge.is_alive()}")
print(f"Port: {mgr.port}")
print(f"Gateway: {mgr.bridge.gateway}")

# Test with known expression
result = mgr.bridge.execute_expression("1 + 1", {})
print(f"Bridge responsive: {result == 2}")

mgr.stop()
```

### Capture Bridge Output

```bash
# Redirect JVM stdout/stderr
java -jar target/java-bridge-with-dependencies.jar \
    > java_bridge.log 2>&1 &

# Monitor in real-time
tail -f java_bridge.log
```

---

## Checklist: Bridge Setup Complete

- [ ] Java 11+ installed and on PATH
- [ ] Python 3.12+ installed
- [ ] py4j and pyarrow packages installed
- [ ] Maven installed and working
- [ ] Java bridge JAR built (`mvn clean package`)
- [ ] JAR file exists (check filesize ~20-30 MB)
- [ ] Bridge starts successfully
- [ ] Simple expressions evaluate correctly
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] No port conflicts (25333 available)
- [ ] No firewall blocks Java

---

## Next Steps

1. **Test basic functionality:** Run quick sanity checks above
2. **Run test suite:** `pytest tests/v1/java_bridge/ -v`
3. **Create first pipeline:** Use tMap component with Java expressions
4. **Monitor performance:** Watch memory and execution time
5. **Troubleshoot as needed:** Use diagnosis steps for specific issues

For more help, see TROUBLESHOOTING.md or check bridge logs in depth.
