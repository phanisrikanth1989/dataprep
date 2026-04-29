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
- **Revision 2 correction:** This recommendation was based on incorrect Talend parity claims. Talaxie source verification (see "Auto-Resolved Pre-Plan Open Questions revision 2" below) shows tJavaRow has no native REJECT and tFilterRow has no errorCode column. D-14 and D-16 rewritten in place.

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
- **Revision 2 correction:** Q2's "Option A" framing was the wrong question entirely. See revision 2 entries below.

## Auto-Resolved -- Pre-Plan Open Questions (revision 2, 2026-04-29)

Direct verification of the Talaxie tdi-studio-se source (the canonical Talend reference) overturned three claims that revision 1 / Q2 / D-14 / D-16 were built on. The user pushed back on accepting prior research at face value with the guidance: **"Don't have faith in audit docs alone -- they might be stale."** Revision 2 is the correction. We do not re-invent semantics; match Talend exactly where verified, mark DataPrep extensions explicitly, and don't claim parity for invented behavior.

### Verified findings (primary-source Talaxie verification)

**Finding 1: Talend tJavaRow has NO native REJECT, period.**
- `tJavaRow_java.xml` connectors: only `<CONNECTOR CTYPE="FLOW" MAX_INPUT="1" MAX_OUTPUT="1"/>`. No `NAME="REJECT"`. No DIE_ON_ERROR parameter.
- `tJavaRow_main.javajet` row-loop body is literally just `<%=code%>` followed by `nb_line_<%=cid %>++;`. No try/catch, no error-routing, no REJECT row construction.
- Uncaught exceptions propagate up the call stack; the parent DIE_ON_ERROR (on tFlowToIterate or similar) decides job termination.
- tJavaFlex is identical (same Custom_Code family).

**Finding 2: Talend reject schemas have NO errorCode field.**
- `tFilterRow_java.xml` reject schema: ONE column only -- `errorMessage` (`id_String`, length 255). No errorCode.
- `tMap_main.inc.javajet` only emits `errorMessage` (String, `e.getMessage()`) and `errorStackTrace` (String). No errorCode.
- Phase 7.1's tFilterRow rewrite may have invented `errorCode` -- that's a separate audit; it's NOT a Talend convention.

**Finding 3: Talend's tJava is code-block-only, no row iteration.**
- `tJava_begin.javajet` is one line: `<%=CODE%>`. No row loop, no input_row/output_row reference.
- FLOW connectors exist for graph wiring but the component doesn't transform row data.

### Existing legacy code reality

| Component | Current REJECT behavior | Current passthrough behavior |
|---|---|---|
| `java_component.py` (one-shot) | NO REJECT (errors propagate) | YES -- `return {'main': input_data}` line 102, passes input unchanged |
| `python_component.py` (one-shot) | NO REJECT (errors propagate) | YES -- similar passthrough |
| `java_row_component.py` | NO REJECT today (line 96-98 re-raises) | N/A -- transforms rows |
| `python_row_component.py` | HAS REJECT with `errorCode='PYTHON_ERROR'` (string) -- DataPrep extension | N/A -- transforms rows |

### Verdicts

**Q-REJECT verdict: Option B-modified.**

- `python_row_component`: KEEP existing REJECT as a DataPrep extension. SIMPLIFY column schema:
  - Reject row contains the original input row's columns + `errorMessage` (str) appended.
  - DROP `errorCode` entirely. Drop the legacy `errorCode='PYTHON_ERROR'` string. Talend has no errorCode; we won't invent one.
  - Per-row error routing only (legacy already does this correctly). Continue processing unless `die_on_error=True`.
- `java_row_component`: NO REJECT. Errors propagate up via `_process` raise. This is BOTH Talend parity AND zero behavior change vs legacy. Plans must:
  - Drop the entire REJECT-flow design (TestRejectFlow class, batch-level routing, errorCode/errorMessage column construction).
  - Drop all references to "Q2 Option A" / "v1 limitation" / "future BRDG-* phase" / batch-level reject.
  - Match the legacy behavior: catch any bridge exception in `_process`, log via component_id prefix, re-raise. BaseComponent's existing `die_on_error` semantics handle fatal-vs-continue.
- `java_component` / `python_component` (one-shot): NO REJECT. Errors propagate. Match legacy.

**Q-PASSTHROUGH verdict: passthrough is the default-and-only behavior for one-shot variants.**

- This isn't a "Talend parity" question -- it's a DataPrep data-flow-graph question. Talend's tJava sits at the begin-block position and doesn't iterate. In DataPrep's data-flow engine, the one-shot component still has an input and output flow connector (per the existing engine model and per Talaxie's tJava_java.xml FLOW connectors), so the natural behavior is "input passes through unchanged because the component doesn't transform rows."
- `java_component` (one-shot): when `input_data` is provided, pass it through unchanged as `result['main']`. When no input, return empty DataFrame. NO toggle.
- `python_component` (one-shot): same behavior.
- Document this as "DataPrep's data-flow equivalent of Talend's begin-block: the component executes the user code once, and any input rows pass through unmodified because the component is not a row transformer."

### CONTEXT.md updates applied

- D-14 rewritten in place -- per-component REJECT matrix (python_row only; java_row no REJECT; one-shots no REJECT).
- D-16 rewritten in place -- single `errorMessage` column for `python_row_component`; no `errorCode`.
- D-29 added -- one-shot passthrough as DataPrep data-flow semantic (not Talend parity claim).
- Deferred Ideas extended -- explicit note that REJECT for `java_row_component` is not on v1 roadmap.

### JROW-02 reinterpretation

REQUIREMENTS.md JROW-02 reads: "Implement REJECT output flow for per-row Java execution errors." Talend has no native REJECT for tJavaRow (verified above), so JROW-02's intent is satisfied by "errors are properly raised and surfaced (no silent failure)" rather than a REJECT connector. This reinterpretation is recorded in 08-PHASE-SUMMARY.md (Plan 06). If the user disagrees with this reinterpretation, a DataPrep-specific Java reject contract becomes a v2 enhancement after Phase 8 (would require a new BRDG-* bridge protocol variant).

### Plan changes applied (revision 2)

- **Plan 03 (java_row_component):** REJECT-flow design entirely removed. Objective simplified to "Rewrite java_row_component cleanly to BaseComponent + Rule 11/12 contract; preserve existing semantics (errors propagate up via _process raise); add `imports` prepend support; add @pytest.mark.java integration tests." TestRejectFlow class deleted. Threat_model entry T-08-13 updated to reflect "no reject path" parity.
- **Plan 04 (python_row_component):** TestRejectFlow class kept but assertions updated -- reject DataFrame has only `errorMessage` column (not `errorCode`). All `errorCode=1` integer references and `errorCode='PYTHON_ERROR'` string references dropped from source and tests.
- **Plan 06 (PHASE-SUMMARY):** "Q2 Option A v1 limitation" framing replaced with the corrected narrative. Added a "Talend parity claims correction" section noting (a) errorCode is not a Talend field (dropped), (b) tJava is code-block-only (passthrough is DataPrep data-flow semantic, not Talend feature), (c) D-14 and D-16 superseded with corrected versions, (d) JROW-02 reinterpretation.
- **Plan 02 (python_component) and Plan 01 (java_component):** confirm one-shot passthrough is in the implementation per D-29.
- **Plan 05 (smoke tests):** dropped any reject-flow integration test for java_row_component; kept python_row REJECT smoke test but with errorMessage-only schema.

## Deferred Ideas Captured

- R / Groovy / arbitrary-language code components -- separate phase if ever needed
- In-process JVM (replacing subprocess JavaBridge) -- separate phase
- Java-side sandboxing -- not in scope; would diverge from Talend parity
- DSL / templating on top of code components -- separate phase
- Performance optimization beyond compile-once-exec-per-row -- separate phase if measurements demand it
- REJECT flow for java_row_component -- Talend has none; not on v1 roadmap. If ever needed, a future BRDG-* phase would add an `executeJavaRowWithReject` bridge variant.

## External Research

None this session for revision 1. Revision 2 used direct primary-source verification of Talaxie tdi-studio-se source (`tJavaRow_java.xml`, `tJavaRow_main.javajet`, `tFilterRow_java.xml`, `tMap_main.inc.javajet`, `tJava_begin.javajet`). The user explicitly directed: "Don't have faith in audit docs alone -- they might be stale." This is the correction.

## Notes

- This is `--auto` mode: every decision is Claude's recommendation. The user is expected to review CONTEXT.md before `/gsd-plan-phase 8` and override any decision they disagree with by editing CONTEXT.md directly.
- Per the user's autonomous-run instruction, the workflow stops at the Phase 8 boundary AFTER writing CONTEXT.md. Plan-phase / execute-phase are the user's call to invoke.
- Revision 2 (2026-04-29) applied the Talaxie verification correction across CONTEXT.md (D-14, D-16, D-29) and Plans 01-06. The plans now make honest Talend parity claims and mark DataPrep extensions explicitly.
