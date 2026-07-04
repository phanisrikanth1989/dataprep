---
phase: 02-java-bridge-reliability
fixed_at: 2026-04-14T16:21:35Z
review_path: .planning/phases/02-java-bridge-reliability/02-REVIEW.md
iteration: 1
findings_in_scope: 7
fixed: 7
skipped: 0
status: all_fixed
---

# Phase 02: Code Review Fix Report

**Fixed at:** 2026-04-14T16:21:35Z
**Source review:** .planning/phases/02-java-bridge-reliability/02-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 7
- Fixed: 7
- Skipped: 0

## Fixed Issues

### CR-01: Arrow resource leak on exception in executeJavaRow and executeTMapPreprocessing

**Files modified:** `src/v1/java_bridge/java/src/main/java/com/citi/gru/etl/JavaBridge.java`
**Commit:** 2c1f702
**Applied fix:** Wrapped Arrow resources (ArrowStreamReader, VectorSchemaRoot) in try-with-resources blocks across four methods: `executeJavaRow`, `executeTMapPreprocessing`, `executeTMapCompiled`, and `executeCompiledTMap`. Also wrapped output VectorSchemaRoot in nested try-with-resources in `executeJavaRow` and `convertTMapOutputsToArrow`. This ensures off-heap Arrow memory buffers are released even when exceptions occur during row processing. Additionally added `writer.start()` calls before `writer.writeBatch()` (WR-01) as part of the same change since the affected lines were being restructured.

### CR-02: String coercion replaces "nan" substring in legitimate data values

**Files modified:** `src/v1/java_bridge/bridge.py`
**Commit:** 080544e
**Applied fix:** Replaced the chained `.astype(str).replace("nan", None)` with a null-mask approach: capture `isna()` mask before string conversion, apply `astype(str)`, then restore `None` only for originally-null positions via `df.loc[null_mask, col_name] = None`. This preserves legitimate string values of "nan" and is compatible with pandas 3.0 CoW semantics.

### WR-01: Missing writer.start() before writeBatch() in Arrow serialization

**Files modified:** `src/v1/java_bridge/java/src/main/java/com/citi/gru/etl/JavaBridge.java`
**Commit:** 2c1f702 (committed together with CR-01)
**Applied fix:** Added `writer.start()` calls before `writer.writeBatch()` in both `executeJavaRow` (output serialization) and `convertTMapOutputsToArrow` (per-output serialization). This ensures the Arrow IPC schema message is written before batch data, following the correct Arrow streaming protocol.

### WR-02: Streaming mode drops named flows beyond 'main' and 'reject'

**Files modified:** `src/v1/engine/base_component.py`
**Commit:** 13a5985
**Applied fix:** Rewrote `_execute_streaming()` to collect all named flow keys from `_process()` results using a `dict[str, list[pd.DataFrame]]` accumulator, instead of only collecting `main` and `reject`. All keys with DataFrame values are accumulated and concatenated. A fallback ensures `main` always exists in the result. This enables multi-output components like tMap to work correctly in streaming mode.

### WR-03: Routine loading error silently swallowed in JavaBridgeManager

**Files modified:** `src/v1/engine/java_bridge_manager.py`
**Commit:** 67c43f3
**Applied fix:** Added `failed_routines` accumulator list. Each routine load failure is now logged with the exception message and the routine class is added to the list. After the loop, if any routines failed, raises `JavaBridgeError` with the list of failed routine names. This provides fail-fast behavior instead of silently proceeding with missing routines.

### WR-04: TOCTOU race in port allocation for Java bridge

**Files modified:** `src/v1/engine/java_bridge_manager.py`
**Commit:** 465f8a2
**Applied fix:** Wrapped the port allocation and bridge startup in a retry loop (max 3 attempts). If the bridge start fails with "Address already in use", the failed bridge is cleaned up and a new port is allocated for the next attempt. Non-port-race errors are raised immediately. Post-startup logic (log level sync, library validation, routine loading) was moved to a separate try block that only executes after successful startup.

### WR-05: RootAllocator with Long.MAX_VALUE allows unbounded memory

**Files modified:** `src/v1/java_bridge/java/src/main/java/com/citi/gru/etl/JavaBridge.java`
**Commit:** 164ccb1
**Applied fix:** Replaced `new RootAllocator(Long.MAX_VALUE)` with a bounded allocator using a `MAX_ALLOCATOR_BYTES` constant set to 4GB (4L * 1024 * 1024 * 1024). This provides earlier and clearer OOM error messages and protects the host system from unbounded off-heap memory growth due to resource leaks or large DataFrames.

---

_Fixed: 2026-04-14T16:21:35Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
