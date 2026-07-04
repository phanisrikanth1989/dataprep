---
phase: 1
reviewers: [gemini]
reviewed_at: 2026-04-14
plans_reviewed: [01-01-PLAN.md, 01-02-PLAN.md, 01-03-PLAN.md, 01-04-PLAN.md, 01-05-PLAN.md, 01-06-PLAN.md, 01-07-PLAN.md]
---

# Cross-AI Plan Review — Phase 1

## Gemini Review

# Phase 1: Infrastructure Bug Fixes & Project Setup — Review

This review covers implementation plans `01-01-PLAN.md` through `01-07-PLAN.md` for the DataPrep engine infrastructure rewrite.

## Summary
The plans represent a high-quality, systematic approach to stabilizing the DataPrep engine. By choosing to rewrite the core infrastructure classes (`BaseComponent`, `GlobalMap`, `ContextManager`, `TriggerManager`) from scratch, the strategy eliminates systemic technical debt and "hallucinated" bugs while providing a clean, iterate-aware foundation for the remaining 11 phases. The sequencing (Waves 1-3) correctly respects dependencies, and the heavy emphasis on exhaustive TDD (Test-Driven Development) ensures that the non-negotiable feature parity with Talend is verifiable at the atomic level.

## Strengths
- **Surgical Bug Resolution:** The plans don't just "fix" bugs; they design them out of existence (e.g., fixing `!=` operator corruption via regex negative lookahead and eliminating config mutation via a strict snapshot/restore lifecycle).
- **Pandas 3.0 Readiness:** The research-backed decision to use `pd.Int64Dtype()` and respect Copy-on-Write (CoW) semantics in `BaseComponent` ensures the engine is compatible with the latest environment.
- **Robust Security Posture:** `TriggerManager` (Plan 04) correctly implements sandboxed evaluation with `__builtins__: {}`, mitigating the risks of executing Talend-derived expressions.
- **Standards-Driven Execution:** Creating `ENGINE_COMPONENT_PATTERN.md` (Plan 07) alongside the code ensures that the architectural "Golden Path" is documented immediately for use in subsequent phases, preventing future drift.
- **Verification Rigor:** Every plan includes both `verify` blocks and automated `acceptance_criteria`, with a total target of ~150+ unit tests across the infrastructure.

## Concerns
- **Component Breakage (LOW):** As per decision D-09, all ~50 existing components will break. Plan 06 handles this gracefully with a `try/except` in `engine.py`, but it means the engine will be in a "non-functional for production" state until components are rewritten. *Note: This is an accepted project constraint.*
- **Subjob Tracking Logic (LOW):** Plan 04 (`TriggerManager`) relies on `register_subjob` being called correctly to track `OnSubjobOk` status. Since the full execution loop rewrite is Phase 3, there is a risk that the Phase 1 tests for multi-component subjobs might be slightly synthetic until integrated with the actual Phase 3 loop.

## Suggestions
- **ContextManager Type Mapping:** In Plan 03, ensure that `id_Date` remains a string (as planned) but add a comment in the code explaining that date parsing is delegated to individual components (like `tFileInputDelimited`), as Talend date patterns are format-specific.
- **GlobalMap Performance:** While not an immediate concern for single-threaded execution, consider adding a `get_all()` test case in Plan 02 specifically to verify that the returned dictionary is a shallow copy, preventing external components from accidentally mutating the internal state.
- **Die-on-Error Property:** In Plan 05 (`BaseComponent`), verify that the `die_on_error` property is indeed accessible to subclasses so they can decide whether to catch and swallow specific data-level exceptions before the template method `execute()` catches the `Exception`.

## Risk Assessment: LOW
The overall risk is low because:
1. The plans are highly prescriptive and based on deep empirical research of the existing buggy codebase.
2. The "Rewrite from scratch" approach is safer than "Patching" for this specific codebase, as it allows for clean implementation of state management (iterate support).
3. The dependency on Waves (1 → 2 → 3) ensures no class is built on "sand."

**Final Verdict: Approved for execution.**

---

## Consensus Summary

*Single reviewer — consensus analysis requires 2+ reviewers.*

### Key Takeaways
- Plans are **approved for execution** with LOW risk
- Rewrite approach validated as safer than patching for this codebase
- Component breakage is an accepted constraint (D-09)
- 3 minor suggestions: date type comment, GlobalMap mutation safety test, die_on_error subclass access verification

### Actionable Items
- None blocking — all suggestions are LOW severity enhancements that can be incorporated during execution
