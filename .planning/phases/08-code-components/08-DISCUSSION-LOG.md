# Phase 8: Code Components - Discussion Log (auto mode)

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions captured in `08-CONTEXT.md` -- this log preserves the analysis.

**Date:** 2026-04-29
**Phase:** 08-code-components
**Mode:** discuss --auto (Claude picked recommended defaults; no user interaction)

## Areas Analyzed (auto-selected per --auto)

1. Approach to existing partial implementations
2. Component structure standardization (JAVA-03, JROW-04, PYCO-01, PYRO-01)
3. Imports support mechanism (JAVA-01, JROW-01)
4. Shared utilities consolidation (PYCO-03)
5. Secure Python execution namespace (PYCO-02)
6. Per-row REJECT flow (JROW-02, PYRO-03)
7. Compiled Python execution (PYRO-02)
8. Java bridge integration (JAVA-02, JROW-03)
9. Test coverage strategy (TEST-07)
10. Configuration / context-var resolution
11. Error type contract

## Recommended Defaults Applied (auto mode)

For each area, Claude picked the recommended choice based on prior context (PROJECT.md, MANUAL_COMPONENT_AUTHORING.md Rules 11+12, Phase 7.1 / 7.2 SUMMARY + LEARNINGS, quick task 260429-hc2, project memory rules around fix-source-no-fallbacks / rewrite-over-patch / test-real-bridge / ASCII-only).

### 1. Approach to existing partial implementations
- **Recommendation:** Rewrite cleanly to BaseComponent + Rule 11/12 contract (D-01, D-02)
- **Why:** Memory rule `feedback_rewrite_over_patch` says prefer clean rewrites for systemic issues. The 4 partial files predate Phase 7.1 standardization and the new Rule 12; patching in place is high-risk.

### 2. Component structure standardization
- **Recommendation:** Each component is its own file; shared mixin for `_get_context_dict`; no supercomponent abstraction (D-03 to D-06)
- **Why:** Phase 7.1 third-strike rewrite of `file_output_delimited.py` is the canonical shape. Don't reinvent. Rule 12 forbids content checks in `_validate_config`.

### 3. Imports support
- **Recommendation:** Prepend `imports` to `java_code` with newline; bridge handles compile errors (D-07, D-08)
- **Why:** Matches REQUIREMENTS.md exact wording (JAVA-01, JROW-01). Bridge is the natural compile-error surface; no re-implementation needed.

### 4. Shared utilities
- **Recommendation:** New `_code_component_mixin.py` with `CodeComponentMixin` (D-09, D-10)
- **Why:** `BaseComponent` should not carry code-component-specific logic. Mixin is the right scope; Python multiple inheritance is idiomatic for this case.

### 5. Secure Python execution namespace
- **Recommendation:** Explicit allow-list: pandas, numpy, datetime, json, re, math, decimal.Decimal, plus `context` / `globalMap` / row proxies. Block os, sys, subprocess, __import__, open, exec, eval, compile (D-11 to D-13)
- **Why:** PYCO-02 says "remove os and sys". An allow-list is more secure than a deny-list (defense in depth). Document as breaking change with no compatibility shim per `feedback_fix_source_no_fallbacks`.

### 6. Per-row REJECT flow
- **Recommendation:** Append `errorMessage` (str) + `errorCode` (int=1 default) columns; continue unless die_on_error=True (D-14 to D-16)
- **Why:** Reuses the tFilterRow REJECT contract from Phase 7.1. Same column casing/conventions. Talend parity preserved.

### 7. Compiled Python execution (PYRO-02)
- **Recommendation:** `compile()` once at first row; reuse compiled code object; rebuild exec namespace per row (cheap dict construction; expensive parser work amortized) (D-17, D-18)
- **Why:** REQUIREMENTS.md PYRO-02 says "compile once outside loop, exec per row". Mirrors Talend's javac-once pattern.

### 8. Java bridge integration
- **Recommendation:** Use existing JavaBridge protocol unchanged; bidirectional sync via JavaBridgeManager (D-19 to D-21)
- **Why:** Phase 2 + Phase 5.1 verified. No protocol changes per CLAUDE.md constraint. Memory rule `feedback_test_real_bridge` mandates @pytest.mark.java integration tests.

### 9. Test coverage
- **Recommendation:** Reuse Phase 7.2 patterns (manual config-population fixture; three-test-per-fix; @pytest.mark.java for Java side) (D-22 to D-24)
- **Why:** Phase 7.2 LEARNINGS established these patterns. Don't reinvent. test_filter_rows.py is the structural reference.

### 10. Context-var resolution
- **Recommendation:** Inherit BaseComponent's three-phase resolution; code components are consumers, not resolvers (D-25, D-26)
- **Why:** Single source of truth. Code-component-specific resolution would create a second resolver and drift.

### 11. Error type contract
- **Recommendation:** ConfigurationError for resolved-value validation failures placed BEFORE broad try/except in _process; ComponentExecutionError only when die_on_error=True for per-row exec failures (D-27, D-28)
- **Why:** Phase 7.2 send_mail lesson -- broad try/except re-wraps ConfigurationError as ComponentExecutionError, breaking caller contracts. Place new raises outside the broad block.

## Auto-Resolved (no user corrections this session)

All decisions were captured at the recommended-default level. No "Other" / "you decide" branches required.

## Auto-Resolved -- Pre-Plan Open Questions (revision 1, 2026-04-29)

The following ambiguities were surfaced by RESEARCH.md after CONTEXT.md was written. They were pre-resolved at planning time before any executor work, and are recorded here for the audit trail. Both choices are reflected in the locked plans (08-01..06) and the in-place CONTEXT.md edits.

- **Q1 (D-26 supersession):** RESEARCH.md Pitfall #1 verified that `ContextManager.SKIP_RESOLUTION_KEYS` (`src/v1/engine/context_manager.py:37-41`, ENG-18) explicitly excludes `python_code`, `java_code`, and `imports` from ${context.X} resolution. CONTEXT.md D-26 ("java_code and python_code may themselves contain ${context.X} references that resolve to substring values") is therefore INCORRECT. Resolution: code bodies pass through verbatim; user code reads context programmatically -- via the `context['VAR_NAME']` dict in the Python exec namespace, and via the bridge's bidirectional sync (`globalMap` Groovy binding) for Java. D-26 is superseded; the supersession is recorded in each plan's module docstring and called out load-bearingly in 08-PHASE-SUMMARY.md (Plan 06).

- **Q2 (JROW-02 REJECT semantics):** Pre-resolved as **Option A (batch-level reject for `java_row_component`)** per researcher recommendation in RESEARCH.md Pitfall #2 + Open Question 1. The existing `JavaBridge.executeJavaRow` (`JavaBridge.java:209-247`) is all-or-nothing -- on any per-row exception it throws `RuntimeException("Error processing row N", cause)` and the whole batch fails. Per D-19 the bridge protocol is locked for Phase 8. Trade-off acknowledged: Talend's native tJavaRow has no REJECT flow at all, so the Phase 8 reject contract is a DataPrep enhancement that we ship in v1 with REDUCED FIDELITY for the Java side (entire batch -> reject when bridge raises); full per-row fidelity for tJavaRow is deferred to a future bridge-protocol phase that adds an `executeJavaRowWithReject` variant. Per-row REJECT is preserved for `python_row_component` (no bridge constraint). CONTEXT.md D-14 has been updated in place to document this per-component divergence.

## Deferred Ideas Captured

- R / Groovy / arbitrary-language code components -- separate phase if ever needed
- In-process JVM (replacing subprocess JavaBridge) -- separate phase
- Java-side sandboxing -- not in scope; would diverge from Talend parity
- DSL / templating on top of code components -- separate phase
- Performance optimization beyond compile-once-exec-per-row -- separate phase if measurements demand it

## External Research

None this session. All decisions could be derived from prior context (Phase 7.1, 7.2, quick task 260429-hc2, REQUIREMENTS.md, Talaxie verification done in earlier sessions). If planning surfaces a Talend semantic ambiguity, planner spawns a focused researcher then.

## Notes

- This is `--auto` mode: every decision is Claude's recommendation. The user is expected to review CONTEXT.md before `/gsd-plan-phase 8` and override any decision they disagree with by editing CONTEXT.md directly.
- Per the user's autonomous-run instruction, the workflow stops at the Phase 8 boundary AFTER writing CONTEXT.md. Plan-phase / execute-phase are the user's call to invoke.
