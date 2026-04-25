---
phase: manager-commits-javabridge
reviewed: 2026-04-25T00:00:00Z
depth: deep
files_reviewed: 1
files_reviewed_list:
  - src/v1/java_bridge/java/src/main/java/com/citi/gru/etl/JavaBridge.java
commit_reviewed: 851195f
findings:
  critical: 0
  warning: 3
  info: 5
  total: 8
status: issues_found
---

# Code Review: JavaBridge.java refactor (commit 851195f)

**Reviewed:** 2026-04-25
**Depth:** deep
**Files Reviewed:** 1
**Status:** issues_found (no regressions; secondary gaps surfaced)

## Summary

The diff is **126 lines changed, but materially almost entirely cosmetic**: javadoc reflow, parameter alignment, method-signature wrapping, and one extracted Closure formatting. The single behavioural change is in `convertTMapOutputsToArrow` (lines 859 and 868) where two local `HashMap` instances are switched to `LinkedHashMap`:

- `Map<String, String> schema = new LinkedHashMap<>();`  (was `HashMap`)
- `Map<String, Object[]> columnData = new LinkedHashMap<>();`  (was `HashMap`)

Both maps are populated in declared-column order (the `for (String colName : columnNames)` and `for (int colIdx = 0; ...)` loops drive insertion in `outputSchemas[outputName]` order). The downstream consumer `ArrowSerializer.createOutputRootFromData` iterates `schema.entrySet()` to assemble Arrow fields, so the change is **load-bearing**: it converts column ordering from "JVM HashMap hash-bucket order" (effectively random across JVMs / map sizes) into "schema-declared order" — which is what Talend feature parity requires.

I traced every prior tMap correctness fix (Phase 5 / 5.1 / 5.2) and verified each is preserved. There are no critical regressions. There are however three warnings worth addressing because the fix as written **does not fully close the column-ordering bug** at the API boundary, plus a few smaller items.

## Phase 5 / 5.1 / 5.2 regression check

| Prior fix | Status | Evidence |
| --- | --- | --- |
| Phase 5.1: `extractTypedValue` schema-driven Arrow conversion (12 types) | PRESERVED | Lines 766-797. Method body identical to pre-refactor; all 12 type branches intact (VarChar -> String, BigInt/Int/Float8/Float4/SmallInt/TinyInt, Bit -> bool, TimeStampNano, Decimal, Decimal256, Object fallback). Null handling at 767-769 unchanged. |
| Phase 5.1: `buildRowWrapper` Groovy closure exposed in tMap binding | PRESERVED | Lines 743-752 (in `buildTMapBinding`). Closure body identical, only whitespace reflow. The closure still routes to `buildArrowRowWrapper(root, rowIdx, tblName)` which uses `extractTypedValue`. |
| Phase 5.1: Compiled tMap script execution caches Class (not instance) | PRESERVED | Lines 542-548 (`compileTMapScript`) and 591-593 (`executeCompiledTMap`). `meta.scriptClass.getDeclaredConstructor().newInstance()` creates a fresh Script per chunk; binding rebuilt via `buildTMapBinding` each call. No shared mutable Script instance. |
| Phase 5.2: RELOAD_AT_EACH_ROW per-row binding (no double filter) | PRESERVED | The Java side is the substrate; per-row reload is implemented in Python and the compiled Groovy. The Java surface that supports it — `buildTMapBinding` exposing `inputRoot`, `rowCount`, `outputSchemas`, `outputTypes`, `buildRowWrapper` closure, `context`, `globalMap` — is unchanged in semantics. No filter or join logic exists on the Java side that could double-apply. |
| Phase 5.2: row context passed to per-row lookup expression | PRESERVED | `buildArrowRowWrapper` (807-827) builds a fresh RowWrapper per `rowIdx` with both `tableName.colName` and unprefixed-`colName` keys — same as before. The closure at 743-752 calls this per script-driven invocation, so per-row context is intact. |
| Phase 5.2: typed (not stringified) keys for lookup | PRESERVED | `extractTypedValue` returns native Java types (Long, Integer, Double, Boolean, BigDecimal, java.util.Date), not stringified. The `else` fallback at 793-796 still does `raw.toString()` for unknown vector types — unchanged. |
| Phase 5.2: column alignment between input and output | PRESERVED + IMPROVED | `convertTMapOutputsToArrow` now uses `LinkedHashMap` (lines 859, 868) so column order in the emitted Arrow schema matches `outputSchemas[outputName]` exactly. This is the stated purpose of the commit and it is correctly implemented for the cached/compiled tMap path. |
| Compile-once execute-many caching lifecycle | PRESERVED | `compiledScriptClasses` is still a `ConcurrentHashMap<String, CachedTMapMeta>` (line 64). `compileTMapScript` puts; `executeCompiledTMap` gets and throws `IllegalArgumentException` if absent (570-575). No `remove`/eviction was added or removed. |
| `{{ERROR}}` exception convention | PRESERVED | `executeBatchOneTimeExpressions` at lines 322-326 still catches Exception and stores `"{{ERROR}}" + e.getMessage()`. Other call sites (`executeJavaRow`, `executeTMapPreprocessing`, `executeTMapCompiled`, `executeCompiledTMap`) still propagate exceptions to Python via Py4J — same convention as before. |
| Decimal/BigDecimal fidelity | PRESERVED | `extractTypedValue` lines 789-792 still uses `((DecimalVector) vec).getObject(rowIndex)` and `((Decimal256Vector) vec).getObject(rowIndex)`, which return `BigDecimal`. No silent double conversion introduced. `ArrowSerializer.createVectorForType` (line 174-176) creates a `DecimalVector(38, 18)` for the BigDecimal type — unchanged. |
| Date/TimeStamp handling | PRESERVED with PRE-EXISTING CAVEAT | Lines 786-788: `TimeStampNanoVector` -> `new java.util.Date(nanos / 1_000_000)`. This truncates sub-millisecond precision — pre-existing behaviour, not introduced by this commit. Flagged separately as JB-WR-03. |

**Verdict: zero regressions vs Phase 5 / 5.1 / 5.2.** All prior fixes are intact. The refactor is safe to merge from a regression perspective.

## Critical Issues

None.

## Warnings

### JB-WR-01: Column ordering fix is incomplete — `executeJavaRow` still uses `HashMap` for output

**File:** `src/v1/java_bridge/java/src/main/java/com/citi/gru/etl/JavaBridge.java:192-195`
**Issue:** The commit fixes column ordering only inside `convertTMapOutputsToArrow` (the tMap path). The `executeJavaRow` path still uses `HashMap` for `outputArrays` and depends on whatever ordering the `outputSchema` Map argument has when iterated.

```java
Map<String, Object[]> outputArrays = new HashMap<>();
for (String colName : outputSchema.keySet()) {
    outputArrays.put(colName, new Object[rowCount]);
}
```

When `ArrowSerializer.createOutputRootFromData(allocator, outputArrays, outputSchema)` iterates `outputSchema.entrySet()` (ArrowSerializer.java:125), the field order is whatever Py4J handed us. Py4J's default conversion of a Python `dict` is `java.util.HashMap`, so `tJavaRow` outputs can suffer the same column-shuffling bug the commit set out to fix for tMap. If the team intent is "tMap output columns follow declared schema order", the same intent presumably applies to tJavaRow.

**Fix:** Make the output map a `LinkedHashMap` and iterate the schema in a deterministic order. Since the schema map itself may already be a `HashMap` from Py4J, copy it into a `LinkedHashMap` ordered by something stable (e.g. the order of `inputRoot.getFieldVectors()` for pass-through columns, or a separate `List<String>` parameter for declared output column order).

```java
// Defensive: copy outgoing schema into LinkedHashMap so column order is deterministic.
Map<String, String> orderedSchema = new LinkedHashMap<>(outputSchema);
Map<String, Object[]> outputArrays = new LinkedHashMap<>();
for (String colName : orderedSchema.keySet()) {
    outputArrays.put(colName, new Object[rowCount]);
}
// ... later ...
try (VectorSchemaRoot outputRoot = ArrowSerializer.createOutputRootFromData(
        allocator, outputArrays, orderedSchema)) { ... }
```

A more robust fix is to change the public API to take `List<String> columnOrder` plus `Map<String, String> outputSchema` and iterate the list — making the contract explicit.

### JB-WR-02: Mutable bridge state (`context`, `globalMap`, `loadedRoutines`) is not thread-safe

**File:** `src/v1/java_bridge/java/src/main/java/com/citi/gru/etl/JavaBridge.java:50-53, 178-179, 277, 305-306, 365-366, 470-471, 577-578, 633-637`
**Issue:** Py4J `GatewayServer` services callbacks on a thread pool (default 4 worker threads). The bridge instance has these mutable members:

- `private Map<String, Object> context = new HashMap<>();` (line 50)
- `private Map<String, Object> globalMap = new HashMap<>();` (line 51)
- `private final Map<String, Class<?>> loadedRoutines = new HashMap<>();` (line 53)

Every public method does `this.context.putAll(contextVars); this.globalMap.putAll(globalMapVars);` at entry. Concurrent `putAll` on a `HashMap` from multiple Py4J threads can cause:

- Lost writes / structural map corruption (HashMap is documented unsafe under concurrent structural modification — can produce infinite loops on resize in rare cases, although less likely in Java 8+).
- Stale reads inside `addRoutinesToBinding` or `buildTMapBinding` (binding sees a partially-updated context).
- ConcurrentModificationException if iteration races with put.

`compiledScriptClasses` is correctly a `ConcurrentHashMap` (line 64) — so the maintainer is aware of the issue, but applied it inconsistently.

**Fix:** Either
1. Convert the three maps to `ConcurrentHashMap` (cheapest fix, but `addRoutinesToBinding` snapshot iteration on line 715 already needs a stable view), OR
2. Add a single `synchronized` block around the "merge incoming vars + build binding" prelude in each public entry point, OR
3. Use a per-call `Map` snapshot pattern: don't mutate `this.context`/`this.globalMap` at all; build a fresh per-call map for each binding by merging the caller's vars with the bridge's stored values under a short lock.

Option 3 is the cleanest and matches the design principle that "context and globalMap are synchronised bi-directionally with the Python side at every call boundary" (javadoc lines 27-28). A long-lived mutable global is unnecessary if Python is the source of truth.

Pre-existing issue (not introduced by this commit), but worth flagging in this review since the bridge is now explicitly relying on "truly parallel chunk execution" (BRDG-06 javadoc, line 62-63).

### JB-WR-03: `TimeStampNanoVector` -> `new java.util.Date(nanos / 1_000_000)` silently truncates sub-millisecond precision

**File:** `src/v1/java_bridge/java/src/main/java/com/citi/gru/etl/JavaBridge.java:786-788`
**Issue:**

```java
} else if (vec instanceof TimeStampNanoVector) {
    long nanos = ((TimeStampNanoVector) vec).get(rowIndex);
    return new java.util.Date(nanos / 1_000_000);
}
```

`java.util.Date` has millisecond resolution; integer division by 1,000,000 silently drops nanoseconds. Talend / pandas timestamps in financial data can have sub-millisecond resolution (microseconds especially). This is pre-existing (not in the diff) but it sits inside `extractTypedValue` which is the main typed-conversion entry point that Phase 5.1 reinforced.

**Fix:** Return a `java.time.Instant` (which is nanosecond-capable) and document the change to the Groovy script contract, or use `java.sql.Timestamp` whose `setNanos()` retains nanos:

```java
} else if (vec instanceof TimeStampNanoVector) {
    long nanos = ((TimeStampNanoVector) vec).get(rowIndex);
    java.sql.Timestamp ts = new java.sql.Timestamp(nanos / 1_000_000);
    ts.setNanos((int) (nanos % 1_000_000_000));
    return ts;
}
```

Also note: there is no branch for `TimeStampMicroVector`, `TimeStampMilliVector`, or `TimeStampSecVector`. If Python ever sends timestamps with non-nano resolution they fall into the `else` branch on line 793 and are stringified — which would be a silent type corruption. Flag for consideration.

## Info

### JB-IN-01: Routine namespace map in `addRoutinesToBinding` rebuilds per binding

**File:** `src/v1/java_bridge/java/src/main/java/com/citi/gru/etl/JavaBridge.java:714-720`
**Issue:** `addRoutinesToBinding` is called from at least 6 sites (executeJavaRow row loop on line 233, `executeOneTimeExpression`, `executeBatchOneTimeExpressions`, `executeTMapPreprocessing` row loop on line 419, `compileTMapScript`, `buildTMapBinding`). Each call does `new HashMap<>(loadedRoutines)`. For row-loop callers this is a per-row allocation. For 1M rows with 50 routines this is 50M Map.Entry instances on the young gen.

**Fix:** Cache an immutable view of `loadedRoutines` (rebuild only when `loadRoutine` is called) and reuse:

```java
private volatile Map<String, Class<?>> routinesNamespaceCache = Collections.emptyMap();

public void loadRoutine(String className) throws Exception {
    Class<?> routineClass = Class.forName(className);
    String simpleName = routineClass.getSimpleName();
    loadedRoutines.put(simpleName, routineClass);
    this.routinesNamespaceCache = Collections.unmodifiableMap(new HashMap<>(loadedRoutines));
    logger.info("[JavaBridge] Loaded routine: " + simpleName + " (" + className + ")");
}

private void addRoutinesToBinding(Binding binding) {
    for (Map.Entry<String, Class<?>> entry : loadedRoutines.entrySet()) {
        binding.setVariable(entry.getKey(), entry.getValue());
    }
    binding.setVariable("routines", routinesNamespaceCache);
}
```

Performance, but worth filing — and out-of-scope for this commit per v1 review rules.

### JB-IN-02: No eviction / lifecycle for `compiledScriptClasses`

**File:** `src/v1/java_bridge/java/src/main/java/com/citi/gru/etl/JavaBridge.java:64`
**Issue:** `compiledScriptClasses` grows monotonically. Each entry holds a `Class<? extends Script>` — Groovy compiled classes are loaded by a `GroovyClassLoader` and pin metaspace until the loader is released. For a long-lived bridge process running 1200+ jobs over its lifetime, with each tMap component generating a unique class, metaspace can fill (`OutOfMemoryError: Metaspace`).

**Fix:** Add a `releaseComponent(String componentId)` method callable from Python at job teardown that does `compiledScriptClasses.remove(componentId)` and (if possible) closes the GroovyShell that produced it. Out of scope for this commit but worth tracking.

### JB-IN-03: `executeOneTimeExpression` allocates a fresh `GroovyShell` per call

**File:** `src/v1/java_bridge/java/src/main/java/com/citi/gru/etl/JavaBridge.java:284-285`
**Issue:**

```java
GroovyShell shell = new GroovyShell(binding);
return shell.evaluate(expression);
```

Each call instantiates a new GroovyShell + classloader + parses + discards. Same in `executeBatchOneTimeExpressions` (313). The class-level `groovyShell` field set in the constructor (line 52) is never used. Either reuse `this.groovyShell` (with a fresh binding per call) or remove the field. Out of scope for this commit.

### JB-IN-04: Commit message typo

**File:** Commit `851195f` message
**Issue:** "produe" should be "produce". Cosmetic only.

### JB-IN-05: 4 GB allocator cap is a bare magic number

**File:** `src/v1/java_bridge/java/src/main/java/com/citi/gru/etl/JavaBridge.java:48-49`
**Issue:** The 4 GB Arrow allocator cap is hardcoded. For larger production jobs (the 1200+ Talend jobs include multi-GB datasets) this can become a hard ceiling at `OutOfMemoryError`. Should be configurable via a system property similar to `py4j.port`:

```java
private static final long MAX_ALLOCATOR_BYTES = Long.parseLong(
    System.getProperty("javabridge.allocator.max.bytes",
                       String.valueOf(4L * 1024 * 1024 * 1024)));
```

Pre-existing, not in diff, INFO only.

---

_Reviewed: 2026-04-25_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
_Commit: 851195f_
