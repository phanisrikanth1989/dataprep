---
phase: 02-java-bridge-reliability
reviewed: 2026-04-14T21:45:00Z
depth: standard
files_reviewed: 15
files_reviewed_list:
  - src/converters/talend_to_v1/components/transform/map.py
  - src/converters/talend_to_v1/components/transform/xml_map.py
  - src/v1/engine/base_component.py
  - src/v1/engine/java_bridge_manager.py
  - src/v1/java_bridge/__init__.py
  - src/v1/java_bridge/bridge.py
  - src/v1/java_bridge/type_mapping.py
  - src/v1/java_bridge/java/pom.xml
  - src/v1/java_bridge/java/src/main/java/com/citi/gru/etl/ArrowSerializer.java
  - src/v1/java_bridge/java/src/main/java/com/citi/gru/etl/JavaBridge.java
  - src/v1/java_bridge/java/src/main/java/com/citi/gru/etl/RowWrapper.java
  - tests/v1/engine/test_bridge_type_mapping.py
  - tests/v1/engine/test_bridge.py
  - tests/v1/engine/test_bridge_integration.py
  - tests/converters/talend_to_v1/components/transform/test_map_types.py
findings:
  critical: 2
  warning: 5
  info: 4
  total: 11
status: issues_found
---

# Phase 02: Code Review Report

**Reviewed:** 2026-04-14T21:45:00Z
**Depth:** standard
**Files Reviewed:** 15
**Status:** issues_found

## Summary

Reviewed the Java bridge layer (Python client, Java server, Arrow serialization, type mapping), the tMap/tXMLMap converters, the engine base component, and associated test suites. The codebase is well-structured with clear separation of concerns -- the 7-type contract between converter and bridge layers is cleanly enforced, tests are comprehensive, and the BRDG-06 compiled script caching fix is correctly implemented.

Key concerns: (1) Arrow resource leaks in Java due to missing try-finally/try-with-resources around VectorSchemaRoot and ArrowStreamReader objects, (2) a string coercion bug in bridge.py that can corrupt data containing the substring "nan", (3) missing `writer.start()` calls before `writer.writeBatch()` in JavaBridge.java, (4) streaming mode silently drops named flows beyond `main` and `reject`, and (5) the Groovy expression evaluation paths constitute an arbitrary code execution surface with no sandboxing.

## Critical Issues

### CR-01: Arrow resource leak on exception in executeJavaRow and executeTMapPreprocessing

**File:** `src/v1/java_bridge/java/src/main/java/com/citi/gru/etl/JavaBridge.java:174-255`
**Issue:** `ArrowStreamReader`, `VectorSchemaRoot`, and `ArrowStreamWriter` are opened but only closed on the happy path. If any exception occurs during row processing (line 233-236 throws RuntimeException), the `inputRoot.close()`, `reader.close()`, and `outputRoot.close()` on lines 250-252 are never reached. The same pattern repeats in `executeTMapPreprocessing` (lines 359-427) and `executeCompiledTMap` (lines 565-592). Over multiple failed invocations, this leaks off-heap Arrow memory buffers from the `RootAllocator`, eventually causing `OutOfMemoryError` on the JVM side.
**Fix:** Wrap Arrow resources in try-with-resources or try-finally blocks:
```java
ByteArrayInputStream inputStream = new ByteArrayInputStream(arrowData);
try (ArrowStreamReader reader = new ArrowStreamReader(inputStream, allocator)) {
    VectorSchemaRoot inputRoot = reader.getVectorSchemaRoot();
    reader.loadNextBatch();
    // ... processing ...
    try (VectorSchemaRoot outputRoot = ArrowSerializer.createOutputRootFromData(...)) {
        ByteArrayOutputStream outputStream = new ByteArrayOutputStream();
        ArrowStreamWriter writer = new ArrowStreamWriter(outputRoot, null, outputStream);
        writer.start();
        writer.writeBatch();
        writer.close();
        return outputStream.toByteArray();
    }
}
```

### CR-02: String coercion replaces "nan" substring in legitimate data values

**File:** `src/v1/java_bridge/bridge.py:709`
**Issue:** The line `coerced_df[col_name] = coerced_df[col_name].astype(str).replace("nan", None)` uses pandas `Series.replace()` which performs exact whole-value matching by default (not substring). However, the `astype(str)` on the same line converts Python `None` and `float('nan')` to the literal string `"nan"`, then `replace("nan", None)` converts those back to `None`. The problem is that this also converts any legitimate data value that is exactly the string `"nan"` (case-sensitive) to None. More critically, when pandas CoW (Copy-on-Write) is active (as noted in project memory for pandas 3.0.1), the chained `.astype(str).replace(...)` may not behave as expected due to CoW semantics. The correct approach is to identify actual null/NaN values before string conversion and mask them afterward.
**Fix:**
```python
if col_type == "str" or col_type == "object":
    null_mask = coerced_df[col_name].isna()
    coerced_df[col_name] = coerced_df[col_name].astype(str)
    coerced_df.loc[null_mask, col_name] = None
```

## Warnings

### WR-01: Missing writer.start() before writeBatch() in Arrow serialization

**File:** `src/v1/java_bridge/java/src/main/java/com/citi/gru/etl/JavaBridge.java:246-248`
**Issue:** The `ArrowStreamWriter` is created and `writeBatch()` is called immediately without calling `writer.start()` first. The Arrow Java IPC API requires `start()` to write the schema message before any batch data. The same issue exists on line 800-802. In Arrow 15.x, `writeBatch()` may internally handle this for streaming format, but relying on this implicit behavior is fragile and will break if Arrow upgrades change the behavior. The Python-side `ipc.new_stream()` (bridge.py line 729) correctly follows the protocol.
**Fix:**
```java
ArrowStreamWriter writer = new ArrowStreamWriter(outputRoot, null, outputStream);
writer.start();
writer.writeBatch();
writer.close();
```

### WR-02: Streaming mode drops named flows beyond 'main' and 'reject'

**File:** `src/v1/engine/base_component.py:404-449`
**Issue:** The `_execute_streaming()` method only collects `main` and `reject` keys from `_process()` results. Per the docstring of `_process()` (line 217-228) and the ENG-17 fix note (line 13), components can return arbitrary named flow keys. When a multi-output component (like tMap) runs in streaming mode, any output flows beyond `main` and `reject` are silently discarded. The batch path (`_execute_batch` on line 393-402) correctly preserves all keys by passing through the full result dict.
**Fix:** Collect all keys from chunk results, not just `main` and `reject`:
```python
def _execute_streaming(self, input_data: pd.DataFrame) -> dict:
    if input_data is None:
        return self._process(None)

    chunk_size = self.config.get("chunk_size", 10000)
    flow_chunks: dict[str, list[pd.DataFrame]] = {}

    for start in range(0, len(input_data), chunk_size):
        chunk = input_data.iloc[start : start + chunk_size]
        chunk_result = self._process(chunk)

        for key, value in chunk_result.items():
            if isinstance(value, pd.DataFrame) and len(value) > 0:
                flow_chunks.setdefault(key, []).append(value)

    result = {}
    for key, chunks in flow_chunks.items():
        result[key] = pd.concat(chunks, ignore_index=True) if chunks else pd.DataFrame()

    # Ensure 'main' always exists
    if "main" not in result:
        result["main"] = pd.DataFrame()
    return result
```

### WR-03: Routine loading error silently swallowed in JavaBridgeManager

**File:** `src/v1/engine/java_bridge_manager.py:76-77`
**Issue:** When a routine fails to load (line 76), the exception is caught and logged but execution continues without raising. The job proceeds with missing routines, which will cause cryptic `MissingPropertyException` errors later when Groovy scripts try to call routine methods. The caller has no way to know that routine loading failed.
**Fix:** Either re-raise the exception to fail fast, or collect all failures and raise after the loop:
```python
failed_routines = []
for routine_class in self.routines:
    try:
        self.bridge.load_routine(routine_class)
        logger.info("[OK] Loaded: %s", routine_class)
    except Exception as e:
        logger.error("[ERROR] Failed to load %s: %s", routine_class, e)
        failed_routines.append(routine_class)
if failed_routines:
    raise JavaBridgeError(f"Failed to load routines: {failed_routines}")
```

### WR-04: TOCTOU race in port allocation for Java bridge

**File:** `src/v1/engine/java_bridge_manager.py:104-115`
**Issue:** `_find_free_port()` binds to port 0, records the port number, then closes the socket. Between closing the socket and the Java process binding to that port, another process could claim it (Time-Of-Check-to-Time-Of-Use race). This can cause intermittent startup failures ("Address already in use") that are difficult to reproduce and diagnose.
**Fix:** Pass port 0 to the Java process and have it report back the actual port it bound to (requires Java-side changes), or retry with a new port on bind failure:
```python
def start(self):
    max_retries = 3
    for attempt in range(max_retries):
        try:
            self.port = self._find_free_port()
            # ... existing start logic ...
            return
        except JavaBridgeError as e:
            if "Address already in use" in str(e) and attempt < max_retries - 1:
                logger.warning("Port %d in use, retrying...", self.port)
                continue
            raise
```

### WR-05: RootAllocator with Long.MAX_VALUE allows unbounded memory

**File:** `src/v1/java_bridge/java/src/main/java/com/citi/gru/etl/JavaBridge.java:43`
**Issue:** `new RootAllocator(Long.MAX_VALUE)` creates an Arrow buffer allocator with no memory limit. If a large DataFrame is sent through the bridge or if resources leak (see CR-01), the JVM will consume unbounded off-heap memory before crashing with an uninformative error. Setting a reasonable limit (e.g., 4GB) would provide earlier, clearer failure messages and protect the host system.
**Fix:**
```java
// 4 GB limit -- adjust based on expected workload
private static final long MAX_ALLOCATOR_BYTES = 4L * 1024 * 1024 * 1024;
private final BufferAllocator allocator = new RootAllocator(MAX_ALLOCATOR_BYTES);
```

## Info

### IN-01: Groovy execution has no sandboxing

**File:** `src/v1/java_bridge/java/src/main/java/com/citi/gru/etl/JavaBridge.java:268-278`
**Issue:** `executeOneTimeExpression` and `executeBatchOneTimeExpressions` evaluate arbitrary Groovy code with full JVM access. While this is by design (Talend expressions may need full Java capabilities), there is no sandboxing or restriction. Groovy scripts can execute `Runtime.exec()`, access the filesystem, open network connections, or call `System.exit()`. This is acceptable for a trusted ETL environment but should be documented as a security consideration if the system is ever exposed to untrusted job configurations.
**Fix:** Add a comment/documentation noting that job JSON configs must be trusted input, since expressions within them are executed with full JVM privileges.

### IN-02: inferDecimalPrecisionScale uses Math.max that inflates precision

**File:** `src/v1/java_bridge/java/src/main/java/com/citi/gru/etl/ArrowSerializer.java:272`
**Issue:** `int precision = Math.max(bd.precision(), 38);` always returns at least 38, meaning the inferred precision can never be less than 38 even when the actual BigDecimal value has lower precision. The intent appears to be a minimum of 38 (which is fine as a safety margin), but if the intent was to detect the actual precision of the data, this defeats that purpose. The method is currently unused by the main code paths (schema-driven serialization is preferred), so this is informational only.
**Fix:** If the intent is "at least 38", the code is correct but the method name `inferDecimalPrecisionScale` is misleading -- consider renaming to `defaultDecimalPrecisionScale` or adding a comment clarifying the floor behavior.

### IN-03: Duplicate backward-compatible alias in JavaBridge.java

**File:** `src/v1/java_bridge/java/src/main/java/com/citi/gru/etl/JavaBridge.java:326-331`
**Issue:** `executeBatchOneTimeExpressionsWithGlobalMap` is a one-line alias for `executeBatchOneTimeExpressions`. The Python client (bridge.py line 273) calls the alias. Since both methods exist and the alias is the only one called from Python, the non-aliased method `executeBatchOneTimeExpressions` is dead code from the Python caller's perspective. Consider consolidating to a single method name to reduce confusion.
**Fix:** Either remove the alias and update bridge.py to call the shorter name, or add a `@Deprecated` annotation to the alias with a comment indicating when it can be removed.

### IN-04: loadedRoutines uses HashMap (not thread-safe) while compiledScriptClasses uses ConcurrentHashMap

**File:** `src/v1/java_bridge/java/src/main/java/com/citi/gru/etl/JavaBridge.java:47-48`
**Issue:** `loadedRoutines` is declared as `HashMap` while `compiledScriptClasses` correctly uses `ConcurrentHashMap`. While the current usage pattern is single-threaded (routines loaded during startup, read during execution), this inconsistency could become a problem if the bridge is ever used with concurrent chunk execution. Not a current bug since routines are loaded before any concurrent access.
**Fix:** Change to `ConcurrentHashMap` for consistency:
```java
private final Map<String, Class<?>> loadedRoutines = new ConcurrentHashMap<>();
```

---

_Reviewed: 2026-04-14T21:45:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
