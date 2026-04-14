---
phase: 3
reviewers: [gemini]
reviewed_at: 2026-04-14T23:30:00Z
plans_reviewed: [03-01-PLAN.md, 03-02-PLAN.md, 03-03-PLAN.md, 03-04-PLAN.md]
---

# Cross-AI Plan Review -- Phase 3

## Gemini Review

# Phase 3: Execution Loop Restructure -- Plan Review

The following review assesses the implementation plans (03-01 through 03-04) for restructuring the DataPrep ETL engine's execution orchestration.

## Summary

The Phase 3 plans provide a clean, modular decomposition of the currently monolithic and fragile ETL execution loop. By splitting responsibilities into a static `ExecutionPlan`, a state-managing `OutputRouter`, a decoupled `ComponentRegistry`, and a specialized `Executor`, the engine transitions from a "guess-and-check" BFS queue to a deterministic, pre-validated DAG execution model. The use of stdlib `graphlib` for topological sorting and the introduction of a `StubComponent` fixture are high-signal architectural improvements that significantly lower the risk of regressions.

## Strengths

- **Clean Decomposition (D-01):** The 5-file split creates clear boundaries between graph analysis, data routing, and execution orchestration, making the system much easier to debug and extend.
- **Deterministic Ordering:** Replacing the dynamic BFS queue with `graphlib.TopologicalSorter` ensures reliable component execution order and provides robust, stdlib-backed cycle detection.
- **High-Fidelity Test Strategy:** The `StubComponent` fixture (D-17) allows for exhaustive testing of orchestration logic (triggers, error propagation, stalls) without the noise or dependencies of real component implementations.
- **Architectural Consistency:** Adopting the converter's decorator-based registry pattern (D-02) eliminates coupled imports and brings the engine into alignment with the project's established patterns.
- **Proactive Validation:** Pre-execution graph validation (D-06) ensures "fail-fast" behavior for unreachable components or circular dependencies before any data processing begins.

## Concerns

- **Trigger Timing Precision (MEDIUM):** In Plan 03-04, the `Executor` must be extremely precise about when `OnSubjobOk` fires (after *all* subjob components) vs. `OnComponentOk` (after a specific component). Any regression here will break jobs relying on side effects from intermediate components.
- **Cross-Subjob Flow Lifecycle (MEDIUM):** Plan 03-03/03-04 mention clearing flows after subjob completion (D-16). If an `OnComponentOk` trigger starts a component in a *different* subjob that consumes a flow from the current subjob, clearing flows prematurely will cause data loss for the triggered component.
- **Actionable Stall Diagnostics (LOW):** While stall detection (D-07) is included, the diagnostics must be highly actionable. If a job stalls, the user needs to know exactly which component is stuck and which specific input flow it is waiting on.
- **Recursion Depth (LOW):** The recursive trigger firing pattern in `_fire_subjob_triggers` is elegant but should be monitored for extremely long linear subjob chains to avoid hitting Python's recursion limit (though this is rare in Talend).

## Suggestions

- **Refine Flow Clearing Logic:** In `OutputRouter.clear_subjob_flows`, add a check (or metadata in `ExecutionPlan`) to identify flows that cross subjob boundaries. Only clear flows where all consumers are confirmed complete.
- **Enhanced Stall Error Message:** Ensure the `ConfigurationError` raised by `Executor` includes a comparison between the `ExecutionPlan`'s expected components and the `executed_components` set, specifically naming the "stuck" component and its missing inputs.
- **Registry Idempotency:** Ensure the `REGISTRY.register()` decorator remains idempotent (as drafted in Plan 01) to handle potential double-imports in complex package structures without crashing.
- **Auto-Detection Logging:** When `ExecutionPlan` falls back to auto-detecting subjobs (if the `subjobs` dict is missing from JSON), log an `INFO` message indicating the engine is inferring the job structure.

## Risk Assessment: LOW

The architectural direction is sound and follows senior engineering standards. The use of standard library components (`graphlib`, `dataclasses`) reduces the "hand-rolled" logic surface area. The phased approach -- building the data structures first (01-03) and wiring them together last (04) -- is the correct way to handle a core engine rewrite. The heavy emphasis on `StubComponent` integration testing provides a strong safety net for the most complex orchestration edge cases.

---

## Consensus Summary

*Single reviewer -- consensus analysis requires 2+ reviewers.*

### Key Concerns from Gemini
1. **Cross-Subjob Flow Lifecycle (MEDIUM):** Clearing flows after subjob completion could cause data loss if an OnComponentOk trigger starts a component in a different subjob that consumes a flow from the completing subjob. OutputRouter should check for cross-subjob flow consumers before clearing.
2. **Trigger Timing Precision (MEDIUM):** Executor must be precise about OnSubjobOk (all components done) vs OnComponentOk (single component done). Regression risk.
3. **Actionable Stall Diagnostics (LOW):** Stall error messages should name the stuck component and its missing input flows specifically.
4. **Recursion Depth (LOW):** Recursive trigger firing could hit Python recursion limit on very long chains (unlikely in practice).

### Actionable Improvements
- Refine `clear_subjob_flows` to check for cross-subjob consumers before clearing
- Include stuck component + missing inputs in stall error messages
- Ensure registry decorator is idempotent for double-import safety
- Log INFO when falling back to auto-detection of subjobs
