# V1 Engine Audit -- Methodology & Scoring Framework

*Last updated: 2026-05-11 after Phase 15.1 reconciliation*

## Purpose

This document describes the canonical methodology for auditing and fixing v1 engine components
against their Talend equivalents. The primary goal is to maintain a per-component parity record
between this engine's source and the Talaxie javajet reference, so that any future
bug-fix phase can plan work from a current, accurate baseline.

Phase 15.1 establishes this Talaxie-diff 8-step workflow as the canonical methodology going
forward. Steps 1-3 of the workflow (audit -> Talaxie research -> feature parity comparison) are
also the per-component reconciliation workflow used in Phase 15.1 specifically, producing an
updated doc artifact rather than a source patch.

## Audience

Engine contributors, future bug-fix phase planners, and anyone evaluating a new component's
parity surface against Talend. Assumes familiarity with the v1 engine component pattern
(see `docs/v1/patterns/ENGINE_COMPONENT_PATTERN.md`) and the Talend Open Studio component
model.

## Scope

- All 66 shipped v1 engine components (those registered in
  `src/v1/engine/component_registry.py`)
- 1 net-new audit doc authored in Phase 15.1 (`tFileOutputXML`)
- 3 cross-cutting docs: this file (`METHODOLOGY.md`), `SUMMARY_SCORECARD.md`,
  `CROSS_CUTTING_ISSUES.md`
- Converter (`src/converters/talend_to_v1/`) + engine coverage in a single per-component
  report
- 20 non-shipped components (Oracle/MSSQL connectors, control components, tForeach,
  tFileOutputEBCDIC, tHashOutput) are **excluded** from reconciliation
- **V1 only** -- reports must contain zero references to v2, V2, PyETL, v1-to-v2 converters,
  talend-to-v2 converters, or any v2 test files

---

## Priority Definitions

| Priority | Label | Definition | Action Required |
| ---------- | ------- | ------------ | ----------------- |
| **P0** | Critical | Causes incorrect results, data loss, runtime crash, or blocks production use. Jobs will fail or produce wrong output. | Must fix before any production migration |
| **P1** | Major | Significant feature gap or behavioral difference vs Talend. Likely to be hit in real jobs. Workaround may exist but is fragile. | Fix before production migration of affected jobs |
| **P2** | Moderate | Minor feature gap, edge case handling, cosmetic issue, naming inconsistency, or standards violation. May not be hit often but indicates quality gap. | Fix during hardening phase |
| **P3** | Low | Enhancement, optimization opportunity, code cleanup, or nice-to-have. Does not affect correctness. | Fix when time permits |

---

## Audit Dimensions

### 1. Talend Feature Baseline

For each component, we document the **complete** feature set of the Talend equivalent:

- All configuration parameters (Basic Settings, Advanced Settings)
- All connection types (input flows, output flows, triggers)
- All behavioral modes and options
- Schema handling capabilities
- GlobalMap variables produced
- Error handling behavior
- Known Talend quirks and edge cases

**Canonical source:** Talaxie GitHub javajet templates at
`github.com/Talaxie/tdi-studio-se/tree/master/main/plugins/
org.talend.designer.components.localprovider/components/<ComponentName>/
<ComponentName>_java.xml`. The javajet is the ground truth for what Talend generates and
therefore what the engine must replicate. Per-component Talaxie paths are enumerated in the
Phase 15.1 research document.

### 2. Converter Coverage (XML -> v1 JSON)

Does `src/converters/talend_to_v1/components/` correctly extract all Talend XML data for
this component?

| Check | Description |
| ------- | ------------- |
| **Parameter extraction** | Every `elementParameter` Talend emits is captured |
| **Parameter mapping** | Raw XML names correctly mapped to v1 config keys |
| **Schema extraction** | All `metadata/column` attributes captured (name, type, nullable, length, precision, pattern) |
| **Expression handling** | Java expressions detected and marked with `{{java}}` |
| **Context variable wrapping** | `context.var` references wrapped as `${context.var}` |
| **Table parameters** | Nested `elementValue` groups parsed correctly (grouping, ordering) |
| **Connection types** | All FLOW/REJECT/FILTER/ITERATE connectors mapped |
| **Quote/entity handling** | `&quot;`, `&#xD;&#xA;`, hex values decoded properly |
| **Missing parser method** | Does the dispatch in the converter registry have a valid target? |

### 3. Engine Feature Parity

Does the Python component produce the same results as the Talend component?

| Check | Description |
| ------- | ------------- |
| **Core functionality** | Does the common/happy path work correctly? |
| **All Talend parameters honored** | Every config option has corresponding logic |
| **Behavioral fidelity** | Output matches Talend row-for-row in common cases |
| **Reject/error flow** | Reject output matches Talend's error row format |
| **GlobalMap integration** | All expected `{id}_*` keys set correctly |
| **Statistics accuracy** | NB_LINE, NB_LINE_OK, NB_LINE_REJECT correct |
| **Schema enforcement** | Type coercion matches Talend's behavior |
| **Multi-flow support** | All output flow types (FLOW, REJECT, UNIQUE, DUPLICATE, etc.) routed correctly |
| **Iteration support** | Works correctly inside tFileList/tFlowToIterate loops |
| **Context variable resolution** | `${context.var}` and `context.var` patterns resolved at execution time |

Engine components are registered in `src/v1/engine/component_registry.py`. Only registered
components are in scope for audit. New components must follow the REGISTRY-driven registration
discipline documented in `docs/CONTRIBUTING.md`.

### 4. Code Quality

| Check | Description |
| ------- | ------------- |
| **Bugs** | Confirmed runtime errors, logic errors, typos |
| **Naming consistency** | Config keys, class names, parameter names follow conventions |
| **CONTRIBUTING.md compliance** | Follows `docs/CONTRIBUTING.md` and `docs/v1/patterns/ENGINE_COMPONENT_PATTERN.md` |
| **Error handling** | Proper exception types, consistent die_on_error, no bare except |
| **Dead code** | Unused methods, unreachable branches |
| **Debug artifacts** | `print()` statements, hardcoded paths, TODO comments |
| **Security** | Unsandboxed eval(), injection risks |
| **Docstrings/comments** | Adequate inline documentation |
| **Method contract** | `_validate_config()` returns `List[str]`, `_process()` returns `Dict[str, Any]` |

### 5. Performance & Memory

| Check | Description |
| ------- | ------------- |
| **Memory efficiency** | Unnecessary copies, full loads vs streaming |
| **Streaming support** | Works in HYBRID mode without data loss |
| **Scalability** | O(n) vs O(n^2) patterns, large file handling |
| **Type handling** | BigDecimal precision, nullable int, date parsing |
| **DataFrame operations** | Uses vectorized pandas vs row-by-row iterrows() |

The engine's base_component.py selects BATCH, STREAMING, or HYBRID mode automatically based
on input size. Stateful components (sort, aggregate) must be validated to produce correct
output in HYBRID mode where `_process()` is called per chunk.

### 6. Testing Coverage

| Check | Description |
| ------- | ------------- |
| **Unit tests exist** | Any test file for this component? |
| **Happy path tested** | Basic functionality verified |
| **Edge cases tested** | Empty input, null values, missing files, encoding |
| **Error paths tested** | die_on_error=True/False, invalid config |
| **Integration tested** | Component tested in a multi-step job |

Phase 14 established a 95% per-module line-coverage floor for all shipped components. This is
the Green threshold for the Testing dimension. Components at or above 95% per-module line
coverage are rated Green; below 95% is Yellow; zero test coverage is Red. See
`scripts/check_per_module_coverage.py` and `pyproject.toml` for the gate definition.

---

## Report Structure

### Per-Component Report (`docs/v1/audit/components/<ComponentName>.md`)

Each per-component audit report follows a fixed 11-section schema. This schema is the
canonical template; use `tFileInputDelimited.md` as the gold standard reference. The
11-section structure below is the authoritative guide for authoring and reviewing audit docs.

**Standard H2 sections in order:**

1. `## 1. Component Identity` -- field/value table (Talend Name, V1 Engine Class, Engine File,
   Converter Parser, Converter Dispatch, Registry Aliases, Category) plus `### Key Files`
   sub-table
2. `## 2. Scorecard` -- dimension/score/P0/P1/P2/P3/Details table (5 rows: Converter Coverage,
   Engine Feature Parity, Code Quality, Performance & Memory, Testing)
3. `## 3. Talend Feature Baseline` -- what the component does, Talaxie source URL, Basic
   Settings table, Advanced Settings, Connection Types, GlobalMap Variables, Behavioral Notes
4. `## 4. Converter Audit` -- per-parameter extraction status, needs_review enumeration,
   converter bug list (N/A for engine-native components)
5. `## 5. Engine Feature Parity` -- 5.1 feature implementation status table, 5.2 behavioral
   differences, 5.3 GlobalMap variable coverage
6. `## 6. Code Quality` -- 6.1 Bugs, 6.2 Naming Consistency, 6.3 Standards Compliance,
   6.4 Debug Artifacts, 6.5 Security, 6.6 Logging Quality, 6.7 Error Handling Quality,
   6.8 Type Hints
7. `## 7. Performance & Memory` -- PERF-* issues, memory management assessment
8. `## 8. Testing` -- test coverage assessment
9. `## 9. Issues Summary` -- by Priority table, by Category table, Cross-Cutting Issues table
10. `## 10. Recommendations` -- Immediate / Short-term / Long-term recommendations
11. `## 11. Risk Assessment` (some docs only) -- risk matrix, high-risk patterns, safe usage
    patterns
- `## Appendix A: Source References` -- source URL/path table
- `## Appendix B/C` -- variable per file (Cross-Cutting Issues, Engine Config Key Mapping, etc.)

**Resolved issues** use the strike-through + tag convention: `~~P0: description~~ [RESOLVED in
Phase N, commit <short_sha> (BUG-ID)]`. Net-new gaps discovered in 15.1 are tagged
`[NEW IN 15.1]` and appended to the existing P0/P1/P2/P3 blocks.

### Cross-Cutting Issues (`docs/v1/audit/CROSS_CUTTING_ISSUES.md`)

Issues that affect the entire engine, not a single component. The regenerated (Phase 15.1)
CROSS_CUTTING_ISSUES.md covers 7 H2 sections:

1. `## 1. Critical Engine Bugs (P0)` -- base_component / global_map crashes (all closed Phase 1)
2. `## 2. Engine Error Handling Flow` -- die_on_error matrix, exit code propagation, job status
3. `## 3. Trigger System Issues` -- Boolean regex, `!` corruption, RunIf eval, trigger firing
4. `## 4. Streaming Mode Issues` -- reject drop, HYBRID stateful, sort order, pivot, stats
5. `## 5. Context & Variable Resolution Issues` -- inverted nullable, config mutation,
   resolve_dict, context type loss
6. `## 6. Missing Component Implementations` -- converter-to-engine mapping gaps and impact
7. `## 7. Converter Systemic Issues` -- broken import chain, missing parser methods, type name
   mismatches, null safety

Issues closed by Phases 1-14 are struck through with `[RESOLVED in Phase N, commit <sha>]`
tags. Live issues retain their full description.

### Summary Scorecard (`docs/v1/audit/SUMMARY_SCORECARD.md`)

Traffic-light matrix and aggregate metrics across all audited components. The regenerated
(Phase 15.1) SUMMARY_SCORECARD.md covers 9 H2 sections:

1. `## Overview` -- scope, methodology note, `### Important Note on Issue Counts`
2. `## Traffic Light Matrix` -- per-component R/A/G table (66 shipped + 1 net-new)
3. `## Rating Distribution` -- `### Overall Component Ratings`, `### Per-Dimension Rating
   Distribution`
4. `## Priority Distribution` -- P0/P1/P2/P3 aggregate counts
5. `## Most Critical Components (Ranked by P0 Count)` -- surviving open P0s after Phase 14
6. `## Cross-Cutting Issues Summary` -- rolls up from CROSS_CUTTING_ISSUES.md
7. `## Component Categories` -- 7 H3 subsections by category (File I/O, Transform, Aggregate,
   Control, Database, Context, Iterate)
8. `## Key Findings` -- numbered findings reconciled against post-Phase-14 reality
9. `## Production Readiness Assessment` -- verdict and minimum fix list for production viability

---

## Scoring

| Score | Meaning |
| ------- | --------- |
| **R (Red)** | Broken, missing, or will produce wrong results |
| **Y (Yellow)** | Partially works, gaps exist, needs attention |
| **G (Green)** | Works correctly, meets standards |
| **N/A** | Not applicable to this component |

**Green threshold for Testing dimension:** >= 95% per-module line coverage (Phase 14 floor).
Components that passed the Phase 14 gate (`scripts/check_per_module_coverage.py coverage.json
--floor 95`) are rated Green for Testing. Those that were exempt from Phase 14 (non-shipped
components) retain their prior rating.

---

## Audit Process

### Pass 1: Initial Audit

The canonical audit-and-fix methodology is an **8-step component workflow**. Steps 1-3 are the
per-component reconciliation workflow (producing a doc artifact); steps 4-8 apply when a fix
phase is warranted.

1. **Audit** -- read the existing per-component audit doc. Catalog all open P0/P1/P2/P3 issues.
   Note which issues have been addressed by Phases 1-14 commits.
2. **Talaxie research** -- read the Talaxie javajet template for the component
   (`github.com/Talaxie/tdi-studio-se/.../<ComponentName>/<ComponentName>_java.xml`).
   Confirm or update the "Talend Feature Baseline" section.
3. **Feature parity comparison** -- diff current `src/v1/engine/components/<cat>/<component>.py`
   and `src/converters/talend_to_v1/components/<cat>/<component>.py` against the Talaxie
   reference. Identify gaps, regressions, or improvements since the audit was written.
4. **Plan fix** -- design the fix approach: patch, rewrite, or defer. Scope per-component
   or cross-cutting as appropriate.
5. **Review plan** -- adversarial review (see Pass 2 below) before coding.
6. **Code fix** -- implement the plan. Follow `docs/v1/patterns/ENGINE_COMPONENT_PATTERN.md`
   and `docs/CONTRIBUTING.md`.
7. **Verify** -- run the test suite (`pytest tests/ -m "not oracle"`). Confirm the Phase 14
   95% per-module floor is not regressed.
8. **Close audit issue** -- update the per-component audit doc: strike through the fixed issue
   with `[RESOLVED in Phase N, commit <short_sha> (BUG-ID)]` and update the Section 2
   Scorecard.

**Phase 15.1 scope:** Steps 1-3 only. Phase 15.1 produces reconciled doc artifacts; no source
patches. Source fixes were delivered in Phases 1-14.

### Pass 2: Adversarial Review

Before any fix is coded (step 6), a separate review reads the audit report AND the source
code with the mindset: "Find at least 3-5 issues the report missed."

Focuses on:
- Edge cases and cross-class interactions (e.g., HYBRID mode with stateful components)
- Behavioral subtleties (e.g., Talend's exact NaN vs None handling)
- Cross-cutting bug interactions (e.g., `_update_global_map()` crash masking other errors)

**Verify-before-claim discipline (D-C3):** Every cited class, function, file path, line number,
and Talaxie reference must be grep-confirmed against the live repo before the report or commit
lands. Stale line numbers from earlier audits are acceptable in struck-through closed-issue
blocks; they must not appear in live open-issue descriptions.

### Mandatory Edge-Case Checklist

Every audit MUST check these cross-cutting concerns:

| Check | Why |
| ------- | ----- |
| NaN handling (`pd.isna()` vs `is None`) | pandas uses NaN, not None -- `value is None` misses NaN |
| Empty strings in config keys | Can produce crashes (e.g., `str.split("")` raises ValueError) |
| Empty DataFrame input (0 rows with columns vs None) | Returning `pd.DataFrame()` loses column schema |
| HYBRID streaming mode via base class | Base class chunks and calls `_process()` per chunk -- stateful components break |
| `_update_global_map()` interaction | Was the base-class crash fixed? Confirm Phase 1 ENG-01 applies. |
| Component status reaching SUCCESS | Verify status transitions in base_component.py execute() reach SUCCESS correctly |
| Thread safety for parallel subjobs | ContextManager, GlobalMap, JavaBridge are shared -- no locking |
| Type demotion through iterrows/Series reconstruction | `Decimal` -> `float64`, `datetime64` -> `object` |
| `validate_schema` nullable logic | Confirm Phase 1 ENG-19 fix is in place (was inverted pre-Phase-1) |
| `_validate_config()` called or dead code | Most components define it but the base class does not call it automatically |

---

## Known Cross-Cutting Bugs

The full inventory of cross-cutting engine bugs -- covering base_component.py, GlobalMap,
trigger evaluation, streaming mode, context resolution, missing components, and converter
systemic issues -- is maintained in `docs/v1/audit/CROSS_CUTTING_ISSUES.md`.

That document was regenerated in Phase 15.1 (Plan 15.1-10) to reflect post-Phase-14 reality:
all Phase 1 critical bugs are struck through as resolved; surviving live issues are retained
with their full descriptions. The 7 H2 sections in CROSS_CUTTING_ISSUES.md map directly to
the audit dimensions above (Critical Bugs, Error Handling, Triggers, Streaming, Context,
Missing Components, Converter Systemic).

For per-component cross-cutting bug references, each audit doc's Section 9 (Issues Summary)
contains a "Cross-Cutting Issues" sub-table that links to the relevant H3 in
CROSS_CUTTING_ISSUES.md.
