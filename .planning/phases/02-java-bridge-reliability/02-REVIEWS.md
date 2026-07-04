---
phase: 2
reviewers: [gemini]
reviewed_at: 2026-04-14T20:30:00Z
plans_reviewed: [02-01-PLAN.md, 02-02-PLAN.md, 02-03-PLAN.md, 02-04-PLAN.md]
---

# Cross-AI Plan Review -- Phase 2

## Gemini Review

# Phase 2: Java Bridge Reliability - Plan Review

## Summary
The proposed plans for Phase 2 provide a comprehensive and surgical rewrite of the Python-Java bridge. By moving from data-inference to a schema-driven serialization model and enforcing a strict 7-type contract between Python and Java, the plans directly address the root causes of data corruption and serialization failures. The architecture for state synchronization (automatic sync after every call) and the performance fix for compiled scripts (caching classes instead of instances) are well-reasoned and align with production-grade engineering standards.

## Strengths
- **Strict Type Contract:** Establishing exactly 7 Python type strings as the bridge API's "language" simplifies both sides and forces the resolution of converter-side bugs (D-05a).
- **Schema-Driven Serialization:** Replacing the "guess-from-first-non-null-value" approach with explicit schema mapping (BRDG-02) is the single most important fix for production reliability.
- **Robust Synchronization:** The `_call_java_with_sync` wrapper pattern ensures `_sync_from_java()` is never forgotten, solving the state divergence issue (BRDG-03) by design.
- **Maintainable Java Architecture:** Decomposing the 42KB `JavaBridge.java` and extracting `ArrowSerializer` is a significant improvement for long-term maintainability (D-17).
- **Concurrency Fix:** The transition to caching `Script` classes rather than instances in the compiled script cache correctly solves the `synchronized` bottleneck (BRDG-06) for parallel chunk processing.
- **Comprehensive Testing:** The multi-layered testing strategy -- unit tests with mocks (Plan 03) and integration tests with a real JVM covering all 12 Talend data types (Plan 04) -- provides high confidence.

## Concerns

- **Decimal Precision/Scale Mapping (MEDIUM):**
  - **Issue:** While `pa.decimal128(38, 18)` is a safe default, Talend jobs often rely on specific precision/scale.
  - **Risk:** If the component config's `length` (precision) and `precision` (scale) are not consistently passed to the bridge, data truncation or overflow may occur.
  - **Mitigation:** Plan 01 includes `extract_precision_map`, but ensure that all bridge callers (especially `tMap` and `tJavaRow`) correctly retrieve and pass this metadata.

- **JVM Startup Race Conditions (LOW):**
  - **Issue:** Relying on `time.sleep(2)` and retry loops for JVM startup can be brittle on high-load CI/CD runners.
  - **Mitigation:** The plan to use exponential backoff and a configurable timeout is a good improvement, but the integration tests should specifically verify the "fail-fast" behavior on timeout.

- **Maven Dependency (LOW):**
  - **Issue:** The research identified that `mvn` is missing from the environment.
  - **Mitigation:** Plan 04 correctly includes a task to install Maven via Homebrew. This is a necessary prerequisite for updating the Py4J version in the JAR.

## Suggestions
- **Decimal Metadata Verification:** In the `TestTypeRoundTrip` integration tests (Plan 04), include a specific test case for a `Decimal` type with non-default precision (e.g., `(10, 2)`) to verify that the precision/scale metadata is correctly respected by the bridge.
- **Bridge Error Diagnostics:** In the `JavaBridgeError` raised during failures, ensure the message includes the last 10 lines of the Java side's logger output if possible, as this significantly speeds up debugging of JVM-side crashes.
- **Explicit Schema Defaulting:** In `bridge.py`, if a component passes an incomplete schema (e.g., missing a column), the bridge should explicitly log a warning and default to `str` rather than crashing, to maintain the "fail-fast but informative" philosophy.

## Risk Assessment
**Overall Risk: LOW**

The risk is low because the "full rewrite" approach replaces a complex, buggy implementation with a simpler, contract-first design. The dependencies (Py4J 0.10.9.9 and Arrow 15.0.2) are stable, and the research phase has correctly identified the version compatibility and backward-compatibility constraints of the Arrow IPC format. The inclusion of 12-type round-trip integration tests serves as a definitive guardrail against regression.

---

## Consensus Summary

*Single reviewer -- consensus analysis requires 2+ reviewers.*

### Key Concerns (from Gemini)
1. **Decimal precision/scale mapping (MEDIUM)** -- ensure `length`/`precision` from schema configs are consistently passed to bridge for Decimal columns
2. **JVM startup race conditions (LOW)** -- exponential backoff is planned but integration tests should verify timeout fail-fast behavior
3. **Maven dependency (LOW)** -- Plan 04 handles this

### Actionable Suggestions
1. Add a Decimal test case with non-default precision (e.g., `(10, 2)`) to integration tests
2. Include Java-side logger output in JavaBridgeError messages for faster debugging
3. Log warning + default to `str` for incomplete schema columns instead of crashing
